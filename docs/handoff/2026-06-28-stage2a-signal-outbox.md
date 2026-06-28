# Codex Handoff — Stage 2A signal outbox, lease slice (ADR-0020)

**Date:** 2026-06-28
**Branch:** `feat/stage2-signal-outbox` (off `main`).
**Read first:** `docs/adr/0020-stage2a-signal-outbox-lease-slice.md`, `docs/adr/0016-...` (envelope contract), `plans/2026-06-27-report-validation-ledger.md` (Stage 2A/2B). The `cross_module_signals` table already exists (empty) in `ledger.py`; `check_results` now carries the real entity key (Stage 1.5).

## One-line contract

Emit a durable, idempotent, content-addressed **signal** from a lease tie-out gap to erp_recon — as an **outbox row + atomic YAML envelope** — built and unit-tested against **synthetic** finding+result inputs. No run-path seam, no vault paths, no consumer import, no verdict-path change.

## Scope (this slice only)

Route ONLY: `account_key == "lease_liabilities"` AND `status == "unexplained_gap"` AND a resolvable entity key → erp_recon `journal_drilldown_required`. Everything else is out of scope this slice.

## Build

1. **`src/dart_footing_reconciler/cross_module.py`:**
   - Input: a finding joined with its check_result (a dict/dataclass carrying: finding_id, result_id, result_lineage_key, run_id + run header fields, status, account_key, consolidation_basis, report_period, balance_level, gap_amount, evidence/source locations). Define a small input type; do NOT require the live ledger/seam.
   - `route_finding(finding) -> Signal | None`: apply the conservative rules (below). Returns a Signal for an in-scope lease gap, else None.
   - `write_signal(signal, queue_dir, conn=None)`: insert the `cross_module_signals` outbox row (if a sqlite conn is given) AND write the YAML envelope **atomically** (tmp → `os.fsync` → `os.replace`) into `queue_dir` (configurable; default a 09-local dir, e.g. `out/cross_module_queue/`). Reconcile orphans/duplicates by `idempotency_key`.
   - Content-addressed `signal_id = hash(finding_id + destination_module + signal_type + routing_version)` (no autoincrement). Envelope fields (ADR-0016): `signal_id, idempotency_key, dedupe_key, schema_version, producer_module="09_dart_footing_reconciler", producer_version, run_id, run_fingerprint, source_file_hash, rulepack_version, finding_id, result_id, result_lineage_key, destination_module="erp_recon", signal_type, produced_at (pass in; do NOT call Date.now/time.time at hash time — keep the fingerprint deterministic), stale_after, supersedes_signal_id, payload_hash`.
   - Payload for lease → erp_recon (`journal_drilldown_required`): full entity key (account/consolidation_basis/report_period/balance_level), gap_amount, related_accounts (["lease_liability","right_of_use_asset"] style), suggested GL queries (drilldown the lease_liability account for the period; closing-entry / post-close manual entries), and the source locations.

2. **Conservative routing guards (enforce, with tests):**
   - `parse_uncertain` → NEVER routes to erp_recon/ksox (route to a `data_quality` signal_type or return None per ADR-0016). 
   - `ksox` → NOT emitted this slice (requires repeated + human-confirmed; do not single-gap → control-deficiency).
   - `consolidation_basis == "consolidated"` → signal_type `consolidation_bridge_drilldown_candidate` (NOT a direct GL mismatch); payload notes component mapping / consolidation adjustments.
   - Missing/`unknown` entity-key dims that make the target ambiguous → return None (abstain) rather than emit a vague signal.
   - Distinguish a level-mismatch from a bounded-Σ(total-only) match in the payload.

3. **`schema/cross_module_signal.schema.json`** (in 09 for now): JSON-schema for the envelope. Add a conformance test that every emitted envelope validates (use a stdlib check or a tiny hand-rolled validator — do NOT add jsonschema as a dep unless already present).

4. **Fake-consumer contract test:** a synthetic consumer that reads envelopes from the queue dir and proves **at-least-once + idempotent**: processing the same envelope twice is a no-op (dedupe by `idempotency_key`); a `supersedes_signal_id` envelope retracts/replaces the prior; a `stale_after`-past envelope is skipped. Plus: atomic-write (no half-written file visible), outbox-row ↔ envelope `payload_hash` match, orphan reconciliation.

## Hard "DO NOT"
- Do NOT wire the run-path seam or touch the engine/verdict path (separate slice).
- Do NOT route parse_uncertain or emit ksox signals this slice.
- Do NOT write to any vault path (`~/vault/Harness/...`, `02_Areas/...`) — queue dir is 09-local/configurable.
- Do NOT import erp_recon or any consumer.
- Do NOT put a wall-clock timestamp inside any hashed/fingerprinted field (pass produced_at in; keep ids deterministic for tests).
- Do NOT add a non-stdlib dependency.

## Verify
Synthetic only — no gitignored corpus, no seam. `uv run pytest -q` x2 (deterministic) + `uv run ruff check`. Leave files uncommitted — Claude owns git and will verify + 2-leg review. Report what you built, the routing rules implemented, and the contract-test results.

## Next slices (NOT now)
- Wire the seam (run path → artifact → ledger → findings → outbox) + a real end-to-end signal test.
- Promote the schema to vault `02_Areas/Shared_Audit_Kernel/` + wire the vault `Harness/queue/` (Harness adapter rule).
- Per-account routing expansion (borrowings, etc.) + ksox (repeated + human-confirmed).
- Remove the ADR-0019 MINOR-1 vestigial param chain before the next entity-key migration.
