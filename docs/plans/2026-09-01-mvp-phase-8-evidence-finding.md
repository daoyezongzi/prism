# Working Plan：MVP Phase 8 Evidence-grounded Fact/Finding Bridge

## Goal

把 Phase 6 的 `CrossValidationResult` 与真实的 `Evidence` 注册表安全地
接入现有 `Fact -> Finding` 领域契约，形成第一个可以被后续合规闸门和
Recommendation 消费的、可审计的研究结论闭包。

本阶段只做确定性桥接，不生成投资建议，不把研究文本或 LLM 输出当成
金融事实。成功的纵切应能证明：只有通过独立来源交叉验证、证据质量和
口径一致性检查的 claim 才能变成 `VERIFIED Fact`，并且 Finding 只能引用
该 Fact。

## Context / Constraints

- `Prism.md` 是唯一项目规范；产品第一条纵切仍是“科技基金集中持仓体检”。
- 上游 `tradeeye-copilot` 与 `TradeEye` 只读；本阶段不修改、运行时导入或复制
  上游代码。
- Phase 1 的 `Evidence`、`Fact`、`Finding` 和 `DecisionTrace` 是现有事实边界；
  Phase 6 的 `CrossValidationResult` 是唯一允许的研究验证输入。
- 所有跨模块对象保持 Pydantic 冻结契约，输入和输出不可变，禁止原始异常、
  凭据、原始响应或未脱敏诊断进入结果。
- 缺失、冲突、过期或非 VERIFIED 证据必须显式降级，不能转换成零值或确定事实。
- 本阶段在无网络、无凭据、无 LLM 的 synthetic fixture 上完成；不能宣称已
  接入同花顺问财 SkillHub。

## In scope（本阶段必须完成）

### 1. 证据注册表闭包

新增纯函数/契约（命名可按现有模块风格调整）接受：

- 一个 `CrossValidationResult`；
- 一个不可变的 `Evidence` 集合（以 `evidence_id` 唯一索引）；
- 用于生成 Finding 的最小结构化元数据。

桥接必须拒绝未知、重复或未被交叉验证结果声明的 evidence ID。结果中应
明确区分 `READY`、`REVIEW_REQUIRED` 和 `BLOCKED`，并保留安全、可读的 issue
代码；不得返回“看起来成功但没有 Fact”的半隐式状态。

### 2. `CrossValidationResult -> Fact`

仅当以下条件全部满足时创建 `Fact(status=VERIFIED)`：

- validation status 为 `SUPPORTED`；
- 至少两条独立 lineage 已由 Phase 6 验证；
- supporting evidence ID 全部存在、唯一且质量为 `VERIFIED`；
- 每条证据的 `value`、`subject/metric`（由 `field`/metadata 映射）、`unit`、
  `period` 与 claim 口径一致；
- 没有 contradiction、unresolved、duplicate-lineage 或 non-verified evidence；
- owner、claim、subject 和 metric 的闭包没有跨请求/跨用户混入。

Fact ID 必须由稳定输入确定性生成（至少包含 owner、claim、metric、period），
不能使用随机 UUID。相同有效输入重复运行应得到等价 Fact。

### 3. `Fact -> Finding`

只允许基于刚刚生成且已验证的 Fact 生成一个结构化 Finding：

- `fact_ids` 必须闭包到已存在的 Fact；
- Finding 的 confidence/methodology 来自验证结果和显式调用参数，不能凭空
  添加概率或收益承诺；
- statement 是调用方提供的非空解释文本，桥接层不得把它当成证据值；
- 允许 `INFO/WARNING/CRITICAL`，但不产生 Recommendation 或交易动作。

### 4. 降级与拒绝语义

- `SUPPORTED` 但证据缺失、口径不一致、证据非 VERIFIED 或重复 lineage：
  `BLOCKED`，不产出 VERIFIED Fact/Finding；
- `CONTRADICTED`、`UNRESOLVED`、`INSUFFICIENT` 或研究节点 PARTIAL/FAILED 的
  结论：`REVIEW_REQUIRED`，只返回安全问题和可供 UI 展示的候选状态，不得伪装
  成已验证事实；
- 输入违反领域契约、owner 不一致、出现敏感字段或未知 ID：`BLOCKED`，错误
  消息不得泄露原始 payload。

