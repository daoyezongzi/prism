# Working Plan：MVP Phase 14 Fixture Advisor Query 与 Profile/Portfolio 集成

## Goal

把 Phase 13 的“只读已保存回执”推进为一条可由 API 触发的、可重放的
fixture-first Advisor 纵切：调用方提交结构化风险问卷和已确认的持仓/基金穿透
快照，Prism 在本地完成画像评分、暴露/集中度、风险预算、allocation envelope、
fixture 研究执行、Evidence/Finding bridge、双闸门和 HOLD/REDUCE Composer，随后
以 Phase 13 的 owner-scoped DecisionEvent 形式保存并返回。重复相同 query 输入必须
产生相同的结构化结果和幂等事件；证据不足只能得到 REVIEW_REQUIRED/BLOCKED，不能
伪造建议。

本阶段是**API 触发的确定性业务纵切**，不是网络接入或聊天 Agent。所有输入和
中间结果继续通过现有不可变 Pydantic 契约；Fixture Provider 只提供脱敏、静态、
可审计的研究来源。

## Context / Constraints

- `Prism.md` 是唯一产品规范；旗舰场景仍是“科技基金集中持仓体检”。
- Phase 13 最终接受提交为 `0156f1b`；本阶段必须在独立
  `D:\Github_Storage\prism-phase-14` worktree 实现。
- Phase 13 API 只接收已闭合的 `RecommendationCompositionResult`。Phase 14 新增
  `/api/v1/advisor/queries`，但生成结果仍必须通过同一 Composer、Receipt、Trace
  和 DecisionEvent 重验证，不能在 API 层复制或放宽 Recommendation 规则。
- `X-Owner-ID` 仍只是 MVP 隔离键，不等同于认证；本地 SQLite 仍不是生产数据库。
- 请求中的 `generated_at` 是显式、带时区的重放锚点；它不是服务器“现在”，用于
  让同一 query 的研究时间、profile/portfolio 计算和 Receipt 内容确定。

## In scope（本阶段必须完成）

### 1. Fixture Advisor query contract

新增严格、不可变的 `AdvisorQueryRequest`/`AdvisorQueryOutput`：

- `query_id`、`fixture_id`、带时区 `generated_at`、`RiskQuestionnaire` 和
  `PortfolioImportBundle`；header owner 必须与问卷、持仓 bundle 的 owner 完全一致；
- query/fixture 标识使用有限字符集，拒绝敏感字段与额外字段；错误响应不回显完整
  问卷、持仓、异常或请求原文；
- 只允许结构化输入，不接受自然语言 recommendation、订单、目标收益或凭据；
- fixture manifest 明确研究 claim、两个独立 lineage 的来源和安全 Finding 文本，
  不含私有持仓或真实凭据。

### 2. Deterministic service pipeline

新增 `app/service` 的 `FixtureAdvisorQueryService`，按固定顺序执行：

1. `build_profile_draft` + `finalize_profile` 对问卷做确定性风险评分；
2. `calculate_exposure`、`calculate_concentration`、`assess_risk_budget`、
   `build_allocation_envelope` 复用现有 Profile/Portfolio/Risk/Allocation 模块；
3. 用现有 `FixtureFinancialProvider`、`build_research_plan`、
   `execute_research_run` 和 `build_research_evidence_pipeline` 执行两个独立
   fixture 来源，形成闭合 `DecisionTrace`；
4. 以 fixture Finding 生成安全 `AdvisoryCandidate`，调用
   `evaluate_decision_gates`，仅把双 PASS 交给 `compose_recommendations`；
5. 重新验证结果，写入 Phase 13 `DecisionEventStore`；非 PASS 保留安全 issue、空
   Receipt/Recommendation/Trace，绝不升级成建议；
6. 通过显式 `query_id + generated_at` 和固定 fixture 输入保证重复请求内容确定，
   由已有事件 content hash 负责幂等保存/冲突保护。

### 3. Owner-scoped API trigger

新增 `POST /api/v1/advisor/queries`：

- 需要 `X-Owner-ID`，只消费结构化 `AdvisorQueryRequest`，返回 query/profile/run
  标识、状态、已保存的 `DecisionEvent` 和 `created`；
- 错误分成 owner scope、invalid fixture/query、store conflict 和 generic refusal，
  不泄漏内部堆栈、原始输入、Provider payload 或凭据；
- 复用 Phase 13 的 list/detail API，调用成功后现有工作台可读取新事件；
- app factory 支持注入 store、clock、service，测试不需要网络或隐式用户目录。

### 4. Offline fixture, docs and verification

- 新增 app 内可打包的 Advisor research manifest 与两个独立 lineage Provider
  fixtures；所有文本、ID 和数值为合成数据；
- 新增服务单元测试/API 集成测试，覆盖 balanced `HOLD`、conservative
  `REDUCE`、问卷/持仓 owner mismatch、重复 query、未知 fixture、研究退化的
  REVIEW/BLOCKED、无目标价/订单/收益承诺和错误脱敏；
