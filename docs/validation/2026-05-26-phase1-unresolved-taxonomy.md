# Phase 1 Primary Unresolved Taxonomy

Date: 2026-05-26

## Verdict

Conditional.

The 100-company corpus now meets Gate 1 because the primary no-difference rate
is 72.87%, above the 70% target. Phase 1 still remains conditional because the
full work order requires broader 95% automatic judgment goals, lower unresolved
cash-flow coverage gaps, reviewer UI verification, and continued false-matched
review.

## Command

```bash
.venv/bin/python -m pytest -q
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-27-hundred-v81 --no-fetch
```

## Evidence

- Corpus result: `out/corpus/run_2026-05-27-hundred-v81/corpus_result.json`
- Corpus report: `out/corpus/run_2026-05-27-hundred-v81/corpus_report.md`
- Taxonomy JSON: `out/corpus/run_2026-05-27-hundred-v81/primary_unresolved_taxonomy.json`
- Taxonomy Markdown: `out/corpus/run_2026-05-27-hundred-v81/primary_unresolved_taxonomy.md`
- False matched review sample: `out/corpus/run_2026-05-27-hundred-v81/false_matched_review.md`

## Current Metrics

| Metric | Result |
|---|---:|
| Samples | 100 |
| Generated reports | 100 |
| Failed samples | 0 |
| Primary checks | 575 |
| Primary matched | 419 |
| Primary unresolved | 156 |
| Primary no-difference rate | 72.87% |
| Primary judgment rate | 100.0% |
| False matched review samples | 15 |
| Tests | 258 passed |

## Root Cause Taxonomy

| Root cause | Count |
|---|---:|
| direct_evidence_missing | 76 |
| formula_template_missing | 80 |

Top three root-cause classes explain 100.0% of primary unresolved items.

## Check-Type Concentration

| Check type | Count |
|---|---:|
| cashflow_reconciliation | 139 |
| primary_balance_reconciliation | 15 |
| expense_allocation | 2 |

## Next Bottleneck

Required next slice: reduce cash-flow reconciliation unresolved items. The
largest remaining surface is asset and financing cash-flow evidence selection:

- direct evidence missing: candidate extraction/scoring is not finding the right
  numeric note table or financing liability movement column.
- formula template missing: partial bridge terms exist, but non-cash exclusions,
  direct disposal proceeds, business-combination additions, transfers, or
  payable/receivable movements do not yet complete the formula.

Expected improvement path: if 20 of the remaining cash-flow unresolved items
can be resolved without false matches, primary matched count would improve to
439/575, lifting the no-difference rate from 72.87% to about 76.35%.

## 2026-05-27 Combined Disposal/Impairment Row Guard Delta

Implemented a quality guard for asset roll-forward rows and columns that combine
disposal with impairment:

- Labels such as `처분/폐기/손상` and `처분, 손상 및 폐기` are no longer
  classified as cash disposal carrying-amount evidence.
- Plain disposal labels such as `처분` and broader non-impairment labels such as
  `처분 및 대체 등` remain eligible.
- v80 was rejected because it only blocked combined disposal/impairment column
  headers and left combined row labels in the generic movement path. v81 is the
  accepted row/header guard.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_excludes_combined_disposal_impairment_columns -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_does_not_treat_combined_disposal_impairment_rows_as_cash_disposal -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-27-hundred-v81 --no-fetch
```

Result:

- RED tests failed before implementation because combined disposal/impairment
  labels were extracted as `disposal` movements.
- Focused input/reconciliation tests: 135 passed.
- Full tests: 258 passed.
- 100-company corpus: generated 100/100 reports.
- Delta from v79: primary checks 577 -> 575, primary matched stayed 419,
  primary unresolved 158 -> 156, primary no-difference rate 72.62% -> 72.87%,
  newly unresolved primary check IDs 0, false matched review samples 15.
- Removed low-quality primary cases: 유한양행 PPE disposal cash-flow and
  한미글로벌 PPE disposal cash-flow. Both had used combined
  disposal/impairment roll-forward rows as direct disposal carrying-amount
  evidence.
- Root cause taxonomy improved from `wrong_table_class` 2 to 0.

Interpretation:

This is accepted as evidence-quality cleanup, not a match-rate improvement. It
prevents ambiguous impairment-including roll-forward rows from being presented
as directly reproducible cash disposal evidence.

## 2026-05-27 Terse Asset Payable Direction Candidate Delta

Implemented a narrow candidate path for terse positive asset-acquisition
payable rows:

- Rows such as `유형자산취득 미지급금` now keep the existing
  `noncash_payable` candidate and also emit a separate
  `noncash_payable_decrease_candidate`.
- The decrease candidate is only added for positive, terse, asset acquisition
  payable labels that do not already state `증가`, `감소`, `변동`, `관련`, or
  `따른`.
- The reconciliation engine can select the candidate direction that completes
  the bridge, instead of globally changing payable sign semantics.
- v78 was rejected because a global sign flip resolved 한화오션 but regressed
  five previously matched asset acquisition checks. v79 is the accepted
  narrower implementation.

Verification:

```bash
.venv/bin/python -m pytest tests/test_checks_reconciliation.py::test_check_reconciliation_targets_treats_terse_positive_asset_payable_as_decrease -q
.venv/bin/python -m pytest tests/test_checks_reconciliation.py::test_check_reconciliation_targets_treats_terse_positive_asset_payable_as_decrease tests/test_checks_reconciliation.py::test_check_reconciliation_targets_adjusts_acquisition_for_noncash_payable tests/test_checks_reconciliation.py::test_check_reconciliation_targets_keeps_terse_negative_payable_change_as_decrease -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-27-hundred-v79 --no-fetch
```

Result:

- RED test failed before implementation because the terse positive payable row
  remained an unexplained acquisition cash-flow gap.
- Focused guard tests: 3 passed.
- Focused input/reconciliation tests: 133 passed.
- Full tests: 256 passed.
- 100-company corpus: generated 100/100 reports.
- Delta from v77: primary matched 418 -> 419, primary unresolved 159 -> 158,
  primary no-difference rate 72.44% -> 72.62%, newly unresolved primary check
  IDs 0, false matched review samples 15.
- Resolved primary case: 한화오션 PPE acquisition cash-flow now matches within
  disclosure precision: note acquisition `373,337,000,000` plus payable
  decrease candidate `303,000,000` equals `373,640,000,000` versus CFS PPE
  acquisition `373,640,224,794`.
- Changed-still-unresolved cases improved but remain open: 한화솔루션 PPE
  acquisition residual `14,826,000,000 -> 6,529,000,000`, 한일시멘트 PPE
  acquisition residual `18,137,000,000 -> 11,105,000,000`, and 후성 PPE
  acquisition residual `19,739,000,000 -> 15,787,000,000`.

Interpretation:

This is accepted as a direction-ambiguity improvement for terse non-cash
payable labels. The accepted pattern is additive candidate generation, not a
global sign flip.

## 2026-05-26 Lease Liability Interest Adjustment Delta

Implemented lease-liability financing cash-flow interest adjustment extraction:

- Rows labeled `리스부채에 대한 이자비용` in scoped lease-liability notes now
  enter the lease-liability financing candidate pool as `리스부채 이자비용 조정`.
- Financing reconciliation requires at least one non-adjustment financing
  movement, so adjustment-only evidence cannot create a new primary check.
- v76 was rejected because an earlier adjustment-only version introduced three
  new unresolved lease-liability primary checks; v77 adds the guard.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_reads_lease_interest_financing_adjustment tests/test_checks_reconciliation.py::test_check_reconciliation_targets_reconciles_lease_principal_using_interest_adjustment -q
.venv/bin/python -m pytest tests/test_checks_reconciliation.py::test_check_reconciliation_targets_does_not_create_lease_financing_check_from_interest_only -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-26-hundred-v77 --no-fetch
```

Result:

- RED tests failed before implementation/restriction: extraction and final
  reconciliation initially missed the lease interest adjustment, and the guard
  initially allowed adjustment-only checks.
- Focused input/reconciliation tests: 132 passed.
- Full tests: 255 passed.
- 100-company corpus: generated 100/100 reports.
- Delta from v75: primary matched 417 -> 418, primary unresolved 160 -> 159,
  primary no-difference rate 72.27% -> 72.44%, newly unresolved primary check
  IDs 0, false matched review samples 15.
- Resolved primary case: 지누스 lease-liability financing cash-flow now matches
  within disclosure precision: `3,281,644,000 + (18,161,527,000) =
  (14,879,883,000)` versus CFS lease principal repayment `(14,879,882,698)`.

Interpretation:

This is accepted as a lease-liability bridge improvement. It handles the common
case where the financing-liability roll-forward cash-flow column includes lease
interest but the cash-flow statement target is principal repayment only.

## 2026-05-26 Financing Inflow/Outflow Column Delta

Implemented `유입`/`유출` action-column semantics for financing liability
roll-forward tables:

- Columns labeled `유입` and `유출` are now treated as financing cash-flow
  action columns, like `증가`/`감소`.
- `유출` is normalized as an outflow even when the source table displays it as
  a positive amount; parenthesized source amounts remain negative.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_reads_financing_inflow_and_outflow_columns -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-26-hundred-v75 --no-fetch
```

Result:

- RED test failed before implementation because `유출` repayment columns were
  ignored and some rows fell back to ending balances.
- Focused input/reconciliation tests: 129 passed.
- Full tests: 252 passed.
- 100-company corpus: generated 100/100 reports.
- Delta from v74: primary matched 416 -> 417, primary unresolved 161 -> 160,
  primary no-difference rate 72.10% -> 72.27%, newly unresolved primary check
  IDs 0, false matched review samples 15.
- Resolved primary case: 계양전기 borrowings financing cash-flow now matches
  exactly with `75,788,499,000 - 46,830,000,000 + 8,000,000,000 =
  36,958,499,000`.

Interpretation:

This is accepted as a financing liability column-semantic improvement. It
captures a common financing roll-forward layout where cash inflows/outflows are
named directly rather than with `증가`/`감소` or `현금흐름` headers.

## 2026-05-26 Acquisition Note Payable Delta

Implemented `지급어음` acquisition adjustment extraction for non-cash asset
acquisition tables:

- Rows such as `유형자산 취득관련 지급어음의 증가(감소)` are now classified
  as payable-style non-cash acquisition obligations.
- The adjustment uses the existing payable delta direction semantics, so a
  negative displayed change is added back to cash acquisition in the same way as
  a payable decrease.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_reads_asset_note_payable_adjustments -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-26-hundred-v74 --no-fetch
```

Result:

- RED test failed before implementation because the `지급어음` row was ignored.
- Focused input/reconciliation tests: 128 passed.
- Full tests: 251 passed.
- 100-company corpus: generated 100/100 reports.
- Delta from v73: primary matched stayed 416, primary unresolved stayed 161,
  primary no-difference rate stayed 72.10%, newly unresolved primary check IDs
  0, false matched review samples 15.
- Changed-still-unresolved primary case: 현대위아 PPE acquisition cash-flow
  now includes `유형자산 취득관련 지급어음의 증가(감소)` evidence and the
  residual improved from 853,000,000 to 441,000,000.

Interpretation:

This is accepted as an evidence-quality improvement. It does not close a
primary item yet, but it captures a real non-cash acquisition obligation that
belongs in the cash-basis acquisition bridge and introduces no corpus
regression.

## 2026-05-26 Net Disposal Gain/Loss Sign Delta

Implemented signed net disposal gain/loss handling for disposal cash-flow
bridges:

- Generic `처분손익` rows from a different note than the asset roll-forward are
  treated as net operating cash-flow adjustments and use their signed direction.
  A positive net `처분손익` adjustment is therefore subtracted from disposal
  carrying amount when deriving cash proceeds.
- Explicit `처분이익` rows still add to disposal carrying amount, and explicit
  `처분손실` rows still subtract from it.
- Asset-note disposal-gain/loss rows remain on the existing gross formula path;
  the sign reversal is limited to cross-note generic net `처분손익` adjustments.

Verification:

```bash
.venv/bin/python -m pytest tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-26-hundred-v73 --no-fetch
```

Result:

- RED test failed before implementation because a positive generic
  `유형자산처분손익` adjustment was added instead of subtracted.
- Focused reconciliation tests: 64 passed.
- Focused input/reconciliation tests: 127 passed.
- Full tests: 250 passed.
- 100-company corpus: generated 100/100 reports.
- Delta from v71: primary matched 414 -> 416, primary unresolved 163 -> 161,
  primary no-difference rate 71.75% -> 72.10%, newly unresolved primary check
  IDs 0, false matched review samples 15.
- Resolved primary cases: 삼성SDI PPE disposal cash-flow and 효성화학 PPE
  disposal cash-flow.

Interpretation:

This is accepted as a formula-sign improvement. Generic net disposal gain/loss
adjustments in operating cash-flow notes are not the same source shape as
explicit income-statement `처분이익`/`처분손실` rows, so the cash bridge must
preserve the net adjustment direction instead of forcing an absolute add-back.

## 2026-05-26 Borrowing Net-Change CFS Sign Delta

Implemented signed net-change handling for borrowing CFS rows:

- CFS labels such as `단기차입금의 순증감` now keep their displayed sign instead
  of being normalized as borrowing proceeds from the `차입금` substring.
- Borrowing net-change rows are included in financing liability net
  reconciliation alongside proceeds and repayments.
- This applies only to explicit `순증감` rows. Ordinary `차입`, `증가`, `상환`,
  and `감소` rows keep the existing directional sign normalization.

Verification:

```bash
.venv/bin/python -m pytest tests/test_checks_reconciliation.py::test_check_reconciliation_targets_preserves_signed_borrowing_net_change_cashflow -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-26-hundred-v71 --no-fetch
```

Result:

- RED test failed before implementation because the negative CFS net-change row
  was flipped to a positive proceeds amount.
- Focused tests: 126 passed.
- Full tests: 249 passed.
- 100-company corpus: generated 100/100 reports.
- Delta from v70: primary matched 412 -> 414, primary unresolved 165 -> 163,
  primary no-difference rate 71.40% -> 71.75%, newly unresolved primary check
  IDs 0, false matched review samples 15.
- Resolved primary cases: 삼성E&A borrowings financing cash-flow and
  현대코퍼레이션 borrowings financing cash-flow.

Interpretation:

This is accepted as a sign-fidelity improvement. A net-change CFS row is already
an aggregated signed cash-flow amount, so the extractor should preserve the
source sign rather than infer a proceeds/repayment direction from a substring.

## 2026-05-26 Non-Principal Debt Fee/Refund CFS Delta

Implemented a narrow financing CFS target guard for non-principal debt rows:

- `차입금중도상환수수료의 지급` is excluded from borrowings financing cash-flow
  extraction because it is an early repayment fee, not principal borrowing
  movement.
- `사채발행분담금의 반환` is excluded from bonds financing cash-flow extraction
  because it is a levy/refund row, not principal bond movement.
- The prior v69 distinction is preserved: `사채발행비 지급` remains a bonds
  financing cash outflow when the liability roll-forward includes it, while
  generic `사채발행비용` remains excluded.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_excludes_non_principal_debt_fee_and_refund_rows -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-26-hundred-v70 --no-fetch
