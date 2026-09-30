#!/usr/bin/env python3
"""Build a deterministic HACS archive containing only the integration."""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "custom_components/velux_active"
ARCHIVE = ROOT / "dist/velux_active.zip"
PAYLOAD_SUFFIXES = {".py", ".json", ".yaml", ".png"}


def files():
    return {
        str(p.relative_to(SOURCE)): p.read_bytes()
        for p in sorted(SOURCE.rglob("*"))
        if p.is_file()
        and p.suffix in PAYLOAD_SUFFIXES
        and "__pycache__" not in p.relative_to(SOURCE).parts
        and not any(part.startswith(".") for part in p.relative_to(SOURCE).parts)
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "verify"))
    args = parser.parse_args()
    expected = files()
    if args.action == "build":
        ARCHIVE.parent.mkdir(exist_ok=True)
        with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in expected.items():
                info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, data)
    with zipfile.ZipFile(ARCHIVE) as archive:
        assert set(archive.namelist()) == set(expected)
        assert all(archive.read(name) == data for name, data in expected.items())
    receipt = {
        "sha256": hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
        "version": json.loads(expected["manifest.json"])["version"],
        "files": {name: hashlib.sha256(data).hexdigest() for name, data in expected.items()},
    }
    ARCHIVE.with_suffix(".manifest.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(f"Verified {ARCHIVE.name}: {receipt['sha256']}")


if __name__ == "__main__":
    main()