### 5. 文档、Fixture 与测试

- 新增 `docs/evidence-finding-bridge.md`，说明状态机、ID 算法、口径匹配、
  产品差异化和后续 Recommendation 闭包边界；
- 新增脱敏 synthetic fixture，覆盖两条不同 lineage 的支持证据、缺证据、
  非 VERIFIED、period/unit/value 冲突、反对/未解决/证据不足及跨 owner；
- 新增单元和集成测试，且所有 Phase 1–7 测试必须继续通过；
- 增加独立 adversarial review：重复调用稳定性、DecisionTrace 闭包、输入
  不可变性、伪造 SUPPORTED、未知 evidence、敏感文本和跨 owner 污染。

## Out of scope（明确不做）

- 真实同花顺问财 SkillHub/Tushare 网络请求、鉴权、重试、缓存、限流或连接池；
- Provider/Agent 的异步执行器、研究 DAG 调度、LLM 解析或自然语言对话；
- 修改 `Evidence`/`Fact`/`Finding` 的既有公共字段语义，或加入数据库/迁移；
- Recommendation、AllocationRange、交易动作、收益目标、回测或订单执行；
- 风险/合规规则本身（下一阶段单独设计独立 gate）；
- FastAPI、React/UI、浏览器验收、并发/3 秒 SLA 和生产可用性声明；
- 任何秘密、真实个人持仓、真实凭据或上游仓库改动。

## Reuse boundary

- 复用 `app.contracts.evidence` 的 `Evidence`、`Fact`、`Finding`、`DecisionTrace`
  和质量/状态枚举，不复制一套弱引用模型。
- 复用 `app.research.contracts` 与 `cross_validation.py` 已验证的 lineage、
  scope、confidence 和四态语义；桥接层只做闭包和领域映射。
- 复用现有 Pydantic `ContractModel`、稳定 ID/Decimal 习惯和 fixture 测试模式。
- 不把上游代码当成运行时依赖；若需借鉴，只在文档中记录来源和理由。

## Product differentiation

同类产品通常只展示“多个 Agent 的结论”或一个来源 URL。Prism 的可见差异是：
每条可用研究判断都必须显示 `Finding -> Fact -> Evidence` 的闭包，证据来自
不同 lineage 且口径一致；一旦缺失、冲突、过期或跨用户混入，系统明确显示
“待复核/阻断”，而不是用流畅文案掩盖不确定性。这样用户能知道结论为何
成立、何时失效，以及系统为什么没有给出建议。

## Acceptance gates

1. Plan commit 在任何实现代码前完成，并位于独立 Phase 8 worktree。
2. 正常两 lineage `SUPPORTED` fixture 生成稳定 `VERIFIED Fact` 和 Finding，
   构造 `DecisionTrace` 成功，所有引用闭包可追溯。
3. 每一种缺失、冲突、非 VERIFIED、period/unit/value mismatch、未知 ID、
   owner mismatch 均得到预期 `REVIEW_REQUIRED`/`BLOCKED`，且没有 VERIFIED Fact。
4. 生成的 Fact/Finding 无随机 ID、无重复 evidence/fact ID，调用不修改输入。
5. 不允许由 `CONTRADICTED`、`UNRESOLVED`、`INSUFFICIENT` 或单一 lineage
   伪造可行动事实；敏感文本不会出现在安全 issue 或序列化结果中。
6. `python -m pytest`、`python -m compileall -q app`、模块导入、fixture JSON
   解析和 `git diff --check` 全部通过；完整测试数量和命令记录在 `LOG.md`。
7. 独立审查确认没有引入 Recommendation、网络、凭据、持久化或 UI；审查发现
   必须修复后才能标记 ACCEPTED。

## Handoff / stop conditions

- 计划提交后才可实现；实现、审查和修复均留在本 worktree，并提交一个最终
  本地 commit，不 push。
- 若 Evidence/Fact 既有契约不足以表达所需状态，先记录阻塞和最小 ADR，
  不得通过弱化校验绕过；必要的契约扩展须另列审查项。
- 只有所有 acceptance gates 有命令或测试证据时，才可进入 Phase 9；下一阶段
  必须从本阶段接受的 commit 新建另一个 worktree。

## Status

`PLANNED`
