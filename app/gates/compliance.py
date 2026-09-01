"""Deterministic compliance preflight independent from recommendation creation."""

from __future__ import annotations

import re
from hashlib import sha256
from typing import TypeVar

from app.contracts.evidence import EvidenceQualityStatus, FactStatus
from app.profile.contracts import RiskProfile
from app.research.pipeline import (
    ResearchEvidencePipelineResult,
    ResearchPipelineStatus,
)

from app.gates.contracts import (
    REQUIRED_DISCLOSURES,
    AdvisoryCandidate,
    ComplianceGateIssue,
    ComplianceGateIssueCode,
    ComplianceGateResult,
    GateStatus,
)
from app.gates.fingerprint import canonical_model_signature


_T = TypeVar("_T")
_SENSITIVE_SUBSTRINGS = (
    "api_key",
    "apikey",
    "authorization",
    "password",
    "private_key",
    "secret",
    "token",
    "credential",
    "cookie",
)
_GUARANTEE_PATTERNS = (
    r"稳赚不赔",
    r"稳赚",
    r"保证(?:收益|回报|盈利|赚钱)",
    r"保本",
    r"无风险",
    r"必涨",
    r"肯定上涨",
    r"guarantee(?:d)?",
    r"risk[- ]?free",
    r"no[- ]?loss",
)
_TARGET_RETURN_PATTERNS = (
    r"(?:目标|预期|预计|至少|可达|有望|承诺)\s*(?:收益|回报|收益率|回报率)\s*(?:达到|超过|不低于|为|是)?\s*\d+(?:\.\d+)?\s*%",
    r"(?:收益|回报|收益率|回报率|return|yield)\s*(?:达到|超过|不低于|为|是)?\s*\d+(?:\.\d+)?\s*%",
    r"\b\d+(?:\.\d+)?\s*%\s*(?:收益|回报|return|yield)",
    r"(?:目标|预期|预计|至少|可达|有望|承诺)\s*(?:年化)?\s*\d+(?:\.\d+)?\s*%",
)
_MAX_POLICY_VALUE_LENGTH = 4096
_MAX_POLICY_TOTAL_LENGTH = 16384
_MAX_POLICY_VALUES = 100


def _contains_sensitive(value: str) -> bool:
    normalized = value.casefold().replace("-", "_")
    return any(item in normalized for item in _SENSITIVE_SUBSTRINGS)


