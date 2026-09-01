import asyncio
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from app.research import (
    ResearchSpecialistMatrixRequest,
    ResearchSpecialistRole,
)
from app.service import (
    FixtureResearchSpecialistMatrixService,
    SpecialistMatrixError,
)


REPO_ROOT = Path(__file__).parents[2]
MATRIX_PROVIDER_DIR = REPO_ROOT / "app" / "fixtures" / "research" / "providers"
NOW = datetime(2026, 9, 2, 1, tzinfo=UTC)
MATRIX_ID = "specialist-matrix-four-track-001"


def _request(*, owner: str = "matrix-integration-owner", request_id: str = "matrix-run-001"):
    return ResearchSpecialistMatrixRequest(
        matrix_id=MATRIX_ID,
        request_id=request_id,
        owner_id=owner,
        generated_at=NOW,
    )


def test_four_track_matrix_reaches_ready_with_two_lineages_per_claim() -> None:
    output = asyncio.run(FixtureResearchSpecialistMatrixService().run(_request()))

    assert output.pipeline.status.value == "READY"
    assert output.execution.state.status.value == "COMPLETED"
    assert len(output.matrix.nodes) == 8
    assert {node.role for node in output.matrix.nodes} == set(ResearchSpecialistRole)
    assert all(validation.status.value == "SUPPORTED" for validation in output.pipeline.validations)
    assert len(output.execution.evidence) == 8
    assert len(output.execution.observations) == 8
    assert len(output.pipeline.trace.facts) == 4
    assert len(output.pipeline.trace.findings) == 4
    assert output.pipeline.trace.recommendations == ()
    assert all(item.owner_id == output.owner_id for item in output.execution.observations)
    assert len({item.evidence_id for item in output.execution.evidence}) == 8


def test_matrix_replay_is_deterministic_and_owner_rebound() -> None:
    service = FixtureResearchSpecialistMatrixService()
    request = _request(request_id="matrix-replay-001")
    first = asyncio.run(service.run(request))
    second = asyncio.run(service.run(request))

    assert first == second
    assert first.matrix.owner_id == request.owner_id
    assert first.execution.state.run_id == second.execution.state.run_id
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    other = asyncio.run(service.run(_request(owner="other-matrix-owner", request_id="matrix-replay-001")))
    assert other.owner_id == "other-matrix-owner"
    assert all(item.owner_id == "other-matrix-owner" for item in other.execution.observations)
    assert all("matrix-integration-owner" not in item.model_dump_json() for item in other.execution.observations)


def test_one_hundred_concurrent_matrix_runs_are_isolated_and_deterministic() -> None:
    service = FixtureResearchSpecialistMatrixService()
    requests = tuple(
        _request(request_id=f"matrix-concurrent-{index:03d}")
        for index in range(100)
    )

    async def run_all():
        return await asyncio.gather(*(service.run(request) for request in requests))

    outputs = asyncio.run(run_all())
    assert len(outputs) == 100
    assert len({output.execution.state.run_id for output in outputs}) == 100
    assert all(output.pipeline.status.value == "READY" for output in outputs)
    assert all(output.owner_id == requests[0].owner_id for output in outputs)
    assert all(len(output.pipeline.trace.facts) == 4 for output in outputs)


