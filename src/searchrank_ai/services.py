"""Runtime service assembly kept outside the FastAPI presentation layer."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from searchrank_ai.agent_models import AgentOutcome
from searchrank_ai.agent_tools import (
    CatalogueSearchTool,
    EvidenceVerificationTool,
    ProductDetailsTool,
)
from searchrank_ai.config import AppConfig
from searchrank_ai.llm import build_llm_provider
from searchrank_ai.retrieval import (
    HybridRetriever,
    RetrievalMode,
    RetrievalResult,
    SearchConstraints,
)
from searchrank_ai.semantic import SentenceTransformerEncoder
from searchrank_ai.storage import PostgresStorage, ProductLookup
from searchrank_ai.workflow import AgentWorkflow

LOGGER = logging.getLogger(__name__)


class SearchService(Protocol):
    def search(
        self,
        query: str,
        *,
        mode: RetrievalMode,
        constraints: SearchConstraints,
        alpha: float,
        limit: int,
    ) -> Sequence[RetrievalResult]: ...


class QueryService(Protocol):
    def invoke(
        self, user_request: str, *, conversation_context: Sequence[str] = ()
    ) -> AgentOutcome: ...


class ProductService(Protocol):
    def get_product_details(self, product_ids: Sequence[str]) -> ProductLookup: ...


@dataclass(slots=True)
class AppServices:
    """The independently available services exposed by the HTTP layer."""

    search: SearchService | None = None
    query: QueryService | None = None
    products: ProductService | None = None
    errors: dict[str, str] = field(default_factory=dict)
    _closers: tuple[Callable[[], None], ...] = field(default=(), repr=False)

    @property
    def components(self) -> dict[str, bool]:
        return {
            "search": self.search is not None,
            "query": self.query is not None,
            "products": self.products is not None,
        }

    def close(self) -> None:
        for closer in reversed(self._closers):
            closer()


def build_application_services(config: AppConfig | None = None) -> AppServices:
    """Load configured local artefacts and expose every component that is ready."""
    active = config or AppConfig.from_environment()
    services = AppServices()

    retriever: HybridRetriever | None = None
    retrieval_paths = {
        "catalogue": active.catalogue_path,
        "BM25 index": active.bm25_index_path,
        "semantic index": active.semantic_index_path,
    }
    missing_paths = [label for label, path in retrieval_paths.items() if not path.is_file()]
    if missing_paths:
        missing = ", ".join(missing_paths)
        services.errors["search"] = f"Missing local retrieval files: {missing}."
    else:
        try:
            encoder = SentenceTransformerEncoder(
                device=active.embedding_device,
                local_files_only=active.embedding_local_only,
            )
            retriever = HybridRetriever.from_paths(
                active.catalogue_path,
                active.bm25_index_path,
                active.semantic_index_path,
                encoder,
            )
            services.search = retriever
        except Exception:
            LOGGER.exception("Search service initialization failed")
            services.errors["search"] = (
                "Search artefacts or the embedding model could not be loaded."
            )

    storage: PostgresStorage | None = None
    if active.database_url is None:
        services.errors["products"] = "SEARCHRANK_DATABASE_URL is not configured."
    else:
        try:
            storage = PostgresStorage.connect(active.database_url)
            services.products = storage
            services._closers = (storage.close,)
        except Exception:
            LOGGER.exception("Product storage initialization failed")
            services.errors["products"] = "PostgreSQL product storage could not be connected."

    if retriever is None:
        services.errors["query"] = "The query workflow requires the search service."
    elif storage is None:
        services.errors["query"] = "The query workflow requires product storage."
    elif active.llm_provider == "mock":
        services.errors["query"] = (
            "The mock LLM is test-only; configure a real provider for interactive queries."
        )
    else:
        try:
            services.query = AgentWorkflow(
                build_llm_provider(active),
                CatalogueSearchTool(retriever),
                ProductDetailsTool(storage),
                EvidenceVerificationTool(),
            )
        except Exception:
            LOGGER.exception("Query workflow initialization failed")
            services.errors["query"] = "The agent workflow could not be initialized."

    return services
