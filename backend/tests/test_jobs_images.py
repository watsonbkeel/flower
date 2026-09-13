from datetime import timedelta
from io import BytesIO
from uuid import uuid4

from PIL import Image
from sqlalchemy import select

from flower.models import Job, PlantImage, Alert, utcnow
from flower.services.jobs import enqueue_job, claim_job, recover_jobs, complete_job
from flower.worker import Worker


def picture():
    stream = BytesIO()
    Image.new("RGB", (400, 400), (50, 170, 80)).save(stream, format="JPEG")
    return stream.getvalue()


def upload(system, content=None, **data):
    return system["client"].post(
        "/api/v1/device/images",
        headers=system["device_headers"],
        data={"plant_id": system["plant_id"], "image_type": "whole"} | data,
        files={
            "file": ("../untrusted.jpg", picture() if content is None else content, "image/jpeg")
        },
    )


def test_image_upload_authorization_and_recognition_job(system):
    response = upload(system)
    assert response.status_code == 202
    image_id, job_id = response.json()["image_id"], response.json()["job_id"]
    assert system["client"].get(f"/api/v1/images/{image_id}").status_code == 401
    assert (
        system["client"]
        .get(f"/api/v1/images/{image_id}", headers=system["user_headers"])
        .status_code
        == 200
    )
    worker = Worker(system["app"].state.sessions, system["settings"])
    assert worker.run_once(isolated=True)
    result = system["client"].get(f"/api/v1/jobs/{job_id}", headers=system["user_headers"]).json()
    assert result["status"] == "succeeded"
    assert len(result["result"]["candidates"]) == 3
    assert result["result"]["source_type"] == "mock"
    with system["app"].state.sessions() as db:
        path = db.get(PlantImage, image_id).file_path
        assert ".." not in path
        assert not path.startswith("/")


def test_image_magic_size_and_ownership(system):
    assert upload(system, b"not an image").status_code == 422
    assert upload(system, plant_id=str(uuid4())).status_code == 404
    assert upload(system, b"x" * (10 * 1024 * 1024 + 1)).status_code == 413


def test_low_disk_refuses_upload_and_persists_alert(system, monkeypatch):
    import flower.services.images as images

    monkeypatch.setattr(images, "free_bytes", lambda _: 0)
    response = upload(system)
    assert response.status_code == 507
    assert response.json()["error"]["code"] == "STORAGE_LOW"
    with system["app"].state.sessions() as db:
        assert db.scalar(select(Alert).where(Alert.alert_type == "STORAGE_LOW"))
        assert db.scalar(select(PlantImage)) is None


def test_job_idempotency_and_expired_lease_fences_old_worker(system):
    sessions = system["app"].state.sessions
    now = utcnow()
    with sessions.begin() as db:
        first = enqueue_job(
            db, "plant_recognition", "plant", system["plant_id"], system["user_id"], "same"
        )
        second = enqueue_job(
            db, "plant_recognition", "plant", system["plant_id"], system["user_id"], "same"
        )
        assert first.id == second.id
    now = utcnow()
    with sessions.begin() as db:
        old = claim_job(db, "old-worker", now)
    with sessions.begin() as db:
        recover_jobs(db, now + timedelta(seconds=100))
    with sessions.begin() as db:
        new = claim_job(db, "new-worker", now + timedelta(seconds=120))
        assert new["id"] == old["id"]
        assert new["attempt"] == old["attempt"] + 1
    with sessions.begin() as db:
        assert not complete_job(db, old["id"], "old-worker", old["attempt"], {"wrong": True})
    with sessions.begin() as db:
        assert complete_job(db, new["id"], "new-worker", new["attempt"], {"ok": True})


def test_worker_failure_retries_are_bounded(system):
    with system["app"].state.sessions.begin() as db:
        job = enqueue_job(db, "unsupported", "plant", system["plant_id"], system["user_id"], "bad")
        jid = job.id
    worker = Worker(system["app"].state.sessions, system["settings"])
    for attempt in range(3):
        assert worker.run_once()
        with system["app"].state.sessions.begin() as db:
            db.get(Job, jid).available_at = utcnow() - timedelta(seconds=1)
    with system["app"].state.sessions() as db:
        job = db.get(Job, jid)
        assert job.status == "failed"
        assert job.attempt == 3


def test_manual_species_confirmation_required_and_capture_uses_command_gate(system):
    client, headers, pid = system["client"], system["user_headers"], system["plant_id"]
    response = client.post(
        f"/api/v1/plants/{pid}/capture", headers=headers | {"Idempotency-Key": "capture"}
    )
    assert response.status_code == 202
    assert response.json()["status"] == "pending"
    confirmed = client.post(
        f"/api/v1/plants/{pid}/confirm-species",
        headers=headers,
        json={
            "common_name": "Jasmine",
            "scientific_name": "Jasminum sambac",
            "input_method": "manual",
        },
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["recognition_confirmed"] is True
    assert confirmed.json()["auto_mode"] is False
