# Handoff — Disclosure-omission candidate (within-document, FP-averse)

**Date:** 2026-06-29
**For:** the next session (recommended: a fresh session — grill first, then Codex implements).
**Read first:** `docs/adr/0023-disclosure-completeness-advisory-class.md`, `docs/adr/0022-...` (scope boundary), CONTEXT.md "Reviewer Lens Extension" (lines ~290–361) and the "Verification Signature" / "Outcome Label" terms.
**Branch base:** `main`. This is a **Tier-3 new module** — do NOT skip the grill (the FP-control surface lives in the design, not the code).

## One-line goal

Detect, **using only the provided PDF/DSD document**, candidates where a source-backed account amount explicitly observed in the document lacks an **expected companion disclosure** — and emit them as a **separate, reviewer-only advisory class (`disclosure_omission_candidate`)**, never as a verdict, **abstaining whenever unsure**.

## First slice (and only this slice)

**Lease liability → maturity-analysis disclosure.** Trigger: a source-backed lease liability amount is explicitly observed in the document (standalone BS line, lease note, financial-liability table, or liquidity-risk table). The BS line does **not** have to be standalone; lease liabilities may be included in another BS caption. Check: does the document disclose a **lease maturity analysis** (a table with maturity buckets — 1년 이내 / 1년 초과~5년 이내 / 5년 초과 — or an equivalent narrative)? If the lease-liability amount is explicitly observed AND a whole-document search clearly finds no such disclosure → emit a `disclosure_omission_candidate`. Otherwise → **abstain** (emit nothing).

## Output contract (load-bearing — ADR-0023)

- A `disclosure_omission_candidate` is **NOT a `CheckResult` status**. It must **never** enter `checks.ALL_STATUSES`, never be a `matched`/gap, never touch the deterministic verdict, never appear in the 5-status KPI/summary.
- It lives in its **own surface** (a distinct finding class / advisory list — e.g. a `qualitative_review_items` / reviewer-lens output), marked `needs_review`, **low priority**, **hypothesis language** ("…에 대한 만기분석 공시가 확인되지 않음 — 후속 확인 필요"), with its **false-positive risks listed inline** (대체 표 가능 / 서술형 공시 가능 / 중요성 낮아 생략 가능 / 기준·기기간 표시 차이).
- No cross-module signal, no external/company linkage (ADR-0022). It is a reviewer prompt about the document.

## How to build it (engine surfaces to reuse)

- **Trigger:** identify an explicitly observed, source-backed lease liability amount via the existing `account_key`/taxonomy and note-table candidate surfaces. A standalone BS line is sufficient but not required; a lease note / financial-liability table / liquidity-risk table lease-liability row is also sufficient. ROU assets, lease expenses, and implied inclusion in 기타채무 without an explicit lease-liability amount → abstain.
- **Whole-document disclosure search:** use `note_inventory.py` (catalogs every note table) + the maturity-bucket signature (`layout_variants.py` / signatures) + label/topic variants (taxonomy) to search **the entire document** — all note tables AND narrative text — for a lease maturity analysis. Search must be thorough (label variants: 만기분석/만기별/잔존만기/계약상 만기; bucket variants; English) before concluding absence.
- **Abstain logic:** if the trigger is implied rather than source-backed, or the maturity-disclosure search is positive/ambiguous (a candidate table exists, a maturity-bucket-like lease/liquidity table exists, or narrative maturity language exists), → abstain. The bar to *emit* is high.
- **Placement:** Reviewer Lens layer, additive — it reads the parsed document + classification, runs after the deterministic checks, and writes to the advisory surface only. It must not modify any `CheckResult`.

## OPEN DESIGN QUESTIONS — resolve in the grill (these ARE the FP control)

