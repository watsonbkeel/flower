# Stage 8 species/profile invalidation audit

Requirements: v2.2.2 sections 6.1 (species -> research -> explicit profile confirmation -> policy), 3.3 (uncertain state cannot water), and 18.6 (confirmation before activation).

Changing species previously cleared confirmation but kept old profiles unexpired, allowing an old profile to be reactivated for the new species. Concurrent species and profile confirmation could also leave the old profile confirmed.

- `stage8-species-red.xml`: 2 failures and 1 pass before implementation. The concurrent test observed the old profile remain confirmed after species change.
- `stage8-species-postgres.xml`: complete regression, 173 passes and one visible upstream Starlette/httpx warning.
- Tests cover old-profile rejection, manual/automatic watering rejection before new research, successful fresh research/confirmation, a species change injected during Provider research, and concurrent species/profile confirmation.
- Species confirmation now expires prior profiles and policies. Device then plant locks serialize it with care activation, auto-mode changes and command creation. No pump driver or Pi gate was changed.
- Ruff passed. Tests use Mock Providers and actual isolated PostgreSQL 17.11, with no physical watering or production deployment. Offline Pi cache revocation still requires its next cloud synchronization.

Reproduce: `PYTHONPATH=backend .venv/bin/python scripts/test_postgres.py .venv/bin/pytest --junitxml=evidence/stage8-species-postgres.xml`.
