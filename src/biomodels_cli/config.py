"""Configuration loading and validation."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .exceptions import ConfigError

DEFAULT_BASE_URL = "https://www.biomodels.org/"
DEFAULT_TIMEOUT = 30.0


@dataclass(frozen=True)
class Config:
    base_url: str
    timeout: float


def default_config_path() -> Path:
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg_config_home).expanduser() if xdg_config_home else Path.home() / ".config"
    return base / "biomodels-cli" / "config.json"


def _normalize_base_url(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ConfigError("Base URL cannot be empty")
    if not normalized.startswith(("http://", "https://")):
        raise ConfigError("Base URL must start with http:// or https://")
    return normalized if normalized.endswith("/") else f"{normalized}/"


def _parse_timeout(value: float | int | str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError("Timeout must be a valid number") from exc
    if parsed <= 0:
        raise ConfigError("Timeout must be greater than 0")
    return parsed


def _read_config_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"Unable to read config file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in config file: {path}") from exc
    if not isinstance(payload, dict):
        raise ConfigError("Config file root must be a JSON object")
    return payload


def load_config(
    *,
    base_url: str | None,
    timeout: float | None,
    config_path: Path | None,
) -> Config:
    cfg_path = config_path if config_path is not None else default_config_path()
    file_config = _read_config_file(cfg_path)

    env_base_url = os.environ.get("BIOMODELS_BASE_URL")
    env_timeout = os.environ.get("BIOMODELS_TIMEOUT")

    chosen_base_url = (
        base_url
        if base_url is not None
        else env_base_url
        if env_base_url is not None
        else file_config.get("base_url", DEFAULT_BASE_URL)
    )
    raw_timeout: float | int | str = (
        timeout
        if timeout is not None
        else env_timeout
        if env_timeout is not None
        else file_config.get("timeout", DEFAULT_TIMEOUT)
    )

    return Config(
        base_url=_normalize_base_url(str(chosen_base_url)), timeout=_parse_timeout(raw_timeout)
    )
