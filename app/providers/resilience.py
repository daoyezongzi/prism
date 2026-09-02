"""Bounded, fixture-friendly provider cache and fallback policy.

This module deliberately contains no network client and no persistence.  It is
an execution boundary around the existing Provider Protocol: cache keys are
public semantic request fingerprints, cached payloads are immutable validated
``ProviderResult`` objects, and every non-direct response carries an explicit
serving mode.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
import threading
from typing import Any

from app.providers.contracts import (
    FinancialProvider,
    ProviderRequest,
    ProviderResult,
    ProviderStatus,
    ProviderServingMode,
    validate_result_for_request,
)
from app.providers.fingerprint import compute_request_fingerprint


_PRIVATE_CACHE_MARKERS = (
    "owner",
    "profile",
    "portfolio",
    "questionnaire",
    "context_memory",
    "memory_id",
    "account",
    "holding",
    "position",
    "user_id",
)

_SENSITIVE_CACHE_MARKERS = (
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


def _require_aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


def _private_marker(value: object) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.casefold().replace("-", "_")
    return any(marker in normalized for marker in _PRIVATE_CACHE_MARKERS)


def _sensitive_marker(value: object) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.casefold().replace("-", "_")
    return any(marker in normalized for marker in _SENSITIVE_CACHE_MARKERS)


def _contains_private_context(value: object, *, inspect_values: bool = True) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if _private_marker(str(key)):
                return True
            if _contains_private_context(item, inspect_values=inspect_values):
                return True
        return False
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(
            _contains_private_context(item, inspect_values=inspect_values)
            for item in value
        )
    return inspect_values and _private_marker(value)


def _contains_sensitive_data(value: object) -> bool:
    """Reject provider payloads that would make a cache a secret store."""

    if isinstance(value, Mapping):
        return any(
            _sensitive_marker(str(key))
            or _contains_sensitive_data(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(_contains_sensitive_data(item) for item in value)
    return _sensitive_marker(value)


def is_public_cache_request(request: ProviderRequest) -> bool:
    """Return whether a request is safe for an owner-agnostic public cache.

    ``ProviderRequest`` already rejects credentials.  This additional boundary
    rejects profile/account-shaped semantic fields because the cache key does
    not contain an owner.  A private request is still executable; it simply
    bypasses the shared cache.
    """

    if _private_marker(request.subject):
        return False
    if any(_private_marker(field) for field in request.required_fields):
        return False
    return not _contains_private_context(request.parameters)


@dataclass(frozen=True, slots=True)
class ProviderCacheHit:
    """A validated cache payload and its age at lookup time."""

    result: ProviderResult
    age_ms: int
    stale: bool


@dataclass(frozen=True, slots=True)
class ProviderCacheStats:
    """Read-only cache counters safe to expose in diagnostics."""

    entries: int
    hits: int
    stale_hits: int
    misses: int
    writes: int
    evictions: int
    bypasses: int


@dataclass(frozen=True, slots=True)
class _CacheEntry:
    result: ProviderResult
    stored_at: datetime


class InMemoryProviderCache:
    """Thread-safe bounded LRU cache for public provider results.

    Entries are retained for ``ttl_ms`` as fresh data and for an optional
    ``stale_grace_ms`` afterwards.  The cache never stores EMPTY or FAILED
    results and never serializes an owner/private request.
    """

    def __init__(
        self,
        *,
        ttl_ms: int = 30_000,
        stale_grace_ms: int = 0,
        max_entries: int = 256,
        clock: Any | None = None,
    ) -> None:
        if ttl_ms < 1:
            raise ValueError("ttl_ms must be at least 1")
        if stale_grace_ms < 0:
            raise ValueError("stale_grace_ms must be non-negative")
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1")
        self._ttl_ms = ttl_ms
        self._stale_grace_ms = stale_grace_ms
        self._max_entries = max_entries
        self._clock = clock or (lambda: datetime.now(UTC))
        self._entries: OrderedDict[tuple[str, str], _CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._hits = 0
        self._stale_hits = 0
        self._misses = 0
        self._writes = 0
        self._evictions = 0
        self._bypasses = 0

    @property
    def ttl_ms(self) -> int:
        return self._ttl_ms

    @property
    def stale_grace_ms(self) -> int:
        return self._stale_grace_ms

    @property
    def max_entries(self) -> int:
        return self._max_entries

    def _now(self, value: datetime | None) -> datetime:
        return _require_aware(value or self._clock(), "cache clock")

    @staticmethod
    def _key(provider_name: str, fingerprint: str) -> tuple[str, str]:
        if not isinstance(provider_name, str) or not provider_name.strip():
            raise ValueError("provider_name must be non-empty")
        if not isinstance(fingerprint, str) or not fingerprint.strip():
            raise ValueError("fingerprint must be non-empty")
        return provider_name, fingerprint

    def get(
        self,
        provider_name: str,
        request: ProviderRequest,
        *,
        now: datetime | None = None,
        allow_stale: bool = True,
    ) -> ProviderCacheHit | None:
        """Look up a request by provider identity and semantic fingerprint."""

        if _sensitive_marker(provider_name) or not is_public_cache_request(request):
            with self._lock:
                self._bypasses += 1
            return None
        key = self._key(provider_name, compute_request_fingerprint(request))
        current = self._now(now)
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._misses += 1
                return None
            age_ms = max(0, int((current - entry.stored_at).total_seconds() * 1000))
            if age_ms <= self._ttl_ms:
                self._entries.move_to_end(key)
                self._hits += 1
                return ProviderCacheHit(entry.result, age_ms, False)
            if age_ms <= self._ttl_ms + self._stale_grace_ms:
                if allow_stale:
                    self._entries.move_to_end(key)
                    self._hits += 1
                    self._stale_hits += 1
                    return ProviderCacheHit(entry.result, age_ms, True)
                # Keep a still-usable stale entry for the post-failure lookup.
                self._misses += 1
                return None
            del self._entries[key]
            self._misses += 1
            return None

    def put(
        self,
        provider_name: str,
        request: ProviderRequest,
        result: ProviderResult,
        *,
        stored_at: datetime | None = None,
    ) -> bool:
        """Store one validated direct SUCCESS/PARTIAL result.

        Returns ``False`` for private requests or non-cacheable four-state
        results.  Malformed or identity-drifting payloads raise instead of
        polluting the cache.
        """

        if _sensitive_marker(provider_name) or not is_public_cache_request(request):
            with self._lock:
                self._bypasses += 1
            return False
        if result.provider != provider_name:
            raise ValueError("cache result provider does not match cache key")
        if result.serving_mode != ProviderServingMode.DIRECT:
            raise ValueError("only DIRECT provider results may enter the cache")
        if result.status not in (ProviderStatus.SUCCESS, ProviderStatus.PARTIAL):
            return False
        if _contains_sensitive_data(result.model_dump(mode="python")):
            with self._lock:
                self._bypasses += 1
            return False
        validate_result_for_request(request, result)
        entry = _CacheEntry(
            result=ProviderResult.model_validate(result.model_dump(mode="python")),
            stored_at=self._now(stored_at),
        )
        key = self._key(provider_name, result.request_fingerprint)
        expected_key = self._key(
            provider_name,
            compute_request_fingerprint(request),
        )
        if key != expected_key:
            raise ValueError("cache result fingerprint does not match request")
        with self._lock:
            self._entries[key] = entry
            self._entries.move_to_end(key)
            self._writes += 1
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)
                self._evictions += 1
        return True

    def invalidate(self, provider_name: str, request: ProviderRequest) -> bool:
        """Remove one public entry, if present."""

        if not is_public_cache_request(request):
            return False
        key = self._key(provider_name, compute_request_fingerprint(request))
        with self._lock:
            return self._entries.pop(key, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def stats(self) -> ProviderCacheStats:
        with self._lock:
            return ProviderCacheStats(
                entries=len(self._entries),
                hits=self._hits,
                stale_hits=self._stale_hits,
                misses=self._misses,
                writes=self._writes,
                evictions=self._evictions,
                bypasses=self._bypasses,
            )

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)


@dataclass(frozen=True, slots=True)
class ProviderResilienceStatsSnapshot:
    """Read-only execution counters with no request payloads."""

    cache_fresh: int
    primary_calls: int
    fallback_calls: int
    fallback_results: int
    stale_fallbacks: int
    failed_results: int
    private_bypasses: int


class ProviderResilienceStats:
    """Thread-safe counters for one execution policy."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._values = {
            "cache_fresh": 0,
            "primary_calls": 0,
            "fallback_calls": 0,
            "fallback_results": 0,
            "stale_fallbacks": 0,
            "failed_results": 0,
            "private_bypasses": 0,
        }

    def increment(self, name: str, amount: int = 1) -> None:
        if name not in self._values:
            raise ValueError(f"unknown resilience counter: {name}")
        with self._lock:
            self._values[name] += amount

    def snapshot(self) -> ProviderResilienceStatsSnapshot:
        with self._lock:
            return ProviderResilienceStatsSnapshot(**self._values)


@dataclass(frozen=True, slots=True)
class ProviderExecutionPolicy:
    """Optional cache/fallback policy injected into ``execute_with_budget``."""

    cache: InMemoryProviderCache | None = None
    fallback: FinancialProvider | None = None
    allow_stale: bool = True
    stats: ProviderResilienceStats = field(default_factory=ProviderResilienceStats)

    def __post_init__(self) -> None:
        if self.fallback is not None:
            fallback_name = self.fallback.name
            if not isinstance(fallback_name, str) or not fallback_name.strip():
                raise ValueError("fallback provider name must be non-empty")
        if self.cache is None and self.allow_stale is not True:
            raise ValueError("allow_stale requires a cache")

    def counters(self) -> ProviderResilienceStats:
        """Return the mutable counter object used by this policy."""
        return self.stats


__all__ = [
    "InMemoryProviderCache",
    "ProviderCacheHit",
    "ProviderCacheStats",
    "ProviderExecutionPolicy",
    "ProviderResilienceStats",
    "ProviderResilienceStatsSnapshot",
    "is_public_cache_request",
]
