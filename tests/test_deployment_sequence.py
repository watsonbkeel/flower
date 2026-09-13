import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest


def production():
    spec = importlib.util.spec_from_file_location("flower_production", "scripts/production.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_deploy_shell_entrypoint_requires_authorization_before_release_access(tmp_path):
    environment = os.environ.copy()
    environment.pop("FLOWER_PRODUCTION_AUTHORIZED", None)
    environment["PATH"] = str(Path(sys.executable).parent) + os.pathsep + environment["PATH"]
    result = subprocess.run(
        ["sh", str(Path("scripts/deploy.sh").resolve()), str(tmp_path / "not-a-release")],
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Production window authorization required; no changes made" in result.stderr
    assert not (tmp_path / "not-a-release").exists()


@pytest.mark.parametrize("action", ["deploy", "rollback"])
def test_service_activation_waits_for_database_and_worker_without_building(action):
    calls = []
    database_ready = False

    def compose(*args):
        nonlocal database_ready
        calls.append(args)
        assert "--build" not in args
        if args[0] == "up":
            assert "--no-build" in args and args[args.index("--pull") + 1] == "never"
            assert "--wait" in args
            assert args[args.index("--wait-timeout") + 1] == "120"
        if args[-1] == "postgres":
            database_ready = True
        elif args[0] == "run":
            assert database_ready, "Migration ran before database health was established"
            assert args == ("run", "--rm", "--no-deps", "api", "alembic", "upgrade", "head")
        else:
            assert database_ready
            assert args[-3:] == ("api", "worker", "proxy")

    production().activate_services(compose, action)
    assert len(calls) == (3 if action == "deploy" else 2)
    assert any(args[0] == "run" for args in calls) == (action == "deploy")


def test_database_health_failure_prevents_migration_and_application_start():
    calls = []

    def unhealthy(*args):
        calls.append(args)
        if "--wait" in args:
            raise subprocess.CalledProcessError(1, ["mock-compose", *args])

    with pytest.raises(subprocess.CalledProcessError):
        production().activate_services(unhealthy, "deploy")
    assert len(calls) == 1
    assert calls[0][-1] == "postgres"


def test_worker_health_failure_is_not_reported_as_success():
    def unhealthy_worker(*args):
        if args[-3:] == ("api", "worker", "proxy") and "--wait" in args:
            raise subprocess.CalledProcessError(1, ["mock-compose", *args])

    with pytest.raises(subprocess.CalledProcessError):
        production().activate_services(unhealthy_worker, "deploy")
