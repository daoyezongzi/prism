# MVP Phase 3 Working Plan：Deterministic Look-through Exposure

- Status：`ACCEPTED`
- Owner：Codex
- Reviewer：Codex + user
- Target worktree：`D:\Github_Storage\prism-phase-3`
- Target branch：`codex/mvp-phase-3-exposure-risk`
- Source of truth：[Prism.md](../../Prism.md)
- Parent plan：[Prism Foundation](2026-09-01-foundation.md)
- Prerequisite：Phase 2 Profile/Portfolio Contracts accepted at `0de0c43`

## Goal

把 Phase 2 的 `PortfolioImportBundle` 转换为一个可审计、确定性的
portfolio look-through exposure result：保留原始持仓/基金成分的来源身份，
计算基准币种下的直接价值、基金穿透价值和未穿透残余，并明确数据覆盖与
降级原因。

本阶段只固定后续集中度、风险预算和最小调整模块的数值输入，不生成风险
结论、配置建议或交易动作。

## Product rationale

同样的基金事实，只有经过完整的穿透和覆盖标记，用户才能看见“我的科技
暴露到底来自哪只基金、哪一条成分记录、哪一个时点”。Prism 的差异不是
给出一个不可复核的 AI 百分比，而是把每个百分比拆回持仓、父基金、原始
权重和覆盖缺口；没有穿透或汇率时，系统保留不确定性而不制造零值。

## Context / constraints

- Phase 1 Provider/Evidence 契约和 Phase 2 Profile/Portfolio 契约是上游边界，
  不修改其模型和既有测试。
- `Prism.md`、`docs/architecture.md`、`docs/reuse-matrix.md` 只读；本阶段
  不重写产品总规范或上游参考仓库。
- 只使用标准库、现有 Pydantic 和 pytest，不新增生产依赖。
- 计算全部使用 `Decimal`，不使用二进制浮点；输出模型保持
  `extra="forbid"`、不可变、时区明确。
- 所有结果和贡献都带 `owner_id`、bundle/position/holding 的稳定身份，
  不能跨用户或跨来源静默合并。
- 基金/ETF 报告权重是来源值；不能按已知 Top-N 记录归一化，也不能把
  `coverage_pct` 当成完整组合暴露。

## In scope

### Deterministic exposure

- `ExposureContribution`：直接持仓、基金/ETF 原始成分穿透、未穿透残余
  三种 basis，并保留父资产、position/holding source IDs、sector 和
  `is_technology` 标记。
- `ExposureReport`：基准币种总市值、已归属市值、未分类市值、科技市值和
  组合百分比；校验贡献加总闭合。
- `ExposureResult`：`COMPLETE`、`PARTIAL`、`FAILED` 三态，区分缺少穿透、
  未来快照、非基准币种和零可计算市值等安全降级原因。
- `calculate_exposure(bundle)`：以 `Decimal` 计算
  `position.market_value * holding.weight_pct / 100`；对每个父持仓保留
  `100 - 已报告权重` 的未穿透残余，不外推、不补零。
- 固定、可测试的科技 sector 规范化规则；不让 LLM 或自然语言参与分类。

### Verification

- 合成多持仓/多基金 fixture，覆盖完整穿透、缺失穿透、非基准币种和覆盖
  缺口。
- 单元反例测试：加总闭合、稳定 ID、Decimal 精度、owner 隔离、状态不变量、
  未来快照、零市值和不可变性。
- 集成测试证明 Phase 2 bundle 可离线被消费，且原有 69 项测试持续通过。

## Explicitly out of scope

- 外汇汇率、跨币种换算、实时行情和任何网络/API/凭据。
- 行业/资产集中度、HHI、相关性、波动率、流动性、压力测试和风险预算。
- 使用 `RiskProfile` 生成风险结论，或生成守稳/均衡/进取配置区间。
- 优化、最小调整、推荐文案、Decision Receipt、Evidence Contract 改造。
- LLM、自然语言画像、研究 DAG、数据库、迁移、FastAPI、Web UI、并发/SLA。
- 修改 `Prism.md`、Phase 1/2 契约与测试、上游仓库。

## Design decisions

### Attribution and residuals

1. 基准币种中的普通股票、债券、现金和其他非基金资产产生
   `DIRECT` contribution，直接归属到 position。
2. ETF/共同基金存在不晚于 position snapshot 的 `FundHoldingSnapshot` 时，
   每条 holding 按来源权重产生 `LOOK_THROUGH` contribution；同一父持仓已
   报告权重之和不足 100% 时，差额产生 `UNLOOKED_THROUGH` contribution。
