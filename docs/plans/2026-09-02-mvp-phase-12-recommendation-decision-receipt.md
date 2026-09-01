# Working Plan：MVP Phase 12 Recommendation and Decision Receipt

## Goal

把 Phase 11 已接受的双闸门资格转换成第一份真正闭合的个性化
`Recommendation -> Finding -> Fact -> Evidence` 决策结果，并同时生成可回放、
可验真的 `DecisionReceipt`。

本阶段不让 LLM 自由选择资产、动作或仓位。Recommendation 由已验证的画像、
持仓/暴露、allocation band、研究 Finding 和双 PASS gate 确定性组装：已确认
breach 只允许降险；无 breach 只允许维持当前配置。任何数据降级、闸门未通过
或跨对象闭包错误都不得产生 Recommendation/Receipt。

## Context / Constraints

- `Prism.md` 是唯一项目规范；旗舰纵切仍是“科技基金集中持仓体检”。
- Phase 11 最终接受提交为 `38c53c2`；本阶段位于独立
  `D:\Github_Storage\prism-phase-12` worktree。
- Phase 11 的 `DecisionGateResult` 是唯一建议资格入口。Composer 必须用当前
  输入重新运行双闸门并逐字段比较，拒绝旧 gate、不同 candidate 或
  `model_copy(update=...)` 篡改。
- Phase 5 allocation envelope 是仓位区间唯一来源；Composer 不计算新的预算、
  不分配 breach 释放的资金、不猜测预期收益。
- Phase 8/10 `DecisionTrace` 和现有 `Recommendation` 是唯一证据/建议契约；
  不创建第二套弱引用。
- 所有输出冻结、owner 隔离、确定性排序；生成时间由调用方显式传入，测试和
  回放不得读取隐式系统时钟。

## In scope（本阶段必须完成）

### 1. Recommendation composition contract

新增冻结 `RecommendationCompositionResult` 及安全 issue/status：

- `PASS` 必须包含至少一条 Recommendation、完整 DecisionTrace、四类披露和
  DecisionReceipt；
- `REVIEW_REQUIRED/BLOCKED` 不包含 Recommendation/Receipt，也不回显候选
  statement/rationale，仅保留 Phase 11 gate 和静态安全原因；
- PASS 输出的 summary 与 rationale 必须逐字来自已通过合规 gate 的同一
  `AdvisoryCandidate`，Finding 引用必须等于 candidate Finding 集合；
- 每条 Recommendation 的 compliance status 固定为 `PASSED`，失效条件为
  candidate 与 allocation envelope 条件的确定性去重并集；
- 结果重新构造 `DecisionTrace`，保留 Phase 10 Evidence/Fact/Finding，并加入
  Recommendation 后再次触发现有闭包验证。

### 2. Deterministic action rules

实现 `compose_recommendations(...)`：

- 先重验证 profile、portfolio bundle、exposure、concentration、risk assessment、
  allocation、research pipeline、candidate 和 gate result，并检查 owner、
  profile/version、bundle/snapshot/report、assessment/envelope/run/gate 闭包；
- 重新调用 `evaluate_decision_gates`，只有结果与传入 gate 完全相等且双 gate
  均 PASS 才进入组装；
- 当 `risk_gate.remediation_required=true`：只对携带
  `remediation_breach_ids` 的 `OVER_LIMIT` bands 生成 `REDUCE`，每条区间严格
  使用 band 的 `[target_min_weight_pct, target_max_weight_pct]`，并要求全部
  remediation breach 被覆盖且无额外 breach；
- 如果 breach 只落在 SECTOR/TECHNOLOGY/UNCLASSIFIED 聚合 band，当前阶段不
  伪造具体证券，返回安全阻断原因，等待后续显式资产映射阶段；
- 当 `remediation_required=false`：只对 ASSET bands 生成 `HOLD`，区间严格等于
  当前权重；不得生成 ADD/EXIT、聚合风险动作或任意仓位变化；
- Recommendation ID 绑定 profile、gate、candidate、band、动作、区间、Finding
  与失效条件，集合顺序与输入排列无关；相同输入得到相同结果。

### 3. Decision Receipt and content hashes

新增冻结 `DecisionReceipt` 与 receipt binding 契约，至少记录：

- owner、profile ID/version、position snapshot、portfolio bundle、exposure report、
  concentration report、risk assessment、allocation envelope、research run；
- candidate、risk/compliance/decision gate ID；
- Evidence/Fact/Finding/Recommendation ID 闭包和每条 Recommendation 对应的
  band dimension/target/breach IDs；
- 固定规则版本（Evidence Contract、risk budget、allocation、compliance policy、
  recommendation composer、receipt schema）；
- `generation_mode=DETERMINISTIC`，并显式记录空 model-version 集合，避免暗示
  本阶段调用了 LLM；
- timezone-aware `generated_at`、完整 DecisionTrace 的 canonical SHA-256 和
  receipt 自身排除 hash 字段后的 canonical SHA-256。

Receipt 构造器与模型 validator 都必须重算 hash；任何字段、引用、顺序、时间或
Recommendation 内容被修改时，验证失败。Receipt 只保存身份/哈希，不保存完整
私人持仓或 raw Provider payload。

### 4. Fixtures、文档与 verification

