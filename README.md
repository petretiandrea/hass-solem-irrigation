# SOLEM WooBee BLE

BLE client for WooBee V2 / WB-4 firmware 7.0.2.

Home Assistant shared polling, availability and device registry design:
[coordinator documentation](docs/coordinator.md).

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

`inspect()` only connects and reads characteristics. It never writes, starts a valve, changes schedules or triggers DFU.

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

Run:

```bash
.venv/bin/python scripts/woobee.py 00000000-0000-0000-0000-000000000001 status
.venv/bin/python scripts/woobee.py 00000000-0000-0000-0000-000000000001 start 1 1
.venv/bin/python scripts/woobee.py 00000000-0000-0000-0000-000000000001 stop
```

Menu interattivo:

```bash
.venv/bin/python scripts/woobee_menu.py 00000000-0000-0000-0000-000000000001
```

Menu item `11` reads device name, serial, hardware, firmware, BLE address and
controller UUID. No persistent controller state changes.

## Programmi irrigazione

`IrrigationProgram` ricostruisce `configIrriV5()` dall'APK. `write_program()`
modifica memoria persistente controller; non viene esposto da CLI.

```python
from woobee_api import Days, ProgramCycle, Schedule, TimeOfDay, ZoneDurations

schedule = Schedule(
    number=1,
    name="Giardino",
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
python scripts/authenticate_woobee.py 00000000-0000-0000-0000-000000000001
```

## Embedded asynchronous client (SBR-90)

The client now lives in `custom_components/solem_woobee/woobee_api`, following
hass-sorgenia's embedded API layout. Update imports from the former root
`solem_woobee` package. It has no Home Assistant imports, including type-only
imports, and is shipped with the integration; no PyPI release is planned.
Both the standalone client and the integration require Python 3.14+. The
integration targets HA 2026.8.0+. CI uses Python 3.14 from `.python-version`
for all jobs and tests the client without HA installed.

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

There are **zero automatic retries**, including read operations. Callers may
retry a failed read with a new connection and their own bounded backoff. A start,
stop or write may already have reached hardware when its response times out:
refresh state rather than replaying it. Manual durations use positive whole
minutes, zones 1–4 and a 24-bit seconds wire limit (279620 minutes). HA's smaller
operational duration limit belongs to SBR-94. An acknowledgement reports controller
state, not measured water flow.

`ControllerIdentity` normalizes BLE MACs and CoreBluetooth UUIDs. Its ID is the
address; four `ZoneIdentity` objects have IDs `<address>_zone_<n>`. Names, serials
and UUID metadata never change registry identity. Missing zone durations remain
`None`, while a reported zero remains zero. Battery and input flags remain raw.
Programs/backup APIs are preserved for the CLI, outside the initial HA scope.

Tests use synthetic BLE transports and anonymous response fixtures. No credentials
or controller-specific secrets are required. Hardware behavior, battery scale,
polling cadence and Bluetooth proxy behavior still need device validation; tests
never connect to hardware or actuate valves.

## Home Assistant configuration

The integration domain is `solem_woobee` (Home Assistant 2026.8.0+, Python
3.14). Copy `custom_components/solem_woobee` to the HA configuration directory,
restart, and add **SOLEM WooBee** from Devices & services. Select the WooBee V2 /
WB-4 visible to Home Assistant Bluetooth. Automatic discovery is deferred until
an advertisement matcher is verified; unrelated Bluetooth devices can appear
in the selector and will fail protocol validation.

Setup authenticates and reads identity and state, without changing irrigation.
The BLE challenge uses the protocol's built-in key: no account, password or
credential reauthentication is available. Timeouts indicate connectivity
failure, not confirmed credential rejection. Each normalized BLE address can
be configured once. Connections and notifications are released after each
validation; unavailable controllers retry setup through Home Assistant.

The coordinator performs an initial read during setup. Periodic polling runs
every five minutes only while entities subscribe; with no active entities it
stops automatically. Read-only sensor and binary_sensor platforms share this snapshot. Commands are
reserved for SBR-94. The client is embedded, not fetched
from PyPI, and shares the integration version in `manifest.json`.

