# Working Plan：MVP Phase 17 研究矩阵 API 与工作台视图

## Goal

把 Phase 16 的四轨道 `ResearchSpecialistMatrix` 从服务层消费到现有 owner-scoped
工作台：用户可以在本地浏览器触发一次结构化研究 run，并看到 Macro、Industry、
Stock、ETF/Fund 四类节点的状态、独立来源验证、Finding/Fact/Evidence 链和降级原因。
这一步补齐“研究可见性”而不是增加一套投顾业务逻辑；DecisionEvent 仍只保存
Advisor Recommendation 回执，研究矩阵结果保持显式的非持久化、不可交易边界。

## Context / Constraints

- `Prism.md` 是唯一产品规范；Phase 15 的结构化 Advisor Query 工作台和 Phase 16
  的四轨道离线矩阵均已接受。
- Phase 16 接受提交为 `b04740c`；本阶段必须在独立
  `D:\Github_Storage\prism-phase-17` worktree 完成，并先提交本计划。
- `ResearchSpecialistMatrix`、`FixtureResearchSpecialistMatrixService`、既有
  `ResearchRunExecutionResult`/`ResearchEvidencePipelineResult` 是唯一研究输入；
  API/UI 不能从 raw JSON 或文本重建金融事实。
- `X-Owner-ID` 仍只是本地隔离键，不等同于认证；研究 run 的结果不写入
  `DecisionEventStore`，也不应被展示为 Recommendation/Receipt。
- 前端继续复用无构建静态页面、CSP、`textContent`/DOM API 和暖白/深墨/陶土橙
  视觉语法；产品结构围绕“持仓→证据→约束”，不复制上游股票页面。

## In scope（本阶段必须完成）

### 1. Safe research-matrix API boundary

在 `app/api` 增加 owner-scoped、结构化的研究矩阵边界（路径和类型名可按实现
调整，但语义必须保持）：

- 一个只返回安全元数据的 template endpoint，提供 `matrix_id`、固定
  `generated_at`、scope、四类 role 和节点数量；不直接暴露 Provider fixture 原文、
  私有持仓、凭据或内部异常；
- 一个 `POST` research-run endpoint，接收严格的
  `ResearchSpecialistMatrixRequest`，要求 body owner 与 `X-Owner-ID` 相同，并调用
  已有 `FixtureResearchSpecialistMatrixService`；不接受自然语言、订单、目标价或
  Recommendation 字段；
- 一个最小响应契约：run/pipeline 状态、四类节点的 node kind/status/安全 issue、
  validation status/lineage count、以及由既有 pipeline 产生的 Evidence/Fact/Finding；
  响应必须 owner/run/claim/trace 闭合，永不包含 Recommendation/Receipt；
- API 错误统一为 owner scope、invalid input、matrix refusal 等安全消息，不回显
  raw Provider result、异常、请求原文或敏感字段；支持注入 service 供降级测试。

### 2. Research tracks workbench slice

在现有 Advisor 工作台增加一个与决策回执并列但语义独立的“Research Tracks”区域：

- 结构化按钮使用 template endpoint 取得 matrix/replay anchor，再提交固定
  request ID 和 owner；不添加聊天框、LLM prompt 或自由 Agent 消息；
- 运行后按 Macro、Industry、Stock、ETF/Fund 显示四类节点的完成/待复核/失败状态、
  pipeline READY/REVIEW/BLOCKED 和独立 lineage 数；
- READY 时可展开 `Finding → Fact → Evidence`（来源、期间、值、lineage）；降级或
  冲突时显示待复核原因，不显示 Fact/Finding 以外的虚假确定结论；不把矩阵结果
  拼入 Advisor DecisionEvent；
- 切换 owner 时清空上一 owner 的矩阵状态、节点、Evidence 和错误；所有动态内容
  使用现有 text-only DOM 安全渲染。

### 3. Regression, browser and adversarial verification

- API/contract tests 覆盖 template owner scope、四类节点 READY、固定输入重放、跨
  owner 拒绝、额外字段/敏感输入/Pydantic bypass、未知矩阵、错误映射、无
  Recommendation/Receipt 和 degraded `REVIEW_REQUIRED`；
- 静态测试确认现有 CSP、无 `innerHTML`/inline script/外部网络，节点状态不会被
  前端重算或原文回显；
- 真实本地浏览器完成“切换 owner→运行研究矩阵→看到四轨道→展开 Evidence/Finding→
  切换另一 owner 清空”路径，同时 Phase 15 Advisor HOLD/REDUCE 路径持续通过；
- 运行旧测试+Phase 17、compile/import、fixture/wheel package-data、
  `git diff --check`、无网络/LLM/交易副作用扫描和 100 次确定性 API/service replay；
- 独立 adversarial review 确认 API 不能将研究状态升级为交易建议，不能跨 owner
  泄露，也不能通过响应拼装绕过 gate/trace。

