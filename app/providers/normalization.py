"""Normalization of ProviderResult into domain Evidence."""

from __future__ import annotations

from urllib.parse import quote

from app.contracts.evidence import (
    Evidence,
    EvidenceQualityStatus,
)
from app.providers.contracts import ProviderRecord, ProviderResult, ProviderStatus


def _build_evidence_id(
    provider: str,
    source: str,
    record_identity: str,
    field: str,
    period: str | None,
    request_fingerprint: str,
) -> str:
    components = (
        provider,
        source,
        record_identity,
        field,
        period or "current",
        request_fingerprint,
    )
    return "ev:" + ":".join(quote(component, safe="") for component in components)


def _record_identity(record: ProviderRecord, index: int) -> str:
    record_id = record.record_id
    lineage_id = record.lineage_id
    if record_id:
        return record_id
    if lineage_id:
        return lineage_id
    raise ValueError(
        f"record at index {index} requires record_id or lineage_id for stable Evidence IDs"
    )


def normalize_result_to_evidence(
    result: ProviderResult,
) -> tuple[Evidence, ...]:
    """Convert validated ProviderResult into domain Evidence objects with stable unique IDs."""
    if result.status in (ProviderStatus.EMPTY, ProviderStatus.FAILED):
        return ()

    evidence_items: list[Evidence] = []
    seen_record_identities: set[tuple[str, str]] = set()
    effective_identities: dict[int, str] = {}
    for idx, record in enumerate(result.records):
        identity = _record_identity(record, idx)
        key = (record.source, identity)
        if key in seen_record_identities:
            raise ValueError(
                f"duplicate record identity {identity!r} for source {record.source!r}"
            )
        seen_record_identities.add(key)
        effective_identities[idx] = identity

    if result.status == ProviderStatus.SUCCESS:
        for idx, record in enumerate(result.records):
            record_identity = effective_identities[idx]
            for field_name, field_value in record.fields.items():
                if field_value is None:
                    continue
                ev_id = _build_evidence_id(
                    result.provider,
                    record.source,
                    record_identity,
                    field_name,
                    record.period,
                    result.request_fingerprint,
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
            record_identity = effective_identities[idx]
            for field_name, field_value in record.fields.items():
                if field_value is None:
                    continue
                ev_id = _build_evidence_id(
                    result.provider,
                    record.source,
                    record_identity,
                    field_name,
                    record.period,
                    result.request_fingerprint,
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
