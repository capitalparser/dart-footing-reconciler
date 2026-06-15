# DART Footing Universal Audit Reconciliation Work Order

Date: 2026-05-26
Owner: DART footing reconciler
Status: approved work order

## Verdict

Conditional.

The current tool has moved beyond a single-company prototype, but it is not yet
an audit-grade universal footing and reconciliation engine. The 100-company
corpus run generated all reports and reached 100.0% primary judgment coverage,
but primary no-difference reconciliation is still 53.6%. The next phase must
replace label-only matching with scoped, evidence-preserving table semantics and
formula search.

Current evidence:

- Corpus: `out/corpus/run_2026-05-26-hundred-v2/`
- Samples: 100
- Generated reports: 100
- Primary checks: 509
- Primary matched: 273
- Primary unresolved: 236
- Primary no-difference rate: 53.6%
- Primary judgment rate: 100.0%

## Objective

Build the DART footing verification tool so that, for any listed-company report,
reviewers can compare and reconcile:

- statement of financial position to notes
- income statement / statement of comprehensive income to notes
- statement of changes in equity to notes
- statement of cash flows to notes
- note-to-note internal consistency

The result must show the original report tables, the matched note evidence, the
formula used, differences, and follow-up classification in audit-review language.

## Non-Negotiable Product Rules

1. Direct report evidence comes first.
   - The UI must show source statement rows and source note tables, not only
     normalized values.
   - Every material amount must retain source location: statement/note, section,
     table, row, column, raw label, and unit.

2. A match requires a reproducible formula.
   - `matched` is allowed only when the tool can show the exact source amounts
     and arithmetic.
   - Do not mark as matched because a nearby value exists.
   - Do not plug unexplained numbers into a formula.

3. Real differences and automation limits are separate.
   - `차이내역 확인 필요`: source evidence is found and a real residual
     difference remains.
   - `자동화 보완 필요`: source evidence is incomplete or table semantics are
     not reliable enough.
   - `대응 주석 미확인`: the statement line exists but no usable numeric note
     table is found.
   - `표 구조 해석 필요`: table-local structure is ambiguous.

4. Consolidated and separate scopes are independent.
   - Do not mix consolidated statements with separate notes.
   - Do not use duplicated note sets from a later separate section when
     reconciling consolidated statements.
   - Scope selection must be visible at the top of the report.

5. Policy notes are not primary reconciliation evidence.
   - Accounting policy paragraphs can support reviewer context.
   - Numeric reconciliation must use numeric note tables.

6. No company-specific hardcoding.
   - Rules may encode table classes, accounting concepts, Korean label aliases,
     sign conventions, and formula templates.
   - Rules must not depend on one company name, one note number, or one fixed
     DART layout.

## Required Architecture

### Layer 1. Report Scope Model

Create an explicit report scope model:

```text
Report
  ├─ consolidated context
  │   ├─ financial statements
  │   └─ notes
  └─ separate context
      ├─ financial statements
      └─ notes
```

Each context must carry:

- statement type
- period columns
- note block range
- unit context
- acode context when available
- raw section boundaries

Acceptance criteria:

- A report with both consolidated and separate financial statements renders
  independent reconciliation results for each scope.
- The same note number appearing in both scopes does not create duplicate
  candidates inside one reconciliation.
- Tests cover reports where scope is explicit in titles and reports where scope
  is inferred from embedded statement boundaries.

### Layer 2. Table Semantic Classifier

Every numeric table used in reconciliation must be classified before matching.

Required table classes:

- statement table
- balance detail table
- movement table
- disposal proceeds table
- non-cash transaction table
- financing liability movement table
- expense by nature table
- depreciation/amortization allocation table
- equity movement / dividend table
- EPS table
- income tax table
- commitment table
- impairment table
- fair value table
- policy-only or narrative table
- unsupported table

For each table, infer:

- reporting scope
- period columns
- unit multiplier
- row label column
- total/subtotal rows
- amount role columns
- sign convention
- account family

Acceptance criteria:

- `약정액`, `공정가치`, `손상`, `정책`, `전기 별도 표` are not used as direct
  cash-flow evidence unless their table class allows it.
