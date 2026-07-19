import { beforeEach, describe, expect, test, vi } from "vitest";

function unavailableFetch() {
  return vi.fn(async () => {
    throw new TypeError("Failed to fetch");
  });
}

function representativeWorkbenchDocument(initialScope = "consolidated") {
  return `<!doctype html>
    <html lang="ko">
      <head>
        <style id="workbench-style">.source-panel[hidden] { display: none; }</style>
      </head>
      <body data-report-profile="audit-workbench" data-active-report-scope="${initialScope}">
        <div data-report-profile="audit-workbench">
          <button id="scope-consolidated" type="button" data-report-scope="consolidated">연결</button>
          <button id="scope-separate" type="button" data-report-scope="separate">별도</button>
          <nav>
            <button id="nav-consolidated" class="source-nav-item" type="button"
                    data-source-panel="panel-consolidated" data-scope-view="consolidated">재무상태표 (연결)</button>
            <button id="nav-separate" class="source-nav-item" type="button"
                    data-source-panel="panel-separate" data-scope-view="separate">재무상태표 (별도)</button>
          </nav>
          <section id="panel-consolidated" class="source-panel" data-scope-view="consolidated">
            <button id="drawer-trigger" type="button" data-open-drawer="0">검증 결과</button>
          </section>
          <section id="panel-separate" class="source-panel" data-scope-view="separate" hidden>별도 원문</section>
          <aside>
            <div data-drawer-empty>결과를 선택하세요</div>
            <article id="drawer-item" data-drawer-item="0" data-scope-view="consolidated" hidden>연결 검증</article>
          </aside>
        </div>
        <script>
          document.body.dataset.workbenchScriptExecutions = String(
            Number(document.body.dataset.workbenchScriptExecutions || 0) + 1,
          );
          (function () {
            function activeReportScope() {
              return document.body.getAttribute("data-active-report-scope") || "all";
            }
            function activatePanel(panelId) {
              document.querySelectorAll(".source-panel[id]").forEach(function (panel) {
                panel.hidden = panel.id !== panelId;
              });
              document.querySelectorAll("[data-source-panel]").forEach(function (button) {
                button.classList.toggle("active", button.getAttribute("data-source-panel") === panelId);
              });
            }
            function closeDrawer() {
              document.querySelectorAll("[data-drawer-item]").forEach(function (item) {
                item.hidden = true;
              });
            }
            function activateReportScope(scope) {
              document.body.setAttribute("data-active-report-scope", scope);
              document.querySelectorAll("[data-report-scope]").forEach(function (button) {
                button.setAttribute(
                  "aria-pressed",
                  button.getAttribute("data-report-scope") === scope ? "true" : "false",
                );
              });
              document.querySelectorAll("[data-scope-view]:not([data-drawer-item])").forEach(function (item) {
                item.hidden = item.getAttribute("data-scope-view") !== scope;
              });
              closeDrawer();
              var first = document.querySelector('[data-source-panel][data-scope-view="' + scope + '"]');
              if (first) activatePanel(first.getAttribute("data-source-panel"));
            }
            document.querySelectorAll("[data-report-scope]").forEach(function (button) {
              button.addEventListener("click", function () {
                activateReportScope(button.getAttribute("data-report-scope"));
              });
            });
            document.querySelectorAll("[data-source-panel]").forEach(function (button) {
              button.addEventListener("click", function () {
                activatePanel(button.getAttribute("data-source-panel"));
              });
            });
            document.querySelectorAll("[data-open-drawer]").forEach(function (trigger) {
              trigger.addEventListener("click", function () {
                var target = document.querySelector(
                  '[data-drawer-item="' + trigger.getAttribute("data-open-drawer") + '"]',
                );
                if (target && target.getAttribute("data-scope-view") === activeReportScope()) {
                  target.hidden = false;
                }
              });
            });
            activateReportScope(activeReportScope());
          })();
        </script>
      </body>
    </html>`;
}

const FALLBACK_CASES = ["html", "htm", "dsd", "xml"].flatMap((extension) =>
  ["network", 404, 405].map((failure) => ({ extension, failure })),
);

const DISGUISED_PDF_CASES = ["network", 404, 405];

function unavailableResponse(failure) {
  return failure === "network"
    ? unavailableFetch()
    : vi.fn(async () => ({ ok: false, status: failure }));
}

