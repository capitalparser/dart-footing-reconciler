"""HTML table extraction for DART viewer documents."""

from __future__ import annotations

from dataclasses import dataclass

from bs4 import BeautifulSoup
from bs4.element import Tag


@dataclass(frozen=True)
class TableRow:
    cells: list[str]
    index: int
    acodes: list[str] | None = None
    source_line: int | None = None
    cell_source_lines: list[int | None] | None = None


@dataclass(frozen=True)
class ParsedTable:
    rows: list[TableRow]
    heading: str
    index: int


def extract_tables(html: str) -> list[ParsedTable]:
    """Extract normalized tables with nearby paragraph headings."""
    soup = BeautifulSoup(html, "html.parser")
    tables: list[ParsedTable] = []

    for index, table in enumerate(soup.find_all("table")):
        rows = _extract_rows(table)
        if not rows:
            continue
        tables.append(ParsedTable(rows=rows, heading=_nearby_heading(table), index=index))

    return tables


def _extract_rows(table: Tag) -> list[TableRow]:
    rows: list[TableRow] = []
    rowspans: dict[int, tuple[str, str, int | None, int]] = {}

    for row_index, tr in enumerate(table.find_all("tr")):
        cells: list[str] = []
        acodes: list[str] = []
        cell_source_lines: list[int | None] = []
        col_index = 0

        for cell in tr.find_all(["th", "td"], recursive=False):
            while col_index in rowspans:
                text, acode, source_line, remaining = rowspans[col_index]
                cells.append(text)
                acodes.append(acode)
                cell_source_lines.append(source_line)
                if remaining <= 1:
                    del rowspans[col_index]
                else:
                    rowspans[col_index] = (text, acode, source_line, remaining - 1)
                col_index += 1

            text = _clean_text(cell.get_text(" ", strip=True))
            acode = str(cell.get("acode") or "")
            source_line = _source_line(cell)
            colspan = _int_attr(cell, "colspan", default=1)
            rowspan = _int_attr(cell, "rowspan", default=1)

            for offset in range(colspan):
                cells.append(text)
                acodes.append(acode)
                cell_source_lines.append(source_line)
                if rowspan > 1:
                    rowspans[col_index + offset] = (text, acode, source_line, rowspan - 1)
            col_index += colspan

        while col_index in rowspans:
            text, acode, source_line, remaining = rowspans[col_index]
            cells.append(text)
            acodes.append(acode)
            cell_source_lines.append(source_line)
            if remaining <= 1:
                del rowspans[col_index]
            else:
                rowspans[col_index] = (text, acode, source_line, remaining - 1)
            col_index += 1

        if any(cells):
            rows.append(
                TableRow(
                    cells=cells,
                    index=row_index,
                    acodes=acodes,
                    source_line=_source_line(tr),
                    cell_source_lines=cell_source_lines,
                )
            )

    return rows


def _nearby_heading(table: Tag, max_parts: int = 2) -> str:
    parts: list[str] = []
    node = table.previous_sibling

    while node is not None and len(parts) < max_parts:
        if isinstance(node, Tag):
            text = _clean_text(node.get_text(" ", strip=True))
            if text and node.name in {"p", "div"}:
                parts.append(text)
        node = node.previous_sibling

    return " ".join(reversed(parts))


def _clean_text(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())


def _int_attr(tag: Tag, attr: str, default: int) -> int:
    raw = tag.get(attr)
    if raw is None:
        return default
    try:
        return int(str(raw))
    except ValueError:
        return default


def _source_line(tag: Tag) -> int | None:
    raw = getattr(tag, "sourceline", None)
    return raw if isinstance(raw, int) else None
