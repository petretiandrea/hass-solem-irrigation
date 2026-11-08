# Bluetooth discovery and address changes (SBR-101)

## Evidence and remaining discovery work

The supported hardware scope remains **WooBee V2 / WB-4, type 180,
firmware 7.0.2**. `AGENTS.md`, `woobee-gatt.json` and the research document
record protocol/GATT evidence. They do not provide an advertisement fixture
with verified manufacturer/service data and a documented matcher. The research
document mentions a historical advertising-only bugreport; its raw capture and
provenance are not in this checkout. No controller or supervised capture was
available in this agent workspace.

Consequently automatic discovery and automatic address updates remain **TODO**.
There is no new manifest matcher or Bluetooth discovery step. A GATT service
UUID is not proof that a device advertises that UUID. A local name alone is not
proof of WB-4 support. Do not use another SOLEM product's advertisement format
or silently generalize the type-180 protocol branch.

Before implementing discovery, collect supervised scan evidence from the known
WB-4. Record date, operator, physical model/type, firmware, scanner/backend and
versions; capture local name, service UUIDs, manufacturer IDs and exact bytes,
service data and connectability. Preserve the relationship between observations
at the original and changed addresses in private evidence. Redact addresses and
serials consistently in public fixtures; retain byte offsets/lengths necessary to
review the matcher. Establish whether any advertised identifier survives address
changes and matches a read identity. Do not automatically map by name or address.

For a supervised advertisement-only capture, an operator with Bleak available
can run this snippet locally, after replacing the address. It scans for ten
seconds and prints only the selected device. It opens no GATT connection and
invokes no controller commands. Scanning can send BLE scan requests. Confirm
connectability separately with the Home Assistant Bluetooth scanner evidence;
Bleak's generic advertisement object does not establish it.

```python
import asyncio
import json
from bleak import BleakScanner

ADDRESS = "replace-with-the-supervised-controller-address"

async def capture():
    found = await BleakScanner.discover(timeout=10, return_adv=True)
    for device, advertisement in found.values():
        if device.address.lower() == ADDRESS.lower():
            print(json.dumps({
                "address": device.address,
                "local_name": advertisement.local_name,
                "service_uuids": advertisement.service_uuids,
                "manufacturer_data": {
                    str(key): value.hex()
                    for key, value in advertisement.manufacturer_data.items()
                },
                "service_data": {
                    key: value.hex()
                    for key, value in advertisement.service_data.items()
                },
                "rssi": advertisement.rssi,
            }, indent=2))

asyncio.run(capture())
```

Repeat under operator supervision as needed to establish stability across normal
advertising/connection states. Do not reset, change firmware, start/stop zones,
sync clocks, or write programs/schedules to generate evidence. No controller
writes are authorized by SBR-101. Simulated BLE tests cannot replace this capture.

## Reconfigure an existing controller

In **Settings → Devices & services → SOLEM WooBee**, open the entry menu and
choose **Reconfigure**. Enter its new Bluetooth MAC address (or CoreBluetooth
UUID), confirm that it is the same physical controller, and submit. This changes
the HA connection address; it does not change the controller's Bluetooth address.
No device password is required. Authentication and identity/state reads are used
for validation; no irrigation/configuration command is sent.

The candidate must be reachable through HA Bluetooth, authenticate successfully,
and return a valid snapshot. Its serial must match a serial previously recorded
on this entry's device registry record. Missing or mismatched candidate serials
are rejected. If the original serial is missing, the flow fails closed: restore
the old connection and reload the entry to read/register its serial before
retrying. A confirmation checkbox cannot substitute for serial evidence. This
limitation is intentional because the protocol permits missing identity pages.
Serial continuity is a device identity check, not a cryptographic attestation.

The flow rejects addresses reserved by another entry, including that entry's
original identity address, before validation and again after the asynchronous
read. Failed validation, collisions and cancellation leave entry data unchanged.
Successful validation updates the connection address and reloads the entry.
If a later reload cannot connect, HA uses its existing setup retry behavior; the
validated new address remains saved. Retry reconfiguration if necessary. Options
and entity/device customizations remain attached to the existing entry.

## Address-based unique ID migration decision

There is **no rewrite** of existing config-entry unique IDs, entity unique IDs or
device identifiers, and no automatic switch to serial-based IDs. On the first
successful reconfiguration, the old `address` is copied to `identity_address` in
entry data; only `address` becomes the new transport address. Later changes keep
`identity_address` unchanged. Entries without the new field continue deriving
identities from their existing address. The additive field is backward compatible
with existing version-1 entries; no bulk registry migration is needed.

The coordinator uses the transport address for BLE and the identity address for
all platforms and the device registry. This preserves existing entity IDs,
registry IDs, history/automation references, device association and disabled
entities. The old identity address remains reserved to avoid creating a second
entry with colliding registry identifiers. The current address is also reserved,
including when its config-entry unique ID is still the old address.

Reconfiguration is for the same physical controller. For replacement hardware,
remove the old entry and add the replacement. No automatic discovery updates are
implemented: a future implementation must establish a verified stable advertised
identity before updating an entry, while respecting this frozen legacy identity.
