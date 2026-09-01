# Prism MVP Phase 29：可审计的结构化上下文记忆计划

状态：`PLANNED`

日期：2026-09-02

工作树：`D:\Github_Storage\prism-phase-29`

基线：Phase 28 已验收提交 `ba5d316`

## 1. 阶段目标

本阶段补齐 `Prism.md` 要求的“多轮交互/上下文记忆”最小可用边界：把用户已经
明确确认的结构化 Risk Profile、Portfolio snapshot 和可选的 Intent/Plan/研究与
组合提案引用保存为 owner-scoped、不可变、可校验的 context memory record；页面刷新
或再次进入工作台后可以读取最近记录，用户可明确恢复到当前会话，再次运行已有
Advisor/Research/Optimization 流程。

记忆保存的是“当时使用了哪些已验证上下文”的可审计快照，不是把自然语言聊天记录
塞进数据库。它解决的是跨轮次不丢失画像/持仓口径和避免模型凭空回忆，而不是建设
开放式长期人格记忆或让 LLM 代替事实来源。

## 2. 明确做什么

### 2.1 严格结构化记忆契约

- 在 `app/store/contracts.py` 增加 `ContextMemoryWriteRequest`、
  `ContextMemoryRecord`、`ContextMemoryListResponse` 和安全的记忆状态/来源字段；
  所有对象 `extra=forbid`、timezone-aware、owner/profile/questionnaire/portfolio
  闭合，稳定 `memory_id` 与 `content_hash` 由服务端从规范化结构计算。
- 记忆载荷只允许已验证的 `RiskQuestionnaire`、`RiskProfile`、
  `PortfolioImportBundle`，以及 `AdvisorIntentRequest`/`AdvisorPlanResponse` 和
  固定格式的 research/optimization 引用；不接受自然语言原文、Provider 参数、
  凭据、任意 JSON 或客户端提交的派生 hash。
- 记录 immutable append-only；同一 owner、同一规范化内容重复写入必须幂等返回，
  不同内容不得复用同一 ID。读取按 `saved_at`/`memory_id` 稳定排序，限制每次返回
  数量，拒绝跨 owner 读取。

### 2.2 复用现有 owner-scoped SQLite 边界

- 复用 `DecisionEventStore` 的 RLock、事务、WAL、migration runner、owner 校验、
  content-addressed JSON 和 `StoreCorruptError` 语义，在同一数据库增加
  `context_memory` 表与幂等写入/列表/读取方法；不另造不一致的存储协议。
- 新迁移必须幂等、旧数据库可升级；损坏的 payload、owner/hash/timestamp 不一致时
  只返回安全 `STORE_CORRUPT` 错误，不回显原文。
- 记忆不写 `DecisionEvent`，不修改既有 Receipt/Recommendation；DecisionEvent 仍
  仅由 Advisor 查询成功路径产生。

### 2.3 API 与工作台

- 增加 `POST /api/v1/advisor/context-memory`：要求 `X-Owner-ID` 与载荷一致，
  服务端重新验证 profile/questionnaire/portfolio/intent/plan 闭包并保存；重复内容
  返回同一 record，响应不回显任何异常细节。
- 增加 `GET /api/v1/advisor/context-memory?limit=N`：只返回当前 owner 的最近
  结构化记录和安全摘要；支持空列表，不能读到其他 owner。
- 工作台增加“保存当前上下文”和“读取最近上下文”动作。保存前必须已有本会话确认的
  profile 与 portfolio；恢复前显示 record 身份/保存时间/画像等级/快照身份和来源，
  用户显式点击后才把结构化值载入当前会话，并清理旧 Advisor/Research/Optimization
  结果。没有恢复时不自动覆盖当前表单。
- 动态内容继续只使用 DOM 节点 API/`textContent`；owner 切换、恢复失败、过期异步
  响应清空旧记忆选择和派生结果。页面明确标注本地 MVP 记忆不是认证、不是云同步。

### 2.4 产品差异化

普通聊天投顾把历史对话当作不可审计的隐式上下文，容易把旧持仓或旧风险偏好混入
新回答。Prism 的记忆单元绑定 questionnaire/profile version、bundle/snapshot、
Intent/Plan 和 hash；恢复动作可核对“这次回答究竟基于哪一份画像和持仓”，过期或
跨 owner 记录直接拒绝。用户选择 Prism 的理由是可恢复、可重放且知道何时失效，而
不是更长的聊天窗口。

## 3. 明确不做

- 不接入真实账户同步、云数据库、生产认证/授权、加密密钥管理、跨设备同步或多租户
  身份系统；本阶段继续使用本地 `X-Owner-ID` 隔离键并明确不等同认证。
