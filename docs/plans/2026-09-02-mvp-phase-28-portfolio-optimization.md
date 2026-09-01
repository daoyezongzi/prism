# Prism MVP Phase 28：确定性组合优化目标提案计划

状态：`PLANNED`

日期：2026-09-02

工作树：`D:\Github_Storage\prism-phase-28`

基线：Phase 27 已验收提交 `5fbd022`

## 1. 阶段目标

本阶段补齐 `Prism.md` Portfolio Engine 的最小可用纵切：在已经确认的
Risk Profile 与 owner-scoped Portfolio snapshot 上，生成一个可复算、可解释、
不产生交易副作用的“约束目标权重提案”。提案以现有 Exposure、Concentration 和
Risk Budget 为输入，使用版本化的 deterministic cap-and-redistribute 规则，明确
说明当前权重、目标权重、上限、释放/分配的算术和失效条件。

这个能力回答的是“在当前证据和画像约束下，目标结构是否可行、每个资产/行业要往
哪里靠近”，而不是“现在应该买卖什么”。它是组合引擎的第一版 target proposal，
不是数学意义上的全局最优解、收益预测或 Recommendation。只有完整且可闭合的
portfolio input 才能产生 READY 提案；数据不足或约束不可行时保留 REVIEW_REQUIRED /
BLOCKED，绝不以零值或默认权重填补。

## 2. 明确做什么

### 2.1 版本化组合优化契约

- 新建 `app/optimization`，提供严格 `PortfolioOptimizationRequest`、模板、场景、
  资产目标、约束摘要、问题和响应契约；所有对象带 schema version、timezone-aware
  时间、owner/bundle/snapshot/profile/assessment/exposure/concentration 闭包。
- 请求只接受已经结构化的 `RiskQuestionnaire`、`PortfolioImportBundle` 和固定场景
  ID，不接受自然语言、Provider 参数、凭据或模型提示；服务端重新确认问卷并重新
  计算 Exposure、Concentration、Risk Budget，不信任客户端传入的派生对象。
- 响应显式记录 `methodology_version`、输入报告 ID、画像版本、规则上限、当前/目标
  权重、每项 delta、约束 disposition、可读但安全的 rationale、invalidation 条件和
  issues；不包含 Recommendation、DecisionEvent 或订单字段。

### 2.2 最小确定性目标算法

采用单一、版本化的 `CAP_AND_REDISTRIBUTE_V1`，以 Decimal 和固定两位小数运行：

1. 从完整 Exposure contributions 按资产和行业聚合当前权重；Technology 与
   UNCLASSIFIED 单独保留预算维度。
2. 根据 `RiskBudget` 计算每个行业/特殊维度的可用上限；先把超过上限的 bucket
   截到上限，记录释放权重，再按稳定的资产 ID 顺序将释放量分配给有 headroom 的
   bucket。每轮都量化并以最后一个可接收项吸收舍入余数，保证目标总和恰为 100.00%。
3. 在 bucket 内按当前权重比例分配，并迭代应用单资产上限；任何资产、行业、科技或
   未分类上限无法同时满足时返回 `BLOCKED/INFEASIBLE_CONSTRAINTS`，不输出伪目标。
4. 输出每个目标资产的 `current_weight_pct`、`target_weight_pct`、`delta_pct`、
   `allowed_max_weight_pct`、受影响约束和解释；算法声明是可解释的约束修复启发式，
   不宣称收益最优、风险最小或经过历史回测。

算法只使用已经观测到的权重，不模拟未来收益、波动、相关性或价格；同一输入、同一
画像版本和同一规则版本必须产生相同 ID、顺序和数值。画像从 Conservative 到
Balanced/Growth 的预算上限改变时，目标提案必须发生可验证的变化；画像变化、持仓
快照变化、穿透覆盖率/基准币种变化或规则版本变化都会使提案失效。

### 2.3 数据质量与状态边界

