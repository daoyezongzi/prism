# Working Plan：MVP Phase 13 Owner-scoped API, Persistence and Explainable UI

## Goal

把 Phase 12 已接受的 `RecommendationCompositionResult` 与
`DecisionReceipt` 接到第一个可运行的产品边界：owner-scoped 本地持久化、
安全 HTTP API 和可解释工作台首屏。用户能够读取自己的决策事件，看到动作、
风险状态、证据 ID、约束区间和失效条件；跨用户、篡改回执或待复核结果不得
被伪装成建议。

本阶段是一个**展示与审计纵切**，不重新计算画像、研究、组合或风险，也不
引入真实 Provider。API 接收已由 Phase 12 Composer 生成并重新验证的结构化
结果，存储层只保存可审计的决策事件，不接受 raw Provider payload 或凭据。

## Context / Constraints

- `Prism.md` 是唯一项目规范；旗舰场景仍是“科技基金集中持仓体检”。
- Phase 12 最终接受提交为 `076e1e6`；本阶段位于独立
  `D:\Github_Storage\prism-phase-13` worktree。
- `RecommendationCompositionResult`、`DecisionReceipt` 和
  `DecisionTrace` 是唯一的建议/证据契约。API、store 和 UI 不创建第二套
  Recommendation，也不放宽 gate、trace 或 receipt 校验。
- 架构 ADR 的生产目标是 PostgreSQL，但当前仓库只有 Pydantic 依赖；本阶段
  使用可替换的 store port + SQLite 本地实现完成可验证纵切，不宣称生产数据
  库、加密或高可用。
- owner header 只是 MVP 的隔离边界，不等同于真实身份认证。任何真实鉴权、
  会话和权限系统另行立项。

## In scope（本阶段必须完成）

### 1. Decision-event persistence

新增 `app/store` 的小型存储端口和 SQLite adapter：

- 以 migration 表和版本化 `decision_events` 表保存事件 ID、owner、状态、
  composition/receipt ID、生成时间、content hash 与结构化结果 JSON；不保存
  输入中的完整私人持仓、raw Provider payload、异常堆栈或凭据；
- 写入前重新构造 `RecommendationCompositionResult`，使 Receipt validator、
  DecisionTrace 闭包和 gate identity 约束在 API/store 边界再次生效；读取时同样
  重新验证并拒绝 hash 或 schema 篡改；
- `owner_id + event/receipt ID` 是所有读写查询的强制范围。相同事件的重复写入
  必须幂等；同一 ID 的不同 owner、不同 content 或不同 hash 必须返回安全冲突，
  不能覆盖旧事件；事务和有限锁保证本地并发写不会产生半条记录；
- 明确区分 `PASS`、`REVIEW_REQUIRED`、`BLOCKED` 事件。只有 PASS 事件包含
  Receipt/Recommendation；待复核/阻断事件可以保存安全 issue 供审计，但不能
  生成或补全建议。

### 2. Owner-scoped FastAPI boundary

新增 `app/api` app factory 和结构化错误映射：

- `GET /api/health`：只返回服务与 schema 版本，不泄漏路径、环境变量或异常；
- `POST /api/v1/decision-events`：要求 `X-Owner-ID`，只接收
  `RecommendationCompositionResult`，校验 body owner 与 header 一致后幂等写入；
- `GET /api/v1/decision-events` 与
  `GET /api/v1/decision-events/{event_id}`：只返回 header owner 的事件，未知
  或其他 owner 统一安全地按不存在处理，避免枚举；
- Pydantic 请求错误、存储冲突、owner 越权和 receipt/hash 失败统一为不回显
  body、候选原文、异常或秘密的 JSON 错误；不引入外部网络、Provider、LLM 或
  交易副作用；
- 通过 app factory 注入 store，测试可使用临时 SQLite 文件；默认路径必须显式
  配置，不读取隐式用户目录或环境中的秘密。

### 3. Explainable workbench first slice

提供 `/` 的零构建静态工作台（HTML/CSS/少量原生 JS），围绕
`tradeeye-copilot/web/styles.css` 已核对的暖白、深墨、陶土橙、衬线标题、
等宽数字和 8pt 间距语法，重新组织为 Prism 的四个区域：

- Overview：当前 owner、最近决策状态、生成时间和 receipt/content hash；
- Advisor：HOLD/REDUCE 动作、精确 allocation range、风险/合规状态和安全的
  summary；REVIEW_REQUIRED/BLOCKED 只显示“为何不能给建议”；
- Evidence：Finding → Fact → Evidence ID 链和来源/期间/新鲜度字段的可展开
  摘要；不显示 raw Provider payload；
- Risk Profile：profile/version、绑定的 portfolio/risk/allocation ID、失效
  条件，以及“同一持仓因画像约束改变动作”的说明；
- 页面通过上述 API 读取，不在浏览器重新计算金融数字；无数据、待复核、越权
  和 API 错误都使用可理解的空/错误状态，不伪造成功卡片。

### 4. Fixtures、文档与 verification

- 新增脱敏决策事件 fixture，覆盖 BALANCED `HOLD`、CONSERVATIVE `REDUCE`、
  REVIEW_REQUIRED/BLOCKED 和无建议的 UI 状态；
