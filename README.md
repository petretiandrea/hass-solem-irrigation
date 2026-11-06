# SOLEM WooBee BLE

BLE client for WooBee V2 / WB-4 firmware 7.0.2.

```bash
python -m pip install -e .
python scripts/inspect_woobee.py
```

```python
import asyncio
from solem_woobee import WooBeeClient

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
from solem_woobee import SolemSession, WOOBEE_V2_GATT

async with BleakClient("AA:BB:CC:DD:EE:FF") as client:
    session = SolemSession(client, WOOBEE_V2_GATT)
    await session.authenticate()
    # MySOLEM command frames: use WooBeeV2(session), below.
```

Static APK reverse engineering maps WooBee V2 firmware 7.0.2 to `type 180`,
`BluetoothV6FrameManager` and these frames:

| Action | MySOLEM builder | Plaintext frame |
| --- | --- | --- |
| state | `statusV5()` | `3b 00` |
| valve faults | `readValveStatusV5()` | `19 03 00 10 ff` |
| input alerts | `readInputsAlerts()` | `71 00` |
| start zone `z`, `m` minutes | `ManualValve` → `testValvesV5(z, m * 60)` | `31 05 12 z ss ss ss` |
| stop | `ManualStop` → `manualStopV5()` | `31 05 15 00 ff 00 00` |
| start all, `m` minutes | `TestAllValves` → `manualRunValvesV5(m * 60)` | `31 05 11 00 ss ss ss` |
| start program `p` | `ManualProgram` → `manualRunProgramV5(p)` | `31 05 14 00 p 00 00` |

`ss ss ss` is big-endian seconds. Commands are AES-CTR encrypted by
`SolemSession`; replies are parsed from MySOLEM Java into `WooBeeState`:
active zone, seconds remaining, manual/configured origin, raw battery value and
valve fault zones. `read_state_raw()` retains decrypted frames.

Run:

```bash
.venv/bin/python scripts/woobee.py EF892F67-45E5-D6DB-633D-6DF1C5AFA7B5 status
.venv/bin/python scripts/woobee.py EF892F67-45E5-D6DB-633D-6DF1C5AFA7B5 start 1 1
.venv/bin/python scripts/woobee.py EF892F67-45E5-D6DB-633D-6DF1C5AFA7B5 stop
```

Menu interattivo:

```bash
.venv/bin/python scripts/woobee_menu.py EF892F67-45E5-D6DB-633D-6DF1C5AFA7B5
```

## Programmi irrigazione

`IrrigationProgram` ricostruisce `configIrriV5()` dall'APK. `write_program()`
modifica memoria persistente controller; non viene esposto da CLI.

```python
from solem_woobee import Days, ProgramCycle, Schedule, TimeOfDay, ZoneDurations

schedule = Schedule(
    number=1,
    name="Giardino",
    days=Days.MONDAY | Days.WEDNESDAY | Days.FRIDAY,
    starts=(TimeOfDay(7),),
    zones=ZoneDurations.minutes(one=10, two=10, three=10, four=10),
)
# await woobee.write_schedule(schedule)
# schedules = await woobee.read_schedules()
```

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
python scripts/authenticate_woobee.py EF892F67-45E5-D6DB-633D-6DF1C5AFA7B5
```
