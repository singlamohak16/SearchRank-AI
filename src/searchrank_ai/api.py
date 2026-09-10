"""FastAPI entry point for smartphone search, products, and agent queries."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from searchrank_ai.api_models import (
    ErrorBody,
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    ProductResponse,
    QueryRequest,
    QueryResponse,
    SearchRequest,
    SearchResponse,
    SearchResultResponse,
)
from searchrank_ai.config import AppConfig
from searchrank_ai.logging_config import configure_logging
from searchrank_ai.services import AppServices, build_application_services


class APIProblem(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message))
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


def create_app(
    services: AppServices | None = None,
    *,
    service_factory: Callable[[], AppServices] = build_application_services,
) -> FastAPI:
    """Create an app with injectable services for deterministic offline tests."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        active = services
        if active is None:
            config = AppConfig.from_environment()
            configure_logging(config.log_level)
            active = await run_in_threadpool(service_factory)
        app.state.services = active
        try:
            yield
        finally:
            if services is None:
                await run_in_threadpool(active.close)

    app = FastAPI(
        title="SearchRank-AI API",
        version="0.1.0",
        description="Evidence-grounded smartphone search and comparison API.",
        lifespan=lifespan,
    )

    @app.exception_handler(APIProblem)
    async def handle_api_problem(_request: Request, error: APIProblem) -> JSONResponse:
        return _error_response(error.status_code, error.code, error.message)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_request: Request, error: RequestValidationError) -> JSONResponse:
        details = [
            ErrorDetail(
                location=list(issue["loc"]),
                message=issue["msg"],
                type=issue["type"],
            )
            for issue in error.errors()
        ]
        body = ErrorResponse(
            error=ErrorBody(
                code="validation_error",
                message="Request validation failed.",
                details=details,
            )
        )
        return JSONResponse(status_code=422, content=body.model_dump(mode="json"))

    def require_service(request: Request, name: str) -> Any:
        active: AppServices = request.app.state.services
        service = getattr(active, name)
        if service is None:
            message = active.errors.get(name, f"The {name} service is unavailable.")
            raise APIProblem(503, "service_unavailable", message)
        return service

    common_errors = {
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    }

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    async def health(request: Request) -> HealthResponse:
        active: AppServices = request.app.state.services
        components = active.components
        return HealthResponse(
            status="ok" if all(components.values()) else "degraded",
            components=components,
            errors=active.errors,
        )

    @app.post("/search", response_model=SearchResponse, responses=common_errors, tags=["catalogue"])
    async def search(payload: SearchRequest, request: Request) -> SearchResponse:
        service = require_service(request, "search")
        constraints = payload.constraints.to_domain()
        try:
            results = await run_in_threadpool(
                service.search,
                payload.query,
                mode=payload.mode,
                constraints=constraints,
                alpha=payload.alpha,
                limit=payload.limit,
            )
        except ValueError as error:
            raise APIProblem(422, "invalid_search", str(error)) from error
        return SearchResponse(
            query=payload.query,
            mode=payload.mode,
            alpha=payload.alpha,
            constraints=payload.constraints,
            results=[SearchResultResponse.from_domain(result) for result in results],
        )

    @app.post("/query", response_model=QueryResponse, responses=common_errors, tags=["agent"])
    async def query(payload: QueryRequest, request: Request) -> QueryResponse:
        service = require_service(request, "query")
        try:
            outcome = await run_in_threadpool(
                service.invoke,
                payload.request,
                conversation_context=tuple(payload.conversation_context),
            )
        except ValueError as error:
            raise APIProblem(422, "invalid_query", str(error)) from error
        return QueryResponse.from_domain(outcome)

    @app.get(
        "/products/{product_id}",
        response_model=ProductResponse,
        responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
        tags=["catalogue"],
    )
    async def product(product_id: str, request: Request) -> ProductResponse:
        normalized_id = product_id.strip()
        if not normalized_id or len(normalized_id) > 300:
            raise APIProblem(422, "invalid_product_id", "Product ID must not be blank.")
        service = require_service(request, "products")
        try:
            lookup = await run_in_threadpool(service.get_product_details, (normalized_id,))
        except ValueError as error:
            raise APIProblem(422, "invalid_product_id", str(error)) from error
        if not lookup.products:
            raise APIProblem(404, "product_not_found", "No product has that catalogue ID.")
        return ProductResponse.from_domain(lookup.products[0])

    return app


app = create_app()
