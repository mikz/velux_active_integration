"""Configure an account or renew its password without changing account identity."""

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import aiohttp_client, selector

from .api import APIConnectionError, InvalidAuthError, VeluxActiveAPI
from .const import DOMAIN
from .coordinator import VeluxActiveConfigEntry


class VeluxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Keep the original username/password storage and version-one identity."""

    VERSION = 1

    async def _form(
        self,
        step_id: str,
        user_input: dict[str, str] | None,
        entry: VeluxActiveConfigEntry | None = None,
    ) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            if entry is not None and user_input[CONF_USERNAME] != entry.data[CONF_USERNAME]:
                errors["base"] = "wrong_account"
            else:
                api = VeluxActiveAPI(aiohttp_client.async_get_clientsession(self.hass))
                try:
                    await api.authenticate(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
                    await api.get_home_data()
                except InvalidAuthError:
                    errors["base"] = "invalid_auth"
                except APIConnectionError:
                    errors["base"] = "cannot_connect"
                else:
                    if entry is not None:
                        return self.async_update_reload_and_abort(entry, data_updates=user_input)
                    return self.async_create_entry(title="Velux Active", data=user_input)
        username = vol.Required(CONF_USERNAME)
        if entry is not None:
            username = vol.Required(CONF_USERNAME, default=entry.data[CONF_USERNAME])
        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(
                {
                    username: selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.EMAIL)
                    ),
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_user(self, user_input: dict[str, str] | None = None) -> ConfigFlowResult:
        return await self._form("user", user_input)

    async def async_step_reauth(self, entry_data: dict[str, str]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        return await self._form("reauth_confirm", user_input, self._get_reauth_entry())

    async def async_step_reconfigure(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        return await self._form("reconfigure", user_input, self._get_reconfigure_entry())
