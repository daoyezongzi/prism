# Working Plan：MVP Phase 11 Independent Risk and Compliance Gates

## Goal

在 Phase 10 的 run-aware Research-to-Evidence pipeline 之后增加独立的风险与
合规闸门。闸门只判断一份候选研究结论是否具备进入下一阶段
Recommendation 组装的资格，不创建 Recommendation、不决定买卖动作，也不把
待复核数据包装成可执行意见。

本阶段完成后，系统能明确回答两件事：

1. 当前用户画像、持仓风险预算、配置约束和研究证据是否闭合且可消费；
2. 候选说明是否满足最小风险披露、证据引用和禁止承诺语义规则。

## Context / Constraints

- `Prism.md` 是唯一项目规范；旗舰纵切仍是“科技基金集中持仓体检”。
- Phase 10 的 `ResearchEvidencePipelineResult` 是研究输入唯一来源；只有
  `READY` 的完整 run 才能通过证据前置检查。
- Phase 4 的 `RiskBudgetAssessment` 与 Phase 5 的 `AllocationResult` 是风险
  约束唯一来源；不重新计算集中度、不优化仓位、不推断收益。
- 所有跨模块对象保持冻结 Pydantic 契约；闸门输出只保存稳定 ID、状态、静态
  安全问题和计数/引用集合，不复制 raw provider payload、异常、凭据或候选
  原文。
- 合规检查采用可测试的确定性规则；LLM 只能在未来阶段生成候选草稿，不能
  绕过本阶段规则。

## In scope（本阶段必须完成）

### 1. Risk gate

新增独立 `evaluate_risk_gate(...)` 与冻结 `RiskGateResult`：

- 校验 profile、research pipeline、risk budget、allocation envelope 的
  owner/profile/version/risk-level 绑定；发现闭包篡改或跨用户输入时阻断；
- 要求 research pipeline 为 `READY`，并重新验证 `DecisionTrace` 中所有
  Fact/Finding/Evidence 的引用、`VERIFIED` 状态和唯一 ID；不暴露
  Recommendation；
- 要求 risk budget 为 `PASS`、allocation 为 `READY`，并核对 envelope 与
  assessment 的预算/报告身份；`REVIEW_REQUIRED` 向上保持待复核，`BLOCKED`
  向上保持阻断；
- 只输出是否具备进入建议组装的风险资格和静态安全 issue，不产生任何交易
  动作、再平衡数量或收益目标。

### 2. Compliance gate

新增 `AdvisoryCandidate`（仅为未来 Recommendation 的非持久化预检输入）和
独立 `evaluate_compliance_gate(...)`：

- 候选只允许携带候选 ID、owner、说明/理由、Finding 引用、失效条件和机器可
  枚举的风险披露；本阶段绝不将其转换为 `Recommendation`；
- 要求候选 owner 与 profile/pipeline 一致，Finding 必须来自当前 READY trace，
  其 Fact 与 Evidence 必须全部 `VERIFIED`；未知引用、跨 owner、伪造闭包和
  不安全输入阻断；研究 pipeline 降级则保持待复核；
- 固定要求 `NO_GUARANTEE`、`LOSS_RISK`、`EVIDENCE_SCOPE`、
  `INVALIDATION_CONDITIONS` 四类披露；缺少任何一类只能待复核；
- 对说明与理由执行确定性禁词/收益承诺检查（如保证收益、稳赚、无风险、
  必涨或数字化目标收益率）；命中即阻断，输出只保留静态规则编号，不回显
  原文；
- 检查说明、理由和失效条件不包含凭据/秘密关键字；输出不包含候选原文。

### 3. Combined eligibility result

新增 `evaluate_decision_gates(...)` 与冻结 `DecisionGateResult`：

- 聚合 RiskGate 与 ComplianceGate 的结果，状态按 `BLOCKED > REVIEW_REQUIRED
  > PASS` 合并；只有两者均 PASS 才将 `eligible_for_recommendation` 置为真；
- 保留两个子闸门的稳定 ID、状态和安全 issue，供后续 Recommendation 阶段和
  UI 展示“为何不能给建议”；不包含 Recommendation、订单、仓位动作或收益
  承诺字段；
- 所有结果 ID、issue 顺序和引用集合确定性生成，输入对象保持不可变。

### 4. Fixtures、文档与测试

- 新增脱敏 gate fixture，覆盖完整 PASS、研究降级、风险预算/配置待复核或
  阻断、缺证据、跨 owner、未知 Finding、缺披露、保证收益/目标收益文本和
  敏感输入；
