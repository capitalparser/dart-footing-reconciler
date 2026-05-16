"""Full DART report document extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup

from dart_footing_reconciler.html_tables import _extract_rows


@dataclass(frozen=True)
class SourceLocation:
    section_id: str
    block_index: int
    table_index: int | None = None
    row_index: int | None = None
    column_index: int | None = None


@dataclass(frozen=True)
class ReportTable:
    index: int
    rows: list[list[str]]
    heading: str
    location: SourceLocation


@dataclass(frozen=True)
class ReportBlock:
    kind: str
    text: str
    table: ReportTable | None
    location: SourceLocation


@dataclass(frozen=True)
class ReportSection:
    section_id: str
    title: str
    kind: str
    note_no: str
    blocks: list[ReportBlock]


@dataclass(frozen=True)
class FullReport:
    source: str
    company: str
    statements: list[ReportSection]
    notes: list[ReportSection]


STATEMENT_TITLES = ("재무상태표", "손익계산서", "포괄손익계산서", "자본변동표", "현금흐름표")


def parse_full_report(source: str | Path, *, company: str = "") -> FullReport:
    """Parse statement and note sections from a local DART HTML file."""
    path = Path(source)
    html = path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "lxml")
    has_note_area_markers = any(
        _note_area_marker(_clean(node.get_text(" ", strip=True)))
        for node in soup.find_all(["p", "div"])
    )
    in_note_area = not has_note_area_markers
    sections: list[ReportSection] = []
    current: ReportSection | None = None
    table_index = 0

    for node in soup.find_all(["p", "div", "table"]):
        if node.name in {"p", "div"}:
            text = _clean(node.get_text(" ", strip=True))
            if not text:
                continue
            if _note_area_marker(text):
                in_note_area = True
                current = None
                continue
            if _non_note_area_marker(text):
                in_note_area = False
                current = None
                continue
            statement_title = _statement_title(text)
            note = _note_heading(text)
            if statement_title:
                current = _new_section(statement_title, "statement", "")
                sections.append(current)
                continue
            if note and in_note_area:
                current = _new_section(note[1], "note", note[0])
                sections.append(current)
                continue
            if current is not None:
                _append_text(current, text)
            continue

        if node.name == "table" and current is not None:
            rows = _extract_rows(node)
            if not rows:
                continue
            block_index = len(current.blocks)
            table = ReportTable(
                index=table_index,
                rows=[row.cells for row in rows],
                heading=current.title,
                location=SourceLocation(current.section_id, block_index, table_index),
            )
            current.blocks.append(
                ReportBlock(
                    "table",
                    "",
                    table,
                    SourceLocation(current.section_id, block_index, table_index),
                )
            )
            table_index += 1

    return FullReport(
        source=str(path),
        company=company,
        statements=[section for section in sections if section.kind == "statement"],
        notes=[section for section in sections if section.kind == "note"],
    )


def _new_section(title: str, kind: str, note_no: str) -> ReportSection:
    section_id = f"{kind}:{note_no or _normalize(title)}"
    return ReportSection(section_id, title, kind, note_no, [])


def _append_text(section: ReportSection, text: str) -> None:
    section.blocks.append(
        ReportBlock("text", text, None, SourceLocation(section.section_id, len(section.blocks)))
    )


def _statement_title(text: str) -> str:
    compact = _normalize(text)
    for title in STATEMENT_TITLES:
        if compact == _normalize(title) or compact.endswith(_normalize(title)):
            return title
    return ""


def _note_heading(text: str) -> tuple[str, str] | None:
    match = re.match(r"^주석?\s*(\d+(?:-\d+)?)\.?\s*(.+)$", text)
    if match:
        if not _valid_note_no(match.group(1)):
            return None
        return match.group(1), _strip_heading_tail(match.group(2))
    match = re.match(r"^(\d+(?:-\d+)?)\.\s*(.+)$", text)
    if not match:
        return None
    if not _valid_note_no(match.group(1)):
        return None
    return match.group(1), _strip_heading_tail(match.group(2))


def _strip_heading_tail(value: str) -> str:
    return re.sub(r"\s*[:：].*$", "", value).strip()


def _clean(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())


def _valid_note_no(value: str) -> bool:
    try:
        first_part = int(value.split("-", 1)[0])
    except ValueError:
        return False
    return 1 <= first_part <= 99


def _note_area_marker(text: str) -> bool:
    compact = _normalize(text)
    return "재무제표주석" in compact or "연결재무제표주석" in compact


def _non_note_area_marker(text: str) -> bool:
    compact = _normalize(text)
    return (
        compact.startswith("감사대상업무")
        or compact.startswith("외부감사")
        or compact.startswith("감사인의")
        or compact.startswith("이사의")
    )


def _normalize(value: str) -> str:
    return re.sub(r"\s+", "", value)
