from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.contracts.evidence import EvidenceQualityStatus
from app.orchestration import (
    ResearchNodeRequest,
    ResearchNodeSpec,
    build_research_plan,
    create_research_run,
    execute_research_run,
)
from app.research import ResearchNodeKind
from app.research import ResearchScenarioId, ResearchSpecialistMatrixRequest
from app.service import FixtureResearchSpecialistMatrixService
from app.providers import (
    InMemoryProviderCache,
    ProviderExecutionPolicy,
    ProviderIssue,
    ProviderIssueCode,
    ProviderOperation,
    ProviderRecord,
    ProviderRequest,
    ProviderResult,
    ProviderServingMode,
    ProviderStatus,
    execute_with_budget,
)
from app.providers.fingerprint import compute_request_fingerprint
from app.providers.normalization import normalize_result_to_evidence


NOW = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)


def _request(subject: str = "PUBLIC-FUND-001", *, request_id: str = "req-1") -> ProviderRequest:
    return ProviderRequest(
        request_id=request_id,
        operation=ProviderOperation.FUND_DATA,
        subject=subject,
        required_fields=("fund_name", "weight_pct"),
        parameters={"period": "2026-06-30"},
        timeout_ms=200,
    )


def _success(request: ProviderRequest, provider: str, value: float = 42.0) -> ProviderResult:
    return ProviderResult(
        request_id=request.request_id,
        request_fingerprint=compute_request_fingerprint(request),
        provider=provider,
        status=ProviderStatus.SUCCESS,
        retrieved_at=NOW,
        records=(
            ProviderRecord(
                source=f"{provider}-source",
                record_id="record-1",
                fields={"fund_name": "Synthetic Fund", "weight_pct": value},
                units={"weight_pct": "pct"},
                period="2026-06-30",
                observed_at=NOW,
                lineage_id=f"lineage:{provider}:1",
            ),
        ),
    )


def _failed(request: ProviderRequest, provider: str) -> ProviderResult:
    return ProviderResult(
        request_id=request.request_id,
        request_fingerprint=compute_request_fingerprint(request),
        provider=provider,
        status=ProviderStatus.FAILED,
        retrieved_at=NOW,
        issues=(
            ProviderIssue(
                code=ProviderIssueCode.TRANSPORT_ERROR,
                stage="upstream",
                safe_message="upstream unavailable",
                retriable=True,
            ),
        ),
    )


class _StaticProvider:
    def __init__(self, name: str, status: ProviderStatus = ProviderStatus.SUCCESS) -> None:
        self._name = name
        self.status = status
        self.calls = 0

    @property
    def name(self) -> str:
        return self._name

    async def execute(self, request: ProviderRequest) -> ProviderResult:
        self.calls += 1
        if self.status == ProviderStatus.SUCCESS:
            return _success(request, self.name)
        if self.status == ProviderStatus.FAILED:
            return _failed(request, self.name)
        return ProviderResult(
            request_id=request.request_id,
            request_fingerprint=compute_request_fingerprint(request),
            provider=self.name,
            status=ProviderStatus.EMPTY,
            retrieved_at=NOW,
            scope_description="no matching public records",
        )


def test_serving_mode_requires_age_only_for_cache_modes() -> None:
    request = _request()
    with pytest.raises(ValidationError, match="requires cache_age_ms"):
        ProviderResult.model_validate(
            _success(request, "fixture-provider").model_dump(mode="python")
            | {"serving_mode": ProviderServingMode.CACHE_FRESH}
        )

    with pytest.raises(ValidationError, match="must not contain cache_age_ms"):
        ProviderResult.model_validate(
            _success(request, "fixture-provider").model_dump(mode="python")
            | {"cache_age_ms": 1}
        )


