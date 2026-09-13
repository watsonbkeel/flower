# Stage 8 development verification

All pump and sensor execution in this evidence is MOCK. PostgreSQL is an actual isolated PostgreSQL 17.11 process, not a mocked database.

- `stage8-postgres.xml`: 149 passed. Reproduction: `PYTHONPATH=backend .venv/bin/python scripts/test_postgres.py .venv/bin/pytest --junitxml=evidence/stage8-postgres.xml`.
- One upstream warning remains: Starlette TestClient deprecates its httpx integration in favor of httpx2. The warning is not filtered, and all assertions passed.
- Red XML files demonstrate missing/incorrect behavior before implementation: live fallback expiry, independent telemetry, claimed-command grace, revocation, late receipts, per-command reconciliation, UTC serialization normalization, fallback session auditing, memory photo presentation, notifications and mixed-source air data.
- `backend/tests/test_full_mock_flow.py`: Mock image -> Top3 -> species confirmation -> care Worker -> confirmation -> create_command -> Pi can_dispense -> two pulses -> result -> authenticated per-command reconciliation. Offline-demo monotonic time is accelerated; no physical pump runs.
- `stage8-browser-workflow.json`: actual loopback development browser flow for pending-to-succeeded, care confirmation, memory rule confirmation and auto-mode switch.
- `stage8-browser-command.png`, `stage5-home-{390,1440}.png`, `stage5-trends-{390,1440}.png`: final development views. Images are labelled placeholders; Chinese fonts and nonblank chart pixels checked.
- `development-health.json`: API health/readiness and 100 read-only status requests, concurrency 4, p95 39.26ms on development SQLite. Production/aibot peak tests NOT_RUN.
- `backend-dependency-audit.json`, `pi-dependency-audit.json`: no known vulnerabilities in resolved declared dependencies at verification time.
- `scripts/release.py` creates a clean-SHA development bundle. Docker was not installed; release state is NOT_BUILT and image IDs remain unavailable.
- No production release, physical setup, WeChat console action, host Nginx/network/VPN changes or aibot modification was performed.
