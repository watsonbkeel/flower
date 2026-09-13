import pytest

from flower.models import PlantImage


@pytest.mark.parametrize(
    "confidence,default,retake",
    [(0.75, 0, False), (0.749, None, False), (0.45, None, False), (0.449, None, True)],
)
def test_recognition_ranks_candidates_before_applying_selection_threshold(
    system, confidence, default, retake
):
    with system["app"].state.sessions.begin() as db:
        db.add(
            PlantImage(
                device_id=system["device_id"],
                plant_id=system["plant_id"],
                file_path="test/selection.jpg",
                image_type="whole",
                source_type="mock",
                recognition_result={
                    "candidates": [
                        {
                            "common_name": "Lower",
                            "scientific_name": "Lower candidate",
                            "confidence": 0.1,
                        },
                        {
                            "common_name": "Best",
                            "scientific_name": "Best candidate",
                            "confidence": confidence,
                        },
                    ],
                    "provider": "mock",
                    "source_type": "mock",
                    "input_quality": "good",
                },
            )
        )
    response = system["client"].get(
        f"/api/v1/plants/{system['plant_id']}/recognition", headers=system["user_headers"]
    )
    assert response.status_code == 200
    value = response.json()
    assert value["result"]["candidates"][0]["scientific_name"] == "Best candidate"
    assert value["default_selection"] == default
    assert value["retake_recommended"] == retake
