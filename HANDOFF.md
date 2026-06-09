# Handoff

## ▶ Latest Handoff (2026-06-07) — 주석 탭 내 검증 표면화 [Codex 인수]

**Plan:** [`plans/2026-06-07-note-tab-verification.md`](plans/2026-06-07-note-tab-verification.md)
**ADR:** [`docs/adr/0004-note-tab-verification-surfacing.md`](docs/adr/0004-note-tab-verification-surfacing.md)

**한 줄 목표:** 주석 번호별 탭 안에서 BS/IS/SCE/CF·다른 주석과의 대사(합계검증·전기대사 포함)를 실제로 채워 보여준다.

**진단(완료):** 탭/패널 레이아웃은 이미 존재하나 패널이 비어 있음. 근본 원인 — `check_fs_note_matches`(note↔BS/PL)·`check_cfs_note_matches`(note↔CF)가 구현·단위테스트 통과하지만 **어떤 runner도 호출하지 않는 dead code**. inveni 즉석 호출 시 fs_note 9건·cfs_note 3건 생성 확인 → 배선만 해도 채워짐. 추가로 기간 컬럼 정렬(과다 gap), 전기대사(동일 파일 전기 컬럼), note↔note, 원문 덤프 가독성.

**리뷰 상태:** `/plan-eng-review`(Opus, P0 매칭무결성·P2 DRY 수정) + Codex read-only 플랜 도전(코드 그라운딩 7건) 완료. 모든 차이를 plan·ADR-0004에 머지함. **Codex는 시작 전 plan의 "Codex 플랜 도전 반영" 섹션(7개 제약)을 먼저 읽을 것.**

**Codex 작업 순서:** plan의 Task 1(공유 조립부 통합+배선)→8(통합 검증+false-matched 가드). Task 1만으로도 패널이 1차 채워지므로 가장 먼저 커밋. 각 Task는 TDD(red→green→commit). 입력은 plan·ADR-0004·CONTEXT.md.

**검증 기준선(inveni):** total 790 check, `fs_note_match`/`cfs_note_match` 0, 패널 "연결된 자동 검증 결과가 없습니다" 523회, "재무제표 원문 근거" 13회. 목표: 후자 증가·전자 감소.

**유의:** 배선 지점 2곳(`corpus._run_checks`, `cli._run_workpaper_checks`)이 중복이니 둘 다 수정. 단일 파일 경로 `foot_local_report`→`scan_html`은 footing 전용이라 무관.

---

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
- 2026-06-08 baseline (run_2026-06-08-statement-ties-baseline):
  total_checks: 70776, matched: 35583, statement_bs_equation: 95 (matched: 95 / gap: 0),
  statement_cash_tie: 61 (matched: 58 / gap: 3), statement_equity_tie: 82 (matched: 0 / gap: 82),
  fs_note_match: 758 (matched: 66 / gap: 692), cfs_note_match: 161 (matched: 7 / gap: 151 / explainable: 3);
  primary_checks: 531, primary_matched: 375 (70.6%), primary_unresolved: 156;
  parse_uncertain: 28949, unexplained_gap: 5458, failed_samples: 0
- Latest implementation slice: layout-aware target extraction now detects note
  table orientation (`row_oriented`, `column_oriented`, `period_oriented`,
  `mixed`, `unknown`), normalizes extracted verification candidates with raw
  amount, display-unit multiplier, row/column source coordinates, layout
  evidence, and orientation evidence, and generates source-backed roll-forward
  formula candidates from trusted evidence only. The new
  `dart-footing candidate-report` command shows one-company diagnostic counts
  for orientations, layouts, extracted candidates, and generated formulas.
  Unknown or low-confidence layouts do not produce matched formula evidence.
  Materiality remains outside pass/fail matching. Verification passed with full
  `uv run pytest` (395 passed).
- Latest implementation slice: unknown layout taxonomy now separates all
  unknown/low-confidence note tables into validation-relevant candidates versus
  general non-validation note tables. The multi-company corpus writes the
  counts to `corpus_result.json`, `corpus_report.md`, and
  `unknown_layout_taxonomy.json/md`, with relevance buckets from the reusable
  `validation_relevance.py` classifier for balance reconciliation, asset
  roll-forward, expense allocation, and cash-flow bridge candidates.
  `dart-footing candidate-report` now uses the same classifier to show, for a
  single company, how many unknown/low-confidence note tables are likely
  validation candidates before formula extraction can trust them. A no-fetch
  100-company corpus run at
  `out/corpus/run_2026-06-04-relevance-taxonomy` generated 100/100 reports:
  primary checks 243, matched 190, unresolved 53; total note tables 40,842;
  unknown/low-confidence layout items 39,957; validation-relevant unknown
  layout items 9,949 (`balance_reconciliation_candidate` 5,214,
  `asset_rollforward_candidate` 3,372, `expense_allocation_candidate` 719,
  `cashflow_bridge_candidate` 644). This did not increase matched primary
  checks yet; it makes the company-format backlog measurable and directly
  consumable by future validation logic. A real INVENI `candidate-report`
  diagnostic shows 366 note tables, 101 validation-relevant unknown/low
  confidence candidates, and 34 extracted verification candidates. Verification
  passed with full `uv run pytest` (400 passed).
- Latest implementation slice: asset measure summary layouts are now recognized
  when asset-topic rows such as `투자부동산`, `유형자산`, `무형자산`, or
  `사용권자산` sit under columns such as `총장부금액`,
  `감가상각누계액 및 상각누계액`, and `장부금액 합계`. These tables are
  classified as `asset_measure_summary`, and column-oriented extraction emits a
  source-backed `ending` verification candidate from the carrying-amount
  column. This moves a common company-format variant out of the unknown layout
  backlog without company-name branching. Verification passed with full
  `uv run pytest` (402 passed). A real INVENI `candidate-report` diagnostic
  improved from 101 to 95 validation-relevant unknown/low-confidence candidates,
  from 34 to 47 extracted verification candidates, and from 6 to 8 formula
  diagnostics. A no-fetch 100-company corpus run at
  `out/corpus/run_2026-06-05-asset-measure-summary` generated 100/100 reports:
  primary checks 243, matched 190, unresolved 53; known layout tables increased
  from 1,052 to 1,404; unknown layout tables decreased from 39,790 to 39,438;
  validation-relevant unknown layout items decreased from 9,949 to 9,625; and
  asset roll-forward unknown candidates decreased from 3,372 to 3,048.
- Latest implementation slice: validation relevance classification now trims
  noisy asset roll-forward candidates before layout work is prioritized.
  Functional depreciation/amortization tables with headers such as `매출원가`,
  `판매비와 일반관리비`, or `기능별 항목 합계` are classified as
  `expense_allocation_candidate`, while disclosure-only asset tables such as
  purchase commitments (`약정액`, `공시금액`) and collateral tables
  (`담보제공자산`, `담보설정금액`) are kept as
  `non_validation_note_table`. This keeps all note tables visible but prevents
  non-roll-forward disclosures from crowding the asset layout backlog.
  Verification passed with full `uv run pytest` (405 passed). A no-fetch
  100-company corpus run at `out/corpus/run_2026-06-05-relevance-noise-trim`
  generated 100/100 reports and kept primary checks 243, matched 190,
  unresolved 53. The total unknown/low-confidence layout items stayed 39,611,
  but validation-relevant unknown layout items decreased from 9,625 to 7,676;
  `asset_rollforward_candidate` decreased from 3,048 to 1,703;
  `expense_allocation_candidate` increased from 719 to 895 as depreciation
  allocation tables moved to the right bucket; `balance_reconciliation_candidate`
  decreased from 5,214 to 4,480; and `non_validation_note_table` increased from
  29,986 to 31,935.
- Latest implementation slice: mixed asset movement-column layouts are now
  recognized and extracted. Tables with asset-topic rows and movement columns
  such as `기초`, `처분`, `감가상각`, and `기말` are classified as
  `asset_movement_columns`; when orientation is `mixed`, extraction reads only
  the asset total row and emits source-backed movement candidates by column.
  This covers the common shape where movement roles are column headers and
  asset classes are row labels, without duplicating individual asset-class rows.
  Verification passed with full `uv run pytest` (408 passed). A real INVENI
  `candidate-report` diagnostic now shows `asset_movement_columns: 2`,
  validation-relevant unknown/low-confidence candidates down from 95 to 75,
  extracted verification candidates up from 47 to 55, and formula diagnostics
  up from 8 to 10. A no-fetch 100-company corpus run at
  `out/corpus/run_2026-06-05-asset-movement-columns` generated 100/100 reports:
  primary checks 243, matched 190, unresolved 53; known layout tables increased
  from 1,404 to 1,708; unknown layout tables decreased from 39,438 to 39,134;
  validation-relevant unknown layout items decreased from 7,676 to 7,401; and
  asset roll-forward unknown candidates decreased from 1,703 to 1,436. Remaining
  high-priority asset cases include `asset_movement_columns` tables whose
  orientation is still `unknown` because headers contain embedded movement words
  like `기초 유형자산` or `기초금액`.
- Latest implementation slice: orientation detection now handles embedded asset
  movement headers such as `기초 유형자산`, `기말 유형자산`, `기초 영업권
  이외의 무형자산`, and similar movement-plus-account labels when asset rows
  are present and at least one substantive asset-change header exists. The guard
  deliberately avoids treating tax temporary-difference tables with only
  `기초/증감/기말` and asset row labels as asset roll-forwards. Candidate role
  mapping now treats `제거` as a disposal role. Verification passed with full
  `uv run pytest` (411 passed). A no-fetch 100-company corpus run at
  `out/corpus/run_2026-06-05-embedded-movement-orientation` generated 100/100
  reports and kept primary checks 243, matched 190, unresolved 53. Known layout
  tables stayed 1,708, but unknown/low-confidence layout items decreased from
  39,334 to 39,318; validation-relevant unknown layout items decreased from
  7,401 to 7,385; and asset roll-forward unknown candidates decreased from
  1,436 to 1,420.
- Latest implementation slice: row-oriented right-of-use asset movement tables
  in lease notes are now classified and extracted. Tables whose row labels
  include `기초 사용권자산`, `취득`, `종료`, `리스변경`, `감가상각비`, and
  `기말 사용권자산`, with headers such as `자산 합계`, are classified as
  `asset_row_movement_total`; existing row-oriented extraction then emits
  source-backed movement candidates. Candidate role mapping now treats `종료`
  as disposal and `리스변경`, `매각예정`, `연결범위`, and `기타변동` as
  transfer-style movements. Verification passed with full `uv run pytest` (413
  passed). A real INVENI `candidate-report` diagnostic now shows
  `asset_row_movement_total: 2`, validation-relevant unknown/low-confidence
  candidates down from 75 to 73, extracted verification candidates up from 55
  to 78, and formula diagnostics up from 10 to 12. A no-fetch 100-company
  corpus run at `out/corpus/run_2026-06-05-rou-row-movement` generated 100/100
  reports and kept primary checks 243, matched 190, unresolved 53. Known layout
  tables increased from 1,708 to 1,773; unknown layout tables decreased from
  39,134 to 39,069; validation-relevant unknown layout items decreased from
  7,385 to 7,322; and asset roll-forward unknown candidates decreased from
  1,420 to 1,371.
- Latest implementation slice: validation relevance classification now removes
  additional disclosure/policy noise from the asset roll-forward backlog.
  Tables under related-party disclosures (`특수관계자`), accounting policy useful
  life/amortization method schedules (`추정내용연수`, `상각방법`), and
  investment-property restriction or remittance disclosures (`실현가능성`,
  `임대수익과 처분대금`, `송금`, `제약`) are classified as
  `non_validation_note_table` even when they contain asset words. This keeps the
  corpus-wide unknown inventory complete while preventing policy and disclosure
  tables from being prioritized as formula-layout work. Verification passed with
  full `uv run pytest` (416 passed). A no-fetch 100-company corpus run at
  `out/corpus/run_2026-06-05-relevance-disclosure-trim` generated 100/100
  reports and kept primary checks 243, matched 190, unresolved 53.
  Validation-relevant unknown layout items decreased from 7,322 to 6,987;
  `asset_rollforward_candidate` decreased from 1,371 to 1,252;
  `balance_reconciliation_candidate` decreased from 4,472 to 4,268; and
  `non_validation_note_table` increased from 31,931 to 32,266.
- Latest implementation slice: reconciliation input extraction now preserves
  layout and orientation metadata on `NoteBalanceInput` and `NoteMovementInput`
  without changing the existing source coordinate contract. This connects the
  layout-aware candidate layer to the existing balance and cash-flow
  reconciliation surface while keeping the current checks behaviorally stable;
  stricter matched-result gating remains concentrated in the trusted
  `VerificationFormula` path until broader corpus remapping is added.
  Verification passed with full `uv run pytest` (396 passed).
- Latest implementation slice: full-note layout coverage foundation now scans
  every note table in a company report, classifies known versus unknown table
  layouts without company-name branching, and reports all-note coverage counts
  through `dart-footing coverage-report`. This is a coverage and
  backlog-management layer only and is also aggregated into multi-company
  workpaper corpus summaries. Materiality is not used as a pass/fail criterion,
  and existing footing and cash-flow reconciliation checks remain separate.
  Verification passed with full `uv run pytest` (383 passed).
