# Adoption review — financial-company footing prompt (2026-06-22)

**Verdict: nonfinancial-company scope stays the v0 priority. The reviewed prompt is FINANCIAL-company specialized; its financial-specific logic is NOT adopted. Only domain-agnostic quality items are adopted.**

## Source

A ChatGPT analysis of an LLM-prompt-driven PDF review tool for **listed financial companies** (banks / holding / securities / insurers — ECL, fair-value hierarchy, IFRS 17, K-ICS, risk management; tasks 1–11 incl. deep financial-instrument checks). The user clarified (2026-06-22): the report-verification tool wanted **first** is **nonfinancial-company specialized**.

## Scope decision (load-bearing — do not re-litigate)

This project is **nonfinancial v0** by design (CONTEXT.md → Company Scope: `{nonfinancial, financial, unknown}`; financial-pattern attempts get a 0.5× confidence multiplier that downgrades to `parse_uncertain`). The user reaffirms nonfinancial-first.

Therefore the prompt's **financial-company logic is OUT of v0 scope** and must not be pulled in:
- ECL / 손실충당금 staging, fair-value hierarchy (Level 1/2/3) movement, IFRS 17 (CSM), K-ICS/RBC/BIS disclosures, financial-instrument deep reconciliation (the prompt's 업무 11).
- Adopting these = a nonfinancial→financial **scope expansion** (ADR-grade decision), explicitly deferred. A future agent proposing to add financial-instrument checks should treat it as a new scope, not a slice.

## What the analysis confirmed (already in this project — validation, not adoption)

The prompt-tool critique's four core risks (전수성 미보장 / 토큰 초과 / IFRS 환각 / 근거 부정확) are exactly what a **deterministic structured engine** avoids — i.e. this project's existing architecture:
- Deterministic Python arithmetic, no LLM judgment (CONTEXT.md; engine runs without MCP) ↔ the analysis §12 "use Python for tasks 1/4/11".
- Structured pre-indexing (`note_inventory.py`, `layout_variants`, `document.py`) ↔ "PDF 사전 구조화 / 표·주석 인덱스".
- Source Location for every material amount (`CheckEvidence`) ↔ "근거위치 + 근거발췌 강제".
- Display-unit tolerance (B-1, `display_unit_tolerance`) ↔ "반올림 허용오차 명시".
- Abstain-over-guess + `not_tested` coverage ↔ "해당없음/확인불가 구분".
- `NotApplicable` vs `Abstain` (ADR-0009 F8, 2026-06-21) ↔ "해당없음(not_applicable) 판정 추가".

## Adopted (domain-agnostic, serves nonfinancial verification)

- **C1 — `not_applicable` ("해당없음") propagation, engine-wide.** Extend the locator's F8 `NotApplicable→not_tested` distinction across `checks_*`, and surface `not_tested` in reports split into human labels: **해당없음 (거래 부재)** vs **미검증/추출불가 (parse_uncertain / extraction-failed)**. Improves the honest-coverage signal the verification-accuracy-strategy already values. Must not change the 5 status COUNTS — sub-categorization only (corpus-gated).
- **C2 — coverage report, 3-way split.** In `coverage.py`, separate **검토완료 / 해당없음 / 확인불가(parse_uncertain) / 추출불가(image·scan·table-structure-unknown)**. The PR #12 `parse_uncertain` reason codes are the foundation; promote "extraction-failed" to a first-class coverage bucket for transparent 전수성 (completeness) tracking.

## Deferred (future nonfinancial module, principle only)

- **C3 — disclosure-completeness via externalized checklist.** The analysis §9 principle ("IFRS requirements come from a *versioned external checklist*, not LLM internal knowledge") is correct. But this project does **footing/reconciliation (arithmetic tie-out)**, not **disclosure completeness (is the required note present)**. Completeness is the deferred **Essential Note** direction (CONTEXT.md). If built, use a **nonfinancial** versioned checklist as data, never code-internal knowledge. Not current scope.

## Not adopted

- Typo / term-consistency (text review, not numeric footing).
- Chunked LLM output tracking (deterministic engine has no token limit).
- PDF preprocessing (input is DART **DSD/HTML**; revisit only if a PDF-only filing path is needed).
- All financial-company specialized logic (see Scope decision).
