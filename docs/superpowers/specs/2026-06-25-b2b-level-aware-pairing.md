# Spec — B-2b level-aware note_to_bs pairing (first entity-keyed slice)

**Date:** 2026-06-25
**Status:** DRAFT for cross-model plan review (Opus plan-eng + Codex feasibility) before implementation.
**Model:** ADR-0012 (entity-keyed reconciliation), `docs/domain-model.md`, CONTEXT.md (Consolidation Basis / Balance Level / Report Period).
**Predecessor residual:** ADR-0011 B-2b ("right account, wrong level").

## Goal
Make `note_to_bs` for level-split liability accounts (lease_liabilities; then borrowings, bonds) pair on `(Account × Consolidation Basis × Report Period × Balance Level)` instead of `fs_hits[0]` + one ranked note row. Recover the verified residual gaps **without any false match**; abstain when level is unresolved.

## Doctrine (load-bearing)
domain accuracy > coverage; abstain over guess; **never a false match**; deterministic arithmetic; **bounded** summation only (exactly current+noncurrent of one basis+period); every change corpus-gated (matched ↑/flat, gaps fall only from removed FPs, zero genuine destroyed). Confidence may only downgrade/gate.

## Corpus ground truth (verified, lease)
Disclosure shapes differ → input-shape-adaptive strategy:

**Shape 1 — level-split note (유동 + 비유동 rows):** pair level-to-level (direct, NO sum).
- NAVER note `유동 리스부채`=208,497,038,000 ↔ FS current 208,497,038,211 ✓; `비유동 리스부채`=387,635,119,000 ↔ FS noncurrent 387,635,118,602 ✓ (noncurrent currently UNTESTED — coverage gain).
- 현대차 note `유동 리스부채`=275,628M ↔ FS 275,628M; `비유동 리스부채`=986,477M ↔ FS 986,477M.
- 롯데쇼핑 note `유동 리스부채`/`비유동 리스부채` ↔ FS current/noncurrent (연결 + 별도 both).

**Shape 2 — total-only note (기말 / single total):** pair Σ(current+noncurrent of same basis+period) ↔ total.
- CJ note `기말`=2,108,693,410,000 ↔ FS current 465,381,950,000 + noncurrent 1,643,311,460,000 = 2,108,693,410,000 ✓ (연결); separate 기말 86,904,164,000 ↔ FS 29,553,746,000 + 57,350,418,000 = 86,904,164,000 ✓.

**Shape 3 — note has only 비유동 + a reclassification (유동성대체부분) row, no clean 유동:** 대한항공 note `비유동 리스부채`=8,744,564,000,000 ↔ FS noncurrent 8,744,563,527,885 ✓ (연결); separate 4,487,439,000,000 ↔ FS 4,487,438,965,088 ✓. Current side pairs to the 유동성대체부분 (negative, already rejected as non-balance) → **abstain current, match noncurrent** (do NOT force current).

## Dimension inference (data-driven, deterministic)
- **Consolidation Basis:** from `ReportSection.scope` (already present). Group lines/rows by basis; never cross.
- **Report Period:** current-period column only for v0 (prior is `checks_prior_*`). Pair current↔current.
- **Balance Level:**
  - FS line: label `유동성`/`유동`→current; `비유동`/`장기`→noncurrent; else **BS section position** (current-liabilities block → current; noncurrent block → noncurrent). When the two lease lines of a basis are both level-silent (NAVER "리스부채"×2), the earlier (current-liabilities section) = current, later = noncurrent.
  - Note row: label `유동`→current; `비유동`→noncurrent; `기말`/단일 합계→total; reclass/contra (유동성대체부분, negative) → not a balance row (already filtered).
  - Unresolved → `unknown` → abstain.

