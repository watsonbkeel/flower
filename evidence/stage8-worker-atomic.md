# Stage 8 Worker result atomicity audit

Requirements: v2.2.2 section 9.3 (job timeout, recovery and idempotency), sections 18.5.1 and JOB-001 acceptance.

The final job completion check could reject an expired lease while the surrounding transaction still committed its business writes. The Worker also performed Provider calls for a lease that had already expired before work began.

- `stage8-worker-atomic-red.xml`: all 6 injected-fault tests failed before implementation.
- `stage8-worker-atomic-postgres.xml`: complete regression, 184 passes and one visible upstream Starlette/httpx warning.
- Five job types were checked against complete snapshots of alerts, care profiles, fallback policies, memories and plant images: recognition, care research, weather refresh, memory structure and notification.
- Expiry at final completion leaves those business snapshots unchanged, does not mark the job succeeded, and allows lease recovery followed by successful attempt 2.
- An already expired notification job never calls the Provider.
- The final result path now explicitly rolls back on completion rejection, matching the maintenance-job path. No schema change was required. Ruff passed.

Notification success in these tests is a simulated Provider result. Database rollback cannot undo an external message already sent; the real notification gateway must continue honoring the persistent job idempotency key. No real messages, physical watering or production changes occurred.

Reproduce: `PYTHONPATH=backend .venv/bin/python scripts/test_postgres.py .venv/bin/pytest --junitxml=evidence/stage8-worker-atomic-postgres.xml`.
