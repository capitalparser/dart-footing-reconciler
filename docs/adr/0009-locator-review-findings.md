# 0009. Canonical Amount Locator — cross-model review findings

**Date:** 2026-06-21
**Status:** Accepted — contract corrections applied to ADR-0008 / spec / scaffold before Codex handoff
**Inputs:** Tier-3 cross-model plan review of ADR-0008.
- Leg (a) independent architecture review (fresh-context Opus-family reviewer).
- Leg (b) Codex (GPT-family) code-grounded review.

Both legs converged: **the architecture is the right call; the interface contract and test plan were not implementable as written.** The fixes below are contract+test corrections, not a redesign. This record exists so future reviews don't re-litigate them.

## Findings & decisions

### F1 (BLOCKER, both legs) — `locate()` signature was dishonest about its inputs
`classify_layout` requires a `NoteTableInventoryItem` (title/headers/row_labels, `layout_variants.py:19`, `note_inventory.py:10-23`); `_source` requires a `ReportSection` (`reconciliation_inputs.py:1729`). A bare `ReportTable` (`document.py:25-31`) cannot produce either. The "derive layout/orientation from the table if not passed" fallback would silently misclassify.

**Decision:** signature becomes `locate(item: NoteTableInventoryItem, table: ReportTable, account_key, role, *, layout=None, orientation=None, scope=None, expected_amount=None)`. `layout`/`orientation` are derived from `item` when not passed (now valid). Every real call site holds both `item`/`section` and `table` (`reconciliation_inputs.py:261-263`; `verification_candidates.py:32-38`).

### F2 (BLOCKER, Codex) — cell-selection vs hit-among-candidates were conflated
"Which cell carries account X's amount in table T" (locator) ≠ "which of N already-located note amounts pairs to this FS line" (`checks_fs_note._select_note_hit_by_label` + `_is_balance_row`, `checks_fs_note.py:116-219`). The B-2a balance-row filter is the second operation and **stays in the check layer**.

**Decision (scope correction):** the locator owns **cell selection** — its real wins are **B-5 (net_carrying_amount cell)** and **B-2b (current/noncurrent_portion cell)**. **B-2a and B-4 are check-layer pairing decisions** and stay in `checks_fs_note`; they *benefit* from cleaner located cells but are not moved into the locator. ADR-0008's claim that the locator "fixes B-2a/B-4" is corrected to "B-2a/B-4 stay in the check layer." Spec §3.2 and test §5.1 #6 are rewritten: the locator is asked about a specific row and returns its value+sign or abstains; it does NOT scan-and-skip rows.

### F3 (BLOCKER, both) — category-matrix archetype has no `classify_layout` key; acceptance fixtures' real keys unverified
The B-5 triad names 3 archetypes but only 2 map to real keys; 더존 N9 may classify as `asset_cost_accumulated_grant_total` (conf 0.9, checked first, `layout_variants.py:26`) not `asset_cost_accumulated_summary`, so the net-vs-gross strategy might never fire. ~13 other asset-family keys are ignored.

**Decision:** add a **Phase 0.5** (Codex, first task): run `classify_layout` on the acceptance fixtures (더존 N9/N12, 셀트리온 N12-1, 롯데정밀화학) and record the *actual* keys; bind strategies to the keys that fire; add a `category_matrix` handling path (or map it to an existing column-summary key). Strategy implementation must not assume the spec's archetype names.

**Phase 0.5 result (2026-06-21, Codex; verified by Claude).** The spec's assumed keys were wrong — confirmed F3 was load-bearing:

| fixture | account / role | actual `classify_layout` key | conf |
|---|---|---|---|
| CJ대한통운 note:18/table:371 | 무형 net_carrying | `asset_carrying_amount_total` | 0.8 |
| 더존 note:9/table:45 | 유형 net_carrying (net-gross matrix) | `asset_carrying_amount_total` | 0.8 |
| 더존 note:11/table:58 | 투자부동산 net_carrying | **`unknown_layout`** | 0.0 |
| 더존 note:10/table:51 | 리스부채 period_end_balance | `lease_liability_current_noncurrent_summary` | 0.85 |