- 新增完整脱敏 fixture，至少覆盖同一持仓/证据下 BALANCED 画像的 HOLD 和
  CONSERVATIVE 画像的 deterministic REDUCE，证明个性化实质改变结果；
- 覆盖 gate review/block、stale gate/candidate、跨 owner/profile/bundle、
  missing/extra breach、band/区间篡改、非 VERIFIED trace、Receipt/hash 篡改、
  重排确定性、输入不可变和 timezone；
- 新增 `docs/recommendation-decision-receipt.md`，说明动作边界、回放字段、hash
  算法、产品差异化与后续 API/存储消费规则；更新 README/TODO/LOG。

## Out of scope（明确不做）

- `ADD`/买入机会选择、自由 `EXIT`、目标价、收益预测、保证收益、概率判断；
- 多资产资金再分配、组合权重和为 100% 的优化、相关性/流动性/税费/交易单位、
  复杂均值方差或风险平价；
- 同一用户的守稳/均衡/进取三套情景区间；本阶段先闭合画像条件的最小
  HOLD/REDUCE 决策，情景包必须在后续独立阶段使用新的计划和约束验证；
- LLM 文案生成或 semantic compliance reviewer；候选文本只复用已通过 Phase 11
  静态规则的精确内容；
- 真实 SkillHub/Tushare、数据库迁移、API、缓存、签名密钥、Web/UI、浏览器、
  真实并发/3 秒 SLA 或交易执行；
- Receipt 持久化、数字签名/公证或法律合规完整性声明。

## Reuse boundary

- 复用 Phase 11 `evaluate_decision_gates`、`AdvisoryCandidate` 和 gate ID；不允许
  Composer 自行声明合规通过。
- 复用 Phase 5 `AllocationBand/Envelope` 的目标区间、breach 和失效条件；不
  重写风险预算或分配算法。
- 复用 `Recommendation`、`ComplianceStatus.PASSED` 和 `DecisionTrace` 闭包；
  不修改既有 action/compliance 语义。
- 复用 canonical structured JSON + SHA-256 约定，并提升为 receipt 可复核的
  公共辅助函数；禁止拼字符串或依赖 Python 对象 repr 生成有效 hash。
- 上游 `tradeeye-copilot` 与 `TradeEye` 继续只读，不作为运行时依赖。

## Product differentiation

同类产品常把“生成一段建议”当作终点，之后很难回答当时使用了哪个画像、哪份
持仓、哪些证据和哪版规则。Prism 的 Recommendation 只是 Receipt 闭包中的一
个节点：用户能看到个人约束究竟把动作从 HOLD 改成了哪些 REDUCE、每个区间
来自哪条风险上限、哪些 Finding 支撑理由，以及任一输入改变后旧决策为何失效。
这使个性化、风险控制和可追责性同时成为产品能力，而不是免责声明。

## Acceptance gates

1. 本计划在任何 Phase 12 实现代码前提交，并位于从 `38c53c2` 新建的独立
   Phase 12 worktree。
2. 同一闭合 portfolio/research evidence：BALANCED/PASS budget 只产生 ASSET
   HOLD 且区间等于当前权重；CONSERVATIVE/完整 breach 只产生 REDUCE，覆盖全部
   remediation breach，区间逐项等于 allocation band。
3. Gate 必须用精确输入重算；REVIEW_REQUIRED/BLOCKED、旧 gate、不同 candidate、
   owner/profile/bundle/report mismatch 或 forged PASS 均不产生 Recommendation/
   Receipt，并返回安全状态。
4. PASS DecisionTrace 的每条 Recommendation 只引用 candidate 的 VERIFIED
   Finding 闭包，compliance 为 PASSED，失效条件闭合；不存在 ADD、目标收益、
   order/quantity/price 或未注册引用。
5. Receipt 覆盖全部身份、规则版本、gate、trace 和 recommendation-band/breach
   binding；canonical hash 对无序集合重排稳定，对任意实质字段篡改敏感，且
   validator 可独立拒绝伪造 hash。
6. 输入在调用前后不变；重复 100 次结果一致；输出不含 raw Provider payload、
   凭据、异常、完整私人持仓或候选文本（非 PASS）。
7. 完整旧测试、`python -m compileall -q app`、公开导入、fixture JSON、
   `git diff --check`、网络/存储/LLM 边界和敏感值扫描全部通过并写入 LOG。
8. 独立 adversarial review 确认没有 LLM、网络、持久化、UI、交易副作用或越过
   allocation 的动作；问题修复后才标记 `ACCEPTED` 并创建下一 worktree。

## Handoff / stop conditions

- 计划提交后才可实现；实现、审查和修复均在本 worktree，最终本地提交不 push。
- 无法证明 gate/candidate/portfolio/research/allocation 精确闭包时宁可 BLOCKED；
  不接受“ID 看起来相同”替代内容重验证。
- 如果 aggregate breach 无法映射到可执行证券，本阶段返回安全阻断结果，不生成
  Recommendation/Receipt，也不伪造具体卖出标的或资金去向。
- 只有所有验收证据齐全，下一阶段才能从接受提交创建新 worktree，接 API/
  持久化或三情景方案；真实外部 Provider 仍受官方文档/凭据阻塞。

## Status

`ACCEPTED`
