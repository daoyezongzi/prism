# MVP Phase 1 Execution Contract：Fixture-first Provider Protocol

- Status：`READY_FOR_DELEGATION`
- Intended executor：Gemini / Antigravity
- Reviewer：Codex + user
- Target branch：`gemini/mvp-phase-1-provider-protocol`
- Source of truth：[Prism.md](../../Prism.md)
- Parent plan：[Prism Foundation](2026-09-01-foundation.md)

## 可直接复制给 Gemini 的派发提示

```text
请在 D:\Github_Storage\prism 中实施 MVP Phase 1。

开始前：
1. 确认 git status 干净；如果不干净，停止并报告，不要覆盖现有修改。
2. 从当前 main 创建并切换到 gemini/mvp-phase-1-provider-protocol；如果我已经为你准备了独立 worktree，则直接使用当前分支。
3. 完整阅读 Prism.md、README.md、TODO.md、LOG.md、docs/evidence-contract.md、docs/architecture.md、docs/reuse-matrix.md，以及 docs/plans/2026-09-01-mvp-phase-1-provider-protocol.md。
4. 严格把本任务书视为执行合同；不得扩大范围或用假实现宣称完成真实 SkillHub 接入。

使用测试先行实现 fixture-first Provider Protocol。只能修改本任务书“允许修改”列出的区域。不得修改 Prism.md、现有 Evidence Contract、两个上游仓库或任何真实凭据。

完成全部验收后：
- 运行本任务书要求的验证命令；
- 更新 TODO.md 和 LOG.md，准确记录完成项与未验证项；
- 检查 git diff 和 git diff --check；
- 创建一个本地提交：feat: add fixture-first provider protocol；
- 不要 push；
- 按本任务书的 Handoff Format 报告结果。

遇到停止条件时立即停止，不要自行绕过。
```

## 1. 本阶段在总路线中的位置

```text
Foundation（已完成）
    Evidence Contract + repository + architecture
                ↓
MVP Phase 1（本任务）
    Provider Protocol + four-state semantics + fixtures
                ↓
Phase 1B（后续，不在本任务）
    persistence + early load harness expansion
                ↓
MVP Phase 2
    user profile + position/fund-ETF import contracts
                ↓
MVP Phase 3
    deterministic exposure/risk/allocation vertical slice
                ↓
MVP Phase 4
    structured research DAG + cross validation
                ↓
MVP Phase 5
    Portfolio/Advisor/Evidence/Risk Profile workbench
                ↓
MVP Phase 6
    live SkillHub + load/failure/browser hardening + submission
```

后续阶段只用于说明接口的下一位消费者。Gemini 本次不得实现后续阶段。

## 2. Goal

建立一个完全离线、可重复、可审计的 Provider 数据边界，使 Prism 在没有真实 SkillHub 凭据时，也能严格区分：

- `SUCCESS`：在明确范围内取得满足请求的记录；
- `PARTIAL`：取得部分记录，但缺少字段或某个辅助来源失败；
- `EMPTY`：请求成功，且在记录的查询范围内确实没有结果；
- `FAILED`：请求没有可靠完成，例如超时、限流、鉴权、传输或解析失败。

本阶段必须证明：`EMPTY != FAILED`，`PARTIAL != SUCCESS`，失败不能产生零值或伪造 Evidence。

## 3. Current baseline

- `app/contracts/evidence.py` 已实现 Evidence/Fact/Finding/Recommendation/DecisionTrace；
- 现有 8 项测试通过；
- 尚无 `app/providers/`；
- 尚无真实 SkillHub/Tushare 凭据、接口 Schema 或比赛专用授权材料；
- 上游仓库只读，不是 Prism 的运行时依赖。

可借鉴但不得整目录复制：

- `D:\Github_Storage\TradeEye\tradeeye\services\data.py`：必需源失败闭合、辅助源降级、失败不缓存；
- `D:\Github_Storage\TradeEye\tests\test_data.py`：required/optional Provider 失败测试模式；
- `D:\Github_Storage\tradeeye-copilot\copilot\datasource\fundamentals.py`：Provider 与 normalization 分层；
- `D:\Github_Storage\tradeeye-copilot\copilot\service\analyzer.py`：Protocol 边界，但其同步运行时不得照搬。

