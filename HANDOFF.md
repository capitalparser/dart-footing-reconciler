# Handoff

## Objective

Implement a Python package and CLI that checks DART DSD/HTML filings for note footing and cash flow statement reconciliation.

## Current State

The repository is scaffolded only. The README, context glossary, and first ADR define the product boundary:

- Core package and CLI first
- MCP wrapper later
- Initial checks for PPE, intangible assets, investment property, borrowings, bonds, and lease liability cash flow relationships
- Result statuses: `matched`, `explainable_gap`, `unexplained_gap`, `parse_uncertain`

## Implementation Priorities

1. Define stable result models with source locations.
2. Build local DSD/HTML fixture loading.
3. Extract statement of cash flows lines.
4. Extract note movement tables.
5. Implement table-local footing checks.
6. Implement first PPE and intangible asset cash flow reconciliation rules.
7. Add CLI JSON and Markdown output.
8. Add regression fixtures from public DART filings.

## Constraints

- Keep MCP out of the first core implementation.
- Do not depend on `kreports_dart_mcp` for calculation logic.
- Preserve source references for every material amount.
- Avoid LLM-only parsing or opaque classification.
- Treat differences as classified findings, not automatic errors.

