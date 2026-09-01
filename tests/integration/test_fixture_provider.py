import asyncio
from datetime import UTC, datetime
import json
from pathlib import Path
import tempfile
import pytest
from pydantic import ValidationError

from app.providers.contracts import (
    ProviderIssueCode,
    ProviderOperation,
    ProviderRequest,
    ProviderResult,
    ProviderStatus,
)
from app.providers.fingerprint import compute_request_fingerprint
from app.providers.fixture import FixtureFinancialProvider
from app.providers.runtime import execute_with_budget


@pytest.fixture
def provider() -> FixtureFinancialProvider:
    return FixtureFinancialProvider()


def test_loads_and_executes_success_fixture(provider: FixtureFinancialProvider) -> None:
    async def _test() -> None:
        req = ProviderRequest(
            request_id="req-success-1",
            operation=ProviderOperation.FUND_DATA,
            subject="FUND_FIXTURE_001",
            required_fields=("fund_name", "technology_weight_pct", "top10_concentration_pct"),
            parameters={"period": "2026-06-30"},
        )
        result = await provider.execute(req)

        assert result.request_id == "req-success-1"
        assert result.request_fingerprint == compute_request_fingerprint(req)
        assert result.status == ProviderStatus.SUCCESS
        assert len(result.records) == 1
        assert result.records[0].fields["technology_weight_pct"] == 63.5
        assert len(result.issues) == 0

    asyncio.run(_test())


def test_loads_and_executes_partial_fixture(provider: FixtureFinancialProvider) -> None:
    async def _test() -> None:
        req = ProviderRequest(
            request_id="req-partial-1",
            operation=ProviderOperation.FUND_DATA,
            subject="FUND_FIXTURE_001_PARTIAL",
            required_fields=("fund_name", "technology_weight_pct", "top10_concentration_pct"),
            parameters={"period": "2026-06-30"},
        )
        result = await provider.execute(req)

        assert result.request_id == "req-partial-1"
        assert result.status == ProviderStatus.PARTIAL
        assert len(result.records) == 1
        assert "top10_concentration_pct" in result.missing_fields
        assert len(result.issues) == 1

    asyncio.run(_test())


def test_loads_and_executes_empty_fixture(provider: FixtureFinancialProvider) -> None:
    async def _test() -> None:
        req = ProviderRequest(
            request_id="req-empty-1",
            operation=ProviderOperation.FUND_DATA,
            subject="FUND_FIXTURE_EMPTY",
            required_fields=("fund_name",),
            parameters={"period": "1990-01-01"},
        )
        result = await provider.execute(req)

        assert result.request_id == "req-empty-1"
        assert result.status == ProviderStatus.EMPTY
        assert len(result.records) == 0
        assert result.scope_description is not None
        assert "FUND_FIXTURE_EMPTY" in result.scope_description

    asyncio.run(_test())


def test_loads_and_executes_failed_fixture(provider: FixtureFinancialProvider) -> None:
    async def _test() -> None:
        req = ProviderRequest(
            request_id="req-failed-1",
            operation=ProviderOperation.FUND_DATA,
            subject="FUND_FIXTURE_DOWN",
            required_fields=("fund_name",),
            parameters={"period": "2026-06-30"},
        )
        result = await provider.execute(req)

        assert result.request_id == "req-failed-1"
        assert result.status == ProviderStatus.FAILED
        assert len(result.records) == 0
        assert len(result.issues) == 1
        assert result.issues[0].code == ProviderIssueCode.TRANSPORT_ERROR
        assert result.issues[0].retriable is True

    asyncio.run(_test())


def test_14_unknown_fixture_returns_structured_failed(provider: FixtureFinancialProvider) -> None:
    async def _test() -> None:
        req = ProviderRequest(
            request_id="req-unknown-1",
            operation=ProviderOperation.MARKET_DATA,
            subject="UNKNOWN_STOCK_999",
            parameters={"param": "value"},
        )
        result = await provider.execute(req)

        assert result.request_id == "req-unknown-1"
        assert result.status == ProviderStatus.FAILED
        assert result.status != ProviderStatus.EMPTY
        assert len(result.records) == 0
        assert len(result.issues) == 1
        assert result.issues[0].code == ProviderIssueCode.UNSUPPORTED_OPERATION
        assert "No matching fixture" in result.issues[0].safe_message

    asyncio.run(_test())


def test_fixture_provider_rejects_invalid_result_template() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        invalid_fixture = {
            "request": {
                "operation": "FUND_DATA",
                "subject": "INVALID_FIXTURE",
                "required_fields": ["fund_name"],
                "parameters": {},
            },
            "result": {
                "provider": "fixture-provider",
                "status": "SUCCESS",
                "records": [],
                "missing_fields": [],
                "issues": [],
            },
        }
        fixture_file = tmp_path / "invalid.json"
        fixture_file.write_text(json.dumps(invalid_fixture), encoding="utf-8")

        with pytest.raises(ValidationError, match="SUCCESS result requires at least one record"):
            FixtureFinancialProvider(fixture_dir=tmp_path)


