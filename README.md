# Prism

> 同一市场，不同约束；每个调整，都能追到底层证据。

Prism 是面向同花顺 A18 赛题的个性化证券研究与决策支持工作台。它不把大语言模型当作金融事实来源，而是把用户画像、可信数据、确定性计算、风险合规和结构化研究组合成一条可审计的决策链。

## 项目真源

[Prism.md](Prism.md) 是本项目的主项目文档和产品/工程总规范。实现文档用于解释如何落实其中的约束，不另建 `PROJECT.md`，也不替代 `Prism.md`。

## 产品切入点

第一条完整纵切固定为“科技基金集中持仓体检”：

1. 用户导入持仓并确认风险、期限、流动性和禁投约束；
2. 系统穿透基金/ETF 暴露，识别行业、风格和相关性集中；
3. 宏观、行业、个股和基金研究节点并行取得结构化证据；
4. 确定性组合与风险引擎计算调整前后的影响；
5. 系统给出守稳、均衡、进取三种调整区间；
6. 任意建议都可追溯到 `Recommendation -> Finding -> Fact -> Evidence`，并显示冲突、缺失和失效条件。

用户选择 Prism 的理由不是“Agent 更多”，而是能看见：哪一条个人约束改变了结果、最小需要调整什么、风险改善了多少，以及这项判断何时不再成立。

## 当前状态

已实现：

- 独立 Git 仓库与 Python 工程基础；
- Evidence/Fact/Finding/Recommendation 的首版领域契约；
- 决策链闭包、缺失数据语义和可行动建议约束测试；
- 架构 ADR、复用矩阵和分阶段实施计划；
- Provider Protocol、四态结果不变量、确定性语义指纹、脱敏与合成 Fixture Provider。
- Phase 2 用户画像契约、确定性问卷评分、结构化提取冲突确认，以及 owner 隔离的持仓/基金穿透原始导入契约。
- Phase 3 已实现基于 Decimal 的直接/基金穿透暴露与数据覆盖结果。
- Phase 4 已实现基于暴露结果的集中度指标与画像条件风险预算；相关性、优化和推荐仍未实现。
- Phase 5 已实现画像条件 allocation envelope、逐约束前后影响和失效条件；最终 Recommendation、研究 DAG 编排、相关性和优化仍未实现。
- Phase 6 已实现四态结构化研究节点、lineage-aware Cross-Validation 与冲突/缺失语义；真实 Provider、DAG 执行器和 Evidence/Finding 连接仍未实现。
- Phase 7 已实现 owner 隔离、依赖闭包、预算/deadline、required/optional 降级和可回放的研究 run 状态机；真实异步执行、Provider 与 Evidence/Finding 桥接仍未实现。
- Phase 8 已实现 CrossValidationResult、ResearchObservation 与 Evidence 的确定性闭包校验，并只在完整支持条件下生成稳定 `VERIFIED Fact -> Finding`；Recommendation、独立合规闸门和真实执行仍未实现。
- Phase 9 已实现注入式 Fixture-backed 异步研究执行：ready 节点并行、依赖门控、四态 Provider 映射、预算边界和 Evidence/Observation 输出；真实 SkillHub、CrossValidation 自动接线、风险合规和 Recommendation 仍未实现。
- Phase 10 已实现 run-aware 研究证据流水线：完整 run 才能将两条独立 lineage 的支持结论接入 Phase 8，并生成闭合 DecisionTrace；partial/failed/empty、冲突和缺失均保持待复核/阻断。
- Phase 11 已实现独立风险/合规闸门：画像、研究证据、风险预算与 allocation envelope 必须跨模块闭合；缺披露保持待复核，保证收益/目标收益和篡改输入会阻断。闸门只输出后续建议资格，仍不生成 Recommendation。
- Phase 12 已实现确定性 Recommendation Composer 与 Decision Receipt：双 PASS 后无 breach 只生成当前权重 HOLD，完整 breach 只生成带 breach 闭合的 REDUCE；回执绑定画像、持仓/风险/研究/gate/证据和规则版本并自校验 hash。API、持久化和 UI 在 Phase 13 接入。
- Phase 13 已实现 owner-scoped SQLite 决策事件持久化、FastAPI 健康/写入/列表/详情边界和首个可解释工作台切片；真实认证、PostgreSQL 和真实 Provider 仍未实现。
- Phase 14 已实现 API 触发的 fixture-first Advisor 纵切：结构化风险问卷与持仓进入 Profile→Exposure→Risk Budget→Allocation→Research→Evidence/Finding→双闸门→HOLD/REDUCE→Decision Receipt，并以幂等 DecisionEvent 返回；固定 `generated_at` 支持确定性重放。
- Phase 14 的脱敏 fixture 覆盖 BALANCED/HOLD、CONSERVATIVE/REDUCE 与研究退化 REVIEW_REQUIRED；工作台可读取并展开新事件，不展示原始 Provider 或私有持仓。
- Phase 14 已通过 `238` 项全量回归、打包/边界检查、100 次确定性并发复核和真实浏览器验收；当前 worktree `HEAD` 在本地接受，未推送。
- Phase 15 已把 Advisor Query 接成结构化表单工作台：模板按 owner 重绑定，表单触发既有
  fixture-first 纵切，支持 BALANCED/HOLD、CONSERVATIVE/REDUCE、回执复用和 Evidence
  展开；`243` 项回归与真实浏览器路径已通过，仍明确是离线合成演示。
