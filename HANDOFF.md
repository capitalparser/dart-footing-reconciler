# HANDOFF.md — Structure-aware footing

**Branch:** `feat/structure-aware-footing` (from `audit-workpaper-note-reconciliation`, already checked out)
**Primary executor:** Codex (files + tests + corpus run)
**Git owner:** Claude (Codex sandbox cannot write `.git`; Claude commits after each verified batch)
**Verifier:** Claude (spec compliance + corpus-regression review)

---

## Read first (in order)
1. `docs/adr/0007-structure-aware-footing.md` — the decision + diagnosis evidence.
2. `docs/superpowers/specs/2026-06-15-structure-aware-footing.md` — full design (this is the contract).

## Objective
Extend `src/dart_footing_reconciler/checks_totals.py` so footing recognizes **total
columns** (row-wise: components-across-columns = 합계 column) and **section/subtotal
blocks** (foot each section's components to its own subtotal), in addition to the existing
total-ROW path — under a hard **no-new-false-positives** constraint.

## Why (root cause, already diagnosed on 현대모비스 2024)
- 차입금/사채·영업부문·위험관리: 합계 is a COLUMN, not a row → engine emits `parse_uncertain`.
- 매출채권(주석8): two subtotals (유동/비유동), no grand total → engine treats the last
  subtotal as a grand total over ALL rows → FALSE `unexplained_gap` (each subtotal actually
  foots). Confirmed false.

## Hard rules
- **Abstain over guess.** When a 합계 column / subtotal scope is ambiguous, emit nothing
  (fall back to existing `parse_uncertain`). NEVER fabricate a total. Fewer high-confidence
  checks > more guesses.
- Do NOT change: the equity-tie fix (`checks_statement_ties.py`), the report renderer, the
  existing total-ROW path. `tests/test_checks_totals.py` must stay green.
- Skip non-amount rows (e.g. 기준이자율 rate rows) from any sum.
- Dedup: never emit two checks for the same (table, row, col) target.

## Tasks (TDD — RED before GREEN, per spec §5)
1. `tests/test_checks_totals_structure.py`: write the 8 failing tests in spec §5 first.
2. Implement total-column footing (`_total_column_results`) — spec §3.1.
3. Implement section/subtotal footing (`_section_total_results`) — spec §3.2.
4. Wire orchestration + dedup into `check_table_totals` — spec §3.3.
5. `uv run pytest -q` green (no regression; new tests pass).

## Done criteria
- `uv run pytest -q` — all pass (was 747 passed, 1 skipped; add the new tests).
- `uv run ruff check` clean on changed files.
- **Corpus regression (mandatory, spec §6):** run the baseline manifest under `out/corpus/`
  before AND after; report `parse_uncertain ↓`, `matched ↑`, and **`unexplained_gap` does
  NOT rise from new false positives** (any net-new gap must be confirmed a GENUINE
  discrepancy, not a structure artifact). Put the before/after counts in your report.
- Spot acceptance on 현대모비스 (`out/corpus/run_2026-06-08-statement-ties-baseline/raw/현대모비스_2024_20250311001180.html`):
  매출채권 두 소계 → matched (was false gap); 차입금/사채 합계-column rows → matched (was
  parse_uncertain); both equity-ties stay matched.

## Division of responsibility
| Role | Does |
|---|---|
| **Codex** | Create/edit files, run `pytest` + `ruff` + the corpus regression, report counts/deltas. Does NOT run git. |
| **Claude** | Commit after verified batches; review corpus delta for false positives. |

Report after implementation: files changed, pytest pass/fail, ruff, and the corpus
before/after status histogram (matched / explainable_gap / unexplained_gap /
parse_uncertain / not_tested).
