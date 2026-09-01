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
    AdvisorPortfolioContextRequest,
    AdvisorPortfolioContextResponse,
    AdvisorProfileContextRequest,
    AdvisorProfileContextResponse,
    AdvisorProfileConfirmationRequest,
    AdvisorProfileConfirmationResponse,
    AdvisorProfileProposalRequest,
    AdvisorProfileProposalResponse,
    AdvisorQueryResponse,
    AdvisorQueryTemplateResponse,
    DecisionEventListResponse,
    DecisionEventWriteResponse,
    ErrorResponse,
    ResearchMatrixIssueResponse,
    ResearchMatrixNodeResponse,
    ResearchMatrixResponse,
    ResearchMatrixTemplateResponse,
    ResearchScenarioResponse,
)
from app.recommendation import RecommendationCompositionResult
from app.research import ResearchSpecialistMatrixRequest
from app.stock import (
    StockResearchRequest,
    StockResearchResponse,
    StockResearchTemplateResponse,
)
from app.service import (
    AdvisorIntentRequest,
    AdvisorPlanResponse,
    AdvisorQueryError,
    AdvisorQueryRequest,
    FixtureAdvisorQueryService,
    FixtureResearchSpecialistMatrixService,
    SpecialistMatrixError,
    SpecialistMatrixOutput,
    ProfileConfirmationError,
    confirm_questionnaire,
    IntentPlanningError,
    build_intent_plan,
    ProfileProposalError,
    build_profile_proposal,
    confirm_profile_proposal,
    FixtureStockResearchService,
    StockResearchError,
)
from app.portfolio import PortfolioImportBundle
from app.profile import RiskQuestionnaire
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


def _research_matrix_response(output: SpecialistMatrixOutput) -> ResearchMatrixResponse:
    matrix_by_id = {node.node_id: node for node in output.matrix.nodes}
    response_nodes: list[ResearchMatrixNodeResponse] = []
    for node in output.execution.state.nodes:
        matrix_node = matrix_by_id[node.node_id]
        issues = [
            ResearchMatrixIssueResponse(
                code=issue.code.value,
                safe_message=issue.safe_message,
            )
            for issue in node.issues
        ]
        if node.result is not None:
            issues.extend(
                ResearchMatrixIssueResponse(
                    code=issue.code.value,
                    safe_message=issue.safe_message,
                )
                for issue in node.result.issues
            )
        response_nodes.append(
            ResearchMatrixNodeResponse(
                node_id=node.node_id,
                role=matrix_node.role,
                node_kind=node.node_kind,
                subject=matrix_node.subject,
                required=node.required,
                status=node.status,
                started_at=node.started_at,
                finished_at=node.finished_at,
                issues=tuple(issues),
            )
        )
    return ResearchMatrixResponse(
        matrix_id=output.matrix.matrix_id,
        scenario=ResearchScenarioResponse.model_validate(
            {
                "scenario_id": output.scenario.scenario_id,
                "label": output.scenario.label,
                "description": output.scenario.description,
            }
        ),
        request_id=output.request_id,
        owner_id=output.owner_id,
        run_id=output.execution.state.run_id,
        run_status=output.execution.state.status,
        pipeline_status=output.pipeline.status,
        nodes=tuple(sorted(response_nodes, key=lambda item: item.node_id)),
        validations=output.pipeline.validations,
        issues=output.pipeline.issues,
        trace=output.pipeline.trace,
    )


