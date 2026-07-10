# 10-Company Validation QA Status

Date: 2026-07-08

## Scope

This run addressed the repeated validation-report gaps around total-check
surfacing, note-to-note references, and financial-statement-to-note displayed
references without adding company-specific routing.

Sample manifest:
`out/corpus/manifest_2026-06-10-nonfinancial-industry-10.json`

Samples:

| Company | Selection tag |
|---|---|
| 삼성SDI | 배터리/전자소재 제조 |
| 현대자동차 | 완성차 |
| 셀트리온 | 바이오/제약 |
| 롯데쇼핑 | 유통/리테일 |
| 현대건설 | 건설 |
| SGC에너지 | 에너지/발전 |
| CJ대한통운 | 물류 |
| 더존비즈온 | 소프트웨어/IT서비스 |
| 롯데정밀화학 | 정밀화학 |
| 한화오션 | 조선 |

## Status

- Implemented generalized reference extraction and a DB-shaped semantic
  reference fact layer.
- Rewired statement-note reference checks to consume semantic facts instead of
  label-only parsing.
- Fixed report surfacing for appropriation formula total evidence so the closing
  amount receives the same total-check border treatment.
- Re-ran the 10-company QA and full test suite.

## Root Cause Findings

### Total-check borders

Total checks were already running. The baseline QA emitted 6,588
`total_check`-family items and 9,199 checks overall. The visible omission came
from the report surface contract:

- `appropriation_formula_check` was handled as total coverage by QA, but was not
  included in the HTML total-surface check type set.
- The closing evidence cell for `appropriation_formula_check` was not treated as
  the target total cell.
- Raw DART table annotation depends on parser-injected cell keys, which are
  already present through `document.py`; the missing part was the report target
  classification.

Fixes:

- `src/dart_footing_reconciler/report_html.py`
  - Added `appropriation_formula_check` to total-surface check types.
  - Marked the final evidence item in `appropriation_formula_check` as the
    target total cell.
- `tests/test_report_html_evidence.py`
  - Added coverage that the closing cell receives `total-cell total-ok`.

### Note reference extraction

The reference checks were missing valid references because extraction was split
across narrow, local routines:

- `note_reference_validator.py` scanned text blocks but did not scan table
  cells.
- Statement-note reference logic only recognized narrow inline variants, missing
  common forms such as `주석 12`, `주 12 및 14`, `Note 5 and 17`, and separate
  note-reference columns.
- A first broad pass found more references but also created false positives from
  patterns such as `[주1]` table markers and stock-share text like `보통주
  3,343,585주`. The final implementation tightened bare `주` handling and
  excludes `[주1]`-style table footnote markers.

Fixes:

- `src/dart_footing_reconciler/note_reference_validator.py`
  - Added reusable `extract_note_ref_tokens()` and
    `extract_plain_note_ref_tokens()`.
  - Added table-cell scanning, including plain numeric values under note
    reference headers.
  - Normalizes subsection references such as `17(2)`, `4.1.2`, and `12-1` to
    the primary note number for section existence checks.
- `tests/test_note_reference_validator.py`
  - Added positive cases for Korean and English variants.
  - Added regression coverage for `[주1]` and stock-share false positives.

### DB and semantic layer

The repository already had semantic table and amount facts, but displayed note
references were not normalized as queryable facts. This made downstream logic
depend on ad hoc label parsing and made it hard to reason about reference source
location, confidence, and scope.

Fixes:

- `src/dart_footing_reconciler/semantic_layer.py`
  - Added `SemanticNoteReferenceFact`.
  - Added `SemanticDataset.note_references` and
    `note_references_for_row(source)`.
  - Builds reference facts from all parsed tables, including explicit inline
    references and plain note-number cells under headers such as `주석`,
    `관련주석`, `Note`, and `註`.
- `src/dart_footing_reconciler/statement_note_reference_harness.py`
  - Uses semantic note-reference facts for statement rows.
  - Keeps label parsing only as a fallback.
  - Carries exact displayed-reference cell source into evidence.
- `tests/test_semantic_layer.py`
  - Added coverage for semantic note reference facts from separate note columns
    and inline labels.
- `tests/test_statement_note_reference_harness.py`
  - Added coverage for separate note columns and `주석 12` label variants.

## 10-Company QA

Commands:

