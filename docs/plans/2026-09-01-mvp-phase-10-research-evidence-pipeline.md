# Working Plan：MVP Phase 10 Research-to-Evidence Pipeline

## Goal

把 Phase 9 的异步执行结果真正交给 Phase 6 的 lineage-aware Cross Validation
和 Phase 8 的 Evidence/Finding bridge，形成一个可回放、可审计的研究结果
集合。该集合只把**完整完成的 run**中、拥有至少两个独立 lineage 且口径
一致的 claim 变成 `VERIFIED Fact -> Finding`；任何 run 降级、冲突、缺失或
不闭合都明确保留为待复核/阻断状态。

这是从“节点能跑”到“研究结论可消费”的桥接阶段，仍不生成投资建议。

## Context / Constraints

- `Prism.md` 是唯一项目规范；旗舰场景仍为科技基金集中持仓体检。
- Phase 6 `validate_claim` 是唯一交叉验证入口；Phase 8
  `bridge_cross_validation` 是唯一 Fact/Finding 注册入口。
- Phase 9 `ResearchRunExecutionResult` 的 state、Evidence、Observation 是本阶段
  唯一运行输入；不重新读取 Provider 或自行推断数据。
- `PARTIAL`、`FAILED`、`EMPTY` run 即使某一 claim 看似有两条支持，也必须显示
  run 降级并阻止该 claim 进入 READY，避免局部成功掩盖全局缺失。
- 所有输出为冻结 Pydantic 契约；不复制 raw Provider payload、异常、凭据或
  LLM 文本，不执行网络或持久化。

## In scope（本阶段必须完成）

### 1. Claim specification and pipeline result

新增最小的 `ResearchClaimSpec`（`ValidationClaim` + finding kind/severity/
statement）以及 `ResearchEvidencePipelineResult`：

- pipeline status 为 `READY`、`REVIEW_REQUIRED` 或 `BLOCKED`；
- 保留每个 claim 的 `CrossValidationResult` 和 bridge 结果，供 UI/后续合规
  层解释支持、冲突、缺失和拒绝原因；
- `DecisionTrace` 只包含执行结果里的 Evidence，以及 READY bridge 产生的
  Fact/Finding，不产生 Recommendation；
- claim ID 唯一、owner 必须与 execution owner 相同，结果 ID 和集合排序稳定。

### 2. Run-aware cross validation

实现 `build_research_evidence_pipeline(...)`（并提供语义清晰的别名）：

- 聚合 execution 的全部 Observation，按 claim 调用 Phase 6 validation；
- 仅当 run 为 `COMPLETED` 时允许 `SUPPORTED` 继续进入 Phase 8 bridge；
- `PARTIAL`/`FAILED`/含 EMPTY 节点的 run 将支持结果安全降级为显式待复核，
  不伪造确定事实；原始支持/未解决 evidence ID 仍可供审查；
- `CONTRADICTED`、`UNRESOLVED`、`INSUFFICIENT` 直接形成 REVIEW_REQUIRED
  bridge；未知 claim、跨 owner、重复 ID、证据闭包异常形成 BLOCKED；
- 每个 READY bridge 必须放入 DecisionTrace 并通过现有闭包校验；任何一个
  BLOCKED claim 都不能让 pipeline 状态变成 READY。

### 3. Fixture and adversarial verification

- 新增至少两条不同 lineage 对同一标量 claim 的完整 fixture，证明
  `ResearchRunExecutionResult -> CrossValidationResult -> Fact -> Finding -> Evidence`
  闭环；
- 覆盖单 lineage、冲突值、非 VERIFIED、run partial/failed、缺 evidence、
  owner mismatch、重复 claim、敏感 finding 文本和伪造 supported metadata；
- 验证同一输入顺序不同的确定性、READY trace 可构造、review/blocked 不泄漏
  Fact/Finding、输入不可变以及无 Recommendation/订单/收益承诺字段；
- 新增 `docs/research-evidence-pipeline.md`，记录状态语义、降级策略、产品
  差异化和后续风险/合规消费边界。

## Out of scope（明确不做）

- 真实 SkillHub/Tushare、鉴权、重试、缓存、限流、数据库和 API；
- LLM 解析、自由 Agent 对话、自然语言 Finding 自动生成；
- 风险/合规规则、Recommendation、配置动作、回测或交易执行；
- 修改 Phase 6/8 公共模型字段语义或绕过其校验；
- Web/UI、浏览器验收、100 用户并发/3 秒 SLA 和生产可用性声明；
- 上游 `tradeeye-copilot` / `TradeEye` 运行时导入或修改。

## Reuse boundary

- 复用 Phase 9 `ResearchRunExecutionResult` 的 normalized Evidence/Observation，
  不重新调用 Provider 或从字符串重建金融数值。
- 复用 Phase 6 的 `validate_claim`、`CrossValidationResult`、四态和 lineage
  语义；run 降级只增加安全 issue，不重写验证算法。
- 复用 Phase 8 `bridge_cross_validation`、`Fact`、`Finding`、`DecisionTrace`，
  不建立第二套引用或 Recommendation 模型。
- 上游仓库继续只读参考，不作为依赖。

## Product differentiation

同类产品通常把“研究完成”与“结论可信”视为同一件事。Prism 将两者分开：
用户可以看到某个节点成功，但如果整体 run 有空结果、失败或来源不独立，
该判断仍标为待复核；只有完整的独立证据闭包才进入 Fact/Finding。这样“为
什么现在没有建议”本身也是可解释、可审计的产品能力。

## Acceptance gates

1. Plan commit 在实现代码前完成，并位于从 Phase 9 接受提交新建的独立
   Phase 10 worktree。
2. 完整 run 的两条独立 lineage 支持 fixture 生成稳定 READY pipeline、
   VERIFIED Fact/Finding 和可构造 DecisionTrace。
3. PARTIAL/FAILED/EMPTY、冲突、非 VERIFIED、单 lineage、缺/未知 Evidence、
   owner mismatch 和伪造 supported 均不产生 READY Fact/Finding，并返回预期
   REVIEW_REQUIRED/BLOCKED。
4. Claim、validation、bridge、trace 的 ID/排序确定性成立，所有输入不可变；
   每个 ready Finding 只能引用同一 pipeline 产生的 Fact。
5. 输出不含 raw exception、凭据、Recommendation/订单/收益承诺或未脱敏 issue；
   既有 Evidence/Finding 公共契约与 Phase 1–9 测试持续通过。
6. `python -m pytest`、`python -m compileall -q app`、模块导入、fixture JSON、
   `git diff --check` 和敏感值扫描全部通过并写入 `LOG.md`。
7. 独立审查确认本阶段没有网络、LLM、持久化、UI、风险/合规或建议生成；问题
   修复后才能标记 `ACCEPTED`。

## Handoff / stop conditions

- 计划提交后才可实现；最终在本 worktree 留一个本地实现 commit，不 push。
- 如 run 降级与 claim 支持语义冲突，宁可 REVIEW_REQUIRED，不得放宽为 READY。
- 只有全部验收证据齐全，下一阶段才可从接受提交创建新 worktree，接独立
  风险/合规 gate 和 Recommendation。

## Status

`ACCEPTED`
