# Working Plan：MVP Phase 20 结构化上下文导入与确认

## Goal

把 MVP 从“只能查看固定合成 Portfolio/Risk 模板”推进到“用户可以提交并确认一份
结构化上下文，再运行既有 Advisor 纵切”。本阶段提供严格 owner-scoped 的 Portfolio
JSON 校验和 Risk Questionnaire 确认；确认结果只在当前浏览器会话中生效，Advisor
提交后仍由既有 DecisionEvent 负责审计。所有风险、暴露、研究、闸门和 Recommendation
规则继续复用，不在本阶段重写。

## Context / constraints

- `Prism.md` 是唯一产品规范；Phase 19 接受提交为 `1a0ccf3`，本阶段必须在新的
  `D:\Github_Storage\prism-phase-20` worktree 完成，并先提交本计划。
- Phase 2 的不可变 `PortfolioImportBundle`/`RiskQuestionnaire`、Phase 14 的 Advisor
  service、Phase 18 的上下文视图和 owner/sequence 清理是唯一复用边界；不从 raw JSON
  绕过 Pydantic，也不把浏览器输入当成已确认事实。
- “导入”限定为本地粘贴 JSON 的结构化验证，不上传文件到外部服务；确认结果不写入
  数据库。只有随后通过既有 `POST /api/v1/advisor/queries` 的查询才会生成
  DecisionEvent/Receipt。
- `X-Owner-ID` 仍只是本地隔离键，不等同认证。任何导入 Portfolio 或确认问卷都要求
  body owner 与 header owner 完全一致；切换 owner、确认失败或异步响应过期时宁可清空
  上下文，不保留上一 owner 数据。

## In scope（本阶段必须完成）

### 1. Strict context confirmation API

- 新增 owner-scoped `POST /api/v1/advisor/context/portfolio`：接收严格
  `portfolio-context-request.v1` wrapper 和已有 `PortfolioImportBundle`，重新验证
  bundle、snapshot、position、fund parent/holding 的 owner/ID/时间/数值闭合，并返回
  `portfolio-context-response.v1` 的已验证 bundle 与只读计数元数据。不得返回 raw
  JSON、凭据、异常或额外字段。
- 新增 owner-scoped `POST /api/v1/advisor/context/profile`：接收严格
  `profile-context-request.v1` 和已有 `RiskQuestionnaire`，复用
  `build_profile_draft`/`finalize_profile` 生成确定性 `RiskProfile`，返回
  `profile-context-response.v1` 的 questionnaire/profile 闭合。没有自然语言抽取、
  extraction conflict 或新的风险评分规则。
- 两个 endpoint 都是无副作用验证：不写 DecisionEvent、不给出 Recommendation、
  不修改模板 fixture；缺 owner、owner mismatch、敏感/额外字段、无时区/无效枚举和
  Pydantic bypass 均映射为现有统一安全错误。

### 2. Context-aware workbench interaction

- Portfolio 区域增加“粘贴结构化 JSON→验证并加载”控件；只用 `JSON.parse`、同源 API
  和现有 `textContent` DOM，成功后展示已确认的 bundle/snapshot/positions/
  look-through 原值，并明确“当前会话、只读、非真实账户”。解析失败或 API 拒绝不回显
  JSON 原文。
- Risk Profile/Advisor 区域增加“确认当前问卷”动作；复用现有表单字段和模板时间，
  显示 profile ID、risk score/level 及 questionnaire ID，确认后仍保留原有 Receipt
  绑定信息。
- Advisor 查询优先使用已确认的 Portfolio，未确认时继续使用 owner-rebound 合成
  模板；Risk Questionnaire 继续由现有显式表单生成。Advisor POST payload 必须带
  已确认 bundle，服务端仍是唯一计算/闸门入口。
- owner 切换、模板重新绑定和异步竞态清理 `portfolioContext/profileContext`、导入
  文本、状态、事件、证据和研究视图；旧 owner 的 Portfolio 或 Profile 不得残留。

### 3. Contract, integration and browser evidence

- 增加 API/contract tests：合法导入/确认、nested owner mismatch、snapshot/fund
  parent mismatch、额外/敏感字段、无 owner/无时区、确定性 profile 结果和无存储副作用。
- 增加 Advisor integration test：确认一个不同 bundle ID 的 Portfolio 后运行既有
  BALANCED 查询，Receipt/DecisionEvent 绑定导入 bundle/snapshot；未确认或失败输入
  不会静默替换为用户数据，也不产生事件。
- 增加静态边界测试：context DOM/API、同源 CSP、无 `innerHTML`/外链/LLM/订单入口、
  输入原文不写入错误响应；已有 Phase 18 Research/Advisor 路径保持通过。
- 真实本地浏览器完成：粘贴合成 Portfolio JSON→确认 Portfolio→确认 Risk Profile→
  Advisor `HOLD`/`REDUCE`→Evidence/Receipt→切换 owner 后清空；浏览器无错误。

## Out of scope（明确不做）

- CSV/券商 API/真实账户同步、文件上传到服务器、认证/JWT/OAuth、多租户会话、生产
  PostgreSQL/Redis、持久化 Profile/Portfolio CRUD、版本迁移或云部署。
