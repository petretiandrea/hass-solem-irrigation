"""Stable identities independent of names, serials and Home Assistant."""
from dataclasses import dataclass
from uuid import UUID
import re


def normalize_address(address: str) -> str:
    compact = address.replace(":", "").replace("-", "")
    if re.fullmatch(r"[0-9a-fA-F]{12}", compact):
        return ":".join(compact[i:i + 2] for i in range(0, 12, 2)).lower()
    try:
        return str(UUID(address))  # CoreBluetooth identifier
    except (ValueError, AttributeError) as exc:
        raise ValueError("expected a BLE MAC address or CoreBluetooth UUID") from exc


@dataclass(frozen=True)
class ControllerIdentity:
    address: str

    def __post_init__(self):
        object.__setattr__(self, "address", normalize_address(self.address))

    @property
    def unique_id(self) -> str:
        return self.address

    @property
    def zones(self) -> tuple["ZoneIdentity", ...]:
        return tuple(ZoneIdentity(self, number) for number in range(1, 5))


@dataclass(frozen=True)
class ZoneIdentity:
    controller: ControllerIdentity
    number: int

    def __post_init__(self):
        if type(self.number) is not int or not 1 <= self.number <= 4:
            raise ValueError("zone must be an integer from 1 to 4")

    @property
    def unique_id(self) -> str:
        return f"{self.controller.unique_id}_zone_{self.number}"
