import { execFileSync, spawn } from "node:child_process";
import fs from "node:fs";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const appDir = path.join(repoRoot, "dist/dart-verify");
const appIndexPath = path.join(appDir, "index.html");
const fixturePath = path.join(
  repoRoot,
  "out/corpus/run_2026-06-06-inveni-one/raw/inveni_2024_20250310000926.html",
);
const assembledPyodidePath = path.join(appDir, "vendor/pyodide/pyodide.js");

let server;
let baseUrl;

test.beforeAll(async () => {
  const port = await freePort();
  server = spawn(
    "python3",
    ["-m", "http.server", String(port), "--bind", "127.0.0.1", "--directory", repoRoot],
    { stdio: "ignore" },
  );
  baseUrl = `http://127.0.0.1:${port}`;
  await waitForServer(baseUrl + "/static/dart-verify/index.html");
});

test.afterAll(() => {
  if (server) server.kill("SIGTERM");
});

test("browser output matches Python verify_html_report golden", async ({ page }, testInfo) => {
  test.skip(
    !fs.existsSync(assembledPyodidePath),
    "Assembled app missing dist/dart-verify/vendor/pyodide/pyodide.js; run scripts/vendor-pyodide.sh then build-verify-app.",
  );
  test.skip(
    !fs.existsSync(appIndexPath),
    "Assembled app missing dist/dart-verify/index.html; run build-verify-app.",
  );
  test.skip(
    !fs.existsSync(fixturePath),
    "Fixture HTML missing at out/corpus/run_2026-06-06-inveni-one/raw/inveni_2024_20250310000926.html.",
  );
  test.setTimeout(180_000);

  const goldenPath = testInfo.outputPath("python-golden.html");
  fs.mkdirSync(path.dirname(goldenPath), { recursive: true });
  writePythonGolden(fixturePath, goldenPath);
  const expectedHtml = fs.readFileSync(goldenPath, "utf8");

  await page.goto(baseUrl + "/dist/dart-verify/index.html");
  await page.setInputFiles("#file-input", {
    name: "INVENI.html",
    mimeType: "text/html",
    buffer: fs.readFileSync(fixturePath),
  });

  await page.waitForFunction(
    () => {
      const out = window.__dartVerifyLastHtml || document.querySelector("#result")?.innerHTML || "";
      return out.trim() && !out.includes("result-placeholder");
    },
    null,
    { timeout: 150_000 },
  );

  const browserHtml = await page.evaluate(
    () => window.__dartVerifyLastHtml || document.querySelector("#result")?.innerHTML || "",
  );

  expect(normalizeHtml(browserHtml)).toBe(normalizeHtml(expectedHtml));
});

test("mounted cockpit runtime responds to real clicks without Pyodide", async ({ page }) => {
  const reportHtml = buildInteractivePythonReport();
  await page.addInitScript(() => {
    globalThis.__DART_VERIFY_DISABLE_AUTO_INIT__ = true;
  });
  await page.goto(baseUrl + "/static/dart-verify/index.html");
  await page.evaluate(async (html) => {
    const { mountReportHtml } = await import("/static/dart-verify/app.js");
    mountReportHtml(document.querySelector("#result"), html, document);
  }, reportHtml);

  const frame = page.locator("iframe.report-frame");
  await expect(frame).toHaveAttribute("sandbox", "allow-scripts");
  const report = page.frameLocator("iframe.report-frame");
  await expect(report.locator("#panel-summary")).toBeVisible();

  await report.locator('.nav-item[data-target="panel-attention"]').click();
  await expect(report.locator("#panel-attention")).toBeVisible();

  await report.locator(".attn-row").first().click();
  await expect(report.locator("body")).toHaveClass(/review-open/);
  await expect(report.locator("#review-rail-body .dd-title").first()).toBeVisible();
});

function freePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.unref();
    srv.on("error", reject);
    srv.listen(0, "127.0.0.1", () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
  });
}

async function waitForServer(url, attempts = 50) {
  for (let i = 0; i < attempts; i++) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
    } catch {
      // not up yet
    }
    await new Promise((r) => setTimeout(r, 200));
  }
  throw new Error(`local server did not start at ${url}`);
}

function writePythonGolden(inputPath, outputPath) {
  const pythonCode = [
    "import pathlib",
    "from dart_footing_reconciler.verify_app import verify_html_report",
    `out=verify_html_report(pathlib.Path(${JSON.stringify(inputPath)}).read_text(), company='INVENI')`,
    `pathlib.Path(${JSON.stringify(outputPath)}).write_text(out)`,
  ].join("\n");
  const env = { ...process.env };
  delete env.VIRTUAL_ENV;
  env.UV_CACHE_DIR = "/tmp/ruffe-uv-cache";
  execFileSync("uv", ["run", "python", "-c", pythonCode], { cwd: repoRoot, env, stdio: "pipe" });
}

function buildInteractivePythonReport() {
  const pythonCode = [
    "from dart_footing_reconciler.checks import CheckEvidence, CheckResult, UNEXPLAINED_GAP",
    "from dart_footing_reconciler.document import FullReport, ReportBlock, ReportSection, ReportTable, SourceLocation",
    "from dart_footing_reconciler.report_html import _ReportMeta, _build_html",
    "table=ReportTable(0, [['구분','당기'],['유형자산','100']], '재무상태표', SourceLocation('statement:bs',0,0))",
    "section=ReportSection('statement:bs','재무상태표','statement','',[ReportBlock('table','',table,table.location)])",
    "report=FullReport('e2e.html','E2E Co',[section],[])",
    "check=CheckResult('e2e-gap','test',UNEXPLAINED_GAP,'report','','실클릭 검증',100,90,-10,1,'차이 확인',[CheckEvidence('유형자산',90,'statement:bs/table:0/row:1/col:1')])",
    "print(_build_html(report,[check],_ReportMeta('E2E Co','')),end='')",
  ].join("\n");
  const env = { ...process.env, UV_CACHE_DIR: "/tmp/ruffe-uv-cache" };
  delete env.VIRTUAL_ENV;
  return execFileSync("uv", ["run", "python", "-c", pythonCode], {
    cwd: repoRoot,
    env,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
}

function normalizeHtml(html) {
  return html.replace(/\r\n/g, "\n").trim();
}
