# Stage 8 memory-policy lifecycle audit

Requirements: v2.2.2 sections 6.5 (confirmed memory rules and enable/disable state), 6.3/10.6 (versioned conservative fallback), 3.3 (uncertainty means no watering).

Editing, detaching or restructuring a confirmed enabled memory previously cleared its rule in the database but left its effects in the active fallback policy. Policy issuance could also outlive the associated care profile or issue from an already expired profile.

- `stage8-memory-policy-red.xml`: all five targeted tests failed before implementation.
- `stage8-memory-policy-postgres.xml`: complete regression, 178 passes with one visible upstream Starlette/httpx warning.
- Tests cover editing an enabled memory, removing its plant association, restructuring it in the Worker, a care profile with 30 minutes of remaining validity, and disabling a rule after care expiry.
- Removing a confirmed rule now recompiles the original plant policy from currently confirmed rules. Missing/expired care revokes policy instead of issuing one. Newly issued versions invalidate prior server versions.
- Both hashed policy content and database validity use the earlier of the care expiry and seven days. The original profile still requires explicit confirmation.
- Ruff and artifact verification passed. PostgreSQL ran as an isolated temporary Unix-socket cluster. All Provider/actuator scenarios remain Mock; no production or physical watering was performed.
- The development stack was restarted with these fixes (supervisor PID 1600614). `/ready` returned HTTP 200 and Worker heartbeat age was verified below 120 seconds. URL: `http://127.0.0.1:18082/preview/`.

Reproduce: `PYTHONPATH=backend .venv/bin/python scripts/test_postgres.py .venv/bin/pytest --junitxml=evidence/stage8-memory-policy-postgres.xml`.

An offline Pi cannot receive cloud-side revocation until its next synchronization; this change does not claim instantaneous offline delivery. Existing hardware, Provider and production blockers remain open.
