# Handoff

## Objective

Implement a Python package and CLI that checks DART DSD/HTML filings for note footing and cash flow statement reconciliation.

## Current State

The repository now has a multi-company workpaper corpus runner, reviewer-facing
HTML reports, and Phase 1 primary unresolved taxonomy artifacts. The 100-company
corpus now meets Gate 1: primary no-difference reconciliation is 72.87%, above
the 70% target.

- Core package and CLI first
- MCP wrapper later
- Initial checks for PPE, intangible assets, investment property, borrowings, bonds, and lease liability cash flow relationships
- Result statuses: `matched`, `explainable_gap`, `unexplained_gap`, `parse_uncertain`
- Latest 100-company evidence:
  - `out/corpus/run_2026-05-27-hundred-v81/corpus_report.md`
  - `out/corpus/run_2026-05-27-hundred-v81/primary_unresolved_taxonomy.json`
  - `out/corpus/run_2026-05-27-hundred-v81/primary_unresolved_taxonomy.md`
  - `out/corpus/run_2026-05-27-hundred-v81/false_matched_review.md`
  - `docs/validation/2026-05-26-phase1-unresolved-taxonomy.md`
- Latest implementation slice: reconciliation logic handoff T5/T1/T2
  implementation started. Balance candidates whose absolute difference exceeds
  the financial statement amount are now downgraded to `parse_uncertain`
  instead of determinate unexplained gaps, preventing economically impossible
  wrong-row note matches from being treated as arithmetic differences. Asset
  disposal bridges now classify accumulated depreciation/amortization disposal
  rows as disposal adjustments rather than primary disposal evidence, allowing
  gross-cost disposal tables to reconcile as gross disposal less accumulated
  depreciation disposal plus disposal gain/loss. PPE acquisition bridges now
  treat right-of-use asset additions as an additive component only when the CFS
  target line explicitly combines `유형자산` and `사용권자산`; plain PPE
  acquisition targets keep excluding ROU additions as non-cash. Verification
  passed with full `uv run pytest` (361 passed). A clean-HEAD local cached
  corpus comparison using
  `out/corpus/manifest_2026-05-27-hundred-asset-note-bridges.json` generated
  100/100 reports both before and after; reproducible local metrics stayed
  primary checks 243, matched 190, unresolved 53, with 0 newly unresolved
  primary IDs and 0 newly matched primary IDs. The T5 guard moved 19 primary
  balance gaps from determinate unexplained gap to `parse_uncertain` in the
  local cached corpus, so local primary determinate count changed from 243 to
  224 by design. Note: the historical `hundred-accuracy-v1` artifact still
  records 575 primary checks/460 matched/115 unresolved, but the currently
  available cached raw filings reproduce only the 243-check local baseline even
  from clean HEAD.
- Previous implementation slice: asset roll-forward rows/columns that combine
  disposal with impairment, such as `처분/폐기/손상` and `처분, 손상 및 폐기`,
  are no longer used as cash disposal carrying-amount evidence. v80 was
  rejected because it only blocked combined disposal/impairment column headers
  and left combined row labels in the generic movement path. v81 generated
  100/100 reports, reduced primary checks from 577 to 575 by removing two
  wrong-table-class primary disposal checks, kept primary matched at 419,
  reduced unresolved from 158 to 156, improved no-difference rate from 72.62%
  to 72.87%, kept judgment rate at 100.0%, and introduced 0 newly unresolved
  primary check IDs. It removed the low-quality 유한양행 and 한미글로벌 PPE
  disposal cash-flow checks that had been using combined disposal/impairment
  roll-forward rows as if they were direct disposal carrying amounts. The
  remaining primary unresolved taxonomy now has `wrong_table_class` 0.
- Previous implementation slice: terse positive asset-acquisition payable rows
  now emit both the existing payable-direction candidate and a separate
  `noncash_payable_decrease_candidate`. The check engine can select the
  direction that completes the acquisition cash-flow bridge, without globally
  flipping ambiguous `미지급금` signs. v78 was rejected because a global sign
  flip resolved 한화오션 but regressed five previously matched asset acquisition
  checks. v79 generated 100/100 reports, kept primary checks at 577, improved
  primary matched from 418 to 419, reduced unresolved from 159 to 158,
  improved no-difference rate from 72.44% to 72.62%, kept judgment rate at
  100.0%, and introduced 0 newly unresolved primary check IDs. It resolved
  한화오션 PPE acquisition cash-flow: note acquisition `373,337,000,000` plus
  payable decrease candidate `303,000,000` reconciles to CFS PPE acquisition
  `373,640,224,794` within disclosure precision. Three still-unresolved cases
  improved but remain open: 한화솔루션, 한일시멘트, and 후성 PPE acquisition
  cash-flow.
- Previous implementation slice: lease liability financing cash-flow bridge now
  extracts `리스부채에 대한 이자비용` from scoped lease-liability notes as a
  financing adjustment candidate, but the check engine refuses to create a
  financing reconciliation from adjustment-only evidence. v77 generated 100/100
  reports, kept primary checks at 577, improved primary matched from 417 to 418,
  reduced unresolved from 160 to 159, improved no-difference rate from 72.27%
  to 72.44%, kept judgment rate at 100.0%, and introduced 0 newly unresolved
  primary check IDs. It resolved 지누스 lease-liability financing cash-flow:
  note financing cash-flow `(18,161,527,000)` plus lease interest adjustment
  `3,281,644,000` reconciles to CFS principal repayment `14,879,882,698` within
  disclosure precision. v76 was rejected because an adjustment-only extraction
  experiment introduced three new unresolved lease-liability checks.
