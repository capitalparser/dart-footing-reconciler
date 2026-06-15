# Nonfinancial 10-Industry Semantic Report Verification Smoke

Date: 2026-06-10

## Purpose

Run the semantic report verification plan against 10 companies from different
nonfinancial industries. Financial, insurance, securities, banking, and REIT
samples were excluded from this slice. Industry labels here are selection tags
only; they are not runtime routing keys.

## Selection

Source cache: `out/corpus/run_2026-06-08-statement-ties-baseline/raw`

Manifest: `out/corpus/manifest_2026-06-10-nonfinancial-industry-10.json`

| Company | Selection industry | Raw source present |
|---|---|---|
| 삼성SDI | 배터리/전자소재 제조 | yes |
| 현대자동차 | 완성차 | yes |
| 셀트리온 | 바이오/제약 | yes |
| 롯데쇼핑 | 유통/리테일 | yes |
| 현대건설 | 건설 | yes |
| SGC에너지 | 에너지/발전 | yes |
| CJ대한통운 | 물류 | yes |
| 더존비즈온 | 소프트웨어/IT서비스 | yes |
| 롯데정밀화학 | 정밀화학 | yes |
| 한화오션 | 조선 | yes |

## Commands

```bash
uv run dart-footing workpaper-corpus out/corpus/manifest_2026-06-10-nonfinancial-industry-10.json out/corpus/run_2026-06-10-nonfinancial-industry-10 --no-fetch
uv run pytest tests/test_signatures.py tests/test_checks_statement_ties.py tests/test_check_pipeline.py tests/test_report_frame.py -q
```

## Result Summary

Output directory: `out/corpus/run_2026-06-10-nonfinancial-industry-10`

- Generated reports: 10/10
- Failed samples: 0
- Focused baseline tests: 43 passed
- Total checks: 8,805
- Matched: 4,396
- Explainable gaps: 2
- Unexplained gaps: 630
- Parse uncertain: 3,683
- Not tested: 94
- Primary checks: 70
- Primary matched: 52
- Primary unresolved: 18
- Primary no-difference rate: 74.3%
- Primary judgment rate: 95.7%
- Note assertion checks: 955
- Note assertion matched: 833
- Validation-relevant unknown layout items: 449

## Company Results

| Company | Industry | Status | Statements | Notes | Checks | Primary | Primary matched | Primary unresolved | BS tie | Cash tie | Equity tie | FS-note | CFS-note | Note-note | Total checks |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 삼성SDI | 배터리/전자소재 제조 | generated | 4 | 85 | 771 | 5 | 5 | 0 | 1 | 0 | 1 | 8 | 2 | 0 | 656 |
| 현대자동차 | 완성차 | generated | 5 | 87 | 835 | 7 | 4 | 3 | 1 | 1 | 1 | 10 | 3 | 3 | 685 |
| 셀트리온 | 바이오/제약 | generated | 4 | 96 | 889 | 5 | 5 | 0 | 1 | 0 | 0 | 4 | 0 | 1 | 827 |
| 롯데쇼핑 | 유통/리테일 | generated | 4 | 104 | 871 | 7 | 4 | 3 | 1 | 1 | 1 | 9 | 4 | 0 | 761 |
| 현대건설 | 건설 | generated | 4 | 92 | 992 | 10 | 4 | 6 | 1 | 1 | 1 | 10 | 3 | 2 | 806 |
| SGC에너지 | 에너지/발전 | generated | 4 | 112 | 901 | 1 | 1 | 0 | 1 | 1 | 1 | 7 | 1 | 0 | 745 |
| CJ대한통운 | 물류 | generated | 5 | 97 | 1,026 | 12 | 11 | 1 | 1 | 1 | 1 | 10 | 3 | 0 | 882 |
| 더존비즈온 | 소프트웨어/IT서비스 | generated | 4 | 85 | 982 | 7 | 3 | 4 | 1 | 1 | 1 | 11 | 4 | 0 | 858 |
| 롯데정밀화학 | 정밀화학 | generated | 4 | 70 | 763 | 5 | 4 | 1 | 1 | 0 | 0 | 8 | 1 | 0 | 704 |
| 한화오션 | 조선 | generated | 5 | 93 | 775 | 11 | 11 | 0 | 1 | 1 | 1 | 8 | 3 | 2 | 661 |

