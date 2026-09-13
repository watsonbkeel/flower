"""Explicit development/production maintenance job entrypoint."""

import json

from flower.config import Settings
from flower.db import make_engine, sessions, ready
from flower.models import utcnow
from flower.services.retention import aggregate, cleanup


def main():
    settings = Settings()
    engine = make_engine(settings.database_url)
    if not ready(engine):
        raise SystemExit("Run explicit migration first")
    with sessions(engine).begin() as db:
        print(
            json.dumps(
                {"aggregation": aggregate(db, utcnow()), "cleanup": cleanup(db, settings, utcnow())}
            )
        )
    engine.dispose()


if __name__ == "__main__":
    main()
