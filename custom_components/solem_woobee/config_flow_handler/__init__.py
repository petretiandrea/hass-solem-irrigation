"""Select and verify a controller using Home Assistant Bluetooth.

WooBee uses a fixed protocol key, not user credentials. Authentication is
repeated for each connection; there is no credential reauthentication flow.
Automatic discovery awaits a verified advertisement matcher.
"""
import voluptuous as vol
from homeassistant import config_entries, data_entry_flow
from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import device_registry as dr

from ..connection import async_validate_device
from ..const import DOMAIN
from ..data import WooBeeConfigEntry
from ..woobee_api import AuthenticationError, ConnectivityError, InvalidResponseError, normalize_address


class WooBeeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure one entry per BLE controller."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, object] | None = None) -> ConfigFlowResult:
        errors = {}
        devices = {
            normalize_address(info.address): f"{info.name or 'Bluetooth'} ({info.address})"
            for info in bluetooth.async_discovered_service_info(self.hass, connectable=True)
        }
        if user_input is not None:
            try:
                raw_address = user_input[CONF_ADDRESS]
                if not isinstance(raw_address, str):
                    raise InvalidResponseError("controller address must be a string")
                address = normalize_address(raw_address)
                self._abort_if_address_configured(address)
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
                self._abort_if_address_configured(address)
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

    async def async_step_reconfigure(
        self, user_input: dict[str, object] | None = None,
    ) -> ConfigFlowResult:
        """Change transport address while retaining the legacy registry identity."""
        entry: WooBeeConfigEntry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            try:
                raw_address = user_input[CONF_ADDRESS]
                if not isinstance(raw_address, str):
                    raise ValueError("controller address must be a string")
                address = normalize_address(raw_address)
            except ValueError:
                errors["base"] = "invalid_address"
            else:
                self._abort_if_address_configured(address, exclude_entry_id=entry.entry_id)
                if not user_input["same_controller"]:
                    errors["base"] = "confirm_controller"
                else:
                    try:
                        data = await async_validate_device(self.hass, address)
                    except AuthenticationError:
                        errors["base"] = "invalid_auth"
                    except (ConnectivityError, TimeoutError):
                        errors["base"] = "cannot_connect"
                    except InvalidResponseError:
                        errors["base"] = "invalid_response"
                    else:
                        devices = dr.async_entries_for_config_entry(
                            dr.async_get(self.hass), entry.entry_id,
                        )
                        known_serials = {device.serial_number for device in devices if device.serial_number}
                        if not known_serials:
                            errors["base"] = "identity_unavailable"
                        elif data.device_info.serial not in known_serials:
                            errors["base"] = "wrong_controller"
                        else:
                            # Validation yields: check again before committing the new address.
                            self._abort_if_address_configured(address, exclude_entry_id=entry.entry_id)
                            return self.async_update_reload_and_abort(
                                entry,
                                data_updates={
                                    CONF_ADDRESS: address,
                                    "identity_address": entry.data.get("identity_address", entry.data[CONF_ADDRESS]),
                                },
                            )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({
                vol.Required(CONF_ADDRESS, default=entry.data[CONF_ADDRESS]): str,
                vol.Required("same_controller", default=False): bool,
            }),
            errors=errors,
        )

    def _abort_if_address_configured(self, address: str, *, exclude_entry_id: str | None = None) -> None:
        """Reserve both current transport and historical registry addresses."""
        for entry in self._async_current_entries():
            if entry.entry_id == exclude_entry_id:
                continue
            if address in {
                normalize_address(entry.data[CONF_ADDRESS]),
                normalize_address(entry.data.get("identity_address", entry.data[CONF_ADDRESS])),
            }:
                raise data_entry_flow.AbortFlow("already_configured")
