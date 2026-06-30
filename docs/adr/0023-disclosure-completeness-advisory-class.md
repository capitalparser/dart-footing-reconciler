# 0023. Disclosure-completeness as a separate advisory finding class (within-document, abstain-first)

**Date:** 2026-06-29
**Status:** Accepted (design seed). First within-document validation family after the scope boundary (ADR-0022). Implementation is a Tier-3 module — grill + plan before code.
**Inputs:** user direction "공시 내부 검증 심화"; the "보고서 검증 툴" plan §7.5 (공시 누락 후보). Bounded by ADR-0022 (PDF/DSD only, no company source).
**Companion:** `docs/handoff/2026-06-29-disclosure-omission-candidate.md`; CONTEXT.md "Reviewer Lens Extension".

## Context

After ADR-0022, 09 deepens validation **within the provided document**. The first new family is **disclosure-completeness**: detect where the document *should* disclose something (given what it already discloses) but appears not to — e.g. a source-backed lease liability amount is explicitly observed in the document, but **no maturity-analysis table** is found in the document.

This is a **different kind of check** from 09's deterministic arithmetic. The engine's 5 statuses (`matched / explainable_gap / unexplained_gap / parse_uncertain / not_tested`) all describe an *arithmetic* outcome against amounts that exist. "A disclosure is absent" is not an arithmetic result — it is a **judgment about completeness**, and it is **false-positive-prone**: the disclosure may be in a differently-named table, narrative (text) rather than tabular, legitimately omitted on immateriality, or presented under a different basis/period.

09's load-bearing doctrine is "an audit verdict must never carry a false match; abstain over guess." A disclosure-omission claim that is wrong is exactly a false positive that erodes trust.

## Decision

1. **Disclosure-completeness is a SEPARATE advisory finding class — `disclosure_omission_candidate` — OUTSIDE the 5-status verdict.** It is **not** a `CheckResult` status; it never appears in `checks.ALL_STATUSES`, never becomes a `matched`/gap, and never perturbs the deterministic verdict. It lives in the **Reviewer Lens** layer (hypothesis language, reviewer-only), in its own surface (a distinct finding class / table), marked `needs_review`, low priority, with its false-positive risks listed.

2. **Within-document only (ADR-0022).** The trigger ("this document explicitly presents a source-backed amount for the account") and the search ("is the expected disclosure present anywhere in the document?") both read **only the provided PDF/DSD**. No external standard DB, no peer filings, no company source. The "expected disclosure" mapping (observed account fact → its companion disclosure) is a **small curated declarative table** of K-IFRS disclosure expectations, starting with lease → maturity analysis.

3. **Abstain-first (false-positive-averse).** Emit a candidate only when BOTH (a) a source-backed account amount is explicitly observed in the document, AND (b) a **whole-document search** (note tables via `note_inventory`, label/topic variants, maturity-bucket signature, narrative keywords) finds the expected disclosure **clearly absent**. If the account fact is only implied (for example, possibly buried in 기타채무) or the search is ambiguous → **abstain** (emit nothing). Better to miss a real omission than to claim a false one.

