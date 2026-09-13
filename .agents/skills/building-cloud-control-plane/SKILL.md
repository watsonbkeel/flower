---
name: building-cloud-control-plane
description: Use when implementing FastAPI, PostgreSQL, migrations, command lifecycle, the job worker, providers, the deterministic decision engine, fallback policies, storage, or cloud deployment.
---

# Building the Cloud Control Plane

## Core architecture

Run PostgreSQL, API, independent Worker, and an internal Nginx proxy under the Flower Docker Compose project; the existing host Nginx remains the only public 80/443 ingress. Slow recognition, search, LLM, aggregation, and cleanup work belongs in the PostgreSQL-backed Worker, never a request-bound BackgroundTask.

## Command contract

All command creation goes through one `create_command()` function. Enforce canonical source and run-mode enums, authorization, quota precheck, active-command uniqueness, claim deadline, and calculated session duration there.

Use `POST /device/commands/claim` with a transaction and `FOR UPDATE SKIP LOCKED`. Pending expiry and executing timeout are different states. Progress updates show pulse details but do not extend the absolute session deadline.

## Decision boundary

The deterministic full watering decision exists in one backend module. Complete branches include: above threshold hold; rain defer; below threshold within window water; severe deficit may override the window; otherwise defer. LLM output is schema-validated knowledge only and contains no execution values.

Generate `fallback_policy` with version, hash, valid period, IANA timezone, local windows, conservative threshold, dose, interval, and quota.

## Data durability

Migrations must include partial unique indexes for one primary plant and one active dispense command. Raw telemetry has an indexed timestamp, hourly aggregation, retention, and source labels. Image upload checks free disk space and refuses below the configured threshold.

## Verification

Test concurrency, restart recovery, job idempotency, timeout semantics, authorization, storage exhaustion, aggregation safety, and backup restoration before claiming readiness.

## 共享宿主机边界

Flower 生产使用独立 Compose project；宿主 Nginx 独占 80/443，Flower 只发布 `127.0.0.1:18080`。Production migration 必须显式一次性执行，镜像按 commit SHA 固定，production auth bypass/非HTTPS 配置必须 fail closed。不得修改 `/opt/asist-embodiment`。