- Exposure 为 `COMPLETE`、无未分类残余且可计算 Concentration/Risk Budget 时，才允许
  READY 提案。
- Exposure/Pipeline 为 `PARTIAL`、非基准币种、穿透覆盖不足或预算输入有 issue 时，
  返回 `REVIEW_REQUIRED`，保留安全 issue、报告身份和当前约束摘要，不返回目标权重。
- Exposure/Concentration 失败或目标约束不可行时，返回 `BLOCKED`，只保留安全原因，
  不把失败、空范围或缺失转换成零权重。现有 `EMPTY`/`FAILED` provider 语义不改变。
- 当前预算有 breach 并不自动伪装成 PASS；若完整输入可通过规则修复，响应仍必须标明
  当前 `REVIEW_REQUIRED` 风险状态以及每个 breach 的目标影响。组合提案不会绕过现有
  Risk/Compliance gate，也不会直接进入 Advisor Recommendation。

### 2.4 Owner-scoped API 与工作台

- `GET /api/v1/advisor/portfolio-optimization-template`：返回一个脱敏的多资产合成
  portfolio、默认问卷、方法版本、约束说明和可重放的 `BASELINE_READY`、
  `SOURCE_PARTIAL`、`INFEASIBLE` 场景目录。
- `POST /api/v1/advisor/portfolio-optimization-runs`：接受严格请求和 `X-Owner-ID`，
  服务端重新绑定/确认 owner，重新计算全部上游派生结果，并在 API 注入边界重新验证
  response 与 request/profile/snapshot/report identity；错误只映射为
  `PORTFOLIO_OPTIMIZATION_ERROR`。
- 静态工作台增加 Portfolio Optimization card，与现有 Portfolio/Risk Profile context
  复用 owner 切换和 sequence 防护；显示方法、当前/目标权重对比、预算上限、delta、
  约束解释、数据质量状态和失效条件。动态内容只使用 DOM 节点 API/textContent，
  请求只走同源 fetch；切换 owner、portfolio、问卷或场景会清空过期提案。
- 页面明确标注 synthetic/offline replay、“目标结构提案，不是交易指令”，并提供
  约束失败时的可审阅原因；不修改既有 Stock/Fund/Convertible 语义。

## 3. 明确不做

- 真实 SkillHub/Wencai/Tushare/券商网络、在线鉴权、凭据、重试、缓存、连接池、
  断路器、动态限流、生产数据库或真实账户同步。
- LLM/Gemini、自然语言解析、模型预测、模型生成权重、自由多 Agent 对话或把模型
  输出当成事实。
- 均值-方差、风险平价、相关性矩阵、协方差估计、波动/回撤预测、流动性压力、税费、
  汇率、交易成本、最小交易单位、历史回测、收益承诺或全市场资产选择。相关性和
  流动性在没有新鲜可验证输入前保持缺失，不写成“已优化”。
- 买入/卖出/持有 Recommendation、HOLD/REDUCE、仓位指令、订单执行、
  `DecisionEventStore` 写入、Advisor receipt 改写或绕过 Compliance。
- 复制 `tradeeye-copilot`/`TradeEye` 运行时代码；只复用已记录的领域命名/审计思路，
  不导入上游模块。不上游仓库写入，不改历史，不 push。
- 借由修改现有 Advisor 模板掩盖优化能力；本阶段使用独立 optimization fixture，
  既有 Advisor/研究卡保持向后兼容。

## 4. 复用边界与实现策略

### 复用

- `PortfolioImportBundle`、`calculate_exposure`、`calculate_concentration`、
  `assess_risk_budget` 和 `RiskProfile`/`confirm_questionnaire` 作为唯一上游输入；
  不重写其 owner、时区、Decimal 和四态数据质量语义。
- 复用 `ContractModel`、敏感字段防护、稳定 ID、`FixtureFinancialProvider` 的
  fixture-first 约束、API owner dependency/error mapping、静态 workbench 的暖白/深墨/
  陶土橙视觉语法与 DOM 安全模式。
