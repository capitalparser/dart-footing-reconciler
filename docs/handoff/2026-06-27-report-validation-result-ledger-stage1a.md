# Codex Handoff — Report Validation Result Ledger (Stage 1A → 1B)

**Date:** 2026-06-27
**For:** Codex (implementation). Claude did grill + 1-leg plan review; this is the implementation contract.
**Branch:** implement on `docs/report-validation-ledger` — it carries this brief + plan v2 + ADR-0015/0016 + the CONTEXT terms, and is based on `main`. (Do not branch from bare `main`; it does not yet have these docs.) Orthogonal to the open borrowings PR #21 — see "Parallel work" below.
**Read first (inputs):** `plans/2026-06-27-report-validation-ledger.md` (v2), `docs/adr/0015-...`, `docs/adr/0016-...` (review amendments), `CONTEXT.md` → "Report Validation Result Ledger & Cross-Module Orchestration". This brief does not restate them; it scopes the build.

## One-line contract

Add a **Result Ledger around the engine** that records every run's full 5-status results — **without the deterministic core ever depending on it, reading it, or having its verdict changed by it.** The core verdict is sealed into an immutable artifact; the ledger is a downstream projection of that artifact.

## Scope of this handoff

- **Stage 1A** — sealed immutable run artifact (the seal).
- **Stage 1B** — SQLite Result Ledger materialized from the artifact.
- **NOT in this handoff:** Stage 2 (signal outbox), Stage 3 (retrieval). Do not start them. `cross_module_signals` table is created empty in 1B; nothing writes to it yet.

## Stage 1A — Immutable CheckResult Manifest

**Goal:** after the pipeline produces `list[CheckResult]`, serialize a canonical, deterministic NDJSON artifact.

**Seam (open question — you decide, justify in code/ADR):** insert post-`check_pipeline.assemble_report_checks` (after scope slicing + 4-Harness flatten), parallel to the report layer. The existing HTML/Excel/cockpit generation **must be untouched** — they keep reading live results this round; re-pointing them at the artifact is explicitly deferred.

**Artifact contents (per result row):**
`attempt_id, rule_version, entity_key{account, consolidation_basis, report_period, balance_level}, status (all 5), expected_amount, actual_amount, gap_amount, tolerance, abstain_reason|parse_uncertain_reason, confidence, source_location_fingerprints, normalization_policy_id`.

