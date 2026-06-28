# 0022. Scope boundary — validate the provided PDF/DSD only; no company-source linkage

**Date:** 2026-06-29
**Status:** Accepted (load-bearing scope decision). Supersedes the cross-module-orchestration direction of ADR-0015/0016 (the ledger itself stays; the company-source routing is retracted).
**Inputs:** user scope correction — "보고서 검증은 제시되는 PDF/DSD 파일을 기반으로 검증; 회사 제시 ERP 등을 참조하는 기능을 넣지 마라."

## Context

Stage 1 (Result Ledger) and Stage 1.5 (entity-key core-emit) shipped. Stage 2A added a cross-module **signal** routing a lease tie-out gap to `erp_recon` (전표분석, a tool over **company-provided** GL/TB). That direction came from the original "보고서 검증 툴" plan's cross-module-orchestration framing (§4.2 journal_entry_analysis → erp_recon).

The user identified this as out of bounds: 09's report validation must validate **the provided public disclosure document(s) (PDF/DSD)** and must **not** reach into **company-provided source data (ERP / GL / TB / 분개장)**. Pulling company GL to "explain" a disclosure gap moves the validation basis outside the public filing and breaks the domain boundary.

## Decision

1. **09 validates only the provided PDF/DSD disclosure document(s).** No ingestion of, and no routing to, company-provided source data (ERP/GL/TB/분개장).
2. **The cross-module signal to `erp_recon` is RETRACTED.** Stage 2A (`cross_module.py`, ADR-0020/0021) is closed unmerged (PR #25). The `Cross-Module Signal` term in `CONTEXT.md` is marked retracted/historical.
3. **What stays (in-bounds — document-internal):** the deterministic engine, the **Result Ledger** + **finding** record (Stage 1) and the **entity-key core-emit** (Stage 1.5) — these are projections of the document's own validation, not external linkage.
4. **New direction — deepen self-contained, within-document validation.** Rule families that close *inside the provided document(s)*: disclosure-completeness candidates (e.g. lease liability is significant in the BS/note but the maturity-analysis disclosure is absent from the document), cross-note consistency, prior-period consistency, note-internal arithmetic. No external/peer/company source required. These extend the engine's existing 5-status, abstain-over-guess doctrine (a "missing disclosure" must abstain unless the document clearly lacks an expected, materiality-warranted disclosure — false-positive-averse).

## Alternatives considered

- **Keep cross-module orchestration but only to non-company-source modules (KSOX/IFRS-judgment from the disclosure).** Deferred, not pursued now: the user's direction is to focus 09 on within-document validation; any future cross-module link must first prove it does not reference company-provided source data.
- **Keep erp_recon routing as opt-in.** Rejected: the boundary is about the validation *basis*, not a feature toggle — a company-source linkage is out regardless of opt-in.

## Consequences

- 09 stays a **self-contained validator of the provided disclosure document**. Findings are a record of that validation; they are not handed to company-source tools.
- Future work targets document-internal rule families (disclosure-completeness, cross-note, prior-period). Disclosure-completeness is **false-positive-prone** (alternate tables, narrative disclosure, materiality, basis/period presentation) and must be designed conservatively (abstain-first, reviewer-only candidates) to honor "never a false match."
- `CONTEXT.md` is corrected; the `Retrieval` / `Cross-Module Signal` terms are historical. The memory `project-09-validation-boundary` records this for cross-session continuity.