## 4. In scope

### 4.1 Provider contracts

实现严格、不可变、`extra="forbid"` 的 Pydantic 契约：

```text
ProviderOperation
ProviderStatus
ProviderIssueCode
ProviderRequest
ProviderRecord
ProviderIssue
ProviderResult
FinancialProvider (typing.Protocol)
```

`ProviderOperation` 首版固定为：

```text
MARKET_DATA
COMPANY_DATA
INDUSTRY_DATA
MACRO_DATA
FUND_DATA
SEARCH_NEWS
SEARCH_REPORTS
```

`FinancialProvider` 只暴露一个异步入口：

```python
class FinancialProvider(Protocol):
    @property
    def name(self) -> str: ...

    async def execute(self, request: ProviderRequest) -> ProviderResult: ...
```

不要现在创建七个未验证的外部 API 方法。领域服务以后可在此入口上提供类型更窄的 facade。

### 4.2 Request identity

区分两个概念：

- `request_id`：每次调用的关联 ID，由调用方传入；
- `request_fingerprint`：同一语义查询的确定性 SHA-256 指纹。

指纹必须使用 canonical JSON，并至少覆盖：Schema 版本、operation、subject、as-of、排序后的 required fields 和 parameters。它必须：

- 不受字典键顺序影响；
- 不包含 `request_id`、timeout 或凭据；
- 对语义不同的查询产生不同结果；
- 只输出小写十六进制摘要。

`ProviderRequest.parameters` 中禁止出现大小写不敏感的敏感键：

```text
token
api_key
apikey
authorization
cookie
secret
password
credential
```

认证将来由 Provider 实例配置注入，不进入请求、fixture、fingerprint 或日志。

### 4.3 Result invariants

状态不变量必须由模型校验，而不是只写在文档中：

| Status | Records | Missing fields / Issues | 额外要求 |
|---|---|---|---|
| `SUCCESS` | 至少 1 条 | 不允许缺失；不允许 issue | 满足 request 的 required fields |
| `PARTIAL` | 至少 1 条 | 至少有 missing field 或 issue | 不得升级为完整 Evidence |
| `EMPTY` | 必须为 0 | 不允许错误 issue | 必须有明确 `scope_description` |
| `FAILED` | 必须为 0 | 至少 1 个 issue | issue 必须含安全消息和可重试性 |

实现一个显式的 `validate_result_for_request(request, result)`，检查：

- request ID 与 fingerprint 对应；
- `SUCCESS` 的每条记录包含全部 required fields；
- `PARTIAL` 明确指出实际缺失字段；
- Provider 返回的字段、时间和状态没有破坏契约。

不得把 Python `None`、空列表或裸异常当作 Provider Protocol。

### 4.4 Issues and safe diagnostics

`ProviderIssueCode` 至少包含：

```text
TIMEOUT
RATE_LIMITED
AUTH_FAILED
PERMISSION_DENIED
TRANSPORT_ERROR
INVALID_RESPONSE
UNSUPPORTED_OPERATION
CANCELLED
INTERNAL_ERROR
```

Issue 至少包含：

- code；
- stage；
- `safe_message`；
- `retriable`；
- 可选 `retry_after_ms`。

实现递归 diagnostics redaction。敏感键的值必须替换为 `[REDACTED]`。不得把原始异常堆栈、Authorization header、Cookie 或 token 写入结果、fixture、日志和测试快照。

### 4.5 Fixture provider

实现 `FixtureFinancialProvider`：

- 初始化时从固定目录加载并校验 JSON fixtures；
- 以 request fingerprint 索引，调用期间不访问网络；
- 不接受路径遍历或调用方提供的任意文件路径；
- 每次执行回填当前调用的 request ID/fingerprint，不能串用其他请求；
- 未找到匹配 fixture 时返回结构化 `FAILED/UNSUPPORTED_OPERATION`，不能返回空结果；
- 多次运行结果确定，不能依赖当前机器时间以外的隐式全局状态。