```

Result:

- RED test failed before implementation because both rows were still classified
  as financing cash-flow lines.
- Focused tests: 125 passed.
- Full tests: 248 passed.
- 100-company corpus: generated 100/100 reports.
- Delta from v69: primary matched 410 -> 412, primary unresolved 167 -> 165,
  primary no-difference rate 71.06% -> 71.40%, newly unresolved primary check
  IDs 0, false matched review samples 15.
- Resolved primary cases: 롯데하이마트 borrowings financing cash-flow and
  롯데하이마트 bonds financing cash-flow.

Interpretation:

This is accepted as a target-quality improvement. It does not ignore cash flow
generally; it prevents ancillary debt fee/refund rows from being treated as
principal financing liability movements in primary liability reconciliation.

## 2026-05-26 Asset Formula Delta

Implemented a limited acquisition adjustment subset rule for explicit
`business_combination` note movements:

- If the direct acquisition row already matches the cash-flow statement, the
  business-combination row is not forced into the formula.
- If excluding a clearly labeled business-combination acquisition improves the
  formula, the row is included as a subtractive term.
- The search space is intentionally limited to compatible extracted adjustment
  rows; it does not use arbitrary amounts.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/python -c "from dart_footing_reconciler.corpus import run_workpaper_corpus; p=run_workpaper_corpus('out/corpus/manifest_2026-05-26-hundred.json','out/corpus/run_2026-05-26-hundred-v2',fetch_missing=False); print(p['summary'])"
```

Result:

- Focused tests: 48 passed.
- Full tests: 168 passed.
- 100-company corpus: primary matched 273 / primary unresolved 236, unchanged
  from the Phase 1 baseline.

Interpretation:

This change prevents a false-negative class introduced by blindly applying
business-combination exclusions, but it does not materially move Gate 1. The
next higher-yield target remains candidate extraction/scoring for direct asset
cash-flow evidence and financing liability movement columns.

## 2026-05-26 Financing Liability Column Delta

Implemented conservative extraction for financing liability roll-forward tables:

- Split `재무현금흐름 증가` / `재무현금흐름 감소` columns are both read instead of only the first cash-flow column.
- Row-driven tables where the row is a financing cash-flow movement and the columns are `단기차입금`, `장기차입금`, `사채`, or `리스부채` are expanded into account-level movement evidence.
- Combined `재무현금흐름 ... 증가(감소)` net columns preserve the signed cell amount; the sign is not flipped merely because the header contains `(감소)`.
- Generic borrowing detail tables are excluded unless the heading or header has an explicit financing-liability roll-forward context.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/python -c "from dart_footing_reconciler.corpus import run_workpaper_corpus; p=run_workpaper_corpus('out/corpus/manifest_2026-05-26-hundred.json','out/corpus/run_2026-05-26-hundred-v3',fetch_missing=False); print(p['summary'])"
```

Result:

- Focused tests: 51 passed.
- Full tests: 171 passed.
- 100-company corpus: primary matched 277 / primary unresolved 234.
- Delta from v2: primary checks 509 -> 511, primary matched 273 -> 277, primary unresolved 236 -> 234, no-difference rate 53.6% -> 54.2%.

Interpretation:

This is a small but real Gate 1 movement. The change is intentionally narrow:
it uses only explicit financing-liability roll-forward tables and avoids
promoting unrelated borrowing detail tables into cash-flow evidence.

## 2026-05-26 Disposal Gain/Loss Formula Delta

Implemented a conservative disposal cash-flow formula expansion:

- Asset disposal gain/loss rows are now extracted from explicit income/expense notes such as `기타수익`, `기타비용`, `기타영업외수익`, and `기타영업외비용`, not only from operating cash-flow adjustment tables.
- Disposal formulas use a limited subset search over compatible carrying amount, disposal gain/loss, and non-cash receivable candidates.
- Duplicate adjustment candidates with the same role and absolute amount are not double-counted, preventing the same loss/gain from being used once from the income note and again from the operating cash-flow adjustment note.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/python -c "from dart_footing_reconciler.corpus import run_workpaper_corpus; p=run_workpaper_corpus('out/corpus/manifest_2026-05-26-hundred.json','out/corpus/run_2026-05-26-hundred-v4',fetch_missing=False); print(p['summary'])"
```

Result:

- Focused tests: 54 passed.
- Full tests: 174 passed.
- 100-company corpus: primary matched 281 / primary unresolved 230.
- Delta from v3: primary matched 277 -> 281, primary unresolved 234 -> 230, no-difference rate 54.2% -> 55.0%.
- Resolved primary cases: 현대자동차 PPE disposal, 동부건설 intangible disposal, 롯데칠성음료 intangible disposal, 효성화학 intangible disposal.
- False-match guard sample: 한화오션 intangible disposal remains unresolved because the same `무형자산처분손실` amount appears in both income/expense and operating cash-flow adjustment notes and is not double-counted.

Interpretation:

This moves Gate 1 modestly while preserving the false-matched-zero posture.
The next largest unresolved class remains asset acquisition cash-flow, especially
mixed asset-family labels, non-cash payable/receivable adjustments, and cases
where the note movement table carries only accrual-basis additions.

## 2026-05-26 Acquisition Candidate Selection Delta

Implemented a conservative primary acquisition movement selection rule:

- When an asset note has multiple acquisition rows for the same account, the
  acquisition row closest to the cash-flow statement amount is selected as the
  primary movement instead of blindly taking the first row.
- The rule is intentionally limited to acquisition cash-flow checks. Disposal
  checks still keep the first carrying-amount movement because disposal proceeds
  may require adding gain/loss adjustments; choosing the closest carrying amount
  can create regressions.
- A disposal regression guard test covers this distinction.

Verification:

```bash
.venv/bin/python -m pytest tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/python -c "from dart_footing_reconciler.corpus import run_workpaper_corpus; p=run_workpaper_corpus('out/corpus/manifest_2026-05-26-hundred.json','out/corpus/run_2026-05-26-hundred-v5',fetch_missing=False); print(p['summary'])"
```

Result:

- Focused tests: 27 passed.
- Full tests: 176 passed.
- 100-company corpus: primary matched 282 / primary unresolved 229.
- Delta from v4: primary matched 281 -> 282, primary unresolved 230 -> 229, no-difference rate 55.0% -> 55.2%.
- Resolved primary case: 광주신세계 intangible asset acquisition cash-flow.
- Newly unresolved primary cases: 0.

Interpretation:

This is a small but clean improvement. It fixes a candidate-order false
negative where a zero acquisition row appeared before the current acquisition
row. It does not solve the larger acquisition formula gap, where the remaining
cases still need stronger evidence for non-cash payable direction, mixed asset
families, and direct cash-basis acquisition tables.

## 2026-05-26 Combined Asset Non-Cash Payable Delta

Implemented conservative extraction for combined `유무형자산` non-cash payable
rows:

- Rows such as `유ㆍ무형자산 취득 관련 미지급금 변동` are added to both the PPE
  and intangible asset candidate pools.
- The candidate is not forced into either formula. Existing subset selection
  uses it only when it improves the target cash-flow reconciliation.
- A regression test confirms that a directly matched intangible acquisition
  remains direct even when the combined payable row is available.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/python -c "from dart_footing_reconciler.corpus import run_workpaper_corpus; p=run_workpaper_corpus('out/corpus/manifest_2026-05-26-hundred.json','out/corpus/run_2026-05-26-hundred-v6',fetch_missing=False); print(p['summary'])"
```

Result:

- Focused tests: 57 passed.
- Full tests: 177 passed.
- 100-company corpus: primary matched 283 / primary unresolved 228.
- Delta from v5: primary matched 282 -> 283, primary unresolved 229 -> 228, no-difference rate 55.2% -> 55.4%.
- Resolved primary case: 광주신세계 PPE acquisition cash-flow.
- Newly unresolved primary cases: 0.
- Additional status movement: 5 primary unresolved items gained formula evidence and moved within unresolved/explainable classifications.

Interpretation:

This is another small but clean movement. The rule is aligned with the target
formula engine because it adds a semantically compatible candidate to the pool
without treating combined asset-family labels as direct evidence by themselves.

## 2026-05-26 Payable Direction Label Delta

Implemented semantic direction handling for non-cash payable labels:

- `미지급금의 감소(증가)` is treated as a payable decrease even when the
  disclosed amount is positive.
- `미지급금의 증가(감소)` is treated as a payable increase even when the
  disclosed amount is positive.
- Existing signed disclosures without this paired direction label continue to
  use the parsed sign.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/python -c "from dart_footing_reconciler.corpus import run_workpaper_corpus; p=run_workpaper_corpus('out/corpus/manifest_2026-05-26-hundred.json','out/corpus/run_2026-05-26-hundred-v7',fetch_missing=False); print(p['summary'])"
```

Result:

- Focused tests: 58 passed.
- Full tests: 178 passed.
- 100-company corpus: primary matched 284 / primary unresolved 227.
- Delta from v6: primary matched 283 -> 284, primary unresolved 228 -> 227, no-difference rate 55.4% -> 55.6%.
- Resolved primary case: GS리테일 intangible asset acquisition cash-flow.
- Newly unresolved primary cases: 0.
- Changed still-unresolved primary cases: 0.

Interpretation:

This moves one more acquisition case without broadening tolerance or using a
company-specific rule. The rule is grounded in the row label itself, so it is
safer than globally flipping payable signs.

## 2026-05-26 Right-of-Use Asset Acquisition Delta

Implemented a conservative lease/right-of-use asset exclusion for PPE
acquisition cash-flow formulas:

- Tables explicitly headed `사용권자산` now contribute
  `right_of_use_noncash_acquisition` adjustment candidates for PPE acquisition
  checks.
- The adjustment is subtractive and is selected only when it improves the
  target acquisition formula.
- Disposal gain/loss extraction remains on the existing row-label logic; this
  prevents the ROU slice from regressing disposal formulas.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/python -c "from dart_footing_reconciler.corpus import run_workpaper_corpus; p=run_workpaper_corpus('out/corpus/manifest_2026-05-26-hundred.json','out/corpus/run_2026-05-26-hundred-v8',fetch_missing=False); print(p['summary'])"
```

Result:

- Focused tests: 59 passed.
- Full tests: 179 passed.
- 100-company corpus: primary matched 285 / primary unresolved 226.
- Delta from v7: primary matched 284 -> 285, primary unresolved 227 -> 226, no-difference rate 55.6% -> 55.8%.
- Resolved primary case: 삼성SDI PPE acquisition cash-flow.
- Newly unresolved primary cases: 0.
- Additional status movement: 6 PPE acquisition items gained ROU/formula evidence while remaining unresolved.

Interpretation:

This directly implements the work-order formula term
`- 리스/사용권자산 비현금 취득`. The extraction is intentionally limited to
right-of-use asset tables and PPE acquisition formulas to avoid using lease
tables as generic acquisition evidence.

## 2026-05-26 Non-Cash Current-Period Label Delta

Implemented a narrow label fix for non-cash asset payable rows while restoring
the disposal label guard:

- Non-cash `현금의 유입과 유출이 없는 거래` rows use the first column as the
  semantic label, so `라벨 / 당기 / 전기` tables classify current-period
  acquisition payable rows correctly instead of treating the current-period
  amount as the label.
- Disposal gain/loss adjustment extraction keeps `_row_label(row)`, preserving
  support for income/expense notes where the first column is a category and the
  second column contains `유형자산처분이익` or `무형자산처분손실`.
- A rejected v9 run showed the risk: applying first-column label logic too
  broadly regressed disposal formulas. The accepted v10b run has no newly
  unresolved primary cases versus v8.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_reads_income_statement_note_disposal_adjustments tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_reads_noncash_asset_payable_adjustments -q
.venv/bin/python -m pytest -q
.venv/bin/python -c "from dart_footing_reconciler.corpus import run_workpaper_corpus; p=run_workpaper_corpus('out/corpus/manifest_2026-05-26-hundred.json','out/corpus/run_2026-05-26-hundred-v10b',fetch_missing=False); print(p['summary'])"
```

Result:

- Focused tests: 2 passed.
- Full tests: 179 passed.
- 100-company corpus: primary matched 288 / primary unresolved 223.
- Delta from v8: primary matched 285 -> 288, primary unresolved 226 -> 223, no-difference rate 55.8% -> 56.4%.
- Resolved primary cases: HS애드 intangible acquisition, HS애드 PPE acquisition, 신세계I&C intangible acquisition.
- Newly unresolved primary cases: 0.
- Changed still-unresolved primary cases: 4; all moved toward smaller formula-backed differences or `explainable_gap`.

Interpretation:

This is a clean acquisition-formula improvement. The accepted change keeps
non-cash payable extraction precise enough for multi-period tables while
avoiding the disposal regression observed in the rejected v9 experiment.

## 2026-05-26 Non-Cash Transfer Acquisition Delta

Implemented a conservative non-cash transfer acquisition adjustment for
intangible asset acquisition formulas:

- Non-cash transaction rows such as `건설중인자산의 무형자산 대체` are extracted
  as `noncash_transfer_acquisition` candidates for intangible assets.
- Acquisition formulas treat the candidate as a subtractive term, because the
  note movement row may include non-cash account transfers in `당기취득(계정대체 포함)`.
- The rule is currently limited to labels that explicitly name `무형자산` and
  `대체`; generic current/non-current reclassifications and lease liability
  transfers are not promoted into asset acquisition formulas.

Verification:

```bash
.venv/bin/python -m pytest -q tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_reads_noncash_intangible_transfer_adjustments tests/test_checks_reconciliation.py::test_check_reconciliation_targets_excludes_noncash_transfer_from_acquisition_cash_basis
.venv/bin/python -m pytest -q tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py
.venv/bin/python -m pytest -q
.venv/bin/python -c "from dart_footing_reconciler.corpus import run_workpaper_corpus; p=run_workpaper_corpus('out/corpus/manifest_2026-05-26-hundred.json','out/corpus/run_2026-05-26-hundred-v11',fetch_missing=False); print(p['summary'])"
```

Result:

- RED tests failed as expected before implementation.
- Focused RED/GREEN tests: 2 passed.
- Reconciliation focused tests: 61 passed.
- Full tests: 181 passed.
- 100-company corpus: primary matched 289 / primary unresolved 222.
- Delta from v10b: primary matched 288 -> 289, primary unresolved 223 -> 222, no-difference rate 56.4% -> 56.6%.
- Resolved primary case: 삼익THK intangible acquisition cash-flow.
- Newly unresolved primary cases: 0.
- Changed still-unresolved primary cases: 3; all gained formula evidence and smaller differences.

Interpretation:

This directly improves the acquisition formula engine without broadening
tolerance or using company-specific logic. The next acquisition slice should
focus on remaining direct-evidence-missing cases where the cash-flow line is a
direct cash-basis table amount rather than a roll-forward acquisition row.

## 2026-05-26 Note Heading Unit Colon Delta

Fixed a parser unit-loss bug in note headings that contain `단위:`:

- `_strip_heading_tail()` no longer treats the colon in `단위: 천원` as a
  generic title separator.
- This preserves note heading text such as `... (단위: 천원)` so downstream
  table extraction applies the correct `unit_multiplier`.
- The change is source-fidelity aligned: some still-unresolved 한미글로벌
  differences became larger because the prior run was using unscaled note
  amounts, but the corrected v12 values now match the original report unit.

Verification:

```bash
.venv/bin/python -m pytest -q tests/test_document.py::test_parse_full_report_preserves_note_heading_unit_after_colon
.venv/bin/python -m pytest -q tests/test_document.py
.venv/bin/python -m pytest -q
.venv/bin/python -c "from dart_footing_reconciler.corpus import run_workpaper_corpus; p=run_workpaper_corpus('out/corpus/manifest_2026-05-26-hundred.json','out/corpus/run_2026-05-26-hundred-v12',fetch_missing=False); print(p['summary'])"
```

