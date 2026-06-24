# HANDOFF.md — DART Footing Reconciler (session wrap 2026-06-23)

Restartable handoff for the next Claude or Codex session. Read this + CONTEXT.md + the ADRs/docs referenced below before resuming.

## Scope reminder (load-bearing)
- This tool is **nonfinancial-company v0** (CONTEXT.md Company Scope; `docs/adoption-review-2026-06-22-footing-prompt.md`). Financial-company logic (ECL / fair-value hierarchy / IFRS 17 / financial-instrument deep checks) is **OUT of scope** — a deferred expansion, not a slice. Do not pull it in.
- Doctrine: **domain accuracy > coverage; abstain over guess; an audit verdict must never carry a false match; all arithmetic is deterministic Python (no LLM judgment); every change is corpus-gated.**

## Current state (all verified)
- Branch `main` @ merge of PR #17. Working tree clean. `uv run pytest -q` = **848 passed, 1 skipped** (deterministic); `uv run ruff check` clean.
- **Canonical Amount Locator** shipped + wired into `reconciliation_inputs` (PR #14): single SSOT for cell selection. Corpus (10-co): **matched +4 / unexplained_gap −2 / FP 0** (diff=0 ties to BS net-carrying line, self-validating). ADRs 0008 (decision), 0009 (plan review findings), 0010 (code-review BLOCKERs). ADR-0003 amended (semantic/signature track → diagnostic).
- **Nonfinancial smoke corpus expanded 10 → 18 industries** (PR #16, #17). Added: 반도체·철강·통신·식음료·인터넷·화장품·항공·유틸리티. Corpus (manifest+raw HTML) is **local-only/gitignored**; committed = baseline `tests/baselines/per_company_counts_2026-06-22-expansion.json` + keyless reproduction recipe `docs/corpus-expansion-2026-06-22.md`.
- **Gap triage done** (PR #18, this branch): the new corpus's `unexplained_gap` clusters classified FP vs genuine. See `docs/accuracy-backlog.md` → "Expansion corpus gap triage (2026-06-23)".

## Open PRs
- **#18** `docs/expansion-gap-triage` — gap triage + this HANDOFF update. **Merge first.**
- (#14/#15/#16/#17 already merged.)

## Next planned feature — fix slice: FP-class A + B + EPS (corpus-gated, check-layer)
The 18-company corpus surfaced a general FP pattern. Fix, smallest-risk-first, each under the corpus hard gate:
- **A. fs_note/cfs_note wrong-pairing** (diff > 50%, ~6–8/company). The check pairs an FS/CF line to the WRONG note row/cell (무형자산 99–100%, 차입금 99%, 배당 179%, 리스부채 75–353%). This is the **B-4/B-5/mis-pair family** — pairing lives in `checks_fs_note._select_note_hit_by_label` (**check-layer**, ADR-0009 F2), NOT the locator. Extend the balance-row/topic guards so the wrong row is rejected → abstain (honest not_tested) instead of a false gap.
- **B. amount parse defect.** NAVER 차입금의상환 `act≈2×10¹⁷` (digit-concatenation). Add a sanity bound (a note movement orders-of-magnitude > total assets → `Abstain(AMOUNT_PARSE_FAILED)`).
- **EPS mis-pair.** CJ 주당이익 paired to a won-total line (92.4M vs 9,294원). Extend the existing EPS guards.
- **Out of scope for this slice:** `total_check` gaps (35–45/company — mostly legitimate "does not tie as presented", ADR-0007; do NOT force-foot) and 금융상품 gaps (nonfinancial scope edge).

### How to run the fix slice (the proven loop)
1. Branch from `main` (merge #18 first).
2. Codex implements the check-layer fix (TDD: real-fixture regression pins from the triaged cases first).
3. **Corpus hard gate** (per `docs/superpowers/specs/2026-06-21-canonical-amount-locator.md` §6 pattern): run the local corpus before/after; `matched` ↑/flat; `unexplained_gap` may fall **only** from removed FPs (per-check confirm); `scripts/check_per_company_snapshot.py` HARD gate (use both baselines: 10-co `per_company_counts.json` + 18-co expansion baseline); **zero genuine matches destroyed**.
4. cross-model review before merge (Opus `code-reviewer` + Codex adversarial), per heavy-zone step 8 — it caught 3 real BLOCKERs on the locator; do not skip.
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