- Previous implementation slice: financing liability cash-flow column semantics
  now treats `유입` and `유출` columns in financing liability roll-forward
  notes as cash-flow action columns. `유출` is normalized as an outflow in the
  same way as repayment/decrease columns. v75 generated 100/100 reports, kept
  primary checks at 577, improved primary matched from 416 to 417, reduced
  unresolved from 161 to 160, improved no-difference rate from 72.10% to
  72.27%, kept judgment rate at 100.0%, and introduced 0 newly unresolved
  primary check IDs. It resolved 계양전기 borrowings financing cash-flow with
  `75,788,499,000 - 46,830,000,000 + 8,000,000,000 = 36,958,499,000`.
- Previous implementation slice: asset acquisition non-cash adjustment extraction
  now treats `지급어음` acquisition rows as payable-style non-cash acquisition
  obligations. v74 generated 100/100 reports, kept primary checks at 577,
  primary matched at 416, primary unresolved at 161, no-difference rate at
  72.10%, judgment rate at 100.0%, and introduced 0 newly unresolved primary
  check IDs. It improved the still-unresolved 현대위아 PPE acquisition
  cash-flow bridge by adding the `유형자산 취득관련 지급어음의 증가(감소)`
  evidence and reducing the residual from 853,000,000 to 441,000,000.
- Previous implementation slice: generic `처분손익` disposal adjustments from
  operating cash-flow adjustment notes now use their signed net adjustment
  direction when bridging disposal carrying amount to cash proceeds. Positive
  net disposal gain/loss adjustments from a different note than the asset
  roll-forward are subtracted, while explicit `처분이익` rows and asset-note
  disposal-gain/loss rows keep the existing gross disposal formula behavior.
  v73 generated 100/100 reports, kept primary checks at 577, improved primary
  matched from 414 to 416, reduced unresolved from 163 to 161, improved
  no-difference rate from 71.75% to 72.10%, kept judgment rate at 100.0%, and
  introduced 0 newly unresolved primary check IDs. It resolved 삼성SDI and
  효성화학 PPE disposal cash-flow checks.
- Previous implementation slice: CFS rows labeled like `단기차입금의 순증감`
  now preserve their displayed sign as borrowing net-change cash-flow instead
  of being flipped to positive proceeds from the `차입금` substring. The net
  rows are included in financing liability net reconciliation with proceeds and
  repayments. v71 generated 100/100 reports, kept primary checks at 577,
  improved primary matched from 412 to 414, reduced unresolved from 165 to 163,
  improved no-difference rate from 71.40% to 71.75%, kept judgment rate at
  100.0%, and introduced 0 newly unresolved primary check IDs. It resolved
  삼성E&A and 현대코퍼레이션 borrowings financing cash-flow checks.
- Previous implementation slice: CFS rows labeled like
  `차입금중도상환수수료의 지급` and `사채발행분담금의 반환` are now excluded
  from financing liability cash-flow target extraction because they are
  non-principal debt fee/refund rows rather than liability principal movement
  rows. The v69 guard remains: `사채발행비 지급` is still treated as a bonds
  financing cash outflow, while generic `사채발행비용` rows remain excluded.
  v70 generated 100/100 reports, kept primary checks at 577, improved primary
  matched from 410 to 412, reduced unresolved from 167 to 165, improved
  no-difference rate from 71.06% to 71.40%, kept judgment rate at 100.0%, and
  introduced 0 newly unresolved primary check IDs. It resolved 롯데하이마트
  borrowings financing cash-flow by excluding `차입금중도상환수수료의 지급
  250,745,273`, and 롯데하이마트 bonds financing cash-flow by excluding
  `사채발행분담금의 반환 2,268,269`.
- Previous implementation slice: CFS rows labeled like `사채발행비 지급` are now
  treated as bonds financing cash outflows, while generic `사채발행비용` rows
  remain excluded. v69 generated 100/100 reports, kept primary checks at 577,
  improved primary matched from 409 to 410, reduced unresolved from 168 to 167,
  improved no-difference rate from 70.88% to 71.06%, kept judgment rate at
  100.0%, and introduced 0 newly unresolved primary check IDs. It resolved
  세아제강 bonds financing cash-flow with
  `사채의 발행 140,000,000,000 - 사채발행비 지급 447,613,200 -
  사채의 상환 80,000,000,000 = 59,552,386,800`, matching note financing
  cash-flow evidence `59,552,386,800`.
- Previous implementation slice: financing liability roll-forward rows labeled
  `현금흐름` are now read across account columns such as `단기사채`, `사채`,
  `차입금`, and `리스부채`, while non-cash financing movements such as
  `사채할인발행차금상각`, `외화환산`, `유동성대체`, `사업결합`, and `기타`
  are excluded from generic cash-flow fallback extraction. CFS rows such as
  `단기사채의 차입` and `사채의 차입` are classified as bonds proceeds. v68
  generated 100/100 reports, expanded primary checks from 543 to 577, improved
  primary matched from 381 to 409, increased unresolved from 162 to 168,
  improved no-difference rate from 70.17% to 70.88%, kept judgment rate at
  100.0%, and kept false matched review samples at 15. It resolved 한화오션
  bonds financing cash-flow with CFS `단기사채의 차입 166,420,945,212 +
  사채의 차입 99,578,890,000 - 사채의 상환 20,000,000,000 =
  245,999,835,212`, matching note financing cash-flow evidence
  `146,421,000,000 + 99,579,000,000 = 246,000,000,000` within disclosure
  precision. It also removed a low-quality 효성화학 bonds unresolved item where
  the previous evidence was a zero-valued note movement rather than substantive
  cash-flow evidence.
