# Working Plan：MVP Phase 16 四类研究专员节点矩阵

## Goal

把项目规范中尚未落地的 Macro、Industry、Stock、ETF/Fund 四类研究节点，
从“枚举和执行器已经预留”推进为可复用、可验证的结构化研究专员矩阵。
每类专员由明确的研究范围、Provider operation、必需字段、预算和 Evidence
输入定义；同一类结论至少由两条独立 lineage 的 fixture 来源支持，再交给
现有 bounded executor、Cross Validation 和 Evidence/Finding pipeline。

本阶段交付的是**确定性节点配方和离线可运行矩阵**，不是把 Gemini/LLM
接入运行时。四类专员的产品价值在于职责和证据可审计，而不是 Agent 数量。

## Context / Constraints

- `Prism.md` 是唯一产品规范；P0 旗舰场景仍是“科技基金集中持仓体检”。
- Phase 15 接受提交为 `1edb3d9`；本阶段必须在独立
  `D:\Github_Storage\prism-phase-16` worktree 完成，并先提交本计划。
- 现有 `ResearchNodeKind` 已包含 `MACRO`、`INDUSTRY`、`STOCK`、`FUND`，
  `ProviderOperation` 已有对应数据操作；本阶段补的是节点配方、四轨道 fixture
  矩阵和消费边界，不再创建第二套研究状态机。
- 一个研究轨道可以有多个 Provider 节点；本阶段的演示矩阵为四个轨道各两个
  source node（共八个执行节点），用两条独立 lineage 支持一条 claim。
- `ResearchNodeKind.FUND` 作为 ETF/Fund 统一运行边界；fixture 使用 ETF 形态的
  合成标的，但不宣称已完成真实 ETF 或公募基金数据接入。
- 任何事实仍必须经过 Provider → normalized Evidence/Observation →
  Cross Validation → Evidence/Finding bridge；不以专员文本或多数票代替证据。

## In scope（本阶段必须完成）

### 1. Structured specialist node contracts

新增 `app/research` 的结构化节点配方/矩阵契约（名称可按实现调整，但必须保持
以下语义）：

- 单节点包含稳定 `node_id`、owner、`ResearchNodeKind`、允许的
  `ProviderOperation`、subject、required fields、只读参数、依赖、required 标记、
  timeout，以及它所服务的 claim 的 metric/unit/period/expected value 和安全
  Finding 元数据；
- 矩阵包含 `matrix_id`、owner、request/replay anchor、budget、scope 和节点集合；
  节点 ID/claim ID/source ID 排序和唯一性确定，至少覆盖四个
  `ResearchNodeKind`，允许同一 kind 出现多个 source node；
- 合同重新验证 owner 闭包、kind→operation 白名单、依赖闭包、节点 timeout≤run
  budget、claim 元数据一致性、每条 claim 至少两条不同 lineage，以及时区/有限
  Decimal/额外字段/敏感元数据拒绝；不允许 recommendation、订单、目标价或秘密
  形状字段；
- 暴露一个供执行器和后续用例复用的 operation 白名单入口，避免在新模块复制
  Provider/研究状态语义。

### 2. Fixture-first four-track matrix runner

新增一个独立的 fixture-first service/adapter，加载打包的四轨道合成 manifest
和八个 Provider fixtures，并只编排现有模块：

1. owner 重绑定并重新验证矩阵模板；
2. 将节点配方转换为既有 `ResearchPlan`/`ResearchNodeSpec` 和
   `ResearchNodeRequest`，八个根节点在 bounded executor 中并行执行；
3. 使用注入的 `generated_at` clock 调用 `FixtureFinancialProvider`，保留四态、
   deadline、required/optional、Evidence ID 和 Observation 闭包；
4. 为 Macro、Industry、Stock、FUND(ETF/Fund) 各构造一个 claim，调用既有
   `build_research_evidence_pipeline`，成功时输出四组 READY `Fact → Finding`
   和每组两条 lineage 的 Evidence；
5. 结果只暴露矩阵/运行状态、验证、bridge 和 trace，不生成
   Recommendation/Decision Receipt，也不写入数据库；固定输入可重放且不同
   owner 完全隔离。

### 3. Degraded and tamper fixtures

- 为四轨道至少提供 SUCCESS 双 lineage 的完整 fixture；文本字段可保留在
  Evidence，但只有有限数值、单位和期间齐全时才成为 Observation；
- 测试替换任一来源为 PARTIAL、EMPTY、FAILED、超时或冲突值时，run/pipeline
  明确降级为 `REVIEW_REQUIRED`/`BLOCKED`，不得产生零值或 READY Fact/Finding；
- 覆盖错误 kind/operation、未知或重复 node/claim/source、跨 owner、lineage
  重复、expected value 漂移、伪造 supported 元数据、敏感字段和 Pydantic bypass，
  并确认错误不回显原始 Provider payload 或异常。

### 4. Tests and documentation

- 单元测试覆盖四类配方、白名单、矩阵排序/闭包、owner 重绑定、claim/source
  一致性和敏感/额外字段拒绝；
- 集成测试证明四轨道八节点实际并行、两条 lineage 交叉验证、四个 Finding 的
  Evidence 闭包、确定性重放、输入不可变、降级和无零值；
- 独立 adversarial review 覆盖跨 owner、错误 Provider 身份、result tamper、
  100 次并发 deterministic runs、无推荐/订单/LLM/网络副作用；