## Strategy (per Account+Basis+Period group)
1. Resolve FS current & noncurrent lines (by level).
2. Classify note disclosure shape from the note's level rows present.
3. Shape 1 → two checks: current↔유동, noncurrent↔비유동.
   Shape 2 → one check: (current+noncurrent) Σ ↔ total. Require BOTH FS levels present (else abstain — no half-sum).
   Shape 3 → noncurrent↔비유동 only; current abstains.
4. Any unresolved level / incomplete group / basis mismatch → abstain (not_tested). Never guess.

## Open implementation questions (for plan review)
1. **Where does Balance Level inference live?** (a) populate `level` on `ClassifiedStatementLine`/`ClassifiedNoteAmount` in `taxonomy.classify_report` (model-correct, wider blast radius), vs (b) a check-layer helper used only by `checks_fs_note` for level-split accounts (smaller, but level not globally first-class yet). ADR-0012 says first-class → lean (a), but (b) may be the safer first strangler step. **Decide in plan review.**
2. **BS section position** for level-silent lines — is section/row order reliably available (source.locator row index within a statement table)? Confirm against 현대차/NAVER tables.
3. **Check structure change** — lease currently emits 1 `fs_note` check; level-aware emits up to 2 (current+noncurrent) per basis. Confirm `check_id` scheme + that per-company snapshot baselines absorb the new check rows (expected: matched ↑).
4. **Scope of slice** — lease only first, or lease+borrowings+bonds together? (borrowings adds 단기차입금/유동성장기부채 complexity.) Recommend lease-only first slice.
5. **`.scope → .consolidation_basis` rename** — in this slice or deferred? Recommend deferred (separate refactor).

## Gate & review (same proven loop)
TDD pins (level-split, total-only, 비유동-only, unresolved→abstain, cross-basis-never) → Codex impl → corpus hard gate (both manifests, check-level matched+gap diff, focus: NO false match from summation) → baselines → cross-model code review → PR.

---

## Plan review resolution (2026-06-25) — Opus plan-eng leg + code grounding

Cross-model plan review (Opus `Plan` leg, code-grounded; Codex feasibility leg best-effort background). Verdict: **CONDITIONAL GO** — current spec would violate "never a false match" via TWO blockers that sit *before* the level logic. **The slice is reframed: "lease note-row isolation + level-aware pairing" — isolation is the harder prerequisite.**

### BLOCKER-1 (must fix first) — note candidate-pool contamination
Empirically, 3 of 4 corpus companies have polluted `lease_liabilities` note pools, so today's selector picks non-lease rows:
- 현대차: 155 candidates (mostly 사용권자산/재고자산); current pick = `기말 사용권자산` (an ASSET).
- 롯데쇼핑: `차입금및사채 총장부금액` (borrowings leak).
- CJ대한통운: 투자부동산 `기말`.
- NAVER: clean.

**Resolution:** the slice's FIRST job is isolating the true lease-liability balance row — reject rows with `사용권자산`/`자산`/`채권`/`재고` tokens (extend the existing `_is_wrong_account_row` "채권" family) and require `note_title` positively matches 리스부채/리스. Level pairing runs ONLY on the isolated pool. Without this, correct level inference still lands on a dirty row.

### BLOCKER-2 (must handle) — multi-table note ambiguity
NAVER note 12 has TWO tables, both with `유동/비유동 리스부채` (208,497M vs 234,727M — the latter likely an undiscounted-maturity schedule). `ClassifiedNoteAmount` has no table/level field to disambiguate, and both share scope.
**Resolution:** picking the table whose amount matches FS = "looking at the answer" (forbidden). If a deterministic, FS-independent signal (e.g. 미할인/만기/현재가치 tokens marking the schedule table) cannot single out one table → **abstain** (not_tested). Never select by FS proximity.

