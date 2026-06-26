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

## Plan review resolution (2026-06-26, Opus Plan leg; Codex leg interim/best-effort)
Verdict: **Conditional GO — narrow v0 hard.** Column extraction is a NEW false-match surface the row-based lease helper never had; the spec's guards there were gestures. Close these before Codex handoff:

### Q1 — home: **check-helper in `checks_fs_note.py` for v0** (confirmed, sharper reason)
The locator can't host it cleanly today: `CURRENT_PORTION`/`NONCURRENT_PORTION` are hard-stubbed to `Abstain` (`amount_locator.py` `_PHASE1_UNIMPLEMENTED_ROLES`); `LocatedAmount` is single-cell/single-role (borrowings needs 3 level cells from one 합계 row → 3 calls + check-layer reassembly anyway); the locator has **zero** column-header→level vocabulary (its column helpers are asset/measure/period). **Debt (record in ADR):** this is a strangler placeholder — promote the column classifier into a locator strategy (`borrowings_level_column_summary` archetype + the two roles) once gate-positive. Two unmigrated selectors in `checks_fs_note` (lease + borrowings) is SSOT erosion CONTEXT warns about; the promotion obligation is explicit, not optional.

### BLOCKERs — column-extraction false-match paths (must close)
- **FM-1 carrying-table ALLOWLIST (not denylist).** Borrowings notes co-locate 재무위험관리/유동성위험 **미할인(undiscounted) maturity** tables whose columns can also be 단기/장기차입금 with a 합계 row; undiscounted ≈ carrying for low-interest/short maturities → coincidence match. Denylist tokens leak (ADR-0013 `자산` lesson). **Extract only from a table positively identified as carrying:** heading/title contains 차입금/사채 AND no maturity-bucket row label (1년이내/1~5년/5년초과/잔존만기/상환예정/12개월이내) AND no 미할인/계약상현금흐름/현재가치/이자포함 token.
- **FM-2 period × level 2-D intersection.** Side-by-side 당기/전기 tables repeat the level columns under each period. A level column is valid only if its header path **also resolves to current period** — intersect `current_period_columns(headers)` (table_semantics) with the level-column classification; no "first 단기차입금 column" without the period check (this is ADR-0013 B-2, worse because 2-D).
- **FM-3 column-side contra/net guard.** Bonds tables carry 사채액면 / 사채할인발행차금 / 사채(순액) as **columns**; the row-token `_NON_BALANCE_LABEL_TOKENS` filter does not reach column headers. Add a column-header contra reject (할인발행차금/할증발행차금/액면/사채발행비) and select the **net/장부금액** column when gross+net both present (mirror `amount_locator._column_has_excluded_net_label`).

