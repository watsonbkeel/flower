"""Developer-only generation against the disposable test database."""

import os
from alembic import command
from flower.db import migration_config

config = migration_config()
config.attributes["database_url"] = os.environ["TEST_DATABASE_URL"]
command.upgrade(config, "head")
command.revision(
    config,
    message="v2.2.2 domain schema and atomic constraints",
    rev_id="0002_domain",
    autogenerate=True,
)
