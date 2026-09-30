"""Enable custom integrations only in the local test Home Assistant."""

import pytest


@pytest.fixture(autouse=True)
def _custom_integrations(enable_custom_integrations):
    """Load this integration in the HA test instance."""
