from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def make_engine(url):
    options = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False, "timeout": 30}
    else:
        options.update(pool_size=5, max_overflow=2,
                       connect_args={"connect_timeout": 3})
    return create_engine(url, **options)


def sessions(engine):
    return sessionmaker(engine, expire_on_commit=False)


def migration_config():
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    return config


def ready(engine):
    expected = set(ScriptDirectory.from_config(migration_config()).get_heads())
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
        actual = set(conn.execute(text("SELECT version_num FROM alembic_version")).scalars())
        if actual != expected:
            return False
        from flower import models  # Register the full local schema before inspection.
        inspector = inspect(conn)
        for table in models.Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                return False
            required = {index.name for index in table.indexes}
            present = {index["name"] for index in inspector.get_indexes(table.name)}
            if not required <= present:
                return False
        return True
