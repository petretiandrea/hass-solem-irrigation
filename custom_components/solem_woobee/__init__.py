"""SOLEM WooBee integration lifecycle."""
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .coordinator import WooBeeCoordinator
from .data import WooBeeConfigEntry
from .entity import controller_device_info

PLATFORMS: list[Platform] = []


async def async_setup_entry(hass: HomeAssistant, entry: WooBeeConfigEntry) -> bool:
    """Load one shared snapshot and register the physical controller."""
    coordinator = WooBeeCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, **controller_device_info(coordinator.data)
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WooBeeConfigEntry) -> bool:
    """Successful unload removes listeners and shuts down scheduled refreshes."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await entry.runtime_data.async_shutdown()
    return True
