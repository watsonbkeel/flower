# Stage 8 memory concurrency verification

Source: isolated PostgreSQL 17.11 transactions and Mock memory rules. No real
hardware, Provider requests or production changes.

Fault injection holds the memory row in one transaction and observes the competing
transaction through PostgreSQL `pg_blocking_pids`, then commits the first writer.
The test does not rely on an arbitrary sleep to order the writes.

1. An edit waiting behind rule activation must clear the now-enabled rule and
   recompile fallback without that rule.
2. Worker result storage waiting behind activation must also clear current
   confirmation/activation and recompile fallback.
3. Activation waiting behind an edit that removed the structured rule must return
   `409 MEMORY_CONFIRMATION_REQUIRED`; the replacement remains unconfirmed.

Before the change, cases 1 and 2 retained `rule_enabled=true`, and case 3 returned
200. See `stage8-memory-concurrency-red.xml` and `stage8-memory-enable-red.xml`.

Mutation endpoints and Worker result storage now select the memory `FOR UPDATE`
before reading mutable state. The existing memory-to-device/plant lock sequence
and policy compiler remain in use. Provider requests run outside this row lock.

```sh
PYTHONPATH=backend .venv/bin/python scripts/test_postgres.py .venv/bin/pytest --junitxml=evidence/stage8-memory-concurrency-postgres.xml
.venv/bin/ruff check backend pi-agent tests
.venv/bin/python scripts/verify_artifacts.py
git diff --check
```

All 197 Python tests passed, with the existing visible Starlette/httpx deprecation
warning. PostgreSQL ran from unpacked binaries on a private Unix socket and was
stopped and removed by the runner. Native/browser code is unchanged since the
11 passing Node tests and desktop/mobile recognition checks in
`stage8-recognition.md`.
