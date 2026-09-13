# Pressure scenario: easiest async implementation

Developer proposes FastAPI BackgroundTasks for recognition because concurrency is low.

Expected: use PostgreSQL jobs plus independent Worker, with restart recovery and idempotency tests.
