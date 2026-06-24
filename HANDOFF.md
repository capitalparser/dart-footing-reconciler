# HANDOFF.md — DART Footing Reconciler (session wrap 2026-06-24)

Restartable handoff for the next Claude or Codex session. Read this + CONTEXT.md + the ADRs/docs referenced below before resuming.

## Scope reminder (load-bearing)
- This tool is **nonfinancial-company v0** (CONTEXT.md Company Scope; `docs/adoption-review-2026-06-22-footing-prompt.md`). Financial-company logic (ECL / fair-value hierarchy / IFRS 17 / financial-instrument deep checks) is **OUT of scope** — a deferred expansion, not a slice. Do not pull it in.
- Doctrine: **domain accuracy > coverage; abstain over guess; an audit verdict must never carry a false match; all arithmetic is deterministic Python (no LLM judgment); every change is corpus-gated.**

## Current state (all verified)
- `main` @ merge of PR #18. **Fix slice shipped in open PR #19** (branch `fix/fp-slice-pairing-parse-eps`); not yet merged. `uv run pytest -q` = **867 passed, 1 skipped** (deterministic); `uv run ruff check` clean.
- **FP fix slice (PR #19, 2026-06-24):** check-layer guards (A1 closing-balance `기말` prefix priority; A2 `채권` reject for liabilities; A3 non-amount-field reject 명칭/기준일/청구권/수량; B cfs plausibility + no blind fallback; EPS 10M ceiling; `_is_balance_row` movement/gross reject 환율조정/환산/평가손익/취득원가/누계액). Corpus hard gate (18 cos, both manifests): **+11 genuine matches, −3 false/vacuous (SK텔레콤 EPS won-totals, NAVER cfs 0==0), −22 FP gaps, ZERO genuine destroyed.** Baselines updated. Cross-model review (Opus + Codex) closed in `docs/adr/0011-fp-slice-review-findings.md`. Spec `docs/superpowers/specs/2026-06-24-fp-slice-pairing-parse-eps.md`.
- **Canonical Amount Locator** shipped + wired into `reconciliation_inputs` (PR #14): single SSOT for cell selection. Corpus (10-co): **matched +4 / unexplained_gap −2 / FP 0** (diff=0 ties to BS net-carrying line, self-validating). ADRs 0008 (decision), 0009 (plan review findings), 0010 (code-review BLOCKERs). ADR-0003 amended (semantic/signature track → diagnostic).
- **Nonfinancial smoke corpus expanded 10 → 18 industries** (PR #16, #17). Added: 반도체·철강·통신·식음료·인터넷·화장품·항공·유틸리티. Corpus (manifest+raw HTML) is **local-only/gitignored**; committed = baseline `tests/baselines/per_company_counts_2026-06-22-expansion.json` + keyless reproduction recipe `docs/corpus-expansion-2026-06-22.md`.
- **Gap triage done** (PR #18, this branch): the new corpus's `unexplained_gap` clusters classified FP vs genuine. See `docs/accuracy-backlog.md` → "Expansion corpus gap triage (2026-06-23)".

## Open PRs
- **#19** `fix/fp-slice-pairing-parse-eps` — the FP fix slice (above). **Review/merge next.** Merging needs explicit user request.
- (#14/#15/#16/#17/#18 already merged.)

## Next planned feature — B-2b level-aware (current/noncurrent), highest-value lever
The FP slice is done. The biggest remaining accuracy lever the 18-co corpus exposed:
- **B-2b level-aware pairing.** After A2, 대한항공/CJ lease now pair to the *right account* but the wrong *level*: `fs_hits[0]` is the current portion (유동성리스부채) while the note row is the closing total (비유동 리스부채 / 기말). The note `비유동 리스부채` exactly equals the FS noncurrent line and FS current+noncurrent sums to the note total (verified: 대한항공 8,744,564,000,000 == FS 8,744,563,527,885; CJ 465,381,950,000 + 1,643,311,460,000 == 2,108,693,410,000). The win is to select/sum the matching FS level(s) instead of `fs_hits[0]`. HANDOFF warns naive summation is gate-negative — design carefully, corpus-gated. `current_portion`/`noncurrent_portion` roles exist in `amount_locator` but are guarded/unimplemented.
- **M-2 layering debt (small):** `checks_cfs_note` imports `_is_non_amount_field_label`/`_plausible_amount` from `checks_fs_note`. Move shared predicates (+ `_MAX_PLAUSIBLE_AMOUNT`, `_NON_AMOUNT_FIELD_LABEL_TOKENS`) to `_match_helpers.py`. No correctness impact, no circular import. See `docs/adr/0011-fp-slice-review-findings.md` M-2.
- **Still deferred / out of scope:** dividends (ambiguous declared-vs-paid), revenue (P&L segment), CJ borrowings (noisy pool), `total_check` (ADR-0007 — do NOT force-foot), 금융상품 (nonfinancial scope edge), corpus batch 3 toward a labeled Gold Set.

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
