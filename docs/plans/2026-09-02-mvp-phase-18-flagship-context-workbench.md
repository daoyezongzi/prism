# Working Plan：MVP Phase 18 旗舰上下文工作台

## Goal

把现有 fixture-first Advisor 纵切的两个输入上下文——Portfolio 持仓快照和 Risk
Profile 问卷——从已存在的 owner-scoped `query-template` 接口展示到工作台。用户在
运行研究/Advisor 前后都能核对“我持有什么、我允许承受什么”，再沿着研究证据和
Decision Receipt 复核结果。此阶段只增加可见性，不新增金融计算或交互式资产管理。

## Context / Constraints

- `Prism.md` 是唯一产品规范；Phase 17 接受提交为 `30c6926`，本阶段必须在独立
  `D:\Github_Storage\prism-phase-18` worktree 完成，并先提交本计划。
- Phase 13–17 的 `AdvisorQueryTemplate`、`PortfolioImportBundle`、
  `RiskQuestionnaire`、Advisor service 和静态工作台是唯一输入；页面不读取 fixture
  文件，也不重复计算暴露、集中度、风险预算或 allocation。
- `X-Owner-ID` 仍只是本地隔离键，不等同认证。模板中所有 owner-bearing 对象必须
  在服务层重绑定后再渲染；切换 owner 必须清空前一 owner 的持仓和画像上下文。
- 现有暖白/深墨/陶土橙视觉语法、同源 CSP、DOM `textContent` 和无构建静态链路
  继续保留；不复制上游股票页面结构。

## In scope（本阶段必须完成）

### 1. Portfolio context view

- 在现有 workbench 增加 `Portfolio` 导航和持仓快照区域；复用
  `GET /api/v1/advisor/query-template` 返回的已验证 `PortfolioImportBundle`。
- 展示 bundle/snapshot ID、as-of、base currency、每个持仓的资产 ID/名称/类型、
  quantity/market value，以及基金/ETF look-through 的 parent、coverage、underlying
  holding 和 sector。字段按模型原值展示，不在前端重算权重或暴露。
- 明确标注这是合成、只读的本地 MVP 模板；不提供上传、编辑、交易或再平衡按钮。

### 2. Risk Profile context view

- 在 `Risk Profile` 区域展示同一模板的 questionnaire：owner、回答时间、承受分数、
  投资期限、流动性、经验、收益预期和最大回撤容忍度；Advisor 已生成 Receipt 后
  继续展示其 profile/assessment/allocation/research ID 元数据。
- 画像上下文只显示输入和已存在的 Receipt 绑定，不在 UI 新算风险分数、阈值或建议。

### 3. Owner-safe integration and verification

- 页面初始化、读取回执和 Advisor 查询都复用既有模板请求；模板加载失败显示安全
  错误，不回显原文。切换 owner 清空 portfolio/profile/context/error，并防止异步旧
  请求写回新 owner。
- 增加 API/静态测试：模板 owner 重绑定、无 owner/敏感 owner/额外字段拒绝，页面
  的 context DOM、安全渲染、同源 CSP 和 no-order 边界。
- 真实浏览器完成：切换 owner→读取模板→看见持仓与画像→运行 Advisor HOLD/REDUCE
  和 Research Tracks→换 owner 后旧上下文消失；Phase 17 研究 Evidence 和已有
  DecisionEvent 语义不回归。

## Out of scope（明确不做）

- 真实持仓上传/编辑/删除、Portfolio/Risk Profile CRUD、账号认证、JWT/OAuth、多用户
  服务端会话和生产数据库；
- 新增暴露、集中度、相关性、压力测试、风险公式、组合优化、目标价、收益承诺或新
  Recommendation/Gate 规则；前端不重算任何金融数值；
- 真实 SkillHub/Tushare/网络 Provider、LLM/Gemini、自然语言对话、后台任务、研究
  历史、推送、React 构建链、复杂动画、订单或再平衡；
- 以本地模板展示推断真实持仓、真实风险等级、100 用户/3 秒 SLA 或生产可用性。

## Reuse boundary

- 复用 Phase 13–17 的 FastAPI app factory、owner dependency、统一错误响应、
  `AdvisorQueryTemplateResponse` 和静态 CSP/text-only workbench。
- 复用 Phase 2 的不可变 Portfolio/Profile contracts 与 Phase 14 的模板 owner
  rebind；不从 raw JSON 重建模型，不复制 Advisor service 的 profile/exposure/risk
  规则。
- 复用 Phase 17 Research Tracks 和 Phase 15 Advisor/Evidence/Receipt 视觉语法；
  Portfolio/Profile 只是上下文视图，不改变研究或建议的服务端闭包。
- `tradeeye-copilot`/`TradeEye` 仍只作只读视觉和工程参考，不导入运行时代码、策略
  或交易 API。

## Product differentiation

聊天式投顾往往只展示一句结论，用户看不到建议使用的持仓和风险假设。Prism 把
Portfolio 快照、Risk Profile 约束、四轨道研究和最终 Receipt 放在同一条可钻取链上：
用户能先核对上下文，再判断“为何改变”和“何时失效”。这种可核对的个性化输入与
拒绝虚构事实的行为，是选择 Prism 而不是更会聊天的产品的理由。

## Acceptance gates

1. 计划在实现前提交，所有修改只位于从 Phase 17 `30c6926` 创建的独立 worktree。
2. Portfolio/Profile 页面只消费已验证模板，显示 owner 与 snapshot/questionnaire
   ID 闭合；无 owner、敏感/伪造输入和模板错误均安全失败且不回显。
3. owner A 的持仓、基金成分和画像不会在 owner B 页面残留；异步旧模板返回也不能
   覆盖新 owner；研究和 Advisor 结果仍走既有 API/service。
4. 真实浏览器验证模板上下文、Advisor BALANCED `HOLD`、CONSERVATIVE `REDUCE`、
   Research Tracks READY/Evidence 和 owner 切换清空；浏览器无错误。
5. 全量旧测试+Phase 18、compile/import/node、fixture/wheel package-data、
   `git diff --check`、100 次模板重放和 no-network/LLM/order/recalculation 扫描通过；
   仅允许已知 Starlette/httpx deprecation warning。
6. 独立审查确认没有前端重算、跨 owner 泄露、Recommendation/Receipt 伪造或订单
   入口；修复后才标记 `ACCEPTED`，再创建下一阶段 worktree。

## Handoff / stop conditions

- 计划提交后才可实现；实现、审查、浏览器验收和最终提交均在本 worktree，不 push。
- 模板加载失败或 owner 改变时宁可显示空上下文，也不保留旧 owner 内容；不为视觉
  完整而制造新的事实。
- Phase 19 只能从接受提交创建新 worktree，并先决定是否优先负载测试骨架、真实
  Provider 输入门，或剩余 Portfolio/Risk 交互。

## Status

`PLANNED`
