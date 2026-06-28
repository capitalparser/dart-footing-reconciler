# 0015. Report-validation tool folds INTO 09 as a ledger-around-engine + cross-module orchestration entry point

**Date:** 2026-06-27
**Status:** Accepted (design). **Amended by ADR-0016** (GPT Pro plan-review leg): Stage 1 = *result* ledger (all 5 statuses) + finding projection; gate = full-result fingerprint diff; cross-module = outbox+ack contract. Implementation is staged and corpus-gated; Stage 1 = result ledger, Stage 2 = signal outbox + routing, Stage 3 = retrieval/qualitative (deferred behind 1–2).
**Inputs:** user "보고서 검증 툴 v0 보강 계획서" + a RAG-vs-SQL cost/role note, reconciled against 09's current state (26k LOC, 13 ADRs, entity-keyed model, deterministic-Python doctrine) via grill-with-docs.
**Companion:** `CONTEXT.md` → "Report Validation Ledger & Cross-Module Orchestration"; `plans/2026-06-27-report-validation-ledger.md`.

## Context

A "보고서 검증 툴" plan proposed a greenfield project — a SQLite-centred validation tool (`report_facts → validation_rules → validation_runs → findings → cross_module_signals`) with SQL checks, a finding ledger, and a router to KSOX / journal-entry-analysis / valuation-review / IFRS-judgment, plus its own directories `01_Projects/report_validation_tool/`, `02_Areas/Report_Validation/`, `02_Areas/Shared_Audit_Kernel/`.

Cross-referenced against 09, the plan's MVP and most of its rule candidates **already exist and are load-bearing** in 09:

- §20/§7.1 MVP "BS 리스부채(유동/비유동) ↔ 리스 주석 총액 본문-주석 대사" = **B-2b, shipped PR #20** (+22 genuine matches, zero false; the 4-dim key `Account × Consolidation Basis × Report Period × Balance Level`, level-split → 유동↔current / 비유동↔noncurrent, total-only → bounded Σ).
- §7.2 주석 내 합계/footing = `checks_totals` + `footing` (NoteInternalHarness).
- §7.4 전기-당기 일관성 = `checks_prior_year` (PriorReportHarness).

So a literal new `report_validation_tool` project would **rebuild a mature 26k-LOC / 891-test engine**. What the plan adds that 09 genuinely lacks: (1) a **persistent finding ledger** (09 is stateless per-run), (2) **cross-module routing** to sibling audit engines (09 only emits HTML/Excel), (3) a **retrieval/qualitative** layer for disclosure-completeness and policy-adequacy (09 is closure-first deterministic arithmetic).

The plan is also SQL-check-centred, which collides head-on with 09's load-bearing doctrine: ADR-0001 "core runs without MCP/DB", and "all arithmetic is deterministic Python; an audit verdict must never carry a false match; abstain over guess."

The RAG-vs-SQL note frames a two-leg model (SQL for facts/findings, RAG for source/peer/standard text). 09 adds a **third leg the note omits**: the arithmetic is already deterministic **Python**, not SQL — which is more controllable and testable than runtime SQL, and even more token-efficient (the engine, not an LLM, computes). And 09 already preserves **Source Location** for every amount, so the note's RAG-use-A (locate the BS page / note page) is a deterministic pointer in 09, not a retrieval problem. RAG's real new value is uses B/C/D (policy adequacy, peer patterns, standard basis) — the qualitative/completeness checks Python cannot do.

## Decision

1. **Fold, do not fork.** 09 *is* the report-validation engine for the financial-statement/note tie-out domain. No new `report_validation_tool` project. 09 becomes the first/reference **`report_validation` rule pack** of the (eventual) shared audit kernel.

2. **Ledger AROUND the engine, never UNDER it.** The deterministic Python core (parse → classify → 4 Harnesses → 5-status `CheckResult`) is **unchanged**. After a run, results are **materialized** into a SQLite ledger (`report_sources / report_facts / validation_runs / findings / cross_module_signals`). SQL is for **cross-run review/aggregation VIEWs only** (e.g. `v_findings_by_domain`); it never executes the primary arithmetic. The plan's `check_logic_ref` maps to a **registered Verification Attempt (Python)**, not a runtime-authored `.sql`.

3. **Triad of responsibilities** (sharpening the RAG-vs-SQL note):
   `Python engine` (arithmetic / closure / abstain) → `SQL ledger` (persist / review / aggregate) → `Retrieval (RAG/MCP)` (qualitative / source / peer / standard). The LLM is confined to **narrative** (finding writeup, follow-up, workpaper), receiving **summaries, never raw tables or full result sets**.

