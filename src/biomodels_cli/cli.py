"""CLI entrypoint and argparse command surface."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .client import BiomodelsClient
from .config import Config, load_config
from .core import (
    choose_main_xml_filename,
    filter_identifiers,
    model_download,
    model_files,
    model_get,
    model_identifiers,
    normalize_find_query,
    p2m_missing,
    p2m_representative,
    p2m_representatives,
    parameter_grep,
    parameter_search,
    parse_key_value_pairs,
    pdgsmm_missing,
    pdgsmm_representative,
    pdgsmm_representatives,
    query_stats,
    render_output,
    resolve_models,
    search_all_models,
    search_download,
    search_models,
    show_model,
)
from .exceptions import ApiError, BiomodelsError, ConfigError, NetworkError, ResponseDecodeError

DEFAULT_PAGE_SIZE = 100


def api_format_to_accept(api_format: str) -> str:
    if api_format == "json":
        return "application/json"
    if api_format == "xml":
        return "application/xml"
    if api_format == "html":
        return "text/html"
    if api_format == "csv":
        return "application/csv"
    raise ValueError(f"Unsupported api format: {api_format}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="biomodels",
        description="BioModels REST API command-line client",
    )
    parser.add_argument("--base-url", help="Override BioModels base URL")
    parser.add_argument("--timeout", type=float, help="HTTP timeout in seconds")
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to JSON config file (default: $XDG_CONFIG_HOME/biomodels-cli/config.json)",
    )
    parser.add_argument(
        "--output",
        choices=["text", "json", "jsonl"],
        default="text",
        help="Output format (default: text)",
    )

    subparsers = parser.add_subparsers(dest="command")

    add_model_subcommands(subparsers)
    add_search_subcommands(subparsers)
    add_params_subcommand(subparsers)
    add_mapping_family_subcommands(subparsers, family="p2m")
    add_mapping_family_subcommands(subparsers, family="pdgsmm")
    add_find_subcommand(subparsers)
    add_show_subcommand(subparsers)
    add_fetch_subcommand(subparsers)
    add_resolve_subcommand(subparsers)
    add_ids_subcommand(subparsers)
    add_stats_subcommand(subparsers)
    add_inspect_subcommand(subparsers)
    add_raw_subcommand(subparsers)

    return parser


def add_model_subcommands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    model = subparsers.add_parser("model", help="Model retrieval and download operations")
    model_sub = model.add_subparsers(dest="model_command", required=True)

    get_cmd = model_sub.add_parser("get", help="Fetch model details by model identifier")
    get_cmd.add_argument("model_id", help="Model identifier (e.g., BIOMD0000000123)")
    get_cmd.add_argument(
        "--api-format",
        choices=["json", "xml", "html"],
        default="json",
        help="Upstream response format",
    )

    files_cmd = model_sub.add_parser("files", help="List files associated with a model")
    files_cmd.add_argument("model_id", help="Model identifier")
    files_cmd.add_argument(
        "--api-format",
        choices=["json", "xml"],
        default="json",
        help="Upstream response format",
    )

    identifiers_cmd = model_sub.add_parser("identifiers", help="List all public model identifiers")
    identifiers_cmd.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum identifiers to return",
    )
    identifiers_cmd.add_argument(
        "--api-format",
        choices=["json", "xml", "html"],
        default="json",
        help="Upstream response format",
    )

    download_cmd = model_sub.add_parser("download", help="Download model archive or a model file")
    download_cmd.add_argument("model_id", help="Model identifier")
    download_cmd.add_argument(
        "-o", "--output-path", required=True, type=Path, help="Destination file path"
    )
    download_cmd.add_argument("--filename", help="Specific model file name to download")


def add_search_subcommands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    search = subparsers.add_parser("search", help="Model search operations")
    search_sub = search.add_subparsers(dest="search_command", required=True)

    query_cmd = search_sub.add_parser("query", help="Search models using BioModels query syntax")
    query_cmd.add_argument("query", help="Search query")
    query_cmd.add_argument("--offset", type=int, default=None, help="Offset for paged search")
    query_cmd.add_argument(
        "--num-results", type=int, default=None, help="Page size for paged search"
    )
    query_cmd.add_argument("--sort", default=None, help="Sort mode (e.g. relevance-desc)")
    query_cmd.add_argument(
        "--api-format",
        choices=["json", "xml", "html"],
        default="json",
        help="Upstream response format",
    )

    all_cmd = search_sub.add_parser("all", help="Fetch all search pages, with optional limit")
    all_cmd.add_argument("query", help="Search query")
    all_cmd.add_argument(
        "--page-size", type=int, default=DEFAULT_PAGE_SIZE, help="Page size per request"
    )
    all_cmd.add_argument("--sort", default=None, help="Sort mode (e.g. relevance-desc)")
    all_cmd.add_argument("--limit", type=int, default=None, help="Maximum records to return")

    dl_cmd = search_sub.add_parser("download", help="Download main files for one or more models")
    dl_cmd.add_argument("models", nargs="+", help="Model identifiers")
    dl_cmd.add_argument(
        "-o", "--output-path", required=True, type=Path, help="Destination zip path"
    )


def add_params_subcommand(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    params = subparsers.add_parser("params", help="Parameter search operations")
    params_sub = params.add_subparsers(dest="params_command", required=True)

    search_cmd = params_sub.add_parser("search", help="Search model parameters")
    search_cmd.add_argument("--query", default=None, help="Parameter search query")
    search_cmd.add_argument("--start", type=int, default=None, help="Result offset")
    search_cmd.add_argument(
        "--size", type=int, default=None, choices=[10, 25, 50, 100], help="Page size"
    )
    search_cmd.add_argument("--sort", default=None, help="Sort expression")
    search_cmd.add_argument(
        "--api-format",
        choices=["json", "xml", "csv"],
        default="json",
        help="Upstream response format",
    )

    grep_cmd = params_sub.add_parser("grep", help="Filter and project parameter-search entries")
    grep_cmd.add_argument("--query", default=None, help="Parameter search query")
    grep_cmd.add_argument("--start", type=int, default=None, help="Result offset")
    grep_cmd.add_argument(
        "--size", type=int, default=None, choices=[10, 25, 50, 100], help="Page size"
    )
    grep_cmd.add_argument("--sort", default=None, help="Sort expression")
    grep_cmd.add_argument("--model", default=None, help="Keep entries matching model id")
    grep_cmd.add_argument("--entity", default=None, help="Keep entries matching entity")
    grep_cmd.add_argument("--organism", default=None, help="Keep entries matching organism")
    grep_cmd.add_argument(
        "--fields",
        default=None,
        help="Comma-separated field list to keep (e.g. model,entity,parameters)",
    )
    grep_cmd.add_argument("--limit", type=int, default=None, help="Maximum entries after filtering")


def add_find_subcommand(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    find = subparsers.add_parser(
        "find", help="High-level model finder using plain terms or query syntax"
    )
    find.add_argument("query", help="Free text or query expression")
    find.add_argument(
        "--field",
        default=None,
        choices=["name", "submissionId", "publicationId"],
        help="Default field for plain-text query",
    )
    find.add_argument("--limit", type=int, default=20, help="Maximum records")
    find.add_argument("--sort", default=None, help="Sort mode (e.g. relevance-desc)")


def add_show_subcommand(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    show = subparsers.add_parser("show", help="Show consolidated model details plus file summary")
    show.add_argument("model_id", help="Model identifier")
    show.add_argument("--full", action="store_true", help="Include full file listing payload")


def add_fetch_subcommand(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    fetch = subparsers.add_parser("fetch", help="Download workflow helper")
    fetch_sub = fetch.add_subparsers(dest="fetch_command", required=True)

    model_cmd = fetch_sub.add_parser("model", help="Download a model archive or main XML")
    model_cmd.add_argument("model_id", help="Model identifier")
    model_cmd.add_argument("-o", "--output-path", type=Path, default=None, help="Destination path")
    model_cmd.add_argument(
        "--main-xml", action="store_true", help="Download the model's main XML file"
    )

    query_cmd = fetch_sub.add_parser(
        "query", help="Search then download main files for matching models"
    )
    query_cmd.add_argument("query", help="Search query")
    query_cmd.add_argument("--limit", type=int, default=20, help="Maximum models to include")
    query_cmd.add_argument("--sort", default=None, help="Sort mode")
    query_cmd.add_argument(
        "-o",
        "--output-path",
        type=Path,
        default=Path("biomodels-search.zip"),
        help="Destination zip path",
    )


def add_resolve_subcommand(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    resolve = subparsers.add_parser("resolve", help="Resolve representative models for IDs")
    resolve.add_argument("model_ids", nargs="+", help="Model identifiers")
    resolve.add_argument(
        "--family",
        default="auto",
        choices=["auto", "p2m", "pdgsmm"],
        help="Mapping family or automatic inference",
    )


def add_ids_subcommand(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    ids = subparsers.add_parser("ids", help="High-level identifier export")
    ids.add_argument(
        "--prefix",
        action="append",
        default=[],
        help="Prefix filter, repeatable (e.g. BIOMD, MODEL)",
    )
    ids.add_argument("--limit", type=int, default=None, help="Maximum identifiers")


def add_stats_subcommand(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    stats = subparsers.add_parser("stats", help="Query result summary statistics")
    stats_sub = stats.add_subparsers(dest="stats_command", required=True)
    query_cmd = stats_sub.add_parser("query", help="Summarize first page of search results")
    query_cmd.add_argument("query", help="Search query")


def add_inspect_subcommand(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    inspect = subparsers.add_parser("inspect", help="Inspect and validate queries")
    inspect_sub = inspect.add_subparsers(dest="inspect_command", required=True)

    query_cmd = inspect_sub.add_parser(
        "query", help="Normalize query and optionally validate upstream"
    )
    query_cmd.add_argument("query", help="Free text or query expression")
    query_cmd.add_argument(
        "--field",
        default=None,
        choices=["name", "submissionId", "publicationId"],
        help="Default field for plain text",
    )
    query_cmd.add_argument(
        "--validate",
        action="store_true",
        help="Run a lightweight upstream validation request",
    )


def add_mapping_family_subcommands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser], *, family: str
) -> None:
    grp = subparsers.add_parser(family, help=f"{family.upper()} representative/missing operations")
    grp_sub = grp.add_subparsers(dest=f"{family}_command", required=True)

    missing_cmd = grp_sub.add_parser(
        "missing", help=f"List {family.upper()} models no longer directly accessible"
    )
    missing_cmd.add_argument(
        "--api-format",
        choices=["json", "xml", "html"],
        default="json",
        help="Upstream response format",
    )

    representative_cmd = grp_sub.add_parser("representative", help="Lookup representative model")
    representative_cmd.add_argument("model", help="Model identifier")
    representative_cmd.add_argument(
        "--api-format",
        choices=["json", "xml", "html"],
        default="json",
        help="Upstream response format",
    )

    reps_cmd = grp_sub.add_parser("representatives", help="Lookup representative models in batch")
    reps_cmd.add_argument("model_ids", nargs="+", help="Model identifiers")
    reps_cmd.add_argument(
        "--api-format",
        choices=["json", "xml", "html"],
        default="json",
        help="Upstream response format",
    )


def add_raw_subcommand(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    raw = subparsers.add_parser("raw", help="Generic raw API call escape hatch")
    raw.add_argument("path", help="API path, e.g. /search")
    raw.add_argument("--method", default="GET", choices=["GET"], help="HTTP method")
    raw.add_argument(
        "--param",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Query parameter, can be repeated",
    )
    raw.add_argument(
        "--accept",
        default="application/json",
        help="Accept header value (default: application/json)",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help(sys.stdout)
        return 0

    try:
        config = load_config(base_url=args.base_url, timeout=args.timeout, config_path=args.config)
        return dispatch(args, config)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"Invalid input: {exc}", file=sys.stderr)
        return 2
    except (ApiError, NetworkError, ResponseDecodeError) as exc:
        print(f"Runtime error: {exc}", file=sys.stderr)
        return 1
    except BiomodelsError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def dispatch(args: argparse.Namespace, config: Config) -> int:
    with BiomodelsClient(base_url=config.base_url, timeout=config.timeout) as client:
        if args.command == "model":
            return dispatch_model(args, client, output_mode=args.output)
        if args.command == "search":
            return dispatch_search(args, client, output_mode=args.output)
        if args.command == "params":
            return dispatch_params(args, client, output_mode=args.output)
        if args.command == "p2m":
            return dispatch_mapping(args, client, family="p2m", output_mode=args.output)
        if args.command == "pdgsmm":
            return dispatch_mapping(args, client, family="pdgsmm", output_mode=args.output)
        if args.command == "find":
            return dispatch_find(args, client, output_mode=args.output)
        if args.command == "show":
            return dispatch_show(args, client, output_mode=args.output)
        if args.command == "fetch":
            return dispatch_fetch(args, client, output_mode=args.output)
        if args.command == "resolve":
            return dispatch_resolve(args, client, output_mode=args.output)
        if args.command == "ids":
            return dispatch_ids(args, client, output_mode=args.output)
        if args.command == "stats":
            return dispatch_stats(args, client, output_mode=args.output)
        if args.command == "inspect":
            return dispatch_inspect(args, client, output_mode=args.output)
        if args.command == "raw":
            return dispatch_raw(args, client, output_mode=args.output)

    raise ValueError(f"Unknown command: {args.command}")


def dispatch_model(args: argparse.Namespace, client: BiomodelsClient, *, output_mode: str) -> int:
    if args.model_command == "get":
        if args.api_format == "json":
            data = model_get(client, args.model_id)
            print(render_output(data, output_mode=output_mode).content)
        else:
            payload = client.get_text(
                f"/{args.model_id}",
                params={"format": args.api_format},
                accept=api_format_to_accept(args.api_format),
            )
            print(payload)
        return 0
    if args.model_command == "files":
        if args.api_format == "json":
            data = model_files(client, args.model_id)
            print(render_output(data, output_mode=output_mode).content)
        else:
            payload = client.get_text(
                f"/model/files/{args.model_id}",
                params={"format": args.api_format},
                accept=api_format_to_accept(args.api_format),
            )
            print(payload)
        return 0
    if args.model_command == "identifiers":
        if args.api_format == "json":
            data = model_identifiers(client)
            if (
                args.limit is not None
                and isinstance(data, dict)
                and isinstance(data.get("models"), list)
            ):
                data = {**data, "models": data["models"][: args.limit]}
            print(render_output(data, output_mode=output_mode).content)
        else:
            payload = client.get_text(
                "/model/identifiers",
                params={"format": args.api_format},
                accept=api_format_to_accept(args.api_format),
            )
            print(payload)
        return 0
    if args.model_command == "download":
        output = model_download(client, args.model_id, args.filename, args.output_path)
        print(str(output))
        return 0
    raise ValueError(f"Unknown model subcommand: {args.model_command}")


def dispatch_search(args: argparse.Namespace, client: BiomodelsClient, *, output_mode: str) -> int:
    if args.search_command == "query":
        if args.api_format == "json":
            data = search_models(
                client,
                query=args.query,
                offset=args.offset,
                num_results=args.num_results,
                sort=args.sort,
            )
            print(render_output(data, output_mode=output_mode).content)
        else:
            params: dict[str, Any] = {"query": args.query, "format": args.api_format}
            if args.offset is not None:
                params["offset"] = args.offset
            if args.num_results is not None:
                params["numResults"] = args.num_results
            if args.sort is not None:
                params["sort"] = args.sort
            raw_payload = client.get_text(
                "/search",
                params=params,
                accept=api_format_to_accept(args.api_format),
            )
            print(raw_payload)
        return 0
    if args.search_command == "all":
        models = search_all_models(
            client,
            query=args.query,
            page_size=args.page_size,
            sort=args.sort,
            limit=args.limit,
        )
        payload: Any = (
            models if output_mode == "jsonl" else {"matches": len(models), "models": models}
        )
        print(render_output(payload, output_mode=output_mode).content)
        return 0
    if args.search_command == "download":
        output = search_download(client, args.models, args.output_path)
        print(str(output))
        return 0
    raise ValueError(f"Unknown search subcommand: {args.search_command}")


def dispatch_params(args: argparse.Namespace, client: BiomodelsClient, *, output_mode: str) -> int:
    if args.params_command == "search":
        if args.api_format == "json":
            data = parameter_search(
                client,
                query=args.query,
                start=args.start,
                size=args.size,
                sort=args.sort,
            )
            print(render_output(data, output_mode=output_mode).content)
        else:
            params: dict[str, Any] = {"format": args.api_format}
            if args.query is not None:
                params["query"] = args.query
            if args.start is not None:
                params["start"] = args.start
            if args.size is not None:
                params["size"] = args.size
            if args.sort is not None:
                params["sort"] = args.sort
            payload = client.get_text(
                "/parameterSearch/search",
                params=params,
                accept=api_format_to_accept(args.api_format),
            )
            print(payload)
        return 0
    if args.params_command == "grep":
        selected_fields = [item.strip() for item in args.fields.split(",")] if args.fields else None
        data = parameter_grep(
            client,
            query=args.query,
            start=args.start,
            size=args.size,
            sort=args.sort,
            model_filter=args.model,
            entity_filter=args.entity,
            organism_filter=args.organism,
            fields=selected_fields,
            limit=args.limit,
        )
        print(render_output(data, output_mode=output_mode).content)
        return 0
    raise ValueError(f"Unknown params subcommand: {args.params_command}")


def dispatch_find(args: argparse.Namespace, client: BiomodelsClient, *, output_mode: str) -> int:
    normalized_query, strategy = normalize_find_query(args.query, default_field=args.field)
    models = search_all_models(
        client,
        query=normalized_query,
        page_size=min(args.limit, DEFAULT_PAGE_SIZE) if args.limit else DEFAULT_PAGE_SIZE,
        sort=args.sort,
        limit=args.limit,
    )
    payload: Any = {
        "query": normalized_query,
        "strategy": strategy,
        "matches": len(models),
        "models": models,
    }
    if output_mode == "jsonl":
        payload = models
    print(render_output(payload, output_mode=output_mode).content)
    return 0


def dispatch_show(args: argparse.Namespace, client: BiomodelsClient, *, output_mode: str) -> int:
    payload = show_model(client, args.model_id, include_full_files=args.full)
    print(render_output(payload, output_mode=output_mode).content)
    return 0


def dispatch_fetch(args: argparse.Namespace, client: BiomodelsClient, *, output_mode: str) -> int:
    _ = output_mode
    if args.fetch_command == "model":
        filename: str | None = None
        output_path = args.output_path
        if args.main_xml:
            files_payload = model_files(client, args.model_id)
            filename = choose_main_xml_filename(files_payload)
            if filename is None:
                raise ValueError("No downloadable main file found for model")
            if output_path is None:
                output_path = Path(filename)
        else:
            if output_path is None:
                output_path = Path(f"{args.model_id}.omex")

        assert output_path is not None
        target = model_download(client, args.model_id, filename, output_path)
        print(str(target))
        return 0

    if args.fetch_command == "query":
        matches = search_all_models(
            client,
            query=args.query,
            page_size=min(args.limit, DEFAULT_PAGE_SIZE) if args.limit else DEFAULT_PAGE_SIZE,
            sort=args.sort,
            limit=args.limit,
        )
        model_ids = [
            str(item.get("id")) for item in matches if isinstance(item, dict) and item.get("id")
        ]
        if not model_ids:
            raise ValueError("No models found for query")
        target = search_download(client, model_ids, args.output_path)
        print(str(target))
        return 0

    raise ValueError(f"Unknown fetch subcommand: {args.fetch_command}")


def dispatch_resolve(args: argparse.Namespace, client: BiomodelsClient, *, output_mode: str) -> int:
    payload = resolve_models(client, args.model_ids, family=args.family)
    print(render_output(payload, output_mode=output_mode).content)
    return 0


def dispatch_ids(args: argparse.Namespace, client: BiomodelsClient, *, output_mode: str) -> int:
    payload = filter_identifiers(
        model_identifiers(client),
        prefixes=args.prefix,
        limit=args.limit,
    )
    print(render_output(payload, output_mode=output_mode).content)
    return 0


def dispatch_inspect(args: argparse.Namespace, client: BiomodelsClient, *, output_mode: str) -> int:
    if args.inspect_command != "query":
        raise ValueError(f"Unknown inspect subcommand: {args.inspect_command}")

    normalized_query, strategy = normalize_find_query(args.query, default_field=args.field)
    payload: dict[str, Any] = {
        "input": args.query,
        "normalized_query": normalized_query,
        "strategy": strategy,
        "valid": True,
    }
    if args.validate:
        validation = search_models(
            client,
            query=normalized_query,
            offset=0,
            num_results=1,
            sort=None,
        )
        payload["matches"] = validation.get("matches") if isinstance(validation, dict) else None
    print(render_output(payload, output_mode=output_mode).content)
    return 0


def dispatch_stats(args: argparse.Namespace, client: BiomodelsClient, *, output_mode: str) -> int:
    if args.stats_command != "query":
        raise ValueError(f"Unknown stats subcommand: {args.stats_command}")
    payload = query_stats(client, query=args.query)
    print(render_output(payload, output_mode=output_mode).content)
    return 0


def dispatch_mapping(
    args: argparse.Namespace,
    client: BiomodelsClient,
    *,
    family: str,
    output_mode: str,
) -> int:
    cmd = getattr(args, f"{family}_command")
    if family == "p2m":
        if cmd == "missing":
            if args.api_format == "json":
                data = p2m_missing(client)
            else:
                payload = client.get_text(
                    "/p2m/missing",
                    params={"format": args.api_format},
                    accept=api_format_to_accept(args.api_format),
                )
                print(payload)
                return 0
        elif cmd == "representative":
            if args.api_format == "json":
                data = p2m_representative(client, args.model)
            else:
                payload = client.get_text(
                    "/p2m/representative",
                    params={"model": args.model, "format": args.api_format},
                    accept=api_format_to_accept(args.api_format),
                )
                print(payload)
                return 0
        elif cmd == "representatives":
            if args.api_format == "json":
                data = p2m_representatives(client, args.model_ids)
            else:
                payload = client.get_text(
                    "/p2m/representatives",
                    params={"modelIds": ",".join(args.model_ids), "format": args.api_format},
                    accept=api_format_to_accept(args.api_format),
                )
                print(payload)
                return 0
        else:
            raise ValueError(f"Unknown {family} subcommand: {cmd}")
    elif family == "pdgsmm":
        if cmd == "missing":
            if args.api_format == "json":
                data = pdgsmm_missing(client)
            else:
                payload = client.get_text(
                    "/pdgsmm/missing",
                    params={"format": args.api_format},
                    accept=api_format_to_accept(args.api_format),
                )
                print(payload)
                return 0
        elif cmd == "representative":
            if args.api_format == "json":
                data = pdgsmm_representative(client, args.model)
            else:
                payload = client.get_text(
                    "/pdgsmm/representative",
                    params={"model": args.model, "format": args.api_format},
                    accept=api_format_to_accept(args.api_format),
                )
                print(payload)
                return 0
        elif cmd == "representatives":
            if args.api_format == "json":
                data = pdgsmm_representatives(client, args.model_ids)
            else:
                payload = client.get_text(
                    "/pdgsmm/representatives",
                    params={"modelIds": ",".join(args.model_ids), "format": args.api_format},
                    accept=api_format_to_accept(args.api_format),
                )
                print(payload)
                return 0
        else:
            raise ValueError(f"Unknown {family} subcommand: {cmd}")
    else:
        raise ValueError(f"Unknown family: {family}")

    print(render_output(data, output_mode=output_mode).content)
    return 0


def dispatch_raw(args: argparse.Namespace, client: BiomodelsClient, *, output_mode: str) -> int:
    params = parse_key_value_pairs(args.param)
    status_code, headers, body = client.request_raw(
        method=args.method,
        path=args.path,
        params=params or None,
        accept=args.accept,
    )
    if output_mode == "text":
        print(f"status: {status_code}")
        print(f"content-type: {headers.get('content-type', '-')}")
        print(body.decode("utf-8", errors="replace"))
    elif output_mode == "json":
        payload = {
            "status": status_code,
            "headers": headers,
            "body": body.decode("utf-8", errors="replace"),
        }
        print(render_output(payload, output_mode="json").content)
    else:
        print(body.decode("utf-8", errors="replace"))
    return 0
