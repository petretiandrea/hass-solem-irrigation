# SOLEM WooBee WB-4 — Home Assistant e BLE

Data ricerca: 2026-11-04.
Target utente: WooBee V2 WB-4, firmware 7.0.2, alimentazione batteria 9 V.

## Esito

WooBee WB-4 è controller BLE locale, non cloud: 4 stazioni con elettrovalvole bistabili 9 V. SOLEM dichiara controllo MySOLEM, Bluetooth Smart 4.0 LE, portata 33 ft/10 m, batteria 9 V oppure quattro AAA, sensore pioggia/contatore e valvola master. Nessuna integrazione Home Assistant ufficiale né progetto pubblico che dichiari supporto WB/WooBee verificato.

Fonti: [scheda ufficiale WooBee](https://usa.solem-irrigation.com/products/woobee/), [manuale ufficiale WooBee](https://solem-irrigation.com/wp-content/uploads/2023/12/WooBee-EN.pdf), [integrazione Bluetooth HA](https://www.home-assistant.io/integrations/bluetooth/).

## Integrazioni esistenti

| Progetto | Trasporto/modelli dichiarati | Cosa fa | Limite per WB-4 |
| --- | --- | --- | --- |
| [SOLEM Irrigation](https://github.com/antitoine/ha-solem-irrigation) | API cloud MySOLEM; LoRa/LR e Wi-Fi | valvole, durata, programmi, stop, rain delay, batteria, flusso | README dichiara controller Bluetooth-only senza live link: solo sensore schedule. WooBee non ottiene controllo remoto. API privata, non supportata SOLEM. |
| [Solem Toolkit](https://github.com/hcraveiro/Home-Assistant-Solem-Toolkit) | BLE; BL-IP consolidato, BL-NR validato | comandi manuali, stop, on/off/rain delay; BL-IP: programmi e stato | non dichiara WooBee. UUID/frame BL-IP e BL-NR differiscono da ramo WooBee ricostruito dall'APK. |
| [Solem Bluetooth Watering Controller](https://github.com/hcraveiro/Home-Assistant-Solem-Bluetooth-Watering-Controller) | BLE BL-IP | entità controller/stazioni, scheduling | repository archiviato/deprecato; autore indica migrazione a Smart Water Controller + Toolkit. Nessun supporto WooBee dichiarato. |
| [solem-blip-ha](https://github.com/beelzetron/solem-blip-ha) / [solem-blip-ble](https://github.com/beelzetron/solem-blip-ble) | BLE BL-IP | controllo, stato e gestione programmi BL-IP | strettamente BL-IP; non evidenza di compatibilità WB-4. |

Il reverse engineering BL-IP pubblico documenta scritture sulla caratteristica `108b0002-eab5-bc09-d0ea-0b8f467ce8ee`, seguite da commit `3b00`; riguarda esplicitamente BL-IP, non WooBee. Fonte: [documentazione protocollo BL-IP](https://github.com/pcman75/solem-blip-reverse-engineering).

## ESPHome Bluetooth Proxy

Percorso consigliato: Home Assistant + proxy ESPHome **ESP32** Ethernet/antenna esterna entro ~10 m reali dal pozzetto + integrazione custom Python che conosce protocollo WooBee. Proxy inoltra GATT al Bluetooth stack HA; non traduce né inventa protocollo.

```yaml
esp32_ble_tracker:

bluetooth_proxy:
  active: true
  connection_slots: 1
  cache_services: true
```

Proxy ESPHome attivo su ESP32 supporta GATT read/write; default 3 slot, massimo 9, raccomandazione non oltre 5. Ethernet evita contesa Wi-Fi/BLE. BK72xx/LN882x sono solo advertisement: inutili per controllo WooBee. Fonti: [Bluetooth Proxy ESPHome](https://esphome.io/components/bluetooth_proxy/), [BLE Client ESPHome](https://esphome.io/components/ble_client/).

`ble_client` dentro ESPHome non elimina lavoro protocollo: gestisce connessione ma non espone sensori/output. Supporta massimo tre device ESP32 e non riceve advertisement mentre dispositivo resta connesso. Per WB-4 preferire proxy HA: integrazione custom può usare stessa API Bluetooth di HA/bleak e mantenere logica protocollo lato HA.

## Limiti operativi

- WB-4 è battery-powered → connessioni, scansioni attive e polling frequente riducono autonomia. SOLEM dichiara Eco Mode; ESPHome conferma active scan aumenta drain su dispositivi BLE a batteria.
- BLE range dichiarato 33 ft: pozzetto interrato, acqua e coperchio riducono margine. Posizionare proxy vicino, alto e asciutto; Ethernet + antenna esterna preferibili.
- Proxy attivo consente trasporto GATT, non conferma semantica dei frame. ACK BLE non prova apertura valvola; servono test controllati e, se disponibile, contatore acqua.
- Scheduling può restare locale sul controller; HA deve inviare manual start/stop e non duplicare programmi finché protocollo configurazione non è validato.
- Connessione MySOLEM telefono e HA/proxy competono: una sessione GATT alla volta è ipotesi prudente da verificare sul WB-4.

## APK disponibile: evidenza statica iniziale

`MySOLEM.apk` presente nel workspace. Ricerca nelle stringhe DEX trova stack Android `BluetoothGatt` e template UUID proprietari:

```
108B000%d-EAB5-BC09-D0EA-0B8F467CE8EE
A3EB000%d-8C8C-B87A-827D-9BF3DE08084A
A449000%d-332E-BBAE-A5E1-9D6BD1FDEA5B
```

Questa evidenza prova che APK contiene più famiglie GATT SOLEM. UUID `108b…`
coincide con protocollo BL-IP pubblico; WooBee usa `A98C…`, selezionato dal tipo
180 nel codice APK. I frame BLE WooBee sono ricostruiti dal ramo statico V6.

### Statico: handshake BLE osservato

Il DEX contiene `fr.solem.connectedpool.com.ble.BleIPXManager`: gestisce
`uuidAuth`, `uuidRead`, `uuidWrite`, legge una challenge (`nounce` nel codice),
abilita le notifiche sulla caratteristica auth e calcola una risposta con
`AES/ECB/NoPadding` e una private key. Sceglie UUID dalle tre famiglie sopra.
Questo prova un handshake proprietario prima delle operazioni; non identifica
quale famiglia appartenga al WooBee V2 né definisce i frame valvola.

Il bugreport acquisito contiene solo advertising BLE, senza pacchetti ACL/ATT:
non aggiunge frame GATT al reverse engineering.

Il manager BLE standard dell'APK usa UUID request `…0002`, notification
`…0003`, auth `…0005`; challenge AES-ECB e payload AES-CTR con la challenge
come nonce. Queste operazioni sono state replicate in `solem_woobee.protocol`.
Il parser/comandi di zona sono recuperabili dal ramo hardware 180.

Per `majorVSoft >= 6` l'APK seleziona `BluetoothV6FrameManager`; WooBee V2
firmware 7.0.2 entra quindi in questo ramo. Per `manufacturerData.type == 180`,
`BluetoothRequester.readState()` accoda `statusV5()`, `readValveStatusV5()`,
`readInputsAlerts()`:

```
3b 00
19 03 00 10 ff
71 00
```

`manualCommandV5()` sul prodotto watering seleziona:

```
ManualValve:   testValvesV5(outputIndex + 1, duration * 60)
               31 05 12 <zona 1-based> <secondi 24-bit big-endian>
ManualStop:    31 05 15 00 ff 00 00
TestAllValves: 31 05 11 00 <secondi 24-bit big-endian>
ManualProgram: 31 05 14 00 <programma 0-based> 00 00
```

`BleManager.doWriteCharacteristic()` cifra AES-CTR e scrive su `…0002` con
`WRITE_TYPE_NO_RESPONSE`; il client Python riproduce questo dettaglio. Stato e
fault valvole hanno parser Python derivati dai metodi Java corrispondenti.

### Programmi irrigazione: RE statico completo scrittura

`configurationV5()` per tipo 180 chiama `configIrriV5()` per ogni programma
modificato. Ogni programma genera sette frame: due nome (`0x2F`), configurazione
(`0x37`, pagina 0), otto start times (`0x37`, pagina 1), tre blocchi durate
(`0x37`, pagine 2–4). ID programma: `0x10 | indice`.

- Start time: minuti da mezzanotte, `1440` = disabilitato.
- Durata zona: secondi big-endian, 24 bit.
- Giorni: bit 0 Lunedì … bit 6 Domenica. `WFBLUtils` Java conferma mapping.
- Configurazione include intervallo tra zone, water budget, ciclo, giorni,
  periodo, giorno sincronizzazione e data corrente.

`solem_woobee.IrrigationProgram` e `WooBeeV2.write_program()` ricostruiscono
questa sequenza. Non esiste comando CLI per scrivere programmi.

## Decisione

Non installare integrazioni BL-IP/BL-NR sul WooBee V2 firmware 7.0.2. Client
dedicato WooBee usa UUID/frame recuperati dall'APK; HCI non serve alla
ricostruzione attuale.

## Client Python nel workspace

`solem_woobee.WooBeeClient` esegue discovery BLE e `inspect(address)`. 
`solem_woobee.WooBeeV2` esegue auth, query stato e comandi manuali recuperati
staticamente dall'APK. Non modifica programmazioni né esegue DFU.

