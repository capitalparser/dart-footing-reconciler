"""Note semantic extraction layer.

This layer summarizes note tables before they are used by footing or
reconciliation checks. It keeps broad semantic candidates and uncertainty
signals without turning them into numeric verdicts.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from dart_footing_reconciler.document import FullReport, ReportSection, ReportTable, SourceLocation
from dart_footing_reconciler.layout_variants import LayoutClassification, classify_layout
from dart_footing_reconciler.note_inventory import NoteTableInventoryItem, build_note_inventory
from dart_footing_reconciler.orientation import TableOrientation, detect_orientation
from dart_footing_reconciler.table_semantics import compact


@dataclass(frozen=True)
class TableFingerprint:
    normalized_section_topic: str
    normalized_header_tokens: tuple[str, ...]
    normalized_stub_labels: tuple[str, ...]
    row_count_bucket: str
    column_axis_schema: str
    unit_pattern: str
    detected_relation_types: tuple[str, ...]
    company: str = ""


@dataclass(frozen=True)
class NoteSemanticTable:
    company: str
    section_id: str
    note_no: str
    title: str
    source: str
    heading: str
    source_location: SourceLocation
    consolidation_basis: str
    unit_multiplier: int
    layout_key: str
    layout_confidence: float
    orientation_key: str
    orientation_confidence: float
    disclosure_families: tuple[str, ...]
    detected_relation_types: tuple[str, ...]
    uncertainty_flags: tuple[str, ...]
    fingerprint: TableFingerprint


@dataclass(frozen=True)
class NoteSemanticExtraction:
    company: str
    tables: tuple[NoteSemanticTable, ...]

    def table_by_source(self, source: str) -> NoteSemanticTable | None:
        for table in self.tables:
            if table.source == source:
                return table
        return None


def build_note_semantic_extraction(report: FullReport) -> NoteSemanticExtraction:
    """Build a semantic note-table summary from an already parsed report."""
    table_lookup = _table_lookup(report)
    semantic_tables: list[NoteSemanticTable] = []

    for item in build_note_inventory(report).tables:
        entry = table_lookup.get(item.source)
        if entry is None:
            continue
        section, table = entry
        semantic_item, header_row_index = _semantic_inventory_item(item, table)
        layout = classify_layout(semantic_item)
        orientation = detect_orientation(
            headers=semantic_item.headers,
            row_labels=semantic_item.row_labels,
        )
        relation_types = _detected_relation_types(semantic_item, table, layout)
        families = _disclosure_families(semantic_item, layout, relation_types)
        uncertainty_flags = _uncertainty_flags(
            semantic_item,
            table,
            layout,
            orientation,
            header_row_index=header_row_index,
        )
        fingerprint = _fingerprint(semantic_item, table, orientation, relation_types)
        semantic_tables.append(
            NoteSemanticTable(
                company=report.company,
                section_id=item.section_id,
                note_no=item.note_no,
                title=item.title,
                source=item.source,
                heading=item.heading,
                source_location=table.location,
                consolidation_basis=section.scope or "unknown",
                unit_multiplier=table.unit_multiplier,
                layout_key=layout.key,
                layout_confidence=layout.confidence,
                orientation_key=orientation.key,
                orientation_confidence=orientation.confidence,
                disclosure_families=families,
                detected_relation_types=relation_types,
                uncertainty_flags=uncertainty_flags,
                fingerprint=fingerprint,
            )
        )

    return NoteSemanticExtraction(report.company, tuple(semantic_tables))


def _semantic_inventory_item(
    item: NoteTableInventoryItem,
    table: ReportTable,
) -> tuple[NoteTableInventoryItem, int]:
    header_row_index = _logical_header_row_index(table.rows)
    return (
        replace(
            item,
            headers=tuple(table.rows[header_row_index]),
            row_labels=_semantic_row_labels(table.rows, header_row_index),
        ),
        header_row_index,
    )


def _logical_header_row_index(rows: list[list[str]]) -> int:
    best_index = 0
    best_score = 0
    for idx, row in enumerate(rows[:-1]):
        maturity_count = _count_maturity_bucket_labels(tuple(row))
        if maturity_count < 2:
            continue
        total_bonus = 1 if _row_has_total_label(row) else 0
        score = maturity_count * 10 + total_bonus
        if score >= best_score:
            best_index = idx
            best_score = score
    return best_index


def _semantic_row_labels(rows: list[list[str]], header_row_index: int) -> tuple[str, ...]:
    return tuple(
        label
        for row in rows[header_row_index + 1 :]
        if (label := _semantic_stub_label(row))
    )


def _semantic_stub_label(row: list[str]) -> str:
    first = row[0] if row else ""
    second = row[1] if len(row) > 1 else ""
    if _should_use_secondary_stub(first, second):
        return second
    return first or second


def _should_use_secondary_stub(first: str, second: str) -> bool:
    normalized_first = compact(first)
    normalized_second = compact(second)
    if not normalized_second or normalized_second == normalized_first:
        return False
    if _looks_like_amount_cell(normalized_second):
        return False
    if normalized_first == "합계구간" and _is_maturity_bucket_label(normalized_second):
        return True
    return _is_group_stub(normalized_first)


def _is_group_stub(value: str) -> bool:
    return any(
        token in value
        for token in (
            "계약상현금흐름",
            "할인되지않은현금흐름",
            "비파생금융부채",
            "파생금융부채",
            "금융부채",
            "금융자산",
        )
    )


def _looks_like_amount_cell(value: str) -> bool:
    if not value:
        return False
    stripped = value.replace(",", "").replace("-", "").replace("(", "").replace(")", "")
    return stripped.isdigit()


def _table_lookup(report: FullReport) -> dict[str, tuple[ReportSection, ReportTable]]:
    lookup: dict[str, tuple[ReportSection, ReportTable]] = {}
    for section in report.notes:
        for block in section.blocks:
            table = block.table
            if table is None:
                continue
            lookup[f"note:{section.note_no}/table:{table.index}"] = (section, table)
    return lookup


def _detected_relation_types(
    item: NoteTableInventoryItem,
    table: ReportTable,
    layout: LayoutClassification,
) -> tuple[str, ...]:
    if layout.key in {
        "lease_liability_maturity_summary",
        "liquidity_maturity_analysis",
        "employee_benefit_maturity_summary",
    }:
        return ("maturity_bucket_sum",)
    if _is_maturity_candidate(item, table):
        return ("maturity_bucket_sum",)
    return ()


def _disclosure_families(
    item: NoteTableInventoryItem,
    layout: LayoutClassification,
    relation_types: tuple[str, ...],
) -> tuple[str, ...]:
    if "maturity_bucket_sum" not in relation_types:
        return ()
    joined = compact(" ".join((item.title, item.heading, *item.headers, *item.row_labels)))
    families: list[str] = []
    if _has_lease_liability_context(joined):
        families.append("lease_liability_schedule")
    if (
        layout.key in {"lease_liability_maturity_summary", "liquidity_maturity_analysis"}
        or "유동성위험" in joined
        or "만기분석" in joined
    ):
        families.append("maturity_analysis")
    return tuple(dict.fromkeys(families or ["maturity_analysis"]))


def _uncertainty_flags(
    item: NoteTableInventoryItem,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
    *,
    header_row_index: int,
) -> tuple[str, ...]:
    flags: list[str] = []
    if layout.key == "unknown_layout":
        flags.append("unknown_layout")
    elif layout.confidence < 0.7:
        flags.append("low_layout_confidence")
    if orientation.key == "unknown":
        flags.append("orientation_unknown")
    elif orientation.confidence < 0.7:
        flags.append("low_orientation_confidence")
    if (
        header_row_index == 0
        and _has_unresolved_multi_header(table)
        and not _is_resolved_row_oriented_lease_maturity(layout, orientation)
    ):
        flags.append("multi_header_unresolved")
    if _is_maturity_candidate(item, table) and not _has_maturity_total(table):
        flags.append("maturity_total_missing")
    return tuple(dict.fromkeys(flags))


def _fingerprint(
    item: NoteTableInventoryItem,
    table: ReportTable,
    orientation: TableOrientation,
    relation_types: tuple[str, ...],
) -> TableFingerprint:
    return TableFingerprint(
        normalized_section_topic=compact(item.title),
        normalized_header_tokens=tuple(compact(header) for header in item.headers if compact(header)),
        normalized_stub_labels=tuple(compact(label) for label in item.row_labels if compact(label)),
        row_count_bucket=_row_count_bucket(item.row_count),
        column_axis_schema=orientation.key,
        unit_pattern=f"x{table.unit_multiplier}",
        detected_relation_types=relation_types,
    )


def _is_maturity_candidate(item: NoteTableInventoryItem, table: ReportTable) -> bool:
    if _is_non_maturity_lease_related_table(table):
        return False
    values = (
        item.title,
        item.heading,
        *item.headers,
        *item.row_labels,
        *[cell for row in table.rows for cell in row],
    )
    joined = compact(" ".join(values))
    title_heading = compact(f"{item.title} {item.heading}")
    if _count_maturity_bucket_labels(values) >= 2 and (
        "리스부채" in joined
        or "유동성위험" in title_heading
        or "만기분석" in title_heading
    ):
        return True
    if "유동성위험" in title_heading and "리스부채" in joined:
        return True
    if "리스부채" in joined and _count_annual_maturity_columns(table.rows) >= 3:
        return True
    return False


def _is_non_maturity_lease_related_table(table: ReportTable) -> bool:
    table_text = compact(" ".join(cell for row in table.rows for cell in row))
    if "운용리스" in table_text and "리스부채" not in table_text:
        return True
    if "내용연수" in table_text and "유형자산" in table_text and "리스부채" not in table_text:
        return True
    return _is_lease_expense_only_table(table_text)


def _is_lease_expense_only_table(table_text: str) -> bool:
    return (
        any(
            token in table_text
            for token in (
                "사용권자산상각비",
                "리스부채에대한이자비용",
                "소액및단기리스료",
                "단기리스료",
            )
        )
        and not any(
            token in table_text
            for token in ("1년이내", "1년초과", "2년이내", "5년초과", "합계구간")
        )
    )


def _has_unresolved_multi_header(table: ReportTable) -> bool:
    if len(table.rows) < 2:
        return False
    first = table.rows[0]
    second = table.rows[1]
    first_nonblank = sum(1 for cell in first if compact(cell))
    second_nonblank = sum(1 for cell in second if compact(cell))
    return first_nonblank <= 1 and second_nonblank >= 2


def _has_maturity_total(table: ReportTable) -> bool:
    return any("합계" in compact(cell) or "총계" in compact(cell) for row in table.rows for cell in row)


def _is_resolved_row_oriented_lease_maturity(
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> bool:
    return (
        layout.key == "lease_liability_maturity_summary"
        and orientation.key == "row_oriented"
    )


def _row_has_total_label(row: list[str]) -> bool:
    return any("합계" in compact(cell) or "총계" in compact(cell) for cell in row)


def _has_lease_liability_context(value: str) -> bool:
    normalized = value.lower()
    return "리스부채" in normalized or "leaseliability" in normalized


def _count_maturity_bucket_labels(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_maturity_bucket_label(value))


def _is_maturity_bucket_label(value: str) -> bool:
    normalized = compact(value).lower()
    if any(token in normalized for token in ("withinoneyear", "lessthanoneyear", "overoneyear")):
        return True
    if "년" not in normalized and "개월" not in normalized:
        return False
    return any(token in normalized for token in ("이내", "이하", "초과", "미만", "이상", "~"))


def _count_annual_maturity_columns(rows: list[list[str]]) -> int:
    if not rows:
        return 0
    return max(
        (sum(1 for cell in row[1:] if _is_annual_maturity_column(cell)) for row in rows),
        default=0,
    )


def _is_annual_maturity_column(value: str) -> bool:
    normalized = compact(value)
    if "년" not in normalized:
        return False
    if any(token in normalized for token in ("이내", "초과", "미만", "이상")):
        return False
    return any(char.isdigit() for char in normalized)


def _row_count_bucket(row_count: int) -> str:
    if row_count == 0:
        return "0"
    if row_count <= 2:
        return "1-2"
    if row_count <= 5:
        return "3-5"
    if row_count <= 10:
        return "6-10"
    return "11+"
