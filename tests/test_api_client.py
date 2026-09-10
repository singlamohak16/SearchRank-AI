"""Transport-only tests for the Streamlit API client."""

from __future__ import annotations

import io
import json
from urllib.error import HTTPError, URLError

import pytest

from searchrank_ai.api_client import APIClient, APIClientError


class FakeResponse:
    def __init__(self, payload) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_client_sends_json_to_the_api_without_business_logic() -> None:
    calls = []

    def opener(request, *, timeout):
        calls.append((request, timeout))
        return FakeResponse({"results": []})

    client = APIClient("http://127.0.0.1:8000/", opener=opener)
    result = client.search({"query": "phone", "constraints": {}})

    request, timeout = calls[0]
    assert result == {"results": []}
    assert request.full_url == "http://127.0.0.1:8000/search"
    assert request.method == "POST"
    assert json.loads(request.data) == {"query": "phone", "constraints": {}}
    assert timeout == 30


def test_client_encodes_product_ids_as_one_path_segment() -> None:
    calls = []

    def opener(request, *, timeout):
        calls.append(request)
        return FakeResponse({"product_id": "91mobiles:phone one"})

    client = APIClient("https://api.example.test", opener=opener)

    assert client.product("91mobiles:phone one")["product_id"] == "91mobiles:phone one"
    assert calls[0].full_url.endswith("/products/91mobiles%3Aphone%20one")


def test_client_surfaces_safe_api_and_connection_errors() -> None:
    body = io.BytesIO(
        json.dumps({"error": {"message": "Search artefacts are unavailable."}}).encode()
    )

    def http_failure(_request, *, timeout):
        raise HTTPError("https://example.test", 503, "unavailable", {}, body)

    with pytest.raises(APIClientError, match="Search artefacts are unavailable"):
        APIClient("https://example.test", opener=http_failure).health()

    def connection_failure(_request, *, timeout):
        raise URLError("offline")

    with pytest.raises(APIClientError, match="Could not connect"):
        APIClient("https://example.test", opener=connection_failure).health()


@pytest.mark.parametrize("url", ["", "localhost:8000", "file:///tmp/api"])
def test_client_rejects_non_http_urls(url: str) -> None:
    with pytest.raises(ValueError, match="http"):
        APIClient(url)
