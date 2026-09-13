---
name: building-raspberry-pi-agent
description: Use when implementing or modifying the Raspberry Pi agent, GPIO, ADS1115, soil sensing, P451 water level, BLE, camera, SQLite state, systemd, or local fallback execution.
---

# Building the Raspberry Pi Agent

## Boundaries

The Pi is a sensor collector and safety executor. It must not copy cloud weather, seasonal, pot, or family-memory decision formulas. It may only execute cloud commands or a validated versioned `fallback_policy`.

## Module isolation

Keep separate modules for sensors, camera, actuators, safety gates, command execution, cloud client, local storage, time, and policy validation. A BLE or camera failure must not block the water-level loop or pump shutdown.

## Hardware behavior

- Use physical pins from the wiring document.
- Initialize GPIO17 LOW before other initialization.
- Read ADS1115 through I²C and expose raw plus relative soil moisture.
- Debounce P451 asymmetrically: enter low-water quickly, recover only after stable water.
- Probe Xiaomi BLE and encryption state; return explicit READY/BINDKEY_REQUIRED/UNSUPPORTED/STALE. Support a wired provider without changing consumers.
- Use stable camera device paths, discard warm-up frames, and quality-check images.

## Persistence and time

Use SQLite with durable writes for commands, events, fallback policy, and water ledger. Use monotonic time within a boot and trusted UTC across reboots. Policy local windows require its IANA timezone through `zoneinfo`.

## Service behavior

Provide install, diagnose, calibrate, BLE probe, emergency-off, and systemd files. A diagnostic pump test must be local, explicit, and at most one second. A real hardware test must record evidence; Mock success is not hardware success.