### Ordered column-header → level classifier (deterministic, first-match-wins, most-specific-first)
1. contra/gross token → **reject** (not a level). 2. header has both 차입금 & 사채 token (combined account) → **reject/abstain** (FM-4). 3. `유동성`/`유동` → **current** (runs BEFORE 장기/비유동 — the precedence fix; covers 유동성장기차입금/유동성사채). 4. `단기차입금 및 유동성장기차입금` combined → **current** (Q4). 5. `단기` → current. 6. `비유동`/`장기` → noncurrent. 7. `사채`/`비유동성사채` → noncurrent-bonds. 8. else → unknown → not extracted. No amount consulted at any step. Same FS-side fix to `_balance_level_from_label` (유동성 before 장기) — **re-run the lease corpus after** (it's live on the lease path; regression-pin).

### Other MAJOR resolutions
- **FM-4 combined account `차입금및사채` → MUST abstain** (was "likely"). Account purity of the column header is a hard precondition.
- **FM-5 table picker:** "lowest index" is unsafe (held-for-sale/매각예정/종속기업별/부문별 subset tables). Pick lowest index **among positively-identified entity-level carrying tables only**; reject subset-context tables unless sole carrying table.
- **Q4 combined-current column → closed-set guard:** pair note combined-current 합계 to `Σ(ALL FS lines whose level resolves current for this account+basis+period)`, and **abstain if any FS current line's level is unknown** (fs_unknown→abstain analogue). Never curate a subset to fit (answer-peeking).
- **Q5 장기 reclassification variant:** do not assume the note 장기차입금 column 합계 is post-reclassification (net of 유동성장기). If a 유동성장기 column exists and 장기 합계 ≠ FS noncurrent, abstain rather than emit a gap silently.
- **No answer-peeking:** cell/column/row selection consults ZERO FS amounts (the locator's `expected_amount` tie-breaker is a trap not to copy). Dedicated test pin.
- **Named positive-match gate FLOOR (hard):** "0 false match" is trivially passed by an abstain-everywhere build (the lease first build did exactly that). Gate MUST assert ≥ these new matches: CJ 단기차입금 + 장기차입금, NAVER current-combined + 장기차입금 + 사채. Below floor → slice not proven.

### MINORs (fix while here)
`infer_balance_level` out-of-range row → early-return unknown (ADR-0013 open MINOR); replicate the locator's mixed-unit guard (`_has_mixed_unit_rows`) in the helper; the FS-level-fix lease regression re-run.

## Implementation outcome (2026-06-26)
Codex implemented per the plan-review resolution (column-header→level classifier, carrying-table allowlist, period∩level, column contra/net guard, 합계-row account context, combined-account abstain, bounded Σ) + 11 TDD pins. The FS-side `_balance_level_from_label` precedence fix (유동성 before 장기) shipped; lease corpus unchanged.

**Probe (real corpus):** CJ borrowings current(3.09tn)/noncurrent(995bn) matched; NAVER borrowings current-combined(335bn)+유동성장기(200bn)/noncurrent(863bn) + bonds(2.0tn) matched; 삼성SDI/대한항공/현대차/롯데쇼핑 abstain (no clean column pattern). Named floor met (not an abstain-everywhere build).

**Dispatch fix (additive-fallback).** Codex's first dispatch REPLACED the borrowings/bonds path (`if debt_results: continue`), which **destroyed 6 genuine old single-pairing matches** (CJ bonds ×2, CJ separate borrowings, CJ대한통운, POSCO, 현대건설) where the level path abstains — corpus gate showed net only +1. Fixed: fall back to single-pairing when the level path yields **no MATCH** (`if any(MATCHED): use level else fall through`), per slice. Re-gate: **matched +7 genuine, ZERO destroyed** (the 6 recovered), 0 false. The fallback restores some honest legacy *gaps* where the level path abstains (acceptable — gaps, never false matches).

**Tests** pin the level helper directly (`_check_debt_level_column_matches`) — that's where the BLOCKER guards live; the dispatch fallback is corpus-verified, not unit-pinned (follow-up nicety). `uv run pytest -q` = 890 passed/1 skipped; ruff clean. Baselines: CJ제일제당 +2, NAVER +5.

**Verification status:** plan review (2-leg, 3 BLOCKERs pre-code) + corpus hard gate (+7/0-destroyed/0-false) + 49 fs_note pins. **Formal cross-model CODE review NOT yet run** (session wrap) — recommended next session (B-2b's code review found 3 false-match paths a clean gate missed; borrowings column extraction warrants the same scrutiny). Residuals: dispatch-fallback lacks a dedicated unit pin; locator-promotion debt (ADR-0012 SSOT); 4/6 companies abstain (correct — no pattern).

## Gate & review (proven loop)
TDD pins (CJ separate-columns, NAVER combined-column + bonds, per-loan-only → abstain, undiscounted-table → abstain, contra 사채할인발행차금 excluded, cross-basis-never) → implement → corpus hard gate (both manifests, check-level matched+gap diff; **focus: zero false match from column extraction + summation**) → baselines → cross-model code review → PR.