def _safe_text(value: object, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    value = value.strip()
    if not value or _contains_sensitive(value):
        return fallback
    return value


def _revalidate(model: _T) -> _T | None:
    try:
        model_type = type(model)
        return model_type.model_validate(model.model_dump(mode="python"))
    except Exception:
        return None


def _stable_id(*parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return "compliance-gate:" + sha256(payload).hexdigest()[:32]


def _issue(code: ComplianceGateIssueCode, message: str) -> ComplianceGateIssue:
    return ComplianceGateIssue(code=code, safe_message=message)


def _scan_values(
    metadata: tuple[str, ...], texts: tuple[str, ...]
) -> tuple[ComplianceGateIssueCode, ...]:
    values = metadata + texts
    if (
        len(values) > _MAX_POLICY_VALUES
        or any(len(value) > _MAX_POLICY_VALUE_LENGTH for value in values)
        or sum(len(value) for value in values) > _MAX_POLICY_TOTAL_LENGTH
    ):
        return (ComplianceGateIssueCode.INVALID_INPUT,)
    if any(_contains_sensitive(value) for value in metadata):
        return (ComplianceGateIssueCode.SENSITIVE_INPUT,)
    if any(_contains_sensitive(value) for value in texts):
        return (ComplianceGateIssueCode.SENSITIVE_INPUT,)

    # A plain disclaimer must not be mistaken for a guarantee.  Machine-readable
    # disclosures remain mandatory; this exception only avoids blocking a correct
    # human-facing negation such as “不保证收益”.
    joined = " ".join(texts).casefold()
    for phrase in (
        "不保证收益",
        "不能保证收益",
        "无法保证收益",
        "不承诺收益",
        "不保本",
        "并非无风险",
        "不是无风险",
        "not guaranteed",
        "no guarantee",
        "not risk-free",
    ):
        joined = joined.replace(phrase.casefold(), " ")

    codes: list[ComplianceGateIssueCode] = []
    if any(
        re.search(pattern, joined, flags=re.IGNORECASE)
        for pattern in _GUARANTEE_PATTERNS
    ):
        codes.append(ComplianceGateIssueCode.GUARANTEE_LANGUAGE)
    if any(
        re.search(pattern, joined, flags=re.IGNORECASE)
        for pattern in _TARGET_RETURN_PATTERNS
    ):
        codes.append(ComplianceGateIssueCode.TARGET_RETURN_LANGUAGE)
    return tuple(codes)


def scan_compliance_texts(
    *, metadata: tuple[str, ...] = (), texts: tuple[str, ...] = ()
) -> tuple[ComplianceGateIssueCode, ...]:
    """Reuse the gate's bounded text policy at downstream trust boundaries."""

    return _scan_values(metadata, texts)


def _scan_candidate(candidate: AdvisoryCandidate) -> tuple[ComplianceGateIssueCode, ...]:
    return _scan_values(
        (candidate.candidate_id, candidate.owner_id, *candidate.finding_ids),
        (candidate.statement, candidate.rationale, *candidate.invalidation_conditions),
    )


def evaluate_compliance_gate(
    profile: RiskProfile,
    pipeline: ResearchEvidencePipelineResult,
    candidate: AdvisoryCandidate,
) -> ComplianceGateResult:
    """Check evidence references and static compliance policy without echoing text."""

    owner_id = _safe_text(getattr(profile, "owner_id", None), "unknown-owner")
    run_id = _safe_text(getattr(pipeline, "run_id", None), "unknown-run")
    candidate_id = _safe_text(
        getattr(candidate, "candidate_id", None), "unknown-candidate"
    )
    input_signatures = (
        canonical_model_signature(profile),
        canonical_model_signature(pipeline),
        canonical_model_signature(candidate),
    )
    normalized_profile = _revalidate(profile)
    normalized_pipeline = _revalidate(pipeline)
    normalized_candidate = _revalidate(candidate)
    if not (
        isinstance(normalized_profile, RiskProfile)
        and isinstance(normalized_pipeline, ResearchEvidencePipelineResult)
        and isinstance(normalized_candidate, AdvisoryCandidate)
    ):
        return ComplianceGateResult(
            gate_id=_stable_id(*input_signatures),
            candidate_id=candidate_id,
            owner_id=owner_id,
            research_run_id=run_id,
            status=GateStatus.BLOCKED,
            issues=(
                _issue(
                    ComplianceGateIssueCode.INVALID_INPUT,
                    "gate input failed contract validation",
                ),
            ),
        )

    profile = normalized_profile
    pipeline = normalized_pipeline
    candidate = normalized_candidate
    actual_owner_id = profile.owner_id
    owner_id = _safe_text(actual_owner_id, "unknown-owner")
    run_id = _safe_text(pipeline.run_id, "unknown-run")
    candidate_id = _safe_text(candidate.candidate_id, "unknown-candidate")
    issues: list[ComplianceGateIssue] = []
    blocked = False
    review = False

    def add(code: ComplianceGateIssueCode, message: str, *, is_blocked: bool = False) -> None:
        nonlocal blocked, review
        if not any(item.code == code for item in issues):
            issues.append(_issue(code, message))
        if is_blocked:
            blocked = True
        else:
            review = True

    if candidate.owner_id != actual_owner_id or pipeline.owner_id != actual_owner_id:
        add(
            ComplianceGateIssueCode.OWNER_MISMATCH,
            "candidate and evidence pipeline do not share one owner",
            is_blocked=True,
        )

    for code in _scan_candidate(candidate):
        if code == ComplianceGateIssueCode.INVALID_INPUT:
            add(code, "candidate exceeds the bounded compliance policy", is_blocked=True)
        elif code == ComplianceGateIssueCode.SENSITIVE_INPUT:
            add(code, "candidate contains sensitive input", is_blocked=True)
        elif code == ComplianceGateIssueCode.GUARANTEE_LANGUAGE:
            add(code, "candidate contains prohibited guarantee language", is_blocked=True)
        elif code == ComplianceGateIssueCode.TARGET_RETURN_LANGUAGE:
            add(code, "candidate contains a prohibited target return", is_blocked=True)

    present_disclosures = tuple(
        code for code in REQUIRED_DISCLOSURES if code in candidate.disclosure_codes
    )
    if present_disclosures != REQUIRED_DISCLOSURES:
        add(
            ComplianceGateIssueCode.MISSING_DISCLOSURE,
            "candidate is missing a required risk disclosure",
        )

    if pipeline.status == ResearchPipelineStatus.BLOCKED:
        add(
            ComplianceGateIssueCode.PIPELINE_BLOCKED,
            "research evidence pipeline is blocked",
            is_blocked=True,
        )
    elif pipeline.status == ResearchPipelineStatus.REVIEW_REQUIRED:
        add(
            ComplianceGateIssueCode.PIPELINE_REVIEW_REQUIRED,
            "research evidence requires human review",
        )
    else:
        trace = pipeline.trace
        findings_by_id = {item.finding_id: item for item in trace.findings}
        facts_by_id = {item.fact_id: item for item in trace.facts}
        evidence_by_id = {item.evidence_id: item for item in trace.evidence}
        for bridge in pipeline.bridges:
            if bridge.fact is None or bridge.finding is None:
                add(
                    ComplianceGateIssueCode.TRACE_INTEGRITY,
                    "ready research bridge is incomplete",
                    is_blocked=True,
                )
                continue
            if (
                facts_by_id.get(bridge.fact.fact_id) != bridge.fact
                or findings_by_id.get(bridge.finding.finding_id) != bridge.finding
            ):
                add(
                    ComplianceGateIssueCode.TRACE_INTEGRITY,
                    "research bridge does not match the registered trace",
                    is_blocked=True,
                )
        unknown = [
            finding_id
            for finding_id in candidate.finding_ids
            if finding_id not in findings_by_id
        ]
        if unknown:
            add(
                ComplianceGateIssueCode.UNKNOWN_FINDING,
                "candidate references a finding outside the ready trace",
                is_blocked=True,
            )
        for finding_id in candidate.finding_ids:
            finding = findings_by_id.get(finding_id)
            if finding is None:
                continue
            for code in _scan_values(
                (finding.finding_id, finding.kind, *finding.fact_ids),
                (finding.statement, finding.methodology),
            ):
                if code == ComplianceGateIssueCode.INVALID_INPUT:
                    add(
                        code,
                        "candidate finding exceeds the bounded compliance policy",
                        is_blocked=True,
                    )
                elif code == ComplianceGateIssueCode.SENSITIVE_INPUT:
                    add(
                        code,
                        "candidate finding contains sensitive input",
                        is_blocked=True,
                    )
                elif code == ComplianceGateIssueCode.GUARANTEE_LANGUAGE:
                    add(
                        code,
                        "candidate finding contains prohibited guarantee language",
                        is_blocked=True,
                    )
                elif code == ComplianceGateIssueCode.TARGET_RETURN_LANGUAGE:
                    add(
                        code,
                        "candidate finding contains a prohibited target return",
                        is_blocked=True,
                    )
            for fact_id in finding.fact_ids:
                fact = facts_by_id.get(fact_id)
                if fact is None:
                    add(
                        ComplianceGateIssueCode.TRACE_INTEGRITY,
                        "candidate finding has an unknown fact reference",
                        is_blocked=True,
                    )
                    continue
                if fact.status != FactStatus.VERIFIED:
                    add(
                        ComplianceGateIssueCode.NON_VERIFIED_FACT,
                        "candidate finding depends on a non-verified fact",
                        is_blocked=True,
                    )
                for evidence_id in fact.evidence_ids:
                    evidence = evidence_by_id.get(evidence_id)
                    if evidence is None:
                        add(
                            ComplianceGateIssueCode.TRACE_INTEGRITY,
                            "candidate fact has an unknown evidence reference",
                            is_blocked=True,
                        )
                    elif evidence.quality_status != EvidenceQualityStatus.VERIFIED:
                        add(
                            ComplianceGateIssueCode.NON_VERIFIED_EVIDENCE,
                            "candidate depends on non-verified evidence",
                            is_blocked=True,
                        )

    status = (
        GateStatus.BLOCKED
        if blocked
        else GateStatus.REVIEW_REQUIRED
        if review
        else GateStatus.PASS
    )
    known_finding_ids = {item.finding_id for item in pipeline.trace.findings}
    checked_finding_ids = tuple(
        sorted(
            finding_id
            for finding_id in candidate.finding_ids
            if finding_id in known_finding_ids
        )
    )
    return ComplianceGateResult(
        gate_id=_stable_id(*input_signatures),
        candidate_id=candidate_id,
        owner_id=owner_id,
        research_run_id=run_id,
        status=status,
        present_disclosures=present_disclosures,
        checked_finding_ids=checked_finding_ids,
        issues=tuple(sorted(issues, key=lambda item: item.code.value)),
    )
