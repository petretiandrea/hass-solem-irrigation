# WooBee WB-4 protocol research

Research date: 2026-11-04. Reference device: WooBee V2 WB-4, firmware 7.0.2,
9 V battery. These notes describe the original static analysis; hardware and
release acceptance are tracked in the [validation guide](../diagnostics-and-validation.md).

## Hardware and related projects

WooBee is a local BLE controller with four stations for 9 V latching valves.
The vendor lists MySOLEM control, Bluetooth Smart 4.0 LE, a nominal 10 m range,
9 V or four AAA power, a rain sensor/counter input and a master valve.
Sources: [product page](https://usa.solem-irrigation.com/products/woobee/),
[manual](https://solem-irrigation.com/wp-content/uploads/2023/12/WooBee-EN.pdf).

The projects reviewed in November 2026 did not establish WB-4 compatibility:

| Project | Documented scope at review |
| --- | --- |
| [SOLEM Irrigation](https://github.com/antitoine/ha-solem-irrigation) | MySOLEM cloud API; Bluetooth-only controllers lack a live control link |
| [Solem Toolkit](https://github.com/hcraveiro/Home-Assistant-Solem-Toolkit) | BLE BL-IP and BL-NR; different UUID/frame branches |
| [Solem Bluetooth Watering Controller](https://github.com/hcraveiro/Home-Assistant-Solem-Bluetooth-Watering-Controller) | Archived BL-IP integration |
| [solem-blip-ha](https://github.com/beelzetron/solem-blip-ha) / [solem-blip-ble](https://github.com/beelzetron/solem-blip-ble) | BL-IP client and integration |

The [public BL-IP protocol](https://github.com/pcman75/solem-blip-reverse-engineering)
uses characteristic `108b0002-eab5-bc09-d0ea-0b8f467ce8ee` and commit `3b00`.
That is not evidence of compatibility with WooBee.

## Bluetooth proxy

An active ESP32 ESPHome proxy can forward GATT to HA; the integration still
implements authentication and commands. Example configuration from the research:

```yaml
esp32_ble_tracker:

bluetooth_proxy:
  active: true
  connection_slots: 1
  cache_services: true
```

See [ESPHome Bluetooth Proxy](https://esphome.io/components/bluetooth_proxy/)
and [HA Bluetooth](https://www.home-assistant.io/integrations/bluetooth/).
Place the adapter near the controller; buried boxes, water and covers reduce
range. Frequent scans/connections may reduce battery life. Proxy compatibility,
connection contention with MySOLEM and battery impact need WB-4 validation.

## Static APK findings

The original analysis used MySOLEM 6.13.3. The APK and decompiled source are not
tracked. Acquisition checksum, tool versions and derivation inventory remain
missing; see [provenance](../dependency-provenance.md).

DEX strings contain several SOLEM UUID families: `108B…`, `A3EB…` and `A449…`.
The hardware-type branch for WooBee V2/type 180 selects `A98C…`. Firmware major
version 6 or later selects `BluetoothV6FrameManager`.

The standard BLE manager reads a challenge, sends its AES-ECB encryption and
waits for `AUTHENTICATED\0`. Request `…0002` and response `…0003` payloads use
AES-CTR with the challenge as nonce; authentication uses `…0005`.
`BleManager.doWriteCharacteristic()` uses `WRITE_TYPE_NO_RESPONSE` for commands.
A historical bugreport contained advertisements only, with no ACL/ATT frames;
it supplied no command or verified discovery fixture.

For type 180, `BluetoothRequester.readState()` queues `statusV5()` (`3b 00`),
`readValveStatusV5()` (`19 03 00 10 ff`) and `readInputsAlerts()` (`71 00`).
Manual commands and frame layouts are retained in the [client reference](../client.md#recovered-mysolem-transport).
State and valve-fault parsers were derived from the corresponding Java methods.

## Schedule frames

For type 180, `configurationV5()` calls `configIrriV5()` for each changed program.
Each program uses seven frames: two name frames (`0x2f`), configuration (`0x37`,
page 0), eight starts (page 1) and three duration blocks (pages 2–4).
The program ID is `0x10 | index`.

- Start times are minutes after midnight; 1440 disables a slot.
- Zone duration is 24-bit big-endian seconds.
- Day bits run Monday (bit 0) through Sunday (bit 6), matching `WFBLUtils`.
- Configuration includes zone pause, water budget, cycle, days, period,
  synchronization day and current date.

`woobee_api.IrrigationProgram` and `WooBeeV2.write_program()` implement this
sequence. The CLI has no program-write command. The standalone API supports
schedule writes and restore; HA exposes only monitoring and manual irrigation.
