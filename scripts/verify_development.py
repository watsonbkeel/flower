"""Read-only loopback health and development latency evidence, with Mock auth."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time

import httpx


def main():
    base = "http://127.0.0.1:18082"
    with httpx.Client(base_url=base, timeout=10) as client:
        health = client.get("/health")
        ready = client.get("/ready")
        health.raise_for_status()
        ready.raise_for_status()
        login = client.post("/api/v1/auth/wechat-login", json={"code": "mock-demo"})
        login.raise_for_status()
        headers = {"Authorization": "Bearer " + login.json()["access_token"]}
        plant = client.get("/api/v1/plants", headers=headers).json()[0]

        def sample(_):
            started = time.perf_counter()
            response = client.get(f"/api/v1/plants/{plant['id']}/status", headers=headers)
            response.raise_for_status()
            return (time.perf_counter() - started) * 1000

        with ThreadPoolExecutor(max_workers=4) as pool:
            elapsed = sorted(pool.map(sample, range(100)))
        result = {
            "source_type": "mock",
            "database": "development SQLite",
            "health": health.json(),
            "ready": ready.json(),
            "requests": len(elapsed),
            "concurrency": 4,
            "p95_ms": round(elapsed[94], 2),
            "production_peak_test": "NOT_RUN",
        }
        Path("evidence/development-health.json").write_text(json.dumps(result, indent=2))
        print(json.dumps(result))


if __name__ == "__main__":
    main()
