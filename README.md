# DART Footing Reconciler

Audit-grade footing and cash flow reconciliation for Korean DART filings.

`dart-footing-reconciler` is a Python package and CLI for checking whether note disclosure movements in DART DSD/HTML filings reconcile to the statement of cash flows. The first target is the recurring audit pain point where property, plant and equipment, intangible assets, borrowings, bonds, leases, and related movement tables need to be footed and reconciled against investing and financing cash flow lines.

This project is intentionally core-first. The reconciliation engine must work as a normal Python package and CLI before it is exposed through MCP. MCP will be an integration layer for agents, not the product's source of truth.

## Why this exists

Korean annual reports often contain enough information to reconcile note movements to the cash flow statement, but the evidence is scattered across DART DSD/HTML sections:

- Statement of cash flows
- Property, plant and equipment notes
- Intangible asset notes
- Investment property notes
- Borrowings, bonds, lease liabilities, and other financing notes
- Non-cash transaction disclosures
- Supplementary cash flow disclosures

In audit work, these checks are repetitive but not trivial. A note movement table can foot perfectly while still failing to reconcile to the cash flow statement because acquisitions, disposals, transfers, foreign exchange, depreciation, amortization, lease additions, capitalized borrowing costs, unpaid payables, and other non-cash items are mixed together.

The tool's job is not to declare every difference an error. Its job is to separate matched amounts, explainable gaps, unexplained gaps, and parse uncertainty with source references.

## Scope

### MVP checks

| Area | Note source | Cash flow statement target | Initial check |
|---|---|---|---|
| Investing activities | Property, plant and equipment | Acquisition and disposal of PPE | Reconcile cash-like acquisition/disposal movements to investing CF lines |
| Investing activities | Intangible assets | Acquisition and disposal of intangible assets | Reconcile cash-like acquisition/disposal movements to investing CF lines |
| Investing activities | Investment property | Acquisition and disposal of investment property | Reconcile when separately disclosed |
| Financing activities | Borrowings | Borrowing proceeds and repayments | Reconcile cash borrowing/repayment movements to financing CF lines |
| Financing activities | Bonds | Bond issuance and redemption | Reconcile proceeds/redemption to financing CF lines |
| Financing activities | Lease liabilities | Lease principal payments | Reconcile lease cash outflows where disclosed |

### Later checks

- Financial asset acquisitions and disposals
- Subsidiary/business acquisition cash flow checks
- Dividend payment reconciliation
- Capital increase, treasury stock, and other equity transaction checks
- Multi-company batch reports
- Agent-facing MCP tools
- Excel workpaper export

## Core concepts

### Footing

Checks whether a table calculates internally:

```text
beginning balance + increases - decreases +/- transfers +/- other movements = ending balance
```

Footing is table-local. It does not prove that the cash flow statement is correct.

### Reconciliation

Checks whether selected note movements reconcile to specific cash flow statement line items after excluding or explaining non-cash movements.

Examples:

- PPE additions in a note may include unpaid purchases, lease additions, construction transfers, capitalized borrowing costs, or non-cash acquisitions.
- Borrowing movements may include foreign exchange, current/non-current reclassification, amortized cost adjustments, or non-cash debt assumptions.
- Lease liability increases usually do not equal cash financing inflows; lease principal payments may reconcile to financing cash outflows depending on presentation.

### Result status

Every check returns one of four statuses:

| Status | Meaning |
|---|---|
| `matched` | Note-derived amount and cash flow statement amount agree within tolerance |
| `explainable_gap` | Difference exists, but disclosed adjustment candidates explain the gap |
| `unexplained_gap` | Difference remains after available adjustment candidates |
| `parse_uncertain` | DSD/HTML extraction or label mapping confidence is too low |

The result should include amount, difference, tolerance, confidence, source locations, and the reason for the status.

## Architecture

```text
dart-footing-reconciler/
├── src/dart_footing_reconciler/
│   ├── documents/        DART DSD/HTML document adapters
│   ├── parsing/          Section, table, row, column extraction
│   ├── normalization/    Label aliases, account taxonomy, sign handling
│   ├── statements/       Cash flow statement model
│   ├── notes/            Note movement table model
│   ├── rules/            Footing and reconciliation rules
│   ├── reporting/        JSON, Markdown, CSV, later Excel outputs
│   └── cli.py            Typer CLI entrypoint
├── tests/                Unit and fixture-based regression tests
├── docs/adr/             Architecture decisions
├── plans/                Implementation plans
├── CONTEXT.md            Domain glossary
└── HANDOFF.md            Codex implementation handoff
```

### Data flow

```text
DART DSD/HTML
  -> document adapter
  -> financial statement section extraction
  -> note section extraction
  -> table normalization
  -> label mapping and sign normalization
  -> footing checks
  -> cash flow reconciliation checks
  -> structured result
  -> JSON/Markdown/CSV report
```

## Package boundary

The package should expose stable Python APIs before MCP tools are added:

```python
from dart_footing_reconciler import reconcile_report

result = reconcile_report(
    document=dsd_or_html,
    company="005930",
    year=2025,
    checks=["ppe", "intangibles", "borrowings", "bonds"],
)
```

Expected output shape:

