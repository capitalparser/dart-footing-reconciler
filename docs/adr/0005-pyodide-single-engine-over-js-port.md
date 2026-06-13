# ADR 0005 — PyOdide single-engine in-browser, not a JS port

**Date:** 2026-06-14
**Status:** Accepted
**Supersedes:** the JS-port plan/spec `docs/superpowers/{plans,specs}/2026-06-12-offline-verify-html.md`

## Context

We needed an **offline, self-contained** way for an auditor to drop a DART filing and get footing /
reconciliation verification, with **client financial data never leaving the machine** (CLAUDE.md §7) and
**no server / no CDN**.

The first plan was a single `dart-verify.html` that **re-implemented the verification core in JavaScript**
(parseAmount, LabelResolver, BS/cash/equity ties, table parsing). Implementation reached a task-1 scaffold
before we re-examined it.

During design review we found the Python engine already contains the **entire** verification stack the JS
port would duplicate:

- `orientation.py` (1078 lines) — 2D note-table orientation/axis detection with confidence + evidence
- `reconciliation_targets.py` — the relationship graph (balance / cashflow / expense-allocation /
  prior→current / table-total, with `required_adjustments`)
- `formula_templates.py` — non-cash adjustment formulas with tolerance + 2^n subset search
- `semantic_layer.py` — `SemanticAmountFact` carrying role / period / confidence / `account_key` /
  `cell_source` provenance
- `label_resolver.py` + `checks_statement_ties.py` — 5-tier label resolution with `PARSE_UNCERTAIN`
  abstention and false-match guards
- `report_html.py` — the evidence_cockpit HTML renderer

## Decision

**Run the existing Python `dart_footing_reconciler` engine unmodified in the browser via PyOdide (WASM).**
The browser is a thin shell: file bytes → PyOdide FS → one pure-Python entry (`verify_app.verify_html_report`)
→ evidence_cockpit HTML string → injected into the DOM.

The deliverable is a **self-contained offline folder** (`dist/dart-verify/`: `index.html`, `app.js`, the
engine wheel, vendored `vendor/pyodide/`), assembled by the `build-verify-app` CLI command. The original
"single HTML file" constraint is intentionally relaxed to "offline folder" because PyOdide requires WASM +
stdlib + package assets. Confidentiality and no-server are preserved; distribution = zip the folder.

## Why (the deciding constraint: accuracy is non-negotiable)

A JS reimplementation would be **strictly less accurate** than the Python engine and would force every
future accuracy fix to be written **twice**, guaranteeing divergence between the "real" engine and the
"browser" engine. PyOdide gives **one engine, zero divergence**: anything the Python test suite proves also
holds in the browser. The accuracy parity is testable directly — `verify_html_report` output vs.
`assemble_report_checks` on the same real fixture (`tests/test_verify_app.py`).

## Feasibility (confirmed before handoff)

- Runtime deps: `beautifulsoup4` (pure), `lxml` (prebuilt PyOdide package — required by `document.py`,
  parser **not** swapped to preserve accuracy), `openpyxl` (pure; eager-imported via `__init__.py`).
  `typer` is CLI-only (not imported in-browser); `pydantic` is declared but unused.
- PDF stays **unsupported** — the engine already rejects it (`local_report.py:42`); the shell surfaces a
  clean Korean "HTML/DSD만 지원" message. Encodings (cp949/euc-kr) handled by the engine's `_decode_text`.

## Consequences

- **+** Single source of truth; browser accuracy == engine accuracy; note↔statement reconciliation (the
  project's real value) is available in-browser, not just the three statement ties.
- **−** Payload: PyOdide runtime + lxml (~several MB) must be vendored locally (one-time network fetch at
  build time); startup latency of a few seconds (shell shows "엔진 로딩 중…").
- **−** The browser-side E2E parity test and a populated `vendor/pyodide/` are still outstanding; until the
  runtime is vendored, the app cannot execute in a browser. The Python-side parity is already proven.

## Alternatives rejected

- **JS port** — less accurate, double-maintenance (this ADR's whole point).
- **Python-local + HTML export** — maximally accurate but needs a Python environment on the auditor's
  machine; loses the drag-drop-in-browser UX.
- **kreports as data source** — irrelevant: the uploaded file is itself the SSOT; pulling external data
  would introduce a second, divergent semantic layer.
