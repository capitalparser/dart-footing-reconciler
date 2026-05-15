# Context

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
