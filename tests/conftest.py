from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture(autouse=True)
def clear_env() -> Iterator[None]:
    original = dict(os.environ)
    for key in ["BIOMODELS_BASE_URL", "BIOMODELS_TIMEOUT", "XDG_CONFIG_HOME"]:
        os.environ.pop(key, None)
    yield
    os.environ.clear()
    os.environ.update(original)