- Latest implementation slice: footing parser evidence now carries HTML source
  line numbers from parsed table cells into `FootingEvidence.line`, while
  retaining the existing deterministic local coordinate string in
  `FootingEvidence.source`. This bridges parser-level source locations into the
  footing result model without changing the current `table:{index} row:{row}
  col:{col}` source contract. Verification passed with full `uv run pytest`
  (374 passed).
- Latest implementation slice: reconciliation expense-allocation coverage now
  excludes research-function labels such as `연구비` from the comparable
  functional allocation basis when that exclusion reconciles the asset
  amortization/depreciation allocation to the expense-by-nature amount. This
  generalizes the existing development-cost exclusion without changing matched
  corpus metrics. Verification passed with full `uv run pytest` (376 passed)
  and a no-fetch 100-company corpus run at
  `out/corpus/run_2026-06-03-reconciliation-coverage-rd`: generated 100/100
  reports, primary checks 243, matched 190, unresolved 53, with 0 newly
  unresolved primary IDs and 0 resolved primary IDs versus
  `run_2026-06-01-codex-243-baseline-remap-default`.
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
- Latest full-note layout slice (2026-06-05): 회사별 전체 주석 표를 계속 보면서
  엘앤에프 `무형자산`에서 확인한 stacked 장부금액 요약 표를 일반 레이아웃으로
  승격했다. 새 layout key는 `asset_stacked_measure_summary`이며, 자산명이 헤더에
  있고 행에 `장부금액`/`장부금액 합계`가 반복되는 표를 mixed orientation으로
  감지한 뒤 `장부금액 합계` 교차 셀을 unit-normalized ending 후보로 추출한다.
  엘앤에프 실제 파일 기준 `candidate-report`는 `asset_stacked_measure_summary: 4`,
  `verification_candidates: 10`, `validation_relevant_unknown_layout_items: 99`를
  기록했다. 100-company no-fetch corpus
  `out/corpus/run_2026-06-05-asset-stacked-measure-summary/`는 100/100 reports,
  primary 243/190/53 유지, known layout tables 1,803, validation-relevant unknown
  layout items 6,943로 마감했다. Verification: focused RED/GREEN 3 tests, related
  layout/orientation/candidate tests 24 passed, full pytest 419 passed.
- Latest balance-layout slice (2026-06-05): balance reconciliation backlog의
  상단 표본인 INVENI 금융상품/매출채권 주석을 회사명 분기 없이 일반화했다.
  `financial_instrument_category_summary`는 계정 행 + 금융상품 범주 열 +
  `범주 합계` 열 구조에서 계정별 ending 후보를 추출하고,
  `receivable_carrying_amount_summary`는 `총장부금액`/`손상차손누계액`/
  `장부금액 합계` 열 구조에서 매출채권·미수금·대여금 ending 후보를 추출한다.
  INVENI 실제 `candidate-report`는 `financial_instrument_category_summary: 8`,
  `receivable_carrying_amount_summary: 4`, `verification_candidates: 112`,
  `validation_relevant_unknown_layout_items: 53`을 기록했다. 100-company
  no-fetch corpus `out/corpus/run_2026-06-05-receivable-carrying-summary/`는
  100/100 reports, primary 243/190/53 유지, known layout tables 2,383,
  validation-relevant unknown layout items 6,575, balance reconciliation unknown
  candidates 3,900로 마감했다. Verification: focused RED/GREEN 5 tests, related
  layout/orientation/candidate tests 29 passed, full pytest 424 passed.
- Latest receivable-detail slice (2026-06-05): INVENI `매출채권 및 기타채권`
  주석의 남은 상단 backlog 두 종류를 추가 일반화했다.
  `loss_allowance_rollforward`는 두 번째 행의 계정 헤더(`매출채권`, `미수금`)
  아래 `기초 손실충당금`/`기대신용손실`/`환입액`/`제각`/`기말 손실충당금`
  행을 source-backed signed roll-forward 후보로 추출하고, `signed_movement`
  role을 `beginning + signed movements = ending` 산식으로 검증한다.
  `receivable_aging_status_summary`는 연체상태 표의 `연체상태 합계` 행을
  계정별 ending 후보로 추출한다. INVENI 실제 `candidate-report`는
  `loss_allowance_rollforward: 4`, `receivable_aging_status_summary: 4`,
  `verification_candidates: 164`, `matched_formulas: 2`,
  `validation_relevant_unknown_layout_items: 45`를 기록했다. 100-company
  no-fetch corpus `out/corpus/run_2026-06-05-receivable-aging-summary/`는
  100/100 reports, primary 243/190/53 유지, known layout tables 2,391,
  validation-relevant unknown layout items 6,567, balance reconciliation unknown
  candidates 3,892로 마감했다. Verification: focused RED/GREEN 7 tests, related
  layout/orientation/candidate/formula tests 39 passed, full pytest 431 passed.
- Latest inventory-layout slice (2026-06-05): top balance backlog로 올라온
  `재고자산` 단일열 총장부금액 표를 `inventory_carrying_amount_summary`로
  일반화했다. `재고자산` 제목/행, `총장부금액` 또는 carrying-amount total 열,
  `합계`/`총계` 행을 요구하며, 합계 행 금액을 `inventories` ending 후보로
  source row/column 및 unit multiplier와 함께 추출한다. INVENI 실제
  `candidate-report`는 `inventory_carrying_amount_summary: 2`,
  `verification_candidates: 166`, `validation_relevant_unknown_layout_items: 43`을
  기록했다. 100-company no-fetch corpus
  `out/corpus/run_2026-06-05-inventory-carrying-summary/`는 100/100 reports,
  primary 243/190/53 유지, known layout tables 2,465, validation-relevant unknown
  layout items 6,491, balance reconciliation unknown candidates 3,816으로
  마감했다. Verification: focused RED/GREEN 3 tests, related
  layout/orientation/candidate/formula tests 42 passed, full pytest 434 passed.
- Latest functional-expense-layout slice (2026-06-05): top expense allocation
  backlog로 올라온 `유형자산`/`무형자산` 기능별 감가상각비·상각비 배부 표를
  기존 `functional_expense_allocation` layout으로 일반화했다. 표 제목이
  `비용`을 포함하지 않아도 headers에 `매출원가`, `판매비와 일반관리비`,
  `기능별 항목 합계`가 있고 rows에 `감가상각비`/`무형자산상각비`가 있으면
  column-oriented functional allocation으로 감지하며, `기능별 항목 합계` 열을
  `expense_allocation_total` 후보로 추출한다. INVENI 실제 `candidate-report`는
  `functional_expense_allocation: 4`, `verification_candidates: 170`,
  `validation_relevant_unknown_layout_items: 39`를 기록했다. 100-company no-fetch
  corpus `out/corpus/run_2026-06-05-functional-expense-allocation/`는 100/100
  reports, primary 243/190/53 유지, known layout tables 2,518,
  validation-relevant unknown layout items 6,309, expense allocation unknown
  candidates 687로 마감했다. Verification: focused RED/GREEN 3 tests, related
  layout/orientation/candidate/formula tests 45 passed, full pytest 437 passed.
- Latest asset-component-net slice (2026-06-05): top balance backlog로 남은
  `투자부동산`/`무형자산` 취득원가·누계액 요약 표를
  `asset_cost_accumulated_summary`로 일반화했다. 장부금액 열이 없는
  INVENI 투자부동산 표는 합계 행의 `gross_cost`와
  `accumulated_depreciation` 후보를 source row/column 및 unit multiplier와
  함께 보존하고, 아남전자 무형자산 표처럼 `손상차손누계액` 및 `기말` 열이
  있는 경우 component-net 산식으로 검증한다: gross_cost +
  accumulated_depreciation + accumulated_impairment = ending. 100-company 직접 집계에서
  이 layout은 INVENI 2개 표(note 14 tables 68/69)와 아남전자 2개 표(note 7
  tables 108/109)에 발생했다. INVENI 실제 `candidate-report`는
  `asset_cost_accumulated_summary: 2`, `verification_candidates: 174`,
  `validation_relevant_unknown_layout_items: 37`을 기록했고, 아남전자 실제
  `candidate-report`는 `asset_cost_accumulated_summary: 2`,
  `verification_candidates: 47`, `matched_formulas: 4`를 기록했다.
  100-company no-fetch corpus
  `out/corpus/run_2026-06-05-asset-component-net-summary/`는 100/100 reports,
  primary 243/190/53 유지, known layout tables 2,522,
  validation-relevant unknown layout items 6,305로 마감했다. 현재 corpus
  primary summary에는 `component_net` table formula가 별도 primary 대사로
  승격되지는 않았고, `candidate-report` formula diagnostics 단계에서 먼저
  검증된다. Verification: focused RED/GREEN 5 tests, related
  layout/orientation/candidate/formula/CLI/package tests 60 passed, full pytest
  442 passed.
- Latest debt-instrument-layout slice (2026-06-05): top balance backlog였던
  `차입금 및 사채` 세부 표를 `debt_instrument_detail_summary`로 일반화했다.
  `차입금명칭` 반복 헤더와 `차입금`/`명목금액`/`사채할인발행차금`/`소계`/
  `1년이내 만기도래분`/`비유동성 차입금`/`합계` 행을 row-oriented debt
  detail로 감지한다. 장기차입금 표는 `debt_total + current_portion = ending`
  debt split 산식으로, 사채 표는 `face_amount + debt_discount = debt_total`
  검증 후 `debt_total + current_portion = ending`으로 닫는다. INVENI 실제
  `candidate-report`는 `debt_instrument_detail_summary: 4`,
  `verification_candidates: 190`, `verification_formulas: 14`,
  `matched_formulas: 6`, `validation_relevant_unknown_layout_items: 33`을
  기록했다. 100-company 직접 집계에서 이 layout은 40개 회사 268개 표에
  발생했다. 100-company no-fetch corpus
  `out/corpus/run_2026-06-05-debt-instrument-detail-summary/`는 100/100 reports,
  primary 243/190/53 유지, known layout tables 2,790,
  validation-relevant unknown layout items 6,035, balance reconciliation unknown
  candidates 3,550로 마감했다. 현재 다음 taxonomy 상단은 INVENI `충당부채`
  roll-forward, `판매비와 관리비` 단일 금액표, `영업으로부터 창출된 현금`
  순부채 bridge 표다. Verification: focused RED/GREEN 9 tests, related
  layout/orientation/candidate/formula/CLI/package tests 67 passed, full pytest
  450 passed.
- Latest provision-rollforward slice (2026-06-05): top balance backlog로
  올라온 `충당부채` 변동 표를 `provision_rollforward`로 일반화했다. `기초`,
  `전입`, `연중 사용액`, `연결범위변동`, `매각예정분류`, `기말` 헤더와
  충당부채 계정 행을 mixed orientation으로 감지하며, 값 자체의 부호를 보존해
  `beginning + signed_movement = ending` 산식으로 검증한다. INVENI 실제
  `candidate-report`는 `provision_rollforward: 2`, `verification_candidates: 202`,
  `verification_formulas: 16`, `matched_formulas: 8`,
  `validation_relevant_unknown_layout_items: 31`을 기록했다. 100-company 직접
  집계에서 이 layout은 5개 회사 20개 표에 발생했다. 100-company no-fetch
  corpus `out/corpus/run_2026-06-05-provision-rollforward/`는 100/100 reports,
  primary 243/190/53 유지, known layout tables 2,810,
  validation-relevant unknown layout items 6,015, balance reconciliation unknown
  candidates 3,530로 마감했다. 현재 다음 taxonomy 상단은 `판매비와 관리비`
  단일 금액표와 `영업으로부터 창출된 현금` 순부채 bridge 표다. Verification:
  focused RED/GREEN 3 tests, related layout/orientation/candidate/formula/CLI/package
  tests 71 passed, full pytest 453 passed.
- Latest selling-admin-expense slice (2026-06-05): top expense allocation
  backlog로 올라온 `판매비와 관리비` 단일 금액표를
  `selling_admin_expense_summary`로 일반화했다. `금액` 열과 판관비 비용 항목,
  `합계` 행을 column-oriented expense summary로 감지하고, 각 비용 항목을
  `expense_component`, 합계 행을 `expense_total` 후보로 추출한다. 후보 진단은
  `expense_summary_total` 산식으로 구성요소 합계가 총액과 일치하는지 검증한다.
  INVENI 실제 `candidate-report`는 `selling_admin_expense_summary: 2`,
  `verification_candidates: 234`, `verification_formulas: 18`,
  `matched_formulas: 10`, `validation_relevant_unknown_layout_items: 29`를
  기록했다. 100-company 직접 집계에서 이 layout은 6개 회사 16개 표에
  발생했다. 100-company no-fetch corpus
  `out/corpus/run_2026-06-05-selling-admin-expense-summary/`는 100/100 reports,
  primary 243/190/53 유지, known layout tables 2,826,
  validation-relevant unknown layout items 6,013, expense allocation unknown
  candidates 685로 마감했다. 현재 다음 taxonomy 상단은 `영업으로부터 창출된
  현금` 순부채 bridge 표와 `재무위험관리` 신용위험/만기분석 표다. Verification:
  focused RED/GREEN 6 tests, related layout/orientation/candidate/formula/CLI/package
  tests 76 passed, full pytest 458 passed.