Result:

- RED test failed as expected before implementation.
- Focused document test: 1 passed.
- Document parser tests: 20 passed.
- Full tests: 182 passed.
- 100-company corpus: primary matched 291 / primary unresolved 220.
- Delta from v11: primary matched 289 -> 291, primary unresolved 222 -> 220, no-difference rate 56.6% -> 56.9%.
- Resolved primary cases: 한미글로벌 intangible balance, 한미글로벌 PPE acquisition cash-flow.
- Newly unresolved primary cases: 0.

Interpretation:

This is an input-structuring improvement rather than a formula heuristic. It
reduces false gaps caused by unit loss while keeping unresolved classifications
when corrected source amounts still do not complete the reconciliation.

## 2026-05-26 Roll-Forward Movement Column Coverage Delta

Implemented extraction for wide roll-forward tables where movement roles live
in column headers and total rows identify the account family:

- Reads total rows such as `유형자산 합계` or `무형자산 합계` and movement
  columns such as `취득 등`, `처분`, and `사업결합으로 인한 증가`.
- Excludes beginning, ending, carrying amount, and `취득원가` columns from
  movement evidence.
- Excludes `정부보조금` rows from row-label movement classification so grant
  tables do not become primary acquisition evidence.
- Adds the newly extracted movement evidence as ordinary candidates; it does
  not loosen `matched` or tolerance.

Verification:

```bash
.venv/bin/python -m pytest -q tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_reads_rollforward_movement_columns_from_total_row tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_excludes_government_grant_acquisition_rows
.venv/bin/python -m pytest -q tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py
.venv/bin/python -m pytest -q
.venv/bin/python -c "from dart_footing_reconciler.corpus import run_workpaper_corpus; p=run_workpaper_corpus('out/corpus/manifest_2026-05-26-hundred.json','out/corpus/run_2026-05-26-hundred-v13',fetch_missing=False); print(p['summary'])"
```

Result:

- RED tests failed as expected before implementation.
- Focused RED/GREEN tests: 2 passed.
- Reconciliation focused tests: 63 passed.
- Full tests: 184 passed.
- 100-company corpus: primary checks 540, matched 303, unresolved 237.
- Delta from v12: primary checks 511 -> 540, matched 291 -> 303,
  unresolved 220 -> 237, no-difference rate 56.9% -> 56.1%,
  `cashflow_target_sparse` 22 -> 19.
- Newly generated primary checks: 29, of which 12 matched and 17 unresolved.
- Existing 롯데이노베이트 PPE acquisition evidence improved from government
  grant to roll-forward total acquisition: 10,000,000 -> 68,096,018,000;
  difference improved from about 63.29 billion to about 4.79 billion.

Interpretation:

This is a coverage and fidelity expansion, not a no-difference-rate improvement.
The denominator expanded because previously sparse roll-forward checks now have
primary movement evidence. The next slice should add formula adjustments for
the newly exposed roll-forward checks, including right-of-use assets, accrual
payables, government-grant contra columns, transfers, and other non-cash
movement columns where the note bridge is explicit.

## 2026-05-26 Cash-Flow Formula Rounding Tolerance Delta

Implemented source-precision accumulation for cash-flow formula checks:

- Single-amount cash-flow checks keep the existing unit tolerance.
- When a cash-flow bridge uses multiple note formula components, the effective
  tolerance accumulates each component's source precision.
- This reflects the source tables: if three disclosed note amounts are each in
  thousands of won, the recomputed formula can differ from a won-denominated
  cash-flow statement line by the sum of those source precisions.
- The rule is limited to source precision from amounts actually used in the
  formula. It does not change status when differences exceed the accumulated
  precision, and it does not alter formula candidate selection.

Verification:

```bash
.venv/bin/python -m pytest -q tests/test_checks_reconciliation.py::test_check_reconciliation_targets_accumulates_rounding_tolerance_for_cashflow_formula_components tests/test_checks_reconciliation.py::test_check_reconciliation_targets_does_not_allow_million_tolerance_for_thousand_unit_amount
.venv/bin/python -m pytest -q tests/test_checks_reconciliation.py tests/test_reconciliation_inputs.py
.venv/bin/python -m pytest -q
.venv/bin/python -c "from dart_footing_reconciler.corpus import run_workpaper_corpus; p=run_workpaper_corpus('out/corpus/manifest_2026-05-26-hundred.json','out/corpus/run_2026-05-26-hundred-v14',fetch_missing=False); print(p['summary'])"
```

Result:

- RED test failed as expected before implementation.
- Focused RED/GREEN tests: 2 passed.
- Reconciliation focused tests: 64 passed.
- Full tests: 185 passed.
- 100-company corpus: primary checks 540, matched 305, unresolved 235.
- Delta from v13: matched 303 -> 305, unresolved 237 -> 235,
  no-difference rate 56.1% -> 56.5%, newly unresolved primary cases 0.
- Resolved primary cases: 애경케미칼 PPE disposal cash-flow and 애경케미칼
  intangible disposal cash-flow.

Interpretation:

This is a source precision fix, not a tolerance relaxation. It converts only
formula rows where the residual difference is within the accumulated rounding
precision of the disclosed note amounts used in the bridge.

## 2026-05-26 Asset Receivable/Payable CFS Target Guard Delta

Implemented a cash-flow statement target guard for asset-related receivable and
payable movement rows:

- Rows such as `기타채무(유형자산 취득)의 증가(감소)` and
  `기타채권(유형자산 처분)의 감소(증가)` are no longer classified as primary
  PPE acquisition/disposal cash-flow targets.
- Direct asset lines such as `유형자산의 취득` and `유형자산의 처분` remain
  classified as primary asset cash-flow targets.
- The rule is based on row-label semantics, not company names. It excludes
  receivable/payable movement rows only when they also reference PPE or
  intangible assets.

Verification:

```bash
.venv/bin/python -m pytest -q tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_excludes_asset_receivable_payable_cfs_rows_from_primary_asset_cashflows
.venv/bin/python -m pytest -q tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py
.venv/bin/python -m pytest -q
.venv/bin/python -c "from dart_footing_reconciler.corpus import run_workpaper_corpus; p=run_workpaper_corpus('out/corpus/manifest_2026-05-26-hundred.json','out/corpus/run_2026-05-26-hundred-v15',fetch_missing=False); print(p['summary'])"
```

Result:

- RED test failed as expected before implementation.
- Focused RED/GREEN test: 1 passed.
- Reconciliation focused tests: 65 passed.
- Full tests: 186 passed.
- 100-company corpus: primary checks 540, matched 306, unresolved 234.
- Delta from v14: matched 305 -> 306, unresolved 235 -> 234,
  no-difference rate 56.5% -> 56.7%, newly unresolved primary cases 0.
- Resolved primary case: 하이트진로홀딩스 PPE acquisition cash-flow.
- Existing 하이트진로홀딩스 PPE disposal remains unresolved, but the target
  changed from a `기타채권(유형자산 처분)` movement row to the direct
  `유형자산의 처분` line, improving target fidelity.

Interpretation:

This is a target-quality fix. It prevents asset receivable/payable settlement
rows from becoming the primary asset acquisition/disposal target while keeping
direct asset cash-flow lines in scope.

## 2026-05-26 Asset Subtype CFS Target Guard Delta

Implemented a second cash-flow statement target guard for asset subtype rows:

- Rows such as `건설중인 유형자산의 취득`, `기타유형자산의 처분`,
  `기타무형자산의 취득`, and `무형자산 등의 처분` are no longer classified
  as primary total PPE/intangible acquisition or disposal targets.
- Direct total-asset rows such as `유형자산의 취득`, `유형자산의 처분`,
  and `무형자산의 취득` remain classified.
- The guard avoids comparing a partial cash-flow line to a whole PPE/intangible
  note roll-forward.

Verification:

```bash
.venv/bin/python -m pytest -q tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_excludes_asset_subtype_cfs_rows_from_primary_asset_cashflows tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_separates_statement_note_and_cfs_sources
.venv/bin/python -m pytest -q tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py
.venv/bin/python -m pytest -q
.venv/bin/python -c "from dart_footing_reconciler.corpus import run_workpaper_corpus; p=run_workpaper_corpus('out/corpus/manifest_2026-05-26-hundred.json','out/corpus/run_2026-05-26-hundred-v16',fetch_missing=False); print(p['summary'])"
```

Result:

- RED test failed as expected before implementation.
- Focused RED/GREEN tests: 2 passed.
- Reconciliation focused tests: 66 passed.
- Full tests: 187 passed.
- 100-company corpus: primary checks 533, matched 305, unresolved 228.
- Delta from v15: primary checks 540 -> 533, matched 306 -> 305,
  unresolved 234 -> 228, no-difference rate 56.7% -> 57.2%.
- Removed low-quality primary unresolved targets: DL이앤씨 PPE acquisition,
  DL이앤씨 PPE disposal, 신세계인터내셔날 PPE acquisition, 신세계인터내셔날
  PPE disposal, 자이에스앤디 intangible acquisition, 한화솔루션 intangible
  disposal.
- Removed matched primary targets: 1. This is accepted as target-quality
  cleanup because the removed line was a partial asset subtype cash-flow line,
  not a total asset cash-flow target.
- Newly unresolved primary cases: 0.

Interpretation:

This is a target-scope fix rather than a formula improvement. It raises corpus
fidelity by removing partial asset lines from total-asset primary targets, even
though it also removes one prior matched item that was not a robust whole-asset
reconciliation.

## 2026-05-26 Financing Cash-Flow Subset Selection Delta

Implemented conservative subset selection for financing cash-flow note
movements:

- When a financing liability note contains multiple cash-flow movements for the
  same account, the checker may use a subset only if that subset agrees to the
  CFS target within effective tolerance and improves over the full note sum.
- If no subset matches within tolerance, the checker keeps all note movements
  and preserves the unresolved gap.
- The selection is capped at 10 note movements to avoid broad combinatorial
  matching.

Verification:

```bash
.venv/bin/python -m pytest -q tests/test_checks_reconciliation.py
.venv/bin/python -m pytest -q tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py tests/test_reconciliation_targets.py
.venv/bin/python -m pytest -q
.venv/bin/python -c "from dart_footing_reconciler.corpus import run_workpaper_corpus; p=run_workpaper_corpus('out/corpus/manifest_2026-05-26-hundred.json','out/corpus/run_2026-05-26-hundred-v17',fetch_missing=False); print(p['summary'])"
```

Result:

- RED test failed as expected before implementation.
- Focused reconciliation tests: 69 passed.
- Full tests: 189 passed.
- 100-company corpus: primary checks 533, matched 315, unresolved 218.
- Delta from v16: matched 305 -> 315, unresolved 228 -> 218,
  no-difference rate 57.2% -> 59.1%.
- Newly unresolved primary cases: 0.
- Resolved financing cash-flow checks: 신세계인터내셔날 bonds,
  풍산홀딩스 lease liabilities, 삼익THK borrowings, 한화시스템 bonds,
  이지스레지던스리츠 borrowings/bonds, 롯데에너지머티리얼즈 borrowings,
  신세계I&C borrowings, 금호에이치티 lease liabilities/borrowings.

Interpretation:

This is a formula-evidence selection fix. It handles cases where the financing
liability reconciliation note discloses both inflow and outflow rows while the
CFS target covers only one matching financing line or matching line group. It
does not loosen tolerance and does not infer a near-match when no subset agrees
within tolerance.

## 2026-05-26 Zero-Amount CFS Target Guard Delta

Implemented a cash-flow statement target guard for zero-amount rows:

- CFS rows classified as asset acquisition/disposal or financing proceeds/
  repayment are excluded from primary target extraction when the current-period
  amount is zero.
- Non-zero rows in the same CFS table remain classified.
- This avoids comparing disclosure-only or empty zero rows to note roll-forward
  movements as if a cash transaction existed.

Verification:

```bash
.venv/bin/python -m pytest -q tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_excludes_zero_amount_cfs_rows_from_primary_cashflows
.venv/bin/python -m pytest -q tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py tests/test_reconciliation_targets.py
.venv/bin/python -m pytest -q
.venv/bin/python -c "from dart_footing_reconciler.corpus import run_workpaper_corpus; p=run_workpaper_corpus('out/corpus/manifest_2026-05-26-hundred.json','out/corpus/run_2026-05-26-hundred-v18',fetch_missing=False); print(p['summary'])"
```

Result:

- RED test failed as expected before implementation.
- Focused RED/GREEN test: 1 passed.
- Reconciliation focused tests: 70 passed.
- Full tests: 190 passed.
- 100-company corpus: primary checks 523, matched 311, unresolved 212.
- Delta from v17: primary checks 533 -> 523, matched 315 -> 311,
  unresolved 218 -> 212, no-difference rate 59.1% -> 59.5%.
- Removed unresolved zero-amount primary targets: 유한양행 intangible disposal,
  신세계 intangible disposal, 삼일제약 bonds financing, 한미글로벌 intangible
  disposal, 하이트진로홀딩스 intangible disposal, 한일시멘트 intangible disposal.
- Newly unresolved primary cases: 0.

Interpretation:

This is a target-scope fix. It intentionally removes zero-amount CFS lines from
primary cash-flow reconciliation targets rather than treating them as failed
cash transactions. The matched count decreased by four because prior zero-amount
matches were also removed from the denominator.

## 2026-05-26 Disposal Primary Candidate Selection Delta

Implemented conservative disposal carrying-amount primary selection:

- Disposal checks still prefer a direct `처분금액`/`처분대가` row when disclosed.
- When multiple disposal carrying-amount rows exist, the first row remains the
  default.
- A later disposal row is selected only if that row plus compatible disposal
  gain/loss/receivable adjustments agrees to the CFS target within effective
  tolerance and improves over the first-row formula.
- Duplicate disposal adjustment rows with the same role and amount are still
  deduplicated, so the 한화오션 duplicate `무형자산처분손실` false-match guard
  remains intact.

Verification:

```bash
.venv/bin/python -m pytest -q tests/test_checks_reconciliation.py::test_check_reconciliation_targets_selects_disposal_primary_that_matches_with_adjustments tests/test_checks_reconciliation.py::test_check_reconciliation_targets_keeps_disposal_primary_with_adjustment_formula tests/test_checks_reconciliation.py::test_check_reconciliation_targets_does_not_double_count_duplicate_disposal_adjustments
.venv/bin/python -m pytest -q tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py tests/test_reconciliation_targets.py
.venv/bin/python -m pytest -q
.venv/bin/python -c "from dart_footing_reconciler.corpus import run_workpaper_corpus; p=run_workpaper_corpus('out/corpus/manifest_2026-05-26-hundred.json','out/corpus/run_2026-05-26-hundred-v19',fetch_missing=False); print(p['summary'])"
```

Result:

- RED test failed as expected before implementation.
- Focused RED/GREEN and guard tests: 3 passed.
- Reconciliation focused tests: 71 passed.
- Full tests: 191 passed.
- 100-company corpus: primary checks 523, matched 312, unresolved 211.
- Delta from v18: matched 311 -> 312, unresolved 212 -> 211,
  no-difference rate 59.5% -> 59.7%.
- Resolved primary case: 엘에스일렉트릭 intangible disposal cash-flow.
- Newly unresolved primary cases: 0.

Interpretation:

