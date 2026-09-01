"""Phase 21 fixed evaluation set and semantic replay evidence."""

from __future__ import annotations

import json

import pytest

from tools.evaluate_mvp import EvaluationCase, evaluate, load_cases, main


def test_fixed_evaluation_set_covers_profile_risk_provider_and_owner_semantics() -> None:
    cases = load_cases()
    assert len(cases) == 9
    assert {
        case.expected_status for case in cases.values()
    } == {"PASS", "REVIEW_REQUIRED", "BLOCKED", "REJECTED", "ERROR"}
    assert {case.portfolio_variant for case in cases.values()} == {
        "template",
        "technology_concentrated",
        "missing_lookthrough",
    }
    assert {case.provider_variant for case in cases.values()} == {
        "complete",
        "partial",
        "conflict",
    }


def test_evaluation_report_passes_all_cases_and_closes_evidence() -> None:
    report = evaluate(repeat=3)
    assert report.schema_version == "mvp-evaluation-report.v1"
    assert report.repeat_count == 3
    assert all(item.passed for item in report.results)
    assert report.metrics.case_pass_rate == 1.0
    assert report.metrics.profile_alignment_rate == 1.0
    assert report.metrics.risk_detection_coverage == 1.0
    assert report.metrics.compliance_block_coverage == 1.0
    assert report.metrics.evidence_coverage == 1.0
    assert report.metrics.semantic_replay_equality == 1.0
    hold = next(item for item in report.results if item.case_id == "balanced-hold")
    reduce_case = next(item for item in report.results if item.case_id == "conservative-reduce")
    assert hold.actual_actions == ("HOLD",)
    assert reduce_case.actual_actions == ("REDUCE",)
    assert hold.evidence_count > 0 and hold.fact_count > 0 and hold.finding_count > 0
    assert report.status_counts == {
        "BLOCKED": 2,
        "ERROR": 1,
        "PASS": 3,
        "REJECTED": 2,
        "REVIEW_REQUIRED": 1,
    }
    assert report.error_counts == {
        "ADVISOR_QUERY_ERROR": 1,
        "INVALID_INPUT": 1,
        "OWNER_SCOPE": 1,
    }


def test_evaluation_cli_emits_safe_json_and_rejects_unknown_cases(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--case", "balanced-hold", "--json"]) == 0
    output = capsys.readouterr().out
    body = json.loads(output)
    assert body["schema_version"] == "mvp-evaluation-report.v1"
    assert body["selected_case_ids"] == ["balanced-hold"]
    assert "exception" not in output.casefold()

    assert main(["--case", "not-a-case", "--json"]) == 2
    error = capsys.readouterr().err
    assert error.strip() == "evaluation refused"
    assert "not-a-case" not in error


def test_evaluation_case_contract_rejects_extra_and_sensitive_fields() -> None:
    base = next(iter(load_cases().values())).model_dump(mode="python")
    with pytest.raises(ValueError):
        EvaluationCase.model_validate({**base, "unexpected": True})
    sensitive = json.loads(json.dumps(base, default=str))
    sensitive["title"] = "secret account"
    with pytest.raises(ValueError):
        EvaluationCase.model_validate(sensitive)


def test_evaluation_runner_has_no_network_or_dom_injection_surface() -> None:
    source = open("tools/evaluate_mvp.py", encoding="utf-8").read().casefold()
    assert "https://" not in source
    assert "http://" not in source
    assert "innerhtml" not in source
    assert "gemini" not in source
    assert "openai" not in source
