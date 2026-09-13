import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from flower.config import Settings
from flower.main import create_app
from flower.db import migration_config
from alembic import command


def test_frozen_baseline():
    spec = next(Path("docs/specs").glob("*v2.2.2*"))
    assert hashlib.sha256(spec.read_bytes()).hexdigest() == (
        "4481d48605aec47660d2cdefb7a004ed2169bb8531302ecdf803c3c12718cf95"
    )
    assert len(list(Path(".agents/skills").glob("*/SKILL.md"))) == 7
    assert len(list(Path("docs/server-audit").glob("*.md"))) == 8


@pytest.mark.parametrize("override", [
    {"dev_mode": True}, {"dev_auth_bypass": True},
    {"app_base_url": "http://flower-api.bkeel.com"},
    {"app_base_url": "https:///missing-host"},
    {"secret_key": ""}, {"secret_key": "change-me"},
    {"database_url": "sqlite:///test.db"}, {"spec_version": "2.2.1"},
])
def test_production_fails_closed(override):
    values = dict(app_env="production", dev_mode=False, dev_auth_bypass=False,
                  app_base_url="https://flower-api.bkeel.com",
                  secret_key="test-only-" + "a" * 40,
                  database_url="postgresql+psycopg://flower:test-only@postgres/flower")
    with pytest.raises(ValueError):
        Settings(**(values | override))


def test_health_does_not_need_database_and_ready_fails_closed(tmp_path):
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path}/empty.db"))
    with TestClient(app) as client:
        assert client.get("/health").json()["spec_version"] == "2.2.2"
        response = client.get("/ready")
        assert response.status_code == 503
        assert "sqlite" not in response.text


def test_explicit_migration_is_repeatable_and_readiness_checks_head(tmp_path):
    url = f"sqlite:///{tmp_path}/migrated.db"
    config = migration_config()
    config.attributes["database_url"] = url
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    with TestClient(create_app(Settings(database_url=url))) as client:
        assert client.get("/ready").status_code == 200


def test_compose_is_private_and_processes_do_not_migrate():
    import yaml
    base = yaml.safe_load(Path("docker-compose.yml").read_text())
    prod = yaml.safe_load(Path("compose.production.yml").read_text())
    assert set(base["services"]) == {"proxy", "api", "worker", "postgres"}
    assert prod["services"]["proxy"]["ports"] == ["127.0.0.1:18080:8080"]
    for name, service in base["services"].items():
        assert "ports" not in service
        assert "container_name" not in service
        assert "network_mode" not in service
        assert not service.get("privileged")
        assert "alembic" not in str(service.get("command", ""))
        if name != "proxy":
            assert "ports" not in prod["services"][name]
    assert base["networks"]["db"]["internal"] is True
