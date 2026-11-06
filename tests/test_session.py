"""Synthetic, anonymous WB-4 protocol fixtures; no hardware connection."""
import asyncio
import ast
from pathlib import Path
import unittest

from custom_components.solem_woobee.woobee_api import (
    AuthenticationError, ConnectivityError, InvalidResponseError,
    SessionTimeoutError, SolemSession, WOOBEE_V2_GATT, WooBeeV2,
    WooBeeConnection, ControllerIdentity,
)
from custom_components.solem_woobee.woobee_api.protocol import ctr_crypt, ecb_encrypt
from custom_components.solem_woobee.woobee_api.responses import parse_status

API = Path(__file__).parents[1] / 'custom_components/solem_woobee/woobee_api'
NONCE = bytes(range(16))
PAGES = [bytes.fromhex(s) for s in (
    '3c10024200aaaaaa0001600210003c100000',
    '3c1001100000100000100000100000100000',
    '3c1000100000100000100000100000100000',
)]


class BLE:
    def __init__(self, address=None):
        self.callbacks = {}
        self.connected = False
        self.disconnections = 0
        self.requests = []
        self.ack = True
        self.reply = True
        self.challenge = NONCE
        self.fail_subscription = False

    async def connect(self):
        self.connected = True

    async def disconnect(self):
        self.connected = False
        self.disconnections += 1

    async def start_notify(self, uuid, callback):
        if self.fail_subscription and self.callbacks:
            raise OSError('synthetic subscription failure')
        self.callbacks[uuid] = callback

    async def stop_notify(self, uuid):
        self.callbacks.pop(uuid, None)

    async def read_gatt_char(self, uuid):
        return self.challenge

    async def write_gatt_char(self, uuid, value, response):
        if uuid == WOOBEE_V2_GATT.auth_uuid:
            assert bytes(value) == ecb_encrypt(NONCE, WOOBEE_V2_GATT.key)
            if self.ack:
                self.callbacks[uuid](None, bytearray(b'AUTHENTICATED\x00'))
        else:
            frame = ctr_crypt(value, WOOBEE_V2_GATT.key, NONCE)
            self.requests.append(frame)
            await asyncio.sleep(0)
            if self.reply:
                replies = {b'\x0f\x00': [bytes.fromhex('100001aabbccddeeffb404410700020201'),
                                            b'\x10\x00\x00Controller\x00'],
                           b'\xe3\x00': [bytes.fromhex('e400010203')],
                           b'\x3b\x00': PAGES,
                           b'\x19\x03\x00\x10\xff': [bytes.fromhex('1a03000000')],
                           b'\x71\x00': [bytes.fromhex('72020000')]}.get(frame, PAGES)
                for reply in replies:
                    self.callbacks[WOOBEE_V2_GATT.response_uuid](None, bytearray(
                        ctr_crypt(reply, WOOBEE_V2_GATT.key, NONCE)))


class SessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_owned_scope_auth_state_manual_and_cleanup(self):
        ble = BLE()
        async with WooBeeConnection('AA:BB:CC:DD:EE:FF', lambda _: ble) as api:
            info = await api.read_device_info()
            self.assertEqual("Controller", info.name)
            self.assertEqual("010203", info.uuid)
            state = await api.read_state()
            self.assertEqual((60, 0, 0, 0), state.status.zone_remaining_seconds)
            self.assertEqual(60, (await api.start_valve(1, 1)).remaining_seconds)
            await api.stop()
        self.assertFalse(ble.callbacks)
        self.assertEqual(1, ble.disconnections)

    async def test_borrowed_session_and_concurrent_operations(self):
        ble = BLE()
        session = SolemSession(ble, WOOBEE_V2_GATT)
        async with session:
            api = WooBeeV2(session)
            await asyncio.gather(api.read_state(), api.read_state())
        self.assertEqual([b'\x3b\x00', b'\x19\x03\x00\x10\xff', b'\x71\x00'] * 2,
                         ble.requests)
        self.assertEqual(0, ble.disconnections)
        self.assertFalse(ble.callbacks)

    async def test_auth_timeout_is_connectivity_not_rejection(self):
        ble = BLE()
        ble.ack = False
        session = SolemSession(ble, WOOBEE_V2_GATT)
        with self.assertRaises(SessionTimeoutError):
            await session.authenticate(.01)
        self.assertFalse(ble.callbacks)
        with self.assertRaises(ConnectivityError):
            await session.authenticate()

    async def test_bad_challenge_and_partial_subscription_cleanup(self):
        for malformed in (True, False):
            ble = BLE()
            if malformed:
                ble.challenge = b'bad'
            else:
                ble.fail_subscription = True
            session = SolemSession(ble, WOOBEE_V2_GATT)
            with self.assertRaises(InvalidResponseError if malformed else ConnectivityError):
                await session.authenticate()
            self.assertFalse(ble.callbacks)

    async def test_timeout_cancellation_no_retry_and_late_callback(self):
        for cancel in (False, True):
            ble = BLE()
            session = SolemSession(ble, WOOBEE_V2_GATT)
            await session.authenticate()
            callback = ble.callbacks[WOOBEE_V2_GATT.response_uuid]
            ble.reply = False
            task = asyncio.create_task(session.exchange_all(b'\x3b\x00', .01))
            if cancel:
                await asyncio.sleep(0)
                task.cancel()
            with self.assertRaises(asyncio.CancelledError if cancel else SessionTimeoutError):
                await task
            callback(None, bytearray(b'late reply'))
            with self.assertRaises(ConnectivityError):
                await session.exchange_all(b'\x3b\x00')
            self.assertEqual(1, len(ble.requests))
            self.assertIsNone(session._nonce)
            self.assertFalse(ble.callbacks)

    async def test_requires_authentication(self):
        with self.assertRaises(AuthenticationError):
            await SolemSession(BLE(), WOOBEE_V2_GATT).exchange(b'\x3b\x00')

    async def test_reconnect_gets_fresh_handshake(self):
        clients = []
        def factory(_):
            ble = BLE()
            clients.append(ble)
            return ble
        for _ in range(2):
            async with WooBeeConnection('AA:BB:CC:DD:EE:FF', factory) as api:
                await api.read_state()
        self.assertEqual(2, len(clients))
        self.assertTrue(all(c.disconnections == 1 for c in clients))


