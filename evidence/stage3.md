# Stage 3 Worker and Recognition / v2.2.2

Source: TEST PostgreSQL + MOCK recognition. Real provider calls: 0.

Command:
`PYTHONPATH=backend .venv/bin/python scripts/test_postgres.py .venv/bin/pytest --junitxml=evidence/stage3-postgres.xml`

Result: 93 passed. Includes an actual independent Worker child process reading the
database, processing a stored image with Mock recognition, and atomically publishing
the result. Worker process execution has a hard subprocess timeout; lease ownership
and attempt fence stale results. Recovery/retry limit is three attempts.

Images: MIME/magic/pixel/size checks, UUID relative storage, authenticated reads,
owner-scoped uploads, missing resource rejection, STORAGE_LOW refusal with durable
alert, and no record/file on invalid upload. Recognition returns explicit mock Top3;
species confirmation disables auto mode and invalidates previous care/policy records.

Subprocess validation found and fixed numeric environment coercion for Worker
concurrency. Configuration exceptions now hide input values to avoid leaking secrets.

stage3-red.xml preserves the initial failing test. An intermediate SQLite-only run is
stage3-green.xml and contains a failure before the lease test clock was corrected;
the final authoritative result is stage3-postgres.xml. No real Provider, Pi camera or
production container result is claimed.
