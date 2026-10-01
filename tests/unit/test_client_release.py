"""Client publication cannot accidentally reuse an integration tag/version."""

import subprocess
import zipfile

import pytest
import yaml

from scripts.client_release import ROOT, validate_tag, validate_wheel


@pytest.mark.parametrize("tag", ["main", "v0.1.0", "client-v0.1.1", "client-v0.1.0-extra"])
def test_client_version_tag_requires_exact_separate_release(tag):
    with pytest.raises(ValueError, match="does not match"):
        validate_tag("0.1.0", tag)
    validate_tag("0.1.0", "client-v0.1.0")


def test_integration_release_excludes_client_tags_and_client_publish_creates_no_release():
    integration = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())
    assert "client-v" in integration["jobs"]["release"]["if"]
    client = (ROOT / ".github/workflows/client-release.yml").read_text()
    assert "softprops/action-gh-release" not in client
    assert "client-v*" in client
    assert "packages-dir: dist/client" in client


@pytest.mark.parametrize("mutation", ["extra", "changed", "missing", "duplicate"])
def test_client_wheel_inventory_rejects_payload_mutations(tmp_path, mutation):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    source = tmp_path / "packages/velux-active-client/src/velux_active_client"
    source.mkdir(parents=True)
    (source / "__init__.py").write_text("VALUE = 1\n")
    (source / "py.typed").touch()
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    wheel = tmp_path / "client.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("velux_active_client/__init__.py", "VALUE = 1\n")
        archive.writestr("velux_active_client/py.typed", "")
    assert len(validate_wheel(wheel, tmp_path)) == 2
    with zipfile.ZipFile(wheel, "w") as archive:
        if mutation != "missing":
            archive.writestr(
                "velux_active_client/__init__.py",
                "VALUE = 2\n" if mutation == "changed" else "VALUE = 1\n",
            )
        archive.writestr("velux_active_client/py.typed", "")
        if mutation == "extra":
            archive.writestr("velux_active_client/.DS_Store", "debris")
        if mutation == "duplicate":
            with pytest.warns(UserWarning, match="Duplicate"):
                archive.writestr("velux_active_client/py.typed", "")
    with pytest.raises(ValueError, match="Duplicate|inventory|source bytes"):
        validate_wheel(wheel, tmp_path)