4. **Vocabulary: preserve the core, map the ledger.** 09's canonical terms (Verification Attempt, LocatedAmount, CheckResult, the 5 statuses) stay unchanged across all 45 modules / 891 tests. The new ledger / cross-module surface adopts the plan's audit-orchestration vocabulary (`finding`, `validation_rule`, `cross_module_signal`) as the **persisted/external contract**, with a bidirectional mapping recorded in `CONTEXT.md`. Critically, **`finding ⊂ CheckResult`**: a finding is the *exception projection* (status ∈ {`unexplained_gap`, `parse_uncertain`}, or a disclosure gap); `matched` / `not_tested` are never findings.

5. **Cross-module signal = durable envelope, not direct call.** A finding emits (a) a `cross_module_signals` ledger row and (b) a `Harness/queue/{date}_{slug}.yaml` envelope (the existing PAS §5.0 async-handoff contract). The envelope **JSON-schema is shared at vault level** (`02_Areas/Shared_Audit_Kernel/`) so consumers read one format. 09 **does not import** any consumer — the engine stays independently testable (ADR-0001). Targets that exist today: `journal_entry_analysis → erp_recon` (GL drilldown on tie-out gaps), `ksox → 23_ksox_review` (financial-close reporting control). `valuation_review` / `ifrs_judgment` envelopes are written but unconsumed until those modules exist.

6. **Retrieval is MCP-backed, deferred behind ledger+signal, and never touches the core.** No own embedding/vector index is built (it would be a heavy dependency that erodes "core runs without DB/MCP"). The Stage-3 qualitative/completeness checks (§7.5 disclosure-omission, policy adequacy) source peer/standard context from **kreports MCP** (`compare_peer_accounting_policies`, `compare_peer_kam_topics`, `search_audit_procedures`, `get_accounting_policy`). This lands in the existing **Reviewer Lens Extension** layer (CONTEXT.md), which is hypothesis-language and explicitly not an audit conclusion.

7. **Defer XBRL and disclosure-completeness as separate expansions.** §7.3 XBRL-PDF consistency contradicts 09's DSD/HTML-first stance (global CLAUDE.md §4.2: DSD ≠ XBRL); §7.5 completeness is a different *kind* of check (FP-prone) and depends on Stage 3. Neither is part of the fold's first two stages.

## Alternatives considered

- **New sibling project `report_validation_tool` (plan as written).** Rejected: duplicates a mature corpus-gated 26k-LOC engine (§7.1/7.2/7.4 already shipped); two footing engines diverge.
- **DB as the check substrate (SQL checks over `report_facts`).** Rejected on doctrine: makes the deterministic core depend on a DB (breaks ADR-0001) and moves arithmetic out of tested Python into runtime SQL — the corpus hard gate and 891 tests would have to migrate for zero accuracy gain.
- **Rename 09 internals to the plan's vocabulary.** Rejected: large churn across 45 modules / 13 ADRs / 891 tests for no accuracy gain (cf. the deliberately-deferred `.scope → .consolidation_basis` rename).
- **Direct 09 → erp_recon call.** Rejected: couples the engine to a consumer, breaks independent testability, and 3 of 5 routing targets do not exist yet.
- **Build a vector index in 09 now (full hybrid up front).** Rejected: heavy new dependency before the deterministic ledger foundation is proven; kreports MCP already serves the peer/standard retrieval need.

## Consequences

- 09 gains a **stateful ledger** (stateless → stateful is the load-bearing change). Verdict-immutability is gated by a **canonical full-result fingerprint diff** (ledger-disabled vs enabled NDJSON byte-identical), **not** a 5-status count diff — counts hide offsetting swaps, which is already 09's reason for its check-level corpus gate (ADR-0016 §2).
- A new **output adapter** (`CheckResult` → `finding` + `cross_module_signal` + queue envelope) is added behind the report layer; the core pipeline is untouched.
- The vault gains a **shared cross-module signal contract** (`02_Areas/Shared_Audit_Kernel/`) — this is vault-level durable state and follows the PAS Harness adapter rule when authored.
- Each stage passes the **corpus hard gate** (matched ↑/flat, zero genuine destroyed, false 0) and cross-model review, same loop as PR #19/#20.
- The Reviewer Lens / retrieval layer stays **hypothesis-language**, MCP-backed, and outside the verdict — it can never promote a `matched`.
- This ADR is **hard to reverse** (it sets 09's identity as the audit-orchestration entry point and the stateless→stateful boundary), which is why it is recorded rather than left implicit.
