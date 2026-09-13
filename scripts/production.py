"""Explicitly authorized Flower release/rollback actions. No host reconfiguration."""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess


def activate_services(run, action):
    start = ("up", "-d", "--no-build", "--pull", "never", "--wait", "--wait-timeout", "120")
    run(*start, "postgres")
    if action == "deploy":
        run("run", "--rm", "--no-deps", "api", "alembic", "upgrade", "head")
    run(*start, "api", "worker", "proxy")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["deploy", "rollback"])
    parser.add_argument("release", type=Path)
    args = parser.parse_args()
    if os.environ.get("FLOWER_PRODUCTION_AUTHORIZED") != "1":
        raise SystemExit("Production window authorization required; no changes made")
    release = args.release.resolve()
    if release.parent != Path("/srv/flower/releases"):
        raise SystemExit("Expected /srv/flower/releases/<commit>")
    spec = importlib.util.spec_from_file_location(
        "release_tools", Path(__file__).with_name("release.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manifest = json.loads((release / "release.json").read_text())
    module.validate_manifest(manifest)
    if release.name != manifest["commit"]:
        raise SystemExit("Release directory does not match commit")
    import hashlib

    for name, expected in manifest["files"].items():
        file = (release / name).resolve()
        if (
            not file.is_relative_to(release)
            or hashlib.sha256(file.read_bytes()).hexdigest() != expected
        ):
            raise SystemExit("Release file checksum mismatch")
    for image in manifest["images"].values():
        actual = json.loads(subprocess.check_output(["docker", "image", "inspect", image["tag"]]))[
            0
        ]["Id"]
        if actual != image["id"]:
            raise SystemExit("Image ID changed; restore the recorded image archive")
    compose = [
        "docker",
        "compose",
        "--project-name",
        "flower-prod",
        "--env-file",
        "/srv/flower/shared/config/production.env",
        "--env-file",
        str(release / "release.env"),
        "-f",
        str(release / "docker-compose.yml"),
        "-f",
        str(release / "compose.production.yml"),
    ]

    def run(*arguments):
        subprocess.run(compose + list(arguments), check=True)

    run("config", "--quiet")
    # Backups and shared-host preflight are required artifacts of the change window.
    proof_path = Path("/srv/flower/shared/config/verified-backup.json")
    if not proof_path.is_file():
        raise SystemExit("Record and verify the pre-release backup first")
    from datetime import datetime, timezone, timedelta
    from backup import verify

    proof = json.loads(proof_path.read_text())
    backup_directory = Path(proof["backup_directory"]).resolve()
    verified_at = datetime.fromisoformat(proof["restored_at"])
    if (
        backup_directory.parent != Path("/srv/flower/shared/backups")
        or proof.get("restore_status") != "PASS"
        or not datetime.now(timezone.utc) - timedelta(days=1)
        < verified_at
        <= datetime.now(timezone.utc)
    ):
        raise SystemExit("A recent independent restore proof is required")
    verify(backup_directory)
    activate_services(run, args.action)
    import urllib.request
    import time

    for attempt in range(30):
        try:
            with urllib.request.urlopen("http://127.0.0.1:18080/ready", timeout=3) as response:
                if response.status == 200:
                    break
        except OSError:
            pass
        time.sleep(2)
    else:
        raise SystemExit("Release readiness failed; current link preserved")
    temporary = Path("/srv/flower/.current-next")
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(release)
    temporary.replace("/srv/flower/current")


if __name__ == "__main__":
    main()
