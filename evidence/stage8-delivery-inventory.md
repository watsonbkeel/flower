# Frozen deliverable inventory

Checked against frozen specification section 21.2. The table records source-file
delivery and relevant verification, not a production or physical PASS. The 25
Definition of Done rows and named acceptance gates remain separately recorded in
`FINAL_IMPLEMENTATION_REPORT.md`; its overall state remains HARD_BLOCKED.

| Item | Delivered source | Verification / remaining boundary |
| --- | --- | --- |
| 1 Backend/API/Worker/PG | backend/flower, backend/Dockerfile | 222-test isolated PG regression; production not deployed |
| 2 Pi service | pi-agent/flower_pi | Mock safety/executor/adapter tests; physical install blocked |
| 3 Miniapp | miniapp/app.json, miniapp/pages | 13 Node tests and browser evidence; native platform blocked |
| 4 Compose | docker-compose.yml, compose.production.yml, compose.development.yml | Static tests; Docker config/runtime not run |
| 5 Alembic | backend/migrations, backend/alembic.ini | Real isolated PG migration/constraint tests |
| 6 Environment examples | .env.example, pi-agent/.env.example | Configuration validation tests; real credentials absent |
| 7 Cloud scripts | scripts/deploy.sh, backup.sh, restore.sh, cleanup.sh | Shell syntax; simulated deployment; real isolated backup/restore |
| 8 Pi scripts/systemd | pi-agent/install.sh, calibrate.sh, ble_probe.sh, diagnose.sh, smart-guardian.service | Syntax and adapter tests; no physical execution |
| 9 Automated tests | tests, backend/tests, pi-agent/tests, miniapp/tests | Latest PG XML and Node TAP in report |
| 10 README | README.md, pi-agent/README.md, miniapp/README.md | Commands reviewed; clean production deployment not run |
| 11 API documentation | docs/API_AND_DATA_CONTRACTS.md, generated FastAPI schema | API contract tests; no production endpoint claim |
| 12 Wiring/anti-siphon | docs/HARDWARE_WIRING.md | Documentation only; real measurements blocked |
| 13 Offline data | backend/flower/data/offline_demo.json, miniapp/assets/plant.jpg, docs/OFFLINE_DEMO.md | Package/Mock integration tests; real DevTools demonstration blocked |
| 14 Acceptance report | FINAL_IMPLEMENTATION_REPORT.md, docs/ACCEPTANCE_MATRIX.md, evidence/ | Explicit PASS/NOT_RUN/BLOCKED scope and evidence |
| 15 Frozen spec/archive | SPEC_CURRENT.md, docs/specs, docs/archive | SHA-256 test; archive is not implementation input |
| 16 Goal/instructions/skills | AGENTS.md, GOAL.md, PROMPT_ONE_GOAL.md, .agents/skills | Baseline tests verify seven skills and eight audit reports |
| 17 Status/blockers/report | STATUS.md, BLOCKERS.md, FINAL_IMPLEMENTATION_REPORT.md | Updated; production and physical gaps remain open |

This review found and repaired two delivery gaps: the deploy.sh entrypoint and
the standalone offline data package. It also corrected startup sequencing so
health checks precede migration and release completion. See the corresponding
stage8-deployment-sequence and stage8-offline-data evidence.

Syntax-only checks passed for all cloud/Pi entry scripts and the production
backup wrapper. No script that installs services, changes host networking,
deploys production or moves physical water was executed during this inventory.
