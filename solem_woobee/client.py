"""Read-only BLE reconnaissance for WooBee V2 controllers.

shortcut: WooBee command frames are unknown; add writes after an HCI capture maps
the exact firmware's service, characteristic, framing, acknowledgement and commit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class Scanner(Protocol):
    async def discover(self, timeout: float) -> list[object]: ...


class ClientFactory(Protocol):
    def __call__(self, address: str) -> object: ...


@dataclass(frozen=True)
class GattCharacteristic:
    uuid: str
    properties: tuple[str, ...]
    value_hex: str | None
    read_error: str | None = None


@dataclass(frozen=True)
class GattService:
    uuid: str
    characteristics: tuple[GattCharacteristic, ...]


@dataclass(frozen=True)
class WooBeeProfile:
    address: str
    name: str | None
    rssi: int | None
    services: tuple[GattService, ...]


class WooBeeClient:
    """BLE transport. No valve write is attempted."""

    def __init__(self, scanner: Scanner, client_factory: ClientFactory) -> None:
        self._scanner = scanner
        self._client_factory = client_factory

    @classmethod
    def local(cls) -> "WooBeeClient":
        """Build client using host Bluetooth adapter."""
        from bleak import BleakClient, BleakScanner

        return cls(BleakScanner, BleakClient)

    async def discover(self, timeout: float = 5.0) -> list[object]:
        """Return advertisements. WooBee advertised name is not assumed."""
        return await self._scanner.discover(timeout=timeout)

    async def inspect(self, address: str) -> WooBeeProfile:
        """Read every readable characteristic; never writes or subscribes."""
        client = self._client_factory(address)
        async with client:
            # Bleak 2.x exposes services as a property; 0.x used a coroutine.
            get_services = getattr(client, "get_services", None)
            services = await get_services() if get_services else client.services
            result = []
            for service in services:
                characteristics = []
                for characteristic in service.characteristics:
                    properties = tuple(characteristic.properties)
                    value_hex = error = None
                    if "read" in properties:
                        try:
                            value_hex = bytes(await client.read_gatt_char(characteristic)).hex()
                        except Exception as exc:  # Device may require pairing/auth.
                            error = f"{type(exc).__name__}: {exc}"
                    characteristics.append(
                        GattCharacteristic(str(characteristic.uuid), properties, value_hex, error)
                    )
                result.append(GattService(str(service.uuid), tuple(characteristics)))
            device = getattr(client, "device", None)
            return WooBeeProfile(
                address=address,
                name=getattr(device, "name", None),
                rssi=getattr(device, "rssi", None),
                services=tuple(result),
            )

