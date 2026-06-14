# ADR 0007 — Structure-aware footing (section/subtotal + row/column totals)

**Date:** 2026-06-15
**Status:** Proposed (spec written; Codex implementation pending)
**Related:** ADR-0006 (schema), the equity-tie column fix (commit 75f859e)

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
