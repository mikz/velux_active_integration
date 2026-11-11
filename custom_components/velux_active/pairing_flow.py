"""Pair a gateway through its physical button; signing secrets stay in entry options."""

from functools import partial
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState, ConfigFlowResult, OptionsFlow
from homeassistant.helpers import selector

from .api import APIConnectionError, VeluxGatewayData
from .coordinator import VeluxActiveConfigEntry
from .velux_active_client.pairing import VeluxPairingError, retrieve_signing_key


class VeluxPairingFlow(OptionsFlow):
    """Optional cloud window control, bound to a gateway from the authenticated account."""

    config_entry: VeluxActiveConfigEntry
    _host: str
    _gateway_id: str

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if self.config_entry.state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="not_loaded")
        coordinator = self.config_entry.runtime_data
        gateways = {
            device.id: device.name or device.id
            for snapshot in coordinator.data.values()
            for device in snapshot["devices"]
            if isinstance(device, VeluxGatewayData)
        }
        errors = {}
        if user_input is not None:
            gateway_id = user_input["gateway_id"]
            if gateway_id not in gateways:
                errors["base"] = "pairing_failed"
            else:
                gateway = next(
                    device
                    for snapshot in coordinator.data.values()
                    for device in snapshot["devices"]
                    if device.id == gateway_id
                )
                try:
                    await coordinator.api.set_state(
                        {
                            "id": gateway.home.id,
                            "modules": [{"id": gateway_id, "retrieve_key": True}],
                        }
                    )
                except APIConnectionError:
                    errors["base"] = "pairing_failed"
                else:
                    self._host = user_input["gateway_host"].strip()
                    self._gateway_id = gateway_id
                    return await self.async_step_pair_button()
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("gateway_id"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value=key, label=name)
                                for key, name in gateways.items()
                            ]
                        )
                    ),
                    vol.Required("gateway_host"): selector.TextSelector(),
                }
            ),
            errors=errors,
        )

    async def async_step_pair_button(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            try:
                key = await self.hass.async_add_executor_job(
                    partial(retrieve_signing_key, host=self._host)
                )
            except VeluxPairingError, OSError:
                errors["base"] = "pairing_failed"
            else:
                return self.async_create_entry(
                    title="",
                    data={
                        **self.config_entry.options,
                        "gateway_id": self._gateway_id,
                        "sign_key_id": key.sign_key_id,
                        "hash_sign_key": key.hash_sign_key,
                    },
                )
        return self.async_show_form(
            step_id="pair_button", data_schema=vol.Schema({}), errors=errors
        )
