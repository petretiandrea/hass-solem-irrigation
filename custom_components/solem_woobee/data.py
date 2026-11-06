"""Entry-scoped data; BLE sessions are opened only for individual operations."""
from dataclasses import dataclass
from .woobee_api import WooBeeDeviceInfo, WooBeeState

from homeassistant.config_entries import ConfigEntry


@dataclass
class WooBeeData:
    address: str
    device_info: WooBeeDeviceInfo
    state: WooBeeState


type WooBeeConfigEntry = ConfigEntry[WooBeeData]