```bash
uv run dart-footing workpaper-corpus out/corpus/manifest_2026-06-10-nonfinancial-industry-10.json out/corpus/run_2026-07-08-goal-10qa-baseline --no-fetch
uv run dart-footing workpaper-corpus out/corpus/manifest_2026-06-10-nonfinancial-industry-10.json out/corpus/run_2026-07-08-goal-10qa-after2 --no-fetch
uv run pytest
```

Artifacts:

- Baseline report:
  `out/corpus/run_2026-07-08-goal-10qa-baseline/corpus_report.md`
- Final report:
  `out/corpus/run_2026-07-08-goal-10qa-after2/corpus_report.md`
- Final HTML reports:
  `out/corpus/run_2026-07-08-goal-10qa-after2/reports/`

## QA Summary

| Metric | Baseline | Final | Delta |
|---|---:|---:|---:|
| Generated reports | 10 | 10 | 0 |
| Failed samples | 0 | 0 | 0 |
| Total checks | 9,199 | 10,092 | +893 |
| Matched | 7,894 | 8,774 | +880 |
| Explainable gaps | 25 | 25 | 0 |
| Unexplained gaps | 931 | 944 | +13 |
| Parse uncertain | 346 | 346 | 0 |
| Not tested | 3 | 3 | 0 |
| Primary checks | 144 | 144 | 0 |
| Primary matched | 99 | 99 | 0 |
| Primary unresolved | 45 | 45 | 0 |
| Note assertion checks | 1,412 | 2,305 | +893 |
| Note assertion matched | 1,279 | 2,159 | +880 |
| Note assertion unresolved | 117 | 130 | +13 |
| Note reference checks | 251 | 1,144 | +893 |
| Unexplained note reference checks | 9 | 22 | +13 |
| Validated note tables | 2,095 | 2,124 | +29 |
| Unvalidated note tables | 2,651 | 2,622 | -29 |
| Validation-relevant unknown layout items | 369 | 369 | 0 |

Interpretation:

- The added note-reference coverage generated 893 more checks across the same
  10-company sample.
- 880 of the 893 added checks matched automatically.
- The 13 additional unresolved items are newly surfaced coverage, not a primary
  reconciliation regression. Primary check counts and outcomes were unchanged.
- The first broad extraction pass produced 1,073 additional reference checks but
  had false positives. The final pass reduced that to 893 higher-confidence
  checks after tightening bare `주` parsing and `[주1]` exclusion.

## Remaining Work

The current work improves reference extraction and report surfacing, but does
not close all validation gaps.

| Area | Current evidence | Next action |
|---|---|---|
| Total formulas | `unexplained_total_check` 439 and `parse_uncertain_total` 346 remain | Improve table role detection for subtotal/total/book-value columns and formula templates. |
| Statement-note references | `statement_note_reference_accuracy` 111 and `statement_note_reference_completeness` 97 remain | Add account/topic evidence expansion and scope-aware statement/note index matching. |
| Primary reconciliation | Primary unresolved remains 45 | Use `out/corpus/run_2026-07-08-goal-10qa-after2/primary_unresolved_taxonomy.md`: 32 `direct_evidence_missing`, 13 `formula_template_missing`; 40 are cash-flow reconciliation items. |
| Note reference leftovers | `note_reference_check` unresolved is 22 | Review parser/index scope for empty or missing note bodies. Company counts: 롯데정밀화학 13, 셀트리온 4, SGC에너지 2, 한화오션 2, CJ대한통운 1. |
| Layout coverage | 4,167 unknown/low-confidence layout candidates, 369 validation-relevant | Promote common schemas into semantic table layout variants rather than company-specific rules. |

Observed leftover pattern:

- Several `주석 3` references point to a note section that exists but is parsed
  as empty in affected filings. This is a parser/section-content issue, not a
  reference-token issue.
- 롯데정밀화학 has many statement references to notes 32/33; the remaining
  failures appear to be note-index or scope selection issues where the displayed
  reference is real but the active section set does not resolve it cleanly.

## Verification

- Focused regression tests for the changed areas passed during development.
- Full suite result after the status report update:
  `1078 passed, 1 skipped in 52.16s`.

Operational note:

- `python -m dart_footing_reconciler.cli` currently produces no output because
  `cli.py` has no module entrypoint. Use the installed console command:
  `uv run dart-footing ...`.
