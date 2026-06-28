# 0017. Result Ledger Stage 1A/1B — cross-model code review findings

**Date:** 2026-06-28
**Status:** Accepted. Two-leg review of commits `4821233` (1A) + `9937fc5` (1B). Required fixes applied this PR; deeper entity-key promotion deferred (required before Stage 2).
**Inputs:** Opus `code-reviewer` agent + Codex adversarial self-review (heavy-zone step 8). Diff = `run_artifact.py`, `ledger.py`, `test_run_artifact.py`, `test_ledger.py`.
**Companion:** ADR-0015/0016, `plans/2026-06-27-report-validation-ledger.md`.

## Verdict (both legs agree): merge-with-fixes

The doctrine skeleton is **structurally sound** — sealed-artifact → downstream projection, core imports nothing from the ledger, materializer never mutates `CheckResult`, ledger failure is an isolated operational event (HTML/Excel byte-unchanged), no SQL arithmetic, `REAL`/float forbidden and runtime-blocked, all-5-statuses in `check_results`, exception never dropped on follow-up failure, content-addressed IDs, stdlib-only. **But the entity-key is not yet trustworthy**, and that key is the content-addressed basis for cross-module signals / lineage / coverage. It must be made honest before Stage 2 builds on it.

## Convergence (both legs independently)

- **Entity-key is unreliable.** Cross-module contract, `result_lineage_key`, and coverage keys all hash dimensions that are currently guessed.
- **The fingerprint test is a no-op for true verdict-immutability.** Because the ledger is not wired into the run path, `test_full_result_fingerprints...` only proves "materializing a pre-written artifact doesn't mutate it" — not "ledger-off run ≡ ledger-on run." The real end-to-end gate cannot close until the seam exists. Verdict-immutability is currently guaranteed only **indirectly** (static import-boundary + materializer-input isolation), which is sufficient *because the ledger is dead code in the run path today*.

## Divergence (the value of two legs)

- **Opus-only:** (B1) `consolidation_basis = result.scope` is **fabrication** — `scope` only ever holds `"note"`/`"report"` (not 연결/별도); putting it in the consolidation slot is worse than `unknown` and breaks the 4-dim key + Stage-2 consolidation-bridge routing. (M1) `test_run_artifact.py` depends on the **gitignored INVENI corpus** → 4 fail on a clean checkout (reproduced by hiding `out/corpus/`). (M2) `_report_period` matches `"current"` inside `"noncurrent"` → period mislabel (`_balance_level` guards this; `_report_period` doesn't).
- **Codex-only:** (MAJOR-4) `result_id` omits amounts/reasons → distinct results sharing run/attempt/entity/evidence/status can collide on the PK. (MAJOR-7) `load_run_artifact` validates nothing (no header/result_count/required-field/fingerprint check) → a truncated artifact materializes silently. (MAJOR-6) `_engine_version()` reads package metadata → same source yields different `run_id` across editable/packaged/uninstalled environments.
- **Both confirmed (no action):** no verdict-influence import path; `result_id` (per-run) vs `result_lineage_key` (cross-run) split is correct; `PRAGMA foreign_keys` is per-connection and set in the materialize path; `reviewer_decisions`/`cross_module_signals` empty tables are correct scaffolding, not over-reach; SQL-injection surface is nil (hardcoded whitelist f-string, `?`-bound elsewhere).

## Decision — required fixes (this PR)

The theme is **honesty over fabrication** (invariant #4): an unsurfaced dimension is `unknown`, never a fabricated value.

1. **`consolidation_basis` → `"unknown"`**, not `result.scope`. (Opus B1)
2. **`account` → a stable value or `"unknown"`**, never the free-text `result.title`; preserve the title in a separate non-key `display_title` field. (Opus M4)
3. **`_report_period` substring bug** fixed (exclude `noncurrent` first / word-boundary); ambiguous → `unknown`. **`balance_level`/`report_period`** set to `unknown` where not reliably inferable. (Opus M2/M3)
4. **`result_id` includes `full_result_fingerprint`** (amounts + reasons) to prevent collision. (Codex M4)
5. **`load_run_artifact` validates** header `record_type`, `result_count` vs actual, and required fields before any ledger insertion. (Codex M7)
6. **`engine_version` accepts an explicit override** (default importlib) so `run_id` is stable across environments when supplied; documented. (Codex M6)
7. **`parse_uncertain_reason` in the fingerprint uses the code value only** (drop the free-text `result.reason` fallback) so the fingerprint gate is not sensitive to prose. (Opus NIT, promoted — fingerprint robustness)
8. **`test_run_artifact.py` → synthetic fixtures** (portable; no `out/corpus`), mirroring `test_ledger.py`. (Opus M1)
9. **Unit tests for the entity-key inference helpers** (title/check_id → expected dims, incl. the `noncurrent` case and the `unknown` fallbacks). (Opus M3)
10. Minor: `materialize_run_artifact` loads the artifact once (no double-parse); intent comments for `explainable_gap` check_results-only, the f-string whitelist, fact_id role-blind-by-design, and `_delete_run_projection` projection-only (overlay/signal lifecycle = Stage 2A).

## Decision — deferred (required BEFORE Stage 2, not this PR)

These are **core changes** that belong with the entity-keyed strangler migration (ADR-0012), each corpus-gated + cross-model-reviewed in its own handoff:

- **Promote the entity-key to core-emit:** `CheckResult` carries a structured `consolidation_basis (연결/별도)`, `report_period`, `balance_level`, and a canonical `account_key` — so the ledger records real dimensions instead of inferring them. This is the load-bearing prerequisite for any cross-module signal (Stage 2). Until then the ledger's entity-key dimensions are honest-`unknown` placeholders.
- **Wire the artifact seam + the true end-to-end gate:** run the same input through ledger-off and ledger-on *run paths* and assert byte-identical canonical fingerprints + HTML/Excel bytes (the real verdict-immutability gate; the current test only covers artifact non-mutation).
- **explainable_gap surfacing:** keep it check_results-only for now; add an explicit third view if a consumer needs "explained but non-matched" coverage.

## Consequences

- Stage 1 merges as an **honest, dead-code-in-run-path persistence foundation**: no fabricated dimensions, portable tests, hardened IDs/validation. It has no consumers yet, so honest-`unknown` entity-keys are safe.
- A hard gate is added to the project's memory: **no Stage 2 cross-module signal may be emitted until the entity-key is core-emitted** (otherwise signals would carry inferred/`unknown` keys into erp_recon/ksox).
- The review caught a defect Claude let through in the Stage 1A commit (non-portable `test_run_artifact.py`) — the two-leg gate paid for itself.
