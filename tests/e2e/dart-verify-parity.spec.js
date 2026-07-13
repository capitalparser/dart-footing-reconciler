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

// PyOdide cannot run from file:// (Chromium blocks ES modules + fetch); the app is
// served over a local loopback HTTP server, matching the real delivery model
// (ADR-0005). These skips keep the suite green when assets aren't vendored.
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

let server;
let baseUrl;

test.beforeAll(async () => {
  const port = await freePort();
  server = spawn(
    "python3",
    ["-m", "http.server", String(port), "--bind", "127.0.0.1", "--directory", appDir],
    { stdio: "ignore" },
  );
  baseUrl = `http://127.0.0.1:${port}`;
  await waitForServer(baseUrl + "/index.html");
});

test.afterAll(() => {
  if (server) server.kill("SIGTERM");
});

test("browser output matches Python verify_html_report golden", async ({ page }, testInfo) => {
  test.setTimeout(180_000);

  const goldenPath = testInfo.outputPath("python-golden.html");
  fs.mkdirSync(path.dirname(goldenPath), { recursive: true });
  writePythonGolden(fixturePath, goldenPath);
  const expectedHtml = fs.readFileSync(goldenPath, "utf8");

  await page.goto(baseUrl + "/index.html");
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
  execFileSync("uv", ["run", "python", "-c", pythonCode], { cwd: repoRoot, env, stdio: "pipe" });
}

function normalizeHtml(html) {
  return html.replace(/\r\n/g, "\n").trim();
}
