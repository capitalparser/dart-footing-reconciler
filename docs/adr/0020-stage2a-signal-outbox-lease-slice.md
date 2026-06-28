# 0020. Stage 2A — signal outbox, lease vertical slice (synthetic-first)

**Date:** 2026-06-28
**Status:** Accepted (design). First Stage-2 slice. The ADR-0017 hard gate is open for lease (ADR-0019). Implementation is synthetic-tested; the run-path seam + vault-queue wiring are deferred to follow-up slices.
**Inputs:** plan v2 "Stage 2A/2B" + ADR-0016 (envelope = outbox + ack + idempotency + supersession + content-addressed id + atomic write; conservative routing). erp_recon CONTEXT (GL/TB reconciliation target).
**Companion:** `plans/2026-06-27-report-validation-ledger.md`, ADR-0015/0016/0019.

## Context

Stage 1 (ledger) + Stage 1.5 (entity-key core-emit) are merged. The entity-key is now real for lease, so the ADR-0017 hard gate opens for the first cross-module signal: a lease tie-out gap → erp_recon GL drilldown. Stage 2 is large; this ADR scopes the **smallest valuable, independently-testable slice**.

Dependencies: a real end-to-end signal needs the ledger wired into the run path (the seam — a deferred Stage-1 lever) so findings exist in production. That wiring is a separate slice. The signal **machinery** (outbox, envelope, routing) can be built and fully tested against **synthetic findings** without the seam.

## Decision

1. **Synthetic-first slice.** Build and unit-test the outbox + envelope + lease routing against synthetic finding+result inputs (matching the ledger's `findings`×`check_results` shape). The run-path seam and a real end-to-end test are an explicit **next slice**, not this one.

2. **Lease-only routing this slice.** Route only `account_key == "lease_liabilities"`, `status == "unexplained_gap"`, with a resolvable entity key → erp_recon `journal_drilldown_required`. Other accounts/statuses wait for their own slice. (Borrowings entity-key is migrated but routing is added per-account deliberately.)

3. **Conservative routing guards (ADR-0016), enforced here:**
   - `parse_uncertain` → **never** auto-routes to erp_recon/ksox (it is a parser/data-quality concern).
   - `ksox` routing requires **repeated + human-confirmed** — **not emitted in this slice** (no single-gap → control-deficiency).
   - **consolidated-basis** gap → emit a `consolidation_bridge_drilldown_candidate` (component mapping / consolidation adjustments), **not** a direct GL mismatch.
   - Every signal carries the **full entity key** (account / consolidation_basis / report_period / balance_level) from the real CheckResult fields; a level-mismatch is distinguished from a bounded-Σ(total-only) match.

4. **Envelope = outbox row + atomic file (ADR-0016 fields).** A `cross_module_signals` ledger row **plus** a YAML envelope written atomically (tmp → fsync → atomic rename). Content-addressed `signal_id`; fields: `idempotency_key, dedupe_key, schema_version, producer_module, producer_version, run_id, run_fingerprint, source_file_hash, rulepack_version, finding_id, result_id, result_lineage_key, destination_module, signal_type, produced_at, stale_after, supersedes_signal_id, payload_hash`. Delivery contract = **at-least-once + idempotent consumer**; a **fake-consumer contract test** is the slice's gate (duplicate / supersede / stale handling).

5. **Schema in 09 first; queue path configurable.** The envelope JSON-schema lives in 09 (`schema/cross_module_signal.schema.json`) for now; promoting it to the vault-level `02_Areas/Shared_Audit_Kernel/` (so erp_recon/ksox consume one copy) is a **vault-level follow-up** under the PAS Harness adapter rule. The outbox writes to a **configurable queue directory** (default 09-local, e.g. `out/cross_module_queue/`); wiring it to the vault `Harness/queue/` is part of the seam/integration follow-up. 09 imports **no consumer**.

6. **No verdict impact.** Signals are emitted strictly downstream of findings; nothing in the engine/verdict path reads them. (When the seam lands, the corpus gate still applies to the engine, never to signal emission.)

## Alternatives considered

- **Wire the seam first, then emit real signals.** Reasonable, but couples this slice to a separate (run-path) change and a real corpus; synthetic-first keeps the machinery testable in isolation and lets the seam land on its own gate.
- **Write straight to the vault `Harness/queue/`.** Rejected for now: couples the 09 repo to vault paths and to the Harness adapter lifecycle; a configurable local queue keeps 09 independently testable (ADR-0001) and defers the vault integration to a governed follow-up.
- **Route borrowings too (it's migrated).** Deferred: routing is added per-account on purpose so each account's signal semantics (and false-positive profile) are reviewed before it ships.

## Consequences

- 09 gains a `cross_module.py` (routing + atomic envelope writer + outbox) and a schema, fully synthetic-tested; the `cross_module_signals` table (already present, empty) gets its first writer.
- The first real end-to-end signal awaits the **seam** slice (run path → artifact → ledger → findings → outbox) + the **vault queue / shared-schema promotion** follow-up.
- erp_recon consumes nothing yet; the durable envelope + ack contract means the signal survives until erp_recon implements an inbox.
