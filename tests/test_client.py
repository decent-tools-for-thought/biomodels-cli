from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from biomodels_cli.client import BiomodelsClient
from biomodels_cli.exceptions import ApiError, ResponseDecodeError


def _mock_client(handler: httpx.MockTransport) -> BiomodelsClient:
    client = BiomodelsClient(base_url="https://www.biomodels.org/", timeout=5.0)
    client._client = httpx.Client(transport=handler, base_url="https://www.biomodels.org/")  # type: ignore[attr-defined]
    return client


def test_get_json_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/search"
        return httpx.Response(200, json={"matches": 1, "models": [{"id": "M1"}]})

    with _mock_client(httpx.MockTransport(handler)) as client:
        payload = client.get_json("/search", params={"query": "*"})
    assert payload["matches"] == 1


def test_get_json_not_found_raises() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    with _mock_client(httpx.MockTransport(handler)) as client, pytest.raises(ApiError):
        client.get_json("/missing")


def test_get_json_decode_error_raises() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not-json", headers={"content-type": "application/json"})

    with _mock_client(httpx.MockTransport(handler)) as client, pytest.raises(ResponseDecodeError):
        client.get_json("/search")


def test_download_file_writes_output(tmp_path: Path) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"zip-bytes")

    output = tmp_path / "models.zip"
    with _mock_client(httpx.MockTransport(handler)) as client:
        client.download_file(path="/search/download", params={"models": "A"}, output_path=output)
    assert output.read_bytes() == b"zip-bytes"
