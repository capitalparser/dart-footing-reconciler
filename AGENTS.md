# 09_dart_footing_reconciler — Project System Context

This project builds an audit-grade footing and cash flow reconciliation engine
for Korean DART DSD/HTML filings.

## Module Responsibilities

| Module | Responsibility | Location |
|---|---|---|
| Parser | DSD/HTML extraction with source locations and parse uncertainty | `src/` parser modules |
| Footing Engine | Internal table arithmetic checks | `src/` footing/domain modules |
| Reconciliation Engine | Statement body, note, cash flow, note-note, and prior-period comparison | `src/` reconciliation/domain modules |
| Classification | Matched, explainable gap, unexplained gap, parse uncertain | `src/` classification modules |
| CLI/Package | Stable command and package interface for local use | `src/` CLI modules |
| Tests/Fixtures | Golden DSD/HTML fixtures and reconciliation regressions | `tests/` |

## Validation Intent Contract

The canonical verification contract is
`docs/validation/report-verification-contract.md`. Keep this file, README, and
the implementation in sync when adding or changing a validation family.

The intended validation surface has seven distinct lanes:

| Lane | Purpose | Current implementation anchor |
|---|---|---|
| 재무제표 본문 검증 | Validate statement arithmetic and cross-statement ties before looking at notes. | `StatementCrossHarness`, `checks_statement_ties.py` |
| 재무제표와 주석간 대사 | Validate that statement body amounts and referenced note evidence agree, and that note-number references are correct/complete. | `StatementNoteHarness`, `StatementNoteReferenceHarness` |
| 현금흐름표와 주석 대사 | Keep cash-flow reconciliation separate from table-local footing; compare cash-like note movements to CFS lines. | `checks_reconciliation.py`, `checks_cfs_note.py`, `checks_note_bridges.py` |
| 주석 내 검산 | Validate totals, formulas, rollforwards, and source-backed note arithmetic inside the note table itself. | `NoteInternalHarness`, `checks_totals.py`, `layout_formula_assertions.py`, `note_assertions.py` |
| 주석 간 대사 | Validate deterministic source-backed relationships between notes. | `checks_note_note.py` |
| 전기 숫자 검증 | Compare comparative columns and rollforward openings against current/prior filings when `--prior-html` exists. | `PriorReportHarness`, `checks_prior_year.py`, `checks_prior_column.py` |
| 검증 QA | Verify coverage, evidence integrity, frontend display contract, and completion-readiness independently from business result status. | `report_qa.py`, `report_html.py` |

## Data and Evidence Rules

- Every material amount must have `CheckEvidence` with a source coordinate such
  as `statement:bs/table:0/row:16/col:2` or `note:10/table:43/row:7/col:9`.
- Evidence roles (`component`, `total`, `beginning`, `movement`, `ending`) are
  part of the frontend contract. They decide which table cell receives a
  합계검증/formula border and how formula popovers are explained.
- Current-report and prior-report evidence are both valid source catalogs for
  QA when a prior report is supplied.
- Consolidated and separate reports must remain separate verification slices;
  do not let 연결 and 별도 evidence satisfy each other accidentally.
- `검증 QA` passing means the tooling coverage/display contract is satisfied.
  It does not mean all accounting relationships are matched.

## Feature Addition Rules

- Footing and cash flow reconciliation must remain separate checks.
- Every material amount must preserve source location.
- Label mapping uncertainty must be explicit through confidence/evidence.
- Add or update the report-verification contract when a new check family,
  evidence role, frontend display behavior, or completion criterion is added.
- Render high-signal validation next to the relevant source number. For
  합계검증/formula/rollforward checks, mark the result cell inside the original
  table when the source coordinate exists.
- The core reconciliation engine must run without MCP.
- MCP wrappers may expose the engine only after the CLI/package contract is
  stable.

## Verification

- Run `uv run pytest` for default tests.
- Parser changes require fixture coverage for source location and uncertainty.
- Workpaper/frontend changes require rendered HTML verification. Prefer serving
  the generated file over localhost HTTP; `file://` is not sufficient for the
  browser-wrapper proof path.
- QA/completion changes require `qa-report` or `workpaper-html` evidence that
  `검증 QA`, `백엔드-프론트 표시 계약`, and `작업 완료 기준` render correctly.
