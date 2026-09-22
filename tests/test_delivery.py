import importlib.util
import json
import os

import pytest
from sqlalchemy.engine import make_url


def module():
    spec = importlib.util.spec_from_file_location("flower_backup", "scripts/backup.py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_restore_rejects_modified_archive_before_touching_database(tmp_path):
    backup = module()
    directory = tmp_path / "backup"
    directory.mkdir()
    (directory / "checksums.json").write_text(json.dumps({"database.dump": "wrong"}))
    (directory / "database.dump").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="checksum"):
        backup.verify(directory)


def test_actual_postgres_dump_and_independent_restore(tmp_path):
    backup = module()
    if not os.environ.get("TEST_DATABASE_URL", "").startswith("postgresql"):
        pytest.skip("Requires disposable PostgreSQL test runner")
    import psycopg

    url = make_url(os.environ["TEST_DATABASE_URL"])
    from alembic import command
    from flower.db import migration_config

    migration = migration_config()
    migration.attributes["database_url"] = os.environ["TEST_DATABASE_URL"]
    command.upgrade(migration, "head")
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "photo.jpg").write_bytes(b"known upload bytes")
    manifest = tmp_path / "release.json"
    manifest.write_text(json.dumps({"spec_version": "2.2.2", "commit": "a" * 40}))
    with psycopg.connect(**backup.connection(url), autocommit=True) as conn:
        conn.execute("CREATE TABLE backup_sentinel (value text)")
        conn.execute("INSERT INTO backup_sentinel VALUES ('flower isolated restore')")
    artifact = backup.create(url, uploads, manifest, tmp_path / "backups")
    restored = tmp_path / "restored"
    target = "flower_restore_acceptance"
    backup.restore(url, artifact, target, restored)
    with psycopg.connect(**(backup.connection(url) | {"dbname": target})) as conn:
        assert (
            conn.execute("SELECT value FROM backup_sentinel").fetchone()[0]
            == "flower isolated restore"
        )
        assert (
            conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
            == "0003_retention"
        )
        assert (
            conn.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public'").fetchone()[0]
            >= 18
        )
    assert (restored / "photo.jpg").read_bytes() == b"known upload bytes"
    with pytest.raises(ValueError, match="fresh"):
        backup.restore(url, artifact, target, tmp_path / "other")


def test_backup_retention_keeps_seven_daily_and_four_weekly(tmp_path):
    from datetime import datetime, timedelta, timezone

    backup = module()
    now = datetime(2026, 9, 13, tzinfo=timezone.utc)
    for age in range(40):
        path = tmp_path / f"b-{age:02}"
        path.mkdir()
        (path / "metadata.json").write_text(
            json.dumps({"created_at": (now - timedelta(days=age)).isoformat()})
        )
    kept = backup.retention(tmp_path)
    assert len(kept) >= 7
    assert len(kept) <= 11
    assert all((tmp_path / f"b-{i:02}").exists() for i in range(7))


def test_release_requires_full_commit_and_immutable_images():
    spec = importlib.util.spec_from_file_location("flower_release", "scripts/release.py")
    release = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(release)
    with pytest.raises(ValueError):
        release.validate_manifest({"commit": "latest"})
    with pytest.raises(ValueError):
        release.validate_manifest(
            {"commit": "a" * 40, "images": {"app": {"tag": "flower-app:latest"}}}
        )


def test_release_ignores_untracked_local_instructions_but_rejects_tracked_edits(tmp_path):
    import subprocess

    spec = importlib.util.spec_from_file_location("flower_release", "scripts/release.py")
    release = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(release)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    tracked = tmp_path / "tracked"
    tracked.write_text("committed")
    subprocess.run(["git", "-C", str(tmp_path), "add", "tracked"], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "initial"],
        check=True,
    )
    (tmp_path / "LOCAL_INSTRUCTIONS.md").write_text("keep private")
    assert release.has_tracked_changes(tmp_path) is False
    tracked.write_text("modified")
    assert release.has_tracked_changes(tmp_path) is True
