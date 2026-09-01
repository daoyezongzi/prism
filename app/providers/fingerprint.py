"""Deterministic canonical request fingerprinting and secret redaction."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
from typing import Any

from app.providers.contracts import (
    ProviderRequest,
    _is_forbidden_key,
)

SCHEMA_VERSION = "provider-request.v1"

SENSITIVE_KEY_SUBSTRINGS = (
    "token",
    "auth",
    "secret",
    "password",
    "cookie",
    "api_key",
    "apikey",
    "credential",
)


def redact_sensitive_data(value: Any) -> Any:
    """Recursively redact dictionary keys and values matching sensitive keywords."""
    if isinstance(value, (dict, Mapping)):
        redacted: dict[str, Any] = {}
        for k, v in value.items():
            key_str = str(k).lower().replace("-", "_")
            if _is_forbidden_key(str(k)) or any(
                s in key_str for s in SENSITIVE_KEY_SUBSTRINGS
            ):
                redacted[str(k)] = "[REDACTED]"
            else:
                redacted[str(k)] = redact_sensitive_data(v)
        return redacted
    elif isinstance(value, (list, tuple, set, frozenset)):
        return [redact_sensitive_data(item) for item in value]
    return value


def canonical_request_dict(request: ProviderRequest) -> dict[str, Any]:
    """Convert request to a normalized, order-invariant dictionary."""
    return {
        "schema_version": SCHEMA_VERSION,
        "operation": str(request.operation.value),
        "subject": str(request.subject),
        "as_of": request.as_of.isoformat() if request.as_of is not None else None,
        "required_fields": sorted(request.required_fields),
        "parameters": _canonicalize_value(request.parameters),
    }


def _canonicalize_value(val: Any) -> Any:
    if isinstance(val, (dict, Mapping)):
        return {str(k): _canonicalize_value(v) for k, v in sorted(val.items())}
    elif isinstance(val, (list, tuple, set, frozenset)):
        return [_canonicalize_value(item) for item in val]
    return val


def compute_request_fingerprint(request: ProviderRequest) -> str:
    """Compute a deterministic SHA-256 fingerprint for semantic request identity."""
    normalized = canonical_request_dict(request)
    canonical_json = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest().lower()