- 更新 `docs/architecture.md`、README、TODO、LOG 与本阶段 API/fixture 说明；
- 真实本地浏览器通过 API 触发至少一条 query，再在工作台读取对应 Receipt，展开
  Evidence 并确认同一 owner 可见、其他 owner 不可见。

## Out of scope（明确不做）

- 同花顺问财 SkillHub/Tushare 网络请求、在线鉴权、真实用户登录、JWT/OAuth、
  cookie、重试、缓存、连接池、断路器、动态限流；
- LLM/Gemini、自然语言画像提取、多轮会话、聊天 UI、自由 Agent 对话或模型生成
  金融事实；
- Profile/Portfolio/Research 的生产级 CRUD、PostgreSQL/Redis、加密存储、云部署、
  多实例一致性和外部 100 用户/3 秒 SLA；
- 新增金融规则、相关性/优化/压力测试、宏观/行业/个股/基金真实节点，或把静态
  fixture 结果描述成实时市场数据；
- ADD/EXIT、目标价、收益率承诺、数量、订单、再平衡、现金再分配和真实交易副作用；
- 完整 Portfolio/Research 页面重构；本阶段只要求现有工作台能消费新事件，不扩大
  UI 业务结构。

## Reuse boundary

- 复用 Phase 2–12 的 RiskQuestionnaire/RiskProfile、PortfolioImportBundle、
  exposure/concentration/risk/allocation、research executor/pipeline、独立闸门、
  Recommendation/Decision Receipt/Trace 和 Phase 13 SQLite/API；不创建第二套模型。
- 复用 `FixtureFinancialProvider` 与 Provider 四态/指纹/预算边界；新增 fixture 只
  通过 Provider Protocol 进入执行器，不在服务里读取 raw JSON 作为金融事实。
- 复用 `ContractModel` 的 frozen/extra-forbid、Decimal 和 owner closure；服务只做
  编排和 ID 绑定，不计算收益或让 LLM 决定仓位。
- 复用 Phase 13 的 event content hash、owner 查询和安全错误映射；未来生产 store
  或认证替换必须保持相同 query/result/event 语义。

## Product differentiation

普通投顾 API 往往把用户问卷、持仓和一段不可审计文本交给模型；Prism 的 query
入口把“个人约束 → 穿透暴露 → 风险预算 → 证据闭合 → 动作”作为同一确定性回执。
同一组持仓在 BALANCED 与 CONSERVATIVE 问卷下可复现地从 HOLD 变为 breach-bound
REDUCE；如果研究来源不足，API 会保留待复核/阻断原因而不编造建议。用户选择 Prism
不是因为 Agent 数量，而是每次调用都能回答“哪条约束改变了答案、依据是什么、何时
失效”，且可以用 query 输入重放同一结果。

## Acceptance gates

1. 本计划在任何 Phase 14 实现代码前提交，并位于从 `0156f1b` 创建的独立
   `prism-phase-14` worktree；
2. 有效 query 通过现有 Profile/Portfolio/Risk/Research/Gate/Composer 全链路，
   结果为合法 PASS Receipt（或保持合法 REVIEW/BLOCKED 空建议），同一固定输入
   重复运行得到相同 composition/receipt/content hash；
3. API 严格校验 header owner、嵌套 owner、query/fixture 标识和 generated_at；跨
   owner、未知 fixture、非法 body、冲突和 provider/研究退化均安全失败，不泄漏原文；
4. DecisionEvent 仍按 Phase 13 规则保存，重复内容 `created=false`，不同内容不覆盖；
   non-PASS 不携带 Receipt、Recommendation 或 Evidence/Finding Trace；
5. 脱敏 fixture 与包数据可加载，两个独立 lineage 形成闭合 Evidence→Fact→Finding；
   研究/输入不完整时显式 REVIEW_REQUIRED/BLOCKED，不把缺失零填或伪装成功；
6. 真实本地浏览器通过 API 触发 query 后能读取事件并显示 HOLD/REDUCE 至少一种、
   Receipt、Evidence 链和失效条件；现有 owner isolation UI 仍成立；
7. `python -m pytest`（旧测试+Phase 14）、`compileall`、公开导入、fixture JSON、
   wheel package data、`git diff --check`、无网络/LLM/交易副作用扫描全部通过；
8. 独立 adversarial review 确认没有 profile/portfolio owner 穿透、弱化 gate/receipt、
   query 重放漂移、伪造 PASS、XSS/原文回显、网络或交易副作用；修复后才标记
   `ACCEPTED`，再从接受提交创建下一 worktree。

## Handoff / stop conditions

- 计划提交后才能实现；实现、审查、浏览器验收和最终提交均在本 worktree，不 push。
- 缺少真实凭据时保持 fixture-first，不把本地 query 成功描述为实时数据或生产可用。
- 只有 API 触发的闭合链路、幂等事件、浏览器结果和独立复审证据齐全，才可进入
  下一阶段；下一阶段仍需新 worktree 和先行计划。

## Status

`PLANNED`
