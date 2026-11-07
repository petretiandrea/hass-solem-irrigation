"""Select and verify a controller using Home Assistant Bluetooth.

WooBee uses a fixed protocol key, not user credentials. Authentication is
repeated for each connection; there is no credential reauthentication flow.
Automatic discovery awaits a verified advertisement matcher.
"""
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResult

from ..connection import async_validate_device
from ..const import DOMAIN
from ..woobee_api import AuthenticationError, ConnectivityError, InvalidResponseError, normalize_address


class WooBeeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure one entry per BLE controller."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors = {}
        devices = {
            normalize_address(info.address): f"{info.name or 'Bluetooth'} ({info.address})"
            for info in bluetooth.async_discovered_service_info(self.hass, connectable=True)
        }
        if user_input is not None:
            try:
                address = normalize_address(user_input[CONF_ADDRESS])
                await self.async_set_unique_id(address)
                self._abort_if_unique_id_configured()
                data = await async_validate_device(self.hass, address)
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except (ConnectivityError, TimeoutError):
                errors["base"] = "cannot_connect"
            except InvalidResponseError:
                errors["base"] = "invalid_response"
            else:
                return self.async_create_entry(
                    title=data.device_info.name or f"SOLEM WooBee {address}",
                    data={CONF_ADDRESS: address},
                )
        if not devices:
            return self.async_abort(reason="no_devices_found")
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(devices)}),
            errors=errors,
        )
