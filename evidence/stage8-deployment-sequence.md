# Stage 8 deployment sequence review

Frozen deliverable 21.2.7 requires deploy.sh alongside backup/restore/cleanup.
`scripts/deploy.sh` now invokes the existing authorized production entrypoint.
Without the authorization environment marker it fails before release-file access.

The former sequence invoked `up -d postgres` and immediately ran migration with
`--no-deps`, which could race database startup. It also did not wait for Worker
health before its later API probe and current-link update.

The shared deploy/rollback activation sequence now uses
`up --no-build --pull never --wait --wait-timeout 120`. Deploy runs explicit
migration only after PG health; rollback performs no migration. Application
startup waits for the Compose health checks of both API and Worker.

Five new tests failed against the old startup sequence and missing shell entrypoint
(`stage8-deployment-sequence-red.xml`). Tests simulate Compose readiness/failure,
check that database failure prevents migration, propagate Worker health failure,
and execute the real shell wrapper with authorization absent and a temporary
nonexistent release path. No Docker executable was invoked and no production
directory was accessed or modified by these tests.

```sh
PYTHONPATH=backend .venv/bin/python scripts/test_postgres.py .venv/bin/pytest --junitxml=evidence/stage8-deployment-sequence-postgres.xml
.venv/bin/ruff check backend pi-agent tests scripts/production.py
sh -n scripts/deploy.sh
```

All 220 tests passed against isolated PostgreSQL, with the existing visible
Starlette/httpx warning. These results verify Python orchestration and authorization,
not Docker runtime behavior, image health, production migration or rollback.
Those acceptance gates remain blocked pending the authorized deployment window.
