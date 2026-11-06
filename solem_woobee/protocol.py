"""MySOLEM 6.13.3 BLE transport and WooBee V2 frames.

Every command frame below is recovered statically from the APK's
``BluetoothV6FrameManager``. No packet capture is used.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID

# `BleManager.isAlreadyAuthenticatedLiteral()` compares this exact byte sequence.
AUTHENTICATED = {b"AUTHENTICATED\x00"}
SOLEM_STANDARD_KEY = "6D680000B74F429C81D47E10E7408105"


class AuthenticationError(RuntimeError):
    pass


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
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    return Cipher(algorithms.AES(key), modes.ECB()).encryptor().update(challenge)


def ctr_crypt(payload: bytes, key: bytes, nonce: bytes) -> bytes:
    if len(nonce) != 16:
        raise ValueError("SOLEM nonce must be 16 bytes")
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    return Cipher(algorithms.AES(key), modes.CTR(nonce)).encryptor().update(payload)


class SolemSession:
    """One MySOLEM-compatible authenticated GATT session."""

    def __init__(self, client: object, gatt: SolemGatt) -> None:
        self._client = client
        self._gatt = gatt
        self._notifications: asyncio.Queue[bytes] = asyncio.Queue()
        self._authenticated: asyncio.Future[None] | None = None
        self._nonce: bytes | None = None

    def _on_auth(self, _characteristic: object, value: bytearray) -> None:
        if bytes(value) in AUTHENTICATED and self._authenticated and not self._authenticated.done():
            self._authenticated.set_result(None)

    def _on_response(self, _characteristic: object, value: bytearray) -> None:
        self._notifications.put_nowait(bytes(value))

    async def authenticate(self, timeout: float = 10.0) -> None:
        """Read challenge, write AES response, wait MySOLEM auth acknowledgement."""
        loop = asyncio.get_running_loop()
        self._authenticated = loop.create_future()
        await self._client.start_notify(self._gatt.auth_uuid, self._on_auth)
        await self._client.start_notify(self._gatt.response_uuid, self._on_response)
        self._nonce = bytes(await self._client.read_gatt_char(self._gatt.auth_uuid))
        response = ecb_encrypt(self._nonce, self._gatt.key)
        await self._client.write_gatt_char(self._gatt.auth_uuid, response, response=True)
        try:
            await asyncio.wait_for(self._authenticated, timeout)
        except TimeoutError as exc:
            raise AuthenticationError("SOLEM controller did not authenticate") from exc

    async def exchange(self, frame: bytes, timeout: float = 20.0) -> bytes:
        """Send one recovered controller frame; return one decrypted notification."""
        if self._nonce is None:
            raise AuthenticationError("authenticate before exchanging frames")
        await self._client.write_gatt_char(
            # BleManager.doWriteCharacteristic(): Android WRITE_TYPE_NO_RESPONSE (1).
            self._gatt.request_uuid, ctr_crypt(frame, self._gatt.key, self._nonce), response=False
        )
        encrypted = await asyncio.wait_for(self._notifications.get(), timeout)
        return ctr_crypt(encrypted, self._gatt.key, self._nonce)

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

    async def exchange_all(self, frame: bytes, timeout: float = 20.0) -> list[bytes]:
        """Send frame and collect all its V6 replies, as MySOLEM does."""
        first = await self.exchange(frame, timeout)
        replies = [first]
        while not self._is_last_new_generation_reply(replies[-1]):
            encrypted = await asyncio.wait_for(self._notifications.get(), timeout)
            replies.append(ctr_crypt(encrypted, self._gatt.key, self._nonce))
        return replies


# Observed on user-owned WooBee V2 WB-4 firmware 7.0.2.
WOOBEE_V2_GATT = SolemGatt(
    pattern="A98C000%d-53E4-441C-96AF-B318E57E3B91",
    key_hex=SOLEM_STANDARD_KEY,
)


class WooBeeV2:
    """WooBee V2/WB-4 commands selected by MySOLEM for firmware 7.0.2.

    ``zone`` is one-based. ``minutes`` has MySOLEM's ``ManualValve`` unit.
    """

    _MAX_SECONDS = (1 << 24) - 1

    def __init__(self, session: SolemSession) -> None:
        self._session = session

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

    async def read_state(self) -> "WooBeeState":
        """Return readable WB-4 state, parsed from MySOLEM Java logic."""
        from .responses import parse_state

        return parse_state(await self.read_state_raw())

    async def read_state_raw(self) -> dict[str, list[bytes]]:
        """APK: type 180 `readState()` sequence; decrypted replies without parsing."""
        return {
            "status": await self._session.exchange_all(b"\x3b\x00"),
            "valve_status": await self._session.exchange_all(b"\x19\x03\x00\x10\xff"),
            "input_alerts": await self._session.exchange_all(b"\x71\x00"),
        }

    async def _command_status(self, frame: bytes) -> "WooBeeStatus":
        # `manageAnswer()`: CMD_MANUAL_V5 → statusAnswerV5().
        from .responses import parse_status

        return parse_status(await self._session.exchange_all(frame))

    async def start_valve(self, zone: int, minutes: int) -> "WooBeeStatus":
        return await self._command_status(self.start_valve_frame(zone, minutes))

    async def stop(self) -> "WooBeeStatus":
        return await self._command_status(self.stop_frame())

    async def start_all(self, minutes: int) -> "WooBeeStatus":
        return await self._command_status(self.start_all_frame(minutes))

    async def start_program(self, program: int) -> "WooBeeStatus":
        return await self._command_status(self.start_program_frame(program))

    async def read_programs_raw(self) -> list[bytes]:
        """APK `readConfigV5()`: request all irrigation-program frames, unparsed."""
        return await self._session.exchange_all(b"\x39\x00")

    async def read_programs(self) -> tuple["IrrigationProgram", ...]:
        """Read and parse programs using MySOLEM `readConfigAnswerV5()` layout."""
        from .programs import parse_program_replies

        return parse_program_replies(await self.read_programs_raw())

    async def read_schedules(self) -> tuple["Schedule", ...]:
        from .programs import Schedule

        return tuple(Schedule.from_program(program) for program in await self.read_programs())

    async def write_program(self, program: "IrrigationProgram") -> list[list[bytes]]:
        """Persist one schedule using MySOLEM `configIrriV5()` frame sequence."""
        from .programs import build_program_frames

        return [await self._session.exchange_all(frame) for frame in build_program_frames(program)]

    async def write_schedule(self, schedule: "Schedule") -> list[list[bytes]]:
        return await self.write_program(schedule.to_program())
