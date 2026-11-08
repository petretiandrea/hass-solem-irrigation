# Standalone client and protocol

The standalone client includes schedule and backup operations that are not exposed
by the Home Assistant integration. Use Python 3.14 or later.

Home Assistant shared polling, availability and device registry design:
[coordinator documentation](coordinator.md).

```bash
python -m pip install -e .
python scripts/inspect_woobee.py
```

```python
import asyncio
from woobee_api import WooBeeClient

async def main():
    client = WooBeeClient.local()
    devices = await client.discover()
    for device in devices:
        print(device)
    print(await client.inspect("AA:BB:CC:DD:EE:FF"))

asyncio.run(main())
```

`inspect()` connects and reads characteristics without sending commands. Its JSON
output contains device addresses, serials and authentication challenges; keep it
private. The default `woobee-gatt.json` output is ignored by Git. The redacted
[example profile](examples/woobee-gatt.json) retains service UUIDs and properties.

## Recovered MySOLEM transport

MySOLEM 6.13.3 uses request UUID `…0002`, notification UUID `…0003` and auth
UUID `…0005` in one UUID family. Authentication reads a challenge, writes its
AES-ECB encryption, then waits for exact `AUTHENTICATED\0`. Request
and response payloads use AES-CTR with that challenge as nonce.

```python
from bleak import BleakClient
from woobee_api import SolemSession, WOOBEE_V2_GATT

async with BleakClient("AA:BB:CC:DD:EE:FF") as client:
    async with SolemSession(client, WOOBEE_V2_GATT) as session:
        # MySOLEM command frames: use WooBeeV2(session), below.
        pass
```

Static APK reverse engineering maps WooBee V2 firmware 7.0.2 to `type 180`,
`BluetoothV6FrameManager` and these frames:

| Action | MySOLEM builder | Plaintext frame |
| --- | --- | --- |
| state | `statusV5()` | `3b 00` |
| device info | `identificationV5()` | `0f 00`, then `e3 00` UUID |
| valve faults | `readValveStatusV5()` | `19 03 00 10 ff` |
| input alerts | `readInputsAlerts()` | `71 00` |
| start zone `z`, `m` minutes | `ManualValve` → `testValvesV5(z, m * 60)` | `31 05 12 z ss ss ss` |
| stop | `ManualStop` → `manualStopV5()` | `31 05 15 00 ff 00 00` |
| start all, `m` minutes | `TestAllValves` → `manualRunValvesV5(m * 60)` | `31 05 11 00 ss ss ss` |
| start program `p` | `ManualProgram` → `manualRunProgramV5(p)` | `31 05 14 00 p 00 00` |
| sync clock | `setTimeV5()` | `03 06 00 yy mm dd hh mm ss` |
| reset valve faults | `resetValveStatusV5()` | `19 03 01 7f ff` |

`ss ss ss` is big-endian seconds. Commands are AES-CTR encrypted by
`SolemSession`; replies are parsed from MySOLEM Java into `WooBeeState`:
active zone, seconds remaining, manual/configured origin, raw battery value and
valve fault zones. `read_state_raw()` retains decrypted frames.

Set `WOOBEE_ADDRESS` locally to your BLE MAC or CoreBluetooth UUID. Examples
below read status, start zone 1 for one minute and stop all irrigation. Run actuator
commands only with supervision and a safe water supply.

Run:

```bash
.venv/bin/python scripts/woobee.py "$WOOBEE_ADDRESS" status
.venv/bin/python scripts/woobee.py "$WOOBEE_ADDRESS" start 1 1
.venv/bin/python scripts/woobee.py "$WOOBEE_ADDRESS" stop
```

Interactive menu:

```bash
.venv/bin/python scripts/woobee_menu.py "$WOOBEE_ADDRESS"
```

Menu item `11` reads device name, serial, hardware, firmware, BLE address and
controller UUID without changing persistent controller state.

## Irrigation schedules

`IrrigationProgram` implements the APK’s `configIrriV5()` frame layout.
`write_program()` changes persistent controller memory and is not exposed by the CLI.

```python
from woobee_api import Days, ProgramCycle, Schedule, TimeOfDay, ZoneDurations

schedule = Schedule(
    number=1,
    name="Garden",
    days=Days.MONDAY | Days.WEDNESDAY | Days.FRIDAY,
    starts=(TimeOfDay(7),),
    zones=ZoneDurations.minutes(one=10, two=10, three=10, four=10),
    water_budget=80,
    zone_pause_seconds=30,
)
# await woobee.write_schedule(schedule)
# schedules = await woobee.read_schedules()
```

