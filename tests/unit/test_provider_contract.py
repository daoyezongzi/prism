from datetime import UTC, datetime
from decimal import Decimal
import pytest
from pydantic import ValidationError

from app.contracts.evidence import (
    ActionType,
    AllocationRange,
    ComplianceStatus,
    DecisionTrace,
    EvidenceQualityStatus,
    Fact,
    FactStatus,
    Finding,
    FindingSeverity,
    Recommendation,
)
from app.providers.contracts import (
    ProviderIssue,
    ProviderIssueCode,
    ProviderOperation,
    ProviderRecord,
    ProviderRequest,
    ProviderResult,
    ProviderStatus,
    validate_result_for_request,
)
from app.providers.fingerprint import compute_request_fingerprint
from app.providers.normalization import normalize_result_to_evidence

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def make_request(**overrides: object) -> ProviderRequest:
    values: dict[str, object] = {
        "request_id": "req-001",
        "operation": ProviderOperation.FUND_DATA,
        "subject": "FUND_FIXTURE_001",
        "as_of": NOW,
        "required_fields": ("fund_name", "technology_weight_pct"),
        "parameters": {"period": "2026-06-30"},
        "timeout_ms": 3000,
    }
    values.update(overrides)
    return ProviderRequest.model_validate(values)


def make_record(**overrides: object) -> ProviderRecord:
    values: dict[str, object] = {
        "source": "fund-holdings-fixture",
        "fields": {
            "fund_name": "Synthetic Tech Growth Fund",
            "technology_weight_pct": 63.5,
        },
        "units": {"technology_weight_pct": "pct"},
        "period": "2026-06-30",
        "observed_at": NOW,
        "lineage_id": "lineage:fixture:001",
    }
    values.update(overrides)
    return ProviderRecord.model_validate(values)


def make_issue(**overrides: object) -> ProviderIssue:
    values: dict[str, object] = {
        "code": ProviderIssueCode.INVALID_RESPONSE,
        "stage": "parse",
        "safe_message": "Missing field in response",
        "retriable": False,
        "diagnostics": {},
    }
    values.update(overrides)
    return ProviderIssue.model_validate(values)


def make_result(request: ProviderRequest, **overrides: object) -> ProviderResult:
    fingerprint = compute_request_fingerprint(request)
    values: dict[str, object] = {
        "request_id": request.request_id,
        "request_fingerprint": fingerprint,
        "provider": "fixture-provider",
        "status": ProviderStatus.SUCCESS,
        "retrieved_at": NOW,
        "records": (make_record(),),
        "missing_fields": (),
        "issues": (),
        "scope_description": None,
        "latency_ms": 5,
    }
    values.update(overrides)
    return ProviderResult.model_validate(values)


def test_1_success_without_records_rejected() -> None:
    req = make_request()
    with pytest.raises(ValidationError, match="SUCCESS result requires at least one record"):
        make_result(req, status=ProviderStatus.SUCCESS, records=())


def test_2_success_missing_required_field_rejected() -> None:
    req = make_request(required_fields=("fund_name", "technology_weight_pct", "missing_field"))
    record = make_record(fields={"fund_name": "Synthetic Fund", "technology_weight_pct": 63.5})
    result = make_result(req, records=(record,))
    with pytest.raises(ValueError, match="missing required field"):
        validate_result_for_request(req, result)


def test_2_success_record_none_value_rejected() -> None:
    req = make_request(required_fields=("fund_name", "technology_weight_pct"))
    record = make_record(fields={"fund_name": "Synthetic Fund", "technology_weight_pct": None})
    result = make_result(req, records=(record,))
    with pytest.raises(ValueError, match="missing required field.*or has None value"):
        validate_result_for_request(req, result)


def test_2_success_requires_every_record_to_have_all_fields() -> None:
    req = make_request(required_fields=("field_a", "field_b"))
    rec1 = make_record(fields={"field_a": 10})
    rec2 = make_record(fields={"field_b": 20})
    result = make_result(req, records=(rec1, rec2))
    with pytest.raises(ValueError, match="missing required field 'field_b'"):
        validate_result_for_request(req, result)


def test_3_partial_without_missing_fields_or_issues_rejected() -> None:
    req = make_request()
    with pytest.raises(ValidationError, match="PARTIAL result requires at least one missing field or issue"):
        make_result(
            req,
            status=ProviderStatus.PARTIAL,
            records=(make_record(),),
            missing_fields=(),
            issues=(),
        )


def test_3_partial_phantom_missing_field_rejected() -> None:
    req = make_request(required_fields=("fund_name",))
    rec = make_record(fields={"fund_name": "Tech Fund"})
    result = make_result(
        req,
        status=ProviderStatus.PARTIAL,
        records=(rec,),
        missing_fields=("unrequested_field",),
    )
    with pytest.raises(ValueError, match="not in request.required_fields"):
        validate_result_for_request(req, result)


