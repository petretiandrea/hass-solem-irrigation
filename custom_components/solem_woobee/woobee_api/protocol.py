"""MySOLEM 6.13.3 BLE transport and WooBee V2 frames.

Every command frame below is recovered statically from the APK's
``BluetoothV6FrameManager``. No packet capture is used.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from uuid import UUID

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .errors import (
    AuthenticationError, ConnectivityError, InvalidResponseError,
    SessionTimeoutError, WooBeeError,
)
from .programs import (
    ControllerBackup, IrrigationProgram, Schedule,
    build_program_frames, parse_program_replies,
)
from .responses import (
    WooBeeDeviceInfo, WooBeeState, WooBeeStatus, WooBeeValveFaults,
    parse_device_info, parse_state, parse_status, parse_valve_faults,
)
from .transport import BLETransport

# `BleManager.isAlreadyAuthenticatedLiteral()` compares this exact byte sequence.
AUTHENTICATED = {b"AUTHENTICATED\x00"}
SOLEM_STANDARD_KEY = "6D680000B74F429C81D47E10E7408105"


@dataclass(frozen=True)
class SolemGatt:
    """UUID family and 128-bit authentication key for one controller type."""

    pattern: str
    key_hex: str

    def uuid(self, number: int) -> str:
        return str(UUID(self.pattern % number))

    @classmethod
    def from_read_uuid(cls, read_uuid: str, key_hex: str = SOLEM_STANDARD_KEY) -> "SolemGatt":
        """Build family from discovered characteristic `…0002-…`."""
        value = str(UUID(read_uuid)).upper()
        if not value[4:8] == "0002":
            raise ValueError("SOLEM request UUID must contain 0002")
        return cls(value[:4] + "000%d" + value[8:], key_hex)

    @property
    def request_uuid(self) -> str:
        return self.uuid(2)

    @property
    def response_uuid(self) -> str:
        return self.uuid(3)

    @property
    def auth_uuid(self) -> str:
        return self.uuid(5)

    @property
    def key(self) -> bytes:
        key = bytes.fromhex(self.key_hex)
        if len(key) != 16:
            raise ValueError("SOLEM BLE key must be 16 bytes")
        return key


def ecb_encrypt(challenge: bytes, key: bytes) -> bytes:
    if len(challenge) % 16:
        raise ValueError("SOLEM auth challenge must be AES block aligned")

    return Cipher(algorithms.AES(key), modes.ECB()).encryptor().update(challenge)


def ctr_crypt(payload: bytes, key: bytes, nonce: bytes) -> bytes:
    if len(nonce) != 16:
        raise ValueError("SOLEM nonce must be 16 bytes")

    return Cipher(algorithms.AES(key), modes.CTR(nonce)).encryptor().update(payload)


class SolemSession:
    """One authenticated connection. Borrowed connections are never disconnected.

    After any interrupted exchange close and reconnect: V6 has no transaction ID
    with which to distinguish a late reply. No commands are retried.
    """

    def __init__(self, client: BLETransport, gatt: SolemGatt, *, owns_connection: bool = False) -> None:
        self._client = client
        self._gatt = gatt
        self._owns_connection = owns_connection
        self._notifications: asyncio.Queue[bytes] = asyncio.Queue(maxsize=128)
        self._authenticated: asyncio.Future[None] | None = None
        self._nonce: bytes | None = None
        self._lock = asyncio.Lock()
        self._owner = None
        self._subscriptions: list[str] = []
        self._broken = False
        self._closed = False
        self._overflow = False

    @asynccontextmanager
    async def transaction(self):
        """Serialize a complete operation, including all of its requests."""
        task = asyncio.current_task()
        if self._owner is task:
            yield
            return
        async with self._lock:
            self._owner = task
            try:
                yield
            finally:
                self._owner = None

    async def __aenter__(self):
        try:
            if self._owns_connection:
                async with asyncio.timeout(10):
                    await self._client.connect()
            await self.authenticate()
            return self
        except BaseException as exc:
            try:
                await self.aclose()
            except ConnectivityError:
                pass
            if isinstance(exc, TimeoutError):
                raise SessionTimeoutError("BLE connect deadline exceeded") from exc
            if isinstance(exc, (asyncio.CancelledError, WooBeeError)):
                raise
            raise ConnectivityError("BLE connection failed") from exc

    async def __aexit__(self, exc_type, exc, tb):
        try:
            await self.aclose()
        except ConnectivityError:
            if exc is None:
                raise

    def _on_auth(self, _characteristic: object, value: bytearray) -> None:
        # Only the exact recovered success literal is known. Other notifications
        # are not evidence of credential rejection; let the auth deadline expire.
        if bytes(value) in AUTHENTICATED and self._authenticated and not self._authenticated.done():
            self._authenticated.set_result(None)

    def _on_response(self, _characteristic: object, value: bytearray) -> None:
        if self._closed or self._broken:
            return
        try:
            self._notifications.put_nowait(bytes(value))
        except asyncio.QueueFull:
            self._overflow = True

    async def aclose(self) -> None:
        """Remove callbacks, clear key material and release an owned connection."""
        async with self.transaction():
            if self._closed:
                return
            self._closed = True
            self._nonce = None
            if self._authenticated and not self._authenticated.done():
                self._authenticated.cancel()
            error = None
            for uuid in reversed(self._subscriptions):
                try:
                    async with asyncio.timeout(5):
                        await self._client.stop_notify(uuid)
                except Exception as exc:
                    error = exc
            self._subscriptions.clear()
            while not self._notifications.empty():
                self._notifications.get_nowait()
            if self._owns_connection:
                try:
                    async with asyncio.timeout(5):
                        await self._client.disconnect()
                except Exception as exc:
                    error = exc
            if error:
                raise ConnectivityError("BLE session cleanup failed") from error

    async def authenticate(self, timeout: float = 10.0) -> None:
        """Fresh challenge per connection; no cloud token or inferred expiry."""
        async with self.transaction():
            if self._broken or self._closed:
                raise ConnectivityError("create a new session on a fresh connection")
            if self._nonce is not None:
                return
            try:
                async with asyncio.timeout(timeout):
                    self._authenticated = asyncio.get_running_loop().create_future()
                    for uuid, callback in ((self._gatt.auth_uuid, self._on_auth),
                                           (self._gatt.response_uuid, self._on_response)):
                        await self._client.start_notify(uuid, callback)
                        self._subscriptions.append(uuid)
                    nonce = bytes(await self._client.read_gatt_char(self._gatt.auth_uuid))
                    if len(nonce) != 16:
                        raise InvalidResponseError("expected a 16-byte authentication challenge")
                    response = ecb_encrypt(nonce, self._gatt.key)
                    await self._client.write_gatt_char(self._gatt.auth_uuid, response, response=True)
                    await self._authenticated
                    self._nonce = nonce
            except BaseException as exc:
                self._broken = True
                try:
                    await self.aclose()
                except ConnectivityError:
                    pass
                if isinstance(exc, TimeoutError):
                    raise SessionTimeoutError("authentication deadline exceeded") from exc
                if isinstance(exc, (asyncio.CancelledError, WooBeeError)):
                    raise
                raise ConnectivityError("BLE authentication transport failed") from exc

    async def _receive(self) -> bytes:
        encrypted = await self._notifications.get()
        if self._overflow or not encrypted:
            raise InvalidResponseError("empty response or notification overflow")
        return ctr_crypt(encrypted, self._gatt.key, self._nonce)

    async def _exchange(self, frame: bytes, timeout: float, all_replies: bool):
        async with self.transaction():
            if self._closed or self._broken:
                raise ConnectivityError("create a new session on a fresh connection")
            if self._nonce is None:
                raise AuthenticationError("authenticate before exchanging frames")
            try:
                async with asyncio.timeout(timeout):
                    if not self._notifications.empty():
                        raise InvalidResponseError("unsolicited response before request")
                    await self._client.write_gatt_char(
                        self._gatt.request_uuid,
                        ctr_crypt(frame, self._gatt.key, self._nonce), response=False
                    )
                    expected = {0x31: 0x3C}.get(frame[0], (frame[0] + 1) & 0xFF)
                    replies = [await self._receive()]
                    if replies[0][0] != expected:
                        raise InvalidResponseError("unexpected response command")
                    while all_replies and not self._is_last_new_generation_reply(replies[-1]):
                        if len(replies) >= 128:
                            raise InvalidResponseError("too many V6 response pages")
                        reply = await self._receive()
                        if reply[0] != expected:
                            raise InvalidResponseError("unexpected response command")
                        replies.append(reply)
                    return replies
            except BaseException as exc:
                self._broken = True
                self._nonce = None
                try:
                    await self.aclose()
                except ConnectivityError:
                    pass
                if isinstance(exc, TimeoutError):
                    raise SessionTimeoutError("BLE exchange deadline exceeded; outcome unknown") from exc
                if isinstance(exc, (asyncio.CancelledError, WooBeeError)):
                    raise
                raise ConnectivityError("BLE exchange failed; outcome unknown") from exc

    async def exchange(self, frame: bytes, timeout: float = 20.0) -> bytes:
        return (await self._exchange(frame, timeout, False))[0]

    async def exchange_all(self, frame: bytes, timeout: float = 20.0) -> list[bytes]:
        return await self._exchange(frame, timeout, True)

    @staticmethod
    def _is_last_new_generation_reply(reply: bytes) -> bool:
        """Exact V6 `isLastAnswerForCommand()` rule for WooBee commands.

        Commands 0x19, 0x31, 0x3b and 0x71 are all V6/new-generation commands.
        """
        if len(reply) > 3 and reply[2] == 0xF0:
            return True
        if len(reply) <= 3 and len(reply) > 1 and reply[1] == 0xFE:
            return True
        return not (
            len(reply) > 2
            and reply[2] != 0
            and (len(reply) <= 3 or reply[3] != 0xF0 or (len(reply) > 4 and reply[4] != 0xF0))
        )



# Observed on user-owned WooBee V2 WB-4 firmware 7.0.2.
WOOBEE_V2_GATT = SolemGatt(
    pattern="A98C000%d-53E4-441C-96AF-B318E57E3B91",
    key_hex=SOLEM_STANDARD_KEY,
)


def serialized(method):
    @wraps(method)
    async def wrapped(self, *args, **kwargs):
        if isinstance(self._session, SolemSession):
            async with self._session.transaction():
                return await method(self, *args, **kwargs)
        return await method(self, *args, **kwargs)
    return wrapped


class WooBeeV2:
    """WooBee V2/WB-4 commands selected by MySOLEM for firmware 7.0.2.

    ``zone`` is one-based. ``minutes`` has MySOLEM's ``ManualValve`` unit.
    """

    _MAX_SECONDS = (1 << 24) - 1

    def __init__(self, session: SolemSession) -> None:
        self._session = session

    async def aclose(self) -> None:
        await self._session.aclose()

    @serialized
    async def authenticate(self) -> None:
        await self._session.authenticate()

    @staticmethod
    def _seconds(minutes: int) -> int:
        if not isinstance(minutes, int) or isinstance(minutes, bool) or minutes < 1:
            raise ValueError("minutes must be a positive integer")
        seconds = minutes * 60
        if seconds > WooBeeV2._MAX_SECONDS:
            raise ValueError("minutes exceeds MySOLEM's 24-bit duration")
        return seconds

    @staticmethod
    def start_valve_frame(zone: int, minutes: int) -> bytes:
        """APK: ManualValve → testValvesV5(outputIndex + 1, duration * 60)."""
        if not isinstance(zone, int) or isinstance(zone, bool) or not 1 <= zone <= 4:
            raise ValueError("zone must be an integer from 1 to 4")
        seconds = WooBeeV2._seconds(minutes)
        return bytes((0x31, 0x05, 0x12, zone)) + seconds.to_bytes(3, "big")

    @staticmethod
    def stop_frame() -> bytes:
        """APK: ManualStop → manualStopV5()."""
        return b"\x31\x05\x15\x00\xff\x00\x00"

    @staticmethod
    def start_all_frame(minutes: int) -> bytes:
        """APK: TestAllValves → manualRunValvesV5(duration * 60)."""
        return b"\x31\x05\x11\x00" + WooBeeV2._seconds(minutes).to_bytes(3, "big")

    @staticmethod
    def start_program_frame(program: int) -> bytes:
        """APK: ManualProgram → manualRunProgramV5(programIndex)."""
        if not isinstance(program, int) or isinstance(program, bool) or program < 0 or program > 255:
            raise ValueError("program must be an integer from 0 to 255")
        return bytes((0x31, 0x05, 0x14, 0x00, program, 0x00, 0x00))

    @staticmethod
    def set_clock_frame(when: datetime) -> bytes:
        """APK `setTimeV5()`: controller-local calendar time."""
        if not 1900 <= when.year <= 2155:
            raise ValueError("controller clock year must be from 1900 to 2155")
        return bytes((
            0x03,
            0x06,
            0x00,
            when.year - 1900,
            when.month,
            when.day,
            when.hour,
            when.minute,
            when.second,
        ))

    @staticmethod
    def reset_valve_faults_frame() -> bytes:
        """APK `resetValveStatusV5()`; clears latched valve fault bits."""
        return b"\x19\x03\x01\x7f\xff"

    @serialized
    async def read_state(self) -> "WooBeeState":
        """Return readable WB-4 state, parsed from MySOLEM Java logic."""

        return parse_state(await self.read_state_raw())

    @serialized
    async def read_device_info(self) -> "WooBeeDeviceInfo":
        """Read name, serial, hardware, firmware and controller UUID."""

        identity = await self._session.exchange_all(b"\x0f\x00")
        uuid = [await self._session.exchange(b"\xe3\x00")]
        return parse_device_info(identity, uuid)

    @serialized
    async def read_state_raw(self) -> dict[str, list[bytes]]:
        """APK: type 180 `readState()` sequence; decrypted replies without parsing."""
        return {
            "status": await self._session.exchange_all(b"\x3b\x00"),
            "valve_status": await self._session.exchange_all(b"\x19\x03\x00\x10\xff"),
            "input_alerts": await self._session.exchange_all(b"\x71\x00"),
        }

    @serialized
    async def _command_status(self, frame: bytes) -> "WooBeeStatus":
        # `manageAnswer()`: CMD_MANUAL_V5 → statusAnswerV5().

        return parse_status(await self._session.exchange_all(frame))

    @serialized
    async def start_valve(self, zone: int, minutes: int) -> "WooBeeStatus":
        return await self._command_status(self.start_valve_frame(zone, minutes))

    @serialized
    async def stop(self) -> "WooBeeStatus":
        return await self._command_status(self.stop_frame())

    @serialized
    async def start_all(self, minutes: int) -> "WooBeeStatus":
        return await self._command_status(self.start_all_frame(minutes))

    @serialized
    async def start_program(self, program: int) -> "WooBeeStatus":
        return await self._command_status(self.start_program_frame(program))

    @serialized
    async def sync_clock(self, when: datetime | None = None) -> list[bytes]:
        """Set controller clock to local current time or supplied calendar time."""
        return await self._session.exchange_all(self.set_clock_frame(when or datetime.now().astimezone()))

    @serialized
    async def reset_valve_faults(self) -> "WooBeeValveFaults":
        """Clear latched valve fault bits and return controller acknowledgement."""

        return parse_valve_faults((await self._session.exchange_all(self.reset_valve_faults_frame()))[-1])

    @serialized
    async def read_programs_raw(self) -> list[bytes]:
        """APK `readConfigV5()`: request all irrigation-program frames, unparsed."""
        return await self._session.exchange_all(b"\x39\x00")

    @serialized
    async def read_programs(self) -> tuple["IrrigationProgram", ...]:
        """Read and parse programs using MySOLEM `readConfigAnswerV5()` layout."""

        return parse_program_replies(await self.read_programs_raw())

    @serialized
    async def read_schedules(self) -> tuple["Schedule", ...]:
        return tuple(Schedule.from_program(program) for program in await self.read_programs())

    @serialized
    async def backup(self) -> "ControllerBackup":
        """Read all schedule data into portable client backup."""

        return ControllerBackup(await self.read_schedules())

    @serialized
    async def write_program(self, program: "IrrigationProgram") -> list[list[bytes]]:
        """Persist one schedule using MySOLEM `configIrriV5()` frame sequence."""

        return [await self._session.exchange_all(frame) for frame in build_program_frames(program)]

    @serialized
    async def write_schedule(self, schedule: "Schedule") -> list[list[bytes]]:
        return await self.write_program(schedule.to_program())

    @serialized
    async def restore(self, backup: "ControllerBackup") -> list[list[list[bytes]]]:
        """Persist every schedule from a client backup, in schedule order."""
        return [await self.write_schedule(schedule) for schedule in backup.schedules]
