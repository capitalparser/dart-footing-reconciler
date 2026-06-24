# Fix slice — fs_note/cfs_note wrong-pairing (A) + parse bound (B) + EPS scale guard

**Date:** 2026-06-24
**Status:** SHIPPED — as-built form and cross-model review evolution recorded in `docs/adr/0011-fp-slice-review-findings.md`. Notably Fix A1's bare `기말` became a **prefix** match (not the literal priority tuple below) + movement/gross rejection in `_is_balance_row`, after review found substring `기말` could pick wrong rows. Read ADR-0011 for the authoritative as-shipped guards.
**Branch:** `fix/fp-slice-pairing-parse-eps`
**Predecessors:** HANDOFF.md "Next fix slice"; `docs/accuracy-backlog.md` → "Expansion corpus gap triage (2026-06-23)"; ADR-0009 F2 (pairing stays in the check layer, NOT the locator).

## Doctrine (load-bearing — do not violate)
- Nonfinancial-company v0 only. Financial-company logic is OUT.
- **domain accuracy > coverage; abstain over guess; an audit verdict must never carry a false match; all arithmetic is deterministic Python (no LLM judgment); every change is corpus-gated.**
- This slice touches ONLY the **check layer** (`checks_fs_note.py`, `checks_cfs_note.py`). Do NOT touch `amount_locator.py` or `taxonomy.py` classification.
- Selection must stay **structural** (label/title/account semantics). The FS amount may be used ONLY as a *tie-breaker among already-structurally-valid same-rank candidates* (ADR-0009 F5), never to fabricate or amount-shop a cell. This slice does **not** add an amount tie-breaker — it fixes the structural ranking so the right row wins on structure alone.

## Root cause (verified against cached corpus HTML, CJ제일제당 / NAVER 2024)

The 18-company smoke set surfaced one general failure: the selector pairs an FS/CF line to the WRONG note row, producing a large false `unexplained_gap`. Verified mechanics:

### A1 — true closing-balance total out-ranked by a sub-line (`checks_fs_note`)
`_label_priority_for_account` = base `_NOTE_LABEL_PRIORITY` + taxonomy `note_amount_aliases`. Today:
```
intangible_assets priority = ('기말장부금액','기말잔액','합계','소계','장부금액','순장부금액','장부가액','기말')
```
`장부금액` sits at idx4; bare `기말` lands LAST at idx7 (it only enters via the taxonomy alias tail). So a category sub-line beats the real closing total:
- CJ 무형자산: true total row `기말` = **4,540,627,818,000** (== FS exactly) is rank 7; sub-line `자산화된 연구개발비 장부금액` = 22,301,000,000 is rank 4 → **sub-line wins → 99.5% false gap.**
- NAVER 무형자산: true total `기말금액` = **3,657,186,453,000** (== FS 3,657,186,453,124 within display-unit rounding) is rank 7; sub-line `순장부금액` = 997,924,000 is rank 4 → **sub-line wins → 100% false gap.**

The correct total IS present in both — so the right fix promotes the closing-balance family **above** generic `장부금액`/`순장부금액`. These FPs become **MATCHES** (matched ↑), not merely abstains.

### A2 — wrong-account row inside a fuzzy title match (`checks_fs_note`)
lease_liabilities `note_title_aliases` includes the loose `리스`; `note_amount_aliases` includes `유동`/`비유동`. So a lease *receivable* row ranks identically to a lease *liability* row and, being earlier in document order, wins:
- NAVER 리스부채: `유동 리스채권` = 52,394,282,000 (a receivable = ASSET) is selected over the true `유동 리스부채` = **208,497,038,000** (== FS 208,497,038,211) → 74.9% false gap. With 리스채권 rejected, `유동 리스부채` wins → **MATCH.**

