from alembic import context
from sqlalchemy import text

from flower.config import Settings
from flower.db import make_engine
from flower.models import Base

config = context.config
url = config.attributes.get("database_url") or Settings().database_url
if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with make_engine(url).connect() as connection:
        if connection.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_lock(222001)"))
            connection.commit()
        try:
            context.configure(connection=connection, target_metadata=Base.metadata)
            with context.begin_transaction():
                context.run_migrations()
        finally:
            if connection.dialect.name == "postgresql":
                connection.execute(text("SELECT pg_advisory_unlock(222001)"))
                connection.commit()
