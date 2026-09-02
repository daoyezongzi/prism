# Prism MVP Phase 33：Scenario Simulation（P2）执行计划

状态：`PLANNED`

基线：Phase 32 已验收提交 `134efe7`（中文工作台与稳定左侧导航）；本阶段在全新
worktree `D:\Github_Storage\prism-phase-33`、分支
`codex/mvp-phase-33-scenario-simulation` 中执行。本计划提交后，下一位 agent 必须先读
完本文件，再开始实现；本阶段不回写 Phase 32 worktree，也不把计划误报为已实现。

## 1. 阶段目标与用户价值

为已经确认的风险画像和持仓快照提供一个有界、可重复的“如果……会怎样”比较：同一份
已观测输入在一个明确标注的假设覆盖层下重新计算暴露、集中度、风险预算和目标结构，
并把基线与假设结果的变化逐项列出。用户看到的是“假设改变导致哪些约束和结果改变”，
而不是一个不可核对的收益预测或买卖清单。

本阶段完成后，用户应能：

1. 先确认风险画像与持仓，再从固定的安全场景目录选择一个假设；
2. 查看基线/模拟两侧的输入锚点、假设参数、风险/暴露指标和目标权重差异；
3. 在数据部分缺失、约束不可行或画像/快照不一致时看到 `REVIEW_REQUIRED` 或
   `BLOCKED`，而不是被补零或伪装成可执行结果；
4. 沿着同一个 owner、profile version、position snapshot、方法版本和来源 ID 复核
   计算边界，并明确知道结果不是事实、Recommendation、Decision Receipt 或交易指令。

产品选择理由：普通“情景分析”常把模型输出包装成预测，用户无法区分事实、假设和
模型变化。Prism 的差异是把 `same observed evidence + changed assumption + deterministic
delta + explicit invalidation` 放在一条链上；即使不能计算，也把不能计算的原因留下来。

## 2. 明确做什么（范围内）

### 2.1 新增不可变契约

新增 `app/simulation/` 模块（命名可在实现时微调，但不得把 P2 类型塞进无关的
Provider/Recommendation 契约），至少包含以下稳定对象：

- `ScenarioSimulationId`：`BASELINE_READY`、`TIGHTER_TECH_CAP`、
  `TOP_ASSET_TRIM_10PP`、`LOOKTHROUGH_PARTIAL` 四个固定 ID，排序和序列化稳定；
- `ScenarioSimulationStatus`：`READY`、`REVIEW_REQUIRED`、`BLOCKED`。HTTP 输入契约
  错误仍由 API 映射为安全的 4xx；不要新增“把异常当成空结果”的状态；
- `ScenarioSimulationRequest`，版本固定为
  `scenario-simulation-request.v1`，字段至少为 `request_id`、`owner_id`、带时区的
  `generated_at`、完整 `RiskQuestionnaire`、完整 `PortfolioImportBundle` 和
  `scenario_id`（默认 `BASELINE_READY`）；拒绝 extra、敏感字段、跨 owner 和 naive
  datetime；客户端不能提交 profile、exposure、concentration、risk budget 或 target
  等服务端派生结果来覆盖计算；
- `ScenarioDefinition`：安全的 ID、标签、说明和假设类型；不得含 Provider 原文、
  凭据或私人持仓；
- `ScenarioAssumption`：结构化记录本次覆盖层的类型、基线值、模拟值、单位、适用
  资产/维度和解释。禁止自由文本公式和任意表达式；
- `ScenarioRunSummary`：基线或模拟一侧的 owner/profile/portfolio/snapshot、
  exposure/concentration/assessment/optimization 身份与状态、可用指标、目标摘要和
  安全 issues；数值缺失就缺失，不用 `0` 代替；
- `ScenarioMetricDiff` 与 `ScenarioTargetDiff`：每行有稳定 `metric_id`/`target_id`、
  `baseline_value`、`scenario_value`、`delta = scenario - baseline`、单位和来源维度，
  采用 Decimal 两位小数并按稳定 ID 排序；任何一侧没有可靠值时不生成虚假的 delta；
- `ScenarioSimulationTrace`：记录输入 fingerprint、基线/模拟计算身份、方法版本、
  source contribution/report ID、计算步骤和失效条件；模拟值标记为 `HYPOTHETICAL`/
  `SIMULATED`，不得升格为 `VERIFIED Fact`；
