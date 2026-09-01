# MVP Phase 7 Working Plan：Bounded Research Orchestration Contract

- Status：`READY`
- Owner：Codex
- Reviewer：Codex + user
- Target worktree：`D:\Github_Storage\prism-phase-7`
- Target branch：`codex/mvp-phase-7-bounded-orchestration`
- Source of truth：[Prism.md](../../Prism.md)
- Parent plan：[Prism Foundation](2026-09-01-foundation.md)
- Prerequisite：Phase 6 Structured Research/Cross-Validation accepted at `4a0eac1`

## Goal

为后续真实研究 Provider 和结构化 DAG 固定一个最小、有界、可回放的运行时
状态契约。它只描述一个 owner 的研究 run、节点依赖、预算、deadline、节点
结果和完成/降级条件；状态转换是纯确定性函数，不在本阶段启动线程、访问
网络或执行 Agent。

本阶段的退出结果是“系统知道每个节点处于什么状态、为什么不能完成、何时
必须降级”，不是一次真实研究请求，也不是建议生成器。

## Product rationale

很多 Agent 产品把后台超时、依赖失败和“没有搜到”折叠成一条空白答案。Prism
把研究 run 的节点 DAG、必需/可选边界和时间预算作为可审计状态展示：用户
能看到是宏观、行业、个股还是基金节点未完成，而不是误以为系统已经完成
全量研究。这个可回放的状态链是 Evidence-grounded 个性化的前提，也避免
用更多 Agent 掩盖不确定性。

## Reuse and architecture boundary

- 复用 Phase 6 的 `ResearchNodeKind`、四态 `ResearchNodeResult` 和 Phase 1
  的安全 issue/预算语义；复用 `tradeeye-copilot` 的 owner/暂停/取消状态
  模式和 `TradeEye` 的稳定 ID/幂等思路，但不运行时导入或复制源码。
- 新模块位于 `app/orchestration/`，只保存结构化状态；未来可由异步 DAG
  执行器消费，当前不实现执行器。
- 不修改 Evidence、Profile、Portfolio、Risk、Allocation、Research 或
  上游仓库的既有模型和测试。

## In scope（本阶段必须完成）

### 1. Frozen DAG and run contracts

在 `app/orchestration/contracts.py` 定义严格冻结模型：

- `ResearchNodeSpec`：node ID、owner、kind、required、依赖 node IDs、节点
  timeout；拒绝重复依赖、未知依赖、自依赖和非正预算；
- `ResearchPlan`：plan ID、owner、run scope、节点集合和确定性拓扑顺序；
  创建时验证唯一 ID、无环和稳定排序；
- `ResearchRunStatus`：`PENDING`、`RUNNING`、`PARTIAL`、`COMPLETED`、
  `FAILED`、`CANCELLED`；
- `ResearchNodeRun`：节点状态、尝试/开始/完成时间、预算、结果引用和安全
  issue；
- `ResearchRunState`：request/run/owner、plan、总 budget/deadline、节点运行
  状态、更新时间和最终 issues。

所有跨模块对象不可变、`extra=forbid`、时间戳带时区；私人 owner 不得在
  节点或 run 之间串线。

### 2. Pure state transitions

在 `app/orchestration/state_machine.py` 实现：

- `create_research_run(plan, request_id, budget_ms, created_at)`：生成
  `PENDING` run，固定 deadline 和节点初始状态；
- `start_research_run(state, now)`：只有依赖为空/已完成的计划可以进入
  `RUNNING`，过 deadline 直接安全失败；
- `record_node_result(state, node_id, node_result, now)`：校验 owner/kind/依赖
  和 deadline，保留 Phase 6 的 COMPLETE/PARTIAL/EMPTY/FAILED 语义；结果
  不得用零值替代失败；
- `finish_research_run(state, now)`：必需节点全部 COMPLETE 才能 `COMPLETED`；
  可选节点 partial/empty/failed 时只能 `PARTIAL`；必需节点失败或超时为
  `FAILED`；
- `cancel_research_run(state, now, reason)`：只允许未终态取消，安全记录原因；
- 每个转换返回新对象，不修改原 state；转换 ID/节点排序稳定，重复提交同
  一节点结果必须拒绝，不静默覆盖历史状态。

### 3. Explicit budget and dependency semantics

- 单节点 timeout 不得超过 run budget；deadline 之后的节点结果一律拒绝，
  run 进入 `FAILED` 或保持可审计终态；
- 必需节点 `FAILED`/`EMPTY`/`PARTIAL` 不得被解释为完成；可选节点降级只能
  让 run 成为 `PARTIAL`；
