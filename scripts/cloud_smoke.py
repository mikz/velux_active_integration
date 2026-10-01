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
import sysconfig
import tempfile
import types
import zipfile
from email.parser import BytesParser
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


def verify_dependency(wheel: Path, requirements: list[str]) -> dict:
    """Require installed wheel bytes; an editable checkout cannot satisfy this proof."""
    distribution = importlib.metadata.distribution("velux-active-client")
    direct_url = json.loads(distribution.read_text("direct_url.json") or "{}")
    if direct_url.get("dir_info", {}).get("editable"):
        raise ValueError("Editable source is not an installed artifact")
    if requirements != [f"velux-active-client=={distribution.version}"]:
        raise ValueError("Dependency version does not match the archive requirement")
    installed = Path(distribution.locate_file("velux_active_client")).resolve()
    install_roots = {Path(sysconfig.get_path(key)).resolve() for key in ("purelib", "platlib")}
    if not any(installed.is_relative_to(root) for root in install_roots):
        raise ValueError("Dependency origin is outside the prepared interpreter install roots")
    modules = {}
    member_hashes = {}
    with zipfile.ZipFile(wheel) as package:
        metadata_files = [
            name for name in package.namelist() if name.endswith(".dist-info/METADATA")
        ]
        if len(metadata_files) != 1:
            raise ValueError("Wheel metadata is not unique")
        metadata = BytesParser().parsebytes(package.read(metadata_files[0]))
        if metadata["Version"] != distribution.version or metadata["Name"] != "velux-active-client":
            raise ValueError("Supplied wheel metadata does not match installed dependency")
        for member in package.namelist():
            if member.startswith("velux_active_client/") and not member.endswith("/"):
                relative = Path(member).relative_to("velux_active_client")
                digest = hashlib.sha256(package.read(member)).hexdigest()
                if hashlib.sha256((installed / relative).read_bytes()).hexdigest() != digest:
                    raise ValueError("Installed dependency member differs from the wheel")
                member_hashes[member] = digest
        for name, module in tuple(sys.modules.items()):
            if name == "velux_active_client" or name.startswith("velux_active_client."):
                origin = Path(module.__file__).resolve()
                member = "velux_active_client/" + origin.relative_to(installed).as_posix()
                digest = hashlib.sha256(origin.read_bytes()).hexdigest()
                if digest != hashlib.sha256(package.read(member)).hexdigest():
                    raise ValueError("Installed dependency differs from the supplied wheel")
                modules[name] = {"member": member, "sha256": digest}
        if not modules or not (installed / "py.typed").is_file():
            raise ValueError("Typed installed dependency proof is missing")
    return {
        "name": "velux-active-client",
        "version": distribution.version,
        "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "modules": modules,
        "member_hashes": member_hashes,
    }


