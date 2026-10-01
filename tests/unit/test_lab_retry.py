"""Installed retry acceptance must reject a timer that never fires."""

import pytest

from tests.lab.probe import assert_native_retry_observed


def test_native_retry_oracle_requires_positive_second_setup_transition():
    with pytest.raises(AssertionError, match="Native retry not observed"):
        assert_native_retry_observed(["setup_in_progress", "setup_retry"])
    with pytest.raises(AssertionError, match="Native retry not observed"):
        assert_native_retry_observed(["setup_in_progress", "setup_retry", "setup_retry"])
    assert_native_retry_observed(
        ["setup_in_progress", "setup_retry", "setup_in_progress", "setup_retry"]
    )
