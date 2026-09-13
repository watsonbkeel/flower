# Stage 7 development preparation

- `stage7-postgres.xml`: 136 tests passed after dependency updates; one upstream Starlette/httpx TestClient deprecation warning remains visible.
- `tests/test_delivery.py` restored a custom-format PostgreSQL dump into a separately created database, checked migration head and at least 18 tables, verified sentinel data and uploaded bytes, and rejected an existing target.
- Checksum corruption and 7 daily / 4 weekly retention tested. Restore never drops an existing DB.
- `backend-dependency-audit-before.json`: 71 vulnerability entries in four dependencies. `backend-dependency-audit.json`: no known vulnerabilities after updates.
- Build/deploy/rollback/timer/Nginx artifacts are prepared, not executed. Docker absent; no image ID, production URL, runtime Compose proof, offsite target or peak coexistence measurement is claimed.
- Production scripts require the authorized window, a full SHA manifest, matching image IDs/file hashes, and a recent independent backup restore record.
- No Docker installation, preflight audit repetition, host network change or writes to production directories occurred.