`water_budget` is controller percentage; `zone_pause_seconds` is pause between
zones. Both are recovered from `configIrriV5()`.

## Backup, clock and faults

`ControllerBackup` stores this client's schedule model as JSON. It is not a
MySOLEM app-export format. Backup reads controller schedules; restore rewrites
every schedule present in JSON.

```python
from pathlib import Path
from woobee_api import ControllerBackup

backup = await woobee.backup()
Path("wb4-backup.json").write_text(backup.to_json())

# await woobee.restore(ControllerBackup.from_json(Path("wb4-backup.json").read_text()))
# await woobee.sync_clock()
# await woobee.reset_valve_faults()
```

Menu items `7`–`10` provide backup, restore, clock sync and fault reset.
Restore, clock sync and reset require literal confirmation.

Periodic example: every three days, phase starts today.

```python
every_three_days = Schedule(
    number=2,
    cycle=ProgramCycle.PERIODIC,
    period_length=3,
    synchronization_day=0,
)
```

Verify authentication only, without actuator commands:

```bash
python scripts/authenticate_woobee.py "$WOOBEE_ADDRESS"
```

## Connection ownership and errors

The client lives in `custom_components/solem_woobee/woobee_api` and has no Home
Assistant imports. An editable install exposes it as `woobee_api`; the integration
uses relative imports. It ships with the integration and has no separate PyPI release.

```python
from bleak import BleakClient
from woobee_api import WooBeeConnection

async with WooBeeConnection("AA:BB:CC:DD:EE:FF", BleakClient) as api:
    state = await api.read_state()
    info = await api.read_device_info()
```

The factory returns a fresh disconnected transport implementing `BLETransport`.
HA may supply its own address-bound adapter to choose a Bluetooth proxy; the
client knows nothing about HA. `WooBeeConnection` owns connection, authentication,
subscriptions and disconnect. Alternatively `SolemSession(connected_client,
gatt)` borrows an existing connection: use it as an async context manager, or
call `aclose()` in `finally`. Borrowing removes notifications but never disconnects
the caller's connection. A connection must have only one session owner; do not
write to it through another client. Scopes cannot be reused.

Authentication uses a fresh 16-byte challenge for every connection, the recovered
protocol's standard product key and the exact success acknowledgement. This
product key is a protocol constant, not a user credential. There is no observed
token expiry or token refresh API. Unknown auth notifications are not treated as
credential rejection. `AuthenticationError` means authentication is required;
`SessionTimeoutError` (a `ConnectivityError` and `TimeoutError`) means no completed
exchange within the deadline. Invalid challenges, response commands and malformed
state raise `InvalidResponseError`. BLE failures raise `ConnectivityError`.

Deadlines: connect/auth 10 seconds each; an entire request and all its reply
pages 20 seconds; each notification teardown/disconnect 5 seconds. Waiting for
the per-session operation lock is outside these deadlines. Notification queues
and responses are capped at 128 frames. All requests in an API operation share
the same lock, including state/identity reads and program writes. Timeout,
cancellation or transport failure invalidate the session and remove callbacks;
create a new connection scope and authenticate again. V6 offers no transaction
ID, so responses from an interrupted exchange must never be reused.

There are no automatic retries, including for reads. Callers may
retry a failed read with a new connection and their own bounded backoff. A start,
stop or write may already have reached hardware when its response times out:
refresh state rather than replaying it. Manual durations use positive whole
minutes, zones 1–4 and a 24-bit seconds wire limit (279620 minutes). HA validates
that wire limit but no smaller firmware limit has been established. An
acknowledgement reports controller state, not measured water flow.

`ControllerIdentity` normalizes BLE MACs and CoreBluetooth UUIDs. Its ID is the
address; four `ZoneIdentity` objects have IDs `<address>_zone_<n>`. Names, serials
and UUID metadata never change registry identity. Missing zone durations remain
`None`, while a reported zero remains zero. Battery and input flags remain raw.
Programs and backups are available through the standalone tools only.

Tests use synthetic BLE transports and anonymous response fixtures. No credentials
or controller-specific secrets are required. Hardware behavior, battery scale,
polling cadence and Bluetooth proxy behavior still need device validation; tests
never connect to hardware or actuate valves.
