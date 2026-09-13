import argparse
from datetime import timedelta
import os
import subprocess
import sys
import time
from uuid import uuid4

from pathlib import Path

from flower.config import Settings
from flower.db import make_engine, ready, sessions as make_sessions
from flower.models import Job, PlantImage, WorkerHeartbeat, utcnow
from flower.services.jobs import claim_job, recover_jobs, complete_job, fail_job, owned_job
from flower.services.providers import providers
from flower.services.commands import sweep_commands
from flower.services.images import image_path


class Worker:
    def __init__(self, sessions, settings):
        self.sessions, self.settings = sessions, settings
        self.owner = str(uuid4())
        self.providers = providers(settings, sessions)

    def acquire(self):
        with self.sessions.begin() as db:
            now = utcnow()
            recover_jobs(db, now)
            sweep_commands(db, now)
            db.merge(WorkerHeartbeat(id="worker", seen_at=now))
            return claim_job(db, self.owner, now)

    def perform(self, claim):
        with self.sessions() as db:
            job = db.get(Job, claim["id"])
            if job.job_type == "plant_recognition":
                image = db.get(PlantImage, job.target_id)
                if not image:
                    raise ValueError("IMAGE_NOT_FOUND")
                content = image_path(self.settings, image.file_path).read_bytes()
            else:
                raise ValueError("UNSUPPORTED_JOB")
        result = self.providers.recognize(content)
        with self.sessions.begin() as db:
            job = owned_job(db, claim["id"], claim["locked_by"], claim["attempt"])
            if job is None:
                return False
            image = db.get(PlantImage, job.target_id)
            image.recognition_result = result
            return complete_job(db, job.id, claim["locked_by"], claim["attempt"], result)

    def run_once(self, isolated=False):
        claim = self.acquire()
        if not claim:
            return False
        try:
            if isolated:
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "flower.worker",
                        "--job",
                        claim["id"],
                        "--owner",
                        self.owner,
                        "--attempt",
                        str(claim["attempt"]),
                    ],
                    timeout=claim["timeout_sec"],
                    check=True,
                    env=os.environ
                    | {key.upper(): str(value) for key, value in self.settings.model_dump().items()}
                    | {"PYTHONPATH": str(Path(__file__).resolve().parents[1])},
                )
            else:
                self.perform(claim)
        except Exception:
            with self.sessions.begin() as db:
                fail_job(db, claim["id"], self.owner, claim["attempt"], "JOB_FAILED")
        return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--health", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--job")
    parser.add_argument("--owner")
    parser.add_argument("--attempt", type=int)
    args = parser.parse_args()
    settings = Settings()
    engine = make_engine(settings.database_url)
    sessions = make_sessions(engine)
    if not ready(engine):
        raise SystemExit("Database/migration not ready; run explicit migration first")
    if args.health:
        with sessions() as db:
            heartbeat = db.get(WorkerHeartbeat, "worker")
            healthy = heartbeat and heartbeat.seen_at > utcnow() - timedelta(seconds=120)
        raise SystemExit(0 if healthy else 1)
    worker = Worker(sessions, settings)
    if args.job:
        worker.perform({"id": args.job, "locked_by": args.owner, "attempt": args.attempt})
        return
    while True:
        worker.run_once(isolated=True)
        if args.once:
            return
        time.sleep(1)


if __name__ == "__main__":
    main()
