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


def normalize_find_query(raw_query: str, *, default_field: str | None = None) -> tuple[str, str]:
    query = raw_query.strip()
    if not query:
        raise ValueError("query cannot be empty")

    lowered = query.lower()
    if ":" in query:
        if lowered.startswith("pubmed:"):
            pubmed_id = query.split(":", 1)[1].strip().strip('"')
            return f'PUBMED:"{pubmed_id}"', "pubmed-shortcut"
        if lowered.startswith("taxon:"):
            taxon_id = query.split(":", 1)[1].strip().strip('"')
            return f'TAXONOMY:"{taxon_id}"', "taxon-shortcut"
        return query, "raw-query"

    if default_field:
        return f'{default_field}:"{query}"', "field-query"
    return f'name:"{query}"', "name-query"


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


def show_model(
    client: BiomodelsClient, model_id: str, *, include_full_files: bool
) -> dict[str, Any]:
    model = model_get(client, model_id)
    files = model_files(client, model_id)

    payload: dict[str, Any] = {
        "model": model,
        "files_summary": summarize_files(files),
    }
    if include_full_files:
        payload["files"] = files
    return payload


def summarize_files(files_payload: Any) -> dict[str, Any]:
    if not isinstance(files_payload, dict):
        return {"main_count": 0, "additional_count": 0, "main_files": []}

    main_entries = files_payload.get("main")
    additional_entries = files_payload.get("additional")
    main = main_entries if isinstance(main_entries, list) else []
    additional = additional_entries if isinstance(additional_entries, list) else []
    main_names = [str(item.get("name", "")) for item in main if isinstance(item, dict)]

    return {
        "main_count": len(main),
        "additional_count": len(additional),
        "main_files": [name for name in main_names if name],
    }


def choose_main_xml_filename(files_payload: Any) -> str | None:
    if not isinstance(files_payload, dict):
        return None
    main_entries = files_payload.get("main")
    if not isinstance(main_entries, list):
        return None

    names: list[str] = []
    for entry in main_entries:
        if isinstance(entry, dict) and isinstance(entry.get("name"), str):
            names.append(entry["name"])
    for name in names:
        if name.lower().endswith(".xml"):
            return name
    return names[0] if names else None


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


def parameter_grep(
    client: BiomodelsClient,
    *,
    query: str | None,
    start: int | None,
    size: int | None,
    sort: str | None,
    model_filter: str | None,
    entity_filter: str | None,
    organism_filter: str | None,
    fields: Sequence[str] | None,
    limit: int | None,
) -> dict[str, Any]:
    payload = parameter_search(client, query=query, start=start, size=size, sort=sort)
    if not isinstance(payload, dict):
        return {"entries": [], "recordsFiltered": 0, "recordsTotal": 0}

    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list):
        return {"entries": [], "recordsFiltered": 0, "recordsTotal": 0}

    selected_fields = [field.strip() for field in fields] if fields else None
    entries: list[dict[str, Any]] = []

    for entry in raw_entries:
        if not isinstance(entry, dict):
            continue
        values = entry.get("fields")
        if not isinstance(values, dict):
            continue

        if model_filter and not _contains(values.get("model"), model_filter):
            continue
        if entity_filter and not _contains(
            values.get("entity", values.get("entity_id")), entity_filter
        ):
            continue
        if organism_filter and not _contains(values.get("organism"), organism_filter):
            continue

        if selected_fields is None:
            item = values
        else:
            item = {key: values.get(key) for key in selected_fields}

        entries.append(item)
        if limit is not None and len(entries) >= limit:
            break

    return {
        "entries": entries,
        "recordsFiltered": len(entries),
        "recordsTotal": payload.get("recordsTotal", len(entries)),
    }


def _contains(value: Any, needle: str) -> bool:
    return needle.casefold() in str(value).casefold()


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


def resolve_models(
    client: BiomodelsClient,
    model_ids: Sequence[str],
    *,
    family: str,
) -> dict[str, Any]:
    if not model_ids:
        return {"results": []}

    results: list[dict[str, Any]] = []
    for model_id in model_ids:
        chosen_family = family
        if family == "auto":
            chosen_family = "p2m" if model_id.upper().startswith("BMID") else "pdgsmm"

        response = (
            p2m_representative(client, model_id)
            if chosen_family == "p2m"
            else pdgsmm_representative(client, model_id)
        )
        representative = _extract_representative(response)
        status = "unresolved"
        if representative is not None:
            status = "direct" if representative == model_id else "replaced"

        results.append(
            {
                "requested": model_id,
                "family": chosen_family,
                "representative": representative,
                "status": status,
            }
        )

    return {"results": results}


def _extract_representative(payload: Any) -> str | None:
    if isinstance(payload, dict):
        representative = payload.get("representativeModelId")
        if isinstance(representative, str):
            return representative

        for value in payload.values():
            if isinstance(value, str):
                return value
            if value is None:
                continue
    return None


def filter_identifiers(
    payload: Any,
    *,
    prefixes: Sequence[str],
    limit: int | None,
) -> dict[str, Any]:
    if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
        return {"hits": 0, "models": []}

    prefixes_folded = [prefix.casefold() for prefix in prefixes]
    filtered: list[str] = []
    for item in payload["models"]:
        identifier = str(item)
        if prefixes_folded and not any(
            identifier.casefold().startswith(pref) for pref in prefixes_folded
        ):
            continue
        filtered.append(identifier)
        if limit is not None and len(filtered) >= limit:
            break

    return {"hits": len(filtered), "models": filtered}


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