**Run header:** `run_fingerprint = hash(source_file_hash, canonical_input_hash, engine_version, parser_version, classifier_version, rulepack_version, config_hash, normalization_policy_version)`. Some version sources are not surfaced today — surfacing them is part of this task (open question; if a version is genuinely unavailable, record `unknown` explicitly, don't fabricate).

**Content-addressed IDs (no autoincrement):**
```
fact_id            = hash(source_doc_hash + source_location + original_label + normalized_amount + unit)
result_id          = hash(run_id + attempt_id + entity_key + evidence_fact_ids + status)
result_lineage_key = hash(source_doc_identity + attempt_id + entity_key + rule_semantic_id)   # cross-run continuity, no run_id
```

**Amounts:** scaled integer or decimal-string + scale. Never float in the artifact's canonical form.

**Determinism:** same input → byte-identical artifact. Exclude wall-clock timestamps from the fingerprinted payload (a `produced_at` may live in a non-fingerprinted header field only).

**Tests (TDD, write first):** same input → identical artifact; fingerprint stable across runs; all 5 statuses representable; entity-key completeness; amounts never float.

**Files (suggested):** `src/dart_footing_reconciler/run_artifact.py`, `tests/test_run_artifact.py`.

## Stage 1B — SQLite Result Ledger

**Goal:** materialize the artifact into SQLite. **Input = the sealed artifact only.** Never import or read live `CheckResult` objects in the materializer.

**Tables:** `validation_runs`, `check_results` (all 5 statuses — this is the ledger's centre, not `findings`), `result_evidence`, `findings` (exception projection: status ∈ {unexplained_gap, parse_uncertain}), `coverage_observations` (matched/not_tested/aggregate digest), `reviewer_decisions` (overlay; `core_status` immutable, `review_status` mutable), `cross_module_signals` (created empty).

**VIEWs:** `v_findings_by_domain`, `v_coverage_by_account`, `v_pending_cross_module_signals` — **aggregate/sort/filter only; never re-compute amount/tolerance/gap in SQL.**

**Amounts:** scaled-integer or decimal-string + scale columns. **SQLite `REAL` is forbidden.**

**Finding projection rule:** an exception (`unexplained_gap`/`parse_uncertain`) **always** produces a `findings` row. If follow-up generation fails, record a `followup_generation_error` — never drop the finding.

## THE HARD GATE (verdict-immutability — do not merge without it)

This is the load-bearing acceptance test. A 5-status count diff is **not** the gate (counts hide offsetting swaps).

1. **Full-result fingerprint diff:** run the corpus with ledger materialization **disabled** vs **enabled**; both emit `canonical_check_results.ndjson`; the sorted full fingerprints must be **byte-identical**. (Fingerprint = attempt × entity_key × status × expected/actual/gap/tolerance × abstain_reason × source_location × normalization_policy.)
2. **Import-boundary test (static):** the core package does **not** import `run_artifact`/`ledger`/sqlite/materializer for its verdict path. Materializer may import core types for deserialization only; core must not import materializer.
3. **Ledger-failure isolation:** simulate a SQLite write failure → it surfaces as a `ledger_materialization_failed` operational event; the core verdict, the 5-status output, and the existing HTML/Excel reports are **unchanged**.
4. **No DB-driven coverage:** the rule catalog is written *into* the ledger as a run-time snapshot; the core never *reads* the ledger to decide which checks run (else `not_tested` becomes DB-dependent).
5. **Corpus hard gate unchanged-pass:** `scripts/check_per_company_snapshot.py` passes on both baselines (10-co `per_company_counts.json` + 18-co expansion baseline); the check-level before/after `comm` diff shows **zero** change to matched+gap sets.

**Files (suggested):** `src/dart_footing_reconciler/ledger.py` (schema + materialize), `findings.py` (projection), `coverage.py` (observation digest); `tests/test_ledger.py`, `tests/test_ledger_verdict_immutability.py`, `tests/test_ledger_import_boundary.py`.

## Hard "DO NOT"
- Do **not** run any arithmetic in SQL (footing/tie-out stays in Python `checks_*`).
- Do **not** use SQLite `REAL` for amounts.
- Do **not** let the core read the ledger or import the materializer.
- Do **not** mutate `CheckResult` objects in the materializer (read the sealed artifact).
- Do **not** drop an exception finding on follow-up failure.
- Do **not** touch existing HTML/Excel/cockpit generation.
- Do **not** start Stage 2/3 (no signal emission, no envelope, no MCP retrieval).
- Do **not** add any non-stdlib dependency (sqlite3 is stdlib; that's all that's needed).

## The proven loop (same as PR #19/#20 — unchanged)
1. Work on `docs/report-validation-ledger` (carries the docs; based on `main`).
2. TDD: regression pins first (write the gate tests before the materializer).
3. **Corpus hard gate** (the 5 checks above) before any claim of done.
4. `uv run pytest -q` ×2 (deterministic) + `uv run ruff check` clean.
5. Cross-model code review 2-leg (Opus `code-reviewer` + Codex adversarial) before merge → `docs/adr/{NNNN}-review-findings.md` (next free number is 0017).
6. PR to `main` on **explicit user request** (Claude is git owner; Codex no git).

## Open questions you must resolve (and record)
1. **Artifact seam insertion point** — exactly where post-`assemble_report_checks`, without perturbing report generation. Record the choice.
2. **`run_fingerprint` version plumbing** — surface engine/parser/classifier/rulepack/normalization versions; where each lives today; `unknown` where genuinely absent.
3. **Ledger lifecycle** — cumulative SQLite keyed by `run_fingerprint` (not file_hash alone: same file + new rulepack = a new run). SQLite must be rebuildable from per-run artifacts (artifacts are append-only, never migrated).

## Parallel work / conflict avoidance
- Open borrowings PR #21 (`feat/level-aware-borrowings-bonds`) edits `checks_*` (within the verdict path). This ledger work is **downstream of** the verdict path and lives in **new files** — disjoint, low conflict risk. Branch from `main`; if #21 merges first, rebase (no expected overlap).
- Project 9 is its own repo (origin `capitalparser/dart-footing-reconciler`); it is OUTSIDE the central vault Harness, so the vault parallel-lease contract does not apply here — use git branches.
