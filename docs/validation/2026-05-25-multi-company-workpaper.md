# Multi-Company Workpaper Validation

Date: 2026-05-25

## Verdict

Conditional.

The tool now runs as a multi-company workpaper corpus instead of a
CJ대한통운-only prototype. Five public DART filings were fetched, parsed, checked,
and rendered to individual HTML reports in one command. The run exposed
company-agnostic parser and reconciliation gaps that should drive the next
implementation cycle.

## Corpus

Manifest: `out/corpus/manifest_2026-05-25.json`

Command:

```bash
uv run dart-footing workpaper-corpus out/corpus/manifest_2026-05-25.json out/corpus/run_2026-05-25
```

Samples:

| Company | Receipt no. | Report |
|---|---:|---|
| AP시스템 | 20250320001493 | `out/corpus/run_2026-05-25/reports/ap_system_2024.html` |
| CJ제일제당 | 20250317000648 | `out/corpus/run_2026-05-25/reports/cj_cheiljedang_2024.html` |
| DB하이텍 | 20250312001130 | `out/corpus/run_2026-05-25/reports/db_hitek_2024.html` |
| DS단석 | 20250321001800 | `out/corpus/run_2026-05-25/reports/ds_danseok_2024.html` |
| GST | 20250318000728 | `out/corpus/run_2026-05-25/reports/gst_2024.html` |

## Result

Summary artifact: `out/corpus/run_2026-05-25/corpus_report.md`

| Metric | Count |
|---|---:|
| Samples | 5 |
| Generated reports | 5 |
| Failed samples | 0 |
| Total checks | 4,689 |
| Matched | 1,854 |
| Explainable gaps | 6 |
| Unexplained gaps | 897 |
| Parse uncertain | 1,389 |
| Not tested | 543 |
| Primary checks | 49 |
| Primary matched | 30 |
| Primary unresolved | 19 |

Company roll-forward:

| Company | Statements | Notes | Checks | Primary | Primary matched | Primary unresolved |
|---|---:|---:|---:|---:|---:|---:|
| AP시스템 | 8 | 94 | 945 | 10 | 7 | 3 |
| CJ제일제당 | 8 | 87 | 1,249 | 12 | 8 | 4 |
| DB하이텍 | 9 | 92 | 1,124 | 10 | 7 | 3 |
| DS단석 | 8 | 89 | 872 | 10 | 4 | 6 |
| GST | 8 | 74 | 499 | 7 | 4 | 3 |

## Implemented Improvements

1. DART financial-section fetcher added.
   - The runner extracts `III. 재무에 관한 사항` from the DART main page and
     downloads the corresponding viewer HTML.

2. Multi-company corpus command added.
   - `workpaper-corpus` fetches or reuses raw filings, generates one HTML report
     per company, and writes `corpus_result.json` plus `corpus_report.md`.

3. Embedded unit-row parsing fixed.
   - Tables whose first row is repeated `(단위: 천원)` now apply the unit
     multiplier and drop the unit row before table analysis.
   - This materially improved GST: matched checks increased from 40 in the
     first pre-fix run to 130 after the unit and movement fixes.

4. Cash movement false positives reduced.
   - `취득원가` is no longer treated as a cash acquisition movement.
   - `유형자산처분손실` and similar gain/loss rows are no longer treated as
     investing cash-flow disposal proceeds.

5. Period selection generalized.
   - Current/prior period inference now prefers semantic headers and otherwise
     selects the latest and prior `제 N 기` columns.

