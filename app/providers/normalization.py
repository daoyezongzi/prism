"""Normalization of ProviderResult into domain Evidence."""

from __future__ import annotations

from app.contracts.evidence import (
    Evidence,
    EvidenceQualityStatus,
)
from app.providers.contracts import ProviderResult, ProviderStatus


def _build_evidence_id(
    provider: str,
    source: str,
    record_identity: str,
    field: str,
    period: str | None,
) -> str:
    period_part = period or "current"
    return f"ev:{provider}:{source}:{record_identity}:{field}:{period_part}"


def normalize_result_to_evidence(
    result: ProviderResult,
) -> tuple[Evidence, ...]:
    """Convert validated ProviderResult into domain Evidence objects with stable unique IDs."""
    if result.status in (ProviderStatus.EMPTY, ProviderStatus.FAILED):
        return ()

    evidence_items: list[Evidence] = []

    if result.status == ProviderStatus.SUCCESS:
        for idx, record in enumerate(result.records):
            record_identity = record.record_id or record.lineage_id or f"rec_{idx}"
            for field_name, field_value in record.fields.items():
                if field_value is None:
                    continue
                ev_id = _build_evidence_id(
                    result.provider,
                    record.source,
                    record_identity,
                    field_name,
                    record.period,
                )
                evidence_items.append(
                    Evidence(
                        evidence_id=ev_id,
                        provider=result.provider,
                        source=record.source,
                        field=field_name,
                        value=field_value,
                        unit=record.units.get(field_name),
                        period=record.period,
                        observed_at=record.observed_at,
                        retrieved_at=result.retrieved_at,
                        quality_status=EvidenceQualityStatus.VERIFIED,
                        quality_note=None,
                        lineage_id=record.lineage_id,
                    )
                )
    elif result.status == ProviderStatus.PARTIAL:
        missing_desc = (
            ", ".join(result.missing_fields)
            if result.missing_fields
            else "partial payload"
        )
        for idx, record in enumerate(result.records):
            record_identity = record.record_id or record.lineage_id or f"rec_{idx}"
            for field_name, field_value in record.fields.items():
                if field_value is None:
                    continue
                ev_id = _build_evidence_id(
                    result.provider,
                    record.source,
                    record_identity,
                    field_name,
                    record.period,
                )
                evidence_items.append(
                    Evidence(
                        evidence_id=ev_id,
                        provider=result.provider,
                        source=record.source,
                        field=field_name,
                        value=field_value,
                        unit=record.units.get(field_name),
                        period=record.period,
                        observed_at=record.observed_at,
                        retrieved_at=result.retrieved_at,
                        quality_status=EvidenceQualityStatus.PARTIAL,
                        quality_note=f"Partial observation from provider '{result.provider}'. Missing fields: {missing_desc}",
                        lineage_id=record.lineage_id,
                    )
                )

    return tuple(evidence_items)
