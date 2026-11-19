// Render svg/*.svg to png/*.png at 2x with a transparent background.
// Usage: node docs/submission/s3-figures/render_png.mjs [browserPath]
import { readdir, readFile, mkdir, mkdtemp } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer-core";

const here = path.dirname(fileURLToPath(import.meta.url));
const svgDir = path.join(here, "svg");
const pngDir = path.join(here, "png");
const executablePath =
  process.argv[2] || "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";

await mkdir(pngDir, { recursive: true });
const browser = await puppeteer.launch({
  executablePath,
  headless: true,
  userDataDir: await mkdtemp(path.join(os.tmpdir(), "s3-figures-")),
  args: ["--no-first-run", "--disable-extensions"],
});
try {
  const page = await browser.newPage();
  for (const name of (await readdir(svgDir)).filter((n) => n.endsWith(".svg"))) {
    const svg = await readFile(path.join(svgDir, name), "utf8");
    const [, w, h] = svg.match(/width="(\d+)" height="(\d+)"/);
    await page.setViewport({ width: +w, height: +h, deviceScaleFactor: 2 });
    await page.setContent(
      `<html><body style="margin:0;background:transparent">${svg}</body></html>`
    );
    const el = await page.$("svg");
    await el.screenshot({
      path: path.join(pngDir, name.replace(/\.svg$/, ".png")),
      omitBackground: true,
    });
    console.log("rendered", name);
  }
} finally {
  await browser.close();
}
