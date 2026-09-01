# MVP Phase 6 Working Plan：Structured Research and Cross-Validation Contract

- Status：`READY`
- Owner：Codex
- Reviewer：Codex + user
- Target worktree：`D:\Github_Storage\prism-phase-6`
- Target branch：`codex/mvp-phase-6-research-cross-validation`
- Source of truth：[Prism.md](../../Prism.md)
- Parent plan：[Prism Foundation](2026-09-01-foundation.md)
- Prerequisite：Phase 5 Allocation Envelope accepted at `437a66a`

## Goal

为后续宏观、行业、个股和基金/ETF 研究节点固定一个离线、结构化、可审计
的最小边界，并实现不依赖 Agent 数量投票的确定性 Cross-Validation。节点
结果必须区分 `COMPLETE`、`PARTIAL`、`EMPTY` 和 `FAILED`；交叉验证必须明确
支持、反对、重复 lineage、口径/期间不一致和无法消解的冲突。

本阶段只建立研究协作契约和纯函数校验器，不取得真实市场数据，不让 LLM
创造金融事实，也不把校验结果直接变成 `Finding`、`Recommendation` 或交易
动作。

## Product rationale

很多“多 Agent 投研”产品把 3 个 Agent 的相同转载当成多数票，用户无法知道
结论是否真的由独立数据支持。Prism 的差异是把每条观察的 provider/source、
lineage、指标、单位和期间固定下来：同一上游记录的重复转载不增加支持度，
口径冲突进入 `UNRESOLVED`，关键数据缺失进入 `INSUFFICIENT`。因此用户能
看到“为什么这个结论可信/不可信，以及哪些输入需要重新核验”，而不是只看
一个 Agent 置信分数。

## Reuse and architecture boundary

- 复用 Phase 1 的 `Evidence`、质量状态、lineage 和冻结 `ContractModel`，
  复用 Phase 2–5 的 owner 隔离、四态降级、Decimal 与稳定 ID 模式；不修改
  上游模型或其测试。
- 参考 `tradeeye-copilot` 的事实白名单/引用解析语义，以及 `TradeEye` 的
  版本化规则和 provider 降级语义；不复制其 Agent 自由对话、荐股权重或
  短周期交易策略。
- 新模块位于 `app/research/`，可被未来结构化 DAG 节点调用；本阶段不创建
  DAG 调度器或跨模块存储。

## In scope（本阶段必须完成）

### 1. Structured research node contracts

在 `app/research/contracts.py` 定义严格冻结模型：

- `ResearchNodeKind`：`MACRO`、`INDUSTRY`、`STOCK`、`FUND`；
- `ResearchObservation`：owner、subject、metric、unit、period、Decimal 值、
  evidence ID、provider/source、lineage ID 和 Evidence 质量状态；只允许
  可确定比较的标量数值，拒绝隐式自由文本事实；
- `ResearchNodeStatus`：`COMPLETE`、`PARTIAL`、`EMPTY`、`FAILED`；
- `ResearchNodeIssue`：安全 issue code/message，不存原始 provider payload、
  凭据或自然语言秘密；
- `ResearchNodeResult`：node/request/owner 闭包、观察、missing fields、
  scope description 和四态不变量。

契约必须拒绝重复 observation/evidence ID、owner 串线、无效质量字段、
`COMPLETE` 携带 issue/missing、`EMPTY` 携带数据、`FAILED` 携带观察等非法
组合。

### 2. Deterministic Cross-Validation

在 `app/research/cross_validation.py` 实现 `validate_claim`：

- `ValidationClaim` 固定 subject、metric、unit、period 和期望 Decimal 值；
- 只比较 `VERIFIED` observation；非 VERIFIED 观察保留在 unresolved issues，
  不得成为支持票；
- 显式 lineage 是去重主键；同 lineage 的重复记录不增加独立来源数，并在
  `duplicate_lineage_evidence_ids` 中可审计；没有 lineage 时只把该 evidence
  自身当作未知来源，不能声称它与别的记录独立；
- 对齐 subject/metric/unit/period 后，输出
  `SUPPORTED`、`CONTRADICTED`、`UNRESOLVED` 或 `INSUFFICIENT`；不匹配的
  观察不能混入投票；
- `SUPPORTED` 至少需要两个不同 lineage 的支持来源且没有独立反对来源；
  所有来源来自同一 lineage 时不得通过；
- 同时存在独立支持与独立反对、同 lineage 内部值冲突、口径/期间不一致或
  非 VERIFIED 数据时输出 `UNRESOLVED`；没有足够独立来源输出 `INSUFFICIENT`；
- confidence 是可复算的 agreement/coverage 比例，不是收益概率或模型自信，
  且使用 Decimal、固定舍入和明确 methodology；
- 输出闭包到 claim、支持/反对 evidence IDs、重复 lineage IDs 和安全 issues，
  不生成 Finding/Recommendation。