必须提供纯合成、无真实账户/凭据/用户持仓的 fixtures：

```text
fund_data_success.json
fund_data_partial.json
fund_data_empty.json
fund_data_failed.json
```

建议使用虚构标的 `FUND_FIXTURE_001`。成功样例可包含 `technology_weight_pct = 63.5`，用于连接现有科技集中度演示语境，但不得声称它是真实金融数据。

### 4.6 Budget wrapper

实现一个小型异步执行包装器，例如：

```python
async execute_with_budget(provider, request) -> ProviderResult
```

要求：

- 使用 request 的 timeout budget；
- 超时转换为 `FAILED/TIMEOUT`；
- 未知异常转换为无敏感内容的 `FAILED/INTERNAL_ERROR`；
- 保留 request identity；
- 不实现重试、缓存或熔断；这些属于后续阶段。

### 4.7 Evidence normalization

实现一个纯函数，把已经验证的 `ProviderResult` 转换为现有 `Evidence`：

```text
SUCCESS -> present fields become VERIFIED Evidence
PARTIAL -> present fields become PARTIAL Evidence with quality_note
EMPTY   -> zero Evidence
FAILED  -> zero Evidence
```

Evidence ID 必须由 provider/source/record/field/period 等稳定输入生成，不能使用随机数。缺失字段不得生成 `value=0` 的 Evidence。

本阶段不负责从 EMPTY/FAILED 自动生成 Fact；后续调用方将其转换为具有 reason 的 `FactStatus.UNAVAILABLE`。

### 4.8 Concurrency smoke test

使用标准库 `asyncio` 对内存中的 fixture Provider 发起 100 个并发请求，验证：

- 每个结果保留自己的 `request_id`；
- 相同语义请求具有相同 fingerprint；
- 没有跨请求状态串扰；
- 全部结果通过契约校验。

该测试只证明结构和隔离，不得宣称已经证明真实 Provider 的 3 秒或 99.9% 指标。

## 5. Recommended file boundaries

允许新增：

```text
app/providers/__init__.py
app/providers/contracts.py
app/providers/fingerprint.py
app/providers/fixture.py
app/providers/runtime.py
app/providers/normalization.py
tests/unit/test_provider_contract.py
tests/unit/test_provider_fingerprint.py
tests/integration/test_fixture_provider.py
tests/fixtures/providers/*.json
docs/provider-protocol.md
```

允许在全部验收通过后更新：

```text
README.md
TODO.md
LOG.md
```

不得修改：

```text
Prism.md
app/contracts/evidence.py
tests/unit/test_evidence_contract.py
docs/evidence-contract.md
D:\Github_Storage\tradeeye-copilot\**
D:\Github_Storage\TradeEye\**
```

如果现有 Evidence Contract 确实阻塞实现，停止并提交一份最小冲突说明，不得自行放宽事实契约。

## 6. Out of scope

- 真实 Wencai SkillHub、Tushare 或其他网络请求；
- 安装或请求任何 API key；
- 重试、缓存、连接池、熔断和限流器；
- PostgreSQL、Redis、迁移或持久化；
- FastAPI 路由；
- 用户画像、持仓、研究 Agent、组合、风险、合规或推荐；
- Web UI；
- 修改上游代码；
- 声称满足真实 100 用户、3 秒或 99.9% 指标；
- 新增生产依赖。

本阶段只允许使用 Python 标准库、现有 Pydantic 和 pytest。若确实需要新依赖，停止并解释，不得直接修改 `pyproject.toml`。

## 7. Test-first implementation order

1. 先写四态结果不变量测试，确认失败；
2. 实现 contracts，直到状态矩阵通过；
3. 写 fingerprint 与 secret-key 拒绝/脱敏测试；
4. 实现 canonical fingerprint 和 redaction；
5. 写四个 fixture 的加载、匹配和未知请求测试；
6. 实现 `FixtureFinancialProvider`；
7. 写 timeout/unknown exception 映射测试；
8. 实现 budget wrapper；
9. 写 ProviderResult -> Evidence 转换测试；
10. 实现 normalization；
11. 写 100 并发隔离测试；
12. 更新 Provider 文档、TODO 和 LOG；
13. 运行完整验证并检查 diff。

