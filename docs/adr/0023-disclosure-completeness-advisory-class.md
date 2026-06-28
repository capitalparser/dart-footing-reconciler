# 0023. Disclosure-completeness as a separate advisory finding class (within-document, abstain-first)

**Date:** 2026-06-29
**Status:** Accepted (design seed). First within-document validation family after the scope boundary (ADR-0022). Implementation is a Tier-3 module — grill + plan before code.
**Inputs:** user direction "공시 내부 검증 심화"; the "보고서 검증 툴" plan §7.5 (공시 누락 후보). Bounded by ADR-0022 (PDF/DSD only, no company source).
**Companion:** `docs/handoff/2026-06-29-disclosure-omission-candidate.md`; CONTEXT.md "Reviewer Lens Extension".

## Context

After ADR-0022, 09 deepens validation **within the provided document**. The first new family is **disclosure-completeness**: detect where the document *should* disclose something (given what it already discloses) but appears not to — e.g. a material lease liability with **no maturity-analysis table** in the document.

This is a **different kind of check** from 09's deterministic arithmetic. The engine's 5 statuses (`matched / explainable_gap / unexplained_gap / parse_uncertain / not_tested`) all describe an *arithmetic* outcome against amounts that exist. "A disclosure is absent" is not an arithmetic result — it is a **judgment about completeness**, and it is **false-positive-prone**: the disclosure may be in a differently-named table, narrative (text) rather than tabular, legitimately omitted on immateriality, or presented under a different basis/period.

09's load-bearing doctrine is "an audit verdict must never carry a false match; abstain over guess." A disclosure-omission claim that is wrong is exactly a false positive that erodes trust.

## Decision

1. **Disclosure-completeness is a SEPARATE advisory finding class — `disclosure_omission_candidate` — OUTSIDE the 5-status verdict.** It is **not** a `CheckResult` status; it never appears in `checks.ALL_STATUSES`, never becomes a `matched`/gap, and never perturbs the deterministic verdict. It lives in the **Reviewer Lens** layer (hypothesis language, reviewer-only), in its own surface (a distinct finding class / table), marked `needs_review`, low priority, with its false-positive risks listed.

2. **Within-document only (ADR-0022).** The trigger ("this account is significant") and the search ("is the expected disclosure present anywhere in the document?") both read **only the provided PDF/DSD**. No external standard DB, no peer filings, no company source. The "expected disclosure" mapping (significant account → its companion disclosure) is a **small curated declarative table** of K-IFRS disclosure expectations, starting with lease → maturity analysis.

3. **Abstain-first (false-positive-averse).** Emit a candidate only when BOTH (a) the account is **clearly significant** within the document (a curated within-document significance rule — e.g. relative size + a distinct presented line), AND (b) a **whole-document search** (note tables via `note_inventory`, label/topic variants, maturity-bucket signature, narrative keywords) finds the expected disclosure **clearly absent**. If the significance is borderline or the search is ambiguous → **abstain** (emit nothing). Better to miss a real omission than to claim a false one.

4. **First slice = lease liability maturity analysis** (matches §7.5's first example; lease is already well-modeled). Other account→disclosure expectations are added one curated rule at a time, each FP-reviewed.

## Alternatives considered

- **Make it a 6th `CheckResult` status.** Rejected: it is not an arithmetic outcome and would pollute the deterministic 5-status verdict + every summary/KPI; a wrong omission claim would read as a verdict.
- **Emit on significance alone (no whole-document search).** Rejected: guarantees false positives (the disclosure usually exists, just elsewhere/narrative).
- **Use external materiality / peer/standard corpus to decide significance.** Rejected by ADR-0022 (no external source) — significance is judged within the document.

## Consequences

- 09 gains an advisory **Reviewer Lens** output distinct from the verdict; the 5-status corpus gate stays byte-identical (this is additive, non-arithmetic).
- The hard parts are **the within-document significance rule** and **the abstain criteria** — both must be sharpened in a grill (they are the FP-control surface) before implementation.
- The expectation mapping is curated and grows slowly; each new account→disclosure rule is FP-reviewed against the corpus.
