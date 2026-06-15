// openpyxl is intentionally excluded: it is not in the PyOdide bundle and the
// verification path never imports it (workbook exporters are lazy in __init__).
export const PYODIDE_PACKAGES = ["micropip", "lxml", "beautifulsoup4"];

const DEFAULT_PYODIDE_INDEX_URL = "vendor/pyodide/";
const DEFAULT_WHEEL_PATH = "./__DART_VERIFY_WHEEL__";
const INPUT_PATH = "/tmp/dart_verify_current.bin";
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
} = {}) {
  const elements = {
    dropZone: documentRef?.getElementById("drop-zone"),
    fileInput: documentRef?.getElementById("file-input"),
    status: documentRef?.getElementById("status"),
    result: documentRef?.getElementById("result"),
    details: documentRef?.getElementById("details"),
  };
  let enginePromise;

  async function bootEngine() {
    if (!enginePromise) {
      enginePromise = (async () => {
        if (!loadPyodideFn) {
          throw new Error("PyOdide 로더를 찾을 수 없습니다. vendor/pyodide 자산을 확인하세요.");
        }
        setStatus("엔진 로딩 중...");
        const pyodide = await loadPyodideFn({ indexURL: pyodideIndexURL });
        await pyodide.loadPackage(PYODIDE_PACKAGES);
        const micropip = pyodide.pyimport("micropip");
        // deps=false (3rd positional: requirements, keep_going, deps): install ONLY
        // the engine wheel. Its declared deps (pydantic, typer, openpyxl) are unused
        // on the verify path and unresolvable offline (e.g. pydantic-core has no pure
        // Python wheel). Runtime deps lxml + beautifulsoup4 are already provided by
        // loadPackage(PYODIDE_PACKAGES) above.
        await micropip.install(wheelPath, false, false);
        setStatus("엔진 준비 완료");
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
    if (await isPdfFile(file)) {
      throw new Error("PDF 파일은 지원하지 않습니다. DART HTML/DSD 파일을 사용하세요.");
    }

    const pyodide = await bootEngine();
    setStatus("검증 실행 중...");
    clearError();

    const bytes = new Uint8Array(await readArrayBuffer(file));
    pyodide.FS.writeFile(INPUT_PATH, bytes);
    pyodide.globals.set("dart_verify_path", INPUT_PATH);
    pyodide.globals.set("dart_verify_company", companyFromFile(file));
    pyodide.globals.set("dart_verify_tolerance", tolerance);

    try {
      const html = pyodide.runPython(VERIFY_PYTHON);
      if (elements.result) {
        elements.result.innerHTML = html;
      }
      globalThis.__dartVerifyLastHtml = html;
      setStatus("검증 완료");
      return html;
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
    bootEngine().catch(() => {});
  }

  return { bootEngine, verifyFile, handleFile, showError };

  function setStatus(message) {
    if (elements.status) {
      elements.status.textContent = message;
    }
  }

  function clearError() {
    if (elements.details) {
      elements.details.hidden = true;
      elements.details.textContent = "";
    }
  }

  function showError(error) {
    setStatus(toKoreanErrorMessage(error));
    if (elements.details) {
      elements.details.hidden = false;
      elements.details.textContent = technicalDetails(error);
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

async function readArrayBuffer(blob) {
  if (typeof blob.arrayBuffer === "function") {
    return blob.arrayBuffer();
  }
  return new Response(blob).arrayBuffer();
}

function attachEvents(elements, handleFile) {
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

function deleteGlobal(pyodide, name) {
  if (typeof pyodide.globals?.delete === "function") {
    pyodide.globals.delete(name);
  }
}

function toKoreanErrorMessage(error) {
  const message = String(error?.message || error || "");
  if (message.includes("PDF") || message.includes("HTML/DSD")) {
    return "PDF 파일은 지원하지 않습니다. DART HTML/DSD 파일을 사용하세요.";
  }
  if (message.includes("vendor/pyodide")) {
    return "PyOdide 엔진 자산을 찾을 수 없습니다. vendor/pyodide 폴더를 확인하세요.";
  }
  if (message.includes("UnsupportedReportFormatError")) {
    return "지원하지 않는 파일 형식입니다. DART HTML/DSD 파일을 사용하세요.";
  }
  return "검증 중 오류가 발생했습니다. HTML/DSD 원문 파일인지 확인하세요.";
}

function technicalDetails(error) {
  if (error?.stack) {
    return error.stack;
  }
  return String(error?.message || error || "");
}

if (
  typeof window !== "undefined" &&
  typeof document !== "undefined" &&
  !globalThis.__DART_VERIFY_DISABLE_AUTO_INIT__
) {
  window.addEventListener("DOMContentLoaded", () => initDartVerifyApp());
}
