# Context

## Schedule

User-facing recurring watering plan. Has one-based program number, days, start
times and four zone durations. It is independent of BLE frame layout.

## IrrigationProgram

Wire model recovered from MySOLEM. Uses zero-based program index, fixed eight
start slots and seconds. Internal transport representation.

## Days

Set of calendar days selected by a Schedule. Monday is bit 0 through Sunday bit
6 on wire.

## TimeOfDay

Validated wall-clock start time with hour and minute.

## ZoneDurations

Lossless four-zone duration value object. Callers normally construct it in
whole minutes; it stores seconds for BLE encoding.
