# Implementation Architecture

本文档描述 [Prism.md](../Prism.md) 的首版落地边界。产品范围和系统不变量以 `Prism.md` 为准；关键架构选择记录于 [ADR-0001](adr/0001-modular-monolith.md)。

## 模块边界

计划中的模块化单体结构：

```text
app/
├── api/               HTTP、认证、租户和错误映射
├── contracts/         跨模块不可变 Pydantic 契约
├── orchestration/     有界异步 DAG、预算、超时和取消
├── profile/           问卷、结构化提取、冲突确认和版本
├── providers/         Wencai、Tushare 与录制 fixture
├── evidence/          registry、质量、新鲜度和 lineage
├── validation/        口径对齐、交叉验证与分歧
├── research/          macro、industry、stock、fund/etf
├── portfolio/         暴露、约束、情景和最小调整
├── risk/              独立风险规则与压力场景
├── compliance/        独立适当性与输出守卫
├── recommendation/    组合结构化结果，不创造事实
├── store/             用户隔离、证据、事件和版本
└── service/           用例边界
```

当前只创建已经具有可测试行为的包；不使用空目录伪装完成度。Phase 13
新增 `app/store` 的 owner-scoped SQLite 决策事件 adapter 和 `app/api` 的
FastAPI/静态工作台边界；Phase 14 新增 `app/service` 的结构化 fixture-first
Advisor query 编排，并把结果保存回同一 DecisionEvent 边界。真实认证、
PostgreSQL、SkillHub 网络和生产级 Provider 仍未实现。Phase 15 在同一边界上增加
owner-scoped query template 与结构化表单；它不改变服务端决策链，也不引入自然语言
或交易入口。Phase 16 增加 `ResearchSpecialistMatrix` 和 fixture-first 四轨道
（Macro/Industry/Stock/FUND）配方；它复用同一 bounded executor、Cross Validation
和 Evidence/Finding bridge，不复制状态机，也不宣称实时专员或 LLM 已接入。Phase 17
增加 Research Tracks 的 owner-scoped template/run API 与静态可解释视图；矩阵结果
仍不进入 DecisionEvent，不产生 Recommendation/Receipt，且切换 owner 会清空研究
状态。

## 数据流

```text
Request + Profile Version + Position Snapshot
                         |
                         v
                 Structured Task Plan
                         |
              bounded parallel execution
          / macro / industry / stock / fund-etf \
                         |
                         v
                 Evidence Registry
                         |
             normalize -> validate -> align
                         |
                         v
                Fact and Finding Graph
                         |
             portfolio -> risk -> compliance
                         |
                         v
           Recommendation + Decision Receipt
```

Orchestrator 只规划、调用、收集和检测缺失；它不计算金融指标，也不能绕过 Evidence Contract。

## 数据与失败语义

Provider 统一返回四类结果：

- `SUCCESS`：取得可验证记录；
- `PARTIAL`：有数据，但缺少完成当前任务所需字段；
- `EMPTY`：请求成功且在明确范围内确实没有记录；
- `FAILED`：超时、限流、鉴权、解析或服务错误。

`EMPTY` 与 `FAILED` 永不互换。`FAILED` 不产生零值 Fact，`PARTIAL` 不得被提升为完整证据。

## 3 秒请求预算

目标以 P95 端到端延迟衡量，而不是平均值。初始预算：

| Stage | Budget |
|---|---:|
| 请求解析、认证和画像读取 | 200 ms |
| 结构化规划 | 250 ms |
| 并行数据/研究节点 | 1,200 ms |
| 验证、组合、风险、合规 | 450 ms |
| 结构化表达和序列化 | 600 ms |
| 网络与余量 | 300 ms |

实现策略：

- 宏观、市场、行业、基金持仓等公共数据预计算；
- 所有外部调用有超时、连接池、并发上限和熔断；
- 缓存键包含数据口径和版本，返回时显示新鲜度；
- 冷路径无法在预算内完成时显式降级，不把后台刷新当成完整响应；
- 负载测试从 Provider Protocol 阶段开始，持续记录 P50/P95/P99 和错误分类。

## 用户隔离与审计

- 所有画像、持仓、会话和决策事件绑定 `owner_id`；
- 公共缓存不得包含用户画像、持仓或生成的个性化建议；
- Decision Receipt 保存画像版本、持仓快照、证据 ID、规则版本、模型版本和生成时间；
- 日志禁止记录凭据和完整私人持仓；
- 后续回放使用当时快照，不用新数据静默重算历史建议。

## Web 工作台

首版只实现四个核心区域：

- Portfolio：当前持仓、穿透暴露和调整前后对比；
- Advisor：任务、研究节点状态和三类调整方案；
- Research Tracks：四类研究节点、独立 lineage 验证和 Finding → Fact → Evidence；
- Evidence：证据回执、来源、期间、新鲜度和冲突；
- Risk Profile：画像参数、置信度、冲突及其对建议的实际影响。

视觉上复用暖白、深墨、陶土橙、衬线标题、等宽数字、低阴影和固定工作台层级。业务结构围绕“持仓到调整单”，不照搬股票分析卡片。

## 当前实现边界

已经实现 Evidence、Provider、画像/持仓、暴露/风险、研究、合规闸门、
Recommendation/Decision Receipt、Phase 13 的本地决策事件存储/FastAPI/首个
解释工作台、Phase 14 的 API 触发 fixture-first Advisor 纵切、Phase 15 的结构化
Query 工作台、Phase 16 的四轨道研究节点矩阵、Phase 17 的 Research Tracks API/UI
切片，以及 Phase 18 的只读 Portfolio 快照/Risk Profile 问卷上下文视图。真实
SkillHub/Tushare、身份认证、生产 PostgreSQL、专用多研究 Agent、Portfolio/Risk
Profile CRUD、真实持仓导入和外部真实旗舰流仍未完成；README 与 TODO 必须持续保持
这一事实边界。
