# HANDOFF.md — dart-verify (PyOdide Offline Verification App)

**Target branch:** `feat/offline-verify-html` (reuse — already checked out)
**Base branch:** `audit-workpaper-note-reconciliation`
**Primary executor:** Codex (file creation + tests)
**Git owner:** Claude (Codex sandbox cannot write `.git`; Claude commits after each verified batch)
**Verifier:** Claude (parity + spec + security after all tasks)

---

## ⚠️ DECISION RECORD — read first

The previous plan (`docs/superpowers/plans/2026-06-12-offline-verify-html.md`, a **JS port** of the
verification core) is **SUPERSEDED and abandoned.** Do not implement it.

**Why:** The Python engine already contains the entire verification stack the JS port would have
re-implemented — 2D table orientation (`orientation.py`, 1078 lines), reconciliation relationship graph
(`reconciliation_targets.py`), semantic dataset with provenance (`semantic_layer.py`), adjustment formula
templates (`formula_templates.py`), label resolution with confidence tiers + abstention
(`label_resolver.py`, `checks_statement_ties.py`), and the evidence_cockpit HTML renderer
(`report_html.py`). A JS reimplementation would be **strictly less accurate** and force every future
accuracy fix to be made twice (guaranteed divergence).

**Decision:** Run the **existing Python engine unmodified in the browser via PyOdide (WASM).** One engine,
zero divergence, in-browser drag-drop, client data never leaves the machine, no server, no CDN.
This was chosen explicitly under a hard "accuracy is non-negotiable" constraint.

Write an ADR capturing this: `docs/adr/0004-pyodide-single-engine-over-js-port.md`.

---

## Objective

A self-contained **offline app folder** (`dist/dart-verify/`) that:
- Loads a vendored PyOdide runtime + the `dart_footing_reconciler` wheel entirely from local files
- Accepts a DART **HTML / DSD** filing via drag-and-drop (PDF is **out of scope** — the engine itself
  rejects PDF at `local_report.py:42`; do not add PDF support)
- Runs the **real Python engine** in-browser: parse → assemble checks → render evidence_cockpit HTML
- Renders the engine's HTML output in the page
- Sends nothing over the network at runtime (confidentiality: CLAUDE.md §7)

Distribution = zip the folder. The "single self-contained HTML" constraint is intentionally relaxed to
"self-contained offline folder" because PyOdide requires WASM + stdlib + package assets.

---

## Confirmed feasibility facts (do not re-derive)

| Concern | Finding |
|---|---|
| `lxml` | Required by `document.py:75` (`BeautifulSoup(html, "lxml")`) — primary parse path. **Do not swap the parser** (accuracy). lxml ships as a prebuilt PyOdide package — load it. |
| `beautifulsoup4` | Pure Python — PyOdide available. |
| `openpyxl` | Eager-imported via `__init__.py` → `excel.py`. Pure Python — PyOdide available. Must be loaded even though Excel export is unused in-browser. |
| `typer` | NOT imported by `__init__.py` (only `cli.py`). Not needed in-browser. |
| `pydantic` | Declared dep but **unused** in `src/` — ignore. |
| PDF | Engine raises `UnsupportedReportFormatError`. App must surface a clean "HTML/DSD만 지원" message; no PDF parsing. |
| Encodings | `local_report._decode_text` already handles utf-8 / utf-8-sig / cp949 / euc-kr. Pass raw bytes, let it decode. |

