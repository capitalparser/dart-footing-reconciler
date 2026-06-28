# Handoff — Disclosure-omission candidate (within-document, FP-averse)

**Date:** 2026-06-29
**For:** the next session (recommended: a fresh session — grill first, then Codex implements).
**Read first:** `docs/adr/0023-disclosure-completeness-advisory-class.md`, `docs/adr/0022-...` (scope boundary), CONTEXT.md "Reviewer Lens Extension" (lines ~290–361) and the "Verification Signature" / "Outcome Label" terms.
**Branch base:** `main`. This is a **Tier-3 new module** — do NOT skip the grill (the FP-control surface lives in the design, not the code).

## One-line goal

Detect, **using only the provided PDF/DSD document**, candidates where a **significant** account lacks an **expected companion disclosure** — and emit them as a **separate, reviewer-only advisory class (`disclosure_omission_candidate`)**, never as a verdict, **abstaining whenever unsure**.

## First slice (and only this slice)

**Lease liability → maturity-analysis disclosure.** Trigger: a **clearly significant** lease liability is presented (BS line and/or lease note). Check: does the document disclose a **lease maturity analysis** (a table with maturity buckets — 1년 이내 / 1년 초과~5년 이내 / 5년 초과 — or an equivalent narrative)? If the account is clearly significant AND a whole-document search clearly finds no such disclosure → emit a `disclosure_omission_candidate`. Otherwise → **abstain** (emit nothing).

## Output contract (load-bearing — ADR-0023)

- A `disclosure_omission_candidate` is **NOT a `CheckResult` status**. It must **never** enter `checks.ALL_STATUSES`, never be a `matched`/gap, never touch the deterministic verdict, never appear in the 5-status KPI/summary.
- It lives in its **own surface** (a distinct finding class / advisory list — e.g. a `qualitative_review_items` / reviewer-lens output), marked `needs_review`, **low priority**, **hypothesis language** ("…에 대한 만기분석 공시가 확인되지 않음 — 후속 확인 필요"), with its **false-positive risks listed inline** (대체 표 가능 / 서술형 공시 가능 / 중요성 낮아 생략 가능 / 기준·기기간 표시 차이).
- No cross-module signal, no external/company linkage (ADR-0022). It is a reviewer prompt about the document.

## How to build it (engine surfaces to reuse)

- **Significance trigger:** identify the lease liability via the existing `account_key`/taxonomy; judge significance **within the document** (see open question Q1 — a curated within-document rule, e.g. presented as a distinct BS line AND above a relative-size threshold). No external materiality.
- **Whole-document disclosure search:** use `note_inventory.py` (catalogs every note table) + the maturity-bucket signature (`layout_variants.py` / signatures) + label/topic variants (taxonomy) to search **the entire document** — all note tables AND narrative text — for a lease maturity analysis. Search must be thorough (label variants: 만기분석/만기별/잔존만기/계약상 만기; bucket variants; English) before concluding absence.
- **Abstain logic:** if significance is borderline, or the maturity-disclosure search is ambiguous (a candidate table exists but is uncertain), → abstain. The bar to *emit* is high.
- **Placement:** Reviewer Lens layer, additive — it reads the parsed document + classification, runs after the deterministic checks, and writes to the advisory surface only. It must not modify any `CheckResult`.

## OPEN DESIGN QUESTIONS — resolve in the grill (these ARE the FP control)

1. **Within-document significance rule.** How is "significant lease liability" defined with no external materiality? (candidate: presented as a distinct BS line AND lease liability / total liabilities ≥ a curated threshold, OR ≥ a curated % of total assets. The threshold is the FP dial.) Define it; make it conservative.
2. **Abstain criteria.** Exactly when does the maturity-search "clearly find nothing" vs "ambiguous → abstain"? (e.g. if any table in the lease note carries maturity-bucket-like rows → abstain; only emit when the lease note exists but has no maturity structure anywhere, or the lease note itself is absent despite a material BS line.)
3. **Narrative disclosure detection.** Maturity analysis can be a sentence, not a table. How hard does the search try on narrative text, and does narrative-present → abstain?
4. **Candidate storage surface.** New table (`qualitative_review_items`) vs a `finding_class` on the existing findings surface vs a separate advisory artifact? (must stay outside the 5-status ledger projections.)
5. **Expectation-rule schema.** The account→expected-disclosure mapping (lease → maturity analysis) as a small declarative table — what shape, so the next rule (e.g. 금융상품 → 위험/공정가치 공시) drops in without code branching?
6. **Terminology** (CONTEXT.md): canonical terms for this family — `Disclosure Expectation`, `Disclosure Omission Candidate`, `Expected Disclosure`, significance vocabulary. Sharpen against the existing glossary (don't collide with "Essential Note" / `non_validation_note_table`).

## Hard "DO NOT"

- Do NOT make it a `CheckResult` status or let it touch the 5-status verdict / KPIs.
- Do NOT claim an omission unless the account is clearly significant AND the whole-document search clearly finds nothing — **abstain over guess**.
- Do NOT read any external/company/peer source (ADR-0022): no standard DB, no peer filings, no ERP/GL. Only the provided document.
- Do NOT emit a cross-module signal.
- Do NOT add a non-stdlib dependency without justification.

## Verification

- **Corpus 5-status byte-identical:** this family is additive and non-arithmetic — the existing per-company snapshot + check-level diff must be **unchanged** on both baselines (it must not perturb the verdict).
- **Synthetic tests:** a material lease liability with a maturity table present → **no** candidate (abstain/none); material lease liability with the lease note present but **no** maturity structure anywhere → candidate emitted with FP-risks; borderline significance → abstain; narrative-only maturity → abstain. No gitignored corpus dependency.
- **FP review against the local corpus:** run the family over the 18-co corpus and **hand-review every emitted candidate** — each must be a genuine plausible omission, not a differently-presented disclosure. Tune the significance/abstain dials until the candidate set is precision-first (few, high-quality). Record the FP review (like `docs/accuracy-backlog.md`).

## Process (Tier-3)

1. **Grill** (`/grill-with-docs`) — resolve Q1–Q6, especially the significance rule + abstain criteria (the FP surface) + CONTEXT.md terms.
2. **Plan** + ADR amendment if the design firms up.
3. **Codex implements** the lease slice (TDD, synthetic).
4. **Corpus gate** (5-status byte-identical) + **FP review** of emitted candidates.
5. **2-leg cross-model review** (focus: false-positive rate of the candidates + abstain coverage) → review-findings ADR.
6. **Korean PR** (user pref).
