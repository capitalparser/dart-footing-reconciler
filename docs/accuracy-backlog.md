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

## Done after PR #2 (item A — rollforward signed-net sign)
- `_movement_amount` no longer force-negates "증가(감소)"·"증감" net-change rows
  (they already carry a disclosed sign). Fixes 현대자동차/현대건설 무형자산 및 영업권
  증감표 false gaps. Corpus before→after: matched 4708 → 4726 (+18),
  unexplained_gap 517 → 499 (−18); explainable_gap/parse_uncertain/not_tested/total
  and all primary checks unchanged. No suppression (no matched↓ / gap↑ anywhere).
  Spot-check: all 7 현대차 signed-net checks tie to disclosed 기말 (diff=0), and a
  genuinely negative signed-net row (−440,739m) is preserved (sign respected both ways).

## Done 2026-06-17 (report presentation — not accuracy)
- **PR #9 report-cockpit-compliance**: `report_html.py` brought up to design-kit
  evidence_cockpit contract (reader-orientation brief, 진행현황/주의 필요/다음 행동 views,
  consolidated gap list, print stylesheet). The hand-built `verification-report-hdec-2024.html`
  mockup design was absorbed into the single renderer and the two one-off HTML mockups deleted.
  Pure presentation: corpus 5-status identical to `run_b5_before` (matched 4739, etc.), lint
  exit 0. Per-company HDEC output unchanged in numbers (498/4/51/72/365).
- **PR #10 not_tested coverage lock**: regression test pins that NOT_TESTED CheckResults are
  surfaced in the 미검증 KPI + 현재 상태 brief (never dropped).

## Remaining clusters (prioritized)

### B decomposition (2026-06-16 corpus diagnosis — 53 fs_note gaps)
Running fs_note across the 10-company corpus revealed B is not one fix but 5
failure classes. Slices, safest-first:
- **B-1 display-unit rounding** ✅ DONE — 백만원 주석 vs 원 FS 반올림(<1 표시단위)을
  tolerance가 못 잡던 건. `display_unit_tolerance`/`amounts_agree`에 `display_unit`
  파라미터를 추가하고 note `unit_multiplier`를 thread. Corpus +12 matched / −12
  unexplained_gap (fs_note + prior_column), primary 불변, 억제 0건. 18개 rounding
  match 전부 `|diff| < unit`, 삼성SDI EPS genuine gap 보존.
- **B-2a 재분류 행 abstain** ✅ DONE — borrowings/bonds 주석을 옳게 찾았어도 후보가
  재분류('유동성 대체')·발행차금 contra·음수 행뿐이면(차입금 잔액은 음수 불가), 잔액이
  아닌 행과 페어링하거나 무관한 주석으로 폴백하지 않고 abstain한다. `_select_note_hit_by_label`
  에 잔액-행 필터(`_is_balance_row`: 음수 또는 대체/할인발행차금/할증발행차금 라벨 제외)
  + topical-empty-after-filter → None. EPS 손실·법인세효익·현금감소·배당은 음수 정상이라
  `_SIGNED_VALUE_ACCOUNTS`로 필터 제외. Corpus before→after: total 8693→8684 (−9),
  unexplained_gap 479→469 (−10), **matched 4738→4739 (+1, 억제 0건·정타 1건 회복)**,
  explainable/parse_uncertain/not_tested/primary 불변. 제거된 10 gap 전부 wrong-row
  (삼성SDI/현대차/현대건설/한화오션/SGC "유동성 대체", 더존비즈온 depreciation 음수행),
  회복된 1 match는 더존비즈온 depreciation 정타 주석(23.7bn). EPS 손실(롯데쇼핑
  -34,674) 매칭 보존 확인.
  잔여 **B-2b** (FS 단기/장기 합산: `fs_hit[0]`만 써서 단기차입금만 비교 → note 총액과
  gap): 별도 슬라이스. abstain된 차입금들은 이제 honest not_tested coverage.
- **B-2b FS 단기/장기 합산** ⏸ DEFERRED — naive 합산은 gate-negative. 현재 matched인
  현대건설:17(744bn=유동차입금=단기차입금)·CJ:20(1.074tn)은 current-portion 매칭이라
  FS 단기+장기를 합산하면 exp가 커져 매칭이 깨짐(현대건설 1.34tn, CJ 2.06tn). 살아남은
  borrowings gap 대부분은 wrong-note over-classification(B-4)이라 FS 합산으로 해결 안 됨.
  올바른 해법은 note 행의 집계 레벨(총액 vs 유동분)에 맞춰 FS측을 합산/단일선택하는
  level-aware matching이며 B-4 이후로 미룬다.
  - **PROMOTED 2026-06-21 → ADR-0008.** level-aware matching은 locator의 `current_portion`/
    `noncurrent_portion` role(Phase 4)로 흡수. 별도 slice 대신 locator가 유동/비유동 cell을
    선택하면 check 층이 FS 단기+장기 합산 vs portion-to-portion을 결정.
