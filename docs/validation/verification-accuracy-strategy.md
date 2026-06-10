# Verification Accuracy Strategy

## Position

보고서 수는 정확도 지표가 아니다. More reports improve layout coverage,
industry variety, and regression discovery only when the corpus is stratified
and each evaluation tier has a clear purpose. Accuracy claims require reviewed
expectations, source evidence, and false-match review.

## Test Set Tiers

### Gold Set

Use 20-30 reviewed filings with expected primary outcomes. Each sample records
company, industry, report year, source file, expected validation outcomes,
reviewed evidence location, and reviewer note. This set measures accuracy.

### Stratified Smoke

Use 10-20 cached nonfinancial filings across different industries. This set
guards parser/render/harness regressions after every substantial change. The
2026-06-10 nonfinancial 10-company manifest is the first smoke set.

### Broad Corpus

Use 100+ cached filings to discover format drift, layout families, unknown
tables, and performance regressions. This set is not an accuracy score by
itself because most rows are not manually labeled.

### Adversarial Set

Use manually reviewed edge cases for false positives: sign reversals,
non-cash movements, subtotal rows, prior-year columns, duplicate labels,
mixed units, disclosure-only tables, and ambiguous note references.

## Metrics

- false-match rate: matched results whose evidence does not support the
  conclusion. This is the highest-risk metric.
- primary no-difference rate: primary checks with zero or tolerated difference.
- reviewed accuracy rate: labeled Gold Set checks where the automated judgment
  equals the reviewed expectation.
- parse-uncertain rate: checks blocked by source extraction or table-shape
  uncertainty.
- validation-relevant unknown layout count: unknown tables that likely affect
  validation.
- evidence completeness rate: checks that retain source locations for every
  material amount.
- layer-level rates: measure `재무제표 본문-주석`, `주석 내부`,
  `현금흐름표-주석`, `재무제표 본문 간`, and `전기 보고서` separately.

## Promotion Policy

A rule change can improve coverage only if it does not increase false matches
in the Gold Set or Adversarial Set. A higher match rate alone is not accepted.
Every accepted improvement must preserve source location, label uncertainty,
and a reviewer-readable next action for unresolved items.

## Near-Term Expansion

Keep the current nonfinancial 10-company smoke set for every harness/UI change.
Build the Gold Set next by reviewing representative samples from manufacturing,
automotive, biopharma, retail, construction, energy, logistics, software,
chemicals, and shipbuilding. Expand the Broad Corpus only after the Gold Set
can distinguish true accuracy gains from parser coverage gains.
