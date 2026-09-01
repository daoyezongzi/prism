# ADR-0001：采用模块化单体和结构化研究 DAG

- 状态：Accepted
- 日期：2026-09-01
- 决策范围：首个可交付版本
- 上位规范：[Prism.md](../../Prism.md)

## 背景

项目需要在同一请求中协调用户画像、多个研究领域、证据校验、组合计算、风险和合规，并满足至少 100 用户并发、单次投顾响应不超过 3 秒的赛题目标。

两个上游仓库已经提供有价值的领域契约和工程模式，但现有路径包含同步研究循环、进程内缓存和 CSV 状态存储，不适合作为 Prism 的生产运行时。首版团队也没有必要承担微服务、服务发现和分布式事务成本。

## 决策

1. 后端采用 Python 模块化单体；HTTP 层计划使用 FastAPI，跨边界对象使用 Pydantic 契约。
2. 研究运行时采用异步、有界、结构化 DAG；专业节点通过 `ResearchState` 交换 Schema，不通过自由自然语言对话交换关键事实。
3. LLM 仅用于意图提取、有限研究归纳和语言表达；画像评分、金融计算、组合、风险及合规由确定性模块完成。
4. Provider 层统一输出带来源、期间、抓取时间和质量状态的 Evidence；Provider 失败不得被归类为空结果或零值。
5. 计划使用 PostgreSQL 保存用户隔离数据、证据、版本和决策事件；Redis 仅承担公共数据缓存、限流和短期任务状态。私人画像不得进入跨用户公共缓存。
6. 前端计划采用 React + TypeScript 的投研工作台；只复用 `tradeeye-copilot` 的视觉和交互语法，不复用其股票业务信息架构。
7. 首版不拆微服务，不引入 Kubernetes，不构建自由聊天式多 Agent 系统。

## 请求路径

```text
User Request
    -> Profile and position lookup
    -> Structured planning
    -> Parallel provider/research nodes
    -> Evidence normalization and validation
    -> Deterministic portfolio/risk/compliance
    -> Recommendation composition
    -> Decision receipt and audit event
```

公共市场、宏观、行业和基金持仓数据优先预计算。请求路径只允许有界 Provider 调用；超时后使用标注新鲜度的可接受缓存，或显式返回 `UNAVAILABLE`/`BLOCKED`，不以异步任务响应冒充已经满足 3 秒完整响应目标。

## 影响

正面影响：

- 可以直接复用 Python 领域模型和规则模式；
- 单仓库内可快速完成纵向闭环和端到端测试；
- 事务、用户隔离和版本追踪比 CSV 更明确；
- 将来可根据观测数据拆出 Provider worker，而非预先猜测服务边界。

代价：

- 必须重写上游同步运行时；
- 模块边界需要通过导入规则和契约测试保持；
- 3 秒目标依赖预计算、缓存命中率和外部 Provider 实测，不能只靠架构声明。

## 复审条件

仅在负载测试证明单体中的某一明确边界无法独立扩缩容，或部署/故障域确有要求时，才评估拆分服务。复审必须附带性能或运维证据。