Integration tests: install `requirements_test.txt` and run
`python -m pytest tests/integration -q`. The existing client tests continue to
run with `python -m unittest discover -s tests -v`, without Home Assistant.

The local client wheel exposes `woobee_api` directly, so CLI tools and client
tests do not load the Home Assistant integration package. HACS still installs
the client at `custom_components/solem_woobee/woobee_api`; integration modules
use relative imports. All Python imports stay at module top level.


### Read-only entities

All four zones belong to the physical controller device. Names are translated
in English and Italian. Entity unique IDs use the normalized configured address plus
zone number and measurement key; renaming or receiving serial/UUID metadata
does not replace registry entries.

| Entity | Source / interpretation | Metadata |
| --- | --- | --- |
| Zone 1–4 remaining time | Reported seconds; missing page is unknown, zero stays zero | Duration, seconds; no state class (countdown, no long-term statistics) |
| Zone 1–4 irrigating | Reported active zone equals this zone | Running; controller status, not measured water flow |
| Zone 1–4 valve fault | Zone in the client's decoded fault bitmap | Problem, diagnostic |
| Irrigation enabled / manual irrigation | Reported status flags | Read-only binary sensors |
| Sensor input open | Raw open flag; does not infer rain or soil moisture | Diagnostic |
| Clock alarm | Reported clock alarm flag | Problem, diagnostic |
| Last read successful | Success of the shared snapshot read | Connectivity, diagnostic |
| Battery raw value | Unscaled battery byte | Diagnostic, disabled by default, no unit/device/state class |

Connectivity describes the **last read**, not an always-connected BLE link; the
client disconnects after every read. On a failed update it turns off, while all
other enabled entities become unavailable until recovery. Missing optional
zone durations remain available with an unknown value. Values update at the
five-minute polling interval; countdowns are not extrapolated between reads.

Enable the raw battery entity from the device's entity settings only if useful
for investigation. Its scale is unverified: it must not be interpreted as a
percentage or voltage. RSSI, rain-delay units, active-program labels and input
alert meanings are not exposed because the shared client provides no verified
measurement/interpretation for them. No configuration entities or additional
platforms are justified by these read-only fields.

### Examples and troubleshooting

To monitor irrigation, add the four **Zone N irrigating** binary sensors and
**Zone N remaining time** sensors to a dashboard. Use the entity picker to select
them: entity IDs depend on the controller name and server language. A remaining
time of zero is reported idle time; unknown means its duration page was absent.

To receive valve-fault notifications, create an automation in **Settings →
Automations & scenes**. Choose an **Entity → State** trigger, select the zone's
**valve fault** entity and set **To** to **On**. Add your preferred notification
action. Repeat for the other zones. This reports controller faults and does not
prove whether water is flowing.

If all state entities become unavailable, check **Last read successful**, the
integration logs and the controller's Bluetooth reachability. Keep it within
range of a connectable HA Bluetooth adapter/proxy and disconnect other apps
that may occupy its BLE connection slot. Wait for the next five-minute poll or
reload the integration after restoring connectivity. Repeated failure logs are
suppressed; recovery is logged once. There is no password to reset.

If only a duration is unknown, the shared read succeeded but the controller
omitted that optional page. Do not replace it with zero. If a diagnostic entity
is missing from the dashboard, check whether it is disabled in the device's
entity settings. Raw battery values cannot establish battery charge; there is
no supported percentage threshold for low-battery automations.

### Remove the integration

In **Settings → Devices & services → SOLEM WooBee**, delete the controller entry.
Repeat for each configured controller. To uninstall the custom integration,
remove `custom_components/solem_woobee` (or uninstall through HACS if installed
there), then restart Home Assistant. Removing the integration does not modify
the controller's locally stored irrigation programs.

### Quality policy

[Quality Scale tracking](custom_components/solem_woobee/quality_scale.yaml)
records implemented rules, pending work and justified exemptions. It is a
project checklist, not an awarded Home Assistant tier. New platforms must
complete their entity-specific rules and lifecycle tests before being marked
done. See [audit and validation](docs/quality-scale.md).
