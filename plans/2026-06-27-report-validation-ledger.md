# Plan v2 — Report Validation Result Ledger & Cross-Module Orchestration

**Date:** 2026-06-27 (v2 — merges GPT Pro cross-model plan review)
**Status:** Plan-reviewed (1 of 2 legs: GPT Pro done; Codex leg pending). Not yet handed to Codex.
**Decision records:** `docs/adr/0015-report-validation-ledger-and-cross-module-orchestration.md` (core decisions), `docs/adr/0016-report-validation-plan-review-findings.md` (review triage + amendments).
**Domain:** `CONTEXT.md` → "Report Validation Result Ledger & Cross-Module Orchestration".
**Branch:** `docs/report-validation-ledger` (off `main`).

## Guiding principle (the one line)

**09's core verdict is sealed into an immutable run artifact; the ledger, findings, signals, and RAG are all downstream projections of that artifact — never inputs to it.** Hold this and the orchestration value is absorbed without touching the doctrine.

## Goal

Evolve 09 from a stateless engine into the vault's first audit-orchestration entry point — without touching the deterministic core — by adding, *around* it: a **Result Ledger** (full 5-status), a **finding projection**, a **coverage/observation** view, a durable **signal outbox**, and an MCP-backed **retrieval lens**.

## Non-goals

- No change to the deterministic core (parse → classify → 4 Harnesses → 5-status `CheckResult`). Ledger may never alter a verdict.
- No SQL-executed arithmetic; no runtime LLM-authored SQL; no DB-driven check enable/disable.
- No own embedding/vector index (retrieval = kreports MCP).
- No XBRL ingestion (DSD/HTML-first). No financial-company scope creep.

## Locked decisions (ADR-0015) + review amendments (ADR-0016)

