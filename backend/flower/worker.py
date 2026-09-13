import argparse
from datetime import timedelta
import os
import subprocess
import sys
import time
from uuid import uuid4

from pathlib import Path
from sqlalchemy import select, func

from flower.config import Settings
from flower.db import make_engine, ready, sessions as make_sessions
from flower.models import Job, PlantImage, WorkerHeartbeat, Plant, CareProfile, Memory, utcnow
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
        from flower.services.retention import aggregate, cleanup

        with self.sessions.begin() as db:
            job = owned_job(db, claim["id"], claim["locked_by"], claim["attempt"])
            if job is None:
                return False
            if job.job_type in {"trend_aggregation", "cleanup"}:
                result = (
                    aggregate(db, utcnow())
                    if job.job_type == "trend_aggregation"
                    else cleanup(db, self.settings, utcnow())
                )
                if not complete_job(db, job.id, claim["locked_by"], claim["attempt"], result):
                    db.rollback()
                    return False
                return True
        with self.sessions() as db:
            job = db.get(Job, claim["id"])
            if job.job_type == "plant_recognition":
                image = db.get(PlantImage, job.target_id)
                if not image:
                    raise ValueError("IMAGE_NOT_FOUND")
                content = image_path(self.settings, image.file_path).read_bytes()
                kind = job.job_type
            elif job.job_type == "care_research":
                from flower.schemas import serialize

                plant = db.get(Plant, job.target_id)
                if not plant or not plant.recognition_confirmed:
                    raise ValueError("SPECIES_UNCONFIRMED")
                content = serialize(plant)
                kind = job.job_type
            elif job.job_type == "weather_refresh":
                from flower.services.weather import weather_context

                content = weather_context(db, db.get(CareProfile, job.target_id), utcnow())
                kind = job.job_type
            elif job.job_type == "memory_structure":
                memory = db.get(Memory, job.target_id)
                content = memory.original_experience
                kind = job.job_type
            elif job.job_type == "alert_notification":
                from flower.models import Alert
                from flower.schemas import serialize

                content = serialize(db.get(Alert, job.target_id)) | {
                    "idempotency_key": job.idempotency_key
                }
                kind = job.job_type
            else:
                raise ValueError("UNSUPPORTED_JOB")
        if kind == "plant_recognition":
            result = self.providers.recognize(content)
        elif kind == "care_research":
            from flower.services.care import research

            result = research(self.providers, content)
        elif kind == "weather_refresh":
            from flower.services.weather import current_weather
            from flower.errors import DomainError

            weather = current_weather(
                self.providers.weather(content), utcnow(), content["source_type"]
            )
            if weather is None:
                raise DomainError("WEATHER_UNAVAILABLE")
            result = weather.model_dump(mode="json")
        elif kind == "alert_notification":
            from flower.schemas import StrictModel, SourceType
            from typing import Literal

            class NotificationResult(StrictModel):
                status: Literal["sent", "mock"]
                source_type: SourceType

            result = NotificationResult.model_validate(self.providers.notify(content)).model_dump(
                mode="json"
            )
        else:
            result = self.providers.structure_memory(content)
        with self.sessions.begin() as db:
            job = owned_job(db, claim["id"], claim["locked_by"], claim["attempt"])
            if job is None:
                return False
            if job.locked_at + timedelta(seconds=job.timeout_sec) <= utcnow():
                return False
            if kind == "plant_recognition":
                image = db.get(PlantImage, job.target_id)
                image.recognition_result = result
            elif kind == "weather_refresh":
                from flower.services.weather import weather_context, current_weather

                profile = db.scalar(
                    select(CareProfile).where(CareProfile.id == job.target_id).with_for_update()
                )
                if weather_context(db, profile, utcnow()) != content:
                    raise ValueError("WEATHER_CONTEXT_CHANGED")
                if current_weather(result, utcnow(), content["source_type"]) is None:
                    raise ValueError("WEATHER_EXPIRED")
                profile.profile = profile.profile | {"weather": result}
            elif kind == "care_research":
                plant = db.scalar(select(Plant).where(Plant.id == job.target_id).with_for_update())
                if (
                    not plant.recognition_confirmed
                    or plant.scientific_name != content["scientific_name"]
                ):
                    raise ValueError("SPECIES_CHANGED")
                version = (
                    db.scalar(
                        select(func.max(CareProfile.version)).where(
                            CareProfile.plant_id == plant.id
                        )
                    )
                    or 0
                ) + 1
                profile = CareProfile(
                    plant_id=plant.id,
                    version=version,
                    profile=result,
                    valid_until=utcnow() + timedelta(days=30),
                    needs_review=result["needs_review"],
                    source_conflict={"conflict": result["source_conflict"]},
                )
                db.add(profile)
                db.flush()
                result = {"profile_id": profile.id, "source_type": result["source_type"]}
            elif kind == "alert_notification":
                from flower.models import Alert

                item = db.get(Alert, job.target_id)
                if result["status"] == "sent" and result["source_type"] == "real":
                    item.pushed_at = utcnow()
            else:
                memory = db.get(Memory, job.target_id)
                if memory.original_experience != content:
                    raise ValueError("MEMORY_CHANGED")
                previous_plant_id = memory.plant_id if memory.rule_enabled else None
                memory.structured_rule = result
                memory.rule_confirmed, memory.rule_enabled = False, False
                from flower.services.care import refresh_fallback_for_plant

                refresh_fallback_for_plant(db, self.settings, previous_plant_id)
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
        from flower.services.retention import schedule
        from flower.services.weather import schedule_weather

        with sessions.begin() as db:
            schedule(db, utcnow())
            schedule_weather(db, utcnow())
        worker.run_once(isolated=True)
        from flower.services.care import evaluate_plant

        with sessions.begin() as db:
            for plant in db.scalars(select(Plant).where(Plant.auto_mode.is_(True))):
                evaluate_plant(db, settings, plant)
        if args.once:
            return
        time.sleep(1)


if __name__ == "__main__":
    main()
