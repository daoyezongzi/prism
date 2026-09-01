# Working Plan：MVP Phase 15 结构化 Advisor Query 工作台

## Goal

把 Phase 14 的“API 可触发、工作台可读取”推进为可演示的完整本地交互：用户在
现有 Prism workbench 中输入 owner 和结构化风险问卷，选择合成持仓模板，触发
`POST /api/v1/advisor/queries`，随后直接在同一页面查看 HOLD/REDUCE、回执和
Evidence 链。页面仍然是 Investment Research Workspace，不变成自由聊天窗口。

本阶段只做浏览器可操作的 fixture-first vertical slice；真实 SkillHub、认证、LLM
和生产持仓导入继续明确延期。

## Context / Constraints

- `Prism.md` 是产品真源；本阶段在独立
  `D:\Github_Storage\prism-phase-15` worktree 实现。
- Phase 14 接受提交是 `8f10ed2` 的内容；其 `AdvisorQueryRequest`、
  `FixtureAdvisorQueryService`、owner-scoped DecisionEvent API 和工作台现有
  Evidence drill-down 是唯一入口，不复制 Profile/Risk/Recommendation 规则。
- UI 只提交结构化枚举和数值，不接受自然语言建议、目标收益、目标价、数量、订单
  或凭据。`generated_at` 与 `query_id` 必须可见且可重放。
- 合成模板中的 owner 会由服务器按 `X-Owner-ID` 重绑定；模板不含私人持仓、真实
  账户或 Provider 原文。

## In scope（本阶段必须完成）

### 1. Safe query template boundary

- 增加打包的合成 Advisor query template（问卷 + 已确认的穿透持仓），并由严格
  契约校验 schema、timezone、owner closure、无敏感字段。
- 增加 owner-scoped `GET /api/v1/advisor/query-template`，按请求 owner 重绑定
  所有嵌套 owner 字段，只返回合成模板和已登记 fixture ID。
- 错误继续使用 Phase 13/14 的统一安全错误响应，不回显请求、异常、原始持仓或
  Provider payload。

### 2. Structured workbench controls

- 在现有 Advisor panel 增加结构化表单：query ID、风险承受分数、投资期限、流动性
  需求、经验、收益预期枚举和最大回撤容忍度；显示当前 owner、fixture 和生成时间。
- 增加“运行 Advisor 查询”按钮、进行中/成功/待复核/阻断状态和安全错误提示。
- 复用现有视觉语法、DOM text-only 渲染和 CSP；不得把 API 返回值作为 `innerHTML`
  或可执行脚本。
- 查询成功后刷新 owner-scoped event list，自动展示刚产生的事件；保留现有点击
  回执、失效条件和 `Finding → Fact → Evidence` 展开能力。

### 3. Integration and verification

- API/contract tests 覆盖模板 owner 重绑定、跨 owner 拒绝、额外字段/敏感输入、
  balanced `HOLD`、conservative `REDUCE`、重复 query 幂等和 degraded research
  非可执行结果。
- Static UI tests 覆盖表单字段、fetch headers、请求路径、状态文本、无
  `innerHTML`/inline script/外部网络引用。
- 真实本地浏览器从表单发起至少一次 BALANCED 查询，再切换 CONSERVATIVE 复用同一
  持仓观察动作变化；展开 Evidence，并切换另一 owner 验证 0 events。
- 更新 README、architecture、TODO、LOG 和本阶段 API/UI 文档，清楚记录这是本地
  合成演示，不是实时行情或正式投顾。

## Out of scope（明确不做）

- 同花顺问财 SkillHub/Tushare 网络、在线鉴权、JWT/OAuth、cookie、重试、缓存、
  连接池、断路器和生产数据库；
- LLM/Gemini、自然语言对话、画像文本抽取、多轮记忆或自由 Agent；
- 用户真实 CSV/券商导入、Portfolio/Profile CRUD、文件上传、云部署和外部 SLA；
- 宏观/行业/个股/ETF 专用 Agent、新金融规则、相关性/优化/压力测试；
- ADD/EXIT、目标价、收益率承诺、数量、交易或再平衡副作用；
- 重写现有 workbench、引入前端框架或外部 CDN/字体/脚本。

## Reuse boundary

- 复用 Phase 2–14 的 `RiskQuestionnaire`、`PortfolioImportBundle`、
  `AdvisorQueryRequest`、`FixtureAdvisorQueryService`、`DecisionEventStore`、
  FastAPI owner dependency、静态页面和 Evidence rendering；不创建第二套业务模型。
