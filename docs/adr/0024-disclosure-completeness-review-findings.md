# 0024. Disclosure-completeness lease slice — code review findings

**Date:** 2026-06-30
**Status:** Accepted — review findings fixed; corpus FP review re-run.
**Scope:** Reviewer Lens advisory only (`disclosure_completeness.py`). Builds on ADR-0023.
**Inputs:** 2-leg review of commit `8053339` (`Add lease disclosure completeness advisory`).
- Leg (a) false-positive / reviewer-memo risk review — verdict **REQUEST CHANGES**.
- Leg (b) abstain-coverage / accounting-reader review — verdict **REQUEST CHANGES**.

## Why this ADR exists

The first implementation correctly kept `disclosure_omission_candidate` outside `CheckResult` and the
5-status verdict surface. Both review legs nevertheless found the same precision problem: when a filing
contains a lease/liability maturity table with weak parser structure, the engine could fail to recognize
the table as present-or-ambiguous and emit a reviewer memo. That is the exact false-positive shape ADR-0023
was designed to avoid.

The accounting decision is: **a maturity-analysis-like table that the parser cannot confidently read is
not an omission candidate. It is parser/layout improvement evidence.**

## Findings & fixes

### F-1 — weak multi-row / annual-column maturity tables could become omission memos

The ambiguous-table fallback inspected only `NoteTableInventoryItem` title, heading, first-row headers,
and first-column row labels. This missed real disclosure shapes where:

- maturity buckets live in a second header row after blank or repeated headers;
- the heading says `잔존만기` or `만기별`, not only `만기분석` / `계약상만기`;
- period columns are annual schedules such as `2025년`, `2026년`, `2027년`, `2028년 이후`.

Because the same table could still include an explicit `리스부채` amount row, the trigger fired while the
expected-disclosure search missed the table, producing a false-positive reviewer memo.

**Fix:** `_is_lease_maturity_like_table()` now inspects the raw `ReportTable.rows` in addition to the
inventory summary, treats `잔존만기` / `만기별` headings as maturity-like, scans all cells for maturity
buckets, and treats repeated annual year columns as an ambiguous maturity schedule. These paths suppress
the omission memo and emit interpretation backlog evidence instead.

**Regression pins:**
- multi-row blank-header bucket table -> backlog, no memo;
- `잔존만기` annual-column table -> backlog, no memo.

### F-2 — observed amount evidence was not follow-up usable enough

The initial memo evidence was a formatted string such as `리스부채 @ note/table/row/col`. That preserved a
rough location, but it did not carry the raw value, parsed amount, unit multiplier, or typed source
location. A reviewer memo saying "리스부채 금액은 확인" should let the accountant see exactly which amount
caused the expectation.

**Fix:** observed evidence is now structured as `ObservedAmountEvidence` with label, raw cell value,
parsed amount, scaled amount, unit multiplier, and `SourceLocation` with row/column coordinates.

## Corpus effect after review fixes

The 18-company nonfinancial smoke set was re-run over:

- `out/corpus/manifest_2026-06-10-nonfinancial-industry-10.json`
- `out/corpus/manifest_2026-06-22-nonfinancial-expansion.json`

Final result:

- **Reviewer memos:** 0.
- **Interpretation backlog:** 17 tables across 셀트리온, CJ대한통운, 삼성전자, POSCO홀딩스, 아모레퍼시픽.

POSCO홀딩스 moved from a plausible low-priority memo to interpretation backlog because the filing has a
non-derivative financial-liability maturity-analysis-like table. The parser cannot yet interpret that table
confidently as lease-liability maturity disclosure, so the correct ADR-0023 behavior is to suppress the
omission candidate and record parser/layout improvement evidence.

## Residuals

- The backlog intentionally contains period/scope sibling tables (for example 당기/전기, 연결/별도). A future
  parser/layout slice should add fixtures for these real tables and then collapse or interpret them, rather
  than displaying them as reviewer omission prompts.
- The durable storage/reporting surface for reviewer memos remains a later slice. This commit exposes the
  reviewer-lens helper and keeps it outside the deterministic check pipeline.

## Verification

- Full suite: `uv run pytest` -> 911 passed / 1 skipped.
- Focused disclosure tests: `uv run pytest tests/test_disclosure_completeness.py` -> 11 passed.
- Related disclosure/package/layout/candidate tests: `uv run pytest tests/test_disclosure_completeness.py tests/test_package.py tests/test_layout_variants.py tests/test_verification_candidates.py` -> 150 passed.
- Ruff: `uv run ruff check src/dart_footing_reconciler/disclosure_completeness.py tests/test_disclosure_completeness.py tests/test_package.py src/dart_footing_reconciler/__init__.py` -> clean.
