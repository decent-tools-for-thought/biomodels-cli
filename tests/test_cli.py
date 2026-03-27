from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from biomodels_cli import cli
from biomodels_cli.exceptions import ApiError


class FakeClient:
    def __init__(self, *_: Any, **__: Any) -> None:
        self.base_url = ""
        self.timeout = 0.0

    def __enter__(self) -> FakeClient:
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    def get_json(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        if path == "/search":
            return {
                "matches": 1,
                "models": [{"id": "BIOMD0000000001", "name": "Example model"}],
                "queryParameters": params or {},
            }
        if path == "/model/identifiers":
            return {"hits": 2, "models": ["A", "B"]}
        if path == "/BIOMD404":
            raise ApiError("not found", status_code=404)
        return {"ok": True, "path": path, "params": params}

    def request_raw(
        self,
        *,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        accept: str = "application/json",
    ) -> tuple[int, dict[str, str], bytes]:
        payload = json.dumps({"method": method, "path": path, "params": params, "accept": accept})
        return 200, {"content-type": "application/json"}, payload.encode("utf-8")

    def download_file(self, *, path: str, params: dict[str, Any] | None, output_path: Path) -> None:
        output_path.write_bytes(f"{path}|{params}".encode())


@pytest.fixture(autouse=True)
def patch_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "BiomodelsClient", FakeClient)


def test_bare_invocation_prints_help_and_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main([])
    captured = capsys.readouterr()
    assert rc == 0
    assert "BioModels REST API command-line client" in captured.out


def test_top_level_help_works(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    captured = capsys.readouterr()
    assert exc.value.code == 0
    assert "usage:" in captured.out


def test_search_query_json_output(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["--output", "json", "search", "query", "name:insulin"])
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["matches"] == 1
    assert payload["models"][0]["id"] == "BIOMD0000000001"


def test_model_identifiers_limit_text_output(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["model", "identifiers", "--limit", "1"])
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out.strip() == "A"


def test_runtime_error_returns_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["model", "get", "BIOMD404"])
    captured = capsys.readouterr()
    assert rc == 1
    assert "Runtime error" in captured.err


def test_invalid_raw_param_returns_usage_code(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["raw", "/search", "--param", "invalid"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "Invalid input" in captured.err
