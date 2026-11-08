# Bluetooth addresses and discovery

## Reconfigure a controller

In **Settings → Devices & services → SOLEM WooBee**, open the entry menu and
choose **Reconfigure**. Enter the new BLE MAC address or CoreBluetooth UUID,
confirm it is the same physical controller and submit. This updates HA’s
connection address, not the controller’s address.

Validation authenticates and reads identity/state without sending irrigation or
configuration commands. The candidate serial must match the serial already in
the entry’s device registry record. Missing or mismatched serials are rejected.
If the original serial is missing, restore the old connection and reload to read
it before retrying. Serial matching is an identity check, not cryptographic proof.

Addresses reserved by other entries are rejected before and after validation.
Failures or cancellation leave entry data unchanged. Success saves the address
and reloads the entry; if the later reload fails, HA retries setup with the saved
address. Options, device customizations and entity identities are preserved.
Replacement hardware should be added as a new entry after removing the old one.

## Registry identity

The first successful reconfiguration copies the original `address` into
`identity_address`. Later changes update only the transport `address`.
Config-entry unique IDs, device identifiers and entity unique IDs keep the
original identity address. Entries without `identity_address` use `address`.
This additive field requires no bulk registry migration.

Both the current connection address and original identity address remain reserved
to prevent duplicate entries or colliding registry IDs. All platforms use the
frozen identity, preserving history and automation references.

## Automatic discovery: pending

There is no verified WB-4 advertisement fixture or stable advertised identity in
this repository. The [redacted GATT profile](examples/woobee-gatt.json) records
services, not advertisements. A service UUID in GATT does not establish that it
is advertised, and a local name alone cannot identify supported hardware.
Automatic discovery and address updates remain TODO.

To establish a matcher, collect advertisements from WB-4/type 180/firmware 7.0.2.
Record date, model, firmware, scanner/backend and versions, local name, service
UUIDs, manufacturer IDs/data, service data and connectability. Check stability
across normal advertising/connection states and address changes. Keep raw
identifiers private; publish consistently redacted fixtures with byte offsets
and lengths preserved. Compare any stable advertised identity with read identity.

This ten-second scan opens no GATT connection. Set the address locally; output
contains private identifiers and must be reviewed before sharing.

```python
import asyncio
import json
from bleak import BleakScanner

ADDRESS = "replace-with-your-controller-address"

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

Bleak’s generic advertisement object does not establish connectability; record
that separately through HA’s Bluetooth scanner. Scanning may send scan requests.
No reset, firmware update, irrigation or configuration write is needed to collect
this evidence. Do not infer WooBee support from other SOLEM product formats.
