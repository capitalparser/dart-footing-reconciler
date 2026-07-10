# Report Verification Contract

This document defines the intended verification logic for
`dart-footing-reconciler` and compares it with the current implementation.
It is the reference contract for report workpapers, QA coverage, and future
check-family changes.

## Goal

The engine validates source-backed numeric relationships inside Korean DART
DSD/HTML filings. It does not certify the financial statements and it does not
replace audit judgment. Its job is to show, near the relevant source number,
whether a relationship is matched, explainable, unresolved, parse-uncertain, or
outside the tested scope.

The intended reader workflow is:

1. Read the original financial statement or note table in report order.
2. See high-signal validation state next to the relevant row or cell.
3. Open the evidence rail only when the reviewer needs the compared source,
   amount, reason, or next action.
4. Use `검증 QA` to confirm that the required validation families, source
   coordinates, frontend display contract, and completion criteria ran.

## Data Lineage Contract

Every material amount must preserve a source coordinate. Source coordinates are
the link between parser output, check results, QA, and rendered workpaper cells.

| Source form | Meaning |
|---|---|
| `statement:bs/table:0/row:16/col:2` | Financial statement body amount |
| `statement:현금흐름표/table:3/row:18/col:1` | Statement source using a Korean statement name |
| `note:10/table:43/row:7/col:9` | Note table amount |
| `note:11/current` | Note-level current-period source when exact cell evidence is not available |
| `note:32/table:401/ending` | Current-report role-level source such as beginning or ending balance |
| `prior:note:10/current` | Prior-report current-period source used as the baseline for current comparative-period reconciliation |
| `prior:note:10/table:5/ending` | Prior-report role-level source used as the baseline for current beginning-balance reconciliation |

Evidence roles drive table marking and formula explanation:

| Role | Intended use |
|---|---|
| `component` | Input to a subtotal, rollforward, or formula |
| `total` | Displayed target/result cell that should receive a table border |
| `beginning` | Rollforward opening balance |
| `movement` | Rollforward movement row |
| `ending` | Rollforward ending/result balance that should receive a table border |

Current implementation: source coordinates and roles are represented by
`CheckEvidence` in `src/dart_footing_reconciler/checks.py`. HTML rendering uses
these fields to connect validation results back to statement rows and note cells
in `src/dart_footing_reconciler/report_html.py`.

## Validation Families

| Family | Intent | Current implementation | Current status |
|---|---|---|---|
| 재무제표 본문 검증 | Validate arithmetic and cross-statement ties inside the primary statements. | `StatementCrossHarness` runs `statement_bs_equation`, `statement_subtotal`, `statement_cash_tie`, and `statement_equity_tie`. | Implemented for detected statement tables and known statement kinds. |
| 재무제표와 주석간 대사 | Compare financial statement body rows and note evidence in both directions: body-to-note amount matching and note-reference correctness/completeness. | `StatementNoteHarness` runs primary balance, FS-note, CFS-note, asset bridge, and prior-column checks. `StatementNoteReferenceHarness` checks note-number accuracy/completeness. | Implemented for source-backed account families; ambiguous labels must remain explicit. |
| 현금흐름표와 주석 대사 | Keep cash-flow reconciliation separate from table-local footing. Compare cash-like note movements to investing/financing cash flow lines after excluding non-cash movements where evidence supports it. | `check_reconciliation_targets`, `check_cfs_note_matches`, and `check_asset_note_bridges` emit `cashflow_reconciliation`, `cfs_note_match`, and `asset_note_bridge_check`. | Implemented for high-value families such as PPE, intangibles, borrowings, bonds, leases, and related movement tables. |
| 주석 내 검산 | Validate arithmetic inside a note table or note-derived formula without claiming that the statement tie is complete. | `NoteInternalHarness` runs `total_check`, `note_layout_formula_check`, `note_rollforward_check`, and appropriation formula checks. | Implemented. Result cells are rendered as borders inside the original note table where source cells are available. |
| 주석 간 대사 | Compare source-backed note disclosures against other note disclosures when the relationship is deterministic. | `check_note_note_matches` emits `note_note_match`. | Implemented for known semantic pairs; not a general free-text cross-reference engine. |
| 전기 숫자 검증 | Compare current comparative columns, current rollforward openings, and current structure against the prior filing when prior evidence is provided. | `PriorReportHarness` runs `check_prior_year_reconciliation`; `check_prior_column_matches` compares current note openings to prior-period statement rows. | Implemented when `--prior-html` is supplied. Prior-report source coordinates are included in QA source lookup. |
| 검증 QA | Check whether required validation families ran and whether the report can be considered complete from a tooling standpoint. | `report_qa.py` emits `statement_body_coverage`, `fs_note_coverage`, `note_note_coverage`, `cashflow_coverage`, `prior_period_coverage`, `total_coverage`, `evidence_integrity`, `frontend_contract`, and `completion_readiness`. | Implemented in CLI JSON and HTML `검증 QA` panels. |

