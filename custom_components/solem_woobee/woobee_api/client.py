"""Read-only GATT inspection and managed WooBee connection scopes."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from types import TracebackType
from typing import Protocol, runtime_checkable

from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.backends.service import BleakGATTService

from .models import ControllerIdentity
from .protocol import SolemSession, WOOBEE_V2_GATT, WooBeeV2
from .transport import BLETransport


class Scanner(Protocol):
    async def discover(self, timeout: float) -> list[BLEDevice]: ...


class ClientFactory(Protocol):
    def __call__(self, address: str, /) -> BLETransport: ...


@runtime_checkable
class LegacyServices(Protocol):
    async def get_services(self) -> Iterable[BleakGATTService]: ...


class InspectionClient(Protocol):
    @property
    def services(self) -> Iterable[BleakGATTService]: ...
    async def __aenter__(self) -> object: ...
    async def __aexit__(self, exc_type: type[BaseException] | None,
                        exc: BaseException | None, tb: TracebackType | None) -> object: ...
    async def read_gatt_char(self, characteristic: BleakGATTCharacteristic, /) -> bytearray: ...


class InspectionFactory(Protocol):
    def __call__(self, address: str, /) -> InspectionClient: ...


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

    def __init__(self, scanner: Scanner, client_factory: InspectionFactory) -> None:
        self._scanner = scanner
        self._client_factory = client_factory

    @classmethod
    def local(cls) -> "WooBeeClient":
        """Build client using host Bluetooth adapter."""

        return cls(BleakScanner, BleakClient)

    async def discover(self, timeout: float = 5.0) -> list[BLEDevice]:
        """Return advertisements. WooBee advertised name is not assumed."""
        return await self._scanner.discover(timeout=timeout)

    async def inspect(self, address: str) -> WooBeeProfile:
        """Read every readable characteristic; never writes or subscribes."""
        client = self._client_factory(address)
        async with client:
            # Bleak 2.x exposes services as a property; 0.x used a coroutine.
            services = (await client.get_services()
                        if isinstance(client, LegacyServices) and callable(client.get_services)
                        else client.services)
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
            device: object = getattr(client, "device", None)
            name: object = getattr(device, "name", None)
            rssi: object = getattr(device, "rssi", None)
            return WooBeeProfile(
                address=address,
                name=name if isinstance(name, str) else None,
                rssi=rssi if isinstance(rssi, int) else None,
                services=tuple(result),
            )



class WooBeeConnection:
    """Factory-backed connection scope; owns only the client it creates.

    Pass an address-bound async BLE factory (e.g. an HA Bluetooth connector
    adapter). Connect/disconnect and authentication are managed by this scope.
    A new scope always means a fresh challenge; commands are never replayed.
    """

    def __init__(self, address: str, client_factory: ClientFactory) -> None:
        self.identity = ControllerIdentity(address)
        self._factory = client_factory
        self._address = address
        self._session: SolemSession | None = None

    async def __aenter__(self) -> WooBeeV2:
        if self._session is not None:
            raise RuntimeError("connection scope cannot be reused")
        self._session = SolemSession(self._factory(self._address), WOOBEE_V2_GATT,
                                     owns_connection=True)
        await self._session.__aenter__()
        return WooBeeV2(self._session)

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._session is None:
            raise RuntimeError("connection scope has not been entered")
        await self._session.__aexit__(exc_type, exc, tb)
