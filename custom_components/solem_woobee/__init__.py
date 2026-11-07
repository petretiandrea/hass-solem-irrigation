"""SOLEM WooBee integration lifecycle."""
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .connection import async_validate_device
from .data import WooBeeConfigEntry
from .woobee_api import AuthenticationError, ConnectivityError, InvalidResponseError

PLATFORMS: list[Platform] = []


async def async_setup_entry(hass: HomeAssistant, entry: WooBeeConfigEntry) -> bool:
    """Verify the controller before loading platforms; retain no live session."""
    try:
        entry.runtime_data = await async_validate_device(hass, entry.data[CONF_ADDRESS])
    except ConnectivityError as exc:
        raise ConfigEntryNotReady("Controller unavailable") from exc
    except (AuthenticationError, InvalidResponseError) as exc:
        raise ConfigEntryError("Controller authentication or protocol not supported") from exc
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WooBeeConfigEntry) -> bool:
    """Unload platforms; no persistent connections, tasks or listeners are owned."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
