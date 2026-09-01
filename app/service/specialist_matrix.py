"""Fixture-first execution of the four structured research specialist tracks."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from urllib.parse import quote
from typing import Literal, Self

from pydantic import Field, model_validator

from app.contracts.evidence import ContractModel, NonEmptyStr
from app.orchestration import (
    ResearchClaimSpec,
    ResearchNodeRequest,
    ResearchNodeSpec,
    ResearchRunExecutionResult,
    build_research_evidence_pipeline,
    build_research_plan,
    create_research_run,
    execute_research_run,
)
from app.providers import FixtureFinancialProvider, ProviderRequest
from app.research import (
    ResearchSpecialistMatrix,
    ResearchSpecialistMatrixRequest,
    ValidationClaim,
)
from app.research.pipeline import ResearchEvidencePipelineResult


_DEFAULT_MATRIX_ROOT = Path(__file__).resolve().parent.parent / "fixtures" / "research"
_DEFAULT_MANIFEST = _DEFAULT_MATRIX_ROOT / "specialist_matrix.json"
_DEFAULT_PROVIDER_DIR = _DEFAULT_MATRIX_ROOT / "providers"


class SpecialistMatrixError(RuntimeError):
    """Safe refusal for an invalid or unavailable specialist matrix."""


class SpecialistMatrixOutput(ContractModel):
    """Closed run and evidence-pipeline output without recommendation semantics."""

    schema_version: Literal["research-specialist-matrix-output.v1"] = (
        "research-specialist-matrix-output.v1"
    )
    matrix: ResearchSpecialistMatrix
    request_id: NonEmptyStr
    owner_id: NonEmptyStr
    execution: ResearchRunExecutionResult
    pipeline: ResearchEvidencePipelineResult

    @model_validator(mode="after")
    def validate_output(self) -> Self:
        if self.matrix.owner_id != self.owner_id:
            raise ValueError("matrix owner does not match output owner")
        if self.execution.state.owner_id != self.owner_id:
            raise ValueError("execution owner does not match output owner")
        if self.execution.state.request_id != self.request_id:
            raise ValueError("execution request does not match output request")
        if self.pipeline.owner_id != self.owner_id:
            raise ValueError("pipeline owner does not match output owner")
        if self.pipeline.run_id != self.execution.state.run_id:
            raise ValueError("pipeline run does not match execution run")
        if self.pipeline.request_id != self.request_id:
            raise ValueError("pipeline request does not match output request")
        if self.pipeline.trace.recommendations:
            raise ValueError("specialist matrix must not produce recommendations")
        return self


def _safe_decimal(value: object) -> Decimal:
    if isinstance(value, bool) or value is None or isinstance(value, (Mapping, list, tuple)):
        raise ValueError("evidence value is not a scalar")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("evidence value is not a Decimal") from exc
    if not parsed.is_finite():
        raise ValueError("evidence value must be finite")
    return parsed


class FixtureResearchSpecialistMatrixService:
    """Run a packaged four-track matrix through the existing research pipeline."""

    def __init__(
        self,
        *,
        manifest_path: str | Path = _DEFAULT_MANIFEST,
        provider_dir: str | Path = _DEFAULT_PROVIDER_DIR,
    ) -> None:
        self._manifest_path = Path(manifest_path)
        self._provider_dir = Path(provider_dir)
        try:
            payload = json.loads(self._manifest_path.read_text(encoding="utf-8"))
            self._template = ResearchSpecialistMatrix.model_validate(payload)
        except Exception as exc:
            raise SpecialistMatrixError("specialist matrix could not be loaded") from exc
        if not self._provider_dir.exists() or not self._provider_dir.is_dir():
            raise SpecialistMatrixError("specialist provider fixtures are unavailable")

    @property
    def matrix_id(self) -> str:
        return self._template.matrix_id

    def matrix_template(self, owner_id: str) -> ResearchSpecialistMatrix:
        """Return the manifest rebound and revalidated for one owner."""

        try:
            request = ResearchSpecialistMatrixRequest.model_validate(
                {
                    "matrix_id": self._template.matrix_id,
                    "request_id": "template",
                    "owner_id": owner_id,
                    "generated_at": self._template.generated_at,
                }
            )
            nodes = tuple(
                node.model_copy(update={"owner_id": request.owner_id})
                for node in self._template.nodes
            )
            return ResearchSpecialistMatrix.model_validate(
                {
                    **self._template.model_dump(mode="python"),
                    "owner_id": request.owner_id,
                    "nodes": nodes,
                }
            )
        except Exception as exc:
            raise SpecialistMatrixError("specialist matrix template was refused") from exc

    @staticmethod
    def _plan(matrix: ResearchSpecialistMatrix):
        nodes = tuple(
            ResearchNodeSpec(
                node_id=node.node_id,
                owner_id=matrix.owner_id,
                node_kind=node.node_kind,
                required=node.required,
                dependencies=node.dependencies,
                timeout_ms=min(node.timeout_ms, matrix.budget_ms),
            )
            for node in matrix.nodes
        )
        return build_research_plan(matrix.owner_id, matrix.scope_description, nodes)

    @staticmethod
    def _requests(matrix: ResearchSpecialistMatrix) -> dict[str, ResearchNodeRequest]:
        return {
            node.node_id: ResearchNodeRequest(
                node_id=node.node_id,
                request=ProviderRequest(
                    request_id=node.request_id,
                    operation=node.operation,
                    subject=node.subject,
                    required_fields=node.required_fields,
                    parameters=node.parameters,
                    timeout_ms=min(node.timeout_ms, matrix.budget_ms),
                ),
            )
            for node in matrix.nodes
        }

    @staticmethod
    def _claim_specs(
        matrix: ResearchSpecialistMatrix,
        execution: ResearchRunExecutionResult,
    ) -> tuple[ResearchClaimSpec, ...]:
        specs: list[ResearchClaimSpec] = []
        for representative in matrix.claims():
            source_lineages = {
                (node.source, node.lineage_id)
                for node in matrix.nodes
                if node.claim_id == representative.claim_id
            }
            observation_ids = tuple(
                sorted(
                    observation.observation_id
                    for observation in execution.observations
                    if (
                        (observation.source, observation.lineage_id) in source_lineages
                        and observation.subject == representative.subject
                        and observation.metric == representative.metric
                        and observation.unit == representative.unit
                        and observation.period == representative.period
                    )
                )
            )
            claim = ValidationClaim(
                claim_id=representative.claim_id,
                owner_id=matrix.owner_id,
                subject=representative.subject,
                metric=representative.metric,
                unit=representative.unit,
                period=representative.period,
                expected_value=representative.expected_value,
            )
            specs.append(
                ResearchClaimSpec(
                    claim=claim,
                    finding_kind=representative.finding_kind,
                    finding_severity=representative.finding_severity,
                    statement=representative.finding_statement,
                    observation_ids=observation_ids,
                )
            )
        return tuple(specs)

    @staticmethod
    def _check_evidence_integrity(
        matrix: ResearchSpecialistMatrix,
        execution: ResearchRunExecutionResult,
    ) -> None:
        """Ensure a complete run contains exactly the declared source fields."""

        expected = {
            (
                node.source,
                node.record_id,
                node.lineage_id,
                node.metric,
                node.unit,
                node.period,
            )
            for node in matrix.nodes
        }
        actual: set[tuple[str, str, str, str, str, str]] = set()
        for evidence in execution.evidence:
            try:
                _safe_decimal(evidence.value)
            except ValueError as exc:
                raise SpecialistMatrixError("specialist evidence is not a scalar") from exc
            matching = [
                node
                for node in matrix.nodes
                if node.source == evidence.source
                and node.lineage_id == evidence.lineage_id
                and node.metric == evidence.field
                and node.unit == evidence.unit
                and node.period == evidence.period
            ]
            if len(matching) != 1:
                raise SpecialistMatrixError("specialist evidence source identity drifted")
            node = matching[0]
            if quote(node.record_id, safe="") not in evidence.evidence_id:
                raise SpecialistMatrixError("specialist evidence record identity drifted")
            actual.add(
                (
                    node.source,
                    node.record_id,
                    node.lineage_id,
                    evidence.field,
                    evidence.unit or "",
                    evidence.period or "",
                )
            )
        if actual != expected:
            raise SpecialistMatrixError("specialist evidence set drifted from matrix")

    async def run(
        self,
        request: ResearchSpecialistMatrixRequest,
    ) -> SpecialistMatrixOutput:
        """Execute one owner-scoped, deterministic matrix without side effects."""

        try:
            request = ResearchSpecialistMatrixRequest.model_validate(
                request.model_dump(mode="python")
                if isinstance(request, ResearchSpecialistMatrixRequest)
                else request
            )
        except Exception as exc:
            raise SpecialistMatrixError("specialist matrix request was refused") from exc
        if request.matrix_id != self._template.matrix_id:
            raise SpecialistMatrixError("requested specialist matrix is unavailable")

        try:
            matrix = self.matrix_template(request.owner_id)
            plan = self._plan(matrix)
            state = create_research_run(
                plan,
                request.request_id,
                matrix.budget_ms,
                request.generated_at,
            )
            clock = lambda: request.generated_at
            execution = await execute_research_run(
                state,
                FixtureFinancialProvider(fixture_dir=self._provider_dir, clock=clock),
                self._requests(matrix),
                started_at=request.generated_at,
                clock=clock,
            )
            if execution.state.status.value == "COMPLETED":
                self._check_evidence_integrity(matrix, execution)
            pipeline = build_research_evidence_pipeline(
                execution,
                self._claim_specs(matrix, execution),
            )
            return SpecialistMatrixOutput(
                matrix=matrix,
                request_id=request.request_id,
                owner_id=request.owner_id,
                execution=execution,
                pipeline=pipeline,
            )
        except SpecialistMatrixError:
            raise
        except Exception as exc:
            raise SpecialistMatrixError("specialist matrix execution was refused") from exc


__all__ = [
    "FixtureResearchSpecialistMatrixService",
    "SpecialistMatrixError",
    "SpecialistMatrixOutput",
]
