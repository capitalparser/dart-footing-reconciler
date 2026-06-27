# HANDOFF.md — DART Footing Reconciler (session wrap 2026-06-24)

Restartable handoff for the next Claude or Codex session. Read this + CONTEXT.md + the ADRs/docs referenced below before resuming.

## Scope reminder (load-bearing)
- This tool is **nonfinancial-company v0** (CONTEXT.md Company Scope; `docs/adoption-review-2026-06-22-footing-prompt.md`). Financial-company logic (ECL / fair-value hierarchy / IFRS 17 / financial-instrument deep checks) is **OUT of scope** — a deferred expansion, not a slice. Do not pull it in.
- Doctrine: **domain accuracy > coverage; abstain over guess; an audit verdict must never carry a false match; all arithmetic is deterministic Python (no LLM judgment); every change is corpus-gated.**

## Current state (all verified)
- `main` @ merge of PR #19. **B-2b level-aware lease pairing shipped in an open PR** (branch `feat/b2b-level-aware-lease`); not yet merged. `uv run pytest -q` = **876 passed, 1 skipped** (deterministic); `uv run ruff check` clean.
- **Entity-keyed reconciliation model established** (whole-tool grill-with-docs): `CONTEXT.md` terms Consolidation Basis / Balance Level / Report Period; `docs/domain-model.md` (entity catalog + ERD + pairing key `Account × Consolidation Basis × Report Period × Balance Level` + rule/data-driven boundary); `docs/adr/0012-entity-keyed-reconciliation-model.md`. Strangler migration; B-2b is the first entity-keyed slice.
- **B-2b level-aware lease pairing (open PR, 2026-06-25):** check-layer; pairs lease on the 4-dim key. Row-level isolation of true lease-liability balance rows; Balance Level inference (label → BS-header boundary); current-period (당기) column + current-year TABLE selection (lowest index, prefer level-row tables); level-split → 유동↔current/비유동↔noncurrent, total-only → bounded Σ(current+noncurrent)↔total; unresolved → abstain. Corpus hard gate: **+22 genuine matches, ZERO destroyed, ZERO false, ZERO new gaps, −14 FP gaps.** Spec `docs/superpowers/specs/2026-06-25-b2b-level-aware-pairing.md` (incl. "Implementation outcome"). NOTE: first build abstained on all real data (prior-year roll-forwards are SEPARATE tables) — fixed by current-period + current-year-table selection. Formal 2-leg CODE review deferred per user interrupt (plan review + corpus gate + self-review done).
- **FP fix slice (PR #19, 2026-06-24):** check-layer guards (A1 closing-balance `기말` prefix priority; A2 `채권` reject for liabilities; A3 non-amount-field reject 명칭/기준일/청구권/수량; B cfs plausibility + no blind fallback; EPS 10M ceiling; `_is_balance_row` movement/gross reject 환율조정/환산/평가손익/취득원가/누계액). Corpus hard gate (18 cos, both manifests): **+11 genuine matches, −3 false/vacuous (SK텔레콤 EPS won-totals, NAVER cfs 0==0), −22 FP gaps, ZERO genuine destroyed.** Baselines updated. Cross-model review (Opus + Codex) closed in `docs/adr/0011-fp-slice-review-findings.md`. Spec `docs/superpowers/specs/2026-06-24-fp-slice-pairing-parse-eps.md`.
- **Canonical Amount Locator** shipped + wired into `reconciliation_inputs` (PR #14): single SSOT for cell selection. Corpus (10-co): **matched +4 / unexplained_gap −2 / FP 0** (diff=0 ties to BS net-carrying line, self-validating). ADRs 0008 (decision), 0009 (plan review findings), 0010 (code-review BLOCKERs). ADR-0003 amended (semantic/signature track → diagnostic).
- **Nonfinancial smoke corpus expanded 10 → 18 industries** (PR #16, #17). Added: 반도체·철강·통신·식음료·인터넷·화장품·항공·유틸리티. Corpus (manifest+raw HTML) is **local-only/gitignored**; committed = baseline `tests/baselines/per_company_counts_2026-06-22-expansion.json` + keyless reproduction recipe `docs/corpus-expansion-2026-06-22.md`.
- **Gap triage done** (PR #18, this branch): the new corpus's `unexplained_gap` clusters classified FP vs genuine. See `docs/accuracy-backlog.md` → "Expansion corpus gap triage (2026-06-23)".

## Open PRs
- **B-2b** `feat/b2b-level-aware-lease` — level-aware lease pairing (above). **Review/merge next.** Merging needs explicit user request. (Optionally run the formal 2-leg CODE review first — deferred per interrupt.)
- (#14/#15/#16/#17/#18/#19 already merged.)

## Next feature (NEW track, 2026-06-27) — Report Validation Result Ledger
A second, orthogonal track: evolve 09 into an audit-orchestration entry point by adding a **Result Ledger around the engine** (the "보고서 검증 툴" plan folds into 09, not a new project). Grill + 1-leg plan review (GPT Pro) done; **Codex implementation brief: `docs/handoff/2026-06-27-report-validation-result-ledger-stage1a.md`** (Stage 1A seal → 1B SQLite ledger). Decisions: `docs/adr/0015` + `docs/adr/0016` (review amendments); plan `plans/2026-06-27-report-validation-ledger.md`; domain `CONTEXT.md` → "Report Validation Result Ledger & Cross-Module Orchestration". Load-bearing rule: **core verdict sealed into an immutable artifact; ledger/findings/signals/RAG are downstream projections, never inputs.** Gate = full-result fingerprint diff (not count diff). Disjoint from the check-layer work below (downstream + new files). Stage 2 (signal outbox) / Stage 3 (retrieval) are NOT yet handed off.

## Next planned feature — extend the entity-keyed model (lease proved it)
B-2b proved the entity-keyed pairing (`Account × Consolidation Basis × Report Period × Balance Level`). Next levers, smallest-risk-first, each corpus-gated:
- **Borrowings/bonds level-aware** (apply the lease pattern to 차입금/사채: 단기차입금/유동성장기부채 ↔ 장기차입금/사채). Dirtier pools than lease (review BLOCKER-1 contamination tokens) — isolate first, then level. Reuse `_lease_*` helpers' shape (consider generalizing to `_level_aware_matches(account)`).
- **대한항공-style table-selection refinement** (residual): the current-year table heuristic ("lowest index = 당기", prefer level rows) can mis-pick a sub-component total table → a gap (safe, never a false match). A stronger current-year signal (period header on the table) would convert remaining lease gaps to matches/abstains.
- **M-2 layering debt (small):** `checks_cfs_note` imports `_is_non_amount_field_label`/`_plausible_amount` from `checks_fs_note`. Move shared predicates (+ `_MAX_PLAUSIBLE_AMOUNT`, `_NON_AMOUNT_FIELD_LABEL_TOKENS`) to `_match_helpers.py`. No correctness impact, no circular import. ADR-0011 M-2.
- **`.scope → .consolidation_basis` rename** (ADR-0012 deferred refactor) + promote `Balance Level`/`Report Period` to structured dataclass fields when a second account needs them (the `infer_balance_level` helper is written promotable).
- **Still deferred / out of scope:** dividends (ambiguous declared-vs-paid), revenue (P&L segment), CJ borrowings FS-note (noisy pool), `total_check` (ADR-0007 — do NOT force-foot), 금융상품 (nonfinancial scope edge), corpus batch 3 toward a labeled Gold Set.

### The proven loop (unchanged — used for PR #19)
1. Branch from `main` (merge #19 first).
2. Codex implements the check-layer fix (TDD: regression pins from the triaged/real cases first).
3. **Corpus hard gate** (per `docs/superpowers/specs/2026-06-21-canonical-amount-locator.md` §6): run the local corpus before/after; `matched` ↑/flat; `unexplained_gap` may fall **only** from removed FPs (per-check confirm); `scripts/check_per_company_snapshot.py` HARD gate (both baselines: 10-co `per_company_counts.json` + 18-co expansion baseline); **zero genuine matches destroyed**. The check-level before/after diff (stash src → run `assemble_report_checks` over both manifests → `comm` matched+gap sets) is the authoritative gate — per-company status counts can hide offsets.
4. cross-model review before merge (Opus `code-reviewer` + Codex adversarial), per heavy-zone step 8 — on PR #19 it caught a real BLOCKER (bare `기말` substring) and a MAJOR (gross-row); do not skip.
5. `uv run pytest -q` ×2 (deterministic) + `uv run ruff check` clean. PR.

## Corpus operations (keyless, reproducible)
- rcp_no discovery: kreports MCP `search_dataset(dataset="source_documents", company=<name>, year=2024, include_excerpt=false)` → `business_report` `rcept_no` (no DART API key).
- Fetch raw HTML: `dart_fetch.fetch_financial_section(rcp_no, out_path)` (network only).
- Run: `run_workpaper_corpus(manifest, out_dir, fetch_missing=False, tolerance=1)`.
- Local manifests: `out/corpus/manifest_2026-06-10-nonfinancial-industry-10.json` (orig 10), `out/corpus/manifest_2026-06-22-nonfinancial-expansion.json` (new 8). HTML under `out/corpus/run_*/raw/` (gitignored).

## Deferred / known gaps
- B-2b level-aware (current/noncurrent portion → FS 단기+장기 합산) — Phase 4, `current_portion`/`noncurrent_portion` roles exist in `amount_locator` but unimplemented (guarded). Uncertain/hard (naive summation is gate-negative).
- SSOT-completion of the locator (route taxonomy `_generic_note_row_amount` + verification_candidates) — **byte-identical no-op for accuracy** (proven); only architecture tidiness, no corpus delta. Not worth chasing for accuracy.
- Corpus batch 3 (화학/엔터/게임/디스플레이/반도체-순수) → toward a labeled Gold Set (20–30) per `docs/validation/verification-accuracy-strategy.md`.
- Adoption items C1 (`not_applicable` propagation engine-wide) + C2 (coverage 3-split) — domain-agnostic honesty improvements, in `docs/accuracy-backlog.md`.

## Git / review conventions
- Project 9 is its own repo (origin `capitalparser/dart-footing-reconciler`), PR-only to `main`. Claude is git owner; Codex implements (no git). Commit/push/merge on explicit user request.
- This project is OUTSIDE the central vault Harness feature_list; its handoff lives here, not in `Harness/feature_list.json`.
