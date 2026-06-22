# 0008. Canonical Amount Locator — single arbiter for cell selection

**Date:** 2026-06-21
**Status:** Accepted (design) — implementation handed to Codex, corpus-gated per phase
**Related:** ADR-0003 (signature-driven verification — status amended below), ADR-0006 (schema/role vocabularies), ADR-0007 (structure-aware footing). Spec: `docs/superpowers/specs/2026-06-21-canonical-amount-locator.md`.

## Decision

Introduce one deep **Module**, the **Canonical Amount Locator** (`amount_locator.py`), as the single source of truth for **cell selection** — "which `(row, col)` carries the `<Target Amount Role>` amount for `<Core Account>` in `<this table>`?". All three current paths (`taxonomy.py`, `reconciliation_inputs.py`, `verification_candidates.py`) are migrated to call it. The locator does **not** classify accounts and does **not** run arithmetic; it sits between classification (taxonomy) and the axis checks.

Interface (the Seam):

```
locate(table, account_key, role: TargetAmountRole) -> LocatedAmount | Abstain
```

- `TargetAmountRole` is a **closed 7-value vocabulary** (CONTEXT.md): `period_end_balance`, `net_carrying_amount`, `cash_like_movement`, `disclosed_total`, `expense_allocation`, `current_portion`, `noncurrent_portion`.
- `Abstain` carries one code from the existing `PARSE_UNCERTAIN_REASONS` set and maps to the `parse_uncertain` Outcome Label — **abstain-over-guess is preserved**.
- Per-archetype cell-selection strategy lives behind the seam, bound to each `layout_variants` archetype.

## Context

A 2026-06-21 architecture review (CONTEXT.md domain language + Explore depth pass) found that the engine has **no single arbiter for cell selection**. The same question — "which cell is this account's amount?" — is answered independently and divergently in at least three places:

- `taxonomy._generic_note_row_amount` (rightmost-column-that-matches heuristic),
- `reconciliation_inputs._asset_total_balance_amount` / `_asset_family_total_balance_amount` / `_asset_family_total_columns`,
- `verification_candidates`' 50+ layout-specific extractors.

Because each path picks cells under its own rules, the same `(table, account)` can yield **different cells** in different paths. This is the structural root of the accuracy backlog's recurring failure family. **Scope correction (ADR-0009 F2):** the locator owns *cell selection*; its direct wins are **B-5** and **B-2b** below. **B-2a / B-4 stay check-layer pairing decisions** (`checks_fs_note._select_note_hit_by_label` + `_is_balance_row`) — they merely *benefit* from cleaner located cells and are NOT moved into the locator.

- **B-2a / B-4** (check-layer; benefit only) — wrong note/row *paired* to a statement line (재분류 행·발행차금 contra·과분류된 무관 주석) → false `unexplained_gap`. Stays in `checks_fs_note`.
- **B-5 (DEFERRED)** — net carrying amount lives in a different cell per table archetype (net-vs-gross matrix → net column; rollforward → 기말 column; category matrix → row sum). The 2026-06-16 fix attempt was reverted (12 recovered / 8 genuine matches destroyed) precisely because cell selection was patched in one path while another still grabbed gross. The diagnosis explicitly concluded a *dedicated multi-archetype model* is required, not a slice.
- **B-2b (DEFERRED)** — FS 단기/장기 합산 needs level-aware cell selection (유동/비유동), which no path expresses.

These are not separate bugs; they are one missing module. Without it, every accuracy fix is whack-a-mole across files with no **locality**.

This decision also reframes ADR-0003. ADR-0003 declared *signature-driven verification dispatch* accepted, but the verification engine never adopted it (see amendment). The locator captures the *defensible* core of that intent — data-driven, archetype-aware selection — applied to **cell selection** (a closed, testable problem) rather than to **verification dispatch** (which stays harness-based).

## Considered Options

