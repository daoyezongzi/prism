(() => {
  "use strict";

  const state = {
    ownerId: "",
    events: [],
    selected: null,
    queryTemplate: null,
    templateContext: null,
    templateSequence: 0,
    portfolioContext: null,
    profileContext: null,
    profileProposalDraft: null,
    profileProposalQuestionnaire: null,
    profileProposalExtraction: null,
    profileProposalProfile: null,
    profileProposalResolutions: {},
    profileProposalSequence: 0,
    advisorPlan: null,
    researchTemplate: null,
    researchRun: null,
    researchSequence: 0,
    stockResearchTemplate: null,
    stockResearchRun: null,
    stockResearchSequence: 0,
    fundResearchTemplate: null,
    fundResearchRun: null,
    fundResearchSequence: 0,
    convertibleBondResearchTemplate: null,
    convertibleBondResearchRun: null,
    convertibleBondResearchSequence: 0,
    portfolioOptimizationTemplate: null,
    portfolioOptimizationRun: null,
    portfolioOptimizationSequence: 0,
    scenarioSimulationTemplate: null,
    scenarioSimulationRun: null,
    scenarioSimulationSequence: 0,
    contextMemoryRecords: [],
    contextMemorySelected: null,
    contextMemorySequence: 0,
    selectedDecisionEvent: null,
    advancedEvidenceSearch: "",
    advancedEvidenceQuality: "ALL",
    advancedEvidenceMode: "ALL",
    advancedEvidenceSource: "ALL",
    advancedEvidencePromotion: "ALL",
    advancedEvidenceSelectedKey: "",
  };
  const byId = (id) => document.getElementById(id);

  const DISPLAY_VALUE_LABELS = Object.freeze({
    READY: "就绪（READY）",
    PASS: "通过（PASS）",
    VERIFIED: "已验证（VERIFIED）",
    STALE: "陈旧/需复核（STALE）",
    CONFLICTING: "来源冲突（CONFLICTING）",
    INVALID: "无效（INVALID）",
    REVIEW_REQUIRED: "待复核（REVIEW_REQUIRED）",
    BLOCKED: "已阻断（BLOCKED）",
    COMPLETED: "已完成（COMPLETED）",
    COMPLETE: "已完成（COMPLETE）",
    PARTIAL: "部分完成（PARTIAL）",
    FAILED: "失败（FAILED）",
    EMPTY: "无结果（EMPTY）",
    SUPPORTED: "已支持（SUPPORTED）",
    CONTRADICTED: "来源冲突（CONTRADICTED）",
    UNRESOLVED: "未解决（UNRESOLVED）",
    INSUFFICIENT: "数据不足（INSUFFICIENT）",
    CLEAR: "规则未触发（CLEAR）",
    WATCH: "需关注（WATCH）",
    HIGH_RISK: "高风险（HIGH_RISK）",
    GROWTH: "成长（GROWTH）",
    ETF_FUND: "ETF / 基金（ETF_FUND）",
    MACRO: "宏观（MACRO）",
    INDUSTRY: "行业（INDUSTRY）",
    STOCK: "个股（STOCK）",
    TECHNOLOGY: "科技（Technology）",
    HEALTHCARE: "医疗健康（Healthcare）",
    FINANCE: "金融（Finance）",
    INDUSTRIALS: "工业（Industrials）",
    UTILITIES: "公用事业（Utilities）",
    UNCLASSIFIED: "未分类（UNCLASSIFIED）",
    EXPLICIT_SAVE: "显式保存（EXPLICIT_SAVE）",
    HOLD: "持有（HOLD）",
    REDUCE: "降低（REDUCE）",
    BUY: "买入（BUY）",
    SELL: "卖出（SELL）",
    WATCHLIST: "观察（WATCHLIST）",
    BALANCED: "平衡（BALANCED）",
    CONSERVATIVE: "保守（CONSERVATIVE）",
    AGGRESSIVE: "进取（AGGRESSIVE）",
    LOW: "低（LOW）",
    MEDIUM: "中（MEDIUM）",
    HIGH: "高（HIGH）",
    SHORT: "短期（SHORT）",
    LONG: "长期（LONG）",
    NOVICE: "新手（NOVICE）",
    INTERMEDIATE: "中等（INTERMEDIATE）",
    EXPERIENCED: "丰富（EXPERIENCED）",
    MODERATE: "中等（MODERATE）",
    CNY: "人民币元（CNY）",
    PCT: "百分比（PCT）",
    USD: "美元（USD）",
    RATING_RANK: "评级序数（rating_rank）",
    SCORE: "分数（score）",
    REPAIRED: "已修复（REPAIRED）",
    WITHIN_LIMIT: "未超过上限（WITHIN_LIMIT）",
    USE_QUESTIONNAIRE: "使用问卷值（USE_QUESTIONNAIRE）",
    USE_EXTRACTION: "使用提取值（USE_EXTRACTION）",
    DIRECT: "主数据提供方直连（DIRECT）",
    CACHE_FRESH: "新鲜缓存（CACHE_FRESH）",
    FALLBACK_PROVIDER: "备用数据提供方（FALLBACK_PROVIDER）",
    CACHE_STALE_FALLBACK: "陈旧缓存回退（CACHE_STALE_FALLBACK）",
    UNAVAILABLE: "未提供（UNAVAILABLE）",
    ACCOUNTS_RECEIVABLE_CNY: "应收账款（accounts_receivable_cny）",
    DEBT_RATIO_PCT: "资产负债率（debt_ratio_pct）",
    GROSS_MARGIN_PCT: "毛利率（gross_margin_pct）",
    NET_PROFIT_CNY: "净利润（net_profit_cny）",
    OPERATING_CASH_FLOW_CNY: "经营活动现金流（operating_cash_flow_cny）",
    REVENUE_CNY: "营业收入（revenue_cny）",
    REVENUE: "营业收入（revenue）",
    TECHNOLOGY_WEIGHT_PCT: "科技行业权重（technology_weight_pct）",
    GROWTH_PCT: "增长率（growth_pct）",
    POLICY_RATE_PCT: "政策利率（policy_rate_pct）",
    ANNUALIZED_VOLATILITY_PCT: "年化波动率（annualized_volatility_pct）",
    EXPENSE_RATIO_PCT: "费率（expense_ratio_pct）",
    MAX_DRAWDOWN_PCT: "最大回撤（max_drawdown_pct）",
    TOP10_WEIGHT_PCT: "前十大持仓权重（top10_weight_pct）",
    TRACKING_ERROR_PCT: "跟踪误差（tracking_error_pct）",
    BOND_FLOOR: "债底（bond_floor）",
    BOND_PRICE: "转债价格（bond_price）",
    CONVERSION_PREMIUM_PCT: "转股溢价率（conversion_premium_pct）",
    CONVERSION_PRICE: "转股价（conversion_price）",
    CONVERSION_VALUE: "转股价值（conversion_value）",
    CREDIT_RATING_RANK: "信用评级序数（credit_rating_rank）",
    LIQUIDITY_SCORE: "流动性等级序数（liquidity_score）",
    UNDERLYING_STOCK_PRICE: "正股价格（underlying_stock_price）",
    YIELD_TO_MATURITY_PCT: "到期收益率（yield_to_maturity_pct）",
    CAP_AND_REDISTRIBUTE_V1: "上限重分配（CAP_AND_REDISTRIBUTE_V1）",
    LTE: "不高于（LTE）",
    GTE: "不低于（GTE）",
    GT: "高于（GT）",
    LT: "低于（LT）",
    EQ: "等于（EQ）",
    INFO: "提示（INFO）",
    WARN: "警告（WARN）",
    WARNING: "警告（WARNING）",
    CRITICAL: "严重（CRITICAL）",
    ERROR: "错误（ERROR）",
    SOURCE_PARTIAL: "来源部分缺失（SOURCE_PARTIAL）",
    SOURCE_DISAGREEMENT: "来源分歧（SOURCE_DISAGREEMENT）",
    SOURCE_EMPTY: "来源无结果（SOURCE_EMPTY）",
    SOURCE_FAILED: "来源失败（SOURCE_FAILED）",
    INFEASIBLE: "不可行（INFEASIBLE）",
    "Synthetic Balanced ETF": "合成平衡 ETF（Synthetic Balanced ETF）",
    "Synthetic Technology Basket": "合成科技资产篮子（Synthetic Technology Basket）",
    "Synthetic Healthcare Basket": "合成医疗健康资产篮子（Synthetic Healthcare Basket）",
    "Synthetic Finance Basket": "合成金融资产篮子（Synthetic Finance Basket）",
    "Synthetic Industrials Basket": "合成工业资产篮子（Synthetic Industrials Basket）",
    "Synthetic Utilities Basket": "合成公用事业资产篮子（Synthetic Utilities Basket）",
  });

  const DISPLAY_SCENARIO_LABELS = Object.freeze({
    BASELINE_READY: "基线：完整多资产快照（BASELINE_READY）",
    TIGHTER_TECH_CAP: "科技限额收紧 10%（TIGHTER_TECH_CAP）",
    TOP_ASSET_TRIM_10PP: "第一大资产削减 10%（TOP_ASSET_TRIM_10PP）",
    LOOKTHROUGH_PARTIAL: "基金穿透部分缺失（LOOKTHROUGH_PARTIAL）",
    SOURCE_PARTIAL: "来源部分缺失（SOURCE_PARTIAL）",
    SOURCE_DISAGREEMENT: "来源分歧（SOURCE_DISAGREEMENT）",
    SOURCE_EMPTY: "来源无结果（SOURCE_EMPTY）",
    SOURCE_FAILED: "来源失败（SOURCE_FAILED）",
    INFEASIBLE: "不可行：配置上限无法同时满足（INFEASIBLE）",
  });

  const DISPLAY_DESCRIPTIONS = Object.freeze({
    "complete multi-asset snapshot": "完整多资产持仓快照",
    "tighten technology budget cap by 10 percent": "将科技行业风险预算上限收紧 10%",
    "reduce top asset weight by 10 percentage points and redistribute to remaining assets": "将第一大资产权重削减 10 个百分点并等比重分配至其余资产",
    "degrade fund look-through coverage to 80 percent": "将基金/ETF穿透覆盖率下调至 80% 触发部分缺失",
    "fund look-through coverage is below 100 percent": "基金穿透覆盖率低于 100%",
    "one-asset concentration cannot satisfy every configured cap": "单一资产集中度无法同时满足全部配置上限",
    "provider returned no records for the requested scope": "数据提供方在请求范围内没有返回记录",
    "synthetic fixture returned no records for the requested scope": "合成样例在请求范围内没有返回记录",
    "synthetic fixture omitted a required field": "合成样例缺少必需字段",
    "synthetic fixture source was unavailable": "合成样例来源不可用",
    "source B was unavailable in this offline replay": "来源 B 在离线回放中不可用",
    "research run was not fully completed; findings require human review": "研究运行未完整完成；发现需要人工复核",
    "research run was partial; supported claim requires human review": "研究运行部分完成；已支持结论需要人工复核",
    "research run was not completed; supported claim requires human review": "研究运行未完成；已支持结论需要人工复核",
    "claim requires review before it can be consumed downstream": "结论在下游使用前需要人工复核",
    "provider returned a partial payload with declared missing fields": "数据提供方返回了已声明缺失字段的部分结果",
    "provider returned a partial payload requiring review": "数据提供方返回部分结果，需要人工复核",
    "provider output could not be normalized safely": "数据提供方结果无法安全规范化",
    "provider served stale cached data because fresh data was unavailable": "新鲜数据不可用，已提供陈旧缓存",
    "one or more stale provider fields were not usable as scalar observations": "一个或多个陈旧来源字段不能作为标量观测使用",
    "stale provider output contained no usable scalar observation": "陈旧来源结果没有可用的标量观测",
    "provider returned no usable scalar observation": "数据提供方没有返回可用的标量观测",
    "one or more provider fields were not usable as scalar observations": "一个或多个来源字段不能作为标量观测使用",
    "partial provider output contained no usable scalar observation": "部分来源结果没有可用的标量观测",
    "provider did not return usable data within the node boundary": "数据提供方未在节点边界内返回可用数据",
    "research run budget was exhausted before provider execution": "研究运行预算在数据提供方执行前已耗尽",
    "provider identity did not match the requested boundary": "数据提供方身份与请求边界不匹配",
    "provider execution failed safely": "数据提供方执行已安全失败",
    "node was not started because a dependency did not complete": "依赖项未完成，因此节点未启动",
    "one or more required research nodes are incomplete": "一个或多个必需研究节点未完成",
    "optional research nodes were incomplete; run is partial": "可选研究节点未完成；本次运行为部分完成",
    "research run deadline exceeded before node completion": "研究运行在节点完成前超过截止时间",
    "research run deadline exceeded; incomplete nodes were failed safely": "研究运行超过截止时间；未完成节点已安全标记失败",
    "required research node did not complete; run was failed safely": "必需研究节点未完成；本次运行已安全失败",
    "research run stopped after a required node was incomplete": "必需研究节点未完成，研究运行已停止",
    "exposure or concentration input is not complete": "暴露或集中度输入不完整",
    "unclassified exposure requires review": "未分类暴露需要复核",
    "unlooked-through exposure requires review": "未完成基金穿透的暴露需要复核",
    "asset sector classification is ambiguous": "资产行业分类不明确",
    "configured asset and sector caps cannot close to 100 percent": "配置的资产与行业上限无法闭合至 100%",
    "partial replay requires a fund look-through snapshot": "部分回放需要基金穿透快照",
    "exposure or concentration calculation failed": "暴露或集中度计算失败",
    "risk-budget assessment is blocked; no allocation envelope was produced": "风险预算评估已阻断；未生成配置约束包",
    "budget limits or input coverage require human review; no executable instruction was produced": "预算上限或输入覆盖需要人工复核；未生成可执行指令",
    "exposure report is unavailable; concentration was blocked": "暴露报告不可用；集中度评估已阻断",
    "exposure data is partial; concentration requires review": "暴露数据不完整；集中度评估需要复核",
    "concentration report is unavailable; budget assessment was blocked": "集中度报告不可用；风险预算评估已阻断",
    "concentration data is partial; assessment requires review": "集中度数据不完整；风险预算评估需要复核",
    "recommendation input failed contract validation": "建议输入未通过契约校验",
    "recommendation identity contains a sensitive field": "建议身份包含敏感字段",
    "recommendation inputs do not share one owner": "建议输入不属于同一隔离标识",
    "recommendation inputs do not share one profile version": "建议输入不属于同一画像版本",
    "portfolio and exposure inputs do not close one snapshot": "持仓与暴露输入未闭合到同一快照",
    "risk assessment does not close the portfolio reports": "风险评估未闭合持仓报告",
    "allocation envelope does not close the risk assessment": "配置约束包未闭合风险评估",
    "decision gate does not match the current inputs": "决策闸门与当前输入不匹配",
    "PASS recommendation requires complete portfolio risk inputs": "通过状态的建议需要完整持仓风险输入",
    "recommendation generated_at must be timezone-aware": "建议生成时间必须带时区",
    "aggregate risk breach has no executable asset mapping": "汇总风险超限没有可执行的资产映射",
    "allocation envelope has no deterministic actionable bands": "配置约束包没有确定性可执行区间",
    "actionable bands do not close remediation breaches": "可执行区间未闭合风险修复超限",
    "gate input failed contract validation": "闸门输入未通过契约校验",
    "gate identity contains a disallowed sensitive field": "闸门身份包含不允许的敏感字段",
    "risk inputs do not share one owner": "风险输入不属于同一隔离标识",
    "risk inputs do not share one profile": "风险输入不属于同一风险画像",
    "risk budget is not bound to the active profile": "风险预算未绑定当前画像",
    "allocation envelope is not bound to the risk assessment": "配置约束包未绑定风险评估",
    "allocation constraints do not match the active risk budget": "配置约束与当前风险预算不匹配",
    "allocation breach references do not match the risk assessment": "配置超限引用与风险评估不匹配",
    "risk assessment contains duplicate constraint breaches": "风险评估包含重复约束超限",
    "allocation breach is attached to the wrong constraint": "配置超限绑定了错误约束",
    "allocation reduction does not match its risk breach": "配置缩减与风险超限不匹配",
    "allocation status does not match the risk assessment": "配置状态与风险评估不匹配",
    "research evidence pipeline is blocked": "研究证据流程已阻断",
    "research evidence requires human review": "研究证据需要人工复核",
    "ready research trace is incomplete": "就绪研究证据链不完整",
    "research trace contains non-verified evidence": "研究证据链包含未验证证据",
    "research trace contains a non-verified fact": "研究证据链包含未验证事实",
    "research trace has an unknown evidence reference": "研究证据链引用了未知证据",
    "research trace has an unknown fact reference": "研究证据链引用了未知事实",
    "ready research bridge is incomplete": "就绪研究桥接不完整",
    "research bridge does not match the registered trace": "研究桥接与已登记证据链不匹配",
    "research trace must not contain recommendations": "研究证据链不得包含建议",
    "risk budget assessment is blocked": "风险预算评估已阻断",
    "risk budget assessment requires human review": "风险预算评估需要人工复核",
    "allocation constraint envelope is blocked": "配置约束包已阻断",
    "allocation constraint envelope requires human review": "配置约束包需要人工复核",
    "ready allocation has no envelope": "就绪配置没有约束包",
    "Provider execution was cancelled": "数据提供方执行已取消",
    "Internal provider execution error": "数据提供方内部执行错误",
    "Provider response identity did not match the requested boundary": "数据提供方响应身份与请求边界不匹配",
    "source B returned no stock record for the requested period": "来源 B 在请求报告期内没有返回个股记录",
    "source B returned no fund record for the requested period": "来源 B 在请求报告期内没有返回基金记录",
    "source B returned no convertible bond record for the requested period": "来源 B 在请求报告期内没有返回可转债记录",
    "offline synthetic four-track research matrix": "离线合成四轨道研究矩阵",
    "offline synthetic stock research Demo F": "离线合成个股研究（演示 F）",
    "offline synthetic ETF fund asset research replay": "离线合成 ETF / 基金资产研究回放",
    "offline synthetic convertible bond asset research replay": "离线合成可转债资产研究回放",
    "offline synthetic five-asset target-structure replay": "离线合成五资产目标结构回放",
    "single-asset cap applied; released weight is redistributed by stable headroom order": "已应用单资产上限；释放的权重按稳定的剩余容量顺序重分配",
    "target is deterministic and profile-conditioned; it is not a trade instruction": "目标由确定性规则和风险画像共同决定；不是交易指令",
    "sector cap is applied before deterministic redistribution": "先应用行业上限，再执行确定性重分配",
    "aggregate budget dimension is checked independently of sector labels": "独立检查汇总预算维度，不受行业标签影响",
    "aggregate exposure contributions into asset and sector buckets": "将暴露贡献汇总到资产和行业桶",
    "cap sector, technology and unclassified buckets using the confirmed risk budget": "使用已确认风险预算限制行业、科技和未分类桶",
    "redistribute released weight by largest headroom then stable ID": "按剩余容量从大到小、再按稳定 ID 重分配释放权重",
    "allocate each bucket proportionally with a single-asset cap and cent-level closure": "在单资产上限和分厘闭合约束下按比例分配各桶",
    "synthetic two-source revenue cross-check": "合成双来源收入交叉核验",
    "Review technology exposure through Macro, Industry, Stock and ETF/Fund tracks.": "通过宏观、行业、个股和 ETF / 基金轨道复核科技暴露",
    "Review portfolio risk constraints through Macro, Industry, Stock and ETF/Fund tracks.": "通过宏观、行业、个股和 ETF / 基金轨道复核组合风险约束",
    "Risk Profile version or risk budget rule changes": "风险画像版本或风险预算规则发生变化",
    "portfolio bundle or position snapshot changes": "持仓包或持仓快照发生变化",
    "fund look-through coverage or base currency changes": "基金穿透覆盖率或基准货币发生变化",
    "CAP_AND_REDISTRIBUTE_V1 methodology changes": "上限重分配（CAP_AND_REDISTRIBUTE_V1）方法发生变化",
    "validate owner, profile and portfolio input": "校验隔离标识、风险画像和持仓输入",
    "calculate exposure, concentration and profile-conditioned risk budget": "计算暴露、集中度和画像约束风险预算",
    "preserve review or blocked state when inputs are incomplete or infeasible": "输入不完整或不可行时保留待复核/阻断状态",
    "fixture stale replay": "样例陈旧回放",
    "technology weight threshold": "科技行业权重阈值",
    "top10 concentration threshold": "前十大持仓集中度阈值",
    "annualized volatility threshold": "年化波动率阈值",
    "maximum drawdown threshold": "最大回撤阈值",
    "expense ratio threshold": "费率阈值",
    "conversion premium threshold": "转股溢价率阈值",
    "bond floor threshold": "债底阈值",
    "negative yield threshold": "负收益率阈值",
    "credit rating rank threshold": "信用评级序数阈值",
    "liquidity score threshold": "流动性等级序数阈值",
  });

  const DISPLAY_LABELS = Object.freeze({
    Owner: "隔离标识",
    Bundle: "持仓包",
    "Position snapshot": "持仓快照",
    "Base currency": "基准货币",
    "As of": "截止时间",
    Asset: "资产",
    Position: "持仓明细",
    Quantity: "数量",
    "Market value": "市值",
    Underlying: "底层资产",
    Holding: "穿透持仓",
    Weight: "权重",
    "Saved at": "保存时间",
    Profile: "风险画像",
    Questionnaire: "风险问卷",
    "Portfolio bundle": "持仓包",
    "Content hash": "内容哈希",
    "Answered at": "回答时间",
    "Loss tolerance": "损失承受度",
    Horizon: "投资期限",
    Liquidity: "流动性需求",
    Experience: "投资经验",
    "Return expectation": "收益预期",
    "Max drawdown": "最大回撤容忍度",
    "Expected range": "预期收益区间",
    "Confirmed profile": "已确认画像",
    "Risk score": "风险评分",
    "Risk level": "风险等级",
    "Profile version": "画像版本",
    "Confirmed at": "确认时间",
    Draft: "提案草稿",
    Status: "状态",
    Extraction: "提取结果",
    Confidence: "置信度",
    "Input digest": "输入摘要",
    Plan: "计划",
    Intent: "意图",
    Scope: "范围",
    Nodes: "节点数",
    Node: "节点",
    Kind: "类型",
    Missing: "缺失字段",
    "Risk assessment": "风险评估",
    "Allocation envelope": "配置约束",
    "Research run": "研究运行",
    "Finding IDs": "发现 ID",
    "Recommendation ID": "建议 ID",
    Run: "运行",
    Provider: "数据提供方",
    Source: "来源",
    Field: "字段",
    Value: "数值",
    Period: "期间",
    "Observed at": "观测时间",
    "Retrieved at": "获取时间",
    Lineage: "来源链",
    "Cache age": "缓存时长",
    Pipeline: "流程",
    Method: "方法",
    "Exposure report": "暴露报告",
    Current: "当前",
    Target: "目标",
    Delta: "变化",
    "Asset cap": "资产上限",
    "Allocation range": "配置区间",
  });

  function displayLabel(value, fallback = "—") {
    if (value === null || value === undefined || value === "") return fallback;
    const rendered = String(value);
    return DISPLAY_LABELS[rendered] || rendered;
  }

  function displayDescription(value, fallback = "—") {
    if (value === null || value === undefined || value === "") return fallback;
    const rendered = String(value);
    if (DISPLAY_DESCRIPTIONS[rendered]) return DISPLAY_DESCRIPTIONS[rendered];
    const replay = rendered.match(/^(.+?) · replay ([A-Z0-9_]+)$/);
    if (replay && DISPLAY_DESCRIPTIONS[replay[1]]) {
      return `${DISPLAY_DESCRIPTIONS[replay[1]]} · 回放 ${replay[2]}`;
    }
    const timeout = rendered.match(/^Request timed out after (\d+)ms$/i);
    if (timeout) return `请求超过 ${timeout[1]} 毫秒后超时`;
    const fixtureMiss = rendered.match(/^No matching fixture found for fingerprint (.+)$/i);
    if (fixtureMiss) return `没有找到匹配请求指纹的合成样例：${fixtureMiss[1]}`;
    return rendered;
  }

  function displayScenarioLabel(scenario) {
    const value = scenario && typeof scenario === "object" ? scenario.label || scenario.scenario_id : scenario;
    if (value === null || value === undefined || value === "") return "未命名场景";
    return DISPLAY_SCENARIO_LABELS[String(value)] || text(value, "未命名场景");
  }

  function displayScenarioDescription(scenario) {
    const value = scenario && typeof scenario === "object" ? scenario.description : scenario;
    return displayDescription(value, "无场景说明");
  }

  function displayMethodology(value) {
    if (value === null || value === undefined || value === "") return "—";
    const rendered = String(value);
    return displayDescription(rendered)
      .replace(/^deterministic Decimal ratio:/, "确定性 Decimal 比率：")
      .replace(/^deterministic Decimal threshold:/, "确定性 Decimal 阈值：")
      .replace(/^deterministic Decimal convertible-bond-formula\.v1;/, "确定性 Decimal 可转债公式（convertible-bond-formula.v1）；")
      .replace(/^input_fact_ids=/, "输入事实 ID=")
      .replace(/configured (stock-risk|fund-risk|convertible-bond-risk)\.v1 limit/, "配置的 $1.v1 限值")
      .replace(/configured (stock-risk|fund-risk|convertible-bond-risk)\.v1/, "配置的 $1.v1")
      .replace(/technology weight threshold/g, "科技行业权重阈值")
      .replace(/top10 concentration threshold/g, "前十大持仓集中度阈值")
      .replace(/annualized volatility threshold/g, "年化波动率阈值")
      .replace(/maximum drawdown threshold/g, "最大回撤阈值")
      .replace(/expense ratio threshold/g, "费率阈值")
      .replace(/conversion premium threshold/g, "转股溢价率阈值")
      .replace(/bond floor threshold/g, "债底阈值")
      .replace(/negative yield threshold/g, "负收益率阈值")
      .replace(/credit rating rank threshold/g, "信用评级序数阈值")
      .replace(/liquidity score threshold/g, "流动性等级序数阈值")
      .replace(/; stock-risk\.v1$/, "；stock-risk.v1")
      .replace(/; fund-risk\.v1$/, "；fund-risk.v1")
      .replace(/; convertible-bond-risk\.v1$/, "；convertible-bond-risk.v1");
  }

  function text(value, fallback = "—") {
    if (value === null || value === undefined || value === "") return fallback;
    const rendered = String(value);
    return DISPLAY_VALUE_LABELS[rendered] || DISPLAY_VALUE_LABELS[rendered.toUpperCase()] || rendered;
  }

  function clear(node) {
    node.replaceChildren();
  }

  function setError(message = "") {
    const node = byId("global-error");
    const rendered = message ? String(message) : "";
    const safeMessage = !rendered
      ? ""
      : /[\u3400-\u9fff]/.test(rendered)
        ? rendered
        : "操作未完成，请检查输入或稍后重试。";
    node.textContent = safeMessage;
    node.hidden = !safeMessage;
  }

  function setQueryStatus(message, className = "") {
    const node = byId("query-status");
    node.className = `status-chip ${className}`.trim();
    node.textContent = message;
  }

  function researchStatusClass(status) {
    return status === "READY" || status === "COMPLETED" || status === "COMPLETE" || status === "SUPPORTED"
      ? "pass"
      : status === "REVIEW_REQUIRED" || status === "PARTIAL" || status === "CONTRADICTED" || status === "UNRESOLVED" || status === "INSUFFICIENT"
        ? "review"
        : "blocked";
  }

  function researchStatusLabel(status) {
    return DISPLAY_VALUE_LABELS[status] || text(status, "待运行");
  }

  function setResearchStatus(message, className = "") {
    const node = byId("research-status");
    node.className = `status-chip ${className}`.trim();
    node.textContent = message;
  }

  function setStockResearchStatus(message, className = "") {
    const node = byId("stock-research-status");
    node.className = `status-chip ${className}`.trim();
    node.textContent = message;
  }

  function setFundResearchStatus(message, className = "") {
    const node = byId("fund-research-status");
    node.className = `status-chip ${className}`.trim();
    node.textContent = message;
  }

  function setConvertibleBondResearchStatus(message, className = "") {
    const node = byId("convertible-bond-research-status");
    node.className = `status-chip ${className}`.trim();
    node.textContent = message;
  }

  function setPortfolioOptimizationStatus(message, className = "") {
    const node = byId("portfolio-optimization-status");
    node.className = `status-chip ${className}`.trim();
    node.textContent = message;
  }

  function setScenarioSimulationStatus(message, className = "") {
    const node = byId("scenario-simulation-status");
    if (!node) return;
    node.className = `status-chip ${className}`.trim();
    node.textContent = message;
  }

  function setContextMemoryStatus(message, className = "") {
    const node = byId("context-memory-status");
    node.className = `status-chip ${className}`.trim();
    node.textContent = message;
  }

  function researchRoleLabel(role) {
    return DISPLAY_VALUE_LABELS[role] || text(role);
  }

  function clearResearchScenarioOptions() {
    const select = byId("research-scenario");
    clear(select);
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "读取场景目录…";
    select.append(option);
    select.disabled = true;
  }

  function renderResearchScenarioOptions(scenarios) {
    const select = byId("research-scenario");
    const previous = select.value;
    clear(select);
    const options = Array.isArray(scenarios) ? scenarios : [];
    options.forEach((scenario) => {
      const option = document.createElement("option");
      option.value = scenario.scenario_id || "";
      option.textContent = displayScenarioLabel(scenario);
      option.title = displayScenarioDescription(scenario);
      select.append(option);
    });
    if (!options.length) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "暂无可用场景";
      select.append(option);
      select.disabled = true;
      return;
    }
    const known = options.some((scenario) => scenario.scenario_id === previous);
    select.value = known ? previous : options[0].scenario_id;
    select.disabled = false;
  }

  function clearStockResearchScenarioOptions() {
    const select = byId("stock-research-scenario");
    clear(select);
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "读取场景目录…";
    select.append(option);
    select.disabled = true;
  }

  function renderStockResearchScenarioOptions(scenarios) {
    const select = byId("stock-research-scenario");
    const previous = select.value;
    clear(select);
    const options = Array.isArray(scenarios) ? scenarios : [];
    options.forEach((scenario) => {
      const option = document.createElement("option");
      option.value = scenario.scenario_id || "";
      option.textContent = displayScenarioLabel(scenario);
      option.title = displayScenarioDescription(scenario);
      select.append(option);
    });
    if (!options.length) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "暂无可用场景";
      select.append(option);
      select.disabled = true;
      return;
    }
    const known = options.some((scenario) => scenario.scenario_id === previous);
    select.value = known ? previous : options[0].scenario_id;
    select.disabled = false;
  }

  function clearFundResearchScenarioOptions() {
    const select = byId("fund-research-scenario");
    clear(select);
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "读取场景目录…";
    select.append(option);
    select.disabled = true;
  }

  function renderFundResearchScenarioOptions(scenarios) {
    const select = byId("fund-research-scenario");
    const previous = select.value;
    clear(select);
    const options = Array.isArray(scenarios) ? scenarios : [];
    options.forEach((scenario) => {
      const option = document.createElement("option");
      option.value = scenario.scenario_id || "";
      option.textContent = displayScenarioLabel(scenario);
      option.title = displayScenarioDescription(scenario);
      select.append(option);
    });
    if (!options.length) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "暂无可用场景";
      select.append(option);
      select.disabled = true;
      return;
    }
    const known = options.some((scenario) => scenario.scenario_id === previous);
    select.value = known ? previous : options[0].scenario_id;
    select.disabled = false;
  }

  function clearConvertibleBondResearchScenarioOptions() {
    const select = byId("convertible-bond-research-scenario");
    clear(select);
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "读取场景目录…";
    select.append(option);
    select.disabled = true;
  }

  function renderConvertibleBondResearchScenarioOptions(scenarios) {
    const select = byId("convertible-bond-research-scenario");
    const previous = select.value;
    clear(select);
    const options = Array.isArray(scenarios) ? scenarios : [];
    options.forEach((scenario) => {
      const option = document.createElement("option");
      option.value = scenario.scenario_id || "";
      option.textContent = displayScenarioLabel(scenario);
      option.title = displayScenarioDescription(scenario);
      select.append(option);
    });
    if (!options.length) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "暂无可用场景";
      select.append(option);
      select.disabled = true;
      return;
    }
    const known = options.some((scenario) => scenario.scenario_id === previous);
    select.value = known ? previous : options[0].scenario_id;
    select.disabled = false;
  }

  function clearPortfolioOptimizationScenarioOptions() {
    const select = byId("portfolio-optimization-scenario");
    clear(select);
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "读取场景目录…";
    select.append(option);
    select.disabled = true;
  }

  function renderPortfolioOptimizationScenarioOptions(scenarios) {
    const select = byId("portfolio-optimization-scenario");
    const previous = select.value;
    clear(select);
    const options = Array.isArray(scenarios) ? scenarios : [];
    options.forEach((scenario) => {
      const option = document.createElement("option");
      option.value = scenario.scenario_id || "";
      option.textContent = displayScenarioLabel(scenario);
      option.title = displayScenarioDescription(scenario);
      select.append(option);
    });
    if (!options.length) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "暂无可用场景";
      select.append(option);
      select.disabled = true;
      return;
    }
    const known = options.some((scenario) => scenario.scenario_id === previous);
    select.value = known ? previous : options[0].scenario_id;
    select.disabled = false;
  }

  function clearScenarioSimulationScenarioOptions() {
    const select = byId("scenario-simulation-scenario");
    if (!select) return;
    clear(select);
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "读取场景目录…";
    select.append(option);
    select.disabled = true;
  }

  function renderScenarioSimulationScenarioOptions(scenarios) {
    const select = byId("scenario-simulation-scenario");
    if (!select) return;
    const previous = select.value;
    clear(select);
    const options = Array.isArray(scenarios) ? scenarios : [];
    options.forEach((scenario) => {
      const option = document.createElement("option");
      option.value = scenario.scenario_id || "";
      option.textContent = displayScenarioLabel(scenario);
      option.title = displayScenarioDescription(scenario);
      select.append(option);
    });
    if (!options.length) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "暂无可用场景";
      select.append(option);
      select.disabled = true;
      return;
    }
    const known = options.some((scenario) => scenario.scenario_id === previous);
    select.value = known ? previous : options[0].scenario_id;
    select.disabled = false;
  }

  function stockRiskStatusClass(status) {
    return status === "CLEAR" ? "pass" : status === "WATCH" ? "review" : "blocked";
  }

  function stockRiskStatusLabel(status) {
    return DISPLAY_VALUE_LABELS[status] || "未评估";
  }

  function fundRiskStatusClass(status) {
    return stockRiskStatusClass(status);
  }

  function fundRiskStatusLabel(status) {
    return stockRiskStatusLabel(status);
  }

  function convertibleBondRiskStatusClass(status) {
    return stockRiskStatusClass(status);
  }

  function convertibleBondRiskStatusLabel(status) {
    return stockRiskStatusLabel(status);
  }

  function optimizationStatusLabel(status) {
    return DISPLAY_VALUE_LABELS[status] || text(status, "待运行");
  }

  function optimizationStatusClass(status) {
    return status === "READY" ? "pass" : status === "REVIEW_REQUIRED" ? "review" : "blocked";
  }

  function statusClass(status) {
    return status === "PASS" ? "pass" : status === "REVIEW_REQUIRED" ? "review" : "blocked";
  }

  function statusLabel(status) {
    return DISPLAY_VALUE_LABELS[status] || text(status, "未知状态");
  }

  function chip(label, className) {
    const node = document.createElement("span");
    node.className = `status-chip ${className || ""}`.trim();
    node.textContent = text(label, "");
    return node;
  }

  function renderEvents() {
    const list = byId("event-list");
    clear(list);
    byId("event-count").textContent = `${state.events.length} 条事件`;
    if (!state.events.length) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "当前隔离标识还没有保存的决策事件。";
      list.append(empty);
      return;
    }
    state.events.forEach((event) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `event-row${state.selected === event.event_id ? " selected" : ""}`;
      button.addEventListener("click", () => loadEvent(event.event_id));
      const top = document.createElement("div");
      top.className = "event-row-top";
      const id = document.createElement("span");
      id.className = "event-row-id";
      id.textContent = event.receipt_id || event.event_id;
      top.append(id, chip(statusLabel(event.status), statusClass(event.status)));
      const bottom = document.createElement("div");
      bottom.className = "event-row-bottom";
      const composition = document.createElement("span");
      composition.textContent = event.composition_id;
      const recorded = document.createElement("time");
      recorded.dateTime = event.recorded_at;
      recorded.textContent = new Date(event.recorded_at).toLocaleString("zh-CN");
      bottom.append(composition, recorded);
      button.append(top, bottom);
      list.append(button);
    });
  }

  function addMetadata(container, label, value) {
    const item = document.createElement("div");
    const dt = document.createElement("dt");
    dt.textContent = displayLabel(label);
    const dd = document.createElement("dd");
    dd.textContent = text(value);
    item.append(dt, dd);
    container.append(item);
  }

  function renderPortfolio(portfolio, sourceLabel = "只读 · 合成模板") {
    byId("portfolio-context-label").textContent = sourceLabel;
    const panel = byId("portfolio-content");
    clear(panel);
    if (!portfolio) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "读取隔离标识模板后查看持仓快照与基金穿透范围。";
      panel.append(empty);
      return;
    }
    const snapshot = portfolio.position_snapshot;
    const summary = document.createElement("dl");
    summary.className = "portfolio-summary";
    addMetadata(summary, "Owner", portfolio.owner_id);
    addMetadata(summary, "Bundle", portfolio.bundle_id);
    addMetadata(summary, "Position snapshot", snapshot.snapshot_id);
    addMetadata(summary, "As of", snapshot.as_of);
    addMetadata(summary, "Base currency", snapshot.base_currency);
    panel.append(summary);

    const positionsHeading = document.createElement("h3");
    positionsHeading.className = "context-heading";
    positionsHeading.textContent = "持仓明细";
    panel.append(positionsHeading);
    const positions = document.createElement("div");
    positions.className = "position-grid";
    (snapshot.positions || []).forEach((position) => {
      const card = document.createElement("article");
      card.className = "position-card";
      const header = document.createElement("header");
      const title = document.createElement("strong");
      title.textContent = text(position.asset_name);
      header.append(title, chip(text(position.asset_type), ""));
      card.append(header);
      const metadata = document.createElement("dl");
      addMetadata(metadata, "Asset", position.asset_id);
      addMetadata(metadata, "Position", position.position_id);
      addMetadata(metadata, "Quantity", position.quantity);
      addMetadata(metadata, "Market value", `${text(position.market_value)} ${text(position.currency)}`);
      card.append(metadata);
      positions.append(card);
    });
    panel.append(positions);

    const holdingHeading = document.createElement("h3");
    holdingHeading.className = "context-heading";
    holdingHeading.textContent = "基金穿透持仓";
    panel.append(holdingHeading);
    if (!(portfolio.fund_holdings || []).length) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "当前模板没有基金/ETF 穿透快照。";
      panel.append(empty);
      return;
    }
    (portfolio.fund_holdings || []).forEach((fund) => {
      const section = document.createElement("section");
      section.className = "holding-section";
      const meta = document.createElement("div");
      meta.className = "holding-meta";
      meta.textContent = `${text(fund.parent_asset_id)} · 快照 ${text(fund.snapshot_id)} · 覆盖率 ${text(fund.coverage_pct)}% · 截止 ${text(fund.as_of)}`;
      section.append(meta);
      const holdings = document.createElement("div");
      holdings.className = "holding-grid";
      (fund.holdings || []).forEach((holding) => {
        const card = document.createElement("article");
        card.className = "holding-card";
        const header = document.createElement("header");
        const title = document.createElement("strong");
        title.textContent = text(holding.underlying_name);
        header.append(title, chip(text(holding.sector, "未分类"), ""));
        card.append(header);
        const metadata = document.createElement("dl");
        addMetadata(metadata, "Underlying", holding.underlying_asset_id);
        addMetadata(metadata, "Holding", holding.holding_id);
        addMetadata(metadata, "Weight", `${text(holding.weight_pct)}%`);
        addMetadata(metadata, "As of", holding.as_of);
        card.append(metadata);
        holdings.append(card);
      });
      section.append(holdings);
      panel.append(section);
    });
  }

  function renderContextMemory(records = state.contextMemoryRecords) {
    const panel = byId("context-memory-content");
    clear(panel);
    const items = Array.isArray(records) ? records : [];
    if (!items.length) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "暂无已保存上下文；保存前必须先确认风险画像与持仓。";
      panel.append(empty);
      return;
    }
    items.forEach((record) => {
      const card = document.createElement("article");
      card.className = `context-memory-card${state.contextMemorySelected === record.memory_id ? " selected" : ""}`;
      const header = document.createElement("header");
      const title = document.createElement("strong");
      title.textContent = `${text(record.profile?.risk_level)} · ${text(record.memory_id)}`;
      header.append(title, chip(text(record.source, "EXPLICIT_SAVE"), "pass"));
      card.append(header);
      const metadata = document.createElement("dl");
      metadata.className = "metadata-grid";
      addMetadata(metadata, "Saved at", record.saved_at);
      addMetadata(metadata, "Profile", `${text(record.profile?.profile_id)} · v${text(record.profile?.profile_version)}`);
      addMetadata(metadata, "Questionnaire", record.questionnaire?.questionnaire_id);
      addMetadata(metadata, "Portfolio bundle", record.portfolio?.bundle_id);
      addMetadata(metadata, "Position snapshot", record.portfolio?.position_snapshot?.snapshot_id);
      addMetadata(metadata, "Content hash", record.content_hash);
      card.append(metadata);
      const references = record.references || {};
      const referenceValues = [
        references.research_run_id && `研究 ${references.research_run_id}`,
        references.stock_research_run_id && `个股 ${references.stock_research_run_id}`,
        references.fund_research_run_id && `基金 ${references.fund_research_run_id}`,
        references.convertible_bond_research_run_id && `可转债 ${references.convertible_bond_research_run_id}`,
        references.optimization_request_id && `组合优化 ${references.optimization_request_id}`,
      ].filter(Boolean);
      const note = document.createElement("p");
      note.className = "context-memory-references";
      note.textContent = referenceValues.length
        ? `引用：${referenceValues.join(" · ")}`
        : "未保存派生研究引用；恢复后需重新运行研究或组合流程。";
      card.append(note);
      const actions = document.createElement("div");
      actions.className = "context-import-actions";
      const restore = document.createElement("button");
      restore.type = "button";
      restore.className = "query-submit";
      restore.textContent = "显式恢复到当前会话";
      restore.addEventListener("click", () => restoreContextMemory(record));
      actions.append(restore);
      card.append(actions);
      panel.append(card);
    });
  }

  function clearContextMemory() {
    state.contextMemorySequence += 1;
    state.contextMemoryRecords = [];
    state.contextMemorySelected = null;
    setContextMemoryStatus("未读取");
    renderContextMemory([]);
  }

  function clearDerivedResultsForContextRestore() {
    state.selected = null;
    state.selectedDecisionEvent = null;
    state.advancedEvidenceSelectedKey = "";
    renderEvents();
    renderProfile(null);
    renderEvidence(null);
    byId("detail-status").className = "status-chip";
    byId("detail-status").textContent = "待选择";
    clear(byId("detail-content"));
    const detailEmpty = document.createElement("div");
    detailEmpty.className = "empty-state";
      detailEmpty.textContent = "上下文已恢复；请重新运行投顾查询后查看新的决策回执。";
    byId("detail-content").append(detailEmpty);
    clearAdvisorPlan();
    clearProfileProposal();
    state.researchRun = null;
    state.researchSequence += 1;
    renderResearchMatrix(null);
    setResearchStatus("需重新运行", "review");
    state.stockResearchRun = null;
    state.stockResearchSequence += 1;
    renderStockResearch(null);
    setStockResearchStatus("需重新运行", "review");
    state.fundResearchRun = null;
    state.fundResearchSequence += 1;
    renderFundResearch(null);
    setFundResearchStatus("需重新运行", "review");
    state.convertibleBondResearchRun = null;
    state.convertibleBondResearchSequence += 1;
    renderConvertibleBondResearch(null);
    setConvertibleBondResearchStatus("需重新运行", "review");
    clearPortfolioOptimizationRun("需重新运行", "review");
  }

  function restoreContextMemory(record) {
    if (!record || record.owner_id !== state.ownerId) {
      state.contextMemorySelected = null;
      setContextMemoryStatus("恢复被拒绝", "blocked");
      setError("上下文记忆不属于当前隔离标识，未恢复。");
      renderContextMemory();
      clearDerivedResultsForContextRestore();
      return;
    }
    state.contextMemorySelected = record.memory_id;
    state.profileContext = {
      questionnaire: record.questionnaire,
      profile: record.profile,
    };
    state.portfolioContext = record.portfolio;
    const questionnaireId = text(record.questionnaire?.questionnaire_id, "");
    const queryId = questionnaireId.endsWith("-questionnaire")
      ? questionnaireId.slice(0, -"-questionnaire".length)
      : questionnaireId;
    if (queryId) byId("query-id").value = queryId;
    [
      ["loss-tolerance", record.questionnaire?.loss_tolerance_score],
      ["investment-horizon", record.questionnaire?.investment_horizon],
      ["liquidity-need", record.questionnaire?.liquidity_need],
      ["experience-level", record.questionnaire?.experience_level],
      ["return-expectation", record.questionnaire?.return_expectation],
      ["max-drawdown", record.questionnaire?.max_drawdown_tolerance_pct],
    ].forEach(([id, value]) => {
      if (value !== undefined && value !== null) byId(id).value = String(value);
    });
    renderPortfolio(record.portfolio, "已恢复 · 本地结构化记忆");
    renderProfileContext(record.questionnaire);
    renderConfirmedProfile(record.profile);
    setPortfolioContextStatus("已恢复 · 当前会话只读", "pass");
    setProfileContextStatus(`已恢复 · ${text(record.profile?.risk_level)}`, "pass");
    clearDerivedResultsForContextRestore();
    setContextMemoryStatus("已显式恢复 · 派生结果已清空", "pass");
    setError("");
    renderContextMemory();
  }

  function buildContextMemoryReferences() {
    const research = state.researchRun;
    const stock = state.stockResearchRun;
    const fund = state.fundResearchRun;
    const convertible = state.convertibleBondResearchRun;
    const optimization = state.portfolioOptimizationRun;
    return {
      research_matrix_id: research?.matrix_id || null,
      research_run_id: research?.run_id || null,
      research_scenario_id: research?.scenario?.scenario_id || null,
      stock_research_run_id: stock?.request_id || null,
      stock_research_scenario_id: stock?.scenario?.scenario_id || null,
      fund_research_run_id: fund?.request_id || null,
      fund_research_scenario_id: fund?.scenario?.scenario_id || null,
      convertible_bond_research_run_id: convertible?.request_id || null,
      convertible_bond_research_scenario_id: convertible?.scenario?.scenario_id || null,
      optimization_request_id: optimization?.request_id || null,
      optimization_scenario_id: optimization?.scenario?.scenario_id || null,
    };
  }

  async function saveContextMemory() {
    const requestOwner = byId("owner-id").value.trim();
    if (!requestOwner) {
      setContextMemoryStatus("需要隔离标识", "blocked");
      setError("请输入隔离标识。");
      return;
    }
    if (requestOwner !== state.ownerId) {
      state.ownerId = requestOwner;
      resetOwnerScopedViews();
      setContextMemoryStatus("需先读取隔离标识", "review");
      setError("请先读取该隔离标识，再确认风险画像与持仓。");
      return;
    }
    if (!state.profileContext?.profile || !state.profileContext?.questionnaire) {
      setContextMemoryStatus("需先确认画像", "review");
      setError("请先确认风险画像，再保存上下文记忆。");
      return;
    }
    if (!state.portfolioContext) {
      setContextMemoryStatus("需先确认持仓", "review");
      setError("请先验证并加载持仓，再保存上下文记忆。");
      return;
    }
    const sequence = ++state.contextMemorySequence;
    const submit = byId("save-context-memory");
    submit.disabled = true;
    setError("");
    setContextMemoryStatus("保存中…");
    try {
      const response = await fetch("/api/v1/advisor/context-memory", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Owner-ID": requestOwner,
        },
        body: JSON.stringify({
          schema_version: "context-memory-write-request.v1",
          owner_id: requestOwner,
          questionnaire: state.profileContext.questionnaire,
          profile: state.profileContext.profile,
          portfolio: state.portfolioContext,
          references: buildContextMemoryReferences(),
        }),
      });
      if (!response.ok) throw await apiError(response);
      if (state.ownerId !== requestOwner || state.contextMemorySequence !== sequence) return;
      const result = await response.json();
      state.contextMemorySelected = result.record?.memory_id || null;
      setContextMemoryStatus(result.created ? "已保存 · EXPLICIT_SAVE" : "已复用 · 内容未改变", "pass");
      await loadContextMemory(requestOwner);
    } catch (error) {
      if (state.ownerId === requestOwner && state.contextMemorySequence === sequence) {
        state.contextMemorySelected = null;
        setContextMemoryStatus("未保存", "blocked");
        renderContextMemory();
        setError(error.message || "保存上下文记忆失败");
      }
    } finally {
      submit.disabled = false;
    }
  }

  async function loadContextMemory(ownerId = state.ownerId) {
    const requestOwner = ownerId;
    const sequence = ++state.contextMemorySequence;
    if (!requestOwner) {
      clearContextMemory();
      return;
    }
    setContextMemoryStatus("读取中…");
    try {
      const response = await fetch("/api/v1/advisor/context-memory?limit=20", {
        headers: { "X-Owner-ID": requestOwner },
      });
      if (!response.ok) throw await apiError(response);
      if (state.ownerId !== requestOwner || state.contextMemorySequence !== sequence) return;
      const result = await response.json();
      state.contextMemoryRecords = Array.isArray(result.records) ? result.records : [];
      state.contextMemorySelected = null;
      setContextMemoryStatus(
        state.contextMemoryRecords.length ? `${state.contextMemoryRecords.length} 条最近记忆` : "暂无记忆",
        state.contextMemoryRecords.length ? "pass" : "",
      );
      renderContextMemory();
    } catch (error) {
      if (state.ownerId === requestOwner && state.contextMemorySequence === sequence) {
        state.contextMemoryRecords = [];
        state.contextMemorySelected = null;
        setContextMemoryStatus("读取失败", "blocked");
        renderContextMemory([]);
        setError(error.message || "读取上下文记忆失败");
      }
    }
  }

  function renderProfileContext(questionnaire) {
    const panel = byId("profile-template-content");
    clear(panel);
    if (!questionnaire) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "读取隔离标识模板后查看风险问卷约束。";
      panel.append(empty);
      return;
    }
    const metadata = document.createElement("dl");
    addMetadata(metadata, "Questionnaire", questionnaire.questionnaire_id);
    addMetadata(metadata, "Owner", questionnaire.owner_id);
    addMetadata(metadata, "Answered at", questionnaire.answered_at);
    addMetadata(metadata, "Loss tolerance", questionnaire.loss_tolerance_score);
      addMetadata(metadata, "Horizon", questionnaire.investment_horizon);
    addMetadata(metadata, "Liquidity", questionnaire.liquidity_need);
    addMetadata(metadata, "Experience", questionnaire.experience_level);
    addMetadata(metadata, "Return expectation", questionnaire.return_expectation);
    addMetadata(metadata, "Max drawdown", `${text(questionnaire.max_drawdown_tolerance_pct)}%`);
    const expected = questionnaire.expected_return_range;
    addMetadata(
      metadata,
      "Expected range",
      expected ? `${text(expected.minimum_pct)}% — ${text(expected.maximum_pct)}%` : "未设置",
    );
    panel.append(metadata);
  }

  function renderConfirmedProfile(profile) {
    const panel = byId("profile-confirmation-content");
    clear(panel);
    if (!profile) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "确认问卷后查看确定性画像结果。";
      panel.append(empty);
      return;
    }
    const metadata = document.createElement("dl");
    metadata.className = "metadata-grid";
    addMetadata(metadata, "Confirmed profile", profile.profile_id);
    addMetadata(metadata, "Questionnaire", profile.questionnaire_id);
    addMetadata(metadata, "Risk score", profile.risk_score);
    addMetadata(metadata, "Risk level", profile.risk_level);
    addMetadata(metadata, "Profile version", profile.profile_version);
    addMetadata(metadata, "Confirmed at", profile.created_at);
    panel.append(metadata);
  }

  function setPortfolioContextStatus(message, className = "") {
    const node = byId("portfolio-context-status");
    node.className = `status-chip ${className}`.trim();
    node.textContent = message;
  }

  function setProfileContextStatus(message, className = "") {
    const node = byId("profile-context-status");
    node.className = `status-chip ${className}`.trim();
    node.textContent = message;
  }

  function setProfileProposalStatus(message, className = "") {
    const node = byId("profile-proposal-status");
    node.className = `status-chip ${className}`.trim();
    node.textContent = message;
  }

  function setProfileProposalConfirmStatus(message, className = "") {
    const node = byId("profile-proposal-confirm-status");
    node.className = `status-chip ${className}`.trim();
    node.textContent = message;
  }

  function profileDimensionLabel(dimension) {
    return {
      investment_horizon: "投资期限",
      liquidity_need: "流动性需求",
      experience_level: "投资经验",
      return_expectation: "收益预期",
      max_drawdown_tolerance_pct: "最大回撤容忍度",
      expected_return_range: "预期收益区间",
    }[dimension] || text(dimension);
  }

  function renderProfileProposalResult(profile) {
    const panel = byId("profile-proposal-result");
    clear(panel);
    if (!profile) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "确认提案后查看保留冲突选择的风险画像。";
      panel.append(empty);
      return;
    }
    const metadata = document.createElement("dl");
    metadata.className = "metadata-grid";
    addMetadata(metadata, "Profile", profile.profile_id);
    addMetadata(metadata, "Risk score", profile.risk_score);
    addMetadata(metadata, "Risk level", profile.risk_level);
    addMetadata(metadata, "Questionnaire", profile.questionnaire_id);
    addMetadata(metadata, "Extraction", profile.extraction_id);
    addMetadata(metadata, "Confidence", profile.confidence);
    addMetadata(metadata, "Confirmed at", profile.created_at);
    panel.append(metadata);
    const conflicts = profile.conflicts || [];
    if (conflicts.length) {
      const heading = document.createElement("h4");
      heading.className = "context-heading";
      heading.textContent = "已解决的冲突";
      panel.append(heading);
      const list = document.createElement("div");
      list.className = "profile-proposal-resolved";
      conflicts.forEach((conflict) => {
        const row = document.createElement("div");
        row.textContent = `${profileDimensionLabel(conflict.dimension)} · ${text(conflict.resolution)} · ${text(conflict.resolved_value)}`;
        list.append(row);
      });
      panel.append(list);
    }
  }

  function renderProfileProposal(draft) {
    const panel = byId("profile-proposal-content");
    clear(panel);
    const confirm = byId("confirm-profile-proposal");
    confirm.disabled = !draft;
    if (!draft) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "粘贴提案后查看问卷与提取值的冲突。";
      panel.append(empty);
      return;
    }
    const meta = document.createElement("div");
    meta.className = "profile-proposal-meta";
    const metadata = document.createElement("dl");
    metadata.className = "metadata-grid";
    addMetadata(metadata, "Draft", draft.draft_id);
    addMetadata(metadata, "Owner", draft.owner_id);
    addMetadata(metadata, "Status", draft.status);
    addMetadata(metadata, "Extraction", draft.extraction?.extraction_id);
    addMetadata(metadata, "Confidence", draft.extraction?.confidence);
    addMetadata(metadata, "Input digest", draft.extraction?.input_digest);
    meta.append(metadata);
    if (!(draft.conflicts || []).length) {
      const ready = document.createElement("p");
      ready.textContent = "没有维度冲突；仍需显式确认后生成风险画像。";
      meta.append(ready);
    }
    panel.append(meta);

    (draft.conflicts || []).forEach((conflict) => {
      const card = document.createElement("article");
      card.className = "profile-conflict";
      const header = document.createElement("header");
      const title = document.createElement("strong");
      title.textContent = profileDimensionLabel(conflict.dimension);
      header.append(title, chip("需要确认", "review"));
      card.append(header);
      const values = document.createElement("dl");
      values.className = "profile-conflict-values";
      addMetadata(values, "Questionnaire", conflict.questionnaire_value);
      addMetadata(values, "Extraction", conflict.extracted_value);
      card.append(values);
      const resolution = document.createElement("label");
      resolution.className = "profile-resolution";
      resolution.textContent = "选择生效值";
      const select = document.createElement("select");
      select.dataset.conflictId = conflict.conflict_id;
      const placeholder = document.createElement("option");
      placeholder.value = "UNRESOLVED";
      placeholder.textContent = "请选择";
      select.append(placeholder);
      [
        ["USE_QUESTIONNAIRE", "使用问卷值"],
        ["USE_EXTRACTION", "使用提取值"],
      ].forEach(([value, label]) => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = label;
        select.append(option);
      });
      const selected = state.profileProposalResolutions[conflict.conflict_id];
      if (selected) select.value = selected;
      select.addEventListener("change", () => {
        if (select.value === "UNRESOLVED") delete state.profileProposalResolutions[conflict.conflict_id];
        else state.profileProposalResolutions[conflict.conflict_id] = select.value;
        state.profileProposalProfile = null;
        renderProfileProposalResult(null);
        setProfileProposalConfirmStatus("待确认");
      });
      resolution.append(select);
      card.append(resolution);
      panel.append(card);
    });
  }

  function clearProfileProposal({ clearInput = true } = {}) {
    state.profileProposalSequence += 1;
    state.profileProposalDraft = null;
    state.profileProposalQuestionnaire = null;
    state.profileProposalExtraction = null;
    state.profileProposalProfile = null;
    state.profileProposalResolutions = {};
    if (clearInput) byId("profile-proposal-json").value = "";
    setProfileProposalStatus("未预览");
    setProfileProposalConfirmStatus("未确认");
    renderProfileProposal(null);
    renderProfileProposalResult(null);
  }

  function setAdvisorPlanStatus(message, className = "") {
    const node = byId("advisor-plan-status");
    node.className = `status-chip ${className}`.trim();
    node.textContent = message;
  }

  function renderAdvisorPlan(plan) {
    const panel = byId("advisor-plan-content");
    clear(panel);
    if (!plan) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "选择一个结构化研究问题后预览四轨道任务。";
      panel.append(empty);
      return;
    }
    const metadata = document.createElement("dl");
    metadata.className = "metadata-grid";
    addMetadata(metadata, "Plan", plan.plan_id);
    addMetadata(metadata, "Intent", `${text(plan.intent_type)} · ${text(plan.intent_id)}`);
    addMetadata(metadata, "Owner", plan.owner_id);
    addMetadata(metadata, "Portfolio bundle", plan.portfolio_bundle_id);
    addMetadata(metadata, "Position snapshot", plan.position_snapshot_id);
    addMetadata(metadata, "Questionnaire", plan.questionnaire_id);
    addMetadata(metadata, "Scope", displayDescription(plan.scope_description));
    addMetadata(metadata, "Nodes", plan.node_count);
    panel.append(metadata);

    const heading = document.createElement("h4");
    heading.className = "context-heading";
    heading.textContent = "专业研究轨道";
    panel.append(heading);
    const roles = document.createElement("div");
    roles.className = "intent-plan-roles";
    (plan.roles || []).forEach((role) => roles.append(chip(researchRoleLabel(role), "pass")));
    panel.append(roles);
  }

  function clearAdvisorPlan() {
    state.advisorPlan = null;
    setAdvisorPlanStatus("未预览");
    renderAdvisorPlan(null);
  }

  function renderProfile(receipt) {
    const panel = byId("profile-content");
    clear(panel);
    if (!receipt) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "该事件没有可展示的决策回执。";
      panel.append(empty);
      return;
    }
    const grid = document.createElement("dl");
    grid.className = "metadata-grid";
    addMetadata(grid, "Profile", `${receipt.profile_id} · v${receipt.profile_version}`);
    addMetadata(grid, "Portfolio bundle", receipt.portfolio_bundle_id);
    addMetadata(grid, "Position snapshot", receipt.position_snapshot_id);
    addMetadata(grid, "Risk assessment", receipt.risk_assessment_id);
    addMetadata(grid, "Allocation envelope", receipt.allocation_envelope_id);
    addMetadata(grid, "Research run", receipt.research_run_id);
    panel.append(grid);
  }

  function renderDetail(event) {
    state.selected = event.event_id;
    state.selectedDecisionEvent = event;
    renderEvents();
    const result = event.result;
    const detail = byId("detail-content");
    clear(detail);
    const status = byId("detail-status");
    status.className = `status-chip ${statusClass(event.status)}`;
    status.textContent = statusLabel(event.status);

    if (event.status !== "PASS" || !result.receipt) {
      const blocked = document.createElement("div");
      blocked.className = "notice error";
      blocked.textContent = event.status === "REVIEW_REQUIRED"
        ? "当前证据或风险输入仍需人工复核，Prism 没有生成可执行建议。"
        : "当前决策被安全阻断，Prism 没有生成可执行建议。";
      detail.append(blocked);
      const issueList = document.createElement("ul");
      (result.issues || []).forEach((issue) => {
        const item = document.createElement("li");
        item.textContent = `${text(issue.code)}: ${displayDescription(issue.safe_message)}`;
        issueList.append(item);
      });
      if (issueList.childElementCount) detail.append(issueList);
      renderProfile(null);
      renderEvidence(null);
      return;
    }

    const summary = document.createElement("div");
    summary.className = "decision-summary";
    const summaryLabel = document.createElement("span");
    summaryLabel.className = "eyebrow clay";
    summaryLabel.textContent = "为什么得到这个结果";
    const summaryText = document.createElement("p");
    summaryText.textContent = text(result.summary);
    summary.append(summaryLabel, summaryText);
    detail.append(summary);

    const recs = document.createElement("div");
    recs.className = "recommendation-list";
    (result.trace.recommendations || []).forEach((recommendation) => {
      const card = document.createElement("article");
      card.className = "recommendation-card";
      const header = document.createElement("header");
      const title = document.createElement("strong");
      title.textContent = recommendation.asset_id;
      const action = document.createElement("span");
      action.className = `action-chip ${recommendation.action_type.toLowerCase()}`;
      action.textContent = text(recommendation.action_type);
      header.append(title, action);
      const grid = document.createElement("dl");
      grid.className = "metadata-grid";
      addMetadata(grid, "Allocation range", `${recommendation.allocation_range.minimum_pct}% — ${recommendation.allocation_range.maximum_pct}%`);
      addMetadata(grid, "Finding IDs", recommendation.finding_ids.join(", "));
      addMetadata(grid, "Recommendation ID", recommendation.recommendation_id);
      card.append(header, grid);
      recs.append(card);
    });
    detail.append(recs);
    const invalidation = document.createElement("div");
    invalidation.className = "invalidation";
    invalidation.textContent = "失效条件";
    const conditions = document.createElement("ul");
    const allConditions = new Set();
    (result.trace.recommendations || []).forEach((recommendation) => {
      (recommendation.invalidation_conditions || []).forEach((condition) => allConditions.add(condition));
    });
    [...allConditions].forEach((condition) => {
      const item = document.createElement("li");
      item.textContent = displayDescription(condition);
      conditions.append(item);
    });
    invalidation.append(conditions);
    detail.append(invalidation);
    renderProfile(result.receipt);
    renderEvidence(result);
  }

  function renderEvidence(result) {
    const panel = byId("evidence-content");
    clear(panel);
    if (!result || !result.trace) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "选择通过（PASS）回执后展开证据。";
      panel.append(empty);
      renderAdvancedEvidence();
      return;
    }
    const evidenceById = new Map((result.trace.evidence || []).map((item) => [item.evidence_id, item]));
    const factsById = new Map((result.trace.facts || []).map((item) => [item.fact_id, item]));
    (result.trace.findings || []).forEach((finding) => {
      const details = document.createElement("details");
      details.className = "evidence-item";
      const summary = document.createElement("summary");
      summary.textContent = `${text(finding.kind)} · ${text(finding.statement)}`;
      details.append(summary);
      const meta = document.createElement("div");
      meta.className = "evidence-meta";
      const addMetaLine = (value) => {
        const line = document.createElement("div");
        line.textContent = value;
        meta.append(line);
      };
      addMetaLine(`发现（FINDING）：${text(finding.finding_id)}`);
      finding.fact_ids.forEach((factId) => {
        const fact = factsById.get(factId);
        if (!fact) return;
        addMetaLine(`事实（FACT）：${text(fact.fact_id)} · ${text(fact.metric)} = ${text(fact.value)}`);
        fact.evidence_ids.forEach((evidenceId) => {
          const evidence = evidenceById.get(evidenceId);
          if (!evidence) return;
          addMetaLine(`证据（EVIDENCE）：${text(evidence.evidence_id)} · ${text(evidence.source)} · ${text(evidence.period)}`);
        });
      });
      details.append(meta);
      panel.append(details);
    });
    if (!panel.childElementCount) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "该回执没有可展示的发现（FINDING）。";
      panel.append(empty);
    }
    renderAdvancedEvidence();
  }

  const ADVANCED_EVIDENCE_QUALITY_LABELS = Object.freeze({
    VERIFIED: "已验证（VERIFIED）",
    STALE: "陈旧/需复核（STALE）",
    PARTIAL: "部分可用（PARTIAL）",
    CONFLICTING: "来源冲突（CONFLICTING）",
    INVALID: "无效（INVALID）",
  });
  const ADVANCED_EVIDENCE_MODE_LABELS = Object.freeze({
    DIRECT: "主数据提供方直连（DIRECT）",
    CACHE_FRESH: "新鲜缓存（CACHE_FRESH）",
    FALLBACK_PROVIDER: "备用数据提供方（FALLBACK_PROVIDER）",
    CACHE_STALE_FALLBACK: "陈旧缓存回退（CACHE_STALE_FALLBACK）",
    UNAVAILABLE: "未提供送达元数据（UNAVAILABLE）",
  });
  const ADVANCED_EVIDENCE_SOURCE_LABELS = Object.freeze({
    ADVISOR: "投顾回执（ADVISOR）",
    RESEARCH_MATRIX: "研究矩阵（RESEARCH_MATRIX）",
    STOCK: "个股研究（STOCK）",
    FUND: "ETF / 基金研究（FUND）",
    CONVERTIBLE_BOND: "可转债研究（CONVERTIBLE_BOND）",
  });
  const ADVANCED_EVIDENCE_PROMOTION_LABELS = Object.freeze({
    FINDING: "已闭合发现（FINDING）",
    FACT: "已进入事实（FACT）",
    AVAILABLE: "可用 · 未升级（AVAILABLE）",
  });

  function advancedEvidenceModeLabel(mode) {
    return ADVANCED_EVIDENCE_MODE_LABELS[mode] || text(mode, ADVANCED_EVIDENCE_MODE_LABELS.UNAVAILABLE);
  }

  function advancedEvidenceQualityLabel(status) {
    return ADVANCED_EVIDENCE_QUALITY_LABELS[status] || text(status, "未知质量");
  }

  function advancedEvidenceQualityClass(status) {
    if (status === "VERIFIED") return "pass";
    if (status === "STALE" || status === "PARTIAL" || status === "CONFLICTING") return "review";
    return "blocked";
  }

  function advancedEvidencePromotionLabel(promotion) {
    return ADVANCED_EVIDENCE_PROMOTION_LABELS[promotion] || text(promotion);
  }

  function advancedEvidenceValue(value) {
    if (value === null || value === undefined || value === "") return "—";
    if (typeof value === "object") return "[结构化值]";
    return String(value);
  }

  function advancedEvidenceCacheAgeLabel(age) {
    if (age === null || age === undefined || age === "") return "未提供";
    const numericAge = Number(age);
    if (!Number.isFinite(numericAge) || numericAge < 0) return "未提供";
    if (numericAge < 1000) return `${Math.round(numericAge)} 毫秒`;
    if (numericAge < 60000) return `${(numericAge / 1000).toFixed(1)} 秒 · ${Math.round(numericAge)} 毫秒`;
    return `${(numericAge / 60000).toFixed(1)} 分钟 · ${Math.round(numericAge)} 毫秒`;
  }

  function advancedEvidenceRunId(result, fallback) {
    return result && (result.run_id || result.request_id || result.matrix_id) || fallback;
  }

  function advancedEvidenceTraceEntries(sourceKey, sourceLabel, result, ownerId, fallbackRunId) {
    if (!result || !result.trace || !ownerId || ownerId !== state.ownerId) return [];
    const trace = result.trace;
    const evidenceItems = Array.isArray(trace.evidence) ? trace.evidence : [];
    const facts = Array.isArray(trace.facts) ? trace.facts : [];
    const findings = Array.isArray(trace.findings) ? trace.findings : [];
    const validations = Array.isArray(result.validations) ? result.validations : [];
    const findingsByFactId = new Map();
    findings.forEach((finding) => {
      (finding.fact_ids || []).forEach((factId) => {
        const existing = findingsByFactId.get(factId) || [];
        existing.push(finding);
        findingsByFactId.set(factId, existing);
      });
    });
    const nodes = Array.isArray(result.nodes) ? result.nodes : [];
    const resultIssues = Array.isArray(result.issues) ? result.issues : [];
    const runId = advancedEvidenceRunId(result, fallbackRunId);
    return evidenceItems.map((evidence) => {
      const relatedFacts = facts.filter((fact) => (fact.evidence_ids || []).includes(evidence.evidence_id));
      const relatedFindings = relatedFacts.flatMap((fact) => findingsByFactId.get(fact.fact_id) || []);
      const relatedValidations = validations.filter((validation) => [
        "supporting_evidence_ids",
        "contradicting_evidence_ids",
        "duplicate_lineage_evidence_ids",
        "unlinked_evidence_ids",
        "unresolved_evidence_ids",
      ].some((field) => (validation[field] || []).includes(evidence.evidence_id)));
      const matchingNodes = nodes.filter((candidate) => candidate.provider && candidate.provider === evidence.provider);
      const node = matchingNodes.find((candidate) => (
        candidate.node_id && evidence.source && String(evidence.source).includes(String(candidate.node_id))
      )) || matchingNodes[0] || null;
      const inferredMode = evidence.quality_status === "STALE"
        ? "CACHE_STALE_FALLBACK"
        : node?.provider_serving_mode || "UNAVAILABLE";
      const mode = node?.provider_serving_mode || inferredMode;
      const promotion = relatedFindings.length ? "FINDING" : relatedFacts.length ? "FACT" : "AVAILABLE";
      const issueLines = [];
      relatedValidations.forEach((validation) => {
        (validation.issues || []).forEach((issue) => {
          const line = `${text(issue.code)}: ${displayDescription(issue.safe_message)}`;
          if (!issueLines.includes(line)) issueLines.push(line);
        });
      });
      if (!relatedValidations.length && resultIssues.length && promotion === "AVAILABLE") {
        resultIssues.forEach((issue) => {
          const line = `${text(issue.code)}: ${displayDescription(issue.safe_message)}`;
          if (!issueLines.includes(line)) issueLines.push(line);
        });
      }
      const searchText = [
        evidence.evidence_id,
        evidence.provider,
        evidence.source,
        evidence.field,
        evidence.period,
        evidence.lineage_id,
        sourceLabel,
        advancedEvidenceQualityLabel(evidence.quality_status),
        advancedEvidenceModeLabel(mode),
        advancedEvidencePromotionLabel(promotion),
      ].map((value) => text(value, "")).join(" ").toLocaleLowerCase();
      return {
        key: `${sourceKey}:${text(evidence.evidence_id, "unknown")}`,
        sourceKey,
        sourceLabel,
        ownerId,
        runId,
        pipelineStatus: result.pipeline_status || result.status || "UNAVAILABLE",
        evidence,
        facts: relatedFacts,
        findings: relatedFindings,
        validations: relatedValidations,
        issues: issueLines,
        node,
        mode,
        cacheAgeMs: node?.provider_cache_age_ms ?? null,
        promotion,
        searchText,
      };
    });
  }

  function collectAdvancedEvidenceEntries() {
    if (!state.ownerId) return [];
    const entries = [];
    const selectedEvent = state.selectedDecisionEvent;
    if (selectedEvent && selectedEvent.owner_id === state.ownerId && selectedEvent.result) {
      entries.push(...advancedEvidenceTraceEntries(
        "ADVISOR",
        ADVANCED_EVIDENCE_SOURCE_LABELS.ADVISOR,
        selectedEvent.result,
        selectedEvent.owner_id,
        selectedEvent.event_id,
      ));
    }
    [
      ["RESEARCH_MATRIX", state.researchRun, ADVANCED_EVIDENCE_SOURCE_LABELS.RESEARCH_MATRIX],
      ["STOCK", state.stockResearchRun, ADVANCED_EVIDENCE_SOURCE_LABELS.STOCK],
      ["FUND", state.fundResearchRun, ADVANCED_EVIDENCE_SOURCE_LABELS.FUND],
      ["CONVERTIBLE_BOND", state.convertibleBondResearchRun, ADVANCED_EVIDENCE_SOURCE_LABELS.CONVERTIBLE_BOND],
    ].forEach(([sourceKey, result, sourceLabel]) => {
      if (!result || result.owner_id !== state.ownerId) return;
      entries.push(...advancedEvidenceTraceEntries(sourceKey, sourceLabel, result, result.owner_id, null));
    });
    return entries.sort((left, right) => {
      const sourceOrder = left.sourceKey.localeCompare(right.sourceKey);
      return sourceOrder || text(left.evidence.evidence_id, "").localeCompare(text(right.evidence.evidence_id, ""));
    });
  }

  function setAdvancedEvidenceSelect(id, stateKey, values, labels, allLabel) {
    const select = byId(id);
    if (!select) return;
    const current = state[stateKey] || "ALL";
    clear(select);
    const all = document.createElement("option");
    all.value = "ALL";
    all.textContent = allLabel;
    select.append(all);
    values.forEach((value) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = labels[value] || value;
      select.append(option);
    });
    const allowed = ["ALL", ...values];
    state[stateKey] = allowed.includes(current) ? current : "ALL";
    select.value = state[stateKey];
  }

  function renderAdvancedEvidenceDetail(panel, entry) {
    clear(panel);
    if (!entry) {
      const empty = document.createElement("div");
      empty.className = "advanced-evidence-empty";
      empty.textContent = "当前筛选没有匹配的证据。";
      panel.append(empty);
      return;
    }
    const header = document.createElement("header");
    const title = document.createElement("strong");
    title.textContent = entry.evidence.evidence_id;
    header.append(title);
    const badges = document.createElement("div");
    badges.className = "advanced-evidence-badges";
    badges.append(
      chip(advancedEvidenceQualityLabel(entry.evidence.quality_status), advancedEvidenceQualityClass(entry.evidence.quality_status)),
      chip(
        advancedEvidenceModeLabel(entry.mode),
        entry.mode === "CACHE_STALE_FALLBACK" || entry.mode === "FALLBACK_PROVIDER" ? "review" : entry.mode === "UNAVAILABLE" ? "" : "pass",
      ),
      chip(advancedEvidencePromotionLabel(entry.promotion), entry.promotion === "FINDING" ? "pass" : "review"),
    );
    panel.append(header, badges);

    const metadata = document.createElement("dl");
    metadata.className = "metadata-grid";
    addMetadata(metadata, "研究轨道", entry.sourceLabel);
    addMetadata(metadata, "Owner", entry.ownerId);
    addMetadata(metadata, "Run", entry.runId);
    addMetadata(metadata, "Provider", entry.evidence.provider);
    addMetadata(metadata, "Source", entry.evidence.source);
    addMetadata(metadata, "Field", entry.evidence.field);
    addMetadata(metadata, "Value", `${advancedEvidenceValue(entry.evidence.value)} ${text(entry.evidence.unit, "")}`.trim());
    addMetadata(metadata, "Period", entry.evidence.period);
    addMetadata(metadata, "Observed at", entry.evidence.observed_at);
    addMetadata(metadata, "Retrieved at", entry.evidence.retrieved_at);
    addMetadata(metadata, "Lineage", entry.evidence.lineage_id);
    addMetadata(metadata, "Cache age", advancedEvidenceCacheAgeLabel(entry.cacheAgeMs));
    addMetadata(metadata, "Pipeline", entry.pipelineStatus);
    panel.append(metadata);

    if (entry.evidence.quality_note) {
      const note = document.createElement("div");
      note.className = "advanced-evidence-notice";
      note.textContent = `质量说明：${displayDescription(entry.evidence.quality_note)}`;
      panel.append(note);
    }
    if (entry.mode === "CACHE_STALE_FALLBACK" || entry.evidence.quality_status === "STALE") {
      const notice = document.createElement("div");
      notice.className = "advanced-evidence-notice blocked";
      notice.textContent = "陈旧缓存回退：需要人工复核，不能作为已验证事实（VERIFIED）或可执行建议。";
      panel.append(notice);
    } else if (entry.mode === "FALLBACK_PROVIDER") {
      const notice = document.createElement("div");
      notice.className = "advanced-evidence-notice";
      notice.textContent = "备用数据提供方已送达：保留备用来源与来源链，使用前仍应检查独立验证状态。";
      panel.append(notice);
    }

    const pathHeading = document.createElement("h4");
    pathHeading.className = "context-heading";
    pathHeading.textContent = "审计路径 · 发现（FINDING）→事实（FACT）→证据（EVIDENCE）";
    panel.append(pathHeading);
    const path = document.createElement("ul");
    path.className = "advanced-evidence-path";
    const evidencePath = document.createElement("li");
    evidencePath.className = "path-primary";
    evidencePath.textContent = `证据（EVIDENCE）· ${entry.evidence.evidence_id} · ${text(entry.evidence.field)} · ${advancedEvidenceQualityLabel(entry.evidence.quality_status)}`;
    path.append(evidencePath);
    entry.facts.forEach((fact) => {
      const item = document.createElement("li");
      item.textContent = `事实（FACT）· ${text(fact.fact_id)} · ${text(fact.metric)} = ${advancedEvidenceValue(fact.value)} ${text(fact.unit, "")} · ${text(fact.status)}`.trim();
      path.append(item);
    });
    entry.findings.forEach((finding) => {
      const item = document.createElement("li");
      item.textContent = `发现（FINDING）· ${text(finding.finding_id)} · ${text(finding.kind)} · ${text(finding.severity)} · ${text(finding.statement)}`;
      path.append(item);
    });
    entry.validations.forEach((validation) => {
      const item = document.createElement("li");
      item.textContent = `验证（VALIDATION）· ${text(validation.metric)} · ${text(validation.status)} · ${text(validation.independent_lineage_count, "0")} 条独立来源链`;
      path.append(item);
    });
    if (!entry.facts.length && !entry.findings.length) {
      const item = document.createElement("li");
      item.textContent = "当前证据尚未进入事实（FACT）/发现（FINDING）；它仍可审计，但不构成结论。";
      path.append(item);
    }
    panel.append(path);

    if (entry.issues.length) {
      const issueHeading = document.createElement("h4");
      issueHeading.className = "context-heading";
      issueHeading.textContent = "需复核的安全问题（ISSUE）";
      panel.append(issueHeading);
      const issues = document.createElement("ul");
      issues.className = "advanced-evidence-issues";
      entry.issues.forEach((line) => {
        const item = document.createElement("li");
        item.textContent = line;
        issues.append(item);
      });
      panel.append(issues);
    }
  }

  function renderAdvancedEvidence() {
    const explorer = byId("advanced-evidence-explorer");
    if (!explorer) return;
    const entries = collectAdvancedEvidenceEntries();
    setAdvancedEvidenceSelect(
      "advanced-evidence-quality",
      "advancedEvidenceQuality",
      Object.keys(ADVANCED_EVIDENCE_QUALITY_LABELS),
      ADVANCED_EVIDENCE_QUALITY_LABELS,
      "全部质量",
    );
    setAdvancedEvidenceSelect(
      "advanced-evidence-mode",
      "advancedEvidenceMode",
      Object.keys(ADVANCED_EVIDENCE_MODE_LABELS),
      ADVANCED_EVIDENCE_MODE_LABELS,
      "全部模式",
    );
    const sourceValues = [...new Set(entries.map((entry) => entry.sourceKey))].sort();
    setAdvancedEvidenceSelect(
      "advanced-evidence-source",
      "advancedEvidenceSource",
      sourceValues,
      ADVANCED_EVIDENCE_SOURCE_LABELS,
      "全部轨道",
    );
    setAdvancedEvidenceSelect(
      "advanced-evidence-promotion",
      "advancedEvidencePromotion",
      Object.keys(ADVANCED_EVIDENCE_PROMOTION_LABELS),
      ADVANCED_EVIDENCE_PROMOTION_LABELS,
      "全部状态",
    );

    const search = byId("advanced-evidence-search");
    if (search && search.value !== state.advancedEvidenceSearch) search.value = state.advancedEvidenceSearch;
    const needle = state.advancedEvidenceSearch.trim().toLocaleLowerCase();
    const filtered = entries.filter((entry) => {
      if (needle && !entry.searchText.includes(needle)) return false;
      if (state.advancedEvidenceQuality !== "ALL" && entry.evidence.quality_status !== state.advancedEvidenceQuality) return false;
      if (state.advancedEvidenceMode !== "ALL" && entry.mode !== state.advancedEvidenceMode) return false;
      if (state.advancedEvidenceSource !== "ALL" && entry.sourceKey !== state.advancedEvidenceSource) return false;
      if (state.advancedEvidencePromotion !== "ALL" && entry.promotion !== state.advancedEvidencePromotion) return false;
      return true;
    });
    const summary = byId("advanced-evidence-summary");
    const list = byId("advanced-evidence-list");
    const detail = byId("advanced-evidence-detail");
    clear(summary);
    clear(list);
    const closedCount = entries.filter((entry) => entry.promotion === "FINDING").length;
    const reviewCount = entries.filter((entry) => entry.evidence.quality_status !== "VERIFIED" || entry.promotion !== "FINDING").length;
    summary.append(
      chip(`${entries.length} 条证据`, entries.length ? "" : "review"),
      chip(`${filtered.length} 条显示`, filtered.length === entries.length ? "" : "review"),
      chip(`${closedCount} 条已闭合`, closedCount ? "pass" : ""),
      chip(`${reviewCount} 条需复核`, reviewCount ? "review" : "pass"),
    );
    const summaryText = document.createElement("span");
    summaryText.textContent = entries.length
      ? "只聚合当前隔离标识的内存结果；切换隔离标识或重新运行会清空旧选择。"
      : "先运行研究轨道或选择通过（PASS）回执，才能建立当前会话的证据索引。";
    summary.append(summaryText);

    if (!entries.length) {
      const empty = document.createElement("div");
      empty.className = "advanced-evidence-empty";
      empty.textContent = "暂无当前隔离标识的证据。运行研究或选择通过（PASS）回执后再查看。";
      list.append(empty);
      renderAdvancedEvidenceDetail(detail, null);
      return;
    }
    if (!filtered.length) {
      const empty = document.createElement("div");
      empty.className = "advanced-evidence-empty";
      empty.textContent = "当前筛选没有匹配的证据；清除筛选后查看全部记录。";
      list.append(empty);
      renderAdvancedEvidenceDetail(detail, null);
      return;
    }
    const selected = filtered.find((entry) => entry.key === state.advancedEvidenceSelectedKey) || filtered[0];
    state.advancedEvidenceSelectedKey = selected.key;
    filtered.forEach((entry) => {
      const row = document.createElement("button");
      row.type = "button";
      row.className = `advanced-evidence-row${entry.key === selected.key ? " selected" : ""}`;
      row.setAttribute("role", "option");
      row.setAttribute("aria-selected", String(entry.key === selected.key));
      row.setAttribute("aria-label", `${entry.evidence.evidence_id} · ${advancedEvidenceQualityLabel(entry.evidence.quality_status)} · ${entry.sourceLabel}`);
      row.addEventListener("click", () => {
        state.advancedEvidenceSelectedKey = entry.key;
        renderAdvancedEvidence();
      });
      const rowHeader = document.createElement("header");
      const rowTitle = document.createElement("strong");
      rowTitle.textContent = entry.evidence.evidence_id;
      rowHeader.append(rowTitle, chip(advancedEvidenceQualityLabel(entry.evidence.quality_status), advancedEvidenceQualityClass(entry.evidence.quality_status)));
      const rowSource = document.createElement("div");
      rowSource.className = "advanced-evidence-row-source";
      rowSource.textContent = `${entry.sourceLabel} · ${text(entry.evidence.field)} · ${text(entry.evidence.period)}`;
      const rowMeta = document.createElement("div");
      rowMeta.className = "advanced-evidence-row-meta";
      rowMeta.textContent = `${advancedEvidenceModeLabel(entry.mode)} · ${advancedEvidencePromotionLabel(entry.promotion)} · ${text(entry.evidence.lineage_id, "无来源链")}`;
      row.append(rowHeader, rowSource, rowMeta);
      list.append(row);
    });
    renderAdvancedEvidenceDetail(detail, selected);
  }

  function renderResearchMatrix(result) {
    const panel = byId("research-matrix-content");
    clear(panel);
    renderAdvancedEvidence();
    if (!result) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "运行矩阵后查看四类节点、独立来源验证与发现（FINDING）→事实（FACT）→证据（EVIDENCE）。";
      panel.append(empty);
      return;
    }

    const summary = document.createElement("div");
    summary.className = "research-summary";
    summary.append(
      chip(researchStatusLabel(result.pipeline_status), researchStatusClass(result.pipeline_status)),
      chip(`运行：${researchStatusLabel(result.run_status)}`, researchStatusClass(result.run_status)),
    );
    const summaryText = document.createElement("p");
    summaryText.textContent = `${text(result.matrix_id)} · ${text(result.run_id)} · 隔离标识 ${text(result.owner_id)}`;
    summary.append(summaryText);
    if (result.scenario) {
      const scenarioText = document.createElement("p");
      scenarioText.textContent = `${displayScenarioLabel(result.scenario)} · ${displayScenarioDescription(result.scenario)}`;
      summary.append(scenarioText);
    }
    panel.append(summary);

    const cards = document.createElement("div");
    cards.className = "research-grid";
    (result.nodes || []).forEach((node) => {
      const card = document.createElement("article");
      card.className = "research-card";
      const header = document.createElement("header");
      const title = document.createElement("strong");
      title.textContent = researchRoleLabel(node.role);
      header.append(title, chip(researchStatusLabel(node.status), researchStatusClass(node.status)));
      card.append(header);
      const subject = document.createElement("div");
      subject.className = "muted";
      subject.textContent = text(node.subject);
      card.append(subject);
      const metadata = document.createElement("dl");
      addMetadata(metadata, "Node", node.node_id);
      addMetadata(metadata, "Kind", node.node_kind);
      addMetadata(metadata, "Status", researchStatusLabel(node.status));
      card.append(metadata);
      if (node.issues && node.issues.length) {
        const issues = document.createElement("ul");
        issues.className = "research-issues";
        node.issues.forEach((issue) => {
          const item = document.createElement("li");
          item.textContent = `${text(issue.code)}: ${displayDescription(issue.safe_message)}`;
          issues.append(item);
        });
        card.append(issues);
      }
      cards.append(card);
    });
    panel.append(cards);

    if (result.pipeline_status !== "READY") {
      const notice = document.createElement("div");
      notice.className = "notice error";
      notice.textContent = "研究结果仍需复核，Prism 不展示未验证的事实（FACT）/发现（FINDING），也不会生成可执行建议。";
      panel.append(notice);
      const issues = document.createElement("ul");
      issues.className = "research-issues";
      (result.issues || []).forEach((issue) => {
        const item = document.createElement("li");
        item.textContent = `${text(issue.code)}: ${displayDescription(issue.safe_message)}`;
        issues.append(item);
      });
      if (issues.childElementCount) panel.append(issues);
    }

    const validationHeading = document.createElement("h3");
    validationHeading.textContent = "独立来源链验证";
    panel.append(validationHeading);
    const validations = document.createElement("div");
    validations.className = "research-validations";
    (result.validations || []).forEach((validation) => {
      const row = document.createElement("article");
      row.className = "research-validation";
      const title = document.createElement("strong");
      title.textContent = `${text(validation.subject)} · ${text(validation.metric)}`;
      row.append(title, chip(text(validation.status), researchStatusClass(validation.status)));
      const meta = document.createElement("div");
      meta.className = "validation-meta";
      meta.textContent = `预期 ${text(validation.expected_value)} ${text(validation.unit)} · ${text(validation.period)} · ${text(validation.independent_lineage_count)} 条独立来源链 · 支持 ${text((validation.supporting_evidence_ids || []).length, "0")} · 冲突 ${text((validation.contradicting_evidence_ids || []).length, "0")} · 未解决 ${text((validation.unresolved_evidence_ids || []).length, "0")}`;
      row.append(meta);
      if (validation.issues && validation.issues.length) {
        const issues = document.createElement("ul");
        issues.className = "validation-issues";
        validation.issues.forEach((issue) => {
          const item = document.createElement("li");
          item.textContent = `${text(issue.code)}: ${displayDescription(issue.safe_message)}`;
          issues.append(item);
        });
        row.append(issues);
      }
      validations.append(row);
    });
    panel.append(validations);

    if (result.pipeline_status !== "READY") {
      const availableHeading = document.createElement("h3");
      availableHeading.textContent = "可用证据 · 未升级为事实（FACT）";
      panel.append(availableHeading);
      const available = document.createElement("div");
      available.className = "research-available-evidence";
      (result.trace && result.trace.evidence || []).forEach((evidence) => {
        const details = document.createElement("details");
        const summaryLine = document.createElement("summary");
        summaryLine.textContent = `${text(evidence.field)} · ${text(evidence.source)} · ${text(evidence.quality_status)}`;
        details.append(summaryLine);
        const metadata = document.createElement("div");
        metadata.className = "research-evidence-meta";
        [
          `证据（EVIDENCE）：${text(evidence.evidence_id)}`,
          `数值：${text(evidence.value)} ${text(evidence.unit, "")}`,
          `期间：${text(evidence.period)}`,
          `来源链：${text(evidence.lineage_id)}`,
        ].forEach((line) => {
          const item = document.createElement("div");
          item.textContent = line;
          metadata.append(item);
        });
        details.append(metadata);
        available.append(details);
      });
      if (available.childElementCount) panel.append(available);
      return;
    }

    const evidenceHeading = document.createElement("h3");
    evidenceHeading.textContent = "发现（FINDING）→事实（FACT）→证据（EVIDENCE）";
    panel.append(evidenceHeading);
    const evidencePanel = document.createElement("div");
    evidencePanel.className = "research-evidence";
    const evidenceById = new Map((result.trace && result.trace.evidence || []).map((item) => [item.evidence_id, item]));
    const factsById = new Map((result.trace && result.trace.facts || []).map((item) => [item.fact_id, item]));
    (result.trace && result.trace.findings || []).forEach((finding) => {
      const details = document.createElement("details");
      details.open = true;
      const summaryLine = document.createElement("summary");
      summaryLine.textContent = `${text(finding.kind)} · ${text(finding.statement)}`;
      details.append(summaryLine);
      const metadata = document.createElement("div");
      metadata.className = "research-evidence-meta";
      const findingLine = document.createElement("div");
      findingLine.textContent = `发现（FINDING）：${text(finding.finding_id)} · ${text(finding.severity)}`;
      metadata.append(findingLine);
      (finding.fact_ids || []).forEach((factId) => {
        const fact = factsById.get(factId);
        if (!fact) return;
        const factLine = document.createElement("div");
        factLine.textContent = `事实（FACT）：${text(fact.fact_id)} · ${text(fact.metric)} = ${text(fact.value)} ${text(fact.unit)} · ${text(fact.status)}`;
        metadata.append(factLine);
        (fact.evidence_ids || []).forEach((evidenceId) => {
          const evidence = evidenceById.get(evidenceId);
          if (!evidence) return;
          const evidenceLine = document.createElement("div");
          evidenceLine.textContent = `证据（EVIDENCE）：${text(evidence.evidence_id)} · ${text(evidence.source)} · ${text(evidence.period)} · ${text(evidence.value)} · 来源链 ${text(evidence.lineage_id)}`;
          metadata.append(evidenceLine);
        });
      });
      details.append(metadata);
      evidencePanel.append(details);
    });
    if (evidencePanel.childElementCount) panel.append(evidencePanel);
  }

  function renderStockResearch(result) {
    const panel = byId("stock-research-content");
    clear(panel);
    renderAdvancedEvidence();
    if (!result) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "运行个股研究后查看财务事实、异常、风险与证据闭合。";
      panel.append(empty);
      return;
    }

    const summary = document.createElement("div");
    summary.className = "stock-research-summary";
    summary.append(
      chip(researchStatusLabel(result.pipeline_status), researchStatusClass(result.pipeline_status)),
      chip(`运行：${researchStatusLabel(result.run_status)}`, researchStatusClass(result.run_status)),
      chip(stockRiskStatusLabel(result.risk && result.risk.status), stockRiskStatusClass(result.risk && result.risk.status)),
    );
    const summaryText = document.createElement("p");
    summaryText.textContent = `${text(result.subject)} · ${text(result.period)} · ${text(result.run_id)} · 隔离标识 ${text(result.owner_id)}`;
    summary.append(summaryText);
    if (result.scenario) {
      const scenarioText = document.createElement("p");
      scenarioText.textContent = `${displayScenarioLabel(result.scenario)} · ${displayScenarioDescription(result.scenario)}`;
      summary.append(scenarioText);
    }
    panel.append(summary);

    const nodeHeading = document.createElement("h3");
    nodeHeading.textContent = "来源节点";
    panel.append(nodeHeading);
    const nodeGrid = document.createElement("div");
    nodeGrid.className = "research-grid";
    (result.nodes || []).forEach((node) => {
      const card = document.createElement("article");
      card.className = "research-card";
      const header = document.createElement("header");
      const title = document.createElement("strong");
      title.textContent = text(node.node_id);
      header.append(title, chip(researchStatusLabel(node.status), researchStatusClass(node.status)));
      card.append(header);
      const metadata = document.createElement("dl");
      addMetadata(metadata, "Status", researchStatusLabel(node.status));
      if (node.missing_fields && node.missing_fields.length) {
        addMetadata(metadata, "Missing", node.missing_fields.join(", "));
      }
      card.append(metadata);
      if (node.scope_description) {
        const scope = document.createElement("div");
        scope.className = "muted";
        scope.textContent = displayDescription(node.scope_description);
        card.append(scope);
      }
      (node.issues || []).forEach((issue) => {
        const issueLine = document.createElement("div");
        issueLine.className = "muted";
        issueLine.textContent = `${text(issue.code)}: ${displayDescription(issue.safe_message)}`;
        card.append(issueLine);
      });
      nodeGrid.append(card);
    });
    if (nodeGrid.childElementCount) panel.append(nodeGrid);

    const validationsHeading = document.createElement("h3");
    validationsHeading.textContent = "来源验证";
    panel.append(validationsHeading);
    const validations = document.createElement("div");
    validations.className = "research-validations";
    (result.validations || []).forEach((validation) => {
      const row = document.createElement("article");
      row.className = "research-validation";
      const title = document.createElement("strong");
      title.textContent = `${text(validation.metric)} · ${text(validation.period)}`;
      row.append(title, chip(text(validation.status), researchStatusClass(validation.status)));
      const meta = document.createElement("div");
      meta.className = "validation-meta";
      meta.textContent = `${text(validation.independent_lineage_count, "0")} 条独立来源链 · 支持 ${text((validation.supporting_evidence_ids || []).length, "0")} · 冲突 ${text((validation.contradicting_evidence_ids || []).length, "0")} · 未解决 ${text((validation.unresolved_evidence_ids || []).length, "0")}`;
      row.append(meta);
      (validation.issues || []).forEach((issue) => {
        const issueLine = document.createElement("div");
        issueLine.className = "muted";
        issueLine.textContent = `${text(issue.code)}: ${displayDescription(issue.safe_message)}`;
        row.append(issueLine);
      });
      validations.append(row);
    });
    if (validations.childElementCount) panel.append(validations);

    if (result.pipeline_status !== "READY") {
      const notice = document.createElement("div");
      notice.className = "notice error";
      notice.textContent = "证据链未闭合；证据仍可审计，但不会升级为事实（FACT）/发现（FINDING），也不会给出风险结论。";
      panel.append(notice);
      const issues = document.createElement("ul");
      issues.className = "stock-issues";
      (result.issues || []).forEach((issue) => {
        const item = document.createElement("li");
        item.textContent = `${text(issue.code)}: ${displayDescription(issue.safe_message)}`;
        issues.append(item);
      });
      if (issues.childElementCount) panel.append(issues);
      const availableHeading = document.createElement("h3");
      availableHeading.textContent = "可用证据 · 未升级为事实（FACT）";
      panel.append(availableHeading);
      const available = document.createElement("div");
      available.className = "stock-available-evidence";
      (result.trace && result.trace.evidence || []).forEach((evidence) => {
        const details = document.createElement("details");
        const line = document.createElement("summary");
        line.textContent = `${text(evidence.field)} · ${text(evidence.source)} · ${text(evidence.quality_status)}`;
        details.append(line);
        const metadata = document.createElement("div");
        metadata.className = "research-evidence-meta";
        [
          `证据（EVIDENCE）：${text(evidence.evidence_id)}`,
          `数值：${text(evidence.value)} ${text(evidence.unit, "")}`,
          `期间：${text(evidence.period)}`,
          `来源链：${text(evidence.lineage_id)}`,
        ].forEach((lineText) => {
          const item = document.createElement("div");
          item.textContent = lineText;
          metadata.append(item);
        });
        details.append(metadata);
        available.append(details);
      });
      if (available.childElementCount) panel.append(available);
      return;
    }

    const factHeading = document.createElement("h3");
    factHeading.textContent = "已验证的财务事实";
    panel.append(factHeading);
    const metricLabels = new Map((state.stockResearchTemplate && state.stockResearchTemplate.metrics || []).map((item) => [item.metric, item.label]));
    const factGrid = document.createElement("div");
    factGrid.className = "stock-fact-grid";
    (result.facts || []).forEach((fact) => {
      const card = document.createElement("article");
      card.className = "stock-fact-card";
      const title = document.createElement("strong");
      title.textContent = text(metricLabels.get(fact.metric), fact.metric);
      const value = document.createElement("div");
      value.className = "stock-fact-value";
      value.textContent = `${text(fact.value)} ${text(fact.unit, "")}`;
      const period = document.createElement("div");
      period.className = "muted";
      period.textContent = `${text(fact.metric)} · ${text(fact.period)} · ${text(fact.status)}`;
      card.append(title, value, period);
      factGrid.append(card);
    });
    if (factGrid.childElementCount) panel.append(factGrid);

    const risk = document.createElement("section");
    risk.className = "stock-risk-summary";
    const riskHeader = document.createElement("header");
    const riskTitle = document.createElement("strong");
    riskTitle.textContent = "确定性风险摘要";
    riskHeader.append(riskTitle, chip(stockRiskStatusLabel(result.risk && result.risk.status), stockRiskStatusClass(result.risk && result.risk.status)));
    risk.append(riskHeader);
    const riskText = document.createElement("p");
    riskText.textContent = text(result.risk && result.risk.summary);
    risk.append(riskText);
    const rules = document.createElement("div");
    rules.className = "stock-rules";
    (state.stockResearchTemplate && state.stockResearchTemplate.risk_rules || []).forEach((rule) => {
      const line = document.createElement("div");
      line.textContent = `${text(rule.label)} · ${text(rule.operator)} ${text(rule.threshold)} ${text(rule.unit)}`;
      rules.append(line);
    });
    if (rules.childElementCount) risk.append(rules);
    panel.append(risk);

    const anomalyHeading = document.createElement("h3");
    anomalyHeading.textContent = "确定性异常";
    panel.append(anomalyHeading);
    const anomalies = document.createElement("div");
    anomalies.className = "stock-findings";
    (result.findings || []).filter((finding) => finding.severity !== "INFO").forEach((finding) => {
      const details = document.createElement("details");
      details.open = true;
      const line = document.createElement("summary");
      line.textContent = `${text(finding.kind)} · ${text(finding.statement)}`;
      details.append(line);
      const meta = document.createElement("div");
      meta.className = "research-evidence-meta";
      meta.textContent = `${text(finding.finding_id)} · ${text(finding.severity)} · ${displayMethodology(finding.methodology)}`;
      details.append(meta);
      anomalies.append(details);
    });
    if (anomalies.childElementCount) panel.append(anomalies);

    const chainHeading = document.createElement("h3");
    chainHeading.textContent = "发现（FINDING）→事实（FACT）→证据（EVIDENCE）";
    panel.append(chainHeading);
    const chain = document.createElement("div");
    chain.className = "stock-findings";
    const evidenceById = new Map((result.trace && result.trace.evidence || []).map((item) => [item.evidence_id, item]));
    const factsById = new Map((result.trace && result.trace.facts || []).map((item) => [item.fact_id, item]));
    (result.findings || []).forEach((finding) => {
      const details = document.createElement("details");
      const line = document.createElement("summary");
      line.textContent = `${text(finding.kind)} · ${text(finding.statement)}`;
      details.append(line);
      const metadata = document.createElement("div");
      metadata.className = "research-evidence-meta";
      const findingLine = document.createElement("div");
      findingLine.textContent = `发现（FINDING）：${text(finding.finding_id)} · ${text(finding.severity)}`;
      metadata.append(findingLine);
      (finding.fact_ids || []).forEach((factId) => {
        const fact = factsById.get(factId);
        if (!fact) return;
        const factLine = document.createElement("div");
        factLine.textContent = `事实（FACT）：${text(fact.fact_id)} · ${text(fact.metric)} = ${text(fact.value)} ${text(fact.unit)} · ${text(fact.status)}`;
        metadata.append(factLine);
        (fact.evidence_ids || []).forEach((evidenceId) => {
          const evidence = evidenceById.get(evidenceId);
          if (!evidence) return;
          const evidenceLine = document.createElement("div");
          evidenceLine.textContent = `证据（EVIDENCE）：${text(evidence.evidence_id)} · ${text(evidence.source)} · ${text(evidence.period)} · ${text(evidence.value)} · 来源链 ${text(evidence.lineage_id)}`;
          metadata.append(evidenceLine);
        });
      });
      details.append(metadata);
      chain.append(details);
    });
    if (chain.childElementCount) panel.append(chain);
  }

  function renderFundResearch(result) {
    const panel = byId("fund-research-content");
    clear(panel);
    renderAdvancedEvidence();
    if (!result) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "运行 ETF / 基金研究后查看资产事实、风险与证据闭合。";
      panel.append(empty);
      return;
    }

    const summary = document.createElement("div");
    summary.className = "fund-research-summary";
    summary.append(
      chip(researchStatusLabel(result.pipeline_status), researchStatusClass(result.pipeline_status)),
      chip(`运行：${researchStatusLabel(result.run_status)}`, researchStatusClass(result.run_status)),
      chip(fundRiskStatusLabel(result.risk && result.risk.status), fundRiskStatusClass(result.risk && result.risk.status)),
    );
    const summaryText = document.createElement("p");
    summaryText.textContent = `${text(result.subject)} · ${text(result.period)} · ${text(result.run_id)} · 隔离标识 ${text(result.owner_id)}`;
    summary.append(summaryText);
    if (result.scenario) {
      const scenarioText = document.createElement("p");
      scenarioText.textContent = `${displayScenarioLabel(result.scenario)} · ${displayScenarioDescription(result.scenario)}`;
      summary.append(scenarioText);
    }
    panel.append(summary);

    const nodeHeading = document.createElement("h3");
    nodeHeading.textContent = "来源节点";
    panel.append(nodeHeading);
    const nodeGrid = document.createElement("div");
    nodeGrid.className = "research-grid";
    (result.nodes || []).forEach((node) => {
      const card = document.createElement("article");
      card.className = "research-card";
      const header = document.createElement("header");
      const title = document.createElement("strong");
      title.textContent = text(node.node_id);
      header.append(title, chip(researchStatusLabel(node.status), researchStatusClass(node.status)));
      card.append(header);
      const metadata = document.createElement("dl");
      addMetadata(metadata, "Status", researchStatusLabel(node.status));
      if (node.missing_fields && node.missing_fields.length) {
        addMetadata(metadata, "Missing", node.missing_fields.join(", "));
      }
      card.append(metadata);
      if (node.scope_description) {
        const scope = document.createElement("div");
        scope.className = "muted";
        scope.textContent = displayDescription(node.scope_description);
        card.append(scope);
      }
      (node.issues || []).forEach((issue) => {
        const issueLine = document.createElement("div");
        issueLine.className = "muted";
        issueLine.textContent = `${text(issue.code)}: ${displayDescription(issue.safe_message)}`;
        card.append(issueLine);
      });
      nodeGrid.append(card);
    });
    if (nodeGrid.childElementCount) panel.append(nodeGrid);

    const validationHeading = document.createElement("h3");
    validationHeading.textContent = "来源验证";
    panel.append(validationHeading);
    const validations = document.createElement("div");
    validations.className = "research-validations";
    (result.validations || []).forEach((validation) => {
      const row = document.createElement("article");
      row.className = "research-validation";
      const title = document.createElement("strong");
      title.textContent = `${text(validation.metric)} · ${text(validation.period)}`;
      row.append(title, chip(text(validation.status), researchStatusClass(validation.status)));
      const meta = document.createElement("div");
      meta.className = "validation-meta";
      meta.textContent = `${text(validation.independent_lineage_count, "0")} 条独立来源链 · 支持 ${text((validation.supporting_evidence_ids || []).length, "0")} · 冲突 ${text((validation.contradicting_evidence_ids || []).length, "0")} · 未解决 ${text((validation.unresolved_evidence_ids || []).length, "0")}`;
      row.append(meta);
      (validation.issues || []).forEach((issue) => {
        const issueLine = document.createElement("div");
        issueLine.className = "muted";
        issueLine.textContent = `${text(issue.code)}: ${displayDescription(issue.safe_message)}`;
        row.append(issueLine);
      });
      validations.append(row);
    });
    if (validations.childElementCount) panel.append(validations);

    if (result.pipeline_status !== "READY") {
      const notice = document.createElement("div");
      notice.className = "notice error";
      notice.textContent = "证据链未闭合；证据仍可审计，但不会升级为事实（FACT）/发现（FINDING），也不会给出风险结论。";
      panel.append(notice);
      const issues = document.createElement("ul");
      issues.className = "fund-issues";
      (result.issues || []).forEach((issue) => {
        const item = document.createElement("li");
        item.textContent = `${text(issue.code)}: ${displayDescription(issue.safe_message)}`;
        issues.append(item);
      });
      if (issues.childElementCount) panel.append(issues);
      const availableHeading = document.createElement("h3");
      availableHeading.textContent = "可用证据 · 未升级为事实（FACT）";
      panel.append(availableHeading);
      const available = document.createElement("div");
      available.className = "fund-available-evidence";
      (result.trace && result.trace.evidence || []).forEach((evidence) => {
        const details = document.createElement("details");
        const line = document.createElement("summary");
        line.textContent = `${text(evidence.field)} · ${text(evidence.source)} · ${text(evidence.quality_status)}`;
        details.append(line);
        const metadata = document.createElement("div");
        metadata.className = "research-evidence-meta";
        [
          `证据（EVIDENCE）：${text(evidence.evidence_id)}`,
          `数值：${text(evidence.value)} ${text(evidence.unit, "")}`,
          `期间：${text(evidence.period)}`,
          `来源链：${text(evidence.lineage_id)}`,
        ].forEach((lineText) => {
          const item = document.createElement("div");
          item.textContent = lineText;
          metadata.append(item);
        });
        details.append(metadata);
        available.append(details);
      });
      if (available.childElementCount) panel.append(available);
      return;
    }

    const factHeading = document.createElement("h3");
    factHeading.textContent = "已验证的基金事实";
    panel.append(factHeading);
    const metricLabels = new Map((state.fundResearchTemplate && state.fundResearchTemplate.metrics || []).map((item) => [item.metric, item.label]));
    const factGrid = document.createElement("div");
    factGrid.className = "fund-fact-grid";
    (result.facts || []).forEach((fact) => {
      const card = document.createElement("article");
      card.className = "fund-fact-card";
      const title = document.createElement("strong");
      title.textContent = text(metricLabels.get(fact.metric), fact.metric);
      const value = document.createElement("div");
      value.className = "fund-fact-value";
      value.textContent = `${text(fact.value)} ${text(fact.unit, "")}`;
      const period = document.createElement("div");
      period.className = "muted";
      period.textContent = `${text(fact.metric)} · ${text(fact.period)} · ${text(fact.status)}`;
      card.append(title, value, period);
      factGrid.append(card);
    });
    if (factGrid.childElementCount) panel.append(factGrid);

    const risk = document.createElement("section");
    risk.className = "fund-risk-summary";
    const riskHeader = document.createElement("header");
    const riskTitle = document.createElement("strong");
    riskTitle.textContent = "确定性基金风险摘要";
    riskHeader.append(riskTitle, chip(fundRiskStatusLabel(result.risk && result.risk.status), fundRiskStatusClass(result.risk && result.risk.status)));
    risk.append(riskHeader);
    const riskText = document.createElement("p");
    riskText.textContent = text(result.risk && result.risk.summary);
    risk.append(riskText);
    const rules = document.createElement("div");
    rules.className = "fund-rules";
    (state.fundResearchTemplate && state.fundResearchTemplate.risk_rules || []).forEach((rule) => {
      const line = document.createElement("div");
      line.textContent = `${text(rule.label)} · ${text(rule.operator)} ${text(rule.threshold)} ${text(rule.unit)}`;
      rules.append(line);
    });
    if (rules.childElementCount) risk.append(rules);
    panel.append(risk);

    const findingHeading = document.createElement("h3");
    findingHeading.textContent = "确定性基金风险";
    panel.append(findingHeading);
    const findings = document.createElement("div");
    findings.className = "fund-findings";
    (result.findings || []).filter((finding) => finding.severity !== "INFO").forEach((finding) => {
      const details = document.createElement("details");
      details.open = true;
      const line = document.createElement("summary");
      line.textContent = `${text(finding.kind)} · ${text(finding.statement)}`;
      details.append(line);
      const meta = document.createElement("div");
      meta.className = "research-evidence-meta";
      meta.textContent = `${text(finding.finding_id)} · ${text(finding.severity)} · ${displayMethodology(finding.methodology)}`;
      details.append(meta);
      findings.append(details);
    });
    if (findings.childElementCount) panel.append(findings);

    const chainHeading = document.createElement("h3");
    chainHeading.textContent = "发现（FINDING）→事实（FACT）→证据（EVIDENCE）";
    panel.append(chainHeading);
    const chain = document.createElement("div");
    chain.className = "fund-findings";
    const evidenceById = new Map((result.trace && result.trace.evidence || []).map((item) => [item.evidence_id, item]));
    const factsById = new Map((result.trace && result.trace.facts || []).map((item) => [item.fact_id, item]));
    (result.findings || []).forEach((finding) => {
      const details = document.createElement("details");
      const line = document.createElement("summary");
      line.textContent = `${text(finding.kind)} · ${text(finding.statement)}`;
      details.append(line);
      const metadata = document.createElement("div");
      metadata.className = "research-evidence-meta";
      const findingLine = document.createElement("div");
      findingLine.textContent = `发现（FINDING）：${text(finding.finding_id)} · ${text(finding.severity)}`;
      metadata.append(findingLine);
      (finding.fact_ids || []).forEach((factId) => {
        const fact = factsById.get(factId);
        if (!fact) return;
        const factLine = document.createElement("div");
        factLine.textContent = `事实（FACT）：${text(fact.fact_id)} · ${text(fact.metric)} = ${text(fact.value)} ${text(fact.unit)} · ${text(fact.status)}`;
        metadata.append(factLine);
        (fact.evidence_ids || []).forEach((evidenceId) => {
          const evidence = evidenceById.get(evidenceId);
          if (!evidence) return;
          const evidenceLine = document.createElement("div");
          evidenceLine.textContent = `证据（EVIDENCE）：${text(evidence.evidence_id)} · ${text(evidence.source)} · ${text(evidence.period)} · ${text(evidence.value)} · 来源链 ${text(evidence.lineage_id)}`;
          metadata.append(evidenceLine);
        });
      });
      details.append(metadata);
      chain.append(details);
    });
    if (chain.childElementCount) panel.append(chain);
  }

  function renderConvertibleBondResearch(result) {
    const panel = byId("convertible-bond-research-content");
    clear(panel);
    renderAdvancedEvidence();
    if (!result) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "运行可转债研究后查看最低资产事实、公式、风险与证据闭合。";
      panel.append(empty);
      return;
    }

    const summary = document.createElement("div");
    summary.className = "convertible-bond-research-summary";
    summary.append(
      chip(researchStatusLabel(result.pipeline_status), researchStatusClass(result.pipeline_status)),
      chip(`运行：${researchStatusLabel(result.run_status)}`, researchStatusClass(result.run_status)),
      chip(convertibleBondRiskStatusLabel(result.risk && result.risk.status), convertibleBondRiskStatusClass(result.risk && result.risk.status)),
    );
    const summaryText = document.createElement("p");
    summaryText.textContent = `${text(result.subject)} · ${text(result.period)} · ${text(result.run_id)} · 隔离标识 ${text(result.owner_id)}`;
    summary.append(summaryText);
    if (result.scenario) {
      const scenarioText = document.createElement("p");
      scenarioText.textContent = `${displayScenarioLabel(result.scenario)} · ${displayScenarioDescription(result.scenario)}`;
      summary.append(scenarioText);
    }
    panel.append(summary);

    const nodeHeading = document.createElement("h3");
    nodeHeading.textContent = "来源节点";
    panel.append(nodeHeading);
    const nodeGrid = document.createElement("div");
    nodeGrid.className = "research-grid";
    (result.nodes || []).forEach((node) => {
      const card = document.createElement("article");
      card.className = "research-card";
      const header = document.createElement("header");
      const title = document.createElement("strong");
      title.textContent = text(node.node_id);
      header.append(title, chip(researchStatusLabel(node.status), researchStatusClass(node.status)));
      card.append(header);
      const metadata = document.createElement("dl");
      addMetadata(metadata, "Status", researchStatusLabel(node.status));
      if (node.missing_fields && node.missing_fields.length) addMetadata(metadata, "Missing", node.missing_fields.join(", "));
      card.append(metadata);
      if (node.scope_description) {
        const scope = document.createElement("div");
        scope.className = "muted";
        scope.textContent = displayDescription(node.scope_description);
        card.append(scope);
      }
      (node.issues || []).forEach((issue) => {
        const issueLine = document.createElement("div");
        issueLine.className = "muted";
        issueLine.textContent = `${text(issue.code)}: ${displayDescription(issue.safe_message)}`;
        card.append(issueLine);
      });
      nodeGrid.append(card);
    });
    if (nodeGrid.childElementCount) panel.append(nodeGrid);

    const validationHeading = document.createElement("h3");
    validationHeading.textContent = "来源验证";
    panel.append(validationHeading);
    const validations = document.createElement("div");
    validations.className = "research-validations";
    (result.validations || []).forEach((validation) => {
      const row = document.createElement("article");
      row.className = "research-validation";
      const title = document.createElement("strong");
      title.textContent = `${text(validation.metric)} · ${text(validation.period)}`;
      row.append(title, chip(text(validation.status), researchStatusClass(validation.status)));
      const meta = document.createElement("div");
      meta.className = "validation-meta";
      meta.textContent = `${text(validation.independent_lineage_count, "0")} 条独立来源链 · 支持 ${text((validation.supporting_evidence_ids || []).length, "0")} · 冲突 ${text((validation.contradicting_evidence_ids || []).length, "0")} · 未解决 ${text((validation.unresolved_evidence_ids || []).length, "0")}`;
      row.append(meta);
      (validation.issues || []).forEach((issue) => {
        const issueLine = document.createElement("div");
        issueLine.className = "muted";
        issueLine.textContent = `${text(issue.code)}: ${displayDescription(issue.safe_message)}`;
        row.append(issueLine);
      });
      validations.append(row);
    });
    if (validations.childElementCount) panel.append(validations);

    if (result.pipeline_status !== "READY") {
      const notice = document.createElement("div");
      notice.className = "notice error";
      notice.textContent = "证据链未闭合；证据仍可审计，但不会升级为事实（FACT）/发现（FINDING），也不会给出风险结论。";
      panel.append(notice);
      const issues = document.createElement("ul");
      issues.className = "convertible-bond-issues";
      (result.issues || []).forEach((issue) => {
        const item = document.createElement("li");
        item.textContent = `${text(issue.code)}: ${displayDescription(issue.safe_message)}`;
        issues.append(item);
      });
      if (issues.childElementCount) panel.append(issues);
      const availableHeading = document.createElement("h3");
      availableHeading.textContent = "可用证据 · 未升级为事实（FACT）";
      panel.append(availableHeading);
      const available = document.createElement("div");
      available.className = "convertible-bond-available-evidence";
      (result.trace && result.trace.evidence || []).forEach((evidence) => {
        const details = document.createElement("details");
        const line = document.createElement("summary");
        line.textContent = `${text(evidence.field)} · ${text(evidence.source)} · ${text(evidence.quality_status)}`;
        details.append(line);
        const metadata = document.createElement("div");
        metadata.className = "research-evidence-meta";
        [
          `证据（EVIDENCE）：${text(evidence.evidence_id)}`,
          `数值：${text(evidence.value)} ${text(evidence.unit, "")}`,
          `期间：${text(evidence.period)}`,
          `来源链：${text(evidence.lineage_id)}`,
        ].forEach((lineText) => {
          const item = document.createElement("div");
          item.textContent = lineText;
          metadata.append(item);
        });
        details.append(metadata);
        available.append(details);
      });
      if (available.childElementCount) panel.append(available);
      return;
    }

    const factHeading = document.createElement("h3");
    factHeading.textContent = "已验证的可转债事实";
    panel.append(factHeading);
    const template = state.convertibleBondResearchTemplate;
    const metricLabels = new Map((template && template.metrics || []).map((item) => [item.metric, item.label]));
    const factGrid = document.createElement("div");
    factGrid.className = "convertible-bond-fact-grid";
    const creditLabels = (template && template.credit_rating_labels) || {};
    const liquidityLabels = (template && template.liquidity_labels) || {};
    (result.facts || []).forEach((fact) => {
      const card = document.createElement("article");
      card.className = "convertible-bond-fact-card";
      const title = document.createElement("strong");
      title.textContent = text(metricLabels.get(fact.metric), fact.metric);
      const value = document.createElement("div");
      value.className = "convertible-bond-fact-value";
      let displayValue = text(fact.value);
      const levelMetric = fact.metric === "credit_rating_rank" || fact.metric === "liquidity_score";
      if (fact.metric === "credit_rating_rank") displayValue = `${text(creditLabels[String(fact.value)], "未知评级")} · 序数 ${displayValue}`;
      if (fact.metric === "liquidity_score") displayValue = `${text(liquidityLabels[String(fact.value)], "未知流动性")} · 分数 ${displayValue}`;
      value.textContent = levelMetric ? displayValue : `${displayValue} ${text(fact.unit, "")}`;
      const period = document.createElement("div");
      period.className = "muted";
      period.textContent = `${text(fact.metric)} · ${text(fact.period)} · ${text(fact.status)}`;
      card.append(title, value, period);
      factGrid.append(card);
    });
    if (factGrid.childElementCount) panel.append(factGrid);

    const formulaHeading = document.createElement("h3");
    formulaHeading.textContent = "确定性公式";
    panel.append(formulaHeading);
    const formulas = document.createElement("div");
    formulas.className = "convertible-bond-formulas";
    (template && template.metrics || []).filter((item) => item.derived).forEach((item) => {
      const line = document.createElement("div");
      line.textContent = `${text(item.label, item.metric)} · ${text(item.formula)}`;
      formulas.append(line);
    });
    if (formulas.childElementCount) panel.append(formulas);

    const risk = document.createElement("section");
    risk.className = "convertible-bond-risk-summary";
    const riskHeader = document.createElement("header");
    const riskTitle = document.createElement("strong");
    riskTitle.textContent = "确定性可转债风险摘要";
    riskHeader.append(riskTitle, chip(convertibleBondRiskStatusLabel(result.risk && result.risk.status), convertibleBondRiskStatusClass(result.risk && result.risk.status)));
    risk.append(riskHeader);
    const riskText = document.createElement("p");
    riskText.textContent = text(result.risk && result.risk.summary);
    risk.append(riskText);
    const rules = document.createElement("div");
    rules.className = "convertible-bond-rules";
    (template && template.risk_rules || []).forEach((rule) => {
      const line = document.createElement("div");
      line.textContent = `${text(rule.label)} · ${text(rule.operator)} ${text(rule.threshold)} ${text(rule.unit)}`;
      rules.append(line);
    });
    if (rules.childElementCount) risk.append(rules);
    panel.append(risk);

    const findingHeading = document.createElement("h3");
    findingHeading.textContent = "确定性可转债风险";
    panel.append(findingHeading);
    const findings = document.createElement("div");
    findings.className = "convertible-bond-findings";
    (result.findings || []).filter((finding) => finding.severity !== "INFO").forEach((finding) => {
      const details = document.createElement("details");
      details.open = true;
      const line = document.createElement("summary");
      line.textContent = `${text(finding.kind)} · ${text(finding.statement)}`;
      details.append(line);
      const meta = document.createElement("div");
      meta.className = "research-evidence-meta";
      meta.textContent = `${text(finding.finding_id)} · ${text(finding.severity)} · ${displayMethodology(finding.methodology)}`;
      details.append(meta);
      findings.append(details);
    });
    if (findings.childElementCount) panel.append(findings);

    const chainHeading = document.createElement("h3");
    chainHeading.textContent = "发现（FINDING）→事实（FACT）→证据（EVIDENCE）";
    panel.append(chainHeading);
    const chain = document.createElement("div");
    chain.className = "convertible-bond-findings";
    const evidenceById = new Map((result.trace && result.trace.evidence || []).map((item) => [item.evidence_id, item]));
    const factsById = new Map((result.trace && result.trace.facts || []).map((item) => [item.fact_id, item]));
    (result.findings || []).forEach((finding) => {
      const details = document.createElement("details");
      const line = document.createElement("summary");
      line.textContent = `${text(finding.kind)} · ${text(finding.statement)}`;
      details.append(line);
      const metadata = document.createElement("div");
      metadata.className = "research-evidence-meta";
      const findingLine = document.createElement("div");
      findingLine.textContent = `发现（FINDING）：${text(finding.finding_id)} · ${text(finding.severity)}`;
      metadata.append(findingLine);
      (finding.fact_ids || []).forEach((factId) => {
        const fact = factsById.get(factId);
        if (!fact) return;
        const factLine = document.createElement("div");
        factLine.textContent = `事实（FACT）：${text(fact.fact_id)} · ${text(fact.metric)} = ${text(fact.value)} ${text(fact.unit)} · ${text(fact.status)}`;
        metadata.append(factLine);
        (fact.evidence_ids || []).forEach((evidenceId) => {
          const evidence = evidenceById.get(evidenceId);
          if (!evidence) return;
          const evidenceLine = document.createElement("div");
          evidenceLine.textContent = `证据（EVIDENCE）：${text(evidence.evidence_id)} · ${text(evidence.source)} · ${text(evidence.period)} · ${text(evidence.value)} · 来源链 ${text(evidence.lineage_id)}`;
          metadata.append(evidenceLine);
        });
      });
      details.append(metadata);
      chain.append(details);
    });
    if (chain.childElementCount) panel.append(chain);
  }

  function renderPortfolioOptimization(result) {
    const panel = byId("portfolio-optimization-content");
    clear(panel);
    if (!result) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "生成提案后查看当前→目标权重、约束上限、算术解释与失效条件。";
      panel.append(empty);
      return;
    }

    const summary = document.createElement("div");
    summary.className = "portfolio-optimization-summary";
    summary.append(
      chip(optimizationStatusLabel(result.status), optimizationStatusClass(result.status)),
      chip(text(result.risk_level), ""),
    );
    const summaryText = document.createElement("p");
    summaryText.textContent = `${displayScenarioLabel(result.scenario)} · ${text(result.summary)} · 隔离标识 ${text(result.owner_id)}`;
    summary.append(summaryText);
    panel.append(summary);

    const metadata = document.createElement("dl");
    metadata.className = "metadata-grid";
    addMetadata(metadata, "Method", result.methodology_version);
    addMetadata(metadata, "Profile", `${text(result.profile_id)} · v${text(result.profile_version)}`);
    addMetadata(metadata, "Portfolio bundle", result.portfolio_bundle_id);
    addMetadata(metadata, "Position snapshot", result.position_snapshot_id);
    addMetadata(metadata, "Exposure report", result.exposure_report_id);
    addMetadata(metadata, "Risk assessment", `${text(result.assessment_id)} · ${text(result.assessment_status)}`);
    panel.append(metadata);

    if (result.issues && result.issues.length) {
      const notice = document.createElement("div");
      notice.className = "notice error";
      notice.textContent = result.status === "BLOCKED"
        ? "目标约束无法闭合；没有生成可执行权重。"
        : "输入数据尚未闭合；没有生成目标权重。";
      panel.append(notice);
      const issues = document.createElement("ul");
      issues.className = "portfolio-optimization-issues";
      result.issues.forEach((issue) => {
        const item = document.createElement("li");
        item.textContent = `${text(issue.code)}: ${displayDescription(issue.safe_message)}`;
        issues.append(item);
      });
      panel.append(issues);
    }

    if (result.status === "READY") {
      const targetHeading = document.createElement("h3");
      targetHeading.textContent = "当前 → 确定性目标权重";
      panel.append(targetHeading);
      const targets = document.createElement("div");
      targets.className = "portfolio-optimization-targets";
      (result.targets || []).forEach((target) => {
        const card = document.createElement("article");
        card.className = "portfolio-optimization-target";
        const header = document.createElement("header");
        const title = document.createElement("strong");
        title.textContent = `${text(target.asset_name)} · ${text(target.sector, "未分类")}`;
        header.append(title);
        card.append(header);
        const grid = document.createElement("dl");
        addMetadata(grid, "Current", `${text(target.current_weight_pct)}%`);
        addMetadata(grid, "Target", `${text(target.target_weight_pct)}%`);
        addMetadata(grid, "Delta", `${text(target.delta_pct)} 个百分点`);
        addMetadata(grid, "Asset cap", `${text(target.allowed_max_weight_pct)}%`);
        card.append(grid);
        const rationale = document.createElement("div");
        rationale.className = "muted";
        rationale.textContent = displayDescription(target.rationale);
        card.append(rationale);
        targets.append(card);
      });
      if (targets.childElementCount) panel.append(targets);

      const constraintHeading = document.createElement("h3");
      constraintHeading.textContent = "约束算术";
      panel.append(constraintHeading);
      const constraints = document.createElement("div");
      constraints.className = "portfolio-optimization-constraints";
      (result.constraints || []).forEach((constraint) => {
        const details = document.createElement("details");
        const line = document.createElement("summary");
        line.textContent = `${text(constraint.dimension)} · ${text(constraint.label)} · ${text(constraint.disposition)}`;
        details.append(line);
        const meta = document.createElement("div");
        meta.className = "research-evidence-meta";
        meta.textContent = `当前 ${text(constraint.current_weight_pct)}% → 目标 ${text(constraint.target_weight_pct)}% · 上限 ${text(constraint.allowed_max_weight_pct)}% · 变化 ${text(constraint.delta_pct)} 个百分点 · ${displayDescription(constraint.rationale)}`;
        details.append(meta);
        constraints.append(details);
      });
      if (constraints.childElementCount) panel.append(constraints);
    }

    const invalidation = document.createElement("div");
    invalidation.className = "invalidation";
    const invalidationTitle = document.createElement("strong");
    invalidationTitle.textContent = "提案失效条件";
    invalidation.append(invalidationTitle);
    const list = document.createElement("ul");
    (result.invalidation_conditions || []).forEach((condition) => {
      const item = document.createElement("li");
      item.textContent = displayDescription(condition);
      list.append(item);
    });
    invalidation.append(list);
    panel.append(invalidation);
  }

  function clearPortfolioOptimizationRun(status = "待运行", className = "") {
    state.portfolioOptimizationRun = null;
    state.portfolioOptimizationSequence += 1;
    renderPortfolioOptimization(null);
    setPortfolioOptimizationStatus(status, className);
  }

  function renderScenarioSimulation(result) {
    const panel = byId("scenario-simulation-content");
    if (!panel) return;
    clear(panel);
    if (!result) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "运行情景模拟后查看基线 vs 假设覆盖层的指标对比与目标权重变化。";
      panel.append(empty);
      return;
    }

    const summary = document.createElement("div");
    summary.className = "portfolio-optimization-summary";
    summary.append(
      chip(optimizationStatusLabel(result.status), optimizationStatusClass(result.status)),
      chip(text(result.risk_level), ""),
      chip(text(result.scenario.scenario_id), "clay"),
    );
    const summaryText = document.createElement("p");
    summaryText.textContent = `${displayScenarioLabel(result.scenario)} · ${displayScenarioDescription(result.scenario)} · 隔离标识 ${text(result.owner_id)}`;
    summary.append(summaryText);
    panel.append(summary);

    const assumptionBox = document.createElement("div");
    assumptionBox.className = "sidebar-note";
    const assumptionTitle = document.createElement("strong");
    assumptionTitle.textContent = "假设覆盖层（SIMULATED 覆盖）";
    const assumptionDesc = document.createElement("p");
    assumptionDesc.textContent = `${displayDescription(result.assumption.description)} (参数: ${text(result.assumption.parameter_name)}, 变化量: ${text(result.assumption.delta)}${result.assumption.unit ? " " + result.assumption.unit : ""})`;
    assumptionBox.append(assumptionTitle, assumptionDesc);
    panel.append(assumptionBox);

    const metadata = document.createElement("dl");
    metadata.className = "metadata-grid";
    addMetadata(metadata, "Method", result.methodology_version);
    addMetadata(metadata, "Profile", `${text(result.profile_id)} · v${text(result.profile_version)}`);
    addMetadata(metadata, "Simulation ID", result.simulation_id);
    addMetadata(metadata, "Fingerprint", result.trace.input_fingerprint);
    addMetadata(metadata, "Baseline Run", result.trace.baseline_run_id);
    addMetadata(metadata, "Simulated Run", result.trace.simulated_run_id);
    panel.append(metadata);

    if (result.issues && result.issues.length) {
      const notice = document.createElement("div");
      notice.className = "notice error";
      notice.textContent = result.status === "BLOCKED"
        ? "情景模拟因数据或约束阻断；未能生成完整有效差分。"
        : "情景模拟包含待复核项；数据不完整或需复核。";
      panel.append(notice);
      const issues = document.createElement("ul");
      issues.className = "portfolio-optimization-issues";
      result.issues.forEach((issue) => {
        const item = document.createElement("li");
        item.textContent = `[${text(issue.dimension)}] ${text(issue.code)}: ${displayDescription(issue.safe_message)}`;
        issues.append(item);
      });
      panel.append(issues);
    }

    if (result.metric_diffs && result.metric_diffs.length) {
      const diffHeading = document.createElement("h3");
      diffHeading.textContent = "基线 vs 模拟关键指标差分对比";
      panel.append(diffHeading);

      const table = document.createElement("table");
      table.className = "scenario-diff-table";
      const thead = document.createElement("thead");
      const trHead = document.createElement("tr");
      ["指标名称", "维度", "基线值 (BASELINE)", "模拟值 (SIMULATED)", "变化量 (Δ)", "单位"].forEach((hText) => {
        const th = document.createElement("th");
        th.textContent = hText;
        trHead.append(th);
      });
      thead.append(trHead);
      table.append(thead);

      const tbody = document.createElement("tbody");
      result.metric_diffs.forEach((diff) => {
        const tr = document.createElement("tr");
        const tdName = document.createElement("td");
        const nameStrong = document.createElement("strong");
        nameStrong.textContent = diff.label;
        tdName.append(nameStrong);

        const tdDim = document.createElement("td");
        tdDim.append(chip(text(diff.dimension), ""));

        const tdBase = document.createElement("td");
        tdBase.textContent = String(diff.baseline_value);

        const tdSim = document.createElement("td");
        tdSim.textContent = String(diff.scenario_value);

        const tdDelta = document.createElement("td");
        const deltaNum = parseFloat(diff.delta);
        if (deltaNum > 0) {
          tdDelta.className = "positive-delta";
          tdDelta.textContent = `+${diff.delta}`;
        } else if (deltaNum < 0) {
          tdDelta.className = "negative-delta";
          tdDelta.textContent = String(diff.delta);
        } else {
          tdDelta.textContent = String(diff.delta);
        }

        const tdUnit = document.createElement("td");
        tdUnit.textContent = text(diff.unit);

        tr.append(tdName, tdDim, tdBase, tdSim, tdDelta, tdUnit);
        tbody.append(tr);
      });
      table.append(tbody);
      panel.append(table);
    }

    if (result.target_diffs && result.target_diffs.length) {
      const targetHeading = document.createElement("h3");
      targetHeading.textContent = "组合目标权重差分对比";
      panel.append(targetHeading);

      const table = document.createElement("table");
      table.className = "scenario-diff-table";
      const thead = document.createElement("thead");
      const trHead = document.createElement("tr");
      ["资产名称", "基线目标权重", "模拟目标权重", "变化量 (Δ)"].forEach((hText) => {
        const th = document.createElement("th");
        th.textContent = hText;
        trHead.append(th);
      });
      thead.append(trHead);
      table.append(thead);

      const tbody = document.createElement("tbody");
      result.target_diffs.forEach((target) => {
        const tr = document.createElement("tr");
        const tdName = document.createElement("td");
        const nameStrong = document.createElement("strong");
        nameStrong.textContent = target.asset_name;
        tdName.append(nameStrong);

        const tdBase = document.createElement("td");
        tdBase.textContent = `${target.baseline_value}%`;

        const tdSim = document.createElement("td");
        tdSim.textContent = `${target.scenario_value}%`;

        const tdDelta = document.createElement("td");
        const deltaNum = parseFloat(target.delta);
        if (deltaNum > 0) {
          tdDelta.className = "positive-delta";
          tdDelta.textContent = `+${target.delta}%`;
        } else if (deltaNum < 0) {
          tdDelta.className = "negative-delta";
          tdDelta.textContent = `${target.delta}%`;
        } else {
          tdDelta.textContent = `${target.delta}%`;
        }

        tr.append(tdName, tdBase, tdSim, tdDelta);
        tbody.append(tr);
      });
      table.append(tbody);
      panel.append(table);
    }

    const invalidation = document.createElement("div");
    invalidation.className = "invalidation";
    const invalidationTitle = document.createElement("strong");
    invalidationTitle.textContent = "情景模拟失效条件";
    invalidation.append(invalidationTitle);
    const list = document.createElement("ul");
    (result.invalidation_conditions || []).forEach((condition) => {
      const item = document.createElement("li");
      item.textContent = displayDescription(condition);
      list.append(item);
    });
    invalidation.append(list);
    panel.append(invalidation);
  }

  function clearScenarioSimulationRun(status = "待运行", className = "") {
    state.scenarioSimulationRun = null;
    state.scenarioSimulationSequence += 1;
    renderScenarioSimulation(null);
    setScenarioSimulationStatus(status, className);
  }

  async function loadEvent(eventId) {
    const requestOwner = state.ownerId;
    const templateSequence = state.templateSequence;
    setError("");
    try {
      const response = await fetch(`/api/v1/decision-events/${encodeURIComponent(eventId)}`, {
        headers: { "X-Owner-ID": requestOwner },
      });
      if (!response.ok) throw await apiError(response);
      if (state.ownerId !== requestOwner || state.templateSequence !== templateSequence) return;
      renderDetail(await response.json());
    } catch (error) {
      setError(error.message || "读取决策事件失败");
    }
  }

  async function apiError(response) {
    try {
      const payload = await response.json();
      const message = payload && typeof payload.message === "string" ? payload.message : "";
      return new Error(message && /[\u3400-\u9fff]/.test(message) ? message : "接口请求失败");
    } catch (_) {
      return new Error("接口请求失败");
    }
  }

  function buildQuestionnaire(template) {
    const queryId = byId("query-id").value.trim() || "ui-profile-confirmation";
    return {
      ...template.questionnaire,
      questionnaire_id: `${queryId}-questionnaire`,
      owner_id: state.ownerId,
      answered_at: template.questionnaire.answered_at,
      loss_tolerance_score: Number(byId("loss-tolerance").value),
      investment_horizon: byId("investment-horizon").value,
      liquidity_need: byId("liquidity-need").value,
      experience_level: byId("experience-level").value,
      return_expectation: byId("return-expectation").value,
      max_drawdown_tolerance_pct: byId("max-drawdown").value,
    };
  }

  async function confirmPortfolioContext() {
    const requestOwner = byId("owner-id").value.trim();
    const raw = byId("portfolio-json").value.trim();
    const submit = byId("confirm-portfolio");
    clearAdvisorPlan();
    clearPortfolioOptimizationRun("需重新运行", "review");
    clearScenarioSimulationRun("需重新运行", "review");
    if (!requestOwner) {
      state.portfolioContext = null;
      renderPortfolio(state.queryTemplate?.portfolio || null);
      setPortfolioContextStatus("需要隔离标识", "blocked");
      setError("请输入隔离标识。");
      return;
    }
    if (!raw) {
      state.portfolioContext = null;
      renderPortfolio(state.queryTemplate?.portfolio || null);
      setPortfolioContextStatus("未提供 JSON", "blocked");
      setError("请粘贴已脱敏的持仓 JSON。");
      return;
    }
    let portfolio;
    try {
      portfolio = JSON.parse(raw);
      if (!portfolio || typeof portfolio !== "object" || Array.isArray(portfolio)) {
        throw new Error("not an object");
      }
    } catch (_) {
      state.portfolioContext = null;
      renderPortfolio(state.queryTemplate?.portfolio || null);
      setPortfolioContextStatus("JSON 无效", "blocked");
      setError("持仓 JSON 无法解析；输入原文不会写入错误信息。");
      return;
    }
    if (requestOwner !== state.ownerId) {
      state.ownerId = requestOwner;
      resetOwnerScopedViews();
      byId("portfolio-json").value = raw;
    }
    const contextSequence = state.templateSequence;
    setError("");
    submit.disabled = true;
    setPortfolioContextStatus("验证中…");
    try {
      const response = await fetch("/api/v1/advisor/context/portfolio", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Owner-ID": requestOwner,
        },
        body: JSON.stringify({
          schema_version: "portfolio-context-request.v1",
          portfolio,
        }),
      });
      if (!response.ok) throw await apiError(response);
      if (state.ownerId !== requestOwner || state.templateSequence !== contextSequence) return;
      const result = await response.json();
      state.portfolioContext = result.portfolio;
      renderPortfolio(state.portfolioContext, "已确认 · 当前会话只读");
      setPortfolioContextStatus(
        `已确认 · ${text(result.position_count)} 个持仓`,
        "pass",
      );
    } catch (error) {
      if (state.ownerId === requestOwner && state.templateSequence === contextSequence) {
        state.portfolioContext = null;
        setPortfolioContextStatus("未确认", "blocked");
        renderPortfolio(state.queryTemplate?.portfolio || null);
      }
      setError(error.message || "持仓校验失败");
    } finally {
      submit.disabled = false;
    }
  }

  async function confirmProfileContext() {
    const requestOwner = byId("owner-id").value.trim();
    const submit = byId("confirm-profile");
    clearAdvisorPlan();
    clearProfileProposal();
    clearPortfolioOptimizationRun("需重新运行", "review");
    clearScenarioSimulationRun("需重新运行", "review");
    if (!requestOwner) {
      state.profileContext = null;
      renderConfirmedProfile(null);
      setProfileContextStatus("需要隔离标识", "blocked");
      setError("请输入隔离标识。");
      return;
    }
    if (requestOwner !== state.ownerId) {
      state.ownerId = requestOwner;
      resetOwnerScopedViews();
    }
    const contextSequence = ++state.templateSequence;
    setError("");
    submit.disabled = true;
    setProfileContextStatus("确认中…");
    try {
      const template = state.queryTemplate || await loadTemplateContext(requestOwner, contextSequence);
      if (!template) return;
      const questionnaire = buildQuestionnaire(template);
      const response = await fetch("/api/v1/advisor/context/profile", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Owner-ID": requestOwner,
        },
        body: JSON.stringify({
          schema_version: "profile-context-request.v1",
          questionnaire,
        }),
      });
      if (!response.ok) throw await apiError(response);
      if (state.ownerId !== requestOwner || state.templateSequence !== contextSequence) return;
      const result = await response.json();
      state.profileContext = result;
      renderProfileContext(result.questionnaire);
      renderConfirmedProfile(result.profile);
      setProfileContextStatus(`已确认 · ${text(result.profile.risk_level)}`, "pass");
    } catch (error) {
      if (state.ownerId === requestOwner && state.templateSequence === contextSequence) {
        state.profileContext = null;
        renderConfirmedProfile(null);
        setProfileContextStatus("未确认", "blocked");
      }
      setError(error.message || "风险画像确认失败");
    } finally {
      submit.disabled = false;
    }
  }

  function clearConfirmedContexts() {
    state.portfolioContext = null;
    state.profileContext = null;
    byId("portfolio-json").value = "";
    setPortfolioContextStatus("未确认");
    setProfileContextStatus("未确认");
    renderConfirmedProfile(null);
    clearProfileProposal();
    clearAdvisorPlan();
  }

  function clearTemplateContext({ clearConfirmed = false } = {}) {
    state.queryTemplate = null;
    state.templateContext = null;
    byId("query-template-meta").textContent = "运行时读取合成持仓模板；不会提交自然语言或订单。";
    if (clearConfirmed) clearConfirmedContexts();
    renderPortfolio(null);
    renderProfileContext(null);
  }

  async function loadTemplateContext(ownerId, sequence) {
    try {
      const response = await fetch("/api/v1/advisor/query-template", {
        headers: { "X-Owner-ID": ownerId },
      });
      if (!response.ok) throw await apiError(response);
      const template = await response.json();
      if (state.ownerId !== ownerId || state.templateSequence !== sequence) return null;
      state.templateContext = template;
      state.queryTemplate = template;
      byId("query-template-meta").textContent = `合成数据 ${text(template.fixture_id)} · 生成时间 ${text(template.generated_at)} · 合成持仓模板`;
      renderPortfolio(
        state.portfolioContext || template.portfolio,
        state.portfolioContext ? "已确认 · 当前会话只读" : "只读 · 合成模板",
      );
      renderProfileContext(state.profileContext?.questionnaire || template.questionnaire);
      renderConfirmedProfile(state.profileContext?.profile || null);
      return template;
    } catch (error) {
      if (state.ownerId === ownerId && state.templateSequence === sequence) {
        clearTemplateContext({ clearConfirmed: true });
      }
      throw error;
    }
  }

  async function loadResearchScenarioCatalog(ownerId) {
    const sequence = ++state.researchSequence;
    const response = await fetch("/api/v1/advisor/research-matrix-template", {
      headers: { "X-Owner-ID": ownerId },
    });
    if (!response.ok) throw await apiError(response);
    const template = await response.json();
    if (state.ownerId !== ownerId || state.researchSequence !== sequence) return null;
    state.researchTemplate = template;
    renderResearchScenarioOptions(template.scenarios);
    byId("research-template-meta").textContent = `矩阵 ${text(template.matrix_id)} · ${text(template.node_count)} 个节点 · ${text((template.scenarios || []).length, "0")} 个回放场景 · 生成时间 ${text(template.generated_at)}`;
    return template;
  }

  async function loadStockResearchCatalog(ownerId) {
    const sequence = ++state.stockResearchSequence;
    const response = await fetch("/api/v1/advisor/stock-research-template", {
      headers: { "X-Owner-ID": ownerId },
    });
    if (!response.ok) throw await apiError(response);
    const template = await response.json();
    if (state.ownerId !== ownerId || state.stockResearchSequence !== sequence) return null;
    state.stockResearchTemplate = template;
    renderStockResearchScenarioOptions(template.scenarios);
    byId("stock-research-template-meta").textContent = `个股 ${text(template.subject)} · ${text(template.period)} · ${text(template.metrics?.length, "0")} 项指标 · ${text((template.scenarios || []).length, "0")} 个回放场景 · 生成时间 ${text(template.generated_at)}`;
    return template;
  }

  async function loadFundResearchCatalog(ownerId) {
    const sequence = ++state.fundResearchSequence;
    const response = await fetch("/api/v1/advisor/fund-research-template", {
      headers: { "X-Owner-ID": ownerId },
    });
    if (!response.ok) throw await apiError(response);
    const template = await response.json();
    if (state.ownerId !== ownerId || state.fundResearchSequence !== sequence) return null;
    state.fundResearchTemplate = template;
    renderFundResearchScenarioOptions(template.scenarios);
    byId("fund-research-template-meta").textContent = `基金 ${text(template.subject)} · ${text(template.period)} · ${text(template.metrics?.length, "0")} 项指标 · ${text((template.scenarios || []).length, "0")} 个回放场景 · 生成时间 ${text(template.generated_at)}`;
    return template;
  }

  async function loadConvertibleBondResearchCatalog(ownerId) {
    const sequence = ++state.convertibleBondResearchSequence;
    const response = await fetch("/api/v1/advisor/convertible-bond-research-template", {
      headers: { "X-Owner-ID": ownerId },
    });
    if (!response.ok) throw await apiError(response);
    const template = await response.json();
    if (state.ownerId !== ownerId || state.convertibleBondResearchSequence !== sequence) return null;
    state.convertibleBondResearchTemplate = template;
    renderConvertibleBondResearchScenarioOptions(template.scenarios);
    byId("convertible-bond-research-template-meta").textContent = `可转债 ${text(template.subject)} · ${text(template.period)} · ${text(template.metrics?.length, "0")} 项指标 · ${text((template.scenarios || []).length, "0")} 个回放场景 · 生成时间 ${text(template.generated_at)}`;
    return template;
  }

  async function loadPortfolioOptimizationCatalog(ownerId) {
    const sequence = ++state.portfolioOptimizationSequence;
    const response = await fetch("/api/v1/advisor/portfolio-optimization-template", {
      headers: { "X-Owner-ID": ownerId },
    });
    if (!response.ok) throw await apiError(response);
    const template = await response.json();
    if (state.ownerId !== ownerId || state.portfolioOptimizationSequence !== sequence) return null;
    state.portfolioOptimizationTemplate = template;
    renderPortfolioOptimizationScenarioOptions(template.scenarios);
    byId("portfolio-optimization-template-meta").textContent = `方法 ${text(template.methodology_version)} · ${text((template.rules || []).length, "0")} 条规则 · ${text((template.scenarios || []).length, "0")} 个回放场景 · 生成时间 ${text(template.generated_at)}`;
    return template;
  }

  async function loadScenarioSimulationCatalog(ownerId) {
    const sequence = ++state.scenarioSimulationSequence;
    const response = await fetch("/api/v1/advisor/scenario-simulation-template", {
      headers: { "X-Owner-ID": ownerId },
    });
    if (!response.ok) throw await apiError(response);
    const template = await response.json();
    if (state.ownerId !== ownerId || state.scenarioSimulationSequence !== sequence) return null;
    state.scenarioSimulationTemplate = template;
    renderScenarioSimulationScenarioOptions(template.scenarios);
    const metaNode = byId("scenario-simulation-template-meta");
    if (metaNode) {
      metaNode.textContent = `方法 ${text(template.methodology_version)} · ${text((template.scenarios || []).length, "0")} 个模拟场景 · 生成时间 ${text(template.generated_at)}`;
    }
    return template;
  }

  async function previewProfileProposal() {
    const requestOwner = byId("owner-id").value.trim();
    const raw = byId("profile-proposal-json").value.trim();
    const submit = byId("preview-profile-proposal");
    if (!requestOwner) {
      clearProfileProposal({ clearInput: false });
      clearAdvisorPlan();
      setProfileProposalStatus("需要隔离标识", "blocked");
      setError("请输入隔离标识。");
      return;
    }
    if (!raw) {
      clearProfileProposal({ clearInput: false });
      clearAdvisorPlan();
      setProfileProposalStatus("未提供 JSON", "blocked");
      setError("请粘贴已脱敏的画像提取提案 JSON。");
      return;
    }
    let extraction;
    try {
      extraction = JSON.parse(raw);
      if (!extraction || typeof extraction !== "object" || Array.isArray(extraction)) {
        throw new Error("not an object");
      }
    } catch (_) {
      clearProfileProposal({ clearInput: false });
      clearAdvisorPlan();
      setProfileProposalStatus("JSON 无效", "blocked");
      setError("画像提案 JSON 无法解析；输入原文不会写入错误信息。");
      return;
    }
    if (requestOwner !== state.ownerId) {
      state.ownerId = requestOwner;
      resetOwnerScopedViews();
      byId("profile-proposal-json").value = raw;
    }
    clearAdvisorPlan();
    clearProfileProposal({ clearInput: false });
    const proposalSequence = ++state.profileProposalSequence;
    let templateSequence = state.templateSequence;
    if (!state.queryTemplate) templateSequence = ++state.templateSequence;
    setError("");
    submit.disabled = true;
    setProfileProposalStatus("验证中…");
    try {
      const template = state.queryTemplate || await loadTemplateContext(requestOwner, templateSequence);
      if (!template) return;
      const questionnaire = buildQuestionnaire(template);
      const response = await fetch("/api/v1/advisor/profile-proposals", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Owner-ID": requestOwner,
        },
        body: JSON.stringify({
          schema_version: "advisor-profile-proposal-request.v1",
          questionnaire,
          extraction,
        }),
      });
      if (!response.ok) throw await apiError(response);
      if (
        state.ownerId !== requestOwner
        || state.templateSequence !== templateSequence
        || state.profileProposalSequence !== proposalSequence
      ) return;
      const result = await response.json();
      state.profileProposalDraft = result.draft;
      state.profileProposalQuestionnaire = questionnaire;
      state.profileProposalExtraction = extraction;
      state.profileProposalProfile = null;
      state.profileProposalResolutions = {};
      renderProfileProposal(result.draft);
      renderProfileProposalResult(null);
      const conflictCount = (result.draft.conflicts || []).length;
      setProfileProposalStatus(
        conflictCount ? `${conflictCount} 个冲突` : "无冲突 · 可确认",
        conflictCount ? "review" : "pass",
      );
      setProfileProposalConfirmStatus(conflictCount ? "待选择" : "待确认");
    } catch (error) {
      if (
        state.ownerId === requestOwner
        && state.templateSequence === templateSequence
        && state.profileProposalSequence === proposalSequence
      ) {
        clearProfileProposal({ clearInput: false });
        setProfileProposalStatus("未生成", "blocked");
      }
      setError(error.message || "风险画像提案验证失败");
    } finally {
      submit.disabled = false;
    }
  }

  async function confirmProfileProposal() {
    const draft = state.profileProposalDraft;
    const questionnaire = state.profileProposalQuestionnaire;
    const extraction = state.profileProposalExtraction;
    const submit = byId("confirm-profile-proposal");
    if (!draft || !questionnaire || !extraction) {
      setProfileProposalConfirmStatus("请先预览", "blocked");
      setError("请先预览结构化风险画像提案。");
      return;
    }
    const resolutions = {};
    let unresolved = false;
    byId("profile-proposal-content").querySelectorAll("select[data-conflict-id]").forEach((select) => {
      if (!select.value || select.value === "UNRESOLVED") unresolved = true;
      else resolutions[select.dataset.conflictId] = select.value;
    });
    if (unresolved) {
      setProfileProposalConfirmStatus("需逐项选择", "blocked");
      setError("请为每个画像冲突选择问卷值或提取值。");
      return;
    }
    const requestOwner = state.ownerId;
    const confirmationSequence = ++state.profileProposalSequence;
    setError("");
    submit.disabled = true;
    setProfileProposalConfirmStatus("确认中…");
    try {
      const response = await fetch("/api/v1/advisor/profile-proposals/confirm", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Owner-ID": requestOwner,
        },
        body: JSON.stringify({
          schema_version: "advisor-profile-confirmation-request.v1",
          questionnaire,
          extraction,
          resolutions,
        }),
      });
      if (!response.ok) throw await apiError(response);
      if (state.ownerId !== requestOwner || state.profileProposalSequence !== confirmationSequence) return;
      const result = await response.json();
      state.profileProposalProfile = result.profile;
      renderProfileProposalResult(state.profileProposalProfile);
      setProfileProposalConfirmStatus(`已确认 · ${text(result.profile.risk_level)}`, "pass");
    } catch (error) {
      if (state.ownerId === requestOwner && state.profileProposalSequence === confirmationSequence) {
        state.profileProposalProfile = null;
        renderProfileProposalResult(null);
        setProfileProposalConfirmStatus("未确认", "blocked");
      }
      setError(error.message || "画像提案确认失败");
    } finally {
      submit.disabled = false;
    }
  }

  async function previewAdvisorPlan() {
    const requestOwner = byId("owner-id").value.trim();
    const submit = byId("preview-advisor-plan");
    if (!requestOwner) {
      clearAdvisorPlan();
      setAdvisorPlanStatus("需要隔离标识", "blocked");
      setError("请输入隔离标识。");
      return;
    }
    if (requestOwner !== state.ownerId) {
      state.ownerId = requestOwner;
      resetOwnerScopedViews();
    }
    const planSequence = ++state.templateSequence;
    setError("");
    submit.disabled = true;
    clearAdvisorPlan();
    setAdvisorPlanStatus("生成中…");
    try {
      const template = state.queryTemplate || await loadTemplateContext(requestOwner, planSequence);
      if (!template) return;
      const portfolio = state.portfolioContext || template.portfolio;
      const questionnaire = buildQuestionnaire(template);
      const intentType = byId("intent-type").value;
      const response = await fetch("/api/v1/advisor/plans", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Owner-ID": requestOwner,
        },
        body: JSON.stringify({
          schema_version: "advisor-intent-request.v1",
          intent_id: `${questionnaire.questionnaire_id}-plan`,
          owner_id: requestOwner,
          intent_type: intentType,
          generated_at: template.generated_at,
          portfolio_bundle_id: portfolio.bundle_id,
          position_snapshot_id: portfolio.position_snapshot.snapshot_id,
          questionnaire_id: questionnaire.questionnaire_id,
        }),
      });
      if (!response.ok) throw await apiError(response);
      if (state.ownerId !== requestOwner || state.templateSequence !== planSequence) return;
      state.advisorPlan = await response.json();
      renderAdvisorPlan(state.advisorPlan);
      setAdvisorPlanStatus(`已生成 · ${text(state.advisorPlan.node_count)} 个节点`, "pass");
    } catch (error) {
      if (state.ownerId === requestOwner && state.templateSequence === planSequence) {
        clearAdvisorPlan();
        setAdvisorPlanStatus("未生成", "blocked");
      }
      setError(error.message || "任务计划生成失败");
    } finally {
      submit.disabled = false;
    }
  }

  function resetOwnerScopedViews() {
    clearContextMemory();
    clearTemplateContext({ clearConfirmed: true });
    setQueryStatus("待运行");
    state.events = [];
    state.selected = null;
    state.selectedDecisionEvent = null;
    state.advancedEvidenceSearch = "";
    state.advancedEvidenceQuality = "ALL";
    state.advancedEvidenceMode = "ALL";
    state.advancedEvidenceSource = "ALL";
    state.advancedEvidencePromotion = "ALL";
    state.advancedEvidenceSelectedKey = "";
    const advancedSearch = byId("advanced-evidence-search");
    if (advancedSearch) advancedSearch.value = "";
    renderEvents();
    renderProfile(null);
    renderEvidence(null);
    byId("detail-status").className = "status-chip";
    byId("detail-status").textContent = "待选择";
    byId("detail-content").replaceChildren();
    const detailEmpty = document.createElement("div");
    detailEmpty.className = "empty-state";
    detailEmpty.textContent = "读取隔离标识后查看已保存的决策事件。";
    byId("detail-content").append(detailEmpty);
    state.researchTemplate = null;
    state.researchRun = null;
    state.researchSequence += 1;
    byId("research-template-meta").textContent = "运行时读取四轨道矩阵模板；研究结果不写入决策回执。";
    clearResearchScenarioOptions();
    setResearchStatus("待运行");
    renderResearchMatrix(null);
    state.stockResearchTemplate = null;
    state.stockResearchRun = null;
    state.stockResearchSequence += 1;
    byId("stock-research-template-meta").textContent = "运行时读取固定合成个股与风险规则；结果不写入决策回执。";
    clearStockResearchScenarioOptions();
    setStockResearchStatus("待运行");
    renderStockResearch(null);
    state.fundResearchTemplate = null;
    state.fundResearchRun = null;
    state.fundResearchSequence += 1;
    byId("fund-research-template-meta").textContent = "运行时读取固定合成基金与资产风险规则；结果不写入决策回执。";
    clearFundResearchScenarioOptions();
    setFundResearchStatus("待运行");
    renderFundResearch(null);
    state.convertibleBondResearchTemplate = null;
    state.convertibleBondResearchRun = null;
    state.convertibleBondResearchSequence += 1;
    byId("convertible-bond-research-template-meta").textContent = "运行时读取固定合成可转债、确定性公式与风险规则；结果不写入决策回执。";
    clearConvertibleBondResearchScenarioOptions();
    setConvertibleBondResearchStatus("待运行");
    renderConvertibleBondResearch(null);
    state.portfolioOptimizationTemplate = null;
    state.portfolioOptimizationRun = null;
    state.portfolioOptimizationSequence += 1;
    byId("portfolio-optimization-template-meta").textContent = "运行时读取确定性上限重分配（cap-and-redistribute）方法与合成组合模板。";
    clearPortfolioOptimizationScenarioOptions();
    setPortfolioOptimizationStatus("待运行");
    renderPortfolioOptimization(null);
    state.scenarioSimulationTemplate = null;
    state.scenarioSimulationRun = null;
    state.scenarioSimulationSequence += 1;
    const simMeta = byId("scenario-simulation-template-meta");
    if (simMeta) simMeta.textContent = "基于已确认画像与持仓进行确定性假设对比；结果不作为买卖建议或交易指令。";
    clearScenarioSimulationScenarioOptions();
    setScenarioSimulationStatus("待运行");
    renderScenarioSimulation(null);
  }

  async function runAdvisorQuery(event) {
    event.preventDefault();
    const nextOwnerId = byId("owner-id").value.trim();
    const ownerChanged = nextOwnerId !== state.ownerId;
    state.ownerId = nextOwnerId;
    if (ownerChanged || !state.ownerId) resetOwnerScopedViews();
    const requestOwner = state.ownerId;
    const templateSequence = ++state.templateSequence;
    const queryId = byId("query-id").value.trim();
    const submit = byId("run-advisor-query");
    if (!state.ownerId) {
      setError("请输入隔离标识。");
      return;
    }
    if (!queryId) {
      setError("请输入查询 ID。");
      return;
    }
    setError("");
    submit.disabled = true;
    setQueryStatus("运行中…");
    try {
      const template = state.queryTemplate || await loadTemplateContext(requestOwner, templateSequence);
      if (!template) return;

      const questionnaire = buildQuestionnaire(template);
      const payload = {
        schema_version: "advisor-query.v1",
        query_id: queryId,
        fixture_id: template.fixture_id,
        generated_at: template.generated_at,
        questionnaire,
        portfolio: state.portfolioContext || template.portfolio,
      };
      const response = await fetch("/api/v1/advisor/queries", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Owner-ID": state.ownerId,
        },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw await apiError(response);
      if (state.ownerId !== requestOwner || state.templateSequence !== templateSequence) return;
      const result = await response.json();
      const createdLabel = result.created ? "已保存" : "已复用";
      setQueryStatus(`${statusLabel(result.status)} · ${createdLabel}`, statusClass(result.status));
      await loadEvents();
      if (result.event && result.event.event_id) await loadEvent(result.event.event_id);
    } catch (error) {
      setQueryStatus("未运行", "blocked");
      setError(error.message || "运行投顾查询失败");
    } finally {
      submit.disabled = false;
    }
  }

  async function runResearchMatrix() {
    const nextOwnerId = byId("owner-id").value.trim();
    const ownerChanged = nextOwnerId !== state.ownerId;
    state.ownerId = nextOwnerId;
    if (ownerChanged || !state.ownerId) resetOwnerScopedViews();
    const requestOwner = state.ownerId;
    const researchSequence = ++state.researchSequence;
    const submit = byId("run-research-matrix");
    const scenarioSelect = byId("research-scenario");
    if (!state.ownerId) {
      setError("请输入隔离标识。");
      return;
    }
    setError("");
    submit.disabled = true;
    scenarioSelect.disabled = true;
    state.researchRun = null;
    renderResearchMatrix(null);
    setResearchStatus("运行中…");
    try {
      const templateResponse = await fetch("/api/v1/advisor/research-matrix-template", {
        headers: { "X-Owner-ID": state.ownerId },
      });
      if (!templateResponse.ok) throw await apiError(templateResponse);
      const template = await templateResponse.json();
      if (state.ownerId !== requestOwner || state.researchSequence !== researchSequence) return;
      state.researchTemplate = template;
      renderResearchScenarioOptions(template.scenarios);
      const scenarioId = scenarioSelect.value || "BASELINE_READY";
      scenarioSelect.disabled = true;
      byId("research-template-meta").textContent = `矩阵 ${text(template.matrix_id)} · ${text(template.node_count)} 个节点 · ${text((template.scenarios || []).length, "0")} 个回放场景 · 生成时间 ${text(template.generated_at)}`;
      const response = await fetch("/api/v1/advisor/research-runs", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Owner-ID": state.ownerId,
        },
        body: JSON.stringify({
          schema_version: "research-specialist-matrix-request.v1",
          matrix_id: template.matrix_id,
          request_id: "ui-research-001",
          owner_id: state.ownerId,
          generated_at: template.generated_at,
          scenario_id: scenarioId,
        }),
      });
      if (!response.ok) throw await apiError(response);
      if (state.ownerId !== requestOwner || state.researchSequence !== researchSequence) return;
      state.researchRun = await response.json();
      setResearchStatus(
        researchStatusLabel(state.researchRun.pipeline_status),
        researchStatusClass(state.researchRun.pipeline_status),
      );
      renderResearchMatrix(state.researchRun);
    } catch (error) {
      if (state.ownerId !== requestOwner || state.researchSequence !== researchSequence) return;
      state.researchRun = null;
      renderResearchMatrix(null);
      setResearchStatus("未运行", "blocked");
      setError(error.message || "运行研究矩阵失败");
    } finally {
      submit.disabled = false;
      if (state.ownerId === requestOwner && state.researchSequence === researchSequence) {
        scenarioSelect.disabled = !state.researchTemplate;
      }
    }
  }

  async function runStockResearch() {
    const nextOwnerId = byId("owner-id").value.trim();
    const ownerChanged = nextOwnerId !== state.ownerId;
    state.ownerId = nextOwnerId;
    if (ownerChanged || !state.ownerId) resetOwnerScopedViews();
    const requestOwner = state.ownerId;
    let sequence = ++state.stockResearchSequence;
    const submit = byId("run-stock-research");
    const scenarioSelect = byId("stock-research-scenario");
    if (!state.ownerId) {
      setError("请输入隔离标识。");
      return;
    }
    setError("");
    submit.disabled = true;
    scenarioSelect.disabled = true;
    state.stockResearchRun = null;
    renderStockResearch(null);
    setStockResearchStatus("运行中…");
    try {
      let template = state.stockResearchTemplate;
      if (!template) {
        template = await loadStockResearchCatalog(requestOwner);
        sequence = state.stockResearchSequence;
      }
      if (!template) return;
      if (state.ownerId !== requestOwner || state.stockResearchSequence !== sequence) return;
      const scenarioId = scenarioSelect.value || "BASELINE_READY";
      const response = await fetch("/api/v1/advisor/stock-research-runs", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Owner-ID": requestOwner,
        },
        body: JSON.stringify({
          schema_version: "stock-research-request.v1",
          request_id: "ui-stock-research-001",
          owner_id: requestOwner,
          subject: template.subject,
          period: template.period,
          generated_at: template.generated_at,
          scenario_id: scenarioId,
        }),
      });
      if (!response.ok) throw await apiError(response);
      if (state.ownerId !== requestOwner || state.stockResearchSequence !== sequence) return;
      state.stockResearchRun = await response.json();
      setStockResearchStatus(
        researchStatusLabel(state.stockResearchRun.pipeline_status),
        researchStatusClass(state.stockResearchRun.pipeline_status),
      );
      renderStockResearch(state.stockResearchRun);
    } catch (error) {
      if (state.ownerId !== requestOwner || state.stockResearchSequence !== sequence) return;
      state.stockResearchRun = null;
      renderStockResearch(null);
      setStockResearchStatus("未运行", "blocked");
      setError(error.message || "运行个股研究失败");
    } finally {
      submit.disabled = false;
      if (state.ownerId === requestOwner && state.stockResearchSequence === sequence) {
        scenarioSelect.disabled = !state.stockResearchTemplate;
      }
    }
  }

  async function runFundResearch() {
    const nextOwnerId = byId("owner-id").value.trim();
    const ownerChanged = nextOwnerId !== state.ownerId;
    state.ownerId = nextOwnerId;
    if (ownerChanged || !state.ownerId) resetOwnerScopedViews();
    const requestOwner = state.ownerId;
    let sequence = ++state.fundResearchSequence;
    const submit = byId("run-fund-research");
    const scenarioSelect = byId("fund-research-scenario");
    if (!state.ownerId) {
      setError("请输入隔离标识。");
      return;
    }
    setError("");
    submit.disabled = true;
    scenarioSelect.disabled = true;
    state.fundResearchRun = null;
    renderFundResearch(null);
    setFundResearchStatus("运行中…");
    try {
      let template = state.fundResearchTemplate;
      if (!template) {
        template = await loadFundResearchCatalog(requestOwner);
        sequence = state.fundResearchSequence;
      }
      if (!template) return;
      if (state.ownerId !== requestOwner || state.fundResearchSequence !== sequence) return;
      const scenarioId = scenarioSelect.value || "BASELINE_READY";
      const response = await fetch("/api/v1/advisor/fund-research-runs", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Owner-ID": requestOwner,
        },
        body: JSON.stringify({
          schema_version: "fund-research-request.v1",
          request_id: "ui-fund-research-001",
          owner_id: requestOwner,
          subject: template.subject,
          period: template.period,
          generated_at: template.generated_at,
          scenario_id: scenarioId,
        }),
      });
      if (!response.ok) throw await apiError(response);
      if (state.ownerId !== requestOwner || state.fundResearchSequence !== sequence) return;
      state.fundResearchRun = await response.json();
      setFundResearchStatus(
        researchStatusLabel(state.fundResearchRun.pipeline_status),
        researchStatusClass(state.fundResearchRun.pipeline_status),
      );
      renderFundResearch(state.fundResearchRun);
    } catch (error) {
      if (state.ownerId !== requestOwner || state.fundResearchSequence !== sequence) return;
      state.fundResearchRun = null;
      renderFundResearch(null);
      setFundResearchStatus("未运行", "blocked");
      setError(error.message || "运行 ETF / 基金研究失败");
    } finally {
      submit.disabled = false;
      if (state.ownerId === requestOwner && state.fundResearchSequence === sequence) {
        scenarioSelect.disabled = !state.fundResearchTemplate;
      }
    }
  }

  async function runConvertibleBondResearch() {
    const nextOwnerId = byId("owner-id").value.trim();
    const ownerChanged = nextOwnerId !== state.ownerId;
    state.ownerId = nextOwnerId;
    if (ownerChanged || !state.ownerId) resetOwnerScopedViews();
    const requestOwner = state.ownerId;
    let sequence = ++state.convertibleBondResearchSequence;
    const submit = byId("run-convertible-bond-research");
    const scenarioSelect = byId("convertible-bond-research-scenario");
    if (!state.ownerId) {
      setError("请输入隔离标识。");
      return;
    }
    setError("");
    submit.disabled = true;
    scenarioSelect.disabled = true;
    state.convertibleBondResearchRun = null;
    renderConvertibleBondResearch(null);
    setConvertibleBondResearchStatus("运行中…");
    try {
      let template = state.convertibleBondResearchTemplate;
      if (!template) {
        template = await loadConvertibleBondResearchCatalog(requestOwner);
        sequence = state.convertibleBondResearchSequence;
      }
      if (!template) return;
      if (state.ownerId !== requestOwner || state.convertibleBondResearchSequence !== sequence) return;
      const scenarioId = scenarioSelect.value || "BASELINE_READY";
      const response = await fetch("/api/v1/advisor/convertible-bond-research-runs", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Owner-ID": requestOwner,
        },
        body: JSON.stringify({
          schema_version: "convertible-bond-research-request.v1",
          request_id: "ui-convertible-bond-research-001",
          owner_id: requestOwner,
          subject: template.subject,
          period: template.period,
          generated_at: template.generated_at,
          scenario_id: scenarioId,
        }),
      });
      if (!response.ok) throw await apiError(response);
      if (state.ownerId !== requestOwner || state.convertibleBondResearchSequence !== sequence) return;
      state.convertibleBondResearchRun = await response.json();
      setConvertibleBondResearchStatus(
        researchStatusLabel(state.convertibleBondResearchRun.pipeline_status),
        researchStatusClass(state.convertibleBondResearchRun.pipeline_status),
      );
      renderConvertibleBondResearch(state.convertibleBondResearchRun);
    } catch (error) {
      if (state.ownerId !== requestOwner || state.convertibleBondResearchSequence !== sequence) return;
      state.convertibleBondResearchRun = null;
      renderConvertibleBondResearch(null);
      setConvertibleBondResearchStatus("未运行", "blocked");
      setError(error.message || "运行可转债研究失败");
    } finally {
      submit.disabled = false;
      if (state.ownerId === requestOwner && state.convertibleBondResearchSequence === sequence) {
        scenarioSelect.disabled = !state.convertibleBondResearchTemplate;
      }
    }
  }

  async function runPortfolioOptimization() {
    const requestOwner = byId("owner-id").value.trim();
    const submit = byId("run-portfolio-optimization");
    const scenarioSelect = byId("portfolio-optimization-scenario");
    if (!requestOwner) {
      setError("请输入隔离标识。");
      return;
    }
    if (!state.portfolioOptimizationTemplate) {
      try {
        await loadPortfolioOptimizationCatalog(requestOwner);
      } catch (error) {
        setError(error.message || "读取组合优化模板失败");
        return;
      }
    }
    const template = state.portfolioOptimizationTemplate;
    if (!template || state.ownerId !== requestOwner) return;
    if (!state.profileContext || !state.profileContext.profile) {
      setPortfolioOptimizationStatus("需先确认画像", "review");
      setError("请先确认风险画像，再生成组合目标结构。");
      return;
    }
    const requestSequence = ++state.portfolioOptimizationSequence;
    const scenarioId = scenarioSelect.value || "BASELINE_READY";
    const questionnaire = state.profileContext && state.profileContext.questionnaire
      ? state.profileContext.questionnaire
      : template.questionnaire;
    const portfolio = state.portfolioContext || template.portfolio;
    submit.disabled = true;
    scenarioSelect.disabled = true;
    state.portfolioOptimizationRun = null;
    renderPortfolioOptimization(null);
    setPortfolioOptimizationStatus("运行中…");
    setError("");
    try {
      const response = await fetch("/api/v1/advisor/portfolio-optimization-runs", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Owner-ID": requestOwner,
        },
        body: JSON.stringify({
          schema_version: "portfolio-optimization-request.v1",
          request_id: "ui-portfolio-optimization-001",
          owner_id: requestOwner,
          generated_at: template.generated_at,
          questionnaire,
          portfolio,
          scenario_id: scenarioId,
        }),
      });
      if (!response.ok) throw await apiError(response);
      if (state.ownerId !== requestOwner || state.portfolioOptimizationSequence !== requestSequence) return;
      state.portfolioOptimizationRun = await response.json();
      setPortfolioOptimizationStatus(
        optimizationStatusLabel(state.portfolioOptimizationRun.status),
        optimizationStatusClass(state.portfolioOptimizationRun.status),
      );
      renderPortfolioOptimization(state.portfolioOptimizationRun);
    } catch (error) {
      if (state.ownerId !== requestOwner || state.portfolioOptimizationSequence !== requestSequence) return;
      state.portfolioOptimizationRun = null;
      renderPortfolioOptimization(null);
      setPortfolioOptimizationStatus("未运行", "blocked");
      setError(error.message || "生成组合目标结构失败");
    } finally {
      submit.disabled = false;
      if (state.ownerId === requestOwner && state.portfolioOptimizationSequence === requestSequence) {
        scenarioSelect.disabled = !state.portfolioOptimizationTemplate;
      }
    }
  }

  async function runScenarioSimulation() {
    const requestOwner = byId("owner-id").value.trim();
    const submit = byId("run-scenario-simulation");
    const scenarioSelect = byId("scenario-simulation-scenario");
    if (!requestOwner) {
      setError("请输入隔离标识。");
      return;
    }
    if (!state.scenarioSimulationTemplate) {
      try {
        await loadScenarioSimulationCatalog(requestOwner);
      } catch (error) {
        setError(error.message || "读取情景模拟模板失败");
        return;
      }
    }
    const template = state.scenarioSimulationTemplate;
    if (!template || state.ownerId !== requestOwner) return;
    if (!state.profileContext || !state.profileContext.profile) {
      setScenarioSimulationStatus("需先确认画像", "review");
      setError("请先确认风险画像，再运行情景模拟。");
      return;
    }
    const requestSequence = ++state.scenarioSimulationSequence;
    const scenarioId = scenarioSelect.value || "BASELINE_READY";
    const baseTemplate = state.queryTemplate || state.portfolioOptimizationTemplate;
    const questionnaire = state.profileContext && state.profileContext.questionnaire
      ? state.profileContext.questionnaire
      : (baseTemplate ? buildQuestionnaire(baseTemplate) : null);
    const portfolio = state.portfolioContext || baseTemplate?.portfolio;
    if (!questionnaire || !portfolio) {
      setError("未找到有效持仓快照或问卷数据，请先加载工作台模板。");
      return;
    }
    submit.disabled = true;
    scenarioSelect.disabled = true;
    state.scenarioSimulationRun = null;
    renderScenarioSimulation(null);
    setScenarioSimulationStatus("运行中…");
    setError("");
    try {
      const response = await fetch("/api/v1/advisor/scenario-simulation-runs", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Owner-ID": requestOwner,
        },
        body: JSON.stringify({
          schema_version: "scenario-simulation-request.v1",
          request_id: "ui-scenario-simulation-001",
          owner_id: requestOwner,
          generated_at: template.generated_at,
          scenario_id: scenarioId,
          questionnaire,
          portfolio,
        }),
      });
      if (!response.ok) throw await apiError(response);
      if (state.ownerId !== requestOwner || state.scenarioSimulationSequence !== requestSequence) return;
      state.scenarioSimulationRun = await response.json();
      setScenarioSimulationStatus(
        optimizationStatusLabel(state.scenarioSimulationRun.status),
        optimizationStatusClass(state.scenarioSimulationRun.status),
      );
      renderScenarioSimulation(state.scenarioSimulationRun);
    } catch (error) {
      if (state.ownerId !== requestOwner || state.scenarioSimulationSequence !== requestSequence) return;
      state.scenarioSimulationRun = null;
      renderScenarioSimulation(null);
      setScenarioSimulationStatus("未运行", "blocked");
      setError(error.message || "运行情景模拟失败");
    } finally {
      submit.disabled = false;
      if (state.ownerId === requestOwner && state.scenarioSimulationSequence === requestSequence) {
        scenarioSelect.disabled = !state.scenarioSimulationTemplate;
      }
    }
  }

  async function loadEvents() {
    const nextOwnerId = byId("owner-id").value.trim();
    const ownerChanged = nextOwnerId !== state.ownerId;
    state.ownerId = nextOwnerId;
    const requestOwner = state.ownerId;
    const templateSequence = ++state.templateSequence;
    setError("");
    state.selected = null;
    state.selectedDecisionEvent = null;
    renderEvents();
    renderEvidence(null);
    byId("detail-status").className = "status-chip";
    byId("detail-status").textContent = "读取中…";
    clear(byId("detail-content"));
    const loadingDetail = document.createElement("div");
    loadingDetail.className = "empty-state";
    loadingDetail.textContent = "读取当前隔离标识的决策回执…";
    byId("detail-content").append(loadingDetail);
    if (ownerChanged || !state.ownerId) {
      resetOwnerScopedViews();
    }
    if (!state.ownerId) {
      setError("请输入隔离标识。");
      return;
    }
    try {
      const response = await fetch("/api/v1/decision-events", {
        headers: { "X-Owner-ID": requestOwner },
      });
      if (!response.ok) throw await apiError(response);
      if (state.ownerId !== requestOwner || state.templateSequence !== templateSequence) return;
      state.events = (await response.json()).items || [];
      state.selected = null;
      state.selectedDecisionEvent = null;
      renderEvents();
      renderProfile(null);
      renderEvidence(null);
      byId("detail-status").className = "status-chip";
      byId("detail-status").textContent = "待选择";
      byId("detail-content").replaceChildren();
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = state.events.length ? "选择一条回执查看详情。" : "这个隔离标识还没有保存的决策事件。";
      byId("detail-content").append(empty);
      try {
        await loadTemplateContext(requestOwner, templateSequence);
      } catch (error) {
        if (state.ownerId === requestOwner && state.templateSequence === templateSequence) {
      setError(error.message || "读取持仓/风险画像模板失败");
        }
      }
      if (state.ownerId === requestOwner && !state.researchTemplate) {
        try {
          await loadResearchScenarioCatalog(requestOwner);
        } catch (error) {
          if (state.ownerId === requestOwner) {
            clearResearchScenarioOptions();
            setError(error.message || "读取研究场景目录失败");
          }
        }
      }
      if (state.ownerId === requestOwner && !state.stockResearchTemplate) {
        try {
          await loadStockResearchCatalog(requestOwner);
        } catch (error) {
          if (state.ownerId === requestOwner) {
            clearStockResearchScenarioOptions();
            setError(error.message || "读取个股研究场景目录失败");
          }
        }
      }
      if (state.ownerId === requestOwner && !state.fundResearchTemplate) {
        try {
          await loadFundResearchCatalog(requestOwner);
        } catch (error) {
          if (state.ownerId === requestOwner) {
            clearFundResearchScenarioOptions();
            setError(error.message || "读取 ETF / 基金研究场景目录失败");
          }
        }
      }
      if (state.ownerId === requestOwner && !state.convertibleBondResearchTemplate) {
        try {
          await loadConvertibleBondResearchCatalog(requestOwner);
        } catch (error) {
          if (state.ownerId === requestOwner) {
            clearConvertibleBondResearchScenarioOptions();
            setError(error.message || "读取可转债研究场景目录失败");
          }
        }
      }
      if (state.ownerId === requestOwner && !state.portfolioOptimizationTemplate) {
        try {
          await loadPortfolioOptimizationCatalog(requestOwner);
        } catch (error) {
          if (state.ownerId === requestOwner) {
            clearPortfolioOptimizationScenarioOptions();
            setError(error.message || "读取组合优化场景目录失败");
          }
        }
      }
      if (state.ownerId === requestOwner && !state.scenarioSimulationTemplate) {
        try {
          await loadScenarioSimulationCatalog(requestOwner);
        } catch (error) {
          if (state.ownerId === requestOwner) {
            clearScenarioSimulationScenarioOptions();
            setError(error.message || "读取情景模拟场景目录失败");
          }
        }
      }
      if (state.ownerId === requestOwner) {
        try {
          await loadContextMemory(requestOwner);
        } catch (error) {
          if (state.ownerId === requestOwner) {
            setContextMemoryStatus("读取失败", "blocked");
            setError(error.message || "读取上下文记忆失败");
          }
        }
      }
      if (state.events.length) await loadEvent(state.events[0].event_id);
    } catch (error) {
      state.events = [];
      renderEvents();
      setError(error.message || "读取决策列表失败");
    }
  }

  async function checkHealth() {
    const node = byId("health-status");
    try {
      const response = await fetch("/api/health");
      if (!response.ok) throw new Error("health check failed");
      node.classList.add("ok");
      node.textContent = "● API 已连接";
    } catch (_) {
      node.classList.add("bad");
      node.textContent = "● API 不可用";
    }
  }

  function syncNavigation(targetId = window.location.hash.replace(/^#/, "")) {
    const items = [...document.querySelectorAll(".nav-item")];
    if (!items.length) return;
    const target = items.find((item) => item.getAttribute("href") === `#${targetId}`)
      || items.find((item) => item.getAttribute("href") === "#overview")
      || items[0];
    items.forEach((item) => {
      const selected = item === target;
      item.classList.toggle("active", selected);
      if (selected) item.setAttribute("aria-current", "location");
      else item.removeAttribute("aria-current");
    });
  }

  function initializeNavigation() {
    const items = [...document.querySelectorAll(".nav-item")];
    items.forEach((item) => {
      item.addEventListener("click", () => syncNavigation(item.hash.slice(1)));
    });
    window.addEventListener("hashchange", () => syncNavigation());
    syncNavigation();
  }

  byId("load-events").addEventListener("click", loadEvents);
  byId("advisor-query-form").addEventListener("submit", runAdvisorQuery);
  byId("confirm-portfolio").addEventListener("click", confirmPortfolioContext);
  byId("confirm-profile").addEventListener("click", confirmProfileContext);
  byId("preview-profile-proposal").addEventListener("click", previewProfileProposal);
  byId("confirm-profile-proposal").addEventListener("click", confirmProfileProposal);
  byId("preview-advisor-plan").addEventListener("click", previewAdvisorPlan);
  byId("intent-type").addEventListener("change", clearAdvisorPlan);
  byId("run-research-matrix").addEventListener("click", runResearchMatrix);
  byId("research-scenario").addEventListener("change", () => {
    state.researchRun = null;
    renderResearchMatrix(null);
    setResearchStatus("待运行");
  });
  byId("run-stock-research").addEventListener("click", runStockResearch);
  byId("stock-research-scenario").addEventListener("change", () => {
    state.stockResearchRun = null;
    state.stockResearchSequence += 1;
    renderStockResearch(null);
    setStockResearchStatus("待运行");
  });
  byId("run-fund-research").addEventListener("click", runFundResearch);
  byId("fund-research-scenario").addEventListener("change", () => {
    state.fundResearchRun = null;
    state.fundResearchSequence += 1;
    renderFundResearch(null);
    setFundResearchStatus("待运行");
  });
  byId("run-convertible-bond-research").addEventListener("click", runConvertibleBondResearch);
  byId("convertible-bond-research-scenario").addEventListener("change", () => {
    state.convertibleBondResearchRun = null;
    state.convertibleBondResearchSequence += 1;
    renderConvertibleBondResearch(null);
    setConvertibleBondResearchStatus("待运行");
  });
  byId("run-portfolio-optimization").addEventListener("click", runPortfolioOptimization);
  byId("advanced-evidence-search").addEventListener("input", (event) => {
    state.advancedEvidenceSearch = event.target.value;
    renderAdvancedEvidence();
  });
  byId("advanced-evidence-quality").addEventListener("change", (event) => {
    state.advancedEvidenceQuality = event.target.value;
    state.advancedEvidenceSelectedKey = "";
    renderAdvancedEvidence();
  });
  byId("advanced-evidence-mode").addEventListener("change", (event) => {
    state.advancedEvidenceMode = event.target.value;
    state.advancedEvidenceSelectedKey = "";
    renderAdvancedEvidence();
  });
  byId("advanced-evidence-source").addEventListener("change", (event) => {
    state.advancedEvidenceSource = event.target.value;
    state.advancedEvidenceSelectedKey = "";
    renderAdvancedEvidence();
  });
  byId("advanced-evidence-promotion").addEventListener("change", (event) => {
    state.advancedEvidencePromotion = event.target.value;
    state.advancedEvidenceSelectedKey = "";
    renderAdvancedEvidence();
  });
  byId("clear-advanced-evidence-filters").addEventListener("click", () => {
    state.advancedEvidenceSearch = "";
    state.advancedEvidenceQuality = "ALL";
    state.advancedEvidenceMode = "ALL";
    state.advancedEvidenceSource = "ALL";
    state.advancedEvidencePromotion = "ALL";
    state.advancedEvidenceSelectedKey = "";
    renderAdvancedEvidence();
  });
  byId("save-context-memory").addEventListener("click", saveContextMemory);
  byId("load-context-memory").addEventListener("click", () => {
    const nextOwnerId = byId("owner-id").value.trim();
    const ownerChanged = nextOwnerId !== state.ownerId;
    state.ownerId = nextOwnerId;
    if (ownerChanged || !state.ownerId) resetOwnerScopedViews();
    loadContextMemory(state.ownerId);
  });
  byId("portfolio-optimization-scenario").addEventListener("change", () => {
    state.portfolioOptimizationRun = null;
    state.portfolioOptimizationSequence += 1;
    renderPortfolioOptimization(null);
    setPortfolioOptimizationStatus("待运行");
  });
  const scenarioOptSelect = byId("scenario-simulation-scenario");
  if (scenarioOptSelect) {
    scenarioOptSelect.addEventListener("change", () => {
      state.scenarioSimulationRun = null;
      state.scenarioSimulationSequence += 1;
      renderScenarioSimulation(null);
      setScenarioSimulationStatus("待运行");
    });
  }
  const runScenarioBtn = byId("run-scenario-simulation");
  if (runScenarioBtn) runScenarioBtn.addEventListener("click", runScenarioSimulation);
  byId("owner-id").addEventListener("keydown", (event) => {
    if (event.key === "Enter") loadEvents();
  });
  [
    "query-id",
    "loss-tolerance",
    "investment-horizon",
    "liquidity-need",
    "experience-level",
    "return-expectation",
    "max-drawdown",
  ].forEach((id) => {
    byId(id).addEventListener("change", () => {
      clearAdvisorPlan();
      clearProfileProposal();
      state.portfolioOptimizationRun = null;
      state.portfolioOptimizationSequence += 1;
      renderPortfolioOptimization(null);
      setPortfolioOptimizationStatus("需重新运行", "review");
      state.scenarioSimulationRun = null;
      state.scenarioSimulationSequence += 1;
      renderScenarioSimulation(null);
      setScenarioSimulationStatus("需重新运行", "review");
      if (!state.profileContext) return;
      state.profileContext = null;
      renderConfirmedProfile(null);
      setProfileContextStatus("需重新确认", "review");
    });
  });
  initializeNavigation();
  checkHealth();
  loadEvents();
})();
