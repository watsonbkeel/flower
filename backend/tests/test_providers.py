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


@pytest.mark.parametrize("operation", ["recognize", "search", "weather", "notify"])
def test_http_gateway_rejects_non_real_results(system, operation):
    settings = system["settings"].model_copy(
        update={
            "provider_base_url": "https://provider.example",
            "provider_api_key": "test-only-provider-key",
        }
    )
    mock = MockProviders()
    response = {
        "recognize": mock.recognize(b"image"),
        "search": {"sources": mock.search({})},
        "weather": mock.weather({}),
        "notify": mock.notify({}),
    }[operation]
    provider = HTTPProviders(
        settings,
        system["app"].state.sessions,
        httpx.MockTransport(lambda _: httpx.Response(200, json=response)),
    )
    plant = {"scientific_name": "Jasminum sambac", "placement_type": "indoor", "city": "Shanghai"}
    with pytest.raises(DomainError, match="PROVIDER_SOURCE_MISMATCH"):
        if operation == "recognize":
            provider.recognize(b"image")
        elif operation == "search":
            provider.search(plant)
        elif operation == "weather":
            provider.weather(plant)
        else:
            provider.notify({"idempotency_key": "test-notification"})


def test_http_gateway_rejects_one_mock_source_among_real_sources(system):
    settings = system["settings"].model_copy(
        update={
            "provider_base_url": "https://provider.example",
            "provider_api_key": "test-only-provider-key",
        }
    )
    sources = MockProviders().search({})
    sources[0]["source_type"] = "real"
    provider = HTTPProviders(
        settings,
        system["app"].state.sessions,
        httpx.MockTransport(lambda _: httpx.Response(200, json={"sources": sources})),
    )
    with pytest.raises(DomainError, match="PROVIDER_SOURCE_MISMATCH"):
        provider.search({"scientific_name": "Jasminum sambac", "placement_type": "indoor", "city": "Shanghai"})


def test_http_gateway_accepts_structured_real_fixture_without_marking_mock_as_real(system):
    import json

    settings = system["settings"].model_copy(
        update={
            "provider_base_url": "https://provider.example",
            "provider_api_key": "test-only-provider-key",
        }
    )
    mock = MockProviders()
    sources = mock.search({})
    weather = mock.weather({})
    recognition = mock.recognize(b"image")
    for source in sources:
        source["source_type"] = "real"
    weather["source_type"] = "real"
    recognition["source_type"] = "real"

    def reply(request):
        operation = request.url.path.rsplit("/", 1)[-1]
        payload = json.loads(request.content)
        result = {
            "recognize": recognition,
            "search": {"sources": sources},
            "weather": weather,
            "structure": mock.structure_care(sources),
            "notify": {"status": "sent", "source_type": "real"},
        }[operation]
        if operation == "structure":
            assert payload["task"] == "care_knowledge"
            assert "pump_seconds" not in payload["output_schema"]["properties"]
        return httpx.Response(200, json=result)

    provider = HTTPProviders(settings, system["app"].state.sessions, httpx.MockTransport(reply))
    plant = {"scientific_name": "Jasminum sambac", "placement_type": "indoor", "city": "Shanghai"}
    assert provider.recognize(b"image")["source_type"] == "real"
    result = research(provider, plant)
    assert result["source_type"] == "real"
    assert result["weather"]["source_type"] == "real"
    assert all(source["source_type"] == "real" for source in result["sources"])
    assert provider.notify({"idempotency_key": "test-notification"}) == {
        "status": "sent",
        "source_type": "real",
    }
