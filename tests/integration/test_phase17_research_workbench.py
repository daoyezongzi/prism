import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from app.api import create_app
from app.research import ResearchSpecialistMatrixRequest, ResearchSpecialistRole
from app.service import FixtureResearchSpecialistMatrixService
from app.store import SQLiteDecisionEventStore


REPO_ROOT = Path(__file__).parents[2]
PROVIDER_DIR = REPO_ROOT / "app" / "fixtures" / "research" / "providers"
MATRIX_ID = "specialist-matrix-four-track-001"
NOW = datetime(2026, 9, 2, 2, tzinfo=UTC)


def _client(*, specialist_service=None):
    store = SQLiteDecisionEventStore(":memory:")
    client = TestClient(
        create_app(
            store,
            clock=lambda: NOW,
            specialist_service=specialist_service,
        )
    )
    return client, store


def _request(*, owner: str = "research-ui-owner", request_id: str = "research-ui-001"):
    return ResearchSpecialistMatrixRequest(
        matrix_id=MATRIX_ID,
        request_id=request_id,
        owner_id=owner,
        generated_at=NOW,
    )


def test_research_template_is_owner_scoped_and_does_not_expose_fixture_sources() -> None:
    client, store = _client()
    response = client.get(
        "/api/v1/advisor/research-matrix-template",
        headers={"X-Owner-ID": "research-template-owner"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "research-matrix-template.v1"
    assert body["owner_id"] == "research-template-owner"
    assert set(body["roles"]) == {item.value for item in ResearchSpecialistRole}
    assert body["node_count"] == 8
    assert "matrix-fund-source-a" not in response.text
    assert "expected_value" not in response.text
    store.close()


def test_research_run_api_returns_four_tracks_without_persisting_decision_event() -> None:
    client, store = _client()
    payload = _request().model_dump(mode="json")
    first = client.post(
        "/api/v1/advisor/research-runs",
        headers={"X-Owner-ID": "research-ui-owner"},
        json=payload,
    )
    assert first.status_code == 200
    body = first.json()
    assert body["pipeline_status"] == "READY"
    assert body["run_status"] == "COMPLETED"
    assert len(body["nodes"]) == 8
    assert {item["role"] for item in body["nodes"]} == {
        item.value for item in ResearchSpecialistRole
    }
    assert len(body["validations"]) == 4
    assert len(body["trace"]["facts"]) == 4
    assert len(body["trace"]["findings"]) == 4
    assert body["trace"]["recommendations"] == []
    assert "receipt" not in first.text.casefold()
    assert store.list("research-ui-owner") == ()

    repeated = client.post(
        "/api/v1/advisor/research-runs",
        headers={"X-Owner-ID": "research-ui-owner"},
        json=payload,
    )
    assert repeated.status_code == 200
    assert repeated.json() == body

    other = client.post(
        "/api/v1/advisor/research-runs",
        headers={"X-Owner-ID": "other-research-owner"},
        json=_request(owner="other-research-owner").model_dump(mode="json"),
    )
    assert other.status_code == 200
    assert other.json()["owner_id"] == "other-research-owner"
    assert "research-ui-owner" not in other.text
    store.close()


def test_research_run_api_one_hundred_replays_are_identical_and_side_effect_free() -> None:
    client, store = _client()
    payload = _request(request_id="research-replay-100").model_dump(mode="json")
    first = client.post(
        "/api/v1/advisor/research-runs",
        headers={"X-Owner-ID": payload["owner_id"]},
        json=payload,
    )
    assert first.status_code == 200
    expected = first.json()
    for _ in range(99):
        replay = client.post(
            "/api/v1/advisor/research-runs",
            headers={"X-Owner-ID": payload["owner_id"]},
            json=payload,
        )
        assert replay.status_code == 200
        assert replay.json() == expected
    assert store.list(payload["owner_id"]) == ()
    store.close()


def test_research_run_api_rejects_scope_extra_and_unknown_inputs_safely() -> None:
    client, store = _client()
    payload = _request().model_dump(mode="json")
    wrong_owner = client.post(
        "/api/v1/advisor/research-runs",
        headers={"X-Owner-ID": "other-owner"},
        json=payload,
    )
    assert wrong_owner.status_code == 403
    assert wrong_owner.json()["error_code"] == "OWNER_SCOPE"

    extra = dict(payload)
    extra["marker"] = "do-not-echo"
    extra_response = client.post(
        "/api/v1/advisor/research-runs",
        headers={"X-Owner-ID": payload["owner_id"]},
        json=extra,
    )
    assert extra_response.status_code == 422
    assert extra_response.json() == {
        "schema_version": "api-error.v1",
        "error_code": "INVALID_INPUT",
        "message": "request failed contract validation",
    }
    assert "do-not-echo" not in extra_response.text

    unknown = dict(payload)
    unknown["matrix_id"] = "unknown-matrix"
    unknown_response = client.post(
        "/api/v1/advisor/research-runs",
        headers={"X-Owner-ID": payload["owner_id"]},
        json=unknown,
    )
    assert unknown_response.status_code == 400
    assert unknown_response.json() == {
        "schema_version": "api-error.v1",
        "error_code": "RESEARCH_MATRIX_ERROR",
        "message": "research matrix was refused",
    }

    sensitive = dict(payload)
    sensitive["owner_id"] = "api_key-owner"
    sensitive_response = client.post(
        "/api/v1/advisor/research-runs",
        headers={"X-Owner-ID": payload["owner_id"]},
        json=sensitive,
    )
    assert sensitive_response.status_code == 422
    assert sensitive_response.json() == {
        "schema_version": "api-error.v1",
        "error_code": "INVALID_INPUT",
        "message": "request failed contract validation",
    }
    assert "api_key" not in sensitive_response.text.casefold()

    naive = dict(payload)
    naive["generated_at"] = "2026-09-02T02:00:00"
    naive_response = client.post(
        "/api/v1/advisor/research-runs",
        headers={"X-Owner-ID": payload["owner_id"]},
        json=naive,
    )
    assert naive_response.status_code == 422
    assert naive_response.json()["error_code"] == "INVALID_INPUT"

    missing = client.get("/api/v1/advisor/research-matrix-template")
    assert missing.status_code == 403
    store.close()


def test_research_api_rejects_pydantic_bypassed_output_without_leakage() -> None:
    base = FixtureResearchSpecialistMatrixService()

    class ForgedService:
        def matrix_template(self, owner_id):
            return base.matrix_template(owner_id)

        async def run(self, request):
            valid = await base.run(request)
            # model_copy(update=...) intentionally skips model validation; the
            # HTTP boundary must still enforce the authenticated owner closure.
            return valid.model_copy(update={"owner_id": "other-owner"})

    client, store = _client(specialist_service=ForgedService())
    response = client.post(
        "/api/v1/advisor/research-runs",
        headers={"X-Owner-ID": "research-ui-owner"},
        json=_request().model_dump(mode="json"),
    )
    assert response.status_code == 400
    assert response.json() == {
        "schema_version": "api-error.v1",
        "error_code": "RESEARCH_MATRIX_ERROR",
        "message": "research matrix was refused",
    }
    assert "other-owner" not in response.text
    store.close()


def test_degraded_matrix_api_keeps_review_and_no_facts() -> None:
    with TemporaryDirectory(prefix=".phase17-provider-", dir=REPO_ROOT) as raw_dir:
        provider_dir = Path(raw_dir)
        for source in PROVIDER_DIR.glob("*.json"):
            shutil.copy2(source, provider_dir / source.name)
        path = provider_dir / "fund_source_b.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["result"]["status"] = "PARTIAL"
        payload["result"]["records"][0]["fields"] = {"other_metric": "1.00"}
        payload["result"]["records"][0]["units"] = {"other_metric": "pct"}
        payload["result"]["missing_fields"] = ["technology_weight_pct"]
        payload["result"]["issues"] = [{
            "code": "INVALID_RESPONSE",
            "stage": "parse",
            "safe_message": "fixture omitted the requested field",
            "retriable": False,
            "diagnostics": {"missing_field": "technology_weight_pct"},
        }]
        path.write_text(json.dumps(payload), encoding="utf-8")

        service = FixtureResearchSpecialistMatrixService(provider_dir=provider_dir)
        client, store = _client(specialist_service=service)
        response = client.post(
            "/api/v1/advisor/research-runs",
            headers={"X-Owner-ID": "research-review-owner"},
            json=_request(owner="research-review-owner", request_id="research-review-001").model_dump(mode="json"),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["pipeline_status"] == "REVIEW_REQUIRED"
        assert body["run_status"] == "FAILED"
        assert body["trace"]["facts"] == []
        assert body["trace"]["findings"] == []
        assert body["trace"]["recommendations"] == []
        store.close()


def test_research_workbench_static_boundary_is_text_only() -> None:
    client, store = _client()
    page = client.get("/")
    css = client.get("/static/styles.css")
    js = client.get("/static/app.js")
    assert page.status_code == 200
    assert 'id="research-matrix-content"' in page.text
    assert 'id="run-research-matrix"' in page.text
    assert css.status_code == 200 and ".research-panel" in css.text
    assert js.status_code == 200
    assert "/api/v1/advisor/research-matrix-template" in js.text
    assert "/api/v1/advisor/research-runs" in js.text
    assert "innerHTML" not in js.text
    assert "<script>" not in page.text
    assert "https://" not in page.text
    store.close()
