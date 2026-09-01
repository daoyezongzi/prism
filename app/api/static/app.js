(() => {
  "use strict";

  const state = {
    ownerId: "",
    events: [],
    selected: null,
    queryTemplate: null,
    templateContext: null,
    templateSequence: 0,
    researchTemplate: null,
    researchRun: null,
    researchSequence: 0,
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

  function researchRoleLabel(role) {
    return role === "ETF_FUND" ? "ETF / Fund" : text(role);
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

  function renderPortfolio(portfolio) {
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
      return;
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
      meta.textContent = `expected ${text(validation.expected_value)} ${text(validation.unit)} · ${text(validation.period)} · ${text(validation.independent_lineage_count)} independent lineages`;
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

  function clearTemplateContext() {
    state.queryTemplate = null;
    state.templateContext = null;
    byId("query-template-meta").textContent = "运行时读取合成持仓模板；不会提交自然语言或订单。";
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
      renderPortfolio(template.portfolio);
      renderProfileContext(template.questionnaire);
      return template;
    } catch (error) {
      if (state.ownerId === ownerId && state.templateSequence === sequence) clearTemplateContext();
      throw error;
    }
  }

  function resetOwnerScopedViews() {
    clearTemplateContext();
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
    setResearchStatus("待运行");
    renderResearchMatrix(null);
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
      const template = await loadTemplateContext(requestOwner, templateSequence);
      if (!template) return;

      const questionnaire = {
        ...template.questionnaire,
        questionnaire_id: `${queryId}-questionnaire`,
        owner_id: state.ownerId,
        answered_at: template.generated_at,
        loss_tolerance_score: Number(byId("loss-tolerance").value),
        investment_horizon: byId("investment-horizon").value,
        liquidity_need: byId("liquidity-need").value,
        experience_level: byId("experience-level").value,
        return_expectation: byId("return-expectation").value,
        max_drawdown_tolerance_pct: byId("max-drawdown").value,
      };
      const payload = {
        schema_version: "advisor-query.v1",
        query_id: queryId,
        fixture_id: template.fixture_id,
        generated_at: template.generated_at,
        questionnaire,
        portfolio: template.portfolio,
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
    if (!state.ownerId) {
      setError("请输入 owner 标识。");
      return;
    }
    setError("");
    submit.disabled = true;
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
      byId("research-template-meta").textContent = `Matrix ${text(template.matrix_id)} · ${text(template.node_count)} nodes · generated_at ${text(template.generated_at)}`;
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
  byId("run-research-matrix").addEventListener("click", runResearchMatrix);
  byId("owner-id").addEventListener("keydown", (event) => {
    if (event.key === "Enter") loadEvents();
  });
  checkHealth();
  loadEvents();
})();