## Out of scope（明确不做）

- 同花顺问财 SkillHub/Tushare 网络、在线鉴权、真实用户登录/JWT/OAuth、凭据、缓存、
  重试、连接池、断路器、动态限流、生产数据库和外部 SLA；
- Gemini/LLM、自然语言研究问题、画像抽取、自由 Agent 对话、persona 和模型生成
  金融事实；
- 把研究矩阵写入 DecisionEventStore、生成 Recommendation/Decision Receipt、
  修改 Advisor Composer/Gate 规则、目标价、收益承诺、订单或再平衡；
- Portfolio/风险画像完整 CRUD、真实持仓上传、研究历史/后台任务、分页/推送、
  新的 React 构建链、复杂动画或上游代码运行时导入；
- 新增金融公式、相关性/优化/压力测试、可转债或真实 ETF/Fund/宏观/行业/个股
  Provider；
- 以本地浏览器通过代替真实 100 用户/3 秒 P95/99.9% 可用性结论。

## Reuse boundary

- 复用 Phase 13–15 的 FastAPI app factory、owner dependency、统一错误响应、静态
  workbench 和 CSP；新增 route 只做结构化输入映射，不复制 service 业务规则。
- 复用 Phase 16 的 `ResearchSpecialistMatrixRequest`、
  `FixtureResearchSpecialistMatrixService`、`ResearchSpecialistRole`、run/pipeline
  状态和 Evidence/Fact/Finding 闭包；API 不读取 fixture 文件或自行计算状态。
- 复用 `DecisionTrace` 的渲染语法与现有 visual grammar；研究结果与已保存 Advisor
  事件在契约和 UI 标签上明确分离，避免用户把“研究 ready”误认成“可执行建议”。
- 上游 `tradeeye-copilot`/`TradeEye` 仅作只读视觉/工具参考，不复制股票页面结构、
  交易 API 或凭据。

## Product differentiation

许多投顾产品把多个 Agent 的一句“看法”放进同一张建议卡，用户看不到哪个节点失败、
来源是否独立，也分不清研究完成与建议可执行。Prism 的研究工作台把四类职责、
状态、lineage 和 Evidence 链并列展示：用户能看到“宏观已验证、行业待复核、ETF
来源为空”以及这会如何阻止下游事实，而 Advisor 回执仍只在独立风险/合规闸门通过后
出现。研究透明度和拒答正确性本身就是选择 Prism 而非聊天式产品的理由。

## Acceptance gates

1. 计划在实现前提交，并确认所有修改位于从 Phase 16 接受提交 `b04740c` 创建的
   独立 `prism-phase-17` worktree。
2. Template/POST API 严格 owner-scoped、extra-forbid、敏感/无时区/未知矩阵安全
   拒绝；响应的 matrix/run/pipeline/node/claim/trace owner 与 ID 完全闭合，且不含
   Recommendation、Receipt、订单或 raw Provider/异常。
3. 正常 fixture run 在 API 和真实浏览器均显示四类节点，pipeline READY，每类 claim
   有两条独立 lineage，并能展开四个 Finding→Fact→Evidence；固定 request/generation
   重放结果一致且不产生 DecisionEvent。
4. PARTIAL/EMPTY/FAILED/timeout/冲突 fixture 经 API 仍保持显式
   `REVIEW_REQUIRED`/`BLOCKED`、无 Fact/Finding/Recommendation，错误不泄漏原始
   provider payload；不同 owner 看不到上一 owner 的节点或证据。
5. UI 静态安全、CSP、text-only DOM、无外部网络和 no-order 边界扫描通过；Owner
   切换清除旧矩阵，Phase 15 Advisor 回执和 HOLD/REDUCE 浏览器路径不回归。
6. `python -m pytest`（旧测试+Phase 17）、`compileall`、公开导入、JSON fixture、
   wheel package-data、`git diff --check`、100 次确定性 replay 和无网络/LLM/交易
   扫描通过；仅允许已知 Starlette/httpx deprecation warning。
7. 独立审查确认没有把研究状态升级为建议、没有绕过既有 pipeline/gate、没有跨 owner
   穿透或 XSS/原文回显；修复后才标记 `ACCEPTED`，再创建下一阶段 worktree。

## Handoff / stop conditions

- 计划提交后才可实现；实现、审查、浏览器验收和最终提交均在本 worktree，不 push。
- 若研究退化，页面必须诚实显示待复核/阻断，不为了展示四类卡片而伪造 Fact/Finding。
- 只有 API、浏览器、owner isolation、回放和边界扫描证据齐全，才可进入 Phase 18；
  下一阶段须新 worktree 和先行计划，继续决定矩阵与 Advisor/Portfolio 纵切的正式
  消费边界。

## Status

`PLANNED`