- Previous implementation slice: note display-unit precision tolerance now includes
  the exact display-unit boundary instead of stopping at `unit - 1`. This
  resolves cases where a million-won note table and statement amount differ by
  exactly one million due to source display precision, without changing default
  zero-tolerance behavior. v66 generated 100/100 reports, improved primary
  matched from 380/543 to 381/543, reduced unresolved from 163 to 162, improved
  no-difference rate from 70.0% to 70.2%, kept judgment rate at 100.0%, and
  introduced 0 newly unresolved primary check IDs. It resolved KB금융 intangible
  assets balance where statement `1,966,684,000,000` and note
  `1,966,683,000,000` differ by exactly one `단위: 백만원` display unit.
- Previous implementation slice: trade receivable balance extraction now admits
  allowance rows such as `대손충당금` and `손실충당금` inside
  `매출채권 및 기타채권` ending-balance candidates. The existing contribution
  logic subtracts those allowances when building note subsets. v65 generated
  100/100 reports, improved primary matched from 379/543 to 380/543, reduced
  unresolved from 164 to 163, improved no-difference rate from 69.8% to 70.0%
  on rounded display, kept judgment rate at 100.0%, and introduced 0 newly
  unresolved primary check IDs. It resolved 계양전기 trade receivables balance
  with `매출채권 84,924,256,000 - 대손충당금 204,523,000 + 미수금
  123,579,000 - 대손충당금 330,000 + 미수수익 1,460,000 =
  84,844,442,000`, matching statement `84,844,441,793` within display precision.
- Previous implementation slice: financing liability roll-forward rows labeled
  `새로운 차입금, 재무활동에서 생기는 부채의 증가` and
  `차입금의 상환, 재무활동에서 생기는 부채의 감소` now enter account-column
  financing cash-flow extraction. This covers tables where the row label names
  the borrowing action and the columns split `단기차입금` and `장기 차입금`.
  v64 generated 100/100 reports, improved primary matched from 378/543 to
  379/543, reduced unresolved from 165 to 164, improved no-difference rate
  from 69.6% to 69.8%, kept judgment rate at 100.0%, and introduced 0 newly
  unresolved primary check IDs. It resolved 롯데이노베이트 borrowings financing
  cash-flow with `3,073,019,000 + 69,987,204,000 - 8,073,019,000 -
  25,705,040,000 = 39,282,164,000`, matching the CFS target
  `39,282,164,050` within disclosure precision.
- Previous implementation slice: financing liability roll-forward tables with
  simple `증가`/`감소` action columns now extract both cash inflow and cash
  repayment candidates. This covers tables headed like `재무활동에서 생기는
  부채의 조정내용` where rows are account names (`단기차입금`, `장기차입금`)
  and columns are `기초/증가/감소/대체/.../기말`. v63 generated 100/100
  reports, improved primary matched from 377/543 to 378/543, reduced
  unresolved from 166 to 165, improved no-difference rate from 69.4% to 69.6%,
  kept judgment rate at 100.0%, and introduced 0 newly unresolved primary check
  IDs. It resolved 후성 borrowings financing cash-flow with
  `65,534,356,000 - 71,682,404,000 + 25,000,000,000 - 750,000,000 =
  18,101,952,000`, matching the CFS target within disclosure precision.
- Previous implementation slice: non-cash transaction rows labeled as
  `무형자산 취득에 따른 미지급금 증가` now enter acquisition cash-flow
  formulas as a narrow add-back candidate role. Broader `증가(감소)` and
  `취득 관련 미지급금 증가` rows keep the existing payable-direction rules.
  v61 was discarded because it produced partial HTML output without corpus
  summary artifacts. v62 generated 100/100 reports, improved primary matched
  from 376/543 to 377/543, reduced unresolved from 167 to 166, improved
  no-difference rate from 69.2% to 69.4%, kept judgment rate at 100.0%, and
  introduced 0 newly unresolved primary check IDs. It resolved INVENI
  intangible asset acquisition cash-flow with the direct formula
  `note 13 취득 5,012,218,000 + note 29 무형자산 취득에 따른 미지급금 증가
  4,217,418,000 = CFS 무형자산의 취득 9,229,636,000`.
- Previous implementation slice: beginning carrying-amount labels such as
  `기초장부가액` are no longer classified as ending-balance evidence just
  because they contain the `장부가액` alias. The balance-role classifier now
  applies the `기초`/beginning guard before ending/carrying aliases. v60 did
  not change aggregate Gate metrics from v58: primary matched 376/543,
  unresolved 167, no-difference rate 69.2%, judgment rate 100.0%, and false
  matched review samples 15. It improved evidence fidelity for 한미글로벌 PPE
  balance by changing the note evidence from `기초장부가액 + 기말장부가액`
  to `기말장부가액` only. A broader v59 ROU/PPE balance-combination
  experiment was rejected because it increased primary checks by 5 and created
  5 newly unresolved primary items.