- `당기 및 전기` comparative tables are retained.
- Dedicated prior-period tables are excluded from current-period primary
  reconciliation.

### Layer 3. Candidate Evidence Pool

Build a candidate pool for each statement line instead of selecting one note row
directly.

Candidate fields:

- account key
- source scope
- source table class
- source label
- amount
- normalized amount
- unit multiplier
- period role
- sign role
- evidence score
- exclusion reason if rejected

Evidence scoring dimensions:

- account taxonomy match
- note title match
- table class match
- row label match
- column semantic match
- period match
- amount direction
- acode match
- scope match
- duplicate candidate penalty

Acceptance criteria:

- The report can show both included and excluded candidates for a primary
  unresolved item.
- Candidate exclusion reasons are human-readable, e.g. `약정표`, `전기표`,
  `정책 주석`, `공정가치 표`, `scope 불일치`.

### Layer 4. Formula Engine

Move from single-row matching to formula-driven reconciliation.

Formula engine requirements:

- formula templates are account-family specific
- candidate subset search is allowed only within compatible table classes
- each included term must have a source location
- each excluded term must have an exclusion reason
- no formula can use more than the configured maximum number of terms without
  marking the result as requiring review
- tolerances must follow source units and report precision

Formula result types:

- direct match
- formula match
- formula residual difference
- insufficient evidence
- conflicting evidence

## Statement-Specific Requirements

### Statement of Financial Position

Primary goal:

Reconcile each FSC statement account to note balances and sub-ledger-style
tables.

Required account families:

- cash and cash equivalents
- short-term and long-term financial assets
- trade receivables and other receivables
- contract assets
- inventories
- assets held for sale
- property, plant and equipment
- right-of-use assets
- intangible assets
- investment property
- investments in subsidiaries, associates, and joint ventures
- deferred tax assets/liabilities
- trade payables and other payables
- borrowings
- bonds
- lease liabilities
- provisions
- equity accounts

Rules:

- Current and non-current splits may be in statement, notes, or both.
- Composite statement labels such as `매출채권 및 기타채권` must be reconciled
  to all relevant note rows, not only the row containing `매출채권`.
- If the statement line is broader than one note row, build a sum formula.
- If the note row is broader than the statement line, classify as
  `차이내역 확인 필요` or `자동화 보완 필요` depending on whether detail evidence
  is available.

Acceptance criteria:

- For every primary balance target, the side panel shows all matched note
  tables and the formula.
- Remaining unmatched balances have one of: no corresponding note table,
  scope conflict, composite account detail missing, or real residual difference.

### Income Statement / Statement of Comprehensive Income

Primary goal:

Render the statement in original order and reconcile material income statement
rows to notes.

Required account families:

- revenue
- cost of sales
- selling and administrative expenses
- expenses by nature
- finance income and finance costs
- other income and other expenses
- equity-method gains/losses
- income tax expense/income
- EPS and diluted EPS
- OCI items where note tables exist

Rules:

- Income statement display must preserve report order from revenue downward.
- Cost of sales and selling/admin expenses reconcile to expense notes and, where
  relevant, expense-by-nature notes.
- Depreciation and amortization reconcile across expense-by-nature notes and
  asset-note allocation tables.
- Income tax labels must allow expense/income presentation without hardcoding
  one direction.
- EPS labels must allow profit/loss presentation without hardcoding one
  direction.

Acceptance criteria:

- `매출`, `매출원가`, `판매비와관리비`, `법인세비용(수익)`, `주당이익(손실)`
  display matched note references when the report includes the numeric note.
- Positive/negative presentation does not create false mismatches.

### Statement of Changes in Equity

Primary goal:

Reconcile beginning equity, comprehensive income, transactions with owners, and
ending equity to notes and prior/current period continuity.

Required checks:

- prior year ending balance to current year beginning balance
- beginning retained earnings to retained earnings note
- profit/loss to income statement
- OCI to statement of comprehensive income and OCI notes
- dividends to dividend / retained earnings appropriation notes
- share capital and capital surplus movements to equity notes
- treasury shares to treasury share notes
- ending total equity to statement of financial position

Rules:

- Treat capital transactions separately from comprehensive income.
- Dividend amounts may appear in cash flow, equity statement, and notes; all
  three should be compared when available.
- A prior-year beginning/ending mismatch must be shown with source references.

Acceptance criteria:

- The report contains a dedicated equity reconciliation section.
- Dividends are linked across equity statement, cash flow statement, and note
  evidence when all exist.

### Statement of Cash Flows

Primary goal:

For investing and financing activities, reconcile each cash-flow line to note
evidence. For operating cash flow notes, reconcile adjustment rows to income
statement or note amounts where possible.

Investing activity required formulas:

```text
cash acquisition of PPE
= movement-table acquisition
- unpaid acquisition increase
+ unpaid acquisition decrease
- lease/right-of-use non-cash additions
- business-combination additions
- transfers/reclassifications
```

```text
cash disposal of PPE
= direct disposal proceeds
or disposal carrying amount +/- disposal gain/loss +/- disposal receivable change
```

The same pattern applies to intangible assets and investment property.

Financing activity required formulas:

```text
net borrowing cash flow
= proceeds - repayments
= financing liability movement table cash-flow column
```

```text
bond cash flow
= issuance - redemption - issue costs where separately disclosed
= financing liability movement table cash-flow column
```

```text
lease liability cash flow
= lease principal payments
= financing liability movement table cash-flow column
```

Operating activity required comparisons:

- depreciation and amortization adjustments to asset notes and expense notes
- gain/loss on disposal to disposal note and other income/expense note
- finance income/cost adjustments to finance income/cost notes
- income tax paid/refund to income tax note where disclosed

Acceptance criteria:

- Cash-flow reconciliation UI shows formula rows, not prose-only explanation.
- If a direct note table exists, the formula uses it before derived bridge
  formulas.
- If residual difference remains, the report shows source terms and residual,
  not a generic explanation.

### Note-to-Note Reconciliation

Primary goal:

Validate that related notes agree with each other before comparing them to
financial statements.

Required note-to-note checks:

- PPE movement table to disposal proceeds table
- intangible movement table to disposal proceeds table
- movement table acquisition to non-cash transaction note
- financing liability note to borrowings/bonds/lease notes
- expense-by-nature note to depreciation/amortization allocation notes
- income tax note subtotals to tax expense summary
- EPS note numerator to profit/loss attributable to owners
- dividend note to equity/cash-flow dividend rows
- note table subtotals to note table totals

Rules:

- If multiple same-account candidates exist, all comparable candidates must
  agree or the result becomes `conflicting evidence`.
- Do not select one convenient candidate while ignoring other same-scope
  candidates.

Acceptance criteria:

- The report has a note-to-note section separate from statement-note
  reconciliation.
- Conflicting note candidates are visible with amounts and source locations.

## UI / Report Requirements

The HTML/PDF output must support reviewer workflow:

- top-level scope selector: `연결`, `별도`
- first viewport verdict and KPI strip
- statement source tables rendered in original order
- clicking an FSC account opens a right-side note evidence panel
- cash-flow reconciliation rendered as formula table
- note-total verification renders source note tables with issue highlights
- review queue lists only items that need reviewer attention
- policy notes hidden from primary evidence but available as context
- machine terms hidden from default UI

Required Korean status labels:

- `대사 완료`
- `차이내역 확인 필요`
- `대응 주석 미확인`
- `자동화 보완 필요`
- `표 구조 해석 필요`
- `검증 제외`
- `주석 간 금액 불일치`

Forbidden UI patterns:

- generic text such as `산식화하세요`
- JSON/schema/raw-field terms in primary reviewer view
- policy paragraphs displayed as numeric evidence
- hover-only evidence that truncates source tables on mobile

## Accuracy Targets

### Gate 1. Current 100-company corpus

Required to pass next implementation stage:

- primary judgment rate: at least 95%
- primary no-difference rate: at least 70%
- false matched: 0 known cases
- generated reports: 100/100
- all tests pass

### Gate 2. Expanded 300-company corpus

Required:

- primary judgment rate: at least 97%
- primary no-difference rate: at least 85%
- false matched: 0 known cases
- industry-specific failure clusters documented

### Gate 3. Audit-review readiness

Required:

