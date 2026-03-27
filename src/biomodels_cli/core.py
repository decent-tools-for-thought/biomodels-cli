"""Core operations and output rendering for biomodels-cli."""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .client import BiomodelsClient

OutputMode = str


@dataclass(frozen=True)
class RenderedOutput:
    content: str


def parse_key_value_pairs(items: Sequence[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Invalid key=value pair: {item}")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Invalid key=value pair with empty key: {item}")
        parsed[key] = value
    return parsed


def model_get(client: BiomodelsClient, model_id: str) -> Any:
    return client.get_json(f"/{model_id}")


def model_files(client: BiomodelsClient, model_id: str) -> Any:
    return client.get_json(f"/model/files/{model_id}")


def model_identifiers(client: BiomodelsClient) -> Any:
    return client.get_json("/model/identifiers")


def model_download(
    client: BiomodelsClient, model_id: str, filename: str | None, output: Path
) -> Path:
    params = {"filename": filename} if filename else None
    client.download_file(path=f"/model/download/{model_id}", params=params, output_path=output)
    return output


def search_models(
    client: BiomodelsClient,
    *,
    query: str,
    offset: int | None,
    num_results: int | None,
    sort: str | None,
) -> Any:
    params: dict[str, Any] = {"query": query}
    if offset is not None:
        params["offset"] = offset
    if num_results is not None:
        params["numResults"] = num_results
    if sort is not None:
        params["sort"] = sort
    return client.get_json("/search", params=params)


def search_all_models(
    client: BiomodelsClient,
    *,
    query: str,
    page_size: int,
    sort: str | None,
    limit: int | None,
) -> list[dict[str, Any]]:
    if page_size <= 0:
        raise ValueError("page_size must be > 0")

    results: list[dict[str, Any]] = []
    offset = 0

    while True:
        batch = search_models(
            client,
            query=query,
            offset=offset,
            num_results=page_size,
            sort=sort,
        )
        models = batch.get("models", []) if isinstance(batch, dict) else []
        if not isinstance(models, list) or not models:
            break
        for model in models:
            if isinstance(model, dict):
                results.append(model)
                if limit is not None and len(results) >= limit:
                    return results
        if len(models) < page_size:
            break
        offset += page_size

    return results


def search_download(client: BiomodelsClient, models: Sequence[str], output: Path) -> Path:
    joined = ",".join(models)
    client.download_file(path="/search/download", params={"models": joined}, output_path=output)
    return output


def parameter_search(
    client: BiomodelsClient,
    *,
    query: str | None,
    start: int | None,
    size: int | None,
    sort: str | None,
) -> Any:
    params: dict[str, Any] = {}
    if query is not None:
        params["query"] = query
    if start is not None:
        params["start"] = start
    if size is not None:
        params["size"] = size
    if sort is not None:
        params["sort"] = sort
    return client.get_json("/parameterSearch/search", params=params)


def p2m_missing(client: BiomodelsClient) -> Any:
    return client.get_json("/p2m/missing")


def p2m_representative(client: BiomodelsClient, model: str) -> Any:
    return client.get_json("/p2m/representative", params={"model": model})


def p2m_representatives(client: BiomodelsClient, model_ids: Sequence[str]) -> Any:
    return client.get_json("/p2m/representatives", params={"modelIds": ",".join(model_ids)})


def pdgsmm_missing(client: BiomodelsClient) -> Any:
    return client.get_json("/pdgsmm/missing")


def pdgsmm_representative(client: BiomodelsClient, model: str) -> Any:
    return client.get_json("/pdgsmm/representative", params={"model": model})


def pdgsmm_representatives(client: BiomodelsClient, model_ids: Sequence[str]) -> Any:
    return client.get_json("/pdgsmm/representatives", params={"modelIds": ",".join(model_ids)})


def render_output(data: Any, *, output_mode: OutputMode) -> RenderedOutput:
    if output_mode == "json":
        return RenderedOutput(content=json.dumps(data, indent=2, sort_keys=True))
    if output_mode == "jsonl":
        if isinstance(data, dict):
            payload = data.get("models")
            if isinstance(payload, list):
                lines = [json.dumps(item, sort_keys=True) for item in payload]
                return RenderedOutput(content="\n".join(lines))
        if isinstance(data, list):
            lines = [json.dumps(item, sort_keys=True) for item in data]
            return RenderedOutput(content="\n".join(lines))
        return RenderedOutput(content=json.dumps(data, sort_keys=True))
    if output_mode == "text":
        return RenderedOutput(content=render_text(data))
    raise ValueError(f"Unsupported output mode: {output_mode}")


def render_text(data: Any) -> str:
    if isinstance(data, dict):
        if "hits" in data and isinstance(data.get("models"), list):
            models = [str(item) for item in data["models"]]
            return "\n".join(models)
        if "models" in data and isinstance(data["models"], list):
            return _render_models(data["models"], matches=data.get("matches"))
        if {"submissionId", "publicationId", "name"}.intersection(data.keys()):
            return _render_model_detail(data)
        return json.dumps(data, indent=2, sort_keys=True)
    if isinstance(data, list):
        return "\n".join(json.dumps(item, sort_keys=True) for item in data)
    return str(data)


def _render_models(models: Iterable[dict[str, Any]], *, matches: Any) -> str:
    lines: list[str] = []
    if matches is not None:
        lines.append(f"matches: {matches}")
    for model in models:
        mid = model.get("id", "-")
        name = model.get("name", "-")
        lines.append(f"{mid}\t{name}")
    return "\n".join(lines)


def _render_model_detail(model: dict[str, Any]) -> str:
    fields: list[tuple[str, Any]] = [
        ("name", model.get("name")),
        ("submissionId", model.get("submissionId")),
        ("publicationId", model.get("publicationId")),
        ("description", model.get("description")),
    ]
    publication = model.get("publication")
    if isinstance(publication, dict):
        fields.append(("publication.title", publication.get("title")))
        fields.append(("publication.journal", publication.get("journal")))
        fields.append(("publication.year", publication.get("year")))
    return "\n".join(f"{k}: {v}" for k, v in fields if v is not None)
