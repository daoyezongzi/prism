# Working Plan：MVP Phase 23 结构化画像提取提案与冲突确认

## Goal

把 `Prism.md` 已定义的用户画像冲突语义接入当前 Portfolio/Advisor 工作台：用户
可以提交一个已经脱敏、已经结构化的画像提取提案，先查看问卷与提取值的差异，再
逐项选择 `USE_QUESTIONNAIRE` 或 `USE_EXTRACTION`，最后得到一个确定性、可审计的
Risk Profile。这样画像变化有明确的确认动作，且不会让自然语言或模型输出绕过规则。

## Context / constraints

- Phase 22 接受提交为 `abd9a35`；本阶段必须在全新的
  `D:\Github_Storage\prism-phase-23` worktree 完成，并先提交本计划。
- `Prism.md`、Phase 2 `ProfileExtractionProposal`/`ProfileConflict`/`finalize_profile`
  和 Phase 20 Risk Profile 会话确认是本阶段真源；不得复制另一套评分、画像或闸门。
- 提取提案的输入边界只接受 typed values、confidence 和 64 字符 input digest；digest
  标识原文而不是原文存储。当前阶段不声称有自然语言解析、LLM/Gemini 或账户认证。
- 继续保持 fixture-first、owner-scoped、无外部网络、无交易；不修改上游仓库。

## In scope（本阶段必须完成）

### 1. Strict profile proposal API

- 新增 `advisor-profile-proposal-request.v1`：owner-scoped `RiskQuestionnaire` 与
  `ProfileExtractionProposal`，严格 extra-forbid、timezone、owner、digest、敏感
  内容和结构校验。
- 新增 `advisor-profile-proposal-response.v1`：返回重新构造的 `ProfileDraft`，
  包含冲突维度、问卷值、提取值和 `REQUIRES_CONFIRMATION`/`READY` 状态；错误只返回
  安全分类，不回显输入或异常。
- 新增 `advisor-profile-confirmation-request.v1`：同样的问卷/提案加显式 conflict
  resolution mapping；服务端重新构造 draft 后调用既有 `finalize_profile`，拒绝
  未解决、未知 conflict ID、跨 owner 或伪造 draft。
- 新增 `advisor-profile-confirmation-response.v1`：只返回闭合的 `RiskProfile` 与
  resolved conflicts；不写 DecisionEventStore，不产生 Recommendation/Receipt。

### 2. Risk Profile workbench flow

- 在现有 Risk Profile 区域增加脱敏 JSON 提案输入、`input_digest` 说明、预览冲突和
  每个冲突的显式选择控件；无冲突提案可以直接确认。
- 预览和确认均复用当前问卷字段，owner/问卷/提案异步序列变化会清空旧 draft/profile
  和 resolution；确认失败不保留旧结果。
- 动态文字继续使用 `textContent` 与同源 fetch；Advisor 查询仍保持原有显式表单和
  既有 scorer 绑定，不把 proposal API 偷接到 Recommendation 链。

### 3. Tests and documentation

- API/integration tests 覆盖无冲突 READY、冲突 unresolved、两种 resolution 的结果
  差异、重复回放、owner/extra/sensitive/naive-time/unknown-ID/forged-draft 拒绝、
  无存储副作用和 Advisor 回归。
- 静态测试确认无 raw natural-language 字段、外链、LLM/Gemini、订单路径和 DOM HTML
  注入；浏览器验证冲突预览→逐项确认→Risk Profile→Advisor HOLD/REDUCE→Evidence/
  Receipt→owner 清理。
- 新增 [画像提案契约](docs/profile-proposal-confirmation.md)，更新 README/TODO/LOG
  与本计划验收记录。

## Out of scope（明确不做）

- 自然语言输入解析、Prompt、LLM/Gemini、第三方模型、真实 SkillHub/Wencai/Tushare、
  账户同步、身份认证或原文持久化。
- 新风险评分权重、组合/暴露/相关性/优化/Recommendation/Receipt 规则；Advisor
  既有 scorer 和纵切只做兼容回归。
- Profile/Portfolio CRUD、数据库迁移、跨会话记忆、后台队列、生产限流、交易/订单。
- 修改 `tradeeye-copilot` 或 `TradeEye` 上游代码。

