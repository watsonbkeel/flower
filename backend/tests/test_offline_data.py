import json
from importlib.resources import files

from flower.services.providers import MockProviders


def demo_data():
    return json.loads(files("flower").joinpath("data/offline_demo.json").read_text(encoding="utf-8"))


def test_offline_data_is_packaged_and_explicitly_mock():
    data = demo_data()
    assert data["spec_version"] == "2.2.2"
    assert data["source_type"] == "mock"
    assert data["recognition"]["source_type"] == "mock"
    assert len(data["recognition"]["candidates"]) == 3
    assert len(data["sources"]) >= 2
    assert all(source["source_type"] == "mock" for source in data["sources"])
    assert data["weather"]["source_type"] == "mock"
    assert data["memory_rule"]["requires_confirmation"] is True
    forbidden = {"gpio", "duration_sec", "pulse_ml", "max_session_ml", "actual_ml"}
    assert not forbidden.intersection(data["knowledge"])
    assert not forbidden.intersection(data["memory_rule"])


def test_mock_providers_load_packaged_data_and_return_independent_results():
    data = demo_data()
    provider = MockProviders()
    assert provider.recognize(b"mock") == data["recognition"]
    result = provider.recognize(b"mock")
    result["candidates"][0]["scientific_name"] = "Changed in caller"
    assert provider.recognize(b"mock") == data["recognition"]
    sources = provider.search({})
    assert [source["url"] for source in sources] == [source["url"] for source in data["sources"]]
    assert provider.structure_care(sources) == data["knowledge"] | {
        "source_ids": [source["id"] for source in sources]
    }
    assert provider.structure_memory("") == data["memory_rule"]
    weather = provider.weather({})
    assert weather["temperature_c"] == data["weather"]["temperature_c"]
    assert weather["source_type"] == "mock"