- primary judgment rate: at least 98%
- primary no-difference rate: at least 90%
- reviewer can reproduce every matched result from source tables
- unresolved items have actionable reason categories

Important:

The 90% hurdle is not permission to over-match. A conservative unresolved result
is better than a false matched result.

## Implementation Phases

### Phase 1. Unresolved Taxonomy and Baseline Lock

Deliverables:

- `primary_unresolved_taxonomy.json`
- `primary_unresolved_taxonomy.md`
- per-check-type counts
- per-company low-success list
- top 20 root-cause examples with source evidence

Required root-cause classes:

- scope mismatch
- wrong table class
- wrong period
- wrong unit
- wrong sign
- direct evidence missing
- composite statement account
- note candidate conflict
- formula template missing
- parser table-boundary issue

Exit criteria:

- Every primary unresolved item in the 100-company corpus has one root-cause
  class.
- Top root-cause classes explain at least 90% of primary unresolved items.

### Phase 2. Asset Cash-Flow Formula Engine

Scope:

- PPE acquisition/disposal
- intangible acquisition/disposal
- investment property acquisition/disposal
- non-cash payable/receivable movements
- business-combination and transfer exclusions
- direct disposal proceeds priority

Exit criteria:

- Asset cash-flow unresolved count reduced by at least 50%.
- Formula view shows included and excluded source terms.
- No new false matched cases in manually reviewed top 20 asset samples.

### Phase 3. Financing Cash-Flow Engine

Scope:

- borrowings
- bonds
- convertible/exchangeable bonds
- lease liabilities
- issue costs
- positive cash-outflow presentation
- financing liability movement tables with multi-row headers

Exit criteria:

- Financing cash-flow unresolved count reduced by at least 50%.
- Bond gain/loss and issue-cost rows are not treated as principal cash flows
  unless formula template explicitly permits them.

### Phase 4. Balance and Income Statement Reconciliation

Scope:

- trade receivables and other receivables
- financial assets
- inventory
- PPE/intangible/investment property balances
- revenue, cost of sales, selling/admin expenses
- income tax
- EPS

Exit criteria:

- Statement-note unresolved balance count reduced by at least 50%.
- Income statement account order is preserved from source statements.
- Cost-of-sales / SG&A / expense-by-nature links are visible.

### Phase 5. Equity and Note-to-Note Reconciliation

Scope:

- statement of changes in equity
- dividends
- retained earnings
- capital stock and capital surplus
- treasury shares
- OCI
- note-to-note conflicts
- table total highlights

Exit criteria:

- Equity reconciliation section exists in HTML report.
- Dividend is linked across equity, cash flow, and notes where available.
- Note-total section shows source tables and highlights only issue cells.

### Phase 6. Report UX and Reviewer Validation

Scope:

- side panel evidence
- formula tables
- review queue
- mobile-readable output
- PDF/HTML export readiness

Exit criteria:

- Playwright screenshot checks pass for desktop and mobile.
- No major table truncation in the evidence panel.
- Reviewer can identify source, formula, difference, and next action within one
  screen for primary items.

## Test and Verification Requirements

Each implementation phase must include:

- unit tests for new table semantics
- fixture tests for at least five representative companies
- 100-company corpus rerun
- corpus delta report: before/after matched, unresolved, false-positive risks
- HTML render check with Playwright
- at least 20 manual spot checks for newly matched high-risk cases

Required commands:

```bash
uv run pytest -q
uv run dart-footing workpaper-corpus out/corpus/manifest_2026-05-26-hundred.json out/corpus/run_2026-05-26-hundred-{phase}
```

Required evidence in completion report:

- test output
- corpus summary
- unresolved taxonomy summary
- top improvements by check type
- known residual gaps
- sample report links
- screenshots or render metadata

## Definition of Done

The goal is not complete until all of the following are true:

- The work order is implemented through code, not only described.
- Reports can show mutual reconciliation among statements and notes.
- The 100-company corpus reaches Gate 1.
- Expanded corpus plan is ready for Gate 2.
- Matched items remain reproducible from source evidence.
- No known false matched item is accepted as a success.
- The UI presents audit-review language and source tables clearly.

Until then, the project status remains conditional.
