# Phase 30 Provider Cache/Fallback 复审

日期：2026-09-02  
工作树：`D:\Github_Storage\prism-phase-30`  
计划提交：`29c6982`  
实现提交：`a2df871`  

## 复审方法

按 Provider Protocol、四态不变量、缓存键/生命周期、fallback 顺序、owner/private
隔离、Evidence 质量、API 投影和现有回归边界逐项阅读实现与新增测试；然后运行全量
pytest、固定评测、100 请求 resilience smoke、compile/import、wheel 安装、静态边界
扫描和真实本地浏览器研究矩阵路径。

## 发现与修复

### R1 — provider 输出中的私人字段可能进入公共 cache（P1，已修复）

初版只拒绝了 request 侧的 owner/profile 等语义和 result 侧的 credential 关键字，
provider record 若携带 `owner_id`/`portfolio` 等字段仍可能被写入公共 cache。
`3972f40` 增加 result payload 的递归 private-context 扫描；命中即 bypass，不影响
直连执行，并新增回归测试。

### R2 — 节点 API 投影会丢失 serving provenance（P1，已修复）

底层 `ProviderResult` 与 `ResearchNodeResult` 已有 mode/age，但矩阵、个股、基金和
可转债的 public node response 初版只返回状态/issue，用户无法审计 fallback 或 stale。
`1541fce` 将 provider、`provider_serving_mode`、`provider_cache_age_ms` 加入四类
response contract 与 service/API 投影，并增加 API 回归测试。

## 复审结论

- 未发现仍开放的 P0/P1 缓存污染、request identity drift、跨 owner 泄露、EMPTY 被
  fallback 覆盖、FAILED 伪装、stale 升级为 VERIFIED 或原始异常泄露问题。
- 进程内 cache 是有界 LRU；只有经过 request/result 校验的 SUCCESS/PARTIAL 可写入；
  cache 命中重绑定当前 request_id，fallback 只调用一次并共享总 timeout；stale 只在
  grace 内返回并变成 `STALE` Evidence。
- 无 policy 的 Phase 29/既有 direct path 保持默认 `DIRECT` 行为；真实 SkillHub、
  生产持久化 cache、circuit breaker、动态限流和完整 Evidence UI 仍按计划排除。

## 复审验证

- Phase 30 tests：`12 passed`；全量测试最终数字记录于计划验收段。
- `python -m compileall -q app tools tests`、公开 import、`node --check`、
  `git diff --check`：通过。
- `python -m tools.evaluate_mvp --repeat 100 --json`：9/9，所有指标 `1.0`。
- `python -m tools.provider_resilience_load_test --requests 100`：fresh/stale 各
  100/100 成功，fresh/stale mode 各 100，错误 0，request IDs 唯一，cache entries 1。
- wheel 构建并隔离安装后可导入 `InMemoryProviderCache`/`ProviderExecutionPolicy`；
  真实本地浏览器运行四轨道矩阵，状态 `READY`、cards 8、外部请求 0、console errors `[]`。

结论：复审发现已全部修复，待最终验收记录补齐后可将 Phase 30 计划标记为 `ACCEPTED`。