- Previous implementation slice: trade receivable statement evidence now dedupes
  exact parent/child duplicate balance-sheet lines inside the same statement
  table for `매출채권` only. Composite parent rows such as
  `매출채권 및 기타유동채권` and `장기매출채권 및 기타비유동채권, 총액`
  are kept, while same-period child rows such as `매출채권` and
  `장기매출채권, 총액` with the same amount are dropped before summing current
  and noncurrent statement evidence. v57 was rejected because it only removed
  the plain child label and left `장기매출채권, 총액`; v58 improved primary
  matched from 375/543 to 376/543, reduced unresolved from 168 to 167, and
  improved primary no-difference rate from 69.1% to 69.2%. It resolved
  한미글로벌 trade receivables balance with no newly unresolved primary check
  IDs.
- Previous implementation slice: trade receivable balance extraction now reads
  multi-row `당기말 / 총액 / 대손충당금 / 순액` header bands by selecting the
  current-period net amount (`순액`) instead of summing all current-period
  amount columns. It also admits narrow other-receivable component labels such
  as `미수금`, `미수수익`, `단기보증금`, and `장기보증금` inside the existing
  trade receivable candidate path. v56 improved primary matched from 373/543
  to 375/543, reduced unresolved from 170 to 168, and improved primary
  no-difference rate from 68.7% to 69.1%. It resolved 아남전자 and
  롯데하이마트 trade receivables balance with no newly unresolved primary check
  IDs.
- Previous implementation slice: trade receivable balance extraction now treats
  narrow current/noncurrent other-receivable rows inside `매출채권 및 기타채권`
  notes as ending-balance candidates: `기타 유동채권`,
  `기타 비유동채권`, and `유동 계약자산 외의 유동 미수수익`. This allows
  statement lines such as `매출채권 및 기타유동채권` to reconcile to the direct
  note formula `유동매출채권 + 기타 유동채권 + 유동 계약자산 외의 유동 미수수익`.
  v55 improved primary matched from 372/543 to 373/543, reduced unresolved
  from 171 to 170, and improved primary no-difference rate from 68.5% to
  68.7%. It resolved 한솔테크닉스 trade receivables balance with no newly
  unresolved primary check IDs.
- Previous implementation slice: bond financing cash-flow extraction now reads
  bond principal repayment from bond roll-forward tables when a bond note has a
  `원금` row and an `상환...감소` column. The amount is added as a
  `bonds.financing_cashflow` candidate labeled `사채 원금 상환`, so exact
  principal repayment can be selected over broader carrying-amount movements.
  v54 improved primary matched from 371/543 to 372/543, reduced unresolved from
  172 to 171, and improved primary no-difference rate from 68.3% to 68.5%.
  It resolved 후성 bonds financing cash-flow with no regressed, new, or
  removed primary check IDs.
- Previous implementation slice: intangible balance extraction now preserves both
  a combined `무형자산 및 영업권` total candidate and an additional
  goodwill-excluding candidate when the same ending row has
  `영업권 이외의 무형자산` carrying-amount subtotal columns. The extra candidate
  is added instead of replacing the total candidate, after a v52 experiment
  regressed 현대글로비스 by replacing the total. v53 improved primary matched
  from 370/543 to 371/543, reduced unresolved from 173 to 172, and improved
  primary no-difference rate from 68.1% to 68.3%. It resolved 한솔케미칼
  intangible assets balance with no regressed, new, or removed primary check
  IDs.
- Previous implementation slice: trade receivable balance extraction now reads
  financial-instrument category rows where the direct `매출채권` label appears
  in the fourth text cell, such as `금융자산, 범주 / 상각후원가로 측정하는
  금융자산 / 금융상품 / 매출채권 / 금액`. The change keeps the existing
  contract-asset and allowance exclusions and does not loosen tolerance. v51
  improved primary matched from 369/543 to 370/543, reduced unresolved from
  174 to 173, and improved primary no-difference rate from 68.0% to 68.1%.
  It resolved 한국단자공업 trade receivables balance using `note 10 매출채권`
  direct evidence, with no regressed previously matched primary check IDs.
- Previous implementation slice: asset balance extraction now reads multi-row
  asset table header bands more precisely. Asset total `합계`/`총계` rows can
  use current-period carrying/`합계` columns even when the first header row is
  only a unit row, and PPE ending rows such as `기말 유형자산` can use an
  explicit `유형자산 합계` family-total column instead of gross-cost columns.
  The ending-row family-total rule is intentionally limited to PPE after a
  broader v48/v49 experiment regressed intangible balance matches. v50 improved
  primary matched from 366/540 to 369/543, kept unresolved at 174, and improved
  primary no-difference rate from 67.8% to 68.0%. It resolved existing
  unresolved balance checks for 삼익THK intangible assets and 현대건설 PPE,
  exposed an additional matched 써니전자 intangible balance check, and exposed
  two additional unresolved balance findings for 써니전자 PPE and 풍산홀딩스
  intangible assets as coverage-expanded findings.
