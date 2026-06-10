"""Company report-order index for semantic validation output."""

from __future__ import annotations

from dataclasses import dataclass

from dart_footing_reconciler.document import FullReport, ReportSection, ReportTable
from dart_footing_reconciler.report_frame import CANONICAL_STATEMENT_ORDER, statement_kind_from_source, statement_kind_from_title


@dataclass(frozen=True)
class ReportOrderEntry:
    source: str
    order: int
    section_kind: str
    statement_kind: str
    section_id: str
    section_title: str
    note_no: str
    table_index: int


@dataclass(frozen=True)
class ReportOrderIndex:
    entries: tuple[ReportOrderEntry, ...]
    _order_by_source: dict[str, int]

    def order_for_source(self, source: str) -> int | None:
        table_source = self.table_source_for(source)
        if not table_source:
            return None
        return self._order_by_source.get(table_source)

    def table_source_for(self, source: str) -> str:
        if "/table:" not in source:
            return ""
        prefix, tail = source.split("/table:", 1)
        table_index = tail.split("/", 1)[0]
        return f"{prefix}/table:{table_index}"


def build_report_order_index(report: FullReport) -> ReportOrderIndex:
    entries: list[ReportOrderEntry] = []
    order = 0

    for kind in CANONICAL_STATEMENT_ORDER:
        for section in report.statements:
            statement_kind = statement_kind_from_title(section.title) or statement_kind_from_source(section.section_id)
            if statement_kind != kind:
                continue
            for table in _section_tables(section):
                entries.append(_entry(section, table, order, statement_kind))
                order += 1

    note_order = 10_000
    for section in report.notes:
        for table in _section_tables(section):
            entries.append(_entry(section, table, note_order, ""))
            note_order += 1

    return ReportOrderIndex(
        entries=tuple(entries),
        _order_by_source={entry.source: entry.order for entry in entries},
    )


def _entry(
    section: ReportSection,
    table: ReportTable,
    order: int,
    statement_kind: str,
) -> ReportOrderEntry:
    return ReportOrderEntry(
        source=f"{section.section_id}/table:{table.index}",
        order=order,
        section_kind=section.kind,
        statement_kind=statement_kind,
        section_id=section.section_id,
        section_title=section.title,
        note_no=section.note_no,
        table_index=table.index,
    )


def _section_tables(section: ReportSection) -> list[ReportTable]:
    return [
        block.table
        for block in section.blocks
        if block.table is not None and getattr(block.table, "rows", None)
    ]
