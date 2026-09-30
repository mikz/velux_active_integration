"""Read-only client for the VELUX ACTIVE cloud API."""

import asyncio
from dataclasses import dataclass, fields
from datetime import datetime, timedelta
from time import monotonic
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

from .const import API_URL, OAUTH2_CLIENT_ID, OAUTH2_CLIENT_SECRET


class APIConnectionError(Exception):
    """VELUX is unavailable or returned an invalid response."""


class InvalidAuthError(Exception):
    """VELUX rejected the account or token."""


class RateLimitError(APIConnectionError):
    """VELUX asked the client to wait before another request."""

    def __init__(self, retry_after: int = 60) -> None:
        super().__init__("VELUX API rate limit reached")
        self.retry_after = retry_after


class AuthToken:
    """A token whose representation never contains credentials."""

    def __init__(self, access_token: str, refresh_token: str, expires_in: int, **rest):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_in = timedelta(seconds=expires_in)
        self.expires_at = datetime.now() + self.expires_in

    def valid_in(self, margin: timedelta = timedelta(seconds=30)) -> bool:
        return bool(self.access_token) and self.expires_at > datetime.now() + margin

    def __repr__(self) -> str:
        return "<AuthToken redacted>"


@dataclass(frozen=True)
class VeluxHome:
    """Home identity, with topology kept out of logs and equality."""

    id: str
    name: str
    # Topology is cached separately on the API client.


class VeluxModule:
    """A status record with the static metadata supplied by homesdata."""

    def __init__(self, home: VeluxHome, id: str, type: str, **kwargs):
        self.home, self.id, self.type = home, id, type
        self.kwargs = kwargs

    def __getitem__(self, key):
        if key in {"home", "id", "type"}:
            return getattr(self, key)
        return self.kwargs[key]

    def keys(self):
        return ["home", "id", "type", *self.kwargs]


class VeluxActiveAPI:
    """Authenticate and poll without sending device commands."""

    def __init__(self, websession: ClientSession, *, base_url: str = API_URL):
        self._websession = websession
        self._base_url = base_url.rstrip("/")
        self.auth_token: AuthToken | None = None
        self._credentials: tuple[str, str] | None = None
        self._token_lock = asyncio.Lock()
        self._retry_at = 0.0
        self._topology: dict[str, dict[str, dict[str, Any]]] = {}

    async def _request(self, path, *, data=None, token=None):
        if monotonic() < self._retry_at:
            raise RateLimitError(max(1, int(self._retry_at - monotonic()) + 1))
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            async with self._websession.request(
                "POST",
                self._base_url + path,
                data=data,
                headers=headers,
                timeout=ClientTimeout(total=20),
            ) as response:
                try:
                    payload = await response.json(content_type=None)
                except ValueError:
                    payload = None
                error = payload.get("error") if isinstance(payload, dict) else None
                code = error.get("code") if isinstance(error, dict) else error
                if response.status == 429 or code in (26, "26"):
                    delay = response.headers.get("Retry-After", "60")
                    retry_after = min(max(int(delay), 1), 3600) if delay.isdigit() else 60
                    self._retry_at = monotonic() + retry_after
                    raise RateLimitError(retry_after)
                if response.status in (401, 403) or code in (
                    1,
                    2,
                    3,
                    "invalid_grant",
                    "invalid_token",
                    "invalid_client",
                ):
                    raise InvalidAuthError("VELUX rejected authentication")
                if response.status >= 400 or error:
                    raise APIConnectionError(f"VELUX request failed (HTTP {response.status})")
                if not isinstance(payload, dict):
                    raise APIConnectionError("VELUX returned an invalid JSON response")
                return payload
        except (ClientError, TimeoutError) as err:
            raise APIConnectionError("Cannot reach the VELUX cloud API") from err

    async def _token_request(self, data):
        payload = await self._request(
            "/oauth2/token",
            data={
                "client_id": OAUTH2_CLIENT_ID,
                "client_secret": OAUTH2_CLIENT_SECRET,
                "app_version": "791302006",
                **data,
            },
        )
        try:
            lifetime = int(payload.get("expires_in", payload.get("expire_in", 10800)))
            access, refresh = payload["access_token"], payload["refresh_token"]
            if (
                not isinstance(access, str)
                or not access
                or not isinstance(refresh, str)
                or not refresh
            ):
                raise ValueError
            if lifetime <= 0:
                raise ValueError
            return AuthToken(access, refresh, lifetime)
        except (KeyError, ValueError, TypeError) as err:
            raise APIConnectionError("VELUX returned an invalid token response") from err

    async def authenticate(self, username: str, password: str) -> AuthToken:
        token = await self._token_request(
            {
                "grant_type": "password",
                "username": username,
                "password": password,
                "user_prefix": "velux",
                "scope": "velux_scopes",
            }
        )
        self._credentials = (username, password)
        self.auth_token = token
        return token

    async def refresh_access_token(self, auth_token: AuthToken) -> AuthToken:
        return await self._token_request(
            {
                "grant_type": "refresh_token",
                "refresh_token": auth_token.refresh_token,
            }
        )

    @property
    async def access_token(self) -> str:
        async with self._token_lock:
            if self.auth_token is not None and self.auth_token.valid_in():
                return self.auth_token.access_token
            if self.auth_token is not None:
                try:
                    self.auth_token = await self.refresh_access_token(self.auth_token)
                    return self.auth_token.access_token
                except InvalidAuthError:
                    pass
            if self._credentials is None:
                raise InvalidAuthError("VELUX login is required")
            await self.authenticate(*self._credentials)
            return self.auth_token.access_token

    async def _api_request(self, path, data=None):
        # Retry a rejected access token once. Network errors never trigger a login.
        token = await self.access_token
        try:
            return await self._request(path, data=data, token=token)
        except InvalidAuthError:
            if self.auth_token is not None and self.auth_token.access_token == token:
                self.auth_token.expires_at = datetime.min
        return await self._request(path, data=data, token=await self.access_token)

    async def get_home_data(self) -> list[VeluxHome]:
        payload = await self._api_request("/api/homesdata")
        try:
            homes = payload["body"]["homes"]
            if not isinstance(homes, list):
                raise TypeError
            result = []
            for home in homes:
                home_id = home["id"]
                modules = home.get("modules", [])
                if not isinstance(modules, list):
                    raise TypeError
                self._topology[home_id] = {m["id"]: m for m in modules}
                result.append(VeluxHome(home_id, home.get("name", "Home")))
            return result
        except (KeyError, TypeError, AttributeError) as err:
            raise APIConnectionError("VELUX returned invalid home topology") from err

    async def get_home_statuses(self, home: VeluxHome) -> list[VeluxModule]:
        payload = await self._api_request("/api/homestatus", {"home_id": home.id})
        try:
            records = payload["body"]["home"]["modules"]
            if not isinstance(records, list):
                raise TypeError
            modules = []
            for record in records:
                # Never retain a previous rain/position/reachability measurement.
                topology = self._topology.get(home.id, {}).get(record["id"], {})
                metadata = {
                    k: v
                    for k, v in topology.items()
                    if k
                    in {
                        "id",
                        "type",
                        "name",
                        "bridge",
                        "manufacturer",
                        "velux_type",
                        "firmware_revision",
                        "firmware_revision_netatmo",
                        "firmware_revision_thirdparty",
                        "hardware_version",
                    }
                }
                modules.append(VeluxModule(home, **(metadata | record)))
            return modules
        except (KeyError, TypeError, AttributeError) as err:
            raise APIConnectionError("VELUX returned invalid home status") from err