1. **Keep patching per-path (rejected).** Status quo. Every B-item touches 2–3 files; fixes in one path silently disagree with another (the documented cause of the B-5 revert). No locality, accuracy ceiling is structural.
2. **Complete the ADR-0003 signature→attempt engine (rejected for now).** Build the full 17-signature library + `essential_notes.py` + attempt registry as the verification front door. Largest build, re-litigates a working harness pipeline, highest risk to verified gains (matched ~4739). Deferred as a possible north star *after* the locator proves the archetype-binding pattern.
3. **Canonical Amount Locator (accepted).** A single deep module for cell selection only, migrated path-by-path under a corpus gate. Bounded interface, directly unit-testable, leaves the harness/checks verification pipeline intact. Turns B-5/B-2b from "deferred, needs a model" into "one module, enumerated archetypes."

## Consequences

- **+ Locality:** every cell-selection accuracy fix lands in one module; the B-series stops being cross-file whack-a-mole.
- **+ Leverage:** a new table shape = one archetype→strategy spec, not a new extractor plus edits in three paths.
- **+ Test surface:** the locator is unit-testable through its own interface ("더존 PPE N9 → net = 장부금액 column"), removing today's asymmetry where accuracy is caught only by the end-to-end corpus.
- **+ B-5 / B-2b become tractable:** `net_carrying_amount` across 3 archetypes and `current_portion`/`noncurrent_portion` get a home.
- **− Blast radius:** migration touches three high-accuracy modules. Mitigated by **strangler-fig**: build the module first (no wiring), then route one path at a time, each behind the mandatory **corpus regression gate** (matched ↑, `unexplained_gap` must not rise from new false positives). Big-bang replacement is prohibited.
- **−** A new closed vocabulary (`TargetAmountRole`) is added; it is orthogonal to the three existing role vocabularies (ADR-0006 §S2) and must not absorb or be absorbed by them.

## Migration (strangler-fig, corpus-gated)

| Phase | Scope | Wiring | Corpus expectation |
|---|---|---|---|
| 0 (Claude) | CONTEXT/ADR/spec + interface scaffold + HANDOFF; demote semantic track | none | unchanged |
| 1 (Codex) | Implement `amount_locator` + archetype strategies for the asset balance / net-carrying family; unit tests for 더존·셀트리온·롯데정밀화학 | module only, not called | unchanged (proves in isolation) |
| 2 (Codex) | Route `reconciliation_inputs` balance/net-carrying selection through locator | 1 path | matched ↑ (recover B-5), `unexplained_gap` not ↑ from FP |
| 3 (Codex) | Route `taxonomy._generic_note_row_amount` + `verification_candidates` extractors | 2 paths | per-path corpus gate |
| 4 (Codex) | `current_portion`/`noncurrent_portion` → B-2b level-aware matching | role extension | corpus gate |

Each phase is independently revertible. A phase that cannot pass the corpus gate stays abstained (honest coverage), not forced.

## Amendment to ADR-0003 (signature-driven verification)

ADR-0003 status is amended from *accepted* to **accepted-but-partially-adopted; verification dispatch deferred**. Findings (2026-06-21):

- `signatures.py` emits only 3 of the 17 designed signatures.
- `semantic_layer` / `semantic_attempts` / `semantic_validation` are wired into `check_pipeline.py` (`build_semantic_validation_report(slice, [])`) but their candidates are **never read** by any harness. Deleting `semantic_validation` changes the 5-status output by zero — it fails the deletion test as a verification contributor.
- The real account-keyed path is `taxonomy` → `reconciliation_inputs` (ADR-0006 §C2 already established this).

**Decision (semantic track, candidate 3):** **demote to diagnostic**, do not delete. The semantic/signature track is relabeled an explicit diagnostic / coverage-discovery overlay for `verify_app` and is separated from the verification pipeline (it must not appear to gate the 5-status output). The signature→attempt dispatch ambition is **deferred**, with the door left open: option 2 above (complete the engine) may revisit it *after* the locator validates archetype-binding. Until then, no code should imply the semantic track verifies anything.