4. **First slice = lease liability maturity analysis** (matches §7.5's first example; lease is already well-modeled). Other account→disclosure expectations are added one curated rule at a time, each FP-reviewed.

## Alternatives considered

- **Make it a 6th `CheckResult` status.** Rejected: it is not an arithmetic outcome and would pollute the deterministic 5-status verdict + every summary/KPI; a wrong omission claim would read as a verdict.
- **Emit on significance alone (no whole-document search).** Rejected: guarantees false positives (the disclosure usually exists, just elsewhere/narrative).
- **Use external materiality / peer/standard corpus to decide significance.** Rejected by ADR-0022 (no external source) — significance is judged within the document.

## Consequences

- 09 gains an advisory **Reviewer Lens** output distinct from the verdict; the 5-status corpus gate stays byte-identical (this is additive, non-arithmetic).
- The hard parts are **the source-backed trigger rule** and **the abstain criteria** — both must be sharpened in a grill (they are the FP-control surface) before implementation.
- The expectation mapping is curated and grows slowly; each new account→disclosure rule is FP-reviewed against the corpus.

## Design clarification — 2026-06-29 grill Q1

For the first lease slice, "significance" is not a ratio threshold such as lease liabilities / total liabilities. The trigger is that the provided document explicitly observes a source-backed lease liability amount. The lease liability may be a standalone BS line, but that is not required: it may be included in another BS caption and still trigger the advisory family if the lease note, financial-liability table, or liquidity-risk table explicitly presents a lease-liability amount. Right-of-use assets, lease expense, short-term lease expense, or an inferred possibility that lease liabilities are buried inside other payables do not trigger the family by themselves.

## Design clarification — 2026-06-29 grill Q2

For the first lease slice, any positive or ambiguous maturity-disclosure signal causes abstention; the advisory candidate is emitted only when the whole-document search clearly finds nothing. Search signals include existing table classification/candidate surfaces (`lease_liability_maturity_summary`, or `liquidity_maturity_analysis` with a `lease_liabilities` maturity candidate), maturity-bucket-like tables in lease / financial-risk / liquidity-risk notes that mention lease liabilities, and narrative text that links lease liabilities with maturity-analysis concepts. The rule does not decide whether such a signal is complete or audit-sufficient; it only decides that a disclosure-omission candidate would be too false-positive-prone.

## Design clarification — 2026-06-29 grill Q3

Narrative-only maturity disclosure is an abstain signal, not a positive verdict. If narrative text links lease liabilities with maturity-analysis concepts and period language, the lease omission candidate is suppressed. The engine does not assert that the narrative disclosure is sufficient, complete, or audit-grade; it only records that an omission candidate would be too false-positive-prone.

## Design clarification — 2026-06-29 grill Q4

Abstention is not a dumping ground for weak parsing. Repeated ambiguity in known disclosure shapes must feed deterministic table-interpretation improvement before it becomes reviewer noise. For disclosure-completeness work, there are three conceptual outcomes:

1. **Expected disclosure found:** the companion disclosure is recognized in table or narrative form, so no omission candidate is emitted.
2. **Known disclosure shape not yet interpreted well enough:** the document appears to contain a maturity-analysis-like table, but the engine cannot yet interpret it confidently. This suppresses the omission candidate and should become parser/layout backlog evidence, not a reviewer-facing omission memo.
3. **Expected disclosure clearly not found:** after the known table and narrative searches run, no maturity-analysis signal is found. Only this path may emit a reviewer-only `disclosure_omission_candidate`.

This keeps the Reviewer Lens from filling with "not confirmed" items caused by underpowered table parsing. The preferred remedy for repeated ambiguity is to strengthen the document interpreter, with fixtures and source-location evidence, while preserving abstain-over-guess.

## Design clarification — 2026-06-29 grill Q5

Disclosure expectations are defined as an accountant-readable review table, not as hidden branching logic. Each rule states: observed item, acceptable observation locations, expected disclosure, evidence that counts as found, evidence that becomes interpretation-backlog rather than reviewer noise, omission-candidate condition, reviewer wording, false-positive risks, and confirmation that the deterministic verdict is unaffected.

First rule:

| Field | Decision |
|---|---|
| Observed item | Lease liability amount |
| Acceptable observation locations | Standalone BS line, lease note, financial-liability table, liquidity-risk / maturity table |
| Expected disclosure | Lease liability maturity analysis |
| Found evidence | Lease liability maturity table; liquidity-risk maturity table with a lease-liability row; narrative that links lease liabilities with maturity periods |
| Interpretation-backlog evidence | A maturity-analysis-like table that current parser/layout logic cannot interpret confidently |
| Omission-candidate condition | A source-backed lease liability amount is observed, and the whole-document table+narrative search finds no maturity-analysis signal |
| Reviewer wording | "리스부채 금액은 문서 내에서 확인되나, 리스부채 만기분석 공시는 확인되지 않았습니다. 후속 확인이 필요합니다." |
| False-positive risks | Alternative table names; narrative disclosure; materiality judgment; period/basis presentation differences |
| Deterministic verdict impact | None |

## Design clarification — 2026-06-29 grill Q6

Disclosure-completeness output belongs in a separate reviewer-memo list, not in the numeric reconciliation result table. Accountants should read it as a follow-up prompt, not as a tickmark conclusion or a failed reconciliation.

Conceptual report grouping:

1. **검산 결과**: numeric footing/reconciliation outcomes, existing five-status summaries, and KPI counts.
2. **리뷰 메모**: disclosure omission candidates, interpretation-backlog evidence, and follow-up prompts. These do not affect KPI counts.

For the first lease slice, `disclosure_omission_candidate` appears as a low-priority reviewer memo marked "후속 확인 필요" with observed lease-liability evidence, the expected disclosure not found, hypothesis wording, and inline false-positive risks. Interpretation-backlog evidence is not shown as an omission candidate; it is routed to parser/layout quality improvement.

## Implementation clarification — 2026-06-30 Note Semantic Extraction Layer

The lease slice now routes ambiguous table evidence through the Note Semantic
Extraction Layer (ADR-0025) instead of adding more ad hoc lease-table parsing
inside the disclosure advisory. In accountant terms:

1. The advisory first asks whether the document explicitly shows a lease
   liability amount.
2. It then asks whether any note table or narrative looks like the expected
   lease maturity disclosure.
3. If a table looks like a lease/liquidity maturity table but the table headers
   or axes are not confidently readable, the advisory does **not** emit an
   omission memo. It records interpretation-backlog evidence with the disclosure
   family, relation type, uncertainty flags, fingerprint, and source.

This preserves the ADR-0023 rule: ambiguous evidence suppresses the omission
candidate and feeds parser/layout improvement, not reviewer-facing noise.
