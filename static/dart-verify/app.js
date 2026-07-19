// openpyxl is intentionally excluded: it is not in the PyOdide bundle and the
// verification path never imports it (workbook exporters are lazy in __init__).
export const PYODIDE_PACKAGES = ["micropip", "lxml", "beautifulsoup4"];

const DEFAULT_PYODIDE_INDEX_URL = "vendor/pyodide/";
const DEFAULT_WHEEL_PATH = "./__DART_VERIFY_WHEEL__";
const INPUT_PATH = "/tmp/dart_verify_current.bin";
const PYODIDE_FALLBACK_EXTENSIONS = [".html", ".htm", ".dsd", ".xml"];
const REPORT_SCOPES = new Set(["consolidated", "separate", "all"]);
const VERIFY_PYTHON = `
from pathlib import Path
from dart_footing_reconciler.local_report import _decode_text
from dart_footing_reconciler.verify_app import verify_html_report

verify_html_report(
    _decode_text(Path(dart_verify_path).read_bytes()),
    company=dart_verify_company,
    tolerance=int(dart_verify_tolerance),
)
`;

export function initDartVerifyApp({
  documentRef = globalThis.document,
  loadPyodideFn = globalThis.loadPyodide,
  pyodideIndexURL = DEFAULT_PYODIDE_INDEX_URL,
  wheelPath = DEFAULT_WHEEL_PATH,
  tolerance = 1,
  autoBoot = true,
  fetchFn = globalThis.fetch?.bind(globalThis),
} = {}) {
  const elements = {
    dropZone: documentRef?.getElementById("drop-zone"),
    fileInput: documentRef?.getElementById("file-input"),
    status: documentRef?.getElementById("status"),
    result: documentRef?.getElementById("result"),
    details: documentRef?.getElementById("details"),
    selectedFileName: documentRef?.getElementById("selected-file-name"),
    runMeta: documentRef?.getElementById("run-meta"),
    verifyAnotherFile: documentRef?.getElementById("verify-another-file"),
  };
  let enginePromise;

  async function bootEngine() {
    if (!enginePromise) {
      enginePromise = (async () => {
        if (!loadPyodideFn) {
          throw new Error("PyOdide 로더를 찾을 수 없습니다. vendor/pyodide 자산을 확인하세요.");
        }
        setStatus("검증 준비 중...", "loading");
        setRunMeta("준비 중");
        const pyodide = await loadPyodideFn({ indexURL: pyodideIndexURL });
        await pyodide.loadPackage(PYODIDE_PACKAGES);
        const micropip = pyodide.pyimport("micropip");
        // deps=false (3rd positional: requirements, keep_going, deps): install ONLY
        // the engine wheel. Its declared deps (pydantic, typer, openpyxl) are unused
        // on the verify path and unresolvable offline (e.g. pydantic-core has no pure
        // Python wheel). Runtime deps lxml + beautifulsoup4 are already provided by
        // loadPackage(PYODIDE_PACKAGES) above.
        await micropip.install(wheelPath, false, false);
        setStatus("파일 선택 가능", "ready");
        setRunMeta("파일 대기 중");
        return pyodide;
      })().catch((error) => {
        enginePromise = undefined;
        showError(error);
        throw error;
      });
    }
    return enginePromise;
  }

  async function verifyFile(file) {
    if (!file) {
      throw new Error("파일을 선택하세요.");
    }

    setSelectedFile(file);
    setStatus("원문 검토 중...", "running");
    setRunMeta(formatBytes(file.size));
    clearError();
    clearResult();

    try {
      const serverHtml = await verifyWithServer(file);
      if (serverHtml !== null) {
        return showResult(serverHtml, file);
      }
      if (await isPdfFile(file)) {
        throw userFacingError(
          "PDF 검증 서비스를 사용할 수 없습니다.",
          "검증 앱을 로컬 서버로 다시 실행하거나 관리자에게 PDF 검증 서비스 상태를 확인하세요.",
        );
      }
      if (!allowsPyodideFallback(file)) {
        throw userFacingError(
          "선택한 파일의 검증 서비스를 사용할 수 없습니다.",
          "HTML/HTM/DSD/XML/PDF 파일을 선택하거나 관리자에게 검증 서비스 상태를 확인하세요.",
        );
      }
      return await verifyWithPyodide(file);
    } catch (error) {
      showError(error);
      throw error;
    }
  }

  async function verifyWithServer(file) {
    if (!fetchFn) {
      return null;
    }
    const body = new FormData();
    body.append("file", file, file.name || "dart-report");
    let response;
    try {
      response = await fetchFn("/api/verify", { method: "POST", body });
    } catch {
      return null;
    }
    if (response.status === 404 || response.status === 405) {
      return null;
    }
    if (!response.ok) {
      let payload;
      try {
        payload = await response.json();
      } catch {
        payload = undefined;
      }
      throw userFacingError(
        stringValue(payload?.message) || "검증 서비스를 통해 파일을 확인하지 못했습니다.",
        stringValue(payload?.next_action) ||
          "파일을 다시 선택하세요. 문제가 계속되면 관리자에게 검증 서비스 상태를 확인하세요.",
        stringValue(payload?.error),
      );
    }
    return response.text();
  }

  async function verifyWithPyodide(file) {
    const pyodide = await bootEngine();

    const bytes = new Uint8Array(await readArrayBuffer(file));
    pyodide.FS.writeFile(INPUT_PATH, bytes);
    pyodide.globals.set("dart_verify_path", INPUT_PATH);
    pyodide.globals.set("dart_verify_company", companyFromFile(file));
    pyodide.globals.set("dart_verify_tolerance", tolerance);

    try {
      const html = pyodide.runPython(VERIFY_PYTHON);
      return showResult(html, file);
    } finally {
      deleteGlobal(pyodide, "dart_verify_path");
      deleteGlobal(pyodide, "dart_verify_company");
      deleteGlobal(pyodide, "dart_verify_tolerance");
    }
  }

  async function handleFile(file) {
    try {
      await verifyFile(file);
    } catch (error) {
      showError(error);
    }
  }

  attachEvents(elements, handleFile);
  if (autoBoot) {
    setStatus("파일 선택 가능", "ready");
    setRunMeta("파일 대기 중");
  }

  return { bootEngine, verifyFile, handleFile, showError };

  function setStatus(message, state = "") {
    if (elements.status) {
      elements.status.textContent = message;
      if (state) {
        elements.status.dataset.state = state;
      }
    }
  }

  function setSelectedFile(file) {
    if (elements.selectedFileName) {
      elements.selectedFileName.textContent = file.name || "선택한 파일";
      elements.selectedFileName.title = file.name || "";
    }
  }

  function setRunMeta(message) {
    if (elements.runMeta) {
      elements.runMeta.textContent = message;
    }
  }

  function clearError() {
    if (elements.details) {
      elements.details.hidden = true;
      elements.details.textContent = "";
    }
  }

  function clearResult() {
    if (elements.result) {
      elements.result.replaceChildren();
    }
    documentRef?.body?.classList.remove("has-result");
    documentRef?.body?.removeAttribute("data-active-report-scope");
    if (elements.verifyAnotherFile) {
      elements.verifyAnotherFile.hidden = true;
    }
    globalThis.__dartVerifyLastHtml = "";
  }

  function showResult(html, file) {
    const initialScope = initialReportScope(html, documentRef);
    if (elements.result) {
      elements.result.innerHTML = html;
      if (initialScope) {
        documentRef?.body?.setAttribute("data-active-report-scope", initialScope);
      }
      reactivateScripts(elements.result, documentRef);
    }
    globalThis.__dartVerifyLastHtml = html;
    documentRef?.body?.classList.add("has-result");
    if (elements.verifyAnotherFile) {
      elements.verifyAnotherFile.hidden = false;
    }
    setStatus("검증 완료", "done");
    setRunMeta(`${formatBytes(file.size)} · 결과 생성됨`);
    return html;
  }

  function showError(error) {
    clearResult();
    setStatus(toKoreanErrorMessage(error), "error");
    setRunMeta("확인 필요");
    if (elements.details) {
      elements.details.hidden = false;
      elements.details.textContent = nextActionForError(error);
    }
  }
}