def test_fresh_cache_hit_rebinds_request_id_and_does_not_call_provider_twice() -> None:
    current = [NOW]
    cache = InMemoryProviderCache(ttl_ms=1000, clock=lambda: current[0])
    provider = _StaticProvider("primary-provider")
    policy = ProviderExecutionPolicy(cache=cache)

    async def run() -> tuple[ProviderResult, ProviderResult]:
        first = await execute_with_budget(provider, _request(request_id="req-a"), policy=policy)
        second = await execute_with_budget(provider, _request(request_id="req-b"), policy=policy)
        return first, second

    first, second = asyncio.run(run())
    assert first.serving_mode == ProviderServingMode.DIRECT
    assert second.serving_mode == ProviderServingMode.CACHE_FRESH
    assert first.request_id == "req-a"
    assert second.request_id == "req-b"
    assert second.request_fingerprint == first.request_fingerprint
    assert provider.calls == 1
    assert cache.stats().hits == 1


def test_stale_cache_is_explicit_and_normalizes_to_stale_evidence() -> None:
    current = [NOW]
    cache = InMemoryProviderCache(
        ttl_ms=1000,
        stale_grace_ms=2000,
        clock=lambda: current[0],
    )
    healthy = _StaticProvider("primary-provider")
    failing = _StaticProvider("primary-provider", ProviderStatus.FAILED)
    request = _request()

    async def run() -> ProviderResult:
        await execute_with_budget(healthy, request, policy=ProviderExecutionPolicy(cache=cache))
        current[0] = NOW + timedelta(milliseconds=1500)
        return await execute_with_budget(
            failing,
            request,
            policy=ProviderExecutionPolicy(cache=cache),
        )

    result = asyncio.run(run())
    assert result.status == ProviderStatus.SUCCESS
    assert result.serving_mode == ProviderServingMode.CACHE_STALE_FALLBACK
    assert result.cache_age_ms == 1500
    evidence = normalize_result_to_evidence(result)
    assert evidence
    assert all(item.quality_status == EvidenceQualityStatus.STALE for item in evidence)


def test_fallback_provider_is_marked_and_is_not_written_under_primary_key() -> None:
    primary = _StaticProvider("primary-provider", ProviderStatus.FAILED)
    fallback = _StaticProvider("secondary-provider", ProviderStatus.SUCCESS)
    cache = InMemoryProviderCache(clock=lambda: NOW)
    policy = ProviderExecutionPolicy(cache=cache, fallback=fallback)

    result = asyncio.run(execute_with_budget(primary, _request(), policy=policy))
    assert result.status == ProviderStatus.SUCCESS
    assert result.provider == "secondary-provider"
    assert result.serving_mode == ProviderServingMode.FALLBACK_PROVIDER
    assert primary.calls == 1
    assert fallback.calls == 1
    assert len(cache) == 0


def test_empty_primary_is_not_replaced_by_fallback_or_cached() -> None:
    primary = _StaticProvider("primary-provider", ProviderStatus.EMPTY)
    fallback = _StaticProvider("secondary-provider", ProviderStatus.SUCCESS)
    cache = InMemoryProviderCache(clock=lambda: NOW)
    result = asyncio.run(
        execute_with_budget(
            primary,
            _request(),
            policy=ProviderExecutionPolicy(cache=cache, fallback=fallback),
        )
    )
    assert result.status == ProviderStatus.EMPTY
    assert result.serving_mode == ProviderServingMode.DIRECT
    assert fallback.calls == 0
    assert len(cache) == 0


def test_private_context_bypasses_public_cache_but_remains_executable() -> None:
    provider = _StaticProvider("primary-provider")
    cache = InMemoryProviderCache(clock=lambda: NOW)
    private_request = _request("PUBLIC-FUND-001", request_id="owner-profile-1").model_copy(
        update={"parameters": {"period": "2026-06-30", "owner_id": "owner-a"}}
    )
    result = asyncio.run(
        execute_with_budget(
            provider,
            private_request,
            policy=ProviderExecutionPolicy(cache=cache),
        )
    )
    assert result.status == ProviderStatus.SUCCESS
    assert result.serving_mode == ProviderServingMode.DIRECT
    assert provider.calls == 1
    assert len(cache) == 0
    assert cache.stats().bypasses >= 1


