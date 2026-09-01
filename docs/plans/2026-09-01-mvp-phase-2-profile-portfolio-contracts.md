# MVP Phase 2 Working Plan：Profile and Portfolio Import Contracts

- Status：`ACCEPTED`
- Owner：Codex
- Reviewer：Codex + user
- Target branch：`codex/mvp-phase-2-profile-portfolio-contracts`
- Source of truth：[Prism.md](../../Prism.md)
- Parent plan：[Prism Foundation](2026-09-01-foundation.md)
- Prerequisite：Phase 1 Provider Protocol and Hardening accepted at `84bbe3b`

## Goal

建立旗舰纵切的两个输入边界：

1. 用户风险画像可以由固定问卷规则确定性评分，并能承载结构化提取结果与冲突确认；
2. 当前持仓以及基金/ETF 的原始穿透持仓可以被严格、不可变、可审计地导入。

本阶段只固定后续 Phase 3（暴露、风险预算和最小调整）的输入契约，不生成投资建议。

## Product rationale

Prism 的差异化不是“更会聊天”，而是让同一组市场证据经过不同用户画像后产生可解释的约束差异。Phase 2 只负责把画像、持仓快照和基金/ETF 原始持仓证据固定下来，保证后续调整可以回答“为什么这个用户和另一个用户不同”。

## Context / constraints

- Phase 1 Provider/Evidence 契约是上游边界，不修改其模型和现有 Evidence Contract。
- `Prism.md`、`docs/architecture.md`、`docs/reuse-matrix.md` 为只读产品/架构依据；本计划不重写它们。
- 只使用标准库、现有 Pydantic 和 pytest，不新增生产依赖。
- 上游 `tradeeye-copilot` 与 `TradeEye` 只读；借鉴其严格 Fact/状态/稳定 ID 模式，不运行时导入或整目录复制。
- 私人对象必须带 `owner_id`；测试和 fixture 只使用合成身份与虚构资产，不记录原始自然语言、凭据或真实持仓。
- 所有跨模块模型保持 `extra="forbid"`、不可变、时区明确；金额、数量和权重使用 `Decimal`，避免二进制浮点误差。

## In scope

### Profile

- `RiskQuestionnaire`：固定维度、范围校验、时区和版本字段。
- 确定性风险评分：固定权重、固定枚举映射、稳定的 `risk_score` 与 `risk_level`。
- `ProfileExtractionProposal`：只接受结构化候选值和不可逆输入摘要，不实现 LLM 或自然语言解析。
- `ProfileConflict` / `ProfileDraft`：检测问卷与结构化提取不一致，并要求显式解决后才能生成 `RiskProfile`。
- `RiskProfile`：输出后续 Portfolio/Risk 模块需要的风险等级、期限、最大回撤容忍度、流动性、经验、偏好、排除项和置信度。

### Portfolio import

- `Position` 与 `PositionSnapshot`：稳定资产/记录身份、数量、市场价值、币种、来源、观测时间和 owner 隔离。
- `PositionImportResult`：明确 `COMPLETE`、`PARTIAL`、`EMPTY`、`FAILED`，并区分缺失、失败和真实空持仓。
- `LookThroughHolding` 与 `FundHoldingSnapshot`：保存基金/ETF 的原始成分及权重、期间、来源和覆盖率，不计算组合暴露。
- `PortfolioImportBundle`：校验持仓快照与基金/ETF 穿透快照的 owner、父资产和身份闭合。
- 合成 fixture 和契约/集成测试，证明 Phase 3 可安全消费这些输入。

## Explicitly out of scope

- LLM、自然语言模型调用、Prompt、Embedding 或在线鉴权。
- 真实 SkillHub/Tushare/行情请求和任何 API key。
- PostgreSQL、Redis、文件持久化、迁移、FastAPI、Web UI、会话记忆。
- 行业/基金穿透后的组合暴露、集中度、相关性、流动性、风险预算、配置优化和推荐文案；这些属于 Phase 3+。
- 研究 DAG、Orchestrator、Cross Validation、Risk Engine、Compliance Guard、Decision Receipt。
- 修改 `Prism.md`、`app/contracts/evidence.py`、已有 Evidence 测试、上游仓库或现有 Provider 语义。

## Design decisions

### Deterministic profile scoring

`RiskQuestionnaire` 使用 5 个 1–5 离散维度：损失承受、投资期限、流动性需求、投资经验、收益预期。除流动性需求反向计分外，其余维度按固定权重归一化为 0–100：

```text
loss_tolerance       30%
investment_horizon   25%
liquidity_capacity   20%  (liquidity_need 反向)
experience           10%
return_expectation  15%
```

风险等级阈值固定为：`0–33 CONSERVATIVE`、`34–66 BALANCED`、`67–100 GROWTH`。最大可接受回撤是独立输入，不由 LLM 或随机规则推断。权重、映射和阈值必须有单元测试。

