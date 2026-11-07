# Shared WooBee updates

Each config entry owns one DataUpdateCoordinator. A refresh uses one short BLE
connection to read identity and all three state groups, then disconnects. All
entities consume the same snapshot; no entity performs its own read. Concurrent
refresh requests use Home Assistant's coordinator debouncer.

The default interval is five minutes. No measured numerical rate limit exists:
this is a conservative battery/connection-slot policy, not a claimed device
limit. There is no immediate retry loop and no cloud token. Every connection
performs a fresh challenge authentication. Authentication rejection is a failed
update, not a user-credential reauth request (the key is fixed by the protocol).
The next scheduled poll retries with a new connection. HA records update
failures. No irrigation command is replayed.

A failed snapshot leaves the last successful data available internally, but
CoordinatorEntity marks all entities unavailable until recovery. A missing
mandatory status page, valve response or input-alert group fails the whole
snapshot. Optional identity fields remain None; missing zone duration pages
produce a None duration on an available zone, without treating unknown as zero.
Future platform state properties must preserve None as an unknown state.
Controller disabled means irrigation disabled, not offline.

Registry identifiers use the normalized configured BLE address/CoreBluetooth
UUID, matching config-entry identity. Names, serial and firmware are metadata.
Zones use stable `<controller>_zone_<1..4>` IDs and the same controller DeviceInfo;
they are channels of the physical controller, not separate registry devices.
Future platforms should subclass WooBeeEntity/WooBeeZoneEntity and give each
entity type its own unique-ID suffix when multiple entities represent one zone.

Setup performs the initial refresh before registering the controller. Only real
entity subscribers keep polling active. Without subscribers there is no periodic
BLE traffic. CoordinatorEntity subscribes when added and unsubscribes on removal.
Successful unload shuts down the coordinator timer; failed platform unload
leaves it running.
Sessions are scoped with async context managers and close on errors/cancellation.
No physical hardware validation or measured battery impact is claimed.
