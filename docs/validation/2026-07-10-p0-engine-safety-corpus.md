# P0 Engine Safety — Corpus Gate

**Date:** 2026-07-10
**Branch:** `fix/p0-engine-safety`
**Manifests:** 10-company nonfinancial corpus + 8-company expansion corpus

## Result

Both cached manifests generated successfully (`10/10`, `8/8`, failures `0`). No check type other than `note_note_match` changed its per-company count. There were no added note-relation results.

| Corpus | Total | Matched | Explainable | Unexplained | Parse uncertain | Not tested |
|---|---:|---:|---:|---:|---:|---:|
| 10-company delta | -2 | 0 | 0 | 0 | -2 | 0 |
| expansion delta | -6 | -1 | 0 | 0 | -5 | 0 |

The one removed matched result was a confirmed same-cell self-reconciliation, not a genuine match.

## Removed relations

| Company | Removed | Triage |
|---|---|---|
| 셀트리온 | `tax_temporary_difference` parse-uncertain ×2 | Both rule sides resolved to the same candidate source set inside the same deferred-tax note. No independent right-side fact existed. |
| CJ제일제당 | `tax_temporary_difference` parse-uncertain ×2 | Both rule sides resolved to the same candidate source set inside the same deferred-tax note. No independent right-side fact existed. |
| 대한항공 | `lease_liability_current_noncurrent` parse-uncertain ×2 | Each scope had `비유동 리스부채의 유동성대체부분` plus `비유동 리스부채`, but no direct `유동 리스부채` balance row. The first label contains both level tokens and is now `unknown`; the relation correctly abstains. |
| 아모레퍼시픽 | `tax_temporary_difference` matched ×1 | Left and right evidence were the exact same cell (`note:24/table:328/row:1/col:1`). This was a false match. |
| 아모레퍼시픽 | `tax_temporary_difference` parse-uncertain ×1 | Both rule sides resolved to the same two sources in one deferred-tax note. No independent right-side fact existed. |

## Genuine-match preservation

The two existing Hanwha Ocean depreciation matches remain byte-identical in status, amounts, and evidence sources:

- `note_note:depreciation_expense:14:32`, `115,934,000,000`;
- `note_note:depreciation_expense:14:32`, `133,635,000,000`.

No existing genuine `note_note_match` was destroyed. The expansion corpus's only pre-change note-relation matched result was the Amorepacific same-cell false match above.

## Prior-report blind spot

The corpus runner supplies no prior report, so it cannot exercise the basis guard. Pipeline-level synthetic regressions cover:

- consolidated current vs separate prior → abstain;
- any unknown side → abstain;
- exact consolidated/consolidated and separate/separate → prior match preserved;
- dual-basis prior report → exact current basis slice selected.

## Snapshot deltas accepted by this safety correction

- 10-company baseline: 셀트리온 `parse_uncertain 61 → 59`.
- expansion baseline:
  - CJ제일제당 `parse_uncertain 46 → 44`;
  - 대한항공 `parse_uncertain 49 → 47`;
  - 아모레퍼시픽 `matched 401 → 400`, `parse_uncertain 39 → 38`.

No other company/status count changes.
