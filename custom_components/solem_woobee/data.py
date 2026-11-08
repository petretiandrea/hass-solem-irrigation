"""Controller snapshots and entry-scoped coordinator type."""
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

from .woobee_api import WooBeeDeviceInfo, WooBeeState

if TYPE_CHECKING:
    from .coordinator import WooBeeCoordinator


@dataclass(frozen=True)
class WooBeeData:
    address: str
    device_info: WooBeeDeviceInfo
    state: WooBeeState
    rssi: int | None = None
    last_fetched: datetime | None = None


type WooBeeConfigEntry = ConfigEntry[WooBeeCoordinator]
