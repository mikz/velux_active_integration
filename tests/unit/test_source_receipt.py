"""Safe CI evidence rejects changed artifacts and preserves nonpassing gate outcomes."""

import json
import subprocess
import zipfile

import pytest

from scripts.source_receipt import GATES, artifact_proof, collect


@pytest.fixture
def receipt_root(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    sources = {
        "custom_components/velux_active/manifest.json": json.dumps(
            {"version": "0.2.0", "requirements": ["velux-active-client==0.1.0"]}
        ),
        "custom_components/velux_active/config_flow.py": "VALUE = 1\n",
        "packages/velux-active-client/src/velux_active_client/__init__.py": "VALUE = 2\n",
        "packages/velux-active-client/src/velux_active_client/py.typed": "",
    }
    for name, content in sources.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        cwd=tmp_path,
        check=True,
    )
    (tmp_path / "dist/client").mkdir(parents=True)
    with zipfile.ZipFile(tmp_path / "dist/velux_active.zip", "w") as archive:
        for name, content in sources.items():
            if name.startswith("custom_components/"):
                archive.writestr(name.removeprefix("custom_components/velux_active/"), content)
    with zipfile.ZipFile(tmp_path / "dist/client/client.whl", "w") as archive:
        for name, content in sources.items():
            if name.startswith("packages/"):
                archive.writestr(name.removeprefix("packages/velux-active-client/src/"), content)
        archive.writestr("client.dist-info/METADATA", "Name: velux-active-client\nVersion: 0.1.0\n")
    summary = {"num_statements": 1, "num_branches": 0, "covered_lines": 1, "covered_branches": 0}
    report = {
        "meta": {"branch_coverage": True},
        "files": {name: {"summary": summary} for name in sources if name.endswith(".py")},
    }
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts/source-coverage.json").write_text(json.dumps(report))
    return tmp_path


def test_source_receipt_binds_verified_payload_and_explicit_success(receipt_root):
    receipt = collect(receipt_root, dict.fromkeys(GATES, "success"))
    assert receipt["status"] == "passed"
    assert receipt["source_revision"]
    assert receipt["artifacts"]["manifest_pin"] == "velux-active-client==0.1.0"
    assert receipt["coverage"]["branch_coverage"] is True
    assert set(receipt["gates"]) == set(GATES)
    assert all(record["outcome"] == "success" for record in receipt["gates"].values())


@pytest.mark.parametrize("mutation", ["changed", "missing", "pin"])
def test_source_receipt_rejects_modified_or_missing_payload(receipt_root, mutation):
    archive = receipt_root / "dist/velux_active.zip"
    if mutation == "pin":
        manifest = receipt_root / "custom_components/velux_active/manifest.json"
        data = json.loads(manifest.read_text())
        data["requirements"] = ["velux-active-client==9.9.9"]
        manifest.write_text(json.dumps(data))
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("manifest.json", manifest.read_text())
            package.writestr("config_flow.py", "VALUE = 1\n")
    else:
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr(
                "manifest.json",
                (receipt_root / "custom_components/velux_active/manifest.json").read_text(),
            )
            if mutation == "changed":
                package.writestr("config_flow.py", "VALUE = 999\n")
    with pytest.raises(ValueError):
        artifact_proof(receipt_root)
    receipt = collect(receipt_root, dict.fromkeys(GATES, "success"))
    assert receipt["artifact_validation"] == "failed"
    assert receipt["status"] == "not_passed"


def test_source_receipt_preserves_failure_and_skipped_prerequisites(receipt_root):
    outcomes = dict.fromkeys(GATES, "skipped")
    outcomes["sync"] = "failure"
    receipt = collect(receipt_root, outcomes)
    assert receipt["status"] == "not_passed"
    assert receipt["artifact_validation"] == receipt["coverage_validation"] == "unavailable"
    assert receipt["gates"]["sync"]["outcome"] == "failure"
    assert receipt["gates"]["pytest"]["outcome"] == "skipped"
    assert "artifacts" not in receipt


def test_source_receipt_does_not_accept_unmeasured_branches(receipt_root):
    path = receipt_root / "artifacts/source-coverage.json"
    report = json.loads(path.read_text())
    report["meta"]["branch_coverage"] = False
    path.write_text(json.dumps(report))
    receipt = collect(receipt_root, dict.fromkeys(GATES, "success"))
    assert receipt["coverage_validation"] == "failed"
    assert receipt["status"] == "not_passed"
