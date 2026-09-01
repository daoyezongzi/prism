# Working Plan：MVP Phase 24 研究场景与不确定性可见化

## Goal

把 `Prism.md` 的 Demo D（Agent/来源分歧）和 Demo E（Provider 数据异常）从“代码与
测试中存在”推进到 Research Tracks 工作台可直接回放、可解释展示的边界。用户可以
明确选择一个脱敏、固定的研究场景，看到四类研究轨道、来源分歧或数据退化的实际
状态，以及哪些 Evidence 仍可见、哪些 Fact/Finding 被阻止升级。这样 Prism 的核心
差异化——拒绝把不确定性包装成确定答案——在产品界面上可验证，而不是只靠 README
描述。

本阶段只扩展离线 fixture-first 研究场景选择与展示；不把场景选择伪装成实时市场
数据、自然语言 Agent 或投资建议。

## Context / constraints

- Phase 23 接受提交为 `063111c`；本阶段必须在全新的
  `D:\Github_Storage\prism-phase-24` worktree 完成，并先提交本计划。
- `Prism.md`、Phase 6–10 的四态 Provider/Research/Cross-Validation/Evidence
  pipeline、Phase 16 的四轨道矩阵和 Phase 17 的 Research Tracks API/UI 是真源；不
  复制研究状态机、交叉验证或 Evidence/Finding bridge。
- 场景是合成、版本化、确定性的本地演示输入。所有节点仍走既有
  `FixtureFinancialProvider`、bounded executor、pipeline 和 owner 隔离；不修改上游
  `tradeeye-copilot`/`TradeEye`。
- 继续保持结构化 contract、timezone、敏感字段拒绝、稳定重放和“研究状态不等于
  Recommendation/Decision Receipt”的边界。

## In scope（本阶段必须完成）

### 1. Versioned research scenario contract and catalog

- 增加严格的 `ResearchScenarioId`，至少覆盖：
  `BASELINE_READY`（两条来源一致）、`SOURCE_DISAGREEMENT`（独立来源数值冲突）、
  `SOURCE_PARTIAL`（一个来源声明缺少必需字段）、`SOURCE_EMPTY`（一个来源在声明
  范围内无结果）和 `SOURCE_FAILED`（一个来源安全失败）。
- 通过 owner-safe 的矩阵模板响应公开稳定的场景 ID、短标签和安全说明；不公开
  Provider 请求参数、fixture 原文、凭据或内部异常。研究请求带场景 ID，缺省值保持
  现有基线行为，并在响应中回显经校验的场景元数据。
- 场景目录与响应排序确定、无重复；场景选择不改变矩阵拓扑、claim 定义、预算或
  owner 闭包。

### 2. Deterministic fixture overlays through existing pipeline

- 在既有 fixture provider 外包一层只读、确定性的 scenario overlay：只对声明的
  一个来源改变 Provider 四态/数值，所有结果重新通过 `ProviderResult` 与请求契约
  校验。
- `SOURCE_DISAGREEMENT` 必须产生完整 run 但 `UNRESOLVED` cross-validation 与
  `REVIEW_REQUIRED` pipeline；不得生成 Fact/Finding 或 Recommendation。
- `SOURCE_PARTIAL`、`SOURCE_EMPTY`、`SOURCE_FAILED` 必须分别保留 PARTIAL/EMPTY/
  FAILED 的节点语义、run 降级和安全 pipeline issue；不可用零值替代缺失数据，
  不可把失败转换成 EMPTY。
- 基线场景继续产生原有 8 节点、4 条验证、4 个 Fact/Finding 的 READY 闭包；所有
  场景均不写 DecisionEventStore。

### 3. Research Tracks scenario workbench

- 在 Research Tracks 操作区增加场景选择器，选项从模板 API 加载；切换 owner、模板
  失败、场景变化或异步竞态时清空旧 run/状态，不能把上一个 owner/场景的结果写回。
- READY 场景保持 Finding → Fact → Evidence 展示；非 READY 场景同时显示四轨道节点
  状态、validation 状态/独立 lineage 数、pipeline/run issue，以及“可见但未升级
  为 Fact”的安全 Evidence。分歧场景必须能看见支持/反对证据的来源和值；退化场景
  必须能看见缺失/失败原因，而不是空白或笼统成功。
- 所有动态内容继续使用 `textContent`/节点 API 和同源 fetch；页面明确标注场景为
  synthetic/offline replay，研究 READY 不代表可交易建议。

### 4. Tests, documentation and review evidence

