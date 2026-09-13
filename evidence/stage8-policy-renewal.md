# Stage 8 fallback renewal audit

Requirements: v2.2.2 sections 6.2-6.3 (continued cloud operation and versioned fallback), 10.6 (bounded policy lifetime), 17 Stage 6 (continuous operation).

Policies were previously generated only by user changes. A seven-day policy could expire despite a still-valid confirmed care profile, and the Pi would then lose its valid policy prerequisite. Worker maintenance now renews due policies through the existing compiler.

- `stage8-policy-renewal-red.xml`: all six targeted tests failed because renewal was absent.
- `stage8-policy-renewal-postgres.xml`: full regression, 190 passes and one visible upstream Starlette/httpx warning.
- Tests simulate time near the first policy expiry, verify one new version, validate its content/hash with the actual Pi policy parser, and verify prior server versions are invalidated.
- Unconfirmed/expired care and revoked devices do not receive new policies. Policies capped at imminent care expiry do not cause a renewal loop. Two concurrent PostgreSQL maintenance transactions issue only one version.
- Renewal is for primary plants, defaults to one day before expiry, and is configurable via `FALLBACK_RENEW_BEFORE_SEC` (60-86400 seconds). It does not extend care confirmation or its validity, change auto-mode, or bypass dispensing gates.
- Configuration is passed through the Compose template; Docker/Compose execution remains unverified pending authorization. Ruff passed. No actual external Provider calls, hardware watering, aibot edits or production changes occurred.
- Restarted only the development supervisor (PID 1604520); API `/ready` returned HTTP 200 and the running Worker had a heartbeat younger than 120 seconds. Preview: `http://127.0.0.1:18082/preview/`.

Reproduce: `PYTHONPATH=backend .venv/bin/python scripts/test_postgres.py .venv/bin/pytest --junitxml=evidence/stage8-policy-renewal-postgres.xml`.

The simulated time advance is not seven days of real telemetry or a physical offline acceptance run. Those blockers remain unchanged.
