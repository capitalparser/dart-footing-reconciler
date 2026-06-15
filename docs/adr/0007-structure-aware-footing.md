# ADR 0007 — Structure-aware footing (section/subtotal + row/column totals)

**Date:** 2026-06-15
**Status:** Accepted — implemented + corpus-verified (2026-06-15)
**Related:** ADR-0006 (schema), the equity-tie column fix (commit 75f859e)

## Outcome (2026-06-15)

Implemented in `checks_totals.py`: total-column (row-wise) footing, section/subtotal
footing, and abstention guards (single rightmost 합계 column; abstain on grouped
super-headers / multiple 합계 columns / nested-subtotal duplicate-leaf headers;
per-column dedup of repeated 합계 headers; column-total requires ≥2 components;
multi-section guard counts only amount-bearing subtotals; `_total_row` must have a real
amount). Tests in `tests/test_checks_totals_structure.py`; full suite 760 passed,
1 skipped; ruff clean.

**Corpus regression gate — PASSED** (manifest_2026-06-10-nonfinancial-industry-10, 10
companies), before (pre-feature) → after:

| status | before | after | Δ |
|---|---:|---:|---:|
| matched | 4,124 | 4,731 | +607 |
| explainable_gap | 10 | 10 | 0 |
| unexplained_gap | 612 | 557 | −55 |
| parse_uncertain | 569 | 500 | −69 |
| not_tested | 3,074 | 2,966 | −108 |
| total_checks | 8,389 | 8,764 | +375 |

unexplained_gap fell (no false-positive inflation) while matched rose +607 — a strict
corpus-wide improvement. Spot acceptance on 현대모비스: unexplained_gap 66→47,
total_check gaps 23→4 (all confirmed FPs eliminated: 배당주식수/공정가치/세그먼트/
계약부채/법인세/투자부동산 운영비용); 매출채권 두 소계 matched; 차입금/사채 flat
합계 matched; equity-ties matched.

**Known residual (follow-up):** (1) 비파생금융부채-type liquidity tables where
|components| == |total| but the disclosed 합계 is negative — kept as a legitimate
"does not tie as presented" flag (sign-tolerant footing would risk hiding real sign
errors). (2) column-total base-row reconciliation tables (a non-additive base row above
the total) need reconciliation-table semantics; deferred to avoid suppressing genuine
footing.

## Context

A row-level audit of 현대모비스 (2024) verification output exposed that the footing
engine recognizes only ONE total shape — a **total ROW** (소계/합계/총계 labeled row
with components summed above it). Real DART note tables use several shapes the engine
mishandles, producing both missed checks and false discrepancies:

1. **Total is a COLUMN, not a row** — e.g. 차입금/사채, 영업부문, 위험관리: each amount
   row's component columns sum to a 합계 column (degenerate header, e.g. last column
   "차입금명칭 합계"). No total ROW exists → engine emits `parse_uncertain`
   ("no reliable total label found"). 현대모비스: ~56 parse_uncertain, clustered here.

2. **Multiple subtotals, NO grand total** — e.g. 매출채권(주석8): a 유동 section (소계)
   and a 비유동 section (소계), no grand total. The engine picks the LAST subtotal as
   "the total" and sums ALL rows (both sections) against it → large false
   `unexplained_gap`. Confirmed: each section subtotal actually foots exactly; the gap
   is an artifact (현대모비스 매출채권: 6 false gaps; suspected across the ~42
   footing/rollforward gaps).

3. **Matrix row total is the rightmost column** — already fixed narrowly for the
   SCE 기말 row in equity-tie (75f859e); the general case is the same family.

All three are one capability gap: **the footing engine cannot segment a table into
sections/subtotals and cannot detect a total that lives in a column.**

## Decision

Build **structure-aware footing**: extend the totals layer to recognize, in priority
order, (a) section/subtotal blocks (foot each section's components to its own subtotal),
and (b) total **columns** (row-wise footing: components-across-columns = 합계 column),
in addition to the existing total-row footing.

This is implemented under a hard **no-new-false-positives** constraint and validated by
a **corpus regression** (before/after on the baseline manifest), not just unit tests.

## Why (not a heuristic patch)

The footing engine feeds an audit verdict; a wrong total identification produces either
a false "검토 필요" (erodes trust) or a missed gap (worse). The fix must be
structure-grounded and abstain when ambiguous (emit nothing / `parse_uncertain` rather
than guess). A quick heuristic risks false positives across the whole corpus + 747-test
suite, so it is scoped as a TDD feature with mandatory corpus regression measurement.

## Consequences

- **+** Recovers many `parse_uncertain` (column-total tables) into real matched/gap
  results; removes false `unexplained_gap` from multi-subtotal tables → verdict reflects
  reality. Coverage (`not_tested`) and abstention (`parse_uncertain`) stay honest.
- **−** Adds detection logic with its own edge cases (degenerate headers, rate rows,
  nested subtotals). Mitigated by abstention-first design + corpus gate.
- Acceptance (현대모비스): 매출채권 소계 → matched (was false gap); 차입금/사채 합계-column
  rows → matched (was parse_uncertain); equity-tie stays matched.

## Alternatives rejected

- **Tune the existing total-ROW heuristic only** — cannot represent column totals or
  multi-section subtotals; would keep mislabeling.
- **Ship a narrow heuristic now without corpus validation** — violates the no-blind-patch
  rule; unacceptable false-positive risk on an audit verdict.
