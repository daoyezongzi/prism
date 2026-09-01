"""Canonical local fingerprints for immutable gate inputs."""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any


def _canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _canonicalize(item)
            for key, item in sorted(value.items(), key=lambda pair: pair[0])
        }
    if isinstance(value, list):
        items = [_canonicalize(item) for item in value]
        return sorted(
            items,
            key=lambda item: json.dumps(
                item,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
    return value


def canonical_payload_signature(payload: object) -> str:
    """Hash structured JSON-like content with collection-order invariance."""

    canonical = json.dumps(
        _canonicalize(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def canonical_model_signature(model: object) -> str:
    """Hash model content while treating contract collections as unordered sets."""

    try:
        payload = model.model_dump(mode="json")  # type: ignore[attr-defined]
    except Exception:
        try:
            payload = {
                "invalid_type": f"{type(model).__module__}.{type(model).__qualname__}",
                "invalid_value": repr(model),
            }
        except Exception:
            payload = {"invalid_type": "unrepresentable"}
    return canonical_payload_signature(payload)


__all__ = ["canonical_model_signature", "canonical_payload_signature"]
