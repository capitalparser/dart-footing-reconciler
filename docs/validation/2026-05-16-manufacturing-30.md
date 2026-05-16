# Manufacturing 30-Company Validation

Date: 2026-05-16

Corpus: 30 listed Korean manufacturing companies with 2024 annual reports filed on DART in 2025.

Raw DART viewer HTML files were stored outside the repository under `/tmp/dart_footing_manufacturing_30/`. The repository keeps only this validation summary and deterministic rule changes.

## Scope

Validation command:

```bash
uv run dart-footing validate /tmp/dart_footing_manufacturing_30/manifest.json \
  --format json \
  --mode conservative \
  --tag manufacturing
```

Conservative mode scans the current target families only:

- property, plant and equipment
- intangible assets
- investment property
- borrowings, bonds, and lease liabilities

## Sample Set

| # | Company | Stock code | DART receipt no. |
|---:|---|---:|---:|
| 1 | APS이노베이션 | 079810 | 20250320001123 |
| 2 | AP시스템 | 265520 | 20250320001493 |
| 3 | AP위성 | 211270 | 20250319000342 |
| 4 | BGF에코머티리얼즈 | 126600 | 20250318001010 |
| 5 | BYC | 001460 | 20250320001026 |
| 6 | CJ씨푸드 | 011150 | 20250317000808 |
| 7 | CJ제일제당 | 097950 | 20250317000648 |
| 8 | CMG제약 | 058820 | 20250320000895 |
| 9 | CS | 065770 | 20250320000616 |
| 10 | CSA 코스믹 | 083660 | 20250317000884 |
| 11 | DB하이텍 | 000990 | 20250312001130 |
| 12 | DGI | 099520 | 20250319000578 |
| 13 | DH오토넥스 | 000300 | 20250401000004 |
| 14 | DH오토리드 | 290120 | 20250331004359 |
| 15 | DH오토웨어 | 025440 | 20250321000004 |
| 16 | DKME | 015590 | 20250320001708 |
| 17 | DL | 000210 | 20250317000751 |
| 18 | DMS | 068790 | 20250321001994 |
| 19 | DN오토모티브 | 007340 | 20250313001452 |
| 20 | DRB동일 | 004840 | 20250313000850 |
| 21 | DSR | 155660 | 20250227006937 |
| 22 | DSR제강 | 069730 | 20250226005968 |
| 23 | DS단석 | 017860 | 20250321001800 |
| 24 | DYP | 092780 | 20250321001077 |
| 25 | EG | 037370 | 20250318000397 |
| 26 | F&F | 383220 | 20250318001144 |
| 27 | GH신소재 | 130500 | 20250317000380 |
| 28 | GST | 083450 | 20250318000728 |
| 29 | HB솔루션 | 297890 | 20250318001052 |
| 30 | HB테크놀러지 | 078150 | 20250317000922 |

## Result Progression

| Stage | Total tables | Matched | Unexplained gaps | Notes |
|---|---:|---:|---:|---|
| Initial 30-company run | 266 | 164 | 102 | Baseline conservative scan |
| After movement-range fix | 266 | 219 | 47 | Ignored composition rows after ending balance |
| After displayed-sign fix | 266 | 236 | 30 | Preserved displayed sign for transfer, revaluation, and FX rows |
| After scope/column filter fix | 260 | 236 | 24 | Skipped stock option tables and non-carrying cost/accumulated columns |
| After liability amortization fix | 260 | 244 | 16 | Treated positive amortization as an increase in bond/liability contexts |

Current match rate: `244 / 260 = 93.8%`.

## Implemented Rule Improvements

1. Movement range is bounded between the selected beginning and ending balance rows.
   - Prevents composition sections such as cost, accumulated depreciation, impairment allowance, and carrying amount from being added after the ending balance.

2. Displayed-sign rows keep their parsed amount sign before contra-keyword logic.
   - Covers labels such as `증가(감소)`, `대체`, `재평가`, `외환`, `환율`, and `환산`.

3. Conservative mode excludes stock option tables contaminated by nearby convertible bond text.
   - Covers `주식매수선택권`, `주식선택권`, `행사가격`, and `가중평균행사가격`.

4. Footing skips non-carrying amount columns in mixed cost/carrying value tables.
   - Covers `총장부금액`, `취득원가`, accumulated amortization/depreciation, and impairment allowance columns.

5. Positive `상각` is treated as an increase in liability contexts.
   - Covers bond and liability movement tables where amortized-cost accretion increases the carrying amount.

## Remaining Gap Classification

At tolerance `1`, 16 tables still show unexplained gaps.

Tolerance sensitivity:

| Tolerance | Matched | Unexplained gaps |
|---:|---:|---:|
| 1 | 244 | 16 |
| 1,000 | 250 | 10 |
| 100,000 | 255 | 5 |

Observed remaining categories:

- Small rounding/display-unit differences: DSR, DS단석 tax tables, EG, DB하이텍, DL.
- Cash flow statement bridge tables: AP시스템 lease liability table under supplementary cash flow disclosure.
- Missing or implicit movement components: CJ씨푸드, CJ제일제당, DKME, GST.
- Contra-asset or government grant columns: DS단석 intangible asset tables with `국고보조금(개발비)`.

## Next Rule Candidates

Required before cash flow reconciliation:

- Add a separate `rounding_gap` or `within_materiality_tolerance` status instead of hiding small gaps as `matched`.
- Split table-local footing from CFS bridge checks so cash flow supplementary tables are not forced into the same movement equation.
- Add column-role classification for contra assets and government grants.

Recommended:

- Keep default tolerance conservative for audit evidence, but allow validation reports to show tolerance sensitivity.
- Build per-company diagnostic reports that list excluded tables, matched tables, and gaps with table indices.
- Expand manufacturing corpus beyond 30 companies only after the remaining 5 structural gap families are handled.