describe("dart-verify browser shell", () => {
  beforeEach(() => {
    vi.resetModules();
    globalThis.__DART_VERIFY_DISABLE_AUTO_INIT__ = true;
    document.body.className = "";
    document.body.removeAttribute("data-active-report-scope");
    document.body.removeAttribute("data-workbench-script-executions");
    document.body.innerHTML = `
      <button id="verify-another-file" type="button" hidden>다른 파일 검증</button>
      <div id="drop-zone"></div>
      <input id="file-input" type="file">
      <div id="status"></div>
      <div id="result"></div>
      <div id="selected-file-name"></div>
      <div id="run-meta"></div>
      <pre id="details"></pre>
    `;
  });

  test("uploads PDF to the verification service and renders returned workbench", async () => {
    const fetchFn = vi.fn(async () => ({
      ok: true,
      headers: new Headers({ "content-type": "text/html; charset=utf-8" }),
      text: async () => '<div data-report-profile="audit-workbench">PDF OK</div>',
    }));
    const { initDartVerifyApp } = await import("../../static/dart-verify/app.js");
    const controller = initDartVerifyApp({
      autoBoot: false,
      fetchFn,
    });

    await controller.verifyFile(
      new File([new Uint8Array([0x25, 0x50, 0x44, 0x46])], "report.pdf"),
    );

    expect(fetchFn).toHaveBeenCalledWith(
      "/api/verify",
      expect.objectContaining({ method: "POST" }),
    );
    expect(document.getElementById("result").innerHTML).toContain("PDF OK");
  });

  test("reveals the other-file action after success and reuses the existing file input", async () => {
    const fetchFn = vi.fn(async () => ({
      ok: true,
      status: 200,
      text: async () => '<div data-report-profile="audit-workbench">OK</div>',
    }));
    const fileInput = document.getElementById("file-input");
    const inputClick = vi.spyOn(fileInput, "click");
    const { initDartVerifyApp } = await import("../../static/dart-verify/app.js");
    const controller = initDartVerifyApp({ autoBoot: false, fetchFn });

    expect(document.getElementById("verify-another-file").hidden).toBe(true);

    await controller.verifyFile(new File(["<html></html>"], "report.html"));

    expect(document.body.classList.contains("has-result")).toBe(true);
    expect(document.getElementById("verify-another-file").hidden).toBe(false);

    document.getElementById("verify-another-file").click();
    expect(inputClick).toHaveBeenCalledTimes(1);
  });

  test("restores upload state while a new verification starts and after its error", async () => {
    let resolveSecondRequest;
    const secondResponse = new Promise((resolve) => {
      resolveSecondRequest = resolve;
    });
    const fetchFn = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        text: async () => '<div data-report-profile="audit-workbench">first</div>',
      })
      .mockImplementationOnce(() => secondResponse);
    const { initDartVerifyApp } = await import("../../static/dart-verify/app.js");
    const controller = initDartVerifyApp({ autoBoot: false, fetchFn });

    await controller.verifyFile(new File(["first"], "first.html"));
    expect(document.body.classList.contains("has-result")).toBe(true);
    expect(document.getElementById("verify-another-file").hidden).toBe(false);

    const pending = controller.verifyFile(new File(["second"], "second.html"));

    expect(document.body.classList.contains("has-result")).toBe(false);
    expect(document.getElementById("verify-another-file").hidden).toBe(true);

    resolveSecondRequest({
      ok: false,
      status: 422,
      json: async () => ({
        message: "선택한 파일을 확인하지 못했습니다.",
        next_action: "다른 파일을 선택하세요.",
      }),
    });
    await expect(pending).rejects.toThrow();

    expect(document.body.classList.contains("has-result")).toBe(false);
    expect(document.getElementById("verify-another-file").hidden).toBe(true);
  });

  test("shows the verification service message and action without internal error details", async () => {
    const fetchFn = vi.fn(async () => ({
      ok: false,
      status: 422,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({
        error: "PDF_OCR_REQUIRED",
        message: "텍스트를 읽을 수 없는 PDF입니다.",
        next_action: "OCR 처리된 PDF를 다시 선택하세요.",
      }),
    }));
    const loadPyodideFn = vi.fn();
    document.getElementById("result").innerHTML =
      '<div data-report-profile="audit-workbench">이전 결과</div>';
    document.body.classList.add("has-result");

    const { initDartVerifyApp } = await import("../../static/dart-verify/app.js");
    const controller = initDartVerifyApp({ autoBoot: false, fetchFn, loadPyodideFn });

    await expect(controller.verifyFile(new File(["%PDF"], "scan.pdf"))).rejects.toThrow();

    expect(document.getElementById("status").textContent).toBe(
      "텍스트를 읽을 수 없는 PDF입니다.",
    );
    expect(document.getElementById("details").textContent).toBe(
      "OCR 처리된 PDF를 다시 선택하세요.",
    );
    expect(document.body.textContent).not.toContain("PDF_OCR_REQUIRED");
    expect(document.getElementById("result").innerHTML).toBe("");
    expect(document.body.classList.contains("has-result")).toBe(false);
    expect(loadPyodideFn).not.toHaveBeenCalled();
  });

  test("does not attempt Pyodide when the PDF verification service is unavailable", async () => {
    const loadPyodideFn = vi.fn();
    const { initDartVerifyApp } = await import("../../static/dart-verify/app.js");
    const controller = initDartVerifyApp({
      autoBoot: false,
      fetchFn: unavailableFetch(),
      loadPyodideFn,
    });

    await expect(controller.verifyFile(new File(["%PDF"], "report.pdf"))).rejects.toThrow(
      "PDF 검증 서비스를 사용할 수 없습니다.",
    );

    expect(document.getElementById("status").textContent).toBe(
      "PDF 검증 서비스를 사용할 수 없습니다.",
    );
    expect(document.getElementById("details").textContent).toBe(
      "검증 앱을 로컬 서버로 다시 실행하거나 관리자에게 PDF 검증 서비스 상태를 확인하세요.",
    );
    expect(loadPyodideFn).not.toHaveBeenCalled();
  });

  test.each(FALLBACK_CASES)(
    "falls back to Pyodide for .$extension on $failure",
    async ({ extension, failure }) => {
      const install = vi.fn();
      const pyodide = {
        FS: { writeFile: vi.fn() },
        globals: { set: vi.fn(), delete: vi.fn() },
        loadPackage: vi.fn(),
        pyimport: vi.fn(() => ({ install })),
        runPython: vi.fn(() => '<div data-report-profile="audit-workbench">fallback</div>'),
      };
      const loadPyodideFn = vi.fn(async () => pyodide);
      const fetchFn = unavailableResponse(failure);
      const { initDartVerifyApp } = await import("../../static/dart-verify/app.js");
      const controller = initDartVerifyApp({ autoBoot: false, fetchFn, loadPyodideFn });

      await controller.verifyFile(new File(["<html></html>"], `report.${extension}`));

      expect(loadPyodideFn).toHaveBeenCalledTimes(1);
      expect(document.getElementById("result").textContent).toContain("fallback");
    },
  );

  test.each(DISGUISED_PDF_CASES)(
    "does not send a disguised PDF to Pyodide on %s",
    async (failure) => {
      const loadPyodideFn = vi.fn();
      const { initDartVerifyApp } = await import("../../static/dart-verify/app.js");
      const controller = initDartVerifyApp({
        autoBoot: false,
        fetchFn: unavailableResponse(failure),
        loadPyodideFn,
      });
      const disguisedPdf = new File(
        [new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d])],
        "report.html",
      );

      await expect(controller.verifyFile(disguisedPdf)).rejects.toThrow(
        "PDF 검증 서비스를 사용할 수 없습니다.",
      );

      expect(loadPyodideFn).not.toHaveBeenCalled();
    },
  );

  test("does not use Pyodide for unsupported files when the service is unavailable", async () => {
    const loadPyodideFn = vi.fn();
    const { initDartVerifyApp } = await import("../../static/dart-verify/app.js");
    const controller = initDartVerifyApp({
      autoBoot: false,
      fetchFn: unavailableFetch(),
      loadPyodideFn,
    });

    await expect(controller.verifyFile(new File(["plain text"], "report.txt"))).rejects.toThrow(
      "선택한 파일의 검증 서비스를 사용할 수 없습니다.",
    );

    expect(loadPyodideFn).not.toHaveBeenCalled();
  });

  test("does not boot Pyodide before a successful server verification", async () => {
    const loadPyodideFn = vi.fn();
    const fetchFn = vi.fn(async () => ({
      ok: true,
      status: 200,
      text: async () => '<div data-report-profile="audit-workbench">server</div>',
    }));
    const { initDartVerifyApp } = await import("../../static/dart-verify/app.js");
    const controller = initDartVerifyApp({ fetchFn, loadPyodideFn });

    await controller.verifyFile(new File(["<html></html>"], "report.html"));

    expect(loadPyodideFn).not.toHaveBeenCalled();
  });

  test("preserves full-document initial scope and workbench interactions", async () => {
    const fetchFn = vi.fn(async () => ({
      ok: true,
      status: 200,
      text: async () => representativeWorkbenchDocument(),
    }));
    const { initDartVerifyApp } = await import("../../static/dart-verify/app.js");
    const controller = initDartVerifyApp({ autoBoot: false, fetchFn });

    await controller.verifyFile(new File(["<html></html>"], "report.html"));

    expect(document.body.dataset.workbenchScriptExecutions).toBe("1");
    expect(document.getElementById("workbench-style")).not.toBeNull();
    expect(document.getElementById("result").querySelectorAll("script")).toHaveLength(1);
    expect(document.body.getAttribute("data-active-report-scope")).toBe("consolidated");
    expect(document.getElementById("scope-consolidated").getAttribute("aria-pressed")).toBe(
      "true",
    );
    expect(document.getElementById("nav-consolidated").hidden).toBe(false);
    expect(document.getElementById("nav-separate").hidden).toBe(true);
    expect(document.getElementById("panel-consolidated").hidden).toBe(false);
    expect(document.getElementById("panel-separate").hidden).toBe(true);

    document.getElementById("drawer-trigger").click();
    expect(document.getElementById("drawer-item").hidden).toBe(false);

    document.getElementById("scope-separate").click();
    expect(document.body.getAttribute("data-active-report-scope")).toBe("separate");
    expect(document.getElementById("nav-consolidated").hidden).toBe(true);
    expect(document.getElementById("nav-separate").hidden).toBe(false);
    expect(document.getElementById("panel-consolidated").hidden).toBe(true);
    expect(document.getElementById("panel-separate").hidden).toBe(false);
    expect(document.getElementById("drawer-item").hidden).toBe(true);
  });

  test("clears stale scope before an invalid full-document scope is initialized", async () => {
    const responses = [
      representativeWorkbenchDocument("consolidated"),
      representativeWorkbenchDocument("unexpected"),
    ];
    const fetchFn = vi.fn(async () => ({
      ok: true,
      status: 200,
      text: async () => responses.shift(),
    }));
    const { initDartVerifyApp } = await import("../../static/dart-verify/app.js");
    const controller = initDartVerifyApp({ autoBoot: false, fetchFn });

    await controller.verifyFile(new File(["first"], "first.html"));
    expect(document.body.getAttribute("data-active-report-scope")).toBe("consolidated");

    await controller.verifyFile(new File(["second"], "second.html"));

    expect(document.body.getAttribute("data-active-report-scope")).toBe("all");
    expect(document.body.dataset.workbenchScriptExecutions).toBe("2");
    expect(document.getElementById("nav-consolidated").hidden).toBe(true);
    expect(document.getElementById("nav-separate").hidden).toBe(true);
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
      fetchFn: unavailableFetch(),
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

  test("surfaces selected file and final run state in the browser shell", async () => {
    const install = vi.fn();
    const pyodide = {
      FS: { writeFile: vi.fn() },
      globals: { set: vi.fn(), delete: vi.fn() },
      loadPackage: vi.fn(),
      pyimport: vi.fn(() => ({ install })),
      runPython: vi.fn(() => '<div class="verdict-banner">OK</div>'),
    };

    const { initDartVerifyApp } = await import("../../static/dart-verify/app.js");
    const controller = initDartVerifyApp({
      autoBoot: false,
      fetchFn: unavailableFetch(),
      loadPyodideFn: vi.fn(async () => pyodide),
    });

    await controller.verifyFile(new File(["<html></html>"], "sample-report.html"));

    expect(document.getElementById("selected-file-name").textContent).toBe("sample-report.html");
    expect(document.getElementById("status").dataset.state).toBe("done");
    expect(document.getElementById("run-meta").textContent).toContain("결과 생성됨");
  });

  test("shows a user action without runtime names or stack traces when preparation fails", async () => {
    const { initDartVerifyApp } = await import("../../static/dart-verify/app.js");
    const controller = initDartVerifyApp({
      autoBoot: false,
      loadPyodideFn: undefined,
    });

    await expect(controller.bootEngine()).rejects.toThrow();

    const visible = `${document.getElementById("status").textContent} ${
      document.getElementById("details").textContent
    }`;
    expect(visible).toContain("다시 열어주세요");
    expect(visible).not.toMatch(/PyOdide|vendor\/pyodide|Error:|at bootEngine|stack/i);
  });

  test("turns raw verification failures into a clear file action", async () => {
    const install = vi.fn();
    const pyodide = {
      FS: { writeFile: vi.fn() },
      globals: { set: vi.fn(), delete: vi.fn() },
      loadPackage: vi.fn(),
      pyimport: vi.fn(() => ({ install })),
      runPython: vi.fn(() => {
        throw new Error("PythonError: Traceback (most recent call last): parser crashed");
      }),
    };
    const { initDartVerifyApp } = await import("../../static/dart-verify/app.js");
    const controller = initDartVerifyApp({
      autoBoot: false,
      fetchFn: unavailableFetch(),
      loadPyodideFn: vi.fn(async () => pyodide),
    });

    await expect(controller.verifyFile(new File(["not a filing"], "sample.html"))).rejects.toThrow();
    controller.showError(new Error("PythonError: Traceback: parser crashed"));

    const visible = `${document.getElementById("status").textContent} ${
      document.getElementById("details").textContent
    }`;
    expect(visible).toContain("DART에서 내려받은 HTML/DSD/XML 파일");
    expect(visible).not.toMatch(/PythonError|Traceback|parser crashed|Error:/);
  });
});
