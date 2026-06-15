import { beforeEach, describe, expect, test, vi } from "vitest";

describe("dart-verify browser shell", () => {
  beforeEach(() => {
    vi.resetModules();
    globalThis.__DART_VERIFY_DISABLE_AUTO_INIT__ = true;
    document.body.innerHTML = `
      <div id="drop-zone"></div>
      <input id="file-input" type="file">
      <div id="status"></div>
      <div id="result"></div>
      <pre id="details"></pre>
    `;
  });

  test("rejects PDF files before engine execution with a Korean message", async () => {
    const { initDartVerifyApp } = await import("../../static/dart-verify/app.js");
    const controller = initDartVerifyApp({
      autoBoot: false,
      loadPyodideFn: vi.fn(),
    });

    await expect(
      controller.verifyFile(new File([new Uint8Array([0x25, 0x50, 0x44, 0x46])], "report.pdf")),
    ).rejects.toThrow("HTML/DSD");
  });

  test("loads PyOdide packages, calls verify_html_report, and injects the returned HTML", async () => {
    const install = vi.fn();
    const pyodide = {
      FS: { writeFile: vi.fn() },
      globals: { set: vi.fn(), delete: vi.fn() },
      loadPackage: vi.fn(),
      pyimport: vi.fn(() => ({ install })),
      runPython: vi.fn(() => '<div class="verdict-banner">OK</div>'),
    };
    const loadPyodideFn = vi.fn(async () => pyodide);

    const { initDartVerifyApp, PYODIDE_PACKAGES } = await import("../../static/dart-verify/app.js");
    const controller = initDartVerifyApp({
      autoBoot: false,
      loadPyodideFn,
      wheelPath: "./dart_footing_reconciler-0.1.0-py3-none-any.whl",
    });

    await controller.bootEngine();
    await controller.verifyFile(new File(["<html></html>"], "report.html"));

    expect(loadPyodideFn).toHaveBeenCalledWith({ indexURL: "vendor/pyodide/" });
    expect(pyodide.loadPackage).toHaveBeenCalledWith(PYODIDE_PACKAGES);
    expect(pyodide.pyimport).toHaveBeenCalledWith("micropip");
    expect(install).toHaveBeenCalledWith(
      "./dart_footing_reconciler-0.1.0-py3-none-any.whl",
      false,
      false,
    );
    expect(pyodide.FS.writeFile).toHaveBeenCalledWith(
      "/tmp/dart_verify_current.bin",
      expect.any(Uint8Array),
    );
    expect(pyodide.runPython.mock.calls[0][0]).toContain("verify_html_report");
    expect(pyodide.runPython.mock.calls[0][0]).toContain("_decode_text");
    expect(document.getElementById("result").innerHTML).toBe('<div class="verdict-banner">OK</div>');
    expect(globalThis.__dartVerifyLastHtml).toBe('<div class="verdict-banner">OK</div>');
  });
});
