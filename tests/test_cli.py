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
            query = (params or {}).get("query", "")
            if query == 'name:"none"':
                return {"matches": 0, "models": [], "queryParameters": params or {}}
            return {
                "matches": 1,
                "models": [{"id": "BIOMD0000000001", "name": "Example model"}],
                "queryParameters": params or {},
            }
        if path == "/model/files/BIOMD0000000001":
            return {"main": [{"name": "main.xml"}], "additional": [{"name": "notes.txt"}]}
        if path == "/model/identifiers":
            return {"hits": 3, "models": ["BIOMD1", "MODEL1", "BIOMD2"]}
        if path == "/BIOMD404":
            raise ApiError("not found", status_code=404)
        if path in {"/p2m/representative", "/pdgsmm/representative"}:
            model = (params or {}).get("model", "")
            return {"requestedModelId": model, "representativeModelId": f"REP-{model}"}
        if path == "/parameterSearch/search":
            return {
                "entries": [
                    {
                        "fields": {
                            "model": "BIOMD1",
                            "entity": "Insulin",
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

    def get_text(self, path: str, *, params: dict[str, Any] | None = None, accept: str) -> str:
        return f"TEXT path={path} params={params} accept={accept}"

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
    assert captured.out.strip() == "BIOMD1"


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


def test_find_command_normalizes_plain_text(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["--output", "json", "find", "insulin", "--limit", "1"])
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["query"] == 'name:"insulin"'
    assert payload["matches"] == 1


def test_show_command_returns_consolidated_payload(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["--output", "json", "show", "BIOMD0000000001"])
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["files_summary"]["main_count"] == 1


def test_fetch_model_main_xml_uses_default_filename(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cwd = Path.cwd()
    try:
        import os

        os.chdir(tmp_path)
        rc = cli.main(["fetch", "model", "BIOMD0000000001", "--main-xml"])
    finally:
        os.chdir(cwd)
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out.strip().endswith("main.xml")


def test_fetch_query_fails_when_no_results(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["fetch", "query", 'name:"none"'])
    captured = capsys.readouterr()
    assert rc == 2
    assert "No models found" in captured.err


def test_resolve_command_outputs_results(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["--output", "json", "resolve", "BMID1", "MODEL1", "--family", "auto"])
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert len(payload["results"]) == 2


def test_params_grep_filters_entries(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(
        [
            "--output",
            "json",
            "params",
            "grep",
            "--model",
            "BIOMD1",
            "--entity",
            "insulin",
            "--fields",
            "model,parameters",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["recordsFiltered"] == 1
    assert payload["entries"][0]["model"] == "BIOMD1"


def test_ids_filters_prefixes(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["ids", "--prefix", "MODEL", "--limit", "1"])
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out.strip() == "MODEL1"


def test_inspect_query_with_validation(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["--output", "json", "inspect", "query", "insulin", "--validate"])
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["normalized_query"] == 'name:"insulin"'
    assert payload["valid"] is True


def test_stats_query_command(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["--output", "json", "stats", "query", "insulin"])
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["query"] == "insulin"
    assert "formats" in payload


def test_model_get_xml_passthrough(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["model", "get", "BIOMD0000000001", "--api-format", "xml"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "accept=application/xml" in captured.out


def test_search_query_html_passthrough(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["search", "query", "insulin", "--api-format", "html"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "accept=text/html" in captured.out


def test_params_search_csv_passthrough(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["params", "search", "--query", "insulin", "--api-format", "csv"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "accept=application/csv" in captured.out


def test_mapping_representative_xml_passthrough(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["p2m", "representative", "BMID1", "--api-format", "xml"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "path=/p2m/representative" in captured.out
