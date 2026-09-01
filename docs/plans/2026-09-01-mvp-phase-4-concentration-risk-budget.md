# MVP Phase 4 Working Plan：Concentration and Profile-conditioned Risk Budget

- Status：`ACCEPTED`
- Owner：Codex
- Reviewer：Codex + user
- Target worktree：`D:\Github_Storage\prism-phase-4`
- Target branch：`codex/mvp-phase-4-concentration-risk`
- Source of truth：[Prism.md](../../Prism.md)
- Parent plan：[Prism Foundation](2026-09-01-foundation.md)
- Prerequisite：Phase 3 Look-through Exposure accepted at `f6a1af4`

## Goal

基于 Phase 3 的 `ExposureResult` 生成可复核的资产/行业集中度指标，并把
已确认的 `RiskProfile` 映射为固定、可解释的风险预算约束。输出只回答
“当前数据在这些约束下哪里超限、哪里需要人工复核”，不生成买卖建议或
最小调整方案。

## Product rationale

同样的市场暴露不能对所有人给出同一个结论：保守用户与进取用户应看到
不同的单资产、行业、科技暴露和未分类数据容忍边界。Prism 的选择理由
是这份差异可被拆解为 `RiskProfile` 版本、固定预算规则和实际贡献行，而
不是一个不可解释的 AI 风险分数；数据不完整时结果会进入复核态，不会
被包装成“安全”。

## Context / constraints

- Phase 1 Provider/Evidence、Phase 2 Profile/Portfolio、Phase 3 Exposure 都是
  上游边界；不修改它们的模型、测试或语义。
- `Prism.md`、`docs/architecture.md`、`docs/reuse-matrix.md` 只读；上游
  `tradeeye-copilot` 与 `TradeEye` 只读。
- 只使用标准库、现有 Pydantic 和 pytest；全部金额、权重、HHI 使用
  `Decimal`，不使用浮点或随机状态。
- 所有新对象保持 `extra="forbid"`、不可变、时区明确并带 owner/profile/
  exposure 身份闭合。
- 风险预算是产品规则版本，不是监管适当性结论；规则本身必须留在结构化
  对象中并可被测试复现。

## In scope

### Concentration

- `ConcentrationGroup`：按资产和按 sector 聚合 Phase 3 contributions，
  保留 contribution IDs、是否未分类以及 Decimal 市值/权重。
- `ConcentrationReport`：资产/行业分组、Top-1 权重、HHI（0–10000）、
  未分类权重和科技权重；校验所有分组加总闭合到 exposure report。
- `calculate_concentration(exposure_result)`：传播 upstream 的 PARTIAL/FAILED
  语义，不把 `UNLOOKED_THROUGH` residual 或未知 sector 删除。

### Profile-conditioned risk budget

- `RiskBudget`：按 `RiskLevel` 选择固定版本化上限，并保留用户的最大回撤
  容忍度；规则只产生约束，不计算实际回撤。
- `RiskBudgetAssessment`：比较单资产、已知 sector、科技权重和
  `UNCLASSIFIED` 权重，输出超限 breach 与数据复核 issue。
- `assess_risk_budget(profile, concentration_result)`：强制 owner/profile/
  exposure 闭合；保守、均衡、进取画像对同一 exposure 产生可测试的不同
  预算与 assessment 状态。

### Verification

- 合成 fixture 复用 Phase 3 exposure，覆盖完整直接持仓、科技穿透、残余和
  partial 数据。
- 单元反例验证 Decimal 聚合、HHI、top tie-break、profile 预算差异、owner
  串线、状态不变量、重复 ID、不可变性和无推荐字段。
- 原有 Phase 1/2/3 的 79 项测试继续通过。

## Explicitly out of scope

- 历史收益、波动率、相关性、Beta、VaR、流动性、压力测试和实际最大回撤。
- 外汇换算、实时行情、网络/API/SkillHub/Tushare、LLM、自然语言解析。
- 组合优化、最小调整、守稳/均衡/进取配置区间、交易动作或推荐文案。
- Evidence Contract、Decision Receipt、研究 DAG、Provider、数据库、迁移、
  FastAPI、Web UI、并发/SLA。
- 修改 `Prism.md`、Phase 1/2/3 文件、上游仓库或现有 Evidence/Provider 测试。

## Design decisions

### Concentration metrics

- Asset groups use each contribution's `asset_id`; sector groups use a trimmed,
  case-folded sector, with missing sector represented by the explicit key
  `UNCLASSIFIED`.