This is a formula-evidence selection fix. It handles cases where an asset note
contains more than one disposal carrying-amount row and the later row is the
one that reconciles to the CFS disposal line with separately disclosed disposal
gain/loss. It does not double-count duplicated operating cash-flow adjustment
rows.

## 2026-05-26 Trade Receivables Composite Balance Delta

Implemented composite trade receivables balance evidence expansion:

- Trade receivables note balance subsets now treat allowance labels such as
  `손실충당금`, `대손충당금`, and `충당금` as subtractive amounts when the
  resulting net amount agrees to the statement within effective tolerance.
- Financial instrument category rows are now eligible as trade receivables
  balance evidence when `매출채권및기타채권` appears outside the first column.
- For those category rows, the first non-zero amount to the right of the
  account label is used as the carrying amount, avoiding later fair-value
  hierarchy zero columns.

Verification:

```bash
.venv/bin/python -m pytest -q tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_reads_trade_receivables_from_financial_instrument_rows tests/test_checks_reconciliation.py::test_check_reconciliation_targets_nets_trade_receivable_allowance_balance
.venv/bin/python -m pytest -q tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py tests/test_reconciliation_targets.py
.venv/bin/python -m pytest -q
.venv/bin/python -c "from dart_footing_reconciler.corpus import run_workpaper_corpus; p=run_workpaper_corpus('out/corpus/manifest_2026-05-26-hundred.json','out/corpus/run_2026-05-26-hundred-v21',fetch_missing=False); print(p['summary'])"
```

Result:

- RED tests failed as expected before implementation.
- Focused RED/GREEN tests: 2 passed.
- Reconciliation focused tests: 73 passed.
- Full tests: 193 passed.
- 100-company corpus: primary checks 524, matched 327, unresolved 197.
- Delta from v19: primary checks 523 -> 524, matched 312 -> 327,
  unresolved 211 -> 197, no-difference rate 59.7% -> 62.4%.
- Resolved primary cases: LG씨엔에스, 엘앤에프, 디와이, 서울도시가스,
  한화오션, HS효성, 세아제강, 에스원, 현대비앤지스틸, 롯데쇼핑,
  현대글로비스, CJ대한통운, 한진, 후성 trade receivables balance.
- Newly unresolved primary cases: 0.

Interpretation:

This is a direct evidence expansion for composite receivable accounts. It
supports the work-order requirement that `매출채권 및 기타채권` style accounts
be reconciled to detailed note tables rather than only to single account-name
rows.

## 2026-05-26 Trade Receivables Current/Noncurrent Column Delta

Implemented trade receivables current/noncurrent column summation:

- When a trade receivables note table has separate `유동매출채권` and
  `비유동매출채권` amount columns without explicit `당기말` headers, the current
  balance extractor now sums the receivable columns instead of taking only the
  last amount column.
- Secondary row labels such as `총장부금액` and `손상차손누계액` are preserved in
  evidence labels when the first row label is only generic `장부금액`.
- `손상차손누계액` is treated as subtractive allowance evidence under the same
  conservative netting rule already used for `손실충당금` and `대손충당금`.

Verification:

```bash
.venv/bin/python -m pytest tests/test_checks_reconciliation.py::test_check_reconciliation_targets_sums_trade_receivable_current_noncurrent_with_hidden_allowance_label -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/python -c "from dart_footing_reconciler.corpus import run_workpaper_corpus; p=run_workpaper_corpus('out/corpus/manifest_2026-05-26-hundred.json','out/corpus/run_2026-05-26-hundred-v22',fetch_missing=False); print(p['summary'])"
```

Result:

- RED test failed as expected before implementation.
- Focused RED/GREEN test: 1 passed.
- Reconciliation focused tests: 73 passed.
- Full tests: 194 passed.
- 100-company corpus: primary checks 524, matched 328, unresolved 196.
- Delta from v21: matched 327 -> 328, unresolved 197 -> 196,
  no-difference rate 62.4% -> 62.6%.
- Resolved primary case: DN오토모티브 trade receivables balance.
- Newly unresolved primary cases: 0.
- Changed-but-still-unresolved primary cases: 0.

Interpretation:

This is a table-shape evidence fix for receivable notes where the period is
implicit in the note heading and the columns split current/noncurrent
receivables. It does not loosen tolerance and does not alter cash-flow
formulas.

## 2026-05-26 Trade Receivables Wide Aggregate Row Delta

Implemented constrained current/noncurrent aggregate-row pairing for wide trade
receivables detail tables:

- When a trade receivables note table has many detail rows, unrestricted subset
  search remains capped to avoid false matches and combinatorial explosion.
- Within that cap, the reconciler now adds a targeted candidate pair for
  `매출채권 및 기타유동채권 합계` + `매출채권 및 기타비유동채권 합계`
  rows from the same table.
- The rule requires both rows to be aggregate rows containing `매출채권` and
  `합계`, with one current and one noncurrent label, so detail rows are not
  freely mixed.

Verification:

```bash
.venv/bin/python -m pytest tests/test_checks_reconciliation.py::test_check_reconciliation_targets_combines_trade_receivable_current_and_noncurrent_aggregate_rows_in_wide_detail_table -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/python -c "from dart_footing_reconciler.corpus import run_workpaper_corpus; p=run_workpaper_corpus('out/corpus/manifest_2026-05-26-hundred.json','out/corpus/run_2026-05-26-hundred-v23',fetch_missing=False); print(p['summary'])"
```

Result:

- RED test failed as expected before implementation.
- Focused RED/GREEN test: 1 passed.
- Reconciliation focused tests: 74 passed.
- Full tests: 195 passed.
- 100-company corpus: primary checks 524, matched 329, unresolved 195.
- Delta from v22: matched 328 -> 329, unresolved 196 -> 195,
  no-difference rate 62.6% -> 62.8%.
- Resolved primary case: GS리테일 trade receivables balance.
- Newly unresolved primary cases: 0.
- Changed-but-still-unresolved primary cases: 0.

Interpretation:

This is a constrained subset-search expansion for composite receivable notes.
It improves direct balance evidence without opening arbitrary combinations
across all receivable detail rows.

## 2026-05-26 Non-Cash Adjustment Second Header Row Delta

Implemented current-period header detection for non-cash asset adjustment
tables:

- Some cash-flow notes put a repeated unit row first, then the real amount
  header row second, such as `(단위: 천원)` followed by `거래내용 / 당기 / 전기`.
- Non-cash asset payable extraction now scans the first three rows for a
  current-period header and uses that row to choose the amount column.
- This prevents prior-period non-cash payable amounts from being used in
  acquisition cash-basis formulas.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_reads_noncash_asset_payable_current_column_when_header_is_second_row -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/python -c "from dart_footing_reconciler.corpus import run_workpaper_corpus; p=run_workpaper_corpus('out/corpus/manifest_2026-05-26-hundred.json','out/corpus/run_2026-05-26-hundred-v24',fetch_missing=False); print(p['summary'])"
```

Result:

- RED test failed as expected before implementation.
- Focused RED/GREEN test: 1 passed.
- Reconciliation focused tests: 75 passed.
- Full tests: 196 passed.
- 100-company corpus: primary checks 524, matched 330, unresolved 194.
- Delta from v23: matched 329 -> 330, unresolved 195 -> 194,
  no-difference rate 62.8% -> 63.0%.
- Resolved primary case: 금호에이치티 PPE acquisition cash-flow.
- Newly unresolved primary cases: 0.
- Changed-but-still-unresolved primary cases: 0.

Interpretation:

This is a period-column extraction fix for non-cash transaction tables. It
does not change payable direction semantics; it only prevents a prior-period
column from being selected when the true current-period header is on the second
row.

## 2026-05-26 Right-of-Use Non-Cash Acquisition Row Delta

Implemented right-of-use asset additions from non-cash transaction tables:

- Non-cash transaction tables can disclose `사용권자산의 추가` or similar rows
  even when the table title is a cash-flow/non-cash transaction note rather
  than a dedicated right-of-use asset table.
- These rows are now extracted as PPE `right_of_use_noncash_acquisition`
  adjustments when the row label contains `사용권자산` and an addition,
  recognition, or acquisition term.
- The existing acquisition formula subtracts these candidates only when the
  subset improves the cash-flow bridge.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_reads_right_of_use_asset_additions_from_noncash_transaction_table -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/python -c "from dart_footing_reconciler.corpus import run_workpaper_corpus; p=run_workpaper_corpus('out/corpus/manifest_2026-05-26-hundred.json','out/corpus/run_2026-05-26-hundred-v25',fetch_missing=False); print(p['summary'])"
```

Result:

- RED test failed as expected before implementation.
- Focused RED/GREEN test: 1 passed.
- Reconciliation focused tests: 76 passed.
- Full tests: 197 passed.
- 100-company corpus: primary checks 524, matched 331, unresolved 193.
- Delta from v24: matched 330 -> 331, unresolved 194 -> 193,
  no-difference rate 63.0% -> 63.2%.
- Resolved primary case: 삼성E&A PPE acquisition cash-flow.
- Newly unresolved primary cases: 0.
- Changed-but-still-unresolved primary cases: 4.

Interpretation:

This is a non-cash evidence extraction fix for the work-order formula term
`- 리스/사용권자산 비현금 취득`. It adds right-of-use additions from cash-flow
non-cash transaction notes without treating lease-liability reclassification
rows as asset acquisition evidence.

## 2026-05-26 Right-of-Use Lease Liability Transfer Delta

Implemented a narrow non-cash transaction extraction rule for right-of-use
asset transfers to lease liabilities:

- Some cash-flow non-cash transaction notes disclose rows such as
  `사용권자산 리스부채로의 대체`.
- These rows represent right-of-use asset recognition through lease liabilities,
  not a cash PPE acquisition, so they now enter the PPE
  `right_of_use_noncash_acquisition` adjustment pool.
- Lease-liability-only reclassification rows remain ignored; the rule requires
  `사용권자산`, `리스부채`, and `대체` in the row label.
- The existing acquisition subset selector uses the adjustment only when it
  improves the CFS bridge, so unrelated transfer rows are not forced into the
  formula.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py -q -k lease_liability_transfer
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/python -c "from dart_footing_reconciler.corpus import run_workpaper_corpus; p=run_workpaper_corpus('out/corpus/manifest_2026-05-26-hundred.json','out/corpus/run_2026-05-26-hundred-v26',fetch_missing=False); print(p['summary'])"
```

Result:

- RED test failed as expected before implementation.
- Focused RED/GREEN test: 1 passed.
- Reconciliation focused tests: 77 passed.
- Full tests: 198 passed.
- 100-company corpus: primary checks 524, matched 332, unresolved 192.
- Delta from v25: matched 331 -> 332, unresolved 193 -> 192,
  no-difference rate 63.2% -> 63.4%.
- Resolved primary case: 제이에스코퍼레이션 PPE acquisition cash-flow.
- Newly unresolved primary cases: 0.
- Changed-but-still-unresolved primary cases: 0.

Interpretation:

This is a narrow evidence extraction fix for the same work-order formula term
`- 리스/사용권자산 비현금 취득`. It does not loosen tolerance, does not change
payable direction semantics, and does not treat lease-liability-only
reclassifications as asset acquisition evidence.

## 2026-05-26 Disposal Gain/Loss Heading Coverage Delta

Implemented broader but still semantic heading coverage for disposal gain/loss
adjustments:

- Disposal gain/loss rows are now extracted from `기타손익` headings in addition
  to `기타수익` and `기타비용`.
- Generic cash-flow note headings such as `현금흐름표` and `연결현금흐름표`
  can now provide disposal gain/loss adjustment rows when the row label itself
  explicitly contains asset disposal gain/loss terms.
- `유무형자산처분이익/손실` rows are routed to both PPE and intangible asset
  disposal candidate pools.
- When a table has explicit current-period headers, disposal adjustment
  extraction now uses only the current-period amount instead of falling back to
  prior-period amounts when current-period cells are blank.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py -q -k 'misc_gain_loss_note_disposal_adjustments or cashflow_note_disposal_loss_adjustments'
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/python -c "from dart_footing_reconciler.corpus import run_workpaper_corpus; p=run_workpaper_corpus('out/corpus/manifest_2026-05-26-hundred.json','out/corpus/run_2026-05-26-hundred-v27',fetch_missing=False); print(p['summary'])"
```

Result:

- RED tests failed as expected before implementation.
- Focused RED/GREEN tests: 2 passed.
- Reconciliation focused tests: 79 passed.
- Full tests: 200 passed.
- 100-company corpus: primary checks 524, matched 336, unresolved 188.
- Delta from v26: matched 332 -> 336, unresolved 192 -> 188,
  no-difference rate 63.4% -> 64.1%.
- Resolved primary cases: HS애드 PPE disposal, HS애드 intangible disposal,
  아남전자 PPE disposal, 후성 intangible disposal.
- Newly unresolved primary cases: 0.
- Changed-but-still-unresolved primary cases: 6, all with reduced absolute
  differences and no false-match promotion.

Interpretation:

This is a source-coverage fix for disposal cash-flow formulas. It uses explicit
asset disposal gain/loss row labels as the guardrail, not generic income or
cash-flow table presence alone. The rule increases matched cases while moving
several remaining disposal cases from unexplained to explainable with smaller
formula differences.

## 2026-05-26 Signed Roll-Forward Transfer Acquisition Delta

Implemented signed roll-forward transfer adjustments for acquisition cash-flow
formulas:

- Asset roll-forward rows such as `대체에 따른 증가(감소)` and
  `재고자산과의 대체에 따른 증가(감소)` now enter the acquisition candidate
  pool as `rollforward_transfer_acquisition`.
- These roll-forward transfers use their signed amount in the cash-flow bridge:
  negative transfers reduce cash-basis acquisition and positive transfers
  increase the comparable amount.
- Existing non-cash transaction table transfers remain separate
  `noncash_transfer_acquisition` adjustments and continue to be subtracted when
  an acquisition row already includes account transfers.
- Rows containing `처분` remain disposal primary candidates even if the label
  also contains `대체`, preventing target disappearance for labels such as
  `처분 및 대체 등`.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_reads_asset_rollforward_transfer_adjustments tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_keeps_disposal_and_transfer_row_as_disposal tests/test_checks_reconciliation.py::test_check_reconciliation_targets_applies_signed_rollforward_transfer_to_acquisition_cash_basis -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/python -c "from dart_footing_reconciler.corpus import run_workpaper_corpus; p=run_workpaper_corpus('out/corpus/manifest_2026-05-26-hundred.json','out/corpus/run_2026-05-26-hundred-v28',fetch_missing=False); print(p['summary'])"
```

Result:

- RED tests failed as expected before implementation.
- Focused RED/GREEN tests: 3 passed.
- Reconciliation focused tests: 82 passed.
- Full tests: 203 passed.
- 100-company corpus: primary checks 524, matched 338, unresolved 186.
- Delta from v27: matched 336 -> 338, unresolved 188 -> 186,
  no-difference rate 64.1% -> 64.5%.
- Resolved primary cases: 한솔테크닉스 PPE acquisition, 진흥기업 intangible
  acquisition.
- Newly unresolved primary cases: 0.
- Changed-but-still-unresolved primary cases: 15, all remaining unresolved and
  moving through explicit formula evidence rather than target disappearance.

Interpretation:

This separates two meanings of `대체`: non-cash transaction table transfers that
should be subtracted from gross acquisition, and signed roll-forward transfers
that reconcile the movement table to cash-flow line presentation. It preserves
existing disposal rows with `처분 및 대체` wording as disposal evidence.

## 2026-05-26 Borrowing Decrease CFS Direction Delta

Implemented repayment-first classification for borrowing decrease rows in the
cash-flow statement:

- Rows such as `단기차입금의 감소` now classify as borrowing repayments before
  the generic `차입금` proceeds rule can match the `차입` substring inside
  `차입금`.
- Existing `차입금의 증가` and `장기차입금의 차입` rows remain proceeds.
- Existing `차입금의 상환` rows remain repayments.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_classifies_borrowing_decrease_as_repayment -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/python -c "from dart_footing_reconciler.corpus import run_workpaper_corpus; p=run_workpaper_corpus('out/corpus/manifest_2026-05-26-hundred.json','out/corpus/run_2026-05-26-hundred-v29',fetch_missing=False); print(p['summary'])"
```