- Phase 16 已把四类研究职责落成可复用矩阵：Macro、Industry、Stock、ETF/Fund
  各有双 lineage 来源，8 个节点有界并行执行后形成 8 条 Evidence、4 个 Fact 和
  4 个 Finding；`257` 项回归、100 次并发与边界审查通过，真实 Provider 仍未接入。
- Phase 17 已把四轨道矩阵接入 owner-scoped API 与 Research Tracks 工作台：模板锚点、
  READY/REVIEW/BLOCKED 节点状态、独立 lineage 验证和 Finding → Fact → Evidence
  展开均复用既有 pipeline；研究结果不写入 DecisionEvent，也不产生 Recommendation。
  `264` 项回归、100 次 API 重放、真实浏览器 owner 隔离与 Advisor HOLD/REDUCE 回归通过。
- Phase 18 已把同一 owner-scoped Advisor 模板中的 Portfolio 持仓快照和 Risk Profile
  问卷上下文接入旗舰工作台：显示 bundle/snapshot/questionnaire 身份、持仓与基金穿透
  原值，并在 owner 切换或异步失败时清空旧上下文；不新增计算、CRUD、交易或外部
  Provider。`267` 项回归、100 次模板重放、真实浏览器 Portfolio/Risk/Advisor/Research
  路径和静态边界审查通过。
- Phase 19 已加入可重复的本地早期负载测试骨架：`template`、`research`、`advisor`
  三场景通过 `asyncio`/`httpx.ASGITransport` 输出 P50/P95/P99、错误分类、owner
  闭合和 DecisionEvent 副作用；100 并发合成基线已记录，但不外推为真实外部 SLA。
  `276` 项回归、CLI smoke、打包和边界审查通过。
- Phase 20 已加入严格的结构化 Portfolio/Risk Profile 会话确认：粘贴的
  `PortfolioImportBundle` 与 `RiskQuestionnaire` 先经 owner 闭合、敏感/额外字段和
  timezone 校验，再进入既有 Advisor 纵切；确认不写库，实际 Advisor Receipt 绑定
  用户提交的 bundle/snapshot。工作台在 owner 切换或失败时清空确认状态；真实账户
  上传、认证、Provider、LLM 与生产持久化仍未实现。`283` 项回归、真实浏览器路径、
  本地 100 并发基线和打包边界审查已通过。
