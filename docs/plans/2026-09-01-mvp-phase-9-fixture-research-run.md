# Working Plan：MVP Phase 9 Fixture-backed Async Research Run

## Goal

把 Phase 1 的 `FinancialProvider`、Phase 7 的 bounded run state machine 和
Phase 8 可消费的 Evidence/Observation 结构接成一个可执行的异步研究纵切。
先通过注入的 Fixture Provider 证明：同一批根节点并行执行，依赖节点只在
前置节点完成后启动，四态 Provider 结果被安全地映射到四态研究节点结果，
最终得到可回放的 `ResearchRunState`、规范化 `Evidence` 和带 owner/lineage
绑定的 `ResearchObservation`。

这一步让“契约已经存在”变成“离线可运行”；它仍不宣称真实 SkillHub 已接入。

## Context / Constraints

- `Prism.md` 是唯一项目规范；产品纵切仍是“科技基金集中持仓体检”。
- Phase 7 的状态转换是唯一的 run 状态写入入口；执行器不能自行修改节点
  状态或绕过 required/optional/deadline 语义。
- Phase 1 的 `execute_with_budget` 是 Provider 调用边界，必须保留 timeout、
  失败分类、指纹校验和安全错误映射。
- Phase 8 的 `Evidence` 不含 owner 字段，因此执行器必须用同一 node 的
  `ResearchNodeSpec.owner_id` 绑定 Observation，供后续 Evidence/Finding 桥接
  做闭包校验。
- 所有输出保持冻结 Pydantic 契约；不保存原始 Provider payload、异常文本、
  凭据或自然语言 Agent 消息。
- 研究 Observation 当前是标量 Decimal 契约；Provider 返回的非数值字段仍可
  作为规范化 Evidence 保存，但不冒充可交叉验证的 Observation。

## In scope（本阶段必须完成）

### 1. Node request 与执行结果契约

新增最小 `ResearchNodeRequest`（node_id + `ProviderRequest`）和
`ResearchRunExecutionResult`（最终 `ResearchRunState`、Evidence、Observation）。
执行结果必须验证：

- node 请求集合与 plan 节点一一对应且无重复；
- Evidence/Observation ID 唯一，Observation 的 Evidence ID 已注册；
- owner、provider/source、field、unit、period、lineage、时间和质量在
  Observation/Evidence 之间闭合；
- 结果对象冻结、稳定排序、不能携带 Recommendation/订单/秘密形状字段。

### 2. Fixture-backed bounded executor

实现纯边界清晰的 `execute_research_run(...)`：

- 先调用 `start_research_run`，只执行当下 `RUNNING` 的 ready 节点；
- 对同一批 ready 节点使用 `asyncio.gather` 并行调用注入 Provider；
- 每个请求的有效 timeout 不超过 node timeout 和 Provider 原始 timeout，
  不超过 run deadline；调用通过 `execute_with_budget`，不得直接绕过预算包装；
- 以确定性 node_id 顺序把完成结果交回 `record_node_result`，让依赖节点在
  下一轮才启动；run 进入终态后不再写入晚到结果；
- 对 required 节点的不完整结果沿用 Phase 7 的 FAILED 语义；optional 节点
  的 PARTIAL/EMPTY/FAILED 允许最终 PARTIAL，并取消其不可运行的后代；
- Provider/执行异常只转换成安全的 FAILED research node issue，不保留 raw
  exception 或 response。

### 3. Provider -> ResearchNodeResult -> Evidence/Observation

- `SUCCESS` + 至少一个带明确 unit/period 的有限标量 → `COMPLETE`；
- `PARTIAL` → `PARTIAL`，保留缺失字段和静态安全 issue；
- `EMPTY` → `EMPTY`，保留明确 scope；
- `FAILED`、预算超时、无可用标量或非法字段 → `FAILED`，使用
  `SOURCE_UNAVAILABLE`/`INVALID_OBSERVATION` 等安全分类；不得把失败当作 0；
- 规范化沿用 `normalize_result_to_evidence` 的 record/lineage-aware Evidence
  ID；Observation ID 使用 owner/node/evidence 的稳定 hash；值只接受有限
  Decimal 标量，字符串数值可解析，布尔/集合/无单位/无期间的字段不进入
  Observation。