```json
{
  "company": "005930",
  "year": 2025,
  "document_id": "20260317001234",
  "checks": [
    {
      "area": "investing",
      "note_topic": "property_plant_equipment",
      "cfs_line": "acquisition_of_property_plant_equipment",
      "note_amount": 1000000000,
      "cfs_amount": 980000000,
      "difference": 20000000,
      "status": "explainable_gap",
      "confidence": 0.82,
      "explanations": ["unpaid acquisition candidate"],
      "sources": []
    }
  ]
}
```

## CLI target

The CLI should support one-company and batch workflows:

```bash
dart-footing reconcile --corp-code 00126380 --year 2025 --source report.html
dart-footing reconcile --stock-code 005930 --year 2025 --format markdown
dart-footing batch --companies companies.csv --year 2025 --out reports/
```

The first implementation can accept local DSD/HTML files. Live DART fetching can be added after the parser and rule engine are stable.

## MCP target

MCP is planned as a thin wrapper after the package and CLI are useful:

| Tool | Purpose |
|---|---|
| `search_company` | Resolve company name, stock code, and DART corp code |
| `fetch_report` | Fetch or locate a DART DSD/HTML report |
| `extract_reconciliation_inputs` | Return parsed CFS lines and note movement tables |
| `reconcile_cashflow` | Run the reconciliation engine |
| `get_reconciliation_result` | Return prior result by run id |

MCP outputs must be structured JSON with source references. Human-readable summaries are allowed only as secondary fields.

## Design principles

1. Domain accuracy before technical elegance.
2. Never treat every difference as an error.
3. Keep parsing, label mapping, calculation, and reporting separate.
4. Preserve source locations so reviewers can trace every number.
5. Prefer deterministic rules and explicit confidence over opaque LLM judgment.
6. Make the core package testable without MCP, network access, or a DART API key.
7. Use fixtures from real DART DSD/HTML filings, but keep sensitive or client-specific data out of the repo.

## Non-goals

- Replacing audit judgment
- Certifying financial statements
- OCR-first PDF extraction
- LLM-only parsing
- Full K-IFRS disclosure validation
- Immediate production MCP hosting

## Development status

Status: first footing engine implemented.

Current focus:

- Parse DART viewer HTML tables
- Normalize DART-style amount cells
- Foot movement tables for PPE, intangible assets, investment property, leases, borrowings, and bonds
- Filter noisy non-target tables such as cash flow statement bodies, equity movement tables, and contaminated previous-section headings
- Return JSON or Markdown CLI reports
- Run validation manifests across a growing fixture corpus

### Current CLI

```bash
dart-footing foot report.html --format markdown
dart-footing foot report.html --format json
dart-footing foot report.html --tolerance 1
dart-footing foot report.html --all

dart-footing validate validation_manifest.json --format markdown
dart-footing validate validation_manifest.json --format json
dart-footing validate validation_manifest.json --mode conservative
dart-footing validate validation_manifest.json --mode diagnostic
dart-footing validate validation_manifest.json --tag manufacturing
```

Default scan mode focuses on the MVP target families and skips non-target movement tables. `--all` includes every table that can be footed, which is useful for parser diagnosis but noisy for audit work.

Validation has two modes:

| Mode | Purpose |
|---|---|
| `conservative` | Default audit mode. Only target families are scanned. Ambiguous or non-target tables are excluded. |
| `diagnostic` | Parser development mode. All footable tables are scanned so false positives and layout surprises are visible. |

Validation manifests are JSON files:

```json
{
  "samples": [
    {
      "name": "manufacturer-a-2024",
      "company": "Manufacturer A",
      "industry": "manufacturing",
      "tags": ["manufacturing", "ppe", "intangibles"],
      "source": "fixtures/public/manufacturer-a-2024.html",
      "expected": {
        "total": 7,
        "matched": 7,
        "unexplained_gap": 0
      }
    }
  ]
}
```

The recommended corpus strategy is to expand manufacturing companies first because PPE, intangible assets, leases, borrowings, and capital expenditure tables appear often and expose the highest-value footing patterns.

Latest validation summary: [`docs/validation/2026-05-16-manufacturing-30.md`](docs/validation/2026-05-16-manufacturing-30.md).

### Smoke-tested public DART samples

The first implementation was exercised against public DART viewer HTML from multiple reports:

| Report | Local smoke result | Notes |
|---|---:|---|
| DGP audit report viewer HTML, 2024 filing | 3 / 3 matched | Classic DART note tables; one rounding difference accepted by tolerance |
| KC Tech business report viewer HTML, 2024 filing | 7 / 7 matched | Added rule to ignore beginning/ending gross cost, accumulated depreciation, and impairment detail rows |
| Samsung Heavy Industries business report viewer HTML, 2024 filing | 14 / 14 matched | Added support for XBRL-style tables where the movement heading is in a separate header table |

These smoke tests are not yet committed as fixtures because the full public viewer HTML files are large. The behavioral patterns found from them are covered by unit tests.

## Relationship to KReports

`kreports_dart_mcp` is the broader DART financial intelligence and MCP project. `dart-footing-reconciler` is narrower:

- KReports answers investor/audit intelligence questions across companies.
- DART Footing Reconciler validates note movements and cash flow statement relationships.

The reconciler may later use KReports for DART company lookup or document fetching, but it should not depend on KReports for its core calculation engine.

## License

Apache-2.0 is the intended license unless changed before publication.
