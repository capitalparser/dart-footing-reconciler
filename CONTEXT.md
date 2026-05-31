# Context

## Project Profile
- 개요: DART 공시의 주석 수치, 현금흐름, 증감표를 파싱해 footing과 reconciliation 차이를 점검하는 도구입니다.
- 목적: 감사/분석 과정에서 수치 검산과 설명 가능한 차이 분류를 자동화해 사람의 검토 시간을 줄입니다.

This project builds an audit-grade footing and cash flow reconciliation engine for Korean DART DSD/HTML filings.

## Ubiquitous Language

### DART DSD/HTML

The primary source format for Korean regulatory filings. The project starts from DSD/HTML because table structure is more reliable than PDF OCR for audit-style reconciliation.

### Footing

An internal arithmetic check inside one table. The canonical movement formula is:

```text
beginning balance + increases - decreases +/- transfers +/- other movements = ending balance
```

Footing proves table arithmetic only. It does not prove cash flow statement agreement.

### Cash Flow Reconciliation

Comparison between note-derived cash-like movements and statement of cash flows line items. The comparison must consider non-cash movements and classification differences.

### Cash-Like Movement

A movement in a note table that is expected to correspond to a cash flow statement line item, such as cash acquisition of PPE, proceeds from sale of assets, borrowing proceeds, or borrowing repayments.

### Non-Cash Movement

A movement that changes note balances but should not be treated as cash flow. Examples include depreciation, amortization, transfers, foreign exchange, lease additions, reclassifications, fair value movements, and unpaid acquisitions.

### Explainable Gap

A difference between note-derived amount and cash flow statement amount that can be tied to disclosed adjustment candidates.

### Unexplained Gap

A difference that remains after available adjustment candidates and tolerance are considered.

### Parse Uncertainty

A condition where document structure, row labels, column labels, signs, or section boundaries are ambiguous enough that the tool should not make a strong reconciliation assertion.

### Source Location

Traceable reference to the originating filing, section, table, row, column, and raw label/text. Every material amount in a reconciliation result should preserve source location.

## Core Domain Rules

- Footing and cash flow reconciliation are separate checks.
- Differences are classified, not automatically treated as errors.
- Label mapping is probabilistic in practice but must be represented explicitly through confidence and source evidence.
- The core reconciliation engine must run without MCP.
- MCP should expose the engine to agents after the CLI/package contract is stable.

## Initial Check Families

### Investing Activities

- Property, plant and equipment acquisitions and disposals
- Intangible asset acquisitions and disposals
- Investment property acquisitions and disposals

### Financing Activities

- Borrowing proceeds and repayments
- Bond issuance and redemption
- Lease liability principal payments

## Result Statuses

- `matched`
- `explainable_gap`
- `unexplained_gap`
- `parse_uncertain`

## Reviewer Lens Extension

The reconciliation report can be extended into a reviewer-facing interpretation
layer, but this must remain separate from the footing engine.

### Product Boundary

Footing and reconciliation results are evidence, not audit conclusions. The
next layer should generate reviewer questions and follow-up prompts from
evidence patterns. It should not assert that fraud, error, or audit risk exists.

Canonical chain:

```text
DART footing
→ report structuring
→ financial statement / note / business section extraction
→ account movement analysis
→ business-model-based risk hypotheses
→ key account review points
→ reviewer question list
```

### Layer Model

1. Footing and extraction: structure financial statements, notes, business
   content, audit report text, KAM, and account-level evidence.
2. Accounting interpretation: translate account changes, ratios, trends, and
   note keywords into business-model-aware signals.
3. Reviewer coach: draft risk hypotheses, key account review points, request
   lists, and manager/partner questions.

### Required Tone

Use hypothesis language:

```text
매출채권 증가율이 매출 증가율을 크게 상회하고 영업현금흐름이 악화되어,
기말 판매조건 완화 또는 채널 밀어내기 가능성을 후속 확인할 필요 있음.
```

Avoid assertion language:

```text
매출 밀어내기 있음.
```

### MVP Scope

Target: one listed manufacturing company with three years of annual
reports/audit reports.

Output:

- Business model summary
- Key account movement table
- Five anomaly signals
- Five risk hypotheses
- Key-account reviewer questions
- Required request list

Initial account families:

- Revenue
- Trade receivables
- Inventory
- Cost of sales
- Property, plant and equipment
- Depreciation
- Operating cash flow
- Provisions, returns, rebates, and sales incentives
