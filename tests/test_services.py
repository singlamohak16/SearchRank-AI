"""Component-aware production assembly tests without external services."""

from pathlib import Path

import searchrank_ai.services as service_module
from searchrank_ai.config import AppConfig
from searchrank_ai.services import build_application_services


def test_missing_retrieval_files_are_reported_without_loading_a_model(
    tmp_path: Path, monkeypatch
) -> None:
    def unexpected_encoder(*_args, **_kwargs):
        raise AssertionError("the embedding model must not load before file checks")

    monkeypatch.setattr(service_module, "SentenceTransformerEncoder", unexpected_encoder)
    config = AppConfig(
        catalogue_path=tmp_path / "catalogue.csv",
        bm25_index_path=tmp_path / "bm25.json",
        semantic_index_path=tmp_path / "semantic.npz",
    )

    services = build_application_services(config)

    assert services.components == {"search": False, "query": False, "products": False}
    assert services.errors["search"] == (
        "Missing local retrieval files: catalogue, BM25 index, semantic index."
    )
    assert "SEARCHRANK_DATABASE_URL" in services.errors["products"]
    assert "search service" in services.errors["query"]


def test_ready_components_are_wired_and_owned_storage_is_closed(
    tmp_path: Path, monkeypatch
) -> None:
    paths = [tmp_path / name for name in ("catalogue.csv", "bm25.json", "semantic.npz")]
    for path in paths:
        path.touch()

    retriever = object()
    provider = object()
    query = object()
    closed = []

    class Storage:
        def close(self):
            closed.append(True)

    storage = Storage()
    monkeypatch.setattr(service_module, "SentenceTransformerEncoder", lambda **_kwargs: object())
    monkeypatch.setattr(
        service_module.HybridRetriever,
        "from_paths",
        lambda *_args: retriever,
    )
    monkeypatch.setattr(
        service_module.PostgresStorage,
        "connect",
        lambda _database_url: storage,
    )
    monkeypatch.setattr(service_module, "build_llm_provider", lambda _config: provider)
    monkeypatch.setattr(
        service_module,
        "AgentWorkflow",
        lambda built_provider, *_args: query if built_provider is provider else None,
    )
    config = AppConfig(
        database_url="postgresql://example.test/searchrank",
        llm_provider="openai",
        llm_model="test-model",
        llm_api_key="test-key",
        catalogue_path=paths[0],
        bm25_index_path=paths[1],
        semantic_index_path=paths[2],
    )

    services = build_application_services(config)

    assert services.search is retriever
    assert services.products is storage
    assert services.query is query
    assert services.errors == {}
    services.close()
    assert closed == [True]