### A3 — non-amount text/date/quantity cells parsed as amounts (`checks_fs_note` + `checks_cfs_note`)
Cells that are labels/dates/quantities, not money, get classified and then paired:
- CJ/NAVER CFS `차입금의차입` → `차입금명칭` ("borrowing name" text cell) = 20,251,231,000 / 15,667 → false gap. (`_keyword_rank` matches it via the loose `차입` startswith.)
- NAVER CFS `차입금의상환` → `발행자의 중도상환청구권` (redemption-option terms text) — also the B parse case below.
- (Hygiene, not the selected row but mis-classified: NAVER 배당 `배당기준일` = 20,250,228 is a *date* 2025-02-28; intangible `기말 배출권 수량` = 605,000 is a *quantity*.)

### B — absurd parse value passes in cfs_note (no plausibility bound)
`checks_fs_note` filters note candidates through `_plausible_amount` (abs < `_MAX_PLAUSIBLE_AMOUNT` = 1e16). **`checks_cfs_note` has no such filter.** So:
- NAVER CFS `차입금의상환` → `발행자의 중도상환청구권` act = **202,507,312,026,013,030** (~2×10¹⁷, digit-concatenation) → 38,019,663% false gap. (2e17 > 1e16 ⇒ the existing bound already catches it once applied in cfs_note.)

### EPS — implausible per-share value paired (`checks_fs_note`)
- CJ 주당이익: FS `보통주기본주당이익 (단위:원)` parsed as **92,440,000** (a mis-parse — no Korean per-share EPS is ~92M won) vs the correct note `기본주당이익(손실)` = 9,294 → 100% false gap. The note side is right; the FS side is implausible. → **abstain** (do not emit a gap from a non-per-share value).

## The fixes (check-layer, smallest-risk-first)

### Fix A1 — promote the closing-balance family above generic carrying tokens
In `checks_fs_note.py`, change:
```python
_NOTE_LABEL_PRIORITY = ("기말장부금액", "기말잔액", "합계", "소계")
```
to:
```python
_NOTE_LABEL_PRIORITY = ("기말장부금액", "기말순장부금액", "기말금액", "기말잔액", "기말", "합계", "소계")
```
Effect: `기말`-family always ranks above the taxonomy-tail `장부금액`/`순장부금액`/`장부가액`. (`_label_rank` returns the first matching alias index, so specific tokens like `기말금액` still beat bare `기말`.)

### Fix A2 — reject wrong-account rows (receivable under a liability)
In `checks_fs_note.py`, add an account-aware anti-token reject applied to the topical pool (alongside `_is_balance_row`). For liability accounts (`borrowings`, `bonds`, `lease_liabilities`), reject rows whose normalized label contains `채권` (a receivable is an asset and must never pair to a liability). Keep the set minimal and account-scoped; do NOT apply `채권` reject to asset accounts.

### Fix A3 — reject non-amount field rows (shared)
Add a shared predicate `_is_non_amount_field_label(label)` rejecting normalized labels that contain a non-money field token: start with `("명칭", "기준일", "청구권", "수량")` (covers 차입금명칭 / 배당기준일 / 중도상환청구권 / 배출권 수량). Apply it in BOTH selectors (`checks_fs_note._select_note_hit_by_label` candidate filtering and `checks_cfs_note._select_note_hit_by_keyword`). Keep the set minimal; each token must be justified by a triaged case.

### Fix B — apply the plausibility bound in cfs_note
In `checks_cfs_note.py`, filter `note_hits` through the same `_plausible_amount` bound used by `checks_fs_note` (factor it into a shared location or mirror the constant; do not duplicate the magic number loosely). After filtering, if no note candidate remains, `continue` (→ honest not_tested coverage), do not fall back to `note_hits[0]`. Also remove/guard the `note_hits[0]` blind fallback (line ~98) so an unranked garbage row is not selected — prefer abstain.

### Fix EPS — per-share plausibility guard
In `checks_fs_note.py`, for `earnings_per_share`, reject any candidate (FS or note side) whose `abs(amount)` exceeds a conservative per-share ceiling `_MAX_PLAUSIBLE_EPS = 10_000_000` (10M KRW/share — safely above the highest real Korean EPS, e.g. 태광산업-class ~1-2M, while excluding net-income/won-total mis-parses). If the FS hit is implausible → skip the check (abstain → not_tested). Do not emit a gap that originates from a non-per-share value.