- Latest net-debt-bridge slice (2026-06-05): top cashflow bridge backlog였던
  `영업으로부터 창출된 현금`의 `재무활동에서 생기는 부채의 조정` 표를
  `net_debt_bridge`로 일반화했다. `기초 순부채`/`현금흐름`/`기말 순부채`
  행과 `사채`/`차입금`/`리스부채` 계정 열을 mixed orientation으로 감지하고,
  하나의 표 안에서 각 부채 계정 열을 별도 signed roll-forward로 분해한다.
  후보는 `current_bonds`, `noncurrent_bonds`, `lease_liabilities`,
  `short_term_borrowings`, `current_long_term_borrowings`,
  `long_term_borrowings` 같은 계정별 `beginning`/`signed_movement`/`ending`
  금액으로 source row/column 및 unit multiplier를 보존한다. INVENI 실제
  `candidate-report`는 `net_debt_bridge: 4`, `verification_candidates: 352`,
  `verification_formulas: 33`, `matched_formulas: 26`,
  `validation_relevant_unknown_layout_items: 63`을 기록했고, 순부채 브릿지만
  따로 분해하면 4개 표, 후보 71개, 공식 15개가 모두 matched였다.
  원천 DART 기준 100-company corpus
  `out/corpus/run_2026-06-05-net-debt-bridge/`는 100/100 reports, primary
  243/190/53 유지, known layout tables 2,830,
  validation-relevant unknown layout items 6,009, cashflow bridge unknown
  candidates 590로 마감했다. 직전 SG&A 슬라이스 대비 known layout은 4개
  증가했고 validation-relevant unknown은 4개 감소했다. 현재 이 산식은
  `candidate-report` formula diagnostics 단계이며, 이후 보고서 검증 로직에는
  재무활동 현금흐름 행과 주석 내 계정별 signed movement를 연결하는
  reconciliation input으로 승격해야 한다. 다음 taxonomy 상단은 INVENI
  `재무위험관리` 신용위험/만기분석 표다. Verification: focused RED/GREEN 5
  tests, related layout/orientation/candidate/formula/CLI/package tests 81 passed,
  full pytest 463 passed.
- Latest credit-risk-exposure slice (2026-06-05): top balance backlog였던
  INVENI `재무위험관리`의 `신용위험 익스포저에 대한 공시` 단일 금액열 표를
  `credit_risk_exposure_summary`로 일반화했다. 단독 `신용위험` 금액 열,
  금융자산 행, `합계` 행을 column-oriented로 감지하고, 각 금융자산을
  `credit_exposure_component`, 합계 행을 `credit_exposure_total` 후보로
  추출한다. 산식은 `credit_risk_exposure_total`로 구성요소 합계가 총액과
  정확히 일치하는지 검증한다. INVENI 원천 파일 기준 이 layout은 연결/별도
  주석의 당기/전기 4개 표에서 발생했으며, 후보 42개와 공식 4개가 모두
  matched였다. 다만 100-company corpus에서는 담보에 의한 신용위험 경감효과
  ECL bucket 표가 `신용위험` 문구를 포함해 과분류될 수 있음을 발견해,
  단독 `신용위험` 금액 열과 `익스포저` 문맥으로 조건을 좁혔다. 최종
  100-company source corpus
  `out/corpus/run_2026-06-05-credit-risk-exposure-summary-v2/`는 100/100 reports,
  primary 243/190/53 유지, known layout tables 2,832,
  validation-relevant unknown layout items 6,008, balance reconciliation unknown
  candidates 3,529로 마감했다. 직접 원천 재분석 기준으로 신용위험 익스포저
  산식 검증에 승격된 것은 INVENI 1개 회사 2개 표, 후보 21개, 공식 2개,
  모두 matched였다. 다음 taxonomy 상단은 INVENI `재무위험관리` 만기분석 표다.
  Verification: focused RED/GREEN 8 tests including 대신증권 ECL overmatch guard,
  related layout/orientation/candidate/formula/CLI/package tests 88 passed, full
  pytest 470 passed.
- Latest liquidity-maturity-analysis slice (2026-06-05): top cashflow/balance
  backlog였던 `재무위험관리` 유동성위험 만기분석 표를
  `liquidity_maturity_analysis`로 일반화했다. `3개월 이내`,
  `3개월 초과 1년 이내`, `1년 초과 2년 이내`, `2년 초과` 같은 기간 bucket
  열과 `합계 구간 합계` 열, 금융부채 행을 column-oriented로 감지하고, 각
  행을 독립 검증 단위로 `maturity_component`/`maturity_total` 후보로
  추출한다. 같은 account key가 여러 행에 반복되는 회사가 있어 공식 그룹은
  `table_source + row_index + account_key` 기준으로 묶었다. INVENI 원천 기준
  연결/별도, 당기/전기 4개 표에서 후보 110개, 공식 22개가 모두 matched였다.
  100-company source corpus
  `out/corpus/run_2026-06-05-liquidity-maturity-analysis/`는 100/100 reports,
  primary 243/190/53 유지, known layout tables 3,072,
  validation-relevant unknown layout items 5,846, cashflow bridge unknown
  candidates 548, balance reconciliation unknown candidates 3,409로 마감했다.
  직접 원천 재분석 기준 이 layout은 62개 회사 238개 표에 발생했고, 후보
  4,057개, 행별 공식 1,158개를 생성했다. 공식 상태는 matched 887,
  unexplained_gap 271, parse_uncertain 0이다. unexplained_gap은 산식이 닫히지
  않는 행을 보수적으로 남기는 진단이며 matched로 승격하지 않는다. 다음
  taxonomy 상단은 INVENI `리스` 비용 관련 표와 중단영업 손익표다. Verification:
  focused RED/GREEN 8 tests including 전기 반복표 and accrued payable rows,
  related layout/orientation/candidate/formula/CLI/package tests 96 passed, full
  pytest 478 passed.
- Latest lease-expense-summary slice (2026-06-05): top expense allocation
  backlog였던 `리스` 주석의 포괄손익계산서 인식 리스 비용 표를
  `lease_expense_summary`로 일반화했다. 3단 stacked header에서 실제 자산 분류
  행(`부동산`, `차량운반구`)과 `자산 합계` 열을 찾아 `감가상각비, 사용권자산`
  행은 `lease_expense_component`/`lease_expense_total` 후보로 추출하고,
  이자비용·단기리스료·소액자산 리스료는 total 후보로만 보존한다. 공식은
  component가 있는 행에만 `lease_expense_total`을 생성하므로 단일 총액 행을
  억지로 matched로 승격하지 않는다. INVENI 원천 기준 연결/별도, 당기/전기
  4개 표에서 후보 24개, 공식 4개가 모두 matched였다. 100-company source
  corpus `out/corpus/run_2026-06-05-lease-expense-summary/`는 100/100 reports,
  primary 243/190/53 유지, known layout tables 3,103,
  validation-relevant unknown layout items 5,815, expense allocation unknown
  candidates 671, asset roll-forward unknown candidates 1,189로 마감했다. 직접
  원천 재분석 기준 이 layout은 9개 회사 31개 표에 발생했고, 후보 195개,
  공식 29개를 생성했으며 공식 29개는 모두 matched였다. 진흥기업 2개 표는
  component row가 없어 후보만 보존하고 공식은 생성하지 않았다. 다음 taxonomy
  상단은 INVENI `중단영업` 손익표 및 중단영업 현금흐름 표다. Verification:
  focused RED/GREEN 5 tests, related layout/orientation/candidate/formula/CLI/package
  tests 101 passed, full pytest 483 passed.
- Latest discontinued-operation slice (2026-06-05): INVENI note 35의
  `매각예정처분자산(부채)집단과 중단영업` 주석에서 손익표 2개와 현금흐름표
  2개를 각각 `discontinued_operation_income_statement`,
  `discontinued_operation_cashflow_summary`로 승격했다. 손익표는 행 레이블 첫
  두 칸을 함께 읽어 중복 `중단영업순이익` 행을
  `net_discontinued_profit`/`parent_attribution`/`noncontrolling_attribution`로
  분리하고, 매출총이익, 영업손익, 세전손익, 세후 중단영업손익, 처분손익 반영
  순이익, 지배/비지배 귀속 합계의 6개 공식을 생성한다. 현금흐름표는
  영업·투자·재무활동 현금흐름 합계 공식을 생성한다. INVENI 실제
  `candidate-report`는 `discontinued_operation_income_statement: 2`,
  `discontinued_operation_cashflow_summary: 2`, `verification_candidates: 598`,
  `verification_formulas: 78`, `matched_formulas: 70`을 기록했다. 직접 100사
  원천 재분석 기준 해당 layout은 1개 회사 / 4개 표에 발생했고 후보 40개,
  공식 14개를 생성했으며 모두 matched였다. 100-company no-fetch corpus
  `out/corpus/run_2026-06-05-discontinued-operation-income-and-cashflow/`는
  100/100 reports, primary 243/190/53 유지, known layout tables 3,107,
  validation-relevant unknown layout items 5,811, cashflow bridge unknown
  candidates 546으로 마감했다. 이번 slice는 회사 수는 1개지만, 동일 회사의
  모든 관련 중단영업 주석 표 4개를 source-backed 후보와 산식으로 닫아
  보고서 내부 완전성 검증 레이어에 바로 녹일 수 있는 형태로 만들었다.
  Verification: focused RED/GREEN discontinued-operation tests, related
  layout/orientation/candidate/formula/CLI/package tests 111 passed.
- Latest operating-expense-summary slice (2026-06-05): INVENI note 22
  `영업비용(별도)`의 단일 `금액` 컬럼 비용 명세를
  `operating_expense_summary`로 승격했다. 기존 `판매비와관리비` summary와 달리
  매출원가와 판관비 성격 비용이 한 표에 섞여 있어 account key를
  `operating_expenses`로 별도 보존하고, `expense_component` 합계가
  `expense_total`에 닫히는 기존 expense summary 공식을 재사용한다. INVENI 실제
  `candidate-report`는 `operating_expense_summary: 2`,
  `verification_candidates: 636`, `verification_formulas: 80`,
  `matched_formulas: 72`를 기록했다. 직접 100사 원천 재분석 기준 이 layout은
  1개 회사 / 2개 표에 발생했고 후보 38개, 공식 2개를 생성했으며 모두
  matched였다. 100-company no-fetch corpus
  `out/corpus/run_2026-06-05-operating-expense-summary/`는 100/100 reports,
  primary 243/190/53 유지, known layout tables 3,109,
  validation-relevant unknown layout items 5,809, expense allocation unknown
  candidates 667로 마감했다. 다음 taxonomy 상단에는 INVENI 별도 자산 주석의
  단일행 기능별 배분표와 순확정급여부채 roll-forward가 남아 있다.
  Verification: operating expense RED/GREEN tests, related
  layout/candidate/CLI tests 74 passed.
- Latest functional-expense-single-row-allocation slice (2026-06-05): 자산 주석의
  단일행 기능별 배분표를 `functional_expense_single_row_allocation`으로
  일반화했다. 이 표는 `기능별 항목 / 영업비용 / 감가상각비, 유형자산` 또는
  `무형자산상각비`처럼 구성요소 합산 공식이 없는 구조라 matched formula를
  만들지 않고, `expense_allocation_total` 후보만 source coordinate와
  unit_multiplier로 보존한다. 이 후보는 이후 자산 주석 감가상각/상각 금액과
  영업비용·비용성격 주석 행을 연결하는 note-to-note 검증 레이어에 녹일 수
  있다. INVENI 실제 `candidate-report`는
  `functional_expense_single_row_allocation: 4`, `verification_candidates: 640`,
  `verification_formulas: 80`, `matched_formulas: 72`를 기록했다. 직접 100사
  원천 재분석 기준 이 layout은 15개 회사 / 91개 표에 발생했고 후보 316개를
  생성했다. 100-company no-fetch corpus
  `out/corpus/run_2026-06-05-functional-expense-single-row-allocation/`는
  100/100 reports, primary 243/190/53 유지, known layout tables 3,200,
  validation-relevant unknown layout items 5,718, expense allocation unknown
  candidates 576으로 마감했다. 다음 taxonomy 상단은 순확정급여부채 roll-forward
  및 statement-like note tables다. Verification: focused RED/GREEN
  layout/orientation/candidate/CLI tests 102 passed.
- Latest defined-benefit-rollforward slice (2026-06-05): `순확정급여부채(자산)`
  주석의 확정급여채무/사외적립자산 변동표를
  `defined_benefit_rollforward`로 승격했다. 계정 컬럼
  `확정급여채무의 현재가치`, `사외적립자산`을 각각
  `defined_benefit_obligation`, `plan_assets`로 매핑하고, `기초금액`/`기말금액`
  사이의 실제 금액 행을 signed movement로 추출한다. `재측정요소:`처럼 금액이
  없는 section header는 제외하고, 세부 재측정 행이 있는 표에서는
  `총 재측정손익` 요약 행을 중복 후보로 넣지 않도록 보정했다. 또한 orientation이
  애매한 표가 generic fallback으로 `unknown` account formula를 만들지 않도록
  defined-benefit 전용 추출 경로를 우선 적용했다. 직접 100사 원천 재분석 기준
  이 layout은 71개 회사 / 180개 표에 발생했고 후보 3,411개, 공식 308개를
  생성했다. 공식 상태는 matched 147, unexplained_gap 153, parse_uncertain 8,
  unknown account formula 0이다. INVENI는 4개 표에서 DBO 공식은 matched로
  닫히고 plan asset 쪽은 일부 unexplained_gap으로 남아 실제 보고서 내 산식
  차이를 보수적으로 드러낸다. 100-company no-fetch corpus
  `out/corpus/run_2026-06-05-defined-benefit-rollforward/`는 100/100 reports,
  primary 243/190/53 유지, known layout tables 3,380,
  validation-relevant unknown layout items 5,650, balance reconciliation unknown
  candidates 3,339로 마감했다. Verification: focused RED/GREEN
  layout/orientation/candidate/formula/CLI/package tests 125 passed, full pytest
  507 passed.
