"""Static and optional live checks for the Phase 7 container setup."""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import urllib.request
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from searchrank_ai.api import create_app
from searchrank_ai.services import AppServices
from searchrank_ai.storage import PostgresStorage


@pytest.mark.parametrize(
    ("search", "products", "ready"),
    [(True, True, True), (False, True, False), (True, False, False), (False, False, False)],
)
def test_api_container_readiness_requires_search_and_products(
    monkeypatch: pytest.MonkeyPatch, search: bool, products: bool, ready: bool
) -> None:
    compose = Path("compose.yaml").read_text(encoding="utf-8")
    healthcheck = next(line for line in compose.splitlines() if "c=json.load" in line)
    command = json.loads(healthcheck.split("test:", 1)[1].strip())[-1]
    body = json.dumps({"components": {"search": search, "products": products, "query": False}})
    monkeypatch.setattr(urllib.request, "urlopen", lambda *_args, **_kwargs: io.StringIO(body))

    if ready:
        exec(command, {})
    else:
        with pytest.raises(AssertionError):
            exec(command, {})


def test_dockerfile_uses_pinned_python_and_non_root_runtime() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

    assert dockerfile.count("FROM python:3.12-slim") == 2
    assert "USER searchrank" in dockerfile
    assert 'CMD ["python", "-m", "uvicorn"' in dockerfile
    assert "COPY . ." not in dockerfile


def test_missing_schema_fails_actual_container_readiness(monkeypatch) -> None:
    class MissingSchemaConnection:
        def cursor(self):
            raise RuntimeError("missing schema; sensitive driver details")

    storage = PostgresStorage(MissingSchemaConnection())
    services = AppServices(
        search=object(),
        products=storage,
        query=object(),
        _product_readiness=storage.check_readiness,
    )
    with TestClient(create_app(services)) as client:
        health = client.get("/health")
    body = health.json()
    assert body["components"] == {"search": True, "products": False, "query": False}
    assert "sensitive" not in health.text
    compose = Path("compose.yaml").read_text(encoding="utf-8")
    line = next(line for line in compose.splitlines() if "c=json.load" in line)
    command = json.loads(line.split("test:", 1)[1].strip())[-1]
    monkeypatch.setattr(urllib.request, "urlopen", lambda *_a, **_kw: io.StringIO(health.text))
    with pytest.raises(AssertionError):
        exec(command, {})


def test_health_rechecks_storage_and_recovers_without_stale_errors() -> None:
    states = iter([True, False, True])
    services = AppServices(
        search=object(),
        products=object(),
        query=object(),
        _product_readiness=lambda: next(states),
    )
    with TestClient(create_app(services)) as client:
        responses = [client.get("/health").json() for _ in range(3)]
    assert [response["status"] for response in responses] == ["ok", "degraded", "ok"]
    assert responses[-1]["errors"] == {}
    assert services.errors == {}


def test_compose_declares_database_api_ui_and_setup_ingestion() -> None:
    compose = Path("compose.yaml").read_text(encoding="utf-8")

    for service in ("database:", "api:", "ui:", "ingest:"):
        assert f"  {service}" in compose
    assert "pgvector/pgvector:pg16" in compose
    assert "condition: service_healthy" in compose
    assert "./data/processed:/app/data/processed:ro" in compose
    assert "./artifacts:/app/artifacts:ro" in compose
    assert "SEARCHRANK_LLM_API_KEY: ${SEARCHRANK_LLM_API_KEY:-}" in compose


@pytest.mark.integration
def test_docker_compose_configuration_is_accepted_when_docker_is_installed() -> None:
    if shutil.which("docker") is None:
        pytest.skip("Docker is not installed on this machine")

    result = subprocess.run(
        ["docker", "compose", "config", "--quiet"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
