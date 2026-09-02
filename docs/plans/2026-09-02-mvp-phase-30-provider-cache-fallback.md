# Prism MVP Phase 30：Provider Cache 与显式降级计划

状态：`PLANNED`

日期：2026-09-02

工作树：`D:\Github_Storage\prism-phase-30`

基线：Phase 29 已验收提交 `fcf35ba`

## 1. 阶段目标

本阶段补齐 `Prism.md` P1 中的 Provider Cache 与 Fallback 最小可用边界。目标是让
已有的 Provider Protocol、四态结果、超时预算和并行研究执行器在本地 fixture 环境
下具备可测试的“新鲜缓存 → 主 Provider → 备用 Provider → 受控陈旧缓存”服务链，
并把每一次非直连服务明确写进结果契约。缓存和降级不能把旧数据伪装成刚刚取得的
事实，也不能把真实空结果误报成上游故障。

本阶段仍然是 fixture-first 的纵切开发：先验证协议和审计语义，再留下将来接入
SkillHub/Tushare 的稳定边界。它不宣称已获得同花顺接口或生产 SLA。

## 2. 明确做什么

### 2.1 可复用的 Provider resilience 契约

- 复用 Phase 1 的 `ProviderRequest` 规范化 fingerprint 作为唯一语义缓存键；键只由
  provider identity 与公开请求语义构成，不使用 request_id，不把 owner/profile/
  portfolio/context-memory 放入公共缓存。
- 新增显式 `ProviderServingMode`：`DIRECT`、`CACHE_FRESH`、
  `FALLBACK_PROVIDER`、`CACHE_STALE_FALLBACK`。`ProviderResult` 保留原有四态，
  同时暴露 serving mode 与受控 cache age；下游可识别“数据从哪里来、是否陈旧”。
- 新增线程安全、有界、可注入时钟的进程内 `ProviderCache` 实现：fresh TTL、
  stale grace、LRU/容量上限、深拷贝/不可变返回、按 provider+fingerprint 隔离，
  不持久化、不跨进程、不接受任意 JSON 或私人字段。
- 新增 `ProviderExecutionPolicy`/runtime adapter，把现有 `execute_with_budget`
  的超时/异常安全映射复用到主 Provider 和一次备用 Provider；主 Provider 的
  `SUCCESS`/`PARTIAL` 才允许写入缓存，`EMPTY`、`FAILED` 和无效结果不得污染缓存。

### 2.2 安全降级顺序与证据语义

- 请求先查 fresh cache；未命中再执行主 Provider。主 Provider 返回 `EMPTY` 时视为
  合法零结果，不触发 fallback，避免把“没有数据”变成另一来源的虚构数据。
- 主 Provider 发生 `FAILED`（含超时、取消、异常或非法输出）时，若配置备用 Provider，
  只执行一次备用请求；备用成功/部分结果标为 `FALLBACK_PROVIDER`，保留备用 provider
  identity，并继续通过既有 request/result 校验。
- 主、备用均失败时，若存在 stale grace 内的成功/部分缓存，返回
  `CACHE_STALE_FALLBACK`；陈旧结果在 normalization 时变为 `STALE` Evidence，因而
  不能通过要求 `VERIFIED` 的 cross-validation/bridge。没有可用缓存则保留安全
  `FAILED`，绝不返回空 records 伪装成成功。
- fresh cache 命中保持底层 `SUCCESS`/`PARTIAL` 状态但标为 `CACHE_FRESH`；每次返回
  都重绑定当前 request_id，保留原始 fingerprint/records/retrieved_at，并验证
  cache entry 未被调用方篡改。
- fallback 与 stale 的 mode、age、provider/source lineage 会在研究节点结果/API
  的安全序列化中可见；不回显异常原文、凭据、URL query secret 或内部栈。

### 2.3 研究执行器接入

- 在 `execute_research_run` 增加可选 resilience policy；没有 policy 的既有调用保持
  字节级行为不变。启用 policy 时，节点并行仍由现有 `asyncio.gather` 控制，单节点
  预算仍由 `execute_with_budget` 约束，且结果 provider identity 只允许主/备用集合。
- 让至少一个现有 fixture research path 通过该可选边界运行，并提供直接 runtime
  API 供未来 SkillHub adapter/服务层注入共享 cache；不在本阶段把全局 cache 隐式
  注入所有用户请求。
- 增加安全的命中/回源/降级统计快照（调用方可读、无 owner/raw payload），用于
  本地负载测试和后续 UI；统计不改变 DecisionEvent/Recommendation 旁路语义。

### 2.4 产品差异化

通用聊天产品往往把“刚查到、缓存命中、备用来源、旧数据”混成一句答案。Prism 将
数据服务路径和新鲜度固化在可审计 ProviderResult/Evidence 中：网络抖动时仍能给出
有限结果，但用户能看见它是备用源或陈旧缓存，并自动失去 VERIFIED 资格。可重放、
可解释的降级比静默编造确定性更值得信任，也是选择 Prism 而不是普通投顾聊天窗口
的直接理由。

## 3. 明确不做

- 不连接真实同花顺问财 SkillHub、Tushare、在线鉴权、代理、cookies、凭据或外部
  网络；不绕过风控，不声称实时数据可用。