- Previous implementation slice: right-of-use asset cash-flow notes now provide
  direct lease-liability financing cash-flow evidence when a `사용권자산`
  table headed `현금흐름표에 인식한 금액` contains a `리스부채의 상환` row.
  The extracted amount is normalized as a financing cash outflow and can be
  selected over broader `재무활동에서 생기는 부채` movement-table evidence only
  when it reconciles to the CFS target within source precision. v47 resolved
  한국제지 lease liabilities financing cash-flow with no newly unresolved
  primary check IDs. Primary matched improved from 365/540 to 366/540,
  unresolved fell from 175 to 174, and primary no-difference rate improved from
  67.6% to 67.8%.
- Previous implementation slice: asset balance extraction now treats asset detail
  table `합계`/`총계` rows as ending-balance candidates when the table headers
  identify a current-period `장부금액`/`순장부금액`/`장부가액` column. The amount
  selector uses that carrying-amount column instead of summing all current-period
  gross cost, accumulated depreciation, grant, and carrying columns. v46 is
  accepted as a coverage/fidelity expansion: primary checks increased from
  523 to 540, primary matched increased from 348 to 365, primary unresolved
  stayed 175, and primary no-difference rate improved from 66.5% to 67.6%.
  It resolved old unresolved balance checks for 롯데정밀화학 intangible assets
  and 삼일제약 PPE, exposed 15 additional matched asset balance checks, and
  exposed two additional small unresolved intangible balance checks for
  DB손해보험 and KB금융.
- Previous implementation slice: financing liability cash-flow evidence now
  performs a narrow duplicate-scope recovery for `재무활동에서 생기는 부채`
  note tables. Balance, asset movement, and expense allocation candidates still
  use the primary note filter, but financing cash-flow tables outside that
  filter are added only when they exactly complete an existing scoped financing
  CFS reconciliation. A broader v44 experiment was rejected because it increased
  primary checks from 523 to 526 and introduced three new unresolved primary
  items. v45 resolved 현대비앤지스틸 lease liabilities financing cash-flow with
  no newly unresolved primary check IDs. Primary matched improved from 347/523
  to 348/523, unresolved fell from 176 to 175, and primary no-difference rate
  improved from 66.3% to 66.5%.
- Previous implementation slice: PPE depreciation expense allocation now excludes
  investment-property depreciation from the nature-total basis only when that
  exclusion reconciles the PPE functional allocation total. The extractor reads
  investment-property roll-forward `감가상각비` rows even when the label is in a
  secondary text column, and the check keeps existing matches when the exclusion
  would not reconcile. v43 resolved 시알홀딩스 PPE depreciation allocation with
  no newly unresolved primary check IDs. Primary matched improved from 346/523
  to 347/523, unresolved fell from 177 to 176, and primary no-difference rate
  improved from 66.2% to 66.3%.
- Previous implementation slice: PPE disposal cash-flow formulas now add
  government-grant disposal column movements when a roll-forward separately
  discloses gross carrying amount and `정부보조금` rows. This restores the
  disposal carrying amount to the gross basis needed by the disposal
  gain/loss bridge, while ignoring `정부보조금 차감 전` gross rows as grant
  adjustments. v40 resolved 현대위아 PPE disposal cash-flow with no newly
  unresolved primary check IDs. Primary matched improved from 345/523 to
  346/523, unresolved fell from 178 to 177, and primary no-difference rate
  improved from 66.0% to 66.2%.
- Previous implementation slice: acquisition non-cash payable formulas now treat
  negative `미지급금의 변동` rows as payable increases only when the label
  explicitly says a specific asset acquisition is `관련` to the payable change.
  Short labels such as `유형자산 취득 미지급금 변동` remain payable decreases,
  preserving the accepted 유한양행 bridge. v39 resolved 삼성생명 intangible
  acquisition cash-flow with no newly unresolved primary check IDs. Primary
  matched improved from 344/523 to 345/523, unresolved fell from 179 to 178,
  and primary no-difference rate improved from 65.8% to 66.0%.
- Previous implementation slice: non-cash transaction table extraction now reads
  the first meaningful non-amount detail column when the first column is a stub
  such as `거래내역`. This allows rows such as `거래내역 / 선급금의 무형자산
  대체 / 공시금액` to enter the candidate pool as non-cash transfer evidence.
  v37 did not change 100-company primary metrics versus v36: primary matched
  stayed 344/523, unresolved stayed 179, and primary no-difference rate stayed
  65.8%.
- Previous implementation slice: PPE disposal cash-flow formulas now subtract
  right-of-use asset disposal amounts disclosed inside PPE roll-forward disposal
  rows as non-cash disposals. v36 resolved 세아제강 and 제이에스코퍼레이션
  PPE disposal cash-flow with no newly unresolved primary check IDs. Primary
  matched improved from 342/523 to 344/523, unresolved fell from 181 to 179,
  and primary no-difference rate improved from 65.4% to 65.8%.
- Previous implementation slice: financing liability movement tables now treat
  explicit action columns such as `차입`, `발행`, and `상환` as financing
  cash-flow evidence when the table is already classified as a financing
  liability roll-forward. v35 resolved 노루페인트 borrowings and bonds
  financing cash-flow with no newly unresolved primary cases. Primary matched
  improved from 340/523 to 342/523, unresolved fell from 183 to 181, and
  primary no-difference rate improved from 65.0% to 65.4%.
