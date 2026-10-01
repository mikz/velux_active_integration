"""Public runtime and entity types reject contract-breaking consumers."""

import subprocess
import sys


def test_strict_types_accept_runtime_contract_and_reject_wrong_owner_and_device(tmp_path):
    positive = tmp_path / "valid.py"
    positive.write_text("""
from custom_components.velux_active.coordinator import (VeluxActiveConfigEntry, VeluxCoordinator)
from custom_components.velux_active.api import VeluxHome, VeluxWindowData
from custom_components.velux_active.cover import VeluxCover

def entity(entry: VeluxActiveConfigEntry) -> VeluxCover:
    coordinator: VeluxCoordinator = entry.runtime_data
    device = VeluxWindowData(home=VeluxHome("synthetic", "Synthetic"), id="synthetic", type="NXO")
    return VeluxCover(coordinator, device, is_window=True)
""")
    negative = tmp_path / "invalid.py"
    negative.write_text("""
from custom_components.velux_active.coordinator import VeluxActiveConfigEntry
from custom_components.velux_active.cover import VeluxCover

def break_contract(entry: VeluxActiveConfigEntry) -> None:
    entry.runtime_data = "not a coordinator"
    VeluxCover(entry.runtime_data, "not a device", is_window=True)
""")
    command = [sys.executable, "-m", "mypy", "--strict", "--cache-dir", str(tmp_path / "cache")]
    valid = subprocess.run([*command, str(positive)], capture_output=True, text=True, check=False)
    assert valid.returncode == 0, valid.stdout + valid.stderr
    invalid = subprocess.run([*command, str(negative)], capture_output=True, text=True, check=False)
    assert invalid.returncode == 1, invalid.stdout + invalid.stderr
    assert "[assignment]" in invalid.stdout
    assert "[arg-type]" in invalid.stdout
