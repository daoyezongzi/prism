/*
 * Prism 开发者模式门控 (Developer Mode Gate)
 * ---------------------------------------------------------------------------
 * 普通用户（股民）看到的是干净、任务导向的界面；开发/评审所需的底层工具
 * （评测看板、数据空间、原始 JSON、四轨道矩阵、证据审计、示例画像、模型密钥）
 * 全部保留在 DOM 中，但默认用 CSS `body:not(.dev-mode) .dev-only` 隐藏。
 *
 * 进入方式（三选一，供演示/答辩使用）：
 *   1. 地址栏加 ?dev=1
 *   2. 连续点击左上角 Logo 5 次
 *   3. 快捷键 Alt+Shift+D
 * 进入后左下角出现「开发者模式 · 退出」芯片，点击即可退出。
 *
 * 本文件不依赖 app.js，独立运行，删除任何业务元素都不会影响它。
 */
(() => {
  "use strict";

  const STORAGE_KEY = "prism_dev_mode";

  function isEnabled() {
    return document.body.classList.contains("dev-mode");
  }

  function createBadge() {
    if (document.getElementById("dev-mode-badge")) return;
    const badge = document.createElement("button");
    badge.id = "dev-mode-badge";
    badge.className = "dev-mode-badge";
    badge.type = "button";
    badge.title = "当前处于开发者模式，点击退出并回到普通用户视图";

    const icon = document.createElement("span");
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = "🛠";

    const label = document.createElement("span");
    label.textContent = "开发者模式";

    const exit = document.createElement("span");
    exit.className = "dev-mode-badge-exit";
    exit.textContent = "退出";

    badge.append(icon, label, exit);
    badge.addEventListener("click", () => setDevMode(false));
    document.body.appendChild(badge);
  }

  function removeBadge() {
    const badge = document.getElementById("dev-mode-badge");
    if (badge) badge.remove();
  }

  function setDevMode(enabled, { persist = true } = {}) {
    document.body.classList.toggle("dev-mode", enabled);
    if (enabled) createBadge();
    else removeBadge();
    if (persist) {
      try {
        if (enabled) localStorage.setItem(STORAGE_KEY, "1");
        else localStorage.removeItem(STORAGE_KEY);
      } catch (_) {
        /* localStorage 不可用时静默降级 */
      }
    }
  }

  function initFromEnvironment() {
    // 显式 URL 参数优先，并作为持久选择记录下来。
    try {
      const params = new URLSearchParams(window.location.search);
      if (params.has("dev")) {
        const raw = params.get("dev");
        const enable = raw === "" || raw === "1" || raw === "true";
        setDevMode(enable);
        return;
      }
    } catch (_) {
      /* URL 解析失败时回退到 localStorage */
    }
    let stored = false;
    try {
      stored = localStorage.getItem(STORAGE_KEY) === "1";
    } catch (_) {
      stored = false;
    }
    setDevMode(stored, { persist: false });
  }

  function bindTriggers() {
    // 连点 Logo 5 次进入/退出。
    const brand = document.querySelector(".brand");
    if (brand) {
      let clicks = 0;
      let timer = null;
      brand.addEventListener("click", () => {
        clicks += 1;
        if (timer) clearTimeout(timer);
        timer = setTimeout(() => {
          clicks = 0;
        }, 1200);
        if (clicks >= 5) {
          clicks = 0;
          setDevMode(!isEnabled());
        }
      });
    }
    // 快捷键 Alt+Shift+D。
    document.addEventListener("keydown", (event) => {
      if (event.altKey && event.shiftKey && (event.key === "D" || event.key === "d")) {
        event.preventDefault();
        setDevMode(!isEnabled());
      }
    });
  }

  function start() {
    initFromEnvironment();
    bindTriggers();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
