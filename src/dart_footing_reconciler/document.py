"""Full DART report document extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup
from bs4.element import Tag

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
    row_acodes: list[list[str]] | None = None
    unit_multiplier: int = 1


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
    html = _read_dart_html(path)
    soup = BeautifulSoup(html, "lxml")
    has_note_area_markers = any(
        _note_area_marker(_clean(node.get_text(" ", strip=True)))
        for node in soup.find_all(["p", "div", "span", "table"])
    )
    in_note_area = not has_note_area_markers
    sections: list[ReportSection] = []
    current: ReportSection | None = None
    table_index = 0
    current_unit_multiplier = 1

    for node in soup.find_all(["p", "div", "span", "table"]):
        if node.name in {"p", "div", "span"}:
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
            if statement_title and _allow_inline_statement_heading(
                current, in_note_area, has_note_area_markers
            ):
                if (
                    current is not None
                    and current.kind == "statement"
                    and current.title == statement_title
                    and not current.blocks
                ):
                    continue
                current = _new_section(statement_title, "statement", "")
                sections.append(current)
                continue
            if note and in_note_area and _should_start_note(current, note[0]):
                current = _new_section(note[1], "note", note[0])
                sections.append(current)
                continue
            if node.name == "span":
                continue
            if current is not None:
                _append_text(current, text)
            continue

        if node.name == "table":
            if _is_layout_container_table(node):
                continue
            rows = _extract_rows(node)
            if not rows:
                continue
            table_text = _table_text([row.cells for row in rows])
            if _note_area_marker(table_text):
                in_note_area = True
                current = None
                continue
            if _non_note_area_marker(table_text):
                in_note_area = False
                current = None
                continue
            statement_title = _statement_title(table_text)
            if statement_title and _is_statement_heading_table(table_text):
                current_unit_multiplier = _unit_multiplier(table_text) or current_unit_multiplier
                current = _new_section(statement_title, "statement", "")
                sections.append(current)
                continue
            note = _note_heading(table_text)
            if note and in_note_area and _should_start_note(current, note[0]):
                current = _new_section(note[1], "note", note[0])
                sections.append(current)
                remaining_text = _strip_note_heading_prefix(table_text, note[1])
                if remaining_text:
                    _append_text(current, remaining_text)
                continue
            unit_multiplier = _unit_multiplier(table_text) if _is_unit_marker_table([row.cells for row in rows]) else None
            if unit_multiplier is not None:
                current_unit_multiplier = unit_multiplier
                continue
            if current is None:
                continue
            layout_text = _layout_table_text([row.cells for row in rows])
            if layout_text is not None:
                for text in layout_text:
                    note = _note_heading(text)
                    if note and in_note_area and _should_start_note(current, note[0]):
                        current = _new_section(note[1], "note", note[0])
                        sections.append(current)
                        remaining_text = _strip_note_heading_prefix(text, note[1])
                        if remaining_text:
                            _append_text(current, remaining_text)
                        continue
                    _append_text(current, text)
                continue
            data_rows = rows
            leading_unit_multiplier = _leading_unit_multiplier([row.cells for row in rows])
            if leading_unit_multiplier is not None and len(rows) > 1:
                current_unit_multiplier = leading_unit_multiplier
                data_rows = rows[1:]
            block_index = len(current.blocks)
            table = ReportTable(
                index=table_index,
                rows=[row.cells for row in data_rows],
                heading=_table_heading(current),
                location=SourceLocation(current.section_id, block_index, table_index),
                row_acodes=[row.acodes or [] for row in data_rows],
                unit_multiplier=_unit_multiplier(_table_heading(current)) or current_unit_multiplier,
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

    statement_sections = [section for section in sections if section.kind == "statement"]
    note_sections = [section for section in sections if section.kind == "note"]
    strict_statement_filter = (
        has_note_area_markers or len(note_sections) > 20 or len(statement_sections) > 8
    )

    return FullReport(
        source=str(path),
        company=company,
        statements=[
            section
            for section in statement_sections
            if not strict_statement_filter or _is_plausible_statement_section(section)
        ],
        notes=note_sections,
    )


def _read_dart_html(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "cp949", "euc-kr"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def _new_section(title: str, kind: str, note_no: str) -> ReportSection:
    section_id = f"{kind}:{note_no or _normalize(title)}"
    return ReportSection(section_id, title, kind, note_no, [])


def _append_text(section: ReportSection, text: str) -> None:
    section.blocks.append(
        ReportBlock("text", text, None, SourceLocation(section.section_id, len(section.blocks)))
    )


def _is_layout_container_table(node: Tag) -> bool:
    # class='nb' tables are DART margin/comment containers — always layout-only.
    classes = node.get("class") or []
    if isinstance(classes, str):
        classes = classes.split()
    if "nb" in classes:
        return True
    # Nested table → layout container (existing logic).
    return node.find("table") is not None


def _layout_table_text(rows: list[list[str]]) -> list[str] | None:
    normalized = [[_clean(cell) for cell in row if _clean(cell)] for row in rows]
    normalized = [row for row in normalized if row]
    if not normalized:
        return []

    if _is_bullet_table(normalized):
        return [_bullet_text(row) for row in normalized]

    if all(len(row) == 1 for row in normalized):
        return [row[0] for row in normalized]

    return None


def _is_bullet_table(rows: list[list[str]]) -> bool:
    bullet_markers = {"-", "ㆍ", "·", "•"}
    return all(len(row) <= 2 and row[0].strip() in bullet_markers for row in rows)


def _bullet_text(row: list[str]) -> str:
    if len(row) == 1:
        return row[0]
    return f"- {row[1]}"


def _looks_numeric_table(rows: list[list[str]]) -> bool:
    values = [cell for row in rows for cell in row]
    return any(re.search(r"\d", value) for value in values)


def _table_text(rows: list[list[str]]) -> str:
    return _clean(" ".join(cell for row in rows for cell in row))


def _unit_multiplier(text: str) -> int | None:
    compact = _normalize(text)
    if "단위" not in compact:
        return None
    if "백만원" in compact:
        return 1_000_000
    if "천원" in compact:
        return 1_000
    if "원" in compact:
        return 1
    return None


def _is_unit_marker_table(rows: list[list[str]]) -> bool:
    non_empty_rows = [[_clean(cell) for cell in row if _clean(cell)] for row in rows]
    non_empty_rows = [row for row in non_empty_rows if row]
    if len(non_empty_rows) > 2:
        return False
    text = _table_text(non_empty_rows)
    if _statement_title(text):
        return False
    compact = _normalize(text)
    return "단위" in compact and not any(
        keyword in compact
        for keyword in ("매출", "자산", "부채", "자본", "순이익", "영업이익", "포괄손익")
    )


def _leading_unit_multiplier(rows: list[list[str]]) -> int | None:
    if len(rows) < 2:
        return None
    first_row_text = _table_text([rows[0]])
    multiplier = _unit_multiplier(first_row_text)
    if multiplier is None:
        return None
    first_row_compact = _normalize(first_row_text)
    second_row_compact = _normalize(_table_text([rows[1]]))
    if "단위" not in first_row_compact or "구분" not in second_row_compact:
        return None
    non_empty_first = [_clean(cell) for cell in rows[0] if _clean(cell)]
    if not non_empty_first:
        return None
    unit_cells = sum(1 for cell in non_empty_first if "단위" in _normalize(cell))
    return multiplier if unit_cells / len(non_empty_first) >= 0.5 else None


def _table_heading(section: ReportSection) -> str:
    parts: list[str] = []
    if section.kind == "note" and section.note_no:
        parts.append(f"{section.note_no}. {section.title}")
    else:
        parts.append(section.title)
    for block in section.blocks[-3:]:
        if block.kind == "text" and block.text:
            parts.append(block.text)
    return _clean(" ".join(parts))


def _is_statement_heading_table(text: str) -> bool:
    compact = _normalize(text)
    return (
        compact.startswith(("연결재무상태표", "재무상태표"))
        and "현재" in compact
    ) or (
        compact.startswith(("연결손익계산서", "손익계산서", "연결포괄손익계산서", "포괄손익계산서", "연결자본변동표", "자본변동표", "연결현금흐름표", "현금흐름표"))
        and "부터" in compact
        and "까지" in compact
    )


def _allow_inline_statement_heading(
    current: ReportSection | None, in_note_area: bool, has_note_area_markers: bool
) -> bool:
    if not has_note_area_markers:
        return True
    if in_note_area:
        return False
    return current is None or not current.blocks


def _is_plausible_statement_section(section: ReportSection) -> bool:
    tables = [block.table for block in section.blocks if block.table is not None]
    if not tables:
        return False
    if section.title == "재무상태표":
        return any(_table_has_row_label(table.rows, ("자산", "유동자산", "자산총계")) for table in tables)
    if section.title == "손익계산서":
        return any(
            _table_has_row_label(table.rows, ("매출", "매출액", "영업수익", "수익", "수익(매출액)"))
            for table in tables
        )
    if section.title == "포괄손익계산서":
        return any(
            _table_has_row_label(table.rows, ("당기순이익", "당기순이익(손실)", "기타포괄손익", "총포괄손익"))
            for table in tables
        )
    if section.title == "자본변동표":
        return any(_table_has_text(table.rows, ("기초자본", "기말자본", "자본금", "이익잉여금")) for table in tables)
    if section.title == "현금흐름표":
        return any(
            _table_has_row_label(table.rows, ("영업활동", "영업활동으로 인한 현금흐름", "영업활동현금흐름", "투자활동현금흐름", "재무활동현금흐름"))
            for table in tables
        )
    return True


def _table_has_row_label(rows: list[list[str]], labels: tuple[str, ...]) -> bool:
    normalized_labels = {_normalize(label) for label in labels}
    for row in rows[1:]:
        if row and _normalize(row[0]) in normalized_labels:
            return True
    return False


def _table_has_text(rows: list[list[str]], labels: tuple[str, ...]) -> bool:
    text = _normalize(_table_text(rows))
    return any(_normalize(label) in text for label in labels)


def _statement_title(text: str) -> str:
    compact = _normalize(text)
    for title in sorted(STATEMENT_TITLES, key=len, reverse=True):
        normalized_title = _normalize(title)
        if (
            compact == normalized_title
            or compact.endswith(normalized_title)
            or compact.startswith(normalized_title)
            or compact.startswith(f"연결{normalized_title}")
        ):
            return title
    return ""


def _note_heading(text: str) -> tuple[str, str] | None:
    note_no_pattern = r"\d+(?:(?:-|\.)\d+)*"
    match = re.match(rf"^(?:주석?\s*)?({note_no_pattern})\.?\s+(.+)$", text)
    if match:
        if not _valid_note_no(match.group(1)):
            return None
        title = _strip_heading_tail(match.group(2))
        if _non_note_heading_title(title):
            return None
        return match.group(1), title
    return None


def _should_start_note(current: ReportSection | None, candidate_note_no: str) -> bool:
    if current is None or current.kind != "note" or not current.note_no:
        return True
    if candidate_note_no == current.note_no:
        return False
    return not (
        candidate_note_no.startswith(f"{current.note_no}.")
        or candidate_note_no.startswith(f"{current.note_no}-")
    )


def _note_number_head(value: str) -> int:
    return int(re.split(r"[-.]", value, maxsplit=1)[0])


def _strip_heading_tail(value: str) -> str:
    if "단위" not in _normalize(value):
        value = re.sub(r"\s*[:：].*$", "", value).strip()
    note_no_pattern = r"\d+(?:(?:-|\.)\d+)*"
    value = re.split(rf"\s+{note_no_pattern}\.?\s+", value, maxsplit=1)[0].strip()
    return value


def _strip_note_heading_prefix(value: str, note_title: str = "") -> str:
    note_no_pattern = r"\d+(?:(?:-|\.)\d+)*"
    if note_title:
        match = re.match(rf"^(?:주석?\s*)?{note_no_pattern}\.?\s+(.+)$", value)
        if match and _clean(match.group(1)) == _clean(note_title):
            return ""
    if re.match(rf"^(?:주석?\s*)?{note_no_pattern}\.?\s+\S+$", value):
        return ""
    return re.sub(rf"^(?:주석?\s*)?{note_no_pattern}\.?\s+.+?\s+", "", value, count=1).strip()


def _non_note_heading_title(title: str) -> bool:
    if title.lstrip().startswith(("~", "-", "－")):
        return True
    return _normalize(title) in {"재무제표", "연결재무제표"}


def _clean(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())


def _valid_note_no(value: str) -> bool:
    try:
        first_part = int(re.split(r"[-.]", value, maxsplit=1)[0])
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
