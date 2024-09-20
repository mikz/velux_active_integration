"""API for velux_active bound to Home Assistant OAuth."""

import logging
from dataclasses import dataclass, fields
from datetime import datetime, timedelta

from aiohttp import ClientSession
from homeassistant.helpers import config_entry_oauth2_flow

from .const import API_URL, OAUTH2_CLIENT_ID, OAUTH2_CLIENT_SECRET, OAUTH2_TOKEN

_LOGGER = logging.getLogger(__name__)
# TODO the following two API examples are based on our suggested best practices
# for libraries using OAuth2 with requests or aiohttp. Delete the one you won't use.
# For more info see the docs at https://developers.home-assistant.io/docs/api_lib_auth/#oauth2.


# {"access_token":"648567d53ee2239dbd0e367d|e81958a231246475bf0975196490daba","refresh_token":"648567d53ee2239dbd0e367d|f1daeb3476cdecf9a809c828ac5f2178","expires_in":10800,"expire_in":10800,"scope":["all_scopes"]}%
class AuthToken:
    """Provide a token for velux_active."""

    def __init__(
        self, access_token: str, refresh_token: str, expires_in: int, **rest
    ) -> None:
        """Initialize the token."""
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_in = timedelta(seconds=expires_in)
        self.created_at = datetime.now()
        self.expires_at = self.created_at + self.expires_in

    def valid_in(self, time: timedelta) -> bool:
        """Return whether the token is valid."""
        return self.access_token is not None and not self.expires(
            time or timedelta(seconds=0)
        )

    def expires(self, time: timedelta) -> bool:
        """Return whether the token is expired."""
        _LOGGER.debug(
            f"Token expires at {self.expires_at} < {datetime.now() + time} ({time})"
        )
        return self.expires_at < (datetime.now() + time)

    def __str__(self) -> str:
        """Return the token as a string."""
        return f"{self.access_token}"

    def __repr__(self) -> str:
        """Return the token as a string for debugging."""
        return f"<AuthToken {self.access_token}>"


class VeluxHome:
    def __init__(self, id: str, name: str, **kwargs) -> None:
        self.id = id
        self.name = name
        self.kwargs = kwargs

    def __str__(self) -> str:
        return self.id

    def __repr__(self) -> str:
        return f"<VeluxHome {self.id} {self.name} {self.kwargs}>"

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if isinstance(other, VeluxHome):
            return self.id == other.id
        return False


class VeluxModule:
    def __init__(self, home: VeluxHome, id: str, type: str, **kwargs) -> None:
        self.id = id
        self.type = type
        self.kwargs = kwargs
        self.home = home

    def __str__(self) -> str:
        return self.id

    def __repr__(self) -> str:
        return f"<VeluxModule {self.id} {self.type} {self.kwargs}>"

    def __hash__(self):
        return hash((self.id, self.type, self.home.id))

    def __eq__(self, other):
        if isinstance(other, VeluxModule):
            return (
                self.home == other.home
                and self.id == other.id
                and self.type == other.type
            )
        return False

    # Method to make the object behave like a dictionary for splat (**)
    def __getitem__(self, key):
        if key in self.kwargs:
            return self.kwargs[key]
        if hasattr(self, key):
            return getattr(self, key)

        raise KeyError(f"Key '{key}' not found in VeluxModule")

    # Optional: Provide the keys for iteration purposes
    def keys(self):
        return [*list(self.kwargs.keys()), "id", "type", "home"]

    # Optional: to make it fully compatible with dict-like behavior
    def __iter__(self):
        yield from self.keys()

    def items(self):
        for key in self.keys():
            yield (key, self[key])


class AsyncConfigEntryAuth:
    """Provide velux_active authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize velux_active auth."""
        super().__init__(websession)
        self._oauth_session = oauth_session

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        if not self._oauth_session.valid_token:
            await self._oauth_session.async_ensure_token_valid()

        return self._oauth_session.token["access_token"]


