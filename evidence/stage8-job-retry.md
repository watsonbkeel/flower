# Stage 8 requested-job retry audit

Requirements: v2.2.2 sections 9.3 (durable jobs with retry/idempotency), 11.3 (asynchronous user experience), 18.6 (Provider failure handling).

Care research and memory structuring previously keyed jobs by resource update time. After three failed attempts, submitting the same user action returned the permanently failed job. Care research also could not be regenerated without an unrelated plant change. Concurrent first-time enqueues could raise a unique-constraint error.

The endpoints now accept an optional 1-100 character `Idempotency-Key`, scoped to user, operation and target. Replaying a key returns its original job, including terminal failures. A new user action uses a fresh key; callers without a key create a new operation. Worker retry limits and failed-job history remain intact. Atomic database conflict handling makes concurrent identical enqueues return one durable job.

Evidence:

- `stage8-job-retry-red.xml`: all four targeted PostgreSQL tests failed before implementation, including a real unique-key violation under concurrent enqueue.
- `stage8-job-retry-node-red.tap`: one new client-action test failed before request keys were wired.
- `stage8-job-retry-postgres.xml`: 170 passes and one visible upstream Starlette/httpx warning. PostgreSQL 17.11 used a temporary private Unix socket cluster removed after testing.
- `stage8-job-retry-sqlite.xml`: four targeted tests pass using the SQLite conflict-handling path.
- `stage8-job-retry-node-green.tap`: nine Node tests pass; native care and memory actions create distinct request keys.
- `stage8-job-retry-browser.json`: on a 390x844 browser, a failed care job re-enables the action and a second action succeeds with a different key. Job responses were intercepted Mock fixtures; this test made no Provider calls or database job mutations.
- The first browser attempt overlapped the development stack restart and failed while the API was unavailable. It was rerun only after `/ready` returned HTTP 200, then passed. This was a test orchestration interruption, not a passed first attempt.
- Ruff and `git diff --check` passed. No schema migration, pump path, production service, host network or external credentials changed.

Reproduce:

```sh
PYTHONPATH=backend .venv/bin/python scripts/test_postgres.py .venv/bin/pytest --junitxml=evidence/stage8-job-retry-postgres.xml
.venv/bin/pytest backend/tests/test_requested_jobs.py --junitxml=evidence/stage8-job-retry-sqlite.xml
npm --prefix miniapp test
```

From `miniapp`, run `FONTCONFIG_FILE=/root/flower/.runtime/fonts.conf LD_LIBRARY_PATH=/root/flower/.runtime/browser/usr/lib/x86_64-linux-gnu node scripts/verify-job-retry.js` for browser verification.

Development supervisor PID after restart: 1596287. Preview: `http://127.0.0.1:18082/preview/`. B01-B09 remain open; no native WeChat, real Provider, deployment or physical acceptance is claimed.
