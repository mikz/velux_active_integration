#!/usr/bin/env python3
"""Run a bounded, read-only cloud smoke from ZIP members in an isolated process.

M0 prepares this runner. Only a final frozen M7 ZIP run closes artifact proof.
No credentials, provider strings, payloads, IDs, tokens, or raw errors are printed.
"""

import argparse
import asyncio
import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
import logging
import subprocess
import sys
import tempfile
import types
import zipfile
from pathlib import Path
from urllib.parse import urlsplit


def extract_verified(archive: Path, destination: Path) -> dict[str, str]:
    """Reject unexpected paths/duplicates and hash the bytes actually extracted."""
    members = {}
    with zipfile.ZipFile(archive) as payload:
        for info in payload.infolist():
            path = Path(info.filename)
            if (
                info.is_dir()
                or path.is_absolute()
                or ".." in path.parts
                or info.filename in members
            ):
                raise ValueError("Invalid archive member")
            data = payload.read(info)
            target = destination / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            members[info.filename] = hashlib.sha256(data).hexdigest()
    return members


def load_archive_api(root: Path, members: dict[str, str]):
    """Namespace paths point only at extracted members; checkout imports cannot satisfy them."""
    for name in ("custom_components", "custom_components.velux_active"):
        namespace = types.ModuleType(name)
        namespace.__path__ = [str(root)]
        namespace.__spec__ = importlib.util.spec_from_loader(name, loader=None, is_package=True)
        sys.modules[name] = namespace
    api = importlib.import_module("custom_components.velux_active.api")
    origins = {}
    for name, module in tuple(sys.modules.items()):
        if name.startswith("custom_components.velux_active."):
            origin = Path(module.__file__).resolve()
            member = origin.relative_to(root).as_posix()
            digest = hashlib.sha256(origin.read_bytes()).hexdigest()
            if digest != members.get(member):
                raise ValueError("Imported module is not a verified ZIP member")
            origins[name] = {"member": member, "sha256": digest}
    if not origins:
        raise ValueError("No artifact module was imported")
    return api, origins


async def check(api_module, credentials: dict, base_url: str | None) -> dict:
    import aiohttp

    report = {}
    async with aiohttp.ClientSession() as session:
        api = api_module.VeluxActiveAPI(session, **({"base_url": base_url} if base_url else {}))
        await api.authenticate(credentials["username"], credentials["password"])
        report["authenticated"] = True
        homes = await api.get_home_data()
        report["home_count"] = len(homes)
        if not homes:
            raise ValueError("Status proof requires a nonempty inventory")
        report["parsed_device_count"] = 0
        for home in homes:
            modules = await api.get_home_statuses(home)
            report["parsed_device_count"] += sum(
                api_module.device_from_module(m) is not None for m in modules
            )
        api.auth_token = await api.refresh_access_token(api.auth_token)
        report["token_refreshed"] = True
        report["refreshed_module_count"] = 0
        for home in homes:
            report["refreshed_module_count"] += len(await api.get_home_statuses(home))
        report["status_refreshed"] = True
    return report


def child(args) -> dict:
    logging.disable(logging.CRITICAL)
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary).resolve()
        members = extract_verified(args.archive, root)
        manifest = json.loads((root / "manifest.json").read_text())
        if manifest["requirements"]:
            raise ValueError("Distributed dependency proof is not prepared yet")
        api, origins = load_archive_api(root, members)
        credentials = json.loads(args.credentials.read_text())
        report = asyncio.run(check(api, credentials, args.synthetic_url))
        report.update(
            status="passed",
            zip_sha256=hashlib.sha256(args.archive.read_bytes()).hexdigest(),
            integration_version=manifest["version"],
            isolated=sys.flags.isolated == 1,
            artifact_modules=origins,
            dependency_proof="inline_client_intermediate",
            aiohttp_version=importlib.metadata.version("aiohttp"),
        )
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--synthetic-url", help="Synthetic tests only: loopback HTTP endpoint")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.synthetic_url and urlsplit(args.synthetic_url).hostname not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        raise SystemExit("Synthetic URL must be loopback")
    if args.child:
        try:
            report = child(args)
        except Exception as error:
            report = {"status": "failed", "error_type": type(error).__name__}
        print(json.dumps(report, sort_keys=True))
        return 0 if report["status"] == "passed" else 1
    command = [
        sys.executable,
        "-I",
        str(Path(__file__).resolve()),
        "--child",
        "--archive",
        str(args.archive.resolve()),
        "--credentials",
        str(args.credentials.resolve()),
    ]
    if args.synthetic_url:
        command.extend(["--synthetic-url", args.synthetic_url])
    with tempfile.TemporaryDirectory() as temporary:
        result = subprocess.run(
            command, cwd=temporary, capture_output=True, text=True, timeout=180, check=False
        )
    # Only the bounded structured child result leaves the runner; stderr is never echoed.
    try:
        report = json.loads(result.stdout)
    except ValueError, TypeError:
        report = {"status": "failed", "error_type": "RunnerFailure"}
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