- 新增 `docs/research-specialist-matrix.md`，并在接受后更新 README、architecture、
  TODO、LOG 和打包配置，明确下一阶段才把矩阵接入更完整的 Portfolio/Advisor
  视图。

## Out of scope（明确不做）

- 同花顺问财 SkillHub/Tushare 网络请求、在线鉴权、真实凭据、缓存、重试、连接池、
  断路器、动态限流和生产 SLA；
- Gemini/LLM、自然语言意图或画像提取、自由 Agent 对话、persona、prompt 或模型
  生成金融事实；
- Portfolio/风险/合规/Recommendation 新规则、目标价、收益承诺、相关性/优化、
  压力测试、可转债、订单、再平衡或交易副作用；
- Profile/Portfolio CRUD、SQLite/PostgreSQL 持久化、FastAPI 新 endpoint、前端页面、
  浏览器新流程和外部 100 用户负载声称；
- 真实 ETF/Fund、宏观、行业或个股数据源适配，以及把合成 fixture 描述为实时行情；
- 修改 Phase 1–15 已接受的状态/证据/事件语义，或运行时导入
  `tradeeye-copilot` / `TradeEye`。

## Reuse boundary

- 复用 `ResearchNodeKind`、`ProviderOperation`、`ResearchNodeSpec`、
  `ResearchPlan`、`ResearchNodeRequest` 和 Phase 7 state machine；新矩阵只是
  配方/验证层，不复制 DAG 状态转换。
- 复用 `FixtureFinancialProvider`、Provider 四态/指纹/预算、
  `normalize_result_to_evidence`、`ResearchNodeResult` 和
  `ResearchRunExecutionResult`；不得直接把 raw JSON 当金融事实。
- 复用 `ResearchClaimSpec`、`validate_claim`、
  `build_research_evidence_pipeline` 与既有 Evidence/Fact/Finding/DecisionTrace
  闭包；四类专员不另造引用格式。
- 只读参考 `tradeeye-copilot`/`TradeEye` 的工具分层和 ETF 分支边界；不复制其
  评分权重、交易逻辑、凭据或运行时依赖。

## Product differentiation

普通“多 Agent 投顾”常用四个名字包装四段不可复核的自然语言。Prism 的四轨道
矩阵把每个专员限制在可检查的 scope、字段、预算和 Provider operation 内，并让
同一 claim 必须由独立 lineage 交叉验证；用户能区分“宏观节点为空”“行业来源
冲突”“个股已验证”“ETF 持仓尚未完成”，而不是看到一段看似一致的聊天结论。
这使速度、覆盖和可信度可以沿 `ResearchRun → Evidence → Fact → Finding`
回放，也是选择 Prism 而非 Agent 数量竞赛产品的理由。

## Acceptance gates

1. 计划在任何实现代码前提交，并确认所有修改位于从 Phase 15 接受提交 `1edb3d9`
   创建的独立 `prism-phase-16` worktree。
2. 合同拒绝缺 kind/operation 映射、未知/重复节点、跨 owner、依赖未闭合、重复
   lineage、claim/source 漂移、无时区/非有限值、额外字段和敏感输入；同一输入
   的矩阵、节点请求、claim 顺序和 ID 稳定。
3. 脱敏 fixture 矩阵实际执行 MACRO、INDUSTRY、STOCK、FUND 四个轨道的八个节点，
   ready nodes 并行；每个 claim 的两条独立 lineage 形成合法 `SUPPORTED`、
   READY pipeline、两条 Evidence 和一个 Fact/Finding。
4. 任一来源 PARTIAL/EMPTY/FAILED/timeout、冲突或非 VERIFIED 时，四态/run/pipeline
   语义保持显式，结果只能 REVIEW/BLOCKED，不产生零值、Fact/Finding、Recommendation
   或 Receipt；失败不泄漏 raw exception/Provider payload。
5. fixture owner 重绑定和跨 owner 隔离通过；伪造 Provider 身份、Pydantic
   `model_construct`、额外字段、敏感文本和结果篡改均安全拒绝；100 次并发固定
   输入得到确定且互不污染的结果。
6. `python -m pytest`（旧测试+Phase 16）、`python -m compileall -q app`、公开
   导入、所有 fixture JSON、wheel package-data、`git diff --check`、无网络/LLM/
   交易/推荐边界扫描通过；Phase 15 API/UI 回归测试持续通过。由于本阶段不改 UI，
   浏览器新交互不作为本阶段门槛，下一阶段再消费矩阵状态。
7. 独立审查确认未复制研究状态机、未把“节点完成”越权升级为建议、未接入真实
   Provider/LLM/持久化；所有问题修复后才标记 `ACCEPTED`，再创建下一阶段 worktree。

## Handoff / stop conditions

- 计划提交后才能实现；实现、审查、修复和最终提交均在本 worktree，不 push。
- 若四类 fixture 不能形成完整证据闭包，保留可审计的 PARTIAL/REVIEW_REQUIRED，
  不放宽 lineage 或填充零值。
- 只有矩阵执行、降级、owner 隔离、确定性并发和边界扫描均有证据，才可进入
  Phase 17；下一阶段须新 worktree 和先行计划，接入矩阵到完整工作台视图或真实
  Provider 之前仍保持离线边界。

## Status

`PLANNED`
