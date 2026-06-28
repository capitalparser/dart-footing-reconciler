# 0021. Stage 2A signal outbox — code review findings

**Date:** 2026-06-28
**Status:** Accepted. 2-leg review (Opus + Codex) of commit `ea59bc7` = **fix-before-merge**. Fixes specified below; applied before the Stage 2A PR.
**Inputs:** Opus `code-reviewer` + Codex adversarial self-review. Both converged on the dedupe/supersession coherence gap; Codex added three routing/robustness guards.
**Companion:** ADR-0016 (envelope/retraction contract), ADR-0020 (Stage 2A design).

## Verdict (both legs): fix-before-merge

The machinery (routing conservatism, atomic write, content-addressing, schema) is sound, but the **retraction half of the ADR-0016 §4 contract is unimplemented while the code serializes `dedupe_key` as if it were used** and a `ledger.py` comment claims "supersession is Stage 2A's responsibility" that the code does not honor. Not a functional bug — an incoherence that would leak duplicate live signals to erp_recon once a consumer exists.

## Convergent findings (both legs)

- **Dead `dedupe_key` → cross-run duplicates** (Opus MAJOR-1 / Codex BLOCKER). `signal_id` is per-run (derives from run-scoped `finding_id`); `dedupe_key` is the cross-run-stable key (from `result_lineage_key`) but is **read by zero lines**. `INSERT OR IGNORE` keys on `signal_id` only, so a parser-fix re-run emits a *second* live signal for the same logical lease gap.
- **Producer never retracts the OLD signal** (Opus MAJOR-2 / Codex MAJOR). `write_signal` records `supersedes_signal_id` on the NEW row but leaves the OLD row `pending` and the OLD envelope in the queue — contradicting ADR-0016 §4 and the existing `ledger.py:_delete_run_projection` comment.
- **`consolidation_bridge` is a dangling target** (Opus MINOR-2 / Codex MAJOR). A new pseudo-module with no consumer/contract.
- **Tests miss the failure modes** (both). The supersede test only proves the fake consumer's logic, not producer retraction; there is no cross-run duplicate test.

## Codex-unique findings

- **Basis-guard bypass:** `if consolidated … else erp_recon` routes *any* non-`consolidated` basis to erp_recon. Only `separate` is a valid erp_recon target.
- **`source_locations` not validated:** a signal can be emitted with no evidence locations — no audit trail.
- **Atomic-write tmp name uses only PID:** two same-process writes to one target collide on `O_EXCL`.

## Decision — fixes (this PR)

Close the contract coherently rather than documenting a half-implementation. Theme (as in ADR-0017): honesty/coherence — no dead field, no contradicting comment, no signal we cannot route correctly.

1. **Producer-side supersession keyed on `dedupe_key`** (closes the dup + the retraction in one move, makes `dedupe_key` live, honors ADR-0016 §4):
   - Add a `dedupe_key` column to `cross_module_signals` (ledger.py schema).
   - On `write_signal`, if a **pending** row with the same `dedupe_key` and a **different** `signal_id` exists: set the new row's `supersedes_signal_id` to the old `signal_id`, mark the **old row `superseded`**, and **remove the old envelope file**, then write the new row + envelope. Exact-dup (same `signal_id`, same run) stays an `INSERT OR IGNORE` no-op.
2. **`consolidated` basis → abstain (deferred), not a dangling target.** erp_recon reconciles a *single entity's* GL and cannot explain a *consolidated* gap (it spans component entities + eliminations), so route **only `consolidation_basis == "separate"` → erp_recon**; `consolidated` → return None (a deferred routing target, recorded — no correct consumer yet). This removes the `consolidation_bridge` pseudo-target and fixes the basis-guard bypass at once.
3. **Require audit evidence + a gap amount → else abstain.** No `source_locations` (≥1) or no resolvable gap amount → return None (an audit signal without evidence/amount is not actionable).
4. **Robustness:** defensive `stale_after_days` parse (garbage → default, no crash); unique tmp name (include `signal_id`); envelope file extension `.json` (the content is JSON; ADR wording "YAML envelope" → JSON-as-envelope).
5. **Tests pin the failure modes:** cross-run supersession (same `dedupe_key`, different run → old `superseded` + old file gone + single pending, `signal_id` differs); abstain on `consolidated` / empty `source_locations` / missing gap; defensive `stale_after_days`. Rename the supersede test to assert **producer-side** retraction (old row status + old file absence), not just the fake consumer.

## Consequences

- Stage 2A's contract becomes coherent: `dedupe_key` is live, the producer retracts superseded signals, no dangling target, and every emitted signal carries evidence + amount + a real consumer (`separate` → erp_recon). The `ledger.py` comment now matches the code.
- Consolidated-basis lease gaps are a **recorded deferred routing target** (no correct consumer until a consolidation-bridge workflow exists).
- The consumer-inbox / ack state machine remains deferred (ADR-0016 calibration) — this slice implements only the **producer-side** outbox lifecycle.
