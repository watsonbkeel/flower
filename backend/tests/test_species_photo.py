from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import select

from flower.models import Plant, PlantImage, utcnow
from flower.services.retention import cleanup


def make_image(system, *, kind="whole", plant_id=None):
    with system["app"].state.sessions.begin() as db:
        image = PlantImage(
            plant_id=plant_id or system["plant_id"],
            device_id=system["device_id"],
            file_path=f"mock/{uuid4()}.jpg",
            image_type=kind,
            source_type="mock",
            expires_at=utcnow() + timedelta(days=90),
        )
        db.add(image)
        db.flush()
        return image.id, image.file_path


def confirm(system, **extra):
    return system["client"].post(
        f"/api/v1/plants/{system['plant_id']}/confirm-species",
        headers=system["user_headers"],
        json={
            "common_name": "Jasmine",
            "scientific_name": "Jasminum sambac",
            "input_method": "manual",
            **extra,
        },
    )


def test_confirmation_keeps_selected_photo_despite_newer_upload(system):
    selected, path = make_image(system)
    later, _ = make_image(system)
    memory, _ = make_image(system, kind="memory")
    response = confirm(system, image_id=selected)
    assert response.status_code == 200
    assert response.json()["photo_path"] == path
    with system["app"].state.sessions() as db:
        assert db.get(PlantImage, selected).expires_at is None
        assert db.get(PlantImage, later).expires_at is not None
        assert db.get(PlantImage, memory).expires_at is not None


def test_confirmation_without_photo_does_not_replace_existing_main_image(system):
    _, path = make_image(system)
    with system["app"].state.sessions.begin() as db:
        db.get(Plant, system["plant_id"]).photo_path = path
    make_image(system, kind="memory")
    response = confirm(system)
    assert response.status_code == 200
    assert response.json()["photo_path"] == path


@pytest.mark.parametrize("kind", ["memory", "other_plant", "missing"])
def test_confirmation_rejects_ineligible_photo_without_changing_species(system, kind):
    pid = system["plant_id"]
    if kind == "other_plant":
        with system["app"].state.sessions.begin() as db:
            plant = Plant(
                user_id=system["user_id"],
                device_id=system["device_id"],
                name="Other",
                is_primary=False,
            )
            db.add(plant)
            db.flush()
            pid = plant.id
    image_id = (
        str(uuid4())
        if kind == "missing"
        else make_image(system, kind="memory" if kind == "memory" else "whole", plant_id=pid)[0]
    )
    response = confirm(system, image_id=image_id, scientific_name="Unwanted replacement")
    assert response.status_code == 404
    with system["app"].state.sessions() as db:
        plant = db.get(Plant, system["plant_id"])
        assert plant.scientific_name == "Jasminum sambac"
        assert plant.auto_mode


def test_image_cleanup_skips_photo_locked_for_confirmation(system):
    sessions = system["app"].state.sessions
    if system["app"].state.engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row-lock test")
    image_id, path = make_image(system)
    with sessions.begin() as db:
        db.get(PlantImage, image_id).expires_at = utcnow() - timedelta(seconds=1)

    def clean():
        with sessions.begin() as db:
            return cleanup(db, system["settings"], utcnow())

    with ThreadPoolExecutor(max_workers=1) as pool:
        with sessions.begin() as db:
            image = db.scalar(select(PlantImage).where(PlantImage.id == image_id).with_for_update())
            future = pool.submit(clean)
            assert future.result(timeout=3)["images"] == 0
            image.expires_at = None
            db.get(Plant, system["plant_id"]).photo_path = path
    with sessions() as db:
        assert db.get(PlantImage, image_id) is not None