- `ScenarioSimulationResponse`，版本固定为
  `scenario-simulation-response.v1`，至少闭合 `request_id`、`owner_id`、`scenario`、
  `assumption`、`baseline`、`simulated`、`diffs`、`status`、`issues` 和 `trace`。

所有嵌套对象都必须重新通过 Pydantic 契约验证；`model_copy(update=...)`、测试注入或
未来自定义 service 不能绕过 owner、数值闭合、敏感字段和状态不变量。

### 2.2 四个固定场景的精确定义

场景目录只能由服务端提供，不能由用户输入任意 cap、脚本或自然语言公式。场景参数
作为版本化常量进入 fingerprint 和 trace：

| ID | 假设覆盖层 | 最小模板预期 | 边界 |
| --- | --- | --- | --- |
| `BASELINE_READY` | 不改变画像、持仓或规则；同一请求内部计算基线 | `READY`（若输入完整） | 用来证明模拟结果可与原始基线一一对照 |
| `TIGHTER_TECH_CAP` | 将确认画像对应的 technology cap 减少 `10.00` 个百分点，最低为 `0.00`；这是情景限值，不修改 `RiskBudget`、profile version 或问卷 | BALANCED 合成模板应能得到可比较结果；容量不足时 `BLOCKED` | 模拟专用限值必须单独标注，不能冒充 v1 风险预算规则 |
| `TOP_ASSET_TRIM_10PP` | 按确定性最大市值→稳定 ID 找出 top asset，把总组合的 `10.00` 个百分点从该资产移出，按稳定规则分配给其余已存在资产；总市值、币种和 owner 保持不变 | 合成五资产模板应返回资产/行业/Technology 的变化 | 这是假设的配置值变化，不是价格变化、成交或收益；无可移出资产时安全阻断 |
| `LOOKTHROUGH_PARTIAL` | 对已有基金/ETF 穿透快照应用固定 `80%` coverage overlay，保留原始 holding，不补零 | `REVIEW_REQUIRED`，不生成目标或 Recommendation | 没有基金穿透输入时返回明确不可适用 issue，不伪造 partial snapshot |

`TOP_ASSET_TRIM_10PP` 的分配算法必须使用 Decimal、总和闭合到原始总市值、稳定资产
ID 处理舍入余数，并生成带 scenario digest 的派生 bundle/snapshot ID，避免与观测
报告 ID 碰撞。不得改变原始对象或工作台状态；数量字段不能被解释为成交数量，界面上
要写明这是 hypothetical allocation overlay。

### 2.3 确定性计算与服务边界

新增 `app/service/scenario_simulation.py`（或等价 service）执行以下顺序：

1. 重建并确认问卷得到 profile；重新校验 request owner 与 `X-Owner-ID`；
2. 用既有 Exposure、Concentration、Risk Budget 和 `FixturePortfolioOptimizationService`
   计算基线，不信任客户端传入的派生对象；
3. 根据服务端场景定义构造不可变的 limit/portfolio/data-quality overlay；
4. 在同一计算入口重算模拟侧，并只投影可闭合的指标、target 和 issues；
5. 生成稳定的 simulation identity/fingerprint：至少包含 owner、profile identity、
   portfolio/snapshot identity、scenario ID、overlay 常量和方法版本；相同输入不能因
   wall-clock 或字典顺序不同而产生不同语义结果；
6. 通过 response contract 做最终闭包检查。

允许为 Phase 28 优化器提取一个只读的 `OptimizationLimitSet`/内部计算参数，以支持
`TIGHTER_TECH_CAP`；现有 `PortfolioOptimizationRequest/Response` 的 v1 公共行为必须
保持不变。不要复制整套优化算法，也不要把模拟专用 cap 写回 `RiskBudget`。

基线和模拟都可以复用同一份已观测 Evidence/source lineage，但模拟派生的 exposure /
target 数值不能注册成新的 `Fact`、`Finding` 或 Evidence。`LOOKTHROUGH_PARTIAL`、
Provider/输入失败和不可行约束必须保持缺失、失败、需复核和阻断的区别。

### 2.4 FastAPI 与隔离

新增两个 owner-scoped endpoint：

- `GET /api/v1/advisor/scenario-simulation-template`：返回版本化场景目录、方法版本、
  支持的 diff 维度和安全边界；不暴露 Provider fixture 原文、凭据或私人输入；