1. **Fold into 09**, not a new project. 09 = the `report_validation` rule pack.
2. **Ledger around the engine.** Core emits a **sealed immutable artifact**; the materializer consumes only that artifact and **never mutates `CheckResult`**. SQL = persist/aggregate/sort/filter VIEWs only — never re-computes amount/tolerance/gap.
3. **Result Ledger first, finding is a projection.** Store **all 5 statuses** as `check_results`; `findings` = exception projection (`unexplained_gap`/`parse_uncertain`); `coverage_observations` = matched/not_tested/aggregate digest. (Review #1, #5.)
4. **Vocabulary:** core terms preserved; ledger/contract uses plan vocabulary; mapping in CONTEXT.md. External event taxonomy splits **finding_signal** vs **coverage/observation**.
5. **Cross-module = outbox + envelope + ack contract**, durable, content-addressed, supersedable. 09 imports no consumer.
6. **Retrieval = kreports-MCP-backed**, deferred behind 1–2, split 3A enrichment / 3B reviewer-only candidates. Never promotes a `matched`.

## Verdict-protection invariants (the hard gate — Review #2, Q1)

Count-diff is a smoke test, **not** the gate (counts hide offsetting swaps — this is already 09's stated reason for its check-level corpus gate). The gate is a **canonical full-result fingerprint diff**:

```
ledger-disabled core run → canonical_check_results.ndjson
ledger-enabled  core run → canonical_check_results.ndjson
sorted full fingerprint of the two files must be byte-identical.
```

Per-result fingerprint includes: `attempt_id, rule_version, entity_key{account, consolidation_basis, report_period, balance_level}, status, expected/actual/gap/tolerance, abstain_reason|parse_uncertain_reason, source_location_fingerprints, normalization_policy_id`.

Plus boundary tests:
- core package does **not import** ledger/sqlite/materializer modules (static import-boundary test).
- materializer input = sealed run artifact only (no live `CheckResult` objects).
- ledger write failure → `ledger_materialization_failed` operational event; **core verdict/report unchanged**.
- rule catalog is an execution-time **snapshot** written *into* the ledger; core never **reads** the ledger to decide coverage (else `not_tested` becomes DB-dependent).
- finding projection **never drops** an exception: `unexplained_gap`/`parse_uncertain` always produce a finding; a failed follow-up is a `followup_generation_error`, not a dropped finding.
- amounts stored as **scaled integer or decimal-string + scale** — SQLite `REAL` forbidden.

## Staged plan

### Stage 0 — Grill close + plan review (done)
ADR-0015, ADR-0016, CONTEXT.md terms, this plan. Next: Codex review leg, then handoff.

### Stage 1A — Immutable CheckResult Manifest (the seal)
- Core run emits canonical NDJSON: **all 5 statuses**, full entity key, source fingerprints, `rule_version`, `config_hash`, `run_fingerprint`.
- This is the audit-evidence/rebuild source. Existing HTML/Excel/cockpit keep working from live results (re-pointing them at the artifact = optional/deferred, Review calibration #2).
- **Files (Codex):** `run_artifact.py` (serialize + fingerprint); tests for determinism + fingerprint stability.

### Stage 1B — SQLite Result Ledger
- Materialize the manifest (read artifact only). Tables: `validation_runs, check_results (all 5), result_evidence, findings (projection), coverage_observations, reviewer_decisions (overlay), cross_module_signals (filled Stage 2)`.
- Review VIEWs: `v_findings_by_domain`, `v_coverage_by_account`, `v_pending_cross_module_signals` — aggregate/sort/filter only.
- **Gate:** the fingerprint diff + boundary tests above; corpus hard gate unchanged-pass on both baselines.
- **Files (Codex):** `ledger.py` (schema + materialize), `findings.py` (projection), `coverage.py` (observation digest); tests pin verdict-immutability, no-import-boundary, exception-never-dropped.

### Stage 2A — Signal Outbox Contract (thin, contract-first)
- Producer **outbox** (09-local SQLite is source of truth) + YAML envelope in `Harness/queue/`; consumer writes ack/reject to `Harness/ack/`; 09 reconciler reads acks to update `cross_module_signals` (Review Option A — 09 still imports no consumer).
- Envelope fields: `signal_id (content-hash), idempotency_key, dedupe_key, schema_version, producer_module, producer_version, run_id, run_fingerprint, source_file_hash, rulepack_version, finding_id|result_id, result_lineage_key, destination_module, signal_type, produced_at, stale_after, supersedes_signal_id, payload_hash`.
- **Atomic write:** tmp → fsync → atomic rename. Producer reconciliation for orphan/half-written/duplicate envelopes.
- **Supersession/retraction:** a later run that resolves a prior gap (e.g. parser fix → matched) must mark the prior signal `superseded`/`retracted` (carry `finding_lifecycle{first_seen, last_seen, resolved_in_run_id, resolution_reason}`).
- Consumer-side state machine (claimed/accepted/rejected/dead_letter/expired) is **defined as schema now, implemented when a real consumer exists**. Stage 2A gate = **fake-consumer contract test** (at-least-once delivery + idempotent consumer; duplicate/supersede/stale handling).
- **Files (Codex):** `cross_module.py` (outbox + atomic writer + reconciler), `Shared_Audit_Kernel/*.schema.json` (vault-level), fake-consumer contract tests.

### Stage 2B — Conservative rule-based routing (V0; no LLM router)
- `unexplained_gap` **+ high source certainty** → `erp_recon` *draft* signal.
- `parse_uncertain` → **parser/data-quality queue**; **no** auto ERP/KSOX routing (`needs_human_review`).
- **Repeated** `unexplained_gap`, **human-confirmed** → `ksox` candidate (never a single raw gap → control-deficiency).
- Qualitative omission candidate → reviewer lens only; no auto routing.
- **Consolidated-basis gap** → not a direct GL mismatch: emit a `consolidation_bridge_drilldown_candidate` carrying `consolidation_basis, entity_scope, requires_component_mapping, requires_consolidation_adjustment_review, suggested_drilldown_scope` (Review #10A).
- Every signal carries the **full entity key** + reconciliation granularity; bounded-Σ(total-only) matches are distinguished from level mismatches (Review #10B).

### Stage 3A — Retrieval enrichment (safe; can lead 3B)
- kreports-MCP enrichment of **existing deterministic findings** (peer policy / KAM / disclosure pattern / standard basis) → narrative / follow-up / workpaper draft. **No verdict.**
- Persist retrieval provenance: `retrieval_query, retrieval_time, retrieval_source_ids, retrieved_excerpt_hashes, model_used, prompt_version, output_hash` (Review #10F).

### Stage 3B — Qualitative review candidates (reviewer-only, later)
- `disclosure_omission_candidate` / `policy_consistency_candidate` as a **separate `finding_class` (or table `qualitative_review_items`)** — outside the 5-status verdict, `needs_review`, low `operational_priority`, FP-risks listed (materiality, alternate table, narrative disclosure, industry practice, basis/period presentation). **No auto cross-module routing before human review.**

### Stage 4+ — Deferred
XBRL-PDF consistency (reconcile with DSD/HTML-first first); peer-pattern mining (candidate-rule, needs_human_review); shared **read-model/index** (not authoritative store) once a 2nd producer exists.

## Supporting designs (from review)

**Content-addressed IDs (Review #10C):**
```
fact_id   = hash(source_doc_hash + source_location + original_label + normalized_amount + unit)
result_id = hash(run_id + attempt_id + entity_key + evidence_fact_ids + status)
finding_id= hash(result_id + finding_projection_version)
signal_id = hash(finding_id + destination_module + signal_type + routing_version)
result_lineage_key = hash(source_doc_identity + attempt_id + entity_key + rule_semantic_id)  # cross-run continuity (no run_id)
```
No SQLite autoincrement IDs in envelopes (rebuild changes them).

**Run lifecycle (Review #7):** idempotent only on identical `run_fingerprint = hash(source_file_hash, canonical_input_hash, engine_version, parser_version, classifier_version, rulepack_version, config_hash, normalization_policy_version)`. A rulepack/parser change on the same file → a **new run** (may retract prior findings). Keep **both** per-run immutable artifact (evidence/rebuild) and cumulative SQLite (query index, rebuildable from artifacts).

**Tiered fact persistence (Review #8):**
- Tier 1 (SQLite, mandatory): facts a CheckResult used + finding evidence + source locations + normalization metadata.
- Tier 2 (SQLite, light): per-attempt candidate fact fingerprints + rejected/abstained reason + classifier confidence bucket + candidate count (explains abstain & cross-run diff & "absence").
- Tier 3 (per-run artifact, not SQLite): full LocatedAmount universe (compressed NDJSON) for reproducibility.

**Triage priority, not severity (Review #9):** replace `severity = amount × confidence` (mis-ranks large-amount/low-confidence). Two axes + reason:
- `impact_magnitude` {affected_amount_abs, %total_assets, %revenue, %materiality_if_available}
- `evidence_reliability` {source certainty, parse confidence, classifier confidence, reconciliation granularity}
- `triage_reason` {large_gap, low_parse_confidence, repeated_gap, high_confidence_unexplained_gap, structural_pattern_candidate} → routes to a queue. Confidence chooses **which queue**, not a lower priority. Label: **`operational_priority is not audit risk`**.

**Reviewer decision (Review #10D):** taxonomy {confirmed_exception, false_positive_parser/classifier/rule_scope, immaterial_no_action, routed_to_erp/ksox, resolved_by_rerun, superseded, needs_more_evidence}. `core_status` immutable; `review_status` is a **mutable overlay**, never overwrites the verdict.

**Shared Audit Kernel = schema-only (Review #6):** share `cross_module_signal.schema.json, validation_observation.schema.json, entity_key.schema, source_location.schema, amount.schema, status_vocabulary.schema, ack_reject.schema` + schema-compat tests + shared ID namespace. Data stays 09-local. Central, when needed = shared read-model/index, not authoritative store.

**Other guards:** RAG snapshot reproducibility (3A); schema migration (artifacts append-only & never migrated, SQLite rebuildable, versioned materializers, migration test corpus); queue privacy (payload = summary + source refs; sensitive originals via local reference only); ADR-stated rule-DB guard ("metadata + registered Python Attempt refs only; no executable arithmetic; no runtime LLM-SQL; no runtime SQL verdict logic").

## Process (Tier 3)
1. ✅ Grill (ADR-0015) + GPT Pro plan review (ADR-0016) + plan v2.
2. **Codex plan-review leg** (`/codex:review`) — feasibility/code-ground on the revised plan.
3. `HANDOFF.md` update → Codex implements 1A → 1B (TDD, corpus-gated), then 2A → 2B.
4. Code review 2-leg → `docs/adr/{NNNN}-review-findings.md`.
5. PR to `main` on explicit user request.

## Still-open for the Codex leg
- Where exactly to insert the artifact-seal seam in the current pipeline (post-`assemble_report_checks`, before report layer) without perturbing existing report generation.
- `run_fingerprint` version-source plumbing (engine/parser/classifier/rulepack versions are not all surfaced today).
- Fake-consumer contract test shape for the outbox (how strict to assert idempotency/supersession without a real erp_recon inbox).
