# Spec — borrowings/bonds level-aware note_to_bs (column-oriented)

**Date:** 2026-06-26
**Status:** DRAFT for cross-model plan review.
**Model:** ADR-0012 (entity-keyed pairing `Account × Consolidation Basis × Report Period × Balance Level`). Follows the lease B-2b slice (ADR-0013) but with a **different extraction axis**.
**Predecessor:** HANDOFF "borrowings/bonds level-aware". FP slice deferred CJ borrowings as a "noisy pool" — this spec explains why (column-oriented disclosure) and how to reconcile it.

## Goal
`note_to_bs` for `borrowings` and `bonds` on the 4-dim key. Recover matches where the note discloses level totals; **abstain** where it does not. No false match.

## Key finding — borrowings is COLUMN-oriented, not row-oriented (verified)
Lease disclosed level as **row labels** (유동/비유동 리스부채) → row-based extraction. Borrowings discloses level as **column headers** with the carrying total in a **합계 row** → row×column extraction. The taxonomy/check looks at row labels, so it missed these and the pool filled with 유동/비유동 contamination from unrelated notes.

Verified (consolidated):
- **CJ제일제당** note21: table162 header col `단기차입금`, `차입금명칭 합계` row = **3,090,894,377(천원)** = FS 단기차입금 ✓; table166 header `장기차입금`, 합계 = **995,153,579** = FS 장기차입금 ✓ (+ `유동성장기차입금` col = (1,276,584,723) current portion of LT).
- **NAVER** note18: `단기차입금 및 유동성장기차입금`(combined col) 합계 = **335,389,910** = FS 단기차입금(135,389,910)+유동성장기차입금(200,000,000) ✓; `장기차입금` = 863,059,968 = FS ✓; `사채`/`비유동성사채` = 2,007,288,716 = FS 사채 ✓; `차감: 유동성사채`/`유동성사채` = current bond portion.

Heterogeneous: of 6 probed, **CJ + NAVER** have the 합계×level-column pattern; 삼성SDI/대한항공/현대자동차/롯데쇼핑 do not (per-loan-only or other layouts) → those **abstain** (coverage, not false match). Lower coverage than lease is expected and acceptable.

## Balance Level mapping (column header → level)
- `단기차입금` → current; `유동성장기차입금`/`유동성 장기사채및차입금`/`유동성사채` → **current** (current portion of long-term — 유동성 must take precedence over 장기); `단기차입금 및 유동성장기차입금` (combined) → current (pairs to FS Σ(단기+유동성장기)); `장기차입금` → noncurrent; `사채`/`비유동성사채` → noncurrent (bonds); `사채할인발행차금` → contra (exclude, ADR-0011 `_NON_BALANCE_LABEL_TOKENS`).
- **FS-side level precedence fix:** `_balance_level_from_label` currently returns `noncurrent` for `유동성장기차입금` (checks 장기 before 유동성). Fix: 유동성/유동 → current BEFORE 비유동/장기 → noncurrent. (Latent today; load-bearing once borrowings uses the level path.)

## Pairing
- current = Σ(FS 단기차입금 + 유동성장기차입금 + 유동성 자산유동화…) ↔ note current-column 합계 (or the combined `단기+유동성장기` column).
- noncurrent = Σ(FS 장기차입금 + 비유동 자산유동화…) ↔ note `장기차입금` column 합계.
- bonds: FS 사채(noncurrent)/유동성사채(current) ↔ note `비유동성사채`/`유동성사채` column 합계.
- Bounded summation (same Consolidation Basis + Report Period only), tolerance = Σ per-line; abstain on any unresolved column/level or missing 합계 row. FS-amount-independent column/row selection (no answer-peeking).

## Open design questions (for plan review)
1. **Extraction home: Canonical Amount Locator vs a borrowings check helper.** Column×row 합계 extraction is the locator's job (ADR-0008, CONTEXT "Canonical Amount Locator"), and a new role (e.g. `level_column_total`) or archetype may fit. But lease B-2b went check-layer (b). Decide: extend the locator (architecturally right, bigger) or a `checks_fs_note` borrowings helper mirroring `_lease_*` but column-oriented (faster, consistent with B-2b). **Lean: check-helper for v0 (strangler), promotable to locator.**
2. **합계 row detection** — `차입금명칭 합계`/`합계`/`소계`/`총계` row; must be the carrying-balance 합계, not an undiscounted (note4 재무위험관리 미할인현금흐름) or held-for-sale (note14) table. Guard: the table's level columns must be carrying (exclude 미할인/만기/현재가치 tables — reuse `_is_lease_schedule_table` idea).
3. **Combined column** (`단기차입금 및 유동성장기차입금`) → FS Σ(단기+유동성장기). Map combined header → current; sum the matching FS current lines.
4. **bonds within 차입금 note** (NAVER 사채 in note18) vs separate 사채 note — handle both; abstain if 사채 column absent.
5. **자산유동화차입금 / 차입금및사채 (combined account, 롯데쇼핑)** — level ambiguous; likely abstain in v0.

## Scope
- v0: borrowings + bonds, column-oriented 합계×level extraction, current-year table (lowest index, prefer level-columns), single basis (split_report_by_scope + assert), current period only.
- Abstain where the 합계×level pattern is absent (per-loan-only, or no carrying 합계). Expect matches at CJ/NAVER (+ any others with the pattern), abstain at the rest.
- Reuse ADR-0011/0013 guards (isolation tokens, contra exclusion, current-year table, bounded sum, never false match).

## Gate & review (proven loop)
TDD pins (CJ separate-columns, NAVER combined-column + bonds, per-loan-only → abstain, undiscounted-table → abstain, contra 사채할인발행차금 excluded, cross-basis-never) → implement → corpus hard gate (both manifests, check-level matched+gap diff; **focus: zero false match from column extraction + summation**) → baselines → cross-model code review → PR.
