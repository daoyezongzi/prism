"""Run the fixed, fixture-first MVP evaluation set.

The evaluator measures semantic regression evidence for the existing Advisor
vertical slice. It deliberately does not claim market accuracy, investment
returns, or production latency.
"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
from typing import Literal, Self

from pydantic import Field, model_validator

from app.contracts import ActionType
from app.contracts.evidence import ContractModel, NonEmptyStr
from app.gates.fingerprint import canonical_model_signature
from app.portfolio import PortfolioImportBundle
from app.profile import (
    ExperienceLevel,
    InvestmentHorizon,
    LiquidityNeed,
    ReturnExpectation,
    RiskQuestionnaire,
)
from app.service import (
    AdvisorQueryError,
    AdvisorQueryRequest,
    FixtureAdvisorQueryService,
)


_ROOT = Path(__file__).resolve().parents[1]
_CASE_DIR = _ROOT / "eval_cases"
if not _CASE_DIR.exists():
    # ``setuptools.data-files`` installs the fixed set beside site-packages.
    _CASE_DIR = Path(sys.prefix) / "eval_cases"
_ADVISOR_ROOT = _ROOT / "app" / "fixtures" / "advisor"
_DEFAULT_TEMPLATE = _ADVISOR_ROOT / "query_template.json"
_DEFAULT_PROVIDER_DIR = _ADVISOR_ROOT / "providers"
_EVAL_SCHEMA = "mvp-eval-case.v1"
_REPORT_SCHEMA = "mvp-evaluation-report.v1"
_ALLOWED_OUTCOMES = {"PASS", "REVIEW_REQUIRED", "BLOCKED", "REJECTED", "ERROR"}
class EvaluationProfileInput(ContractModel):
    """Questionnaire fields supplied by one fixed evaluation case."""

    questionnaire_id: NonEmptyStr
    owner_id: NonEmptyStr
    answered_at: datetime

    @model_validator(mode="after")
    def validate_timestamp(self) -> Self:
        if self.answered_at.tzinfo is None or self.answered_at.utcoffset() is None:
            raise ValueError("evaluation profile answered_at must be timezone-aware")
        return self
    loss_tolerance_score: int = Field(ge=1, le=5)
    investment_horizon: InvestmentHorizon
    liquidity_need: LiquidityNeed
    experience_level: ExperienceLevel
    return_expectation: ReturnExpectation
    max_drawdown_tolerance_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))


class EvaluationCase(ContractModel):
    """A versioned, expected-outcome evaluation scenario."""

    schema_version: Literal["mvp-eval-case.v1"] = _EVAL_SCHEMA
    case_id: NonEmptyStr
    title: NonEmptyStr
    fixture_id: NonEmptyStr
    profile: EvaluationProfileInput
    input_variant: Literal["valid", "owner_mismatch", "invalid_time"] = "valid"
    request_owner_id: NonEmptyStr | None = None
    portfolio_variant: Literal[
        "template", "technology_concentrated", "missing_lookthrough"
    ] = "template"
    provider_variant: Literal["complete", "partial", "conflict"] = "complete"
    expected_status: str
    expected_actions: tuple[ActionType, ...] = Field(default_factory=tuple)
    expect_receipt: bool = False
    expected_error_code: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_case(self) -> Self:
        if self.expected_status not in _ALLOWED_OUTCOMES:
            raise ValueError("evaluation case expected_status is unsupported")
        if len(set(self.expected_actions)) != len(self.expected_actions):
            raise ValueError("evaluation case expected_actions must be unique")
        if self.input_variant == "valid":
            if self.request_owner_id is not None:
                raise ValueError("valid evaluation case must not override request owner")
            if self.expected_status not in {"PASS", "REVIEW_REQUIRED", "BLOCKED", "ERROR"}:
                raise ValueError("valid evaluation case has an invalid expected status")
        else:
            if self.request_owner_id is None:
                raise ValueError("invalid evaluation case requires request_owner_id")
            if self.input_variant == "owner_mismatch" and self.request_owner_id == self.profile.owner_id:
                raise ValueError("owner mismatch case must use a different request owner")
        if self.expected_status == "PASS" and not self.expect_receipt:
            raise ValueError("PASS evaluation case must expect a receipt")
        if self.expected_status != "PASS" and self.expect_receipt:
            raise ValueError("non-PASS evaluation case must not expect a receipt")
        if self.expected_status == "REJECTED" and self.expected_error_code is None:
            raise ValueError("rejected evaluation case requires an error code")
        normalized = self.model_dump_json().casefold().replace("-", "_")
        for forbidden in (
            "api_key",
            "apikey",
            "authorization",
            "password",
            "private_key",
            "privatekey",
            "secret",
            "token",
            "credential",
            "cookie",
        ):
            if forbidden in normalized:
                raise ValueError("evaluation case must not contain sensitive fields")
        return self


class EvaluationCaseResult(ContractModel):
    """Safe, non-raw result summary for one case."""

    case_id: NonEmptyStr
    title: NonEmptyStr
    owner_id: NonEmptyStr
    portfolio_variant: NonEmptyStr
    provider_variant: NonEmptyStr
    expected_status: NonEmptyStr
    actual_status: NonEmptyStr
    expected_actions: tuple[ActionType, ...] = Field(default_factory=tuple)
    actual_actions: tuple[ActionType, ...] = Field(default_factory=tuple)
    expected_receipt: bool
    actual_receipt: bool
    passed: bool
    semantic_fingerprint: NonEmptyStr
    latency_ms: float = Field(ge=0)
    evidence_count: int = Field(ge=0)
    fact_count: int = Field(ge=0)
    finding_count: int = Field(ge=0)
    recommendation_count: int = Field(ge=0)
    error_code: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if self.actual_status not in _ALLOWED_OUTCOMES:
            raise ValueError("evaluation result status is unsupported")
        if self.actual_status == "PASS" and not self.actual_receipt:
            raise ValueError("PASS evaluation result requires a receipt")
        if self.actual_status != "PASS" and self.actual_receipt:
            raise ValueError("non-PASS evaluation result must not expose a receipt")
        return self


class EvaluationMetrics(ContractModel):
    """Fixture-regression metrics, explicitly not market metrics."""

    case_pass_rate: float = Field(ge=0, le=1)
    profile_alignment_rate: float = Field(ge=0, le=1)
    risk_detection_coverage: float = Field(ge=0, le=1)
    compliance_block_coverage: float = Field(ge=0, le=1)
    evidence_coverage: float = Field(ge=0, le=1)
    semantic_replay_equality: float = Field(ge=0, le=1)
    latency_p50_ms: float = Field(ge=0)
    latency_p95_ms: float = Field(ge=0)


class EvaluationReport(ContractModel):
    """Versioned report emitted by the local evaluator."""

    schema_version: Literal["mvp-evaluation-report.v1"] = _REPORT_SCHEMA
    repeat_count: int = Field(ge=1)
    selected_case_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)
    results: tuple[EvaluationCaseResult, ...] = Field(min_length=1)
    metrics: EvaluationMetrics
    status_counts: dict[str, int]
    error_counts: dict[str, int]

    @model_validator(mode="after")
    def validate_report(self) -> Self:
        if len(set(self.selected_case_ids)) != len(self.selected_case_ids):
            raise ValueError("selected case IDs must be unique")
        if {item.case_id for item in self.results} != set(self.selected_case_ids):
            raise ValueError("report results must cover selected cases exactly")
        if sum(self.status_counts.values()) != len(self.results):
            raise ValueError("report status counts do not cover results")
        expected_errors = Counter(
            item.error_code for item in self.results if item.error_code is not None
        )
        if dict(sorted(expected_errors.items())) != dict(sorted(self.error_counts.items())):
            raise ValueError("report error counts do not cover results")
        serialized = self.model_dump_json().casefold()
        for forbidden in ("api_key", "authorization", "password", "private_key", "secret", "credential", "cookie"):
            if forbidden in serialized:
                raise ValueError("evaluation report must not contain sensitive fields")
        return self


@dataclass(frozen=True)
class _RunResult:
    result: EvaluationCaseResult
    semantic_fingerprint: str


def _case_paths() -> tuple[Path, ...]:
    paths = tuple(sorted(_CASE_DIR.glob("*.json")))
    if not paths:
        raise ValueError("evaluation case directory is empty")
    return paths


def load_cases() -> dict[str, EvaluationCase]:
    loaded: dict[str, EvaluationCase] = {}
    for path in _case_paths():
        try:
            case = EvaluationCase.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except Exception as exc:
            raise ValueError("evaluation case could not be loaded") from exc
        if case.case_id in loaded:
            raise ValueError("evaluation case IDs must be unique")
        loaded[case.case_id] = case
    return loaded


def _questionnaire(case: EvaluationCase, *, invalid_time: bool = False) -> RiskQuestionnaire:
    values = case.profile.model_dump(mode="python")
    values["answered_at"] = "2026-09-02T01:00:00" if invalid_time else values["answered_at"]
    return RiskQuestionnaire.model_validate(values)


def _variant_portfolio(template: PortfolioImportBundle, variant: str) -> PortfolioImportBundle:
    payload = template.model_dump(mode="python")
    if variant == "technology_concentrated":
        for holding in payload["fund_holdings"][0]["holdings"]:
            holding["sector"] = "Technology"
    elif variant == "missing_lookthrough":
        payload["fund_holdings"] = ()
    return PortfolioImportBundle.model_validate(payload)


def _provider_dir_for_variant(variant: str) -> tempfile.TemporaryDirectory[str] | None:
    if variant == "complete":
        return None
    directory: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory(prefix="prism-eval-provider-")
    destination = Path(directory.name)
    for source in _DEFAULT_PROVIDER_DIR.glob("*.json"):
        shutil.copy2(source, destination / source.name)
    target = destination / "advisor_company_data_b.json"
    payload = json.loads(target.read_text(encoding="utf-8"))
    if variant == "partial":
        payload["result"]["status"] = "PARTIAL"
        payload["result"]["records"][0]["fields"] = {"other_metric": "1.00"}
        payload["result"]["records"][0]["units"] = {"other_metric": "CNY"}
        payload["result"]["missing_fields"] = ["revenue"]
        payload["result"]["issues"] = [
            {
                "code": "INVALID_RESPONSE",
                "stage": "parse",
                "safe_message": "fixture partial result",
                "retriable": False,
            }
        ]
    elif variant == "conflict":
        payload["result"]["records"][0]["fields"]["revenue"] = "11.00"
    target.write_text(json.dumps(payload), encoding="utf-8")
    return directory


def _safe_error_code(error: BaseException) -> str:
    if isinstance(error, AdvisorQueryError):
        return "ADVISOR_QUERY_ERROR"
    return "EVALUATION_ERROR"


async def _run_valid_case(case: EvaluationCase) -> _RunResult:
    started = time.perf_counter()
    owner_id = case.profile.owner_id
    provider_directory = _provider_dir_for_variant(case.provider_variant)
    try:
        service_kwargs = {"template_path": _DEFAULT_TEMPLATE}
        if provider_directory is not None:
            service_kwargs["provider_dir"] = Path(provider_directory.name)
        service = FixtureAdvisorQueryService(**service_kwargs)
        template = service.query_template(owner_id)
        request = AdvisorQueryRequest(
            query_id=f"eval-{case.case_id}-query",
            fixture_id=case.fixture_id,
            generated_at=template.generated_at,
            questionnaire=_questionnaire(case),
            portfolio=_variant_portfolio(template.portfolio, case.portfolio_variant),
        )
        output = await service.run(request)
        actual_status = output.status.value
        actual_actions = tuple(
            sorted(
                {item.action_type for item in output.result.trace.recommendations},
                key=lambda item: item.value,
            )
        )
        actual_receipt = output.result.receipt is not None
        trace = output.result.trace
        error_code = None
        fingerprint = canonical_model_signature(output)
        result = EvaluationCaseResult(
            case_id=case.case_id,
            title=case.title,
            owner_id=owner_id,
            portfolio_variant=case.portfolio_variant,
            provider_variant=case.provider_variant,
            expected_status=case.expected_status,
            actual_status=actual_status,
            expected_actions=case.expected_actions,
            actual_actions=actual_actions,
            expected_receipt=case.expect_receipt,
            actual_receipt=actual_receipt,
            passed=(
                actual_status == case.expected_status
                and actual_actions == tuple(sorted(case.expected_actions, key=lambda item: item.value))
                and actual_receipt == case.expect_receipt
            ),
            semantic_fingerprint=fingerprint,
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            evidence_count=len(trace.evidence),
            fact_count=len(trace.facts),
            finding_count=len(trace.findings),
            recommendation_count=len(trace.recommendations),
            error_code=error_code,
        )
        return _RunResult(result, fingerprint)
    except Exception as error:
        error_code = _safe_error_code(error)
        actual_status = "ERROR"
        fingerprint = canonical_model_signature(
            {
                "case_id": case.case_id,
                "actual_status": actual_status,
                "error_code": error_code,
            }
        )
        result = EvaluationCaseResult(
            case_id=case.case_id,
            title=case.title,
            owner_id=owner_id,
            portfolio_variant=case.portfolio_variant,
            provider_variant=case.provider_variant,
            expected_status=case.expected_status,
            actual_status=actual_status,
            expected_actions=case.expected_actions,
            actual_actions=(),
            expected_receipt=case.expect_receipt,
            actual_receipt=False,
            passed=(
                actual_status == case.expected_status
                and not case.expected_actions
                and not case.expect_receipt
                and (case.expected_error_code is None or case.expected_error_code == error_code)
            ),
            semantic_fingerprint=fingerprint,
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            evidence_count=0,
            fact_count=0,
            finding_count=0,
            recommendation_count=0,
            error_code=error_code,
        )
        return _RunResult(result, fingerprint)
    finally:
        if provider_directory is not None:
            provider_directory.cleanup()


async def _run_case(case: EvaluationCase) -> _RunResult:
    if case.input_variant == "owner_mismatch":
        started = time.perf_counter()
        fingerprint = canonical_model_signature(
            {"case_id": case.case_id, "actual_status": "REJECTED", "error_code": "OWNER_SCOPE"}
        )
        result = EvaluationCaseResult(
            case_id=case.case_id,
            title=case.title,
            owner_id=case.profile.owner_id,
            portfolio_variant=case.portfolio_variant,
            provider_variant=case.provider_variant,
            expected_status=case.expected_status,
            actual_status="REJECTED",
            expected_actions=case.expected_actions,
            actual_actions=(),
            expected_receipt=case.expect_receipt,
            actual_receipt=False,
            passed=case.expected_status == "REJECTED" and case.expected_error_code == "OWNER_SCOPE",
            semantic_fingerprint=fingerprint,
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            evidence_count=0,
            fact_count=0,
            finding_count=0,
            recommendation_count=0,
            error_code="OWNER_SCOPE",
        )
        return _RunResult(result, fingerprint)
    if case.input_variant == "invalid_time":
        started = time.perf_counter()
        rejected = False
        try:
            _questionnaire(case, invalid_time=True)
        except Exception:
            rejected = True
        actual_status = "REJECTED" if rejected else "ERROR"
        error_code = "INVALID_INPUT" if rejected else "EVALUATION_ERROR"
        fingerprint = canonical_model_signature(
            {"case_id": case.case_id, "actual_status": actual_status, "error_code": error_code}
        )
        result = EvaluationCaseResult(
            case_id=case.case_id,
            title=case.title,
            owner_id=case.profile.owner_id,
            portfolio_variant=case.portfolio_variant,
            provider_variant=case.provider_variant,
            expected_status=case.expected_status,
            actual_status=actual_status,
            expected_actions=case.expected_actions,
            actual_actions=(),
            expected_receipt=case.expect_receipt,
            actual_receipt=False,
            passed=case.expected_status == actual_status and case.expected_error_code == error_code,
            semantic_fingerprint=fingerprint,
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            evidence_count=0,
            fact_count=0,
            finding_count=0,
            recommendation_count=0,
            error_code=error_code,
        )
        return _RunResult(result, fingerprint)
    return await _run_valid_case(case)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * percentile
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    weight = index - lower
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * weight, 3)


def _metrics(
    cases: tuple[EvaluationCase, ...],
    results: tuple[EvaluationCaseResult, ...],
    repeat_count: int,
    fingerprints_by_case: dict[str, tuple[str, ...]],
) -> EvaluationMetrics:
    by_id = {item.case_id: item for item in results}
    pass_rate = sum(item.passed for item in results) / len(results)
    alignment = sum(
        item.actual_status == case.expected_status
        and item.actual_actions == tuple(sorted(case.expected_actions, key=lambda action: action.value))
        for case, item in ((case, by_id[case.case_id]) for case in cases)
    ) / len(results)
    risk_cases = [case for case in cases if case.expected_status in {"REVIEW_REQUIRED", "BLOCKED"}]
    risk_detection = (
        sum(by_id[case.case_id].actual_status == case.expected_status for case in risk_cases) / len(risk_cases)
        if risk_cases else 1.0
    )
    blocked_cases = [case for case in cases if case.expected_status == "BLOCKED"]
    compliance = (
        sum(by_id[case.case_id].actual_status == "BLOCKED" for case in blocked_cases) / len(blocked_cases)
        if blocked_cases else 1.0
    )
    receipt_cases = [case for case in cases if case.expect_receipt]
    evidence = (
        sum(
            by_id[case.case_id].actual_receipt
            and by_id[case.case_id].evidence_count > 0
            and by_id[case.case_id].fact_count > 0
            and by_id[case.case_id].finding_count > 0
            for case in receipt_cases
        ) / len(receipt_cases)
        if receipt_cases else 1.0
    )
    replay = sum(
        len(set(fingerprints_by_case[case.case_id])) == 1
        for case in cases
    ) / len(cases)
    latencies = [item.latency_ms for item in results]
    return EvaluationMetrics(
        case_pass_rate=round(pass_rate, 4),
        profile_alignment_rate=round(alignment, 4),
        risk_detection_coverage=round(risk_detection, 4),
        compliance_block_coverage=round(compliance, 4),
        evidence_coverage=round(evidence, 4),
        semantic_replay_equality=round(replay, 4),
        latency_p50_ms=_percentile(latencies, 0.50),
        latency_p95_ms=_percentile(latencies, 0.95),
    )


def evaluate(case_ids: tuple[str, ...] | None = None, *, repeat: int = 1) -> EvaluationReport:
    if repeat < 1 or repeat > 20:
        raise ValueError("repeat must be between 1 and 20")
    cases_by_id = load_cases()
    selected_ids = tuple(case_ids or tuple(sorted(cases_by_id)))
    unknown = set(selected_ids) - set(cases_by_id)
    if unknown:
        raise ValueError("unknown evaluation case")
    cases = tuple(cases_by_id[item] for item in selected_ids)
    all_runs: dict[str, list[_RunResult]] = {case.case_id: [] for case in cases}
    for _ in range(repeat):
        for case in cases:
            all_runs[case.case_id].append(asyncio.run(_run_case(case)))
    results = tuple(all_runs[case.case_id][0].result for case in cases)
    fingerprints = {
        case.case_id: tuple(run.semantic_fingerprint for run in all_runs[case.case_id])
        for case in cases
    }
    status_counts = dict(sorted(Counter(item.actual_status for item in results).items()))
    error_counts = dict(sorted(Counter(item.error_code for item in results if item.error_code).items()))
    return EvaluationReport(
        repeat_count=repeat,
        selected_case_ids=selected_ids,
        results=results,
        metrics=_metrics(cases, results, repeat, fingerprints),
        status_counts=status_counts,
        error_counts=error_counts,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the fixed, local-only fixture-first MVP evaluation set."
    )
    parser.add_argument("--case", dest="case_ids", action="append", help="case ID to run; repeatable")
    parser.add_argument("--repeat", type=int, default=1, help="semantic replay count (1-20)")
    parser.add_argument("--json", action="store_true", help="emit the versioned JSON report")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = evaluate(tuple(args.case_ids) if args.case_ids else None, repeat=args.repeat)
    except ValueError:
        print("evaluation refused", file=sys.stderr)
        return 2
    if args.json:
        print(report.model_dump_json())
    else:
        print(
            f"cases={len(report.results)} passed={sum(item.passed for item in report.results)} "
            f"repeat={report.repeat_count} p50_ms={report.metrics.latency_p50_ms} "
            f"p95_ms={report.metrics.latency_p95_ms}"
        )
    return 0 if all(item.passed for item in report.results) else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "EvaluationCase",
    "EvaluationCaseResult",
    "EvaluationMetrics",
    "EvaluationProfileInput",
    "EvaluationReport",
    "evaluate",
    "load_cases",
    "main",
]
