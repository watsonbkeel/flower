---
name: implementing-safety-critical-watering
description: Use when changing pump control, water-level handling, command execution, timeouts, quotas, fallback behavior, calibration, or any path that can cause water to move.
---

# Implementing Safety-Critical Watering

## Safety invariants

- Uncertainty means no watering.
- SAFE_HOLD and STARTING never open the pump.
- `cloud_auto` and `user_manual` require FULL; `local_fallback` requires LOCAL_CONSERVATIVE and a valid policy.
- Low water, invalid soil data, untrusted time, missing calibration, active pump, duplicate command, or insufficient quota blocks execution.
- Pi local `water_ledger` is the hardware quota authority.

## Command timing

Do not mix the two clocks:

- `claim_ttl_sec`: only while command is pending.
- `session_max_duration_sec`: from started through all pulses and waits.

The Pi must enforce a monotonic session deadline during pumping and waiting. A 60-second claim TTL must never abort an already-started 10-minute session.

## Pump execution

Before opening: persist quota reservation, verify water level, arm a watchdog, set activity WATERING. During operation: poll water level, enforce maximum continuous time, and check session deadline. Always close in `finally`; on restart set GPIO LOW first.

Use `pump_afterdrip_mean_ml` for dose estimation and `pump_afterdrip_max_ml` only for acceptance/safety. Reject or explicitly raise requests below the minimum controllable dose.

## Physical truth

Software cannot prove motor current is off. GPIO readback is only commanded state. Ordinary one-way valves do not stop forward siphoning. Acceptance requires the reservoir below the free-air outlet, mechanical fixation, and measured post-stop leakage.

## Tests first

Write failing tests for every gate, boundary, duplicate, restart, timeout, and quota reconciliation case before implementation. Never weaken a test to make unsafe code pass.

## 语音与外设旁路

任何 aibot peripheral、语音助手、本地 HTTP 调试入口或通用 Agent 都不能直接调用泵驱动或 GPIO17。未来语音只产生业务意图，仍必须通过云端 `create_command()` 与 Pi `can_dispense()`。
