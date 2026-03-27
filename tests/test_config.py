from __future__ import annotations

import json
from pathlib import Path

import pytest

from biomodels_cli.config import DEFAULT_BASE_URL, load_config
from biomodels_cli.exceptions import ConfigError


def test_load_config_uses_defaults_when_no_sources() -> None:
    cfg = load_config(base_url=None, timeout=None, config_path=Path("/tmp/does-not-exist.json"))
    assert cfg.base_url == DEFAULT_BASE_URL
    assert cfg.timeout > 0


def test_load_config_applies_precedence_cli_over_env_over_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(
        json.dumps({"base_url": "https://from-file.example", "timeout": 55}), encoding="utf-8"
    )
    monkeypatch.setenv("BIOMODELS_BASE_URL", "https://from-env.example")
    monkeypatch.setenv("BIOMODELS_TIMEOUT", "66")

    cfg = load_config(base_url="https://from-cli.example", timeout=77.0, config_path=cfg_file)
    assert cfg.base_url == "https://from-cli.example/"
    assert cfg.timeout == 77.0


def test_load_config_uses_env_when_no_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(
        json.dumps({"base_url": "https://from-file.example", "timeout": 55}), encoding="utf-8"
    )
    monkeypatch.setenv("BIOMODELS_BASE_URL", "https://from-env.example")
    monkeypatch.setenv("BIOMODELS_TIMEOUT", "66")

    cfg = load_config(base_url=None, timeout=None, config_path=cfg_file)
    assert cfg.base_url == "https://from-env.example/"
    assert cfg.timeout == 66.0


def test_invalid_base_url_raises(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps({"base_url": "ftp://invalid"}), encoding="utf-8")

    with pytest.raises(ConfigError):
        load_config(base_url=None, timeout=None, config_path=cfg_file)


def test_invalid_json_config_raises(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text("{ invalid json", encoding="utf-8")

    with pytest.raises(ConfigError):
        load_config(base_url=None, timeout=None, config_path=cfg_file)
