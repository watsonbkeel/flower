import httpx
import pytest

from flower.errors import DomainError
from flower.services.providers import HTTPProviders, MockProviders
from flower.services.care import research


def test_llm_failure_and_source_conflict_are_visible_conservative_fallbacks():
    class Broken(MockProviders):
        def structure_care(self, sources):
            return {"pump_seconds": 10}

        def weather(self, plant):
            raise DomainError("PROVIDER_UNAVAILABLE")

    result = research(Broken(), {})
    assert result["needs_review"] is True
    assert result["weather"] is None
    assert "pump_seconds" not in result

    class Conflicted(MockProviders):
        def search(self, plant):
            sources = super().search(plant)
            sources[0]["conflict"] = True
            return sources

    conflict = research(Conflicted(), {})
    assert conflict["source_conflict"]
    assert conflict["soil_target_min_pct"] < 40


def test_provider_timeout_has_bounded_retries_and_persistent_budget(system):
    settings = system["settings"].model_copy(
        update={
            "provider_base_url": "https://provider.example",
            "provider_api_key": "test-only-provider-key",
            "provider_daily_limit": 2,
        }
    )
    calls = []

    def fail(request):
        calls.append(request)
        raise httpx.ReadTimeout("injected timeout")

    provider = HTTPProviders(settings, system["app"].state.sessions, httpx.MockTransport(fail))
    with pytest.raises(DomainError, match="PROVIDER_UNAVAILABLE"):
        provider.call("recognize", {})
    assert len(calls) == 2
    with pytest.raises(DomainError, match="PROVIDER_QUOTA"):
        provider.call("recognize", {})
    assert len(calls) == 2
