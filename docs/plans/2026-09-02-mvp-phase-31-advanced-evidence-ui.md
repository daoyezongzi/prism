# Prism MVP Phase 31：Advanced Evidence UI 计划

状态：`ACCEPTED`

日期：2026-09-02

工作树：`D:\Github_Storage\prism-phase-31`

基线：Phase 30 已验收提交 `63f6a4e`

## 1. 阶段目标

本阶段补齐 `Prism.md` P1 路线中的 Advanced Evidence UI。目标不是增加新的研究
算法，而是把已经存在于 DecisionTrace、Research node response 和 Provider resilience
契约中的“为什么、来自哪里、何时取得、如何送达、是否仍可信、验证走到哪一步”变成
可浏览、可筛选、可复核的界面。

用户应能在当前 owner 的已加载研究结果中，按 Evidence、来源、字段、质量状态、
lineage 和 provider serving mode 找到一条记录，并看见它通往 Fact/Finding/Validation
的闭合或未闭合路径。`DIRECT`、`CACHE_FRESH`、`FALLBACK_PROVIDER` 和
`CACHE_STALE_FALLBACK` 必须保持语义差异；陈旧或退化的结果只能降低信任，不能被
界面包装成 VERIFIED 或可交易建议。这是 Prism 区别于只给一段流畅回答的产品证据：
用户可以检查事实的出处与新鲜度，而不是相信隐藏的检索过程。

本阶段继续 fixture-first、同源本地工作台路线。所有信息都来自当前会话已经加载的
owner-bound API 结果，不引入另一套事实来源或持久化索引。

## 2. 明确做什么

### 2.1 Advanced Evidence explorer

- 在现有 Evidence 页面增加可见的 Advanced Evidence explorer，而不是另起一套页面。
- 汇总当前会话已加载的 Advisor receipt、Research Matrix、Stock、Fund/ETF 和
  Convertible Bond 结果；每一项带安全的来源标签，不能跨 owner 或跨旧 run 残留。
- 提供 Evidence ID/source/field/metric/period 的文本搜索，以及按 quality status、
  provider serving mode、来源轨道和“是否已进入 Fact/Finding”筛选；空结果和筛选
  结果都要有明确状态，不以空白掩盖没有数据。
- 提供键盘可达、文本化的 Evidence rows 与 detail pane。详情至少展示：Evidence ID、
  provider、source、field/value/unit/period、observed_at、retrieved_at、quality
  status/note、lineage_id、所属 run/owner（安全标识），以及它关联的 Fact、Finding、
  Cross-Validation 和 issue。所有动态文本只通过 DOM 节点与 `textContent` 写入。
- 显示一条简洁的 `Finding → Fact → Evidence` 或“Available Evidence · not promoted”
  路径；当缺少闭合对象时说明缺口，而不是猜测或补造结论。

### 2.2 Provider provenance 与新鲜度

- 复用 Phase 30 的 `provider`、`provider_serving_mode`、`provider_cache_age_ms`，
  在轨道摘要和 Evidence 详情中显示“直连、fresh cache、备用 provider、陈旧缓存
  fallback”等可读标签。
- 对 cache age 使用确定性格式（毫秒并可读化），并同时保留原始 `retrieved_at`；
  不把缓存命中显示为新的取得时间。
- `CACHE_STALE_FALLBACK` 和 `STALE` Evidence 必须显示“需要人工复核/不能作为
  VERIFIED 事实”的警示；`FALLBACK_PROVIDER` 必须保留备用 provider/source/lineage；
  `PARTIAL`、`EMPTY`、`FAILED` 的原因继续用现有 safe issue 展示。
- 对没有 node provenance 的 Advisor receipt 明确显示“该回执未提供 provider
  serving metadata”，不猜测为 `DIRECT` 以外的路径。

### 2.3 Owner、run 与交互安全

- 复用现有 owner 切换、sequence guard、resetOwnerScopedViews 和结果清理逻辑；owner
  变化、scenario 变化或重新运行后，explorer 必须同步清空旧 rows、搜索词、筛选器和
  选中详情，避免把上一 owner/run 的 Evidence 留在屏幕上。
- Explorer 只读，不新增 fetch、不访问外部网络、不保存 raw payload、不改变现有
  Recommendation、DecisionEvent、Fact/Finding 或 API 状态。
- 保持现有 Evidence chain、各 research card、Advisor receipt 的展示语义；新 UI 是
  可导航的审计入口，不把任何 review/blocked/stale 结果升级为 recommendation。
- 添加适量 aria-label、`aria-live`/焦点状态和响应式布局，确保窄屏仍能阅读 ID、状态
  与详情，不依赖颜色单独传达质量。

### 2.4 文档与复用记录

- 新增 Advanced Evidence UI contract 文档，记录聚合输入、状态标签、freshness 计算、
  owner/run 清理和“未闭合不升级”的规则。
