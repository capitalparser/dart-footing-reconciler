# 0016. Report-validation plan — cross-model review findings (GPT Pro leg)

**Date:** 2026-06-27
**Status:** Accepted. Amends the implementation specifics of ADR-0015 (no decision reversed).
**Inputs:** GPT Pro adversarial review of `plans/2026-06-27-report-validation-ledger.md` (v1). This is the first of the Tier-3 two-leg plan review (Codex leg pending).
**Companion:** ADR-0015 (core decisions), `plans/2026-06-27-report-validation-ledger.md` (v2 merges these).

## Context

ADR-0015 folded the report-validation tool into 09 as a ledger-around-engine with cross-module envelopes. The GPT Pro review accepted all five core decisions but found three structural weaknesses and a set of audit-domain gaps. Each was checked against 09's existing doctrine before acceptance (per `receiving-code-review`: verify, don't perform). Notably the review's central catch independently re-derived 09's existing gate doctrine.

## Decision — none of the five ADR-0015 decisions is reversed; the following amendments are adopted

1. **Stage 1 is a Result Ledger, not a Finding Ledger.** Store **all 5 statuses** as `check_results`; `findings` = exception projection; add `coverage_observations` (matched / not_tested / aggregate digest). Rationale: a finding-centric ledger erodes 09's "`not_tested` is coverage, never dropped" and breaks future consumers that want positive tie-out evidence.

2. **The verdict-immutability gate is a canonical full-result fingerprint diff, not a 5-status count diff.** Counts hide offsetting swaps (A's `matched` ↔ B's `unexplained_gap`). *This is already 09's stated reason for using a check-level corpus diff over per-company counts* (HANDOFF.md, architecture-overview §2.4) — the amendment extends that existing gate to the ledger. Fingerprint = `attempt × entity_key × status × expected/actual/gap/tolerance × abstain_reason × source_location × normalization_policy`.

3. **Verdict-protection invariants (structure, not just a test):** sealed immutable run artifact as the materializer's only input; materializer never mutates `CheckResult`; static import-boundary test (core ⊥ ledger); ledger failure → operational event, never alters the verdict/report; rule catalog is a written snapshot, core never *reads* the ledger for coverage; exception findings are never dropped on follow-up failure; amounts as scaled-integer/decimal-string (SQLite `REAL` forbidden).

4. **Cross-module = outbox + envelope + ack contract**, not a bare durable YAML. Content-addressed IDs (no autoincrement in envelopes); `idempotency_key`, `schema_version`, `stale_after`, `supersedes_signal_id`, `payload_hash`; atomic write (tmp→fsync→rename); **supersession/retraction** (a parser-fix run that resolves a gap must retract the prior signal). *Calibration:* the consumer-side state machine is defined as schema now but implemented when a real consumer exists; the Stage-2A gate is a **fake-consumer contract test** (at-least-once + idempotent consumer). Ack via 09 reading `Harness/ack/` (Option A) — 09 still imports no consumer.

5. **Conservative routing.** `parse_uncertain` never auto-routes to ERP/KSOX (→ parser/data-quality queue). KSOX only on **repeated + human-confirmed** gaps (a single raw gap → control-deficiency is over-interpretation). **Consolidated-basis** gaps route as a `consolidation_bridge_drilldown_candidate` (component mapping / consolidation adjustments / eliminations), **not** a direct GL mismatch. Every signal carries the full entity key; bounded-Σ(total-only) matches are distinguished from level mismatches.

6. **Routing targets are not only findings.** Split the external taxonomy: `finding_signal` (exceptions) vs `coverage/validation_observation` (matched digest, not_tested coverage gap, rule-coverage summary). `matched` is a per-company **aggregate digest**, never per-row signal spam.

7. **Triage priority, not severity.** Drop `severity = amount × confidence` (mis-ranks large-amount/low-confidence, which is high parse-review priority). Two axes (`impact_magnitude`, `evidence_reliability`) + `triage_reason` routing; confidence selects the queue, not a lower priority; explicit label `operational_priority is not audit risk`.

8. **Run identity = `run_fingerprint`, not file_hash.** Include engine/parser/classifier/rulepack/config/normalization versions; same file + new rulepack = a new run. Keep both per-run immutable artifact (evidence/rebuild) and cumulative SQLite (rebuildable index).

9. **Tiered fact persistence.** SQLite: consumed facts + light candidate trace (abstain reasons, candidate fingerprints) — needed to explain abstain, cross-run diff, and "absence" for omission candidates. Per-run artifact: full LocatedAmount universe (not in SQLite).

10. **Stage 3 split + qualitative isolation.** 3A = retrieval enrichment of existing deterministic findings (safe; provenance-snapshotted). 3B = new qualitative candidates as a separate `finding_class`/table, reviewer-only, no auto-routing. Deterministic and qualitative findings never share the same evidence language.

11. **Shared Audit Kernel = schema-only** (+ shared ID namespace + schema-compat tests); data stays 09-local; central, when needed, is a read-model/index, not an authoritative store.

12. **Reviewer decision is an overlay.** `core_status` immutable; `review_status` mutable; a taxonomy of decisions; review never overwrites the verdict.

13. **Rule-DB guard in writing:** the rule registry stores metadata + registered Python Attempt references only — no executable arithmetic, no runtime LLM-authored SQL, no runtime SQL-authored verdict logic.

## Consequences

- Plan v2 restructures Stage 1 → 1A (immutable manifest seal) + 1B (Result Ledger), Stage 2 → 2A (outbox contract) + 2B (conservative routing), Stage 3 → 3A/3B.
- The load-bearing structural move is the **sealed artifact seam** (core → artifact → {existing reports, materializer}); re-pointing existing HTML/Excel at the artifact is deferred (verdict protection only needs the materializer to read the seal, not the reports).
- One review point not yet closed: where to insert the artifact seam without perturbing existing report generation, and surfacing the version sources for `run_fingerprint` — handed to the Codex review leg.
