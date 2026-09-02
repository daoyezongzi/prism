# Prism MVP Phase 34-37：P2 阶段 4 项里程碑任务执行计划

状态：`IN_PROGRESS`

基线：Phase 33（Scenario Simulation）已验收。本项目根据 [Prism.md](../../Prism.md) 第 31 节执行 P2 阶段剩余 4 项任务：

1. **Phase 34：Recommendation History（历史建议追溯与审计）**
2. **Phase 35：Portfolio Rebalancing（组合再平衡行动规划）**
3. **Phase 36：Evaluation Dashboard（评测与监控看板）**
4. **Phase 37：Advanced Explainability（全链路高级可解释性）**

## 1. 设计目标与边界

- **确定性金融算术**：全部采用 Decimal 高精度算术，绝不使用浮点数或模糊文本生成。
- **Owner 严格隔离**：跨用户数据访问严格拦截。
- **证据闭环追溯**：`Recommendation -> Finding -> Fact -> Evidence`。
- **降级与防御性安全**：数据不完整时停在 `REVIEW_REQUIRED` 或 `BLOCKED`，不伪造零值或虚假结果。
- **静态工作台安全**：无 `innerHTML`，无外部脚本或 CDN，符合 CSP 规范。

## 2. 交付物清单

- **对接书文档**：`docs/recommendation-history.md`、`docs/portfolio-rebalancing.md`、`docs/evaluation-dashboard.md`、`docs/advanced-explainability.md`
- **代码实现**：
  - `app/history/` & `app/service/recommendation_history.py`
  - `app/rebalancing/` & `app/service/portfolio_rebalancing.py`
  - `app/evaluation/` & `app/service/evaluation_dashboard.py`
  - `app/explainability/` & `app/service/advanced_explainability.py`
  - `app/api/main.py`
  - `app/api/static/index.html`、`app/api/static/styles.css`、`app/api/static/app.js`
- **单元与集成测试**：
  - `tests/unit/test_recommendation_history.py`
  - `tests/unit/test_portfolio_rebalancing.py`
  - `tests/unit/test_evaluation_dashboard.py`
  - `tests/unit/test_advanced_explainability.py`
  - `tests/integration/test_phase34_recommendation_history.py`
  - `tests/integration/test_phase35_portfolio_rebalancing.py`
  - `tests/integration/test_phase36_evaluation_dashboard.py`
  - `tests/integration/test_phase37_advanced_explainability.py`