- Latest inventory-allowance-rollforward slice (2026-06-05): 한솔케미칼
  `재고자산 평가충당금의 변동내역` 표를
  `inventory_allowance_rollforward`로 승격했다. 단일 금액 컬럼
  `재고자산 평가충당금`을 `inventory_valuation_allowance` 계정으로 고정하고,
  `기초재고자산`/`기말재고자산` 사이의 환입, 평가손실, 폐기, 기타 행을
  signed movement로 추출한다. 직접 100사 원천 재분석 기준 이 layout은
  1개 회사 / 2개 표에 발생했고 후보 12개, signed roll-forward 공식 2개를
  생성했으며 모두 matched였다. 이번 slice는 후보 진단에 그치지 않고
  `note_layout_formula_check`로 workpaper 검증 결과에 승격했다. 100-company
  no-fetch corpus `out/corpus/run_2026-06-05-inventory-allowance-rollforward/`는
  100/100 reports, primary 243/190/53 유지, total checks 63,540 -> 63,542,
  matched 30,273 -> 30,275, note assertion matched 774 -> 776,
  known layout tables 3,380 -> 3,382, validation-relevant unknown layout items
  5,650 -> 5,648, validated tables 11,572 -> 11,574로 마감했다. Verification:
  focused RED/GREEN layout/orientation/candidate/CLI/workpaper-check tests,
  full pytest 512 passed.
- Latest provision-row-rollforward slice (2026-06-05): 한솔케미칼 등에서 확인된
  충당부채 변동표의 반대 방향 구조, 즉 `기초/변동/기말`이 행이고
  복구충당부채·기타장기종업원급여부채·제품보증충당부채·반품충당부채가 열인
  표를 기존 `provision_rollforward` layout에 통합했다. 기존 movement-column
  provision 표와 달리 계정 열별로 후보를 그룹핑해 signed roll-forward 공식을
  독립 검증한다. `기타장기종업원급여부채`처럼 `충당부채` 문자열이 직접 없는
  계정 헤더도 충당부채 주석 컨텍스트 안에서는 provision account로 인식한다.
  직접 100사 원천 재분석 기준 이 layout은 24개 회사 / 82개 표에 발생했고
  후보 1,938개를 생성했다. 공식 상태는 matched 81, unexplained_gap 37,
  parse_uncertain 74로, 맞는 표만 통과시키고 닫히지 않거나 불확실한 표는 그대로
  분리한다. 100-company no-fetch corpus
  `out/corpus/run_2026-06-05-provision-row-rollforward/`는 100/100 reports,
  primary 243/190/53 유지, total checks 63,542 -> 63,741, matched
  30,275 -> 30,356, unexplained_gap 3,759 -> 3,796, parse_uncertain
  28,807 -> 28,888, known layout tables 3,382 -> 3,450,
  validation-relevant unknown layout items 5,648 -> 5,580, validated tables
  11,574 -> 11,600으로 마감했다. Verification: focused RED/GREEN
  layout/orientation/candidate/CLI/workpaper-check tests, full pytest
  517 passed.
- Latest defined-benefit-title-generalization slice (2026-06-05):
  `순확정급여부채(자산)`처럼 제목에 확정급여가 직접 있는 표뿐 아니라,
  `퇴직급여제도`/`종업원급여` 제목 아래 놓인 확정급여채무·사외적립자산
  변동표도 `defined_benefit_rollforward`로 승격했다. 분류 기준은 제목 문자열이
  아니라 계정 헤더(`확정급여채무`, `사외적립자산`)와 기초/기말 행, 그리고
  당기근무원가·순확정급여 등 benefit movement 증거의 결합으로 완화했다.
  또한 defined-benefit signed roll-forward 공식을 `note_layout_formula_check`로
  workpaper 검증 결과에 승격했다. 직접 100사 원천 재분석 기준 이 layout은
  62개 회사 / 230개 표에 발생했고 후보 5,086개를 생성했다. 공식 상태는
  matched 218, unexplained_gap 234, parse_uncertain 8이다. 100-company no-fetch
  corpus `out/corpus/run_2026-06-05-defined-benefit-title-generalization/`는
  100/100 reports, primary 243/190/53 유지, total checks 63,741 -> 64,201,
  matched 30,356 -> 30,574, unexplained_gap 3,796 -> 4,030,
  parse_uncertain 28,888 -> 28,896, known layout tables 3,450 -> 3,536,
  validation-relevant unknown layout items 5,580 -> 5,528, validated tables
  11,600 -> 11,747로 마감했다. Verification: focused RED/GREEN
  layout/CLI/workpaper-check tests, related tests 120 passed, full pytest
  520 passed.
- Latest financing-debt-bridge-generalization slice (2026-06-05):
  `현금흐름표` 제목 아래의 `재무활동에서 생기는 기초/기말 부채` 표를 기존
  `net_debt_bridge` 검증 경로에 통합했다. 기존 `기초 순부채`/`기말 순부채`
  형태뿐 아니라, 단기차입금·장기차입금·사채·리스부채·미지급배당금·임대보증금
  등 금융부채 계정 열과 재무활동 부채 변동 행을 조합해 source-backed
  beginning/signed movement/ending 후보를 추출한다. 유동성장기부채, 미지급배당금,
  임대보증금 계정 key도 추가했고, signed roll-forward 공식은
  `note_layout_formula_check`로 workpaper 검증 결과에 승격했다. 직접 100사 전체
  주석 스캔 기준 이 layout은 29개 회사 / 89개 표에 발생했고 후보 2,414개,
  공식 355개를 생성했다. 공식 상태는 matched 310, unexplained_gap 19,
  parse_uncertain 26이다. 100-company no-fetch corpus
  `out/corpus/run_2026-06-05-financing-debt-bridge/`는 100/100 reports,
  primary 243/190/53 유지, total checks 64,201 -> 64,557, matched
  30,574 -> 30,884, unexplained_gap 4,030 -> 4,049, parse_uncertain
  28,896 -> 28,923, note assertion checks 1,823 -> 2,179, known layout tables
  3,536 -> 3,621, validation-relevant unknown layout items 5,528 -> 5,443,
  validated tables 11,747 -> 11,796로 마감했다. Verification: RED/GREEN
  layout/orientation/candidate/CLI/workpaper-check tests 5 passed, related tests
  140 passed, full pytest 525 passed.
- Latest lease-liability-column-disambiguation refinement (2026-06-05):
  financing debt bridge 안에서 `리스 부채`, `유동성리스부채`,
  `리스 부채(비유동)`이 같은 `lease_liabilities` account key로 합쳐져
  parse_uncertain이 되던 표를 계정 열별로 분리했다. `유동성리스부채`는
  `current_lease_liabilities`, `(비유동)` 리스부채는
  `noncurrent_lease_liabilities`로 매핑하고, 일반 `리스 부채`는 기존
  `lease_liabilities`로 유지한다. 직접 100사 전체 주석 스캔 기준 같은
  29개 회사 / 89개 net debt bridge 표에서 공식 상태가 matched 310 ->
  341, unexplained_gap 19 -> 20, parse_uncertain 26 -> 10으로 개선됐다.
  100-company no-fetch corpus
  `out/corpus/run_2026-06-05-lease-liability-column-disambiguation/`는
  100/100 reports, primary 243/190/53 유지, total checks 64,557 ->
  64,573, matched 30,884 -> 30,915, unexplained_gap 4,049 -> 4,050,
  parse_uncertain 28,923 -> 28,907, note assertion checks 2,179 -> 2,195,
  note assertion matched 1,385 -> 1,416으로 마감했다. Verification:
  RED/GREEN candidate test, related tests 79 passed, full pytest 526 passed.
- Latest bond-column-disambiguation refinement (2026-06-05): financing debt
  bridge 안에서 `사채(유동)`, `사채(비유동)`, `단기사채`, `유동성장기사채`,
  `전환사채 및 교환사채`가 모두 `bonds`로 합쳐져 parse_uncertain이 되던 표를
  계정 열별로 분리했다. 새 account key는 `short_term_bonds`,
  `current_long_term_bonds`, `current_bonds`, `noncurrent_bonds`,
  `convertible_bonds`, `exchangeable_bonds`,
  `convertible_exchangeable_bonds`다. 직접 100사 전체 주석 스캔 기준 같은
  29개 회사 / 89개 net debt bridge 표에서 공식 상태가 matched 341 ->
  356, unexplained_gap 20 유지, parse_uncertain 10 -> 1로 개선됐다.
  100-company no-fetch corpus
  `out/corpus/run_2026-06-05-bond-column-disambiguation/`는 100/100 reports,
  primary 243/190/53 유지, total checks 64,573 -> 64,585, matched
  30,915 -> 30,930, parse_uncertain 28,907 -> 28,904, note assertion checks
  2,195 -> 2,207, note assertion matched 1,416 -> 1,431로 마감했다.
  Verification: RED/GREEN candidate test, related tests 80 passed, full pytest
  527 passed.
- Latest rental-deposit-column-disambiguation refinement (2026-06-05):
  financing debt bridge 안에서 `유동 임대보증금`과 `비유동 임대보증금`이 같은
  `rental_deposits` account key로 합쳐져 남던 마지막 net debt bridge
  parse_uncertain을 분리했다. `유동` 임대보증금은
  `current_rental_deposits`, `비유동` 임대보증금은
  `noncurrent_rental_deposits`, 일반 임대보증금은 기존 `rental_deposits`로
  유지한다. 직접 100사 전체 주석 스캔 기준 같은 29개 회사 / 89개 net debt
  bridge 표에서 공식 상태가 matched 356 -> 358, unexplained_gap 20 유지,
  parse_uncertain 1 -> 0으로 개선됐다. 100-company no-fetch corpus
  `out/corpus/run_2026-06-05-rental-deposit-column-disambiguation/`는
  100/100 reports, primary 243/190/53 유지, total checks 64,585 ->
  64,586, matched 30,930 -> 30,932, parse_uncertain 28,904 -> 28,903,
  note assertion checks 2,207 -> 2,208, note assertion matched 1,431 ->
  1,433으로 마감했다. Verification: RED/GREEN candidate test, related tests
  81 passed, full pytest 528 passed.
- Latest net-debt-aggregate-movement-skip refinement (2026-06-05):
  두 라벨 열을 쓰는 financing debt bridge 표에서 `재무현금흐름 증가(감소)`
  총계 행과 `증가`/`감소` 세부 행이 함께 표시될 때 총계와 세부를 모두 후보로
  넣어 이중 집계되던 문제를 보정했다. primary/secondary 라벨이 같은
  signed movement 행은 같은 primary 아래 더 구체적인 secondary 행이 뒤따를 때만
  aggregate movement로 보고 제외하며, 기초/기말 행은 그대로 보존한다. 직접 100사
  전체 주석 스캔 기준 같은 29개 회사 / 89개 net debt bridge 표에서 후보 수는
  2,414 -> 2,390, 공식 상태는 matched 358 -> 368, unexplained_gap 20 -> 10,
  parse_uncertain 0 유지로 개선됐다. 100-company no-fetch corpus
  `out/corpus/run_2026-06-05-net-debt-aggregate-movement-skip/`는
  100/100 reports, primary 243/190/53 유지, matched 30,932 -> 30,942,
  unexplained_gap 4,050 -> 4,040, note assertion matched 1,433 -> 1,443,
  note assertion unresolved 679 -> 669로 마감했다. Verification: RED/GREEN
  candidate test, related tests 82 passed, full pytest 529 passed.
- Latest display-unit-tolerance refinement (2026-06-05): roll-forward 공식의
  matched 판정 tolerance를 명시 tolerance와 후보 표시 단위(`unit_multiplier`) 중
  큰 값으로 계산하도록 보정했다. DART 표가 `백만원`/`천원` 단위로 표시될 때
  1 표시 단위 이내의 차이는 반올림 차이로 닫고, 그보다 큰 차이는 계속
  unexplained_gap으로 남긴다. 직접 100사 전체 주석 스캔 기준 같은 29개 회사 /
  89개 net debt bridge 표에서 공식 상태가 matched 368 -> 375,
  unexplained_gap 10 -> 3, parse_uncertain 0 유지로 개선됐다. 잔여 3건은
  표시 단위 1단위를 넘는 실제 차이로 남는다. 100-company no-fetch corpus
  `out/corpus/run_2026-06-05-display-unit-tolerance/`는 100/100 reports,
  primary 243/190/53 유지, matched 30,942 -> 30,956,
  unexplained_gap 4,040 -> 4,026, note assertion matched 1,443 -> 1,457,
  note assertion unresolved 669 -> 655로 마감했다. Verification: RED/GREEN
  formula test, related tests 83 passed, full pytest 530 passed.
