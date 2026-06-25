# 0013. B-2b level-aware lease pairing — code review findings

**Date:** 2026-06-25
**Status:** Accepted — BLOCKER + 2 MAJOR fixed (corpus-gated, regression-pinned); MINORs recorded.
**Scope:** check-layer (`checks_fs_note.py` lease functions). Slice: ADR-0012, spec `docs/superpowers/specs/2026-06-25-b2b-level-aware-pairing.md`, impl commit `8e773b0` (PR #20).
**Inputs:** Tier-3 cross-model code review (heavy-zone step 8) of the B-2b implementation.
- Leg (a) Opus `code-reviewer` agent — verdict **REQUEST CHANGES**; reproduced every finding with executed probe scripts.
- Leg (b) Codex adversarial — runtime returned interim repeatedly this session (best-effort); the Opus leg + corpus gate + self-review stand as the verification.

## Why this ADR exists
The corpus hard gate (18 companies) was clean (+22 matched, 0 false, 0 destroyed) — yet the Opus leg **reproduced three false-MATCH paths** the corpus shape happens to avoid. A green gate does not exempt the code from review; these are out-of-corpus doctrine violations ("an audit verdict must never carry a false match") that would surface on other filings. All fixed before merge.

## Findings & fixes

### B-1 (BLOCKER) — context-free aggregate label promoted to lease-liability total → false match
A bare `합계`/`소계`/`장부금액`/`기말` row in a 리스-titled note passed row-label isolation (no wrong-account token) and `_is_total_balance_label` classified it as the lease total. In a **combined note** (e.g. "리스 및 사용권자산"), an asset-side subtotal that coincides with the FS current+noncurrent sum produced a `matched`. This is the BLOCKER-1b failure mode (title-based trust) the spec claimed to have removed — row-label isolation is blind to context-free aggregate labels.

**Fix:** `_is_lease_liability_total_context(hit)` gates the `total` classification — a bare aggregate is a lease total only if (a) the label itself contains `리스부채`, or (b) the note title is pure-lease-liability (`리스` present, `사용권자산`/`자산` absent). Verified against the corpus total-matches: CJ ("기말", title "리스부채") passes via (b); SGC/현대건설 ("기말 리스부채") via (a); the combined-note bare `합계` is rejected → abstain. Pin: `test_fs_note_lease_bare_aggregate_in_asset_titled_note_not_matched_as_total`.

### B-2 (MAJOR) — prior-year-only table picked as current → wrong-period false match
`row_amount_prefer_current` falls back to the rightmost column when no current-period header is present, so a 전기(prior)-only table yields the prior amount with no period marker. If that table has a lower `table.index` and the lease balance is YoY-flat, the prior amount coincides with the current FS line → `matched` on the wrong period. "current↔current only" (spec) was not enforced at extraction.

**Fix:** `_lease_note_candidates` skips a table whose headers have no current-period column but do have a prior-period column (`current_period_columns`/`prior_period_columns`), and uses `amount_from_current_period` (current columns only) when current columns are identifiable — generic rightmost fallback only when the table has no period markers at all. Pin: `test_fs_note_lease_prior_year_only_table_not_matched_as_current`.

### B-3 (MAJOR) — consolidated + unscoped basis leak → cross-basis false match
`split_report_by_scope` only splits when **both** `consolidated` and `separate` are present; a `consolidated` + unscoped (`""`) report (no `separate`) stays one slice. `_has_single_consolidation_basis` only counted `{consolidated, separate}`, ignoring `""`, so it returned single → a consolidated current line and an unscoped noncurrent line were summed/paired across bases.

**Fix:** `_has_single_consolidation_basis` now counts **all** distinct section scopes (including `""`); a mixed slice → abstain. Pin: `test_fs_note_lease_mixed_consolidated_and_unscoped_basis_abstains`.

### MINORs (recorded, doctrine-safe — all abstain/coverage side)
- `infer_balance_level` returns a level for an out-of-range `row_index` (should early-return `unknown`); corpus-harmless (source rows are valid). Defer.
- `_LEASE_WRONG_ACCOUNT_ROW_TOKENS` includes broad `자산` — could reject a legitimate row in theory (false-negative = abstain, doctrine-safe); corpus-harmless. Defer.
- Coverage asymmetry: a lower-index noncurrent-only table leaves `current` permanently `not_tested` (surfaced as coverage, never a false match). Defer.
- `_lease_note_hits_by_level` 3rd return value is always `False` (dead ambiguous path, compatibility). Defer.

## Net effect
Three false-match paths closed; corpus gate unchanged (baselines identical → the fixes are out-of-corpus guards): **+22 matched, 0 destroyed, 0 false, 0 new gaps**. `uv run pytest -q` = 879 passed/1 skipped (deterministic); ruff clean. Confirms the cross-model CODE review's value even over a clean gate (cf. ADR-0010/0011, where review also caught BLOCKERs a gate missed).