def test_sensitive_provider_payload_is_not_stored_in_cache() -> None:
    request = _request()
    result = _success(request, "primary-provider")
    secret_result = ProviderResult.model_validate(
        result.model_dump(mode="python")
        | {
            "records": (
                ProviderRecord(
                    source="primary-source",
                    record_id="record-secret",
                    fields={"fund_name": "Synthetic Fund", "api_key_value": "redacted"},
                    units={},
                    period="2026-06-30",
                    observed_at=NOW,
                    lineage_id="lineage:primary:secret",
                ),
            )
        }
    )
    cache = InMemoryProviderCache(clock=lambda: NOW)
    assert cache.put("primary-provider", request, secret_result) is False
    assert len(cache) == 0


def test_lru_capacity_evicts_oldest_entry_without_corrupting_payload() -> None:
    cache = InMemoryProviderCache(max_entries=1, clock=lambda: NOW)
    provider = _StaticProvider("primary-provider")
    request_a = _request("PUBLIC-FUND-A")
    request_b = _request("PUBLIC-FUND-B")

    async def run() -> None:
        await execute_with_budget(provider, request_a, policy=ProviderExecutionPolicy(cache=cache))
        await execute_with_budget(provider, request_b, policy=ProviderExecutionPolicy(cache=cache))
        await execute_with_budget(provider, request_a, policy=ProviderExecutionPolicy(cache=cache))

    asyncio.run(run())
    assert provider.calls == 3
    assert cache.stats().evictions == 2
    assert cache.stats().entries == 1


def test_research_executor_propagates_fallback_provider_metadata() -> None:
    primary = _StaticProvider("primary-provider", ProviderStatus.FAILED)
    fallback = _StaticProvider("secondary-provider", ProviderStatus.SUCCESS)
    cache = InMemoryProviderCache(clock=lambda: NOW)
    policy = ProviderExecutionPolicy(cache=cache, fallback=fallback)
    node = ResearchNodeSpec(
        node_id="fund-root",
        owner_id="executor-owner",
        node_kind=ResearchNodeKind.FUND,
        required=True,
        timeout_ms=1000,
    )
    plan = build_research_plan("executor-owner", "resilience run", (node,))
    state = create_research_run(plan, "resilience-request", 1500, NOW)
    request = ResearchNodeRequest(
        node_id="fund-root",
        request=ProviderRequest(
            request_id="resilience-provider-request",
            operation=ProviderOperation.FUND_DATA,
            subject="PUBLIC-FUND-001",
            required_fields=("fund_name", "weight_pct"),
            parameters={"period": "2026-06-30"},
            timeout_ms=1000,
        ),
    )

    execution = asyncio.run(
        execute_research_run(
            state,
            primary,
            (request,),
            started_at=NOW,
            clock=lambda: NOW,
            policy=policy,
        )
    )
    node_result = execution.state.nodes[0].result
    assert node_result is not None
    assert node_result.status.value == "COMPLETE"
    assert node_result.provider == "secondary-provider"
    assert node_result.provider_serving_mode == ProviderServingMode.FALLBACK_PROVIDER
    assert node_result.provider_cache_age_ms is None


def test_specialist_fixture_path_can_opt_into_shared_public_cache() -> None:
    current = [NOW]
    cache = InMemoryProviderCache(ttl_ms=10_000, clock=lambda: current[0])
    policy = ProviderExecutionPolicy(cache=cache)
    service = FixtureResearchSpecialistMatrixService(provider_policy=policy)
    template = service.matrix_template("public-research-owner")

    def request(request_id: str) -> ResearchSpecialistMatrixRequest:
        return ResearchSpecialistMatrixRequest(
            matrix_id=template.matrix_id,
            request_id=request_id,
            owner_id=template.owner_id,
            generated_at=NOW,
            scenario_id=ResearchScenarioId.BASELINE_READY,
        )

    first = asyncio.run(service.run(request("matrix-run-a")))
    second = asyncio.run(service.run(request("matrix-run-b")))
    assert all(
        node.result is not None
        and node.result.provider_serving_mode == ProviderServingMode.DIRECT
        for node in first.execution.state.nodes
    )
    assert all(
        node.result is not None
        and node.result.provider_serving_mode == ProviderServingMode.CACHE_FRESH
        for node in second.execution.state.nodes
    )
    assert cache.stats().entries == len(template.nodes)
