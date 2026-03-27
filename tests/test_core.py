from __future__ import annotations

from typing import Any

import pytest

from biomodels_cli.core import (
    choose_main_xml_filename,
    filter_identifiers,
    normalize_find_query,
    parameter_grep,
    parse_key_value_pairs,
    render_output,
    resolve_models,
    search_all_models,
)


class StubClient:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = responses
        self.calls = 0

    def get_json(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        assert path == "/search"
        _ = params
        response = self._responses[self.calls]
        self.calls += 1
        return response


class ParameterStubClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def get_json(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        _ = params
        assert path == "/parameterSearch/search"
        return self.payload


class ResolveStubClient:
    def get_json(self, _path: str, *, params: dict[str, Any] | None = None) -> Any:
        assert params is not None
        requested = params["model"]
        return {"requestedModelId": requested, "representativeModelId": f"REP-{requested}"}


def test_parse_key_value_pairs_success() -> None:
    parsed = parse_key_value_pairs(["query=BIOMD", "offset=10"])
    assert parsed == {"query": "BIOMD", "offset": "10"}


def test_parse_key_value_pairs_failure() -> None:
    with pytest.raises(ValueError):
        parse_key_value_pairs(["invalid"])


def test_render_output_jsonl_for_models() -> None:
    payload = {"models": [{"id": "M1"}, {"id": "M2"}]}
    out = render_output(payload, output_mode="jsonl")
    assert '{"id": "M1"}' in out.content
    assert '{"id": "M2"}' in out.content


def test_search_all_models_paginates_and_limits() -> None:
    client = StubClient(
        responses=[
            {"models": [{"id": "A"}, {"id": "B"}]},
            {"models": [{"id": "C"}]},
        ]
    )
    results = search_all_models(client, query="*", page_size=2, sort=None, limit=2)
    assert [item["id"] for item in results] == ["A", "B"]
    assert client.calls == 1


def test_normalize_find_query_plain_text_and_shortcuts() -> None:
    q1, s1 = normalize_find_query("insulin", default_field=None)
    q2, s2 = normalize_find_query("pubmed:27869123", default_field=None)
    assert q1 == 'name:"insulin"'
    assert s1 == "name-query"
    assert q2 == 'PUBMED:"27869123"'
    assert s2 == "pubmed-shortcut"


def test_choose_main_xml_filename_prefers_xml() -> None:
    payload = {"main": [{"name": "model.xml"}, {"name": "model.sbml"}]}
    assert choose_main_xml_filename(payload) == "model.xml"


def test_filter_identifiers_by_prefix_and_limit() -> None:
    payload = {"models": ["BIOMD1", "MODEL1", "BIOMD2"]}
    filtered = filter_identifiers(payload, prefixes=["BIOMD"], limit=1)
    assert filtered["models"] == ["BIOMD1"]
    assert filtered["hits"] == 1


def test_parameter_grep_filters_and_projects_fields() -> None:
    client = ParameterStubClient(
        {
            "entries": [
                {
                    "fields": {
                        "model": "BIOMD1",
                        "entity": "Insulin receptor",
                        "organism": "Homo sapiens",
                        "parameters": "k=1",
                    }
                },
                {
                    "fields": {
                        "model": "BIOMD2",
                        "entity": "Glucose",
                        "organism": "Mus musculus",
                        "parameters": "k=2",
                    }
                },
            ],
            "recordsTotal": 2,
        }
    )
    out = parameter_grep(
        client,
        query="insulin",
        start=None,
        size=None,
        sort=None,
        model_filter="BIOMD1",
        entity_filter="insulin",
        organism_filter="homo",
        fields=["model", "parameters"],
        limit=None,
    )
    assert out["recordsFiltered"] == 1
    assert out["entries"][0] == {"model": "BIOMD1", "parameters": "k=1"}


def test_resolve_models_auto_family() -> None:
    out = resolve_models(ResolveStubClient(), ["BMID123", "MODEL999"], family="auto")
    assert out["results"][0]["family"] == "p2m"
    assert out["results"][1]["family"] == "pdgsmm"
