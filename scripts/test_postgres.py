"""Run tests against a private, disposable PostgreSQL cluster without system installation."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    import psycopg
    from sqlalchemy.engine import URL

    source = Path(".runtime/pg/usr")
    if not source.exists():
        raise SystemExit("Extract PostgreSQL server/client/libpq packages into .runtime/pg first")
    root = Path(tempfile.mkdtemp(prefix="flower-pg-test-"))
    uid, gid = (65534, 65534) if os.geteuid() == 0 else (os.getuid(), os.getgid())
    shutil.copytree(source, root / "usr", symlinks=True)
    for directory in [root, root / "data", root / "socket"]:
        directory.mkdir(exist_ok=True)
        os.chown(directory, uid, gid)
        directory.chmod(0o700)
    env = os.environ | {"LD_LIBRARY_PATH": str(root / "usr/lib/x86_64-linux-gnu")}
    binary = root / "usr/lib/postgresql/17/bin"

    def demote():
        if os.geteuid() == 0:
            os.setgroups([])
            os.setgid(gid)
            os.setuid(uid)

    def pg(*args):
        return subprocess.run(
            [str(binary / args[0]), *args[1:]],
            env=env,
            cwd=root,
            preexec_fn=demote,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

    started = False
    try:
        pg(
            "initdb",
            "-D",
            str(root / "data"),
            "-U",
            "flower_test",
            "--auth=trust",
            "--no-locale",
            "--encoding=UTF8",
        )
        pg(
            "pg_ctl",
            "-D",
            str(root / "data"),
            "-l",
            str(root / "postgres.log"),
            "-o",
            f"-h '' -k {root / 'socket'} -c shared_buffers=32MB -c max_connections=30",
            "-w",
            "start",
        )
        started = True
        with psycopg.connect(
            user="flower_test", host=str(root / "socket"), dbname="postgres", autocommit=True
        ) as conn:
            conn.execute("CREATE DATABASE flower_test")
        url = URL.create(
            "postgresql+psycopg",
            username="flower_test",
            database="flower_test",
            query={"host": str(root / "socket")},
        ).render_as_string(hide_password=False)
        command = sys.argv[1:] or [".venv/bin/pytest"]
        result = subprocess.run(command, env=os.environ | {"TEST_DATABASE_URL": url})
        return result.returncode
    except subprocess.CalledProcessError as exc:
        print(exc.stdout)
        raise
    finally:
        if started:
            pg("pg_ctl", "-D", str(root / "data"), "-m", "fast", "-w", "stop")
        shutil.rmtree(root)


if __name__ == "__main__":
    raise SystemExit(main())