Result:

- RED test failed as expected before implementation.
- Focused RED/GREEN test: 1 passed.
- Reconciliation focused tests: 83 passed.
- Full tests: 204 passed.
- 100-company corpus: primary checks 524, matched 338, unresolved 186.
- Delta from v28: matched unchanged at 338, unresolved unchanged at 186,
  no-difference rate unchanged at 64.5%.
- Newly unresolved primary cases: 0.
- Changed-but-still-unresolved primary cases: 1. 현대코퍼레이션 borrowings
  financing expected amount changed from 912.1B to 264.4B because `차입금의 감소`
  rows are no longer treated as proceeds.

Interpretation:

This is a target-quality fix, not a match-rate improvement. It prevents a
borrowings cash-flow repayment row from being turned into a positive proceeds
line solely because `차입금` contains `차입`.

## 2026-05-26 CFS Blank Current-Period Amount Guard Delta

Implemented strict current-period amount extraction for primary cash-flow
statement lines:

- When a cash-flow statement has explicit current-period columns such as `당기`
  or fiscal columns such as `제 52 기`, CFS line extraction now reads only those
  current-period columns.
- If the current-period cell is blank, the row is skipped instead of falling
  back to a rightmost prior-period amount.
- Tables without explicit current-period columns keep the prior generic row
  amount fallback.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_skips_cfs_row_when_current_period_amount_is_blank -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/python -c "from dart_footing_reconciler.corpus import run_workpaper_corpus; p=run_workpaper_corpus('out/corpus/manifest_2026-05-26-hundred.json','out/corpus/run_2026-05-26-hundred-v30',fetch_missing=False); print(p['summary'])"
```

Result:

- RED test failed as expected before implementation.
- Focused RED/GREEN test: 1 passed.
- Reconciliation focused tests: 84 passed.
- Full tests: 205 passed.
- 100-company corpus: primary checks 523, matched 340, unresolved 183.
- Delta from v29: checks 524 -> 523, matched 338 -> 340, unresolved 186 -> 183,
  no-difference rate 64.5% -> 65.0%.
- Resolved primary cases: 아남전자 borrowings financing cash-flow,
  현대오토에버 borrowings financing cash-flow, 금호에이치티 bonds financing
  cash-flow.
- Newly unresolved primary cases: 0.
- Changed-but-still-unresolved primary cases: 0.

Interpretation:

This is both a target-quality and match-rate improvement. It prevents blank
current-period cash-flow rows from importing prior-period amounts, while
preserving legitimate current-period financing repayment/proceeds lines in the
same table.

## 2026-05-26 Financing Prior Table Marker Delta

Implemented a narrow prior-period table guard for financing liability movement
tables:

- Headings ending with `(당기) (전기)` are treated as prior-period tables when
  the heading also indicates a financing liability movement table
  (`재무활동에서 생기는 부채` or `재무활동 관련 부채`).
- Existing asset roll-forward headings such as `당기와 전기 중 변동내역` and
  `당기말 및 전기말` remain current comparative tables.
- The rule is intentionally not applied to all headings ending in `당기전기`,
  to avoid dropping valid comparative tables.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_skips_financing_table_marked_current_then_prior tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_reads_direct_financing_cashflow_column_and_skips_prior_table tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_keeps_current_tables_that_compare_current_and_prior_periods -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/python -c "from dart_footing_reconciler.corpus import run_workpaper_corpus; p=run_workpaper_corpus('out/corpus/manifest_2026-05-26-hundred.json','out/corpus/run_2026-05-26-hundred-v31',fetch_missing=False); print(p['summary'])"
```

Result:

- RED test failed as expected before implementation.
- Focused RED/GREEN and guard tests: 3 passed.
- Reconciliation focused tests: 85 passed.
- Full tests: 206 passed.
- 100-company corpus: primary checks 523, matched 340, unresolved 183.
- Delta from v30: matched unchanged, unresolved unchanged, no-difference rate
  unchanged at 65.0%.
- Resolved primary cases: 0.
- Newly unresolved primary cases: 0.
- Changed-but-still-unresolved primary cases: 1. NICE평가정보 borrowings
  financing actual changed from 21.36904B to 23.36908B after prior-period
  financing cash-flow rows were removed; the case remains unresolved.

Interpretation:

This is a period/scope quality guard, not a match-rate improvement. It prevents
prior-year financing liability movement tables from contaminating current-year
note cash-flow evidence while preserving current comparative roll-forward
tables.

## 2026-05-26 Corpus Success-Rate Table Delta

Added a `검증유형별 성공률` section to the corpus Markdown report:

- The table reports primary check counts, no-difference counts, unresolved
  counts, no-difference rate, and automatic judgment rate by verification type.
- The section uses user-facing Korean labels such as `현금흐름 대사` and
  `재무제표-주석 금액 대사`, not raw check type names.
- Each sample payload and the summary payload now carry
  `primary_type_status_counts` so the table is reproducible from
  `corpus_result.json`.

Verification:

```bash
.venv/bin/python -m pytest tests/test_corpus.py::test_corpus_markdown_includes_primary_success_rates_by_check_type -q
.venv/bin/python -m pytest tests/test_corpus.py -q
.venv/bin/python -m pytest -q
.venv/bin/python -c "from dart_footing_reconciler.corpus import run_workpaper_corpus; p=run_workpaper_corpus('out/corpus/manifest_2026-05-26-hundred.json','out/corpus/run_2026-05-26-hundred-v32',fetch_missing=False); print(p['summary'])"
```

Result:

- RED test failed as expected before implementation.
- Focused RED/GREEN test: 1 passed.
- Corpus tests: 4 passed.
- Full tests: 207 passed.
- 100-company corpus: primary checks 523, matched 340, unresolved 183.
- Delta from v31: match metrics unchanged; report deliverable expanded.
- v32 verification type success rates:
  - 현금흐름 대사: 128 / 285 matched, 44.9% no-difference, 100.0%
    automatic judgment.
  - 재무제표-주석 금액 대사: 204 / 227 matched, 89.9% no-difference,
    100.0% automatic judgment.
  - 성격별 비용 대사: 8 / 11 matched, 72.7% no-difference, 100.0%
    automatic judgment.

Interpretation:

This satisfies the current 100-company corpus requirement to present
company-level and verification-type success-rate tables. It also makes the next
bottleneck quantitative: cash-flow reconciliation has 157 remaining unresolved
items and a 44.9% no-difference rate.

## 2026-05-26 False Matched Review Sample Delta

Added a false matched review sample artifact to every corpus run:

- The runner writes `false_matched_review.md` next to `corpus_report.md`.
- The artifact samples matched primary checks by verification type and includes
  expected amount, actual amount, difference, tolerance, reason, and source
  evidence.
- v33 selected 15 review samples: 5 cash-flow reconciliations, 5 balance
  reconciliations, and 5 expense allocation checks.

Verification:

```bash
.venv/bin/python -m pytest tests/test_corpus.py::test_corpus_writes_false_matched_review_sample -q
.venv/bin/python -m pytest tests/test_corpus.py -q
.venv/bin/python -m pytest -q
.venv/bin/python -c "from dart_footing_reconciler.corpus import run_workpaper_corpus; p=run_workpaper_corpus('out/corpus/manifest_2026-05-26-hundred.json','out/corpus/run_2026-05-26-hundred-v33',fetch_missing=False); print(p['summary'])"
```

Result:

- RED test failed as expected before implementation.
- Focused RED/GREEN test: 1 passed.
- Corpus tests: 5 passed.
- Full tests: 208 passed.
- 100-company corpus: primary checks 523, matched 340, unresolved 183.
- Delta from v32: match metrics unchanged; false matched review deliverable
  added.
- False matched review samples: 15.

Interpretation:

This does not prove the global false-matched count is zero, but it creates the
required reusable review packet for matched primary checks and exposes the
source evidence needed for manual false-positive inspection.

## 2026-05-26 Payable Increase-Decrease Sign Delta

Refined acquisition cash-flow bridge semantics for non-cash payable rows:

- `미지급금의 감소(증가)` remains a payable decrease label and is treated as a
  cash-basis addition.
- `미지급금의 증가(감소)` no longer forces all amounts to payable increases.
  If the extracted amount is negative, the formula now treats it as a payable
  decrease and adds it back to cash acquisitions.
- This avoids a label-only direction override and keeps the amount sign as
  evidence when the Korean label is an increase/decrease pair.

Verification:

```bash
.venv/bin/python -m pytest tests/test_checks_reconciliation.py::test_check_reconciliation_targets_treats_negative_increase_decrease_payable_as_decrease -q
.venv/bin/python -m pytest tests/test_checks_reconciliation.py::test_check_reconciliation_targets_uses_payable_decrease_increase_label_direction tests/test_checks_reconciliation.py::test_check_reconciliation_targets_adds_negative_payable_delta_to_cash_acquisition -q
.venv/bin/python -m pytest tests/test_checks_reconciliation.py tests/test_reconciliation_inputs.py -q
.venv/bin/python -m pytest tests/test_corpus.py -q
.venv/bin/python -m pytest -q
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-26-hundred-v34 --no-fetch
```

Result:

- RED test failed as expected before implementation.
- Focused new test: 1 passed.
- Payable-direction guard tests: 2 passed.
- Reconciliation/input focused tests: 86 passed.
- Corpus tests: 5 passed.
- Full tests: 209 passed.
- 100-company corpus v34: generated reports 100/100, primary checks 523,
  matched 340, unresolved 183, no-difference rate 65.0%, judgment rate 100.0%.
- Delta from v33: primary matched unchanged; cash-flow unresolved status mix
  changed from 76 unexplained / 81 explainable to 75 unexplained / 82
  explainable.
- 현대위아 PPE acquisition changed from direct-evidence-missing to
  formula-template-missing:
  `주석 취득 225,153,000,000 + 비현금거래-미지급금 감소 15,029,000,000 =
  240,182,000,000`; CFS target remains `241,035,000,000`, residual difference
  `(853,000,000)`.

Interpretation:

This does not move the 70% Gate 1 rate. It improves formula evidence quality and
taxonomy accuracy for an explicit non-cash payable adjustment, leaving the next
numeric bottleneck unchanged: 157 cash-flow primary unresolved items.

## 2026-05-26 Financing Action Column Delta

Refined financing liability movement-table extraction:

- Financing liability roll-forward tables now read explicit cash-flow action
  columns such as `차입`, `발행`, and `상환`.
- Positive values in repayment columns are directionally normalized to cash
  outflows, while already signed combined columns keep their signed amount.
- The rule is limited to tables already classified as financing liability
  cash-flow evidence, so generic borrowing detail tables remain excluded.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_reads_financing_borrowing_and_repayment_columns -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_reads_split_financing_cashflow_increase_and_decrease_columns tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_reads_financing_cashflow_rows_with_account_columns tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_preserves_signed_combined_financing_cashflow_column -q
.venv/bin/python -m pytest tests/test_checks_reconciliation.py::test_check_reconciliation_targets_matches_financing_liability_net_cashflow_note tests/test_checks_reconciliation.py::test_check_reconciliation_targets_selects_matching_financing_cashflow_subset tests/test_checks_reconciliation.py::test_check_reconciliation_targets_keeps_financing_cashflow_movements_when_no_subset_matches -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest tests/test_corpus.py -q
.venv/bin/python -m pytest -q
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-26-hundred-v35 --no-fetch
```

Result:

- RED test failed as expected before implementation.
- Focused new test: 1 passed.
- Financing input guard tests: 3 passed.
- Financing reconciliation guard tests: 3 passed.
- Reconciliation/input focused tests: 87 passed.
- Corpus tests: 5 passed.
- Full tests: 210 passed.
- 100-company corpus v35: generated reports 100/100, primary checks 523,
  matched 342, unresolved 181, no-difference rate 65.4%, judgment rate 100.0%.
- Delta from v34: primary matched +2, primary unresolved -2, no newly
  unresolved primary cases.
- Resolved 노루페인트 borrowings financing cash-flow:
  `5,000,000,000 - 5,947,785,000 - 23,500,000,000 = (24,447,785,000)`
  versus CFS `(24,447,784,970)`.
- Resolved 노루페인트 bonds financing cash-flow:
  `(15,000,000,000)` versus CFS `(15,000,000,000)`.

Interpretation:

This moves Gate 1 in the right direction but does not clear it. Remaining
primary unresolved items are still concentrated in cash-flow reconciliation:
155 of 181 unresolved items.

## 2026-05-26 Right-of-Use Disposal Delta

Refined PPE disposal cash-flow bridge semantics:

- PPE roll-forward disposal rows now preserve the amount in a `사용권자산`
  column as `right_of_use_noncash_disposal`.
- Disposal cash-flow formulas subtract that amount from total disposal carrying
  amount before applying disposal gain/loss and non-cash receivable
  adjustments.
- This covers cases where the PPE note's total disposal row includes
  right-of-use asset derecognition but the CFS `유형자산의 처분` line reflects
  cash proceeds from non-lease PPE disposals.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_reads_right_of_use_asset_disposal_from_ppe_rollforward tests/test_checks_reconciliation.py::test_check_reconciliation_targets_excludes_right_of_use_asset_disposal_from_ppe_cash_basis -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest tests/test_corpus.py -q
.venv/bin/python -m pytest -q
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-26-hundred-v36 --no-fetch
```

Result:

- RED tests failed as expected before implementation.
- Focused new tests: 2 passed.
- Reconciliation/input focused tests: 89 passed.
- Corpus tests: 5 passed.
- Full tests: 212 passed.
- 100-company corpus v36: generated reports 100/100, primary checks 523,
  matched 344, unresolved 179, no-difference rate 65.8%, judgment rate 100.0%.
- Delta from v35: primary matched +2, primary unresolved -2, no newly
  unresolved primary check IDs.
- Resolved 세아제강 PPE disposal cash-flow:
  `주석 처분 장부금액 528,025,316 - 사용권자산 비현금 처분 6,444,468
  + 처분손익 882,464,833 - 처분손실 174,502,211 = 1,229,543,470`
  versus CFS `1,229,543,470`.
- Resolved 제이에스코퍼레이션 PPE disposal cash-flow:
  `주석 처분 장부금액 2,320,607,000 - 사용권자산 비현금 처분 553,032,000
  + 처분손익 954,430,000 - 처분손실 1,340,426,000 = 1,381,579,000`
  versus CFS `1,381,578,523`, difference 477 within accumulated source
  precision.
- 효성화학 and 롯데에너지머티리얼즈 remain unresolved but their residuals
  decreased after excluding right-of-use disposal amounts.

Interpretation:

This is a narrow evidence-based formula improvement, not a tolerance change.
Gate 1 remains below 70%; remaining primary unresolved items are still
concentrated in cash-flow reconciliation: 153 of 179 unresolved items.

