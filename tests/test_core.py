from __future__ import annotations

from typing import Any

import pytest

from biomodels_cli.core import parse_key_value_pairs, render_output, search_all_models


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