- 更新 `Prism.md`、README、TODO、LOG，说明本阶段的产品差异和仍未实现的实时/生产
  边界；不宣称完整 SkillHub 在线证据浏览器。
- 复用现有暖白工作台视觉语言、DOM helper、status chip、metadata grid、研究卡片和
  浏览器验收工具，不引入重量级图可视化依赖。

## 3. 明确不做

- 不连接同花顺问财 SkillHub、Tushare、任何在线鉴权、代理、cookies、凭据或外网；
  不新增 LLM/Gemini/自然语言解析。
- 不做后端 Evidence 搜索服务、数据库/向量索引、跨进程缓存、云同步、跨用户共享或
  自动恢复；聚合范围严格限于当前已加载响应。
- 不改变 Evidence/Facts/Findings/DecisionTrace/Provider 四态契约，不重新计算金融
  数字，不修改 cross-validation、Recommendation、Decision Receipt 或交易能力。
- 不将 stale、fallback、PARTIAL、EMPTY、FAILED 或缺少 lineage 的记录变成 VERIFIED；
  不隐藏 issue、不伪造 source URL、不回显 raw provider payload 或异常原文。
- 不做大规模页面重构、复杂 graph canvas、拖拽编排、分页后端、导出/分享链接或实时
  自动刷新；这些需要独立的产品与权限设计。
- 不顺手实现真实认证、生产 SLA、Redis/数据库持久化、断路器/动态限流或未列入本阶段
  验收的研究轨道。

## 4. 复用边界与实现策略

### 复用

- `app/contracts/evidence.py` 的 Evidence、Fact、Finding、Validation、DecisionTrace
  闭包与 quality status 语义。
- `app/api/contracts.py`、股票/基金/可转债响应及 Phase 30 ProviderServingMode 的
  安全 node projection；不在浏览器推断服务端未返回的字段。
- 现有 `renderEvidence`、四类 research renderers、`state`、owner/sequence reset、
  `text()`/`clear()`/`addMetadata()`/`chip()` 和同源 fetch/CSP 边界。
- 既有 CSS 变量、panel/card/status 样式与真实本地浏览器验收纪律；保留静态资源无
  `innerHTML`/外部请求的安全约束。

### 新增或适配

- `app/api/static/index.html`：在 Evidence panel 增加 explorer controls、summary、
  list/detail 容器与无数据/筛选状态；为 nav 提供明确的 Advanced Evidence 文案。
- `app/api/static/app.js`：增加 owner-bound run aggregation、稳定排序、搜索/筛选、
  provenance/quality label、path projection、键盘 row selection 和 reset；让所有
  现有结果更新点调用统一 `renderAdvancedEvidence()`。
- `app/api/static/styles.css`：增加紧凑、响应式、可聚焦的 explorer/list/detail 样式，
  复用现有色彩并为 stale/fallback/review 提供非颜色文字。
- `tests/`：增加可独立运行的静态契约/浏览器 smoke 检查，覆盖所有来源轨道、质量与
  serving mode、搜索/筛选、详情闭合/未闭合、owner/run 清理与无外部请求；不把浏览器
  测试变成对真实网络的依赖。
- `docs/advanced-evidence-ui.md` 及项目日志：描述输入边界、审计语义、产品差异和
  验收证据。

## 5. 验收门（必须全部通过）

### 计划与复审门

1. 本计划书必须先于业务代码独立提交；实现后进行至少一轮代码复审，重点检查跨 owner
   残留、mode/age 误标、stale 信任升级、未闭合 Evidence 被当作事实、raw payload/HTML
   sink 和状态竞态。P0/P1 缺口修复后才能标记 `ACCEPTED`。

### 功能与契约门

2. Explorer 能从当前已加载的五类结果稳定汇总 Evidence，按 ID/source/field/period
   搜索并按质量、serving mode、轨道、promotion 状态筛选；稳定排序和计数可复现。
3. 详情能闭合展示 Evidence → Fact → Finding → Validation（或明确显示未闭合原因），
   展示 provider/source/lineage/observed/retrieved/cache age，并保留 safe issue；
   `STALE`、`FALLBACK_PROVIDER`、`CACHE_FRESH` 与 `DIRECT` 的文案不混淆。
4. 所有动态内容通过 `textContent`/DOM API；无 `innerHTML`、`eval`、外部 fetch、raw
   exception/secret；搜索输入不会执行 HTML/脚本。
5. owner 切换、scenario 变化、重新运行和无结果路径均清理 explorer 选择/筛选/详情；
   sequence guard 不会让过期响应重新写入当前 owner。

### 回归与工程门

6. 阶段测试、全量 `python -m pytest`、`python -m compileall -q app tools tests`、
   `node --check app/api/static/app.js`、`git diff --check` 全部通过；Phase 30 的
   `431` 项基线保持绿色（加上本阶段新增测试）。