def test_3_partial_claimed_missing_field_actually_present_rejected() -> None:
    req = make_request(required_fields=("fund_name", "technology_weight_pct"))
    rec = make_record(fields={"fund_name": "Tech Fund", "technology_weight_pct": 60.0})
    result = make_result(
        req,
        status=ProviderStatus.PARTIAL,
        records=(rec,),
        missing_fields=("technology_weight_pct",),
    )
    with pytest.raises(ValueError, match="claims missing field.*but all records contain valid values"):
        validate_result_for_request(req, result)


def test_3_partial_cannot_omit_an_actual_missing_field_when_issue_exists() -> None:
    req = make_request(required_fields=("fund_name", "technology_weight_pct"))
    rec = make_record(fields={"fund_name": "Tech Fund"})
    result = make_result(
        req,
        status=ProviderStatus.PARTIAL,
        records=(rec,),
        missing_fields=(),
        issues=(make_issue(safe_message="Response was truncated"),),
    )
    with pytest.raises(ValueError, match="actual missing|required field"):
        validate_result_for_request(req, result)


def test_record_units_must_be_strings() -> None:
    with pytest.raises(ValidationError):
        make_record(units={"technology_weight_pct": 123})


def test_4_empty_with_records_rejected() -> None:
    req = make_request()
    with pytest.raises(ValidationError, match="EMPTY result must not contain records"):
        make_result(
            req,
            status=ProviderStatus.EMPTY,
            records=(make_record(),),
            scope_description="No records found",
        )


def test_5_empty_without_scope_description_rejected() -> None:
    req = make_request()
    with pytest.raises(ValidationError, match="EMPTY result requires a non-empty scope_description"):
        make_result(
            req,
            status=ProviderStatus.EMPTY,
            records=(),
            scope_description=None,
        )


def test_6_failed_with_records_rejected() -> None:
    req = make_request()
    with pytest.raises(ValidationError, match="FAILED result must not contain records"):
        make_result(
            req,
            status=ProviderStatus.FAILED,
            records=(make_record(),),
            issues=(make_issue(),),
        )


def test_7_failed_without_issues_rejected() -> None:
    req = make_request()
    with pytest.raises(ValidationError, match="FAILED result requires at least one issue"):
        make_result(
            req,
            status=ProviderStatus.FAILED,
            records=(),
            issues=(),
        )


def test_8_failed_and_empty_serialization_distinct() -> None:
    req = make_request()
    empty_res = make_result(
        req,
        status=ProviderStatus.EMPTY,
        records=(),
        scope_description="Query scope has no records",
    )
    failed_res = make_result(
        req,
        status=ProviderStatus.FAILED,
        records=(),
        issues=(make_issue(code=ProviderIssueCode.TRANSPORT_ERROR, safe_message="Network connection failed"),),
    )

    empty_json = empty_res.model_dump_json()
    failed_json = failed_res.model_dump_json()

    assert empty_res.status == ProviderStatus.EMPTY
    assert failed_res.status == ProviderStatus.FAILED
    assert "EMPTY" in empty_json
    assert "FAILED" in failed_json
    assert empty_json != failed_json
    assert empty_res.scope_description is not None
    assert len(failed_res.issues) > 0


def test_16_success_generates_verified_evidence() -> None:
    req = make_request()
    record = make_record(
        fields={"fund_name": "Synthetic Tech Growth Fund", "technology_weight_pct": 63.5},
        units={"technology_weight_pct": "pct"},
    )
    result = make_result(req, records=(record,))
    evidence_list = normalize_result_to_evidence(result)

    assert len(evidence_list) == 2
    for ev in evidence_list:
        assert ev.quality_status == EvidenceQualityStatus.VERIFIED
        assert ev.quality_note is None
        assert ev.retrieved_at == NOW

    tech_ev = next(e for e in evidence_list if e.field == "technology_weight_pct")
    assert tech_ev.value == 63.5
    assert tech_ev.unit == "pct"


def test_17_partial_generates_partial_evidence_with_note() -> None:
    req = make_request()
    record = make_record(
        fields={"fund_name": "Synthetic Tech Growth Fund"},
    )
    result = make_result(
        req,
        status=ProviderStatus.PARTIAL,
        records=(record,),
        missing_fields=("technology_weight_pct",),
        issues=(make_issue(safe_message="Missing technology_weight_pct"),),
    )
    evidence_list = normalize_result_to_evidence(result)

    assert len(evidence_list) == 1
    ev = evidence_list[0]
    assert ev.quality_status == EvidenceQualityStatus.PARTIAL
    assert ev.quality_note is not None
    assert "technology_weight_pct" in ev.quality_note


def test_18_empty_and_failed_generate_zero_evidence() -> None:
    req = make_request()
    empty_res = make_result(
        req,
        status=ProviderStatus.EMPTY,
        records=(),
        scope_description="No data for scope",
    )
    failed_res = make_result(
        req,
        status=ProviderStatus.FAILED,
        records=(),
        issues=(make_issue(),),
    )

    assert normalize_result_to_evidence(empty_res) == ()
    assert normalize_result_to_evidence(failed_res) == ()


