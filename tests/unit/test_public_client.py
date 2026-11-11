"""A downloaded package must match reviewed source before installation."""

import json
import subprocess
import zipfile
from unittest.mock import Mock

import pytest

from scripts import check_public_client
from scripts.client_release import validate_wheel


@pytest.mark.parametrize("tampered", [False, True])
def test_public_install_rejects_changed_payload_before_install(tmp_path, monkeypatch, tampered):
    root = tmp_path / "repo"
    source = root / "packages/velux-active-client/src/velux_active_client"
    source.mkdir(parents=True)
    (source / "__init__.py").write_text("VALUE = 1\n")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    manifest = root / "custom_components/velux_active/manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"requirements": ["velux-active-client==0.1.0"]}))
    monkeypatch.setattr(check_public_client, "ROOT", root)
    monkeypatch.setattr(
        check_public_client, "validate_wheel", lambda wheel: validate_wheel(wheel, root)
    )
    staging = tmp_path / "download"
    staging.mkdir()
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        if "download" in command:
            with zipfile.ZipFile(staging / "client.whl", "w") as wheel:
                wheel.writestr(
                    "velux_active_client/__init__.py", f"VALUE = {2 if tampered else 1}\n"
                )
        if "pip" in command:
            assert kwargs["env"]["PIP_CONFIG_FILE"] == "/dev/null"
            assert "PIP_EXTRA_INDEX_URL" not in kwargs["env"]

    # Keep the independent git inventory real while replacing package/network operations.
    real_run = subprocess.run
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **kw: (
            real_run(command, **kw) if command[0] == "git" else run(command, **kw)
        ),
    )
    real_output = subprocess.check_output
    proof = Mock(return_value='{"version": "0.1.0"}')
    monkeypatch.setattr(
        subprocess,
        "check_output",
        lambda command, **kw: (
            real_output(command, **kw) if command[0] == "git" else proof(command, **kw)
        ),
    )
    monkeypatch.setenv("PIP_EXTRA_INDEX_URL", "https://untrusted.invalid/simple")
    if tampered:
        with pytest.raises(ValueError, match="source bytes"):
            check_public_client.check_public_client(staging)
        assert not any("install" in command for command in commands)
        proof.assert_not_called()
    else:
        assert check_public_client.check_public_client(staging) == {"version": "0.1.0"}
        install = next(command for command in commands if "install" in command)
        assert install[-1] == "velux-active-client==0.1.0"
        assert install[install.index("--index-url") + 1] == "https://pypi.org/simple"
        assert "--no-cache-dir" in install
        assert "-I" in proof.call_args.args[0]
