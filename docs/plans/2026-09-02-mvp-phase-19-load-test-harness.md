# Working Plan：MVP Phase 19 早期负载测试骨架

## Goal

在已经接受的 fixture-first 纵切上建立一个可重复、可审计的早期负载测试工具，
记录本地 app/API 在并发请求下的 P50/P95/P99、错误分类、owner 隔离和持久化副作用。
这一步补齐 `Prism.md` 要求的 benchmark/measure/record 基础，但只报告当前合成
fixture 和本地运行时的事实，不把 ASGI 进程内结果包装成真实 100 用户、3 秒或 99.9%
可用性承诺。

## Context / constraints

- `Prism.md` 是唯一产品规范；Phase 18 接受提交为 `1bcaddb`，本阶段必须在新的
  `D:\Github_Storage\prism-phase-19` worktree 完成，并先提交本计划。
- Phase 2–18 的 Provider、Research、Advisor、DecisionEventStore、owner dependency
  和 API contract 是唯一被测对象；负载工具不能复制业务逻辑、重算金融数值或绕过
  现有 gate/trace。
- 负载测试默认使用 `create_app` + `httpx.ASGITransport` 的本地进程内链路，使用
  固定合成请求与唯一 owner；它不自动访问互联网、SkillHub/Tushare、真实账户或外部
  URL。若将来支持已启动的本地 URL，也必须显式传入并在输出中标记为 local-only。
- 指标必须保留请求总数、完成数、错误数、状态分布和耗时样本；不能只输出平均值，
  不能在失败时以 0 或成功替代缺失值。

## In scope（本阶段必须完成）

### 1. Reusable load-test runner

- 新增 `tools/load_test.py`（及必要的 `tools` 包入口），提供可从命令行和测试调用
  的 runner；不改变 `app/` 生产模块的业务路径。
- 支持三个已有 API 场景：
  - `template`：owner-scoped `GET /api/v1/advisor/query-template`，验证只读模板读取；
  - `research`：`POST /api/v1/advisor/research-runs`，验证四轨道 READY、8 节点和
    不写入 DecisionEvent；
  - `advisor`：`POST /api/v1/advisor/queries`，验证既有 Advisor 纵切和 owner-scoped
    DecisionEvent 写入。
- 使用 `asyncio` 并发调度，支持 `--concurrency`、`--requests-per-user`、`--scenario`
  和可选的 `--json` 输出；每个虚拟用户使用确定性 owner/query/request ID，避免把
  相同请求去重误认为吞吐。
- 输出版本化 JSON 记录：scenario、transport、configured concurrency、total/
  completed/failed、status counts、wall-clock duration、request latency 的
  `min/p50/p95/p99/max`、错误码分类、owner mismatch 数和 store rows before/after。
  空样本、无效参数和执行异常必须显式失败。

### 2. Contract-level load assertions

- 增加 Phase 19 测试覆盖 percentile 边界、参数校验、100 个并发模板/研究请求的
  owner 闭合和确定性响应；Advisor 场景验证每个 owner 最多一条预期事件且没有跨
  owner 返回。
- 负载 runner 不吞异常：HTTP 非 2xx、响应 owner 不匹配、研究状态不是 READY、
  模板缺少 owner/portfolio 或 store 副作用超出预期都进入失败计数并在最终退出码中
  体现。
- 在受控本地 runner 中记录一次基准输出，测试只断言结构、闭合和错误语义，不硬编码
  机器相关的毫秒数，不把本地快于 3 秒当成 SLA 证明。

### 3. Documentation and boundary record

- 新增 `docs/load-test.md`，说明 runner 用法、场景、指标定义、ASGI transport 与
  真实部署的差异、失败分类、owner/存储副作用解释及禁止外推的结论。
- 更新 README/TODO/LOG/architecture，记录 Phase 19 的真实结果和下一阶段边界；
  明确真实外部 Provider、缓存/连接池/断路器、生产数据库、认证、云压测和 SLA 仍未
  实现。

## Out of scope（明确不做）

- 真实 SkillHub/Tushare/Wencai 网络、在线鉴权、真实用户数据、外部压测平台、云部署
  或公网 URL；不伪造 100 用户、3 秒 P95、99.9% 可用性结论。
- Provider cache、连接池、重试、断路器、动态限流、后台队列、分布式 tracing、
  PostgreSQL/Redis、持久化迁移或生产监控告警。
- 修改 Advisor、Research、Provider、Risk、Gate、Recommendation、Receipt 或
  Portfolio 业务规则；不新增金融公式、目标价、交易/再平衡入口。
- 前端 UI、自然语言/LLM/Gemini、画像抽取、真实持仓导入和新的工作台交互；本阶段
  不要求重复 Phase 18 浏览器验收，但必须保持已有 UI/静态测试回归通过。

## Reuse boundary