- 新增单元/集成测试，证明 tampered `model_copy` 输入会安全阻断、合法输入不
  被修改、输出无 raw 文本/秘密/Recommendation，旧 Phase 1–10 全部保持绿色；
- 新增 `docs/risk-compliance-gates.md`，记录状态传播、静态合规规则、产品差异
  化和 Phase 12 Recommendation 的严格输入边界；更新 README/TODO/LOG。

## Out of scope（明确不做）

- Recommendation/Decision Receipt 生成、动作类型选择、仓位优化、回测、交易
  执行或收益预测；
- 真实 SkillHub/Tushare 网络、鉴权、重试、缓存、限流、数据库、API、Web/UI；
- LLM 调用、自然语言画像提取、自动改写候选文本或替代人工披露；
- 新增或修改 Phase 1–10 公共模型语义，绕过 `DecisionTrace`、risk budget 或
  allocation envelope 的既有校验；
- 生产法规/牌照结论、法律意见、真实用户 SLA 或浏览器验收声明；本阶段是
  可审计的 MVP 静态规则层，不声称覆盖全部监管要求。

## Reuse boundary

- 复用 `RiskProfile`、`RiskBudgetAssessment`、`AllocationResult` 的既有身份和
  三态语义；不复制集中度或配置计算算法。
- 复用 Phase 10 `ResearchEvidencePipelineResult` 与 `DecisionTrace` 的证据
  闭包；闸门重新从序列化模型校验输入，防止 `model_copy(update=...)` 绕过
  不变量。
- 复用 `EvidenceQualityStatus`、`FactStatus` 和稳定 ID 约定；不建立第二套
  Evidence/Finding 引用格式。
- 上游 `tradeeye-copilot` 与 `TradeEye` 仍只读参考，不作为运行时依赖。

## Product differentiation

同类产品往往把合规声明附在生成文本末尾，风险约束也常由同一个生成器自证。
Prism 将风险闸门与合规闸门置于 Recommendation 之前并保持独立：当研究来源
不完整、画像与组合不一致、风险预算超限或候选使用收益保证语义时，系统会
明确拒绝给出建议，并保留可审计的静态原因。用户看到的不只是“一个答案”，
而是“为什么这个答案现在还不能出现”。

## Acceptance gates

1. 本计划在任何实现代码前提交，并位于从 Phase 10 接受提交新建的独立
   `prism-phase-11` worktree。
2. 完整、同 owner、同 profile 的 READY pipeline + PASS budget + READY
   allocation + 四类披露候选得到两个 PASS 子闸门和
   `eligible_for_recommendation=True`，但结果仍没有 Recommendation。
3. 研究 `REVIEW_REQUIRED/BLOCKED`、风险预算 `REVIEW_REQUIRED/BLOCKED`、
   allocation `REVIEW_REQUIRED/BLOCKED` 按规则传播，不得降级为 PASS 或填充
   缺失事实；身份不匹配、未知 Finding、伪造 trace/状态必须 BLOCKED。
4. 非 VERIFIED Fact/Evidence、缺少证据闭包、重复/未知引用不能通过；输出只
   含安全 issue code/message 和稳定 ID，不泄漏候选原文、异常或秘密。
5. 缺任一披露为 REVIEW_REQUIRED；保证收益、无风险、必涨或数字化目标收益
   承诺为 BLOCKED；规则命中后序列化结果不包含被拒绝的原文。
6. 输入对象在评估前后字节/模型内容不变，结果顺序和 ID 确定；完整旧测试、
   `python -m compileall -q app`、模块导入、fixture JSON、`git diff --check`
   和敏感值扫描全部通过并写入 `LOG.md`。
7. 独立 adversarial review 确认本阶段没有网络、LLM、持久化、UI、Recommendation
   或交易副作用；发现问题修复后才将计划标为 `ACCEPTED`。

## Handoff / stop conditions

- 计划提交后才可实现；实现、审查和修复均在本 worktree，最终只保留本地提交，
  不 push。
- 任何输入边界无法安全重验证时宁可 BLOCKED；不得为了让示例通过而放宽
  `DecisionTrace` 或风险预算不变量。
- 只有所有 acceptance evidence 齐全且独立审查通过，才从接受提交创建下一
  个 worktree，进入 Phase 12 Recommendation/Decision Receipt；若外部
  SkillHub 凭据仍缺失，继续保持 fixture-only 事实边界。

## Status

`PLANNED`
