"""Domain exceptions for biomodels-cli."""

from __future__ import annotations


class BiomodelsError(Exception):
    """Base application error."""


class ConfigError(BiomodelsError):
    """Invalid configuration provided by user or environment."""


class ApiError(BiomodelsError):
    """HTTP/API-level error."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class NetworkError(BiomodelsError):
    """Network transport failure."""


class ResponseDecodeError(BiomodelsError):
    """Response body could not be decoded as expected."""
