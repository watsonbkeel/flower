# Stage 8 weather cache audit

Requirements: frozen v2.2.2 sections 2.1 (fetch/cache local weather), 9.3-9.4 (independent Worker, bounded Provider retries), 10.4 (rain decision), 18.6 (failure degradation).

The audit found that weather was fetched only during care research and never refreshed after expiry. It also found that a future observation or mismatched source could affect rain decisions, while malformed cached timestamps could stop evaluation with an exception.

Changes:

- Schedule `weather_refresh` through existing durable jobs for the latest confirmed, unexpired care profile when its weather is unusable.
- Keep HTTP calls in the existing isolated Worker process. Use existing three-attempt job retry and persistent Provider quota. Hourly idempotency and an active-job check prevent repeated scheduling.
- Preserve the previous cache on failure. Fence writes against profile revocation, replacement, expiry and changed location/source. Updating weather does not reconfirm or version the underlying care knowledge.
- Validate weather time and source before rain decisions; invalid weather is ignored under the existing unavailable-weather behavior.

Evidence:

- `stage8-weather-red.xml`: 6 expected failures and 1 pass before implementation.
- `stage8-weather-green.xml`: initial 7 targeted checks passed; four further cases were then added for a valid rain forecast, changed location and inactive profiles.
- `stage8-weather-postgres.xml`: final complete regression, 166 passes, 1 visible upstream Starlette/httpx warning. Includes 11 weather checks, with a real isolated Worker subprocess and Mock weather.
- Ruff passed for backend, Pi and tests. No miniapp or physical adapter changes were made.
- Restarted only the Flower development stack to load this implementation. The loopback `/ready` returned HTTP 200, and its SQLite Worker heartbeat was verified younger than 120 seconds. Development supervisor PID: 1591092; URL: `http://127.0.0.1:18082/preview/`.

Reproduce:

```sh
PYTHONPATH=backend .venv/bin/python scripts/test_postgres.py .venv/bin/pytest --junitxml=evidence/stage8-weather-postgres.xml
.venv/bin/ruff check backend pi-agent tests
.venv/bin/python scripts/verify_artifacts.py
git diff --check
```

The PostgreSQL runner uses unpacked PostgreSQL 17.11 binaries with a private Unix socket and removes its temporary cluster after testing. No Docker installation, production deployment, host network changes, aibot edits, real Provider calls or physical watering were performed. Existing B01-B09 remain open.