async function isPdfFile(file) {
  if (file.name?.toLowerCase().endsWith(".pdf")) {
    return true;
  }
  const head = new Uint8Array(await readArrayBuffer(file.slice(0, 4)));
  return head[0] === 0x25 && head[1] === 0x50 && head[2] === 0x44 && head[3] === 0x46;
}

function allowsPyodideFallback(file) {
  const name = (file.name || "").toLowerCase();
  return PYODIDE_FALLBACK_EXTENSIONS.some((extension) => name.endsWith(extension));
}

function initialReportScope(html, documentRef) {
  const Parser = documentRef?.defaultView?.DOMParser || globalThis.DOMParser;
  if (!Parser) {
    return "";
  }
  const parsed = new Parser().parseFromString(html, "text/html");
  const scope = parsed.body.getAttribute("data-active-report-scope") || "";
  return REPORT_SCOPES.has(scope) ? scope : "";
}

function reactivateScripts(container, documentRef) {
  for (const oldScript of container.querySelectorAll("script")) {
    const script = documentRef.createElement("script");
    for (const attribute of oldScript.attributes) {
      script.setAttribute(attribute.name, attribute.value);
    }
    script.textContent = oldScript.textContent;
    oldScript.replaceWith(script);
  }
}

async function readArrayBuffer(blob) {
  if (typeof blob.arrayBuffer === "function") {
    return blob.arrayBuffer();
  }
  if (typeof FileReader !== "undefined") {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.addEventListener("load", () => resolve(reader.result));
      reader.addEventListener("error", () => reject(reader.error));
      reader.readAsArrayBuffer(blob);
    });
  }
  return new Response(blob).arrayBuffer();
}