- Phase 21 已加入 9 个固定 `eval_cases/` 与版本化 `mvp-evaluation-report.v1`：覆盖
  HOLD/REDUCE 个性化差异、集中度/穿透缺失、Provider 降级/冲突和 owner/时间拒绝，
  支持最多 100 次语义回放；`288` 项回归和本地 fixture 评测通过。报告不代表市场
  准确率、投资收益或真实部署 SLA。
- Phase 22 已加入显式 `advisor-intent-request.v1` 与只读
  `advisor-plan-response.v1`：用户可在 Advisor 工作台选择科技暴露复核或组合风险
  复核，预览复用既有 Macro/Industry/Stock/ETF-Fund 四轨道的确定性任务计划，再
  显式运行原有 HOLD/REDUCE 纵切；计划不运行 Provider、不写 DecisionEvent，也不把
  自然语言或 LLM/Gemini 当作问题理解。详见 [Intent/Plan 契约](docs/intent-planning.md)。

尚未实现：

- 真实同花顺问财 SkillHub Provider 网络接入；
- 实时自然语言画像提取与真实宏观/行业/个股/基金研究节点；
- Recommendation/Decision Receipt 的生产级持久化审计与认证 API；
- 完整 Portfolio/Risk Profile CRUD、真实持仓导入和真实端到端场景；
- 宏观、行业、个股、ETF/Fund 的真实 SkillHub Provider、实时数据和完整工作台消费；
- 真实外部 100 并发、3 秒响应和长期可用性验证。

## 核心不变量

- 金融事实必须可追溯；
- 金融算术必须确定性执行；
- 缺失数据必须保持缺失；
- LLM 推断不得冒充金融事实；
- 用户画像必须实质影响建议；
- 风险与合规独立于建议生成；
- Provider 失败必须显式降级；
- 每项能力必须有新鲜测试证据。

## 本地开发

