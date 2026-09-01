# Working Plan：Prism Foundation

## Goal

以 [Prism.md](../../Prism.md) 为主项目文档，建立可恢复、可测试、可审计的独立工程基础，并完成“科技基金集中持仓体检”纵切所需的最小底座。

## Context / Constraints

- 上游 `tradeeye-copilot` 与 `TradeEye` 只读；只做小范围移植、适配或设计借鉴。
- 金融事实与 LLM 推断严格分离，缺失和 Provider 失败不得伪装成零值。
- 赛题目标包括 100 用户并发、单次投顾响应不超过 3 秒和 99.9% 可用性；必须实测，不以文档声明完成。
- SkillHub 安装/接口、数据展示、缓存、留存和限流边界尚待比赛专用材料确认。
- `Prism.md` 就是项目主文档，不创建重复的 `PROJECT.md`。

## Design

- 模块化单体 + 异步结构化研究 DAG；
- Pydantic 领域契约作为模块边界；
- Evidence-first：`Recommendation -> Finding -> Fact -> Evidence`；
- 画像、组合、风险与合规使用确定性规则；
- PostgreSQL 目标存储，Redis 用于公共缓存和短期状态；
- React/TypeScript 投研工作台，视觉语法参考 `tradeeye-copilot`。

## Scope

### Phase 0：授权与契约门

- 获取 SkillHub 比赛专用开发文档、凭据、配额、缓存及输出展示规则；
- 获取赛题评分附件；
- 确认两个上游仓库的代码复用授权；
- 固化 Reuse Matrix、ADR 和录制 Provider fixtures。

退出门槛：可以用脱敏 fixture 复现至少一个官方 Skill 的成功、空、部分和失败响应，且字段/时间/授权边界有书面记录。

### Phase 1：可信数据底座

- Phase 1A：完成 Evidence/Fact/Finding/Recommendation 契约，并按 [Gemini 执行合同](2026-09-01-mvp-phase-1-provider-protocol.md) 建立 fixture-first Provider Protocol、失败分类与并发隔离 smoke test；
- Phase 1B：在取得接口材料后建立 Wencai/Tushare live adapters；
- Phase 1B：建立数据库迁移、用户隔离和决策事件模型；
- Phase 1B：扩展 100 用户负载测试骨架，而不是最后补测。

退出门槛：缺失、无效、不适用和 Provider 失败在契约及 API 中可区分；所有可行动建议能闭包到有效证据。

### Phase 2：旗舰纵切

- 用户画像问卷、自然语言结构化提取及冲突确认；
- 持仓导入与基金/ETF 暴露穿透；
- 集中度、相关性、流动性和风险预算；
- 守稳/均衡/进取三种最小调整区间；
- 调整前后影响和 Decision Receipt。

退出门槛：相同市场证据、不同风险画像产生实质不同且各自满足约束的方案。

### Phase 3：结构化研究协作

- 宏观、行业、股票、基金/ETF 节点并行；
- Cross Validation 检查来源独立性、时间、口径和冲突；
- 关键冲突无法消解时输出不确定或 `BLOCKED`。

退出门槛：固定测试集能覆盖支持、反对、重复证据、数据过期和关键证据缺失。

### Phase 4：工作台

- 首版只完成 Portfolio、Advisor、Evidence、Risk Profile；
- 任意结论可展开 Why、Evidence、Source、Method 和 Invalidation Conditions；
- 复用视觉语法，不照搬上游股票页面结构。

退出门槛：旗舰场景能够在真实浏览器内完成，证据钻取、冲突和缺失状态均可见。

### Phase 5：硬化与交付

- 黄金案例、故障注入、用户隔离、安全和合规测试；
- 100 并发、P95 延迟、缓存冷热路径和 Provider 降级实测；
- Demo 脚本、架构说明、测试报告和部署说明。

退出门槛：只报告实测指标；短期成功率不得被描述为已经证明长期 99.9% 可用性。

## Priority Corrections

相对 `Prism.md` 原始 P0/P1 列表，执行时做两项前移：

1. `Fund/ETF` 持仓与暴露分析进入 P0，否则科技基金旗舰场景无法闭环；
2. 负载测试骨架进入 Phase 1，否则同步/缓存/用户隔离问题会在末期才暴露。

完整持久记忆仍为 P1；P0 只保存画像版本、当前会话和决策审计所需状态。

## Verification

- Unit：金融算术、Fact/Evidence、规则、状态机；
- Contract：Provider 响应、Schema、失败和缺失语义；
- Integration：fixture 驱动的完整决策链；
- Eval：画像一致性、证据覆盖、数值幻觉、风险识别、拒答正确性；
- Load：100 虚拟用户下 P50/P95/P99、错误率、缓存命中和跨用户泄漏；
- Browser：旗舰场景与证据钻取真实验收。

## Current State

- Git 仓库已初始化；
- Reuse Matrix 与 ADR 已落盘；
- Evidence Contract 首版已实现并通过 8 项单元测试；
- MVP Phase 1A Provider Protocol 执行合同已就绪，等待 Gemini 在独立分支实施；
- 真实 SkillHub 接入仍受专用材料约束，不属于 Phase 1A。
