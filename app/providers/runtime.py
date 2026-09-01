"""Async budget execution wrapper with safe error mapping."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import logging

from app.providers.contracts import (
    FinancialProvider,
    ProviderIssue,
    ProviderIssueCode,
    ProviderRequest,
    ProviderResult,
    ProviderStatus,
    validate_result_for_request,
)
from app.providers.fingerprint import (
    compute_request_fingerprint,
    redact_sensitive_data,
)

logger = logging.getLogger(__name__)


async def execute_with_budget(
    provider: FinancialProvider,
    request: ProviderRequest,
) -> ProviderResult:
    """Execute provider request within timeout budget and safely map errors."""
    timeout_sec = max(request.timeout_ms / 1000.0, 0.001)
    fingerprint = compute_request_fingerprint(request)

    try:
        result = await asyncio.wait_for(
            provider.execute(request),
            timeout=timeout_sec,
        )
        validate_result_for_request(request, result)
        return result
    except TimeoutError:
        return ProviderResult(
            request_id=request.request_id,
            request_fingerprint=fingerprint,
            provider=provider.name,
            status=ProviderStatus.FAILED,
            retrieved_at=datetime.now(UTC),
            records=(),
            missing_fields=(),
            issues=(
                ProviderIssue(
                    code=ProviderIssueCode.TIMEOUT,
                    stage="budget",
                    safe_message=f"Request timed out after {request.timeout_ms}ms",
                    retriable=True,
                    diagnostics={"timeout_ms": request.timeout_ms},
                ),
            ),
            scope_description=None,
            latency_ms=request.timeout_ms,
        )
    except asyncio.CancelledError:
        return ProviderResult(
            request_id=request.request_id,
            request_fingerprint=fingerprint,
            provider=provider.name,
            status=ProviderStatus.FAILED,
            retrieved_at=datetime.now(UTC),
            records=(),
            missing_fields=(),
            issues=(
                ProviderIssue(
                    code=ProviderIssueCode.CANCELLED,
                    stage="runtime",
                    safe_message="Provider execution was cancelled",
                    retriable=False,
                ),
            ),
            scope_description=None,
        )
    except Exception as exc:
        safe_diagnostics = redact_sensitive_data(
            {"error_type": type(exc).__name__}
        )
        return ProviderResult(
            request_id=request.request_id,
            request_fingerprint=fingerprint,
            provider=provider.name,
            status=ProviderStatus.FAILED,
            retrieved_at=datetime.now(UTC),
            records=(),
            missing_fields=(),
            issues=(
                ProviderIssue(
                    code=ProviderIssueCode.INTERNAL_ERROR,
                    stage="runtime",
                    safe_message="Internal provider execution error",
                    retriable=False,
                    diagnostics=safe_diagnostics,
                ),
            ),
            scope_description=None,
        )