3. 缺少穿透快照或快照晚于持仓时点时，整个父持仓产生
   `UNLOOKED_THROUGH` residual 并附 `PARTIAL` issue；不把父基金假装成其
   未知成分，也不把缺失当成零。
4. 所有贡献的 `market_value` 加总必须等于可计算基准币种持仓总值；其中
   `is_attributed=false` 的 residual 加总为 `unclassified_market_value`。

### Currency and time safety

- 只有 `position.currency == snapshot.base_currency` 才进入数值总值；其他
  币种不做换算，产生 `NON_BASE_CURRENCY` issue 并使结果至少为 `PARTIAL`。
- holding snapshot 的 `as_of` 不得晚于 position snapshot 的 `as_of`；未来
  数据不能回填历史组合，产生 `FUTURE_HOLDINGS` issue 并保留 residual。
- 没有正的基准币种总市值时返回 `FAILED`，不返回人为的 0% 科技暴露报告。

### Stable classification and IDs

- sector 先 trim、casefold；只有 `technology`、`information technology`、
  `tech` 命中科技规则。未知 sector 保持未知，不猜测。
- contribution ID 由 `bundle_id`、`position_id`、`holding_id`/`residual`
  和 basis 的稳定组合构成；同一输入重复计算必须得到相同 JSON。
- 结果只引用 Phase 2 的 source/identity 字段，不把自然语言或秘密写入
  结果、日志或 fixture。

## Proposed file boundaries

允许新增或修改：

```text
app/portfolio/exposure.py
app/portfolio/__init__.py
tests/unit/test_portfolio_exposure.py
tests/integration/test_phase3_exposure.py
tests/fixtures/portfolio/portfolio_exposure_bundle.json
docs/portfolio-exposure.md
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
tests/unit/test_evidence_contract.py
tests/unit/test_provider_contract.py
tests/unit/test_profile_*.py
D:\Github_Storage\tradeeye-copilot\**
D:\Github_Storage\TradeEye\**
```

## Required acceptance cases

1. 直接持仓使用 Decimal 加总并产生可复核的 `DIRECT` contribution。
2. 一条基金 holding 的金额严格等于父持仓市值乘来源权重百分比。
3. 多条 holding、多只基金的 contribution ID 唯一且重复计算稳定。
4. 已报告权重不足 100% 时产生未穿透 residual，且贡献加总闭合。
5. 缺少基金快照时返回 `PARTIAL`，不把父基金或未知成分填成零。
6. 晚于持仓时点的基金快照不能被使用，返回 `FUTURE_HOLDINGS` issue。
7. 非基准币种不做 FX 猜测，返回 `NON_BASE_CURRENCY` issue。
8. 科技 sector 只按固定规范化集合分类，未知 sector 不被猜测。
9. 0 总基准币种市值返回 `FAILED` 且无伪造 0% 报告。
10. `COMPLETE` / `PARTIAL` / `FAILED` 的结果状态和 report/issues 组合不可伪造。
11. owner、bundle、position、holding 身份闭合，跨 owner 输入被拒绝。
12. 结果、贡献和集合不可变，未知字段和重复 ID 被拒绝。
13. 同一合成 bundle 离线重复计算得到相同序列化结果，无网络/凭据。
14. 原有 Phase 1/Phase 2 的 69 项测试继续通过。

## Verification commands

```powershell
python -m pytest
python -m compileall -q app
python -c "from app.portfolio import ExposureResult, calculate_exposure; print('phase3-import-ok')"
git diff --check
git status --short --branch
```

另外运行独立反例脚本，检查残余加总、跨币种、未来 holding、零市值、
owner 串线和稳定 ID；审阅最终 diff 与 fixture 内容。

## Stop conditions

- 需要修改 Phase 1/2 契约、Evidence、`Prism.md` 或引入新依赖。
- 必须调用真实行情、汇率、SkillHub、数据库或 LLM 才能完成计算。
- 只能通过归一化未完整报告的权重或把缺失填成零来闭合组合。
- 无法区分未穿透 residual、非基准币种和真正的零市值。
- 需要实现集中度、风险预算、配置优化或推荐才能通过当前验收。
- 基线测试失败且无法证明是本阶段新增范围造成。

## Definition of done

- 14 个验收案例有自动化测试并通过，Phase 1/2 的 69 项测试仍通过。
- 所有百分比和金额为 Decimal，贡献加总闭合，来源身份和降级 issue 可审计。
- 文档、README、TODO、LOG 与实际完成度一致，不声称 Phase 4 或真实数据源。
- 只生成一个本地 Phase 3 实现提交，不 push，目标 worktree 干净。
- 完成独立反例复审并明确剩余风险；只有通过后才创建下一阶段计划书。
