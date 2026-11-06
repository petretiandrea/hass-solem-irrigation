# Context

## Schedule

User-facing recurring watering plan. Has one-based program number, days, start
times, four zone durations, water budget and pause between zones. It is
independent of BLE frame layout.

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

## ControllerBackup

Portable collection of Schedules. It represents configuration read from a
controller and is restored by replacing its included schedules.
