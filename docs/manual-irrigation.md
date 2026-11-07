# Manual irrigation (SBR-94)

## Platform and protocol boundary

Each WB-4 zone is a **water valve** with OPEN and CLOSE capabilities and reported
open/closed state. Position, opening/closing transitions and STOP-motion are not
exposed: the client reports the active zone, not position or actuator movement.
An active zone is open; the other zones are closed. A missing countdown page
does not make the activity unknown. Failed communication makes valves unavailable.
State is controller-reported, not proof of physical water flow.

`valve.open_valve` starts the zone with its saved default duration (initially
**one minute**). The custom entity action `solem_woobee.set_default_duration`
saves a default independently for each zone in HA config-entry options, without
opening a BLE connection, modifying controller programs or starting watering.
It survives reload/restart and is shown as `default_duration_minutes` on the valve.
`solem_woobee.start_irrigation` starts one run with an explicit duration and does
not change that default. Both actions target the **valve**, not the stop button.

Both duration actions require `minutes`: a strict integer in **1–279620**,
inclusive. Booleans, fractions and strings are rejected. The client multiplies
minutes by 60 and encodes seconds in 24 bits (`start_valve_frame`, 0x31/0x12).
The maximum is a wire-format limit, not a confirmed firmware/UI limit or a safe
watering recommendation. Use short supervised runs until hardware validation.
No controller program APIs are exposed.

Example: set a zone's default for subsequent standard open actions (replace the
entity ID with the actual valve selected in HA):

```yaml
action: solem_woobee.set_default_duration
target:
  entity_id: valve.garden_zone_1
data:
  minutes: 2
```

Use `valve.open_valve` / `valve.close_valve` on that entity in dashboards and
automations. To override duration for one run, use `solem_woobee.start_irrigation`
with the same target and `minutes` field. Do not open several valves together:
only one active zone is supported and starts while any zone is active are rejected.

## Conditional close and global stop

The client has **only a global stop opcode**; it does not provide an atomic
"stop zone N" operation. Under the per-controller I/O lock, HA re-reads state
immediately before `valve.close_valve`. If that zone is active it sends one global
stop and reads back state. If the controller is idle or another zone is active,
it publishes the read state and sends **no command**. Closing an inactive zone
therefore does not intentionally interrupt irrigation on another zone.

The **Stop all irrigation** controller button remains available for an explicit
global stop, including externally started runs; it requires no pre-read.

There is still a race with MySOLEM or any external client between the read and
global stop. HA's lock serializes its own commands/polling only; it cannot make
the external protocol atomic. Avoid concurrent control from other applications.
If independent atomic zone closure becomes a requirement, a new client/API
capability must be established rather than hiding this limitation.

## Consistency and errors

Each command opens a fresh authenticated BLE session. One entry-scoped lock
serializes commands and polling. Before every start, a fresh state read must
report no active zone. Any active zone, including the requested zone, rejects
the start without writing: runs are never implicitly replaced or extended.

After one command transmission, HA performs a full state read in the same
session and publishes that observation. Start is confirmed only when the target
zone is active; close/global stop only when no WB-4 zone is active. A mismatch
raises an action error and preserves the observed state. There is no documented
settling interval or decoded rejection code; rejection and delayed application
are reported as **unconfirmed**, not success. No optimistic open/closed state is
written. Timed completion or changes made outside HA are observed on the next
shared five-minute poll; countdowns are not extrapolated.

Offline, authentication, invalid-response and timeout failures raise an HA action
error and mark the coordinator unavailable. Cancellation also invalidates state
and releases the lock/session. A command may have been applied before timeout:
unknown outcome is not proof watering stopped. No command is automatically
retried. A normal poll or explicit refresh safely reads state and restores
availability. Check the device before manually retrying an ambiguous command.
HA's global stop button timestamp records an attempted press, not success.

## Entity compatibility

Four zone valves replace the start buttons in this unmerged SBR-94 PR. They use
stable controller/zone unique IDs in the valve domain and share the physical
controller device. Existing read-only sensor/binary-sensor IDs and the global
stop button ID remain stable. Automations made against the earlier PR's start
buttons must target valves and use the standard open action; custom duration
actions must likewise target valves. HA may retain old disabled/unavailable
registry entries from a previously installed PR version; remove those obsolete
start-button entries manually after updating.

## Supervised device verification (not executed by the agent)

Only perform these actuator steps with explicit authorization, physical access
and a safe water supply/drainage arrangement. Record model, firmware, HA version,
latencies, reported state and physical behavior without publishing device IDs.

1. Use the confirmed WB-4 firmware 7.0.2, close MySOLEM, establish HA Bluetooth
   reachability and confirm idle status. Check the four water valves share the
   controller device and offer open/close, without position or motion controls.
2. Open each zone in turn using its initial one-minute default. Verify the correct
   valve opens physically, HA reports it open and countdown is in seconds. Close
   it using its own valve entity; verify the controller and physical valve stop.
3. Set zone 1's default to 2 minutes, reload HA and open it. Check persistence and
   automatic timed completion; an explicit one-minute run must not change the
   saved default. Other zones retain their own defaults.
4. While zone 1 runs, close zone 2: there must be no BLE stop and zone 1 must keep
   watering. Close zone 1: it must stop. Repeat close while idle: no stop is sent.
5. Attempt opening the same or another zone during a run: HA must reject both
   without extending/replacing the run. Verify the global stop button separately.
6. Verify invalid durations (0, negatives, bools, strings, fractions and 279621)
   are rejected before I/O. Do not physically test the wire maximum as a long run.
7. Start a short run externally, release MySOLEM's BLE connection and refresh HA:
   the corresponding valve must appear open and conditional close must stop it.
   Do not race MySOLEM against HA during physical validation.
8. With no active watering, make the controller unreachable and attempt an action:
   expect an HA error and unavailable valves, then recovery after a safe read.
   Use simulated tests for post-write timeout/rejection rather than deliberately
   losing control while watering. Never blindly retry an uncertain start.
9. Record command-to-state latency; document any measured need for bounded
   read-only verification polling before changing the implementation.
10. Reload/unload HA, verify stable registry identity and polling teardown, and
    finish with all physical valves idle.

Automated evidence: `tests/integration/test_commands.py`, simulated client,
actual HA valve actions/state/metadata, duration persistence, guarded closes,
command failures/no retries, serialization, recovery and entity lifecycle.

Sources reviewed:
- https://contributors.home-assistant.io/core/entities/valve/
- https://contributors.home-assistant.io/core/integrations/actions/
- https://contributors.home-assistant.io/core/quality-scale/
- Existing client protocol and README reverse-engineering evidence (SBR-88).