- Group weights are `group market value / total exposure market value * 100`,
  rounded to two Decimal places. HHI is
  `sum((group market value / total value)^2) * 10000`, computed from unrounded
  values and rounded to two Decimal places.
- Group ordering is deterministic: descending market value, then ascending
  group ID. Top-1 ties therefore have a stable winner.
- `UNLOOKED_THROUGH` residuals stay in the groups and are marked unclassified;
  their presence prevents a `COMPLETE` concentration result.

### Fixed risk budget rules

The first ruleset is `risk-budget.v1` and is intentionally small:

| Risk level | Single asset max | Known sector max | Technology max | Unclassified max |
| --- | ---: | ---: | ---: | ---: |
| `CONSERVATIVE` | 20% | 30% | 25% | 10% |
| `BALANCED` | 35% | 45% | 40% | 20% |
| `GROWTH` | 50% | 60% | 60% | 35% |

The user's `max_drawdown_tolerance_pct` is copied into the budget as an
independent constraint. No historical series exists in this phase, so it never
becomes a fabricated drawdown measurement.

Assessment states are `PASS` only when exposure and concentration are complete
and no breach exists; `REVIEW_REQUIRED` when any breach or partial data exists;
and `BLOCKED` when no usable exposure report exists. A breach is a finding, not
an instruction to trade.

## Proposed file boundaries

允许新增或修改：

```text
app/risk/__init__.py
app/risk/contracts.py
app/risk/concentration.py
app/risk/budget.py
tests/unit/test_risk_concentration.py
tests/unit/test_risk_budget.py
tests/integration/test_phase4_risk_budget.py
tests/fixtures/risk/risk_budget_case.json
docs/risk-budget.md
README.md
TODO.md
LOG.md
```

不得修改：

```text
Prism.md
app/contracts/evidence.py
app/providers/**
app/profile/**
app/portfolio/contracts.py
app/portfolio/exposure.py
tests/unit/test_evidence_contract.py
tests/unit/test_provider_contract.py
tests/unit/test_profile_*.py
tests/unit/test_portfolio_*.py
D:\Github_Storage\tradeeye-copilot\**
D:\Github_Storage\TradeEye\**
```

## Required acceptance cases

1. asset/sector groups use Decimal sums and close to total exposure value。
2. HHI uses unrounded values and deterministic two-decimal serialization。
3. top-1 ties use a stable group-ID tie-break。
4. unknown sector and unlooked residual remain `UNCLASSIFIED`。
5. COMPLETE/PARTIAL/FAILED concentration states cannot be masqueraded。
6. missing/failed upstream exposure propagates to safe concentration states。
7. fixed risk-budget v1 maps each RiskLevel to the documented limits。
8. the same exposure produces different budgets for conservative vs growth profiles。
9. single-asset, known-sector, technology and unclassified breaches are explicit。
10. partial exposure yields `REVIEW_REQUIRED`, not PASS, even without a breach。
11. owner/profile/exposure identities must close; cross-owner inputs are rejected。
12. duplicate IDs, extra fields and mutable nested structures are rejected。
13. synthetic offline fixture is deterministic and contains no credentials/recommendation。
14. original Phase 1/2/3 79 tests continue to pass。

## Verification commands

```powershell
python -m pytest
python -m compileall -q app
python -c "from app.risk import RiskBudget, ConcentrationReport; print('phase4-import-ok')"
git diff --check
git status --short --branch
```

另外运行独立反例脚本检查 partial/failed 传播、预算边界、owner 串线、HHI
闭合、稳定排序与推荐字段扫描；审阅最终 diff 与 fixture。

## Stop conditions

- 需要修改上游 Provider/Evidence/Profile/Portfolio/Exposure 契约或 `Prism.md`。
- 必须调用网络、汇率、历史行情、LLM 或数据库才能得出指标。
- 只能通过删除 residual、填零或把风险预算解释为实际风险来通过测试。
- 无法区分数据复核、预算超限和没有可用暴露。
- 需要实现优化、最小调整或推荐才能完成当前验收。
- 基线测试失败且无法证明是本阶段新增范围造成。

## Definition of done

- 14 个验收案例有自动化测试并通过，Phase 1/2/3 的 79 项测试仍通过。
- 规则、阈值、HHI、排序和状态语义都可从结构化结果复现。
- 文档、README、TODO、LOG 与实际完成度一致，不声称优化、推荐或真实数据源。
- 只生成一个本地 Phase 4 实现提交，不 push，目标 worktree 干净。
- 完成独立反例复审；只有通过后才创建下一阶段计划书。
