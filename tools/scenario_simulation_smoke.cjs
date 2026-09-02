/**
 * Browser Smoke Test for Phase 33 Scenario Simulation UI
 */
const { chromium } = require("C:\\Users\\Soyo\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright-core");

;(async () => {
  const baseUrl = process.env.PRISM_UI_BASE_URL || "http://127.0.0.1:8777/";
  const testOwner = `phase33-ui-${Date.now()}`;
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  const externalRequests = [];
  const consoleErrors = [];

  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.hostname !== "127.0.0.1" && url.hostname !== "localhost") {
      externalRequests.push(request.url());
    }
  });

  page.on("console", (message) => {
    if (message.type() === "error") {
      consoleErrors.push(message.text());
    }
  });

  const waitForText = async (selector, fragment, timeout = 15000) => {
    await page.waitForFunction(
      ({ selector, fragment }) => {
        const node = document.querySelector(selector);
        return Boolean(node && (node.textContent || "").includes(fragment));
      },
      { selector, fragment },
      { timeout }
    );
  };

  const waitForOption = async (selector, value, timeout = 15000) => {
    await page.waitForFunction(
      ({ selector, value }) => {
        const option = document.querySelector(`${selector} option[value="${value}"]`);
        return Boolean(option);
      },
      { selector, value },
      { timeout }
    );
  };

  try {
    console.log(`[Smoke] Navigating to ${baseUrl}...`);
    await page.goto(baseUrl, { waitUntil: "networkidle" });
    await waitForText("#health-status", "API 已连接");

    // 1. Navigation verification
    console.log("[Smoke] Verifying navigation links...");
    const simNav = page.locator('.nav-item[href="#scenario-simulation"]');
    if ((await simNav.count()) !== 1) {
      throw new Error("scenario-simulation navigation link not found in sidebar");
    }
    await simNav.click();
    const isActive = await simNav.evaluate((node) => node.classList.contains("active"));
    if (!isActive) {
      throw new Error("scenario-simulation navigation link did not become active on click");
    }

    // 2. Load owner and check scenario catalog
    console.log(`[Smoke] Loading workspace for owner: ${testOwner}...`);
    await page.locator("#owner-id").fill(testOwner);
    await page.locator("#load-events").click();
    await waitForOption("#scenario-simulation-scenario", "BASELINE_READY");
    await waitForOption("#scenario-simulation-scenario", "TIGHTER_TECH_CAP");
    await waitForOption("#scenario-simulation-scenario", "TOP_ASSET_TRIM_10PP");
    await waitForOption("#scenario-simulation-scenario", "LOOKTHROUGH_PARTIAL");
    console.log("[Smoke] Scenario simulation catalog successfully loaded.");

    // 3. Try to run without confirmed profile
    console.log("[Smoke] Testing pre-condition check without confirmed profile...");
    await page.locator("#run-scenario-simulation").click();
    await waitForText("#scenario-simulation-status", "需先确认画像");
    console.log("[Smoke] Pre-condition check verified (requires confirmed profile).");

    // 4. Confirm profile context
    console.log("[Smoke] Confirming risk profile context...");
    await page.locator("#confirm-profile").click();
    await waitForText("#profile-context-status", "已确认");

    // 5. Run BASELINE_READY simulation
    console.log("[Smoke] Running BASELINE_READY scenario simulation...");
    await page.locator("#scenario-simulation-scenario").selectOption("BASELINE_READY");
    await page.locator("#run-scenario-simulation").click();
    await waitForText("#scenario-simulation-status", "READY");

    const contentText = await page.locator("#scenario-simulation-content").textContent();
    if (!contentText.includes("基线 vs 模拟关键指标差分对比")) {
      throw new Error("Metric diffs table not rendered for BASELINE_READY");
    }
    if (!contentText.includes("组合目标权重差分对比")) {
      throw new Error("Target diffs table not rendered for BASELINE_READY");
    }
    if (!contentText.includes("假设覆盖层")) {
      throw new Error("Assumption details not rendered for BASELINE_READY");
    }
    console.log("[Smoke] BASELINE_READY simulation passed successfully.");

    // 6. Run TIGHTER_TECH_CAP simulation
    console.log("[Smoke] Running TIGHTER_TECH_CAP scenario simulation...");
    await page.locator("#scenario-simulation-scenario").selectOption("TIGHTER_TECH_CAP");
    await page.locator("#run-scenario-simulation").click();
    await waitForText("#scenario-simulation-status", "READY");

    const techCapText = await page.locator("#scenario-simulation-content").textContent();
    if (!techCapText.includes("科技行业限额（%）")) {
      throw new Error("Technology cap diff metric not found in TIGHTER_TECH_CAP run");
    }
    console.log("[Smoke] TIGHTER_TECH_CAP simulation passed successfully.");

    // 7. Run LOOKTHROUGH_PARTIAL simulation
    console.log("[Smoke] Running LOOKTHROUGH_PARTIAL scenario simulation...");
    await page.locator("#scenario-simulation-scenario").selectOption("LOOKTHROUGH_PARTIAL");
    await page.locator("#run-scenario-simulation").click();
    await waitForText("#scenario-simulation-status", "待复核");

    const partialText = await page.locator("#scenario-simulation-content").textContent();
    if (!partialText.includes("待复核") && !partialText.includes("PARTIAL")) {
      throw new Error("Review status / issues not rendered for LOOKTHROUGH_PARTIAL");
    }
    console.log("[Smoke] LOOKTHROUGH_PARTIAL simulation passed successfully.");

    // 8. Assert safety constraints
    if (externalRequests.length > 0) {
      throw new Error(`External network requests detected: ${JSON.stringify(externalRequests)}`);
    }
    if (consoleErrors.length > 0) {
      throw new Error(`Console errors detected: ${JSON.stringify(consoleErrors)}`);
    }

    console.log("[Smoke] ALL SCENARIO SIMULATION SMOKE CHECKS PASSED!");
  } finally {
    await browser.close();
  }
})().catch((err) => {
  console.error("[Smoke Error]", err);
  process.exit(1);
});