- `POST /api/v1/advisor/scenario-simulation-runs`：接收严格 request，要求
  `X-Owner-ID` 与 body/nested owner 一致，服务端重新确认 profile/portfolio，响应重新
  验证 owner、scenario、profile、snapshot 和 simulation identity。

模拟结果不写 `DecisionEventStore`、Context Memory、Recommendation 或 Receipt，不进入
公共 cache；没有数据库迁移。输入错误、未知场景、owner drift、服务内部异常均映射为
现有安全错误边界，不返回原始 traceback、请求 payload 或敏感诊断。

### 2.5 中文工作台纵切

在现有中文静态工作台增加一个“场景模拟”区域（建议新建 `#scenario-simulation`
section 和左侧导航项，以便可直接打开；若实现选择放在组合优化 section，也必须在计划
验收中保持同样的可发现性）。必须复用 Phase 32 的 `syncNavigation`，保留既有所有
hash 的 active/`aria-current` 行为，不重写导航系统。

最小 UI：

- 场景选择器：`option.value` 保持原始稳定 ID，`textContent`/`title` 显示中文说明 +
  代码；
- 运行按钮和当前状态 chip；未确认画像/持仓时明确提示先确认，不偷偷使用模板替代；
- 假设卡：显示基线值→模拟值、单位、适用维度和“假设/非交易指令”警示；
- 基线/模拟两列摘要：状态、profile/snapshot/report ID、科技权重、top asset、HHI、
  assessment/optimization 状态；
- diff 表：资产目标、暴露/集中度/预算等稳定指标的 current→scenario→delta；缺失值
  显示“未提供/需复核”，不显示 0；
- Evidence/trace 摘要和 invalidation 条件；模拟数字始终标为 `SIMULATED`，不会出现在
  Advanced Evidence 的 VERIFIED/FINDING promotion 中；
- owner、profile、portfolio 或 scenario 变化/恢复上下文时清空旧结果，并用序列号阻止
  异步旧响应写回；动态内容继续只用 DOM API/`textContent`，不引入 HTML sink、外链、
  LLM/Gemini 或新运行时依赖。

## 3. 明确不做（本阶段禁止扩张）

- 不接真实同花顺问财 SkillHub、Tushare、行情、券商账户、认证、云服务或外部网络；
- 不调用 LLM/Gemini/Agent 来生成场景、数字、权重或自然语言金融结论；不把本计划当成
  Antigravity/Gemini subagent 的运行入口；
- 不做价格预测、收益率预测、概率承诺、历史回测、Monte Carlo、相关性/协方差、流动性
  压力、税费/交易成本、最小交易单位或订单执行；这些能力另立阶段；
- 不做任意用户公式、任意 JSON overlay、脚本执行或开放式场景编辑器；本阶段只做上表
  四个可审计目录项；
- 不生成或持久化 Recommendation、Decision Receipt、DecisionEvent、再平衡订单、交易
  信号或自动调仓；不修改已确认 Profile/Portfolio/Context Memory；
- 不做 Recommendation History、Portfolio Rebalancing、Evaluation Dashboard、
  Advanced Explainability 或完整 Simulation History；
- 不改变 Phase 24/25/26/27 既有研究场景语义，不把 Research `SOURCE_PARTIAL` 等已有
  fixture 场景冒充 P2 simulation；
- 不修改 Phase 32 已验收的中文翻译、稳定枚举、错误脱敏和导航生命周期，除非为新增
  section 所需的最小注册与回归断言；不顺手做视觉重构/i18n/动画；
- 不复制 TradeEye/TradeEye Copilot 运行时代码；不修改相邻仓库、LICENSE/NOTICE 或
  远端分支。

## 4. 复用矩阵与边界

| 能力 | 复用来源 | 本阶段处理 |
| --- | --- | --- |
| 风险画像与 owner 闭合 | `app/profile`、Phase 20/23 contracts | 直接复用并重新确认；不接受客户端派生 profile 覆盖 |
| 暴露/集中度/风险预算 | `app/portfolio/exposure.py`、`app/risk` | 作为基线与模拟的同一确定性计算入口；保留四态/需复核语义 |
| 组合目标结构 | Phase 28 `app/service/portfolio_optimization.py`、`app/optimization` | 提取小型只读 limit/derived-bundle seam；不复制算法、不改公共 v1 结果 |
| 固定场景/fixture | Phase 24 `docs/research-scenarios.md`、Phase 28 optimization fixture | 只借鉴 catalog/overlay/fingerprint 模式；新 ID 独立命名空间 |
| 证据链与降级显示 | Phase 31 Advanced Evidence、`docs/advanced-evidence-ui.md` | 显示来源和失效条件；模拟派生值不升级 Evidence/Finding |
| 中文展示与导航 | Phase 32 `DISPLAY_*` 映射、`syncNavigation`、smoke | 复用映射和 hash 生命周期；稳定 option value 不得被翻译 |
| owner/异步清理 | Phase 29 Context Memory、Phase 31/32 UI guards | 为 simulation 增加独立 sequence/clear，不能绕过 owner guard |
| 上游组合/回测想法 | `docs/reuse-matrix.md` 中 TradeEye 组合状态/评估 | 只借鉴状态机、确定性排序、审计思想；不移植短线策略/历史回测 |

