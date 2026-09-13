---
name: integrating-real-hardware
description: Use when wiring devices, calibrating sensors or pumps, running physical tests, validating anti-siphon behavior, collecting real telemetry, testing offline operation, or preparing a competition demonstration.
---

# Integrating Real Hardware

## Evidence before conclusions

Label each result as REAL, DEMO, TEST, or MOCK. Do not convert a simulated pass into a physical pass. Save measurements, timestamps, photographs, logs, and exact configuration under `evidence/`.

## Safe bring-up

Power off both supplies, check polarity, validate GPIO LOW without the pump, then run a local one-second pump test. Complete water-level, soil, flow, afterdrip, and minimum-dose calibration before enabling automatic mode.

Record three flow measurements and three ten-minute afterdrip measurements. Use the mean afterdrip for estimates; use the maximum for the ≤3mL acceptance rule. Verify the reservoir’s highest water level is at least 5cm below the fixed free-air outlet.

## Fault tests

Run low-water rejection, sensor disconnect, NTP failure, network degradation, duplicate command, command/session timeout, kill -9 recovery, and reboot tests. Kill recovery must close within five seconds in all ten trials. Run BLE scanning plus one camera capture/upload per minute for 30 minutes without blocking the safety loop.

## Real telemetry

Start source_type=real collection immediately after the Stage 2 device link works. Monitor gaps daily. Never manufacture a seven-day chart; show actual coverage.

## Competition preparation

Prepare OFFLINE_DEMO with cached external knowledge but real sensors and pump, a phone hotspot, local Docker option, recorded full flow, spare SD card, spare tubing, and a physical checklist. Safety and data labels remain active in demo mode.
