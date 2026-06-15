# Accuracy backlog — diagnosed FP/coverage clusters (2026-06-15)

Corpus reference: `manifest_2026-06-10-nonfinancial-industry-10` (10 nonfinancial companies).
Each item below is FP-class (confirmed by inspection) but needs deeper, corpus-validated
work in a central module — do NOT rush; protect the verified gains.

## Done this round (merged to PR #1)
- equity-tie SCE 합계-column (75f859e), structure-aware footing + abstain guards
  (d58742e, 2c3988d), schema status/version (eccacbb), fs-note topic-match (fe50e1d),
  rollforward blank-subcolumn skip (d154a26).
- Corpus trend (pre-feature → now): matched 4124 → ~4708, unexplained_gap 612 → ~517,
  parse_uncertain 569 → 500. Every step corpus-gated (no FP inflation).

## Remaining clusters (prioritized)

### 1. fs_note_match — row selection + 별도 scope (mode-2)  [taxonomy.py]
- **Root:** `taxonomy` over-classifies many unrelated note rows to an account (삼성SDI
  borrowings: 52 hits in 연결 from 영업부문/기타투자자산/매입채무, 32 in 별도). The
  `_select_note_hit_by_label` topic-match fix (fe50e1d) handles cases where the correct
  note exists AND its title matches the account's `note_title_aliases`. Residual:
  - **Right note, wrong row:** 차입금(연결) → 주석17 차입금 but picks "비유동차입금의
    유동성 대체" sub-row, not the 차입금 total.
  - **별도 scope:** in the 별도 slice the 차입금 note is NOT classified as borrowings →
    no topical candidate → fallback picks 기타투자자산 (wrong note).
- **Rejected quick fix:** "abstain when titled account has no topical match" — it
  over-suppresses GENUINE findings (EPS gap 8,961 vs 8,138 has no title-alias match and
  would be hidden). Broke `test_fs_note_keeps_eps_difference_in_won_as_gap`.
- **Proper fix:** reduce taxonomy over-classification (tighten `note_amount_aliases` so
  기타투자자산/영업부문 rows aren't tagged borrowings) + complete `note_title_aliases`
  (EPS etc.) + scope-aware note classification (별도 notes classified within the 별도
  slice). Central, high blast radius → dedicated TDD + corpus.

### 2. note_rollforward_check — variation sign / missing movement  [note_assertions.py / formula_discovery.py]
- Blank-subcolumn FP fixed (d154a26). Residual: 현대자동차 무형자산 기초 700,819 / 기말
  726,830 (net +26,011) but engine variation sum = −26,011 → diff +52,022. Sign or
  missing-movement-row in the variation aggregation for 무형자산 및 영업권 matrices.
- **Proper fix:** audit `_movement_amount` sign handling vs already-negative
  (parenthesized) movement cells, and movement-row coverage in wide grouped matrices.

### 3. total_check residuals  [checks_totals.py]
- 비파생금융부채: |components| == |total| but disclosed 합계 is negative (liquidity-table
  sign convention) — kept as a legitimate "does not tie as presented" flag (ADR-0007).
- column-total base-row reconciliation tables — needs reconciliation-table semantics
  (ADR-0007 residual).

### 4. parse_uncertain "전기 표" (~bulk of 473 total_check)
- Mostly LEGITIMATE abstention (prior-period mirror tables without a clean total).
  Do NOT force-foot — would reintroduce FPs. Only recover where a safe total exists.

## Principle
Reducing parse_uncertain or unexplained_gap is not always correct — abstention and honest
gaps protect against false confidence. Every change must pass the corpus gate
(unexplained_gap must not rise from new FPs; genuine findings must not be suppressed).
