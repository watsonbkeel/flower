from io import BytesIO

from PIL import Image


def test_owner_can_upload_memory_photo_without_recognition(system):
    content = BytesIO()
    Image.new("RGB", (256, 256), "green").save(content, "JPEG")
    client = system["client"]
    response = client.post(
        "/api/v1/images",
        headers=system["user_headers"],
        data={"plant_id": system["plant_id"]},
        files={"file": ("memory.jpg", content.getvalue(), "image/jpeg")},
    )
    assert response.status_code == 201
    photo = response.json()["image_id"]
    memory = client.post(
        "/api/v1/memories",
        headers=system["user_headers"],
        json={"title": "Memory", "plant_id": system["plant_id"], "photo_id": photo},
    )
    assert memory.status_code == 201
    listed = client.get("/api/v1/memories", headers=system["user_headers"]).json()
    assert listed[0]["photo_id"] == photo
    assert client.get("/api/v1/images/" + photo).status_code == 401
    assert client.get("/api/v1/images/" + photo, headers=system["user_headers"]).status_code == 200
