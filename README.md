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

尚未实现：

- 真实同花顺问财 SkillHub Provider 网络接入；
- 实时自然语言画像提取、研究编排、组合暴露/风险/合规计算模块；
- Web 工作台与真实端到端场景；
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
- [任务状态](TODO.md)
- [执行记录](LOG.md)

## 上游边界

`D:\Github_Storage\tradeeye-copilot` 与 `D:\Github_Storage\TradeEye` 是只读参考。Prism 不在运行时导入相邻仓库；需要的能力以小范围移植、适配器或重新实现的方式进入本仓库，并保留来源与契约测试。

Prism 当前是研究与决策支持原型，不构成证券投资建议，也不执行真实交易。