- **B-3 dividends confounder 제외** ✅ DONE — 배당 reconciliation은 소유주에게 *지급된*
  현금배당 총액만 대상으로 한다. dividends `note_amount_exclusions`에 non-payout
  confounder 16종(수익/수취/수령/받은/받을/주식수/주당/배당률/배당성향/평균적립금/
  미지급/배당권/비지배/신종자본증권/주식배당/인식되지)을 등록하고, `_entry_for_statement_label`
  에서 같은 제외 규칙을 재무제표(SCE/CF) 행에도 적용. Corpus before→after:
  total 8701→8693 (−8), unexplained_gap 487→479 (−8); matched 4738 불변(억제 0건),
  explainable_gap/parse_uncertain/not_tested/primary 전부 불변. 제거된 8 fs_note
  pairing은 모두 confounder note 행 대상(배당금수익/관계기업수령/배당받을주식/
  신종자본증권배당/비지배배당/주식배당/인식되지아니한분배금/배당성향 ratio)으로,
  진짜 "지급된 배당금" 총액 행은 어디서도 제외되지 않음(per-company 배당 행 전수 확인).
  보존: SGC에너지(23.5bn vs 24.5bn)·롯데정밀화학(58.6bn vs 50.9bn) genuine gap 유지,
  셀트리온은 "소유주에 대한 배분으로 인식된 배당금", 현대차/현대건설은 중간배당·
  특수관계자 지급 행으로 페어링 품질 개선(현대건설 act=0 ratio 행 → 5.83bn 지급 행).
  잔여(B-2/B-4): 현대차·현대건설·셀트리온은 row/column·scope 선택 이슈로 여전히 gap.
  ~~배당수익·주식수·우선주배당 mis-pair~~
- **B-4 틀린 주석 over-classification 폴백 차단** ✅ DONE (1차) — 재무상태표 잔액 계정
  (borrowings/bonds/PPE/무형자산/투자부동산/리스부채)은 진짜 주석 제목이 항상 계정명과
  일치하므로(차입금/사채/유형자산…), 제목 일치 주석이 없으면 곧 진짜 주석 부재로 본다.
  `_select_note_hit_by_label`에서 잔액 계정 + topical 없음 → 과분류된 무관 주석으로
  폴백하지 않고 abstain(`_BALANCE_SHEET_ACCOUNTS`). revenue/cost/sga/depreciation은
  주석 제목이 계정명과 달라(영업부문/비용분류) 폴백이 필요하므로 제외. Corpus
  before→after: total 8684→8675 (−9), unexplained_gap 469→460 (−9), matched 4739
  불변(억제 0건), 나머지 전부 불변. 제거된 9 gap 전부 garbage wrong-note 페어링
  (PPE 1.24조 vs 매출채권 267백만, 사채 96조 vs SPC 10백만, 차입금 vs 현금흐름표 합계 등)
  으로 per-check 전수 확인, matched 손실 0건. revenue→영업부문·법인세 폴백 매칭은 보존.
  잔여(2차): note_amount_aliases 자체를 좁혀(유동/비유동 bare token) 과분류 행이 애초에
  태깅되지 않게 하는 작업 — topical 안에서의 과분류는 아직 남음.
