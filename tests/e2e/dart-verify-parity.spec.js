import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { expect, test } from "@playwright/test";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const appIndexPath = path.join(repoRoot, "dist/dart-verify/index.html");
const fixturePath = path.join(
  repoRoot,
  "out/corpus/run_2026-06-06-inveni-one/raw/inveni_2024_20250310000926.html",
);
const rootPyodidePath = path.join(repoRoot, "vendor/pyodide/pyodide.js");
const assembledPyodidePath = path.join(
  repoRoot,
  "dist/dart-verify/vendor/pyodide/pyodide.js",
);

test.skip(
  !fs.existsSync(rootPyodidePath),
  "PyOdide runtime assets are missing at vendor/pyodide/pyodide.js; run scripts/vendor-pyodide.sh before parity E2E.",
);
test.skip(
  !fs.existsSync(assembledPyodidePath),
  "Assembled app is missing dist/dart-verify/vendor/pyodide/pyodide.js; rebuild dist/dart-verify after vendoring PyOdide.",
);
test.skip(
  !fs.existsSync(appIndexPath),
  "Assembled app is missing at dist/dart-verify/index.html; run the build-verify-app command first.",
);
test.skip(
  !fs.existsSync(fixturePath),
  "Fixture HTML is missing at out/corpus/run_2026-06-06-inveni-one/raw/inveni_2024_20250310000926.html.",
);

test("browser output matches Python verify_html_report golden", async ({ page }, testInfo) => {
  test.setTimeout(180_000);

  const goldenPath = testInfo.outputPath("python-golden.html");
  fs.mkdirSync(path.dirname(goldenPath), { recursive: true });
  writePythonGolden(fixturePath, goldenPath);
  const expectedHtml = fs.readFileSync(goldenPath, "utf8");

  await page.goto(pathToFileURL(appIndexPath).href);
  await page.setInputFiles("#file-input", {
    name: "INVENI.html",
    mimeType: "text/html",
    buffer: fs.readFileSync(fixturePath),
  });

  await page.waitForFunction(
    () => {
      const output = window.__dartVerifyLastHtml || document.querySelector("#result")?.innerHTML || "";
      return output.trim() && !output.includes("result-placeholder");
    },
    null,
    { timeout: 120_000 },
  );

  const browserHtml = await page.evaluate(
    () => window.__dartVerifyLastHtml || document.querySelector("#result")?.innerHTML || "",
  );

  expect(normalizeHtml(browserHtml)).toBe(normalizeHtml(expectedHtml));
});

function writePythonGolden(inputPath, outputPath) {
  const pythonCode = [
    "import pathlib",
    "try:",
    "    from dart_footing_reconciler.verify import verify_html_report",
    "except ModuleNotFoundError:",
    "    from dart_footing_reconciler.verify_app import verify_html_report",
    `out=verify_html_report(pathlib.Path(${JSON.stringify(inputPath)}).read_text(), company='INVENI')`,
    `pathlib.Path(${JSON.stringify(outputPath)}).write_text(out)`,
  ].join("\n");
  const env = { ...process.env };
  delete env.VIRTUAL_ENV;
  execFileSync("uv", ["run", "python", "-c", pythonCode], {
    cwd: repoRoot,
    env,
    stdio: "pipe",
  });
}

function normalizeHtml(html) {
  return html.replace(/\r\n/g, "\n").trim();
}