### 3. Offline fixture/tests/docs

- 新增纯合成宏观/行业/基金观察 fixture；禁止真实账户、凭据、在线请求和
  未脱敏 provider payload。
- 新增单元/集成测试覆盖四态、lineage 去重、独立支持、冲突、非 VERIFIED、
  指标/单位/期间错配、owner 串线、稳定排序、Decimal 边界、不可变性和无
  推荐字段。
- 新增 `docs/research-cross-validation.md`，描述输入对齐、状态机、置信度
  语义、产品差异和明确非目标。
- README/TODO/LOG 只在复审通过后记录实际状态，不声称已有真实研究节点、
  SkillHub 访问、DAG、UI 或建议生成。

## Out of scope（本阶段明确不做）

- 不接入 Wencai/SkillHub/Tushare、网络、凭据、LLM、Prompt、搜索、实时行情
  或外部报告；
- 不创建/修改 `Fact`、`Finding`、`Recommendation`、`DecisionTrace` 或
  Evidence Contract，不把 `ValidationResult` 变成投资结论；
- 不实现异步 DAG、Orchestrator、重试、缓存、断路器、数据库、迁移、API、
  Web UI、浏览器验收、并发/SLA 或持久化审计回执；
- 不实现宏观/行业/个股/基金的金融分析公式、收益预测、估值、相关性、波动率、
  回撤、流动性、配置优化、交易动作或合规文案；
- 不以 Agent 数量、相同 provider 的转载数量或多数票替代 lineage/source/
  metric/period 对齐；
- 不修改 `Prism.md`、Phase 1–5 源代码/测试、上游仓库或其他阶段 worktree；
- 不 push，不声称比赛接口授权、真实 100 用户并发、3 秒 P95 或 99.9% 可用性。

## Implementation sequence

1. 先提交本计划书并确认 `git diff --check`，状态保持 `READY`。
2. 先写四态和跨来源反例测试，再实现 `app/research` 纯函数与导出接口。
3. 加入合成 fixture、契约文档和少量集成示例；保持 Phase 1–5 文件不变。
4. 运行完整测试、编译、导入、fixture JSON/敏感字段扫描和重复运行稳定性
   检查。
5. 独立复审重点检查：同 lineage 是否被错误计票、同口径/期间是否真的对齐、
   partial/failed 是否被包装为支持、confidence 是否被误读为概率、owner 是否
   串线、输出是否越界成推荐。
6. 复审通过后再把计划标记为 `ACCEPTED`，补 README/TODO/LOG，形成单个本地
   Phase 6 实现提交；下一阶段必须建立新 worktree。

## Acceptance criteria

1. `COMPLETE`、`PARTIAL`、`EMPTY`、`FAILED` 的 node result 都有反例测试；
   非法字段组合被 Pydantic 拒绝。
2. 两个不同 lineage、同 subject/metric/unit/period 且值相等时为 `SUPPORTED`；
   一个 lineage 的重复转载不得通过。
3. 独立来源同时支持与反对时为 `UNRESOLVED`，并列出双方 evidence IDs；
   只有反对来源时为 `CONTRADICTED`，不输出建议。
4. 缺少 VERIFIED 或只有一个独立来源时为 `INSUFFICIENT`，不伪装成支持。
5. 非 VERIFIED、subject/metric/unit/period 错配、同 lineage 内部冲突均有
   可审计 issue，且不会进入支持票。
6. 相同输入顺序变化不改变 validation ID、证据 ID 顺序、状态、confidence 或
   issue 顺序；稳定排序有测试。
7. owner 串线、重复 ID、篡改 claim/value/lineage、深度不可变和未知字段均
   被拒绝。
8. confidence 使用 Decimal 固定舍入，并在文档明确不是收益概率或投资胜率。
9. 输出只包含 claim/observation/evidence 引用和安全方法字段，不包含
   recommendation/order/price/return promise 等字段或措辞。
10. Phase 1–5 原有 103 项测试继续通过；新增测试全部通过。
11. `python -m compileall -q app`、模块导入、`git diff --check`、fixture
    JSON 和敏感字段扫描通过。
12. 最终 worktree 干净，只产生一个本地 Phase 6 实现提交，不 push；复审记录
    明确剩余风险和下一阶段建议。

## Review stop conditions

遇到以下任一情况必须停止并记录，而不是放宽契约：

- 需要修改 Evidence/Recommendation 才能表达校验结果；
- 无法区分同 lineage 重复、独立支持、独立反对和口径错配；
- 只能通过填零、忽略非 VERIFIED 或把单来源包装成支持来通过测试；
- confidence 无法解释为可复算的覆盖/一致比例；
- 需要真实网络、LLM 或 DAG 调度才能完成当前验收；
- 发现 Phase 1–5 owner/状态闭包缺陷，应退回复审而不是旁路。
