# Structure-aware footing — Design Spec

**Date:** 2026-06-15
**ADR:** `docs/adr/0007-structure-aware-footing.md`
**Scope:** Extend `checks_totals.py` to foot two table shapes it currently mishandles —
**total columns** (row-wise) and **section/subtotal blocks** — under a no-new-false-
positives constraint, validated by corpus regression.

---

## 1. Current behavior (baseline — do not break)

`check_table_totals(table, *, note_no, tolerance)` today:
- `_requires_total_check(table)` = `_has_amounts` ∧ `_summable_structure` ∧
  `classify_validation_relevance(...).validation_relevant`.
- If a check is required but no total ROW is found → `PARSE_UNCERTAIN`
  (reason "no reliable total label found"). Else → `NOT_TESTED`.
- `_row_total_results` / `_column_total_results` both require a total **ROW**
  (`_total_row`, `_is_total_label`) and sum component rows above it.
- `_is_total_label` matches 소계/합계/총계/계 and the grand-total labels.

These row-total paths must keep working unchanged (regression-protected by the
existing `tests/test_checks_totals.py`).

---

## 2. The two new shapes

### Shape A — total COLUMN (row-wise footing)
Example (현대모비스 주석20 차입금/사채, unit 백만):
```
[label,                 외화대출,  원화대출,  매출채권할인,  (…명칭) 합계]
유동 차입금(사채 포함)    513,308    130,180    4,325          647,813
```
- Each amount row: `sum(component columns) == 합계 column`. (513,308+130,180+4,325 = 647,813)
- The 합계 column is identified by its **header** containing 합계/총계/계 (headers may be
  degenerate/merged, e.g. "차입금명칭 합계" repeated; inspect every header cell, prefer the
  rightmost qualifying column).
- Rows that are NOT all-numeric (e.g. 기준이자율 "3M SOFR", 0.0100) are **excluded** — only
  rows where every component cell AND the total cell parse as amounts are footed.

### Shape B — section/subtotal blocks (no grand total)
Example (현대모비스 주석8 매출채권, unit 백만):
```
유동매출채권              9,916,129  …
단기미수금                368,501    …
유동 대여금 및 수취채권    1,776      …
매출채권 및 기타유동채권 합계   10,286,406  …   ← 유동 소계
비유동매출채권            246        …
장기미수금                509,249    …
비유동 대여금 및 수취채권  1,819      …
매출채권 및 기타비유동채권 합   511,314    …   ← 비유동 소계
```
- Two sections, each with its own subtotal, NO grand total.
- Foot **each section's components to ITS subtotal** (유동소계 = sum of the 3 유동 rows;
  비유동소계 = sum of the 3 비유동 rows). Both foot exactly here.
- The bug to remove: treating the LAST subtotal as a grand total and summing all rows
  across sections → false gap. A subtotal's component scope is **only the rows since the
  previous subtotal/section boundary**, not the whole table.

---

## 3. Design

Add to `checks_totals.py` (or a new `checks_totals_structure.py` imported by it):

### 3.1 Total-column footing
`_total_column_results(table, *, note_no, tolerance) -> list[CheckResult]`
- Find candidate total column(s): header cell (compacted) contains 합계/총계/계. If
  multiple, prefer the rightmost. If none, return [].
- For each data row (skip the header row and any 소계/합계/총계 labeled row):
  - components = parseable amounts in columns `[1 .. total_col)`; total = amount in total_col.
  - Require ≥2 components AND all parseable AND total parseable; else skip the row
    (this auto-excludes rate/ratio rows).
  - Emit `_result(...)` with `check_type="total_check"`, title `"{row_label} 행 합계"`,
    expected=sum(components)*unit, actual=total*unit, reason_ok "row total agrees" /
    reason_gap "row total does not agree". Evidence = the total cell with col source.

### 3.2 Section/subtotal footing
`_section_total_results(table, *, note_no, tolerance) -> list[CheckResult]`
- Walk rows top→bottom. A **subtotal row** = `_is_total_label(row[0])` (소계/합계/계) that
  is NOT a grand total. Maintain a running list of component rows since the last
  subtotal/section start.
