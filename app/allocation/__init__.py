"""Deterministic profile-conditioned allocation constraint envelopes."""

from app.allocation.contracts import (
    AllocationBand,
    AllocationBandDimension,
    AllocationBandDisposition,
    AllocationEnvelope,
    AllocationIssue,
    AllocationIssueCode,
    AllocationResult,
    AllocationStatus,
    ConstraintImpact,
)
from app.allocation.envelope import build_allocation_envelope

__all__ = [
    "AllocationBand",
    "AllocationBandDimension",
    "AllocationBandDisposition",
    "AllocationEnvelope",
    "AllocationIssue",
    "AllocationIssueCode",
    "AllocationResult",
    "AllocationStatus",
    "ConstraintImpact",
    "build_allocation_envelope",
]