- 不做 Redis/数据库/磁盘持久化缓存、跨进程共享、跨用户画像缓存、缓存加密、后台
  TTL 清理或分布式一致性；本阶段 cache 仅是进程内、有界、可丢弃 fixture 边界。
- 不实现完整 circuit breaker、动态限流、重试风暴抑制、连接池或生产级服务发现；
  这些是后续生产 Provider 适配阶段，备用调用严格限制为一次。
- 不缓存 `EMPTY`/`FAILED`，不自动把 stale/fallback 结果升级为 VERIFIED，不修改
  既有四态不变量、Evidence ID 算法、DecisionTrace 闭包或 Recommendation 规则。
- 不做 Advanced Evidence UI 的完整重构；本阶段只保证安全序列化所需的 mode/age
  边界，详细 drill-down 与视觉交互留给后续阶段。
- 不修改 owner-scoped context memory、profile、portfolio、订单/调仓或任何真实
  交易能力；不新增 LLM/Gemini 调用。

## 4. 复用边界与实现策略

### 复用

- Phase 1 的 `compute_request_fingerprint`、`ProviderRequest` 敏感字段拒绝、
  `ProviderResult` 四态校验、`validate_result_for_request` 和 fixture provider。
- Phase 1/7 的 `execute_with_budget` 安全 timeout/exception 映射、研究节点预算、
  `asyncio.gather` 并行执行和 Evidence normalization/DecisionTrace 闭包。
- Phase 28/29 的固定评测、负载脚本、wheel/compile/import/static scan 与真实浏览器
  验收纪律；仅复用现有暖白工作台结构，不复制外部仓库运行时代码。

### 新增或适配

- `app/providers/resilience.py`：缓存 entry/policy、LRU 有界存储、主/备用调用顺序、
  安全 mode/age 重绑定与统计快照。
- `app/providers/contracts.py` 与 `normalization.py`：增加 serving mode 元数据，
  stale 输出映射为 `EvidenceQualityStatus.STALE`，保持既有直接调用默认值。
- `app/providers/runtime.py` 与 `app/orchestration/executor.py`：增加可选 policy
  接入和主/备用 provider identity 边界；默认路径不改变。
- `tests/unit`、`tests/integration`：覆盖缓存键/owner 隔离、TTL/grace、LRU、并发、
  request_id 重绑定、EMPTY/FAILED 污染、fallback 失败、stale Evidence 与执行器
  传播；必要时增加 `tools/provider_resilience_load_test.py`。
- `docs/provider-cache-fallback.md`、README/TODO/LOG：记录契约、示例、验证结果和
  未实现的实时/生产边界。

## 5. 验收门（必须全部通过）

### 计划与复审门

1. 本计划书先于业务代码独立提交；实现后进行一次独立代码审查，修复所有 P0/P1
   的缓存污染、身份漂移、陈旧升级、跨 owner 和异常泄露问题，再写入 ACCEPTED。

### 契约与运行时门

2. 覆盖 direct/fresh/fallback/stale mode 序列化、mode/age 边界、未知字段/敏感字段、
   request fingerprint 与 request_id 隔离、主/备用 provider identity 校验。
3. 覆盖 fresh TTL、stale grace、过期失败、LRU 容量、同键并发（只允许安全结果）、
   深度不可变返回与统计快照不泄露 payload；缓存永不写入 EMPTY/FAILED。
4. 覆盖主成功、主 partial、主 EMPTY、主 timeout/异常、备用成功/partial、备用失败、
   stale fallback、无缓存失败；每条路径都保留四态语义并通过既有校验。
5. 覆盖研究执行器 policy 传播、并行节点隔离和 stale → `STALE` Evidence → bridge
   `REVIEW_REQUIRED/BLOCKED`；直接无 policy 的 Phase 29 行为必须不变。

### 回归与安全门

6. 阶段测试、全量 pytest、`compileall`、公开 import、前端 `node --check`、
   `git diff --check` 通过；Phase 29 的 `417` 项基线全部保持绿色。
7. `python -m tools.evaluate_mvp --repeat 100 --json` 保持 9/9 与所有指标 1.0；
   100 个并发语义请求记录命中、回源、fallback、stale、错误、owner mismatch 和
   cache size（本地 fixture 基线，不宣称生产 SLA）。
8. wheel 安装后包含 resilience 模块和文档；静态扫描无外网、LLM/Gemini、凭据、
   raw chat、HTML sink、订单或 Recommendation 旁路；公开 API 错误只返回安全 code。

### 浏览器门

9. 若本阶段仅做 runtime/contract，不扩大 UI；至少用真实本地浏览器验证现有工作台
   的直接路径无回归，并通过 API/fixture 观察 mode/age 与 stale 结果。Advanced
   Evidence drill-down 的完整可视交互在后续阶段单独验收。

## 6. 阶段停止条件与后续

只有所有验收门通过、复审缺口已修复、计划记录补齐并提交后，才将状态改为
`ACCEPTED`，再从该接受提交创建新的独立 worktree。实时 SkillHub、生产缓存/断路器、
Advanced Evidence UI、云持久化与认证继续作为后续阶段，不在本阶段顺手实现。

## 7. 验收记录（实现后填写）

- 计划提交：待填写（必须早于业务代码）。
- 实现提交：待填写。
- 复审修复：待填写。
- 测试/评测/负载/浏览器/wheel/静态扫描：待填写。
- 最终状态：`PLANNED`，直至所有验收门完成。
