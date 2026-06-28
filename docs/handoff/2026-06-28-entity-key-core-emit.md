# Codex Handoff — Entity-key core-emit (Stage 1.5, ADR-0018)

**Date:** 2026-06-28
**Branch:** `feat/entity-key-core-emit` (off `main`).
**Read first:** `docs/adr/0018-entity-key-core-emit-promotion.md`, `docs/adr/0012-entity-keyed-reconciliation-model.md`, `CONTEXT.md` (Consolidation Basis / Balance Level / Report Period).

## One-line contract

Promote the 4-dim pairing key onto `CheckResult` so the ledger records REAL dimensions instead of inferring them — **as metadata only**: never touch pairing, summation, tolerance, or status. The corpus verdict must be byte-identical before/after.

## The change (strangler, corpus-gated)

1. **`CheckResult` (src/.../checks.py:44) — add 4 fields with safe defaults** (so all 25 construction sites keep compiling):
   `account_key: str = "unknown"`, `consolidation_basis: str = "unknown"`, `report_period: str = "unknown"`, `balance_level: str = "unknown"`.
   **Do NOT touch the existing `scope` field** — it is the check classification ("note"/"report"/"operating"/"investing"/"financing"/"prior_year"), NOT the consolidation basis. Tests assert on it (e.g. `test_checks_cfs_note.py` `result.scope == "investing"`) and must stay green.

2. **Thread `consolidation_basis` once via `VerificationContext`** (check_pipeline.py — `assemble_report_harness_runs` builds the context per slice from `split_report_by_scope`). Each slice is homogeneous, so compute the basis once: `report_slice.statements[0].scope` (or `.notes[0].scope`), normalized to `"consolidated"` / `"separate"` / `"unknown"` (map `""`/residual → `"unknown"`). Put it on `VerificationContext`; each check copies it onto every `CheckResult` it builds. This covers ALL families cheaply.

3. **Populate the other three where already known; else honest `"unknown"`** (no fabrication):
   - `account_key`: fs_note family — it's the loop var `account_key` (already used in `check_id`). prior_* — from the taxonomy entry if available.
   - `balance_level`: fs_note lease/borrowings level-aware pairing — emit the level used in the by-level grouping (`infer_balance_level()` at checks_fs_note.py:326; the by-level dicts at ~145–192). `current`/`noncurrent`/`total`; `unknown` for the flat (non-level) model.
   - `report_period`: `"prior"` for the `prior_*` families (checks_prior_year.py, checks_prior_column.py); `"current"` where the check explicitly used current-period filtering (lease candidate selection via `amount_from_current_period`); `"unknown"` otherwise. **Do NOT blanket-assume "current".**

4. **Wire the ledger to read the fields; delete the inference.** In `run_artifact.py`:
   - `_entity_key` reads `result.account_key / result.consolidation_basis / result.report_period / result.balance_level` directly (fallback to `"unknown"` if absent).
   - **Delete** the `_report_period` and `_balance_level` substring helpers (and the now-unused `import re` if nothing else uses it). The honest-`unknown` defaults flow through unchanged for unmigrated families.

## THE HARD GATE (do not merge without it)

- **Verdict byte-identical:** the 4 fields are metadata copied at construction — they must NOT change any pairing/summation/tolerance/status. Run the corpus before/after; the **check-level matched+gap diff is empty** and `scripts/check_per_company_snapshot.py` passes on both baselines (10-co + 18-co). The full-result fingerprint in run_artifact WILL change (entity_key now carries real values) — that is expected and fine; what must not change is the 5-status CheckResults from the engine.
- Existing `scope` assertions stay green.
- New tests (synthetic, no gitignored corpus): lease fs_note CheckResult carries the right `account_key`/`balance_level`; a 2-basis report yields `consolidation_basis` "consolidated"/"separate" on the resulting CheckResults; `prior_*` yields `report_period == "prior"`; run_artifact `_entity_key` now reflects the structured fields (and the deleted helpers are gone).

## Hard "DO NOT"
- Do NOT overload or change the meaning of `scope`.
- Do NOT change any pairing / summation / tolerance / status logic (metadata only).
- Do NOT break existing tests; keep `scope` assertions.
- Do NOT add a non-stdlib dependency.
- Do NOT migrate every family — fs_note/lease/borrowings + basis-everywhere + period-for-prior is the Phase-1 scope; leave the rest `"unknown"` (strangler).

## Verify
`uv run pytest -q` x2 (deterministic) + `uv run ruff check` + the corpus hard gate (check-level diff empty, snapshot pass). Leave files uncommitted — Claude owns git and will verify + commit. Report what changed, the corpus-gate result, and which families now emit real dims vs `"unknown"`.

## The proven loop
Work on `feat/entity-key-core-emit` (off main). TDD: regression pins first. Corpus hard gate before any "done". pytest x2 + ruff. Then Claude runs the 2-leg code review before merge.
