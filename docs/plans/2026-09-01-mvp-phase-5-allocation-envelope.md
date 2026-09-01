# MVP Phase 5 Working Plan：Profile-conditioned Allocation Envelope

- Status：`ACCEPTED`
- Owner：Codex
- Reviewer：Codex + user
- Target worktree：`D:\Github_Storage\prism-phase-5`
- Target branch：`codex/mvp-phase-5-minimal-adjustment`
- Source of truth：[Prism.md](../../Prism.md)
- Parent plan：[Prism Foundation](2026-09-01-foundation.md)
- Prerequisite：Phase 4 Concentration/Risk Budget accepted at `c1d516a`

## Goal

基于已确认的 `RiskProfile`、Phase 3 `ExposureResult`、Phase 4
`ConcentrationResult` 和 `RiskBudgetAssessment`，生成一个可复核的
“调整边界（allocation envelope）”：对每个资产、行业、科技聚合和未分类
聚合给出当前权重、画像条件上限、最小超限幅度，以及一个不声称已经执行
再平衡的目标区间。

本阶段输出的是确定性约束结果和逐约束的前后影响，不是交易指令、收益预测
或最终 `Recommendation`。只有在后续 Evidence/Finding/Compliance/Composer
阶段完成后，才允许把这些边界转译为面向用户的行动建议。

## Product rationale

同一份持仓和同一份市场事实不应对所有人返回同一组仓位边界。保守、均衡、
进取画像使用不同的、版本化的 Phase 4 风险预算，因此同一暴露会产生不同的
允许上限、最小调整幅度和人工复核状态。每一行都保留画像版本、预算版本、
集中度组和原始暴露报告 ID，用户可以回答“为什么我的边界与另一个用户不
同”，而不是得到一个无法解释的 AI 分数。

## Reuse and architecture boundary

- 复用 Phase 2/3/4 的冻结 Pydantic 契约和 `Decimal` 算术；不跨仓库运行时
  导入。
- 规则组织沿用 `TradeEye` 版本化、未知字段拒绝和稳定 ID 的可复用模式，
  但不复制其荐股权重、五槽位或交易状态机。
- 新模块位于 `app/allocation/`，只消费上游输出；不改写
  `app/contracts/evidence.py`、Provider、Profile、Portfolio、Exposure 或
  Risk 的既有模型与测试。
- 结果仍是模块化单体内的纯函数边界，未来可由结构化 DAG 节点调用；本阶段
  不创建 Orchestrator、HTTP route、数据库表或 UI。

## In scope（本阶段必须完成）

### 1. Immutable allocation-envelope contracts

在 `app/allocation/contracts.py` 定义严格、冻结、`extra=forbid` 的模型：

- `AllocationBandDimension`：`ASSET`、`SECTOR`、`TECHNOLOGY`、
  `UNCLASSIFIED`；
- `AllocationBandDisposition`：`WITHIN_LIMIT`、`OVER_LIMIT`、`UNRESOLVED`，
  表示约束状态而不是交易动作；
- `AllocationBand`：owner、维度、稳定 target ID/label、当前权重、画像条件
  允许上限、目标最小/最大权重、最小削减幅度、约束状态和触发的 budget
  breach IDs；
- `ConstraintImpact`：单条约束的 before/after 权重、百分点变化和对应 band；
- `AllocationEnvelope`：profile/budget/concentration/exposure 闭包、按稳定
  顺序排列的 bands 与逐约束 impacts、状态和固定失效条件；
- `AllocationIssue` 与 `AllocationResult`：`READY`、`REVIEW_REQUIRED`、
  `BLOCKED` 三态，明确 partial/failed 不能伪装成可用结果。

契约校验至少保证：

- owner、profile、budget、concentration 和 exposure 身份一致；
- 百分比在 0–100，目标下限不超过上限，最小削减等于
  `max(current - allowed_max, 0)`；
- `WITHIN_LIMIT` 的目标区间固定为当前权重，`OVER_LIMIT` 的目标上限不超过
  预算上限，`UNRESOLVED` 不得声称已通过；
- breach ID 唯一且必须来自对应的 Phase 4 assessment；band/impact ID 唯一；
- 不允许出现 `recommendation`、交易数量、价格、收益承诺或自由文本结论字段。

### 2. Deterministic envelope calculation

在 `app/allocation/envelope.py` 实现 `build_allocation_envelope`：

- 资产 band：每个 Phase 4 asset group 使用 `max_single_asset_weight_pct`；
- 已知行业 band：每个非 `UNCLASSIFIED` sector group 使用
  `max_sector_weight_pct`；
- 科技 band：使用 `technology_weight_pct` 与
  `max_technology_weight_pct`；
- 未分类 band：使用 `unclassified_weight_pct` 与
  `max_unclassified_weight_pct`；
- band 按维度顺序、市场值降序、稳定 ID 排序；同值不能因输入顺序变化；
- 完整且未超限时生成 `WITHIN_LIMIT` 区间；完整但超限时生成 `OVER_LIMIT` 区间，目标
  上限为固定预算，最小削减明确为超限百分点；
- 上游暴露/集中度或预算为 partial 时，保留可计算的数值但把所有 band
  标记为 `UNRESOLVED`，结果不得成为 `READY`；
- 上游失败或没有 concentration report 时只返回 `BLOCKED` 与安全 issue，
  不生成虚构的零值 band；
