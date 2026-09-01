import asyncio
from datetime import UTC, datetime

import pytest

from app.research import (
    ResearchNodeKind,
    ResearchSpecialistMatrix,
    ResearchSpecialistMatrixRequest,
    ResearchSpecialistRole,
    allowed_operations_for_node,
)
from app.service import (
    FixtureResearchSpecialistMatrixService,
    SpecialistMatrixError,
)
from app.orchestration import ResearchPipelineIssueCode, build_research_evidence_pipeline


def _service() -> FixtureResearchSpecialistMatrixService:
    return FixtureResearchSpecialistMatrixService()


def test_matrix_covers_four_roles_and_declared_provider_operations() -> None:
    matrix = _service().matrix_template("matrix-unit-owner")

    assert {node.role for node in matrix.nodes} == set(ResearchSpecialistRole)
    assert {node.node_kind for node in matrix.nodes} == {
        ResearchNodeKind.MACRO,
        ResearchNodeKind.INDUSTRY,
        ResearchNodeKind.STOCK,
        ResearchNodeKind.FUND,
    }
    assert all(node.operation in allowed_operations_for_node(node.node_kind) for node in matrix.nodes)
    assert len(matrix.claims()) == 4
    assert all(
        len({node.lineage_id for node in matrix.nodes if node.claim_id == claim.claim_id}) >= 2
        for claim in matrix.claims()
    )


def test_node_kind_operation_and_role_mismatch_are_rejected() -> None:
    matrix = _service().matrix_template("matrix-unit-owner")
    node = next(item for item in matrix.nodes if item.role == ResearchSpecialistRole.MACRO)

    wrong_operation = node.model_dump(mode="python")
    wrong_operation["operation"] = "FUND_DATA"
    with pytest.raises(ValueError, match="operation"):
        type(node).model_validate(wrong_operation)

    wrong_role = node.model_dump(mode="python")
    wrong_role["role"] = "ETF_FUND"
    with pytest.raises(ValueError, match="role"):
        type(node).model_validate(wrong_role)


def test_matrix_rejects_missing_kind_duplicate_lineage_and_claim_drift() -> None:
    matrix = _service().matrix_template("matrix-unit-owner")
    payload = matrix.model_dump(mode="python")

    payload["nodes"] = tuple(
        node for node in payload["nodes"] if node["node_kind"] != ResearchNodeKind.MACRO
    )
    with pytest.raises(ValueError, match="missing node kind"):
        ResearchSpecialistMatrix.model_validate(payload)

    duplicate = matrix.model_dump(mode="python")
    duplicate["nodes"] = list(duplicate["nodes"])
    duplicate["nodes"][1]["lineage_id"] = duplicate["nodes"][0]["lineage_id"]
    with pytest.raises(ValueError, match="lineage IDs"):
        ResearchSpecialistMatrix.model_validate(duplicate)

    drift = matrix.model_dump(mode="python")
    drift["nodes"] = list(drift["nodes"])
    drift["nodes"][1]["expected_value"] = "64.00"
    with pytest.raises(ValueError, match="inconsistent source metadata"):
        ResearchSpecialistMatrix.model_validate(drift)

    cycle = matrix.model_dump(mode="python")
    cycle["nodes"] = list(cycle["nodes"])
    cycle["nodes"][0]["dependencies"] = (cycle["nodes"][1]["node_id"],)
    cycle["nodes"][1]["dependencies"] = (cycle["nodes"][0]["node_id"],)
    with pytest.raises(ValueError, match="cycle"):
        ResearchSpecialistMatrix.model_validate(cycle)


def test_matrix_template_and_forged_request_refuse_sensitive_owner() -> None:
    with pytest.raises(SpecialistMatrixError, match="refused"):
        _service().matrix_template("api_key-owner")

    service = _service()
    forged = ResearchSpecialistMatrixRequest.model_construct(
        schema_version="research-specialist-matrix-request.v1",
        matrix_id=service.matrix_id,
        request_id="matrix-forged",
        owner_id="credential-owner",
        generated_at=datetime(2026, 9, 2, tzinfo=UTC),
    )
    assert forged.owner_id == "credential-owner"
    with pytest.raises(SpecialistMatrixError, match="refused"):
        asyncio.run(service.run(forged))


def test_explicit_claim_scope_cannot_hide_same_subject_observations() -> None:
    service = _service()
    output = asyncio.run(
        service.run(
            ResearchSpecialistMatrixRequest(
                matrix_id=service.matrix_id,
                request_id="matrix-scope-guard",
                owner_id="matrix-scope-owner",
                generated_at="2026-09-02T01:00:00Z",
            )
        )
    )
    claim = next(
        spec
        for spec in service._claim_specs(output.matrix, output.execution)
        if spec.claim.claim_id == "claim-stock-revenue"
    )
    narrowed = claim.model_copy(update={"observation_ids": claim.observation_ids[:1]})
    result = build_research_evidence_pipeline(output.execution, (narrowed,))
    assert result.status.value == "BLOCKED"
    assert result.trace.facts == ()
    assert result.trace.findings == ()
    assert result.issues[0].code == ResearchPipelineIssueCode.CLAIM_INVALID
