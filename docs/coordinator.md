# Shared updates and identity

Each config entry owns one `DataUpdateCoordinator`. A refresh opens a short BLE
connection, authenticates, reads identity and three state groups, then disconnects.
Entities share the snapshot. Concurrent refresh requests use HA’s debouncer;
commands and polling share an entry-scoped I/O lock.

Polling runs every five minutes while entities subscribe and stops without
subscribers. This interval is a conservative battery/connection-slot choice;
battery impact and device rate limits have not been measured. Successful unload
stops the timer; failed platform unload leaves the coordinator running.

Each connection uses a fresh challenge. There are no immediate retries or cloud
tokens. Failed reads retry on the next scheduled poll with a new connection;
irrigation commands are never replayed. Context managers close sessions on errors
and cancellation.

A missing mandatory status, valve or input-alert response fails the snapshot.
Optional identity fields and missing zone durations remain `None`; zero duration
remains zero. Irrigation disabled is a controller flag, not an offline state.

On failure, the last snapshot remains cached internally, but state entities become
unavailable. Connectivity remains available to show the last read outcome, and
Last fetched retains its prior successful-poll time. RSSI samples HA’s cached
connectable advertisement after a successful poll; missing cache data is unknown.
Command-only reads do not update RSSI or Last fetched.

Device and entity IDs derive from the normalized identity address (BLE MAC or
CoreBluetooth UUID). Reconfiguration freezes that address while changing the
connection address; see [address changes](bluetooth-discovery.md#registry-identity).
Names, serials and firmware are metadata. Zones use `<controller>_zone_<1..4>`
identities and share one physical controller device. Entity types add a field
suffix where several entities represent one zone.