## Observations

- The 10-company nonfinancial slice generated all HTML reports without fetch.
- Statement-level checks were present across the slice: BS equation emitted for
  every company, cash tie for 7/10, and equity tie for 8/10.
- The weakest primary slices were 현대건설, 더존비즈온, 현대자동차, and 롯데쇼핑.
  These remain useful follow-up targets because the failures are across
  different nonfinancial report shapes, not a single industry cluster.
- The plan's core risk remains visible: 4,527 unknown/low-confidence layout
  items, of which 449 are validation-relevant. This supports continuing the
  semantic layer work without introducing company-specific routing.

## Semantic Harness Bridge Follow-Up

Implementation run: `out/corpus/run_2026-06-10-semantic-harness-bridge-nonfinancial-10`

Additional verification after adding the semantic dataset/candidate layer and
verification harness bridge:

```bash
uv run pytest -q
uv run dart-footing workpaper-corpus out/corpus/manifest_2026-06-10-nonfinancial-industry-10.json out/corpus/run_2026-06-10-semantic-harness-bridge-nonfinancial-10 --no-fetch
```

Result:

- Full pytest: 735 passed
- Generated reports: 10/10
- Failed samples: 0
- Total checks: 8,805
- Primary checks: 70
- Primary matched: 52
- Primary unresolved: 18
- Validation-relevant unknown layout items: 449

The semantic layer now emits source-backed table/amount facts and validation
candidates for both `statement_note` and `note_internal`, while the public
`assemble_report_checks()` output remains a flat `list[CheckResult]` for CLI and
corpus callers.

## Harness Layer, UI Contract, And Accuracy Follow-Up

Implementation run: `out/corpus/run_2026-06-10-harness-layer-nonfinancial-10`

The verification pipeline now exposes explicit harness runs while keeping the
public check assembly contract stable:

- `statement_note`: financial statement body to note validation
- `note_internal`: validation inside note contents
- `statement_cross`: financial statement body to financial statement body
- `prior_report`: current filing to prior filing when provided

The report UI continues to use the shared `evidence_cockpit` app-shell contract.
The design kit now treats `보고서 순서` and `검증 범위` as audit verification
optional tabs, and DART report rows expose reader-facing scope labels instead of
internal harness terms.

Accuracy strategy note:

- Report count is a coverage and regression tool, not an accuracy metric.
- Accuracy claims require a reviewed Gold Set and false-match review.
- The 10-company nonfinancial corpus remains the Stratified Smoke set.

Post-migration verification:

```bash
npm --prefix /Users/kjun/vault/01_Projects/00_personal_agent_system/design-kit/typescript run typecheck
npm --prefix /Users/kjun/vault/01_Projects/00_personal_agent_system/design-kit/typescript test
python3 /Users/kjun/vault/Harness/scripts/check_design_kit.py
uv run pytest -q
uv run dart-footing workpaper-corpus out/corpus/manifest_2026-06-10-nonfinancial-industry-10.json out/corpus/run_2026-06-10-harness-layer-nonfinancial-10 --no-fetch
```

Result:

- Design-kit typecheck: passed
- Design-kit tests: 9 passed
- `check_design_kit.py`: `design kit verify ok`
- Full pytest: 736 passed
- Generated reports: 10/10
- Failed samples: 0
- Total checks: 8,805
- Primary checks: 70
- Primary matched: 52
- Primary unresolved: 18
- Validation-relevant unknown layout items: 449
