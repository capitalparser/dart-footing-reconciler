# Evidence-traceability drilldown — Design Spec

**Date:** 2026-06-15
**Project:** 09_dart_footing_reconciler
**Surface:** `report_html.py` evidence_cockpit (also rendered by the PyOdide offline app via the same `_build_html`).
**Design kit:** PAS Workbench / `evidence_cockpit` profile + `interactive-patterns-kit` (inline micro-runtime, no CDN).

## Goal

Make a verification finding traceable to its source: from a finding's inline drilldown, the
auditor sees human-readable source locations and the component math, and can jump to and
highlight the exact source cell in the original-table panel. Primary auditor job: **근거 추적**
(evidence trail / 조서 증빙).

## Non-goals
- No new panel / no cockpit re-architecture (keep the inline-drilldown pattern).
- No change to verification logic, statuses, or counts. Evidence enrichment is **additive**.
- No PDF/print redesign (inherits existing print rules).

## Current state (baseline)
- `_render_drilldown(result)` (report_html.py) shows a table of `result.evidence`
  (`CheckEvidence{label, amount, source}`) with the **raw** source string
  (`note:8/table:28/row:8/col:1`) plus the reason callout.
- Source strings: `statement:{kind}/table:{idx}/row:{i}/col:{c}` and
  `note:{note_no}/table:{idx}/row:{i}/col:{c}`. Panels: `panel-{kind}` / `panel-note-{note_no}`.
  Table rows carry `data-check-row="{i}"`; cells currently have no per-cell address.
- Most checks emit only the operands (1–2 cells); footing/rollforward compute components but do
  **not** attach them to evidence.

Two gaps: (1) raw source string is the primary surface (violates design.md §3 — machine fields
must not lead), and (2) no component math (구성요소 합산 내역).

## Architecture
All changes land in the single renderer `report_html.py` (+ a small evidence-model field in
`checks.py` for Phase 2). The PyOdide offline app reuses `_build_html`, so it inherits everything
with no separate work. Inline micro-runtime only (no external JS), per interactive-patterns-kit.

## Phase 1 — Humanized source + jump/highlight (renderer + inline JS; no engine change)

### 1.1 Source humanization
- Add `_parse_source(source) -> (panel_id, table_key, row, col) | None` parsing the
  `statement:{kind}` / `note:{no}` + `table:{idx}/row:{i}/col:{c}` form.
- Add `_humanize_source(report, source) -> str`: resolve to
  `"{주석N 주제 | 재무제표명} · '{행 라벨}' · {열 헤더}"` using the report's tables
  (`row[0]` = 행 라벨, `rows[0][col]` = 열 헤더). Fall back to the panel/coords label when a
  table/cell can't be resolved (never crash).
- The raw source string moves into a secondary `<details><summary>기술 세부정보</summary>…</details>`
  inside the drilldown (design.md §3: raw machine detail only in secondary areas).

### 1.2 Jump + highlight
- When rendering panel tables (`_render_table_rows`), add `data-cell="r{i}c{c}"` to each `<td>`
  (and keep `data-check-row`). Panels already have stable ids.
- Each humanized source in the drilldown is a clickable control
  (`data-jump="{panel_id}" data-jump-cell="r{i}c{c}"`).
- Source-format robustness: some sources omit `col` (e.g.
  `statement:bs/table:0/row:43`) — those jump+highlight the **row** (existing
  `data-check-row`); sources with `col` highlight the cell. `kind` may be a short code
  (`bs/is/sce/cf`) or a section id; `_parse_source` maps to the panel id the sidebar/panels
  already use (reuse `_section_key`), and falls back to the summary panel when unresolvable.
- Inline JS `jumpToCell(panelId, cellKey)`: activate the target panel (reuse existing panel
  switch), scroll the cell into view, and apply a transient highlight class
  (`.cell-flash`, ~1.2s) using border/background-accent + opacity only (motion rules: no
  layout-animating properties). Cross-panel jumps (fs_note: BS row ↔ note row) work because the
  source encodes the panel.
- Keyboard/click accessible (visible control, not hover-only).

## Phase 2 — Component breakdown (engine evidence enrichment + UI)

### 2.1 Evidence model
- Extend `CheckEvidence` with an optional `role: str = ""` (values: `operand`, `component`,
  `total`, `beginning`, `ending`, `movement`). Backward compatible (default empty).

### 2.2 Engine enrichment (additive only — must not change status/expected/actual/difference)
Attach the already-computed components as `CheckEvidence(role="component", …)` with source coords:
- `checks_totals.py`: `_row_total_results` / `_column_total_results` / `_subtotal_results` —
  the summed component cells (each with its row/col source).
- `note_assertions.py`: `_asset_rollforward_results` — 기초 (beginning), each movement
  (movement, signed), 기말 (ending), with sources.
Operands keep their existing role (`operand`/`total`). No other check is required to enrich in
this phase (fs_note/equity already show both operands).

### 2.3 UI breakdown
- `_render_drilldown` groups evidence by role: a **구성요소 합산** mini-table listing each
  component (humanized source-jump · 금액), a sum line **기대 = Σ**, then **실제 = {total}** and
  **차이 = {difference}**. Each component source uses the Phase-1 jump/highlight.
- When a check has no component evidence (fs_note/equity/parse_uncertain), render the current
  operand list (unchanged).

## Design-kit compliance
- Korean-first labels: `근거 위치`, `기대`, `실제`, `차이`, `구성요소 합산`, `기술 세부정보`.
- Status as point signals only; no new fill colors; highlight flash uses accent border + opacity.
- Self-contained HTML, no CDN; native `<details>` for the raw-detail disclosure.
- First-viewport verdict/KPI unchanged.

## Invariant (the gate)
Evidence enrichment is **purely additive**: `status`, `expected`, `actual`, `difference`, and the
per-status counts must be identical before/after. Verified by (a) unit assertion that a known
fixture's status histogram is unchanged, and (b) the corpus regression (5-status counts unchanged).

## Testing
- **Python (`tests/test_report_html*.py`)**: humanized source string present; raw source only inside
  the `기술 세부정보` disclosure; `data-cell`/`data-jump` attributes present; Phase-2 breakdown
  renders `기대 = Σ` for a footing fixture; drilldown unchanged for operand-only checks.
- **Status-invariance**: assert `assemble_report_checks` status histogram unchanged after Phase-2
  evidence enrichment (same fixture, before/after counts equal).
- **Corpus**: 5-status counts unchanged vs base (additive evidence only).
- **Visual**: render 현대모비스 report → screenshot the drilldown (humanized source + breakdown +
  highlight) for design review.
- **Parity**: `verify_app` inherits `_build_html`; existing E2E parity covers it.

## Files
- `src/dart_footing_reconciler/report_html.py` (renderer + inline JS) — Phase 1 & 2 UI.
- `src/dart_footing_reconciler/checks.py` (`CheckEvidence.role`) — Phase 2.
- `src/dart_footing_reconciler/checks_totals.py`, `note_assertions.py` — Phase 2 component evidence.
- `tests/test_report_html*.py`, `tests/test_*` for status-invariance.
