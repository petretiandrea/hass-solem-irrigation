"""Synthetic, anonymous WB-4 protocol fixtures; no hardware connection."""
import asyncio
import ast
from pathlib import Path
import unittest

from woobee_api import (
    AuthenticationError, ConnectivityError, InvalidResponseError,
    SessionTimeoutError, SolemSession, WOOBEE_V2_GATT, WooBeeV2,
    WooBeeConnection, ControllerIdentity,
)
from woobee_api.protocol import ctr_crypt, ecb_encrypt
from woobee_api.responses import parse_status

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

    async def test_receive_requires_authentication(self):
        session = SolemSession(BLE(), WOOBEE_V2_GATT)
        session._on_response(None, bytearray(b"response"))
        with self.assertRaises(AuthenticationError):
            await session._receive()
        await session.aclose()

    async def test_exit_requires_an_entered_connection(self):
        connection = WooBeeConnection('AA:BB:CC:DD:EE:FF', BLE)
        with self.assertRaises(RuntimeError):
            await connection.__aexit__(None, None, None)

class AdditionalFailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_auth_idempotence_and_unknown_ack(self):
        ble = BLE()
        session = SolemSession(ble, WOOBEE_V2_GATT)
        session._on_auth(None, bytearray(b'AUTHENTICATED\x00'))
        await session.authenticate()
        session._on_auth(None, bytearray(b'unknown'))
        session._on_auth(None, bytearray(b'AUTHENTICATED\x00'))
        subscriptions = dict(ble.callbacks)
        await session.authenticate()
        self.assertEqual(subscriptions, ble.callbacks)
        await session.aclose()

    async def test_cancel_auth_cleans_pending_future_and_owned_connection(self):
        ble = BLE()
        ble.ack = False
        session = SolemSession(ble, WOOBEE_V2_GATT, owns_connection=True)
        task = asyncio.create_task(session.__aenter__())
        while not ble.callbacks:
            await asyncio.sleep(0)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(session._authenticated.cancelled())
        self.assertIsNone(session._nonce)
        self.assertFalse(ble.callbacks)
        self.assertEqual(1, ble.disconnections)

    async def test_transport_failures_do_not_retry_and_preserve_cause(self):
        for phase in ('read', 'write'):
            ble = BLE()
            session = SolemSession(ble, WOOBEE_V2_GATT)
            async def fail(*args, **kwargs):
                raise OSError('transport failure')
            if phase == 'read':
                ble.read_gatt_char = fail
                operation = session.authenticate()
            else:
                await session.authenticate()
                ble.write_gatt_char = fail
                operation = session.exchange(b'\x3b\x00')
            with self.assertRaises(ConnectivityError) as caught:
                await operation
            self.assertIsInstance(caught.exception.__cause__, OSError)
            self.assertFalse(ble.callbacks)
            self.assertIsNone(session._nonce)

    async def test_empty_overflow_wrong_later_page_and_page_limit(self):
        for mode in ('empty', 'overflow', 'wrong_page', 'limit'):
            with self.subTest(mode=mode):
                ble = BLE()
                session = SolemSession(ble, WOOBEE_V2_GATT)
                await session.authenticate()
                callback = ble.callbacks[WOOBEE_V2_GATT.response_uuid]
                async def respond(*args, **kwargs):
                    if mode == 'empty':
                        callback(None, bytearray())
                        return
                    count = 129 if mode == 'overflow' else 128 if mode == 'limit' else 2
                    for index in range(count):
                        frame = b'\xff\x00' if mode == 'wrong_page' and index else b'\x3c\x00\x01'
                        callback(None, bytearray(ctr_crypt(frame, WOOBEE_V2_GATT.key, NONCE)))
                ble.write_gatt_char = respond
                with self.assertRaises(InvalidResponseError):
                    await session.exchange_all(b'\x3b\x00')
                self.assertFalse(ble.callbacks)
                self.assertTrue(session._notifications.empty())

    async def test_cleanup_failure_preserves_primary_error(self):
        for primary in (None, ValueError('primary')):
            ble = BLE()
            session = SolemSession(ble, WOOBEE_V2_GATT, owns_connection=True)
            await session.__aenter__()
            async def fail():
                raise OSError('disconnect failure')
            ble.disconnect = fail
            if primary is None:
                with self.assertRaises(ConnectivityError):
                    await session.__aexit__(None, None, None)
            else:
                await session.__aexit__(ValueError, primary, None)
            self.assertFalse(ble.callbacks)
            self.assertIsNone(session._nonce)

    def test_reply_completion_sentinels(self):
        for frame, last in ((b'\x3c\x00\xf0\x00', True),
                            (b'\x3c\xfe', True), (b'\x3c', True),
                            (b'\x3c\x00\x01\xf0', True),
                            (b'\x3c\x00\x01\xf0\xf0', True),
                            (b'\x3c\x00\x01\xf0\x00', False)):
            self.assertEqual(last, SolemSession._is_last_new_generation_reply(frame))

    async def test_connect_timeout_is_typed_even_when_disconnect_fails(self):
        ble = BLE()
        async def timeout():
            raise TimeoutError('connect timed out')
        async def fail():
            raise OSError('disconnect failed')
        ble.connect = timeout
        ble.disconnect = fail
        session = SolemSession(ble, WOOBEE_V2_GATT, owns_connection=True)
        with self.assertRaises(SessionTimeoutError) as caught:
            await session.__aenter__()
        self.assertIsInstance(caught.exception.__cause__, TimeoutError)
        self.assertIsNone(session._nonce)

    async def test_cleanup_failure_does_not_mask_auth_or_exchange_failure(self):
        for authenticate in (True, False):
            ble = BLE()
            session = SolemSession(ble, WOOBEE_V2_GATT)
            async def fail(*args, **kwargs):
                raise OSError('unsubscribe failed')
            if authenticate:
                ble.challenge = b'bad'
                ble.stop_notify = fail
                operation = session.authenticate()
            else:
                await session.authenticate()
                ble.stop_notify = fail
                async def wrong(*args, **kwargs):
                    session._on_response(None, bytearray())
                ble.write_gatt_char = wrong
                operation = session.exchange(b'\x3b\x00')
            with self.assertRaises(InvalidResponseError):
                await operation
            self.assertTrue(session._closed)
            self.assertFalse(session._subscriptions)
            self.assertIsNone(session._nonce)
