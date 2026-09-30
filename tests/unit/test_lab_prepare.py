"""Shared-checkout preparation cannot mix independently generated TLS inputs."""

import fcntl
from unittest.mock import Mock, patch

import pytest

from scripts import lab


def test_overlapping_preparation_fails_before_building(tmp_path):
    directory = tmp_path / ".lab"
    directory.mkdir()
    with (directory / "prepare.lock").open("w") as competing:
        fcntl.flock(competing, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with patch.object(lab, "ROOT", tmp_path), patch.object(lab, "_prepare") as build:
            with pytest.raises(RuntimeError, match="prepare sequentially"):
                lab.prepare(Mock())
            build.assert_not_called()
    with patch.object(lab, "ROOT", tmp_path), patch.object(lab, "_prepare") as build:
        args = Mock()
        lab.prepare(args)
        build.assert_called_once_with(args)