- Latest inventory-carrying-allowance-summary refinement (2026-06-05):
  `재고자산` 주석에서 세부 행이 `상품`/`제품`/`원재료` 등으로 나오고 총계 행이
  `합계`가 아니라 `재고자산`으로 표시되는 총장부금액/평가충당금/장부금액 합계
  표를 `inventory_carrying_amount_summary`로 승격했다. 분류는
  `재고자산` 제목 또는 inventory-topic rows, `총장부금액` 또는
  `장부금액 합계` 헤더, 그리고 `합계`/`총계`/정확한 `재고자산` 총계 행을
  요구한다. 후보 추출은 이 layout에서만 `재고자산` 행을 ending
  `inventories` 후보로 허용해 세부 제품/상품 행을 개별 검증 후보로 오인하지
  않는다. 한솔케미칼 source `candidate-report`는
  `inventory_carrying_amount_summary: 4`, `verification_candidates: 398`을
  기록했다. 직접 100사 원천 재분석 기준 현재 inventory carrying summary는
  30개 회사 / 106개 표 / 132개 후보이며, 이번 신규 변형은 그중 9개 회사에서
  32개 unknown table을 줄였다(한솔케미칼, 현대위아, 엘앤에프, 롯데하이마트,
  지누스, 풍산, 하이트진로홀딩스, 롯데렌탈, 제이에스코퍼레이션).
  100-company no-fetch corpus
  `out/corpus/run_2026-06-05-inventory-carrying-allowance-summary/`는
  100/100 reports, primary 243/190/53 유지, total checks/matched unchanged,
  known layout tables 3,621 -> 3,653, unknown layout items 37,301 -> 37,269,
  validation-relevant unknown layout items 5,443 -> 5,411로 마감했다.
  Verification: RED/GREEN layout/candidate tests, focused related tests 5
  passed, full pytest 532 passed.
- Latest loss-allowance-financial-asset-rows refinement (2026-06-05):
  `매출채권 및 기타채권` 주석의 손실충당금 변동표 중 movement 행이
  `기초 손실충당금`/`기말 손실충당금`이 아니라 `기초금융자산`/
  `기말금융자산`으로 표시되고, 계정/측정치 헤더가 여러 행에 쌓이는 표를
  `loss_allowance_rollforward`로 승격했다. `금융상품` 헤더와
  `기초금융자산`/`기말금융자산`, `기대신용손실`, `손실충당금 전입`,
  `제거에 따른 감소`, `외화환산`, `매각예정대체`, `기타` movement를
  signed movement로 인식한다. 후보 추출은 표 상단에 `손상차손누계액` measure
  row가 있을 때만 손실충당금 후보를 내도록 guard를 둬, 총장부금액 변동표를
  손실충당금으로 오인하지 않게 했다. `금융상품` 헤더가 반복되는 경우에도
  loss allowance movement rows가 충분하면 row-oriented가 generic financial
  category orientation보다 우선한다. 이 layout의 signed roll-forward formulas는
  이제 `note_layout_formula_check`로 workpaper 검증 결과에 승격되며, 표시 단위
  rounding은 formula의 effective tolerance로 CheckResult에 보존된다. 한솔케미칼
  source `candidate-report`는 `loss_allowance_rollforward: 2`,
  `verification_candidates: 410`, `matched_formulas: 48`을 기록했다. 직접
  100사 원천 재분석 기준 이 layout은 37개 회사 / 127개 표 / 639개 후보 /
  126개 formulas에 발생했고 formula 상태는 matched 67, unexplained_gap 47,
  parse_uncertain 12였다. 100-company no-fetch corpus
  `out/corpus/run_2026-06-05-loss-allowance-financial-asset-rows/`는
  100/100 reports, primary 243/190/53 유지, total checks 64,586 -> 64,716,
  matched 30,956 -> 31,023, unexplained_gap 4,026 -> 4,073,
  parse_uncertain 28,903 -> 28,919, note assertion checks 2,208 -> 2,338,
  note assertion matched 1,457 -> 1,524, known layout tables 3,653 -> 3,776,
  validation-relevant unknown layout items 5,411 -> 5,308, validated tables
  11,796 -> 11,888로 마감했다. Verification: RED/GREEN
  layout/orientation/candidate/formula/workpaper-check tests, full pytest
  540 passed.
- Latest financial-fair-value-summary refinement (2026-06-05): `금융상품`
  주석의 단일 `공정가치` 금액 열 표를
  `financial_instrument_fair_value_summary`로 승격했다. 세부 금융자산/
  금융부채 row를 `fair_value_component`, `금융자산`/`금융부채` 총계 row를
  `fair_value_total` 후보로 보존하고, `financial_fair_value_total` formula를
  `note_layout_formula_check`로 승격한다. `단기금융상품`, `장기금융상품`,
  `단기투자자산`, `장기투자자산`, `매출채권및기타채권`, `기타유동/비유동금융자산`,
  `당기손익/기타포괄손익 공정가치 금융자산` 등 반복 라벨을 계정 키로
  매핑했다. 삼성생명처럼 `금융자산`/`금융부채`가 숫자 총계가 아니라 섹션
  헤더인 계층형 표는 아직 formula로 억지 matched하지 않고 후보 또는 unresolved로
  남긴다. 한솔케미칼 source `candidate-report`는
  `financial_instrument_fair_value_summary: 8`, `verification_candidates: 460`,
  `matched_formulas: 50`을 기록했다. 직접 100사 원천 재분석 기준 이 layout은
  10개 회사 / 40개 표 / 233개 후보 / 16개 formulas에 발생했고 formula 상태는
  matched 6, unexplained_gap 10, parse_uncertain 0이었다. 100-company no-fetch
  corpus `out/corpus/run_2026-06-05-financial-fair-value-summary/`는
  100/100 reports, primary 243/190/53 유지, total checks 64,716 -> 64,752,
  matched 31,023 -> 31,029, unexplained_gap 4,073 -> 4,084,
  parse_uncertain 28,919 -> 28,938, note assertion checks 2,338 -> 2,374,
  note assertion matched 1,524 -> 1,530, known layout tables 3,776 -> 3,816,
  validation-relevant unknown layout items 5,308 -> 5,296, validated tables
  11,888 -> 11,905로 마감했다. Verification: RED/GREEN
  layout/orientation/candidate/formula/workpaper-check tests, related tests
  137 passed, full pytest 545 passed.
- Latest functional-expense-research-allocation refinement (2026-06-05):
  `무형자산` 등 자산 주석의 `경상연구개발비 지출액` 표처럼 단일 행
  `연구와 개발 비용`이 `매출원가`, `판매비와 일반관리비`, `기능별 항목 합계`
  열로 배부되는 표를 `functional_expense_research_allocation`으로 승격했다.
  기존 감가상각/상각비 expense allocation 후보와 섞지 않고, 이 layout에서만
  매출원가/판관비를 `expense_component`, 기능별 항목 합계를 `expense_total`로
  추출해 `expense_summary_total` formula를 `note_layout_formula_check`로 검증한다.
  한솔케미칼 source `candidate-report`는
  `functional_expense_research_allocation: 2`, `verification_candidates: 470`,
  `matched_formulas: 52`를 기록했다. 직접 100사 원천 재분석 기준 이 layout은
  4개 회사 / 9개 표 / 22개 후보 / 8개 formulas에 발생했고 formula 상태는
  matched 4, unexplained_gap 4, parse_uncertain 0이었다. 100-company no-fetch
  corpus `out/corpus/run_2026-06-05-functional-expense-research-allocation/`는
  100/100 reports, primary 243/190/53 유지, total checks 64,752 -> 64,761,
  matched 31,029 -> 31,033, unexplained_gap 4,084 -> 4,088,
  parse_uncertain 28,938 -> 28,939, note assertion checks 2,374 -> 2,383,
  note assertion matched 1,530 -> 1,534, known layout tables 3,816 -> 3,825,
  validation-relevant unknown layout items 5,296 -> 5,287로 마감했다.
  Verification: RED/GREEN layout/orientation/candidate/workpaper-check tests,
  related tests 141 passed, full pytest 549 passed.
- Latest employee-benefit-maturity-summary refinement (2026-06-05):
  `퇴직급여제도`/`순확정급여부채` 주석의 확정급여 지급예상액 만기 표를
  `employee_benefit_maturity_summary`로 별도 승격했다. 금융부채
  `liquidity_maturity_analysis`와 섞지 않고, `확정급여제도에서 지급될 것으로
  예상되는 급여 지급액 추정치` row만 `defined_benefit_expected_payments`로
  추출한다. `1년 이내`뿐 아니라 `1~2년 미만`, `2~5년 미만`, `5년 이상` 같은
  회사별 maturity bucket header를 후보 열로 인식하고, 단위 배율 기준 1표시단위
  tolerance를 maturity formula에도 적용했다. 한솔케미칼 source
  `candidate-report`는 `employee_benefit_maturity_summary: 2`,
  `verification_candidates: 480`, `matched_formulas: 54`를 기록했다. 직접 100사
  원천 재분석 기준 이 layout은 22개 회사 / 53개 표 / 255개 후보 / 51개
  formulas에 발생했고 formula 상태는 matched 51, unexplained_gap 0,
  parse_uncertain 0이었다. 100-company no-fetch corpus
  `out/corpus/run_2026-06-05-employee-benefit-maturity-summary/`는 100/100 reports,
  primary 243/190/53 유지, total checks 64,761 -> 64,812, matched 31,033 -> 31,084,
  unexplained_gap 4,088 유지, parse_uncertain 28,939 유지, note assertion checks
  2,383 -> 2,434, note assertion matched 1,534 -> 1,585, known layout tables
  3,825 -> 3,889, unknown layout tables 37,017 -> 36,953,
  validation-relevant unknown layout items 5,287 -> 5,253로 마감했다.
  Verification: RED/GREEN layout/orientation/candidate/formula/workpaper-check
  tests, focused related tests passed, full pytest 556 passed.
- Latest lease-liability-maturity-summary refinement (2026-06-05):
  `리스`/`사용권자산 및 리스부채` 주석의 리스부채 만기 표를
  `lease_liability_maturity_summary`로 별도 승격했다. `총 리스부채`,
  `할인되지 않은 리스부채`, `최소리스료`, `리스부채에 대한 이자비용`,
  `최소리스료의 현재가치`, `리스부채` row를 source-backed maturity component와
  total 후보로 추출하고, 각 row별 `liquidity_maturity_total` formula를
  `note_layout_formula_check`로 승격한다. `받게 될 할인되지 않은 금융/운용
  리스료`, `금융리스채권`, `금융리스 순투자` 등 lessor/receivable 표는 제외하고,
  유동/비유동 total-only row처럼 maturity bucket component가 2개 미만인 row는
  formula 후보에서 제외한다. 한솔케미칼 source `candidate-report`는
  `lease_liability_maturity_summary: 4`, `verification_candidates: 490`,
  `matched_formulas: 56`을 기록했다. 직접 100사 원천 재분석 기준 이 layout은
  32개 회사 / 102개 표 / 587개 후보 / 141개 formulas에 발생했고 formula 상태는
  matched 140, unexplained_gap 1, parse_uncertain 0이었다. 남은 1건은
  더존비즈온 별도 리스부채 이자비용 표의 2천원 차이로, 1표시단위 tolerance를
  넘기 때문에 보수적으로 후속 확인으로 남겼다. 100-company no-fetch corpus
  `out/corpus/run_2026-06-05-lease-liability-maturity-summary/`는 100/100 reports,
  primary 243/190/53 유지, total checks 64,812 -> 64,953, matched 31,084 -> 31,224,
  unexplained_gap 4,088 -> 4,089, parse_uncertain 28,939 유지, note assertion checks
  2,434 -> 2,575, note assertion matched 1,585 -> 1,725, note assertion unresolved
  717 -> 718, known layout tables 3,889 -> 3,959, unknown layout tables
  36,953 -> 36,883, validated tables 11,905 -> 11,913,
  validation-relevant unknown layout items 5,253 -> 5,196로 마감했다.
  Verification: RED/GREEN layout/orientation/candidate/workpaper-check tests,
  related tests 176 passed, full pytest 561 passed.
- Latest financial-category-formula-summary refinement (2026-06-05):
  기존 `financial_instrument_category_summary`를 확장해 `범주별 금융상품`
  표의 category component columns를 source-backed 후보로 추출하고, row별
  `financial_category_total` formula를 `note_layout_formula_check`로 승격했다.
  `범주 합계`뿐 아니라 plain `합계`/`합 계` total header를 인식하고,
  `기타금융자산`, `기타금융부채`, `위험회피목적파생상품` category column을
  component로 포함한다. CJ대한통운처럼 첫 label column이 `금융부채` 섹션이고
  둘째 label column이 실제 계정(`매입채무`, `차입금`, `리스부채`)인 표는
  둘째 label을 account key로 사용하며, 섹션 header row와 0원 component는
  formula 후보에서 제외한다. 한솔케미칼 source `candidate-report`에는 새 formula
  증가가 없었다. 한솔케미칼 금융상품 범주표는 명시적 total header가 부족한
  stacked/section형이어서 보수적으로 남겼다. 직접 100사 원천 재분석 기준 이
  layout은 69개 회사 / 503개 표 / 2,342개 후보 / 956개 formulas에 발생했고
  formula 상태는 matched 920, unexplained_gap 36, parse_uncertain 0이었다.
  남은 gap은 자동 matched하지 않고 row-level 후속 확인으로 남긴다.
  100-company no-fetch corpus
  `out/corpus/run_2026-06-05-financial-category-formula-summary/`는 100/100 reports,
  primary 243/190/53 유지, total checks 64,953 -> 65,909, matched 31,224 -> 32,144,
  unexplained_gap 4,089 -> 4,125, parse_uncertain 28,939 유지, note assertion checks
  2,575 -> 3,531, note assertion matched 1,725 -> 2,645, note assertion unresolved
  718 -> 754, known layout tables 3,959 -> 4,058, unknown layout tables
  36,883 -> 36,784, validated tables 11,913 -> 11,968,
  validation-relevant unknown layout items 5,196 -> 5,113로 마감했다.
  Verification: RED/GREEN layout/candidate/formula/workpaper-check tests,
  related tests 184 passed, full pytest 566 passed.