产品层必须持续说明：模拟是对同一观测快照的假设计算，不是新的市场事实；数据质量
下降时 Prism 的优势是拒答或待复核，而不是给出一个看似完整的数字。

## 5. 推荐实现顺序与文件地图

1. **接手检查**：在本 worktree 执行 `git status --short`、`git log -1 --oneline`，确认
   基线为 `134efe7` 且工作树只包含本计划相关变更；阅读本文件、Phase 28/31/32 契约。
2. **契约先行**：新增 `app/simulation/contracts.py`、导出模块，先写状态、owner、敏感
   字段、Decimal 闭合、diff 无幻觉和 scenario 排序测试。
3. **纯函数/服务**：新增 overlay builder 与 simulation service；为 derived bundle /
   snapshot 使用 scenario digest；给 Phase 28 优化器增加最小内部参数 seam，先证明
   旧 Phase 28 全部测试不变。
4. **API 注入边界**：在 `app/api/contracts.py`/`app/api/main.py` 增加 template/run
   endpoint、owner header guard、输出重验证和安全错误映射；确认没有 store/cache 副作用。
5. **UI**：修改 `app/api/static/index.html`、`app/api/static/app.js`（必要时
   `styles.css`），增加中文场景卡；复用 `displayScenarioLabel`、`displayDescription`、
   `text`、`syncNavigation` 和同源 fetch；不得改写现有业务结果。
6. **测试/文档**：新增 `tests/unit/test_scenario_simulation.py`、
   `tests/integration/test_phase33_scenario_simulation.py`，扩展 Phase 32 UI/static
   smoke；新增 `docs/scenario-simulation.md`，更新 README/TODO/LOG 与本计划验收记录。
7. **独立复审**：由另一人/另一审查回合按第 7 节逐项检查，优先寻找假设值被当作事实、
   simulation 输出进入 Recommendation/Store、owner 串线、稳定 ID 改写、伪造零值和
   cap 写回 RiskBudget 等 P0/P1 问题；修复后才进入验收。

建议文件地图（允许增加小型测试/适配文件，但不得借此扩大范围）：

```text
app/simulation/__init__.py
app/simulation/contracts.py
app/simulation/overlays.py
app/service/scenario_simulation.py
app/api/contracts.py
app/api/main.py
app/api/static/index.html
app/api/static/app.js
tests/unit/test_scenario_simulation.py
tests/integration/test_phase33_scenario_simulation.py
tools/scenario_simulation_smoke.cjs
docs/scenario-simulation.md
docs/reviews/2026-09-02-phase-33-scenario-simulation-review.md
```

## 6. 验收标准与必须留下的证据

只有计划、实现、独立审查、回归、文档和干净提交全部满足，才能把本计划状态改为
`ACCEPTED`。

### 契约与服务

- 四个场景目录排序、ID、标签、fingerprint 和 response identity 可重复；同一输入重复
  运行产生相同语义结果，字典顺序/请求并发不改变结果；
- 基线与模拟的 owner/profile/bundle/snapshot/report/assessment 身份闭合；跨 owner、
  naive datetime、extra、敏感字段、未知 scenario 和注入派生对象均被拒绝；
- `TIGHTER_TECH_CAP` 的模拟限值不污染 `RiskBudget` 或 profile；
  `TOP_ASSET_TRIM_10PP` 总市值/Decimal 权重/差异闭合、派生 ID 不碰撞；
  `LOOKTHROUGH_PARTIAL` 保持 `REVIEW_REQUIRED`、缺失字段/issue 真实且无 target；
- 任何非 READY 一侧都不能生成可执行 Recommendation、Fact/Finding 升级或虚假零值；
  response 的 diff 只包含两侧都有可靠值的指标。

