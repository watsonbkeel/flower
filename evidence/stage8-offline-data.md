# Stage 8 offline demonstration data

Specification 21.2.13 requires an offline demonstration data package. Existing
Mock values were embedded in Provider methods; they are now delivered together
in `backend/flower/data/offline_demo.json` and loaded through Python package
resources by `MockProviders`.

The data retains the existing Top3 names/confidences, two source links, care
knowledge, weather, unconfirmed family rule and notification response. Existing
schemas still validate responses. Runtime timestamps describe simulated calls,
not live observations or retrieval. Mock labels remain explicit; the bundle has
no real telemetry, dispense commands, GPIO or execution-volume parameters.

Two new tests first failed because the package was absent
(`stage8-offline-data-red.xml`). They now verify packaged metadata/source labels,
Provider use, confirmation requirement and independent returned data. Full
regression passed all 222 tests (`stage8-offline-data-postgres.xml`), including
the Mock end-to-end flow and independent Worker subprocesses. The existing
Starlette/httpx deprecation warning remains visible.

```sh
PYTHONPATH=backend .venv/bin/python scripts/test_postgres.py .venv/bin/pytest --junitxml=evidence/stage8-offline-data-postgres.xml
.venv/bin/ruff check backend pi-agent tests scripts/production.py
```

The source release includes the JSON; the backend Dockerfile's `COPY . .` includes
the package in its build context. Actual image build and DevTools offline display
remain NOT_RUN/BLOCKED. No network Provider, real sensor or pump evidence was added.