PyOdide runtime package list to load: `["micropip", "lxml", "beautifulsoup4", "openpyxl"]`, then install the
local wheel. Pin a PyOdide version that ships lxml (e.g. 0.26.x — verify lxml is in that release's package index).

---

## Existing engine — REUSE, do not reimplement

Orchestration mirror of `cli.py::workpaper_html` (the canonical parse→check→html flow):

```python
from dart_footing_reconciler.document import parse_full_report          # path -> FullReport
from dart_footing_reconciler.check_pipeline import assemble_report_checks  # (report, prior, tolerance) -> [CheckResult]
from dart_footing_reconciler.report_html import export_audit_reconciliation_html  # (report, checks, output_path) -> Path
```

Note: `parse_full_report` and `export_audit_reconciliation_html` are path-based. In-browser you have
bytes/text, not a real path. See Task 1 — add ONE thin pure-Python entry that takes text and returns an
HTML string, so the browser glue calls a single function and the same function is unit-testable in plain
Python (this is the accuracy parity anchor).

---

## Task sequence (TDD; Codex creates files + runs tests, Claude commits)

### Task 1 — Pure-Python in-memory entry (the parity anchor)
**File:** `src/dart_footing_reconciler/verify_app.py` + `tests/test_verify_app.py`
Add `verify_html_report(html_text: str, *, company: str = "", prior_text: str | None = None, tolerance: int = 1) -> str`:
- Parse `html_text` (adapt `parse_full_report`; if it is path-only, write to a tmp path or factor out its
  text-parsing core — keep parser = lxml). Same for prior.
- `checks = assemble_report_checks(report, prior_report, tolerance=tolerance)`
- Return the evidence_cockpit HTML **as a string** (reuse `report_html._build_html` or write-then-read).
- DSD/HTML both flow through the same text path; reject PDF text (`%PDF` signature) with the engine's message.
- Unit test: feed a fixture's HTML text, assert the returned HTML contains the verdict banner and that the
  check count/statuses equal `assemble_report_checks` run directly. **This test runs in plain Python — no PyOdide.**

### Task 2 — Build command that assembles the offline folder
**File:** add `build-verify-app` to `cli.py` + `tests/test_build_verify_app.py`
- `dart-footing build-verify-app --output dist/dart-verify/ [--pyodide-dir vendor/pyodide]`
- Builds/locates the wheel (`python -m build` or reuse `dist/*.whl`), copies it + `index.html` + `app.js`
  into the output folder, and references the vendored PyOdide dir.
- Test: run the command against a temp dir, assert `index.html`, `app.js`, and `*.whl` exist in output.
- Fetching the PyOdide runtime itself needs network — script/document the asset URLs + version; if the
  sandbox has no network, leave a `vendor/pyodide/README.md` with the exact download command and DO NOT
  fail the build test on missing vendor assets (test the assembly logic, not the download).

### Task 3 — Browser shell (index.html + app.js)
**Files:** `static/dart-verify/index.html`, `static/dart-verify/app.js`
- index.html: PAS evidence_cockpit shell — drop zone, loading state ("엔진 로딩 중…"), result container,
  Korean-first UI per CLAUDE.md §4.4. No external CDN.
- app.js: `loadPyodide({indexURL:"vendor/pyodide/"})` → `loadPackage([...])` → `micropip.install(wheel)` →
  read dropped file bytes → decode to text in Python (pass bytes via `pyodide.FS` or as a JS string) →
  `verify_html_report(text, company=…)` → inject returned HTML into the result container.
- Surface PDF/parse errors as human-readable Korean messages (기술 세부정보는 보조 영역).

### Task 4 — E2E parity test (the accuracy gate)
**File:** `tests/e2e/dart-verify-parity.spec.js`
- Launch the assembled app via `file://`, drop a fixture HTML, wait for render.
- Capture the rendered result HTML.
- Assert it is **equal to** `verify_html_report(<same fixture text>)` computed by Python on the same input.
- This proves the in-browser engine === the Python engine (zero divergence). If PyOdide assets aren't
  vendored in the sandbox, mark this test `skip` with a clear reason and report it — Claude/user runs it
  locally after vendoring.

### Task 5 — Build the wheel + final full suite
- `python -m build` (or hatch) → `dist/dart_footing_reconciler-0.1.0-py3-none-any.whl`
- Run `pytest -q` (no regressions), Task 1/2 tests green, report E2E status.

---

## Division of responsibility

| Role | Does |
|---|---|
| **Codex** | Creates/edits files, runs `pytest` + (if possible) `playwright`, reports results + file list + test counts. **Does NOT run git.** |
| **Claude** | `git add` + `git commit` after each verified task batch; final verification. |

After each task report: task number, files created, pytest result (pass/fail counts), any skips with reason.

---

## Done Criteria

- `pytest -q` — all Python tests pass (no regressions); `test_verify_app.py` + `test_build_verify_app.py` green.
- `verify_html_report(text)` returns evidence_cockpit HTML whose checks match `assemble_report_checks`.
- `build-verify-app` assembles a folder with `index.html`, `app.js`, wheel.
- E2E parity test passes **or** is skipped with a documented vendoring reason.
- ADR `0004-pyodide-single-engine-over-js-port.md` written.
- Drag a DART HTML filing onto the assembled app → evidence_cockpit verdict renders, identical to CLI output.