### API/UI/安全

- template/run endpoint 的 owner header、错误映射、响应重验证和无 store/cache 副作用
  有 integration 证据；Advisor/Research/Optimization 旧 endpoint 全部保持原行为；
- 浏览器覆盖中文场景选择、原始 option value、运行结果基线/模拟 diff、READY、
  REVIEW_REQUIRED、BLOCKED、owner 切换、profile/portfolio 恢复、直接 `#scenario-simulation`
  hash、键盘焦点和异步竞态；模拟输出明确“假设/非交易指令”；
- 动态内容只进入 DOM/textContent；无外链/外部请求/console error；Advanced Evidence
  不出现新的 VERIFIED/FINDING promotion；导航既有 hash 的 active/`aria-current` 回归。

### 全量门

在 Phase 33 worktree 执行并把摘要写入 LOG/计划：

```powershell
node --check app/api/static/app.js
python -m pytest
python -m compileall -q app tools tests
git diff --check
python -m tools.evaluate_mvp --repeat 100 --json
python -m tools.provider_resilience_load_test --requests 100
python -m pip wheel . --no-deps --wheel-dir .wheel-check
node tools/scenario_simulation_smoke.cjs
git status --short
```

wheel 必须检查静态资源和 simulation 模块都在包内；临时 wheel 目录必须在验收后清理。
浏览器 smoke 必须使用本地 uvicorn，记录 `external_requests=[]`、`console_errors=[]`
和各场景关键状态；不能用静态 HTML 断言替代真实交互证据。

## 7. 独立审查清单与停止条件

审查者必须从接受的 `134efe7` 重新看 diff，并至少回答：

1. 是否任何 overlay 改写了原始事实、RiskBudget、Profile、DecisionEvent 或 Evidence
   promotion？
2. 是否任何场景把失败、EMPTY、PARTIAL、unlooked-through 或不可行约束补成 0/READY？
3. 是否 derived bundle/snapshot/report/run ID 在同一 owner 下确定且跨 scenario 不碰撞？
4. 是否 API 重新验证 nested owner、scenario、profile/snapshot identity，并隐藏 raw
   exception/敏感 payload？
5. 是否 UI 的 option value、API enum、Evidence ID 和导航 hash 仍保留稳定机器值？
6. 是否 owner 切换、Context Memory 恢复和异步旧请求会清空/阻止旧 simulation 写回？
7. 是否没有外部网络、LLM/Gemini、交易接口、新数据库表或未授权上游代码？

出现 P0/P1 契约、隔离、事实真实性、安全或回归问题时，必须修复并重跑相关门；未修复
的 P2 视觉/文案问题可以记录但不能掩盖 P1。若无法在当前范围内安全实现，应停在
`BLOCKED/REVIEW_REQUIRED` 语义并在审查中说明，不得扩大范围。

## 8. 下一 agent 的无缝交接规则

- 起点固定为 `D:\Github_Storage\prism-phase-33` / `codex/mvp-phase-33-scenario-simulation`
  / `134efe7`；先读本文件和 `README.md`、`TODO.md`、`LOG.md`，再读
  `docs/portfolio-optimization.md`、`docs/advanced-evidence-ui.md`、
  `docs/research-scenarios.md`。
- 只在本 worktree 写入；不要 reset、rebase、覆盖用户文件或操作 Phase 32 worktree；
  不 push。提交顺序建议为：计划（本提交）→ 契约/服务 → API/UI → 独立审查修复 →
  最终验收；每个中间提交都要可回退。
- 同一时间只允许一个 writer 修改该 worktree；如果交给 Gemini/Antigravity，只交付本
  计划、当前 commit 和测试证据，不假设另一 agent 继承隐藏上下文；接手者必须重新运行
  关键门并把结果写入 LOG。
- 只有在第 6 节全部通过、审查记录无 P0/P1、计划改为 `ACCEPTED`、最终 commit 已建
  立且 `git status --short` 为空后，才能开始下一独立 P2 阶段。

## 9. 验收记录（实现前留空）

本节在实现、独立审查和验证完成后填写：实现提交、审查提交/文件、测试数量、评测与
resilience 摘要、wheel entries、浏览器 smoke JSON、最终工作树状态，以及明确列出仍
未实现的真实 SkillHub、预测、交易、持久化和其他 P2 边界。当前状态为 `PLANNED`，不
得把 Phase 32 的验证数字冒充 Phase 33 证据。