def test_fixture_provider_rejects_duplicate_fingerprints() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        f1 = {
            "request": {
                "operation": "FUND_DATA",
                "subject": "SAME_SUBJ",
                "required_fields": ["fund_name"],
                "parameters": {"a": 1},
            },
            "result": {
                "provider": "fixture-provider",
                "status": "EMPTY",
                "records": [],
                "missing_fields": [],
                "issues": [],
                "scope_description": "empty 1",
            },
        }
        f2 = {
            "request": {
                "operation": "FUND_DATA",
                "subject": "SAME_SUBJ",
                "required_fields": ["fund_name"],
                "parameters": {"a": 1},
            },
            "result": {
                "provider": "fixture-provider",
                "status": "EMPTY",
                "records": [],
                "missing_fields": [],
                "issues": [],
                "scope_description": "empty 2",
            },
        }
        (tmp_path / "f1.json").write_text(json.dumps(f1), encoding="utf-8")
        (tmp_path / "f2.json").write_text(json.dumps(f2), encoding="utf-8")

        with pytest.raises(ValueError, match="Duplicate request fingerprint"):
            FixtureFinancialProvider(fixture_dir=tmp_path)


class SlowProvider:
    @property
    def name(self) -> str:
        return "slow-provider"

    async def execute(self, request: ProviderRequest) -> ProviderResult:
        await asyncio.sleep(0.5)
        return ProviderResult(
            request_id=request.request_id,
            request_fingerprint=compute_request_fingerprint(request),
            provider=self.name,
            status=ProviderStatus.EMPTY,
            retrieved_at=datetime.now(UTC),
            records=(),
            missing_fields=(),
            issues=(),
            scope_description="never reached",
        )


class FaultyProvider:
    @property
    def name(self) -> str:
        return "faulty-provider"

    async def execute(self, request: ProviderRequest) -> ProviderResult:
        raise RuntimeError("database connection crashed with password=secret123")


def test_15_timeout_returns_failed_timeout_without_raw_exception() -> None:
    async def _test() -> None:
        req = ProviderRequest(
            request_id="req-timeout-1",
            operation=ProviderOperation.FUND_DATA,
            subject="FUND_001",
            timeout_ms=50,
        )
        slow_provider = SlowProvider()
        result = await execute_with_budget(slow_provider, req)

        assert result.request_id == "req-timeout-1"
        assert result.status == ProviderStatus.FAILED
        assert len(result.issues) == 1
        assert result.issues[0].code == ProviderIssueCode.TIMEOUT
        assert result.issues[0].retriable is True
        assert "timed out after 50ms" in result.issues[0].safe_message

    asyncio.run(_test())


def test_budget_catches_unknown_exception_safely() -> None:
    async def _test() -> None:
        req = ProviderRequest(
            request_id="req-fault-1",
            operation=ProviderOperation.FUND_DATA,
            subject="FUND_001",
            timeout_ms=3000,
        )
        faulty_provider = FaultyProvider()
        result = await execute_with_budget(faulty_provider, req)

        assert result.request_id == "req-fault-1"
        assert result.status == ProviderStatus.FAILED
        assert len(result.issues) == 1
        assert result.issues[0].code == ProviderIssueCode.INTERNAL_ERROR
        assert "secret123" not in result.issues[0].safe_message
        assert "secret123" not in str(result.issues[0].diagnostics)

    asyncio.run(_test())


def test_20_100_concurrent_requests_isolation(provider: FixtureFinancialProvider) -> None:
    async def _test() -> None:
        subjects = [
            "FUND_FIXTURE_001",
            "FUND_FIXTURE_001_PARTIAL",
            "FUND_FIXTURE_EMPTY",
            "FUND_FIXTURE_DOWN",
        ]

        async def run_one(i: int) -> ProviderResult:
            subj = subjects[i % len(subjects)]
            if subj == "FUND_FIXTURE_EMPTY":
                req = ProviderRequest(
                    request_id=f"req-concurrent-{i}",
                    operation=ProviderOperation.FUND_DATA,
                    subject=subj,
                    required_fields=("fund_name",),
                    parameters={"period": "1990-01-01"},
                )
            elif subj in ("FUND_FIXTURE_001", "FUND_FIXTURE_001_PARTIAL"):
                req = ProviderRequest(
                    request_id=f"req-concurrent-{i}",
                    operation=ProviderOperation.FUND_DATA,
                    subject=subj,
                    required_fields=("fund_name", "technology_weight_pct", "top10_concentration_pct"),
                    parameters={"period": "2026-06-30"},
                )
            else:
                req = ProviderRequest(
                    request_id=f"req-concurrent-{i}",
                    operation=ProviderOperation.FUND_DATA,
                    subject=subj,
                    required_fields=("fund_name",),
                    parameters={"period": "2026-06-30"},
                )
            return await execute_with_budget(provider, req)

        tasks = [run_one(i) for i in range(100)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 100
        for i, res in enumerate(results):
            expected_req_id = f"req-concurrent-{i}"
            assert res.request_id == expected_req_id

        # Same semantic requests share same fingerprint
        fp_0 = results[0].request_fingerprint
        fp_4 = results[4].request_fingerprint
        assert fp_0 == fp_4

    asyncio.run(_test())
