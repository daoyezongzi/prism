# Working Plan：MVP Phase 22 结构化投资意图与任务计划预览

## Goal

补齐 `Prism.md` MVP 闭环中“投资问题理解与任务规划”的可审计边界：用户先从明确
支持的结构化问题类型中选择一个目标，系统生成 owner、Portfolio/Profile 身份闭合的
研究任务计划预览，说明将由哪些 Macro/Industry/Stock/ETF-Fund 专业轨道提供事实。
计划只是只读的编排意图，不提前运行研究、不生成 Recommendation；Advisor 仍沿用既有
fixture-first 计算链。这样可以让用户看到 Prism 如何把问题拆成可验证任务，而不是把
模糊聊天直接变成不可追溯结论。

## Context / constraints

- `Prism.md` 是唯一产品规范；Phase 21 接受提交为 `f86c73f`。本阶段必须在新的
  `D:\Github_Storage\prism-phase-22` worktree 完成，并先提交本计划。
- 复用 Phase 16 `ResearchSpecialistRole`/矩阵、Phase 18/20 Portfolio/Profile 上下文、
  Phase 14 Advisor owner boundary、Phase 21 评测/静态安全约定；不复制研究执行器或
  另造金融计算。
- 结构化 intent 是显式的本地输入契约，不是自然语言理解、LLM/Gemini 规划或认证。
  请求携带 Portfolio bundle/snapshot 与 Questionnaire 身份摘要，服务端只验证 owner/
  ID/时间闭合并生成确定性计划；不保存在数据库，不把摘要当作账户真实性证明。

## In scope（本阶段必须完成）

### 1. Strict intent and plan contracts

- 新增 `InvestmentIntentType`，至少支持 `TECHNOLOGY_EXPOSURE_REVIEW` 与
  `PORTFOLIO_RISK_REVIEW` 两种可解释问题类型；未知枚举、额外字段、敏感内容、无时区
  和跨 owner 输入均拒绝。
- 新增 `advisor-intent-request.v1`：`intent_id`、`owner_id`、`intent_type`、
  `generated_at`、`portfolio_bundle_id`、`position_snapshot_id`、`questionnaire_id`。
  身份摘要不能被前端任意改写为另一 owner，且所有 ID 必须为非空、可重放字符串。
- 新增 `advisor-plan-response.v1`：稳定 `plan_id`、intent/owner/context 身份、目标
  scope、四类 Research Specialist roles、node_count、generated_at；只返回安全的
  计划元数据，不返回 raw input、Evidence、Fact、Finding 或 Recommendation。

### 2. Read-only planning API and workbench preview

- 增加 owner-scoped `POST /api/v1/advisor/plans`，复用已有
  `FixtureResearchSpecialistMatrixService.matrix_template` 的四轨道节点覆盖，生成
  确定性计划；不运行 Provider、不写 DecisionEventStore、不调用 Advisor Recommendation。
- Advisor 表单增加结构化 Intent 选择和“预览任务计划”动作；预览显示计划 ID、问题
  类型、Portfolio bundle/snapshot、Questionnaire、四条轨道与 node count。
- 预览成功后仍需用户显式运行既有 Advisor Query；Advisor payload 和 Receipt 逻辑不
  改写。owner 切换、模板失败、异步响应过期或上下文确认失败会清空计划和旧 ID。
- 所有动态文字继续通过 `textContent`/同源 fetch 渲染，保持现有 CSP、错误脱敏和
  Phase 20 Portfolio/Profile 会话语义。

### 3. Tests and documentation

- 增加 contract/API/integration tests：两种 intent 的确定性 plan、roles 覆盖、owner/
  ID/时间/敏感/extra 拒绝、无存储副作用、未知 intent 安全错误、replay equality、
  Advisor HOLD/REDUCE 回归和静态无外链/LLM/订单边界。