- 复用 Phase 26/27 的“计划先行、fixture manifest、明确非 READY、注入边界再校验、
  browser evidence”验收方法；不复制资产卡字段或研究节点状态机。

### 新增或适配

- 新建 `app/optimization/contracts.py` 与 deterministic service；算法实现只有一个
  入口，所有数值使用 `Decimal`/固定 rounding，响应模型自行闭合并检查总和、上限、
  owner/报告 identity、状态和 rationale 引用。
- 新建 `app/fixtures/optimization`，包含一个五资产、多行业、可在不同 profile 下
  展示 cap-and-redistribute 的模板和一个低覆盖/不可行 replay 输入；fixture 不含
  网络地址、凭据或私人持仓。
- 在 `app/api` 增加最小模板/run 路由与 service 注入点，在 `index.html`/`app.js` 增加
  一个独立卡片；任何现有 API 返回字段的改动都必须有回归测试证明兼容。
- 在 `docs/architecture.md`、README、TODO、LOG 和本计划验收记录中如实记录目标提案
  能力及剩余未实现项；更新 package-data，保证 wheel 安装后可加载 optimization
  fixture。

## 5. 验收门（必须全部通过）

### 计划门

1. 本计划书先独立提交；计划提交前不修改业务代码。

### 契约与算法门

2. 阶段测试覆盖：合法/extra/敏感/naive 时间/owner 越权拒绝；严格 schema version；
   当前和目标权重总和闭合；单资产、行业、technology、unclassified 上限；Decimal
   舍入余数；稳定排序/ID；profile 版本与报告 identity；methodology/invalidation；
   无 Recommendation/DecisionEvent 字段或副作用。
3. 算法测试覆盖 baseline、Conservative/Balanced/Growth 的可重复且有差异的目标、
   已有 breach 的可修复提案、非基准币种/不完整穿透的 REVIEW_REQUIRED、约束总容量
   不足的 BLOCKED/INFEASIBLE；缺失保持缺失，不生成零值。
4. API 注入测试用 `model_copy(update=...)`、伪造 owner/profile/report/target/status/
   总和和 scope，确认边界重新验证并安全返回 `PORTFOLIO_OPTIMIZATION_ERROR`；重复
   请求不得写入 DecisionEventStore。

### 回归与静态安全门

5. 阶段测试、全量 `pytest`、`compileall`、公开 import、前端 `node --check`、
   `git diff --check` 全部通过，既有 377 项基线不退化。
6. 静态/打包扫描确认无外网、LLM/Gemini、上游运行时导入、凭据、raw fixture leak、
   HTML sink、订单或 Recommendation 旁路；wheel 包含 optimization contracts/service/
   manifest/fixtures/static resources，wheel 安装后可加载模板。
7. `python -m tools.evaluate_mvp --repeat 100 --json` 维持 9/9、所有指标 1.0；本地
   ASGI 100 并发记录 template/run 的 P50/P95/P99、错误、owner mismatch 和 store
   行数，明确声明为 fixture 基线，不外推真实市场 SLA。

### 浏览器验收门

8. 真实本地浏览器完成模板、baseline READY、不同 Risk Profile 目标变化、PARTIAL /
   INFEASIBLE 阻断和 owner 切换；可见方法、权重对比、cap/delta、约束解释、报告/画像
   identity、失效条件；控制台错误为 `[]`、无外部请求，旧 owner/旧场景结果不残留。

## 6. 阶段停止条件与后续

只有上述验收门全部通过，并由独立审查修复所有 P0/P1 契约缺口后，才把本计划改为
`ACCEPTED` 并从接受提交创建下一个全新 worktree。任何实时 Provider、相关性/流动性
模型、组合历史回测、调仓执行和持久化画像都登记为后续阶段，不在本阶段顺手实现。

## 7. 验收记录（实现后填写）

- 待实现后填写实现提交、独立审查发现/修复、阶段与全量测试、评测/并发、wheel、
  浏览器和最终状态。
