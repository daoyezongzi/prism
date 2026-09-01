"""Independent risk/compliance eligibility gates for Prism."""

from app.gates.compliance import evaluate_compliance_gate, scan_compliance_texts
from app.gates.contracts import (
    REQUIRED_DISCLOSURES,
    AdvisoryCandidate,
    ComplianceGateIssue,
    ComplianceGateIssueCode,
    ComplianceGateResult,
    DecisionGateResult,
    DisclosureCode,
    GateStatus,
    RiskGateIssue,
    RiskGateIssueCode,
    RiskGateResult,
)
from app.gates.pipeline import evaluate_decision_gates
from app.gates.risk import evaluate_risk_gate

__all__ = [
    "REQUIRED_DISCLOSURES",
    "AdvisoryCandidate",
    "ComplianceGateIssue",
    "ComplianceGateIssueCode",
    "ComplianceGateResult",
    "DecisionGateResult",
    "DisclosureCode",
    "GateStatus",
    "RiskGateIssue",
    "RiskGateIssueCode",
    "RiskGateResult",
    "evaluate_compliance_gate",
    "evaluate_decision_gates",
    "evaluate_risk_gate",
    "scan_compliance_texts",
]
