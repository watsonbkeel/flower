from flower.models import User, Alert, Device
from flower.auth import issue_token


def test_mock_login_is_explicit_and_production_never_bypasses(system):
    response = system["client"].post("/api/v1/auth/wechat-login", json={"code": "mock-owner"})
    assert response.status_code == 200
    assert response.json()["source_type"] == "mock"
    assert response.json()["user_id"] == system["user_id"]
    response = system["client"].post("/api/v1/auth/wechat-login", json={"code": "ordinary-code"})
    assert response.status_code == 503


def test_resource_ownership_across_user_routes(system):
    with system["app"].state.sessions.begin() as db:
        user = User(openid="other-user")
        db.add(user)
        db.flush()
        token = issue_token(system["settings"], user.id, "user")
    headers = {"Authorization": "Bearer " + token}
    client, pid = system["client"], system["plant_id"]
    assert client.get("/api/v1/plants", headers=headers).json() == []
    for path in [f"/plants/{pid}/status", f"/plants/{pid}/events", f"/plants/{pid}/recognition"]:
        assert client.get("/api/v1" + path, headers=headers).status_code == 404


def test_alert_center_and_read_status(system):
    with system["app"].state.sessions.begin() as db:
        alert = Alert(
            user_id=system["user_id"],
            device_id=system["device_id"],
            alert_type="LOW_WATER",
            title="缺水",
            message="水箱水量不足",
        )
        db.add(alert)
        db.flush()
        aid = alert.id
    client, headers = system["client"], system["user_headers"]
    alerts = client.get("/api/v1/alerts", headers=headers).json()
    assert alerts[0]["id"] == aid
    assert client.put(f"/api/v1/alerts/{aid}/read", headers=headers).json()["is_read"] is True


def test_manual_water_rate_limit_and_request_schema(system):
    client, headers, pid = system["client"], system["user_headers"], system["plant_id"]
    with system["app"].state.sessions.begin() as db:
        db.get(Device, system["device_id"]).time_trusted = False
    for i in range(6):
        response = client.post(
            f"/api/v1/plants/{pid}/water",
            headers=headers | {"Idempotency-Key": str(i)},
            json={"quantity": 10, "unit": "ml"},
        )
        assert response.status_code == 409
    assert (
        client.post(
            f"/api/v1/plants/{pid}/water",
            headers=headers | {"Idempotency-Key": "last"},
            json={"quantity": 10, "unit": "ml"},
        ).status_code
        == 429
    )
