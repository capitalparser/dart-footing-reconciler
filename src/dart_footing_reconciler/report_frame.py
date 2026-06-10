"""Report-order verification frame for HTML rendering."""

from __future__ import annotations

from dataclasses import dataclass
import re

from dart_footing_reconciler.checks import CheckResult
from dart_footing_reconciler.document import FullReport, ReportSection, ReportTable


CANONICAL_SECTION_ORDER = (
    "financial_position",
    "income_statement",
    "changes_in_equity",
    "cash_flows",
    "notes",
)

CANONICAL_STATEMENT_ORDER = CANONICAL_SECTION_ORDER[:-1]

CHECK_GROUP_ORDER = (
    "재무제표 교차 검증",   # statement_bs_equation, statement_cash_tie, statement_equity_tie
    "합계 검증",
    "전기대사",
    "재무제표-주석 대사",
    "현금흐름표-주석 대사",
    "주석끼리 대사",
    "주석 내부/공식 검증",
)

_STATEMENT_ALIASES = {
    "financial_position": ("bs", "balance_sheet", "financial_position", "재무상태표"),
    "income_statement": ("is", "pl", "income_statement", "손익계산서", "포괄손익계산서"),
    "changes_in_equity": ("sce", "ce", "equity", "changes_in_equity", "자본변동표"),
    "cash_flows": ("cf", "cfs", "cashflow", "cash_flows", "현금흐름표"),
}


@dataclass(frozen=True)
class PriorReconciliationFrame:
    status: str
    message: str


@dataclass(frozen=True)
class SourceTableFrame:
    source: str
    table: ReportTable
    check_groups: dict[str, tuple[CheckResult, ...]]
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class StatementFrameSection:
    kind: str
    title: str
    source_section: ReportSection
    tables: tuple[SourceTableFrame, ...]


@dataclass(frozen=True)
class NoteFrameSection:
    note_no: str
    title: str
    source_section: ReportSection
    tables: tuple[SourceTableFrame, ...]


@dataclass(frozen=True)
class ReportFrame:
    statement_sections: tuple[StatementFrameSection, ...]
    notes: tuple[NoteFrameSection, ...]
    prior_reconciliation: PriorReconciliationFrame


def build_report_frame(report: FullReport, checks: list[CheckResult]) -> ReportFrame:
    statement_builders: list[tuple[str, ReportSection, list[_SourceTableBuilder]]] = []
    note_builders: list[tuple[ReportSection, list[_SourceTableBuilder]]] = []
    source_lookup: dict[str, _SourceTableBuilder] = {}
    note_no_lookup: dict[str, _SourceTableBuilder] = {}

    for section in report.statements:
        kind = statement_kind_from_title(section.title) or statement_kind_from_source(section.section_id)
        if kind not in CANONICAL_STATEMENT_ORDER:
            continue
        builders: list[_SourceTableBuilder] = []
        for table in _section_tables(section):
            source = f"{section.section_id}/table:{table.index}"
            aliases = _statement_table_aliases(kind, section.section_id, table.index)
            builder = _SourceTableBuilder(source=source, table=table, aliases=aliases)
            builders.append(builder)
            for alias in aliases:
                source_lookup[alias] = builder
        if builders:
            statement_builders.append((kind, section, builders))

    for section in report.notes:
        builders = []
        for table in _section_tables(section):
            source = f"{section.section_id}/table:{table.index}"
            aliases = _note_table_aliases(section, table.index)
            builder = _SourceTableBuilder(source=source, table=table, aliases=aliases)
            builders.append(builder)
            for alias in aliases:
                source_lookup[alias] = builder
            if section.note_no and section.note_no not in note_no_lookup:
                note_no_lookup[section.note_no] = builder
        note_builders.append((section, builders))

    for check in checks:
        group = check_group(check)
        attached: set[int] = set()
        for evidence in check.evidence:
            table_source = _source_table_prefix(evidence.source)
            builder = source_lookup.get(table_source)
            if builder is None and evidence.source.startswith("note:") and "/table:" not in evidence.source:
                note_no = evidence.source.split("note:", 1)[1].split("/", 1)[0]
                builder = note_no_lookup.get(note_no)
            if builder is None or id(builder) in attached:
                continue
            builder.groups.setdefault(group, []).append(check)
            attached.add(id(builder))

    statement_sections = tuple(
        StatementFrameSection(
            kind=kind,
            title=section.title,
            source_section=section,
            tables=tuple(builder.to_frame() for builder in builders),
        )
        for kind, section, builders in sorted(
            statement_builders,
            key=lambda item: (CANONICAL_STATEMENT_ORDER.index(item[0]), _source_sort_key(item[1].section_id)),
        )
    )
    notes = tuple(
        NoteFrameSection(
            note_no=section.note_no,
            title=section.title,
            source_section=section,
            tables=tuple(builder.to_frame() for builder in builders),
        )
        for section, builders in note_builders
    )
    prior_checks = [check for check in checks if check.check_type == "prior_year_beginning_balance_match"]
    prior_reconciliation = (
        PriorReconciliationFrame("performed", f"전기대사 수행: {len(prior_checks)}개 항목")
        if prior_checks
        else PriorReconciliationFrame("not_performed", "전기대사 미수행: prior-html 미제공")
    )
    return ReportFrame(
        statement_sections=statement_sections,
        notes=notes,
        prior_reconciliation=prior_reconciliation,
    )