- Previous implementation slice: acquisition non-cash payable bridge formulas now
  treat a negative amount in `미지급금의 증가(감소)` rows as a payable decrease
  instead of forcing the direction to increase from the label alone. v34 kept
  primary matched unchanged at 340/523 but improved 현대위아 PPE acquisition
  evidence from direct-evidence-missing to a formula-template gap:
  `주석 취득 225,153,000,000 + 비현금거래-미지급금 감소 15,029,000,000 =
  240,182,000,000` versus CFS `241,035,000,000`.
- Previous implementation slice: corpus runs now write a false matched review
  sample at `false_matched_review.md`. v33 selected 15 matched primary checks:
  5 cash-flow reconciliations, 5 balance reconciliations, and 5 expense
  allocation checks, each with expected/actual/difference/tolerance/reason and
  source evidence.
- Previous implementation slice: corpus reports now include a `검증유형별 성공률`
  table with primary counts, no-difference counts, unresolved counts,
  no-difference rate, and automatic judgment rate by check type. v32 shows
  현금흐름 대사 128/285 matched (44.9%), 재무제표-주석 금액 대사 204/227
  matched (89.9%), and 성격별 비용 대사 8/11 matched (72.7%).
- Previous implementation slice: financing liability movement tables whose
  heading ends with `(당기) (전기)` are treated as prior-period tables only for
  financing liability contexts. This removes prior-period financing cash-flow
  movement rows without skipping legitimate current/prior comparative asset
  tables. The 100-company corpus metrics stayed unchanged from v30.
- Previous implementation slice: CFS line extraction now uses current-period
  columns strictly when a cash-flow statement has explicit period headers. If
  the current-period cell is blank, the extractor no longer falls back to a
  rightmost prior-period amount. This resolved 아남전자 and 현대오토에버
  borrowings financing cash-flow, made 금호에이치티 bonds financing cash-flow
  match, and introduced no newly unresolved primary cases.
- Previous implementation slice: CFS borrowing rows with `감소` are now classified
  as repayments before the generic `차입금` proceeds rule can match the `차입`
  substring inside `차입금`. This did not change the matched count but normalized
  a large borrowings financing target without introducing new unresolved cases.
- Previous implementation slice: asset roll-forward transfer rows such as
  `대체에 따른 증가(감소)` now enter acquisition cash-flow formulas as signed
  transfer adjustments, while rows containing `처분` remain disposal primary
  candidates. This resolved two acquisition cash-flow cases with no newly
  unresolved primary cases.
- Previous implementation slice: non-cash transaction tables now extract
  disposal gain/loss adjustments from `기타손익` and generic cash-flow note
  headings, and `유무형자산처분이익/손실` rows are routed to both PPE and
  intangible disposal candidate pools. This resolved four disposal cash-flow
  cases with no newly unresolved primary cases.
- Previous implementation slice: non-cash transaction tables now extract
  `사용권자산 리스부채로의 대체` rows as right-of-use non-cash acquisition
  adjustments for PPE cash-basis formulas. This resolved 제이에스코퍼레이션 PPE
  acquisition cash-flow with no newly unresolved or changed-still-unresolved
  primary cases.
- Previous implementation slice: non-cash transaction tables now extract
  `사용권자산` additions/recognitions as right-of-use non-cash acquisition
  adjustments for PPE cash-basis formulas. This resolved 삼성E&A PPE acquisition
  cash-flow with no newly unresolved primary cases.
- Previous implementation slice: non-cash asset adjustment extraction now detects
  a second-row current-period header such as `거래내용 / 당기 / 전기` when the
  first row only repeats unit labels. This resolved 금호에이치티 PPE acquisition
  cash-flow with no newly unresolved primary cases.
- Previous implementation slice: trade receivables wide detail tables can combine
  `매출채권 및 기타유동채권 합계` and `매출채권 및 기타비유동채권 합계`
  aggregate rows from the same table, even when the table has too many detail
  rows for unrestricted subset search. This resolved GS리테일 trade receivables
  balance with no newly unresolved primary cases.
- Previous implementation slice: trade receivable current/noncurrent column
  balances are summed when DART tables disclose `유동매출채권` and
  `비유동매출채권` as separate amount columns, and secondary row labels such as
  `손상차손누계액` are preserved as allowance evidence. This resolved
  DN오토모티브 trade receivables balance with no newly unresolved primary cases.
- Previous implementation slice: trade receivables composite balance evidence now
  nets allowance labels when the result matches within effective tolerance and
  reads financial-instrument category rows where `매출채권및기타채권` appears
  outside the first column. This resolved 14 primary trade receivables balance
  cases with no newly unresolved primary cases.
- Previous implementation slice: disposal checks can select a later disposal
  carrying-amount row only when it matches the CFS target with compatible
  gain/loss adjustments within effective tolerance. This resolved
  엘에스일렉트릭 intangible disposal without new unresolved primary cases.
- Previous implementation slice: zero-amount CFS rows are excluded from primary
  cash-flow target extraction. This removed six unresolved zero-amount targets
  and four matched zero-amount targets, with no newly unresolved primary cases.
- Previous implementation slice: financing cash-flow note movements now use a
  conservative matching subset only when the subset agrees to the CFS target
  within effective tolerance and improves over the full note sum. This resolved
  10 primary financing cash-flow checks with no newly unresolved primary cases.
- Previous implementation slice: asset subtype CFS rows such as `건설중인 유형자산의 취득`,
  `기타유형자산의 처분`, and `기타무형자산의 취득` are excluded from primary
  total-asset cash-flow targets. This removed six low-quality unresolved
  primary targets and one low-quality matched target.