class VeluxActiveAPI:
    def __init__(self, websession: ClientSession) -> None:
        """Initialize the velux_active API."""
        self._websession = websession
        self.auth_token = None

    async def authenticate(self, username: str, password: str) -> AuthToken:
        """Authenticate to the velux_active API."""
        response = await self._websession.request(
            "POST",
            OAUTH2_TOKEN,
            data={
                "username": username,
                "password": password,
                "grant_type": "password",
                "user_prefix": "velux",
                "client_id": OAUTH2_CLIENT_ID,
                "client_secret": OAUTH2_CLIENT_SECRET,
            },
        )

        if not response.ok:
            raise InvalidAuthError("Invalid username or password")

        self.auth_token = AuthToken(**await response.json())

        return self.auth_token

    async def refresh_access_token(self, auth_token: AuthToken) -> AuthToken:
        """Refresh the access token."""
        response = await self._websession.request(
            "POST",
            OAUTH2_TOKEN,
            data={
                "refresh_token": auth_token.refresh_token,
                "grant_type": "refresh_token",
                "client_id": OAUTH2_CLIENT_ID,
                "client_secret": OAUTH2_CLIENT_SECRET,
            },
        )

        response.raise_for_status()

        return AuthToken(**await response.json())

    @property
    async def access_token(self) -> str:
        """Return a valid access token."""
        if not self.auth_token.valid_in(timedelta(hours=2, minutes=59)):
            try:
                self.auth_token = await self.refresh_access_token(self.auth_token)
                _LOGGER.debug(
                    f"Refreshed Auth Token. Now expires at {self.auth_token.expires_at} (in {self.auth_token.expires_in})"
                )
            except Exception as err:
                raise InvalidAuthError("Invalid refresh token") from err

        return self.auth_token.access_token

    async def get_home_data(self) -> list[VeluxHome]:
        """Get the home data."""

        access_token = await self.access_token
        response = await self._websession.request(
            "POST", API_URL + "/api/gethomedata", data={"access_token": access_token}
        )

        response.raise_for_status()

        # {'body': {'homes': [{'id': '648568c7fea0e6dd240ca4db', 'name': 'Chata', 'share_info': False, 'gone_after': 14400, 'smart_notifs': True, 'notify_movements': 'empty', 'record_movements': 'empty', 'notify_unknowns': 'empty', 'record_alarms': 'always', 'record_animals': 'empty', 'notify_animals': 'empty', 'events_ttl': 'one_month', 'persons': [], 'record_humans': 'empty', 'notify_humans': 'empty', 'outdoor_record_movements': 'always', 'outdoor_record_animals': 'always', 'outdoor_record_vehicles': 'always', 'outdoor_record_humans': 'always', 'outdoor_notify_movements': 'never', 'outdoor_notify_animals': 'never', 'outdoor_notify_vehicles': 'always', 'outdoor_notify_humans': 'always', 'outdoor_enable_notification_range': 'empty', 'outdoor_notification_begin': 0, 'outdoor_notification_end': 86399, 'doorbell_record_humans': 'always', 'doorbell_notify_humans': 'always', 'place': {'altitude': 293, 'city': 'Prague', 'country': 'CZ', 'location': [14.362734, 50.016443], 'timezone': 'Europe/Prague'}, 'cameras': [], 'smokedetectors': [], 'admin_access_code': None}], 'user': {'reg_locale': 'cs-CZ', 'lang': 'cs-CZ', 'country': 'CZ', 'mail': 'michal@cichra.cz', 'pending_user_consent': True, 'app_telemetry': False}, 'global_info': {'show_tags': True}}, 'status': 'ok', 'time_exec': 0.01279902458190918, 'time_server': 1726354813}
        response_json = await response.json()
        _LOGGER.debug(response_json)

        for home in response_json["body"]["homes"]:
            _LOGGER.debug(home)

        return [VeluxHome(**home) for home in response_json["body"]["homes"]]

    async def get_home_statuses(self, home: VeluxHome) -> list[VeluxModule]:
        """Get the home data."""

        access_token = await self.access_token
        response = await self._websession.request(
            "POST",
            API_URL + "/api/homestatus",
            data={"access_token": access_token, "home_id": home.id},
        )

        response.raise_for_status()

        response_json = await response.json()

        _LOGGER.debug(await response.text())

        return [
            VeluxModule(home, **module)
            for module in response_json["body"]["home"]["modules"]
        ]


class InvalidAuthError(Exception):
    """Exception raised when authentication fails."""


@dataclass
class VeluxGatewayData:
    home: VeluxHome
    busy: bool
    calibrating: bool
    firmware_revision_netatmo: int
    firmware_revision_thirdparty: str
    hardware_version: int
    id: str
    is_raining: bool
    last_seen: int
    locked: bool
    locking: bool
    name: str
    pairing: str
    secure: bool
    type: str
    wifi_strength: int
    wifi_state: str
    outdated_weather_forecast: bool | None = None

    @property
    def unlocked(self) -> bool:
        return not self.locked

    def update(self, data: dict):
        """Update the dataclass attributes with new data."""
        for field in fields(self):
            if field.name in data:
                setattr(self, field.name, data[field.name])


@dataclass
class VeluxWindowData:
    home: VeluxHome
    current_position: int
    firmware_revision: int
    id: str
    last_seen: int
    manufacturer: str
    mode: str
    reachable: bool
    silent: bool
    target_position: int
    type: str
    velux_type: str
    bridge: str
    rain_position: int
    secure_position: int


@dataclass
class VeluxShutterData:
    home: VeluxHome
    current_position: int
    firmware_revision: int
    id: str
    last_seen: int
    manufacturer: str
    mode: str
    reachable: bool
    silent: bool
    target_position: int
    type: str
    velux_type: str
    bridge: str


@dataclass
class VeluxSwitchData:
    home: VeluxHome
    battery_level: int
    battery_percent: int
    firmware_revision: int
    id: str
    last_seen: int
    reachable: bool
    rf_strength: int
    type: str
    bridge: str
    battery_state: str
    rf_state: str