## 2026-05-26 Non-Cash Detail Label Delta

Refined non-cash transaction table extraction:

- Some DART non-cash transaction tables use the first column as a repeated stub
  such as `거래내역`, with the actual transaction label in the second text
  column and the amount in `공시금액`.
- The extractor now reads the first meaningful non-amount detail column before
  falling back to the first cell.
- This allows rows like `거래내역 / 선급금의 무형자산 대체 / 6,867` to be
  classified as an intangible `noncash_transfer_acquisition` candidate.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_reads_noncash_transfer_label_from_detail_column tests/test_checks_reconciliation.py::test_check_reconciliation_targets_excludes_prepayment_to_intangible_transfer_from_cash_acquisition -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest tests/test_corpus.py -q
.venv/bin/python -m pytest -q
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-26-hundred-v37 --no-fetch
```

Result:

- RED tests failed as expected before implementation.
- Focused new tests: 2 passed.
- Reconciliation/input focused tests: 91 passed.
- Corpus tests: 5 passed.
- Full tests: 214 passed.
- 100-company corpus v37: generated reports 100/100, primary checks 523,
  matched 344, unresolved 179, no-difference rate 65.8%, judgment rate 100.0%.
- Delta from v36: primary metrics unchanged; no newly unresolved primary check
  IDs.

Interpretation:

This is input-structure coverage, not a Gate 1 metric mover. It exposes
detail-column non-cash transfer candidates for later formula rules, while
leaving v36's accepted matched/unresolved counts unchanged.

## 2026-05-26 Specific Payable Change Direction Delta

Refined non-cash payable direction semantics for acquisition cash-flow bridges:

- A negative `미지급금의 변동` amount is treated as a payable increase only
  when the row label explicitly ties a specific asset acquisition to the payable
  change with `관련`, for example `무형자산 취득 관련 미지급금의 변동`.
- Short labels such as `유형자산 취득 미지급금 변동` remain payable decreases.
  The rejected v38 experiment proved this guard is necessary: a broad negative
  `변동` rule resolved 삼성생명 but regressed the accepted 유한양행 PPE
  acquisition bridge.
- Combined `유ㆍ무형자산` payable rows keep the existing candidate-subset guard
  and are selected only when the formula improves the target.

Verification:

```bash
.venv/bin/python -m pytest tests/test_checks_reconciliation.py::test_check_reconciliation_targets_treats_specific_negative_payable_change_as_increase tests/test_checks_reconciliation.py::test_check_reconciliation_targets_keeps_terse_negative_payable_change_as_decrease tests/test_checks_reconciliation.py::test_check_reconciliation_targets_uses_combined_asset_payable_only_when_formula_improves -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest tests/test_corpus.py -q
.venv/bin/python -m pytest -q
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-26-hundred-v39 --no-fetch
```

Result:

- RED tests failed as expected before the narrowed implementation.
- Focused direction/guard tests: 3 passed.
- Reconciliation/input focused tests: 93 passed.
- Corpus tests: 5 passed.
- Full tests: 216 passed.
- 100-company corpus v39: generated reports 100/100, primary checks 523,
  matched 345, unresolved 178, no-difference rate 66.0%, judgment rate 100.0%.
- Delta from v37: primary matched +1, primary unresolved -1, no newly
  unresolved primary check IDs.
- Resolved 삼성생명 intangible acquisition cash-flow:
  `주석 취득 93,968,000,000 - 비현금거래-미지급금 증가 2,683,000,000 =
  91,285,000,000` versus CFS `91,286,000,000`, difference `(1,000,000)`
  within accumulated source precision.

Interpretation:

This is a narrow label-semantics improvement for accrual payable bridges, not a
global sign flip. Gate 1 remains below 70%; remaining primary unresolved items
are still concentrated in cash-flow reconciliation: 152 of 178 unresolved items.

## 2026-05-26 Government Grant Disposal Column Delta

Refined PPE disposal cash-flow bridge semantics for government-grant contra rows:

- Some PPE roll-forward tables disclose `총장부금액, 정부보조금 차감 전` rows
  and separate `정부보조금` rows. The account-family total row is a net carrying
  amount; disposal gain/loss bridge may require adding the government-grant
  disposal column back to the disposal carrying amount.
- PPE roll-forward `정부보조금` rows now provide a
  `government_grant_disposal` adjustment when the current-period movement
  header is `처분`.
- Rows labelled `정부보조금 차감 전` are explicitly ignored as grant
  adjustments so gross carrying-amount rows are not double-counted.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_reads_government_grant_disposal_from_ppe_rollforward tests/test_checks_reconciliation.py::test_check_reconciliation_targets_adds_government_grant_disposal_to_ppe_cash_basis -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest tests/test_corpus.py -q
.venv/bin/python -m pytest -q
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-26-hundred-v40 --no-fetch
```

Result:

- RED tests failed as expected before implementation.
- Focused new tests: 2 passed.
- Reconciliation/input focused tests: 95 passed.
- Corpus tests: 5 passed.
- Full tests: 218 passed.
- 100-company corpus v40: generated reports 100/100, primary checks 523,
  matched 346, unresolved 177, no-difference rate 66.2%, judgment rate 100.0%.
- Delta from v39: primary matched +1, primary unresolved -1, no newly
  unresolved primary check IDs.
- Resolved 현대위아 PPE disposal cash-flow:
  `주석 처분 장부금액 62,318,000,000 + 정부보조금 처분 1,258,000,000
  + 처분손익 9,833,000,000 - 처분손실 27,013,000,000 = 46,396,000,000`
  versus CFS `46,396,000,000`.

Interpretation:

This is a narrow roll-forward column semantics improvement, not a tolerance
change. Gate 1 remains below 70%; remaining primary unresolved items are still
concentrated in cash-flow reconciliation: 151 of 177 unresolved items.

## 2026-05-26 Investment Property Depreciation Allocation Delta

Refined depreciation expense allocation semantics:

- Some companies disclose a PPE depreciation functional allocation table, while
  the nature-of-expense `감가상각비` total includes both PPE depreciation and
  investment-property depreciation.
- Investment-property roll-forward rows labelled `감가상각비` now enter the
  functional expense candidate pool as a `nature_exclusion` for PPE depreciation
  allocation. The extractor reads the depreciation label from a secondary text
  column, matching DART tables like `투자부동산의 변동에 대한 조정 /
  감가상각비, 투자부동산 / ... / 합계`.
- The exclusion is applied only when subtracting the investment-property amount
  makes the PPE functional allocation total agree with the nature-total basis.
  This guard prevents regressions in cases where investment-property
  depreciation exists but is not the reconciling item.

Verification:

```bash
.venv/bin/python -m pytest tests/test_checks_reconciliation.py::test_check_reconciliation_targets_excludes_investment_property_depreciation_from_ppe_nature_basis tests/test_checks_reconciliation.py::test_check_reconciliation_targets_keeps_investment_property_depreciation_when_it_does_not_reconcile -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest tests/test_corpus.py -q
.venv/bin/python -m pytest -q
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-26-hundred-v43 --no-fetch
```

Result:

- RED test failed as expected before implementation; a v42 broad extraction
  experiment was rejected because it regressed 셀트리온 PPE depreciation
  allocation.
- Focused new/guard tests: 2 passed.
- Reconciliation/input focused tests: 97 passed.
- Corpus tests: 5 passed.
- Full tests: 220 passed.
- 100-company corpus v43: generated reports 100/100, primary checks 523,
  matched 347, unresolved 176, no-difference rate 66.3%, judgment rate 100.0%.
- Delta from v40: primary matched +1, primary unresolved -1, no newly
  unresolved primary check IDs.
- Expense allocation type rate improved from 8/11 matched (72.7%) to
  9/11 matched (81.8%).
- Resolved 시알홀딩스 PPE depreciation allocation:
  `매출원가 20,153,545,000 + 판매비와 일반관리비 5,940,839,000 =
  26,094,384,000; 성격별 비용 감가상각비 28,282,645,000 -
  투자부동산 감가상각비 2,188,261,000 = 26,094,384,000`.

Interpretation:

This is a Phase 2 allocation improvement with a strict reconciling-item guard.
Gate 1 remains below 70%; remaining primary unresolved items are still
concentrated in cash-flow reconciliation: 151 of 176 unresolved items.

## 2026-05-26 Financing Duplicate-Scope Recovery Delta

Refined financing liability cash-flow evidence selection:

- Some DART filings include duplicate `재무활동에서 생기는 부채` tables across
  connected/separate note areas, while the current primary-note filter keeps
  only one scope.
- Financing cash-flow evidence now has a narrow recovery path: unscoped
  financing liability cash-flow rows are considered only for accounts that
  already have scoped financing evidence, and only when the added row or subset
  exactly completes the CFS financing target.
- Balance, asset roll-forward, disposal, acquisition, and expense allocation
  candidates remain scoped through the existing primary-note filter.
- A broader v44 experiment that added all unscoped financing rows was rejected
  because it increased primary checks from 523 to 526 and introduced three new
  unresolved primary items.

Verification:

```bash
.venv/bin/python -m pytest tests/test_checks_reconciliation.py::test_check_reconciliation_targets_uses_duplicate_scope_financing_table_when_it_matches_cfs -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-26-hundred-v45 --no-fetch
```

Result:

- RED test failed as expected before implementation.
- Focused duplicate-scope financing test: 1 passed.
- Reconciliation/input focused tests: 98 passed.
- Full tests: 221 passed.
- 100-company corpus v45: generated reports 100/100, primary checks 523,
  matched 348, unresolved 175, no-difference rate 66.5%, judgment rate 100.0%.
- Delta from v43: primary matched +1, primary unresolved -1, no newly
  unresolved primary check IDs.
- Cash-flow type rate improved from 134/285 matched (47.0%) to 135/285 matched
  (47.4%).
- Resolved 현대비앤지스틸 lease liabilities financing cash-flow:
  `현금흐름표 리스부채의 감소 (59,979,788) = (59,979,788);
  주석 재무활동현금흐름 리스부채 (59,979,788) = (59,979,788)`.

Interpretation:

This is a financing evidence selection improvement, not a general scope-mixing
rule. Gate 1 remains below 70%; remaining primary unresolved items are still
concentrated in cash-flow reconciliation: 150 of 175 unresolved items.

## 2026-05-26 Asset Total Carrying Amount Balance Delta

Refined asset balance extraction:

- Some PPE/intangible notes disclose a detail table with multi-row headers:
  a top current/prior period band such as `당기말`, and a second-row measurement
  axis such as `취득원가`, `감가상각 누계액`, `정부보조금`, and `장부금액`.
- The reconciler previously did not treat `합계`/`총계` rows in these asset
  detail tables as ending-balance candidates unless the row label itself
  contained `기말` or `장부금액`. In those cases it could fall back to unrelated
  fair-value hierarchy rows.
- Asset `합계`/`총계` rows now become ending-balance candidates only when the
  table headers identify a carrying-amount column (`장부금액`, `순장부금액`, or
  `장부가액`). The selected amount is the current-period carrying-amount column,
  not the sum of all current-period gross cost/depreciation/grant/carrying
  columns.

Verification:

```bash
.venv/bin/python -m pytest tests/test_checks_reconciliation.py::test_check_reconciliation_targets_matches_asset_total_row_with_carrying_amount_column -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-26-hundred-v46 --no-fetch
```

Result:

- RED test failed as expected before implementation.
- Focused asset total carrying amount test: 1 passed.
- Reconciliation/input focused tests: 99 passed.
- Full tests: 222 passed.
- 100-company corpus v46: generated reports 100/100, primary checks 540,
  matched 365, unresolved 175, no-difference rate 67.6%, judgment rate 100.0%.
- Delta from v45: primary checks +17, primary matched +17, primary unresolved
  unchanged, no-difference rate 66.5% -> 67.6%.
- Existing unresolved -> matched: 롯데정밀화학 intangible assets balance,
  삼일제약 PPE balance.
- Newly exposed matched checks: 15 asset balance checks, including DB손해보험
  PPE, KB금융 PPE, 대한방직 PPE/intangible, 롯데이노베이트 PPE/intangible,
  현대위아 PPE, and other asset balances.
- Newly exposed unresolved checks: DB손해보험 intangible assets balance
  (`180,318,806,591` vs `180,320,000,000`) and KB금융 intangible assets balance
  (`1,966,684,000,000` vs `1,966,683,000,000`). These are coverage-expanded
  findings, not regressions of prior matched checks.

Interpretation:

This is a balance coverage and table-semantics improvement. It moves the tool
toward direct statement-to-note table reconciliation for asset balances, but
Gate 1 remains below 70%; remaining primary unresolved items are still
concentrated in cash-flow reconciliation: 150 of 175 unresolved items.

## 2026-05-26 Right-of-Use Lease Repayment Cash-Flow Delta

Refined financing cash-flow evidence extraction:

- Some right-of-use asset notes disclose a compact table headed
  `현금흐름표에 인식한 금액` with a direct `리스부채의 상환` row.
- The reconciler previously preferred the broader `재무활동에서 생기는 부채`
  movement table for lease liabilities, which can include amounts that do not
  reconcile to the CFS lease repayment line.
- Direct ROU cash-flow-note lease repayment rows are now extracted as
  `lease_liabilities` financing cash-flow evidence, normalized as cash outflows.
  Existing financing subset selection then chooses that direct row only when it
  matches the CFS target within source precision.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_reads_lease_repayment_from_rou_cashflow_note tests/test_checks_reconciliation.py::test_check_reconciliation_targets_prefers_rou_lease_repayment_cashflow_note -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-26-hundred-v47 --no-fetch
