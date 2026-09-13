import base64
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


class MockProviders:
    def recognize(self, content):
        return RecognitionResult(
            candidates=[
                Candidate(common_name="茉莉", scientific_name="Jasminum sambac", confidence=0.82),
                Candidate(
                    common_name="栀子", scientific_name="Gardenia jasminoides", confidence=0.12
                ),
                Candidate(common_name="山茶", scientific_name="Camellia japonica", confidence=0.06),
            ],
            provider="mock",
            input_quality="good",
            source_type="mock",
        ).model_dump(mode="json")


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


def providers(settings, sessions):
    return (
        MockProviders() if settings.provider_mode == "mock" else HTTPProviders(settings, sessions)
    )
