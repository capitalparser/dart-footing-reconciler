# 09_dart_footing_reconciler — Project System Context

This project builds an audit-grade footing and cash flow reconciliation engine
for Korean DART DSD/HTML filings.

## Module Responsibilities

| Module | Responsibility | Location |
|---|---|---|
| Parser | DSD/HTML extraction with source locations and parse uncertainty | `src/` parser modules |
| Footing Engine | Internal table arithmetic checks | `src/` footing/domain modules |
| Reconciliation Engine | Note movement to cash flow statement comparison | `src/` reconciliation/domain modules |
| Classification | Matched, explainable gap, unexplained gap, parse uncertain | `src/` classification modules |
| CLI/Package | Stable command and package interface for local use | `src/` CLI modules |
| Tests/Fixtures | Golden DSD/HTML fixtures and reconciliation regressions | `tests/` |

## Feature Addition Rules

- Footing and cash flow reconciliation must remain separate checks.
- Every material amount must preserve source location.
- Label mapping uncertainty must be explicit through confidence/evidence.
- The core reconciliation engine must run without MCP.
- MCP wrappers may expose the engine only after the CLI/package contract is
  stable.

## Verification

- Run `uv run pytest` for default tests.
- Parser changes require fixture coverage for source location and uncertainty.