- 不保存自然语言问题、聊天全文、Prompt、LLM/Gemini 输出、Provider 原始响应、
  凭据、cookie、token 或任何任意用户输入；不做语义检索、向量库、自动摘要或人格推断。
- 不自动选取/恢复记忆，不改变用户当前确认值，不在恢复时静默重算历史结果；必须显式
  点击并重新运行需要新鲜上下文的流程。
- 不删除/覆盖历史记录，不实现 TTL 清理、跨 owner 管理、管理员导出或生产备份；不
  修改既有 DecisionEvent 内容或 Recommendation 语义。
- 不接入实时 Provider、复杂 Agent 编排、交易/调仓、相关性/流动性模型，也不借机重写
  现有 Portfolio/Research/Optimization 模块。

## 4. 复用边界与实现策略

### 复用

- Phase 2/20 的 `RiskQuestionnaire`、`RiskProfile`、`PortfolioImportBundle` 和
  owner/timezone/sensitive validators；Phase 22 的 Intent/Plan 结构化引用；Phase
  28 的 Optimization request/scenario identity。
- Phase 13 的 SQLite migration/transaction/content hash/owner isolation；Phase 18/20
  的 UI state reset、异步 sequence 防护和 text-only DOM；Phase 21 固定评测和 Phase 28
  的 plan→implement→review→browser 验收纪律。
- 视觉继续复用现有暖白、深墨、陶土橙工作台语法；不复制 TradeEye 运行时代码，只借鉴
  已记录的审计/状态思想。

### 新增或适配

- 在既有 `store` 契约和 SQLite adapter 中新增一张 owner-scoped context memory 表、
  migration、append-only 幂等方法及安全列表投影；服务端负责 canonical identity，
  客户端只提交结构化已确认对象。
- 在 `app/api` 增加两条 memory 路由和注入边界再验证；在静态工作台增加 memory card，
  只恢复当前会话结构化 Profile/Portfolio 与引用，不恢复 raw text 或派生结果。
- 增加 Phase 29 单元/集成/攻击性测试、迁移重启测试、owner/limit/hash/敏感/extra/
  stale 恢复测试，并保持 Phase 28 的 Optimization 结果和 DecisionEvent 副作用不变。

## 5. 验收门（必须全部通过）

### 计划门

1. 本计划书先独立提交；计划提交前不修改业务代码。

### 契约与存储门

2. 覆盖合法写入、重复幂等、不同内容稳定 ID、extra/敏感/naive 时间/owner 越权、
   nested owner/profile/portfolio/intent/plan drift、客户端伪造 memory_id/content_hash、
   limit 边界与空列表。
3. 覆盖 SQLite migration 首次启动/重启读取、事务冲突、损坏 payload/hash/timestamp/
   owner 行拒绝和 append-only（没有更新/删除路径）。
4. 覆盖恢复只能显式发生、恢复清理旧派生结果、过期异步结果不回写、跨 owner 不泄露；
   记忆保存/读取不增加 DecisionEventStore 行，也不产生 Recommendation 旁路。

### 回归与安全门

5. 阶段测试、全量 pytest、`compileall`、公开 import、前端 `node --check`、
   `git diff --check` 通过；Phase 28 的 398 项基线全部保持绿色。
6. `python -m tools.evaluate_mvp --repeat 100 --json` 维持 9/9 与所有指标 1.0；
   100 owner 并发写入/读取 memory 记录，记录 P50/P95/P99、错误、owner mismatch、
   store rows 和跨重启读取，明确这是本地 SQLite fixture 基线。
7. wheel 包含迁移、contracts、adapter、API/static resources；安装后可写入/读取一条
   memory record。运行时扫描无外网、LLM/Gemini、凭据、raw chat、HTML sink、订单或
   Recommendation 旁路。

### 浏览器验收门

8. 真实本地浏览器完成：确认 Profile/Portfolio → 保存上下文 → 刷新/读取最近记录 →
   显式恢复 → 重新运行 Advisor/Optimization；可见 owner/profile/snapshot/hash/时间
   与“本地记忆非认证”边界。切换 owner 后旧记录和派生结果清空，跨 owner API 403，
   控制台错误为 `[]`，无外部请求。

## 6. 阶段停止条件与后续

只有上述验收门全部通过，并由独立审查修复所有 P0/P1 契约、owner、hash 和恢复竞态
缺口后，才把本计划改为 `ACCEPTED`，并从接受提交创建下一个全新 worktree。Provider
Cache/Fallback、Advanced Evidence UI、实时 SkillHub、生产认证与云持久化继续登记为
后续阶段，不在本阶段顺手实现。

## 7. 验收记录（实现后填写）

- 待实现后填写计划/实现/审查提交、阶段与全量测试、评测/并发、wheel、浏览器和最终状态。

