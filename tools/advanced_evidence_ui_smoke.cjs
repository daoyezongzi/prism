const { chromium } = require("C:\\Users\\Soyo\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright-core");

;(async () => {
const baseUrl = process.env.PRISM_UI_BASE_URL || "http://127.0.0.1:8777/";
const testOwner = `phase32-ui-${Date.now()}`;
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
const externalRequests = [];
const consoleErrors = [];
page.on("request", (request) => {
  const url = new URL(request.url());
  if (url.hostname !== "127.0.0.1" && url.hostname !== "localhost") externalRequests.push(request.url());
});
page.on("console", (message) => {
  if (message.type() === "error") consoleErrors.push(message.text());
});
const waitForText = async (selector, fragment, timeout = 15000) => {
  await page.waitForFunction(({ selector, fragment }) => {
    const node = document.querySelector(selector);
    return Boolean(node && (node.textContent || "").includes(fragment));
  }, { selector, fragment }, { timeout });
};
const waitForOption = async (selector, value, timeout = 15000) => {
  await page.waitForFunction(({ selector, value }) => {
    const option = document.querySelector(`${selector} option[value="${value}"]`);
    return Boolean(option);
  }, { selector, value }, { timeout });
};
const visibleRows = () => page.locator("#advanced-evidence-list .advanced-evidence-row").count();

try {
  await page.goto(baseUrl, { waitUntil: "networkidle" });
  await waitForText("#health-status", "API 已连接");
  await page.locator("#owner-id").fill(testOwner);
  await page.locator("#load-events").click();
  await waitForText("#advanced-evidence-summary", "0 条证据");
  await waitForOption("#research-scenario", "SOURCE_PARTIAL");

  const profileNav = page.locator('.nav-item[href="#profile"]');
  await profileNav.click();
  if (!(await profileNav.getAttribute("aria-current")) || !(await profileNav.evaluate((node) => node.classList.contains("active")))) {
    throw new Error("profile navigation did not become selected");
  }
  const overviewNav = page.locator('.nav-item[href="#overview"]');
  if (await overviewNav.getAttribute("aria-current")) throw new Error("overview remained selected after profile navigation");
  await page.goto(`${baseUrl}#evidence`, { waitUntil: "networkidle" });
  await waitForText("#evidence-title", "证据链浏览器");
  const evidenceNav = page.locator('.nav-item[href="#evidence"]');
  if (!(await evidenceNav.getAttribute("aria-current")) || !(await evidenceNav.evaluate((node) => node.classList.contains("active")))) {
    throw new Error("hash navigation did not select evidence");
  }
  const initialBodyText = await page.locator("body").textContent();
  for (const phrase of ["Decision workspace", "Evidence chain explorer", "Research Tracks", "Risk Profile"]) {
    if (initialBodyText.includes(phrase)) throw new Error(`English core UI label remains visible: ${phrase}`);
  }
  await page.locator("#owner-id").fill(testOwner);
  await page.locator("#load-events").click();
  await waitForText("#advanced-evidence-summary", "0 条证据");
  await waitForOption("#research-scenario", "SOURCE_PARTIAL");
  await page.locator('.nav-item[href="#overview"]').click();

  await page.locator("#run-research-matrix").click();
  await waitForText("#research-status", "READY");
  if ((await visibleRows()) < 1) throw new Error("research matrix did not populate advanced evidence rows");
  const firstRow = page.locator("#advanced-evidence-list .advanced-evidence-row").first();
  const firstId = (await firstRow.locator("strong").textContent()).trim();
  await firstRow.click();
  const detailText = await page.locator("#advanced-evidence-detail").textContent();
  for (const token of ["数据提供方", "来源", "来源链", "获取时间", "审计路径"]) {
    if (!detailText.includes(token)) throw new Error(`detail missing ${token}`);
  }
  await page.locator("#advanced-evidence-search").fill(firstId);
  if ((await visibleRows()) !== 1) throw new Error("Evidence ID search did not narrow to one row");
  await page.locator("#clear-advanced-evidence-filters").click();
  await page.locator("#advanced-evidence-quality").selectOption("VERIFIED");
  if ((await visibleRows()) < 1) throw new Error("VERIFIED filter hid all baseline evidence");

  let staleOnce = true;
  await page.route("**/api/v1/advisor/research-runs", async (route) => {
    const response = await route.fetch();
    const payload = await response.json();
    if (staleOnce) {
      staleOnce = false;
      (payload.nodes || []).forEach((node) => {
        node.provider_serving_mode = "CACHE_STALE_FALLBACK";
        node.provider_cache_age_ms = 123456;
      });
      const evidence = payload.trace && payload.trace.evidence && payload.trace.evidence[0];
      if (evidence) {
        evidence.quality_status = "STALE";
        evidence.quality_note = "fixture stale replay";
      }
      await route.fulfill({ response, body: JSON.stringify(payload) });
      return;
    }
    await route.continue();
  });
  await page.locator("#clear-advanced-evidence-filters").click();
  await page.locator("#research-scenario").selectOption("SOURCE_PARTIAL");
  await page.locator("#run-research-matrix").click();
  await page.waitForFunction(() => {
    const value = document.querySelector("#research-status")?.textContent || "";
    return value.includes("待复核") || value.includes("PARTIAL");
  });
  const staleText = await page.locator("#advanced-evidence-list").textContent();
  if (!staleText.includes("STALE") || !staleText.includes("CACHE_STALE_FALLBACK")) {
    throw new Error("stale/fallback provenance was not visible");
  }
  const staleFirstRowText = await page.locator("#advanced-evidence-list .advanced-evidence-row").first().textContent();
  if (!staleFirstRowText.includes("研究矩阵")) throw new Error(`stale first row was not matrix evidence: ${staleFirstRowText}`);
  await page.locator("#advanced-evidence-list .advanced-evidence-row").first().click();
  const staleDetail = await page.locator("#advanced-evidence-detail").textContent();
  if (!staleDetail.includes("不能作为已验证事实（VERIFIED）") || !staleDetail.includes("2.1 分钟")) {
    throw new Error(`stale review notice or cache age was not visible: ${staleDetail}`);
  }

  let fallbackOnce = true;
  await page.route("**/api/v1/advisor/stock-research-runs", async (route) => {
    const response = await route.fetch();
    const payload = await response.json();
    if (fallbackOnce) {
      fallbackOnce = false;
      (payload.nodes || []).forEach((node) => {
        node.provider_serving_mode = "FALLBACK_PROVIDER";
        delete node.provider_cache_age_ms;
      });
      await route.fulfill({ response, body: JSON.stringify(payload) });
      return;
    }
    await route.continue();
  });
  await page.locator("#stock-research-scenario").selectOption("BASELINE_READY");
  await page.locator("#run-stock-research").click();
  await waitForText("#stock-research-status", "READY");
  const fallbackText = await page.locator("#advanced-evidence-list").textContent();
  if (!fallbackText.includes("FALLBACK_PROVIDER")) throw new Error("fallback provider mode was not visible");

  await page.locator("#stock-research-scenario").selectOption("SOURCE_PARTIAL");
  await page.locator("#run-stock-research").click();
  await waitForText("#stock-research-status", "待复核");
  const partialStockText = await page.locator("#stock-research-content").textContent();
  if (!partialStockText.includes("数据提供方返回了已声明缺失字段的部分结果")) {
    throw new Error("partial provider issue was not localized");
  }
  if (partialStockText.includes("provider returned a partial payload")) {
    throw new Error("raw English provider issue remained visible");
  }

  await page.locator("#run-fund-research").click();
  await waitForText("#fund-research-status", "READY");
  if (!(await page.locator("#advanced-evidence-list").textContent()).includes("ETF / 基金研究")) {
    throw new Error("fund research evidence was not aggregated");
  }
  await page.locator("#run-convertible-bond-research").click();
  await waitForText("#convertible-bond-research-status", "READY");
  if (!(await page.locator("#advanced-evidence-list").textContent()).includes("可转债研究")) {
    throw new Error("convertible-bond research evidence was not aggregated");
  }
  await page.locator("#run-advisor-query").click();
  await waitForText("#query-status", "PASS");
  await waitForText("#advanced-evidence-list", "投顾回执");
  if (!(await page.locator("#advanced-evidence-list").textContent()).includes("投顾回执")) {
    throw new Error("advisor receipt evidence was not aggregated");
  }

  const template = await page.evaluate(async () => {
    const response = await fetch("/api/v1/advisor/query-template", { headers: { "X-Owner-ID": document.querySelector("#owner-id").value } });
    return response.json();
  });
  await page.locator("#portfolio-json").fill(JSON.stringify(template.portfolio));
  await page.locator("#confirm-portfolio").click();
  await waitForText("#portfolio-context-status", "已确认");
  await page.locator("#confirm-profile").click();
  await waitForText("#profile-context-status", "已确认");
  await page.locator("#save-context-memory").click();
  await page.waitForSelector("#context-memory-content .context-memory-card");
  await page.locator("#context-memory-content .context-memory-card button").click();
  await waitForText("#detail-content", "上下文已恢复");
  await waitForText("#advanced-evidence-summary", "0 条证据");

  await page.locator("#owner-id").fill("phase32-other-owner");
  await page.locator("#load-events").click();
  await waitForText("#advanced-evidence-summary", "0 条证据");
  if ((await visibleRows()) !== 0) throw new Error("owner change retained evidence rows");
  await page.setViewportSize({ width: 480, height: 1000 });
  await page.locator("#advanced-evidence-search").focus();
  if (!(await page.locator("#advanced-evidence-search").evaluate((node) => node === document.activeElement))) {
    throw new Error("search control is not keyboard focusable");
  }
  if (externalRequests.length || consoleErrors.length) {
    throw new Error(`external requests=${externalRequests.length}, console errors=${consoleErrors.length}`);
  }
  console.log(JSON.stringify({
    baseline_evidence_id: firstId,
    baseline_rows: await visibleRows(),
    external_requests: externalRequests,
    console_errors: consoleErrors,
    owner_reset: true,
    narrow_keyboard_focus: true,
  }));
} finally {
  await browser.close();
}
})().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exitCode = 1;
});
