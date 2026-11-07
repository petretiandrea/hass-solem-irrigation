"""Domain validation and malformed controller data; synthetic fixtures only."""
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, patch

from woobee_api import SolemGatt, WooBeeClient, WooBeeConnection, WooBeeV2
from woobee_api.models import ControllerIdentity, ZoneIdentity
from woobee_api.programs import (
    ControllerBackup, IrrigationProgram, Schedule, TimeOfDay, ZoneDurations,
    parse_program_replies,
)
from woobee_api.protocol import ctr_crypt, ecb_encrypt
from woobee_api.responses import parse_device_info, parse_state, parse_status, parse_valve_faults
from woobee_api.errors import InvalidResponseError
from test_client import FakeClient, Characteristic
from test_session import BLE, PAGES


class ValidationTests(unittest.TestCase):
    def test_schedule_and_wire_boundaries(self):
        cases = [
            (TimeOfDay, {'hour': 24}), (TimeOfDay, {'hour': 0, 'minute': -1}),
            (ZoneDurations, {'seconds': (0,)}),
            (ZoneDurations, {'seconds': (0, 0, 0, 0x1000000)}),
            (IrrigationProgram, {'index': 12}),
            (IrrigationProgram, {'index': 0, 'name': 'é' * 16}),
            (IrrigationProgram, {'index': 0, 'start_minutes': ()}),
            (IrrigationProgram, {'index': 0, 'zone_durations_seconds': ()}),
            (IrrigationProgram, {'index': 0, 'start_minutes': (1440,) * 8}),
            (IrrigationProgram, {'index': 0, 'zone_durations_seconds': (-1,) * 4}),
            (IrrigationProgram, {'index': 0, 'water_budget': 65536}),
            (IrrigationProgram, {'index': 0, 'time_between_zones': -1}),
            (IrrigationProgram, {'index': 0, 'period_length': 256}),
            (IrrigationProgram, {'index': 0, 'synchronization_day': -1}),
            (Schedule, {'number': 0}),
            (Schedule, {'number': 1, 'starts': (TimeOfDay(0),) * 9}),
            (Schedule, {'number': 1, 'water_budget': -1}),
            (Schedule, {'number': 1, 'zone_pause_seconds': 65536}),
            (Schedule, {'number': 1, 'period_length': 0}),
            (Schedule, {'number': 1, 'synchronization_day': 2}),
        ]
        for factory, kwargs in cases:
            with self.subTest(factory=factory, kwargs=kwargs), self.assertRaises(ValueError):
                factory(**kwargs)
        for value in (-1, 1.5):
            with self.assertRaises(ValueError):
                ZoneDurations.minutes(one=value)
        program = IrrigationProgram(0, start_minutes=(0, 1439) + (None,) * 6,
                                    zone_durations_seconds=(60, 0, 120, 0))
        self.assertEqual(('00:00', '23:59'), program.starts)
        self.assertEqual({1: 1, 3: 2}, program.zone_minutes)
        self.assertEqual(1, program.number)

    def test_invalid_backups(self):
        for value in ('[]', '{}', '{"format":"solem-woobee-backup/v1"}',
                      '{"format":"solem-woobee-backup/v1","schedules":[{}]}'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ControllerBackup.from_json(value)
        with self.assertRaises(ValueError):
            ControllerBackup((Schedule(1), Schedule(1)))

    def test_identity_and_crypto_validation(self):
        identity = ControllerIdentity('108B0002-EAB5-BC09-D0EA-0B8F467CE8EE')
        self.assertEqual('108b0002-eab5-bc09-d0ea-0b8f467ce8ee', identity.unique_id)
        for number in (0, 5, True):
            with self.assertRaises(ValueError):
                ZoneIdentity(identity, number)
        with self.assertRaises(ValueError):
            SolemGatt.from_read_uuid('108b0003-eab5-bc09-d0ea-0b8f467ce8ee')
        with self.assertRaises(ValueError):
            SolemGatt('unused', '00').key
        with self.assertRaises(ValueError):
            ecb_encrypt(b'bad', bytes(16))
        with self.assertRaises(ValueError):
            ctr_crypt(b'payload', bytes(16), b'bad')
        for command in (lambda: WooBeeV2.start_valve_frame(True, 1),
                        lambda: WooBeeV2.start_all_frame(0x1000000),
                        lambda: WooBeeV2.start_program_frame(256),
                        lambda: WooBeeV2.set_clock_frame(datetime(1899, 1, 1))):
            with self.assertRaises(ValueError):
                command()

    def test_malformed_response_groups_and_identity(self):
        valid = {'status': PAGES, 'valve_status': [bytes.fromhex('1a03000000')],
                 'input_alerts': [b'\x72\x00']}
        for raw in ({}, {**valid, 'input_alerts': []}, {**valid, 'input_alerts': [b'']},
                    {**valid, 'input_alerts': [b'\xff']}, {**valid, 'valve_status': []}):
            with self.subTest(raw=raw), self.assertRaises(InvalidResponseError):
                parse_state(raw)
        for reply in (b'', b'\xff\x00\x00\x00\x00'):
            with self.assertRaises(InvalidResponseError):
                parse_valve_faults(reply)
        self.assertEqual((1, 16), parse_valve_faults(b'\x1a\x00\x00\x80\x01').faulty_zones)
        for replies in ([b'', b'\xff\x00\x00', b'\x10\x00\x01'], [b'\x10\x00\x00\xff']):
            with self.assertRaises(InvalidResponseError):
                parse_device_info(replies, [b'', b'\xff\x00'])
        info = parse_device_info([b'\x10\x00\x00Name'], [b'', b'\xff\x00'])
        self.assertIsNone(info.uuid)
        self.assertIsNone(info.hardware)

    def test_partial_zone_page_preserves_unknown_durations(self):
        status = parse_status([PAGES[0], b"\x3c\x00\x01"])
        self.assertEqual((60, 0, None, None), status.zone_remaining_seconds)

    def test_truncated_programs(self):
        for replies in ([b'', b'\xff\x00\x00\x10', b'\x3a\x00\x00\x00'],
                        [b'\x3a\x00\x04\x10'],
                        [bytes((0x3a, 0, page, 0x10)) for page in range(5)]):
            with self.subTest(replies=replies), self.assertRaises(ValueError):
                parse_program_replies(replies)


class InspectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_discovery_delegates_timeout_without_hardware(self):
        scanner = AsyncMock()
        scanner.discover.return_value = ['advertisement']
        self.assertEqual(['advertisement'], await WooBeeClient(scanner, None).discover(2))
        scanner.discover.assert_awaited_once_with(timeout=2)
        with patch('woobee_api.client.BleakScanner', scanner):
            self.assertIs(scanner, WooBeeClient.local()._scanner)

    async def test_inspection_preserves_read_errors_and_skips_write_only(self):
        client = FakeClient('address')
        client.read_gatt_char = AsyncMock(side_effect=OSError('denied'))
        write_only = type('Characteristic', (), {'uuid': 'write-only', 'properties': ['write']})()
        service = type('Service', (), {'uuid': 'service', 'characteristics': [Characteristic(), write_only]})()
        client.get_services = AsyncMock(return_value=[service])
        result = await WooBeeClient(None, lambda _: client).inspect('address')
        readable, writable = result.services[0].characteristics
        self.assertEqual('OSError: denied', readable.read_error)
        self.assertIsNone(readable.value_hex)
        self.assertIsNone(writable.read_error)
        client.read_gatt_char.assert_awaited_once()

    async def test_connection_scope_cannot_be_reused(self):
        scope = WooBeeConnection('AA:BB:CC:DD:EE:FF', lambda _: BLE())
        async with scope:
            with self.assertRaises(RuntimeError):
                await scope.__aenter__()


class CommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_commands_delegate_frames_and_parse_acknowledgements(self):
        session = AsyncMock()
        api = WooBeeV2(session)
        session.exchange_all.return_value = PAGES
        self.assertEqual(60, (await api.start_all(1)).remaining_seconds)
        session.exchange_all.assert_awaited_with(WooBeeV2.start_all_frame(1))
        await api.start_program(2)
        session.exchange_all.assert_awaited_with(WooBeeV2.start_program_frame(2))
        when = datetime(2026, 11, 7, 12)
        session.exchange_all.return_value = [b'\x04\x00']
        self.assertEqual([b'\x04\x00'], await api.sync_clock(when))
        session.exchange_all.assert_awaited_with(WooBeeV2.set_clock_frame(when))
        await api.sync_clock()
        self.assertEqual(3, session.exchange_all.call_args.args[0][0])
        session.exchange_all.return_value = [bytes.fromhex('1a03000001')]
        self.assertEqual((1,), (await api.reset_valve_faults()).faulty_zones)
        await api.authenticate()
        session.authenticate.assert_awaited_once()
        await api.aclose()
        session.aclose.assert_awaited_once()

    async def test_backup_and_restore_simulated_schedule_frames(self):
        session = AsyncMock()
        session.exchange_all.return_value = [
            bytes.fromhex('3a10041047617264656e') + bytes(10),
            bytes.fromhex('3a100310') + bytes(16),
            bytes.fromhex('3a10021000000064004502'),
            bytes.fromhex('3a10011001e005a005a005a005a005a005a005a0'),
            bytes.fromhex('3a10001000003c000078') + bytes(9),
        ]
        api = WooBeeV2(session)
        backup = await api.backup()
        session.exchange_all.assert_awaited_once_with(b'\x39\x00')
        self.assertEqual('Garden', backup.schedules[0].name)
        self.assertEqual((60, 120, 0, 0), backup.schedules[0].zones.seconds)
        session.exchange_all.reset_mock()
        session.exchange_all.return_value = [b'ack']
        result = await api.restore(backup)
        self.assertEqual([[[b'ack']] * 7], result)
        self.assertEqual(7, session.exchange_all.await_count)
        self.assertEqual(b'\x2f', session.exchange_all.call_args_list[0].args[0][:1])
