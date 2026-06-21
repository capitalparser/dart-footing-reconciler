# HANDOFF.md — Canonical Amount Locator

**Branch to create:** `feat/canonical-amount-locator` (from `main`)
**Primary executor:** Codex (files + tests + corpus run)
**Git owner:** Claude (Codex sandbox cannot write `.git`; Claude commits after each verified, corpus-gated batch)
**Verifier:** Claude (spec compliance + corpus-regression review for false positives)
**Plan status:** finalized after Tier-3 cross-model review — implement the CORRECTED contract (ADR-0009), not a naive reading of ADR-0008.

---

## Read first (in order)
1. `docs/adr/0009-locator-review-findings.md` — the review corrections (BLOCKERS F1/F2/F3/F4); read this FIRST.
2. `docs/adr/0008-canonical-amount-locator.md` — the decision + migration phases (scope corrected by F2).
3. `docs/superpowers/specs/2026-06-21-canonical-amount-locator.md` — the contract (interface, archetype strategies §3, phases §4, tests §5, corpus gate §6).
4. `CONTEXT.md` — Target Amount Role (closed 7); status SSOT = `checks.ALL_STATUSES` (5).
5. `docs/accuracy-backlog.md` — B-5 / B-2b are the acceptance targets; the 2026-06-16 revert (12 recovered / **8 GENUINE destroyed**) is the regression to lock.

## Objective
Make `amount_locator.py` the single source of truth for **cell selection** (which cell carries an account's amount for a Target Amount Role), then migrate the three current paths onto it under a hard no-new-false-positives corpus gate. The scaffold (interface + three return types) exists at `src/dart_footing_reconciler/amount_locator.py`; do **not** change the public interface without an ADR amendment.

## Scope boundary (F2 — do not cross)
The locator owns **cell selection**; its wins are **B-5** (`net_carrying_amount`) and **B-2b** (`current_/noncurrent_portion`). It does **not**: classify accounts (taxonomy), run arithmetic (checks_*), or choose among located hits / filter balance rows (`checks_fs_note._select_note_hit_by_label` — that is where B-2a/B-4 stay).

## Tasks (strangler-fig — one phase per PR; TDD RED before GREEN)

**Phase 0.5 — record reality FIRST (F3):** run `classify_layout` on the acceptance fixtures (더존 N9/N12, 셀트리온 N12-1, 롯데정밀화학) and record the keys that ACTUALLY fire (더존 N9 may be `asset_cost_accumulated_grant_total`, not `_summary`). Add a `category_matrix` handling path (no key exists for 더존 무형 N12 today). Bind strategies to the keys that fire.

**Phase 1 — module only, UNWIRED (corpus must stay byte-identical):**
1. `tests/test_amount_locator.py`: write spec §5.1's failing tests first — including #6 NotApplicable→not_tested, #9 the **real-fixture regression pins** for the 8 destroyed checks (CJ 무형×2, 더존 PPE/투자부동산/리스×2), #10 orthogonality guard.
2. Implement `locate()` + the per-(archetype, role) strategy registry for `net_carrying_amount` + `period_end_balance`. Handle scope-driven column choice, multi-row headers, and the §3.4 abstain/NotApplicable rules.
3. `uv run pytest -q` green; `uv run ruff check` clean. Corpus **byte-identical** to baseline (module not yet called).

**Phase 1.5 — observe coupling (F7/M3):** route ONE company/ONE account through the locator behind a flag; confirm the `_select_note_hit_by_label` pairing rank does not flip unexpectedly before full cutover.

**Phase 2** — route `reconciliation_inputs` balance/net-carrying. **Phase 3** — route `taxonomy._generic_note_row_amount` (locator proposes, taxonomy validates vs `line.amount` via `expected_amount`) + `verification_candidates`. **Phase 4** — `current_/noncurrent_portion` → B-2b.

## Done criteria (every wiring phase)
- `uv run pytest -q` all pass (existing `test_checks_totals*`, `test_taxonomy`, `test_reconciliation_inputs`, `test_verification_candidates`, `test_checks_fs_note` stay green).
- `uv run ruff check` clean on changed files.
- **Corpus regression:** `manifest_2026-06-10-nonfinancial-industry-10` before/after; report 5-status histogram. `matched` ↑/flat; **`unexplained_gap` not ↑ from FP**; legitimate abstentions stay abstained.
- **`scripts/check_per_company_snapshot.py` is a HARD gate** — aggregate gains must not hide per-company destruction.
- **Spot acceptance:** 더존·셀트리온·롯데정밀화학 net-carrying B-5 abstain → matched, diff=0 vs FS, **zero genuine matches destroyed**.

## Division of responsibility
| Role | Does |
|---|---|
| **Codex** | Create/edit files, write tests, run `pytest` + `ruff` + corpus + per-company snapshot, report counts/deltas. Does NOT run git. |
| **Claude** | Commit after each verified batch; review corpus delta for false positives; update `docs/accuracy-backlog.md` as B-items close. |

Report after each phase: files changed, pytest pass/fail, ruff, the corpus before/after 5-status histogram, and the per-company snapshot delta.
