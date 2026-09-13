"""Flower-only backup archives and restoration into a fresh test database."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
from uuid import uuid4

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url


def connection(url):
    return {
        k: v
        for k, v in dict(
            user=url.username,
            password=url.password,
            host=url.query.get("host", url.host),
            port=url.port,
            dbname=url.database,
        ).items()
        if v is not None
    }


def pg(url, command, *arguments):
    values = connection(url)
    env = os.environ.copy()
    for key, value in values.items():
        env[
            {
                "user": "PGUSER",
                "password": "PGPASSWORD",
                "host": "PGHOST",
                "port": "PGPORT",
                "dbname": "PGDATABASE",
            }[key]
        ] = str(value)
    binary = str(Path(os.environ.get("FLOWER_PG_BIN", "/usr/bin")) / command)
    subprocess.run([binary, *map(str, arguments)], env=env, check=True, capture_output=True)


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def create(url, uploads, manifest, destination):
    uploads, manifest, destination = map(Path, (uploads, manifest, destination))
    if not uploads.is_dir() or not manifest.is_file():
        raise ValueError("uploads and release manifest are required")
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    identifier = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    temporary = destination / (".partial-" + identifier)
    temporary.mkdir(mode=0o700)
    try:
        pg(url, "pg_dump", "--format=custom", "--no-owner", "--file", temporary / "database.dump")
        with tarfile.open(temporary / "uploads.tar.gz", "w:gz") as archive:
            for path in sorted(uploads.rglob("*")):
                if path.is_symlink():
                    raise ValueError("uploads cannot contain symlinks")
                if path.is_file():
                    archive.add(path, arcname=path.relative_to(uploads).as_posix(), recursive=False)
        shutil.copyfile(manifest, temporary / "release.json")
        (temporary / "metadata.json").write_text(
            json.dumps(
                {"created_at": datetime.now(timezone.utc).isoformat(), "spec_version": "2.2.2"}
            )
        )
        (temporary / "checksums.json").write_text(
            json.dumps(
                {p.name: digest(p) for p in temporary.iterdir() if p.is_file()}, sort_keys=True
            )
        )
        verify(temporary)
        final = destination / identifier
        temporary.rename(final)
        return final
    except BaseException:
        shutil.rmtree(temporary)
        raise


def verify(directory):
    directory = Path(directory)
    checksums = json.loads((directory / "checksums.json").read_text())
    for name, checksum in checksums.items():
        path = directory / name
        if (
            Path(name).name != name
            or not path.is_file()
            or path.is_symlink()
            or digest(path) != checksum
        ):
            raise ValueError("backup checksum mismatch")
    if set(checksums) != {"database.dump", "uploads.tar.gz", "release.json", "metadata.json"}:
        raise ValueError("backup checksum manifest incomplete")


def restore(url, directory, target_database, target_uploads):
    directory, target_uploads = Path(directory), Path(target_uploads)
    verify(directory)
    if not re.fullmatch(r"flower_restore_[a-z0-9_]{1,40}", target_database):
        raise ValueError("restore requires a fresh flower_restore_ database")
    if target_uploads.exists():
        raise ValueError("restore requires a fresh uploads directory")
    with tarfile.open(directory / "uploads.tar.gz") as archive:
        for member in archive.getmembers():
            if (
                not member.isfile()
                or Path(member.name).is_absolute()
                or ".." in Path(member.name).parts
            ):
                raise ValueError("unsafe archive member")
    with psycopg.connect(**connection(url), autocommit=True) as conn:
        if conn.execute(
            "SELECT 1 FROM pg_database WHERE datname=%s", (target_database,)
        ).fetchone():
            raise ValueError("restore requires a fresh database")
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target_database)))
    # Never drop or overwrite an existing DB, including after a failed restore.
    pg(
        url.set(database=target_database),
        "pg_restore",
        "--exit-on-error",
        "--no-owner",
        "--no-privileges",
        "--dbname",
        target_database,
        directory / "database.dump",
    )
    target_uploads.mkdir(parents=True, mode=0o700)
    with tarfile.open(directory / "uploads.tar.gz") as archive:
        archive.extractall(target_uploads, filter="data")
    return target_database


def retention(destination):
    candidates = []
    for path in Path(destination).iterdir():
        if (
            path.is_dir()
            and not path.is_symlink()
            and not path.name.startswith(".")
            and (path / "metadata.json").is_file()
        ):
            created = datetime.fromisoformat(
                json.loads((path / "metadata.json").read_text())["created_at"]
            )
            candidates.append((created, path))
    candidates.sort(reverse=True)
    days, weeks, kept = set(), set(), set()
    for created, path in candidates:
        day, week = created.date(), created.isocalendar()[:2]
        daily = day not in days and len(days) < 7
        weekly = week not in weeks and len(weeks) < 4
        if daily or weekly:
            kept.add(path)
        days.add(day)
        weeks.add(week)
    for _, path in candidates:
        if path not in kept:
            shutil.rmtree(path)
    return kept


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["backup", "restore", "verify", "retention"])
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--uploads", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--target-database")
    args = parser.parse_args()
    if args.action == "verify":
        verify(args.directory)
    elif args.action == "retention":
        retention(args.directory)
    else:
        url = make_url(os.environ["DATABASE_URL"])
        if not url.drivername.startswith("postgresql"):
            raise ValueError("PostgreSQL required")
        if args.action == "backup":
            print(create(url, args.uploads, args.manifest, args.directory))
            retention(args.directory)
        else:
            print(restore(url, args.directory, args.target_database, args.uploads))


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError:
        raise SystemExit(
            "PostgreSQL backup/restore command failed; credentials and server output suppressed"
        ) from None