## Reuse boundary

- 复用 `ProfileExtractionProposal`、`ProfileDraft`、`ProfileConflict`、
  `ConflictResolution`、`build_profile_draft` 和 `finalize_profile`；不复制字段、
  冲突比较或评分公式。
- 复用 Phase 20 的 owner dependency、错误脱敏、会话确认和模板问卷；复用 Phase 22
  的同源静态 workbench、intent/plan 清理与序列保护。
- API 只负责边界重验证和确定性 orchestration；不让客户端提交可直接信任的 draft 或
  Risk Profile。

## Product differentiation

通用投顾通常把一句自然语言直接变成不可审计的画像。Prism 把“提取出的画像候选”
与用户问卷并排展示，每个冲突都必须由用户选择，最终 Profile 还保留选择记录和
提案 digest。用户因此能看见究竟是哪个约束改变了结果，而不是接受一个无法复核的
模型标签；这与 Phase 22 可预览的任务拆解共同形成“先确认约束、再运行证据链”的
差异化体验。

## Acceptance gates

1. 计划先于实现提交；所有改动只在 `prism-phase-23` worktree，且从 Phase 22
   接受提交开始。
2. 两个 request/response contract strict extra-forbid、owner/time/digest/sensitive
   安全；draft 冲突闭合，客户端伪造 draft、unknown ID 和 unresolved resolution 均拒绝。
3. 预览/确认 endpoint 只读且无 DecisionEvent/Provider/Recommendation 副作用；同一
   输入重放稳定，`USE_QUESTIONNAIRE` 与 `USE_EXTRACTION` 结果可解释地不同。
4. 浏览器完成提案预览、冲突逐项确认、Risk Profile 展示、Advisor HOLD/REDUCE、
   Evidence/Receipt 和 owner 清理；无浏览器错误。
5. Phase 23 tests、全量回归、compile/import、node/static、CLI/eval replay、wheel、
   `git diff --check` 通过，仅允许已知 Starlette/httpx warning。
6. 独立审查确认没有自然语言/LLM 假象、前端评分、跨 owner 泄露、原文存储、外部
   网络或交易路径；修复后将计划标记 `ACCEPTED`，再创建 Phase 24 worktree。

## Handoff / stop conditions

- 没有提案或仍有 unresolved conflict 时，系统只能展示 `REQUIRES_CONFIRMATION`，
  不得自动选值或生成确认 Profile。
- 提案 digest 不代表原文真实性；真实自然语言解析与官方 SkillHub 授权另立阶段，
  不在本阶段宣称完成。
- Phase 24 只能从 Phase 23 接受提交创建新 worktree，并先提交计划书。

## Independent review and acceptance

- Implementation commits: `5b24d68` (proposal API/workbench) and `dd21d06`
  (deeply immutable confirmation resolutions); branch
  `codex/mvp-phase-23-profile-confirmation`; no push.
- Phase-specific tests: `6 passed`; full regression: `299 passed`, with only the
  existing Starlette/httpx deprecation warning.
- `compileall`, public imports, `node --check`, `git diff --check`, runtime-scope
  and DOM-sink scans passed. The wheel contains the new service, contracts and
  static assets together with the existing tools and 9 evaluation cases.
- `python -m tools.evaluate_mvp --repeat 100 --json` passed all 9 cases with
  case/profile/risk/compliance/evidence/replay metrics equal to `1.0`.
- Local ASGI load replay at 100 concurrent owners remained 100/100 with zero
  errors and zero owner mismatches for Template, Research and Advisor; these
  remain fixture baselines rather than production SLA evidence.
- Real local browser verification completed a five-conflict proposal preview,
  mixed explicit resolutions, the resulting Risk Profile, Advisor `HOLD` and
  `REDUCE`, Evidence/Receipt expansion, questionnaire invalidation, owner
  clearing, and an empty browser error log.
- Review found no natural-language/LLM/Gemini façade, frontend scoring, raw
  language persistence, cross-owner path, external network, order, or new
  Recommendation side effect in the proposal boundary.

## Status

`ACCEPTED`
