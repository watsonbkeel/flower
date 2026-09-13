# Stage 0 / v2.2.2

Source: TEST. Production deployment: NOT_RUN.

- Baseline SHA-256 matches SPEC_CURRENT.md; seven skills and eight preserved audit reports.
- Clean independent repository at 08534ae; development branch feat/flower-v2.2.2.
- Red/green commands: `.venv/bin/pytest tests/test_foundation.py --junitxml=evidence/stage0-{red,green}.xml` (run separately).
- Readiness was tested against an empty SQLite DB and an explicitly migrated DB; migration is repeatable.
- Compose checked structurally using PyYAML. Docker runtime was not installed or invoked.
- Preflight is prepared but not run; the existing server audit remains the factual baseline.
- No tool mutation targeted /root/aibot, /opt/asist-embodiment, /srv/flower or host networking/services.
- Full PostgreSQL constraints and independent Worker implementation follow in Stages 2/3.