6. Primary reconciliation candidate filtering improved.
   - Statement-note balances now use net carrying/current-period amount
     selection, including current/non-current trade receivable columns.
   - Note-to-note checks only match multiple candidates when the whole
     candidate set agrees to the same comparable amount.
   - Explicit prior-period tables are excluded from current-period note-to-note
     candidate pools.
   - Depreciation and amortization note-to-note checks compare absolute amounts
     because asset movement tables often present expense movements as negative
     while expense-by-nature tables present positive expense amounts.
   - Updated policy: when note-to-note checks have multiple candidates, the
     whole candidate set must agree to the same comparable amount. A single
     best-matching pair is no longer sufficient because other same-account
     candidates may indicate a scope, account, or table-selection issue.
   - Rounding tolerance now follows the note table unit multiplier. A thousand
     won note gets a 999 won tolerance, a million won note gets a 999,999 won
     tolerance, and won-denominated notes stay effectively exact. This moved
     AP시스템 유형자산 처분 cash-flow reconciliation from matched to
     unresolved because the difference exceeded the source table precision.
   - Cash-flow non-cash adjustment rows are now extracted from `현금의 유입과
     유출이 없는 거래` tables when the row explicitly identifies a PPE or
     intangible acquisition payable. Ambiguous combined labels such as
     `유무형자산` are left out of automatic matching.
   - Financing-liability note tables now read the named `현금흐름` column and
     sum multiple borrowing rows, instead of taking the second numeric cell.
   - Cash-flow bridge formulas now preserve the sign of non-cash payable
     movements in the reviewer-facing formula. A payable decrease is displayed
     as an increase to cash acquisition, not as a misleading subtraction.
   - Expense-by-nature reconciliation now treats asset-note `개발비` components
     as an excluded bridge component only when the remaining functional
     allocation exactly agrees to the expense-by-nature note. This resolved two
     CJ제일제당 primary checks without loosening the match rule.

7. Cash-flow bridge extraction improved.
   - Operating cash-flow note headings such as `영업활동현금흐름` are now used to
     extract disposal gain/loss adjustments.
   - Business-combination acquisition rows are separated from cash acquisition
     rows, while `사업결합을 통한 취득 이외의 증가` remains an acquisition
     candidate.
   - Financing-liability note cash-flow rows continue to support borrowings,
     bonds, and lease liabilities.

8. Scope and unit handling improved.
   - Reports with enough explicit `(연결)` note sections use the consolidated
     note block as the primary note scope, reducing consolidated/separate mixed
     candidates.
   - A table heading unit marker now overrides an earlier inherited unit marker,
     fixing cases where a prior `(단위: 백만원)` marker incorrectly scaled a
     later `(단위: 천원)` table.

9. Statement-source review surface improved.
   - The statement-match section now preserves the source statement rows instead
     of trimming the income statement before `매출액`.
   - Common financial asset rows such as `현금및현금성자산`, `단기금융상품`,
     `장기금융자산`, and `기타금융자산` now classify to canonical accounts
     even when DART row acodes are missing.
   - Statement-note matching now accepts source-table unit rounding. For
     example, a won-denominated statement amount can connect to a 백만원 note
     amount when the difference is only source-unit rounding.
   - Non-financial business-disclosure tables such as `장기체화 재고 등 현황`
     are excluded from the statement-note side panel candidate list.
   - HTML reports now expose a top-level `연결`/`별도` scope selector when both
     reporting layers are present. Statement source tables, coverage rows,
     review queue cards, reconciliation rows, and cash-flow coverage rows are
     tagged by scope so reviewers do not see consolidated and separate
     validation results mixed in one view.

## Gap Classification

| Category | Count | Meaning |
|---|---:|---|
| `parse_uncertain_total` | 1,389 | Generic total footing cannot yet determine a reliable total/subtotal role. |
| `unexplained_total_check` | 892 | Table-local total check disagrees under the current generic total rule. |
| `unexplained_cashflow_reconciliation` | 5 | Cash-flow statement line and note movement still require direct bridge logic. |
| `explainable_cashflow_reconciliation` | 6 | Cash-flow bridge components were found, but the explicit formula still leaves a difference. |

## Required Next Work

Required:

- Build a cash-flow bridge candidate scorer:
  CFS row label, note title, table heading, amount direction, non-cash
  adjustment labels, and connected/separate scope should all contribute to the
  score.
- Split generic total checks from audit primary checks in the UI so reviewers are
  not distracted by parser-development noise.
- Extend cash-flow bridge formulas beyond the current asset/financing set:
  equity transactions, dividends, financial assets, investment property,
  business-combination cash flow, government grants, and interest-related
  investing/financing rows need explicit role mapping.
- Add row-level scope filtering using acode context where title scope is not
  explicit enough.

Recommended:

- Expand this corpus to 20-30 companies only after primary matched rate improves
  on the current five-company set.
- Add a per-company gap drilldown page that lists only primary unresolved items
  before total-check diagnostics.
