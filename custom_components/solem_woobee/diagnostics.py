"""Anonymous, read-only diagnostics from the last coordinator snapshot.

Use an explicit allowlist: never serialize config entries, identities, exceptions,
raw BLE frames or transport/session objects (including fixed protocol keys).
"""
from homeassistant.core import HomeAssistant

from .data import WooBeeConfigEntry

type JSONValueType = None | bool | int | float | str | list[JSONValueType] | dict[str, JSONValueType]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: WooBeeConfigEntry,
) -> dict[str, JSONValueType]:
    """Return cached operational data without opening a BLE connection."""
    coordinator = entry.runtime_data
    data = coordinator.data
    result: dict[str, JSONValueType] = {
        "last_update_success": coordinator.last_update_success,
        "poll_interval_seconds": coordinator.update_interval.total_seconds() if coordinator.update_interval else None,
        "snapshot": None,
    }
    if data is None:
        return result
    status = data.state.status
    result["snapshot"] = {
        "enabled": status.enabled,
        "manual": status.manual,
        "sensor_open": status.sensor_open,
        "clock_alarm": status.clock_alarm,
        "rain_delay": status.rain_delay,
        "battery_raw": status.battery_raw,
        "active_program": status.active_program,
        "active_zone": status.active_zone,
        "remaining_seconds": status.remaining_seconds,
        "zone_remaining_seconds": list(status.zone_remaining_seconds),
        "faulty_zones": list(data.state.valve_faults.faulty_zones),
    }
    return result
