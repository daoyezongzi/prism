"""Fixture-first Advisor query orchestration over existing deterministic modules."""

from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path
from hashlib import sha256
from typing import Literal, Self

from pydantic import Field, model_validator

from app.allocation import build_allocation_envelope
from app.contracts.evidence import ContractModel, FindingSeverity, NonEmptyStr
from app.gates import (
    REQUIRED_DISCLOSURES,
    AdvisoryCandidate,
    evaluate_decision_gates,
)
from app.orchestration import (
    ResearchClaimSpec,
    ResearchNodeSpec,
    build_research_evidence_pipeline,
    build_research_plan,
    create_research_run,
    execute_research_run,
)
from app.portfolio import PortfolioImportBundle, calculate_exposure
from app.profile import (
    RiskProfile,
    build_profile_draft,
    finalize_profile,
)
from app.providers import (
    FixtureFinancialProvider,
    FrozenDict,
    ProviderOperation,
    ProviderRequest,
)
from app.recommendation import compose_recommendations
from app.research import ResearchNodeKind, ValidationClaim
from app.risk import assess_risk_budget, calculate_concentration
from app.service.contracts import (
    AdvisorQueryOutput,
    AdvisorQueryRequest,
    AdvisorQueryTemplate,
)
from app.store.contracts import build_decision_event


_DEFAULT_FIXTURE_ROOT = Path(__file__).resolve().parent.parent / "fixtures" / "advisor"
_DEFAULT_MANIFEST = _DEFAULT_FIXTURE_ROOT / "two_lineage_research.json"
_DEFAULT_PROVIDER_DIR = _DEFAULT_FIXTURE_ROOT / "providers"
_DEFAULT_TEMPLATE = _DEFAULT_FIXTURE_ROOT / "query_template.json"


class AdvisorQueryError(RuntimeError):
    """A safe, expected refusal while loading or executing a fixture query."""


def _stable_id(prefix: str, *parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}:" + sha256(payload).hexdigest()[:32]


class _ClaimTemplate(ContractModel):
    claim_id: NonEmptyStr
    subject: NonEmptyStr
    metric: NonEmptyStr
    unit: NonEmptyStr
    period: NonEmptyStr
    expected_value: Decimal


class _FindingTemplate(ContractModel):
    kind: NonEmptyStr
    severity: FindingSeverity
    statement: NonEmptyStr


class _CandidateTemplate(ContractModel):
    statement: NonEmptyStr
    rationale: NonEmptyStr
    invalidation_conditions: tuple[NonEmptyStr, ...] = Field(min_length=1)


class _SourceTemplate(ContractModel):
    node_id: NonEmptyStr
    node_kind: ResearchNodeKind
    operation: ProviderOperation
    request_id: NonEmptyStr
    subject: NonEmptyStr
    required_fields: tuple[NonEmptyStr, ...] = Field(min_length=1)
    parameters: FrozenDict = Field(default_factory=FrozenDict)
    source: NonEmptyStr
    record_id: NonEmptyStr
    lineage_id: NonEmptyStr
    value: Decimal


