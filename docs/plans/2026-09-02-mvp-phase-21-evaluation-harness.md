# Working Plan：MVP Phase 21 固定评测集与可回放验收工具

## Goal

把 Prism 的“可解释、个性化、风险优先”从单次 Demo 证据推进为一套可重复的
`eval_cases/` 固定评测集与本地报告。评测工具沿用已经接受的 fixture-first
Advisor 纵切，证明不同画像/持仓/证据状态会产生预期的 HOLD、REDUCE、REVIEW 或
BLOCKED 结果，并验证 Recommendation/Receipt 的证据闭包。它不把小样本 fixture
结果包装成真实市场准确率或外部 SLA。

## Context / constraints

- `Prism.md` 是唯一产品规范；Phase 20 接受提交为 `b241b4c`。本阶段必须在新的
  `D:\Github_Storage\prism-phase-21` worktree 完成，并先提交本计划。
- Phase 2 风险/Portfolio contracts、Phase 14 `FixtureAdvisorQueryService`、Phase 18
  上下文展示、Phase 19 本地负载报告是复用边界；不另造评分、暴露、闸门或
  Recommendation 算法。
- 评测输入是可版本化的结构化 JSON，不含自然语言、凭据或真实账户数据；所有时间
  固定为 fixture 时间以保证语义可重放。运行只在进程内完成，不访问网络、不写生产
  数据库或 DecisionEventStore。

## In scope（本阶段必须完成）

### 1. Versioned evaluation cases

- 新增 `eval_cases/` 固定案例集，至少覆盖：BALANCED/长期、CONSERVATIVE/短期、
  高风险画像、科技/行业集中持仓、Provider partial/缺失、Provider conflict/无效
  事实，以及跨 owner/非法输入拒绝。
- 每个 case 严格声明 `case_id`、输入覆盖、预期 `GateStatus`、预期 action 集合、
  是否应生成 Receipt、预期风险/合规语义；案例自身 extra-forbid、敏感字段拒绝、
  timezone 与 owner 闭合。
- 使用既有 Advisor query template 与 provider fixtures 的最小变体；不得把最终
  HOLD/REDUCE 写死到运行时代码，也不得复制一套金融计算。

### 2. Local evaluation runner and report

- 新增 `tools/evaluate_mvp.py`，提供 `--case`、`--repeat`、`--json` 等受限 CLI，
  读取固定案例并运行既有 `FixtureAdvisorQueryService`，输出
  `mvp-evaluation-report.v1`。
- 报告保留 case 输入摘要、预期/实际 status、action 集合、receipt/trace 闭包、
  owner、错误/降级类别、语义 fingerprint 与耗时；不输出原始异常、原始 JSON、
  凭据或外部 URL。
- 计算并明确标注小样本指标：case pass rate、profile alignment、risk detection
  coverage、compliance block coverage、evidence coverage、semantic replay equality
  和 P50/P95 latency。指标是 fixture regression evidence，不是投资收益或市场
  准确率。
- `--repeat N` 对同一固定输入重复运行，必须检查除 latency 外的结果语义一致；失败
  case 不能伪装为通过，未知 case/非法参数必须安全拒绝。

### 3. Tests and documentation

- 增加 contract/unit/integration tests：案例 schema、完整矩阵覆盖、HOLD→REDUCE
  个性化差异、集中度/风险闸门、Provider partial/conflict、evidence/receipt
  closure、owner isolation、sensitive/error redaction、repeat determinism、CLI
  JSON 输出与无存储副作用。
- 增加 [MVP 评测契约](docs/mvp-evaluation.md)，说明案例来源、指标定义、可解释链路、
  结果边界与如何新增案例；README/TODO/LOG 记录真实命令和结果。
- 评测不改 Web UI 或 API semantics；既有浏览器确认链路和 Phase 20 API 必须全量回归。

## Out of scope（明确不做）

- 真实 SkillHub/Wencai/Tushare、实时行情、外部网络鉴权、Gemini/LLM、自然语言解析、
  真实用户问卷、真实账户/CSV/券商同步、认证和云部署。
- 收益率/命中率/回测、基准比较、模型排行榜、生产监控、真实 100 用户/3 秒/99.9%
  SLA 或任何投资收益承诺；不以固定 fixture 结果推导市场能力。
- 新的风险阈值、暴露/集中度/相关性/流动性/优化、Recommendation 规则、订单/交易、
  Portfolio/Profile CRUD、数据库迁移和复杂 UI/动画。
- 不修改 Phase 20、Phase 19 或 main worktree，不推送远程，不引入 upstream runtime
  代码或未确认许可证的实现。

