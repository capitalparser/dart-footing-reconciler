# 0019. Entity-key core-emit — code review findings

**Date:** 2026-06-28
**Status:** Accepted. Review of commit `58d5782` (ADR-0018 implementation). Clean-to-merge; MINOR-2 + NITs applied this PR, MINOR-1 tracked as a pre-next-migration follow-up.
**Inputs:** Opus `code-reviewer` (full leg) + Codex adversarial leg (runtime-flaked, see below). Verdict-safety proven independently by the corpus hard gate.
**Companion:** ADR-0018, `plans/2026-06-27-report-validation-ledger.md`.

## Review basis

- **Verdict-safety — PROVEN (not just reviewed):** both local corpora were run on this code; per-company status counts are **byte-identical** to the committed baselines (10-co + 8-co expansion), and the full suite is 897 passed/1 skipped (×2). The four fields are metadata; they provably do not change a verdict.
- **Opus leg (dimension-value correctness — the real risk surface, since these values feed Stage 2 signals): clean-to-merge.** All four dimensions are correct or honest-`unknown`; no fabricated/mislabeled non-unknown value that could poison a Stage 2 signal. All seven correctness checks passed (basis compute + replace logic; lease level mapping; period labels; canonical account_key; frozen-replace safety; strangler discipline / no over-reach — reconciliation builds `StatementLineInput`, not a CheckResult; tests pin actual values).
- **Codex adversarial leg: not delivered.** The Codex companion runtime flaked twice this session and produced no findings for this change. Recorded honestly rather than claimed. Given (a) the corpus gate proves verdict-safety and (b) the Opus leg covered dimension correctness thoroughly with only MINOR/NIT findings, the review basis is sufficient for this metadata-only change; a Codex pass can be added later if desired.

## Findings & disposition

- **MINOR-1 — vestigial `consolidation_basis` parameter chain (tracked follow-up).** Codex threaded a `consolidation_basis` parameter through ~10 sites in `checks_fs_note.py` + `checks_prior_column.py`, but the harness never passes it, so it is always `"unknown"` in production; the real value is injected once by the central `dataclasses.replace` in `run_harnesses`. Two mechanisms, one dead. **Values are correct** (central replace wins). Removing the dead chain is a ~10-site mechanical cleanup with regression risk; per Opus it is post-merge-sufficient. **Disposition: tracked in HANDOFF; clean up before the next family migration** (so the two paths don't diverge). ADR-0018 §2 wording corrected to describe the central-replace reality.

- **MINOR-2 — `_with_context_consolidation_basis` had no direct unit test (FIXED).** The production basis-application path was covered only e2e (the "concrete → replace" branch). Added synthetic unit tests in `tests/test_verification_harness.py` for all three branches: concrete-context-applies, unknown-context-leaves-unchanged, and already-set-not-overridden.

- **NIT-1 — "borrowings level-aware" wording (FIXED).** Only `lease_liabilities` is level-aware; borrowings/bonds use the flat branch and honestly emit `unknown` level. ADR-0018 §3 corrected.

- **NIT-2 — "slice is homogeneous" overgeneralization (FIXED).** A single-scope *passthrough* slice with untagged residual is not homogeneous; `_slice_consolidation_basis` conservatively returns `"unknown"` there (a single-basis filing with untagged sections is under-populated, never mis-populated — consistent with ADR-0017 honesty). ADR-0018 §2 corrected.

## Consequence

The change is clean-to-merge. With the migrated families (lease level-aware + consolidation_basis everywhere it is concretely known + report_period for prior_*) now emitting **real** dimensions, the ADR-0017 hard gate **opens for the first Stage 2 signal (lease tie-out → erp_recon)**. The vestigial parameter chain (MINOR-1) must be removed before the next family's migration to keep a single basis-application mechanism.