- At each subtotal row: foot `sum(components in that buffer, per column)` == subtotal row
  amount (per column), then reset the buffer. Component rows = non-subtotal amount rows.
- Skip rate/ratio rows (non-all-numeric) from the buffer.
- A grand-total row (e.g. label exactly 총계 or a label that equals the table's overall
  total) closes the table; if present, also foot grand total = sum of subtotals.
- If there is exactly one subtotal and it behaves as today's total row, defer to the
  existing `_row_total_results` (do not double-emit).

### 3.3 Orchestration & dedup
`check_table_totals` runs, in order: existing row-total → section-total → column-total.
- **Dedup:** never emit two checks for the same (table, row/col) target. If section
  footing already covered a subtotal, the column path must not also foot that row, etc.
  Use a set of `(table.index, row_idx, col_idx)` targets.
- If ANY structured check is emitted, the table is no longer `parse_uncertain` for "no
  total found". `parse_uncertain` remains only when required-but-nothing-anchored.

### 3.4 Abstention (the accuracy spine)
- When a column/section is ambiguous (no clear 합계 header; mixed parseability; nested
  subtotals you cannot scope confidently) → **emit nothing** for that target (fall back to
  the existing `PARSE_UNCERTAIN` if the table is required and otherwise unanchored).
- NEVER guess a total. Prefer fewer high-confidence checks. A new check that would be a
  coin-flip must abstain.

---

## 4. Status semantics (unchanged contract, more coverage)
- structured total found + foots → `matched`
- structured total found + mismatch → `unexplained_gap`
- required + summable + relevant but nothing anchorable → `parse_uncertain`
- not summable / not relevant → `not_tested`
(`checks.ALL_STATUSES`; surface all five — ADR-0006.)

---

## 5. Tests (TDD — write first, RED before GREEN)
`tests/test_checks_totals_structure.py`:
1. Shape A matched: 차입금-like table, header last col "…합계", row foots → matched.
2. Shape A gap: same but total ≠ sum → unexplained_gap.
3. Shape A excludes rate rows: a 기준이자율 row (non-numeric) is skipped, not failed.
4. Shape A degenerate header: repeated header tokens, 합계 only in last header cell.
5. Shape B two subtotals matched: 매출채권-like; each section foots → 2× matched, NO gap.
6. Shape B regression guard: the OLD behavior (last subtotal as grand total over all rows)
   must NOT produce a gap here.
7. Dedup: a table with both a 합계 column and a subtotal row emits each target once.
8. Abstention: a table with no 합계 header and no subtotal row, but amounts present →
   parse_uncertain (unchanged), no fabricated check.

Plus: existing `tests/test_checks_totals.py` must stay green (row-total path untouched).

---

## 6. Corpus regression (MANDATORY — the real gate)
Before merge, run the baseline corpus before/after and report the delta:
```
uv run dart-footing workpaper-corpus out/corpus/manifest_2026-06-08-... <out_dir_before>   # baseline = current HEAD
# implement feature
uv run dart-footing workpaper-corpus out/corpus/manifest_2026-06-08-... <out_dir_after>
```
(Use the statement-ties / nonfinancial-industry manifest available under `out/corpus/`.)
Acceptance:
- `parse_uncertain` ↓ (column/section tables now checked).
- `matched` ↑.
- **`unexplained_gap` must NOT rise from new false positives.** Any net-new gap must be
  opened and confirmed a GENUINE disclosure discrepancy (not a structure artifact). If a
  new gap is an artifact → the detector is wrong → fix or abstain.
- Spot acceptance (현대모비스): 매출채권 두 소계 → matched (was false gap); 차입금/사채
  합계-column rows → matched (was parse_uncertain); equity-tie stays matched.
Record the before/after counts in the PR description.

---

## 7. Files
- `src/dart_footing_reconciler/checks_totals.py` (+ optional `checks_totals_structure.py`)
- `tests/test_checks_totals_structure.py` (new)
- Reuse: `table_semantics.compact`, `layout_variants`, `validation_relevance` as helpful.
- Do NOT touch the equity-tie fix or the report renderer.