要求 Python 3.11 或更高版本。

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m pytest
```

当前环境若已安装兼容版本的 Pydantic 与 pytest，也可直接运行：

```powershell
python -m pytest
```

## 仓库索引

- [主项目规范](Prism.md)
- [实施架构](docs/architecture.md)
- [Evidence Contract](docs/evidence-contract.md)
- [Provider Protocol](docs/provider-protocol.md)
- [复用矩阵](docs/reuse-matrix.md)
- [架构决策 ADR-0001](docs/adr/0001-modular-monolith.md)
- [当前实施计划](docs/plans/2026-09-01-foundation.md)
- [Gemini Phase 1 执行合同](docs/plans/2026-09-01-mvp-phase-1-provider-protocol.md)
- [Phase 1 Hardening 计划](docs/plans/2026-09-01-mvp-phase-1-hardening.md)
- [Phase 2 Profile/Portfolio 计划](docs/plans/2026-09-01-mvp-phase-2-profile-portfolio-contracts.md)
- [Phase 2 Profile/Portfolio 契约](docs/profile-portfolio-contracts.md)
- [Phase 3 Look-through Exposure 计划](docs/plans/2026-09-01-mvp-phase-3-lookthrough-exposure.md)
- [Phase 3 Portfolio Exposure 契约](docs/portfolio-exposure.md)
- [Phase 4 Concentration/Risk Budget 计划](docs/plans/2026-09-01-mvp-phase-4-concentration-risk-budget.md)
- [Phase 4 Concentration/Risk Budget 契约](docs/risk-budget.md)
- [Phase 5 Allocation Envelope 计划](docs/plans/2026-09-01-mvp-phase-5-allocation-envelope.md)
- [Phase 5 Allocation Envelope 契约](docs/allocation-envelope.md)
- [Phase 6 Structured Research/Cross-Validation 计划](docs/plans/2026-09-01-mvp-phase-6-research-cross-validation.md)
- [Phase 6 Structured Research/Cross-Validation 契约](docs/research-cross-validation.md)
- [Phase 7 Bounded Orchestration 计划](docs/plans/2026-09-01-mvp-phase-7-bounded-orchestration.md)
- [Phase 7 Bounded Orchestration 契约](docs/bounded-orchestration.md)
- [Phase 8 Evidence/Finding 桥接计划](docs/plans/2026-09-01-mvp-phase-8-evidence-finding.md)
- [Phase 8 Evidence/Finding 桥接契约](docs/evidence-finding-bridge.md)
- [Phase 9 Fixture-backed Research Run 计划](docs/plans/2026-09-01-mvp-phase-9-fixture-research-run.md)
- [Phase 9 Fixture-backed Research Run 契约](docs/fixture-research-run.md)
- [Phase 10 Research-to-Evidence Pipeline 计划](docs/plans/2026-09-01-mvp-phase-10-research-evidence-pipeline.md)
- [Phase 10 Research-to-Evidence Pipeline 契约](docs/research-evidence-pipeline.md)
- [Phase 11 Risk/Compliance Gate 计划](docs/plans/2026-09-01-mvp-phase-11-risk-compliance-gates.md)
- [Phase 11 Risk/Compliance Gate 契约](docs/risk-compliance-gates.md)
- [Phase 12 Recommendation/Decision Receipt 计划](docs/plans/2026-09-02-mvp-phase-12-recommendation-decision-receipt.md)
- [Phase 12 Recommendation/Decision Receipt 契约](docs/recommendation-decision-receipt.md)
- [Phase 13 Owner-scoped API/Persistence/UI 计划](docs/plans/2026-09-02-mvp-phase-13-owner-scoped-api-persistence-ui.md)
- [Phase 13 Decision Events API 与工作台](docs/decision-events-api.md)
- [Phase 14 Advisor Query API 与 Fixture 边界](docs/advisor-query-api.md)
- [Phase 14 Advisor Query/Profile/Portfolio 计划](docs/plans/2026-09-02-mvp-phase-14-advisor-query-profile-portfolio.md)
- [Phase 15 Advisor Query 结构化工作台](docs/advisor-query-workbench.md)
- [Phase 15 结构化工作台计划与验收](docs/plans/2026-09-02-mvp-phase-15-advisor-query-workbench.md)
- [Phase 16 四类研究专员节点矩阵](docs/research-specialist-matrix.md)
- [Phase 16 研究节点矩阵计划与验收](docs/plans/2026-09-02-mvp-phase-16-research-node-matrix.md)
- [Phase 17 Research Tracks 工作台](docs/research-workbench.md)
- [Phase 17 研究工作台计划与验收](docs/plans/2026-09-02-mvp-phase-17-research-workbench.md)
- [Phase 18 Portfolio/Risk Profile 上下文工作台](docs/flagship-context-workbench.md)
- [Phase 18 旗舰上下文工作台计划与验收](docs/plans/2026-09-02-mvp-phase-18-flagship-context-workbench.md)
- [Phase 19 早期负载测试工具](docs/load-test.md)
- [Phase 19 负载测试计划与验收](docs/plans/2026-09-02-mvp-phase-19-load-test-harness.md)
- [Phase 20 结构化上下文确认](docs/context-input.md)
- [Phase 20 上下文确认计划与验收](docs/plans/2026-09-02-mvp-phase-20-context-input-confirmation.md)
- [Phase 21 MVP 固定评测集](docs/mvp-evaluation.md)
- [Phase 21 固定评测与回放计划](docs/plans/2026-09-02-mvp-phase-21-evaluation-harness.md)
- [Phase 22 Intent/Plan 契约](docs/intent-planning.md)
- [Phase 22 结构化意图与任务计划预览计划](docs/plans/2026-09-02-mvp-phase-22-intent-planning.md)
- [任务状态](TODO.md)
- [执行记录](LOG.md)

## 上游边界

`D:\Github_Storage\tradeeye-copilot` 与 `D:\Github_Storage\TradeEye` 是只读参考。Prism 不在运行时导入相邻仓库；需要的能力以小范围移植、适配器或重新实现的方式进入本仓库，并保留来源与契约测试。

Prism 当前是研究与决策支持原型，不构成证券投资建议，也不执行真实交易。