```

Result:

- RED tests failed as expected before implementation.
- Focused ROU lease repayment tests: 2 passed.
- Reconciliation/input focused tests: 101 passed.
- Full tests: 224 passed.
- 100-company corpus v47: generated reports 100/100, primary checks 540,
  matched 366, unresolved 174, no-difference rate 67.8%, judgment rate 100.0%.
- Delta from v46: primary matched +1, primary unresolved -1, no newly unresolved
  primary check IDs.
- Resolved 한국제지 lease liabilities financing cash-flow:
  `현금흐름표 리스부채의 상환 (1,449,540,484) = (1,449,540,484);
  주석 리스부채의 상환 (1,449,540,000) = (1,449,540,000); 차이 484`.

Interpretation:

This is a direct evidence extraction improvement for lease repayments, not a
general scope or tolerance relaxation. Gate 1 remains below 70%; remaining
primary unresolved items are still concentrated in cash-flow reconciliation:
149 of 174 unresolved items.

## 2026-05-26 Asset Header Band Balance Delta

Refined asset balance column selection:

- Some asset balance tables have a first row that only repeats unit labels, a
  second row with current/prior fiscal period bands, and a third row with
  measurement labels such as `취득원가`, `상각누계액`, and `합계`.
- Asset total rows such as `합 계` now scan the first four header rows and can
  select the current-period carrying/`합계` column instead of falling back to
  the prior-period amount.
- PPE roll-forward ending rows such as `기말 유형자산` now use an explicit
  `유형자산 합계` family-total column instead of the gross-cost column.
- The ending-row family-total rule is deliberately limited to PPE. A broader
  v48/v49 experiment was rejected because it regressed existing intangible
  balance matches by applying the family-total heuristic to ordinary
  intangible ending rows.

Verification:

```bash
.venv/bin/python -m pytest tests/test_checks_reconciliation.py::test_check_reconciliation_targets_matches_asset_total_row_with_unit_and_period_header_bands tests/test_checks_reconciliation.py::test_check_reconciliation_targets_matches_asset_ending_row_with_asset_family_total_column tests/test_checks_reconciliation.py::test_check_reconciliation_targets_matches_asset_total_row_with_carrying_amount_column -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-26-hundred-v50 --no-fetch
```

Result:

- RED tests failed as expected before implementation.
- Focused asset header-band tests: 3 passed.
- Reconciliation/input focused tests: 103 passed.
- Full tests: 226 passed.
- 100-company corpus v50: generated reports 100/100, primary checks 543,
  matched 369, unresolved 174, no-difference rate 68.0%, judgment rate 100.0%.
- Delta from v47: primary checks +3, primary matched +3, primary unresolved
  unchanged, no regressed previously matched primary check IDs.
- Existing unresolved -> matched: 삼익THK intangible assets balance and
  현대건설 PPE balance.
- Newly exposed matched: 써니전자 intangible assets balance.
- Newly exposed unresolved checks: 써니전자 PPE balance and 풍산홀딩스
  intangible assets balance. These are coverage-expanded findings, not
  regressions of prior matched checks.

Interpretation:

This is a balance table-semantics improvement. It moves the tool toward direct
statement-to-note table reconciliation for asset balances, but Gate 1 remains
below 70%; remaining primary unresolved items are still concentrated in
cash-flow reconciliation: 149 of 174 unresolved items.

## 2026-05-26 Financial Instrument Trade Receivable Label Delta

Refined trade receivable balance extraction:

- Some financial-instrument category tables place the account label after
  classification columns, e.g. `금융자산, 범주 / 상각후원가로 측정하는
  금융자산 / 금융상품 / 매출채권 / 당기말 금액`.
- Trade receivable row-label detection now scans the first four text cells
  instead of the first three, while preserving the existing exclusions for
  `계약자산`, `대손`, and `손실충당`.
- This is direct evidence recovery from a numeric financial-instrument table,
  not a tolerance relaxation or broad candidate-scope expansion.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_reads_trade_receivables_from_fourth_financial_instrument_label_cell tests/test_checks_reconciliation.py::test_check_reconciliation_targets_matches_trade_receivable_financial_instrument_category_row -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py -q
.venv/bin/python -m pytest tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-26-hundred-v51 --no-fetch
```

Result:

- RED tests failed as expected before implementation.
- Focused financial-instrument trade receivable tests: 2 passed.
- Reconciliation input tests: 52 passed.
- Reconciliation check tests: 53 passed.
- Full tests: 228 passed.
- 100-company corpus v51: generated reports 100/100, primary checks 543,
  matched 370, unresolved 173, no-difference rate 68.1%, judgment rate 100.0%.
- Delta from v50: primary matched +1, primary unresolved -1, no regressed
  previously matched primary check IDs, no new or removed primary check IDs.
- Resolved 한국단자공업 trade receivables balance:
  `statement 유동매출채권 268,201,105,000 = note 10 매출채권
  268,201,105,000`.

Interpretation:

This is a narrow balance direct-evidence extraction improvement. Gate 1 remains
below 70%; remaining primary unresolved items are still concentrated in
cash-flow reconciliation: 149 of 173 unresolved items.

## 2026-05-26 Intangible Goodwill-Excluding Balance Delta

Refined combined intangible/goodwill balance extraction:

- Some intangible notes disclose a combined `무형자산 및 영업권` ending row,
  while the statement line is `무형자산` excluding goodwill.
- When the ending row has `영업권 이외의 무형자산` carrying-amount subtotal
  columns, the extractor now adds a goodwill-excluding balance candidate by
  summing only those subtotal columns.
- The combined total candidate remains available. A v52 replacement experiment
  was rejected because it regressed 현대글로비스 intangible balance by
  replacing a valid combined-total match.
- The final v53 rule treats goodwill-excluding evidence as an additional
  candidate, not as a replacement or tolerance relaxation.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_reads_intangible_balance_excluding_goodwill_from_combined_table -q
.venv/bin/python -m pytest tests/test_checks_reconciliation.py::test_check_reconciliation_targets_matches_intangible_balance_excluding_goodwill_from_combined_table tests/test_checks_reconciliation.py::test_check_reconciliation_targets_preserves_combined_intangible_and_goodwill_total_candidate -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-26-hundred-v53 --no-fetch
```

Result:

- RED tests failed as expected before implementation.
- Focused intangible/goodwill tests: 3 passed.
- Reconciliation/input focused tests: 108 passed.
- Full tests: 231 passed.
- 100-company corpus v53: generated reports 100/100, primary checks 543,
  matched 371, unresolved 172, no-difference rate 68.3%, judgment rate 100.0%.
- Delta from v51: primary matched +1, primary unresolved -1, no regressed
  previously matched primary check IDs, no new or removed primary check IDs.
- Resolved 한솔케미칼 intangible assets balance:
  `statement 기타무형자산 27,646,933,660` matched `note 10 기말 무형자산 및
  영업권 27,646,934,000` within note unit precision.

Interpretation:

This is a narrow balance direct-evidence extraction improvement for combined
intangible/goodwill tables. Gate 1 remains below 70%; remaining primary
unresolved items are still concentrated in cash-flow reconciliation: 149 of 172
unresolved items.

## 2026-05-26 Bond Principal Repayment Cash-Flow Delta

Refined bond financing cash-flow extraction:

- Some bond notes disclose a bond roll-forward outside the generic
  `재무활동에서 생기는 부채` note, with a `원금` row and an `상환에 따른 감소`
  column.
- The extractor now adds that principal repayment amount as a
  `bonds.financing_cashflow` candidate labeled `사채 원금 상환`.
- Broader bond carrying-amount movements remain available, but the financing
  subset selector can now choose the exact principal repayment when it
  reconciles to the CFS `사채의 상환` target.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_reads_bond_principal_repayment_from_bond_rollforward -q
.venv/bin/python -m pytest tests/test_checks_reconciliation.py::test_check_reconciliation_targets_selects_bond_principal_repayment_from_bond_rollforward -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-26-hundred-v54 --no-fetch
```

Result:

- RED tests failed as expected before implementation.
- Focused bond principal repayment tests: 2 passed.
- Reconciliation/input focused tests: 110 passed.
- Full tests: 233 passed.
- 100-company corpus v54: generated reports 100/100, primary checks 543,
  matched 372, unresolved 171, no-difference rate 68.5%, judgment rate 100.0%.
- Delta from v53: primary matched +1, primary unresolved -1, no regressed
  previously matched primary check IDs, no new or removed primary check IDs.
- Resolved 후성 bonds financing cash-flow:
  `statement 사채의 상환 (3,000,000,000)` matched `note 38 사채 원금 상환
  (3,000,000,000)`.

Interpretation:

This is a narrow direct-evidence improvement for bond principal repayment cash
flows, not a generic financing-liability scope expansion. Gate 1 remains below
70%; remaining primary unresolved items are still concentrated in cash-flow
reconciliation: 148 of 171 unresolved items.

## 2026-05-26 Current Other Receivables Balance Delta

Refined trade receivables balance extraction:

- Some balance sheet lines use a composite display such as `매출채권 및 기타유동채권`.
- The matching note can disclose the direct carrying amount formula in a single
  `매출채권 및 기타채권` table: `유동매출채권 + 기타 유동채권 + 유동 계약자산
  외의 유동 미수수익`.
- The extractor now treats the narrow labels `기타 유동채권`, `기타 비유동채권`,
  and `유동 계약자산 외의 유동 미수수익` as trade receivable ending-balance
  candidates only inside the existing trade receivable candidate path.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_reads_current_other_receivables_in_trade_receivable_note -q
.venv/bin/python -m pytest tests/test_checks_reconciliation.py::test_check_reconciliation_targets_combines_current_trade_receivables_and_other_current_receivables -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-26-hundred-v55 --no-fetch
```

Result:

- RED tests failed as expected before implementation.
- Focused current other receivables tests: 2 passed.
- Reconciliation/input focused tests: 112 passed.
- Full tests: 235 passed.
- 100-company corpus v55: generated reports 100/100, primary checks 543,
  matched 373, unresolved 170, no-difference rate 68.7%, judgment rate 100.0%.
- Delta from v54: primary matched +1, primary unresolved -1, newly unresolved
  primary check IDs 0.
- Resolved 한솔테크닉스 trade receivables balance:
  `statement 매출채권 및 기타유동채권 110,483,379,271` matched `note 7
  유동매출채권 + 기타 유동채권 + 유동 계약자산 외의 유동 미수수익
  110,483,379,000` within note unit precision.

Interpretation:

This is a narrow composite receivables direct-evidence improvement, not a broad
other-current-asset expansion. Gate 1 remains below 70%; remaining primary
unresolved items are still concentrated in cash-flow reconciliation: 148 of 170
unresolved items.

## 2026-05-26 Trade Receivables Current Net Header-Band Delta

Refined trade receivables net amount extraction:

- Some `매출채권 및 기타채권` notes use a two-row amount header:
  `당기말 / 총액 / 대손충당금 / 순액`.
- The previous selector treated the repeated `당기말` columns as all current
  columns and summed gross, allowance, and net values.
- The extractor now selects the current-period net column (`순액`, or equivalent
  carrying-amount labels) before falling back to current/noncurrent summation.
- Narrow component rows such as `미수금`, `미수수익`, `단기보증금`, and
  `장기보증금` are treated as trade receivable ending-balance candidates only
  inside the trade receivable candidate path.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_prefers_current_net_amount_in_trade_receivable_header_band tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_sums_current_trade_receivable_current_and_noncurrent_columns -q
.venv/bin/python -m pytest tests/test_checks_reconciliation.py::test_check_reconciliation_targets_matches_trade_receivables_using_current_net_header_band -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-26-hundred-v56 --no-fetch
```

Result:

- RED tests failed as expected before implementation.
- Focused current net header-band tests: 3 passed.
- Reconciliation/input focused tests: 114 passed.
- Full tests: 237 passed.
- 100-company corpus v56: generated reports 100/100, primary checks 543,
  matched 375, unresolved 168, no-difference rate 69.1%, judgment rate 100.0%.
- Delta from v55: primary matched +2, primary unresolved -2, newly unresolved
  primary check IDs 0.
- Resolved 아남전자 trade receivables balance:
  `statement 매출채권 및 기타유동채권 + 장기매출채권 및 기타비유동채권, 총액
  47,073,442` matched `note 4 합 계 + 장기보증금 47,073,442`.
- Resolved 롯데하이마트 trade receivables balance:
  `statement 매출채권및기타채권 43,905,467,245` matched `note 8 매출채권
  + 미수금 43,905,467,000` within note unit precision.

Interpretation:

This is a header-semantics and component-label improvement for receivables
balance evidence, not a tolerance relaxation. Gate 1 remains just below 70%;
remaining primary unresolved items are still concentrated in cash-flow
reconciliation: 148 of 168 unresolved items.

## 2026-05-26 Trade Receivables Statement Parent/Child Dedupe Delta

Refined trade receivables statement evidence:

- Some balance sheets disclose a composite parent line such as
  `매출채권 및 기타유동채권`, then repeat the same amount on the nested child
  line `매출채권`.
- The same pattern can occur for noncurrent receivables as
  `장기매출채권 및 기타비유동채권, 총액` plus `장기매출채권, 총액`.
- The statement-line combiner now dedupes only exact same-amount parent/child
  duplicates inside the same statement table and only for `trade_receivables`.
  Current and noncurrent parent lines are still summed when they represent
  different statement amounts.
- v57 was rejected: it removed the plain `매출채권` duplicate but left
  `장기매출채권, 총액`, so aggregate corpus metrics did not improve.

Verification:

```bash
.venv/bin/python -m pytest tests/test_checks_reconciliation.py::test_check_reconciliation_targets_dedupes_trade_receivable_parent_child_statement_lines -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-26-hundred-v57 --no-fetch
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-26-hundred-v58 --no-fetch
```

Result:

- RED test failed as expected before implementation and again after sharpening
  the child label to `장기매출채권, 총액`.
- Focused trade receivable parent/child test: 1 passed.
- Reconciliation/input focused tests: 115 passed.
- Full tests: 238 passed.
- 100-company corpus v57: generated reports 100/100, primary checks 543,
  matched 375, unresolved 168, no-difference rate 69.1%, judgment rate 100.0%;
  rejected because aggregate metrics were unchanged from v56.
- 100-company corpus v58: generated reports 100/100, primary checks 543,
  matched 376, unresolved 167, no-difference rate 69.2%, judgment rate 100.0%.
- Delta from v56: primary matched +1, primary unresolved -1, newly unresolved
  primary check IDs 0, false matched review sample count unchanged at 15.
- Resolved 한미글로벌 trade receivables balance:
  `statement 매출채권 및 기타유동채권 + 장기매출채권 및 기타비유동채권, 총액
  100,126,481,118` matched `note 11 매출채권 100,126,482,000` within note
  unit precision.

Interpretation:

This is a conservative statement-structure dedupe for duplicated receivable
presentation, not a broad duplicate-row collapse and not a note-candidate
relaxation. Gate 1 remains below 70%; remaining primary unresolved items are
still concentrated in cash-flow reconciliation: 148 of 167 unresolved items.

## 2026-05-26 Beginning Carrying-Amount Balance Guard

Refined balance-role classification:

- Labels such as `기초장부가액` contain the generic carrying-amount alias
  `장부가액`, but they are beginning balances, not ending balances.
- The prior classifier checked ending/carrying aliases before `기초`, causing
  beginning rows to enter ending-balance candidate pools.
- The classifier now applies the `기초` guard first. This removes false ending
  candidates without adding new candidate surfaces.
