# Prism MVP Phase 32：中文 UI 与导航选中态计划

状态：`PLANNED`

基线：Phase 31 已验收提交 `d6fccd7`；本阶段在全新 worktree
`D:\Github_Storage\prism-phase-32`、分支 `codex/mvp-phase-32-scenario-simulation` 中执行。

## 1. 阶段目标

把当前本地工作台从中英混杂的开发展示统一为面向中文用户的可读界面，并修复左侧
单页导航点击后选中项仍停留在 `Overview` 的状态同步问题。中文化只改变展示层，不
改变 API、Provider、Evidence、Decision Receipt 或任何稳定 ID/枚举的契约。

本阶段完成后，用户应能：

1. 在首次加载、owner 切换、研究/回执成功或失败、空结果和证据详情等路径中看到
   一致的中文标题、按钮、说明、状态、元数据标签和无障碍文案；
2. 点击左侧任一导航项后立即看到该项的选中态，刷新或直接打开带 hash 的 URL 后仍
   与当前 section 一致；
3. 在窄屏和键盘操作下使用同一套导航，不依赖颜色 alone 判断选中项。

## 2. 明确做什么

### 2.1 展示层中文化

- 翻译 `app/api/static/index.html` 中所有面向用户的标题、导航、eyebrow、按钮、
  表单标签、占位符、帮助文本、边界说明、`title`、`aria-label` 和页面标题。
- 翻译 `app/api/static/app.js` 中所有动态渲染文案：加载/成功/失败/空结果状态、
  错误提示、回执与风险标签、Profile/Portfolio/Research/Fund/可转债/Optimization/
  Evidence 的元数据标签、审计路径和筛选摘要。
- 保留可审计的机器值（例如 `PASS`、`READY`、`STALE`、`CACHE_FRESH`、Provider 名称、
  Evidence ID、lineage、schema/API 字段名）作为中文说明后的代码标识，避免用户无法
  对照回执或日志；代码标识不作为自然语言句子单独占据界面。
- 用集中、无外部依赖的展示映射处理状态、角色、字段和常见枚举，未知值安全回退，
  不把后端原始异常或敏感 payload 回显到页面。

### 2.2 导航选中态

- 给左侧导航项保留稳定的 section hash，使用 `aria-current="location"` 与现有
  `.active` 样式表达当前 section。
- 在点击、`hashchange`、首次加载（包括直接打开 `#profile` 等 hash）时同步选中项；
  点击同一个 hash 也必须立即保持正确状态。
- 不新增路由、不重载页面、不发起网络请求；section 仍是现有单页锚点。

### 2.3 测试、文档与回归

- 增加静态契约测试，覆盖中文关键文案、无残留的核心英文展示词、导航 hash/无障碍
  属性和导航同步逻辑。
- 扩展现有本地 Playwright smoke：逐项点击导航并断言 `active` 与
  `aria-current="location"`，直接访问 hash 后断言选中项，检查中文关键标题、无外部
  请求和无 console error。
- 更新 `README.md`、`TODO.md`、`LOG.md` 和本计划的验收记录，明确中文化完成、英文
  机器标识保留规则，以及 Scenario Simulation 顺延到下一独立 worktree。

## 3. 明确不做

- 不改 FastAPI/API、Provider、数据库、Evidence/Fact/Finding/Recommendation 契约，
  不修改请求/响应字段名和稳定枚举值。
- 不实现 Scenario Simulation、Recommendation History、Portfolio Rebalancing、
  Evaluation Dashboard 或其他 P2 功能；它们必须从本阶段接受提交另建 worktree。
- 不引入 i18n 框架、打包依赖、外部字体、网络翻译服务或运行时外部请求。
- 不做大规模视觉重构、复杂动画、路由系统、后端分页或登录认证；只调整文案、必要
  的可访问性属性和导航状态同步。
- 不把 Evidence ID、Provider/source/lineage、API 路径或审计所需的机器标识翻译成
  不可检索的别名；不改变敏感信息脱敏边界。

## 4. 复用边界与产品差异化

- 复用 Phase 31 的暖白工作台视觉语言、`.nav-item.active`、现有 DOM helper、
  `textContent` 安全渲染、owner 隔离清理和 Playwright smoke；不新增另一套组件系统。
- 复用后端返回的事实与状态，只在 UI 层建立可追溯的中文展示映射；这样中文界面与
  日志/API 仍能一一对照。
- Prism 的差异不是“把英文换成中文”本身，而是中文用户仍能看见约束、来源、新鲜度、
  闭合状态和失败/需复核语义。翻译必须保留这些审计信息，不能用更顺滑的文案掩盖
  缺失数据或降级结果。

## 5. 实现顺序

1. 盘点静态 HTML 与动态 JS 的用户可见英文，确定展示映射与保留的机器标识。
2. 先修改 HTML 文案、导航可访问性属性和测试基线。
3. 再修改 JS 映射、动态渲染文案及 hash/点击导航同步。
4. 运行静态测试、全量回归、代码/安全边界检查和本地浏览器 smoke。
5. 独立复核英文残留、owner/异步清理是否受影响、导航直接 hash 与窄屏键盘行为，
   修复 P0/P1 问题后再记录验收。

## 6. 验收标准

1. 核心静态界面无面向用户的英文句子；英文只保留经计划说明的产品名、机器标识、
   ID、Provider/source/lineage 和必要代码枚举，并有中文解释。
2. 首次加载与每个已有 section（总览、Advisor、Portfolio、Context Memory、组合
   优化、研究轨道、个股、基金、可转债、Evidence、Risk Profile）均能正确显示中文
   导航名称；直接 hash 加载和点击后 active/`aria-current` 一致。
3. 动态成功、失败、PARTIAL/EMPTY/FAILED、陈旧缓存、备用 Provider、Evidence 未闭合、
   owner 切换和 Context Memory 恢复路径的中文语义保持准确，不能把失败当成空结果或
   把需复核升级为通过。
4. `python -m pytest` 全部通过并保持 Phase 31 的 `434` 项基线；新增静态/浏览器
   回归有明确输出。
5. `python -m compileall -q app tools tests`、`node --check app/api/static/app.js`、
   `git diff --check`、wheel/隔离导入通过；不得引入外部运行时请求或依赖。
6. Playwright smoke 证明导航点击/直接 hash、中文关键文案、窄屏键盘焦点、无外部请求、
   无 console error；工作树干净并有阶段接受提交。

## 7. 停止条件与后续

只有计划、实现、独立审查、回归测试、静态检查、真实本地浏览器门和文档记录全部有
可复核证据，且工作树干净提交后，才将本计划状态改为 `ACCEPTED`。之后从接受提交
创建全新的 Phase 33 worktree，重新写 Scenario Simulation 计划；不在本阶段顺手实现
其他 P2 能力。

## 8. 风险

- 当前页面已有部分中文，完整盘点容易漏掉动态渲染分支；静态英文扫描和浏览器路径
  必须同时覆盖。
- 机器枚举若完全翻译会削弱日志对照，故采用“中文说明 + 稳定代码标识”的明确规则。
- 导航只做 hash 同步，不做滚动侦测；避免滚动过程覆盖用户刚点击的选中态，后续如需
  滚动跟随必须另立 UX 计划。
