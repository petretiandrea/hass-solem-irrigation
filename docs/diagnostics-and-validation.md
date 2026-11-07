# Diagnostics and cross-cutting validation (SBR-95)

## Anonymous diagnostics

In Home Assistant, open Settings → Devices & services → SOLEM WooBee → entry
menu → Download diagnostics. The integration section contains only cached
operational values: last-read success, polling interval, controller flags, raw
battery value (not a percentage), active program/zone, remaining seconds and
faulty zone numbers. It performs no Bluetooth I/O or commands. A failed read
retains the last snapshot with `last_update_success: false`; missing durations
remain JSON null, distinct from zero. Before the first snapshot it returns null.

The export deliberately excludes all config entry data/options/title/IDs, BLE
MAC/CoreBluetooth address, device name, serial, UUID, raw identity/state/alert
frames, credentials, tokens, fixed protocol keys, challenges and session objects.
An explicit field allowlist also excludes future unknown configuration fields.
No pseudonym or hash permits linking controllers across exports. HA may add its
own system metadata around the integration payload; inspect the complete download
before publishing it. The unscaled battery field is retained for troubleshooting.

Poll errors distinguish authentication rejection from transport/invalid-response
failure; check Bluetooth reachability, connection slots and response completeness.
The coordinator logs one outage and one recovery, without repeating each failed
poll. Each new poll authenticates a new session. The fixed-key local BLE protocol
has no cloud account, expiring token or user credential reauth flow. A session
expiry is represented by failed authentication or transport timeout and tested
with a new connection on the next poll. Command errors are surfaced to the caller;
unknown outcomes must be checked on the device before another command is sent.
Outward exceptions explicitly chain an anonymized copy of the client failure.
Known client exception types, traceback locations and cause/context links are
retained, including at DEBUG level. Arbitrary messages, notes and custom
attributes are excluded; unknown transport exception types are represented by a
RuntimeError containing their original class name and traceback. The original
client exception is not modified. This applies to integration-owned messages,
not logs emitted independently by HA, Bleak or the host Bluetooth stack.

## Automated evidence (all simulated)

All addresses, names, nonces and frames in tests are synthetic. No live account,
captured private payload or real controller identifier is required. Tests use
real HA setup/services/states/registries with mocked BLE/client boundaries:

| Scope | Evidence |
| --- | --- |
| Configuration, duplicate entries, auth/transport/response failures | `test_config_flow.py` |
| Setup retry, unload/reload, BLE resource closure | `test_init.py` |
| Shared polling, unknown/zero data, offline/recovery, listener teardown | `test_coordinator.py`, `test_entities.py` |
| Entity states, metadata, translations, identity stability | `test_entities.py`, `test_commands.py` |
| Commands, timeouts, rejected auth, serialization, no replay, recovery | `test_commands.py` |
| Secret-bearing failures at DEBUG and anonymized command exception chains; fresh scope after session rejection | `test_privacy.py` |
| Anonymous cached diagnostics, stale/empty/partial snapshots, no I/O | `test_diagnostics.py` |
| Real protocol parsing, fresh handshake and cleanup over fake BLE | `tests/test_session.py`, `tests/test_client.py` |

Run the validation commands in `quality-scale.md`; its per-module adapter gate
includes diagnostics. This does not establish whole embedded-client coverage.

## Manual WB-4 validation (pending; no hardware run for SBR-95)

Use WB-4 firmware 7.0.2; do not infer other product support. Record date, tester,
HA/Python/integration version, adapter/proxy type, firmware, expected/observed
result and pass/fail for every step. Use anonymous controller/zone labels; keep
hardware identifiers outside the published report.

1. Close MySOLEM, confirm HA BLE reachability and configure the controller. Check
   one controller device and four zone valves with expected read entities.
2. Download diagnostics while idle and compare numeric/boolean values with HA.
   Search the whole downloaded JSON for the actual name, MAC (all forms), serial,
   UUID and known personal labels. Confirm none occurs in the integration payload;
   record any HA envelope disclosure separately. Check logs at INFO and DEBUG.
3. Perform the explicitly authorized, supervised zone procedure in
   [manual-irrigation.md](manual-irrigation.md#supervised-device-verification-not-executed-by-the-agent).
   Check every real zone, default/override duration, conditional close, global stop
   and physical timed completion. Report controller state versus physical water
   behavior separately; HA does not measure flow.
4. With all watering stopped, make BLE unreachable. Wait for a poll: entities
   become unavailable and one failure appears. Download diagnostics: cached
   values remain, success is false, and identifiers are absent. Keep unreachable
   for another poll and check no duplicate outage log.
5. Restore reachability; next poll must reconnect/authenticate, restore entity
   availability and log recovery once. Download diagnostics again. Do not induce
   loss of control during irrigation. Session rejection, malformed/partial frames
   and post-write timeout are deliberately simulated, not forced on hardware.
6. Reload, confirm stable registry associations, unload and verify no further
   polling. End with all physical valves idle. Do not publish raw BLE backups.

SBR-88 documents earlier WB-4 protocol evidence; it is not evidence that this HA
adapter or SBR-95 procedure was tested on hardware. No SBR-95 hardware results
are claimed. BLE range, battery impact, actual latency and physical zone behavior
remain pending. Fill a separate report table after supervised execution:

| Step | Expected | Observed | Simulated or hardware | Result/date |
| --- | --- | --- | --- | --- |
| 1–6 | As above | Not executed | Hardware pending | Pending |
