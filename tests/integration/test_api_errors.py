"""Client failure contracts through synthetic HTTP responses, without cloud access."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock

import aiohttp
import pytest
from aiohttp import web

from custom_components.velux_active.api import (
    APIConnectionError,
    AuthToken,
    InvalidAuthError,
    RateLimitError,
    VeluxActiveAPI,
    VeluxHome,
    VeluxModule,
    device_from_module,
)
from tests.lab.cloud import PASSWORD, USERNAME


@pytest.fixture
async def response_api(aiohttp_server, socket_enabled):
    state = {"status": 200, "payload": {}, "raw": None, "headers": {}}
    calls = []

    async def respond(request):
        calls.append(request.path)
        if state["raw"] is not None:
            return web.Response(text=state["raw"], status=state["status"], headers=state["headers"])
        return web.json_response(state["payload"], status=state["status"], headers=state["headers"])

    app = web.Application()
    app.router.add_post("/{path:.*}", respond)
    server = await aiohttp_server(app)
    async with aiohttp.ClientSession() as session:
        yield state, calls, VeluxActiveAPI(session, base_url=str(server.make_url("")))


@pytest.mark.parametrize("payload", [None, [], "text"])
async def test_non_object_json_is_connection_failure(response_api, payload):
    state, _, api = response_api
    state["payload"] = payload
    with pytest.raises(APIConnectionError, match="invalid JSON"):
        await api.authenticate(USERNAME, PASSWORD)


async def test_invalid_json_is_connection_failure(response_api):
    state, _, api = response_api
    state["raw"] = "bad-json"
    with pytest.raises(APIConnectionError, match="invalid JSON"):
        await api.authenticate(USERNAME, PASSWORD)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"access_token": "", "refresh_token": "refresh"},
        {"access_token": "access", "refresh_token": ""},
        {"access_token": "access", "refresh_token": "refresh", "expires_in": 0},
        {"access_token": "access", "refresh_token": "refresh", "expires_in": None},
        {"access_token": "access", "refresh_token": "refresh", "expires_in": float("inf")},
        {"access_token": "access", "refresh_token": "refresh", "expires_in": float("nan")},
        {"access_token": "access", "refresh_token": "refresh", "expires_in": 10**30},
    ],
)
async def test_invalid_token_fields_are_connection_failure(response_api, payload):
    state, _, api = response_api
    state["payload"] = payload
    with pytest.raises(APIConnectionError, match="invalid token"):
        await api.authenticate(USERNAME, PASSWORD)
    assert api.auth_token is None


@pytest.mark.parametrize("delay,expected", [("invalid", 60), ("0", 1), ("99999", 3600)])
async def test_retry_after_is_bounded_and_blocks_repeat_requests(response_api, delay, expected):
    state, calls, api = response_api
    state.update(status=429, headers={"Retry-After": delay})
    with pytest.raises(RateLimitError) as error:
        await api.authenticate(USERNAME, PASSWORD)
    assert error.value.retry_after == expected
    with pytest.raises(RateLimitError):
        await api.authenticate(USERNAME, PASSWORD)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "method,payload",
    [
        ("get_home_data", {}),
        ("get_home_data", {"body": {"homes": [None]}}),
        ("get_home_statuses", {}),
        ("get_home_statuses", {"body": {"home": {"modules": [None]}}}),
    ],
)
async def test_invalid_topology_and_status_are_connection_failure(response_api, method, payload):
    state, _, api = response_api
    api.auth_token = AuthToken("synthetic", "synthetic-refresh", 10800)
    state["payload"] = payload
    args = [VeluxHome("synthetic-home", "Synthetic")] if method == "get_home_statuses" else []
    with pytest.raises(APIConnectionError, match="invalid home"):
        await getattr(api, method)(*args)


@pytest.mark.parametrize("error", [aiohttp.ClientConnectionError(), TimeoutError()])
async def test_transport_failures_are_safe_connection_errors(error):
    session = AsyncMock()
    # ClientSession.request raises synchronously before entering its context manager.
    from unittest.mock import Mock

    session.request = Mock(side_effect=error)
    with pytest.raises(APIConnectionError, match="Cannot reach"):
        await VeluxActiveAPI(session).authenticate(USERNAME, PASSWORD)


async def test_missing_login_rejects_request_without_http():
    with pytest.raises(InvalidAuthError, match="login is required"):
        await VeluxActiveAPI(AsyncMock()).get_home_data()


async def test_concurrent_expired_token_reads_share_one_refresh(cloud):
    simulator, api = cloud
    await api.authenticate(USERNAME, PASSWORD)
    api.auth_token.expires_at = datetime.min
    tokens = await asyncio.gather(api.access_token, api.access_token, api.access_token)
    assert len(set(tokens)) == 1
    assert simulator.counts["refresh_token"] == 1


@pytest.mark.parametrize("kind", ["UNKNOWN", "NXO"])
def test_unknown_module_types_and_cover_kinds_are_ignored(kind):
    assert (
        device_from_module(
            VeluxModule(VeluxHome("synthetic", "Synthetic"), "module", kind, velux_type="unknown")
        )
        is None
    )


@pytest.mark.parametrize("collection", [{}, "", None])
@pytest.mark.parametrize("endpoint", ["homes", "topology_modules", "status_modules"])
async def test_object_string_and_null_collections_are_not_empty_inventories(
    response_api, collection, endpoint
):
    state, _, api = response_api
    api.auth_token = AuthToken("synthetic", "synthetic-refresh", 10800)
    if endpoint == "homes":
        state["payload"] = {"body": {"homes": collection}}
    elif endpoint == "topology_modules":
        state["payload"] = {"body": {"homes": [{"id": "synthetic", "modules": collection}]}}
    else:
        state["payload"] = {"body": {"home": {"modules": collection}}}
    with pytest.raises(APIConnectionError, match="invalid home"):
        if endpoint == "status_modules":
            await api.get_home_statuses(VeluxHome("synthetic", "Synthetic"))
        else:
            await api.get_home_data()


async def test_valid_empty_arrays_remain_valid_inventories(response_api):
    state, _, api = response_api
    api.auth_token = AuthToken("synthetic", "synthetic-refresh", 10800)
    state["payload"] = {"body": {"homes": []}}
    assert await api.get_home_data() == []
    state["payload"] = {"body": {"homes": [{"id": "synthetic", "modules": []}]}}
    home = (await api.get_home_data())[0]
    state["payload"] = {"body": {"home": {"modules": []}}}
    assert await api.get_home_statuses(home) == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("wifi_strength", "strong"),
        ("hardware_version", True),
        ("name", []),
        ("firmware_revision_thirdparty", {}),
        ("pairing", []),
    ],
)
async def test_invalid_typed_measurements_reject_http_snapshot(response_api, field, value):
    state, _, api = response_api
    api.auth_token = AuthToken("synthetic", "synthetic-refresh", 10800)
    home = VeluxHome("synthetic", "Synthetic")
    state["payload"] = {
        "body": {"home": {"modules": [{"id": "module", "type": "NXG", field: value}]}}
    }
    modules = await api.get_home_statuses(home)
    with pytest.raises(APIConnectionError, match="invalid .* measurement"):
        device_from_module(modules[0])


@pytest.mark.parametrize("identifier", [None, 0, "", []])
async def test_invalid_home_identity_rejects_http_topology(response_api, identifier):
    state, _, api = response_api
    api.auth_token = AuthToken("synthetic", "synthetic-refresh", 10800)
    state["payload"] = {"body": {"homes": [{"id": identifier, "modules": []}]}}
    with pytest.raises(APIConnectionError, match="invalid home topology"):
        await api.get_home_data()


@pytest.mark.parametrize("version,pairing", [(12, True), ("1.2", "pending")])
def test_provider_revision_and_pairing_variants_remain_typed(version, pairing):
    module = VeluxModule(
        VeluxHome("synthetic", "Synthetic"),
        "module",
        "NXG",
        firmware_revision_thirdparty=version,
        pairing=pairing,
    )
    device = device_from_module(module)
    assert device.firmware_revision_thirdparty == version
    assert device.pairing == pairing
