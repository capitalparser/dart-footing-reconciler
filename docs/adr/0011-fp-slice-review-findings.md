# 0011. FP fix-slice (pairing + parse + EPS) — cross-model review findings

**Date:** 2026-06-24
**Status:** Accepted — all BLOCKER/MAJOR closed; corpus-gated; merged via PR (fix slice).
**Scope:** check-layer only (`checks_fs_note.py`, `checks_cfs_note.py`). Spec: `docs/superpowers/specs/2026-06-24-fp-slice-pairing-parse-eps.md`.
**Inputs:** Tier-3 cross-model review (heavy-zone step 8) of the FP slice.
- Leg (a) Opus `code-reviewer` agent — verdict **REQUEST CHANGES** (1 BLOCKER, 2 MAJOR, minors).
- Leg (b) Codex (GPT-family) adversarial review — verdict **no BLOCKER, 1 MAJOR**.
- Claude (verifier) reproduced every finding against the cached 18-company corpus before acting.

## What shipped (5 check-layer guards, corpus-gated)
A1 closing-balance priority; A2 receivable-row reject for liability accounts (`채권`); A3 non-amount-field reject (`명칭/기준일/청구권/수량`); B cfs plausibility bound + removal of the blind `note_hits[0]` fallback; EPS per-share ceiling (`_MAX_PLAUSIBLE_EPS = 10_000_000`).

**Net corpus effect (18 companies, both manifests, check-level diff vs main):**
- **+11 genuine matches** (CJ/NAVER intangible, NAVER lease×2, 삼성SDI/현대자동차/아모레 investment_property, 셀트리온 intangible).
- **−3 matches removed, ALL false/vacuous** (SK텔레콤 EPS 5.78bn/5.92bn won-totals mislabeled per-share; NAVER cfs `차입금의차입` 0==0 garbage-cell match).
- **−22 false-positive gaps.** ZERO genuine matches destroyed. No false match introduced.
- 3 "new" gaps are net-neutral gap→gap shifts in deferred/out-of-scope cells (대한항공 lease = B-2b right-account level mismatch; 삼성전자 dividends = out-of-scope value shift after a date-cell was dropped).

Baselines updated (`tests/baselines/per_company_counts.json` + `…_2026-06-22-expansion.json`) and re-verified equal to the shipped code.

## Findings & decisions

### B-1 (BLOCKER, Opus) — bare `기말` priority token with substring match could let a movement sub-line beat a true total
A1 promoted closing-balance tokens above the generic `장부금액`. With **substring** matching, bare `기말` matched not only true closing totals but any `기말…` label — e.g. a fair-value-model investment-property note where the true net total is `장부금액` and a `기말환율조정` / `기말 평가손익` sub-line (rank-4) overtakes it → a structurally **false pairing** in companies outside the 18-co corpus. Opus reproduced it; the corpus only passed by coincidence (no such note in the 18).

**First attempt (rejected):** exact-match for bare `기말` (+ auto-generated `기말{display_name}` compound aliases). Re-gating proved this **over-corrected** — it destroyed genuine intangible matches at 5 companies (CJ대한통운, SK텔레콤, 삼성SDI, 현대건설, 대한항공), whose real closing totals are labeled `기말의 무형자산 및 영업권` / `기말 영업권 이외의 무형자산` (i.e. `기말` + account phrase *with particles*), which neither exact-match nor the narrow compound alias caught.

**Decision (shipped):** bare `기말` → **prefix match** (`normalized.startswith("기말")`), which restores coverage of all real `기말 …` closing-total labels, **combined with** rejecting movement/adjustment rows in `_is_balance_row` (tokens `환율조정/환산/평가손익`). This resolves the structural CJ-vs-IP tension cleanly: a closing total *starts with* `기말`; movement rows are filtered *before* ranking; sub-components (`자산화된 연구개발비 장부금액`) don't start with `기말`. The principle: **`_is_balance_row` = "is this a net closing balance (not a movement/contra/gross)?"** Any `기말 …` row that survives it is a genuine closing balance.

### F-1 (MAJOR, Codex) — a gross/accumulator row starting with `기말` could be selected over the net carrying total
`기말 취득원가` (gross cost; confirmed in real filings, 세방 2024) or `기말 손상차손누계액` (accumulated-impairment contra) are positive, start with `기말`, and were not caught by the movement tokens → prefix `기말` rank-4 could beat a real net total (`장부금액`/`공정가치`). Selecting gross/contra instead of net carrying is the same class as ADR-0010 ("never select 총장부금액/취득원가").

**Decision (shipped):** extend `_NON_BALANCE_LABEL_TOKENS` with `취득원가` and `누계액` (covers 감가상각/상각/손상차손 누계액). **Zero corpus delta** (pure defensive guard for out-of-corpus filings). Pinned by `test_fs_note_gross_cost_row_not_selected_over_net_carrying_total`.

### M-1 (MAJOR, Opus) — A3 `기준일` touches out-of-scope dividends
`_is_non_amount_field_label` applies to all accounts; the `기준일` token drops a `배당기준일` date-cell (e.g. 20250228) from the dividends pool. **Verified safe:** the only corpus effect is 삼성전자 dividends shifting from a garbage date-value gap to a real-number gap — still a gap, no false match created, no genuine gap suppressed; CJ/NAVER dividends unchanged. A date is never a dividend amount, so the hygiene is sound. Pinned by `test_fs_note_dividends_record_date_cell_never_selected`. Dividends remains a deferred residual otherwise.

### M-2 (MAJOR, Opus) — `checks_cfs_note` imports private symbols from `checks_fs_note` (layering debt)
`checks_cfs_note` imports `_is_non_amount_field_label` and `_plausible_amount` from `checks_fs_note`. No circular import (fs does not import cfs), so it is correct but a layering smell — the spec intended a shared home. **Decision (deferred, recorded debt):** move these (plus `_MAX_PLAUSIBLE_AMOUNT`, `_NON_AMOUNT_FIELD_LABEL_TOKENS`) into `_match_helpers.py` in a follow-up; not done in this accuracy-critical slice to minimise unrelated churn. Tracked in `docs/accuracy-backlog.md`.

### Minor / confirmed sound
- m-1 (Opus): duplicate non-amount filter in the `else` branch — simplified.
- n-1 (Opus): redundant pre-filter `if not note_hits` guard — removed; the post-filter guard remains (catches the filter emptying the pool).
- Codex F-2/F-3/F-5: movement-token reject, specific-alias precedence, EPS ceiling, `채권` reject — all confirmed sound, no legitimate balance row affected within the 6 balance-sheet accounts.
- Codex F-4 (speculative): `채권` reject could abstain a future `…채권 담보부 단기차입금` row — an abstain (coverage), not a false match; acceptable under "abstain over guess."

## Residuals (NOT this slice)
- **B-2b level-aware** (current/noncurrent FS line ↔ note total): 대한항공/CJ lease now pair to the *right account* but the wrong level (`fs_hits[0]` is the current portion). The note `비유동 리스부채` exactly equals the FS noncurrent line — a future match blocked only by fs-line selection. Deferred per HANDOFF.
- **dividends, revenue, CJ borrowings, total_check, 금융상품** — out of slice scope, preserved.
- **M-2 shared-module move** — layering debt, follow-up.