- Latest receivable-present-value-carrying-summary refinement (2026-06-05):
  `매출채권 및 기타채권` 계열의 `총장부금액`/`현재가치할인차금`/
  `손상차손누계액`/`대손충당금`/`손실충당금`/`이연대출부대수익(비용)`/
  `장부금액 합계` 표를 `receivable_present_value_carrying_summary`로 별도
  승격했다. 기존 `receivable_carrying_amount_summary`처럼 장부금액 후보만
  뽑는 데서 멈추지 않고, row별 `receivable_carrying_component` 후보를
  source-backed로 추출해 `receivable_carrying_total` formula를
  `note_layout_formula_check`로 승격한다. DL이앤씨처럼 첫 label column이
  `매출채권 및 기타유동채권` 같은 broad bucket이고 둘째 label column이
  실제 계정(`유동매출채권`, `단기미수금`, `장기보증금`)인 표는 둘째 label을
  account key로 사용한다. 직접 100사 원천 재분석 기준 이 layout은 16개 회사 /
  54개 표 / 1,132개 후보 / 404개 formulas에 발생했고 formula 상태는
  matched 396, unexplained_gap 8, parse_uncertain 0이었다. 남은 8건은 모두
  삼성E&A의 단기미수금/장기보증금 행에서 `손상차손누계액=0`,
  `현재가치할인차금=0`인데 장부금액이 총장부금액보다 작은 표 내부 미설명
  차이로, 자동 matched하지 않고 후속 확인으로 남겼다. 100-company no-fetch
  corpus `out/corpus/run_2026-06-05-receivable-present-value-carrying-summary/`는
  100/100 reports, primary 243/190/53 유지, total checks 65,909 -> 66,313,
  matched 32,144 -> 32,540, unexplained_gap 4,125 -> 4,133, parse_uncertain
  28,939 유지, note assertion checks 3,531 -> 3,935, note assertion matched
  2,645 -> 3,041, note assertion unresolved 754 -> 762, known layout tables
  4,058 -> 4,064, unknown layout tables 36,784 -> 36,778, validated tables
  11,968 -> 11,989, validation-relevant unknown layout items 5,113 -> 5,107로
  마감했다. Verification: RED/GREEN layout/candidate/formula/workpaper-check
  tests, related tests 132 passed, full pytest 571 passed.
- Latest inventory-carrying-formula-summary refinement (2026-06-05):
  기존 `inventory_carrying_amount_summary`를 확장해 `재고자산` 표의
  `총장부금액`/`취득원가`/`평가전금액`과 `재고자산 평가충당금`/
  `평가충당금`/`평가손실충당금`/`평가손실누계액`/`손상차손누계액`/
  `손실충당금`/`충당금`을 source-backed component로 추출하고, row별
  `inventory_carrying_total` formula를 `note_layout_formula_check`로 승격했다.
  `유동재고자산`, `총유동재고자산`, `재고자산 합계` 같은 회사별 total row를
  inventory total로 인식하며, 삼성전기처럼 첫 label column이 `재고자산 합계`
  broad bucket이고 둘째 label column이 실제 품목(`제품 및 상품`, `재공품`,
  `원재료`)인 표는 둘째 label을 account key로 사용한다. 총장부금액 한 열만
  있는 표는 기존처럼 total ending 후보만 보수적으로 유지한다. 직접 100사 원천
  재분석 기준 이 layout은 63개 회사 / 228개 표 / 3,644개 후보 / 1,404개
  formulas에 발생했고 formula 상태는 matched 1,378, unexplained_gap 26,
  parse_uncertain 0이었다. 100-company no-fetch corpus
  `out/corpus/run_2026-06-05-inventory-carrying-formula-summary/`는 100/100 reports,
  primary 243/190/53 유지, total checks 66,313 -> 67,717, matched
  32,540 -> 33,942, unexplained_gap 4,133 -> 4,135, parse_uncertain 28,939 유지,
  note assertion checks 3,935 -> 5,339, note assertion matched 3,041 -> 4,443,
  note assertion unresolved 762 -> 764, known layout tables 4,064 -> 4,194,
  unknown layout tables 36,778 -> 36,648, validated tables 11,989 -> 12,011,
  validation-relevant unknown layout items 5,107 -> 4,979로 마감했다. Corpus에서
  새로 남은 +2 gap은 자이에스앤디 재고자산 행의 표 내부 산식 차이로
  자동 matched하지 않았다. Verification: RED/GREEN layout/candidate/formula/
  workpaper-check tests, full pytest 576 passed.
- Latest lease-liability-current-noncurrent-summary refinement (2026-06-05):
  `리스`/`리스부채` 주석의 `유동 리스부채` + `비유동 리스부채` = `합계`/
  `리스부채 합계`/`총 리스부채` 단일 금액 요약표를
  `lease_liability_current_noncurrent_summary`로 승격했다. 후보는
  `lease_liabilities` account로 source-backed `lease_liability_split_component`
  2개와 `ending` 1개를 보존하고, `lease_liability_split_total` formula를
  `note_layout_formula_check`로 만든다. 표 순서는 회사마다 달라서 행 순서가
  아니라 row label role로 묶으며, `1년 이내`/`1년 초과`/`합계 구간 합계`
  같은 maturity bucket 헤더가 2개 이상 있으면 기존
  `lease_liability_maturity_summary`로 남기고 이 layout에서는 제외한다.
  직접 100사 원천 재분석은 27개 회사 / 100개 표 / 300개 후보 / 100개
  formulas를 찾았고 모두 matched였다. 최초 스캔에서 풍산 만기분석 2개 표가
  유동/비유동 요약표로 오분류되어 unexplained_gap이 생겼으나 maturity bucket
  배제 조건으로 제거했다. 100-company no-fetch corpus
  `out/corpus/run_2026-06-05-lease-liability-current-noncurrent-summary/`는
  100/100 reports, primary 243/190/53 유지, total checks 67,717 -> 67,817,
  matched 33,942 -> 34,042, unexplained_gap 4,135 유지, parse_uncertain
  28,939 유지, note assertion checks 5,339 -> 5,439, note assertion matched
  4,443 -> 4,543, note assertion unresolved 764 유지, known layout tables
  4,194 -> 4,294, unknown layout tables 36,648 -> 36,548, validated tables
  12,011 -> 12,017, validation-relevant unknown layout items 4,979 -> 4,971로
  마감했다. Verification: RED/GREEN layout/candidate/formula/workpaper-check
  tests, focused lease maturity regression tests, full pytest 581 passed.
- Latest financial-fair-value-level-summary refinement (2026-06-05):
  `금융상품 공정가치` 주석의 공정가치 서열체계 표를
  `financial_fair_value_level_summary`로 승격했다. `수준1`/`수준2`/`수준3`
  열을 source-backed `fair_value_level_component`로 추출하고 `합 계` 열을
  `fair_value_total`로 추출해 row별 `financial_fair_value_level_total`
  formula를 `note_layout_formula_check`로 검증한다. 한화손해보험처럼 첫 번째
  label column이 `금융자산`/`금융부채` section이고 두 번째 label column이
  실제 상품명인 표는 두 번째 label을 account key와 증거 label에 사용하며,
  `합계` 행은 section label을 기준으로 `financial_assets` 또는
  `financial_liabilities` aggregate key를 부여한다. 직접 100사 원천 재분석은
  2개 회사 / 9개 표 / 106개 후보 / 37개 formulas를 찾았고 모두 matched였다.
  100-company no-fetch corpus
  `out/corpus/run_2026-06-05-financial-fair-value-level-summary/`는 100/100 reports,
  primary 243/190/53 유지, total checks 67,817 -> 67,854, matched
  34,042 -> 34,079, unexplained_gap 4,135 유지, parse_uncertain 28,939 유지,
  note assertion checks 5,439 -> 5,476, note assertion matched 4,543 -> 4,580,
  note assertion unresolved 764 유지, known layout tables 4,294 -> 4,394,
  unknown layout tables 36,548 -> 36,448, validated tables 12,017 -> 12,026,
  validation-relevant unknown layout items 4,971 -> 4,964로 마감했다.
  Verification: RED/GREEN layout/candidate/formula/workpaper-check tests,
  full pytest 585 passed.
- Latest tax-expense-composition-summary refinement (2026-06-05):
  `법인세비용` 주석의 구성표를 `tax_expense_composition_summary`로
  승격했다. 기간 열(`당기`/`전기`)별로 `법인세부담액`/`법인세추납(환급)액`,
  `이연법인세 변동액`, `자본에 직접 반영된 법인세`, 단순 구성표의 `기타`
  행을 source-backed `tax_expense_component`로 추출하고 최종
  `법인세비용`/`법인세비용(수익)` 행을 `tax_expense_total`로 추출해
  `tax_expense_composition_total` formula를 `note_layout_formula_check`로
  검증한다. 유효세율 조정표(`법인세비용차감전`, `적용세율`, `유효세율`)와
  OCI 세효과 상세표(`순확정급여`, `기타포괄손익`, `위험회피`, `회계정책변경`
  등)는 이번 layout에서 제외했다. 직접 100사 원천 재분석은 10개 회사 /
  19개 표 / 167개 후보 / 37개 formulas를 찾았고 모두 matched였다.
  최초 넓은 스캔은 16개 회사 / 32개 표 / 59개 formulas까지 잡았지만
  effective-tax reconciliation과 이연법인세 상세 변동표가 섞여
  parse_uncertain/gap이 발생해 보수화했다. 100-company no-fetch corpus
  `out/corpus/run_2026-06-05-tax-expense-composition-summary/`는 100/100 reports,
  primary 243/190/53 유지, total checks 67,854 -> 67,891, matched
  34,079 -> 34,116, unexplained_gap 4,135 유지, parse_uncertain 28,939 유지,
  note assertion checks 5,476 -> 5,513, note assertion matched 4,580 -> 4,617,
  note assertion unresolved 764 유지, known layout tables 4,394 -> 4,413,
  unknown layout tables 36,448 -> 36,429, validated tables 12,026 -> 12,045,
  validation-relevant unknown layout items 4,964 유지로 마감했다.
  Verification: RED/GREEN layout/candidate/formula/workpaper-check tests,
  direct 100-company scan, full pytest 589 passed.
- Latest credit-risk-exposure-row-summary refinement (2026-06-05):
  `재무위험관리`/`금융상품` 주석의 신용위험 최대노출 표를 기존
  `credit_risk_exposure_summary` layout 안에서 가로형까지 확장했다. 기존
  세로형(`신용위험` 금액 열 + 금융자산 rows)은 그대로 유지하고, 새 가로형은
  `신용위험에 대한 최대 노출정도` row와 금융자산/금융보증/대출약정 등
  exposure component columns 및 `금융상품 합계` column을 사용한다. 합계 전
  숫자 열 전체를 source-backed `credit_exposure_component`로 추출하고,
  taxonomy가 불명확한 `금융보증계약`/`미사용대출약정` 등은
  `credit_risk_exposure_component` generic key로 보수 처리한다. 여러 exposure
  rows가 한 표에 있을 수 있어 `discover_credit_risk_exposure_formulas`를
  추가해 row별 `credit_risk_exposure_total` formula를
  `note_layout_formula_check`로 검증한다. 직접 100사 구현 경로 재분석은
  8개 회사 / 28개 표 / 208개 후보 / 30개 formulas를 찾았고 모두 matched였다.
  최초 좁은 스캔은 POSCO홀딩스와 롯데렌탈의 `예금상품`, `금융보증계약`,
  `리스채권`, `미사용대출약정`을 빼먹어 gap이 발생했으나, 합계 전 숫자 열
  전체를 component로 다루면서 제거했다. 100-company no-fetch corpus
  `out/corpus/run_2026-06-05-credit-risk-exposure-row-summary/`는 100/100 reports,
  primary 243/190/53 유지, total checks 67,891 -> 67,921, matched
  34,116 -> 34,146, unexplained_gap 4,135 유지, parse_uncertain 28,939 유지,
  note assertion checks 5,513 -> 5,543, note assertion matched 4,617 -> 4,647,
  note assertion unresolved 764 유지, known layout tables 4,413 -> 4,437,
  unknown layout tables 36,429 -> 36,405, validated tables 12,045 -> 12,049,
  validation-relevant unknown layout items 4,964 -> 4,940으로 마감했다.
  Verification: RED/GREEN layout/orientation/candidate/formula/workpaper-check
  tests, direct 100-company scan, full pytest 594 passed.
