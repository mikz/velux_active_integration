"""Enable custom integrations only in the local test Home Assistant."""

import pytest


@pytest.fixture(autouse=True)
def _custom_integrations(enable_custom_integrations):
    """Load this integration in the HA test instance."""


@pytest.fixture
async def cloud(aiohttp_server, socket_enabled):
    """Expose only the synthetic service on the test HTTP boundary."""
    import aiohttp

    from custom_components.velux_active.api import VeluxActiveAPI
    from tests.lab.cloud import Cloud

    simulator = Cloud()
    server = await aiohttp_server(simulator.app())
    async with aiohttp.ClientSession() as session:
        yield simulator, VeluxActiveAPI(session, base_url=str(server.make_url("")))