- 逐约束 `ConstraintImpact` 只比较“当前权重”和“该约束的预算上限”，不
  进行再分配、不把不同维度的削减相加成虚假的组合收益；文档必须明确这
  是约束边界场景，不是完整投资组合回测。

### 3. Profile difference and invalidation semantics

- 计划必须保留 `profile_id`、`profile_version`、`risk_level`、`budget_id`、
  `concentration_report_id` 和 `exposure_report_id`；
- 固定失效条件至少包括：风险画像版本变化、持仓/基金成分快照变化、穿透
  覆盖率或基准币种变化；
- 相同 concentration 输入分别使用 conservative/balanced/growth profile
  时，输出上限或 disposition/状态必须能够被测试证明不同；
- 失效条件是审计元数据，不是建议文案，也不绕过 Evidence Contract。

### 4. Offline fixture/tests/docs

- 新增纯合成 allocation fixture；禁止真实账户、凭据、在线数据和私人持仓。
- 新增单元与集成测试，覆盖状态传播、边界、排序、Decimal、profile 差异、
  owner 串线、篡改拒绝、不可变性和无推荐字段。
- 新增 `docs/allocation-envelope.md`，说明算法、舍入、语义边界、产品差异
  和明确非目标。
- README/TODO/LOG 只记录实际完成度，不声称已有最终推荐、真实数据源或 UI。

## Out of scope（本阶段明确不做）

- 不创建或修改 `Recommendation`、`Finding`、`Fact`、`Evidence`、
  `DecisionTrace`，不生成可直接执行的买卖建议；
- 不做组合优化、风险平价、均值方差、相关性、波动率、VaR、回撤实现、
  流动性、税费、手续费、滑点、FX、价格/数量/交易 lot 或现金再投资；
- 不把行业/科技/未分类的独立约束影响合并成“组合预计收益”或保证改善，
  不在没有收益序列时发明收益或风险概率；
- 不接入 Wencai/SkillHub/Tushare、LLM、网络、凭据、缓存、数据库、迁移、
  FastAPI、异步 DAG、浏览器或 Web UI；
- 不修改 `Prism.md`、Phase 1–4 的源代码/测试/契约，不修改上游仓库；
- 不声称满足真实 100 用户并发、3 秒 P95、99.9% 可用性或比赛接口授权；
- 不 push，不删除或重写其他阶段 worktree 的分支。

## Implementation sequence

1. 先提交本计划书，确认 `git diff --check`，计划状态为 `READY`。
2. 设计并测试不变量，再实现 `app/allocation` 最小纯函数和导出接口。
3. 添加合成 fixture、单元/集成测试和契约文档；不碰上游阶段文件。
4. 执行完整测试、编译、导入、fixture 敏感字段扫描和确定性重复运行。
5. 由独立复审检查：状态是否泄漏、profile 是否实质影响输出、是否误称为
   推荐、是否存在 owner 串线、重复/不稳定 ID、舍入或范围漏洞。
6. 只有复审通过后，才把本计划标记为 `ACCEPTED`，补齐 README/TODO/LOG，
   形成一个本地实现提交；下一阶段必须再建新 worktree。

## Acceptance criteria

1. 完整、无 breach 的 exposure 生成 `READY` envelope，所有 band 为
   `WITHIN_LIMIT`，
   impacts 为零变化。
2. 单资产/行业/科技/未分类各有超限反例，均生成准确的上限和最小削减，
   且状态不是 `READY`。
3. `PARTIAL` concentration 的数值可以审阅但结果为 `REVIEW_REQUIRED`，
   所有 band 为 `UNRESOLVED`，不得伪装通过。
4. `FAILED` exposure 或缺失 report 只生成 `BLOCKED`，不带 envelope、band
   或零值替代物。
5. 相同 exposure 对 conservative、balanced、growth 生成可观察的不同上限
   或 disposition/状态，并能沿 profile/budget ID 解释差异。
6. 输入顺序变化不改变 band、impact 或 plan ID；稳定 tie-break 有测试。
7. 目标区间、百分比、最小削减和 impact 的 Decimal 边界有测试，无浮点漂移。
8. owner/profile/budget/concentration/exposure 串线和篡改均被拒绝；模型深度
   不可变且未知字段被拒绝。
9. breach 引用只能来自当前 assessment；重复 band/impact/breach ID 被拒绝。
10. 固定失效条件非空且明确包含画像、快照、穿透覆盖/基准币种变化。
11. 输出模型和文档不包含 recommendation/action instruction、价格、数量、
    收益承诺或“已完成再平衡”字段/措辞。
12. Phase 1–4 原有 92 项测试继续通过；新增测试全部通过。
13. `python -m compileall -q app`、模块导入、`git diff --check`、fixture
    JSON 与敏感字段扫描均通过。
14. 最终 worktree 干净，只产生一个本地 Phase 5 实现提交，不 push；复审记录
    明确剩余风险和下一阶段建议。

## Review stop conditions

遇到以下任一情况必须停止实现并记录，而不是放宽契约：

- 需要修改 Evidence/Recommendation 或依赖真实 Provider 才能完成；
- 无法在不重复计算的前提下解释跨维度 impact，或必须把它包装成收益/风险
  预测；
- partial/failed 只能通过填零、丢弃残余或降级成 HOLD 才能通过；
- 不同 profile 的输出没有可验证的预算差异；
- 发现 Phase 4 owner/状态闭包存在缺陷，应退回复审而不是在本阶段旁路。
