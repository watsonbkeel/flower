from datetime import timedelta

from sqlalchemy import select, update

from flower.models import Job, utcnow
from flower.schemas import serialize


def enqueue_job(db, job_type, target_type, target_id, user_id, key):
    previous = db.scalar(select(Job).where(Job.idempotency_key == key))
    if previous:
        return previous
    job = Job(
        job_type=job_type,
        target_type=target_type,
        target_id=target_id,
        user_id=user_id,
        idempotency_key=key,
    )
    db.add(job)
    db.flush()
    return job


def claim_job(db, owner, now):
    candidate = (
        select(Job.id)
        .where(Job.status == "queued", Job.available_at <= now)
        .order_by(Job.created_at)
        .limit(1)
    )
    if db.bind.dialect.name == "postgresql":
        candidate = candidate.with_for_update(skip_locked=True)
    jid = db.scalar(candidate)
    if not jid:
        return None
    job = db.scalar(
        update(Job)
        .where(Job.id == jid, Job.status == "queued")
        .values(
            status="running",
            progress_stage="running",
            locked_by=owner,
            locked_at=now,
            started_at=now,
            attempt=Job.attempt + 1,
        )
        .returning(Job)
    )
    return serialize(job) if job else None


def recover_jobs(db, now):
    for job in db.scalars(
        select(Job).where(Job.status == "running").with_for_update(skip_locked=True)
    ):
        if job.locked_at + timedelta(seconds=job.timeout_sec) <= now:
            fail_job(db, job.id, job.locked_by, job.attempt, "WORKER_LEASE_EXPIRED", now)


def owned_job(db, jid, owner, attempt):
    return db.scalar(
        select(Job)
        .where(
            Job.id == jid, Job.status == "running", Job.locked_by == owner, Job.attempt == attempt
        )
        .with_for_update()
    )


def complete_job(db, jid, owner, attempt, result):
    job = owned_job(db, jid, owner, attempt)
    if job is None or job.locked_at + timedelta(seconds=job.timeout_sec) <= utcnow():
        return False
    job.status, job.progress_stage, job.result = "succeeded", "succeeded", result
    job.finished_at = utcnow()
    return True


def fail_job(db, jid, owner, attempt, code, now=None):
    job = owned_job(db, jid, owner, attempt)
    if not job:
        return False
    now = now or utcnow()
    job.status = "failed" if job.attempt >= 3 else "queued"
    job.progress_stage = job.status
    job.error_message = code
    job.available_at = now + timedelta(seconds=2**job.attempt)
    job.locked_by, job.locked_at = None, None
    if job.status == "failed":
        job.finished_at = now
    return True