### 4. Fixtures、文档与验收测试

- 新增脱敏的多节点合成 fixture，覆盖 SUCCESS、PARTIAL、EMPTY、FAILED、
  timeout、依赖和 optional degradation；
- 新增单元/集成测试，证明并行执行、依赖门控、owner/请求闭包、四态映射、
  evidence 唯一性、无零值幻觉及状态不可变；
- 新增独立 adversarial review，覆盖伪造 Provider result、晚到结果、跨 owner
  request、未知/重复 node、敏感异常、超时和原始输入不变性；
- 新增 `docs/fixture-research-run.md`，说明运行边界、产品差异化和 Phase 8
  桥接的输入如何获得。

## Out of scope（明确不做）

- 真实同花顺问财 SkillHub/Tushare 网络 adapter、鉴权、缓存、重试、限流或
  任何真实凭据；
- LLM、自然语言画像/意图解析、研究结论生成或自由 Agent 对话；
- 在执行器中自动调用 Cross Validation、Evidence/Finding bridge、风险/合规、
  Allocation 或 Recommendation；本阶段只产出它们所需的结构化输入；
- PostgreSQL/Redis、API、Web/UI、浏览器验收、真实 100 用户并发/3 秒 SLA；
- 修改 Phase 1–8 的既有公共字段语义或上游仓库。

## Reuse boundary

- 复用 `FinancialProvider`、`ProviderRequest/Result`、
  `execute_with_budget` 和 `normalize_result_to_evidence`，不复制 Provider
  协议或自行捕获未经脱敏的异常。
- 复用 Phase 7 `start_research_run`、`record_node_result`、
  `finish_research_run` 的状态/依赖/预算语义；执行器只是调度和映射层。
- 复用 Phase 6 `ResearchNodeResult`、`ResearchObservation` 四态/lineage
  契约，以及 Phase 8 的 Evidence/Finding 闭包方向；不重造引用模型。
- 上游 `tradeeye-copilot` 与 `TradeEye` 仅作只读架构参考，不作为运行时依赖。

## Product differentiation

同类产品常把“并行 Agent”当作卖点，却无法说明一个节点失败后哪些结论仍然
可信。Prism 将并行性限定在可回放的结构化 DAG：每个节点拥有 owner、预算、
依赖和四态结果，用户能看到哪些数据真的到达、哪些只是待复核；之后的
Finding 还可沿 Evidence lineage 钻取。这样产品差异不是 Agent 数量，而是
在速度、个性化和证据完整性之间给出可验证的取舍。

## Acceptance gates

1. Plan commit 在实现代码前完成，并位于从 Phase 8 接受提交新建的独立
   Phase 9 worktree。
2. 两个或以上 ready 根节点实际并行；有依赖的节点不会提前执行，最终状态
   与 Phase 7 required/optional/deadline 规则一致。
3. Fixture 的 SUCCESS/PARTIAL/EMPTY/FAILED/timeout 都映射为正确研究节点
   状态；失败、空结果和缺失字段不产生虚假数值 0。
4. 成功数值字段形成 owner/field/value/unit/period/provider/source/lineage
   闭合的 Evidence + Observation，ID 稳定且输入不被修改。
5. Provider 超时/异常、跨 owner、重复/未知 node、晚到结果和敏感异常均被
   安全处理，输出不含 raw exception、凭据或 Recommendation/订单字段。
6. `python -m pytest`、`python -m compileall -q app`、模块导入、fixture JSON、
   `git diff --check` 和敏感值扫描全部通过，并记录完整测试数。
7. 独立审查确认没有真实网络、LLM、持久化、UI 或 Phase 8 之外的建议生成；
   发现的问题修复后才能标记 `ACCEPTED`。

## Handoff / stop conditions

- 计划提交后才可实现；实现、审查和修复均在本 worktree，最终一个本地 commit，
  不 push。
- 如果 Provider 结果无法无歧义映射为标量 Observation，保留 Evidence 但将
  节点安全降级，不放宽契约或填充零值。
- 只有全部 acceptance gates 有命令/测试证据，才可从接受提交创建下一阶段
  worktree；下一阶段再接 Evidence bridge、风险/合规或 Recommendation。

## Status

`PLANNED`
