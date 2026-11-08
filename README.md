# SOLEM WooBee for Home Assistant

Local Bluetooth integration for the SOLEM WooBee V2 / WB-4 irrigation controller.
It provides four timed zone valves, a global stop button and status sensors.
The protocol reference is WB-4, type 180, firmware 7.0.2, recovered from MySOLEM
6.13.3. Other models and firmware have not been verified.

## Requirements

- Home Assistant 2026.8.0 or later (Python 3.14+).
- A connectable Bluetooth adapter or active Bluetooth proxy within range.
- HACS 2.0.5 or later if installing through HACS.

Controller operations use local BLE and require no account or Internet access.
Downloads and updates require Internet access. Bluetooth proxy compatibility,
battery impact and the full HA hardware procedure still need validation.

## Install and configure

In HACS, add `https://github.com/petretiandrea/hass-solem-irrigation` under
**Custom repositories**, category **Integration**. Download **SOLEM WooBee** and
restart Home Assistant. This repository is not in the default HACS catalog.

For a manual install, copy the complete `custom_components/solem_woobee/`
directory, including `woobee_api/`, into `<config>/custom_components/` and restart.
Use a reviewed checkout when testing an unreleased change.

Open **Settings → Devices & services → Add integration → SOLEM WooBee** and
select the controller. Setup authenticates and reads identity and state. There
is no YAML configuration or password. Automatic discovery is not implemented;
unrelated Bluetooth devices may appear in the selector and fail validation.

## Entities and updates

All zones belong to one controller device. Entity names are available in English
and Italian. Select entities through HA’s entity picker; IDs depend on your
controller name and language.

| Entity | Meaning |
| --- | --- |
| Zone 1–4 valves | Open with a timed duration; close the active zone |
| Stop all irrigation | Stop the controller, including externally started runs |
| Zone 1–4 remaining time | Reported seconds; a missing page is unknown, zero is zero |
| Zone 1–4 irrigating | Controller reports this zone active |
| Zone 1–4 valve fault | Reported fault bitmap; diagnostic problem sensor |
| Irrigation enabled / manual irrigation | Reported controller flags |
| Sensor input open | Raw input flag; does not identify rain or soil moisture |
| Clock alarm | Reported clock fault |
| Last read successful | Result of the latest shared read |
| Signal strength | Cached Bluetooth advertisement RSSI in dBm |
| Last fetched | UTC time of the last successful full poll |
| Battery raw value | Unscaled byte; diagnostic, disabled by default |

Entities share a five-minute poll while subscribed. Countdowns do not decrease
between reads. A failed read makes state entities unavailable; **Last read
successful** stays available and turns off, and **Last fetched** keeps its prior
time. Missing optional durations remain unknown on available entities. RSSI may
predate the poll or be unknown if HA has no cached advertisement. Commands do
not advance Last fetched.

Each session uses Home Assistant's Bluetooth device selection and
`bleak-retry-connector` to retry transient connection establishment failures.
Authentication and requests follow only after connection succeeds. Irrigation
commands are sent once; a failed or interrupted command is never replayed.

## Irrigation

Opening a zone uses its saved default duration, initially one minute.
`solem_woobee.set_default_duration` saves a per-zone default in HA;
`solem_woobee.start_irrigation` supplies a duration for one run. Both target a
valve and require whole `minutes` from 1 to 279620. The maximum is a wire limit,
not a recommended watering duration.

Example: a one-minute run at 06:00. Replace the entity ID and test under supervision.

```yaml
alias: Garden timed manual irrigation
triggers:
  - trigger: time
    at: "06:00:00"
conditions:
  - condition: state
    entity_id: valve.garden_zone_1
    state: "closed"
actions:
  - action: solem_woobee.start_irrigation
    target:
      entity_id: valve.garden_zone_1
    data:
      minutes: 1
mode: single
```

The controller handles timed completion. Starts are rejected while any zone is
active. Closing an inactive zone sends no stop; closing the active zone uses
the controller’s global stop after reading state. Another application can race
that read and stop. Avoid concurrent control through MySOLEM.

Commands are never retried automatically. A timeout can occur after execution;
check controller state before retrying. Reported valve state does not measure
water flow. HA does not expose controller programs or backup/restore.
See [manual irrigation](docs/manual-irrigation.md) for actions and validation.

## Monitoring and troubleshooting

Add **Zone N irrigating** and **Zone N remaining time** to a dashboard. For fault
notifications, create an automation with an **Entity → State** trigger on a
zone’s **valve fault** entity, **To: On**, and a notification action.

If reads fail, check Bluetooth range and adapter/proxy availability, and close
apps that may hold the BLE connection. Wait for the next poll or reload the
integration. Logs record the first failure and recovery. There is no password
to reset. If only a duration is unknown, the controller omitted that page;
unknown should not be treated as zero.

Enable **Battery raw value** in the device’s entity settings if needed for
investigation. Its scale is unverified; do not use it as percentage or voltage.
Rain-delay units and active-program labels are not exposed.

Download diagnostics from the integration entry menu. The integration payload
contains cached operational fields without controller identifiers. Review the
complete download and logs before sharing; HA metadata and exception tracebacks
may contain personal details. See [diagnostics](docs/diagnostics-and-validation.md).

## Change the Bluetooth address

Use the entry menu’s **Reconfigure** action for the same physical controller.
It validates the new address against the serial already recorded in HA and
preserves entity identities. If the original serial is missing, restore the old
connection and reload first. Replacement hardware needs a new entry.
See [address changes and discovery](docs/bluetooth-discovery.md).

## Remove

Delete each controller entry under **Settings → Devices & services → SOLEM WooBee**.
To uninstall, remove the integration through HACS or delete
`custom_components/solem_woobee/`, then restart HA. Controller programs are
stored on the device and remain there.

## Development

- [Standalone client and protocol](docs/client.md)
- [Coordinator and identity](docs/coordinator.md)
- [Protocol research](docs/research/solem-woobee-wb4-home-assistant.md)
- [Quality checks and remaining work](docs/quality-scale.md)
- [Dependencies and provenance](docs/dependency-provenance.md)
- [Release procedure](docs/releasing.md)

The protocol is unofficial and may change with firmware. Clean-install and
supervised hardware acceptance remain pending; no official Quality Scale tier
is claimed. Source is licensed under [MIT](LICENSE); see the provenance guide
for third-party assets and protocol-origin review.