async def check(
    api_module, credentials: dict, base_url: str | None, known_registry_ids: set[str] | None = None
) -> dict:
    import aiohttp

    report = {}

    def rain_observations(modules):
        gateways = [
            device
            for module in modules
            if isinstance(
                device := api_module.device_from_module(module), api_module.VeluxGatewayData
            )
        ]
        exact = sum(type(device.is_raining) is bool for device in gateways)
        usable = sum(
            type(device.is_raining) is bool and device.reachable is not False for device in gateways
        )
        return {
            "gateway_count": len(gateways),
            "exact_boolean_rain_count": exact,
            "missing_or_null_rain_count": len(gateways) - exact,
            "reachable_with_known_rain_count": usable,
            "rain_available": usable > 0,
        }

    async with aiohttp.ClientSession() as session:
        api = api_module.VeluxActiveAPI(session, **({"base_url": base_url} if base_url else {}))
        await api.authenticate(credentials["username"], credentials["password"])
        report["authenticated"] = True
        homes = await api.get_home_data()
        report["home_count"] = len(homes)
        if not homes:
            raise ValueError("Status proof requires a nonempty inventory")
        # The typed client accepts only explicit, atomically validated home/module
        # arrays from the unfiltered request. This is protocol corroboration,
        # not a provider guarantee of completeness.
        observed = api.inventory_ids
        report["inventory_shape"] = {
            "validated_unfiltered_inventory": True,
            "all_homes_explicit_module_arrays": True,
            "account_visible_id_count": len(observed),
        }
        if known_registry_ids is not None:
            report["known_inventory_comparison"] = {
                "known_count": len(known_registry_ids),
                "observed_count": len(observed),
                "overlap_count": len(known_registry_ids & observed),
                "missing_count": len(known_registry_ids - observed),
                "extra_count": len(observed - known_registry_ids),
            }
        report["parsed_device_count"] = 0
        observed_modules = []
        for home in homes:
            modules = await api.get_home_statuses(home)
            observed_modules.extend(modules)
            report["parsed_device_count"] += sum(
                api_module.device_from_module(m) is not None for m in modules
            )
        report["rain_before_token_refresh"] = rain_observations(observed_modules)
        api.auth_token = await api.refresh_access_token(api.auth_token)
        report["token_refreshed"] = True
        report["refreshed_module_count"] = 0
        refreshed_modules = []
        for home in homes:
            modules = await api.get_home_statuses(home)
            refreshed_modules.extend(modules)
            report["refreshed_module_count"] += len(modules)
        report["rain_after_token_refresh"] = rain_observations(refreshed_modules)
        report["status_refreshed"] = True
    return report


def child(args) -> dict:
    logging.disable(logging.CRITICAL)
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary).resolve()
        members = extract_verified(args.archive, root)
        manifest = json.loads((root / "manifest.json").read_text())
        api, origins = load_archive_api(root, members)
        dependency = None
        if manifest["requirements"]:
            if args.dependency_wheel is None:
                raise ValueError("An exact installed dependency wheel is required")
            dependency = verify_dependency(args.dependency_wheel, manifest["requirements"])
        credentials = json.loads(args.credentials.read_text())
        known_registry_ids = None
        if args.compare_registry_stdin:
            comparison = json.loads(sys.stdin.read(1_048_577))
            if not isinstance(comparison, dict) or set(comparison) != {"known_registry_ids"}:
                raise ValueError("Invalid comparison input")
            values = comparison["known_registry_ids"]
            if (
                not isinstance(values, list)
                or not 1 <= len(values) <= 1000
                or any(not isinstance(value, str) or not value for value in values)
                or len(set(values)) != len(values)
            ):
                raise ValueError("Invalid comparison input")
            known_registry_ids = set(values)
        report = asyncio.run(check(api, credentials, args.synthetic_url, known_registry_ids))
        report.update(
            status="passed",
            zip_sha256=hashlib.sha256(args.archive.read_bytes()).hexdigest(),
            integration_version=manifest["version"],
            isolated=sys.flags.isolated == 1,
            artifact_modules=origins,
            dependency_proof=dependency or "inline_client_intermediate",
            aiohttp_version=importlib.metadata.version("aiohttp"),
        )
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--dependency-wheel", type=Path)
    parser.add_argument(
        "--compare-registry-stdin",
        action="store_true",
        help='Read private {"known_registry_ids": [str, ...]} JSON from stdin; emit counts only',
    )
    parser.add_argument(
        "--python", type=Path, help="Prepared clean interpreter with the exact wheel"
    )
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
        str(args.python.absolute()) if args.python else sys.executable,
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
    if args.dependency_wheel:
        command.extend(["--dependency-wheel", str(args.dependency_wheel.resolve())])
    private_input = None
    if args.compare_registry_stdin:
        command.append("--compare-registry-stdin")
        print("COMPARISON_INPUT_READY", file=sys.stderr, flush=True)
        private_input = sys.stdin.read(1_048_577)
    with tempfile.TemporaryDirectory() as temporary:
        result = subprocess.run(
            command,
            cwd=temporary,
            capture_output=True,
            text=True,
            input=private_input,
            timeout=180,
            check=False,
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