- 新增 store 单元测试、API 集成测试和静态 UI/浏览器验收：重复写入、内容
  冲突、跨 owner 读取、篡改 JSON/hash、非法 body、非 PASS 无 Receipt、
  Recommendation/Receipt 闭包和错误脱敏都必须有反例；
- 更新 `docs/architecture.md`、README、TODO、LOG 和本阶段契约文档，明确
  SQLite 仅为本地纵切、owner header 非认证、API/UI 已实现但真实 Provider/
  PostgreSQL/生产 SLA 未实现。

## Out of scope（明确不做）

- 真实同花顺问财 SkillHub/Tushare、鉴权凭据、重试、缓存、连接池、断路器、
  生产 PostgreSQL/Redis、云部署和多实例一致性；
- Profile/Portfolio 的完整 CRUD、自然语言画像提取、持仓导入、研究节点、
  Orchestrator 或在 API 内自动启动 Composer；本阶段 API 消费已闭合结果，下一
  阶段再接查询用例；
- 新增 `ADD`/`EXIT`、目标价、收益率、数量、订单、再平衡、现金再分配或任何
  新的风险/合规规则；
- JWT/OAuth、真实租户管理、加密密钥管理、法律合规认证和外部 100 用户/3 秒
  SLA 声明；
- React 构建链、复杂动画、实时推送、推荐历史搜索和高级图表；本阶段静态
  工作台只实现可点击的证据/状态展示首片。

## Reuse boundary

- 复用 Phase 12 `RecommendationCompositionResult`、`DecisionReceipt`、
  `DecisionTrace`、canonical SHA-256 和 `GateStatus`；store/API 只做重验证、
  持久化和读取，不重算或改写金融结果。
- 复用 `ContractModel` 的 `extra=forbid`、`frozen=True` 语义；任何 JSON 进入
  SQLite 或 HTTP 响应前都经过同一 Pydantic contract。
- 复用 `tradeeye-copilot` 的视觉 token 和证据卡交互语法，保留 Prism 的
  “持仓约束 → 风险 → 建议 → 证据回执”信息架构；不复制其股票页面业务代码，
  不把上游仓库作为运行时依赖。
- SQLite adapter 实现稳定的 store port；未来 PostgreSQL adapter 必须保持
  同一 owner/idempotency/hash contract，而不能让 API 依赖 SQLite 细节。

## Product differentiation

普通投顾 API 常把一段建议文本写进数据库，用户无法确认它属于谁、基于哪份
持仓或哪版规则。Prism 的展示层从第一天就以 Receipt 为中心：每个动作绑定
画像版本、风险/配置约束和证据链；读取必须验证 hash；当数据不足时保留
`REVIEW_REQUIRED/BLOCKED` 的“不能建议原因”，而不是用空卡片冒充正常答案。
同一持仓在 BALANCED 与 CONSERVATIVE 下从 HOLD 变为带 breach 的 REDUCE，UI
可以直接展示这种可解释的约束差异。

## Acceptance gates

1. 本计划在任何 Phase 13 实现代码前提交，并位于从 `076e1e6` 新建的独立
   `prism-phase-13` worktree；
2. store migration 可重复执行，PASS/REVIEW/BLOCKED 事件均能安全保存/读取，
   写入和读取都会重验 receipt/trace/hash；重复同内容写入幂等，冲突不覆盖；
3. 任何 owner 只能读取自己的事件；跨 owner、未知 ID、错误 header、非法类型、
   篡改 JSON/hash 都不会泄漏候选原文、私人持仓、raw payload、异常或凭据；
4. API 集成测试证明健康检查、创建、列表、详情、幂等、冲突和安全错误映射；
   `REVIEW_REQUIRED/BLOCKED` 响应保持空 trace/Receipt，不可被 API/UI 升级；
5. UI 在真实本地浏览器中打开，能通过 API 展示至少一个 HOLD 和一个 REDUCE
   receipt，展开 Evidence 链和失效条件，并能显示待复核/阻断空状态；视觉
   采用已核对的上游 token，但页面业务结构属于 Prism；
6. 输入和已存结果不可变，重复读写确定；全量旧测试、Phase 13 测试、
   `python -m compileall -q app`、公开导入、fixture JSON、`git diff --check`、
   no-network/LLM/secret boundary scan 全部通过；
7. 独立 adversarial review 确认没有跨 owner 读写、弱化 Receipt/hash、伪造
   PASS、XSS/原文回显、网络副作用或交易动作；修复后才标记 `ACCEPTED`，再从
   接受提交创建下一 worktree。

## Handoff / stop conditions

- 计划提交后才可实现；实现、审查、浏览器验收和最终提交均在本 worktree，
  不 push。
- 若缺少真实认证、PostgreSQL 或 Provider 凭据，只保持本地 fixture-first
  边界，不把本地 API/浏览器成功描述为生产可用或真实数据接入。
- 只有 store/API/UI 的验收证据齐全并独立复核通过，下一阶段才能接入
  Profile/Portfolio CRUD、Fixture advisor query 或真实 Provider；仍必须新建
  worktree 并先写计划。

## Status

`PLANNED`