7. `python -m tools.evaluate_mvp --repeat 100 --json` 保持 9/9、全部指标 `1.0`；
   provider resilience load test 的 mode/错误/缓存统计不受 UI 改动影响。
8. wheel/包内静态资源包含 explorer 文档与更新后的 HTML/CSS/JS；隔离加载、公开导入、
   静态安全扫描通过。不得引入外部运行时依赖或改动 API 数据契约。

### 浏览器门

9. 真实本地浏览器访问同源工作台，完成 owner → load → 至少运行 Research Matrix、
   Stock、Fund、Convertible Bond 与 Advisor receipt；Evidence explorer 显示汇总行、
   搜索/筛选、详情链和 provenance。通过路由拦截或安全 fixture 注入验证 stale/fallback
   警示与 cache age 文案，且不发出外部请求、无 console errors。
10. 浏览器回放一个空/退化结果与 owner 切换，确认“无结果/需复核”可见、旧选择清除、
    没有把上一 owner 的 Evidence 留在 explorer 中；窄屏/键盘聚焦至少完成一次 smoke。

## 6. 阶段停止条件与后续

只有计划、实现、审查修复、测试、静态安全扫描和真实浏览器门全部有可复核记录，且
工作树干净提交后，才把本计划状态改为 `ACCEPTED`。随后再从接受提交创建下一个全新
worktree。实时 SkillHub/生产证据服务、持久化索引、认证与更复杂的可视化继续按
`Prism.md` 的 deferred 边界推进，不在本阶段顺手扩大。

## 7. 验收记录

- 计划提交：`7826035 docs: plan phase 31 advanced evidence ui`，先于业务代码。
- 初版实现：`fd56d19 feat: add advanced evidence explorer`；新增 Evidence chain explorer、
  owner-bound 聚合、质量/serving mode/轨道/promotion 筛选、详情链和 DOM/textContent
  安全边界；契约说明见 `docs/advanced-evidence-ui.md`。
- 复审修复：`fba69ec` 修正同 Provider 多节点的 source-to-node provenance 映射并将
  fallback 设为 review；`467bfb5` 清除 Context Memory 恢复后的旧 selected receipt；
  `29e1d23` 在决策列表刷新开始时清除旧回执，避免刷新失败残留。完整记录见
  `docs/reviews/2026-09-02-phase-31-advanced-evidence-ui-review.md`。
- 阶段测试：`tests/unit/test_advanced_evidence_ui.py` 通过（3 项）；全量回归 `434 passed`，
  仅已知 Starlette/httpx deprecation warning，Phase 30 的 `431` 项基线保持绿色。
- 代码门：`python -m compileall -q app tools tests`、公开 API/包内 import、
  `node --check app/api/static/app.js`、`node --check tools/advanced_evidence_ui_smoke.cjs`、
  `git diff --check` 全部通过。静态扫描未发现 innerHTML/outerHTML/HTML sink、外部网络、
  LLM/Gemini、凭据或 raw exception 输出。
- 固定评测：`python -m tools.evaluate_mvp --repeat 100 --json`，9/9 cases，所有语义指标
  `1.0`（本次本地 fixture P50/P95=`12.413/16.542 ms`）。
- resilience 回归：`python -m tools.provider_resilience_load_test --requests 100`，fresh
  `100/100 CACHE_FRESH`、stale `100/100 CACHE_STALE_FALLBACK`、错误 `0`、request IDs
  唯一，healthy provider 回源 `1` 次，cache entries `1`；UI 未改变服务端 mode/age 语义。
- wheel：`python -m pip wheel . --no-deps` 成功，`115` entries；包含更新后的
  `app/api/static/index.html`、`app/api/static/app.js`、`app/api/static/styles.css` 和
  `app/providers/resilience.py`；解压隔离后 `InMemoryProviderCache`、`ProviderServingMode`
  与 `create_app()` 公开导入成功。
- 真实浏览器：本地 Uvicorn + headless Chromium 运行
  `tools/advanced_evidence_ui_smoke.cjs` 通过，覆盖 Research Matrix、Stock、Fund、
  Convertible Bond、Advisor、Evidence ID 搜索、VERIFIED/stale/fallback、cache age、
  Context Memory 显式恢复清理、owner 切换清理、窄屏键盘 focus；外部请求 `[]`、
  console errors `[]`。这是本地 fixture/ASGI 验证，不代表实时市场数据或生产 SLA。
- 产品差异：普通聊天往往隐藏数据是直连、缓存、备用源还是陈旧；Prism 将 provider/source/
  lineage、取得时间、serving mode、闭合路径和需复核原因置于可筛选详情中，且 stale /
  fallback 不会被包装成 VERIFIED 或建议。
- 最终状态：`ACCEPTED`；实时 SkillHub、后端证据索引、认证、云/生产持久化、自动刷新、
  复杂图视图和 Recommendation 旁路仍按本计划明确未实现。
