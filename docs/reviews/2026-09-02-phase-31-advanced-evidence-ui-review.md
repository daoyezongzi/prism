# Phase 31 Advanced Evidence UI review

日期：2026-09-02  
审查基线：Phase 31 implementation `fd56d19` 及后续修复  
审查范围：`app/api/static/index.html`、`app/api/static/app.js`、`app/api/static/styles.css`、
静态契约测试、浏览器 smoke、owner/run 生命周期与 Phase 30 provenance 投影。

## 审查方法

- 阅读 explorer 的聚合、排序、筛选、详情和 reset 调用链，沿现有 `state.ownerId`、
  sequence guard、`renderEvidence` 与四类 research renderer 追踪结果生命周期。
- 用同源本地 headless 浏览器覆盖五类来源轨道；用 route interception 只在浏览器内将
  fixture response 改成 `CACHE_STALE_FALLBACK`/`STALE` 与 `FALLBACK_PROVIDER`，验证 UI
  文案和 cache age，不改变服务端实现。
- 静态扫描 `innerHTML`/`outerHTML`/HTML sink、外部 URL、LLM/Gemini、凭据字段和 raw
  exception；运行前端语法、静态契约、全量回归和既有 evaluator/resilience load。

## Findings and fixes

### P1 — 同一 Provider 的多节点可能错误继承 provenance

首版按 `provider` 取第一个 node；Phase 30 fixture 的多个轨道共享 provider identity，
如果不同 node 的 serving mode/age 不同，Evidence 详情可能显示错误的 cache age。修复
提交 `fba69ec` 优先用 `evidence.source` 包含的 node identity 匹配，再回退到 provider
匹配；fallback mode 使用 review 样式，不暗示自动可信。

### P1 — Context Memory 显式恢复仍保留旧 selected receipt

恢复结构化上下文后，旧 Advisor event 原本仍在 selected 状态，explorer 会把旧 owner
上下文派生的证据继续展示。修复提交 `467bfb5` 在恢复清理边界清空 selected event、
detail、Evidence chain 和 explorer selection，恢复后必须重新运行 Advisor。

### P1 — 决策列表刷新失败时旧回执会残留

如果同一 owner 刷新 `/decision-events` 失败，旧 selected receipt 可能继续出现在详情
与 explorer。修复提交 `29e1d23` 在请求开始即清空 selected receipt、detail 和 loading
状态；失败时不保留上一轮回执。

### P2 — 标题替换破坏既有静态契约

首版将 `Evidence chain` 完全替换为 `Evidence explorer`，Phase 13 的静态 workbench
回归因此失败。修复提交 `467bfb5` 使用 `Evidence chain explorer`，保留原有可解释链
语义，同时新增 explorer controls。

其余检查未发现 P0/P1 缺口：owner mismatch 被丢弃；stale/fallback 不升级为 VERIFIED；
未闭合 trace 显示 Available/需复核；所有动态内容使用 DOM/textContent；无外部请求或
HTML sink；cache hit 不改 retrieved_at，详情明确显示 cache age。

## 审查结论

上述 P1/P2 均已修复并由阶段测试、浏览器 smoke 或全量回归复验。未发现需要阻止
Phase 31 验收的剩余缺口。实时 SkillHub、后端索引、认证、持久化/云同步、自动刷新和
Recommendation 旁路仍按计划明确排除。
