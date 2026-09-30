"""Read-only client for the VELUX ACTIVE cloud API."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import isfinite
from time import monotonic
from typing import cast

from aiohttp import ClientError, ClientSession, ClientTimeout

from .const import API_URL, OAUTH2_CLIENT_ID, OAUTH2_CLIENT_SECRET

type JSON = None | bool | int | float | str | list[JSON] | dict[str, JSON]


def object_value(value: JSON) -> dict[str, JSON]:
    if not isinstance(value, dict):
        raise TypeError("Expected object")
    return value


def array_value(value: JSON) -> list[JSON]:
    if not isinstance(value, list):
        raise TypeError("Expected array")
    return value


def required_text(value: JSON) -> str:
    if not isinstance(value, str) or not value:
        raise TypeError("Expected nonempty string")
    return value


def optional_text(value: JSON) -> str | None:
    if value is None or isinstance(value, str):
        return value
    raise APIConnectionError("VELUX returned an invalid text measurement")


def optional_integer(value: JSON) -> int | None:
    if value is None or (isinstance(value, int) and not isinstance(value, bool)):
        return value
    raise APIConnectionError("VELUX returned an invalid integer measurement")


def optional_boolean(value: JSON) -> bool | None:
    if value is None or isinstance(value, bool):
        return value
    raise APIConnectionError("VELUX returned an invalid boolean measurement")


def optional_version(value: JSON) -> str | int | None:
    """Provider revisions occur as both numeric revisions and text versions."""
    if (
        value is None
        or isinstance(value, str)
        or (isinstance(value, int) and not isinstance(value, bool))
    ):
        return value
    raise APIConnectionError("VELUX returned an invalid version measurement")


def optional_pairing(value: JSON) -> str | bool | None:
    if value is None or isinstance(value, (str, bool)):
        return value
    raise APIConnectionError("VELUX returned an invalid pairing measurement")


BOOLEAN_FIELDS = frozenset(
    {
        "is_raining",
        "reachable",
        "silent",
        "busy",
        "calibrating",
        "locked",
        "locking",
        "secure",
        "outdated_weather_forecast",
    }
)


def validate_boolean_fields(record: Mapping[str, JSON]) -> None:
    """Missing/null is unknown; supplied boolean values must actually be booleans."""
    for key in BOOLEAN_FIELDS:
        if (value := record.get(key)) is not None and not isinstance(value, bool):
            raise APIConnectionError("VELUX returned an invalid boolean measurement")


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

    def __init__(
        self, access_token: str, refresh_token: str, expires_in: int, **rest: object
    ) -> None:
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

    def __init__(self, home: VeluxHome, id: str, type: str, **kwargs: JSON) -> None:
        self.home, self.id, self.type = home, id, type
        self.kwargs = kwargs


class VeluxActiveAPI:
    """Authenticate and poll without sending device commands."""

    def __init__(self, websession: ClientSession, *, base_url: str = API_URL) -> None:
        self._websession = websession
        self._base_url = base_url.rstrip("/")
        self.auth_token: AuthToken | None = None
        self._credentials: tuple[str, str] | None = None
        self._token_lock = asyncio.Lock()
        self._retry_at = 0.0
        self._topology: dict[str, dict[str, dict[str, JSON]]] = {}

    async def _request(
        self, path: str, *, data: dict[str, str] | None = None, token: str | None = None
    ) -> dict[str, JSON]:
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
                    # aiohttp uses the JSON decoder: its values have this recursive shape.
                    payload = cast(JSON, await response.json(content_type=None))
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

    async def _token_request(self, data: dict[str, str]) -> AuthToken:
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
            raw_lifetime = payload.get("expires_in", payload.get("expire_in", 10800))
            if not isinstance(raw_lifetime, (int, float, str)) or isinstance(raw_lifetime, bool):
                raise TypeError
            if isinstance(raw_lifetime, float) and not isfinite(raw_lifetime):
                raise ValueError
            lifetime = int(raw_lifetime)
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
        except (KeyError, ValueError, TypeError, OverflowError) as err:
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
            token = await self.authenticate(*self._credentials)
            return token.access_token

    async def _api_request(self, path: str, data: dict[str, str] | None = None) -> dict[str, JSON]:
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
            homes = array_value(object_value(payload["body"])["homes"])
            if not isinstance(homes, list):
                raise TypeError
            result = []
            for raw_home in homes:
                home = object_value(raw_home)
                home_id = required_text(home["id"])
                modules = array_value(home.get("modules", []))
                if not isinstance(modules, list):
                    raise TypeError
                self._topology[home_id] = {
                    required_text(object_value(m)["id"]): object_value(m) for m in modules
                }
                result.append(VeluxHome(home_id, required_text(home.get("name", "Home"))))
            return result
        except (KeyError, TypeError, AttributeError) as err:
            raise APIConnectionError("VELUX returned invalid home topology") from err

    async def get_home_statuses(self, home: VeluxHome) -> list[VeluxModule]:
        payload = await self._api_request("/api/homestatus", {"home_id": home.id})
        try:
            records = array_value(object_value(object_value(payload["body"])["home"])["modules"])
            if not isinstance(records, list):
                raise TypeError
            modules = []
            for raw_record in records:
                record = object_value(raw_record)
                validate_boolean_fields(record)
                # Never retain a previous rain/position/reachability measurement.
                topology = self._topology.get(home.id, {}).get(required_text(record["id"]), {})
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
                merged = metadata | record
                module_id, module_type = (
                    required_text(merged.pop("id")),
                    required_text(merged.pop("type")),
                )
                modules.append(VeluxModule(home, module_id, module_type, **merged))
            return modules
        except (KeyError, TypeError, AttributeError) as err:
            raise APIConnectionError("VELUX returned invalid home status") from err


def device_from_module(module: VeluxModule) -> VeluxDevice | None:
    """Validate owned measurements and ignore unknown API fields."""
    if module.type == "NXG":
        return VeluxGatewayData(
            home=module.home,
            busy=optional_boolean(module.kwargs.get("busy")),
            calibrating=optional_boolean(module.kwargs.get("calibrating")),
            firmware_revision_netatmo=optional_integer(
                module.kwargs.get("firmware_revision_netatmo")
            ),
            firmware_revision_thirdparty=optional_version(
                module.kwargs.get("firmware_revision_thirdparty")
            ),
            hardware_version=optional_integer(module.kwargs.get("hardware_version")),
            id=module.id,
            is_raining=optional_boolean(module.kwargs.get("is_raining")),
            last_seen=optional_integer(module.kwargs.get("last_seen")),
            locked=optional_boolean(module.kwargs.get("locked")),
            locking=optional_boolean(module.kwargs.get("locking")),
            name=optional_text(module.kwargs.get("name")),
            pairing=optional_pairing(module.kwargs.get("pairing")),
            secure=optional_boolean(module.kwargs.get("secure")),
            type=module.type,
            wifi_strength=optional_integer(module.kwargs.get("wifi_strength")),
            wifi_state=optional_text(module.kwargs.get("wifi_state")),
            outdated_weather_forecast=optional_boolean(
                module.kwargs.get("outdated_weather_forecast")
            ),
            reachable=optional_boolean(module.kwargs.get("reachable")),
        )
    if module.type in {"NXS", "NXD"}:
        return VeluxSwitchData(
            home=module.home,
            battery_level=optional_integer(module.kwargs.get("battery_level")),
            battery_percent=optional_integer(module.kwargs.get("battery_percent")),
            firmware_revision=optional_integer(module.kwargs.get("firmware_revision")),
            id=module.id,
            last_seen=optional_integer(module.kwargs.get("last_seen")),
            reachable=optional_boolean(module.kwargs.get("reachable")),
            rf_strength=optional_integer(module.kwargs.get("rf_strength")),
            type=module.type,
            bridge=optional_text(module.kwargs.get("bridge")),
            battery_state=optional_text(module.kwargs.get("battery_state")),
            rf_state=optional_text(module.kwargs.get("rf_state")),
        )
    if module.type == "NXO" and module.kwargs.get("velux_type") == "window":
        return VeluxWindowData(
            home=module.home,
            current_position=optional_integer(module.kwargs.get("current_position")),
            firmware_revision=optional_integer(module.kwargs.get("firmware_revision")),
            id=module.id,
            last_seen=optional_integer(module.kwargs.get("last_seen")),
            manufacturer=optional_text(module.kwargs.get("manufacturer")),
            mode=optional_text(module.kwargs.get("mode")),
            reachable=optional_boolean(module.kwargs.get("reachable")),
            silent=optional_boolean(module.kwargs.get("silent")),
            target_position=optional_integer(module.kwargs.get("target_position")),
            type=module.type,
            velux_type=optional_text(module.kwargs.get("velux_type")),
            bridge=optional_text(module.kwargs.get("bridge")),
            rain_position=optional_integer(module.kwargs.get("rain_position")),
            secure_position=optional_integer(module.kwargs.get("secure_position")),
        )
    if module.type == "NXO" and module.kwargs.get("velux_type") == "shutter":
        return VeluxShutterData(
            home=module.home,
            current_position=optional_integer(module.kwargs.get("current_position")),
            firmware_revision=optional_integer(module.kwargs.get("firmware_revision")),
            id=module.id,
            last_seen=optional_integer(module.kwargs.get("last_seen")),
            manufacturer=optional_text(module.kwargs.get("manufacturer")),
            mode=optional_text(module.kwargs.get("mode")),
            reachable=optional_boolean(module.kwargs.get("reachable")),
            silent=optional_boolean(module.kwargs.get("silent")),
            target_position=optional_integer(module.kwargs.get("target_position")),
            type=module.type,
            velux_type=optional_text(module.kwargs.get("velux_type")),
            bridge=optional_text(module.kwargs.get("bridge")),
        )
    return None


@dataclass(kw_only=True)
class VeluxGatewayData:
    home: VeluxHome
    busy: bool | None = None
    calibrating: bool | None = None
    firmware_revision_netatmo: int | None = None
    firmware_revision_thirdparty: str | int | None = None
    hardware_version: int | None = None
    id: str
    is_raining: bool | None = None
    last_seen: int | None = None
    locked: bool | None = None
    locking: bool | None = None
    name: str | None = None
    pairing: str | bool | None = None
    secure: bool | None = None
    type: str
    wifi_strength: int | None = None
    wifi_state: str | None = None
    outdated_weather_forecast: bool | None = None
    reachable: bool | None = None

    @property
    def unlocked(self) -> bool | None:
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


type VeluxDevice = VeluxGatewayData | VeluxWindowData | VeluxShutterData | VeluxSwitchData