Neither `asset_cost_accumulated_summary` nor `asset_period_rollforward_summary` (the spec's named archetypes) fired. The headline net-gross matrix is `asset_carrying_amount_total`. **One acceptance fixture (더존 투자부동산) is `unknown_layout` (conf 0.0)** — so the locator cannot dispatch on layout key alone for it; the implemented strategy falls back to header/orientation inspection and the regression pin (row 4, col 7 = 222,521,190) passes. Consequence for Phase 2: the `unknown_layout` path must be watched closely under the corpus gate (it must abstain, not guess, on the general population).

### F4 (BLOCKER, Codex; MAJOR, leg a) — `LocatedAmount` single cell cannot represent a category-matrix row-sum
Net carrying for a category matrix is a sum across category columns (multiple cells); CONTEXT requires Source Location for every material amount.

**Decision:** `LocatedAmount` carries `component_sources: tuple[str, ...]` (each summed cell's source) in addition to the anchor `(row_index, col_index, source)`. For single-cell results `component_sources` is empty; for a row-sum `amount` = sum and `component_sources` lists every contributing cell.

### F5 (MAJOR, Codex) — taxonomy path is amount-validated; the locator has no target amount
`taxonomy._generic_note_row_amount` (`taxonomy.py:864-885`) selects the rightmost column whose value `_amounts_close(line.amount, …)` — it uses the known FS figure as an oracle. A pure `(table, account, role)` locator cannot reproduce this.

**Decision:** add optional `expected_amount` to `locate()`, used **only as a tie-breaker** among structurally-valid candidates (never to fabricate a cell). Taxonomy keeps its amount-validation: in Phase 3 the locator *proposes* candidates and taxonomy *validates* against `line.amount`. Phase 3 stays last.

### F6 (MAJOR, both) — scope drives column choice, not just confidence
별도/연결 and 당기/전기 mirror columns mean `scope` must select the column, not merely modify confidence (롯데정밀화학 acceptance is 별도; `reconciliation_inputs.py:486` already filters current-only but has no consolidated/separate filter).

**Decision:** `scope` drives column selection in the strategies; abstain (`COLUMN_NOT_DETECTED`) when the scope-matching column cannot be identified.

### F7 (MAJOR, both) — test plan didn't lock the 8-destroyed-matches regression
§5.1 were synthetic-shape tests; the 2026-06-16 revert destroyed specific real checks (CJ 무형×2, 더존 PPE/투자부동산/리스×2).

**Decision:** add fixture-based per-destroyed-check regression pins (one assertion per check, real parsed fixtures) to §5. Per-company snapshot (`scripts/check_per_company_snapshot.py`) is a **hard gate**, not "report", on every wiring phase. Add a Phase 1.5 single-account flagged observation before the full reconciliation_inputs cutover.

### F8 (MINOR, Codex) — abstain semantics: NotApplicable (→ not_tested) vs Abstain (→ parse_uncertain)
Role-inapplicable (asking `cash_like_movement` of a pure balance table) is `not_tested`, not `parse_uncertain`. Mapping it to parse_uncertain corrupts the honest-coverage signal (backlog §4a).

**Decision:** the locator returns three outcomes: `LocatedAmount` | `Abstain` (tried-but-ambiguous → parse_uncertain: AMBIGUOUS_MULTIPLE/COLUMN_NOT_DETECTED/LOW_CONFIDENCE_MATCH) | `NotApplicable` (role/account structurally absent → not_tested). Add a code-level test that `TargetAmountRole` is exactly the 7 strings and that `amount_locator` does not import the three role enums for mapping (orthogonality guard, F-m3).

### F9 (MINOR, both) — deferred-role notes
- `disclosed_total`: when implemented, must call into / share ADR-0007's total-cell detection in `checks_totals`, not reimplement it.
- Role vocab (7) confirmed right-sized by both legs; no additions.
- ADR-0003 amendment (semantic track → diagnostic) confirmed clean by both legs.

## Net effect on the plan
ADR-0008 scope claim corrected (F2). Spec §2.1 signature, §3 strategies (F1/F3/F4/F6), §4 phases (F5/F7), §5 tests (F7), §3.2 boundary (F2), abstain contract (F8) updated. Scaffold interface updated (F1/F4/F5/F8). Then Codex Phase 0.5→1.