@dataclass
class _SourceTableBuilder:
    source: str
    table: ReportTable
    aliases: tuple[str, ...]
    groups: dict[str, list[CheckResult]]

    def __init__(self, source: str, table: ReportTable, aliases: tuple[str, ...]) -> None:
        self.source = source
        self.table = table
        self.aliases = aliases
        self.groups = {}

    def to_frame(self) -> SourceTableFrame:
        ordered = {
            group: tuple(self.groups[group])
            for group in CHECK_GROUP_ORDER
            if group in self.groups
        }
        for group, checks in self.groups.items():
            if group not in ordered:
                ordered[group] = tuple(checks)
        return SourceTableFrame(
            source=self.source,
            table=self.table,
            check_groups=ordered,
            aliases=self.aliases,
        )


def statement_kind_from_title(title: str) -> str:
    normalized = _compact(title)
    if "재무상태표" in normalized:
        return "financial_position"
    if "자본변동표" in normalized:
        return "changes_in_equity"
    if "현금흐름표" in normalized:
        return "cash_flows"
    if "손익계산서" in normalized or "포괄손익계산서" in normalized:
        return "income_statement"
    return ""


def statement_kind_from_source(source: str) -> str:
    if not source.startswith("statement:"):
        return ""
    head = source.split("/", 1)[0].split(":", 1)[1]
    normalized = _compact(head)
    for kind, aliases in _STATEMENT_ALIASES.items():
        if normalized in {_compact(alias) for alias in aliases}:
            return kind
    return ""


def check_group(check: CheckResult) -> str:
    if check.check_type == "total_check":
        return "합계 검증"
    if check.check_type in {
        "prior_year_beginning_balance_match",
        "prior_column_fs_note",
        "prior_column_rollforward",
    }:
        return "전기대사"
    if check.check_type == "cfs_note_match":
        return "현금흐름표-주석 대사"
    if check.check_type in {
        "primary_balance_reconciliation",
        "cashflow_reconciliation",
        "fs_note_match",
        "asset_note_bridge_check",
        "expense_allocation",
    }:
        return "재무제표-주석 대사"
    if check.check_type in {"note_note_match", "note_note_reconciliation"}:
        return "주석끼리 대사"
    if check.check_type in {
        "note_rollforward_check",
        "note_balance_bridge_check",
        "note_internal_consistency_check",
        "note_layout_formula_check",
    }:
        return "주석 내부/공식 검증"
    sources = [evidence.source for evidence in check.evidence]
    if any(source.startswith("statement:") for source in sources) and any(
        source.startswith("note:") for source in sources
    ):
        return "재무제표-주석 대사"
    return "주석 내부/공식 검증"


def check_layer(check: CheckResult) -> str:
    if check.check_type in {
        "primary_balance_reconciliation",
        "cashflow_reconciliation",
        "fs_note_match",
        "cfs_note_match",
        "asset_note_bridge_check",
        "expense_allocation",
        "prior_column_fs_note",
    }:
        return "statement_note"
    if check.check_type in {
        "total_check",
        "note_rollforward_check",
        "note_balance_bridge_check",
        "note_internal_consistency_check",
        "note_layout_formula_check",
        "note_note_match",
        "note_note_reconciliation",
        "prior_column_rollforward",
    }:
        return "note_internal"
    if check.check_type in {
        "statement_bs_equation",
        "statement_cash_tie",
        "statement_equity_tie",
    }:
        return "statement_cross"
    if check.check_type == "prior_year_beginning_balance_match":
        return "prior_report"
    sources = [evidence.source for evidence in check.evidence]
    if any(source.startswith("statement:") for source in sources) and any(
        source.startswith("note:") for source in sources
    ):
        return "statement_note"
    if sources and all(source.startswith("note:") for source in sources if source):
        return "note_internal"
    return "unknown"


def _section_tables(section: ReportSection) -> list[ReportTable]:
    return [
        block.table
        for block in section.blocks
        if block.table is not None and getattr(block.table, "rows", None)
    ]


def _statement_table_aliases(kind: str, section_id: str, table_index: int) -> tuple[str, ...]:
    aliases = {f"{section_id}/table:{table_index}"}
    for alias in _STATEMENT_ALIASES.get(kind, ()):
        aliases.add(f"statement:{alias}/table:{table_index}")
    return tuple(sorted(aliases))


def _note_table_aliases(section: ReportSection, table_index: int) -> tuple[str, ...]:
    aliases = {f"{section.section_id}/table:{table_index}"}
    if section.note_no:
        aliases.add(f"note:{section.note_no}/table:{table_index}")
    return tuple(sorted(aliases))


def _source_table_prefix(source: str) -> str:
    if "/table:" not in source:
        return ""
    prefix, tail = source.split("/table:", 1)
    table_index = tail.split("/", 1)[0]
    return f"{prefix}/table:{table_index}"


def _note_section_sort_key(section: ReportSection) -> tuple[tuple[int, ...], str]:
    numbers = tuple(int(value) for value in re.findall(r"\d+", section.note_no or section.section_id))
    return (numbers or (9999,), section.title)


def _source_sort_key(source: str) -> tuple[int, ...]:
    numbers = tuple(int(value) for value in re.findall(r"\d+", source))
    return numbers or (0,)


def _compact(value: str) -> str:
    return "".join(value.split()).lower()
