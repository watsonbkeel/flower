from datetime import timedelta

import pytest

from flower.models import Command, Job, PlantImage, utcnow
from flower.worker import Worker
from test_jobs_images import upload


def recognition(system):
    return (
        system["client"]
        .get(f"/api/v1/plants/{system['plant_id']}/recognition", headers=system["user_headers"])
        .json()
    )


def old_result(system):
    image = upload(system).json()
    assert Worker(system["app"].state.sessions, system["settings"]).run_once()
    return image


@pytest.mark.parametrize("status", ["queued", "running", "failed"])
def test_latest_photo_job_never_reuses_previous_photo_candidates(system, status):
    old_result(system)
    latest = upload(system).json()
    with system["app"].state.sessions.begin() as db:
        db.get(Job, latest["job_id"]).status = status
    value = recognition(system)
    assert value["result"] is None
    assert value["status"] == status
    assert value["image_id"] == latest["image_id"]
    assert value["manual_input_available"] is True


@pytest.mark.parametrize(
    "status", ["pending", "claimed", "executing", "failed", "expired", "timed_out", "cancelled"]
)
def test_retake_status_never_presents_an_old_result(system, status):
    old_result(system)
    capture = (
        system["client"]
        .post(
            f"/api/v1/plants/{system['plant_id']}/capture",
            headers=system["user_headers"] | {"Idempotency-Key": "retake"},
        )
        .json()
    )
    with system["app"].state.sessions.begin() as db:
        db.get(Command, capture["id"]).status = status
    value = recognition(system)
    assert value["result"] is None
    assert value["status"] == "capture_" + status
    assert value["capture_id"] == capture["id"]


def test_capture_result_is_limited_to_its_execution_window_and_excludes_memory_photos(system):
    old = old_result(system)
    capture = (
        system["client"]
        .post(
            f"/api/v1/plants/{system['plant_id']}/capture",
            headers=system["user_headers"] | {"Idempotency-Key": "window"},
        )
        .json()
    )
    started = utcnow()
    with system["app"].state.sessions.begin() as db:
        command = db.get(Command, capture["id"])
        command.status, command.started_at = "succeeded", started
        command.finished_at = started + timedelta(seconds=10)
        source = db.get(PlantImage, old["image_id"])
        for offset, kind in [(1, "whole"), (2, "memory"), (20, "whole")]:
            image = PlantImage(
                device_id=source.device_id,
                plant_id=source.plant_id,
                file_path=f"mock/{offset}.jpg",
                image_type=kind,
                source_type="mock",
                recognition_result=source.recognition_result,
                created_at=started + timedelta(seconds=offset),
            )
            db.add(image)
            db.flush()
            if offset == 1:
                expected = image.id
    value = recognition(system)
    assert value["status"] == "succeeded"
    assert value["image_id"] == expected


def test_successful_capture_without_images_is_reported_as_missing(system):
    old_result(system)
    capture = (
        system["client"]
        .post(
            f"/api/v1/plants/{system['plant_id']}/capture",
            headers=system["user_headers"] | {"Idempotency-Key": "missing"},
        )
        .json()
    )
    with system["app"].state.sessions.begin() as db:
        command = db.get(Command, capture["id"])
        command.status, command.started_at, command.finished_at = "succeeded", utcnow(), utcnow()
    value = recognition(system)
    assert value["result"] is None
    assert value["status"] == "image_missing"