- 真实 SkillHub/Tushare/Wencai Provider、实时行情、缓存/重试/连接池/断路器、LLM/
  Gemini/自然语言画像提取和后台 DAG；当前只提交已验证结构化输入给既有 fixture-first
  Advisor。
- 新增暴露、集中度、相关性、流动性、优化、风险阈值、Recommendation/Gate 规则、
  目标价、收益承诺、订单、交易或再平衡；profile score 只调用既有确定性 scorer。
- React 构建链、复杂动画、跨会话记忆、真实 100 用户/3 秒/99.9% SLA 声明；Phase 19
  负载基线和 Phase 18 Research/Portfolio 视图不重写。

## Reuse boundary

- 复用 `PortfolioImportBundle`、`PositionSnapshot`、`FundHoldingSnapshot`、
  `RiskQuestionnaire` 和 `RiskProfile` contracts；新 API 只增加严格 wrapper/response
  contract，不复制字段校验或从 dict 手工重算。
- 复用 `build_profile_draft`/`finalize_profile`、`FixtureAdvisorQueryService`、
  `AdvisorQueryRequest`、DecisionEvent Store 和统一 FastAPI error handlers；不另造
  profile scorer、portfolio engine 或建议 composer。
- 复用 Phase 18 的 `loadTemplateContext`、owner/sequence 清理、Portfolio/Profile
  renderers、暖白/深墨/陶土橙视觉语法和 text-only DOM；`tools/load_test.py` 只作为
  后续并发回归入口，不复制其 HTTP 编排。
- `tradeeye-copilot`/`TradeEye` 仍只作只读架构/视觉参考，不导入运行时代码、行情或
  交易 API。

## Product differentiation

固定演示数据或聊天式投顾会让用户难以确认建议是否真的基于自己的组合。Prism 让用户
先提交一份可验证的 Portfolio 快照、确认风险问卷，再沿着同一条
`Portfolio → Profile → Research → Evidence → Receipt` 链检查结果；owner 闭合、原值
可核对和失败不替换，是选择 Prism 而不是只给一句“个性化”结论的理由。本阶段尤其
避免“粘贴成功就算真实账户”的错觉，明确确认只在当前本地会话有效。

## Acceptance gates

1. 计划先于实现提交，所有修改只位于从 Phase 19 `1a0ccf3` 创建的独立 Phase 20
   worktree；不修改 Phase 19、Phase 18 或 main worktree。
2. Portfolio/Profile endpoint 严格 extra-forbid、敏感拒绝、owner/ID/时间闭合；确认
   只返回安全模型，不产生事件或 Recommendation，错误不回显输入原文。
3. 已确认 Portfolio 能进入既有 Advisor POST 并在 Receipt/DecisionEvent 中绑定其
   bundle/snapshot；未确认/失败输入不会被静默采用，Risk score/level 与既有 scorer 一致。
4. 浏览器完成粘贴 JSON、Portfolio/Profile 确认、Advisor HOLD/REDUCE、Evidence/Receipt
   和 owner 切换清空；无浏览器错误，旧 owner 的输入/状态/事件不残留。
5. Phase 20 测试、全量回归、compile/import、node/静态边界、CLI/fixture/wheel、
   `git diff --check` 和必要的负载/重放检查通过；仅允许已知 Starlette/httpx warning。
6. 独立审查确认没有前端金融重算、认证假象、跨 owner 泄露、Recommendation 伪造、
   订单/外部网络/LLM 路径；修复后才将计划标记 `ACCEPTED`，再创建下一阶段 worktree。

## Handoff / stop conditions

- 结构化 JSON 任何字段不合法或 owner 不闭合时，保持空上下文并显示安全错误；不得
  为了展示而放宽契约、自动重写 owner 或吞掉验证失败。
- 只记录本地会话确认和既有 DecisionEvent 绑定；真实账户导入、认证和生产持久化需
  单独获得接口/授权后另立阶段。
- Phase 21 只能从 Phase 20 接受提交创建新 worktree，并先提交计划书。

## Status

`ACCEPTED`

## Acceptance record

- Implementation commits: `912dedc` (context confirmation API/workbench) and
  `35e27fd` (profile identity and adversarial boundary tests).
- Phase-specific tests: `7 passed`; full regression: `283 passed`, with only the known
  Starlette/httpx deprecation warning.
- `compileall`, public imports, `node --check`, `git diff --check`, package wheel and
  package-data checks passed. The final wheel contained 74 entries including both
  context endpoints, static workbench assets and `profile_confirmation.py`.
- Local ASGI 100-concurrency replay (one operation per owner) completed with zero
  failures and zero owner mismatches for Template, Research and Advisor. Advisor wrote
  100 expected DecisionEvents; Template/Research wrote none.
- Real browser replay passed Portfolio JSON confirmation, Risk Profile confirmation,
  diversified BALANCED `HOLD`, CONSERVATIVE `REDUCE`, expanded Evidence/Receipt, and
  owner switch clearing of imported bundle, profile, textarea and status. Browser error
  logs were empty.
- Independent review found and fixed stale confirmed-context retention after invalid
  Portfolio input; the final boundary keeps validation server-side, does not recalculate
  financial values in the browser, and adds no authentication, external network, LLM,
  order, or Recommendation path.
