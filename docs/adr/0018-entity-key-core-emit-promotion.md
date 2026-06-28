# 0018. Entity-key core-emit — promote the 4-dim pairing key onto CheckResult (Stage 1.5)

**Date:** 2026-06-28
**Status:** Accepted (design). Implementation is strangler/incremental, corpus-gated. Unblocks the ADR-0017 hard gate (no Stage 2 signal until the entity-key is core-emitted).
**Inputs:** ADR-0012 (entity-keyed model — domain already settled), ADR-0017 (ledger review: entity-key must be core-emitted, not inferred from display strings). Structure map (this session).
**Companion:** `CONTEXT.md` (Consolidation Basis / Balance Level / Report Period), `docs/domain-model.md`.

## Context

ADR-0012 established the 4-dim pairing key `Account × Consolidation Basis × Report Period × Balance Level` and B-2b proved all four are *simultaneously known* during lease pairing. But `CheckResult` does **not carry** them as fields — so the Stage-1 ledger (`run_artifact._entity_key`) had to **infer** them from display strings, which the ADR-0017 review found unreliable and fabricating (`consolidation_basis = result.scope` where `scope` is actually `"note"/"report"/"operating"/…`, never 연결/별도). ADR-0017 set a hard gate: **no Stage 2 cross-module signal may be emitted until the entity-key is core-emitted.** This ADR is that promotion.

Findings from the structure map:
- `CheckResult` (checks.py:44) is a frozen dataclass; its `scope` field is a **check classification** (note/report/cycle/prior_year), not the consolidation basis.
- The basis lives on `ReportSection.scope ∈ {consolidated, separate, ""}` and, after `split_report_by_scope`, every slice is **homogeneous** — so the basis is knowable at one threading point (`VerificationContext`).
- `account_key` is the loop variable in the fs_note family (already used in `check_id`); `balance_level` is computed by `infer_balance_level()` and used in lease by-level grouping; `report_period` is explicit for `prior_*` families and filtered for lease.
- 25 construction sites across 10 modules; checks_reconciliation.py is heaviest (4).

## Decision

1. **Add four fields to `CheckResult` with safe defaults** (strangler — all 25 sites keep compiling): `account_key: str = "unknown"`, `consolidation_basis: str = "unknown"`, `report_period: str = "unknown"`, `balance_level: str = "unknown"`. The existing `scope` field is **unchanged** (it remains the check-classification; do not overload it).

2. **Thread `consolidation_basis` once via `VerificationContext`.** Compute it per slice in the harness runner (`_slice_consolidation_basis`: concrete `consolidated`/`separate` only when the slice is single-basis; a multi-scope *split* slice is homogeneous, but a single-scope *passthrough* slice that still carries untagged (`""`) residual stays honest `"unknown"`). Apply it **once, post-harness**, via `dataclasses.replace` in `run_harnesses` (only onto checks whose basis is still `"unknown"`) — covering *all* families from one point, no per-construction-site copy. (The per-check `consolidation_basis` parameter threaded into the fs_note/prior_column functions is vestigial — it always receives `"unknown"` in production because the central replace does the work — and is slated for removal; ADR-0019 MINOR-1.)

3. **Populate the other three where they are already known; otherwise honest `"unknown"`** (no fabrication, per ADR-0017):
   - `account_key`: fs_note family (loop var) and `prior_*` (taxonomy entry) where available.
   - `balance_level`: fs_note **lease** level-aware pairing emits the level used in the by-level grouping (`current`/`noncurrent`/`total`). Borrowings/bonds use the **flat** branch and honestly emit `unknown` level; `unknown` for the non-level model generally.
   - `report_period`: `prior` for `prior_*` families; `current` where the check explicitly used current-period filtering (lease candidate selection); `unknown` otherwise. Do **not** blanket-assume `current`.

4. **Wire the ledger to read the structured fields and delete the string inference.** `run_artifact._entity_key` reads `result.account_key / consolidation_basis / report_period / balance_level` directly; the `_report_period` / `_balance_level` substring helpers (added in Stage 1A, hardened in ADR-0017) are **removed**. The honest-`unknown` defaults flow through unchanged for unmigrated families.

5. **Verdict-immutability is the corpus gate.** The four fields are **metadata copied at construction** — they never touch pairing, summation, tolerance, or status. The check-level before/after diff (matched+gap sets) and the per-company snapshot must be **byte-identical**; the new fields appear only as added metadata, never as a verdict change.

## Alternatives considered

- **Reuse the existing `scope` field for the basis.** Rejected: `scope` is load-bearing as the check classification (cfs cycle, prior_year) and tests assert on it (`result.scope == "investing"`); overloading it would corrupt both meanings.
- **Make the four fields required (no default) and update all 25 sites at once.** Rejected: a big-bang touch of every check family at once is higher-risk against the corpus gate; defaults + strangler migrate the high-value families (lease/borrowings + basis everywhere) first.
- **Keep inferring in the ledger.** Rejected by ADR-0017 — inference fabricated the basis and was fragile; this is the agreed fix.

## Consequences

- After this lands, the ledger entity-key is **real** for the migrated families (lease/borrowings level-aware + consolidation_basis for every family) and honest-`unknown` for the rest → the ADR-0017 hard gate opens for the **first Stage 2 signal (lease tie-out → erp_recon)**, while other families wait for their own migration slice.
- `CheckResult` gains four metadata fields; the 25 construction sites are updated incrementally; existing `scope` assertions are untouched.
- The corpus gate proves the verdict is unchanged (metadata-only); this is the load-bearing safety property of the change.
- Remaining families (totals, formulas, reconciliation, note_note, …) keep `"unknown"` dims until each is migrated under its own corpus-gated slice (strangler, per ADR-0012).