- **B-5 note-classification coverage 회복** ❌ ATTEMPTED & REVERTED (2026-06-16) — 진짜
  주석은 실재하나(셀트리온 "유형자산", SGC "무형자산", 롯데정밀화학 "유형자산") 총액 행이
  PPE/무형 note_amount_aliases(장부금액/기말)에 안 걸려 누락 → B-4로 abstain된 coverage를
  회복하려 시도. title-gated "{계정명} 합계" 인식(`_is_account_total_label`, table_entry가
  같은 계정일 때만)을 구현. **결과: gate FAIL.** full-corpus aggregate는 matched +4처럼
  보였으나 per-check 분해 시 **12 회복 / 8 정타 파괴**:
  - 회복(abstain→match) 12: 셀트리온·롯데정밀화학·현대차 무형/유형/투자부동산
  - 파괴(match→gap) 8: CJ대한통운 무형자산×2, 더존비즈온 PPE/투자부동산/리스×2
  **근본 결함:** "{계정명} 합계"는 순장부금액이 아니라 **gross/취득원가 총액**인 경우가
  많고(예: 더존 "유형자산 합계"=549bn(gross) vs "기말 유형자산"=361bn(net=FS)), 선택
  우선순위에서 "합계"(rank 2)가 "기말"(rank 8)을 압도해 **올바른 순액 행을 밀어냄**.
  net +4는 8건 정타 파괴를 가린 것 → revert. **올바른 해법:** 단순 합계가 아니라 순장부금액
  (기말 {계정}/기말장부금액)만 총액으로 인식 + gross 합계 배제 + 선택 우선순위 재설계.
  net-vs-gross 구분이 필요한 dedicated 설계 작업. 현재 abstain 상태는 honest coverage gap.
  - **REFINED 2026-06-17 (parsed real notes):** the net carrying amount is not a *row*
    problem but a *column*/*layout* problem, and the layout VARIES by company — there is no
    single discriminator:
    - **더존 유형자산 N9**: net-vs-gross matrix. Row "유형자산 합계", columns
      `[총장부금액 549bn(gross) · 감가상각누계 · 정부보조금 · 장부금액 합계 361bn(NET=FS)]`.
      Net = the "장부금액(합계)" column; gross = "총장부금액". Reverted attempt grabbed gross.
    - **셀트리온 유형자산 N12-1**: rollforward matrix. Row "유형자산 합계", columns
      `[기초 1,214bn · 변동조정 … · 기말]`. Net = the "기말" column, not 기초/movement.
    - **더존 무형자산 N12**: ending-balance row "기말 무형자산 및 영업권" spread across
      asset-TYPE columns (산업재산권/회원권/개발비/…). Net = row sum across category columns.
    So a safe fix must identify the net carrying amount across ≥3 table archetypes
    (net-gross matrix → net column; rollforward → 기말 column; category matrix → row sum)
    while never selecting 총장부금액/취득원가/기초. Partial single-archetype handling is
    fragile across companies.
  - **DECISION 2026-06-17: keep DEFERRED.** Per CLAUDE.md (domain accuracy > coverage;
    honest abstain > false confidence), forcing marginal PPE/intangible total coverage at
    the risk of false matches in an audit tool is the wrong trade. The abstain is correct,
    not a bug. A real fix is a dedicated multi-archetype note-layout model (own spec/plan +
    per-company gate via `scripts/check_per_company_snapshot.py`), not a slice.
  - **PROMOTED 2026-06-21 → ADR-0008 Canonical Amount Locator.** The "dedicated multi-archetype
    note-layout model" is now scoped as `amount_locator.py` (`net_carrying_amount` role across
    net-vs-gross matrix / rollforward / category matrix). 더존·셀트리온·롯데정밀화학 are the
    acceptance triad. See `docs/superpowers/specs/2026-06-21-canonical-amount-locator.md`
    (Phase 2 corpus gate). Do not attempt another single-archetype slice.
  - **PARTIAL RECOVERY 2026-06-22 (locator wired into reconciliation_inputs).** Wiring
    `amount_locator.locate()` into `reconciliation_inputs` for the three asset accounts
    (PPE / intangible / investment_property) net-carrying + period-end — and letting the
    locator drive ROW identification when the legacy alias path abstains — recovered the
    10-company corpus **matched 4739→4743 (+4), unexplained_gap 460→458 (−2)**, with
    `parse_uncertain`/`not_tested` flat and **zero companies' unexplained_gap rising (FP=0)**.
    Recoveries: 롯데정밀화학 (gap→matched), 현대건설 (gap→matched), 셀트리온 (+2 net-new matched).
    All recovered matches are **diff=0 ties to the BS net-carrying line** — self-validating
    (a gross/wrong cell cannot coincidentally equal the exact-won net carrying amount).
    Correction to the ADR-0008 phase model: B-5 recovery happens in **reconciliation_inputs
    row identification**, not a separate taxonomy phase; the Phase 2 "column-only refiner"
    was byte-identical because the blockage was row identification (see ADR-0009 F2). Phase 3
    (taxonomy `_generic_note_row_amount`, verification_candidates) and 더존-specific cases
    remain; baseline `tests/baselines/per_company_counts.json` updated + regression-locked.
- ~~**B-5 별도 scope** (차입금 note 별도 slice 미분류 → fallback wrong note)~~: B-4가 wrong-note
  fallback을 abstain으로 차단함. 잔여는 위 B-5 coverage 회복(net-vs-gross)으로 흡수.

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

### 2. note_rollforward_check — variation sign / missing movement  [note_assertions.py / formula_discovery.py]  ✅ RESOLVED (item A)
- Blank-subcolumn FP fixed (d154a26). Residual was: 현대자동차 무형자산 기초 700,819 /
  기말 726,830 (net +26,011) but engine variation sum = −26,011 → diff +52,022.
- **Root cause:** `_movement_amount` force-negated the "기타변동에 따른 증가(감소)" net
  row because its label contains "감소", double-counting the sign that the disclosed
  value already carries.
- **Fix (item A):** treat labels containing "증가" or "증감" as signed-net rows and do
  NOT force-negate them. Corpus-gated (+18 matched / −18 unexplained_gap, no
  suppression). See "Done after PR #2" above.

### 3. total_check residuals  [checks_totals.py]
- 비파생금융부채: |components| == |total| but disclosed 합계 is negative (liquidity-table
  sign convention) — kept as a legitimate "does not tie as presented" flag (ADR-0007).
- column-total base-row reconciliation tables — needs reconciliation-table semantics
  (ADR-0007 residual).

### 4. parse_uncertain "전기 표" (~bulk of 473 total_check)
- Mostly LEGITIMATE abstention (prior-period mirror tables without a clean total).
  Do NOT force-foot — would reintroduce FPs. Only recover where a safe total exists.

#### 4a. parse_uncertain reason-code instrumentation gap (2026-06-17 diagnosis)
- **Finding:** all 500 corpus parse_uncertain render `UNKNOWN` in the 파싱 진단 panel.
  `PARSE_UNCERTAIN` is raised at **53 sites across 9 files** but `parse_uncertain_reason`
  is set at only **4 sites (checks_statement_ties.py)**. The other ~49 sites pass no reason.
- **Consequence:** the legitimate abstentions (§4) cannot be told apart from the genuinely
  recoverable ones — the diagnostic panel is blind, so any "reduce parse_uncertain" target
  is unmeasurable.
- **Correction to earlier framing:** "reduce 500 parse_uncertain = biggest reliability
  lever" is overstated. Most are correct abstentions; forcing them would re-introduce FPs.
  The real bounded prerequisite is **reason-code instrumentation** (tag each raise site with
  one of LABEL_NOT_FOUND / LOW_CONFIDENCE_MATCH / AMBIGUOUS_MULTIPLE / COLUMN_NOT_DETECTED /
  TABLE_NOT_FOUND / AMOUNT_PARSE_FAILED), then triage by code.
- **Scope:** 8 files / ~49 sites = Tier 3 multi-file change. Should carry a plan and is a
  natural Codex handoff (code-heavy refactor) per CLAUDE.md §5.0. Instrumentation alone is
  additive metadata (must not change any of the 5 status counts — corpus-gated).

- **✅ DONE 2026-06-17 (PR #12, Codex-implemented, Claude-verified).** reason codes threaded
  through formula_discovery (VerificationFormula `__post_init__` maps free-text → code),
  footing, checks_totals, checks_note_note, checks_reconciliation, layout_formula_assertions.
  Independent corpus gate: 5-status byte-identical to `run_b5_before` (matched 4739 …, 0 failed).
  Tests 793 passed (800 w/ corpus). **UNKNOWN: 500 → 0.** Distribution:
  `491 AMOUNT_PARSE_FAILED · 8 AMBIGUOUS_MULTIPLE · 1 LOW_CONFIDENCE_MATCH`.
  - **Honest residual:** 98% (491/500) collapsed into one code. So the diagnostic is now
    *coarse-but-non-blind*. The real next triage is **decompose AMOUNT_PARSE_FAILED** —
    separate legitimate prior-period mirror-table abstentions (keep) from recoverable
    parser gaps (recover) — not a 6-way even split. Mapping uses `reason.startswith(...)`
    substring rules; formula_discovery branches whose reason text matches neither
    `low-confidence` nor `missing ` would fall to None (none fire in this corpus → UNKNOWN 0,
    but latent for other filings).
  - **Decompose follow-up 2026-06-17:** all 500 parse_uncertain are `parse_uncertain_total`
    (total_check) per `gap_categories` — i.e. tables without a clean footable total
    (prior-period mirrors etc.), exactly §4. The AMOUNT_PARSE_FAILED instrumentation matches
    this. **No safe bulk recovery exists** — forcing a total would re-introduce FPs (§4
    principle). Future *targeted* recovery (current-period tables with a real but unfooted
    total) is now queryable via the reason code + table period, but is dedicated work, not a
    slice. Net: the abstentions are doing their job; the gap is honest, not a defect.

## Principle
Reducing parse_uncertain or unexplained_gap is not always correct — abstention and honest
gaps protect against false confidence. Every change must pass the corpus gate
(unexplained_gap must not rise from new FPs; genuine findings must not be suppressed).
