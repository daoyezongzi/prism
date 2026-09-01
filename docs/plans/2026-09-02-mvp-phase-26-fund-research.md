# Working Plan：MVP Phase 26 ETF/Fund 资产研究 Evidence Card（Demo G）

## Goal

在 Phase 25 的 Demo F 个股卡之后，把 Prism 旗舰场景中“科技基金集中持仓体检”所需
的资产级基金事实做成独立、可回放、可审计的 Demo G。用户选择一个脱敏的合成 ETF
场景后，可以看到：

`独立来源 → Cross-Validation → VERIFIED Fact → 确定性资产风险 Finding → 风险摘要`

本阶段补齐基金/ETF 研究最有价值的第一组数字（科技暴露、前十大集中度、费用、波动、
最大回撤、跟踪误差），并把“来源冲突/字段缺失/无结果/失败”展示为可解释的阻断。
它服务于 Portfolio 复核，但不把资产卡直接变成组合调整或交易建议。选择 Prism 的
理由仍然是可验证的 Evidence 与明确的失效边界，而不是另一个不可审计的基金评分。

## Context / constraints

- Phase 25 接受提交为 `956d753`；本阶段只能在新建的
  `D:\Github_Storage\prism-phase-26` worktree 实施，并且本计划先于代码提交。
- `Prism.md` 的 ETF/Fund Agent、Evidence Architecture、Cross Validation、Portfolio
  Engine 和 Phase 16/24 研究轨道是产品/架构真源。
- Phase 16/24 的四轨道矩阵保持不变；Demo G 是独立资产卡，不扩张原矩阵的 claim/node
  闭包，也不把结果写入 Advisor 的 DecisionEvent。
- 继续复用 Phase 25 的严格 contract、fixture overlay、owner/时间/敏感字段边界和
  text-only 工作台模式；所有派生计算在服务端 deterministic `Decimal` 层完成。
- `D:\Github_Storage\tradeeye-copilot` 只读参考其 ETF 字段语义、持仓集中度/费用和
  波动回顾思路；不得运行时导入其分析器、认证、数据库或短线评分。

## In scope（本阶段必须完成）

### 1. Versioned fund research contract and fixture manifest

- 新增严格的 `FundResearchRequest`、`FundResearchTemplateResponse`、
  `FundResearchResponse`、`FundResearchScenarioId`、`FundResearchNodeResponse`、
  `FundRiskSummary` 与安全 issue contract。请求仅接受 owner、request ID、固定合成
  fund subject/period、timezone-aware `generated_at` 和场景 ID，不接受任意 Provider
  参数或自然语言。
- 增加独立版本化 manifest 与两条独立 lineage 的 ETF 事实 fixture。六个最小原始
  指标为：`technology_weight_pct`、`top10_weight_pct`、`expense_ratio_pct`、
  `annualized_volatility_pct`、`max_drawdown_pct`、`tracking_error_pct`。所有值、单位、
  期间、source、record 和 lineage 必须来自校验后的 fixture。
- 场景目录至少包含 `BASELINE_READY`（双源一致）、`SOURCE_DISAGREEMENT`（来源 B
  改变科技暴露或前十大集中度）、`SOURCE_PARTIAL`（来源 B 缺一个必需字段）、
  `SOURCE_EMPTY` 和 `SOURCE_FAILED`。目录只公开稳定 ID、标签和安全说明，不公开 raw
  fixture、请求参数、凭据或异常堆栈。

### 2. Deterministic fund execution and asset-risk card

- 使用两个有界 `FUND_DATA` 节点，复用现有 `FixtureFinancialProvider`、research run
  状态机、Provider 四态校验、lineage-aware Cross-Validation、Evidence/Finding bridge
  与 `DecisionTrace`。场景 overlay 只能重建并重新验证 `ProviderResult`。
- 六个 claim 只有在两条独立、同口径、同期间来源一致时才生成 VERIFIED Fact；任何
  非 READY 运行保留 Evidence 与节点 reason，但不得暴露 Fact/Finding/风险分级。
- READY 基线在 deterministic layer 计算固定阈值 Finding：
  - 科技暴露高于 50% → `FUND_TECHNOLOGY_CONCENTRATION` WARNING；
  - 前十大权重高于 60% → `FUND_TOP10_CONCENTRATION` WARNING；
  - 年化波动高于 25% → `FUND_VOLATILITY_RISK` WARNING；
  - 最大回撤高于 30% → `FUND_DRAWDOWN_RISK` CRITICAL；
  - 费率高于 1.00% → `FUND_COST_WARNING` WARNING；
  - 跟踪误差只作为已验证资产事实展示，不在本阶段额外发明质量评分。
  每个 Finding 只引用闭合 Fact，使用 `Decimal`、固定量化和版本化 methodology，不由
  LLM 或前端计算。