1. **Trigger rule (resolved in grill Q1).** Trigger on an explicitly observed, source-backed lease liability amount inside the document. Do not require a standalone BS line and do not use lease-liability / total-liability materiality as an emit threshold. If only ROU assets, lease expenses, or possible inclusion inside other payables are visible, abstain.
2. **Abstain criteria (resolved in grill Q2).** Treat `present_or_ambiguous` as abstain. Abstain when existing `lease_liability_maturity_summary` candidates exist, when `liquidity_maturity_analysis` includes `lease_liabilities` maturity candidates, when a lease / financial-risk / liquidity-risk table has maturity buckets plus lease-liability wording, or when narrative text links lease liabilities with maturity concepts. Emit only when Q1 trigger is met and the whole-document table+narrative search clearly finds none of those signals.
3. **Narrative disclosure detection (resolved in grill Q3).** Narrative-only maturity disclosure is an abstain signal, not a positive finding. If narrative text links lease liabilities with maturity-analysis concepts and period language, suppress the candidate; do not assert that the narrative disclosure is complete or audit-sufficient.
4. **Ambiguity handling (resolved in grill Q4).** Do not turn weak table parsing into reviewer noise. If a maturity-analysis-like table exists but the engine cannot interpret it confidently, suppress the omission candidate and record it as parser/layout improvement evidence. Only emit when the expected disclosure is clearly not found after known table and narrative searches.
5. **Candidate storage surface.** New table (`qualitative_review_items`) vs a `finding_class` on the existing findings surface vs a separate advisory artifact? (must stay outside the 5-status ledger projections.)
6. **Expectation-rule schema (resolved in grill Q5).** Define expectations as an accountant-readable review table: observed item, acceptable observation locations, expected disclosure, found evidence, interpretation-backlog evidence, omission-candidate condition, reviewer wording, false-positive risks, and deterministic-verdict impact. First row: lease liability amount → lease liability maturity analysis.
7. **Output surface (resolved in grill Q6).** Disclosure-completeness output is a separate reviewer-memo list, not the numeric reconciliation result table. It is read as follow-up prompts, not tickmark conclusions or failed reconciliations. Interpretation-backlog evidence goes to parser/layout quality improvement, not omission-candidate display.
8. **Terminology** (CONTEXT.md): canonical terms for this family — `Disclosure Expectation`, `Disclosure Omission Candidate`, `Expected Disclosure`, significance vocabulary. Sharpen against the existing glossary (don't collide with "Essential Note" / `non_validation_note_table`).

## Hard "DO NOT"

- Do NOT make it a `CheckResult` status or let it touch the 5-status verdict / KPIs.
- Do NOT claim an omission unless a source-backed lease liability amount is explicitly observed AND the whole-document search clearly finds nothing — **abstain over guess**.
- Do NOT read any external/company/peer source (ADR-0022): no standard DB, no peer filings, no ERP/GL. Only the provided document.
- Do NOT emit a cross-module signal.
- Do NOT add a non-stdlib dependency without justification.

## Verification

- **Corpus 5-status byte-identical:** this family is additive and non-arithmetic — the existing per-company snapshot + check-level diff must be **unchanged** on both baselines (it must not perturb the verdict).
- **Synthetic tests:** source-backed lease liability with a maturity table present → **no** candidate (abstain/none); source-backed lease liability with the lease note present but **no** maturity structure anywhere → candidate emitted with FP-risks; implied-only trigger → abstain; narrative-only maturity → abstain; maturity-like table not yet confidently interpreted → no omission candidate and parser/layout backlog evidence. No gitignored corpus dependency.
- **FP review against the local corpus:** run the family over the 18-co corpus and **hand-review every emitted candidate** — each must be a genuine plausible omission, not a differently-presented disclosure. Tune the significance/abstain dials until the candidate set is precision-first (few, high-quality). Record the FP review (like `docs/accuracy-backlog.md`).

## Process (Tier-3)

1. **Grill** (`/grill-with-docs`) — resolve Q1–Q6, especially the significance rule + abstain criteria (the FP surface) + CONTEXT.md terms.
2. **Plan** + ADR amendment if the design firms up.
3. **Codex implements** the lease slice (TDD, synthetic).
4. **Corpus gate** (5-status byte-identical) + **FP review** of emitted candidates.
5. **2-leg cross-model review** (focus: false-positive rate of the candidates + abstain coverage) → review-findings ADR.
6. **Korean PR** (user pref).