## Out of scope for THIS slice (do NOT touch — preserve current behavior)
- **dividends** — genuinely ambiguous (SCE multi-year, annual vs interim, declared vs paid; NAVER 배당 168bn note vs −213bn FS may be a legitimate declared-vs-paid non-tie). Forcing it risks suppressing a real difference. Leave as residual.
- **revenue** — P&L segment-subtotal vs total (NAVER 영업수익 vs 영업부문). Out of the balance/EPS/parse scope.
- **CJ borrowings** (3.09tn vs 452bn) — noisy 163-candidate pool from 재무위험관리/공정가치 notes; may be a genuine difference. Defer.
- **CJ lease** (465bn vs 2.11tn) — B-2b level-aware: FS 유동성(465,381,950,000) + 비유동(1,643,311,460,000) = note 기말 2,108,693,410,000 exactly. The correct sum-of-levels fix is deferred B-2b (HANDOFF). Leave as residual this slice.
- `total_check` gaps and 금융상품 gaps — per triage, NOT in scope.

## TDD — regression pins first (synthetic FullReport fixtures mirroring the real structure)
Build synthetic `FullReport`s (same pattern as existing `tests/test_checks_fs_note.py` / `tests/test_checks_cfs_note.py`) that replicate each triaged structure, then assert the post-fix outcome. RED before GREEN.

1. **A1 intangible (→ matched):** note table rows `기말금액 = 3,657,186,453` (total) and `순장부금액 = 997,924` (sub), FS 무형자산 = `3,657,186,453`. Assert the check pairs to the `기말금액` row and `status == matched`. Add a CJ-shaped variant with the total labeled bare `기말` and a `자산화된 연구개발비 장부금액` sub-line.
2. **A2 lease (→ matched):** note rows `유동 리스채권 = 52,394` and `유동 리스부채 = 208,497`, FS 리스부채 = `208,497`. Assert pairs to `유동 리스부채`, `status == matched`; assert `리스채권` is never selected.
3. **A3 cfs garbage (→ abstain/not the garbage):** cfs `차입금의차입` with note rows `차입금명칭 = 20,251,231` (text) and a legitimate movement row; assert `차입금명칭` is never selected (and if it is the only candidate, the check abstains rather than emitting a gap).
4. **B parse bound (→ abstain):** cfs `차입금의상환` note candidate `= 202,507,312,026,013,030`; assert it is filtered and the check does not emit an `unexplained_gap` from it.
5. **EPS (→ abstain):** FS 보통주기본주당이익 = `92,440,000`, note 기본주당이익(손실) = `9,294`; assert NO `unexplained_gap` is emitted (abstain → not_tested).
6. **Must-stay-matched guards (anti-regression):** the existing `test_check_fs_note_matches_balance_sheet_line_to_note_total` (label `기말 장부금액`) and the PL/SCE/CF matched set must remain `matched`. Add an explicit pin that a bare-`기말` total still wins over a `장부금액` sub-line without breaking the `기말 장부금액` exact case.

## Corpus hard gate (Claude runs after Codex; non-negotiable)
Per `docs/superpowers/specs/2026-06-21-canonical-amount-locator.md` §6:
- Run both local manifests before/after (`manifest_2026-06-10-nonfinancial-industry-10.json` + `manifest_2026-06-22-nonfinancial-expansion.json`).
- `matched` ↑ or flat (this slice should turn ≥4 FPs into matches: CJ/NAVER intangible, NAVER lease, and any A1 siblings).
- `unexplained_gap` may fall ONLY from removed FPs — confirm per-check, per-company. No genuine match destroyed.
- `scripts/check_per_company_snapshot.py` HARD gate against BOTH baselines (`tests/baselines/per_company_counts.json` + `per_company_counts_2026-06-22-expansion.json`).
- If any genuine match is destroyed or any new gap appears → narrow the offending token and re-gate.

## Done criteria
- All new regression pins green; full suite `uv run pytest -q` ×2 deterministic; `uv run ruff check` clean.
- Corpus hard gate passes both baselines.
- Cross-model review (Opus `code-reviewer` + Codex adversarial) — findings recorded in `docs/adr/0011-fp-slice-review-findings.md` if any BLOCKER/MAJOR.