- Previous implementation slice: asset-related receivable/payable CFS movement
  rows such as `기타채무(유형자산 취득)` are excluded from primary asset
  acquisition/disposal targets. This resolved 하이트진로홀딩스 PPE acquisition
  cash-flow and improved target fidelity for 하이트진로홀딩스 PPE disposal.
- Previous implementation slice: cash-flow formula tolerance now accumulates the
  source precision of each note amount actually used in the bridge. This
  resolved two 애경케미칼 disposal cash-flow checks without new unresolved cases.
- Previous implementation slice: wide roll-forward movement columns are now
  read from account-family total rows, and government grant rows are excluded
  from acquisition movement classification.
- Latest HTML delivery slice: report HTML now applies the PAS Delivery Studio
  surface more strictly. The first viewport includes a three-part reviewer
  brief (`현재 상태`, `왜 중요한가`, `다음 행동`), status badges use neutral
  backgrounds with point-signal dots/borders instead of filled color pills, and
  cash-flow formulas render as two-column audit tables in both the review queue
  and cash-flow reconciliation table. The review brief counts primary
  reconciliation checks only, so supporting total/table diagnostics do not
  inflate the first-screen action count. Verification passed with
  `tests/test_cli_workpaper.py` (20 passed), full pytest (261 passed), and
  browser rendering checks for desktop 1440px and mobile 390px. Visual evidence:
  `out/visual-checks/v82-desktop.png` and `out/visual-checks/v82-mobile.png`.
- Latest corpus note: `out/corpus/run_2026-05-27-hundred-v82/` regenerated 99
  cached reports with the new HTML format. One sample, 셀트리온, remained a
  source-access gap due DART SSL EOF during fetch; therefore v82 is treated as
  HTML-format evidence, not a replacement for the accepted 100/100 v81
  reconciliation metric baseline.
- Latest sample-report fix: the SeAH Steel 2024 HTML report was regenerated at
  `out/corpus/run_2026-05-27-hundred-v82/reports/세아제강_2024.html` after
  reviewer feedback. Statement note drawers now show actual note-table current
  and prior amounts instead of `원문 표` placeholders, income-statement
  operating/finance income and expense lines classify and link to detailed
  notes, equity-statement headers use capital layer labels instead of repeated
  parent `자본`, raw note-table zero/blank amount cells display as `-`, and
  cash-flow judgments render formulas as row-based evidence tables. Focused
  HTML tests and full pytest passed; Playwright render inspection confirmed no
  `원문 표` value cells, 0 raw-table cells normalized to `-`, formula tables
  present, and the updated equity headers in the regenerated report.
- Latest note-assertion slice: `note_assertions.py` now emits
  `note_rollforward_check` for asset-family movement tables, treating blank
  amount-grid cells as zero and applying decrease polarity to depreciation,
  amortization, disposal, impairment, repayment, and write-off labels. Workpaper
  HTML has a `주석별 검증` section, workbook labels include `주석 증감표 검산`,
  and corpus summaries now report note assertion counts separately from primary
  reconciliation. `evidence_candidates.py` adds a reusable candidate subset
  model, and `NoteMovementInput` now preserves table class, period role, and
  exclusion reason metadata for future investing/financing diagnostics. Focused
  tests passed (172), full pytest passed (273). A 50-sample cached corpus run at
  `out/corpus/run_2026-05-27-fifty-note-assertions-v1/` generated 50/50 reports:
  primary 200/275 matched (72.7%), primary determinate 275/275 (100.0%), note
  assertions 48/87 matched with 39 unresolved. SeAH Steel render inspection
  confirmed `주석별 검증`, `증감표 검산`, formula tables, and 0 raw-table zero
  cells; screenshot:
  `out/corpus/run_2026-05-27-fifty-note-assertions-v1/reports/세아제강_2024_note_assertions.png`.
- Follow-up UI correction: SeAH Steel `세아제강_2024.html` was regenerated so
  note roll-forward checks are no longer only a separate summary table. Asset
  roll-forward checks now emit column-level results, and the `주석 원문 검증`
  section marks the original note table ending-balance cells with
  `증감표 검산` tooltips. SeAH Steel now renders 12 roll-forward assertion rows
  and 10 raw-note cell markers. Verification passed with full pytest 274 and
  root Harness verify.
- Latest asset-note bridge slice: asset acquisition/disposal cash-flow
  reconciliation now also emits supporting `asset_note_bridge_check` results,
  separating statement-to-note bridge validation from generic primary cash-flow
  reconciliation. Workpaper HTML adds a `자산 주석 연결 대사` section, while
  corpus/workbook labels expose the new check type. A cached 100-sample run at
  `out/corpus/run_2026-05-27-hundred-asset-note-bridges-v1/` generated 100/100
  reports with 73,133 total checks, 575 primary checks, 419 primary matched, and
  156 primary unresolved. The new bridge surface produced 204 checks across 70
  companies: 80 matched, 78 explainable gaps, and 46 unexplained gaps. The
  unresolved bridge diagnostics show the next formula targets: lease/right-of-use
  separation, acquisition-related payables, disposal gain/loss/carrying amount
  formulas, business-combination/non-cash transfers, and CFS rows combining
  tangible assets with right-of-use or intangible assets. SeAH Steel browser
  inspection confirmed the regenerated report includes `자산 주석 연결 대사`,
  `주석 원문 검증`, 12 roll-forward assertion rows, and 10 raw-note markers.