- Latest provision-current-noncurrent-summary refinement (2026-06-05):
  `충당부채` 주석에서 구성 충당부채 행들이 있고 열이 `유동`/`비유동`
  또는 `유동충당부채`/`비유동충당부채`로 나뉘며 마지막 행이
  `기타충당부채 합계`인 표를 `provision_current_noncurrent_summary`로
  승격했다. 이 표는 roll-forward가 아니라 구성행 합계표이므로 기존
  `provision_rollforward`와 분리했고, 각 유동/비유동 열에서 source-backed
  `provision_column_component` 후보를 모아 `provision_column_total`과
  비교하는 `provision_column_total` formula를
  `note_layout_formula_check`로 검증한다. 구성행은 literal `충당부채`가
  없는 `기타장기종업원급여부채` 같은 충당부채성 계정도 포함하도록
  provision account taxonomy를 재사용한다. 직접 100사 구현 경로 재분석은
  5개 회사 / 14개 표 / 112개 후보 / 28개 formulas를 찾았고 모두
  matched였다. 단위는 천원과 백만원 사례를 모두 통과했고, 한 표시단위
  이내 rounding difference는 candidate unit multiplier를 tolerance floor로
  사용해 matched 처리했다. 100-company no-fetch corpus
  `out/corpus/run_2026-06-05-provision-current-noncurrent-summary/`는 100/100
  reports, primary 243/190/53 유지, total checks 67,921 -> 67,945, matched
  34,146 -> 34,174, unexplained_gap 4,135 유지, parse_uncertain
  28,939 -> 28,935, note assertion checks 5,543 -> 5,567, note assertion
  matched 4,647 -> 4,675, note assertion unresolved 764 유지, known layout
  tables 4,437 -> 4,447, unknown layout tables 36,405 -> 36,395,
  validation-relevant unknown layout items 4,940 -> 4,930으로 마감했다.
  Verification: RED/GREEN layout/orientation/candidate/formula/workpaper-check
  tests, direct 100-company scan, full pytest 599 passed.
- Latest debt-detail matched-assertions refinement (2026-06-05):
  기존 `debt_instrument_detail_summary` 후보/진단을 보고서 공식
  `note_layout_formula_check`로 일부 승격했다. 장기차입금/사채 상세표에서
  `명목금액`, `현재가치할인차금`/`사채할인발행차금`,
  `...유동성 대체 부분`, `...비유동성 대체 부분`이 source-backed로
  잡히면 `face_amount + debt_discount + current_portion = ending` 형태의
  `debt_component_split`을 검증한다. `사채 제외` 문구가 있는 차입금 표를
  bonds로 오분류하지 않도록 title이 명확한 `차입금`이면 borrowings를 우선
  적용했다. 다만 직접 100사 구현 경로 재분석에서 36개 회사 / 165개 표 /
  373개 후보 / 165개 formulas 중 matched 9, unexplained_gap 9,
  parse_uncertain 147이 나와, 아직 섹션/행 역할이 불완전한 non-closing 및
  parse-uncertain debt formula는 공식 report check로 승격하지 않고 matched로
  닫힌 산식만 올리도록 보수화했다. 공식 assertion 경로 재스캔은 3개 회사 /
  9개 checks / 9개 matched였다. 100-company no-fetch corpus
  `out/corpus/run_2026-06-05-debt-detail-matched-assertions/`는 100/100 reports,
  primary 243/190/53 유지, total checks 67,945 -> 67,954, matched
  34,174 -> 34,183, unexplained_gap 4,135 유지, parse_uncertain 28,935 유지,
  note assertion checks 5,567 -> 5,576, note assertion matched
  4,675 -> 4,684, note assertion unresolved 764 유지로 마감했다.
  Verification: RED/GREEN candidate/formula/workpaper-check tests, direct
  100-company formula and assertion scans, full pytest 604 passed.
- Latest financial-category-column-totals refinement (2026-06-05):
  `financial_instrument_category_summary`를 total column 중심 검증에서
  total row 중심 검증까지 확장했다. `범주별 금융상품` 표가
  `상각후원가측정 금융자산`, `당기손익-공정가치측정 금융자산`,
  `기타포괄손익-공정가치측정 금융자산` 같은 category columns와 마지막
  `합계`/`총계` row만 갖는 경우, 각 category column의 source-backed account
  rows를 `financial_category_column_component`로 모으고 같은 column의 total
  row를 `financial_category_column_total`로 추출해
  `financial_category_column_total` formula를 검증한다. 기존 row-wise
  `financial_category_total`은 유지했고, 금융 category total column 탐지에서
  마지막 열 fallback을 제거해 `기타포괄손익...금융자산` 같은 category 열이
  total로 오인되지 않도록 했다. 직접 100사 heuristic scan은 43개 회사 /
  228개 표 / 439개 formulas 중 matched 267, gap 172로 넓게 잡혔지만,
  공식 assertion 경로는 layout/orientation/account-key evidence가 충분하고
  formula가 matched로 닫힌 5개 회사 / 18개 checks만 승격했다. 100-company
  no-fetch corpus `out/corpus/run_2026-06-05-financial-category-column-totals/`는
  100/100 reports, primary 243/190/53 유지, total checks 67,954 -> 67,964,
  matched 34,183 -> 34,201, unexplained_gap 4,135 유지, parse_uncertain
  28,935 -> 28,927, note assertion checks 5,576 -> 5,586,
  note assertion matched 4,684 -> 4,702, note assertion unresolved 764 유지,
  known layout tables 4,447 -> 4,607, unknown layout tables 36,395 -> 36,235,
  validation-relevant unknown layout items 4,930 -> 4,866으로 마감했다.
  Verification: RED/GREEN layout/candidate/formula/workpaper-check tests,
  direct 100-company assertion scan, full pytest 608 passed.
- Latest employee-benefit-expense-allocation refinement (2026-06-05):
  `퇴직급여제도`/`종업원급여` 주석의 비용 배부표가 회사별로 행 방향
  component(`판관비에 포함된 금액`, `매출원가에 포함된 금액`)와 기간 열
  (`당기`, `전기`)을 갖는 경우를 `employee_benefit_expense_allocation`으로
  분류하고, 각 기간별 source-backed component 합계가 `합계`/`총계` row와
  닫히는지 검증하도록 추가했다. 단위/tolerance와 source coordinates는
  기존 `VerificationCandidate` 경로를 그대로 사용하며, 공식
  `note_layout_formula_check`에는 matched formula만 승격한다. 직접 100사
  assertion scan은 LG씨엔에스 1개 회사 / 2개 표 / 4개 checks / 4개
  matched였다. 100-company no-fetch corpus
  `out/corpus/run_2026-06-05-employee-benefit-expense-allocation/`는 100/100
  reports, total checks 67,964 -> 67,968, matched 34,201 -> 34,205,
  unexplained_gap 4,135 유지, parse_uncertain 28,927 유지, note assertion
  checks 5,586 -> 5,590, note assertion matched 4,702 -> 4,706,
  known layout tables 4,607 -> 4,609, unknown layout tables 36,235 -> 36,233,
  validation-relevant unknown layout items 4,866 -> 4,864로 마감했다. 누적
  산출물 관리를 위해 해당 run의 중복 `raw/`와 `reports/`는 삭제하고
  summary/JSON artifacts만 보존했으며, 기존 screenshot/image artifacts도
  정리했다. Verification: RED/GREEN layout/candidate/formula/workpaper-check
  tests, direct 100-company assertion scan, full pytest 612 passed.
- Latest receivable-loss-allowance-carrying refinement (2026-06-05):
  `매출채권, 대여금 및 기타채권` 장부금액 구성표가
  `총장부금액`, `차감: 손실충당금`/`손실충당금`, `장부금액 합계` headers로
  표시되는 변형을 `receivable_carrying_amount_summary`로 인식하고, 각
  source-backed row에서 gross amount와 allowance component를 preserving한
  뒤 carrying amount total과 대사하도록 확장했다. 기존 ending candidate도
  유지하되, 공식 `note_layout_formula_check`에는 matched로 닫힌 carrying
  formula만 승격해 애매한 row/account interpretation이 false gap으로
  보고되지 않게 했다. 직접 100사 assertion scan은 36개 회사 / 522개
  checks / 522개 matched였다. 100-company no-fetch corpus
  `out/corpus/run_2026-06-05-receivable-loss-allowance-carrying/`는 100/100
  reports, total checks 67,968 -> 68,490, matched 34,205 -> 34,727,
  unexplained_gap 4,135 유지, parse_uncertain 28,927 유지, note assertion
  checks 5,590 -> 6,112, note assertion matched 4,706 -> 5,228,
  note assertion unresolved 764 유지, known layout tables 4,609 -> 4,627,
  unknown layout tables 36,233 -> 36,215, validation-relevant unknown layout
  items 4,864 -> 4,846으로 마감했다. 누적 산출물 관리를 위해 해당 run의
  중복 `raw/`와 `reports/`는 삭제하고 summary/JSON artifacts만 보존했다.
  Verification: RED/GREEN layout/candidate/formula/workpaper-check tests,
  direct 100-company assertion scan, full pytest 615 passed.
- Corpus artifact cleanup / disk guardrail (2026-06-05): `out/corpus`가
  repeated 100-company run의 duplicated `raw/` and generated `reports/`
  artifacts로 약 41GB까지 증가했기 때문에, manifest files와 최신
  `out/corpus/run_2026-06-05-receivable-loss-allowance-carrying/`의
  summary/JSON artifacts만 남기고 stale run directories 및 raw/report
  artifacts를 정리했다. Current footprint: `out/corpus` 약 77MB, `out`
  약 91MB. 재발 방지를 위해 `dart-footing workpaper-corpus`에
  `--results-only` 옵션을 추가했다. 이 옵션은 `corpus_result.json`,
  `corpus_report.md`, taxonomy artifacts를 쓴 뒤 generated `raw/` and
  `reports/` directories를 제거한다. Future goal-mode corpus runs should
  use `--results-only` unless raw HTML or rendered reports are explicitly
  needed for debugging. Verification: focused corpus prune test, CLI help,
  full pytest 616 passed.
- Latest receivable-aging-bucket-summary refinement (2026-06-05):
  `매출채권` 손실충당금 상세내역이 aging bucket columns
  (`6개월 이내 연체 및 정상`, `6개월 초과 1년 이내 연체`, `1년 초과 연체`,
  `합계`)과 measure rows (`총 장부금액`, `손실충당금`, `기대 손실률`)로
  표시되는 변형을 `receivable_loss_allowance_aging_summary`로 분류하고,
  금액 row인 `총 장부금액`과 `손실충당금`만 bucket component 합계와 total
  column을 대사하도록 추가했다. 비율 row인 `기대 손실률`은 검증 대상에서
  제외한다. 디와이 재확보 샘플 직접 scan은 6개 checks / 6개 matched였다.
  100-company corpus는 `--results-only`로 실행해 generated `raw/` and
  `reports/` artifacts를 자동 제거했다. New run
  `out/corpus/run_2026-06-05-receivable-aging-bucket-summary/`는 100/100
  reports, total checks 68,490 -> 68,500, matched 34,727 -> 34,737,
  unexplained_gap 4,135 유지, parse_uncertain 28,927 유지, note assertion
  checks 6,112 -> 6,122, note assertion matched 5,228 -> 5,238,
  note assertion unresolved 764 유지, known layout tables 4,627 -> 4,638,
  unknown layout tables 36,215 -> 36,204, validation-relevant unknown layout
  items 4,846 -> 4,838로 마감했다. Verification: RED/GREEN
  layout/orientation/candidate/formula/workpaper-check tests, direct 디와이
  assertion scan, full pytest 621 passed.
- Latest asset-period-rollforward-summary refinement (2026-06-05):
  삼일제약 `유형자산` 주석처럼 rows are periods (`당기`, `전기`) and columns
  are movement labels (`기초`, `처분`, `기말`)인 기간별 증감표 변형을
  `asset_period_rollforward_summary`로 분류했다. 각 기간 row를 별도
  account key로 묶고, `기초`는 beginning, `기말`은 ending, 나머지
  변동열은 displayed sign 그대로 `signed_movement`로 추출한다. `-` 표시는
  parse amount가 없으므로 후보에서 제외하고, 기초=기말이면 일반
  roll-forward로 닫힌다. 삼일제약 실제 샘플 직접 scan은 8개 checks / 8개
  matched였다. 100-company corpus는 `--results-only`로 실행했고, raw/reports
  artifacts 및 큰 상세 JSON은 `run_summary.json`으로 축약 후 삭제했다.
  New run `out/corpus/run_2026-06-05-asset-period-rollforward-summary/`는
  total checks 68,500 -> 68,508, matched 34,737 -> 34,745,
  unexplained_gap 4,135 유지, parse_uncertain 28,927 유지, note assertion
  checks 6,122 -> 6,130, note assertion matched 5,238 -> 5,246,
  note assertion unresolved 764 유지, known layout tables 4,638 -> 4,642,
  unknown layout tables 36,204 -> 36,200, validation-relevant unknown layout
  items 4,838 -> 4,834로 마감했다. Current footprint: `out/corpus` 약
  268KB, `out` 약 15MB. Verification: RED/GREEN
  layout/orientation/candidate/workpaper-check tests, direct 삼일제약 assertion
  scan, full pytest 625 passed.
