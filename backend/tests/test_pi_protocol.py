from flower_pi.cloud.client import CloudClient
from flower_pi.config import PiSettings
from flower_pi.main import decode_command
import httpx


def test_cloud_client_refreshes_expired_token_once():
    seen = []
    auth_count = 0

    def transport(request):
        nonlocal auth_count
        seen.append(request)
        if request.url.path.endswith("/auth/token"):
            auth_count += 1
            return httpx.Response(
                200, json={"device_id": "device", "access_token": f"token{auth_count}"}
            )
        if request.headers["authorization"] == "Bearer token1":
            return httpx.Response(401)
        return httpx.Response(200, json={"command": None})

    client = CloudClient(PiSettings(), httpx.MockTransport(transport))
    assert client.request("POST", "/commands/claim") == {"command": None}
    assert len(seen) == 4
    client.close()


def test_api_command_decodes_in_pi(system):
    response = system["client"].post(
        f"/api/v1/plants/{system['plant_id']}/water",
        headers=system["user_headers"] | {"Idempotency-Key": "pi-contract"},
        json={"quantity": 20, "unit": "ml"},
    )
    command = decode_command(response.json())
    assert command.max_pulses == 2
    assert command.session_max_duration_sec > 60
    assert command.device_id == system["device_id"]


def test_cloud_policy_revocation_clears_cached_fallback(tmp_path):
    from flower_pi.main import refresh_policy
    from flower_pi.storage.ledger import Ledger

    ledger = Ledger(tmp_path / "local.db")
    ledger.set_value("fallback", {"auto_mode": True})

    class Revoked:
        def request(self, *args):
            response = httpx.Response(
                404, request=httpx.Request("GET", "https://flower.invalid/fallback")
            )
            response.raise_for_status()

    assert refresh_policy(Revoked(), ledger) is None
    assert ledger.value("fallback") == {}
    ledger.close()