### Open-question resolutions
1. **Level inference location → (b) check-layer helper.** Decisive: `source` is a string; correct level needs raw BS section row-context (the `유동부채`/`비유동부채` header rows), which classified lines drop. Putting it in `classify_report` = pipeline-wide change (big-bang the ADR-0012 warns against). The dataclasses are `frozen` (compute on-demand anyway) and have only 2 construction sites each, so field-addition for (a) is cheap *later* — but the v0 helper computes level on demand for lease only. **Design the helper as a pure promotable function** `infer_balance_level(section_rows, row_index) → current|noncurrent|unknown`.
2. **Level signal = header boundary, not row-order.** A level-silent line is `current` if it sits before the `비유동부채`/`비유동` header row in its BS table, `noncurrent` if after; if no boundary header is found between two level-silent lease lines → abstain. (NAVER: row25 `유동부채`, row33 lease=current; row35 `비유동부채`, row42 lease=noncurrent.) The helper reads raw `section.blocks[].table.rows`, not just `source` row index.
3. **Consolidation Basis grouping is already done** by `check_pipeline.split_report_by_scope` (single-basis report reaches `check_fs_note_matches`). The helper does NOT re-group; it only **asserts single-basis** to defend standalone/whole-report test inputs. (Resolves spec's "group by basis" duplication.)
4. **Report Period:** current-period only for v0 (prior stays in `checks_prior_*`); pair current↔current.
5. **Slice scope:** lease-only first (borrowings/bonds pools are dirtier — defer). `.scope→.consolidation_basis` rename deferred.

### check_id collision (MAJOR)
Two level checks share `note_no` → duplicate `check_id` (breaks `corpus.py` triage anchor + `report_html` DOM id). Use suffix `fs_note:{account}:{note_no}:current|noncurrent|total`. Verify the suffix does not collide with `audit_workbook.py`'s `:row`/`:col` substring parsing.

### Summation false-match guard (Shape 2) — 3 conditions → 6 (provably safe)
`require both FS levels present, same basis+period` is necessary but NOT sufficient. Required guards:
1. **basis single:** both lines same scope (or assert single-basis report).
2. **account purity:** both lines pass `_is_wrong_account_row`/채권/사용권자산 filters (real lease-liability balance).
3. **exactly two** = after filtering, precisely {current 1, noncurrent 1}; 0/1/3+ → abstain.
4. **note-total purity:** total row is a balance row (not 음수/대체/발행차금/취득원가/누계액), `note_title` 리스, no 자산/채권/사용권 token, AND single-table (BLOCKER-2).
5. **tolerance = Σ(per-line display tolerance)**, not per-line; no looser.
6. any condition unmet → not_tested.

### TDD pins (Opus additions to the 5)
+ NAVER multi-table → abstain when single table not deterministically identifiable.
+ 현대차 사용권자산 contamination → isolate; abstain or correct row (never the asset).
+ 롯데쇼핑 차입금 leak → never pair lease to a 차입금 row.
+ 3-lease-line (리스채권 included) → exactly-two guard abstains.
+ summation tolerance accumulation boundary.
+ 대한항공 Shape 3 (유동성대체분 negative contra) → match noncurrent, abstain current (regression pin).

### Codex feasibility leg (folded 2026-06-25) — both BLOCKERs CONFIRMED + 1 new risk
Codex confirmed BLOCKER-1 (`_is_wrong_account_row` rejects only `채권`; `사용권자산/재고/차입금/투자부동산` pass — `checks_fs_note.py:271-280`) and BLOCKER-2 (no table/level field on `ClassifiedNoteAmount`; tie-break returns first, no multi-table abstain — `checks_fs_note.py:169-177`). Confirmed Q1=(b) (classify_report returns level-less dataclass; pairing already centralized in the check). New finding both Opus and the spec missed:

**BLOCKER-1b — opposite-direction false-NEGATIVE from isolation.** `taxonomy._entries_for_note_title` returns the first matching account on multi-account-recognition failure, and the taxonomy orders PPE before lease (`taxonomy.py:79-85, 247-253`). In a note titled with 사용권자산 (e.g. 현대차 "리스 및 운용리스자산 (연결)"), the genuine 리스부채 rows can be consumed under PPE context — so isolating contamination *heading-wise* could drop legitimate lease rows.
**Resolution:** isolation is **row-label-based, not note-title-based** — reject the specific asset/receivable ROWS (`사용권자산`/`재고`/`채권` in the row label), never reject a note because its TITLE mentions 사용권자산. Add a regression pin that 현대차-style "리스 및 운용리스자산" notes still surface their 유동/비유동 리스부채 rows (no false-negative). Verify lease rows aren't pre-consumed by PPE in `_entries_for_note_title`.

### Net effect on the plan (2-leg review complete, converged)
The slice is **row-level isolation-first** (reject asset/receivable ROWS, keep the note), then level-aware pairing (header-boundary level signal), then bounded summation under the 6-guard, with multi-table and unresolved-level → abstain, and a false-negative guard so genuine lease rows in 사용권자산-titled notes survive. Lease-only, check-layer (b) helper, corpus-gated. Ready for implementation.

---

## Implementation outcome (2026-06-25) — design evolved during corpus gating

The first implementation **failed the corpus hard gate** (abstained on EVERY real-company lease case → 0 gained, 4 genuine matches lost → net-negative). The gate caught a synthetic-green / real-broken build. Diagnosis + fix evolved the design on two points the plan review under-modeled:

1. **Root cause was prior-year SEPARATE TABLES, not prior-year columns.** Korean lease notes routinely present the current-year and prior-year roll-forwards as **distinct tables**, each carrying 기말/유동/비유동 rows (CJ table129[당기] + table130[전기]; NAVER table111[당기] + table112[전기]). Both entered the candidate pool, so the `==1` level/total guards saw count 2 and abstained everywhere.
2. **Resolution: deterministic current-year TABLE selection, not multi-table abstain.** BLOCKER-2's "abstain on multiple level tables" was net-negative (it killed correct matches the FP-slice ranking had). Replaced with: (a) extract the **current-period (당기) column** per row (`row_amount_prefer_current`; drop the taxonomy `classified_note_hits` which carry both periods); (b) among isolated, non-schedule lease-balance tables, **select the current-year table by lowest `table.index`** (document order), **preferring tables that have level rows** over total-only tables; (c) from that single table → level pairing (유동↔current, 비유동↔noncurrent) or bounded Σ(current+noncurrent)↔total. The selection is **FS-amount-independent** (no answer-peeking); a wrong pick yields a gap, never a false match.
   - The level-table preference fixes 대한항공: a lower-index total-only sub-table (6.0조) was being chosen over the real BS-split note (비유동 8.74조); preferring level rows selects the BS note → noncurrent matches, current honestly abstains (Shape 3).

**Corpus hard gate (final, both manifests, check-level diff vs post-PR#19 main):** **matched +22 genuine** (CJ/CJ대한통운/SGC/현대건설 bounded total-sums; NAVER/현대차/롯데쇼핑/더존/대한항공 current+noncurrent levels — all exact or display-rounding). **Zero genuine matches destroyed** (the 4 "lost" are check_id renames `:N`→`:N:current`, identical amounts). **Zero false matches. Zero new gaps** (대한항공's misleading gap removed). −14 FP lease gaps. `uv run pytest -q` = 876 passed/1 skipped (deterministic); ruff clean. Baselines updated.

**Residual:** the current-year-table heuristic ("lowest index = 당기") is document-order-based; a wrong pick degrades to a gap (safe), never a false match. The `자산` isolation token is broad (corpus-harmless). The `_lease_note_hits_by_level` 3rd return value is now always False (compatibility; the ambiguous-abstain path is dead). Verification done: 2-leg PLAN review (Opus+Codex, converged) + corpus hard gate + self-review of the false-match surface + 876 tests. Formal 2-leg CODE review (heavy-zone step 8) deferred per user interrupt — run before merge if desired.
