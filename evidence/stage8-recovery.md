# Stage 8 recovery audit

Scope: development-only fixes following commit `7b3277004138f9701d965a5133594166c28acb73`.
All clock faults and Pi sessions below are simulated; no hardware acceptance is claimed.

- `stage8-recovery-audit-red.xml`: 6 expected failures, 2 passes before implementation.
- `stage8-recovery-audit-green.xml`: 14 passes for clock recovery, local reconciliation and adapters.
- `stage8-recovery-postgres.xml`: full regression, 155 passes, one visible upstream Starlette/httpx deprecation warning. PostgreSQL 17.11 ran using unpacked binaries and a private Unix socket; the runner stopped and removed the temporary cluster afterward.
- Clock tests inject forward/backward and repeated wall-clock corrections, failed NTP verification, and a correction during an NTP probe. A correction latches untrusted time for 30 stable seconds and requires a fresh successful NTP probe. Mode recovery still requires 180 healthy seconds after trust returns.
- Reconciliation test retains 101 fallback receipts and verifies that the later remote receipt remains eligible for cloud reconciliation without changing local quota. Filtering occurs before the 100-record SQL limit.
- Ruff passed for backend, Pi and tests. Development `/ready` returned HTTP 200 with `spec_version=2.2.2` at `http://127.0.0.1:18082`.
- Prior Node/browser evidence remains applicable; no miniapp code changed in this repair.
- No Docker installation, production deployment, host network/Nginx/VPN change or aibot modification occurred. B01-B09 remain open.

Reproduce:

```sh
.venv/bin/pytest pi-agent/tests/test_clock_recovery.py pi-agent/tests/test_local_reconciliation.py pi-agent/tests/test_adapters.py --junitxml=evidence/stage8-recovery-audit-green.xml
PYTHONPATH=backend .venv/bin/python scripts/test_postgres.py .venv/bin/pytest --junitxml=evidence/stage8-recovery-postgres.xml
.venv/bin/ruff check backend pi-agent tests
.venv/bin/python scripts/verify_artifacts.py
git diff --check
```
