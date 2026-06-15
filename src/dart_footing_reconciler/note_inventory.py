"""Full-note inventory extraction for parsed DART reports."""

from __future__ import annotations

from dataclasses import dataclass

from dart_footing_reconciler.document import FullReport


@dataclass(frozen=True)
class NoteTableInventoryItem:
    company: str
    section_id: str
    note_no: str
    title: str
    table_index: int
    source: str
    heading: str
    unit_multiplier: int
    row_count: int
    column_count: int
    headers: tuple[str, ...]
    row_labels: tuple[str, ...]


@dataclass(frozen=True)
class NoteInventory:
    company: str
    note_count: int
    tables: tuple[NoteTableInventoryItem, ...]


def build_note_inventory(report: FullReport) -> NoteInventory:
    tables: list[NoteTableInventoryItem] = []
    for section in report.notes:
        for block in section.blocks:
            table = block.table
            if table is None:
                continue
            rows = table.rows
            headers = tuple(rows[0]) if rows else ()
            row_labels = tuple(row[0] for row in rows[1:] if row)
            column_count = max((len(row) for row in rows), default=0)
            tables.append(
                NoteTableInventoryItem(
                    company=report.company,
                    section_id=section.section_id,
                    note_no=section.note_no,
                    title=section.title,
                    table_index=table.index,
                    source=f"note:{section.note_no}/table:{table.index}",
                    heading=table.heading,
                    unit_multiplier=table.unit_multiplier,
                    row_count=len(rows),
                    column_count=column_count,
                    headers=headers,
                    row_labels=row_labels,
                )
            )
    return NoteInventory(
        company=report.company,
        note_count=len(report.notes),
        tables=tuple(tables),
    )
