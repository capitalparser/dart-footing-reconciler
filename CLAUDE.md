# DART Footing Reconciler Project Context

This project is a Python package and CLI for audit-grade footing and cash flow reconciliation over Korean DART DSD/HTML filings.

## Working Rules

- Domain accuracy is more important than technical elegance.
- Keep parsing, normalization, calculation, and reporting separate.
- Core package first; MCP wrapper later.
- Differences are classified as `matched`, `explainable_gap`, `unexplained_gap`, or `parse_uncertain`.
- Every material amount should preserve source location.
- Avoid storing sensitive client information or API keys in this repository.

## Initial Scope

- Property, plant and equipment notes vs. investing cash flows
- Intangible asset notes vs. investing cash flows
- Investment property notes vs. investing cash flows
- Borrowings and bonds notes vs. financing cash flows
- Lease liability principal payments where disclosed

## Adjacent Project

`../kreports_dart_mcp` can be used as a reference for DART and MCP conventions, but this project's reconciliation engine must stay independently testable.