class ModelTests(unittest.TestCase):
    def test_unknown_zone_duration_is_not_zero(self):
        state = parse_status(PAGES[:1])
        self.assertEqual((60, 0, None, None), state.zone_remaining_seconds)
        with self.assertRaises(InvalidResponseError):
            parse_status([b'\x3c\x00\x02'])

    def test_stable_ids(self):
        a = ControllerIdentity('AA-BB-CC-DD-EE-FF')
        self.assertEqual(a, ControllerIdentity('aabbccddeeff'))
        self.assertEqual('aa:bb:cc:dd:ee:ff_zone_4', a.zones[3].unique_id)
        with self.assertRaises(ValueError):
            ControllerIdentity('name')

    def test_client_imports_no_home_assistant_or_parent_integration(self):
        for path in API.glob('*.py'):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertFalse(any(n.name.startswith(('homeassistant', 'custom_components')) for n in node.names))
                if isinstance(node, ast.ImportFrom):
                    self.assertLessEqual(node.level, 1)
                    self.assertFalse((node.module or '').startswith(('homeassistant', 'custom_components')))

class FailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_owned_auth_failure_disconnects_once(self):
        ble = BLE()
        ble.challenge = b'bad'
        with self.assertRaises(InvalidResponseError):
            async with WooBeeConnection('AA:BB:CC:DD:EE:FF', lambda _: ble):
                self.fail('must not enter')
        self.assertEqual(1, ble.disconnections)
        self.assertFalse(ble.callbacks)

    async def test_connect_failure_is_typed_and_cleans_up(self):
        ble = BLE()
        async def fail():
            raise OSError('synthetic connect failure')
        ble.connect = fail
        with self.assertRaises(ConnectivityError):
            async with WooBeeConnection('AA:BB:CC:DD:EE:FF', lambda _: ble):
                self.fail('must not enter')
        self.assertEqual(1, ble.disconnections)

    async def test_wrong_response_and_unsolicited_response_invalidate(self):
        for unsolicited in (False, True):
            ble = BLE()
            session = SolemSession(ble, WOOBEE_V2_GATT)
            await session.authenticate()
            ble.reply = False
            callback = ble.callbacks[WOOBEE_V2_GATT.response_uuid]
            if unsolicited:
                callback(None, bytearray(b'unsolicited'))
            else:
                original = ble.write_gatt_char
                async def wrong(*args, **kwargs):
                    await original(*args, **kwargs)
                    callback(None, bytearray(ctr_crypt(b'\xff\x00', WOOBEE_V2_GATT.key, NONCE)))
                ble.write_gatt_char = wrong
            with self.assertRaises(InvalidResponseError):
                await session.exchange_all(b'\x3b\x00')
            self.assertFalse(ble.callbacks)

    async def test_deadline_covers_write_and_all_pages(self):
        ble = BLE()
        session = SolemSession(ble, WOOBEE_V2_GATT)
        await session.authenticate()
        async def hang(*args, **kwargs):
            await asyncio.Event().wait()
        ble.write_gatt_char = hang
        with self.assertRaises(SessionTimeoutError):
            await session.exchange_all(b'\x3b\x00', .01)
        self.assertFalse(ble.callbacks)

    async def test_cleanup_continues_after_unsubscribe_error(self):
        ble = BLE()
        session = SolemSession(ble, WOOBEE_V2_GATT, owns_connection=True)
        await session.__aenter__()
        attempts = []
        async def fail(uuid):
            attempts.append(uuid)
            raise OSError('synthetic cleanup error')
        ble.stop_notify = fail
        with self.assertRaises(ConnectivityError):
            await session.aclose()
        self.assertEqual(2, len(attempts))
        self.assertEqual(1, ble.disconnections)
        await session.aclose()
        self.assertEqual(1, ble.disconnections)
