# Working Plan：MVP Phase 25 个股研究 Evidence Card（Demo F）

## Goal

把 `Prism.md` 的 Demo F——“财务事实、异常、Evidence、风险”——从上游
`tradeeye-copilot` 的参考能力和 Phase 16 的单一收入 claim，推进到一个可回放、可
审计的 Prism 个股研究工作台。用户选择一个脱敏的合成个股场景后，可以看到：

`独立来源 → Cross-Validation → VERIFIED Fact → 确定性异常 → 风险摘要`

当来源冲突、缺失、无结果或失败时，页面仍显示可审计 Evidence 和具体降级原因，
但不把未闭合数据升级为 Fact/Finding，也不产生 Recommendation 或交易动作。这样
Prism 的差异化不只是“有个股分析”，而是让用户能证明每个风险结论来自哪些来源、
为何可以或不可以被接受。

本阶段只实现 fixture-first 的个股研究纵切和本地工作台；不把离线合成结果宣称为
实时行情、真实公司覆盖或投资建议。

## Context / constraints

- Phase 24 接受提交为 `8c38a3a`；本阶段必须在全新的
  `D:\Github_Storage\prism-phase-25` worktree 完成，并先提交本计划。
- `Prism.md` 的 Stock Research Agent/Demo F、Phase 2–10 的 Provider、bounded
  executor、Cross-Validation、Evidence/Finding bridge 和 Phase 24 场景回放是实现
  真源。
- `D:\Github_Storage\tradeeye-copilot` 只读参考：复用其财务事实字段语义、现金流
  质量/应收质量/硬校验的思路和 Evidence 引用白名单原则；不跨仓库运行时导入，不
  整体复制公司分析器、短周期荐股权重、数据库或认证。
- 当前 Phase 16/24 四轨道矩阵保持不变。个股卡使用独立 manifest、fixture 和服务，
  但仍调用同一 `FixtureFinancialProvider`、`execute_research_run`、
  `build_research_evidence_pipeline`、`DecisionTrace` 和 owner/时间/敏感信息校验。
- 所有跨模块对象继续使用严格、不可变、extra-forbid、timezone-aware contract；
  金融算术只能在 deterministic layer 使用 `Decimal`，不得由 LLM 或前端计算。

## In scope（本阶段必须完成）

### 1. Versioned stock research contract and fixture manifest

- 新增严格的 `StockResearchRequest`、`StockResearchTemplateResponse`、
  `StockResearchResponse`、`StockResearchScenarioId`、`StockResearchScenarioResponse`、
  `StockRiskSummary` 和安全 issue contract。请求只接受 owner、request ID、固定合成
  subject、生成时间和场景 ID，不接受任意 Provider 参数或自然语言。
- 增加独立版本化 manifest 与两条独立 lineage 的公司财务 fixture。最小原始事实集
  为 `revenue_cny`、`net_profit_cny`、`operating_cash_flow_cny`、
  `accounts_receivable_cny`、`gross_margin_pct`、`debt_ratio_pct`；所有值、单位、
  期间、source、record 和 lineage 均来自已校验 fixture，不在代码中隐式补值。
- 场景目录至少包含：
  `BASELINE_READY`（两源一致）、`SOURCE_DISAGREEMENT`（独立来源在债务率 claim
  上冲突）、`SOURCE_PARTIAL`（一源缺少必需字段）、`SOURCE_EMPTY`（一源无结果）和
  `SOURCE_FAILED`（一源安全失败）。目录只公开稳定 ID、标签和安全说明，排序固定，
  不公开 fixture 原文、请求参数、凭据或 raw exception。

### 2. Deterministic stock research execution and evidence card

- 在新服务中构造两个有界 `COMPANY_DATA` 节点，经过现有研究 run 状态机并行执行；
  场景 overlay 只能重建并重新验证 `ProviderResult`，不得绕过 Provider 契约。
- 对六个原始 claim 逐项执行 lineage-aware Cross-Validation。只有两条独立、同口径、
  同期间且一致的 VERIFIED Evidence 才能经既有 bridge 生成 Fact；任何非 READY 运行
  保留 Evidence，但不得暴露 Fact/Finding。
