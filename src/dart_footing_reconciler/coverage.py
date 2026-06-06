"""Company-level validation coverage aggregation."""

from __future__ import annotations

from dataclasses import dataclass

from dart_footing_reconciler.checks import CheckResult
from dart_footing_reconciler.layout_variants import LayoutClassification
from dart_footing_reconciler.note_inventory import NoteInventory


@dataclass(frozen=True)
class CoverageReport:
    company: str
    total_notes: int
    total_tables: int
    known_layout_tables: int
    unknown_layout_tables: int
    validated_tables: int
    parse_uncertain_tables: int
    unvalidated_tables: int


def build_coverage_report(
    inventory: NoteInventory,
    layouts: dict[str, LayoutClassification],
    checks: list[CheckResult],
) -> CoverageReport:
    table_sources = {table.source for table in inventory.tables}
    known_layout_tables = sum(
        1
        for table in inventory.tables
        if layouts.get(table.source) is not None
        and layouts[table.source].key != "unknown_layout"
    )
    unknown_layout_tables = len(inventory.tables) - known_layout_tables
    validated_sources: set[str] = set()
    parse_uncertain_sources: set[str] = set()
    for check in checks:
        touched = {
            source
            for evidence in check.evidence
            for source in table_sources
            if evidence.source.startswith(source + "/")
        }
        if check.status == "parse_uncertain":
            parse_uncertain_sources.update(touched)
        else:
            validated_sources.update(touched)
    validated_tables = len(validated_sources)
    parse_uncertain_tables = len(parse_uncertain_sources - validated_sources)
    unvalidated_tables = len(table_sources - validated_sources - parse_uncertain_sources)
    return CoverageReport(
        company=inventory.company,
        total_notes=inventory.note_count,
        total_tables=len(inventory.tables),
        known_layout_tables=known_layout_tables,
        unknown_layout_tables=unknown_layout_tables,
        validated_tables=validated_tables,
        parse_uncertain_tables=parse_uncertain_tables,
        unvalidated_tables=unvalidated_tables,
    )
