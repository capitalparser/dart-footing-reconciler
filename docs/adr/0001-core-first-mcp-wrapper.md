# ADR 0001: Build the Core Reconciliation Package Before MCP

## Status

Accepted

## Context

The product goal is to check DART DSD/HTML filings for note footing and cash flow statement reconciliation. The same capability could be shipped directly as an MCP server, because agent workflows are a likely consumer.

However, the hard part is not the MCP transport. The hard part is deterministic parsing, label normalization, sign handling, rule execution, confidence scoring, and source traceability.

## Decision

Build `dart-footing-reconciler` as a standalone Python package and CLI first. Add MCP later as a thin wrapper around stable package APIs.

## Consequences

### Positive

- Reconciliation logic can be unit-tested without an agent runtime.
- Batch workflows can run locally from the CLI.
- MCP output contracts can mirror already-tested Python result objects.
- The project can reuse or integrate with `kreports_dart_mcp` without being coupled to it.

### Negative

- Agent-facing workflow is delayed until the core contract stabilizes.
- Some wrapper work will be duplicated later for MCP tool schemas.

## Alternatives Considered

### MCP-first

Rejected. It would expose a tool surface before the underlying audit logic is stable and make regression testing harder.

### Embed directly into KReports

Rejected for the first version. KReports is a broader DART intelligence/MCP project. The reconciler has a narrower audit workpaper-style domain and should keep its calculation engine independent.

### Spreadsheet-first

Rejected for the first version. Excel output is useful, but making Excel the primary engine would weaken automated testing and source traceability.