- 复用 Phase 13–18 的 `create_app`、统一错误响应、`AdvisorQueryRequest`、
  `ResearchSpecialistMatrixRequest`、`AdvisorQueryTemplateResponse` 和
  `SQLiteDecisionEventStore`；runner 只做 HTTP 请求编排与响应断言。
- 复用 Phase 1 的 asyncio fixture concurrency 语义、Phase 7–10 的 bounded/research
  四态降级语义和 Phase 14–18 的 owner-scoped replay/隔离测试；不另造并行执行器或
  业务状态机。
- 复用现有 `httpx` dev 依赖和标准库 percentile 计算；不为一次性 benchmark 引入
  第三方压测框架。
- `tradeeye-copilot`/`TradeEye` 仅作只读工程参考，不导入其策略、行情或交易 API。

## Product differentiation

同类产品常用一个“响应很快”的平均数掩盖慢请求、失败和跨用户污染。Prism 的负载
基线把延迟分位数、错误状态、owner 闭合和 DecisionEvent 副作用放在同一份记录中：
用户选择 Prism 不只因为结果可解释，也因为系统在压力和退化时仍诚实地说明哪些数据
没有完成、哪些请求被拒绝、以及结论是否仍可复核。可审计性能证据与拒绝伪造 SLA
是本产品相对只展示漂亮响应时间的产品的差异。

## Acceptance gates

1. 计划先于实现提交，所有修改只位于从 Phase 18 `1bcaddb` 创建的独立 Phase 19
   worktree；不修改 Phase 18 或 main worktree。
2. runner 支持三个既有场景和确定性参数，输出版本化、可机器读取的完整指标；空样本、
   非法参数、HTTP/契约/owner/store 错误均不会被隐藏或伪装为成功。
3. 100 并发模板与 Research 请求在本地 ASGI transport 下保持 owner/ID 闭合；Advisor
   场景只产生每个预期 owner 的事件，研究/模板场景不产生事件；错误分类可回放。
4. Phase 19 单元/集成测试、旧全量回归、compile/import、runner CLI smoke、
   `git diff --check` 和 package/static 边界检查通过；只允许已知 Starlette/httpx
   deprecation warning。
5. benchmark 输出至少包含 P50/P95/P99 和错误/副作用证据；文档清楚标注进程内
   fixture 基线不等于真实外部 SLA，不以本地数字宣称比赛指标达标。
6. 独立审查确认 runner 没有网络 Provider、LLM、订单、金融重算、跨 owner 泄露或
   失败吞没；修复后才把计划标记 `ACCEPTED`，再创建下一阶段 worktree。

## Handoff / stop conditions

- runner 或任何被测 API 出现非 2xx、owner mismatch、错误状态丢失或不预期写入时，
  先修复/记录，不能通过放宽断言“让压测通过”。
- 负载结果若受当前机器、ASGI transport 或 fixture 限制，只记录事实和限制，不人为
  调整样本或延迟；真实 Provider/生产性能需要后续获得授权、文档和部署环境后另立
  阶段。
- Phase 20 只能从 Phase 19 接受提交创建新 worktree，并先提交计划书。

## Status

`ACCEPTED`

## Acceptance record (2026-09-02)

- Worktree: `D:\Github_Storage\prism-phase-19`, branch
  `codex/mvp-phase-19-load-test`; plan commit `6ab60c8` preceded implementation.
  Implementation commits are `b77cd16` and `dc23e01`.
- Added reusable `python -m tools.load_test` runner with `template`, `research` and
  `advisor` scenarios. It reports versioned JSON with logical operations, actual HTTP
  request count, completion/error categories, status counts, operation latency
  min/P50/P95/P99/max, owner mismatches and store row deltas. Advisor measures the
  existing template→query path; no production business module was changed.
- Added nine Phase 19 tests covering percentile/empty samples, workload validation,
  100-concurrent template and Research owner closure, Advisor event scope, CLI smoke,
  HTTP failure classification, sensitive error rejection and owner mismatch detection.
- Full regression: `python -m pytest -o addopts=` → `276 passed`, with only the known
  Starlette/httpx deprecation warning. `compileall`, public imports, CLI smoke,
  `git diff --check` and final wheel package-data checks pass.
- Final local ASGI fixture baselines (100 concurrent, one operation per owner):
  template P50/P95/P99 `81.790/93.394/95.937 ms`, Research
  `578.552/796.039/807.497 ms`, Advisor end-to-end template→query
  `873.164/1419.673/1451.030 ms`; all completed with zero owner mismatch and zero
  errors. Advisor used 200 HTTP requests and stored 100 owner-scoped events; the other
  two scenarios stored none.
- Boundary review confirms the runner uses only in-process `httpx.ASGITransport` and
  the existing app/API contracts; no external Provider, LLM/Gemini, credentials,
  financial recalculation, order/trade path or raw exception/response leakage was added.
  The measured numbers are local fixture baselines only, not evidence of real 100-user,
  3-second or 99.9% production SLA compliance.
- Phase 19 is accepted locally; no push was performed. Phase 20 must start in a new
  worktree with a plan-only commit.
