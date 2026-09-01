(() => {
  "use strict";

  const state = { ownerId: "", events: [], selected: null, queryTemplate: null };
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

  async function loadEvent(eventId) {
    setError("");
    try {
      const response = await fetch(`/api/v1/decision-events/${encodeURIComponent(eventId)}`, {
        headers: { "X-Owner-ID": state.ownerId },
      });
      if (!response.ok) throw await apiError(response);
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

  async function runAdvisorQuery(event) {
    event.preventDefault();
    state.ownerId = byId("owner-id").value.trim();
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
      const templateResponse = await fetch("/api/v1/advisor/query-template", {
        headers: { "X-Owner-ID": state.ownerId },
      });
      if (!templateResponse.ok) throw await apiError(templateResponse);
      const template = await templateResponse.json();
      state.queryTemplate = template;
      byId("query-template-meta").textContent = `Fixture ${text(template.fixture_id)} · generated_at ${text(template.generated_at)} · 合成持仓模板`;

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

  async function loadEvents() {
    const nextOwnerId = byId("owner-id").value.trim();
    const ownerChanged = nextOwnerId !== state.ownerId;
    state.ownerId = nextOwnerId;
    setError("");
    if (!state.ownerId) {
      setError("请输入 owner 标识。");
      return;
    }
    if (ownerChanged) {
      state.queryTemplate = null;
      setQueryStatus("待运行");
      byId("query-template-meta").textContent = "运行时读取合成持仓模板；不会提交自然语言或订单。";
    }
    try {
      const response = await fetch("/api/v1/decision-events", {
        headers: { "X-Owner-ID": state.ownerId },
      });
      if (!response.ok) throw await apiError(response);
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
  byId("owner-id").addEventListener("keydown", (event) => {
    if (event.key === "Enter") loadEvents();
  });
  checkHealth();
  loadEvents();
})();