- 节点依赖按确定性拓扑序返回，不能按输入字典顺序或 Agent 到达顺序漂移；
- 任何 owner、plan、node kind、request/run ID 不匹配均拒绝，而不是生成跨
  用户状态；
- 状态机不执行网络/LLM/重试，只记录未来执行器所需的状态边界。

### 4. Offline fixture/tests/docs

- 新增纯合成 DAG fixture（宏观、行业、股票、基金节点），不含账户、凭据、
  在线响应或私人内容。
- 新增单元/集成测试覆盖拓扑排序、环/未知依赖、预算、required/optional
  降级、四态节点结果、重复提交、deadline、取消、owner 串线、不可变性和
  稳定序列化。
- 新增 `docs/bounded-orchestration.md`，明确状态机、降级语义、产品差异和
  非目标。
- README/TODO/LOG 只在独立复审通过后记录实际完成度，不声称已有真实 DAG
  执行、Provider、并发或 UI。

## Out of scope（本阶段明确不做）

- 不启动异步任务、线程、进程、Agent、Provider、网络、SkillHub/Tushare、
  LLM、Prompt、重试、缓存、断路器、数据库、迁移、API、Web UI 或浏览器；
- 不修改 `Evidence`、`Fact`、`Finding`、`Recommendation`、`DecisionTrace`
  或 Phase 1–6 的既有代码/测试；Evidence-grounded Finding 桥接另立阶段；
- 不实现宏观/行业/个股/基金金融分析、收益预测、估值、相关性、波动率、
  回撤、流动性、配置优化、交易动作、合规文案或最终建议；
- 不把 `EMPTY`、`PARTIAL`、`FAILED` 解释为零值或成功，不伪造 100 用户、
  3 秒 P95、99.9% 可用性或比赛接口授权；
- 不修改 `Prism.md`、上游仓库或其他阶段 worktree，不 push。

## Implementation sequence

1. 先提交本计划书并确认 `git diff --check`，状态保持 `READY`。
2. 先写 DAG/状态转换反例，再实现 `app/orchestration` 的冻结模型和纯函数。
3. 添加合成 fixture、契约文档和集成示例，保持 Phase 1–6 文件不变。
4. 运行完整测试、编译、导入、fixture JSON/敏感字段扫描和状态序列化重复
   运行检查。
5. 独立复审重点检查：必需/可选降级、deadline、依赖环、重复提交、终态
   保护、owner 串线和错误状态隐藏。
6. 复审通过后再标记 `ACCEPTED`，补 README/TODO/LOG，形成单个本地实现提交；
   下一阶段必须建立新 worktree。

## Acceptance criteria

1. 合法 DAG 生成稳定拓扑序；输入节点/依赖顺序变化不改变 plan ID 或序列。
2. 重复 node ID、重复依赖、自依赖、未知依赖和环均被拒绝。
3. run 创建固定总 budget/deadline；节点 timeout 非正或超过总预算被拒绝。
4. 依赖未完成时不能记录下游结果；重复记录同一 node 被拒绝且旧 state 不变。
5. 必需节点全部 `COMPLETE` 才能 `COMPLETED`；必需 partial/empty/failed 或
   超时不能伪装完成。
6. 可选节点不完整时 run 只能 `PARTIAL`，并保留安全 issue；不可选节点不会
   产生虚构结果。
7. `PENDING`/`RUNNING`/`PARTIAL`/`COMPLETED`/`FAILED`/`CANCELLED` 终态转换
   有实际反例，终态不可再次写入或取消。
8. 节点 owner、kind、plan/run ID、request ID 串线和篡改均被拒绝；模型深度
   不可变且未知字段被拒绝。
9. deadline 之后的结果、安全取消和预算失败不泄漏原始异常或敏感 payload。
10. 序列化只包含结构化状态/安全 issue，不含 recommendation/order/price/
    return promise/api_key/authorization/secret 字段或措辞。
11. Phase 1–6 原有 122 项测试继续通过；新增测试全部通过。
12. `python -m compileall -q app`、模块导入、`git diff --check`、fixture
    JSON 和敏感字段扫描通过。
13. 最终 worktree 干净，只产生一个本地 Phase 7 实现提交，不 push；复审记录
    明确剩余风险和下一阶段建议。

## Review stop conditions

遇到以下任一情况必须停止并记录，而不是放宽契约：

- 需要网络、真实 Provider、线程/异步执行器或 LLM 才能完成当前验收；
- 必需节点失败却只能通过填零、跳过依赖或降级成 `COMPLETED` 通过测试；
- 终态可以被重复提交覆盖，或不同 owner 能读取同一 run；
- 拓扑序、deadline 或状态结果随输入/到达顺序漂移；
- 发现 Phase 1–6 owner/状态闭包缺陷，应退回复审而不是旁路。