## Status Vocabulary

Check results use the canonical five-status model from
`src/dart_footing_reconciler/checks.py`.

| Status | Meaning |
|---|---|
| `matched` | The compared amounts agree within tolerance. |
| `explainable_gap` | A difference exists, but source-backed disclosed adjustments explain it. |
| `unexplained_gap` | A difference remains and needs reviewer follow-up. |
| `parse_uncertain` | The engine found a plausible target but source extraction, table shape, or label confidence is too weak. |
| `not_tested` | The relationship is outside the current tested scope or lacks a reliable target. |

`검증 QA` pass/fail is separate from business-result status. A report can pass
QA while still containing `unexplained_gap` items that require audit follow-up.

## Frontend and Workpaper Contract

The HTML workpaper is part of the verification surface, not a cosmetic export.
The frontend must display the backend contract faithfully:

- Original DART statement and note content stays visible.
- Statement body validation appears beside the relevant statement row.
- 주석 내 합계검증, layout formula, and rollforward result cells are marked
  inside the original note table with colored borders and formula popovers.
- The right evidence rail shows source comparison details without replacing
  the original table. Prior-report evidence is labeled as `전기 보고서 ...` and
  is not linked to current-report source panels.
- `검증 QA` remains visible in the sidebar and body panel, including
  `백엔드-프론트 표시 계약` and `작업 완료 기준`.

Current implementation: `workpaper-html` renders split 연결/별도 reports, source
tables, status filters, reviewer backlog, QA coverage, and total-cell borders.
Browser verification should be done over localhost HTTP for generated reports;
`file://` is not a sufficient proof path for the browser wrapper.

## Current Implementation Boundaries

Implemented now:

- Source-backed parsing of DART viewer HTML into `FullReport`, statements,
  notes, and tables.
- Harness-level orchestration through `assemble_report_checks`.
- Consolidated/separate slicing with matching prior-report slices where possible.
- Statement body, statement-note, note-internal, note-note, prior-report, and
  QA coverage layers.
- Reviewer-facing HTML and Excel workpaper surfaces.

Still bounded:

- The engine is not a full K-IFRS disclosure completeness validator.
- Accuracy is not measured by report count; use the Gold Set, stratified smoke,
  broad corpus, and adversarial sets from
  `docs/validation/verification-accuracy-strategy.md`.
- Unknown layouts and ambiguous labels should abstain or surface
  `parse_uncertain`, not guess.
- PDF/OCR-first extraction and MCP hosting are outside the core engine contract.
- Final accounting or audit conclusions remain reviewer responsibility.

## Code Map

| Contract area | Main implementation |
|---|---|
| Check model and statuses | `src/dart_footing_reconciler/checks.py` |
| Harness orchestration | `src/dart_footing_reconciler/check_pipeline.py` |
| Statement body checks | `src/dart_footing_reconciler/checks_statement_ties.py` |
| Statement-note and cash-flow checks | `src/dart_footing_reconciler/statement_note_harness.py`, `checks_fs_note.py`, `checks_cfs_note.py`, `checks_reconciliation.py` |
| Note-internal checks | `src/dart_footing_reconciler/note_internal_harness.py`, `checks_totals.py`, `layout_formula_assertions.py`, `note_assertions.py` |
| Note-reference correctness/completeness | `src/dart_footing_reconciler/statement_note_reference_harness.py` |
| Prior-report checks | `src/dart_footing_reconciler/supporting_harnesses.py`, `checks_prior_year.py`, `checks_prior_column.py` |
| QA coverage and completion gate | `src/dart_footing_reconciler/report_qa.py` |
| HTML workpaper display contract | `src/dart_footing_reconciler/report_html.py` |