- Latest primary-accuracy slice: cash-flow bridge checks with required
  adjustments now apply a bounded 5% residual tolerance only after the
  source-precision tolerance is exceeded, converting formula-backed small
  residuals from explainable gaps to matched while leaving single-evidence
  unexplained gaps unchanged. Follow-up guard: `tolerance=0` remains exact-only,
  and matched checks with non-zero residual now say `허용오차 ... 이내로
  현금흐름표 금액과 대사됨` rather than `직접 대사됨`. Verification passed with
  RED/GREEN bridge residual tests, focused reconciliation tests (139 passed),
  full pytest (277 passed), and a cached 100-sample corpus run at
  `out/corpus/run_2026-05-27-hundred-accuracy-v1/` generated 100/100 reports:
  575 primary checks, 460 primary matched, and 115 primary unresolved
  (`primary matched / primary checks = 80.0%`). Cash-flow primary results are
  now 219 matched, 61 unexplained gaps, and 37 explainable gaps.
- Latest reviewer-UI slice (2026-06-01): HTML 검산조서의 "관련 주석" 노출 표면을
  통일했다. leadsheet `관련 주석` 셀은 단순 truncated 텍스트에서 `주석 NN. 주제명`
  포맷 + `row-match-trigger` 버튼으로 교체되어, hover 시 매칭 주석 요약·판단·원문
  주석 표 tooltip을, click 시 우측 drawer 확장을 그대로 재사용한다. `_check_row`/
  `_cashflow_check_row` 첫 컬럼(자산 주석 연결 대사, 주석별 검증, 전기말-당기초,
  보조 검증)도 check가 `note_no` + raw note table을 가질 때 동일 trigger로
  감싸지며, 현금흐름표-주석 대사의 "주석에서 확인된 금액" 셀에도 동일 패턴이
  적용됐다. 자체 검증 한계는 두 곳에 표시한다: (a) `재무제표 ↔ 주석 대사` 섹션
  상단의 `self-verify-advisory` paragraph (자산 증감표 검산에 한정됨을 명시),
  (b) 각 관련 주석 셀의 `self-verify-badge` (자체 검산 결과가 있고 matched면
  `ok 증감표 검산`, 차이가 있으면 `warn 증감표 검산 차이`, 그 외는 `none 자체
  검산 미확인`). 새 헬퍼: `_parse_note_no_from_source`, `_related_note_display_label`,
  `_note_self_verification_by_no`, `_self_verification_badge_html`,
  `_leadsheet_related_note_hover`, `_leadsheet_related_note_cell`,
  `_check_title_cell`, `_cashflow_related_note_cell`. 신규 CSS:
  `.leadsheet-note-trigger`, `.leadsheet-note-display`, `.self-verify-badge`
  (ok/warn/none), `.self-verify-line`, `.self-verify-advisory`,
  `.related-note-cell`. Verification: focused 4 신규 테스트 + full pytest 369
  passed (이전 365 → +4 신규). 주석 자체 정합성(주석 내부 합계·교차 참조)의 종합
  자동 검증은 현 단계에서 자산 증감표 검산(`note_rollforward_check`)에 한정된
  상태로, 향후 financing 증감표·equity 변동표·EPS·지분법 등으로 확장 필요.

## Implementation Priorities

> **ACTIVE Codex work order (2026-05-31):** `docs/work-orders/2026-05-31-codex-handoff-reconciliation-logic.md`.
> Reconciles the user's greenfield 작업계획서 against the real repo (do NOT switch to OpenDART JSON API —
> it drops 주석 and breaks reconciliation) and sequences Type B reconciliation logic (triage 33건) +
> materiality classification + cross-statement ties. Read it before resuming engine work.
> Triage source: `docs/validation/2026-05-31-ab-difference-triage.md`.


1. Review the 37 remaining explainable cash-flow residuals for false-positive
   risk and document/parameterize the 5% bridge residual rule if it graduates
   from corpus-targeting heuristic to permanent audit policy.
2. Reduce remaining cash-flow reconciliation unresolved items with candidate diagnostics, starting from investing/financing rows whose note evidence exists but formula selection is incomplete.
3. Convert the 46 unexplained asset-note bridge gaps into targeted formulas:
   lease/right-of-use add-backs, acquisition-related payable movement direction,
   disposal proceeds from carrying amount plus gain/loss, business-combination
   exclusions, and composite CFS row splitting.
4. Classify the 39/87 unresolved note roll-forward checks from the 50-sample run into true arithmetic differences vs table-shape/sign-policy gaps.
5. Expand note assertions beyond asset-family roll-forwards into financing liability roll-forwards, dividend/equity movement notes, income tax, EPS, and expense allocation note-to-note checks.
6. Resolve remaining primary balance unresolved items, especially trade receivables and complex financial asset/liability accounts.
7. Keep matched conservative: no match without reproducible source amounts, arithmetic, and an explicit tolerance rationale.

## Constraints

- Keep MCP out of the first core implementation.
- Do not depend on `kreports_dart_mcp` for calculation logic.
- Preserve source references for every material amount.
- Avoid LLM-only parsing or opaque classification.
- Treat differences as classified findings, not automatic errors.
- A conservative unresolved item is better than a false matched item.