function attachEvents(elements, handleFile) {
  if (elements.verifyAnotherFile) {
    elements.verifyAnotherFile.addEventListener("click", () => elements.fileInput?.click());
  }
  if (elements.fileInput) {
    elements.fileInput.addEventListener("change", () => {
      const file = elements.fileInput.files?.[0];
      if (file) {
        handleFile(file);
      }
    });
  }

  if (!elements.dropZone) {
    return;
  }

  elements.dropZone.addEventListener("click", () => elements.fileInput?.click());
  elements.dropZone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      elements.fileInput?.click();
    }
  });
  elements.dropZone.addEventListener("dragover", (event) => {
    event.preventDefault();
    elements.dropZone.classList.add("drag-over");
  });
  elements.dropZone.addEventListener("dragleave", () => {
    elements.dropZone.classList.remove("drag-over");
  });
  elements.dropZone.addEventListener("drop", (event) => {
    event.preventDefault();
    elements.dropZone.classList.remove("drag-over");
    const file = event.dataTransfer?.files?.[0];
    if (file) {
      handleFile(file);
    }
  });
}

function companyFromFile(file) {
  return (file.name || "DART").replace(/\.[^.]+$/, "");
}

function formatBytes(size) {
  if (!Number.isFinite(size) || size <= 0) {
    return "파일 크기 확인 전";
  }
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function deleteGlobal(pyodide, name) {
  if (typeof pyodide.globals?.delete === "function") {
    pyodide.globals.delete(name);
  }
}

function stringValue(value) {
  return typeof value === "string" && value.trim() ? value : "";
}

function userFacingError(message, nextAction, errorCode = "") {
  const error = new Error(message);
  error.userMessage = message;
  error.nextAction = nextAction;
  error.errorCode = errorCode;
  return error;
}

function toKoreanErrorMessage(error) {
  if (stringValue(error?.userMessage)) {
    return error.userMessage;
  }
  const message = String(error?.message || error || "");
  if (message.includes("vendor/pyodide")) {
    return "검증 준비에 필요한 파일을 불러오지 못했습니다.";
  }
  if (message.includes("UnsupportedReportFormatError")) {
    return "선택한 파일을 확인할 수 없습니다.";
  }
  return "검증을 완료하지 못했습니다.";
}

function nextActionForError(error) {
  if (stringValue(error?.nextAction)) {
    return error.nextAction;
  }
  const message = String(error?.message || error || "");
  if (message.includes("vendor/pyodide")) {
    return "앱을 닫은 뒤 다시 열어주세요. 문제가 계속되면 관리자에게 검증 앱 재설치를 요청하세요.";
  }
  return "DART에서 내려받은 HTML/DSD/XML 파일인지 확인한 뒤 다시 선택하세요.";
}

if (
  typeof window !== "undefined" &&
  typeof document !== "undefined" &&
  !globalThis.__DART_VERIFY_DISABLE_AUTO_INIT__
) {
  window.addEventListener("DOMContentLoaded", () => initDartVerifyApp());
}
