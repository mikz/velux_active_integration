"""Release inventories reflect intended tracked payload rather than workstation debris."""

import os
import subprocess
import zipfile

import pytest

from scripts import release


@pytest.fixture
def package(tmp_path, monkeypatch):
    source = tmp_path / "integration"
    source.mkdir()
    payload = {
        "manifest.json": b'{"version":"synthetic"}',
        "__init__.py": b'"""Synthetic integration."""\n',
        "nested/module.py": b"VALUE = 0\n",
        "translations/en.json": b"{}\n",
        "quality_scale.yaml": b"rules: {}\n",
        "brand/icon.png": b"synthetic-png-bytes",
    }
    for filename, content in payload.items():
        target = source / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    archive = tmp_path / "dist/integration.zip"
    monkeypatch.setattr(release, "SOURCE", source)
    monkeypatch.setattr(release, "ARCHIVE", archive)
    monkeypatch.setattr("sys.argv", ["release.py", "build"])
    return source, archive, payload


def test_payload_excludes_debris_and_is_independent_of_host_file_metadata(package):
    source, archive, payload = package
    release.main()
    clean = archive.read_bytes()
    for filename in [
        ".DS_Store",
        ".hidden/config.json",
        "__pycache__/module.pyc",
        "__pycache__/module.py",
        "cached.pyc",
        "module.py~",
        "module.swp",
        "home-assistant.log",
        "runtime.sqlite",
        "Thumbs.db",
    ]:
        target = source / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"workstation debris")
    for filename in payload:
        target = source / filename
        os.utime(target, (1, 1))
        target.chmod(0o600)
    release.main()
    assert archive.read_bytes() == clean
    with zipfile.ZipFile(archive) as installed:
        assert set(installed.namelist()) == set(payload)
        assert {name: installed.read(name) for name in installed.namelist()} == payload


def test_verification_rejects_an_extra_archive_member(package, monkeypatch):
    _, archive, _ = package
    release.main()
    with zipfile.ZipFile(archive, "a") as installed:
        installed.writestr("unexpected.json", b"{}")
    monkeypatch.setattr("sys.argv", ["release.py", "verify"])
    with pytest.raises(AssertionError):
        release.main()


def test_repository_archive_inventory_matches_independent_tracked_payload():
    tracked = subprocess.run(
        ["git", "ls-files", "custom_components/velux_active"],
        cwd=release.ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    prefix = "custom_components/velux_active/"
    assert set(release.files()) == {name.removeprefix(prefix) for name in tracked}
