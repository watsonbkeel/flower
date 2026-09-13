# Stage 2 Device Chain / v2.2.2

Source: TEST PostgreSQL 17.11 + MOCK Pi. Real telemetry: BLOCKED_PHYSICAL.

Command:
`PYTHONPATH=backend .venv/bin/python scripts/test_postgres.py .venv/bin/pytest --junitxml=evidence/stage2-postgres.xml`

Result: 86 passed. The runner extracts no system packages, creates a disposable cluster,
uses a private Unix socket with TCP disabled, then stops and deletes that cluster.
PostgreSQL server/client/libpq Debian packages were downloaded and extracted below
`.runtime/`; no apt installation, Docker, systemd or network configuration occurred.

The initial red run failed importing missing User/auth/domain modules before conftest
could initialize; pytest exited 4 and did not generate XML. Subsequent red regression
evidence is preserved in stage2-quota-red.xml and stage2-receipt-red.xml.

Verified: 100 concurrent claims yield one winner; actual PostgreSQL unique indexes reject
second primary plants and second active dispense commands; pending/claimed/executing
timeouts differ; progress does not extend deadline; UTC is normalized; token scope is
enforced; telemetry is idempotent and old uploads cannot replace newer status; source
labels are checked against provisioned device identity; positive successful settlement
requires matching pulse totals. Full-schema migration from empty DB runs explicitly.

Pi CloudClient refresh and command decode use MockTransport/API contract tests. Pi
runtime, camera capture, installation and systemd are implemented but not physically run.
The conservative quota merge was corrected so repeated lower cloud values cannot renew
an old high value forever. Unverified partial execution retains reserved quota.

Real hardware, production HTTPS/Compose, service coexistence and release deployment remain
NOT_RUN/BLOCKED. No server-audit report was edited.