def device_from_module(module: VeluxModule):
    """Ignore new API fields and preserve absent measurements as unknown."""
    model = {"NXG": VeluxGatewayData, "NXS": VeluxSwitchData, "NXD": VeluxSwitchData}.get(
        module.type
    )
    if module.type == "NXO":
        model = {"window": VeluxWindowData, "shutter": VeluxShutterData}.get(
            module.kwargs.get("velux_type")
        )
    if model is None:
        return None
    names = {field.name for field in fields(model)}
    return model(**{key: module[key] for key in module.keys() if key in names})


@dataclass(kw_only=True)
class VeluxGatewayData:
    home: VeluxHome
    busy: bool | None = None
    calibrating: bool | None = None
    firmware_revision_netatmo: int | None = None
    firmware_revision_thirdparty: str | None = None
    hardware_version: int | None = None
    id: str
    is_raining: bool | None = None
    last_seen: int | None = None
    locked: bool | None = None
    locking: bool | None = None
    name: str | None = None
    pairing: str | None = None
    secure: bool | None = None
    type: str
    wifi_strength: int | None = None
    wifi_state: str | None = None
    outdated_weather_forecast: bool | None = None
    reachable: bool | None = None

    @property
    def unlocked(self) -> bool:
        return None if self.locked is None else not self.locked


@dataclass(kw_only=True)
class VeluxWindowData:
    home: VeluxHome
    current_position: int | None = None
    firmware_revision: int | None = None
    id: str
    last_seen: int | None = None
    manufacturer: str | None = None
    mode: str | None = None
    reachable: bool | None = None
    silent: bool | None = None
    target_position: int | None = None
    type: str
    velux_type: str | None = None
    bridge: str | None = None
    rain_position: int | None = None
    secure_position: int | None = None


@dataclass(kw_only=True)
class VeluxShutterData:
    home: VeluxHome
    current_position: int | None = None
    firmware_revision: int | None = None
    id: str
    last_seen: int | None = None
    manufacturer: str | None = None
    mode: str | None = None
    reachable: bool | None = None
    silent: bool | None = None
    target_position: int | None = None
    type: str
    velux_type: str | None = None
    bridge: str | None = None


@dataclass(kw_only=True)
class VeluxSwitchData:
    home: VeluxHome
    battery_level: int | None = None
    battery_percent: int | None = None
    firmware_revision: int | None = None
    id: str
    last_seen: int | None = None
    reachable: bool | None = None
    rf_strength: int | None = None
    type: str
    bridge: str | None = None
    battery_state: str | None = None
    rf_state: str | None = None
