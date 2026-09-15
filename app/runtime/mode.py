"""Prism Runtime Mode Controller.

Manages process-level data mode (MOCK vs. LIVE) with concurrency revision locks.
Enforces the core invariant:
"严禁在未接通官方接口时伪造 LIVE 或 FACT CHECKED，未配置凭据时严格处于 MOCK
或 Live 模式下的受控不可用态，坚决杜绝在 Live 失败时静默兜底回退至 Mock。"
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from enum import StrEnum
import logging
import os
from collections.abc import Iterable
from typing import Any

logger = logging.getLogger(__name__)


class DataMode(StrEnum):
    """Runtime data operation mode."""
    MOCK = "MOCK"
    LIVE = "LIVE"


class ModeRevisionConflictError(Exception):
    """Raised when expected revision does not match current controller revision."""
    pass


class LiveProviderUnavailableError(Exception):
    """Raised when switching to LIVE mode is refused due to missing credentials."""
    pass


WENCAI_SKILL_CAPABILITIES: dict[str, tuple[str, ...]] = {
    "announcement-search": ("announcement_search", "semantic_search"),
    "news-search": ("news_search", "semantic_search"),
    "report-search": ("report_search", "semantic_search"),
    "hithink-market-query": ("market_data",),
    "hithink-finance-query": ("company_data",),
    "hithink-industry-query": ("industry_data",),
    "hithink-macro-query": ("macro_data",),
    "hithink-fund-query": ("fund_data",),
    "hithink-cb-selector": ("convertible_bond_data", "convertible_bond"),
}

WENCAI_CAPABILITY_NAMES = tuple(
    sorted({capability for capabilities in WENCAI_SKILL_CAPABILITIES.values() for capability in capabilities})
)


def wencai_skills_for_capability(capability: str) -> tuple[str, ...]:
    """Return bundled Skill IDs that provide one isolated capability."""
    return tuple(
        skill_id
        for skill_id, capabilities in WENCAI_SKILL_CAPABILITIES.items()
        if capability in capabilities
    )


def wencai_capabilities_for_skills(skill_ids: Iterable[str]) -> dict[str, bool]:
    """Translate successful bundled Skill IDs into isolated runtime capabilities."""
    capabilities = {name: False for name in WENCAI_CAPABILITY_NAMES}
    for skill_id in skill_ids:
        for capability in WENCAI_SKILL_CAPABILITIES.get(str(skill_id), ()):
            capabilities[capability] = True
    return capabilities


def wencai_capability_for_operation(operation: str, channel: str | None = None) -> str | None:
    """Return the narrow capability required by one Wencai request."""
    if operation == "SEARCH_NEWS":
        return {
            "announcement": "announcement_search",
            "news": "news_search",
        }.get(str(channel or "announcement").lower())
    return {
        "SEARCH_REPORTS": "report_search",
        "MARKET_DATA": "market_data",
        "COMPANY_DATA": "company_data",
        "INDUSTRY_DATA": "industry_data",
        "MACRO_DATA": "macro_data",
        "FUND_DATA": "fund_data",
        "CONVERTIBLE_BOND_DATA": "convertible_bond_data",
    }.get(operation)


class RuntimeModeController:
    """Process-level controller for runtime data mode and revision management."""

    def __init__(self, initial_mode: DataMode | None = None) -> None:
        self._lock = asyncio.Lock()
        self._revision = 1
        self._updated_at = datetime.now(UTC)
        self._fuyao_capabilities = {
            "stock_quote": False,
            "fund_lookthrough": False,
        }
        self._fuyao_capability_checked_at: dict[str, datetime | None] = {
            "stock_quote": None,
            "fund_lookthrough": None,
        }
        self._fuyao_capability_errors: dict[str, str | None] = {
            "stock_quote": None,
            "fund_lookthrough": None,
        }
        self._fuyao_verification = (
            "NOT_CHECKED" if self._fuyao_configured else "UNCONFIGURED"
        )
        self._wencai_configured_override: bool | None = None
        self._wencai_contract_verified_override: bool | None = None
        self._wencai_available = self._wencai_configured_and_verified
        self._wencai_capabilities = {
            name: self._wencai_configured_and_verified
            for name in WENCAI_CAPABILITY_NAMES
        }
        self._wencai_capability_checked_at: dict[str, datetime | None] = {
            name: None for name in WENCAI_CAPABILITY_NAMES
        }
        self._wencai_capability_errors: dict[str, str | None] = {
            name: None for name in WENCAI_CAPABILITY_NAMES
        }
        # Portfolio refresh needs a narrower contract than the nine-Skill
        # aggregate probe: a real company/industry lookup combined with a real
        # Fuyao quote.  Track that contract independently so an unrelated Skill
        # failure does not disable a working portfolio path, while quote-only
        # availability can never advertise a complete refresh.
        self._portfolio_metadata_available = self._wencai_configured_and_verified
        self._wencai_checked_at: datetime | None = None
        self._wencai_last_error_code: str | None = None
        self._initial_probe_pending = initial_mode is None and self._fuyao_configured

        # Boot mode detection:
        # A non-empty key is configuration evidence, not proof of permissions.
        # The API layer performs a real capability probe before entering LIVE.
        if initial_mode is not None:
            self._mode = initial_mode
        else:
            self._mode = (
                DataMode.LIVE
                if self.is_live_ready and not self._fuyao_configured
                else DataMode.MOCK
            )

    @property
    def mode(self) -> DataMode:
        return self._mode

    @property
    def revision(self) -> int:
        return self._revision

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    @property
    def is_live_ready(self) -> bool:
        """Indicate whether at least one external provider capability is ready."""
        return self.is_fuyao_ready or any(self._wencai_capabilities.values())

    @property
    def is_fuyao_ready(self) -> bool:
        """Report whether at least one Fuyao capability passed a real probe."""
        return any(self._fuyao_capabilities.values())

    @property
    def _fuyao_configured(self) -> bool:
        return bool(os.getenv("HITHINK_FINANCE_API_KEY", "").strip())

    @property
    def _wencai_ready(self) -> bool:
        return self.is_wencai_ready

    @property
    def is_contract_verified(self) -> bool:
        """Require server-side confirmation of the Wencai response mapping."""
        if self._wencai_contract_verified_override is not None:
            return self._wencai_contract_verified_override
        return os.getenv("WENCAI_SKILLHUB_CONTRACT_VERIFIED", "").strip().lower() in {
            "1",
            "true",
            "yes",
        }

    @property
    def _wencai_configured_and_verified(self) -> bool:
        return self.is_wencai_configured and self.is_contract_verified

    @property
    def is_wencai_configured(self) -> bool:
        """Report whether either protected project settings or env provide a key."""
        return (
            self._wencai_configured_override
            if self._wencai_configured_override is not None
            else bool(
                os.getenv("WENCAI_SKILLHUB_API_KEY", "").strip()
                or os.getenv("IWENCAI_API_KEY", "").strip()
            )
        )

    @property
    def is_wencai_ready(self) -> bool:
        """Report Wencai readiness, including observed runtime failures."""
        return (
            self._wencai_available
            and self._wencai_configured_and_verified
            and all(self._wencai_capabilities.values())
        )

    def is_wencai_capability_ready(self, capability: str) -> bool:
        """Report readiness for one isolated Wencai operation."""
        return (
            self.is_wencai_configured
            and capability in self._wencai_capabilities
            and self._wencai_capabilities[capability]
        )

    @property
    def live_readiness_issues(self) -> tuple[str, ...]:
        """List unavailable provider groups without blocking working providers."""
        issues: list[str] = []
        if not any(self._fuyao_capabilities.values()):
            issues.append("FUYAO_MARKET_AND_FUND")
        if not any(self._wencai_capabilities.values()):
            issues.append("WENCAI_RESEARCH_AND_REFRESH")
        elif not self.is_wencai_ready:
            issues.append("WENCAI_PARTIAL_CONTRACT")
        return tuple(issues)

    @property
    def capabilities(self) -> dict[str, Any]:
        """Matrix of feature readiness under MOCK and LIVE modes."""
        live_wencai_ready = self._wencai_ready
        live_portfolio_market_ready = (
            self._fuyao_capabilities["stock_quote"]
            and self._portfolio_metadata_available
        )
        return {
            "MOCK": {
                "stock_quote": True,
                "fund_lookthrough": True,
                "convertible_bond": True,
                "semantic_search": True,
                "portfolio_health_check": True,
                "portfolio_rebalancing": True,
            },
            "LIVE": {
                "stock_quote": self._fuyao_capabilities["stock_quote"],
                "fund_lookthrough": self._fuyao_capabilities["fund_lookthrough"],
                "convertible_bond": self.is_wencai_capability_ready("convertible_bond"),
                "market_data": self.is_wencai_capability_ready("market_data"),
                "company_data": self.is_wencai_capability_ready("company_data"),
                "industry_data": self.is_wencai_capability_ready("industry_data"),
                "macro_data": self.is_wencai_capability_ready("macro_data"),
                "fund_data": self.is_wencai_capability_ready("fund_data"),
                "convertible_bond_data": self.is_wencai_capability_ready("convertible_bond_data"),
                "semantic_search": self.is_wencai_capability_ready("semantic_search"),
                "announcement_search": self.is_wencai_capability_ready("announcement_search"),
                "news_search": self.is_wencai_capability_ready("news_search"),
                "report_search": self.is_wencai_capability_ready("report_search"),
                "portfolio_refresh": live_portfolio_market_ready,
                "portfolio_health_check": True,
                "portfolio_optimization": live_portfolio_market_ready,
                "portfolio_rebalancing": live_portfolio_market_ready,
            },
        }

    @property
    def needs_initial_probe(self) -> bool:
        return self._initial_probe_pending

    async def apply_fuyao_probe(
        self, capabilities: dict[str, bool], *, auto_activate: bool = False,
        errors: dict[str, str | None] | None = None,
    ) -> None:
        """Record a real provider probe and optionally activate LIVE once."""
        async with self._lock:
            checked_at = datetime.now(UTC)
            self._fuyao_capabilities = {
                "stock_quote": bool(capabilities.get("stock_quote")),
                "fund_lookthrough": bool(capabilities.get("fund_lookthrough")),
            }
            self._fuyao_capability_checked_at = {
                name: checked_at for name in self._fuyao_capabilities
            }
            self._fuyao_capability_errors = {
                name: None if available else (errors or {}).get(name) or "PROBE_FAILED"
                for name, available in self._fuyao_capabilities.items()
            }
            available_count = sum(self._fuyao_capabilities.values())
            self._fuyao_verification = (
                "VERIFIED" if available_count == len(self._fuyao_capabilities)
                else "DEGRADED" if available_count
                else "FAILED"
            )
            self._initial_probe_pending = False
            if auto_activate and self.is_live_ready and self._mode != DataMode.LIVE:
                self._mode = DataMode.LIVE
                self._revision += 1
            elif not self.is_live_ready and self._mode == DataMode.LIVE:
                self._mode = DataMode.MOCK
                self._revision += 1
            self._updated_at = checked_at

    async def record_fuyao_capability_failure(
        self, capability: str, error_code: str
    ) -> None:
        """Invalidate a failed capability and keep LIVE state internally valid."""
        if capability not in self._fuyao_capabilities:
            raise ValueError(f"Unknown Fuyao capability: {capability}")
        async with self._lock:
            checked_at = datetime.now(UTC)
            self._fuyao_capabilities[capability] = False
            self._fuyao_capability_checked_at[capability] = checked_at
            self._fuyao_capability_errors[capability] = error_code
            available_count = sum(self._fuyao_capabilities.values())
            self._fuyao_verification = "DEGRADED" if available_count else "FAILED"
            if not self.is_live_ready and self._mode == DataMode.LIVE:
                self._mode = DataMode.MOCK
                self._revision += 1
            self._updated_at = checked_at

    async def record_wencai_failure(
        self, error_code: str, *, capability: str | None = None
    ) -> None:
        """Invalidate one Wencai capability, or the aggregate when unspecified."""
        async with self._lock:
            checked_at = datetime.now(UTC)
            if capability is None:
                self._wencai_available = False
                for name in self._wencai_capabilities:
                    self._wencai_capabilities[name] = False
                    self._wencai_capability_checked_at[name] = checked_at
                    self._wencai_capability_errors[name] = error_code
            elif capability in self._wencai_capabilities:
                self._wencai_capabilities[capability] = False
                self._wencai_capability_checked_at[capability] = checked_at
                self._wencai_capability_errors[capability] = error_code
                if capability == "industry_data":
                    self._portfolio_metadata_available = False
            else:
                raise ValueError(f"Unknown Wencai capability: {capability}")
            self._wencai_checked_at = checked_at
            self._wencai_last_error_code = error_code
            if not self.is_live_ready and self._mode == DataMode.LIVE:
                self._mode = DataMode.MOCK
                self._revision += 1
            self._updated_at = checked_at

    async def record_wencai_capability_result(
        self, capability: str, *, available: bool, error_code: str | None = None
    ) -> None:
        """Record one direct Wencai capability result without changing others."""
        if capability not in self._wencai_capabilities:
            raise ValueError(f"Unknown Wencai capability: {capability}")
        async with self._lock:
            checked_at = datetime.now(UTC)
            if available:
                # A successful direct call proves that a configured provider
                # can serve this route, even if the optional nine-Skill probe
                # has not yet completed.
                self._wencai_configured_override = True
            self._wencai_capabilities[capability] = available
            self._wencai_capability_checked_at[capability] = checked_at
            self._wencai_capability_errors[capability] = (
                None if available else error_code or "WENCAI_CAPABILITY_FAILED"
            )
            self._wencai_available = all(self._wencai_capabilities.values())
            self._portfolio_metadata_available = self._wencai_capabilities["industry_data"]
            self._wencai_checked_at = checked_at
            self._wencai_last_error_code = (
                None if available else error_code or "WENCAI_CAPABILITY_FAILED"
            )
            if not self.is_live_ready and self._mode == DataMode.LIVE:
                self._mode = DataMode.MOCK
                self._revision += 1
            self._updated_at = checked_at

    async def record_portfolio_metadata_result(
        self, *, available: bool, error_code: str | None = None
    ) -> None:
        """Record the operation-specific Wencai industry-enrichment result."""
        await self.record_wencai_capability_result(
            "industry_data", available=available, error_code=error_code
        )

    async def configure_wencai(
        self, *, configured: bool, contract_verified: bool = False,
        verified_capabilities: Iterable[str] = (),
    ) -> None:
        """Bind project-protected Wencai configuration to runtime readiness."""
        async with self._lock:
            self._wencai_configured_override = configured
            self._wencai_contract_verified_override = configured and contract_verified
            self._wencai_available = configured and contract_verified
            verified = {
                capability for capability in verified_capabilities
                if capability in self._wencai_capabilities
            }
            self._wencai_capabilities = {
                name: configured and (contract_verified or name in verified)
                for name in WENCAI_CAPABILITY_NAMES
            }
            self._portfolio_metadata_available = self._wencai_capabilities["industry_data"]
            self._wencai_capability_checked_at = {
                name: None for name in WENCAI_CAPABILITY_NAMES
            }
            self._wencai_capability_errors = {
                name: None for name in WENCAI_CAPABILITY_NAMES
            }
            self._wencai_checked_at = None
            self._wencai_last_error_code = None
            self._updated_at = datetime.now(UTC)

    def restore_wencai_configuration(
        self, *, configured: bool, contract_verified: bool,
        verified_capabilities: Iterable[str] = (), auto_activate: bool = True,
    ) -> None:
        """Restore protected configuration before the application serves requests."""
        self._wencai_configured_override = configured
        self._wencai_contract_verified_override = configured and contract_verified
        self._wencai_available = configured and contract_verified
        verified = {
            capability for capability in verified_capabilities
            if capability in self._wencai_capabilities
        }
        self._wencai_capabilities = {
            name: configured and (contract_verified or name in verified)
            for name in WENCAI_CAPABILITY_NAMES
        }
        self._portfolio_metadata_available = self._wencai_capabilities["industry_data"]
        self._wencai_capability_checked_at = {
            name: None for name in WENCAI_CAPABILITY_NAMES
        }
        self._wencai_capability_errors = {
            name: None for name in WENCAI_CAPABILITY_NAMES
        }
        self._wencai_checked_at = None
        self._wencai_last_error_code = None
        if auto_activate and self.is_live_ready and self._mode != DataMode.LIVE:
            self._mode = DataMode.LIVE
            self._updated_at = datetime.now(UTC)

    async def apply_wencai_probe(
        self, *, available: bool, error_code: str | None = None,
        auto_activate: bool = False, capabilities: dict[str, bool] | None = None,
        capability_errors: dict[str, str | None] | None = None,
    ) -> None:
        """Record a real nine-Skill probe and update LIVE capability state."""
        async with self._lock:
            checked_at = datetime.now(UTC)
            self._wencai_configured_override = True
            self._wencai_contract_verified_override = available
            self._wencai_available = available
            self._wencai_capabilities = {
                name: bool((capabilities or {}).get(name, available))
                for name in WENCAI_CAPABILITY_NAMES
            }
            self._wencai_capability_checked_at = {
                name: checked_at for name in WENCAI_CAPABILITY_NAMES
            }
            self._wencai_capability_errors = {
                name: None if is_available else (capability_errors or {}).get(name) or error_code
                for name, is_available in self._wencai_capabilities.items()
            }
            self._portfolio_metadata_available = self._wencai_capabilities["industry_data"]
            self._wencai_checked_at = checked_at
            self._wencai_last_error_code = None if available else (error_code or "PROBE_FAILED")
            if auto_activate and self.is_live_ready and self._mode != DataMode.LIVE:
                self._mode = DataMode.LIVE
                self._revision += 1
            elif not self.is_live_ready and self._mode == DataMode.LIVE:
                self._mode = DataMode.MOCK
                self._revision += 1
            self._updated_at = checked_at

    def get_status(self) -> dict[str, Any]:
        """Return serialized state representation."""
        return {
            "data_mode": self._mode.value,
            "revision": self._revision,
            "live_ready": self.is_live_ready,
            "live_configured": self._fuyao_configured,
            "live_verification": self._fuyao_verification,
            "wencai_ready": self.is_wencai_ready,
            "wencai_configured": self.is_wencai_configured,
            "contract_verified": self.is_contract_verified,
            "wencai_capability_status": {
                "available": self.is_wencai_ready,
                "checked_at": (
                    self._wencai_checked_at.isoformat()
                    if self._wencai_checked_at is not None
                    else None
                ),
                "last_error_code": self._wencai_last_error_code,
            },
            "wencai_capabilities": {
                name: self._wencai_capabilities[name]
                for name in WENCAI_CAPABILITY_NAMES
            },
            "wencai_live_capability_status": {
                name: {
                    "available": self._wencai_capabilities[name],
                    "checked_at": (
                        self._wencai_capability_checked_at[name].isoformat()
                        if self._wencai_capability_checked_at[name] is not None
                        else None
                    ),
                    "last_error_code": self._wencai_capability_errors[name],
                }
                for name in WENCAI_CAPABILITY_NAMES
            },
            "portfolio_metadata_ready": self._portfolio_metadata_available,
            "live_readiness_issues": self.live_readiness_issues,
            "capabilities": self.capabilities,
            "live_capability_status": {
                name: {
                    "available": self._fuyao_capabilities[name],
                    "checked_at": (
                        self._fuyao_capability_checked_at[name].isoformat()
                        if self._fuyao_capability_checked_at[name] is not None
                        else None
                    ),
                    "last_error_code": self._fuyao_capability_errors[name],
                }
                for name in self._fuyao_capabilities
            },
            "updated_at": self._updated_at.isoformat(),
        }

    async def switch_mode(
        self, target_mode: DataMode | str, expected_revision: int
    ) -> dict[str, Any]:
        """Switch data mode with concurrency revision check.

        Raises:
            ModeRevisionConflictError: If expected_revision != self._revision.
            LiveProviderUnavailableError: If target_mode is LIVE but credentials are unconfigured.
        """
        async with self._lock:
            if expected_revision != self._revision:
                raise ModeRevisionConflictError(
                    f"Revision conflict: expected revision {expected_revision}, "
                    f"but current revision is {self._revision}."
                )

            if isinstance(target_mode, str):
                try:
                    target_enum = DataMode(target_mode.upper())
                except ValueError:
                    raise ValueError(f"Invalid data mode: {target_mode}. Must be MOCK or LIVE.")
            else:
                target_enum = target_mode

            if target_enum == DataMode.LIVE and not self.is_live_ready:
                raise LiveProviderUnavailableError(
                    "No verified external data capability is available. Configure a valid "
                    "HITHINK_FINANCE_API_KEY or a verified Wencai SkillHub provider."
                )

            if target_enum != self._mode:
                self._mode = target_enum
                self._revision += 1
                self._updated_at = datetime.now(UTC)
                logger.info(
                    "Runtime mode transitioned to %s (revision: %d)",
                    self._mode.value,
                    self._revision,
                )

            return self.get_status()


_GLOBAL_CONTROLLER: RuntimeModeController | None = None


def get_runtime_mode_controller() -> RuntimeModeController:
    """Obtain or initialize the process-level RuntimeModeController singleton."""
    global _GLOBAL_CONTROLLER
    if _GLOBAL_CONTROLLER is None:
        _GLOBAL_CONTROLLER = RuntimeModeController()
    return _GLOBAL_CONTROLLER


def reset_runtime_mode_controller(mode: DataMode | None = None) -> RuntimeModeController:
    """Reset controller singleton for test isolation."""
    global _GLOBAL_CONTROLLER
    _GLOBAL_CONTROLLER = RuntimeModeController(initial_mode=mode)
    return _GLOBAL_CONTROLLER