def test_19_real_zero_preserved_and_missing_not_zero() -> None:
    req = make_request()
    record = make_record(
        fields={"technology_weight_pct": 0.0, "cash_ratio": 0},
        units={"technology_weight_pct": "pct", "cash_ratio": "pct"},
    )
    result = make_result(req, records=(record,))
    evidence_list = normalize_result_to_evidence(result)

    assert len(evidence_list) == 2
    tech_ev = next(e for e in evidence_list if e.field == "technology_weight_pct")
    cash_ev = next(e for e in evidence_list if e.field == "cash_ratio")

    assert tech_ev.value == 0.0
    assert cash_ev.value == 0


def test_multi_records_generate_unique_evidence_ids_and_pass_decision_trace() -> None:
    req = make_request(required_fields=("technology_weight_pct",))
    rec1 = make_record(
        record_id="fund-001",
        fields={"technology_weight_pct": 63.5},
        units={"technology_weight_pct": "pct"},
        period="2026-06-30",
    )
    rec2 = make_record(
        record_id="fund-002",
        fields={"technology_weight_pct": 45.0},
        units={"technology_weight_pct": "pct"},
        period="2026-06-30",
    )
    result = make_result(req, records=(rec1, rec2))
    evidence_list = normalize_result_to_evidence(result)

    assert len(evidence_list) == 2
    assert evidence_list[0].evidence_id != evidence_list[1].evidence_id
    assert "fund-001" in evidence_list[0].evidence_id
    assert "fund-002" in evidence_list[1].evidence_id

    fact1 = Fact(
        fact_id="fact:tech:001",
        subject="fund:001",
        metric="technology_weight_pct",
        value=63.5,
        unit="pct",
        period="2026-06-30",
        status=FactStatus.VERIFIED,
        evidence_ids=(evidence_list[0].evidence_id,),
    )
    fact2 = Fact(
        fact_id="fact:tech:002",
        subject="fund:002",
        metric="technology_weight_pct",
        value=45.0,
        unit="pct",
        period="2026-06-30",
        status=FactStatus.VERIFIED,
        evidence_ids=(evidence_list[1].evidence_id,),
    )
    finding = Finding(
        finding_id="finding:tech:both",
        kind="CONCENTRATION_RISK",
        severity=FindingSeverity.WARNING,
        statement="两个科技基金持仓均具有科技暴露。",
        fact_ids=("fact:tech:001", "fact:tech:002"),
        confidence=0.95,
        methodology="concentration rule",
    )
    rec = Recommendation(
        recommendation_id="rec:reduce:both",
        action_type=ActionType.REDUCE,
        asset_id="portfolio:tech",
        allocation_range=AllocationRange(minimum_pct=Decimal("20"), maximum_pct=Decimal("40")),
        rationale="降低科技暴露",
        finding_ids=("finding:tech:both",),
        compliance_status=ComplianceStatus.PASSED,
        invalidation_conditions=("更新画像",),
    )

    trace = DecisionTrace(
        evidence=evidence_list,
        facts=(fact1, fact2),
        findings=(finding,),
        recommendations=(rec,),
    )
    assert len(trace.evidence) == 2


def test_duplicate_record_identity_is_rejected_before_decision_trace() -> None:
    req = make_request(required_fields=("technology_weight_pct",))
    rec1 = make_record(
        record_id="duplicate",
        fields={"technology_weight_pct": 63.5},
        period="2026-06-30",
    )
    rec2 = make_record(
        record_id="duplicate",
        fields={"technology_weight_pct": 45.0},
        period="2026-06-30",
    )
    result = make_result(req, records=(rec1, rec2))

    with pytest.raises(ValueError, match="duplicate record identity"):
        normalize_result_to_evidence(result)


def test_normalization_requires_a_stable_record_identity() -> None:
    req = make_request(required_fields=("technology_weight_pct",))
    record = make_record(
        lineage_id=None,
        record_id=None,
        fields={"technology_weight_pct": 63.5},
        period="2026-06-30",
    )
    result = make_result(req, records=(record,))

    with pytest.raises(ValueError, match="requires record_id or lineage_id"):
        normalize_result_to_evidence(result)


def test_evidence_id_escapes_delimiters_and_separates_requests() -> None:
    req_a = make_request(required_fields=("technology_weight_pct",), subject="FUND_A")
    req_b = make_request(required_fields=("technology_weight_pct",), subject="FUND_B")
    result_a = make_result(
        req_a,
        records=(
            make_record(
                source="source:a",
                record_id="record",
                fields={"technology_weight_pct": 63.5},
                period="2026-06-30",
            ),
            make_record(
                source="source",
                record_id="a:record",
                fields={"technology_weight_pct": 45.0},
                period="2026-06-30",
            ),
        ),
    )
    result_b = make_result(
        req_b,
        records=(
            make_record(
                source="source:a",
                record_id="record",
                fields={"technology_weight_pct": 63.5},
                period="2026-06-30",
            ),
        ),
    )

    ids_a = [item.evidence_id for item in normalize_result_to_evidence(result_a)]
    ids_b = [item.evidence_id for item in normalize_result_to_evidence(result_b)]
    assert len(ids_a) == len(set(ids_a)) == 2
    assert set(ids_a).isdisjoint(ids_b)
