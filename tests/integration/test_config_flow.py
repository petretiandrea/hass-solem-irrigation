"""Exercise the actual HA flow manager, without Bluetooth hardware."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solem_woobee.const import DOMAIN
from custom_components.solem_woobee.data import WooBeeData
from custom_components.solem_woobee.woobee_api import (
    AuthenticationError, ConnectivityError, SessionTimeoutError, InvalidResponseError,
)

ADDRESS = "aa:bb:cc:dd:ee:ff"
DATA = WooBeeData(ADDRESS, SimpleNamespace(name="Garden"), SimpleNamespace())


@pytest.fixture(autouse=True)
def devices():
    with patch(
        "homeassistant.components.bluetooth.async_discovered_service_info",
        return_value=[SimpleNamespace(address=ADDRESS.upper(), name="WooBee")],
    ):
        yield


async def start(hass):
    return await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})


async def test_success(hass):
    with patch("custom_components.solem_woobee.config_flow_handler.async_validate_device", return_value=DATA), patch(
        "custom_components.solem_woobee.async_setup_entry", return_value=True,
    ):
        result = await start(hass)
        assert result["type"] == FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_ADDRESS: ADDRESS})
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ADDRESS: ADDRESS}
    assert result["result"].unique_id == ADDRESS
    assert result["title"] == "Garden"


@pytest.mark.parametrize(("error", "expected"), [
    (AuthenticationError(), "invalid_auth"),
    (ConnectivityError(), "cannot_connect"),
    (SessionTimeoutError(), "cannot_connect"),
    (InvalidResponseError(), "invalid_response"),
])
async def test_errors_and_retry(hass, error, expected):
    with patch("custom_components.solem_woobee.config_flow_handler.async_validate_device", side_effect=error):
        result = await start(hass)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_ADDRESS: ADDRESS})
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": expected}
    with patch("custom_components.solem_woobee.config_flow_handler.async_validate_device", return_value=DATA), patch(
        "custom_components.solem_woobee.async_setup_entry", return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_ADDRESS: ADDRESS})
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_duplicate(hass):
    MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS, data={CONF_ADDRESS: ADDRESS}).add_to_hass(hass)
    with patch("custom_components.solem_woobee.config_flow_handler.async_validate_device", new_callable=AsyncMock) as validate:
        result = await start(hass)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_ADDRESS: ADDRESS})
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    validate.assert_not_called()


async def test_no_devices(hass):
    with patch("homeassistant.components.bluetooth.async_discovered_service_info", return_value=[]):
        result = await start(hass)
    assert result["reason"] == "no_devices_found"