- 增加 [Intent/Plan 契约](docs/intent-planning.md)，更新 README/TODO/LOG，记录计划
  与真实浏览器证据。
- 浏览器验收：选择 Technology Exposure Review→预览四轨道计划→运行 BALANCED/HOLD，
  选择 Portfolio Risk Review→预览→运行 CONSERVATIVE/REDUCE，展开 Evidence/Receipt，
  换 owner 后计划和上下文清空；浏览器无错误。

## Out of scope（明确不做）

- 自然语言问题解析、对话记忆、Prompt/LLM/Gemini/第三方模型、真实 SkillHub/Wencai/
  Tushare、动态工具选择、在线鉴权或账户真实性判断。
- 研究节点实际执行、Provider 请求、Evidence/Finding 生成、Portfolio/Risk/Correlation/
  Optimization 新规则、Recommendation/Receipt 算法、交易/订单/再平衡。
- 计划持久化、CRUD、跨会话记忆、后台队列、React/动画、生产监控、真实并发/SLA。
  Phase 21 evaluator 和 Phase 20 context API 不重写。

## Reuse boundary

- 复用 `ResearchSpecialistRole` 全量集合、现有矩阵模板的 role/node_count/scope、
  `PortfolioImportBundle`/`RiskQuestionnaire` 的既有 ID/时区模型和 owner dependency。
- 新 service 只负责 intent 类型到既有四轨道 scope 的确定性映射与 plan ID；不复制
  `FixtureResearchSpecialistMatrixService`、Provider、profile scorer、risk gate 或
  receipt 逻辑。
- UI 复用 Phase 20 `loadTemplateContext`、owner/sequence 清理、Portfolio/Profile
  renderer 和暖白/深墨/陶土橙视觉语法；静态测试延续 Phase 18/20 text-only boundary。

## Product differentiation

很多投顾产品把一句“帮我看看组合”直接交给黑盒模型。Prism 先把用户选择的问题变成
一个可检查的 plan：目标、上下文身份和四类专业轨道都能在 Advisor 运行前确认；用户
知道系统会查什么、不会偷偷查什么，之后还能从同一条 Evidence→Receipt 链验证结论。
这把“多 Agent”从展示话术变成可审计的任务拆解，也让同一证据下的个性化差异能够被
复现。

## Acceptance gates

1. 计划先于实现提交；所有变更只在从 Phase 21 `f86c73f` 创建的独立 worktree。
2. 两种 intent request/response 严格 extra-forbid、敏感/owner/ID/时间闭合，plan ID
   和 role 集合确定性；错误不回显输入或异常。
3. `POST /api/v1/advisor/plans` 只读且无 DecisionEvent/Provider/Recommendation 副作用，
   response 明确覆盖 Macro/Industry/Stock/ETF-Fund 四轨道。
4. 浏览器完成两种 intent 预览→Advisor HOLD/REDUCE→Evidence/Receipt→owner 清理，
   保持既有 Portfolio/Profile 确认和上下文隔离；无浏览器错误。
5. Phase 22 tests、全量回归、compile/import、node/static、CLI/eval replay、wheel、
   `git diff --check` 通过；仅允许已知 Starlette/httpx warning。
6. 独立审查确认没有自然语言/LLM 假象、前端金融重算、跨 owner 泄露、Recommendation
   伪造、外部网络或订单路径；修复后将计划标记 `ACCEPTED`，再创建 Phase 23 worktree。

## Handoff / stop conditions

- 仅支持列举的 intent 类型；用户输入不在枚举内时安全拒绝，不自动猜测、不降级为聊天
  任务。计划失败不运行 Advisor，也不保留旧 owner 的计划。
- plan response 是任务意图摘要，不是研究结果或真实账户确认；自然语言和 SkillHub
  仍等待官方文档、授权与配额后另立阶段。
- Phase 23 只能从 Phase 22 接受提交创建新 worktree，并先提交计划书。

## Status

`PLANNED`