- 新增 API/服务集成测试覆盖五种场景、稳定重放、场景/owner/extra/sensitive/naive
  输入拒绝、四态映射、分歧证据闭合、非 READY 无 Fact/Finding、无存储副作用和旧
  Advisor 回归。
- 静态边界测试确认场景目录/响应不泄露 Provider 原文或敏感字段，无外链、LLM/
  Gemini、自然语言、订单/交易、Recommendation 旁路或 HTML 注入。
- 真实本地浏览器验证：选择 READY→展开证据；选择 DISAGREEMENT→看到支持/反对
  来源且显示待复核；选择 PARTIAL/EMPTY/FAILED→看到对应降级状态且不出现 Fact；
  切换 owner 后全部清空，浏览器错误日志为空。
- 新增研究场景契约文档，更新 README/TODO/LOG 与本计划的独立审查/验收记录。

## Out of scope（明确不做）

- 真实同花顺问财 SkillHub/Tushare/网络 Provider、在线鉴权、凭据、重试/缓存/断路器
  或生产限流；场景 overlay 不代表真实数据质量或市场准确率。
- 自然语言研究问题、LLM/Gemini、多 Agent 自由对话、模型生成结论或自动场景推断。
- 新金融公式、Portfolio/Risk/Compliance/Recommendation/Receipt 规则；研究结果不
  进入 Advisor 决策事件、不改变现有 HOLD/REDUCE 链。
- Portfolio/Profile CRUD、研究历史/后台队列、推送、认证、跨会话持久化、真实 100
  用户/3 秒/99.9% SLA 声明。
- 修改上游仓库、重写历史或 push。

## Reuse boundary

- 复用 `ResearchSpecialistMatrix`/`ResearchSpecialistMatrixRequest`、既有四轨道
  manifest、`FixtureFinancialProvider`、`execute_research_run`、四态映射、
  `build_research_evidence_pipeline` 和 `ResearchMatrixResponse` 的闭包校验；overlay
  只负责可验证的输入变体。
- 复用 Phase 17 的 owner dependency、错误映射、静态 workbench 与异步 sequence
  保护；复用 Phase 21 的固定回放/安全扫描方法，不另建评测或负载体系。
- 复用 Phase 23 的文档/审查格式与无 push、独立 worktree 交接规则。

## Product differentiation

普通聊天式产品往往只给一个“综合观点”，用户看不见来源是否冲突，也分不清“没有
数据”和“数据为零”。Prism 让用户主动选择同一任务的可回放场景，并沿着
`source/lineage → validation → pipeline status → Evidence` 查看为什么结论被接受、
待复核或阻断；即使在退化场景仍展示可审计的边界证据，但绝不伪造完整事实。这种对
不确定性的可见与可拒答，是用户选择 Prism 而不是另一个泛化投顾聊天框的直接理由。

## Acceptance gates

1. 本计划先于任何实现提交；所有代码/文档改动只发生在 Phase 24 worktree，基于
   `063111c`。
2. 场景 contract/catalog 严格 extra-forbid、owner/time/sensitive 校验，排序稳定；
   旧请求不带场景 ID 仍得到 BASELINE_READY，未知场景安全拒绝。
3. 五种场景的 provider/result/run/pipeline 状态与既有四态不变量一致：基线 READY；
   分歧 REVIEW_REQUIRED 且 validation 为 UNRESOLVED；partial/empty/failed 显式
   降级且无 Fact/Finding；任何场景不产生 Recommendation 或 DecisionEvent。
4. API 重放结果稳定、跨 owner 隔离；可见 Evidence 的 source/lineage/value/period
   与响应闭合，不泄露原始 fixture、请求参数、敏感字段或 raw exception。
5. 浏览器完成五场景选择与展示、owner 清理和 Advisor HOLD/REDUCE 回归；无浏览器
   错误、HTML sink 或外网调用。
6. Phase-specific tests、全量回归、compile/import、node/static、eval replay、
   load baseline、wheel/package-data 和 `git diff --check` 通过；独立审查后修复
   问题，再将本计划标记 `ACCEPTED`，随后才创建 Phase 25 worktree。

## Handoff / stop conditions

- 若某个 overlay 无法通过既有 Provider/Research 契约，必须保留安全失败并停止该
  场景，不降低校验标准或伪造 READY。
- 非 READY 场景只能显示待复核/阻断与未升级 Evidence；不得为了演示而补零、补 Fact
  或生成建议。
- 真实 SkillHub、在线鉴权和生产 SLA 仍是外部输入，不因本阶段的离线回放而宣称完成。
- Phase 25 只能从 Phase 24 接受提交创建新 worktree，并先提交下一阶段计划书。

## Status

`PLANNED`
