"""Service for recommendation history retrieval and comparison."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from app.history.contracts import (
    RecommendationComparisonRequest,
    RecommendationComparisonResponse,
    RecommendationHistoryItem,
    RecommendationHistoryResponse,
)

if TYPE_CHECKING:
    from app.store.sqlite import DecisionEventStore


class RecommendationHistoryService:
    """Owner-scoped service for querying and comparing recommendation history."""

    def __init__(self, store: DecisionEventStore) -> None:
        self._store = store

    def get_history(
        self,
        owner_id: str,
        limit: int = 50,
        action_filter: str | None = None,
    ) -> RecommendationHistoryResponse:
        summaries = self._store.list(owner_id)
        items: list[RecommendationHistoryItem] = []

        for summary in summaries:
            event = self._store.get(owner_id, summary.event_id)
            if event is None:
                continue

            rec = (
                event.result.trace.recommendations[0]
                if event.result.trace.recommendations
                else None
            )

            action_type = rec.action_type if rec else None
            if action_filter and action_type and action_type.value != action_filter:
                continue

            item = RecommendationHistoryItem(
                event_id=event.event_id,
                receipt_id=event.receipt_id,
                composition_id=event.composition_id,
                status=event.status,
                action_type=action_type,
                asset=rec.asset_id if rec else None,
                allocation_range=rec.allocation_range if rec else None,
                risk_score=None,
                profile_version=event.result.receipt.profile_id if event.result.receipt else None,
                recorded_at=event.recorded_at,
                content_hash=event.content_hash,
                finding_count=len(event.result.trace.findings),
                invalidation_conditions=rec.invalidation_conditions if rec else (),
                summary=event.result.summary,
            )
            items.append(item)

        items_slice = tuple(items[:limit])
        return RecommendationHistoryResponse(
            owner_id=owner_id,
            total_count=len(items_slice),
            items=items_slice,
        )

    def compare_receipts(
        self,
        request: RecommendationComparisonRequest,
    ) -> RecommendationComparisonResponse:
        summaries = self._store.list(request.owner_id)

        event_a = None
        event_b = None

        for summary in summaries:
            event = self._store.get(request.owner_id, summary.event_id)
            if event is None:
                continue
            if event.receipt_id == request.receipt_a_id:
                event_a = event
            if event.receipt_id == request.receipt_b_id:
                event_b = event

        if event_a is None:
            raise KeyError(f"Receipt A '{request.receipt_a_id}' not found for owner '{request.owner_id}'")
        if event_b is None:
            raise KeyError(f"Receipt B '{request.receipt_b_id}' not found for owner '{request.owner_id}'")

        rec_a = event_a.result.trace.recommendations[0] if event_a.result.trace.recommendations else None
        rec_b = event_b.result.trace.recommendations[0] if event_b.result.trace.recommendations else None

        action_a = rec_a.action_type if rec_a else None
        action_b = rec_b.action_type if rec_b else None
        action_changed = action_a != action_b
        action_transition = (
            f"{action_a.value if action_a else 'NONE'} -> {action_b.value if action_b else 'NONE'}"
        )

        score_a = None
        score_b = None
        score_delta = None

        range_a = rec_a.allocation_range if rec_a else None
        range_b = rec_b.allocation_range if rec_b else None

        min_delta = (range_b.minimum_pct - range_a.minimum_pct) if (range_a and range_b) else None
        max_delta = (range_b.maximum_pct - range_a.maximum_pct) if (range_a and range_b) else None

        inv_a = set(rec_a.invalidation_conditions) if rec_a else set()
        inv_b = set(rec_b.invalidation_conditions) if rec_b else set()

        new_inv = tuple(sorted(inv_b - inv_a))
        rem_inv = tuple(sorted(inv_a - inv_b))

        summary = (
            f"建议动作: {action_transition} (状态: {event_a.status.value} -> {event_b.status.value}); "
            f"事实判断数: {len(event_a.result.trace.findings)} -> {len(event_b.result.trace.findings)}"
        )

        return RecommendationComparisonResponse(
            owner_id=request.owner_id,
            receipt_a_id=request.receipt_a_id,
            receipt_b_id=request.receipt_b_id,
            event_a_id=event_a.event_id,
            event_b_id=event_b.event_id,
            action_a=action_a,
            action_b=action_b,
            action_changed=action_changed,
            action_transition=action_transition,
            risk_score_a=score_a,
            risk_score_b=score_b,
            risk_score_delta=score_delta,
            allocation_range_a=range_a,
            allocation_range_b=range_b,
            min_allocation_delta_pct=min_delta,
            max_allocation_delta_pct=max_delta,
            findings_count_a=len(event_a.result.trace.findings),
            findings_count_b=len(event_b.result.trace.findings),
            new_invalidation_conditions=new_inv,
            removed_invalidation_conditions=rem_inv,
            summary=summary,
        )