### Conflict semantics

- 问卷是确定性基线；结构化提取只能提出候选值。
- 候选值与问卷在同一维度不一致时生成 `UNRESOLVED` conflict。
- 未解决冲突不得产出最终 `RiskProfile`；只能返回需要确认的 Draft。
- 解决方式必须明确选择问卷值或提取值，并保留冲突记录；不静默覆盖。
- 原始自然语言不进入模型、fixture、日志或 fingerprint，只保存输入摘要用于审计关联。

### Position and look-through semantics

- `PositionSnapshot` 是某一 owner 在一个明确时间点的原始持仓快照；不在导入层计算占比或行业暴露。
- Position 与 holding 的 ID 必须稳定且不可重复；重复记录、空身份、非正数量和非法权重拒绝。
- `FundHoldingSnapshot` 的权重是来源报告值；`coverage_pct` 只描述来源覆盖范围，不被解释成完整组合暴露。
- Empty import 是“明确范围内没有持仓”，Failed import 是“没有可靠完成”，不得互相转换。
- 任何 bundle 中的私人快照都必须属于同一个 `owner_id`；公共基金成分仍通过父持仓绑定进入用户 bundle。

## Proposed file boundaries

允许新增或修改：

```text
app/profile/__init__.py
app/profile/contracts.py
app/profile/scoring.py
app/portfolio/__init__.py
app/portfolio/contracts.py
app/portfolio/validation.py
tests/unit/test_profile_contracts.py
tests/unit/test_profile_scoring.py
tests/unit/test_portfolio_contracts.py
tests/integration/test_phase2_contracts.py
tests/fixtures/profile/*.json
tests/fixtures/portfolio/*.json
docs/profile-portfolio-contracts.md
README.md
TODO.md
LOG.md
```

不得修改：

```text
Prism.md
app/contracts/evidence.py
tests/unit/test_evidence_contract.py
docs/evidence-contract.md
D:\Github_Storage\tradeeye-copilot\**
D:\Github_Storage\TradeEye\**
```

## Required acceptance cases

### Profile

1. 问卷维度范围、枚举和时区非法时被拒绝。
2. 相同问卷输入得到相同 score、level 和序列化结果。
3. 低风险与高风险问卷得到不同风险等级和分数。
4. 问卷评分不依赖自然语言或随机状态。
5. 结构化提取与问卷冲突时生成 unresolved conflict。
6. 未解决冲突不能生成 `RiskProfile`。
7. 显式选择问卷值/提取值后才能生成 profile，并保留冲突记录。
8. profile 不记录原始自然语言或敏感字段。

### Portfolio import

9. 位置、数量、金额、币种、时间和稳定身份非法时被拒绝。
10. 同一快照中的重复 position/holding identity 被拒绝。
11. COMPLETE/PARTIAL/EMPTY/FAILED 的序列化和不变量清晰分离。
12. 缺失持仓与真实空持仓不被转换为零金额持仓。
13. 基金/ETF holding 权重在 0–100 且覆盖率语义可审计；不计算暴露。
14. bundle 拒绝 owner 不一致、未知 parent asset 和重复父快照。
15. 合成 Phase 2 bundle 可以被后续模块读取，且没有网络或凭据。
16. 原有 50 项 Phase 1/Evidence 测试继续通过。

## Verification commands

```powershell
python -m pytest
python -m compileall -q app
python -c "from app.profile import RiskProfile; from app.portfolio import PositionSnapshot; print('phase2-import-ok')"
git diff --check
git status --short --branch
```

另外运行独立反例脚本检查冲突、owner 串线、重复 ID、非法权重、真实空持仓与非 JSON/敏感输入，并审阅最终 diff 与 fixture 内容。

## Stop conditions

- 需要修改 Phase 1 Provider/Evidence 契约或 `Prism.md`。
- 需要真实网络、凭据、新生产依赖或数据库。
- 必须把自然语言/LLM 输出当作未经确认的事实才能继续。
- 无法区分 EMPTY、FAILED、PARTIAL 或无法保持 owner 隔离。
- 需要实现 Phase 3 的暴露、风险或配置算法才能通过当前验收。
- 基线测试失败且无法证明是本阶段新增范围造成。

## Definition of done

- 所有 16 个验收案例有自动化测试并通过，Phase 1 的 50 项测试仍通过。
- Profile 评分、冲突确认、Position/holding import 都有实际反例证据。
- 文档、TODO、LOG 与实际完成度一致；未声称 Phase 3 或真实数据源已实现。
- 只生成一个本地 Phase 2 提交，不 push，工作区干净。
- 完成独立复审并明确列出剩余风险；只有通过后才创建 Phase 3 计划书。
