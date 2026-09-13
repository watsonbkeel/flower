# Stage 6 TEST evidence

- `stage6-red.xml`: 3 failures before implementation, including falsely counting a six-day data gap.
- `stage6-postgres.xml`: 132 passed using disposable PostgreSQL 17.11 over Unix socket.
- Hourly aggregation includes device, plant, UTC hour and source; the open hour is excluded.
- Cleanup checks count, coverage, means, extrema and water ratio against raw rows. A modified aggregate prevents raw deletion.
- Raw retention is at least 30 days; hourly is at least 365 days. Late rows after a bucket was purged remain for reconciliation and cannot overwrite that bucket.
- Pinned photos and active image jobs survive cleanup. Unreferenced files are removed on a subsequent sweep after a one-day grace period, so a transaction rollback cannot remove a live photo.
- Watering audit sessions retain their command parents. Only old terminal unreferenced commands and terminal jobs are removed.
- Worker schedules hourly leased jobs; `scripts/cleanup.sh` is an explicit maintenance entrypoint.
- No real telemetry exists. DATA-001 remains BLOCKED_PHYSICAL.
