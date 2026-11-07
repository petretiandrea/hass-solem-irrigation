"""Anonymous synthetic snapshots; diagnostics must never contact hardware."""
from dataclasses import replace
import json
from unittest.mock import patch

import pytest
from homeassistant.const import CONF_ADDRESS
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import get_diagnostics_for_config_entry

from custom_components.solem_woobee.const import DOMAIN
from custom_components.solem_woobee.coordinator import WooBeeCoordinator
from custom_components.solem_woobee.diagnostics import async_get_config_entry_diagnostics
from test_coordinator import snapshot, ADDRESS


@pytest.mark.parametrize("available", [True, False])
async def test_anonymous_cached_diagnostics(hass, available):
    secret = "synthetic-person@example.invalid token=password"
    entry = MockConfigEntry(domain=DOMAIN, title=secret, unique_id=ADDRESS,
                            data={CONF_ADDRESS: ADDRESS, "token": secret},
                            options={"password": secret})
    coordinator = WooBeeCoordinator(hass, entry)
    entry.runtime_data = coordinator
    data = snapshot()
    coordinator.async_set_updated_data(replace(data, device_info=replace(
        data.device_info, name=secret, serial=secret, uuid=secret,
        bluetooth_address=ADDRESS, raw_identification=(secret.encode(),),
        raw_uuid=(secret.encode(),)), state=replace(data.state,
        status=replace(data.state.status, raw_pages=(secret.encode(),)))))
    coordinator.last_update_success = available
    with patch("custom_components.solem_woobee.coordinator.async_validate_device") as read:
        result = await async_get_config_entry_diagnostics(hass, entry)
        read.assert_not_called()
    encoded = json.dumps(result)
    assert secret not in encoded
    assert ADDRESS not in encoded
    assert "raw" not in encoded.replace("battery_raw", "")
    assert result["last_update_success"] is available
    assert result["poll_interval_seconds"] == 300
    assert result["snapshot"]["zone_remaining_seconds"] == [0, 0, None, None]
    assert result["snapshot"]["battery_raw"] == 90
    assert result["snapshot"]["faulty_zones"] == []
    assert coordinator.data.device_info.name == secret
    await coordinator.async_shutdown()


async def test_diagnostics_before_first_snapshot(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_ADDRESS: ADDRESS})
    entry.runtime_data = WooBeeCoordinator(hass, entry)
    result = await async_get_config_entry_diagnostics(hass, entry)
    assert result["snapshot"] is None
    assert result["last_update_success"] is True
    await entry.runtime_data.async_shutdown()


async def test_ha_diagnostics_download(hass, hass_client):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS, data={CONF_ADDRESS: ADDRESS})
    entry.add_to_hass(hass)
    with patch("custom_components.solem_woobee.coordinator.async_validate_device", return_value=snapshot()) as read:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        result = await get_diagnostics_for_config_entry(hass, hass_client, entry)
        assert result == await async_get_config_entry_diagnostics(hass, entry)
        assert read.await_count == 1
        assert await hass.config_entries.async_unload(entry.entry_id)