- READY 基线在 deterministic layer 计算并登记可追溯 Finding：
  - 现金流质量：`operating_cash_flow_cny / net_profit_cny * 100`，低于固定阈值时
    生成 WARNING；
  - 应收占比：`accounts_receivable_cny / revenue_cny * 100`，超过固定阈值时生成
    WARNING；
  - 杠杆风险：`debt_ratio_pct` 超过固定阈值时生成 CRITICAL。
  每个 Finding 只引用已闭合 Fact，使用 `Decimal`、固定量化和版本化 methodology；
  不实现估值、价格预测、公告情绪或推荐评分。
- 输出一个 owner/run/subject/period 闭合的 `StockResearchResponse`：包含 run 与
  pipeline 状态、六个 Fact（仅 READY）、异常 Findings、`StockRiskSummary`、完整
  `DecisionTrace` 和安全 issues。风险只表达 `NOT_ASSESSED/CLEAR/WATCH/HIGH_RISK`，
  不表达买卖或配置比例。
- 非 READY 场景分别保留 PARTIAL/EMPTY/FAILED/UNRESOLVED 语义；不可将失败映射为
  EMPTY、不可用零值代替缺失、不可因为存在部分 Evidence 就伪造风险结论。

### 3. Owner-scoped API and Demo F workbench

- 增加 owner-scoped：
  - `GET /api/v1/advisor/stock-research-template`：返回固定合成 subject/period、
    指标标签、阈值说明和安全场景目录；
  - `POST /api/v1/advisor/stock-research-runs`：提交严格请求并返回上述卡片。
  服务可注入以便契约测试，错误只映射为安全 `STOCK_RESEARCH_ERROR`，不回显异常。
- 在静态工作台增加 “Demo F · 个股研究” 区域：从模板加载场景选择器，显示运行
  状态、财务事实、异常/风险摘要，并可展开 Finding → Fact → Evidence 的 source、
  lineage、value、unit、period；非 READY 时显示“Evidence 可见但未升级”为 Fact
  的原因。
- 复用 Phase 24 的 owner 切换、场景变化、异步 sequence 保护；任何 owner、模板、
  场景或请求竞态都不能把旧卡写回。动态内容只用 `textContent`/节点 API 和同源
  `fetch`，页面明确标注 synthetic/offline replay 与“不是交易建议”。
- 个股研究不写 `DecisionEventStore`，不进入 Advisor HOLD/REDUCE 纵切，不增加
  Recommendation 旁路。

### 4. Tests, documentation and review evidence

- 新增 Phase 25 contract/service/API 集成测试：五场景状态、六 claim 的证据闭合、
  cashflow/receivable/debt deterministic Finding、风险分级、稳定重放、owner 隔离、
  extra/unknown/sensitive/naive 输入拒绝、失败/缺失语义、无 DecisionEvent 副作用、
  既有 Advisor/Research Tracks 回归。
- 增加静态边界测试：无上游运行时导入、无 LLM/Gemini/网络/凭据/原始 fixture leak、
  无 HTML sink、无订单/Recommendation 路径；检查 wheel 包含新 fixture 和静态资源。
- 真实本地浏览器验证：基线显示六个财务事实、至少一条异常和 HIGH_RISK 但无交易
  建议；分歧显示待复核与双方 Evidence；PARTIAL/EMPTY/FAILED 显示具体降级且不出现
  Fact/Finding；切换 owner 清空旧卡，浏览器 console error 为空。
- 新增 `docs/stock-research-card.md`，更新 `docs/architecture.md`、README/TODO/LOG
  和本计划的独立审查/验收记录。

## Out of scope（明确不做）

- 真实同花顺问财 SkillHub/Tushare/网络 Provider、在线鉴权、凭据、重试/缓存/断路器、
  生产持久化、认证或真实公司覆盖。
- 自然语言问题理解、LLM/Gemini、多 Agent 对话、模型生成结论或自动场景推断。
- 估值模型、价格/收益预测、公告/新闻、完整盈利质量因子库、行业分类、财报多期
  趋势、可转债/ETF 分析，以及任何交易、配置、买卖或 Recommendation/Receipt 变化。
