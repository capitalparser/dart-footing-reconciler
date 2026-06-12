# HANDOFF.md — dart-verify.html (Offline Verification HTML)

**Target branch:** `feat/offline-verify-html`  
**Base branch:** `audit-workpaper-note-reconciliation`  
**Primary executor:** Codex  
**Verifier:** Claude (spec compliance + security review after all tasks complete)

---

## Objective

Build `dart-verify.html` — a single self-contained HTML file that:
- Accepts DART HTML / DSD / electronic PDF file uploads (drag-and-drop)
- Runs BS equation / cash tie / equity tie checks in-browser (JS port of Python core)
- Renders PAS evidence_cockpit UI (dark sidebar, verdict banner, tick overlays, drilldowns)
- Has kreports stub panel (UI present, API calls no-op)

No server. No external CDN. Single artifact file.

---

## Documents to Read (in order)

1. **`docs/superpowers/specs/2026-06-12-offline-verify-html.md`** — full design spec (architecture, data structures, format handling, checks, UI)
2. **`docs/superpowers/plans/2026-06-12-offline-verify-html.md`** — step-by-step implementation plan with complete code for every step

---

## Python Reference Files

| File | Port target |
|------|-------------|
| `src/dart_footing_reconciler/amounts.py` | `parseAmount()` in verify-engine.js |
| `src/dart_footing_reconciler/label_resolver.py` | `LabelResolver.findRow()` in verify-engine.js |
| `src/dart_footing_reconciler/checks_statement_ties.py` | `bsEquationCheck/cashTieCheck/equityTieCheck` in verify-engine.js |
| `src/dart_footing_reconciler/html_tables.py` | `parseHtml()` in html-parser.js |

---

## Execution

1. Create branch: `git checkout -b feat/offline-verify-html`
2. Follow the plan task-by-task (Tasks 1–15)
3. TDD throughout: write failing test → implement → pass → commit
4. After Task 15 passes all tests, report status to Claude for code review

---

## Done Criteria

- `npx vitest run` — all JS unit tests pass
- `npx playwright test` — all 4 E2E smoke tests pass
- `python -m pytest tests/ -x -q` — all Python tests pass (no regressions)
- `python -m dart_footing_reconciler build-verify-html --output dart-verify.html` — builds successfully
- Drag a DART HTML file onto dart-verify.html → verdict banner renders
