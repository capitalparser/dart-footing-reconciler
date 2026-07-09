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
    "appropriation",
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

CHECK_GROUPS: dict[str, str] = {
    "statement_bs_equation": "재무제표 교차 검증",
    "statement_cash_tie": "재무제표 교차 검증",
    "statement_equity_tie": "재무제표 교차 검증",
    "total_check": "합계 검증",
    "prior_year_beginning_balance_match": "전기대사",
    "prior_column_fs_note": "전기대사",
    "prior_column_rollforward": "전기대사",
    "prior_year_amount_match": "전기대사",
    "prior_year_structure_change": "전기대사",
    "cfs_note_match": "현금흐름표-주석 대사",
    "primary_balance_reconciliation": "재무제표-주석 대사",
    "cashflow_reconciliation": "재무제표-주석 대사",
    "fs_note_match": "재무제표-주석 대사",
    "asset_note_bridge_check": "재무제표-주석 대사",
    "expense_allocation": "재무제표-주석 대사",
    "note_reference_check": "재무제표-주석 대사",
    "note_note_match": "주석끼리 대사",
    # Reserved: no current producer emits this check type yet.
    "note_note_reconciliation": "주석끼리 대사",
    "note_rollforward_check": "주석 내부/공식 검증",
    # Reserved: no current producer emits this check type yet.
    "note_balance_bridge_check": "주석 내부/공식 검증",
    # Reserved: no current producer emits this check type yet.
    "note_internal_consistency_check": "주석 내부/공식 검증",
    "note_layout_formula_check": "주석 내부/공식 검증",
    "appropriation_formula_check": "주석 내부/공식 검증",
}

CHECK_LAYERS: dict[str, str] = {
    "primary_balance_reconciliation": "statement_note",
    "cashflow_reconciliation": "statement_note",
    "fs_note_match": "statement_note",
    "cfs_note_match": "statement_note",
    "asset_note_bridge_check": "statement_note",
    "expense_allocation": "statement_note",
    "prior_column_fs_note": "statement_note",
    "note_reference_check": "statement_note",
    "total_check": "note_internal",
    "note_rollforward_check": "note_internal",
    # Reserved: no current producer emits this check type yet.
    "note_balance_bridge_check": "note_internal",
    # Reserved: no current producer emits this check type yet.
    "note_internal_consistency_check": "note_internal",
    "note_layout_formula_check": "note_internal",
    "appropriation_formula_check": "note_internal",
    "note_note_match": "note_internal",
    # Reserved: no current producer emits this check type yet.
    "note_note_reconciliation": "note_internal",
    "prior_column_rollforward": "note_internal",
    "statement_bs_equation": "statement_cross",
    "statement_cash_tie": "statement_cross",
    "statement_equity_tie": "statement_cross",
    "prior_year_beginning_balance_match": "prior_report",
    "prior_year_amount_match": "prior_report",
    "prior_year_structure_change": "prior_report",
}

TABLE_UNIT_TOLERANCE_CHECK_TYPES = frozenset({
    "total_check",
    "note_rollforward_check",
    # Broad layout formulas are sourced from source-table candidates; render
    # their tolerance as display-unit arithmetic for auditor-facing drilldowns.
    "note_layout_formula_check",
    "appropriation_formula_check",
})

CHECK_METHOD_DESCRIPTIONS: dict[str, str] = {
    "statement_bs_equation": "자산총계 = 부채총계 + 자본총계",
    "statement_cash_tie": "재무상태표 현금및현금성자산 기말금액 = 현금흐름표 기말 현금",
    "statement_equity_tie": "자본변동표 기말 자본총계 = 재무상태표 자본총계",
    "total_check": "표 안의 구성요소 합계 = 표시된 합계 (행·소계·총계·열 방향)",
    "prior_year_beginning_balance_match": "전기 말 장부금액 = 당기 기초 장부금액",
    "prior_column_fs_note": "당기 공시 안의 재무제표 전기 열 금액 = 주석 전기 열 금액",
    "prior_column_rollforward": "주석 증감표의 기초 장부금액 = 재무제표 전기 열 금액",
    "prior_year_amount_match": "당기 비교표시 전기 금액 = 전기 공시 당기 금액",
    "prior_year_structure_change": "당기 주석 구조와 전기 주석 구조의 번호·행 존재 여부 비교",
    "cfs_note_match": "현금흐름표 라인 금액 ↔ 관련 주석의 취득·처분·증감 금액 (부호 무시, 크기 비교)",
    "primary_balance_reconciliation": "재무상태표 본문 계정 금액 ↔ 관련 주석 기말 장부금액",
    "cashflow_reconciliation": "현금흐름표 본문 라인 금액 ↔ 주석 증감·취득·처분 금액",
    "fs_note_match": "재무제표 본문 라인 금액 ↔ 해당 주석의 합계·기말 금액",
    "asset_note_bridge_check": "자산 주석의 취득·처분 금액 ↔ 현금흐름표 투자활동 취득·처분 라인",
    "expense_allocation": "성격별 비용 주석의 상각비 = 기능별 배분 주석의 합계",
    "note_reference_check": "재무제표 말 주기 참조 번호 ↔ 실제 주석 번호·내용 존재 여부",
    "note_note_match": "두 주석에 반복 공시된 동일 항목 금액 상호 대조",
    # Reserved: no current producer emits this check type yet.
    "note_note_reconciliation": "관련 주석 간 기초·증감·기말 연결 금액 상호 대조",
    "note_rollforward_check": "기초 장부금액 + 증감 합계 = 기말 장부금액",
    # Reserved: no current producer emits this check type yet.
    "note_balance_bridge_check": "주석의 세부 잔액 합계 = 표시된 장부금액·총액",
    # Reserved: no current producer emits this check type yet.
    "note_internal_consistency_check": "동일 주석 안에서 반복 표시된 같은 항목 금액 일치 여부",
    "note_layout_formula_check": "주석 표 레이아웃의 산식 행·열 구성요소 합계 = 표시 금액",
    "appropriation_formula_check": "미처분이익잉여금 + 이입액 - 처분액 = 차기이월미처분이익잉여금",
}

_STATEMENT_ALIASES = {
    "financial_position": ("bs", "balance_sheet", "financial_position", "재무상태표"),
    "income_statement": ("is", "pl", "income_statement", "손익계산서", "포괄손익계산서"),
    "changes_in_equity": ("sce", "ce", "equity", "changes_in_equity", "자본변동표"),
    "cash_flows": ("cf", "cfs", "cashflow", "cash_flows", "현금흐름표"),
    "appropriation": ("appropriation", "이익잉여금처분계산서", "결손금처리계산서"),
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
    if "처분계산서" in normalized or "처리계산서" in normalized:
        return "appropriation"
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
    if check.check_type in CHECK_GROUPS:
        return CHECK_GROUPS[check.check_type]
    sources = [evidence.source for evidence in check.evidence]
    if any(source.startswith("statement:") for source in sources) and any(
        source.startswith("note:") for source in sources
    ):
        return "재무제표-주석 대사"
    return "주석 내부/공식 검증"


def check_layer(check: CheckResult) -> str:
    if check.check_type in CHECK_LAYERS:
        return CHECK_LAYERS[check.check_type]
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
