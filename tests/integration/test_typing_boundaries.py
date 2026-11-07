"""Persisted HA mappings are validated before entering the typed domain API."""
from unittest.mock import patch

import pytest
import voluptuous as vol
from homeassistant.const import CONF_ADDRESS
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solem_woobee.config_flow_handler import WooBeeConfigFlow
from custom_components.solem_woobee.const import DOMAIN
from custom_components.solem_woobee.coordinator import WooBeeCoordinator
from custom_components.solem_woobee.diagnostics import async_get_config_entry_diagnostics
from custom_components.solem_woobee.valve import DURATION_OPTIONS, WooBeeValve
from test_coordinator import ADDRESS


async def test_invalid_persisted_address(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_ADDRESS: 123})
    with pytest.raises(ValueError, match="address must be a string"):
        WooBeeCoordinator(hass, entry)


@pytest.mark.parametrize("durations,error", [([], ValueError), ({1: 2}, ValueError),
                                                      ({"1": True}, vol.Invalid)])
async def test_invalid_persisted_durations(hass, durations, error):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_ADDRESS: ADDRESS},
                            options={DURATION_OPTIONS: durations})
    coordinator = WooBeeCoordinator(hass, entry)
    entry.runtime_data = coordinator
    valve = WooBeeValve(entry, 1)
    with pytest.raises(error):
        _ = valve.default_duration_minutes
    await coordinator.async_shutdown()


async def test_untyped_flow_input(hass):
    flow = WooBeeConfigFlow()
    flow.hass = hass
    with patch("homeassistant.components.bluetooth.async_discovered_service_info", return_value=[]):
        assert (await flow.async_step_user({CONF_ADDRESS: 123}))["reason"] == "no_devices_found"


async def test_diagnostics_without_polling(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_ADDRESS: ADDRESS})
    entry.runtime_data = WooBeeCoordinator(hass, entry)
    entry.runtime_data.update_interval = None
    assert (await async_get_config_entry_diagnostics(hass, entry))["poll_interval_seconds"] is None
    await entry.runtime_data.async_shutdown()
