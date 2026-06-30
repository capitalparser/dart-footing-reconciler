# 0025. Note semantic extraction layer before validation

**Date:** 2026-06-30
**Status:** Accepted. First code slice: table-level semantic summary feeding the lease disclosure-completeness backlog.
**Companion:** ADR-0023, `src/dart_footing_reconciler/note_semantics.py`, `tests/test_note_semantics.py`.

## Context

Korean DART notes vary heavily by company and by year. Adding a new parser for
each company-specific note form would increase short-term coverage but would
also make the audit result hard to explain and hard to regression-test.

The safer direction is to place a **Note Semantic Extraction Layer** in front of
the existing footing/reconciliation engines. This layer reads note tables
broadly and records what the table appears to be, which axes are visible, and
which parts remain uncertain. The validation engine still decides conservatively
and only uses confident evidence for `matched` or `unexplained_gap`.

## Decision

1. **Do not grow company-specific note parsers.** Add disclosure-family and
   table-pattern semantics instead. A table may be recognized as a lease
   liability schedule, liquidity maturity analysis, roll-forward, breakdown,
   fair-value hierarchy, or similar family without depending on company name or
   note number.

2. **Parse broadly, validate narrowly.** The semantic layer may keep weak
   candidates such as "this looks like a lease maturity table." The core
   validation layer may only conclude when period, consolidation basis, account
   topic, amount nature, unit/currency, sign convention, and amount all line up.
   Amount equality is last, not first.

3. **Ambiguity becomes parser/layout evidence, not reviewer noise.** When a
   maturity-analysis-like table exists but the engine cannot confidently read
   the headers or axes, disclosure-completeness suppresses the omission memo and
   records interpretation-backlog evidence with:

   - disclosure family
   - relation type
   - parser uncertainty flags
   - table fingerprint
   - source location

4. **Fingerprints describe table patterns, not companies.** A fingerprint uses
   section topic, header tokens, row labels, row-count bucket, axis schema, unit
   pattern, and detected relation types. It intentionally excludes company
   names so the same table pattern can be clustered across the corpus.

5. **DB/server scope stays unchanged.** This is a Python extraction layer before
   validation. SQLite remains a downstream result ledger; it is not the parser,
   validator, or source of truth. XBRL/TSV and LLM outputs, if added later, may
   rank or explain candidates but must not become the final judge.

## First implemented slice

`build_note_semantic_extraction(report)` builds table-level semantic summaries
from the existing `FullReport`, `note_inventory`, `layout_variants`, and
`orientation` surfaces. It currently records:

| Field | Meaning for accountants |
|---|---|
| `disclosure_families` | What kind of note table this appears to be, such as lease liability schedule or maturity analysis |
| `detected_relation_types` | What relationship may be present, such as maturity buckets adding to a total |
| `uncertainty_flags` | Why the engine is not yet comfortable treating the table as confidently read |
| `fingerprint` | The reusable pattern of the table layout, excluding company identity |
| `source_location` | Where the table came from in the document |

The first consumer is the lease disclosure-completeness advisory. Ambiguous
lease/liquidity maturity tables now enter interpretation backlog with semantic
metadata instead of being checked by ad hoc table-shape code.

## Non-goals

- No new `CheckResult` status.
- No change to `checks.ALL_STATUSES`.
- No company-source / ERP / GL / TB linkage.
- No company-name-specific parser.
- No LLM or XBRL truth source.
