from datetime import UTC, datetime
import pytest
from pydantic import ValidationError

from app.providers.contracts import (
    ProviderIssue,
    ProviderIssueCode,
    ProviderOperation,
    ProviderRequest,
)
from app.providers.fingerprint import (
    compute_request_fingerprint,
    redact_sensitive_data,
)

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)


def test_9_request_rejects_sensitive_keys_in_parameters() -> None:
    sensitive_keys = [
        "token",
        "api_key",
        "apiKey",
        "API_KEY",
        "authorization",
        "cookie",
        "secret",
        "password",
        "credential",
    ]
    for key in sensitive_keys:
        with pytest.raises(ValidationError, match="forbidden sensitive key"):
            ProviderRequest(
                request_id="req-test",
                operation=ProviderOperation.FUND_DATA,
                subject="FUND_FIXTURE_001",
                parameters={key: "secret-value"},
            )


def test_9_request_rejects_nested_sensitive_keys_in_parameters() -> None:
    nested_cases = [
        {"nested": {"api_key": "secret"}},
        {"deep": {"level2": {"level3": {"password": "pwd"}}}},
        {"list_of_dicts": [{"safe": 1}, {"auth_token": "tok"}]},
    ]
    for case in nested_cases:
        with pytest.raises(ValidationError, match="forbidden sensitive key"):
            ProviderRequest(
                request_id="req-nested-test",
                operation=ProviderOperation.FUND_DATA,
                subject="FUND_FIXTURE_001",
                parameters=case,
            )


def test_9_issue_rejects_nested_sensitive_keys_in_diagnostics() -> None:
    nested_cases = [
        {"trace": {"headers": {"authorization": "Bearer xxx"}}},
        {"env": [{"api_key": "key123"}]},
    ]
    for case in nested_cases:
        with pytest.raises(ValidationError, match="forbidden sensitive key"):
            ProviderIssue(
                code=ProviderIssueCode.INTERNAL_ERROR,
                stage="runtime",
                safe_message="Internal error",
                retriable=False,
                diagnostics=case,
            )


def test_10_diagnostics_nested_sensitive_keys_redacted() -> None:
    raw_diagnostics = {
        "status_code": 401,
        "auth_header": "Bearer secret_jwt_token",
        "user_info": {
            "username": "trader",
            "api_key": "my_secret_key",
            "nested": {
                "password": "super_secret_password",
                "cookie": "session_cookie=abc",
                "safe_field": 12345,
            },
        },
        "tokens": ["tok1", "tok2"],
    }
    redacted = redact_sensitive_data(raw_diagnostics)

    assert redacted["status_code"] == 401
    assert redacted["auth_header"] == "[REDACTED]"
    assert redacted["user_info"]["api_key"] == "[REDACTED]"
    assert redacted["user_info"]["nested"]["password"] == "[REDACTED]"
    assert redacted["user_info"]["nested"]["cookie"] == "[REDACTED]"
    assert redacted["user_info"]["nested"]["safe_field"] == 12345
    assert redacted["tokens"] == "[REDACTED]"


def test_11_fingerprint_invariant_to_key_order() -> None:
    req1 = ProviderRequest(
        request_id="req-1",
        operation=ProviderOperation.FUND_DATA,
        subject="FUND_001",
        parameters={"alpha": 1, "beta": 2, "gamma": {"x": 10, "y": 20}},
        required_fields=("field_b", "field_a"),
    )
    req2 = ProviderRequest(
        request_id="req-2",
        operation=ProviderOperation.FUND_DATA,
        subject="FUND_001",
        parameters={"beta": 2, "gamma": {"y": 20, "x": 10}, "alpha": 1},
        required_fields=("field_a", "field_b"),
    )

    fp1 = compute_request_fingerprint(req1)
    fp2 = compute_request_fingerprint(req2)

    assert fp1 == fp2
    assert len(fp1) == 64
    assert fp1 == fp1.lower()


def test_12_fingerprint_changes_on_semantic_difference() -> None:
    base = ProviderRequest(
        request_id="req-base",
        operation=ProviderOperation.FUND_DATA,
        subject="FUND_001",
        as_of=NOW,
        required_fields=("field_a",),
        parameters={"period": "2026-06-30"},
    )
    base_fp = compute_request_fingerprint(base)

    op_diff = base.model_copy(update={"operation": ProviderOperation.MARKET_DATA})
    assert compute_request_fingerprint(op_diff) != base_fp

    subj_diff = base.model_copy(update={"subject": "FUND_002"})
    assert compute_request_fingerprint(subj_diff) != base_fp

    as_of_diff = base.model_copy(update={"as_of": LATER})
    assert compute_request_fingerprint(as_of_diff) != base_fp

    fields_diff = base.model_copy(update={"required_fields": ("field_a", "field_b")})
    assert compute_request_fingerprint(fields_diff) != base_fp

    param_diff = base.model_copy(update={"parameters": {"period": "2026-03-31"}})
    assert compute_request_fingerprint(param_diff) != base_fp


def test_13_fingerprint_ignores_request_id_and_timeout() -> None:
    req1 = ProviderRequest(
        request_id="req-alpha",
        operation=ProviderOperation.FUND_DATA,
        subject="FUND_001",
        as_of=NOW,
        timeout_ms=1000,
        parameters={"period": "2026-06-30"},
    )
    req2 = ProviderRequest(
        request_id="req-beta",
        operation=ProviderOperation.FUND_DATA,
        subject="FUND_001",
        as_of=NOW,
        timeout_ms=5000,
        parameters={"period": "2026-06-30"},
    )

    assert compute_request_fingerprint(req1) == compute_request_fingerprint(req2)


def test_request_parameters_deeply_immutable() -> None:
    req = ProviderRequest(
        request_id="req-immut",
        operation=ProviderOperation.FUND_DATA,
        subject="FUND_001",
        parameters={"period": "2026-06-30", "nested": {"k": "v"}},
    )
    with pytest.raises(TypeError, match="FrozenDict is immutable"):
        req.parameters["period"] = "2026-09-30"

    with pytest.raises(TypeError, match="FrozenDict is immutable"):
        req.parameters["nested"]["k"] = "new_v"


def test_request_rejects_non_json_parameter_values() -> None:
    non_json_values = [object(), {"unordered"}]
    for value in non_json_values:
        with pytest.raises(ValidationError):
            ProviderRequest(
                request_id="req-non-json",
                operation=ProviderOperation.FUND_DATA,
                subject="FUND_001",
                parameters={"value": value},
            )


def test_frozen_dict_freezes_deep_sequences_and_in_place_union() -> None:
    req = ProviderRequest(
        request_id="req-immut-deep",
        operation=ProviderOperation.FUND_DATA,
        subject="FUND_001",
        parameters={"layers": [[{"safe": 1}]]},
    )

    with pytest.raises(AttributeError):
        req.parameters["layers"][0].append("mutated")

    with pytest.raises(TypeError, match="FrozenDict is immutable"):
        req.parameters.__ior__({"added": 1})

    assert "added" not in req.parameters