- 输出 owner/run/subject/period 闭合的 `FundResearchResponse`，风险只表达
  `NOT_ASSESSED/CLEAR/WATCH/HIGH_RISK`，不表达买卖、配置比例或收益承诺。

### 3. Owner-scoped API and Demo G workbench

- 增加 owner-scoped：
  - `GET /api/v1/advisor/fund-research-template`：返回固定合成 fund/period、指标标签、
    阈值和安全场景目录；
  - `POST /api/v1/advisor/fund-research-runs`：提交严格请求并返回资产卡。
  服务可注入，错误只映射为安全 `FUND_RESEARCH_ERROR`。
- 静态工作台增加“Demo G · ETF/Fund 研究”区域：显示模板场景、run/pipeline、六个
  Fact、确定性 Finding/风险，并支持 Finding → Fact → Evidence 展开 source、lineage、
  value、unit、period。非 READY 显示节点状态、缺失字段、范围说明和安全 issue。
- 复用 owner 切换、场景变化、异步 sequence 保护；动态内容只用 `textContent`/节点 API，
  请求只走同源 `fetch`。页面明确标注 synthetic/offline replay 与“不是交易建议”。
- Demo G 不写 `DecisionEventStore`，不进入 HOLD/REDUCE 纵切，不生成 Recommendation，
  不把资产风险 Finding 当成组合调整命令。

### 4. Tests, documentation and review evidence

- 新增 Phase 26 contract/service/API 集成测试：五场景语义、六 claim 证据闭合、五条
  deterministic Finding、风险分级、稳定重放、owner 隔离、extra/unknown/sensitive/
  naive 输入拒绝、无副作用和既有 Phase 25/24 回归。
- 增加静态边界测试：无上游运行时导入、无网络/LLM/Gemini/凭据/raw fixture leak、无
  HTML sink、无订单/Recommendation 旁路；检查 wheel 包含新 fixture、服务和静态资源。
- 真实本地浏览器验证：基线六 Fact、风险 Finding、HIGH_RISK；分歧显示双方 Evidence；
  PARTIAL/EMPTY/FAILED 显示具体节点 reason 且无 Fact/Finding；owner 切换清空旧卡；
  console error 为空。
- 新增 `docs/fund-research-card.md`，更新 `docs/architecture.md`、README、TODO、LOG
  与本计划独立审查/验收记录。

## Out of scope（明确不做）

- 真实同花顺问财/SkillHub/Tushare 网络 Provider、在线鉴权、凭据、重试/缓存/断路器、
  真实基金覆盖、实时行情和生产存储。
- 自然语言理解、LLM/Gemini、多 Agent 对话或模型生成基金结论。
- 组合优化、相关性矩阵、流动性压力、调仓区间、HOLD/REDUCE、交易/配置/Recommendation
  和 Decision Receipt 变化。
- 基金成分股逐行导入、行业分类全量映射、收益预测、估值、新闻情绪、可转债和个股卡
  的改写；这些能力留给后续独立阶段。
- 修改 Phase 16/24 四轨道矩阵的 claim/node 数量，修改上游仓库，重写历史或 push。

## Reuse boundary

- 复用 Prism 的 `Evidence`、`Fact`、`Finding`、`DecisionTrace`、
  `FixtureFinancialProvider`、Provider 四态校验、normalization、bounded executor、
  Cross-Validation、Evidence/Finding bridge 和 Phase 25 的 node-reason UI 模式；新服务
  只编排 fund manifest、场景 overlay、deterministic Finding 和卡片投影。
- 只读借鉴 `tradeeye-copilot` 的 ETF 字段命名、费用/波动/回撤/集中度检查思路和引用
  白名单原则；运行时代码全部在 Prism 内重写，不带入其 store、认证、短线权重或网络。
- 复用 Phase 25 的 owner 依赖、状态标签、异步 sequence、错误脱敏和 Evidence drill-down，
  但不复制个股风险阈值或股票-specific contract。

## Product differentiation

许多基金产品把“科技仓位高”“回撤大”压缩成一个无法核验的分数，来源冲突时仍然照常
给出结论。Prism 的 Demo G 先让用户看到两条独立 lineage 的原始数字和期间，再用固定
规则计算集中度、费用、波动和回撤风险；一旦来源冲突或字段退化，Evidence 仍可审阅，
但 Fact/Finding/风险评估被阻断。对于已经持有科技基金的用户，这种可回答“哪条数据、
哪个期间、何时失效”的资产卡比泛化的基金推荐更能支撑下一步组合讨论。

## Acceptance gates

1. 本计划先于任何实现提交；全部改动只发生在 Phase 26 worktree，基于 `956d753`。
2. Request/template/response/scenario/risk/node contracts extra-forbid、immutable、
   timezone/owner/sensitive-safe；排序、枚举和错误映射稳定。
