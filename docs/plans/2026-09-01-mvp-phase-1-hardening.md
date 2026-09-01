# Phase 1 Hardening Working Plan

## Goal

把 Phase 1 Provider Protocol 修复到可验收状态，处理独立复审发现的契约漏洞，然后再次进行独立反例复审。Phase 2 在本计划通过前不启动。

## Context / Constraints

- 基线提交：`68ed7ff32d5ae9e4a5d76562fb3a9d6cbeacba08`。
- 保留现有 Provider 四态、Evidence Contract 和 fixture-first 架构。
- 仅修改 Phase 1 允许的 Provider 代码、Provider 测试、Provider 文档以及必要的 README/TODO/LOG 记录。
- 不修改 `Prism.md`、现有 `app/contracts/evidence.py`、Evidence Contract 测试或上游仓库。
- 不添加生产依赖，不访问真实网络，不引入凭据。
- 开始前和结束后都必须保持可审计的 Git 状态；不自动 push。

## In scope

1. 保留 `JsonValue` 语义的深度不可变映射：递归冻结所有 JSON 映射与序列，拒绝 set、任意对象等非 JSON 值，并阻断 `|=` 等原地变更。
2. 对 `ProviderRecord.units` 保留字符串值约束，避免合法 ProviderResult 在 Evidence normalization 阶段才崩溃。
3. 完整校验 `PARTIAL.missing_fields`：声明项必须是请求字段、必须实际缺失，并且实际缺失的请求字段不得漏报；仅有非字段类 issue 时允许空 missing_fields。
4. 使 Evidence ID 对记录身份、请求语义和特殊分隔符安全；拒绝同一来源下重复的有效记录身份。
5. 为每个修复增加最小回归测试，补充跨边界反例测试。

## Out of scope

- 真实同花顺问财/SkillHub/Tushare 请求、鉴权或网络适配器。
- 重试、缓存、连接池、断路器、限流、数据库、FastAPI、Web UI。
- 修改上游参考项目或放宽现有 Evidence Contract。
- Phase 2 的研究 DAG、用户画像、持仓、组合、风险或推荐功能。

## Design decisions

- `FrozenDict` 的 Pydantic schema 必须继续验证 JSON-compatible values；不可为了实现冻结而退化为 `Any`。
- 深度冻结统一递归处理 `Mapping`、`list`、`tuple`；序列冻结为 tuple，且嵌套层级不能遗留可变 list/dict。
- `PARTIAL` 的字段缺失集合按 required fields 在任一 record 中缺失或为 `None` 计算；声明集合必须覆盖且仅覆盖该实际集合。没有字段缺失、但有结构化 issue 的部分结果仍可合法存在。
- Evidence ID 使用稳定、无分隔符歧义的编码材料，并在 normalization 前检查有效记录身份唯一；不能依赖随机数或仅依赖数组下标。

## Required regression cases

- 非 JSON request parameter 被拒绝，且 fingerprint 不会在运行时才崩溃。
- `units` 非字符串被拒绝。
- 两层以上嵌套序列与 `|=` 均不能改变已创建的 request。
- `PARTIAL` 漏报实际缺失字段、声明未请求字段、声明已存在字段均被拒绝。
- 同一 source 下重复 record identity 被拒绝。
- source/record identity 含 `:` 的不同记录仍生成不同 Evidence ID。
- 两个不同请求语义不会因相同 source/record/field/period 产生跨请求 ID 碰撞。

## Verification

```powershell
python -m pytest
python -m compileall -q app
python -c "from app.providers import FinancialProvider, FixtureFinancialProvider, FrozenDict; print('provider-import-ok')"
git diff --check
git status --short --branch
```

另外运行独立 Python 反例脚本，确认上述边界均按预期拒绝或保持不变，并审阅最终 diff、测试数量和提交范围。

## Stop conditions

- 需要修改现有 Evidence Contract 或 `Prism.md`。
- 需要新增生产依赖或真实凭据/网络。
- 基线测试失败且无法证明由本次修复引起。
- 记录身份或 `PARTIAL` 缺失集合无法在不改变现有四态语义的情况下确定。

## Definition of done

- 全部测试通过，新增反例覆盖本计划的每个修复点。
- 完整验证命令有真实输出；Evidence Contract 原有测试继续通过。
- Provider 文档、TODO、LOG 不再声称未验证的行为已完成。
- 工作区干净，产生一个本地 hardening 提交且未 push。
- 只有本计划通过后，才创建并执行 Phase 2 计划书。
