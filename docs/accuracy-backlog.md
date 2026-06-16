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
- **B-4 틀린 주석 over-classification** (투자부동산 텍스트행, bonds 주석1 SPC, PPE→매출채권):
  note_amount_aliases가 텍스트/무관 행까지 태깅. 최대 blast radius.
- **B-5 별도 scope** (차입금 note 별도 slice 미분류 → fallback wrong note): residual #2.

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

## Principle
Reducing parse_uncertain or unexplained_gap is not always correct — abstention and honest
gaps protect against false confidence. Every change must pass the corpus gate
(unexplained_gap must not rise from new FPs; genuine findings must not be suppressed).
