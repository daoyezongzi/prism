# Prism MVP Phase 27：最低可转债资产卡计划

状态：`PLANNED`

日期：2026-09-02

工作树：`D:\Github_Storage\prism-phase-27`

基线：Phase 26 已验收提交 `21714f8`

## 1. 阶段目标

本阶段把 `Prism.md` 第 15 节要求的最低可转债研究能力落成一条
fixture-first、owner-scoped、可审计的本地纵切。用户能够在研究工作台选择一个
固定的合成可转债，看到正股、转股参数、债底/信用/流动性事实，看到可复算的转股
价值与溢价率，并在双来源一致时得到确定性风险摘要；来源分歧或数据退化时只能
审阅 Evidence，不能继续升级成 Fact、Finding 或风险结论。

这是一张“资产事实与风险体检卡”，不是实时行情、估值预测或交易建议。它补齐
P1 的 Convertible Bond Agent 最小资产级契约，同时保持目前主协调器、组合、合规
和 Recommendation 边界不变。

## 2. 明确做什么

### 2.1 可复现研究输入与契约

- 新增显式的 `CONVERTIBLE_BOND` research node kind 和
  `CONVERTIBLE_BOND_DATA` provider operation；它们是对现有 Provider/Research
  枚举与允许操作映射的向后兼容扩展，不改变既有四轨道矩阵的必备集合。
- 新增版本化、严格 `extra=forbid` 的 Convertible Bond 请求、模板、manifest、
  场景、节点投影、响应和风险摘要契约；所有时间带时区，所有 Decimal 输入与
  派生值必须有限，所有 owner/request/subject/period/scenario 闭合。
- 固定一个合成标的、报告期和双独立 lineage。模板只公开安全的指标标签、单位、
  风险规则和五个离线场景，不公开 fixture 原文、Provider 参数、凭据或内部路径。

### 2.2 最低资产指标

Provider 原始字段和对外 Fact 使用以下稳定 metric ID（字段名本身也是契约的一部分）：

| metric | 含义 | 来源/计算 | 单位 |
| --- | --- | --- | --- |
| `underlying_stock_price` | 正股价格 | 双源原始事实 | `CNY` |
| `conversion_price` | 转股价 | 双源原始事实 | `CNY` |
| `bond_price` | 转债价格（面值基准 100） | 双源原始事实 | `CNY` |
| `bond_floor` | 债底 | 双源原始事实 | `CNY` |
| `yield_to_maturity_pct` | 到期收益率 | 双源原始事实 | `pct` |
| `credit_rating_rank` | 信用情况的可比较序数（AA+、AA、AA- 等映射由 manifest 固定） | 双源原始事实，UI 同时展示安全评级标签 | `rating_rank` |
| `liquidity_score` | 流动性等级序数 | 双源原始事实，manifest 固定等级标签 | `score` |
| `conversion_value` | 按面值 100 的转股价值 | `underlying_stock_price / conversion_price * 100` | `CNY` |
| `conversion_premium_pct` | 转股溢价率 | `(bond_price / conversion_value - 1) * 100` | `pct` |

`conversion_value` 和 `conversion_premium_pct` 不从浏览器计算，也不接受 provider
直接伪造：服务端用有限、正数 Decimal 输入，以固定两位小数、`ROUND_HALF_UP`
计算，并将公式版本与输入 Fact ID 写入 Finding methodology/证据说明。信用等级
与流动性序数的 label 映射只来自安全 manifest；未知或越界序数阻断运行，不猜测
等级。

### 2.3 双来源与五态回放

沿用 Phase 25/26 的两个独立来源 A/B 与 `BASELINE_READY`、`SOURCE_DISAGREEMENT`、
`SOURCE_PARTIAL`、`SOURCE_EMPTY`、`SOURCE_FAILED`：

- 基线：同一期间、同一口径、两条 lineage 一致；生成全部最低指标 Fact、派生
  Finding 与风险摘要。
- 分歧：来源 B 改变一个原始数值（默认转股价），Cross-Validation 为未决，双方
  Evidence 可见但不生成任何 Fact/Finding/风险结论。
- 部分：来源 B 缺少一个必需原始字段（默认债底）；节点为 `PARTIAL`，保留已取
  Evidence，不填零、不补算。
- 空结果：来源 B 在明确期间返回 `EMPTY` 与范围说明；不把空结果转换为零值。
- 失败：来源 B 返回安全 `FAILED` issue；不伪装成 `EMPTY`，不保留原始异常、URL
  或凭据。

### 2.4 风险摘要（只表达风险，不表达交易）

使用版本化的 `convertible-bond-risk.v1`，所有规则在服务端以 Decimal 执行：

| 条件 | Finding | 严重度 |
| --- | --- | --- |
| `conversion_premium_pct > 30%` | `CONVERTIBLE_PREMIUM_WARNING` | WARNING |
| `bond_floor < 80` | `CONVERTIBLE_BOND_FLOOR_WARNING` | WARNING |
| `yield_to_maturity_pct < 0` | `CONVERTIBLE_NEGATIVE_YIELD` | WARNING |
| `credit_rating_rank >= 4`（AA- 及以下） | `CONVERTIBLE_CREDIT_RISK` | CRITICAL |
| `liquidity_score >= 3`（低流动性） | `CONVERTIBLE_LIQUIDITY_RISK` | WARNING |

风险摘要只允许 `NOT_ASSESSED`、`CLEAR`、`WATCH`、`HIGH_RISK`，并且必须完整引用
所有非 INFO Finding；不生成 HOLD/BUY/SELL、仓位、收益承诺、Recommendation、
DecisionEvent 或订单。