def test_matrix_ready_nodes_execute_in_parallel(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.service.specialist_matrix as module
    from app.providers import FixtureFinancialProvider

    class DelayedFixtureProvider(FixtureFinancialProvider):
        active = 0
        max_active = 0

        async def execute(self, request):
            type(self).active += 1
            type(self).max_active = max(type(self).max_active, type(self).active)
            try:
                await asyncio.sleep(0.02)
                return await super().execute(request)
            finally:
                type(self).active -= 1

    monkeypatch.setattr(module, "FixtureFinancialProvider", DelayedFixtureProvider)
    output = asyncio.run(FixtureResearchSpecialistMatrixService().run(_request(request_id="matrix-parallel-001")))

    assert output.pipeline.status.value == "READY"
    assert DelayedFixtureProvider.max_active >= 8


def _copy_provider_fixtures() -> tuple[TemporaryDirectory, Path]:
    temp = TemporaryDirectory(prefix=".phase16-provider-", dir=REPO_ROOT)
    target = Path(temp.name)
    for source in MATRIX_PROVIDER_DIR.glob("*.json"):
        shutil.copy2(source, target / source.name)
    return temp, target


def test_partial_required_track_stays_review_without_facts_or_findings() -> None:
    temp, provider_dir = _copy_provider_fixtures()
    try:
        path = provider_dir / "macro_source_b.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["result"]["records"][0]["fields"] = {"other_metric": "1.00"}
        payload["result"]["records"][0]["units"] = {"other_metric": "pct"}
        payload["result"]["status"] = "PARTIAL"
        payload["result"]["missing_fields"] = ["policy_rate_pct"]
        payload["result"]["issues"] = [{
            "code": "INVALID_RESPONSE",
            "stage": "parse",
            "safe_message": "fixture omitted the requested policy rate",
            "retriable": False,
            "diagnostics": {"missing_field": "policy_rate_pct"}
        }]
        path.write_text(json.dumps(payload), encoding="utf-8")

        service = FixtureResearchSpecialistMatrixService(provider_dir=provider_dir)
        output = asyncio.run(service.run(_request(request_id="matrix-partial-001")))
        assert output.execution.state.status.value == "FAILED"
        assert output.pipeline.status.value == "REVIEW_REQUIRED"
        assert output.pipeline.trace.facts == ()
        assert output.pipeline.trace.findings == ()
        assert output.pipeline.trace.recommendations == ()
        assert all(item.value != 0 for item in output.execution.observations)
    finally:
        temp.cleanup()


def test_conflicting_source_stays_review_and_never_becomes_ready() -> None:
    temp, provider_dir = _copy_provider_fixtures()
    try:
        path = provider_dir / "stock_source_b.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["result"]["records"][0]["fields"]["revenue_cny"] = "9.00"
        path.write_text(json.dumps(payload), encoding="utf-8")

        output = asyncio.run(
            FixtureResearchSpecialistMatrixService(provider_dir=provider_dir).run(
                _request(request_id="matrix-conflict-001")
            )
        )
        assert output.execution.state.status.value == "COMPLETED"
        assert output.pipeline.status.value == "REVIEW_REQUIRED"
        assert any(item.status.value == "UNRESOLVED" for item in output.pipeline.validations)
        assert output.pipeline.trace.facts == ()
        assert output.pipeline.trace.findings == ()
    finally:
        temp.cleanup()


def test_completed_source_identity_drift_is_refused() -> None:
    temp, provider_dir = _copy_provider_fixtures()
    try:
        path = provider_dir / "industry_source_a.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["result"]["records"][0]["lineage_id"] = "unexpected-lineage"
        path.write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(SpecialistMatrixError, match="execution|evidence"):
            asyncio.run(
                FixtureResearchSpecialistMatrixService(provider_dir=provider_dir).run(
                    _request(request_id="matrix-identity-drift-001")
                )
            )
    finally:
        temp.cleanup()


def test_wrong_provider_identity_degrades_without_findings(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.service.specialist_matrix as module
    from app.providers import FixtureFinancialProvider

    class WrongIdentityProvider(FixtureFinancialProvider):
        @property
        def name(self):
            return "fixture-provider"

        async def execute(self, request):
            result = await super().execute(request)
            return result.model_copy(update={"provider": "unexpected-provider"})

    monkeypatch.setattr(module, "FixtureFinancialProvider", WrongIdentityProvider)
    output = asyncio.run(
        FixtureResearchSpecialistMatrixService().run(_request(request_id="matrix-provider-identity-001"))
    )
    assert output.pipeline.status.value == "REVIEW_REQUIRED"
    assert output.pipeline.trace.facts == ()
    assert output.pipeline.trace.findings == ()


def test_unknown_matrix_and_sensitive_request_fail_without_provider_details() -> None:
    service = FixtureResearchSpecialistMatrixService()
    with pytest.raises(SpecialistMatrixError, match="unavailable"):
        asyncio.run(service.run(_request(request_id="matrix-unknown-001").model_copy(update={"matrix_id": "missing"})))

    with pytest.raises(SpecialistMatrixError, match="refused"):
        asyncio.run(service.run(_request(request_id="matrix-safety-001").model_copy(update={"owner_id": "api_key-owner"})))