不要为了展示 TDD 创建或保留无意义的临时提交；最终一个清晰提交即可。

## 8. Required acceptance cases

以下案例必须有自动化测试：

1. `SUCCESS` 无 records 被拒绝；
2. `SUCCESS` 缺 required field 被拒绝；
3. `PARTIAL` 没有缺失字段或 issue 被拒绝；
4. `EMPTY` 带 record 被拒绝；
5. `EMPTY` 没有查询范围说明被拒绝；
6. `FAILED` 带 record 被拒绝；
7. `FAILED` 没有 issue 被拒绝；
8. `FAILED` 与 `EMPTY` 序列化结果明显不同；
9. request 参数包含敏感键时被拒绝；
10. diagnostics 中嵌套的敏感键被脱敏；
11. 参数键顺序不同仍产生相同 fingerprint；
12. operation/subject/as-of/parameters 变化会改变 fingerprint；
13. request ID 和 timeout 变化不改变语义 fingerprint；
14. 未知 fixture 返回结构化 FAILED，而不是 EMPTY；
15. timeout 返回 FAILED/TIMEOUT，且不泄露原始异常；
16. SUCCESS 只生成 VERIFIED Evidence；
17. PARTIAL 只生成 PARTIAL Evidence 并带 quality note；
18. EMPTY/FAILED 不生成 Evidence；
19. 真实数值零可以保留，缺失值不能转换为零；
20. 100 并发请求没有 request ID 串扰；
21. 原有 Evidence Contract 的 8 项测试继续通过。

## 9. Verification commands

必须在仓库根目录运行并读取结果：

```powershell
python -m pytest
python -m compileall -q app
python -c "from app.providers import FinancialProvider, FixtureFinancialProvider; print('provider-import-ok')"
git diff --check
git status --short --branch
```

如果增加了文档链接，还要验证所有本地 Markdown 相对链接存在。

## 10. Definition of Done

只有同时满足以下条件才算完成：

- 所有 required acceptance cases 有自动化测试并通过；
- 原有测试继续通过；
- fixture 纯合成、无网络、无凭据、无私人数据；
- 四态结果不可相互伪装；
- ProviderResult 能安全连接现有 Evidence Contract；
- 100 并发 fixture smoke test 无串扰；
- README/TODO/LOG 对实际完成度描述准确；
- diff 仅包含允许区域；
- 没有修改 Prism.md、现有 Evidence Contract 或上游；
- 创建一个本地提交且未 push；
- 最终工作区干净。

## 11. Stop conditions

遇到任一情况必须停止并报告：

- 开始时工作区不干净或存在不明修改；
- 需要真实 SkillHub/Tushare Schema、凭据或网络才能继续；
- 需要新增生产依赖；
- 需要修改现有 Evidence Contract 才能满足计划；
- 基线测试在任何实现修改前已失败；
- 需要修改 Prism.md 或上游仓库；
- 无法在不记录敏感数据的情况下实现某项要求；
- 计划内部出现无法同时满足的矛盾。

停止报告必须写明：阻塞条件、已验证证据、尚未修改的内容和建议的最小决策。

## 12. Handoff Format

Gemini 最终必须返回：

```text
Outcome
- COMPLETE 或 BLOCKED

Commit
- <commit hash and subject>，或说明未提交原因

Changed
- 按模块列出文件和实际行为

Verification
- 每条命令及真实结果
- 新增测试数量与完整测试总数

Contract evidence
- SUCCESS/PARTIAL/EMPTY/FAILED 各由哪个测试证明
- secret redaction、fingerprint、timeout、Evidence conversion、100 并发各由哪个测试证明

Not implemented
- 明确列出 out-of-scope 和未验证外部层

Risks / decisions needed
- 仅列真实剩余风险，不复述整个计划

Repository state
- branch
- git status
- push status（必须是 not pushed）
```

不得只回复“已完成”“测试通过”或给出没有命令输出支撑的总结。
