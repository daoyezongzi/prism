# Phase 32 中文 UI 与导航选中态独立审查

日期：2026-09-02  
审查基线：Phase 32 当前实现（基于 Phase 31 accepted `d6fccd7`）  
审查范围：`app/api/static/index.html`、`app/api/static/app.js`、静态契约测试、
既有 Advanced Evidence smoke、导航 hash/点击生命周期、动态四态文案与 owner 隔离。

## 审查方法

- 对照 Phase 32 计划逐项阅读静态 HTML、动态 renderer、场景 option 构建和
  `syncNavigation`/`initializeNavigation` 调用链；特别检查展示映射不会改变请求契约。
- 搜索所有动态 `textContent`、错误路径、scope/rationale/methodology/issue 输出，
  追踪来自现有 fixture/service 的英文描述，并确认翻译只发生在 UI 层。
- 使用本地 headless 浏览器覆盖首次加载、点击 `#profile`、直接打开 `#evidence`、
  Research Matrix、STALE/CACHE_STALE_FALLBACK、FALLBACK_PROVIDER、Stock、Fund、
  Convertible Bond、Advisor、Context Memory 恢复、owner 切换和窄屏键盘焦点。
- 运行静态契约、全量 pytest、前端语法检查、compileall、diff 检查、评测/负载、wheel
  和无外部请求/无 console error 的浏览器门。

## Findings and fixes

### P1 — 展示映射曾改写场景 option 的机器值

首版复用 `text()` 生成 `<option>.value`，会把 `SOURCE_PARTIAL` 等稳定场景 ID 变成中文，
导致提交给 API 的 `scenario_id` 不再符合后端契约。修复为 option value 始终取原始
`scenario.scenario_id`，只对 `textContent`/`title` 使用中文展示映射；新增静态断言，
并由 smoke 等待原始 option value、实际选择场景后再次运行复核。

### P1 — 降级/异常分支仍可能显示后端英文句子

审查发现来源不可用、字段缺失、暴露计算失败和确定性 methodology 的英文安全描述，
以及 `pct`/`rating_rank` 等小写单位在非主路径中未统一。补齐 UI 层 description/method
映射、大小写不敏感的稳定枚举展示和 replay 后缀处理；未修改 service、API 或响应契约。

### P2 — 安全问题标题大小写不一致

详情面板仍显示小写 `issue`，与中文说明后的稳定代码约定不一致。已统一为
`需复核的安全问题（ISSUE）`，不影响筛选或状态判断。

其余检查未发现 P0/P1 缺口：导航点击与 `hashchange` 均只同步 `.active` 和
`aria-current="location"`，不发起网络请求；未知 hash 安全回退总览；owner 切换/恢复仍
清空派生结果与证据；稳定 ID、Provider/source/lineage、schema/API 字段和枚举代码保留
可检索性；动态内容继续使用 DOM API/`textContent`，不新增 HTML sink、外部请求、凭据或
LLM/Gemini 依赖。

## 审查结论

上述 P1/P2 已修复，并由新增静态测试、全量回归和真实本地浏览器 smoke 复验。Phase 32
可以进入最终验收；Scenario Simulation、后端索引、实时 SkillHub、认证、云持久化和
滚动侦测仍按计划排除，必须在下一独立 worktree 另立阶段。
