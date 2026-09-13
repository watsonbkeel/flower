import httpx


class CloudClient:
    def __init__(self, settings, transport=None):
        self.settings = settings
        self.http = httpx.Client(
            base_url=settings.server_base_url,
            timeout=httpx.Timeout(10, connect=3),
            transport=transport,
        )
        self.device_id = None
        self.token = None

    def authenticate(self):
        response = self.http.post(
            "/api/v1/device/auth/token",
            json={
                "device_code": self.settings.device_code,
                "device_secret": self.settings.device_secret,
            },
        )
        response.raise_for_status()
        data = response.json()
        self.device_id, self.token = data["device_id"], data["access_token"]

    def request(self, method, route, **kwargs):
        if self.token is None:
            self.authenticate()
        response = self.http.request(
            method,
            "/api/v1/device" + route,
            headers={"Authorization": "Bearer " + self.token},
            **kwargs,
        )
        if response.status_code == 401:
            self.authenticate()
            response = self.http.request(
                method,
                "/api/v1/device" + route,
                headers={"Authorization": "Bearer " + self.token},
                **kwargs,
            )
        response.raise_for_status()
        return response.json()

    def close(self):
        self.http.close()
