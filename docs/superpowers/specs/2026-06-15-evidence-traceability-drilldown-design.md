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

## Phase 0 — Panel correctness & label clarity (renderer-only; do first)

Live review of the current dashboard surfaced two render bugs that must be fixed before the
drilldown work, because they affect what evidence is shown at all.

### 0.1 Statement account verifications are orphaned (not shown)
`_section_key` maps a check to a panel via its first evidence source. fs_note account checks
(유형자산/무형자산/투자부동산/차입금/매출액/법인세/주당이익/배당 — 16 on 현대모비스) carry
sources like `statement:재무상태표/...` (Korean section id), so `_section_key` returns
`"재무상태표"`, but statement panels are keyed `bs/is/oci/sce/cf` (and statement-tie checks use
`statement:bs/...`). Result: the account-level verifications land under a key no panel reads and
are **never displayed**. Fix: normalize statement keys in `_section_key` —
`재무상태표→bs, 손익계산서→is, 포괄손익계산서→oci, 자본변동표→sce, 현금흐름표→cf` (keep the
existing short codes). Then the 16 fs_note account verifications appear in their statement panel's
검증 결과.

### 0.2 Note title duplication in check labels
Check titles (esp. parse_uncertain total_check) embed the full table heading, e.g.
`"4. 영업부문 (연결) 보고부문에 대한 공시 ... total check"`, which repeats the panel title
`"4. 영업부문 (연결)"`. Fix at render time: strip the leading note-no/section-title prefix from a
check's displayed title when it is shown inside that note's panel (the panel already names the
note). Keep the distinguishing tail (e.g. `보고부문에 대한 공시 합계검증`). Also translate the
trailing English `total check` / `column total` to Korean (`합계검증`) per design.md §3.

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
- **Phase 0**: a fixture with fs_note account checks renders them in the **statement** panel's
  검증 결과 (not orphaned); statement-tie + fs_note both appear in the same statement panel; note
  check titles inside a note panel do not repeat the note-no/title prefix. `_section_key`
  normalization unit test (재무상태표→bs etc.). Phase 0 changes only WHERE/HOW checks display —
  status/counts unchanged.
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
