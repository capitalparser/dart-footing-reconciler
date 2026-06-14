# ADR 0006 — Schema contract & semantic-layer consolidation

**Date:** 2026-06-14
**Status:** Accepted — C1/S4/C3 done (2026-06-14), C2 done via option B (2026-06-14), S1–S3 in progress

## Context

A re-examination of the tool's data schemas and serialized JSON states (driven by the offline verify-app
work) found that each layer's `@dataclass` is individually clean (all frozen, typed) but the **contract
across layers is implicit and has drifted**. Same concepts (amount, source, role, confidence, account_key,
status) are represented differently per layer, some fields are defined-but-never-populated, and some
computed statuses were hidden from output.

## Decisions taken (Accepted, implemented 2026-06-14)

**C1 — Surface all five statuses.** The status set is `matched / explainable_gap / unexplained_gap /
parse_uncertain / not_tested` (5, defined in `checks.py`). The KPI strip and every `_summary` previously
exposed only 3, hiding `explainable_gap` and — critically — `not_tested` coverage. An auditor could read a
clean verdict while large portions were never tested (silent coverage truncation, which the design kit
forbids). Fixed: `report_html` verdict banner renders all five status tiles; `verify_app` inherits it.

**S4 — One summary function.** Three duplicate `_summary()` (cli, local_report, validation) each counted a
different subset. Replaced by a single `checks.status_summary()` counting all five statuses everywhere.

**C3 — Schema versioning.** Added `checks.SCHEMA_VERSION = "1.0"`, stamped on `foot_local_report`,
`validate`, and `corpus_result` JSON payloads, so archived workpaper (조서) evidence can be read back
against the contract that produced it. Bump on any breaking field/shape change.

CLAUDE.md still documents a 4-status taxonomy; it should be updated to 5 (separate edit, SkillOpt-gated).

## Proposed (pending user ratification)

### C2 — `account_key` zombie field / dual semantic representation

**Finding.** `semantic_layer.SemanticAmountFact.account_key` is **always `None`** and `confidence` is
hardcoded `0.80`. `SemanticAmountFact` is consumed **only** by `semantic_validation.py`, which uses it for
*table placement* (mapping checks to their source table for display/ordering) — not for account-keyed
reconciliation. The **real account-keyed semantic layer** is `taxonomy.py` →
`reconciliation_inputs.py` (`StatementLineInput`, `NoteBalanceInput`, `NoteMovementInput`, …), all of which
carry a populated `account_key`, real confidence, role, and source, and feed the actual checks
(`checks_reconciliation`, `checks_fs_note`, `verification_candidates`, `formula_discovery`).

So the field advertises an SSOT linkage (fact → account → relationship graph) that `semantic_layer` does not
provide. The linkage exists, but on the taxonomy/reconciliation_inputs path.

**Decision (2026-06-14): option B.** `taxonomy` + `reconciliation_inputs` are the canonical account-keyed
semantic SSOT. `SemanticAmountFact` is now an honest *placement fact* (fact_id / table_source / cell_source
/ label / amount / period / role); the never-populated `account_key` and the cosmetic hardcoded
`confidence = 0.80` were **removed**. Verified that the only consumer (`semantic_validation`) and the tests
read solely `cell_source` / `label` / `amount` / `role`, so removal is non-breaking.

Rejected — **A (invest):** populate `account_key` from `taxonomy` and promote `semantic_layer` to the
unified account SSOT. Larger build, only worth it if `semantic_layer` becomes the single front door; no
near-term plan, so YAGNI. Revisit if a unified-SSOT effort starts.

### S1–S3 — Controlled-vocabulary unification

- **S1 `parse_uncertain_reason`:** `label_resolver` defines `LABEL_NOT_FOUND / LOW_CONFIDENCE_MATCH /
  AMBIGUOUS_MULTIPLE / COLUMN_NOT_DETECTED / TABLE_NOT_FOUND / AMOUNT_PARSE_FAILED`, but only some checks use
  them; others write free-form strings. Make it a controlled enum used everywhere so "why couldn't we
  verify" is aggregatable/filterable (audit abstention transparency).
- **S2 role vocab:** `semantic_layer` role (beginning/ending/total/movement), `label_resolver.AccountRole`,
  and `orientation` label groups are three granularities with no mapping. Define the layering explicitly.
- **S3 period vocab:** `table_semantics` and `semantic_layer._period_for_column` both classify 당기/전기
  with slightly different keyword sets (당해·당기현재 vs 당기말현재) — single source to avoid drift.

## Consequences

- Output JSON now self-describes its version; coverage (not_tested) is never hidden.
- Until C2 is ratified, `SemanticAmountFact.account_key` stays a misleading `None`; readers must use the
  taxonomy/reconciliation_inputs path for account resolution.
- A future "canonical data contract" doc (versioned, enum-locked statuses + reasons) is the umbrella these
  fixes move toward.
