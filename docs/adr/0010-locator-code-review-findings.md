# 0010. Canonical Amount Locator — Phase 1 code-review findings (cross-model)

**Date:** 2026-06-21
**Status:** Accepted — **NO-GO for Phase 2 wiring** until the BLOCKERs below are closed.
**Inputs:** Tier-3 cross-model code review (heavy-zone step 8) of Phase 1 (`amount_locator.py` @ cb2f950).
- Leg (a) Opus `code-reviewer` agent — verdict **REQUEST CHANGES**.
- Leg (b) Codex (GPT-family) adversarial self-review — verdict **NO-GO**.

Both legs independently reproduced their findings by calling `locate()`/helpers directly. They **converged** on the same primary BLOCKER. Claude (verifier) independently confirmed the two structural BLOCKERs by reading `amount_locator.py:275` and `:333`/`:652`.

## Convergent verdict
Architecture is sound; the three-outcome contract, degenerate-input robustness (no crashes), `component_sources`, and the orthogonality guard are all good. But against the doctrine *abstain over guess; an audit verdict must never carry a false match*, three paths can emit a **false `LocatedAmount`** the moment Phase 2 routes `reconciliation_inputs` through the locator. Module is correctly UNWIRED, so nothing has reached the corpus yet.

## BLOCKERs (must fix before Phase 2)

**B-1 (both legs) — `unknown_layout` (conf 0.0) emits a confident LocatedAmount; `LOW_CONFIDENCE_MATCH` never wired.**
`"unknown_layout"` is in `_ASSET_NET_LAYOUT_KEYS` (`amount_locator.py:652-660`), so a table the classifier completely failed on dispatches into the full header-substring heuristic; `_located()` (`:333`) returns `confidence=0.0` as a "confidently selected amount". Both legs reproduced: an `unknown_layout` table with an account-total row + a single column whose header contains `장부금액` returns a LocatedAmount, not an Abstain. `LOW_CONFIDENCE_MATCH` is declared (`:98`) but emitted nowhere. The one passing fixture (더존 투자부동산 N11, conf 0.0) masks this.
**Fix:** (a) remove `"unknown_layout"` from `_ASSET_NET_LAYOUT_KEYS`; give 더존 투자부동산 N11 a real `classify_layout` key (or a dedicated investment-property/simple-net archetype) so it is covered by an archetype, not a blind heuristic; **and** (b) add a confidence floor in `locate()`/`_located()` — if `layout.confidence < 0.5` and the result relied on header-substring inference → `Abstain(LOW_CONFIDENCE_MATCH)`.

**B-2 (Codex; Claude-confirmed at `:275`) — `period_end` silently downgrades to `net_carrying` when 기말 is absent.**
`_locate_asset_period_end` does `if col_idx is None: return _locate_asset_net_carrying(ctx)` (`:273-275`), contradicting spec §3.4 "기말 absent → abstain `COLUMN_NOT_DETECTED`". A period-end request returns a net-carrying cell.
**Fix:** replace the fallback with `Abstain(COLUMN_NOT_DETECTED)`; regression: net/gross columns present but no current-period ending column → abstain.

**B-3 (Codex) — net-carrying prefers a family-total column not filtered against gross/opening.**
`_locate_asset_net_carrying` / `_net_carrying_column` prefer `family_cols` (detected by account-family aliases, `~:448/:551`) over explicit `net_cols`; family columns are not excluded against `총장부금액`/`취득원가`/`기초`. A multi-row-header column carrying both `유형자산합계` and `총장부금액` can be selected for `NET_CARRYING_AMOUNT`, violating "never select 총장부금액/취득원가".
**Fix:** prioritize explicit net labels; allow a family-total column only when the same header band positively indicates net/carrying AND negatively excludes every gross/opening variant.

## MAJORs (fix with B-1..B-3; each can cause a wrong amount or corrupt the gate)

**M-1 (Opus) — category-matrix row-sum double-counts a 소계 (subtotal) column.** `_category_component_columns` excludes family-total/gross but not intermediate `소계`/`부분합`. Row `[토지10, 건물20, 소계30, 기계40, 합계100]` sums `{10,20,30,40}` → inflated. **Fix:** skip `소계`/`부분합`/subtotal columns; structural guard — if Σcomponents ≠ family-total anchor (when present), Abstain.

**M-2 (Opus) — scope does not drive selection when the scope marker is glued to the label** (`연결 장부금액` → normalized `연결장부금액` ∉ exact sets → all columns returned). Safe-side (abstains) but "scope drives selection" is only half-true. **Fix:** substring/split matching for scope+net markers, not exact-set membership; add an inline-scope mirror-table regression pin.

**M-3 (Opus) — `_is_prior_period_table` over-fires** on `당기 … (전기 대비)`, `… (전기말 잔액 포함)`, `… (전기 비교)` → false `NotApplicable`/`not_tested`, understating coverage. **Fix:** require `전기` as a standalone qualifier (e.g. only when `당기` absent); expand the combined-table allowlist.

**M-4 (Opus) — Abstain reason-code miscategorization.** Two net columns → `COLUMN_NOT_DETECTED`/`AMOUNT_PARSE_FAILED` instead of `AMBIGUOUS_MULTIPLE`. Misleads the PR #12 instrumentation + Phase 2 gate diagnosis. **Fix:** `len(candidates)>1` → `AMBIGUOUS_MULTIPLE`; `==0` → `COLUMN_NOT_DETECTED`; parse fail on an identified cell → `AMOUNT_PARSE_FAILED`.

**M-5 (Codex) — deferred roles (`current_portion`/`noncurrent_portion`) return `NotApplicable` (→ not_tested) although they are "applicable-but-unimplemented".** **Fix:** add an explicit unimplemented-role guard distinct from `not_tested`, or ensure Phase 2 callers request only implemented roles.

## MINORs
- Orientation computed then discarded (`:180-182`): wire an orientation gate (abstain on unsupported orientation) or document transposed tables as an explicit exclusion.
- `_has_mixed_unit_rows` scans only `row[:2]`: widen to all cells/heading.
- Gross/contra exclusion set omits `감가상각누계액`/`상각누계액`/`손상차손누계액`: make contra handling explicit in the category-matrix path.

## Tests to add (both legs) — the suite must FAIL with the BLOCKERs present
- `unknown_layout` / `confidence < 0.5` on an unseen table → **Abstain(LOW_CONFIDENCE_MATCH)**, not LocatedAmount.
- `period_end` with no current-period ending column → **Abstain**, not a net cell.
- net-carrying where a family-total column is actually gross → does **not** select gross.
- category matrix with an intermediate 소계 column → no double-count (or Abstain).
- inline-scope mirror table (`연결 장부금액`/`별도 장부금액` in one cell) → scope drives column.
- assert `(layout.key, evidence[3] strategy_id)` per real-fixture pin → exposes over-fit (each `_ASSET_NET_LAYOUT_KEYS` member needs one positive + one abstain sibling).

## Gate
Phase 2 wiring is blocked until B-1, B-2, B-3 and M-1, M-2 are closed **with the failing-first tests above**, re-verified (full pytest + ruff), and re-committed. M-3/M-4/M-5 and the MINORs should land in the same fix batch.
