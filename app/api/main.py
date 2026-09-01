"""Owner-scoped HTTP API and static explainable workbench."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from app.api.contracts import (
    AdvisorQueryResponse,
    AdvisorQueryTemplateResponse,
    DecisionEventListResponse,
    DecisionEventWriteResponse,
    ErrorResponse,
)
from app.recommendation import RecommendationCompositionResult
from app.service import AdvisorQueryError, AdvisorQueryRequest, FixtureAdvisorQueryService
from app.store import (
    DecisionEvent,
    DecisionEventStore,
    StoreConflictError,
    StoreCorruptError,
    StoreError,
    StoreOwnerError,
    SQLiteDecisionEventStore,
)
from app.store.contracts import build_decision_event


_STATIC_DIR = Path(__file__).parent / "static"


def _error_response(status_code: int, error_code: str, message: str) -> JSONResponse:
    payload = ErrorResponse(error_code=error_code, message=message).model_dump(
        mode="json"
    )
    return JSONResponse(status_code=status_code, content=payload)


def _owner_id_from_header(x_owner_id: str | None) -> str:
    if x_owner_id is None or not isinstance(x_owner_id, str) or not x_owner_id.strip():
        raise StoreOwnerError("owner scope is required")
    return x_owner_id.strip()


def create_app(
    store: DecisionEventStore | None = None,
    *,
    clock: Callable[[], datetime] | None = None,
    advisor_service: FixtureAdvisorQueryService | None = None,
) -> FastAPI:
    """Create an API instance with an explicitly injectable store and clock.

    The default store is process-local memory, so a caller must inject a path-backed
    ``SQLiteDecisionEventStore`` when local persistence across restarts is desired.
    """

    owned_store = store is None
    active_store = store or SQLiteDecisionEventStore(":memory:")
    active_clock = clock or (lambda: datetime.now(UTC))
    active_advisor = advisor_service or FixtureAdvisorQueryService()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            yield
        finally:
            if owned_store:
                active_store.close()

    api = FastAPI(
        title="Prism Decision API",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    api.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    @api.exception_handler(RequestValidationError)
    async def request_validation_handler(
        _: Request, __: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            422,
            "INVALID_INPUT",
            "request failed contract validation",
        )

    @api.exception_handler(StoreOwnerError)
    async def owner_error_handler(_: Request, __: StoreOwnerError) -> JSONResponse:
        return _error_response(403, "OWNER_SCOPE", "owner scope is not allowed")

    @api.exception_handler(StoreConflictError)
    async def conflict_error_handler(
        _: Request, __: StoreConflictError
    ) -> JSONResponse:
        return _error_response(
            409,
            "CONFLICT",
            "decision event already exists with different content",
        )

    @api.exception_handler(StoreCorruptError)
    async def corrupt_error_handler(_: Request, __: StoreCorruptError) -> JSONResponse:
        return _error_response(
            500,
            "CORRUPT_RECORD",
            "stored decision event failed integrity validation",
        )

    @api.exception_handler(StoreError)
    async def store_error_handler(_: Request, __: StoreError) -> JSONResponse:
        return _error_response(400, "STORE_ERROR", "decision event request was refused")

    @api.exception_handler(AdvisorQueryError)
    async def advisor_query_error_handler(
        _: Request, __: AdvisorQueryError
    ) -> JSONResponse:
        return _error_response(400, "ADVISOR_QUERY_ERROR", "advisor query was refused")

    @api.exception_handler(HTTPException)
    async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
        if exc.status_code == 404:
            return _error_response(404, "NOT_FOUND", "decision event was not found")
        return _error_response(exc.status_code, "HTTP_ERROR", "request was refused")

    def owner_dependency(
        x_owner_id: str | None = Header(default=None, alias="X-Owner-ID"),
    ) -> str:
        return _owner_id_from_header(x_owner_id)

    @api.get("/", include_in_schema=False)
    def workbench() -> FileResponse:
        return FileResponse(_STATIC_DIR / "index.html", media_type="text/html")

    @api.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "schema_version": "decision-event.v1"}

    @api.post(
        "/api/v1/decision-events",
        response_model=DecisionEventWriteResponse,
    )
    def create_decision_event(
        result: RecommendationCompositionResult,
        owner_id: str = Depends(owner_dependency),
    ) -> DecisionEventWriteResponse:
        if result.owner_id != owner_id:
            raise StoreOwnerError("result owner does not match owner scope")
        try:
            event = build_decision_event(result, recorded_at=active_clock())
            stored, created = active_store.save(event)
        except (ValidationError, ValueError) as exc:
            raise StoreError("decision event failed contract validation") from exc
        return DecisionEventWriteResponse(event=stored, created=created)

    @api.post(
        "/api/v1/advisor/queries",
        response_model=AdvisorQueryResponse,
    )
    async def create_advisor_query(
        query: AdvisorQueryRequest,
        owner_id: str = Depends(owner_dependency),
    ) -> AdvisorQueryResponse:
        if (
            query.questionnaire.owner_id != owner_id
            or query.portfolio.owner_id != owner_id
        ):
            raise StoreOwnerError("query owner does not match owner scope")
        try:
            output = await active_advisor.run(query)
        except AdvisorQueryError:
            raise
        except Exception as exc:
            raise AdvisorQueryError("advisor query was refused") from exc
        try:
            event = build_decision_event(
                output.result,
                recorded_at=active_clock(),
            )
            stored, created = active_store.save(event)
        except (ValidationError, ValueError) as exc:
            raise StoreError("advisor result failed event validation") from exc
        return AdvisorQueryResponse(
            query_id=output.query_id,
            owner_id=output.owner_id,
            profile_id=output.profile_id,
            research_run_id=output.research_run_id,
            status=output.status.value,
            created=created,
            event=stored,
        )

    @api.get(
        "/api/v1/advisor/query-template",
        response_model=AdvisorQueryTemplateResponse,
    )
    def get_advisor_query_template(
        owner_id: str = Depends(owner_dependency),
    ) -> AdvisorQueryTemplateResponse:
        template = active_advisor.query_template(owner_id)
        return AdvisorQueryTemplateResponse(
            fixture_id=template.fixture_id,
            generated_at=template.generated_at,
            questionnaire=template.questionnaire,
            portfolio=template.portfolio,
        )

    @api.get(
        "/api/v1/decision-events",
        response_model=DecisionEventListResponse,
    )
    def list_decision_events(
        owner_id: str = Depends(owner_dependency),
    ) -> DecisionEventListResponse:
        return DecisionEventListResponse(items=active_store.list(owner_id))

    @api.get(
        "/api/v1/decision-events/{event_id}",
        response_model=DecisionEvent,
    )
    def get_decision_event(
        event_id: str,
        owner_id: str = Depends(owner_dependency),
    ) -> DecisionEvent:
        event = active_store.get(owner_id, event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="not found")
        return event

    return api


app = create_app()


__all__ = ["app", "create_app"]