- Latest receivable-two-label-carrying refinement (2026-06-05):
  현대위아 `매출채권, 대여금 및 기타채권` 주석처럼 first label column이
  `유동`/`기타 비유동채권` 같은 bucket이고 second label column이 실제 계정명
  (`미수금`, `대여금`, `장기미수금`, `보증금`)인 gross/allowance/carrying
  표를 기존 `receivable_carrying_amount_summary`로 일반화했다. 레이아웃
  분류는 receivable title plus explicit `총장부금액`/`손실충당금`/`장부금액
  합계` columns and two-label bucket shape를 허용하고, 후보 추출은 first-label
  current/noncurrent context를 second-label account name에 결합해
  `short_term_other_receivables`, `short_term_loans`,
  `long_term_other_receivables`, `long_term_deposits` 등으로 source-backed
  components와 ending을 보존한다. 현대위아 실제 샘플 직접 scan은 table 29/30에서
  8개 matched checks를 확인했다. 100-company corpus는 `--results-only`로
  실행했고, raw/reports artifacts 및 큰 상세 JSON은 `run_summary.json`으로 축약
  후 삭제했다. New run
  `out/corpus/run_2026-06-05-receivable-two-label-carrying-summary/`는
  total checks 68,508 -> 68,522, matched 34,745 -> 34,759,
  unexplained_gap 4,135 유지, parse_uncertain 28,927 유지, note assertion
  checks 6,130 -> 6,144, note assertion matched 5,246 -> 5,260,
  note assertion unresolved 764 유지, known layout tables 4,642 -> 4,646,
  unknown layout tables 36,200 -> 36,196, validation-relevant unknown layout
  items 4,834 -> 4,830으로 마감했다. Current footprint: `out/corpus` 약
  268KB, `out` 약 15MB. Verification: RED/GREEN
  layout/candidate/workpaper-check tests, direct 현대위아 assertion scan,
  full pytest 628 passed plus post-evidence focused tests 3 passed.
- Latest asset-two-label-row-rollforward refinement (2026-06-05):
  현대위아 `투자부동산` 주석처럼 first label column이 repeated disclosure
  descriptor (`투자부동산의 변동에 대한 조정`), second label column이 movement
  label (`기초`, `감가상각비`, `대체`, `기타`, `기말`), final amount column이
  single asset account인 표를 `asset_two_label_row_rollforward_summary`로
  분류했다. 이 표는 displayed signs가 이미 괄호 음수로 들어오므로 중간 movement를
  asset add/subtract role로 해석하지 않고 모두 `signed_movement`로 보존해
  `beginning + signed movements = ending`만 검증한다. 현대위아 실제 샘플 직접
  scan은 연결/별도 투자부동산 table에서 4개 matched checks를 확인했다.
  100-company corpus는 `--results-only`로 실행했고, raw/reports artifacts 및 큰
  상세 JSON은 `run_summary.json`으로 축약 후 삭제했다. New run
  `out/corpus/run_2026-06-05-asset-two-label-row-rollforward-summary/`는
  total checks 68,522 -> 68,581, matched 34,759 -> 34,818,
  unexplained_gap 4,135 유지, parse_uncertain 28,927 유지, note assertion
  checks 6,144 -> 6,203, note assertion matched 5,260 -> 5,319,
  note assertion unresolved 764 유지, known layout tables 4,646 -> 4,705,
  unknown layout tables 36,196 -> 36,137, validation-relevant unknown layout
  items 4,830 -> 4,824로 마감했다. Current footprint: `out/corpus` 약
  268KB, `out` 약 15MB. Verification: RED/GREEN
  layout/orientation/candidate/workpaper-check tests, direct 현대위아 assertion
  scan, full pytest 632 passed.
- Latest debt-component-column refinement (2026-06-05):
  현대위아 `차입금 및 사채` 주석처럼 사채 상세 표가 행별 개별 사채를 나열하고
  요약 행에서 `명목금액`, `차감: 유동성사채`, `차감: 사채할인발행차금`,
  `비유동 사채의 비유동성 부분`을 열 단위로 표시하는 경우를
  `debt_instrument_detail_summary` 안에서 component-column variant로 처리했다.
  기존 행 기반 debt split(`차입금`, `1년이내 만기도래분`,
  `비유동성 차입금`)과 충돌하지 않도록 header role mapper와 row label role
  mapper를 분리했다. 현대위아 실제 샘플 직접 scan은 table 104/105에서
  `100,000 + (50,000) + (68) = 49,932` 및
  `300,000 + (200,000) + (235) = 99,765` 두 개의 matched checks를
  확인했다. 100-company corpus는 `--results-only`로 실행했고, raw/reports
  artifacts 및 큰 상세 JSON은 `run_summary.json`으로 축약 후 삭제했다. New run
  `out/corpus/run_2026-06-05-debt-component-column-summary/`는 total checks
  68,581 -> 68,594, matched 34,818 -> 34,831, unexplained_gap 4,135 유지,
  parse_uncertain 28,927 유지, note assertion checks 6,203 -> 6,216,
  note assertion matched 5,319 -> 5,332, note assertion unresolved 764 유지,
  known layout tables 4,705 -> 4,715, unknown layout tables 36,137 -> 36,127,
  validation-relevant unknown layout items 4,824 -> 4,816으로 마감했다. Current
  footprint: `out/corpus` 약 256KB, `out` 약 15MB. Verification:
  RED/GREEN layout/orientation/candidate/workpaper-check tests, direct 현대위아
  assertion scan, full pytest 636 passed.
- Latest earnings-per-share refinement (2026-06-05):
  INVENI `주당순손익 및 배당금` 주석처럼 수익 금액은 표 단위 `천원`을 적용하지만
  `가중평균유통보통주식수`와 `주당이익(손실)`은 각각 주/원 단위로 남겨야 하는
  EPS 표를 `earnings_per_share_summary`로 분류했다. 후보 추출은 profit row에만
  table unit multiplier를 적용하고 share-count/EPS result row에는 multiplier 1을
  적용해 `profit / weighted_average_shares = EPS`를 원 단위 반올림으로 검증한다.
  INVENI 실제 샘플 직접 scan은 연결 table 121/122에서 계속영업/중단영업 4개
  matched checks를 확인했다. 100-company corpus는 `--results-only`로 실행했고,
  raw/reports artifacts 및 큰 상세 JSON은 `run_summary.json`으로 축약 후 삭제했다.
  New run `out/corpus/run_2026-06-05-eps-summary/`는 total checks 68,594 ->
  68,668, matched 34,831 -> 34,905, unexplained_gap 4,135 유지, parse_uncertain
  28,927 유지, note assertion checks 6,216 -> 6,290, note assertion matched
  5,332 -> 5,406, note assertion unresolved 764 유지, known layout tables
  4,715 -> 4,862, unknown layout tables 36,127 -> 35,980,
  validation-relevant unknown layout items 4,816 -> 4,815로 마감했다. Current
  footprint: `out/corpus` 약 252KB, `out` 약 15MB. Verification:
  RED/GREEN layout/orientation/candidate/formula/workpaper-check tests, direct
  INVENI assertion scan, full pytest 641 passed.
- Latest dividend-payout refinement (2026-06-05):
  INVENI `배당에 관한 사항`의 배당 요약표처럼 기간 열(`당기`, `전기`, `전전기`)에
  백만원 금액 행과 percent 행이 섞인 표를 `dividend_payout_summary`로 분류했다.
  후보 추출은 `(연결)당기순이익(백만원)`, `현금배당금총액(백만원)`,
  `(연결)현금배당성향(%)`을 period별로 묶고, percent 값은 parser가 소수점을
  제거해 `58.9 -> 589`로 읽는 점을 명시적으로 활용해
  `cash_dividends / net_income * 1000 = payout_ratio_tenths`를 검증한다.
  INVENI 실제 샘플 직접 scan은 table 350에서 당기/전기 2개 matched checks를
  확인했다. 100-company corpus는 `--results-only`로 실행했고, raw/reports
  artifacts 및 큰 상세 JSON은 `run_summary.json`으로 축약 후 삭제했다. New run
  `out/corpus/run_2026-06-05-dividend-payout-summary/`는 total checks 68,668 ->
  68,795, matched 34,905 -> 35,032, unexplained_gap 4,135 유지,
  parse_uncertain 28,927 유지, note assertion checks 6,290 -> 6,417,
  note assertion matched 5,406 -> 5,533, note assertion unresolved 764 유지,
  known layout tables 4,862 -> 4,961, unknown layout tables 35,980 -> 35,881,
  validation-relevant unknown layout items 4,815 -> 4,814로 마감했다. Current
  footprint: `out/corpus` 약 256KB, `out` 약 15MB. Verification:
  RED/GREEN layout/candidate/formula/workpaper-check tests, direct INVENI
  assertion scan, full pytest 645 passed.
- Latest employee-benefit-contribution-maturity refinement (2026-06-06):
  현대위아/현대비앤지스틸 `퇴직급여제도` 주석처럼 만기 bucket 열 아래
  `다음 연차보고기간 동안에 납부할 것으로 예상되는 기여금` row가 표시되는
  표를 기존 `employee_benefit_maturity_summary` 안에서
  `defined_benefit_expected_contributions` account key로 처리했다. 예상 급여
  지급액(`defined_benefit_expected_payments`)과 같은 maturity formula를 쓰되,
  실제 bucket component가 2개 이상 있는 row만 공식 검증 대상으로 삼는다. 이
  guard는 합계 단독 row를 `actual=0` 불일치로 만들던 stale pre-filter run의
  false unresolved 15건을 제거한다. Direct 100-company scan은 현대위아 4건,
  현대비앤지스틸 2건, 총 6개 matched checks와 unresolved 0건을 확인했다.
  100-company corpus는 `--results-only`로 재실행했고, raw/reports artifacts 및
  큰 상세 JSON은 `run_summary.json`으로 축약 후 삭제했다. New run
  `out/corpus/run_2026-06-06-employee-benefit-contribution-maturity-summary/`는
  baseline `out/corpus/run_2026-06-05-dividend-payout-summary/` 대비 total
  checks +6, matched +6, unexplained_gap +0, parse_uncertain +0, note assertion
  checks +6, note assertion matched +6, note assertion unresolved +0, known layout
  tables +15, unknown layout tables -15, validation-relevant unknown layout items
  -12로 마감했다. Current footprint: `out/corpus` 약 296KB,
  latest run 약 176KB, `out` 약 15MB. Verification: RED/GREEN
  layout/orientation/candidate/workpaper-check tests, direct 100-company assertion
  scan, corrected 100-company corpus run.
- Latest asset-component-column-summary refinement (2026-06-06):
  현대위아 `무형자산 및 영업권` 개발비 현황처럼 구성항목이 열(`상각자산`,
  `개발 중인 무형자산`)로 표시되고 `장부금액`이 마지막 열인 표를
  `asset_component_column_summary`로 분리했다. 이 표는 자산 잔액 증감표나
  단순 `asset_carrying_amount_total` 근거가 아니라, 행별 내부 산식
  `상각자산 + 개발 중인 무형자산 = 장부금액`을 검증하는 주석 내부 공식이다.
  후보 추출은 여러 라벨 열 중 가장 구체적인 행 라벨(`차량부품`, `특수`)을
  account key로 쓰고, 합계 row는 `무형자산 및 영업권 합계`/`부문 합계`를
  보존한다. 단위는 기존 candidate `unit_multiplier`를 그대로 적용한다
  (현대위아 표는 백만원). Direct 현대위아 scan은 note 13 table 94/326에서
  총 6개 `자산 구성열 합계 검산` matched checks와 unresolved 0건을 확인했다.
  100-company corpus는 `--results-only`로 재실행했고, 상세 JSON 및 임시 HTML과
  이전 run 디렉터리는 삭제했다. New run
  `out/corpus/run_2026-06-06-asset-component-column-summary/`는 직전
  employee-benefit run 대비 total checks +6, matched +6, unexplained_gap +0,
  parse_uncertain +0, note assertion checks +6, note assertion matched +6, note
  assertion unresolved +0, known layout tables +20, unknown layout tables -20,
  validation-relevant unknown layout items -9로 마감했다. Current footprint:
  latest run 약 256KB. Verification: RED/GREEN layout/orientation/candidate/formula/
  workpaper-check tests, direct Hyundai Wia assertion scan, 100-company corpus run,
  full pytest 655 passed.

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

- Previous implementation slice: 243-baseline A/B triage remap completed against
  `out/corpus/run_2026-06-01-codex-243-baseline-remap-default/` using the cached
  100-company manifest and no external fetch. The accepted local baseline is
  243 primary checks / 190 matched / 53 unresolved; no cash-flow primary check
  IDs are present in the local 243 unresolved taxonomy, so the 575-baseline
  Stream 1 cash-flow rows remap to `drop_575_only`. Keep/drop counts:
  keep 3, drop_575_only 30, replace_with_local_equivalent 0. Updated priority:
  T6 (`B02` 현대건설 무형 balance, `B05` 풍산 PPE balance), then S2-1
  materiality, then S2-2 cross-statement ties; T1/T2/T3/T4 need cash-flow
  primary target extraction restored before corpus-primary acceptance.
