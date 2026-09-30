"""Configure or renew VELUX account credentials through Home Assistant."""

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import aiohttp_client

from .api import APIConnectionError, InvalidAuthError, VeluxActiveAPI
from .const import DOMAIN


class VeluxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Preserve the original config entry while replacing expired credentials."""

    VERSION = 1

    async def _form(self, step_id, user_input):
        errors = {}
        if user_input is not None:
            api = VeluxActiveAPI(aiohttp_client.async_get_clientsession(self.hass))
            try:
                await api.authenticate(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
                await api.get_home_data()
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except APIConnectionError:
                errors["base"] = "cannot_connect"
            else:
                if step_id == "reauth_confirm":
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(), data_updates=user_input
                    )
                if step_id == "reconfigure":
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(), data_updates=user_input
                    )
                return self.async_create_entry(title="Velux Active", data=user_input)
        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_user(self, user_input=None):
        return await self._form("user", user_input)

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        return await self._form("reauth_confirm", user_input)

    async def async_step_reconfigure(self, user_input=None):
        return await self._form("reconfigure", user_input)