## Reuse boundary

- 复用现有 `AdvisorQueryRequest`、`RiskQuestionnaire`、`PortfolioImportBundle`、
  `FixtureAdvisorQueryService`、Recommendation/Receipt/DecisionTrace contracts、
  `SQLiteDecisionEventStore` 的只读计数语义和 Phase 19 的本地报告/percentile 约定。
- 新 runner 只负责案例加载、输入变体、调用、对比和报告；所有金融算术、profile
  scorer、research evidence、gate 和 receipt 仍由既有模块提供。
- 允许为 evaluator 增加纯数据模型与 fixture 变体，不允许把 evaluator 专用分支
  混入生产 Advisor service；坏 provider 只通过临时复制的既有 fixture 注入。

## Product differentiation

同类产品往往展示一个漂亮结论，却无法证明“换一条用户约束是否真的改变答案”。Prism
的评测报告把 `Profile → Portfolio → Research → Evidence → Gate → Recommendation →
Receipt` 作为可复核对象：同一证据下 BALANCED 可以 HOLD、保守画像可以 REDUCE，数据
缺失/冲突会降级为 REVIEW/BLOCKED，而不是被模型补齐。评委和用户可以查看每个 case
的预期、实际、证据闭包和失败原因，选择的是可审计的个性化系统，而不是不可复现的
聊天演示。

## Acceptance gates

1. 计划先于实现提交；所有变更只在 Phase 21 独立 worktree，基于 Phase 20 `b241b4c`。
2. `eval_cases/` 至少覆盖 8 个明确场景，结构化输入严格校验，敏感/额外/跨 owner/
   无时区等非法 case 不会进入 Advisor 计算。
3. `tools/evaluate_mvp.py --json` 能生成版本化安全报告；`--repeat` 的非耗时语义
   完全一致，case 失败、未知 case 和错误输入保持失败语义。
4. 评测证明 profile-conditioned HOLD/REDUCE 差异、集中度/风险与 Provider 降级检测，
   并逐 case 验证 Evidence → Fact → Finding → Gate → Receipt 闭包和 owner isolation。
5. Phase 21 测试、全量回归、compile/import、CLI smoke、fixture/schema、node/static
   边界、wheel package-data、`git diff --check` 及必要的 100 次语义重放通过；仅允许
   已知 Starlette/httpx warning。
6. 独立审查确认没有市场准确率幻觉、前端金融重算、Recommendation 伪造、认证假象、
   网络/LLM/订单路径；修复后将计划标记 `ACCEPTED`，再创建 Phase 22 新 worktree。

## Handoff / stop conditions

- 缺失、冲突、无效或 owner 不闭合的 case 必须以明确 REVIEW/BLOCKED/拒绝状态报告，
  不得自动填零、降级为 EMPTY 或吞掉错误。
- 报告中的耗时为本地 fixture 运行观测，不得宣称真实市场延迟；case pass rate 不是
  投资建议准确率。真实 SkillHub 接入仍等待官方文档、授权和配额决定。
- Phase 22 只能从 Phase 21 接受提交创建新 worktree，并先提交计划书。

## Status

`ACCEPTED`

## Acceptance record

- Implementation commits: `680ffed` (fixed cases, evaluator, report contract and docs),
  `02dc8bd` (portable/closed report invariants), and `73d926f` (bounded replay up to 100).
- Fixed set contains 9 cases spanning three profile outcomes, concentration and missing
  look-through blocks, Provider partial/conflict, cross-owner refusal and timezone refusal.
- `python -m tools.evaluate_mvp --repeat 100 --json` completed all 9 cases with
  `case_pass_rate=1.0`, `profile_alignment_rate=1.0`, `risk_detection_coverage=1.0`,
  `compliance_block_coverage=1.0`, `evidence_coverage=1.0` and
  `semantic_replay_equality=1.0`. The report exposes only safe summaries and error classes.
- Phase-specific tests: `5 passed`; full regression: `288 passed`, with only the known
  Starlette/httpx deprecation warning. `compileall`, public import, CLI smoke, fixture
  schema, `node --check`, static boundary and `git diff --check` passed.
- Wheel verification confirmed `tools/evaluate_mvp.py`, all 9 `eval_cases` data files and
  existing static assets are packaged; the evaluator resolves data-file installation paths.
- Independent review confirmed the evaluator only delegates to existing deterministic
  Advisor/Profile/Portfolio/Research/Gate/Receipt modules. No new financial formula,
  market accuracy claim, external network, LLM/Gemini, auth, order or persistence path was
  introduced. Phase 21 is accepted; the next phase must use a new worktree and plan.
