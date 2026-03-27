"""HTTP transport client for the BioModels API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from .exceptions import ApiError, NetworkError, ResponseDecodeError


class BiomodelsClient:
    """Thin HTTP wrapper around BioModels REST endpoints."""

    def __init__(self, *, base_url: str, timeout: float) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=timeout, follow_redirects=True)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> BiomodelsClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        accept: str = "application/json",
    ) -> httpx.Response:
        headers = {"Accept": accept}
        try:
            response = self._client.request(method, path, params=params, headers=headers)
        except httpx.TimeoutException as exc:
            raise NetworkError("Request timed out. Increase --timeout or retry.") from exc
        except httpx.RequestError as exc:
            raise NetworkError(f"Network error while contacting BioModels: {exc}") from exc

        if response.status_code >= 400:
            detail = _extract_error_detail(response)
            if response.status_code == 401:
                raise ApiError(
                    "Unauthorized request to BioModels API", status_code=response.status_code
                )
            if response.status_code == 404:
                raise ApiError("Resource not found", status_code=response.status_code)
            if response.status_code == 429:
                raise ApiError(
                    "Rate limit reached. Please retry later.", status_code=response.status_code
                )
            message = f"BioModels API error ({response.status_code})"
            if detail:
                message = f"{message}: {detail}"
            raise ApiError(message, status_code=response.status_code)

        return response

    def request_raw(
        self,
        *,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        accept: str = "application/json",
    ) -> tuple[int, dict[str, str], bytes]:
        response = self._request(method, path, params=params, accept=accept)
        headers = {k: v for k, v in response.headers.items()}
        return response.status_code, headers, response.content

    def get_text(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        accept: str,
    ) -> str:
        response = self._request("GET", path, params=params, accept=accept)
        return response.text

    def get_json(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        response = self._request("GET", path, params=params, accept="application/json")
        try:
            return response.json()
        except ValueError as exc:
            raise ResponseDecodeError("Failed to decode JSON response from BioModels") from exc

    def download_file(self, *, path: str, params: dict[str, Any] | None, output_path: Path) -> None:
        response = self._request("GET", path, params=params, accept="application/octet-stream")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)


def _extract_error_detail(response: httpx.Response) -> str | None:
    text = str(response.text).strip()
    if not text:
        return None
    return text[:200]