### 2.5 API 与工作台

- `GET /api/v1/advisor/convertible-bond-research-template`：返回安全模板与五个
  场景。
- `POST /api/v1/advisor/convertible-bond-research-runs`：接受严格 owner/request/
  subject/period/generated_at/scenario 请求，返回 owner-closed 资产卡；注入服务
  输出时重新做完整模型校验与 scope closure，漂移映射为安全错误。
- 静态工作台新增独立 Convertible Bond 区域，展示节点状态、验证统计、最低指标、
  公式说明、Finding→Fact→Evidence 链和非 READY 的可审计 Evidence；切换 owner/
  场景清空旧卡，异步序列不能写回过期响应。
- 运行只使用同源本地 API 与 fixture，不访问外网，不接在线鉴权或 LLM/Gemini。

## 3. 明确不做

- 同花顺问财/SkillHub/Tushare 真实网络 Provider、在线鉴权、凭据、重试、缓存、
  连接池、断路器、动态限流和生产级 SLA。
- 实时转债行情、赎回/回售/强赎条款、纯债估值模型、隐含波动率、期权定价、
  久期/凸性、信用迁移模型、历史回测、可转债全市场扫描或排名。
- 自然语言画像、LLM/Gemini、多 Agent 自由对话、Recommendation、组合优化、
  交易执行、真实持仓写入、DecisionEvent 持久化或 Portfolio/Risk Profile CRUD。
- 为了本卡复制上游 `tradeeye-copilot`/`TradeEye` 目录，或在运行时导入上游代码。
- 将信用/流动性缺失、冲突或无法比较的值猜成安全等级；将 `EMPTY`/`FAILED` 转成
  零值或“无风险”；让前端重算公式或改变风险状态。

## 4. 复用边界与实现策略

### 复用

- `FixtureFinancialProvider`、Provider 四态校验、递归敏感字段防护与 fingerprint。
- bounded `ResearchPlan`/executor、owner 隔离、超时安全映射和节点运行状态机。
- normalization、lineage-aware `validate_claim`/Cross-Validation、
  `build_research_evidence_pipeline`、`bridge_cross_validation` 与 `DecisionTrace`。
- Phase 26 fund card 的 manifest/template/overlay/API 注入复核/静态工作台投影结构；
  只复用边界与小型辅助函数，不复制旧业务字段或风险权重。
- 暖白、深墨、陶土橙与 Evidence 展开交互；不照搬股票页面结构。

### 新增或适配

- 为通用 research/provider 枚举增加可转债语义；在 `allowed_operations_for_node`
  建立单一兼容映射，并增加回归测试证明既有四轨道行为不变。
- 新建 `app/convertible_bond` 契约、`app/service/convertible_bond_research.py`、
  `app/fixtures/convertible_bond` 与阶段集成测试；派生公式和风险规则只在服务端
  有一个实现入口。
- 新增 API 路由、前端卡片和必要静态样式；不修改既有 Fund/Stock 卡的语义或 API。

## 5. 验收门（必须全部通过）

### 计划门

1. 本计划书先独立提交；提交前不修改业务代码。

### 契约与服务门

2. 阶段新增单元/集成测试覆盖：合法模板与请求、extra/敏感/naive 时间/owner
   越权拒绝、显式 operation/node kind、双 lineage 闭合、四态不变量、未知/越界
   rating、正数除法和有限 Decimal、公式值/舍入/输入引用、风险 Finding 全覆盖、
   trace 闭合、无 Recommendation/DecisionEvent。
3. 五个场景与 owner 隔离测试通过；任意非 READY 场景 `facts/findings=()`、
   `risk=NOT_ASSESSED`，但保留 Evidence、验证和安全 issue。
4. API 对自定义注入服务做二次模型校验和 request/scope closure；伪造类型、字段、
   owner、scenario 或 scope 必须安全返回 `CONVERTIBLE_BOND_RESEARCH_ERROR`。

### 回归与静态安全门

5. 阶段测试、全量 `pytest`、`compileall`、公开 import、前端 `node --check`、
   `git diff --check` 全部通过；现有阶段测试不能退化。
6. 运行时扫描确认无外网、LLM/Gemini、上游运行时导入、凭据、原始异常/HTML sink、
   交易或 Recommendation 旁路；wheel/打包文件包含 manifest、fixtures、服务、
   contracts 与静态资源。
7. 固定评测重复 100 次保持所有指标 1.0；本地 100 并发记录 template 与 research
   的 p50/p95/p99、错误数、owner mismatch 和存储行数，报告“fixture/ASGI 基线”
   而不外推真实市场 SLA。

### 浏览器验收门

8. 在真实本地浏览器完成模板加载、基线、分歧、PARTIAL/EMPTY/FAILED、owner 切换；
   可见指标、派生公式说明、风险状态、节点状态、Evidence lineage 与 Finding→Fact
   →Evidence 展开；控制台错误为 `[]`，无外部请求。

## 6. 阶段停止条件与后续

只有上述验收门全部通过，且独立审查已经修复所有 P0/P1 契约缺口，才把本计划状态
改为 `ACCEPTED` 并创建下一阶段新 worktree。任何实时 Provider、真实信用评级源、
强赎条款或交易/组合需求都登记为后续阶段，不在本阶段顺手实现。

## 7. 验收记录（实现后填写）

- 实现提交：待定
- 独立审查：待定
- 阶段测试：待定
- 全量回归：待定
- 固定评测/并发：待定
- 浏览器验收：待定
- 最终状态：`PLANNED`