def create_app(
    store: DecisionEventStore | None = None,
    *,
    clock: Callable[[], datetime] | None = None,
    advisor_service: FixtureAdvisorQueryService | None = None,
    specialist_service: FixtureResearchSpecialistMatrixService | None = None,
    stock_service: FixtureStockResearchService | None = None,
) -> FastAPI:
    """Create an API instance with an explicitly injectable store and clock.

    The default store is process-local memory, so a caller must inject a path-backed
    ``SQLiteDecisionEventStore`` when local persistence across restarts is desired.
    """

    owned_store = store is None
    active_store = store or SQLiteDecisionEventStore(":memory:")
    active_clock = clock or (lambda: datetime.now(UTC))
    active_advisor = advisor_service or FixtureAdvisorQueryService()
    active_specialist = specialist_service or FixtureResearchSpecialistMatrixService()
    active_stock = stock_service or FixtureStockResearchService()

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

    @api.exception_handler(SpecialistMatrixError)
    async def specialist_matrix_error_handler(
        _: Request, __: SpecialistMatrixError
    ) -> JSONResponse:
        return _error_response(400, "RESEARCH_MATRIX_ERROR", "research matrix was refused")

    @api.exception_handler(StockResearchError)
    async def stock_research_error_handler(
        _: Request, __: StockResearchError
    ) -> JSONResponse:
        return _error_response(400, "STOCK_RESEARCH_ERROR", "stock research was refused")

    @api.exception_handler(ProfileConfirmationError)
    async def profile_confirmation_error_handler(
        _: Request, __: ProfileConfirmationError
    ) -> JSONResponse:
        return _error_response(
            400,
            "PROFILE_CONTEXT_ERROR",
            "risk profile confirmation was refused",
        )

    @api.exception_handler(IntentPlanningError)
    async def intent_planning_error_handler(
        _: Request, __: IntentPlanningError
    ) -> JSONResponse:
        return _error_response(
            400,
            "INTENT_PLAN_ERROR",
            "advisor intent plan was refused",
        )

    @api.exception_handler(ProfileProposalError)
    async def profile_proposal_error_handler(
        _: Request, __: ProfileProposalError
    ) -> JSONResponse:
        return _error_response(
            400,
            "PROFILE_PROPOSAL_ERROR",
            "profile proposal was refused",
        )

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

    @api.post(
        "/api/v1/advisor/context/portfolio",
        response_model=AdvisorPortfolioContextResponse,
    )
    def confirm_portfolio_context(
        request: AdvisorPortfolioContextRequest,
        owner_id: str = Depends(owner_dependency),
    ) -> AdvisorPortfolioContextResponse:
        if request.portfolio.owner_id != owner_id:
            raise StoreOwnerError("portfolio context owner does not match owner scope")
        try:
            portfolio = PortfolioImportBundle.model_validate(
                request.portfolio.model_dump(mode="python")
            )
            return AdvisorPortfolioContextResponse(
                portfolio=portfolio,
                position_count=len(portfolio.position_snapshot.positions),
                fund_snapshot_count=len(portfolio.fund_holdings),
                holding_count=sum(
                    len(snapshot.holdings) for snapshot in portfolio.fund_holdings
                ),
            )
        except (ValidationError, ValueError) as exc:
            raise AdvisorQueryError("portfolio context was refused") from exc

    @api.post(
        "/api/v1/advisor/context/profile",
        response_model=AdvisorProfileContextResponse,
    )
    def confirm_profile_context(
        request: AdvisorProfileContextRequest,
        owner_id: str = Depends(owner_dependency),
    ) -> AdvisorProfileContextResponse:
        if request.questionnaire.owner_id != owner_id:
            raise StoreOwnerError("profile context owner does not match owner scope")
        try:
            questionnaire = RiskQuestionnaire.model_validate(
                request.questionnaire.model_dump(mode="python")
            )
        except (ValidationError, ValueError) as exc:
            raise ProfileConfirmationError("risk profile confirmation was refused") from exc
        profile = confirm_questionnaire(questionnaire)
        return AdvisorProfileContextResponse(
            questionnaire=questionnaire,
            profile=profile,
        )

    @api.post(
        "/api/v1/advisor/profile-proposals",
        response_model=AdvisorProfileProposalResponse,
    )
    def create_profile_proposal(
        request: AdvisorProfileProposalRequest,
        owner_id: str = Depends(owner_dependency),
    ) -> AdvisorProfileProposalResponse:
        if (
            request.questionnaire.owner_id != owner_id
            or request.extraction.owner_id != owner_id
        ):
            raise StoreOwnerError("profile proposal owner does not match owner scope")
        draft = build_profile_proposal(request.questionnaire, request.extraction)
        return AdvisorProfileProposalResponse(draft=draft)

    @api.post(
        "/api/v1/advisor/profile-proposals/confirm",
        response_model=AdvisorProfileConfirmationResponse,
    )
    def confirm_profile_proposal_endpoint(
        request: AdvisorProfileConfirmationRequest,
        owner_id: str = Depends(owner_dependency),
    ) -> AdvisorProfileConfirmationResponse:
        if (
            request.questionnaire.owner_id != owner_id
            or request.extraction.owner_id != owner_id
        ):
            raise StoreOwnerError("profile confirmation owner does not match owner scope")
        profile = confirm_profile_proposal(
            request.questionnaire,
            request.extraction,
            request.resolutions,
        )
        return AdvisorProfileConfirmationResponse(profile=profile)

    @api.post(
        "/api/v1/advisor/plans",
        response_model=AdvisorPlanResponse,
    )
    def create_advisor_plan(
        request: AdvisorIntentRequest,
        owner_id: str = Depends(owner_dependency),
    ) -> AdvisorPlanResponse:
        if request.owner_id != owner_id:
            raise StoreOwnerError("intent owner does not match owner scope")
        try:
            matrix = active_specialist.matrix_template(owner_id)
            return build_intent_plan(request, matrix)
        except IntentPlanningError:
            raise
        except Exception as exc:
            raise IntentPlanningError("advisor intent plan was refused") from exc

    @api.get(
        "/api/v1/advisor/research-matrix-template",
        response_model=ResearchMatrixTemplateResponse,
    )
    def get_research_matrix_template(
        owner_id: str = Depends(owner_dependency),
    ) -> ResearchMatrixTemplateResponse:
        template = active_specialist.matrix_template(owner_id)
        return ResearchMatrixTemplateResponse(
            matrix_id=template.matrix_id,
            owner_id=template.owner_id,
            generated_at=template.generated_at,
            scope_description=template.scope_description,
            roles=tuple(sorted({node.role for node in template.nodes}, key=lambda item: item.value)),
            node_count=len(template.nodes),
            scenarios=tuple(
                ResearchScenarioResponse.model_validate(
                    {
                        "scenario_id": scenario.scenario_id,
                        "label": scenario.label,
                        "description": scenario.description,
                    }
                )
                for scenario in active_specialist.scenarios
            ),
        )

    @api.post(
        "/api/v1/advisor/research-runs",
        response_model=ResearchMatrixResponse,
    )
    async def create_research_matrix_run(
        request: ResearchSpecialistMatrixRequest,
        owner_id: str = Depends(owner_dependency),
    ) -> ResearchMatrixResponse:
        if request.owner_id != owner_id:
            raise StoreOwnerError("research request owner does not match owner scope")
        try:
            output = await active_specialist.run(request)
        except SpecialistMatrixError:
            raise
        except Exception as exc:
            raise SpecialistMatrixError("specialist matrix execution was refused") from exc
        try:
            if output.owner_id != owner_id:
                raise SpecialistMatrixError("specialist matrix output owner drifted")
            return _research_matrix_response(output)
        except SpecialistMatrixError:
            raise
        except (AttributeError, KeyError, TypeError, ValidationError, ValueError) as exc:
            raise SpecialistMatrixError("specialist matrix output was refused") from exc

    @api.get(
        "/api/v1/advisor/stock-research-template",
        response_model=StockResearchTemplateResponse,
    )
    def get_stock_research_template(
        owner_id: str = Depends(owner_dependency),
    ) -> StockResearchTemplateResponse:
        return active_stock.template(owner_id)

    @api.post(
        "/api/v1/advisor/stock-research-runs",
        response_model=StockResearchResponse,
    )
    async def create_stock_research_run(
        request: StockResearchRequest,
        owner_id: str = Depends(owner_dependency),
    ) -> StockResearchResponse:
        if request.owner_id != owner_id:
            raise StoreOwnerError("stock research request owner does not match owner scope")
        try:
            output = await active_stock.run(request)
        except StockResearchError:
            raise
        except Exception as exc:
            raise StockResearchError("stock research execution was refused") from exc
        if output.owner_id != owner_id:
            raise StockResearchError("stock research output owner drifted")
        return output

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
