import base64
from importlib.resources import files
import json
from typing import Literal

import httpx
from pydantic import Field
from sqlalchemy import update

from flower.errors import DomainError
from flower.models import ProviderUsage, utcnow
from flower.schemas import StrictModel, SourceType


class Candidate(StrictModel):
    common_name: str = Field(min_length=1, max_length=200)
    scientific_name: str = Field(min_length=1, max_length=200)
    confidence: float = Field(ge=0, le=1)
    notes: str = Field(default="", max_length=2000)


class RecognitionResult(StrictModel):
    candidates: list[Candidate] = Field(min_length=1, max_length=3)
    provider: str
    input_quality: Literal["good", "poor"]
    source_type: SourceType


class NotificationResult(StrictModel):
    status: Literal["sent", "mock"]
    source_type: SourceType


class MockProviders:
    def __init__(self):
        self.data = json.loads(
            files("flower").joinpath("data/offline_demo.json").read_text(encoding="utf-8")
        )
        if self.data["spec_version"] != "2.2.2" or self.data["source_type"] != "mock":
            raise ValueError("INVALID_MOCK_DATA")

    def search(self, plant):
        from flower.services.knowledge import CareSource

        return [
            CareSource(
                **source,
                retrieved_at=utcnow(),
            ).model_dump(mode="json")
            for source in self.data["sources"]
        ]

    def structure_care(self, sources):
        from flower.services.knowledge import Knowledge

        return Knowledge.model_validate(
            self.data["knowledge"] | {"source_ids": [source["id"] for source in sources]}
        ).model_dump(mode="json")

    def weather(self, plant):
        from datetime import timedelta
        from flower.services.knowledge import Weather

        return Weather(
            **self.data["weather"],
            observed_at=utcnow(),
            valid_until=utcnow() + timedelta(hours=3),
        ).model_dump(mode="json")

    def structure_memory(self, text):
        from flower.services.knowledge import MemoryRule

        return MemoryRule.model_validate(self.data["memory_rule"]).model_dump(mode="json")

    def notify(self, message):
        return dict(self.data["notification"])

    def recognize(self, content):
        return RecognitionResult.model_validate(self.data["recognition"]).model_dump(mode="json")


class HTTPProviders:
    """Independent normalized provider gateway; no device or hardware credentials."""

    def __init__(self, settings, sessions, transport=None):
        from urllib.parse import urlsplit

        if urlsplit(settings.provider_base_url).scheme != "https" or not settings.provider_api_key:
            raise DomainError("PROVIDER_NOT_CONFIGURED", status=503)
        self.settings, self.sessions = settings, sessions
        self.transport = transport

    def call(self, operation, payload):
        key = f"{utcnow():%Y-%m-%d}:{operation}"
        for attempt in range(2):
            with self.sessions.begin() as db:
                if db.bind.dialect.name == "postgresql":
                    from sqlalchemy.dialects.postgresql import insert
                else:
                    from sqlalchemy.dialects.sqlite import insert
                db.execute(insert(ProviderUsage).values(key=key, calls=0).on_conflict_do_nothing())
                count = db.scalar(
                    update(ProviderUsage)
                    .where(
                        ProviderUsage.key == key,
                        ProviderUsage.calls < self.settings.provider_daily_limit,
                    )
                    .values(calls=ProviderUsage.calls + 1)
                    .returning(ProviderUsage.calls)
                )
                if count is None:
                    raise DomainError("PROVIDER_QUOTA")
            try:
                with httpx.Client(
                    base_url=self.settings.provider_base_url,
                    timeout=self.settings.provider_timeout_sec,
                    transport=self.transport,
                ) as client:
                    response = client.post(
                        f"/{operation}",
                        json=payload,
                        headers={"Authorization": "Bearer " + self.settings.provider_api_key},
                    )
                    response.raise_for_status()
                    if len(response.content) > 2 * 1024 * 1024:
                        raise DomainError("PROVIDER_RESPONSE_TOO_LARGE")
                    return response.json()
            except (httpx.HTTPError, ValueError):
                if attempt == 1:
                    raise DomainError("PROVIDER_UNAVAILABLE", retryable=True) from None

    def recognize(self, content):
        response = self.call("recognize", {"image_base64": base64.b64encode(content).decode()})
        result = RecognitionResult.model_validate(response)
        if result.source_type != "real":
            raise DomainError("PROVIDER_SOURCE_MISMATCH")
        return result.model_dump(mode="json")

    def search(self, plant):
        from flower.services.knowledge import CareSource

        response = self.call(
            "search",
            {
                "scientific_name": plant["scientific_name"],
                "placement_type": plant["placement_type"],
                "city": plant["city"],
                "terms": ["container", "watering", "temperature", "soil moisture", "season"],
            },
        )
        sources = [
            CareSource.model_validate(source).model_dump(mode="json")
            for source in response["sources"]
        ]
        if any(source["source_type"] != "real" for source in sources):
            raise DomainError("PROVIDER_SOURCE_MISMATCH")
        return sources

    def structure_care(self, sources):
        from flower.services.knowledge import Knowledge

        result = self.call(
            "structure",
            {
                "task": "care_knowledge",
                "sources": sources,
                "output_schema": Knowledge.model_json_schema(),
            },
        )
        return Knowledge.model_validate(result).model_dump(mode="json")

    def weather(self, plant):
        from flower.services.knowledge import Weather

        result = self.call(
            "weather", {key: plant.get(key) for key in ("city", "latitude", "longitude")}
        )
        weather = Weather.model_validate(result)
        if weather.source_type != "real":
            raise DomainError("PROVIDER_SOURCE_MISMATCH")
        return weather.model_dump(mode="json")

    def structure_memory(self, text):
        from flower.services.knowledge import MemoryRule

        result = self.call(
            "structure",
            {
                "task": "family_memory",
                "original_experience": text,
                "output_schema": MemoryRule.model_json_schema(),
            },
        )
        return MemoryRule.model_validate(result).model_dump(mode="json")

    def notify(self, message):
        result = NotificationResult.model_validate(self.call("notify", message))
        if result.status != "sent" or result.source_type != "real":
            raise DomainError("PROVIDER_SOURCE_MISMATCH")
        return result.model_dump(mode="json")


def providers(settings, sessions):
    return (
        MockProviders() if settings.provider_mode == "mock" else HTTPProviders(settings, sessions)
    )
