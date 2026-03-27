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
    model_download,
    model_files,
    model_get,
    model_identifiers,
    p2m_missing,
    p2m_representative,
    p2m_representatives,
    parameter_search,
    parse_key_value_pairs,
    pdgsmm_missing,
    pdgsmm_representative,
    pdgsmm_representatives,
    render_output,
    search_all_models,
    search_download,
    search_models,
)
from .exceptions import ApiError, BiomodelsError, ConfigError, NetworkError, ResponseDecodeError

DEFAULT_PAGE_SIZE = 100


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
    add_raw_subcommand(subparsers)

    return parser


def add_model_subcommands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    model = subparsers.add_parser("model", help="Model retrieval and download operations")
    model_sub = model.add_subparsers(dest="model_command", required=True)

    get_cmd = model_sub.add_parser("get", help="Fetch model details by model identifier")
    get_cmd.add_argument("model_id", help="Model identifier (e.g., BIOMD0000000123)")

    files_cmd = model_sub.add_parser("files", help="List files associated with a model")
    files_cmd.add_argument("model_id", help="Model identifier")

    identifiers_cmd = model_sub.add_parser("identifiers", help="List all public model identifiers")
    identifiers_cmd.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum identifiers to return",
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


def add_mapping_family_subcommands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser], *, family: str
) -> None:
    grp = subparsers.add_parser(family, help=f"{family.upper()} representative/missing operations")
    grp_sub = grp.add_subparsers(dest=f"{family}_command", required=True)

    grp_sub.add_parser(
        "missing", help=f"List {family.upper()} models no longer directly accessible"
    )

    representative_cmd = grp_sub.add_parser("representative", help="Lookup representative model")
    representative_cmd.add_argument("model", help="Model identifier")

    reps_cmd = grp_sub.add_parser("representatives", help="Lookup representative models in batch")
    reps_cmd.add_argument("model_ids", nargs="+", help="Model identifiers")


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
        if args.command == "raw":
            return dispatch_raw(args, client, output_mode=args.output)

    raise ValueError(f"Unknown command: {args.command}")


def dispatch_model(args: argparse.Namespace, client: BiomodelsClient, *, output_mode: str) -> int:
    if args.model_command == "get":
        data = model_get(client, args.model_id)
        print(render_output(data, output_mode=output_mode).content)
        return 0
    if args.model_command == "files":
        data = model_files(client, args.model_id)
        print(render_output(data, output_mode=output_mode).content)
        return 0
    if args.model_command == "identifiers":
        data = model_identifiers(client)
        if (
            args.limit is not None
            and isinstance(data, dict)
            and isinstance(data.get("models"), list)
        ):
            data = {**data, "models": data["models"][: args.limit]}
        print(render_output(data, output_mode=output_mode).content)
        return 0
    if args.model_command == "download":
        output = model_download(client, args.model_id, args.filename, args.output_path)
        print(str(output))
        return 0
    raise ValueError(f"Unknown model subcommand: {args.model_command}")


def dispatch_search(args: argparse.Namespace, client: BiomodelsClient, *, output_mode: str) -> int:
    if args.search_command == "query":
        data = search_models(
            client,
            query=args.query,
            offset=args.offset,
            num_results=args.num_results,
            sort=args.sort,
        )
        print(render_output(data, output_mode=output_mode).content)
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
        data = parameter_search(
            client,
            query=args.query,
            start=args.start,
            size=args.size,
            sort=args.sort,
        )
        print(render_output(data, output_mode=output_mode).content)
        return 0
    raise ValueError(f"Unknown params subcommand: {args.params_command}")


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
            data = p2m_missing(client)
        elif cmd == "representative":
            data = p2m_representative(client, args.model)
        elif cmd == "representatives":
            data = p2m_representatives(client, args.model_ids)
        else:
            raise ValueError(f"Unknown {family} subcommand: {cmd}")
    elif family == "pdgsmm":
        if cmd == "missing":
            data = pdgsmm_missing(client)
        elif cmd == "representative":
            data = pdgsmm_representative(client, args.model)
        elif cmd == "representatives":
            data = pdgsmm_representatives(client, args.model_ids)
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