class _FixtureManifest(ContractModel):
    schema_version: Literal["advisor-research-fixture.v1"]
    fixture_id: NonEmptyStr
    source: NonEmptyStr
    scope_description: NonEmptyStr
    budget_ms: int = Field(gt=0)
    claim: _ClaimTemplate
    finding: _FindingTemplate
    candidate: _CandidateTemplate
    sources: tuple[_SourceTemplate, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_manifest(self) -> Self:
        if self.source != "offline-test-only":
            raise ValueError("advisor fixture source must be offline-test-only")
        node_ids = [item.node_id for item in self.sources]
        request_ids = [item.request_id for item in self.sources]
        lineage_ids = [item.lineage_id for item in self.sources]
        if len(set(node_ids)) != len(node_ids):
            raise ValueError("advisor fixture node IDs must be unique")
        if len(set(request_ids)) != len(request_ids):
            raise ValueError("advisor fixture request IDs must be unique")
        if len(set(lineage_ids)) != len(lineage_ids):
            raise ValueError("advisor fixture lineage IDs must be unique")
        if any(source.subject != self.claim.subject for source in self.sources):
            raise ValueError("advisor fixture sources must share claim subject")
        if any(source.operation != ProviderOperation.COMPANY_DATA for source in self.sources):
            raise ValueError("advisor fixture uses only COMPANY_DATA sources")
        serialized = self.model_dump_json().casefold()
        if any(
            token in serialized
            for token in (
                "api_key",
                "authorization",
                "password",
                "private_key",
                "secret",
                "credential",
                "cookie",
            )
        ):
            raise ValueError("advisor fixture must not contain sensitive fields")
        return self


class FixtureAdvisorQueryService:
    """Run one bounded, offline query and return a closed composition result."""

    def __init__(
        self,
        *,
        manifest_path: str | Path = _DEFAULT_MANIFEST,
        provider_dir: str | Path = _DEFAULT_PROVIDER_DIR,
        template_path: str | Path = _DEFAULT_TEMPLATE,
    ) -> None:
        self._manifest_path = Path(manifest_path)
        self._provider_dir = Path(provider_dir)
        self._template_path = Path(template_path)
        try:
            manifest_payload = json.loads(
                self._manifest_path.read_text(encoding="utf-8")
            )
            template_payload = json.loads(
                self._template_path.read_text(encoding="utf-8")
            )
            self._manifest = _FixtureManifest.model_validate(manifest_payload)
            self._template = AdvisorQueryTemplate.model_validate(template_payload)
            if self._template.fixture_id != self._manifest.fixture_id:
                raise ValueError("advisor template fixture does not match manifest")
        except Exception as exc:
            raise AdvisorQueryError("advisor fixture could not be loaded") from exc
        if not self._provider_dir.exists() or not self._provider_dir.is_dir():
            raise AdvisorQueryError("advisor provider fixtures are unavailable")

    @property
    def fixture_id(self) -> str:
        return self._manifest.fixture_id

    @staticmethod
    def _rebind_portfolio_owner(
        portfolio: PortfolioImportBundle,
        owner_id: str,
    ) -> PortfolioImportBundle:
        position_snapshot = portfolio.position_snapshot
        rebound_positions = tuple(
            position.model_copy(update={"owner_id": owner_id})
            for position in position_snapshot.positions
        )
        rebound_snapshot = position_snapshot.model_copy(
            update={"owner_id": owner_id, "positions": rebound_positions}
        )
        rebound_funds = tuple(
            snapshot.model_copy(
                update={
                    "owner_id": owner_id,
                    "holdings": tuple(snapshot.holdings),
                }
            )
            for snapshot in portfolio.fund_holdings
        )
        return portfolio.model_copy(
            update={
                "owner_id": owner_id,
                "position_snapshot": rebound_snapshot,
                "fund_holdings": rebound_funds,
            }
        )

    def query_template(self, owner_id: str) -> AdvisorQueryTemplate:
        """Return synthetic defaults rebound and revalidated for one owner."""

        try:
            questionnaire = self._template.questionnaire.model_copy(
                update={"owner_id": owner_id}
            )
            portfolio = self._rebind_portfolio_owner(
                self._template.portfolio,
                owner_id,
            )
            return AdvisorQueryTemplate.model_validate(
                {
                    **self._template.model_dump(mode="python"),
                    "questionnaire": questionnaire,
                    "portfolio": portfolio,
                }
            )
        except Exception as exc:
            raise AdvisorQueryError("advisor query template was refused") from exc

    def _profile(self, request: AdvisorQueryRequest) -> RiskProfile:
        try:
            draft = build_profile_draft(request.questionnaire)
            return finalize_profile(
                draft,
                profile_id=_stable_id(
                    "advisor-profile",
                    request.questionnaire.owner_id,
                    request.query_id,
                    request.questionnaire.questionnaire_id,
                ),
                profile_version=1,
                created_at=request.generated_at,
            )
        except Exception as exc:
            raise AdvisorQueryError("risk profile could not be scored") from exc

    def _research_inputs(
        self,
        request: AdvisorQueryRequest,
    ) -> tuple[object, object, object]:
        manifest = self._manifest
        owner_id = request.questionnaire.owner_id
        nodes = tuple(
            ResearchNodeSpec(
                node_id=source.node_id,
                owner_id=owner_id,
                node_kind=source.node_kind,
                required=True,
                timeout_ms=min(1000, manifest.budget_ms),
            )
            for source in manifest.sources
        )
        plan = build_research_plan(owner_id, manifest.scope_description, nodes)
        state = create_research_run(
            plan,
            _stable_id("advisor-research-request", request.query_id),
            manifest.budget_ms,
            request.generated_at,
        )
        requests = {
            source.node_id: ProviderRequest(
                request_id=source.request_id,
                operation=source.operation,
                subject=source.subject,
                required_fields=source.required_fields,
                parameters=source.parameters,
                timeout_ms=min(1000, manifest.budget_ms),
            )
            for source in manifest.sources
        }
        claim = ValidationClaim(
            claim_id=_stable_id("advisor-claim", request.query_id, manifest.claim.claim_id),
            owner_id=owner_id,
            subject=manifest.claim.subject,
            metric=manifest.claim.metric,
            unit=manifest.claim.unit,
            period=manifest.claim.period,
            expected_value=manifest.claim.expected_value,
        )
        return state, requests, claim

    async def run(self, request: AdvisorQueryRequest) -> AdvisorQueryOutput:
        try:
            request = AdvisorQueryRequest.model_validate(
                request.model_dump(mode="python")
                if isinstance(request, AdvisorQueryRequest)
                else request
            )
        except Exception as exc:
            raise AdvisorQueryError("advisor query was refused") from exc
        if request.fixture_id != self._manifest.fixture_id:
            raise AdvisorQueryError("requested advisor fixture is unavailable")
        profile = self._profile(request)
        exposure = calculate_exposure(
            request.portfolio,
            request_id=_stable_id("advisor-exposure-request", request.query_id),
            calculated_at=request.generated_at,
        )
        concentration = calculate_concentration(exposure)
        assessment = assess_risk_budget(profile, concentration)
        allocation = build_allocation_envelope(
            profile, exposure, concentration, assessment
        )

        state, requests, claim = self._research_inputs(request)
        try:
            provider = FixtureFinancialProvider(
                fixture_dir=self._provider_dir,
                clock=lambda: request.generated_at,
            )
            execution = await execute_research_run(
                state,
                provider,
                requests,
                started_at=request.generated_at,
                clock=lambda: request.generated_at,
            )
        except Exception as exc:
            raise AdvisorQueryError("fixture research execution was refused") from exc

        manifest = self._manifest
        if execution.state.status.value == "COMPLETED":
            expected_evidence = {
                (
                    source.source,
                    source.record_id,
                    source.lineage_id,
                    manifest.claim.metric,
                    manifest.claim.unit,
                    manifest.claim.period,
                    source.value,
                )
                for source in manifest.sources
            }
            actual_evidence: list[tuple[str, str, str, str, str, str, Decimal]] = []
            try:
                for evidence in execution.evidence:
                    matching_source = next(
                        (
                            source
                            for source in manifest.sources
                            if source.source == evidence.source
                            and source.lineage_id == evidence.lineage_id
                        ),
                        None,
                    )
                    if matching_source is None:
                        raise ValueError("unknown source lineage")
                    actual_evidence.append(
                        (
                            evidence.source,
                            matching_source.record_id,
                            evidence.lineage_id or "",
                            evidence.field,
                            evidence.unit or "",
                            evidence.period or "",
                            Decimal(str(evidence.value)),
                        )
                    )
            except Exception as exc:
                raise AdvisorQueryError(
                    "fixture research evidence failed integrity check"
                ) from exc
            if len(actual_evidence) != len(expected_evidence) or set(
                actual_evidence
            ) != expected_evidence:
                raise AdvisorQueryError("fixture research evidence failed integrity check")

        claim_spec = ResearchClaimSpec(
            claim=claim,
            finding_kind=manifest.finding.kind,
            finding_severity=manifest.finding.severity,
            statement=manifest.finding.statement,
        )
        try:
            pipeline = build_research_evidence_pipeline(execution, (claim_spec,))
        except Exception as exc:
            raise AdvisorQueryError("fixture research validation was refused") from exc
        finding_ids = (
            tuple(item.finding_id for item in pipeline.trace.findings)
            or (_stable_id("finding-pending", request.query_id),)
        )
        candidate = AdvisoryCandidate(
            candidate_id=_stable_id("advisor-candidate", request.query_id),
            owner_id=profile.owner_id,
            statement=manifest.candidate.statement,
            rationale=manifest.candidate.rationale,
            finding_ids=finding_ids,
            invalidation_conditions=manifest.candidate.invalidation_conditions,
            disclosure_codes=REQUIRED_DISCLOSURES,
        )
        decision_gate = evaluate_decision_gates(
            profile, pipeline, assessment, allocation, candidate
        )
        try:
            result = compose_recommendations(
                profile=profile,
                portfolio=request.portfolio,
                exposure=exposure,
                concentration=concentration,
                assessment=assessment,
                allocation=allocation,
                pipeline=pipeline,
                candidate=candidate,
                decision_gate=decision_gate,
                generated_at=request.generated_at,
            )
        except Exception as exc:
            raise AdvisorQueryError("recommendation composition was refused") from exc
        return AdvisorQueryOutput(
            query_id=request.query_id,
            owner_id=request.questionnaire.owner_id,
            profile_id=profile.profile_id,
            research_run_id=execution.state.run_id,
            status=result.status,
            result=result,
        )


__all__ = ["AdvisorQueryError", "FixtureAdvisorQueryService"]