- 修改 Phase 16/24 四轨道矩阵的 claim/node 数量；修改上游仓库、重写历史或 push。
- Portfolio/Risk Profile CRUD、研究历史/后台队列、推送和真实 100 用户/3 秒/99.9%
  SLA 声明。

## Reuse boundary

- 复用 Prism 现有 `Evidence`、`Fact`、`Finding`、`DecisionTrace`、
  `FixtureFinancialProvider`、Provider 四态校验、`normalize_result_to_evidence`、
  bounded executor、`validate_claim`、`bridge_cross_validation` 和
  `build_research_evidence_pipeline`；新服务只编排个股 manifest、场景 overlay、
  deterministic 派生 Finding 和卡片投影。
- 复用 `tradeeye-copilot` 的 `PeriodSnapshot` 字段语义、现金流质量/应收质量规则
  思路、硬检查与引用白名单原则；所有运行时代码在 Prism 内重写，并注明上游基线，
  不携带其 store、认证、短线权重或未经授权的资产。
- 复用 Phase 24 的静态 UI 视觉 token、owner dependency、错误边界、场景回放和
  sequence 保护；不复制 Research Tracks 的四轨道响应契约。

## Product differentiation

普通个股聊天产品通常直接给出“看多/看空”或一个综合分数，用户无法确认数字来自哪
个来源，也不知道缺一个字段时结论是否仍然成立。Prism 的个股卡先展示独立来源与
lineage，再让 deterministic layer 计算现金流质量、应收占比和杠杆风险；来源冲突或
退化时，证据仍可见但 Fact/Finding 和风险评估被拒绝。用户选择 Prism，是因为可以
追问“这条风险用的是什么数、哪个来源、何时失效”，而不是只能相信一段不可审计的
生成式摘要。

## Acceptance gates

1. 本计划先于任何实现提交；所有代码/文档改动只发生在 Phase 25 worktree，基于
   `8c38a3a`。
2. Request/template/response/scenario/risk contracts extra-forbid、immutable、
   timezone/owner/sensitive-safe；目录和结果排序稳定，未知场景、额外字段、敏感
   字段和 naive timestamp 安全拒绝。
3. 基线两源六 claim 形成 COMPLETED/READY，六个 VERIFIED Fact、确定性异常 Finding
   和 HIGH_RISK 摘要；分歧为 UNRESOLVED/REVIEW_REQUIRED，partial/empty/failed 保留
   各自四态，所有非 READY 响应无 Fact/Finding/风险分级结论。
4. 每个 READY Finding 的 Fact/Evidence 引用通过 `DecisionTrace` 闭合；Evidence 的
   source/record/lineage/value/unit/period 与 provider 输出一致。重复请求字节稳定，
   不同 owner 隔离，任何运行不写 DecisionEventStore，不生成 Recommendation。
5. 本地浏览器完成五场景展示、Evidence 展开和 owner 清理；无 console error、外网
   请求、HTML 注入或 raw exception/fixture leak；Advisor HOLD/REDUCE 与 Phase 24
   Research Tracks 回归通过。
6. Phase-specific tests、全量回归、compile/import、node/static、eval replay、load
   baseline、wheel/package-data 和 `git diff --check` 通过；独立审查后修复发现，
   再将本计划标记 `ACCEPTED`，随后才创建 Phase 26 worktree。

## Handoff / stop conditions

- 若个股场景无法满足既有 Provider、run、Cross-Validation 或 DecisionTrace 契约，
  必须保留安全失败并停止该场景，不降低验证标准或伪造 READY。
- 任何派生 Finding 必须能回到本次运行的 VERIFIED Fact；计算输入缺失、非有限或
  单位/期间不一致时，风险状态只能是 `NOT_ASSESSED`。
- 真实 SkillHub、在线鉴权、估值/价格数据和生产 SLA 仍是外部输入，不因本地 fixture
  卡片而宣称完成。
- Phase 26 只能从 Phase 25 接受提交创建新 worktree，并先提交下一阶段计划书。

## Independent review and acceptance

待 Phase 25 实现、独立审查、修复和验证后填写。

## Status

`PLANNED`
