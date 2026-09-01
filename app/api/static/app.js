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
  };
  const byId = (id) => document.getElementById(id);

  function text(value, fallback = "—") {
    if (value === null || value === undefined || value === "") return fallback;
    return String(value);
  }

  function clear(node) {
    node.replaceChildren();
  }

  function setError(message = "") {
    const node = byId("global-error");
    node.textContent = message;
    node.hidden = !message;
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
    return status === "READY" ? "READY"
      : status === "REVIEW_REQUIRED" ? "待复核"
        : status === "BLOCKED" ? "已阻断"
          : status === "COMPLETED" || status === "COMPLETE" ? "完成"
            : status === "PARTIAL" ? "部分完成"
              : status === "FAILED" ? "失败"
                : status === "EMPTY" ? "无结果" : text(status, "待运行");
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

  function researchRoleLabel(role) {
    return role === "ETF_FUND" ? "ETF / Fund" : text(role);
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
      option.value = text(scenario.scenario_id, "");
      option.textContent = text(scenario.label, option.value);
      option.title = text(scenario.description, "");
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
    select.value = known ? previous : text(options[0].scenario_id, "");
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
      option.value = text(scenario.scenario_id, "");
      option.textContent = text(scenario.label, option.value);
      option.title = text(scenario.description, "");
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
    select.value = known ? previous : text(options[0].scenario_id, "");
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
      option.value = text(scenario.scenario_id, "");
      option.textContent = text(scenario.label, option.value);
      option.title = text(scenario.description, "");
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
    select.value = known ? previous : text(options[0].scenario_id, "");
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
      option.value = text(scenario.scenario_id, "");
      option.textContent = text(scenario.label, option.value);
      option.title = text(scenario.description, "");
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
    select.value = known ? previous : text(options[0].scenario_id, "");
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
      option.value = text(scenario.scenario_id, "");
      option.textContent = text(scenario.label, option.value);
      option.title = text(scenario.description, "");
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
    select.value = known ? previous : text(options[0].scenario_id, "");
    select.disabled = false;
  }

  function stockRiskStatusClass(status) {
    return status === "CLEAR" ? "pass" : status === "WATCH" ? "review" : "blocked";
  }

  function stockRiskStatusLabel(status) {
    return status === "HIGH_RISK" ? "高风险" : status === "WATCH" ? "需关注" : status === "CLEAR" ? "规则未触发" : "未评估";
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
    return status === "READY" ? "READY"
      : status === "REVIEW_REQUIRED" ? "待复核"
        : status === "BLOCKED" ? "已阻断" : text(status, "待运行");
  }

  function optimizationStatusClass(status) {
    return status === "READY" ? "pass" : status === "REVIEW_REQUIRED" ? "review" : "blocked";
  }

  function statusClass(status) {
    return status === "PASS" ? "pass" : status === "REVIEW_REQUIRED" ? "review" : "blocked";
  }

  function statusLabel(status) {
    return status === "PASS" ? "PASS" : status === "REVIEW_REQUIRED" ? "待复核" : "已阻断";
  }

  function chip(label, className) {
    const node = document.createElement("span");
    node.className = `status-chip ${className || ""}`.trim();
    node.textContent = label;
    return node;
  }

  function renderEvents() {
    const list = byId("event-list");
    clear(list);
    byId("event-count").textContent = `${state.events.length} events`;
    if (!state.events.length) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "这个 owner 还没有保存的决策事件。";
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
    dt.textContent = label;
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
      empty.textContent = "读取 owner 模板后查看持仓快照与基金穿透范围。";
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
    positionsHeading.textContent = "Positions";
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
    holdingHeading.textContent = "Look-through holdings";
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
      meta.textContent = `${text(fund.parent_asset_id)} · snapshot ${text(fund.snapshot_id)} · coverage ${text(fund.coverage_pct)}% · as of ${text(fund.as_of)}`;
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

  function renderProfileContext(questionnaire) {
    const panel = byId("profile-template-content");
    clear(panel);
    if (!questionnaire) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "读取 owner 模板后查看风险问卷约束。";
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
      investment_horizon: "Investment horizon",
      liquidity_need: "Liquidity need",
      experience_level: "Experience level",
      return_expectation: "Return expectation",
      max_drawdown_tolerance_pct: "Max drawdown tolerance",
      expected_return_range: "Expected return range",
    }[dimension] || text(dimension);
  }

  function renderProfileProposalResult(profile) {
    const panel = byId("profile-proposal-result");
    clear(panel);
    if (!profile) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "确认提案后查看保留冲突选择的 Risk Profile。";
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
      heading.textContent = "Resolved conflicts";
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
      ready.textContent = "没有维度冲突；仍需显式确认后生成 Profile。";
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
    addMetadata(metadata, "Scope", plan.scope_description);
    addMetadata(metadata, "Nodes", plan.node_count);
    panel.append(metadata);

    const heading = document.createElement("h4");
    heading.className = "context-heading";
    heading.textContent = "Specialist tracks";
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
      empty.textContent = "该事件没有可展示的 Receipt。";
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
        item.textContent = `${issue.code}: ${issue.safe_message}`;
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
    summaryLabel.textContent = "WHY THIS DECISION";
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
      action.textContent = recommendation.action_type;
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
      item.textContent = condition;
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
      empty.textContent = "选择 PASS 回执后展开证据。";
      panel.append(empty);
      return;
    }
    const evidenceById = new Map((result.trace.evidence || []).map((item) => [item.evidence_id, item]));
    const factsById = new Map((result.trace.facts || []).map((item) => [item.fact_id, item]));
    (result.trace.findings || []).forEach((finding) => {
      const details = document.createElement("details");
      details.className = "evidence-item";
      const summary = document.createElement("summary");
      summary.textContent = `${finding.kind} · ${finding.statement}`;
      details.append(summary);
      const meta = document.createElement("div");
      meta.className = "evidence-meta";
      const addMetaLine = (value) => {
        const line = document.createElement("div");
        line.textContent = value;
        meta.append(line);
      };
      addMetaLine(`Finding: ${finding.finding_id}`);
      finding.fact_ids.forEach((factId) => {
        const fact = factsById.get(factId);
        if (!fact) return;
        addMetaLine(`Fact: ${fact.fact_id} · ${fact.metric} = ${text(fact.value)}`);
        fact.evidence_ids.forEach((evidenceId) => {
          const evidence = evidenceById.get(evidenceId);
          if (!evidence) return;
          addMetaLine(`Evidence: ${evidence.evidence_id} · ${evidence.source} · ${text(evidence.period)}`);
        });
      });
      details.append(meta);
      panel.append(details);
    });
    if (!panel.childElementCount) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "该回执没有可展示的 Finding。";
      panel.append(empty);
    }
  }

  function renderResearchMatrix(result) {
    const panel = byId("research-matrix-content");
    clear(panel);
    if (!result) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "运行矩阵后查看四类节点、独立来源验证与 Finding → Fact → Evidence。";
      panel.append(empty);
      return;
    }

    const summary = document.createElement("div");
    summary.className = "research-summary";
    summary.append(
      chip(researchStatusLabel(result.pipeline_status), researchStatusClass(result.pipeline_status)),
      chip(`Run ${researchStatusLabel(result.run_status)}`, researchStatusClass(result.run_status)),
    );
    const summaryText = document.createElement("p");
    summaryText.textContent = `${text(result.matrix_id)} · ${text(result.run_id)} · owner ${text(result.owner_id)}`;
    summary.append(summaryText);
    if (result.scenario) {
      const scenarioText = document.createElement("p");
      scenarioText.textContent = `${text(result.scenario.label)} · ${text(result.scenario.description)}`;
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
          item.textContent = `${text(issue.code)}: ${text(issue.safe_message)}`;
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
      notice.textContent = "研究结果仍需复核，Prism 不展示未验证的 Fact/Finding，也不会生成可执行建议。";
      panel.append(notice);
      const issues = document.createElement("ul");
      issues.className = "research-issues";
      (result.issues || []).forEach((issue) => {
        const item = document.createElement("li");
        item.textContent = `${text(issue.code)}: ${text(issue.safe_message)}`;
        issues.append(item);
      });
      if (issues.childElementCount) panel.append(issues);
    }

    const validationHeading = document.createElement("h3");
    validationHeading.textContent = "Independent lineage validation";
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
      meta.textContent = `expected ${text(validation.expected_value)} ${text(validation.unit)} · ${text(validation.period)} · ${text(validation.independent_lineage_count)} independent lineages · support ${text((validation.supporting_evidence_ids || []).length, "0")} · contradict ${text((validation.contradicting_evidence_ids || []).length, "0")} · unresolved ${text((validation.unresolved_evidence_ids || []).length, "0")}`;
      row.append(meta);
      if (validation.issues && validation.issues.length) {
        const issues = document.createElement("ul");
        issues.className = "validation-issues";
        validation.issues.forEach((issue) => {
          const item = document.createElement("li");
          item.textContent = `${text(issue.code)}: ${text(issue.safe_message)}`;
          issues.append(item);
        });
        row.append(issues);
      }
      validations.append(row);
    });
    panel.append(validations);

    if (result.pipeline_status !== "READY") {
      const availableHeading = document.createElement("h3");
      availableHeading.textContent = "Available Evidence · not promoted to Fact";
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
          `Evidence: ${text(evidence.evidence_id)}`,
          `Value: ${text(evidence.value)} ${text(evidence.unit, "")}`,
          `Period: ${text(evidence.period)}`,
          `Lineage: ${text(evidence.lineage_id)}`,
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
    evidenceHeading.textContent = "Finding → Fact → Evidence";
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
      findingLine.textContent = `Finding: ${text(finding.finding_id)} · ${text(finding.severity)}`;
      metadata.append(findingLine);
      (finding.fact_ids || []).forEach((factId) => {
        const fact = factsById.get(factId);
        if (!fact) return;
        const factLine = document.createElement("div");
        factLine.textContent = `Fact: ${text(fact.fact_id)} · ${text(fact.metric)} = ${text(fact.value)} ${text(fact.unit)} · ${text(fact.status)}`;
        metadata.append(factLine);
        (fact.evidence_ids || []).forEach((evidenceId) => {
          const evidence = evidenceById.get(evidenceId);
          if (!evidence) return;
          const evidenceLine = document.createElement("div");
          evidenceLine.textContent = `Evidence: ${text(evidence.evidence_id)} · ${text(evidence.source)} · ${text(evidence.period)} · ${text(evidence.value)} · lineage ${text(evidence.lineage_id)}`;
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
    if (!result) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "运行个股研究后查看财务事实、异常、风险与 Evidence 闭合。";
      panel.append(empty);
      return;
    }

    const summary = document.createElement("div");
    summary.className = "stock-research-summary";
    summary.append(
      chip(researchStatusLabel(result.pipeline_status), researchStatusClass(result.pipeline_status)),
      chip(`Run ${researchStatusLabel(result.run_status)}`, researchStatusClass(result.run_status)),
      chip(stockRiskStatusLabel(result.risk && result.risk.status), stockRiskStatusClass(result.risk && result.risk.status)),
    );
    const summaryText = document.createElement("p");
    summaryText.textContent = `${text(result.subject)} · ${text(result.period)} · ${text(result.run_id)} · owner ${text(result.owner_id)}`;
    summary.append(summaryText);
    if (result.scenario) {
      const scenarioText = document.createElement("p");
      scenarioText.textContent = `${text(result.scenario.label)} · ${text(result.scenario.description)}`;
      summary.append(scenarioText);
    }
    panel.append(summary);

    const nodeHeading = document.createElement("h3");
    nodeHeading.textContent = "Source nodes";
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
        scope.textContent = node.scope_description;
        card.append(scope);
      }
      (node.issues || []).forEach((issue) => {
        const issueLine = document.createElement("div");
        issueLine.className = "muted";
        issueLine.textContent = `${text(issue.code)}: ${text(issue.safe_message)}`;
        card.append(issueLine);
      });
      nodeGrid.append(card);
    });
    if (nodeGrid.childElementCount) panel.append(nodeGrid);

    const validationsHeading = document.createElement("h3");
    validationsHeading.textContent = "Source validation";
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
      meta.textContent = `${text(validation.independent_lineage_count, "0")} independent lineages · support ${text((validation.supporting_evidence_ids || []).length, "0")} · contradict ${text((validation.contradicting_evidence_ids || []).length, "0")} · unresolved ${text((validation.unresolved_evidence_ids || []).length, "0")}`;
      row.append(meta);
      (validation.issues || []).forEach((issue) => {
        const issueLine = document.createElement("div");
        issueLine.className = "muted";
        issueLine.textContent = `${text(issue.code)}: ${text(issue.safe_message)}`;
        row.append(issueLine);
      });
      validations.append(row);
    });
    if (validations.childElementCount) panel.append(validations);

    if (result.pipeline_status !== "READY") {
      const notice = document.createElement("div");
      notice.className = "notice error";
      notice.textContent = "证据链未闭合；Evidence 仍可审计，但不会升级为 Fact/Finding，也不会给出风险结论。";
      panel.append(notice);
      const issues = document.createElement("ul");
      issues.className = "stock-issues";
      (result.issues || []).forEach((issue) => {
        const item = document.createElement("li");
        item.textContent = `${text(issue.code)}: ${text(issue.safe_message)}`;
        issues.append(item);
      });
      if (issues.childElementCount) panel.append(issues);
      const availableHeading = document.createElement("h3");
      availableHeading.textContent = "Available Evidence · not promoted to Fact";
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
          `Evidence: ${text(evidence.evidence_id)}`,
          `Value: ${text(evidence.value)} ${text(evidence.unit, "")}`,
          `Period: ${text(evidence.period)}`,
          `Lineage: ${text(evidence.lineage_id)}`,
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
    factHeading.textContent = "Verified financial facts";
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
    riskTitle.textContent = "Deterministic risk summary";
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
    anomalyHeading.textContent = "Deterministic anomalies";
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
      meta.textContent = `${text(finding.finding_id)} · ${text(finding.severity)} · ${text(finding.methodology)}`;
      details.append(meta);
      anomalies.append(details);
    });
    if (anomalies.childElementCount) panel.append(anomalies);

    const chainHeading = document.createElement("h3");
    chainHeading.textContent = "Finding → Fact → Evidence";
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
      findingLine.textContent = `Finding: ${text(finding.finding_id)} · ${text(finding.severity)}`;
      metadata.append(findingLine);
      (finding.fact_ids || []).forEach((factId) => {
        const fact = factsById.get(factId);
        if (!fact) return;
        const factLine = document.createElement("div");
        factLine.textContent = `Fact: ${text(fact.fact_id)} · ${text(fact.metric)} = ${text(fact.value)} ${text(fact.unit)} · ${text(fact.status)}`;
        metadata.append(factLine);
        (fact.evidence_ids || []).forEach((evidenceId) => {
          const evidence = evidenceById.get(evidenceId);
          if (!evidence) return;
          const evidenceLine = document.createElement("div");
          evidenceLine.textContent = `Evidence: ${text(evidence.evidence_id)} · ${text(evidence.source)} · ${text(evidence.period)} · ${text(evidence.value)} · lineage ${text(evidence.lineage_id)}`;
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
    if (!result) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "运行 ETF / Fund 研究后查看资产事实、风险与 Evidence 闭合。";
      panel.append(empty);
      return;
    }

    const summary = document.createElement("div");
    summary.className = "fund-research-summary";
    summary.append(
      chip(researchStatusLabel(result.pipeline_status), researchStatusClass(result.pipeline_status)),
      chip(`Run ${researchStatusLabel(result.run_status)}`, researchStatusClass(result.run_status)),
      chip(fundRiskStatusLabel(result.risk && result.risk.status), fundRiskStatusClass(result.risk && result.risk.status)),
    );
    const summaryText = document.createElement("p");
    summaryText.textContent = `${text(result.subject)} · ${text(result.period)} · ${text(result.run_id)} · owner ${text(result.owner_id)}`;
    summary.append(summaryText);
    if (result.scenario) {
      const scenarioText = document.createElement("p");
      scenarioText.textContent = `${text(result.scenario.label)} · ${text(result.scenario.description)}`;
      summary.append(scenarioText);
    }
    panel.append(summary);

    const nodeHeading = document.createElement("h3");
    nodeHeading.textContent = "Source nodes";
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
        scope.textContent = node.scope_description;
        card.append(scope);
      }
      (node.issues || []).forEach((issue) => {
        const issueLine = document.createElement("div");
        issueLine.className = "muted";
        issueLine.textContent = `${text(issue.code)}: ${text(issue.safe_message)}`;
        card.append(issueLine);
      });
      nodeGrid.append(card);
    });
    if (nodeGrid.childElementCount) panel.append(nodeGrid);

    const validationHeading = document.createElement("h3");
    validationHeading.textContent = "Source validation";
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
      meta.textContent = `${text(validation.independent_lineage_count, "0")} independent lineages · support ${text((validation.supporting_evidence_ids || []).length, "0")} · contradict ${text((validation.contradicting_evidence_ids || []).length, "0")} · unresolved ${text((validation.unresolved_evidence_ids || []).length, "0")}`;
      row.append(meta);
      (validation.issues || []).forEach((issue) => {
        const issueLine = document.createElement("div");
        issueLine.className = "muted";
        issueLine.textContent = `${text(issue.code)}: ${text(issue.safe_message)}`;
        row.append(issueLine);
      });
      validations.append(row);
    });
    if (validations.childElementCount) panel.append(validations);

    if (result.pipeline_status !== "READY") {
      const notice = document.createElement("div");
      notice.className = "notice error";
      notice.textContent = "证据链未闭合；Evidence 仍可审计，但不会升级为 Fact/Finding，也不会给出风险结论。";
      panel.append(notice);
      const issues = document.createElement("ul");
      issues.className = "fund-issues";
      (result.issues || []).forEach((issue) => {
        const item = document.createElement("li");
        item.textContent = `${text(issue.code)}: ${text(issue.safe_message)}`;
        issues.append(item);
      });
      if (issues.childElementCount) panel.append(issues);
      const availableHeading = document.createElement("h3");
      availableHeading.textContent = "Available Evidence · not promoted to Fact";
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
          `Evidence: ${text(evidence.evidence_id)}`,
          `Value: ${text(evidence.value)} ${text(evidence.unit, "")}`,
          `Period: ${text(evidence.period)}`,
          `Lineage: ${text(evidence.lineage_id)}`,
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
    factHeading.textContent = "Verified fund facts";
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
    riskTitle.textContent = "Deterministic fund risk summary";
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
    findingHeading.textContent = "Deterministic fund risks";
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
      meta.textContent = `${text(finding.finding_id)} · ${text(finding.severity)} · ${text(finding.methodology)}`;
      details.append(meta);
      findings.append(details);
    });
    if (findings.childElementCount) panel.append(findings);

    const chainHeading = document.createElement("h3");
    chainHeading.textContent = "Finding → Fact → Evidence";
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
      findingLine.textContent = `Finding: ${text(finding.finding_id)} · ${text(finding.severity)}`;
      metadata.append(findingLine);
      (finding.fact_ids || []).forEach((factId) => {
        const fact = factsById.get(factId);
        if (!fact) return;
        const factLine = document.createElement("div");
        factLine.textContent = `Fact: ${text(fact.fact_id)} · ${text(fact.metric)} = ${text(fact.value)} ${text(fact.unit)} · ${text(fact.status)}`;
        metadata.append(factLine);
        (fact.evidence_ids || []).forEach((evidenceId) => {
          const evidence = evidenceById.get(evidenceId);
          if (!evidence) return;
          const evidenceLine = document.createElement("div");
          evidenceLine.textContent = `Evidence: ${text(evidence.evidence_id)} · ${text(evidence.source)} · ${text(evidence.period)} · ${text(evidence.value)} · lineage ${text(evidence.lineage_id)}`;
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
    if (!result) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "运行可转债研究后查看最低资产事实、公式、风险与 Evidence 闭合。";
      panel.append(empty);
      return;
    }

    const summary = document.createElement("div");
    summary.className = "convertible-bond-research-summary";
    summary.append(
      chip(researchStatusLabel(result.pipeline_status), researchStatusClass(result.pipeline_status)),
      chip(`Run ${researchStatusLabel(result.run_status)}`, researchStatusClass(result.run_status)),
      chip(convertibleBondRiskStatusLabel(result.risk && result.risk.status), convertibleBondRiskStatusClass(result.risk && result.risk.status)),
    );
    const summaryText = document.createElement("p");
    summaryText.textContent = `${text(result.subject)} · ${text(result.period)} · ${text(result.run_id)} · owner ${text(result.owner_id)}`;
    summary.append(summaryText);
    if (result.scenario) {
      const scenarioText = document.createElement("p");
      scenarioText.textContent = `${text(result.scenario.label)} · ${text(result.scenario.description)}`;
      summary.append(scenarioText);
    }
    panel.append(summary);

    const nodeHeading = document.createElement("h3");
    nodeHeading.textContent = "Source nodes";
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
        scope.textContent = node.scope_description;
        card.append(scope);
      }
      (node.issues || []).forEach((issue) => {
        const issueLine = document.createElement("div");
        issueLine.className = "muted";
        issueLine.textContent = `${text(issue.code)}: ${text(issue.safe_message)}`;
        card.append(issueLine);
      });
      nodeGrid.append(card);
    });
    if (nodeGrid.childElementCount) panel.append(nodeGrid);

    const validationHeading = document.createElement("h3");
    validationHeading.textContent = "Source validation";
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
      meta.textContent = `${text(validation.independent_lineage_count, "0")} independent lineages · support ${text((validation.supporting_evidence_ids || []).length, "0")} · contradict ${text((validation.contradicting_evidence_ids || []).length, "0")} · unresolved ${text((validation.unresolved_evidence_ids || []).length, "0")}`;
      row.append(meta);
      (validation.issues || []).forEach((issue) => {
        const issueLine = document.createElement("div");
        issueLine.className = "muted";
        issueLine.textContent = `${text(issue.code)}: ${text(issue.safe_message)}`;
        row.append(issueLine);
      });
      validations.append(row);
    });
    if (validations.childElementCount) panel.append(validations);

    if (result.pipeline_status !== "READY") {
      const notice = document.createElement("div");
      notice.className = "notice error";
      notice.textContent = "证据链未闭合；Evidence 仍可审计，但不会升级为 Fact/Finding，也不会给出风险结论。";
      panel.append(notice);
      const issues = document.createElement("ul");
      issues.className = "convertible-bond-issues";
      (result.issues || []).forEach((issue) => {
        const item = document.createElement("li");
        item.textContent = `${text(issue.code)}: ${text(issue.safe_message)}`;
        issues.append(item);
      });
      if (issues.childElementCount) panel.append(issues);
      const availableHeading = document.createElement("h3");
      availableHeading.textContent = "Available Evidence · not promoted to Fact";
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
          `Evidence: ${text(evidence.evidence_id)}`,
          `Value: ${text(evidence.value)} ${text(evidence.unit, "")}`,
          `Period: ${text(evidence.period)}`,
          `Lineage: ${text(evidence.lineage_id)}`,
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
    factHeading.textContent = "Verified convertible-bond facts";
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
      if (fact.metric === "credit_rating_rank") displayValue = `${text(creditLabels[String(fact.value)], "未知评级")} · rank ${displayValue}`;
      if (fact.metric === "liquidity_score") displayValue = `${text(liquidityLabels[String(fact.value)], "未知流动性")} · score ${displayValue}`;
      value.textContent = levelMetric ? displayValue : `${displayValue} ${text(fact.unit, "")}`;
      const period = document.createElement("div");
      period.className = "muted";
      period.textContent = `${text(fact.metric)} · ${text(fact.period)} · ${text(fact.status)}`;
      card.append(title, value, period);
      factGrid.append(card);
    });
    if (factGrid.childElementCount) panel.append(factGrid);

    const formulaHeading = document.createElement("h3");
    formulaHeading.textContent = "Deterministic formulas";
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
    riskTitle.textContent = "Deterministic convertible-bond risk summary";
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
    findingHeading.textContent = "Deterministic convertible-bond risks";
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
      meta.textContent = `${text(finding.finding_id)} · ${text(finding.severity)} · ${text(finding.methodology)}`;
      details.append(meta);
      findings.append(details);
    });
    if (findings.childElementCount) panel.append(findings);

    const chainHeading = document.createElement("h3");
    chainHeading.textContent = "Finding → Fact → Evidence";
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
      findingLine.textContent = `Finding: ${text(finding.finding_id)} · ${text(finding.severity)}`;
      metadata.append(findingLine);
      (finding.fact_ids || []).forEach((factId) => {
        const fact = factsById.get(factId);
        if (!fact) return;
        const factLine = document.createElement("div");
        factLine.textContent = `Fact: ${text(fact.fact_id)} · ${text(fact.metric)} = ${text(fact.value)} ${text(fact.unit)} · ${text(fact.status)}`;
        metadata.append(factLine);
        (fact.evidence_ids || []).forEach((evidenceId) => {
          const evidence = evidenceById.get(evidenceId);
          if (!evidence) return;
          const evidenceLine = document.createElement("div");
          evidenceLine.textContent = `Evidence: ${text(evidence.evidence_id)} · ${text(evidence.source)} · ${text(evidence.period)} · ${text(evidence.value)} · lineage ${text(evidence.lineage_id)}`;
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
    summaryText.textContent = `${text(result.scenario && result.scenario.label)} · ${text(result.summary)} · owner ${text(result.owner_id)}`;
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
        item.textContent = `${text(issue.code)}: ${text(issue.safe_message)}`;
        issues.append(item);
      });
      panel.append(issues);
    }

    if (result.status === "READY") {
      const targetHeading = document.createElement("h3");
      targetHeading.textContent = "Current → deterministic target weights";
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
        addMetadata(grid, "Delta", `${text(target.delta_pct)} pp`);
        addMetadata(grid, "Asset cap", `${text(target.allowed_max_weight_pct)}%`);
        card.append(grid);
        const rationale = document.createElement("div");
        rationale.className = "muted";
        rationale.textContent = text(target.rationale);
        card.append(rationale);
        targets.append(card);
      });
      if (targets.childElementCount) panel.append(targets);

      const constraintHeading = document.createElement("h3");
      constraintHeading.textContent = "Constraint arithmetic";
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
        meta.textContent = `Current ${text(constraint.current_weight_pct)}% → Target ${text(constraint.target_weight_pct)}% · cap ${text(constraint.allowed_max_weight_pct)}% · delta ${text(constraint.delta_pct)} pp · ${text(constraint.rationale)}`;
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
      item.textContent = condition;
      list.append(item);
    });
    invalidation.append(list);
    panel.append(invalidation);
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
      return new Error(payload.message || "API request failed");
    } catch (_) {
      return new Error("API request failed");
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
    if (!requestOwner) {
      state.portfolioContext = null;
      renderPortfolio(state.queryTemplate?.portfolio || null);
      setPortfolioContextStatus("需要 owner", "blocked");
      setError("请输入 owner 标识。");
      return;
    }
    if (!raw) {
      state.portfolioContext = null;
      renderPortfolio(state.queryTemplate?.portfolio || null);
      setPortfolioContextStatus("未提供 JSON", "blocked");
      setError("请粘贴已脱敏的 Portfolio JSON。");
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
      setError("Portfolio JSON 无法解析；输入原文不会写入错误信息。");
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
        `已确认 · ${text(result.position_count)} positions`,
        "pass",
      );
    } catch (error) {
      if (state.ownerId === requestOwner && state.templateSequence === contextSequence) {
        state.portfolioContext = null;
        setPortfolioContextStatus("未确认", "blocked");
        renderPortfolio(state.queryTemplate?.portfolio || null);
      }
      setError(error.message || "Portfolio 校验失败");
    } finally {
      submit.disabled = false;
    }
  }

  async function confirmProfileContext() {
    const requestOwner = byId("owner-id").value.trim();
    const submit = byId("confirm-profile");
    clearAdvisorPlan();
    clearProfileProposal();
    if (!requestOwner) {
      state.profileContext = null;
      renderConfirmedProfile(null);
      setProfileContextStatus("需要 owner", "blocked");
      setError("请输入 owner 标识。");
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
      setError(error.message || "Risk Profile 确认失败");
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
      byId("query-template-meta").textContent = `Fixture ${text(template.fixture_id)} · generated_at ${text(template.generated_at)} · 合成持仓模板`;
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
    byId("research-template-meta").textContent = `Matrix ${text(template.matrix_id)} · ${text(template.node_count)} nodes · ${text((template.scenarios || []).length, "0")} replay scenarios · generated_at ${text(template.generated_at)}`;
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
    byId("stock-research-template-meta").textContent = `Stock ${text(template.subject)} · ${text(template.period)} · ${text(template.metrics?.length, "0")} metrics · ${text((template.scenarios || []).length, "0")} replay scenarios · generated_at ${text(template.generated_at)}`;
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
    byId("fund-research-template-meta").textContent = `Fund ${text(template.subject)} · ${text(template.period)} · ${text(template.metrics?.length, "0")} metrics · ${text((template.scenarios || []).length, "0")} replay scenarios · generated_at ${text(template.generated_at)}`;
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
    byId("convertible-bond-research-template-meta").textContent = `Convertible Bond ${text(template.subject)} · ${text(template.period)} · ${text(template.metrics?.length, "0")} metrics · ${text((template.scenarios || []).length, "0")} replay scenarios · generated_at ${text(template.generated_at)}`;
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
    byId("portfolio-optimization-template-meta").textContent = `Method ${text(template.methodology_version)} · ${text((template.rules || []).length, "0")} rules · ${text((template.scenarios || []).length, "0")} replay scenarios · generated_at ${text(template.generated_at)}`;
    return template;
  }

  async function previewProfileProposal() {
    const requestOwner = byId("owner-id").value.trim();
    const raw = byId("profile-proposal-json").value.trim();
    const submit = byId("preview-profile-proposal");
    if (!requestOwner) {
      clearProfileProposal({ clearInput: false });
      clearAdvisorPlan();
      setProfileProposalStatus("需要 owner", "blocked");
      setError("请输入 owner 标识。");
      return;
    }
    if (!raw) {
      clearProfileProposal({ clearInput: false });
      clearAdvisorPlan();
      setProfileProposalStatus("未提供 JSON", "blocked");
      setError("请粘贴已脱敏的 ProfileExtractionProposal JSON。");
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
      setError("Profile 提案 JSON 无法解析；输入原文不会写入错误信息。");
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
        conflictCount ? `${conflictCount} conflicts` : "无冲突 · 可确认",
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
      setError(error.message || "Profile 提案验证失败");
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
      setError("请先预览结构化 Profile 提案。");
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
      setError(error.message || "Profile 提案确认失败");
    } finally {
      submit.disabled = false;
    }
  }

  async function previewAdvisorPlan() {
    const requestOwner = byId("owner-id").value.trim();
    const submit = byId("preview-advisor-plan");
    if (!requestOwner) {
      clearAdvisorPlan();
      setAdvisorPlanStatus("需要 owner", "blocked");
      setError("请输入 owner 标识。");
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
      setAdvisorPlanStatus(`已生成 · ${text(state.advisorPlan.node_count)} nodes`, "pass");
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
    clearTemplateContext({ clearConfirmed: true });
    setQueryStatus("待运行");
    state.events = [];
    state.selected = null;
    renderEvents();
    renderProfile(null);
    renderEvidence(null);
    byId("detail-status").className = "status-chip";
    byId("detail-status").textContent = "待选择";
    byId("detail-content").replaceChildren();
    const detailEmpty = document.createElement("div");
    detailEmpty.className = "empty-state";
    detailEmpty.textContent = "读取 owner 后查看已保存的决策事件。";
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
    byId("portfolio-optimization-template-meta").textContent = "运行时读取确定性 cap-and-redistribute 方法与合成组合模板。";
    clearPortfolioOptimizationScenarioOptions();
    setPortfolioOptimizationStatus("待运行");
    renderPortfolioOptimization(null);
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
      setError("请输入 owner 标识。");
      return;
    }
    if (!queryId) {
      setError("请输入 query ID。");
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
      setError(error.message || "运行 Advisor 查询失败");
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
      setError("请输入 owner 标识。");
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
      byId("research-template-meta").textContent = `Matrix ${text(template.matrix_id)} · ${text(template.node_count)} nodes · ${text((template.scenarios || []).length, "0")} replay scenarios · generated_at ${text(template.generated_at)}`;
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
      setError("请输入 owner 标识。");
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
      setError("请输入 owner 标识。");
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
      setError(error.message || "运行 ETF / Fund 研究失败");
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
      setError("请输入 owner 标识。");
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
      setError("请输入 owner 标识。");
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
      setError("请先确认 Risk Profile，再生成组合目标结构。");
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

  async function loadEvents() {
    const nextOwnerId = byId("owner-id").value.trim();
    const ownerChanged = nextOwnerId !== state.ownerId;
    state.ownerId = nextOwnerId;
    const requestOwner = state.ownerId;
    const templateSequence = ++state.templateSequence;
    setError("");
    if (ownerChanged || !state.ownerId) {
      resetOwnerScopedViews();
    }
    if (!state.ownerId) {
      setError("请输入 owner 标识。");
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
      renderEvents();
      renderProfile(null);
      renderEvidence(null);
      byId("detail-status").className = "status-chip";
      byId("detail-status").textContent = "待选择";
      byId("detail-content").replaceChildren();
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = state.events.length ? "选择一条回执查看详情。" : "这个 owner 还没有保存的决策事件。";
      byId("detail-content").append(empty);
      try {
        await loadTemplateContext(requestOwner, templateSequence);
      } catch (error) {
        if (state.ownerId === requestOwner && state.templateSequence === templateSequence) {
          setError(error.message || "读取 Portfolio/Risk Profile 模板失败");
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
            setError(error.message || "读取 ETF / Fund 研究场景目录失败");
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
  byId("portfolio-optimization-scenario").addEventListener("change", () => {
    state.portfolioOptimizationRun = null;
    state.portfolioOptimizationSequence += 1;
    renderPortfolioOptimization(null);
    setPortfolioOptimizationStatus("待运行");
  });
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
      if (!state.profileContext) return;
      state.profileContext = null;
      renderConfirmedProfile(null);
      setProfileContextStatus("需重新确认", "review");
    });
  });
  checkHealth();
  loadEvents();
})();
