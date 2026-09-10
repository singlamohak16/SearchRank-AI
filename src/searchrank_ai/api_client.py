"""Small JSON client used by Streamlit; it contains no search business logic."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class APIClientError(RuntimeError):
    """A safe message returned by the API or its transport."""


class APIClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 30,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        normalized = base_url.strip().rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("API URL must start with http:// or https://")
        if timeout_seconds <= 0:
            raise ValueError("timeout must be positive")
        self.base_url = normalized
        self.timeout_seconds = timeout_seconds
        self._opener = opener

    @staticmethod
    def _error_message(payload: object, fallback: str) -> str:
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict) and isinstance(error.get("message"), str):
                return error["message"]
        return fallback

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        try:
            with self._opener(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            try:
                value = json.loads(error.read().decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                value = None
            message = self._error_message(value, f"API request failed with status {error.code}.")
            raise APIClientError(message) from error
        except (URLError, TimeoutError) as error:
            raise APIClientError("Could not connect to the SearchRank-AI API.") from error
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise APIClientError("The API returned an invalid JSON response.") from error

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def search(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/search", payload)

    def query(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/query", payload)

    def product(self, product_id: str) -> dict[str, Any]:
        from urllib.parse import quote

        return self._request("GET", f"/products/{quote(product_id, safe='')}")