- 模板只作为 API 结构化输入的安全样例；金融事实仍只能从 Fixture Provider→
  Research Pipeline→Evidence/Finding 进入 Composer。
- 表单值映射到既有问卷枚举/Decimal 字段，Profile→Risk Budget→Allocation→Gate
  逻辑保持服务端唯一实现。
- 继续使用 CSP、`textContent`、响应契约和统一错误映射；模板 owner 重绑定须在
  Pydantic 契约边界重新验证，不能依赖前端字符串替换。

## Product differentiation

多数投顾 Demo 让用户在聊天框里描述“我能承受多少风险”，再返回一段无法复核的
文本。Prism 的表单把关键约束显式化：相同合成持仓、相同证据和相同生成时间下，
BALANCED 可以得到 HOLD，CONSERVATIVE 可以得到 breach-bound REDUCE；用户能立即
看到是哪一个约束改变了动作，并沿 `Recommendation → Finding → Fact → Evidence`
展开依据。没有足够证据时页面显示待复核/阻断，而不是用聊天语气掩盖缺口。这个
“结构化输入 + 可重放回执 + 证据钻取”是选择 Prism 而不是普通聊天产品的理由。

## Acceptance gates

1. 本计划在实现代码前提交，且所有实现位于独立 `prism-phase-15` worktree；
2. `GET /api/v1/advisor/query-template` 只返回合法、脱敏、按 header owner 重绑定
   的合成模板；跨 owner、敏感字段、额外字段和无时区输入安全拒绝；
3. 浏览器表单只生成 `AdvisorQueryRequest`，调用 Phase 14 服务和既有 DecisionEvent
   store；BALANCED/CONSERVATIVE 的 HOLD/REDUCE 与 API 单元结果一致；
4. 固定 query ID + generated_at 重复提交返回 `created=false`，不同 owner 不能读到
   事件；Provider/研究退化不展示 Receipt、Recommendation 或 Evidence/Finding trace；
5. UI 通过现有 CSP 和 text-only DOM 渲染，静态扫描确认无 inline script、`innerHTML`
   和外部网络/交易副作用；
6. 真实本地浏览器完成“表单→API→回执→Evidence 展开→切换 owner”验收；
7. `python -m pytest`（旧测试+Phase 15）、`compileall`、公开导入、fixture JSON、
   wheel package data、`git diff --check`、无网络/LLM/交易边界扫描通过；
8. 独立 adversarial review 确认模板 owner 不可穿透、输入不能绕过服务校验、UI 不回显
   原文、不弱化 gate/receipt、幂等和状态语义不漂移；通过后才标记 `ACCEPTED`，再
   创建下一阶段新 worktree。

## Handoff / stop conditions

- 计划提交后才能实现；实现、审查和浏览器验收均在本 worktree，不 push。
- 若缺少真实凭据或真实持仓，继续使用 synthetic fixture，并在文档和 UI 明示边界。
- 未完成表单触发、回执钻取和 owner isolation 之前，不进入下一阶段；下一阶段仍须
  新 worktree 和先行计划。

## Status

`ACCEPTED`

## Acceptance record

- Implementation landed in this dedicated worktree at the current `HEAD` after the
  plan-only commit `765d64c`; no push was performed.
- Full regression: `python -m pytest -q` → `243 passed` (only the installed
  Starlette/httpx deprecation warning); `python -m compileall -q app`, public imports,
  fixture JSON parsing, `node --check app/api/static/app.js`, wheel package-data and
  `git diff --check` passed.
- Boundary scans confirmed no network/LLM/transaction path, no inline script or
  `innerHTML`, no sensitive fixture values, and no package-data omission.
- Adversarial review passed template owner rebinding and sensitive-owner rejection,
  Pydantic-bypass revalidation, generic extra-field errors, 100 concurrent deterministic
  runs, unique persisted events, and owner isolation.
- Real local browser passed structured-form BALANCED `HOLD`, CONSERVATIVE `REDUCE`,
  receipt reuse (`created=false`), `Finding → Fact → Evidence` expansion, and another
  owner seeing `0 events` with a reset form state.
- This phase is accepted locally. The next phase must start from this accepted tree in a
  new worktree and must keep live Provider access, authentication, LLM/chat and orders
  deferred.
