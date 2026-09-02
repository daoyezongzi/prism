"""Pure, deterministic scenario overlays for the Phase 33 simulation service."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from hashlib import sha256

from app.portfolio import PortfolioImportBundle
from app.simulation.contracts import (
    ScenarioAssumption,
    ScenarioDefinition,
    ScenarioOverlayType,
    ScenarioSimulationId,
)


_CENT = Decimal("0.01")
_TEN_PERCENT = Decimal("0.10")
_TECH_CAP_DELTA = Decimal("10.00")


class ScenarioOverlayError(ValueError):
    """A fixed scenario cannot be constructed safely for the submitted bundle."""


@dataclass(frozen=True)
class BuiltScenarioOverlay:
    """Internal immutable overlay output; it is never accepted from HTTP input."""

    scenario_id: ScenarioSimulationId
    portfolio: PortfolioImportBundle
    technology_cap_override: Decimal | None
    assumption: ScenarioAssumption
    overlay_digest: str


def _digest(*parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return sha256(payload).hexdigest()[:32]


def _derived_ids(
    portfolio: PortfolioImportBundle,
    scenario_id: ScenarioSimulationId,
    overlay_digest: str,
) -> tuple[str, str]:
    digest = _digest(
        portfolio.bundle_id,
        portfolio.position_snapshot.snapshot_id,
        scenario_id.value,
        overlay_digest,
    )
    return f"scenario-bundle:{digest}", f"scenario-snapshot:{digest}"


def _with_derived_ids(
    portfolio: PortfolioImportBundle,
    scenario_id: ScenarioSimulationId,
    overlay_digest: str,
    *,
    positions=None,
    fund_holdings=None,
) -> PortfolioImportBundle:
    bundle_id, snapshot_id = _derived_ids(portfolio, scenario_id, overlay_digest)
    original_snapshot = portfolio.position_snapshot
    snapshot = original_snapshot.model_copy(
        update={
            "snapshot_id": snapshot_id,
            "positions": tuple(positions if positions is not None else original_snapshot.positions),
        }
    )
    return PortfolioImportBundle.model_validate(
        portfolio.model_copy(
            update={
                "bundle_id": bundle_id,
                "position_snapshot": snapshot,
                "fund_holdings": tuple(
                    fund_holdings if fund_holdings is not None else portfolio.fund_holdings
                ),
            }
        ).model_dump(mode="python")
    )


def scenario_definitions() -> tuple[ScenarioDefinition, ...]:
    definitions = (
        ScenarioDefinition(
            scenario_id=ScenarioSimulationId.BASELINE_READY,
            label="基线完整快照（BASELINE_READY）",
            description="不改变已确认画像、持仓或规则；用于建立可比较基线。",
            overlay_type=ScenarioOverlayType.IDENTITY,
            parameter_summary="无假设覆盖；复算同一份已观测快照。",
        ),
        ScenarioDefinition(
            scenario_id=ScenarioSimulationId.LOOKTHROUGH_PARTIAL,
            label="基金穿透部分缺失（LOOKTHROUGH_PARTIAL）",
            description="将已有基金/ETF 穿透覆盖降为 80%，保留缺失语义，不补零。",
            overlay_type=ScenarioOverlayType.DATA_COVERAGE,
            parameter_summary="coverage_pct 固定为 80.00；仅适用于存在基金穿透快照的输入。",
        ),
        ScenarioDefinition(
            scenario_id=ScenarioSimulationId.TIGHTER_TECH_CAP,
            label="收紧科技上限（TIGHTER_TECH_CAP）",
            description="将确认画像对应的科技上限收紧 10.00 个百分点；不修改 RiskBudget。",
            overlay_type=ScenarioOverlayType.LIMIT_OVERRIDE,
            parameter_summary="scenario technology cap = max(base cap - 10.00, 0.00)。",
        ),
        ScenarioDefinition(
            scenario_id=ScenarioSimulationId.TOP_ASSET_TRIM_10PP,
            label="减少头部资产 10 个百分点（TOP_ASSET_TRIM_10PP）",
            description="从确定性头部资产移出组合总市值的 10.00 个百分点，再分配给其余资产。",
            overlay_type=ScenarioOverlayType.PORTFOLIO_ALLOCATION_SHIFT,
            parameter_summary="固定 10.00 percentage points；保持总市值、币种和资产集合不变。",
        ),
    )
    return tuple(sorted(definitions, key=lambda item: item.scenario_id.value))


def tighter_technology_cap(base_cap: Decimal) -> Decimal:
    """Return the scenario-only cap without mutating the confirmed RiskBudget."""

    return max(Decimal("0.00"), (base_cap - _TECH_CAP_DELTA).quantize(_CENT))


def _allocate_trim_cents(
    trim_cents: int,
    values: dict[str, Decimal],
) -> dict[str, int]:
    if trim_cents < 0 or not values:
        raise ScenarioOverlayError("top asset trim has no receiving assets")
    total = sum(values.values(), Decimal("0"))
    if total <= Decimal("0"):
        raise ScenarioOverlayError("top asset trim has no positive receiving value")
    raw = {
        key: Decimal(trim_cents) * value / total
        for key, value in values.items()
    }
    floors = {
        key: int(value.to_integral_value(rounding=ROUND_DOWN))
        for key, value in raw.items()
    }
    remaining = trim_cents - sum(floors.values())
    order = sorted(
        raw,
        key=lambda key: (-(raw[key] - Decimal(floors[key])), key),
    )
    for key in order[:remaining]:
        floors[key] += 1
    return floors


def _top_asset_trim(
    portfolio: PortfolioImportBundle,
) -> tuple[PortfolioImportBundle, ScenarioAssumption, str]:
    positions = tuple(portfolio.position_snapshot.positions)
    if len(positions) < 2:
        raise ScenarioOverlayError("top asset trim requires at least two positions")
    currencies = {position.currency for position in positions}
    if currencies != {portfolio.position_snapshot.base_currency}:
        raise ScenarioOverlayError("top asset trim requires a single base-currency snapshot")
    total = sum((position.market_value for position in positions), Decimal("0"))
    if total <= Decimal("0"):
        raise ScenarioOverlayError("top asset trim requires positive portfolio value")
    top = sorted(
        positions,
        key=lambda position: (-position.market_value, position.asset_id, position.position_id),
    )[0]
    trim_value = (total * _TEN_PERCENT).quantize(_CENT, rounding=ROUND_HALF_UP)
    if trim_value <= Decimal("0") or top.market_value < trim_value:
        raise ScenarioOverlayError("top asset cannot safely absorb a 10 percentage point trim")
    receivers = {
        position.position_id: position.market_value
        for position in positions
        if position.position_id != top.position_id and position.market_value > Decimal("0")
    }
    allocation = _allocate_trim_cents(int(trim_value * 100), receivers)
    updated = []
    for position in positions:
        if position.position_id == top.position_id:
            updated.append(
                position.model_copy(
                    update={"market_value": (position.market_value - trim_value).quantize(_CENT)}
                )
            )
            continue
        increase = Decimal(allocation.get(position.position_id, 0)) / Decimal("100")
        updated.append(position.model_copy(update={"market_value": (position.market_value + increase).quantize(_CENT)}))
    digest = _digest(
        "TOP_ASSET_TRIM_10PP",
        top.asset_id,
        top.position_id,
        str(trim_value),
        *(f"{item.position_id}:{item.market_value}" for item in updated),
    )
    derived = _with_derived_ids(
        portfolio,
        ScenarioSimulationId.TOP_ASSET_TRIM_10PP,
        digest,
        positions=updated,
    )
    assumption = ScenarioAssumption(
        overlay_type=ScenarioOverlayType.PORTFOLIO_ALLOCATION_SHIFT,
        dimension="PORTFOLIO_ALLOCATION",
        target_id=top.asset_id,
        summary=(
            "假设从确定性头部资产移出组合总市值的 10.00 个百分点，并按稳定规则分配给其余资产；"
            "不是价格变化或交易指令。"
        ),
    )
    return derived, assumption, digest


def _partial_lookthrough(
    portfolio: PortfolioImportBundle,
) -> tuple[PortfolioImportBundle, ScenarioAssumption, str]:
    if not portfolio.fund_holdings:
        raise ScenarioOverlayError("look-through partial scenario requires fund holdings")
    digest = _digest(
        "LOOKTHROUGH_PARTIAL",
        *(f"{item.parent_asset_id}:{item.snapshot_id}:80.00" for item in portfolio.fund_holdings),
    )
    funds = tuple(
        fund.model_copy(update={"coverage_pct": Decimal("80.00")})
        for fund in portfolio.fund_holdings
    )
    derived = _with_derived_ids(
        portfolio,
        ScenarioSimulationId.LOOKTHROUGH_PARTIAL,
        digest,
        fund_holdings=funds,
    )
    assumption = ScenarioAssumption(
        overlay_type=ScenarioOverlayType.DATA_COVERAGE,
        dimension="FUND_LOOKTHROUGH_COVERAGE",
        summary="假设基金/ETF 穿透覆盖率为 80.00%；保留部分数据状态，不补零。",
    )
    return derived, assumption, digest


def build_overlay(
    portfolio: PortfolioImportBundle,
    scenario_id: ScenarioSimulationId,
    *,
    base_technology_cap: Decimal,
) -> BuiltScenarioOverlay:
    """Build one server-owned overlay without mutating the submitted bundle."""

    if scenario_id == ScenarioSimulationId.BASELINE_READY:
        digest = _digest("BASELINE_READY", portfolio.bundle_id, portfolio.position_snapshot.snapshot_id)
        assumption = ScenarioAssumption(
            overlay_type=ScenarioOverlayType.IDENTITY,
            dimension="OBSERVED_SNAPSHOT",
            summary="不改变已确认画像、持仓或规则；仅建立可比较基线。",
        )
        return BuiltScenarioOverlay(scenario_id, portfolio, None, assumption, digest)
    if scenario_id == ScenarioSimulationId.TIGHTER_TECH_CAP:
        cap = tighter_technology_cap(base_technology_cap)
        digest = _digest("TIGHTER_TECH_CAP", str(base_technology_cap), str(cap))
        assumption = ScenarioAssumption(
            overlay_type=ScenarioOverlayType.LIMIT_OVERRIDE,
            dimension="TECHNOLOGY_CAP",
            baseline_value=base_technology_cap,
            scenario_value=cap,
            delta=cap - base_technology_cap,
            unit="PCT",
            summary="假设科技上限收紧 10.00 个百分点；不修改确认画像或 RiskBudget。",
        )
        return BuiltScenarioOverlay(scenario_id, portfolio, cap, assumption, digest)
    if scenario_id == ScenarioSimulationId.TOP_ASSET_TRIM_10PP:
        derived, assumption, digest = _top_asset_trim(portfolio)
        return BuiltScenarioOverlay(scenario_id, derived, None, assumption, digest)
    if scenario_id == ScenarioSimulationId.LOOKTHROUGH_PARTIAL:
        derived, assumption, digest = _partial_lookthrough(portfolio)
        return BuiltScenarioOverlay(scenario_id, derived, None, assumption, digest)
    raise ScenarioOverlayError("unknown scenario simulation ID")


__all__ = [
    "BuiltScenarioOverlay",
    "ScenarioOverlayError",
    "build_overlay",
    "scenario_definitions",
    "tighter_technology_cap",
]
