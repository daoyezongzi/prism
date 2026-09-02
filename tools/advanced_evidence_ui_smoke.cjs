const { chromium } = require("C:\\Users\\Soyo\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright-core");

;(async () => {
const baseUrl = process.env.PRISM_UI_BASE_URL || "http://127.0.0.1:8777/";
const testOwner = `phase31-ui-${Date.now()}`;
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
const visibleRows = () => page.locator("#advanced-evidence-list .advanced-evidence-row").count();

try {
  await page.goto(baseUrl, { waitUntil: "networkidle" });
  await waitForText("#health-status", "API 已连接");
  await page.locator("#owner-id").fill(testOwner);
  await page.locator("#load-events").click();
  await waitForText("#advanced-evidence-summary", "0 Evidence");

  await page.locator("#run-research-matrix").click();
  await waitForText("#research-status", "READY");
  if ((await visibleRows()) < 1) throw new Error("research matrix did not populate advanced evidence rows");
  const firstRow = page.locator("#advanced-evidence-list .advanced-evidence-row").first();
  const firstId = (await firstRow.locator("strong").textContent()).trim();
  await firstRow.click();
  const detailText = await page.locator("#advanced-evidence-detail").textContent();
  for (const token of ["Provider", "Source", "Lineage", "Retrieved at", "审计路径"]) {
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
  if (!staleFirstRowText.includes("Research Matrix")) throw new Error(`stale first row was not matrix evidence: ${staleFirstRowText}`);
  await page.locator("#advanced-evidence-list .advanced-evidence-row").first().click();
  const staleDetail = await page.locator("#advanced-evidence-detail").textContent();
  if (!staleDetail.includes("不能作为 VERIFIED Fact") || !staleDetail.includes("2.1 min")) {
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

  await page.locator("#run-fund-research").click();
  await waitForText("#fund-research-status", "READY");
  if (!(await page.locator("#advanced-evidence-list").textContent()).includes("ETF / Fund Research")) {
    throw new Error("fund research evidence was not aggregated");
  }
  await page.locator("#run-convertible-bond-research").click();
  await waitForText("#convertible-bond-research-status", "READY");
  if (!(await page.locator("#advanced-evidence-list").textContent()).includes("Convertible Bond Research")) {
    throw new Error("convertible-bond research evidence was not aggregated");
  }
  await page.locator("#run-advisor-query").click();
  await waitForText("#query-status", "PASS");
  await waitForText("#advanced-evidence-list", "Advisor receipt");
  if (!(await page.locator("#advanced-evidence-list").textContent()).includes("Advisor receipt")) {
    throw new Error("advisor receipt evidence was not aggregated");
  }

  await page.locator("#owner-id").fill("phase31-other-owner");
  await page.locator("#load-events").click();
  await waitForText("#advanced-evidence-summary", "0 Evidence");
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
