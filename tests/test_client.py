import unittest
from datetime import date, datetime

from woobee_api import ControllerBackup, SolemGatt, SolemSession, WOOBEE_V2_GATT, WooBeeClient, WooBeeV2
from woobee_api.protocol import ctr_crypt
from woobee_api.programs import (
    Days,
    IrrigationProgram,
    ProgramCycle,
    Schedule,
    TimeOfDay,
    Weekday,
    ZoneDurations,
    build_program_frames,
    parse_program_replies,
)
from woobee_api.responses import parse_device_info, parse_state


class Characteristic:
    uuid = "a4490001-332e-bbae-a5e1-9d6bd1fdea5b"
    properties = ["read", "write"]


class Service:
    uuid = "a4490000-332e-bbae-a5e1-9d6bd1fdea5b"
    characteristics = [Characteristic()]


class FakeClient:
    device = type("Device", (), {"name": "WooBee V2", "rssi": -61})()

    def __init__(self, address):
        self.address = address

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def get_services(self):
        return [Service()]

    async def read_gatt_char(self, characteristic):
        return b"\x07\x00\x02"


class FakeBleak2Client(FakeClient):
    get_services = None
    services = [Service()]


class TransportClient:
    def __init__(self):
        self.writes = []

    async def write_gatt_char(self, uuid, value, response):
        self.writes.append((uuid, bytes(value), response))


class ClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_inspect_reads_without_writing(self):
        client = WooBeeClient(None, FakeClient)

        profile = await client.inspect("AA:BB:CC:DD:EE:FF")

        characteristic = profile.services[0].characteristics[0]
        self.assertEqual("WooBee V2", profile.name)
        self.assertEqual("070002", characteristic.value_hex)
        self.assertEqual(("read", "write"), characteristic.properties)

    async def test_inspect_supports_bleak_2_services_property(self):
        profile = await WooBeeClient(None, FakeBleak2Client).inspect("AA:BB:CC:DD:EE:FF")

        self.assertEqual("070002", profile.services[0].characteristics[0].value_hex)

    async def test_uuid_family_derives_auth_and_response(self):
        gatt = SolemGatt.from_read_uuid("108b0002-eab5-bc09-d0ea-0b8f467ce8ee")

        self.assertEqual("108b0003-eab5-bc09-d0ea-0b8f467ce8ee", gatt.response_uuid)
        self.assertEqual("108b0005-eab5-bc09-d0ea-0b8f467ce8ee", gatt.auth_uuid)

    async def test_woobee_v2_profile_matches_discovered_gatt(self):
        self.assertEqual("a98c0002-53e4-441c-96af-b318e57e3b91", WOOBEE_V2_GATT.request_uuid)
        self.assertEqual("a98c0005-53e4-441c-96af-b318e57e3b91", WOOBEE_V2_GATT.auth_uuid)

    async def test_static_woobee_manual_frames_match_mysolem(self):
        self.assertEqual(b"\x31\x05\x12\x01\x00\x00\x3c", WooBeeV2.start_valve_frame(1, 1))
        self.assertEqual(b"\x31\x05\x15\x00\xff\x00\x00", WooBeeV2.stop_frame())
        self.assertEqual(b"\x31\x05\x11\x00\x00\x00\x3c", WooBeeV2.start_all_frame(1))
        self.assertEqual(b"\x31\x05\x14\x00\x00\x00\x00", WooBeeV2.start_program_frame(0))
        self.assertEqual(
            bytes.fromhex("0306007e0b06090807"),
            WooBeeV2.set_clock_frame(datetime(2026, 11, 6, 9, 8, 7)),
        )
        self.assertEqual(bytes.fromhex("1903017fff"), WooBeeV2.reset_valve_faults_frame())

    async def test_static_woobee_frame_validation(self):
        with self.assertRaises(ValueError):
            WooBeeV2.start_valve_frame(0, 1)
        with self.assertRaises(ValueError):
            WooBeeV2.start_valve_frame(1, 0)

    async def test_exchange_matches_apk_no_response_write_and_decrypts_reply(self):
        client = TransportClient()
        session = SolemSession(client, WOOBEE_V2_GATT)
        session._nonce = bytes(range(16))
        reply = b"\x3c\x00\x02"
        original_write = client.write_gatt_char
        async def write(*args, **kwargs):
            await original_write(*args, **kwargs)
            session._on_response(None, bytearray(ctr_crypt(reply, WOOBEE_V2_GATT.key, session._nonce)))
        client.write_gatt_char = write

        self.assertEqual(reply, await session.exchange(b"\x3b\x00"))
        uuid, payload, response = client.writes[0]
        self.assertEqual(WOOBEE_V2_GATT.request_uuid, uuid)
        self.assertFalse(response)
        self.assertEqual(b"\x3b\x00", ctr_crypt(payload, WOOBEE_V2_GATT.key, session._nonce))

    def test_v6_reply_completion_matches_static_manager(self):
        self.assertFalse(SolemSession._is_last_new_generation_reply(b"\x3c\x10\x02\x00"))
        self.assertFalse(SolemSession._is_last_new_generation_reply(b"\x3c\x10\x01\x00"))
        self.assertTrue(SolemSession._is_last_new_generation_reply(b"\x3c\x10\x00\x00"))
        self.assertTrue(SolemSession._is_last_new_generation_reply(b"\x3c\xfe\x01"))

    def test_parse_status_matches_user_wb4_replies(self):
        state = parse_state(
            {
                "status": [
                    bytes.fromhex("3c10024200aaaaaa0001600210003c100000"),
                    bytes.fromhex("3c1001100000100000100000100000100000"),
                    bytes.fromhex("3c1000100000100000100000100000100000"),
                ],
                "valve_status": [bytes.fromhex("1a03000000")],
                "input_alerts": [bytes.fromhex("72020000")],
            }
        )

        self.assertTrue(state.status.enabled)
        self.assertTrue(state.status.manual)
        self.assertEqual(1, state.status.active_zone)
        self.assertEqual(60, state.status.remaining_seconds)
        self.assertEqual((60, 0, 0, 0), state.status.zone_remaining_seconds)
        self.assertEqual(96, state.status.battery_raw)
        self.assertEqual((), state.valve_faults.faulty_zones)

    def test_parse_device_info_matches_mysolem_identification_v5(self):
        info = parse_device_info(
            (
                b"\x10\x00\x00Giardino\x00",
                bytes((0x10, 0, 1, 0xD7, 0x60, 0x40, 0, 1, 2, 0xB4, 4, ord("A"), 7, 0, 2, 2, 1)),
            ),
            (bytes.fromhex("e400010203"),),
        )

        self.assertEqual("Giardino", info.name)
        self.assertEqual("D76040000102", info.bluetooth_address)
        self.assertEqual("7.0.2", info.firmware)
        self.assertEqual("B4040001020102", info.serial)
        self.assertEqual("010203", info.uuid)

    def test_program_frames_match_static_config_irri_v5(self):
        program = IrrigationProgram(
            index=0,
            name="Garden",
            weekdays=frozenset({Weekday.MONDAY, Weekday.WEDNESDAY, Weekday.SUNDAY}),
            start_minutes=(480, None, None, None, None, None, None, None),
            zone_durations_seconds=(60, 120, 0, 0),
            cycle=ProgramCycle.CUSTOM,
        )

        frames = build_program_frames(program, today=date(2026, 11, 5))

        self.assertEqual(7, len(frames))
        self.assertEqual(bytes.fromhex("2f12001047617264656e") + bytes(10), frames[0])
        self.assertEqual(bytes.fromhex("370e00100000006400450200050b07ea"), frames[2])
        self.assertEqual(bytes.fromhex("3712011001e005a005a005a005a005a005a005a0"), frames[3])
        self.assertEqual(bytes.fromhex("3711021000003c000078") + bytes(9), frames[4])

    def test_program_parser_matches_static_read_config_answer_v5(self):
        replies = (
            bytes.fromhex("3a10041047617264656e") + bytes(10),
            bytes.fromhex("3a100310") + bytes(16),
            bytes.fromhex("3a10021000000064004502"),
            bytes.fromhex("3a10011001e005a005a005a005a005a005a005a0"),
            bytes.fromhex("3a10001000003c000078") + bytes(9),
        )

        (program,) = parse_program_replies(replies)

        self.assertEqual("Garden", program.name)
        self.assertEqual(frozenset({Weekday.MONDAY, Weekday.WEDNESDAY, Weekday.SUNDAY}), program.weekdays)
        self.assertEqual((480, None, None, None, None, None, None, None), program.start_minutes)
        self.assertEqual((60, 120, 0, 0), program.zone_durations_seconds)

    def test_schedule_hides_wire_indexes_and_disabled_start_slots(self):
        schedule = Schedule(
            number=1,
            name="Giardino",
            days=Days.MONDAY | Days.WEDNESDAY | Days.FRIDAY,
            starts=(TimeOfDay(7), TimeOfDay(19, 30)),
            zones=ZoneDurations.minutes(one=10, two=15),
            water_budget=75,
            zone_pause_seconds=30,
        )
        program = schedule.to_program()

        self.assertEqual(0, program.index)
        self.assertEqual((420, 1170, None, None, None, None, None, None), program.start_minutes)
        self.assertEqual((600, 900, 0, 0), program.zone_durations_seconds)
        self.assertEqual(75, program.water_budget)
        self.assertEqual(30, program.time_between_zones)
        self.assertEqual(schedule, Schedule.from_program(program))

    def test_backup_round_trip_preserves_schedule_domain_values(self):
        backup = ControllerBackup(
            (
                Schedule(
                    number=1,
                    name="Giardino",
                    days=Days.MONDAY | Days.FRIDAY,
                    starts=(TimeOfDay(7, 30),),
                    zones=ZoneDurations.minutes(one=10, two=5),
                    water_budget=80,
                    zone_pause_seconds=45,
                ),
            )
        )

        self.assertEqual(backup, ControllerBackup.from_json(backup.to_json()))

    def test_periodic_schedule_preserves_cycle_parameters(self):
        schedule = Schedule(
            number=2,
            cycle=ProgramCycle.PERIODIC,
            period_length=3,
            synchronization_day=1,
        )

        program = schedule.to_program()

        self.assertEqual(ProgramCycle.PERIODIC, program.cycle)
        self.assertEqual(3, program.period_length)
        self.assertEqual(1, program.synchronization_day)

