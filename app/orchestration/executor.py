"""Fixture-friendly asynchronous execution for the bounded research run.

The executor is intentionally a thin adapter.  It delegates all state changes to
the Phase 7 transition functions, delegates provider budgets to
``execute_with_budget``, and returns normalized Evidence plus scalar
ResearchObservations for later validation/bridging phases.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from hashlib import sha256
from math import isfinite
from typing import Literal, Self

from pydantic import Field, model_validator

from app.contracts.evidence import (
    ContractModel,
    Evidence,
    EvidenceQualityStatus,
    NonEmptyStr,
)
from app.providers import (
    FinancialProvider,
    ProviderRequest,
    ProviderResult,
    ProviderServingMode,
    ProviderStatus,
    ProviderExecutionPolicy,
    execute_with_budget,
    normalize_result_to_evidence,
)
from app.research import (
    ResearchNodeIssue,
    ResearchNodeIssueCode,
    ResearchNodeResult,
    ResearchNodeStatus,
    ResearchObservation,
    allowed_operations_for_node,
)

from app.orchestration.contracts import (
    ResearchNodeRun,
    ResearchNodeRunStatus,
    ResearchRunState,
)
from app.orchestration.state_machine import (
    finish_research_run,
    record_node_result,
    start_research_run,
)


class ExecutionIssueCode(StrEnum):
    """Safe preflight issue categories for an invalid execution request."""

    INVALID_REQUEST_SET = "INVALID_REQUEST_SET"
    SENSITIVE_METADATA = "SENSITIVE_METADATA"


_SENSITIVE_SUBSTRINGS = (
    "api_key",
    "apikey",
    "authorization",
    "password",
    "private_key",
    "secret",
    "token",
    "credential",
    "cookie",
)

def _contains_sensitive(value: str) -> bool:
    normalized = value.casefold().replace("-", "_")
    return any(item in normalized for item in _SENSITIVE_SUBSTRINGS)


def _contains_sensitive_value(value: object) -> bool:
    if isinstance(value, str):
        return _contains_sensitive(value)
    if isinstance(value, Mapping):
        return any(
            _contains_sensitive(str(key)) or _contains_sensitive_value(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(_contains_sensitive_value(item) for item in value)
    return False


def _safe_identifier(value: str) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= 256
        and not _contains_sensitive(value)
        and all(character.isalnum() or character in "_.:/-%" for character in value)
    )


def _stable_id(prefix: str, *parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}:" + sha256(payload).hexdigest()[:32]


def _decimal_value(value: object) -> Decimal | None:
    if isinstance(value, bool) or value is None or isinstance(value, (list, tuple, dict)):
        return None
    if not isinstance(value, (str, int, float, Decimal)):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not parsed.is_finite():
        return None
    if isinstance(value, float) and not isfinite(value):
        return None
    return parsed


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


class ResearchNodeRequest(ContractModel):
    """Provider request bound to one static plan node."""

    schema_version: Literal["research-node-request.v1"] = "research-node-request.v1"
    node_id: NonEmptyStr
    request: ProviderRequest


class ResearchRunExecutionResult(ContractModel):
    """Final run state plus normalized inputs for downstream validation."""

    schema_version: Literal["research-run-execution-result.v1"] = (
        "research-run-execution-result.v1"
    )
    state: ResearchRunState
    evidence: tuple[Evidence, ...] = Field(default_factory=tuple)
    observations: tuple[ResearchObservation, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_closure(self) -> Self:
        serialized = self.model_dump_json().casefold()
        if any(item in serialized for item in _SENSITIVE_SUBSTRINGS):
            raise ValueError("execution result must not contain sensitive fields")
        evidence_ids = [item.evidence_id for item in self.evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("execution evidence must not contain duplicate IDs")
        observation_ids = [item.observation_id for item in self.observations]
        if len(observation_ids) != len(set(observation_ids)):
            raise ValueError("execution observations must not contain duplicate IDs")
        observation_evidence_ids = [item.evidence_id for item in self.observations]
        if len(observation_evidence_ids) != len(set(observation_evidence_ids)):
            raise ValueError("one Evidence ID must not have multiple observations")
        evidence_by_id = {item.evidence_id: item for item in self.evidence}
        for observation in self.observations:
            evidence = evidence_by_id.get(observation.evidence_id)
            if evidence is None:
                raise ValueError(
                    f"observation {observation.observation_id!r} references unknown evidence"
                )
            if observation.owner_id != self.state.owner_id:
                raise ValueError("observation owner_id does not match execution owner")
            if (
                observation.provider != evidence.provider
                or observation.source != evidence.source
                or observation.metric != evidence.field
                or observation.unit != evidence.unit
                or observation.period != evidence.period
                or observation.lineage_id != evidence.lineage_id
                or observation.observed_at != evidence.observed_at
                or observation.retrieved_at != evidence.retrieved_at
                or observation.quality_status != evidence.quality_status
            ):
                raise ValueError(
                    f"observation {observation.observation_id!r} does not match evidence"
                )
            parsed_evidence = _decimal_value(evidence.value)
            if parsed_evidence is None or parsed_evidence != observation.value:
                raise ValueError(
                    f"observation {observation.observation_id!r} value does not match evidence"
                )
        return self


def _request_items(
    node_requests: Mapping[str, ProviderRequest] | Iterable[ResearchNodeRequest],
) -> tuple[ResearchNodeRequest, ...]:
    if isinstance(node_requests, Mapping):
        items: list[ResearchNodeRequest] = []
        for node_id, request in node_requests.items():
            if isinstance(request, ResearchNodeRequest):
                if request.node_id != node_id:
                    raise ValueError("mapping key does not match node request node_id")
                items.append(request)
            else:
                items.append(ResearchNodeRequest(node_id=node_id, request=request))
        return tuple(items)
    return tuple(node_requests)


def _index_requests(
    state: ResearchRunState,
    node_requests: Mapping[str, ProviderRequest] | Iterable[ResearchNodeRequest],
) -> dict[str, ResearchNodeRequest]:
    items = _request_items(node_requests)
    ids = [item.node_id for item in items]
    expected = set(state.plan.topological_order)
    if len(ids) != len(set(ids)):
        raise ValueError("node requests must not contain duplicate node_id")
    if set(ids) != expected:
        raise ValueError("node requests must match every plan node exactly")
    by_id = {item.node_id: item for item in items}
    for node in state.nodes:
        request = by_id[node.node_id].request
        if not _safe_identifier(request.subject):
            raise ValueError("node request subject contains a disallowed field")
        if request.operation not in allowed_operations_for_node(node.node_kind):
            raise ValueError("node request operation does not match node kind")
    if _contains_sensitive(state.owner_id):
        raise ValueError("research owner metadata contains a disallowed field")
    return by_id


def _bounded_request(request: ProviderRequest, node: ResearchNodeRun) -> ProviderRequest:
    timeout_ms = min(request.timeout_ms, node.timeout_ms)
    if timeout_ms == request.timeout_ms:
        return request
    payload = request.model_dump(mode="python")
    payload["timeout_ms"] = timeout_ms
    return ProviderRequest.model_validate(payload)


def _safe_missing_fields(result: ProviderResult) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                field_name
                for field_name in result.missing_fields
                if _safe_identifier(field_name)
            }
        )
    )


def _issue(
    code: ResearchNodeIssueCode,
    message: str,
    *,
    field_name: str | None = None,
) -> ResearchNodeIssue:
    return ResearchNodeIssue(code=code, safe_message=message, field_name=field_name)


def _failed_result(
    *,
    state: ResearchRunState,
    node: ResearchNodeRun,
    subject: str,
    completed_at: datetime,
    code: ResearchNodeIssueCode,
    message: str,
) -> ResearchNodeResult:
    return ResearchNodeResult(
        request_id=state.request_id,
        node_id=node.node_id,
        owner_id=state.owner_id,
        node_kind=node.node_kind,
        subject=subject,
        completed_at=completed_at,
        status=ResearchNodeStatus.FAILED,
        issues=(_issue(code, message),),
    )


def _observation_id(
    state: ResearchRunState,
    node: ResearchNodeRun,
    evidence: Evidence,
) -> str:
    return _stable_id(
        "observation",
        state.owner_id,
        node.node_id,
        evidence.evidence_id,
    )


def _normalize_provider_output(
    *,
    state: ResearchRunState,
    node: ResearchNodeRun,
    request: ProviderRequest,
    provider_result: ProviderResult,
    completed_at: datetime,
) -> tuple[ResearchNodeResult, tuple[Evidence, ...], tuple[ResearchObservation, ...]]:
    subject = request.subject
    try:
        normalized = normalize_result_to_evidence(provider_result)
    except Exception:
        return (
            _failed_result(
                state=state,
                node=node,
                subject=subject,
                completed_at=completed_at,
                code=ResearchNodeIssueCode.SOURCE_UNAVAILABLE,
                message="provider output could not be normalized safely",
            ),
            (),
            (),
        )

    safe_evidence: list[Evidence] = []
    observations: list[ResearchObservation] = []
    invalid_scalar_count = 0
    for item in normalized:
        metadata = (
            item.evidence_id,
            item.provider,
            item.source,
            item.field,
        )
        if any(not _safe_identifier(value) for value in metadata):
            invalid_scalar_count += 1
            continue
        if _contains_sensitive_value(item.value):
            invalid_scalar_count += 1
            continue
        if item.lineage_id is not None and not _safe_identifier(item.lineage_id):
            invalid_scalar_count += 1
            continue
        if (
            (item.unit is not None and not _safe_identifier(item.unit))
            or (item.period is not None and not _safe_identifier(item.period))
        ):
            invalid_scalar_count += 1
            continue
        safe_evidence.append(item)
        parsed = _decimal_value(item.value)
        if parsed is None:
            # Textual fields (for example a fund name) remain auditable Evidence,
            # but the scalar research contract intentionally does not treat them
            # as numeric observations.
            continue
        if item.unit is None or item.period is None:
            invalid_scalar_count += 1
            continue
        observations.append(
            ResearchObservation(
                observation_id=_observation_id(state, node, item),
                owner_id=state.owner_id,
                evidence_id=item.evidence_id,
                subject=subject,
                metric=item.field,
                value=parsed,
                unit=item.unit,
                period=item.period,
                provider=item.provider,
                source=item.source,
                lineage_id=item.lineage_id,
                quality_status=item.quality_status,
                observed_at=item.observed_at,
                retrieved_at=item.retrieved_at,
            )
        )

    safe_evidence_tuple = tuple(sorted(safe_evidence, key=lambda item: item.evidence_id))
    observations_tuple = tuple(sorted(observations, key=lambda item: item.evidence_id))
    safe_missing = _safe_missing_fields(provider_result)
    issues: list[ResearchNodeIssue] = []
    if provider_result.serving_mode == ProviderServingMode.CACHE_STALE_FALLBACK:
        issues.append(
            _issue(
                ResearchNodeIssueCode.SOURCE_UNAVAILABLE,
                "provider served stale cached data because fresh data was unavailable",
            )
        )
        if invalid_scalar_count:
            issues.append(
                _issue(
                    ResearchNodeIssueCode.INVALID_OBSERVATION,
                    "one or more stale provider fields were not usable as scalar observations",
                )
            )
        if not observations_tuple:
            return (
                _failed_result(
                    state=state,
                    node=node,
                    subject=subject,
                    completed_at=completed_at,
                    code=ResearchNodeIssueCode.INVALID_OBSERVATION,
                    message="stale provider output contained no usable scalar observation",
                ),
                safe_evidence_tuple,
                (),
            )
        return (
            ResearchNodeResult(
                request_id=state.request_id,
                node_id=node.node_id,
                owner_id=state.owner_id,
                node_kind=node.node_kind,
                subject=subject,
                completed_at=completed_at,
                status=ResearchNodeStatus.PARTIAL,
                observations=observations_tuple,
                missing_fields=safe_missing,
                issues=tuple(issues[:2]),
                provider=provider_result.provider,
                provider_serving_mode=provider_result.serving_mode,
                provider_cache_age_ms=provider_result.cache_age_ms,
            ),
            safe_evidence_tuple,
            observations_tuple,
        )
    if provider_result.status == ProviderStatus.SUCCESS:
        if not observations_tuple:
            return (
                _failed_result(
                    state=state,
                    node=node,
                    subject=subject,
                    completed_at=completed_at,
                    code=ResearchNodeIssueCode.INVALID_OBSERVATION,
                    message="provider returned no usable scalar observation",
                ),
                safe_evidence_tuple,
                (),
            )
        if invalid_scalar_count:
            issues.append(
                _issue(
                    ResearchNodeIssueCode.INVALID_OBSERVATION,
                    "one or more provider fields were not usable as scalar observations",
                )
            )
        if issues:
            return (
                ResearchNodeResult(
                    request_id=state.request_id,
                    node_id=node.node_id,
                    owner_id=state.owner_id,
                    node_kind=node.node_kind,
                    subject=subject,
                    completed_at=completed_at,
                    status=ResearchNodeStatus.PARTIAL,
                    observations=observations_tuple,
                    issues=tuple(issues),
                    provider=provider_result.provider,
                    provider_serving_mode=provider_result.serving_mode,
                    provider_cache_age_ms=provider_result.cache_age_ms,
                ),
                safe_evidence_tuple,
                observations_tuple,
            )
        return (
            ResearchNodeResult(
                request_id=state.request_id,
                node_id=node.node_id,
                owner_id=state.owner_id,
                node_kind=node.node_kind,
                subject=subject,
                completed_at=completed_at,
                status=ResearchNodeStatus.COMPLETE,
                observations=observations_tuple,
                provider=provider_result.provider,
                provider_serving_mode=provider_result.serving_mode,
                provider_cache_age_ms=provider_result.cache_age_ms,
            ),
            safe_evidence_tuple,
            observations_tuple,
        )

    if provider_result.status == ProviderStatus.PARTIAL:
        if safe_missing:
            issues.append(
                _issue(
                    ResearchNodeIssueCode.MISSING_FIELDS,
                    "provider returned a partial payload with declared missing fields",
                )
            )
        elif provider_result.issues:
            issues.append(
                _issue(
                    ResearchNodeIssueCode.SOURCE_UNAVAILABLE,
                    "provider returned a partial payload requiring review",
                )
            )
        if invalid_scalar_count:
            issues.append(
                _issue(
                    ResearchNodeIssueCode.INVALID_OBSERVATION,
                    "one or more provider fields were not usable as scalar observations",
                )
            )
        if not observations_tuple:
            return (
                _failed_result(
                    state=state,
                    node=node,
                    subject=subject,
                    completed_at=completed_at,
                    code=ResearchNodeIssueCode.INVALID_OBSERVATION,
                    message="partial provider output contained no usable scalar observation",
                ),
                safe_evidence_tuple,
                (),
            )
        if not issues:
            issues.append(
                _issue(
                    ResearchNodeIssueCode.SOURCE_UNAVAILABLE,
                    "provider returned a partial payload requiring review",
                )
            )
        return (
            ResearchNodeResult(
                request_id=state.request_id,
                node_id=node.node_id,
                owner_id=state.owner_id,
                node_kind=node.node_kind,
                subject=subject,
                completed_at=completed_at,
                status=ResearchNodeStatus.PARTIAL,
                observations=observations_tuple,
                missing_fields=safe_missing,
                issues=tuple(issues[:2]),
                provider=provider_result.provider,
                provider_serving_mode=provider_result.serving_mode,
                provider_cache_age_ms=provider_result.cache_age_ms,
            ),
            safe_evidence_tuple,
            observations_tuple,
        )

    if provider_result.status == ProviderStatus.EMPTY:
        return (
            ResearchNodeResult(
                request_id=state.request_id,
                node_id=node.node_id,
                owner_id=state.owner_id,
                node_kind=node.node_kind,
                subject=subject,
                completed_at=completed_at,
                status=ResearchNodeStatus.EMPTY,
                scope_description="provider returned no records for the requested scope",
                provider=provider_result.provider,
                provider_serving_mode=provider_result.serving_mode,
                provider_cache_age_ms=provider_result.cache_age_ms,
            ),
            (),
            (),
        )

    return (
        _failed_result(
            state=state,
            node=node,
            subject=subject,
            completed_at=completed_at,
            code=ResearchNodeIssueCode.SOURCE_UNAVAILABLE,
            message="provider did not return usable data within the node boundary",
        ),
        (),
        (),
    )


async def _execute_node(
    *,
    state: ResearchRunState,
    node: ResearchNodeRun,
    request: ProviderRequest,
    provider: FinancialProvider,
    clock: Callable[[], datetime],
    policy: ProviderExecutionPolicy | None = None,
) -> tuple[ResearchNodeResult, tuple[Evidence, ...], tuple[ResearchObservation, ...]]:
    subject = request.subject
    started_at = node.started_at or clock()
    _require_aware(started_at, "node started_at")
    now = clock()
    _require_aware(now, "clock time")
    remaining_ms = int((state.deadline_at - now).total_seconds() * 1000)
    if remaining_ms <= 0:
        return (
            _failed_result(
                state=state,
                node=node,
                subject=subject,
                completed_at=max(started_at, now),
                code=ResearchNodeIssueCode.SOURCE_UNAVAILABLE,
                message="research run budget was exhausted before provider execution",
            ),
            (),
            (),
        )
    bounded = _bounded_request(request, node)
    if remaining_ms < bounded.timeout_ms:
        payload = bounded.model_dump(mode="python")
        payload["timeout_ms"] = max(1, remaining_ms)
        bounded = ProviderRequest.model_validate(payload)
    try:
        provider_result = await execute_with_budget(provider, bounded, policy=policy)
        allowed_provider_names = {provider.name}
        if policy is not None and policy.fallback is not None:
            allowed_provider_names.add(policy.fallback.name)
        if provider_result.provider not in allowed_provider_names:
            completed_at = clock()
            if completed_at < started_at:
                completed_at = started_at
            return (
                _failed_result(
                    state=state,
                    node=node,
                    subject=subject,
                    completed_at=completed_at,
                    code=ResearchNodeIssueCode.SOURCE_UNAVAILABLE,
                    message="provider identity did not match the requested boundary",
                ),
                (),
                (),
            )
        completed_at = clock()
        _require_aware(completed_at, "clock time")
        if completed_at < started_at:
            completed_at = started_at
        return _normalize_provider_output(
            state=state,
            node=node,
            request=request,
            provider_result=provider_result,
            completed_at=completed_at,
        )
    except Exception:
        completed_at = clock()
        if completed_at < started_at:
            completed_at = started_at
        return (
            _failed_result(
                state=state,
                node=node,
                subject=subject,
                completed_at=completed_at,
                code=ResearchNodeIssueCode.SOURCE_UNAVAILABLE,
                message="provider execution failed safely",
            ),
            (),
            (),
        )


def _merge_unique(
    target: dict[str, object],
    values: Iterable[object],
    *,
    kind: str,
) -> None:
    for value in values:
        identifier = getattr(value, "evidence_id", None)
        if identifier is None:
            identifier = getattr(value, "observation_id", None)
        if identifier in target:
            raise ValueError(f"duplicate {kind} identifier across research nodes")
        target[identifier] = value


async def execute_research_run(
    state: ResearchRunState,
    provider: FinancialProvider,
    node_requests: Mapping[str, ProviderRequest] | Iterable[ResearchNodeRequest],
    *,
    started_at: datetime | None = None,
    clock: Callable[[], datetime] | None = None,
    policy: ProviderExecutionPolicy | None = None,
) -> ResearchRunExecutionResult:
    """Execute a bounded plan with fixture or live-provider injection.

    No provider-specific data source is selected here.  Callers provide the
    implementation, making the same runner usable with the offline Fixture
    Provider now and a reviewed SkillHub adapter later.
    """

    clock_fn = clock or (lambda: datetime.now(UTC))
    initial_time = started_at or clock_fn()
    _require_aware(initial_time, "started_at")
    requests_by_id = _index_requests(state, node_requests)

    current = start_research_run(state, initial_time)
    evidence_by_id: dict[str, Evidence] = {}
    observation_by_id: dict[str, ResearchObservation] = {}

    while current.status.value == "RUNNING":
        active_nodes = tuple(
            node
            for node in current.nodes
            if node.status == ResearchNodeRunStatus.RUNNING
        )
        if not active_nodes:
            current = finish_research_run(current, clock_fn())
            break
        outcomes = await asyncio.gather(
            *(
                _execute_node(
                    state=current,
                    node=node,
                    request=requests_by_id[node.node_id].request,
                    provider=provider,
                    clock=clock_fn,
                    policy=policy,
                )
                for node in active_nodes
            )
        )
        for node, outcome in zip(active_nodes, outcomes):
            if current.status.value != "RUNNING":
                break
            node_result, node_evidence, node_observations = outcome
            completion_time = clock_fn()
            _require_aware(completion_time, "clock time")
            if node.started_at is not None and completion_time < node.started_at:
                completion_time = node.started_at
            before = next(item for item in current.nodes if item.node_id == node.node_id)
            current = record_node_result(
                current,
                node.node_id,
                node_result,
                completion_time,
            )
            after = next(item for item in current.nodes if item.node_id == node.node_id)
            if after.result == node_result and before.status == ResearchNodeRunStatus.RUNNING:
                _merge_unique(evidence_by_id, node_evidence, kind="evidence")
                _merge_unique(observation_by_id, node_observations, kind="observation")

    return ResearchRunExecutionResult(
        state=current,
        evidence=tuple(sorted(evidence_by_id.values(), key=lambda item: item.evidence_id)),
        observations=tuple(
            sorted(observation_by_id.values(), key=lambda item: item.observation_id)
        ),
    )


run_research = execute_research_run


__all__ = [
    "ExecutionIssueCode",
    "ResearchNodeRequest",
    "ResearchRunExecutionResult",
    "execute_research_run",
    "run_research",
]