- A broader v59 experiment that combined PPE and right-of-use asset balance
  notes was rejected because it increased primary checks by 5 and created 5
  newly unresolved primary balance findings.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_does_not_treat_beginning_carrying_amount_as_ending_balance -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-26-hundred-v59 --no-fetch
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-26-hundred-v60 --no-fetch
```

Result:

- RED test failed as expected before implementation.
- Focused beginning carrying-amount guard test: 1 passed.
- Reconciliation/input focused tests: 116 passed.
- Full tests: 239 passed.
- 100-company corpus v59: rejected; primary checks increased from 543 to 548,
  primary unresolved increased from 167 to 172, and 5 newly unresolved primary
  PPE balance findings appeared.
- 100-company corpus v60: generated reports 100/100, primary checks 543,
  matched 376, unresolved 167, no-difference rate 69.2%, judgment rate 100.0%.
- Delta from v58: aggregate counts unchanged, newly unresolved primary check IDs
  0, false matched review sample diff empty.
- Evidence fidelity improvement: 한미글로벌 PPE balance no longer uses
  `note 16 기초장부가액 + 기말장부가액`; it uses `note 16 기말장부가액`
  only and remains correctly unresolved.

Interpretation:

This is a false-candidate guard, not a match-rate improvement. Gate 1 remains
below 70%; remaining primary unresolved items are still concentrated in
cash-flow reconciliation: 148 of 167 unresolved items.

## 2026-05-26 Payable-Increase Add-Back Cash-Flow Delta

Refined non-cash payable acquisition evidence:

- Some non-cash transaction notes disclose a row such as
  `무형자산 취득에 따른 미지급금 증가`.
- For INVENI, that source amount exactly bridges the acquisition roll-forward
  and CFS acquisition outflow: `5,012,218,000 + 4,217,418,000 =
  9,229,636,000`.
- The extractor now classifies only the narrow `취득에 따른 미지급금 증가`
  label as `noncash_payable_addback`. Existing broader payable-direction
  patterns, including `증가(감소)` and `취득 관련 미지급금 증가`, retain their
  prior semantics.
- v61 was discarded as incomplete evidence because it produced partial HTML
  output without corpus summary artifacts.

Verification:

```bash
.venv/bin/python -m pytest tests/test_checks_reconciliation.py::test_check_reconciliation_targets_adds_payable_increase_only_noncash_acquisition_when_it_completes_formula -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-26-hundred-v62 --no-fetch
```

Result:

- RED test failed as expected before implementation.
- Focused payable add-back test: 1 passed.
- Reconciliation/input focused tests: 117 passed.
- Full tests: 240 passed.
- 100-company corpus v62: generated reports 100/100, primary checks 543,
  matched 377, unresolved 166, no-difference rate 69.4%, judgment rate 100.0%.
- Delta from v60: primary matched +1, primary unresolved -1, newly unresolved
  primary check IDs 0, false matched review sample count unchanged at 15.
- Resolved INVENI intangible asset acquisition cash-flow:
  `note 13 취득 5,012,218,000 + note 29 무형자산 취득에 따른 미지급금 증가
  4,217,418,000 = CFS 무형자산의 취득 9,229,636,000`.

Interpretation:

This is a narrow source-label formula expansion, not a global payable sign flip
and not a tolerance relaxation. Gate 1 remains below 70%; remaining primary
unresolved items are still concentrated in cash-flow reconciliation: 147 of 166
unresolved items.

## 2026-05-26 Simple Financing Increase/Decrease Column Delta

Refined financing liability roll-forward extraction:

- Some financing liability notes disclose account rows such as `단기차입금` and
  `장기차입금` with simple action columns `증가` and `감소`.
- The previous extractor treated the table as a financing roll-forward but only
  fell back to the first cash-like numeric column, so it captured `증가` and
  missed the matching repayment column.
- The action-column detector now treats simple `증가` and `감소` headers as
  financing cash-flow columns when the table is already scoped to
  `재무활동에서 생기는 부채`.
- This is narrower than a general movement-column expansion because it still
  requires the existing financing liability row/account and table-scope guards.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_reads_simple_financing_increase_and_decrease_columns -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_reads_split_financing_cashflow_increase_and_decrease_columns tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_reads_financing_cashflow_rows_with_account_columns -q
.venv/bin/python -m pytest -q
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-26-hundred-v63 --no-fetch
```

Result:

- RED test failed as expected before implementation.
- Focused simple `증가`/`감소` financing-column test: 1 passed.
- Existing financing column guard tests: 2 passed.
- Full tests: 241 passed.
- 100-company corpus v63: generated reports 100/100, primary checks 543,
  matched 378, unresolved 165, no-difference rate 69.6%, judgment rate 100.0%.
- Delta from v62: primary matched +1, primary unresolved -1, newly unresolved
  primary check IDs 0.
- Resolved 후성 borrowings financing cash-flow:
  `주석 재무활동현금흐름 차입금 65,534,356,000 - 71,682,404,000
  + 25,000,000,000 - 750,000,000 = 18,101,952,000`, matching CFS
  `18,101,952,367` within disclosure precision.

Interpretation:

This is a narrow action-column extraction fix, not a financing scope expansion
or tolerance relaxation. Gate 1 remains below 70%; remaining primary unresolved
items are still concentrated in cash-flow reconciliation: 146 of 165 unresolved
items.

## 2026-05-26 Borrowing Action Row Label Delta

Refined financing liability roll-forward account-column extraction:

- Some financing liability notes disclose borrowing actions as row labels, such
  as `새로운 차입금, 재무활동에서 생기는 부채의 증가` and `차입금의 상환,
  재무활동에서 생기는 부채의 감소`.
- The previous extractor recognized the table as a financing roll-forward but
  did not send those row labels through the account-column extractor, so it
  captured only the fallback long-term borrowing columns and missed short-term
  borrowing proceeds/repayments.
- The row-label detector now admits the narrow aliases `새로운차입금` and
  `차입금의상환` when the row is already scoped to `재무활동에서 생기는 부채`.
- This is narrower than a financing scope expansion because it still requires
  the existing table-scope guard and account-column headers such as `단기차입금`
  and `장기 차입금`.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_reads_new_borrowing_and_repayment_rows_with_account_columns tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_reads_financing_cashflow_rows_with_account_columns tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_reads_simple_financing_increase_and_decrease_columns -q
.venv/bin/python -m pytest -q
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-26-hundred-v64 --no-fetch
```

Result:

- RED test failed as expected before implementation.
- Focused borrowing action row-label test plus existing financing guards: 3
  passed.
- Full tests: 242 passed.
- 100-company corpus v64: generated reports 100/100, primary checks 543,
  matched 379, unresolved 164, no-difference rate 69.8%, judgment rate 100.0%.
- Delta from v63: primary matched +1, primary unresolved -1, newly unresolved
  primary check IDs 0.
- Resolved 롯데이노베이트 borrowings financing cash-flow:
  `3,073,019,000 + 69,987,204,000 - 8,073,019,000 - 25,705,040,000 =
  39,282,164,000`, matching CFS `39,282,164,050` within disclosure precision.

Interpretation:

This is a narrow action-row label extraction fix, not a tolerance relaxation or
unscoped duplicate-note inclusion. Gate 1 remains below 70%; remaining primary
unresolved items are still concentrated in cash-flow reconciliation: 145 of 164
unresolved items.

## 2026-05-26 Trade Receivable Allowance Netting Delta

Refined trade receivable balance candidate extraction:

- Some `매출채권 및 기타채권` notes disclose current gross receivables and
  immediately adjacent allowance rows instead of a separate current net column.
- The previous extractor admitted gross `매출채권`, `미수금`, and `미수수익`
  rows, but skipped `대손충당금` rows, so the note subset could not reproduce
  the statement line `매출채권 및 기타유동채권`.
- Trade receivable note balances now admit allowance labels such as
  `대손충당금`, `손실충당금`, `충당금`, and `손상차손누계액`; the existing
  trade receivable contribution logic subtracts those balances in subset
  formulas.

Verification:

```bash
.venv/bin/python -m pytest tests/test_checks_reconciliation.py::test_check_reconciliation_targets_nets_trade_receivable_allowances_in_current_receivable_note tests/test_checks_reconciliation.py::test_check_reconciliation_targets_matches_trade_receivables_using_current_net_header_band tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_reads_current_other_receivables_in_trade_receivable_note tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_prefers_current_net_amount_in_trade_receivable_header_band -q
.venv/bin/python -m pytest -q
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-26-hundred-v65 --no-fetch
```

Result:

- RED test failed as expected before implementation.
- Focused trade receivable allowance and guard tests: 4 passed.
- Full tests: 243 passed.
- 100-company corpus v65: generated reports 100/100, primary checks 543,
  matched 380, unresolved 163, no-difference rate 69.98%, judgment rate 100.0%.
- Delta from v64: primary matched +1, primary unresolved -1, newly unresolved
  primary check IDs 0.
- Resolved 계양전기 trade receivables balance:
  `84,924,256,000 - 204,523,000 + 123,579,000 - 330,000 + 1,460,000 =
  84,844,442,000`, matching statement `84,844,441,793` within display precision.

Interpretation:

This is a narrow note-subset candidate fix for receivable allowance netting, not
a generic allowance sign flip outside trade receivables. Gate 1 was still just
below 70% on exact arithmetic at v65 (`380/543 = 69.9816%`).

## 2026-05-26 Display Unit Boundary Tolerance Delta

Refined note display precision handling:

- The previous tolerance helper used `unit_multiplier - 1`, so a note shown in
  `단위: 백만원` failed when the statement and note differed by exactly
  `1,000,000`.
- The tolerance helper now treats the display unit itself as the precision
  boundary, while preserving explicit `tolerance=0` behavior.
- Cash-flow formula precision accumulation uses the same unit-boundary rule
  across source components.

Verification:

```bash
.venv/bin/python -m pytest tests/test_checks_reconciliation.py::test_check_reconciliation_targets_allows_exact_display_unit_boundary_for_note_precision tests/test_checks_reconciliation.py::test_check_reconciliation_targets_allows_thousand_won_rounding_when_tolerance_is_default tests/test_checks_reconciliation.py::test_check_reconciliation_targets_limits_thousand_unit_rounding_to_under_one_thousand tests/test_checks_reconciliation.py::test_check_reconciliation_targets_does_not_allow_million_tolerance_for_thousand_unit_amount tests/test_checks_reconciliation.py::test_check_reconciliation_targets_accumulates_rounding_tolerance_for_cashflow_formula_components -q
.venv/bin/python -m pytest -q
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-26-hundred-v66 --no-fetch
```

Result:

- RED test failed as expected before implementation.
- Focused display-unit tolerance tests: 5 passed.
- Full tests: 244 passed.
- 100-company corpus v66: generated reports 100/100, primary checks 543,
  matched 381, unresolved 162, no-difference rate 70.17%, judgment rate 100.0%.
- Delta from v65: primary matched +1, primary unresolved -1, newly unresolved
  primary check IDs 0.
- Resolved KB금융 intangible assets balance: statement
  `1,966,684,000,000` versus note `1,966,683,000,000`, a difference of exactly
  one `단위: 백만원` display unit.

Interpretation:

This is a display-unit boundary correction, not a broad tolerance increase.
Gate 1 is now met on exact arithmetic: `381 / 543 = 70.1657%`. Remaining
primary unresolved items are still concentrated in cash-flow reconciliation:
145 of 162 unresolved items.

## 2026-05-26 Financing Account-Column Cash-Flow Delta

Expanded financing liability cash-flow evidence with two narrow rules:

- Financing liability roll-forward rows labeled `현금흐름` are now read across
  account columns such as `단기사채`, `사채`, `차입금`, and `리스부채`.
- Non-cash financing movement labels such as `사채할인발행차금상각`,
  `외화환산`, `유동성대체`, `사업결합`, and `기타` are excluded from generic
  financing cash-flow fallback extraction.
- Cash-flow statement rows such as `단기사채의 차입` and `사채의 차입` are
  classified as bonds proceeds, matching DART filings that describe bond
  issuance as borrowing.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_excludes_bond_discount_amortization_from_financing_cashflow -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_classifies_bond_borrowing_as_proceeds -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-26-hundred-v68 --no-fetch
```

Result:

- RED tests failed as expected before implementation.
- Focused reconciliation input/check tests: 123 passed.
- Full tests: 246 passed.
- 100-company corpus v68: generated reports 100/100, primary checks 577,
  matched 409, unresolved 168, no-difference rate 70.88%, judgment rate 100.0%.
- Delta from v66: primary checks +34, primary matched +28, primary unresolved
  +6, no-difference rate +0.72pp, false matched review samples unchanged at 15.
- Resolved 한화오션 bonds financing cash-flow: CFS
  `단기사채의 차입 166,420,945,212 + 사채의 차입 99,578,890,000 -
  사채의 상환 20,000,000,000 = 245,999,835,212`, matching note financing
  cash-flow evidence `146,421,000,000 + 99,579,000,000 = 246,000,000,000`
  within disclosure precision.
- Removed a low-quality 효성화학 bonds unresolved item where the old evidence was
  a zero-valued note movement rather than substantive cash-flow evidence.

Interpretation:

This is accepted as a coverage and fidelity expansion. It exposes additional
financing cash-flow checks because account-column `현금흐름` rows now provide
substantive note evidence. The denominator increased, but matched checks grew
faster than unresolved checks and the primary no-difference rate improved from
70.17% to 70.88%.

## 2026-05-26 Bond Issuance Fee Payment Sign Delta

Refined CFS bond financing sign semantics:

- Cash-flow statement rows labeled like `사채발행비 지급` are now treated as
  bonds financing cash outflows.
- Generic `사채발행비용` rows remain excluded, preserving the distinction
  between cash-flow payment rows and expense/cost labels.
- The rule is label-driven and applies before the generic `사채 + 발행`
  proceeds classifier.

Verification:

```bash
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_treats_bond_issuance_fee_payment_as_financing_outflow -q
.venv/bin/python -m pytest tests/test_reconciliation_inputs.py tests/test_checks_reconciliation.py -q
.venv/bin/python -m pytest -q
.venv/bin/dart-footing workpaper-corpus /private/tmp/dart_footing_reconciler_manifest_v34_cached_abs.json out/corpus/run_2026-05-26-hundred-v69 --no-fetch
```

Result:

- RED test failed as expected before implementation.
- Focused reconciliation input/check tests: 124 passed.
- Full tests: 247 passed.
- 100-company corpus v69: generated reports 100/100, primary checks 577,
  matched 410, unresolved 167, no-difference rate 71.06%, judgment rate 100.0%.
- Delta from v68: primary matched +1, primary unresolved -1, newly unresolved
  primary check IDs 0, false matched review samples unchanged at 15.
- Resolved 세아제강 bonds financing cash-flow by changing `사채발행비 지급`
  from `+447,613,200` to `(447,613,200)` in the CFS financing net formula:
  `140,000,000,000 - 447,613,200 - 80,000,000,000 = 59,552,386,800`,
  matching note financing cash-flow evidence `59,552,386,800`.

Interpretation:

This is a narrow CFS label sign correction. It does not broaden debt movement
matching and does not include generic issuance-cost expense rows as primary
financing cash-flow evidence.

## 2026-05-27 HTML Delivery Studio Delta

Applied the new PAS Delivery Studio report surface to the HTML workpaper output:

- Added a first-viewport reviewer brief with `현재 상태`, `왜 중요한가`, and
  `다음 행동`.
- Changed status badges from colored fills to neutral badges with point-signal
  dots and semantic borders.
- Rendered cash-flow formula evidence as a two-column table (`구분` / `내용`)
  instead of stacked free text.
- Kept the first-screen count scoped to primary reconciliation checks only.
  Supporting total/table diagnostics no longer inflate the reviewer action
  count.
- Fixed nested review-card CSS so formula tables are not narrowed by the card
  definition-list grid.

Verification:

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/pytest tests/test_cli_workpaper.py -q
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/pytest -q
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/dart-footing workpaper-corpus out/corpus/manifest_2026-05-26-hundred.json out/corpus/run_2026-05-27-hundred-v82 --no-fetch
node <playwright visual check for 세아제강 desktop 1440px / mobile 390px>
```

Result:

- HTML-focused tests: 20 passed.
- Full tests: 261 passed.
- v82 cached corpus render: 99/100 reports generated. 셀트리온 remained a
  source-access gap because DART fetch failed with SSL EOF; v82 is therefore
  HTML-format evidence only.
- Accepted reconciliation baseline remains v81: 100/100 generated reports,
  primary matched 419/575, primary unresolved 156, primary no-difference rate
  72.87%, primary judgment rate 100.0%.
- Browser visual checks passed for representative report
  `out/corpus/run_2026-05-27-hundred-v82/reports/세아제강_2024.html`:
  section brief present, status dot rendered, formula table visible, formula
  table width fits both desktop and mobile viewports. Screenshots:
  `out/visual-checks/v82-desktop.png`, `out/visual-checks/v82-mobile.png`.

Interpretation:

This is a reviewer-facing output improvement, not a reconciliation algorithm
change. It should make the current evidence easier to inspect without changing
the accepted v81 corpus metrics.