3. 基线两源六 claim 形成 COMPLETED/READY、六个 VERIFIED Fact、确定性 Finding 和
   HIGH_RISK；分歧、PARTIAL、EMPTY、FAILED 保留各自语义，非 READY 无 Fact/Finding、
   风险为 NOT_ASSESSED。
4. 每个 READY Finding 的 Fact/Evidence 引用通过 `DecisionTrace` 闭合；Evidence 的
   source/record/lineage/value/unit/period 与 provider 一致；重复请求稳定、owner 隔离、
   不写 DecisionEvent、不生成 Recommendation。
5. 本地浏览器完成五场景、Evidence 展开、owner 清理；无 console error、外网请求、
   HTML 注入、raw exception 或 fixture leak；Phase 25/24 与 Advisor HOLD/REDUCE 回归通过。
6. Phase-specific、全量、compile/import、node/static、eval replay、load baseline、
   wheel/package-data、`git diff --check` 通过；独立审查发现必须有单独修复提交，之后
   才将计划标记 `ACCEPTED` 并创建 Phase 27 worktree。

## Handoff / stop conditions

- 若 ETF/Fund 场景不能满足既有 Provider、run、Cross-Validation 或 DecisionTrace 契约，
  保留安全失败并停止，不降低验证标准或伪造 READY。
- 计算输入缺失、非有限、单位/期间不一致时只能输出 `NOT_ASSESSED`；不得以零值补齐。
- 真实 SkillHub、实时数据、组合优化、身份认证和生产 SLA 是外部输入，不因离线卡片而
  宣称完成。
- Phase 27 只能从 Phase 26 接受提交创建新 worktree，并先提交下一阶段计划书。

## Independent review and acceptance

- 计划提交：`975cfe6`；首版实现：`5a32d4f`。
- 独立审查发现 Fund 节点投影只校验时间排序，可能接受 COMPLETE 携带缺失/问题、
  PARTIAL/FAILED 无原因以及不合适的运行中状态；`d076ff2` 对齐底层 run 状态机的
  PENDING/RUNNING/COMPLETE/PARTIAL/EMPTY/FAILED/CANCELLED 不变量，并增加 11 条
  对抗性回归。
- 第二项审查发现可注入服务的 `model_copy(update=...)` 可以绕过输出模型且不检查
  request subject/period/scenario 闭合；`bcb77a2` 在 API 边界重新验证
  `FundResearchResponse`、拒绝类型/owner/范围漂移，并增加安全错误映射测试。
- 第三项审查发现风险摘要只检查 finding ID 存在，可能把触发 WARNING/CRITICAL 的
  卡伪装成 CLEAR；`6efa834` 要求 READY 的 WATCH/HIGH_RISK 覆盖全部非 INFO Finding，
  CLEAR 不得隐藏风险，并增加风险闭合回归。
- Phase-specific tests `24 passed`；全量回归 `349 passed`（仅已知 Starlette/httpx
  deprecation warning）。`compileall`、公开导入、`node --check`、`git diff --check`
  通过。
- `python -m tools.evaluate_mvp --repeat 100 --json` 为 9/9，所有评测指标为 `1.0`。
  本地 ASGI 100 并发基线：template 100/100，P50/P95/P99
  `89.246/105.397/110.999 ms`；research 100/100，`633.268/846.385/858.832 ms`；
  advisor 100 logical operations（200 requests），`939.101/1478.687/1520.639 ms`；
  error 与 owner mismatch 均为 0，Advisor 预期写入 100 条，另两场景无写入。以上仅为
  fixture/ASGI 基线，不外推生产 SLA。
- wheel 复核为 `100` entries，包含 fund manifest、双 provider fixture、service/contracts
  和静态资源；运行时范围扫描确认没有上游运行时导入、外网、LLM/Gemini、凭据、HTML
  sink、订单或 Recommendation 旁路。
- 真实本地浏览器完成模板与五场景回放：基线显示六个 VERIFIED Fact、五类确定性
  Finding/HIGH_RISK；分歧显示双方科技权重 Evidence 与 lineage；PARTIAL/EMPTY/FAILED
  显示各自状态、缺失/范围/安全 issue 且没有 Fact/Finding；展开链路可见
  Finding → Fact → Evidence；owner 切换清空旧 run。浏览器 console error 为 `[]`，页面
  只发同源请求。

结论：Phase 26 验收通过，提交链为 `975cfe6` → `5a32d4f` → `d076ff2` → `bcb77a2`
→ `6efa834`；本地未 push。下一阶段必须从 `6efa834` 创建新 worktree 并先提交
计划书。

## Status

`ACCEPTED`
