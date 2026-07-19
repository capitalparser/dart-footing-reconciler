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
    "cashflow_reconciliation": "현금흐름표-주석 대사",
    "fs_note_match": "재무제표-주석 대사",
    "asset_note_bridge_check": "현금흐름표-주석 대사",
    "expense_allocation": "재무제표-주석 대사",
    "note_reference_check": "재무제표-주석 대사",
    "statement_note_row_reconciliation": "재무제표-주석 대사",
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
    "statement_note_row_reconciliation": "statement_note",
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

CHECK_PRESENTATIONS: dict[str, str] = {
    check_type: (
        "cell"
        if check_type
        in {
            "total_check",
            "note_rollforward_check",
            "note_layout_formula_check",
            "appropriation_formula_check",
        }
        else "drawer"
    )
    for check_type in CHECK_GROUPS
}

TARGET_EVIDENCE_ROLES: dict[str, tuple[str, ...]] = {
    "total_check": ("target",),
    "note_rollforward_check": ("ending",),
    "note_layout_formula_check": ("target",),
    "appropriation_formula_check": ("target",),
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
    "statement_note_row_reconciliation": "재무제표 계정의 당기 금액 = 본문에 표시된 주석의 해당 계정 금액",
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

CHECK_DISPLAY_NAMES: dict[str, str] = {
    "statement_bs_equation": "재무상태표 등식 검증",
    "statement_cash_tie": "현금및현금성자산 대사",
    "statement_equity_tie": "자본총계 대사",
    "total_check": "표 합계 검증",
    "prior_year_beginning_balance_match": "전기말-당기초 대사",
    "prior_column_fs_note": "전기 재무제표-주석 대사",
    "prior_column_rollforward": "전기 기초잔액 대사",
    "prior_year_amount_match": "전기 공시 금액 대사",
    "prior_year_structure_change": "전기 주석 구조 확인",
    "cfs_note_match": "현금흐름표-주석 대사",
    "primary_balance_reconciliation": "재무상태표-주석 잔액 대사",
    "cashflow_reconciliation": "현금흐름 금액 대사",
    "fs_note_match": "재무제표-주석 대사",
    "asset_note_bridge_check": "자산 취득·처분 대사",
    "expense_allocation": "비용 배분 대사",
    "note_reference_check": "주석 참조 확인",
    "statement_note_row_reconciliation": "재무제표 계정-주석 금액 대사",
    "note_note_match": "주석 간 금액 대사",
    "note_note_reconciliation": "주석 간 잔액 대사",
    "note_rollforward_check": "주석 증감표 검산",
    "note_balance_bridge_check": "주석 잔액 합계 검증",
    "note_internal_consistency_check": "주석 내부 일관성 검증",
    "note_layout_formula_check": "주석 표 산식 검증",
    "appropriation_formula_check": "이익잉여금 처분 산식 검증",
}

_DISPLAY_REASON_TEXTS = {
    "row total agrees": "행 구성항목 합계가 표시 금액과 일치함",
    "column total agrees": "열 구성항목 합계가 표시 금액과 일치함",
    "row total does not agree": "행 구성항목 합계와 표시 금액 간 차이가 있음",
    "column total does not agree": "열 구성항목 합계와 표시 금액 간 차이가 있음",
    "no reliable total label found": "합계/소계 표시를 신뢰성 있게 식별하지 못함",
    "financial statement amount agrees to note amount": "재무제표 금액과 주석 금액이 일치함",
    "financial statement amount agrees within display-unit rounding": (
        "재무제표 금액과 주석 금액의 차이가 표시단위 절사 허용범위 내에 있음"
    ),
    "financial statement amount does not agree to note amount": "재무제표 금액과 주석 금액 간 차이가 있음",
    "financial statement line agrees to note ending balance": "재무제표 계정과 주석 기말 장부금액이 일치함",
    "financial statement line does not agree to note ending balance": (
        "재무제표 계정과 주석 기말 장부금액 간 차이가 있음"
    ),
    "cash flow statement amount agrees to note movement": "현금흐름표 항목과 관련 주석 변동금액이 일치함",
    "cash flow statement amount does not agree to note movement": (
        "현금흐름표 항목과 관련 주석 변동금액 간 차이가 있음"
    ),
    "cash flow statement line agrees to note cash movement": "현금흐름표 금액 크기와 주석 현금성 변동금액이 일치함",
    "cash flow statement line does not agree to note cash movement": (
        "현금흐름표 금액 크기와 주석 현금성 변동금액 간 차이가 있음"
    ),
    "current comparative amount agrees to prior current amount": "당기 비교표시 전기금액과 전기 공시 당기금액이 일치함",
    "current comparative amount does not agree to prior current amount": (
        "당기 비교표시 전기금액과 전기 공시 당기금액 간 차이가 있음"
    ),
    "prior-year ending balance agrees to current-year beginning balance": "전기말 주석 금액과 당기초 주석 금액이 일치함",
    "prior-year ending balance does not agree to current-year beginning balance": (
        "전기말 주석 금액과 당기초 주석 금액 간 차이가 있음"
    ),
    "related note amounts agree": "관련 주석에 반복 공시된 금액이 일치함",
    "multiple candidate note amounts found": "비교할 후보가 여러 개여서 자동으로 확정하지 못했습니다.",
    "candidate difference exceeds statement amount; note balance match is parse uncertain": (
        "후보 금액 차이가 재무제표 금액보다 커서 자동으로 확정하지 못했습니다."
    ),
}

_EVIDENCE_PREFIX_LABELS = (
    ("excluded note ", "대사 제외 주석 "),
    ("nature exclusion ", "성격별 비용 제외 "),
    ("allocation total ", "기능별 배부 합계 "),
    ("current beginning ", "당기 기초 "),
    ("prior ending ", "전기 기말 "),
    ("statement ", "재무제표 "),
    ("cfs ", "현금흐름표 "),
    ("note ", "주석 "),
    ("nature ", "성격별 비용 "),
    ("allocation ", "기능별 배부 "),
)

_EVIDENCE_CODE_LABELS = {
    "financing_adjustment_not_cash": "비현금 재무조정",
    "not_needed_for_best_formula": "최적 대사식에 사용되지 않음",
    "no_formula_match": "적합한 대사식을 찾지 못함",
}

_STATUS_LABELS = {
    "matched": "일치",
    "explainable_gap": "차이 설명 가능",
    "unexplained_gap": "미해소 차이",
    "parse_uncertain": "자동 해석 확인",
    "not_tested": "검증 미수행",
}

_STATUS_COMPACT_LABELS = {
    "matched": "일치",
    "explainable_gap": "설명 가능",
    "unexplained_gap": "차이",
    "parse_uncertain": "해석 확인",
    "not_tested": "미검증",
}

_GENERIC_REASON_BY_STATUS = {
    "matched": "비교 금액이 허용오차 안에서 일치합니다.",
    "explainable_gap": "차이가 확인되었으며 공시 근거로 설명됩니다.",
    "unexplained_gap": "비교 금액의 차이 원인을 확인해야 합니다.",
    "parse_uncertain": "원문 구조를 자동으로 확정하지 못했습니다.",
    "not_tested": "적용 가능한 검증 근거를 확정하지 못했습니다.",
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


@dataclass(frozen=True)
class SourceCellRef:
    scope: str
    name: str
    table_index: int
    row_index: int | None
    column_index: int | None

    @property
    def is_exact_cell(self) -> bool:
        return self.row_index is not None and self.column_index is not None


@dataclass(frozen=True)
class CellAnnotation:
    target: SourceCellRef
    status: str
    checks: tuple[CheckResult, ...]

    @property
    def count(self) -> int:
        return len(self.checks)


@dataclass(frozen=True)
class DrawerItem:
    check: CheckResult
    anchors: tuple[SourceCellRef, ...]


@dataclass(frozen=True)
class WorkbenchAnnotations:
    cells: tuple[CellAnnotation, ...]
    drawers: tuple[DrawerItem, ...]


_CELL_SOURCE_RE = re.compile(
    r"^(statement|note):([^/]+)/table:(\d+)"
    r"(?:/row:(\d+))?(?:/col:(\d+))?$"
)

_DISPLAY_SEVERITY = {
    "matched": 1,
    "explainable_gap": 2,
    "parse_uncertain": 3,
    "unexplained_gap": 4,
}


def source_cell_ref(source: str) -> SourceCellRef | None:
    match = _CELL_SOURCE_RE.match(source)
    if match is None:
        return None
    return SourceCellRef(
        scope=match.group(1),
        name=match.group(2),
        table_index=int(match.group(3)),
        row_index=int(match.group(4)) if match.group(4) is not None else None,
        column_index=int(match.group(5)) if match.group(5) is not None else None,
    )


def build_workbench_annotations(
    report: FullReport,
    checks: list[CheckResult],
) -> WorkbenchAnnotations:
    grouped: dict[SourceCellRef, list[CheckResult]] = {}
    drawers: list[DrawerItem] = []

    for check in checks:
        presentation = CHECK_PRESENTATIONS.get(check.check_type, "drawer")
        refs = tuple(
            dict.fromkeys(
                ref
                for evidence in check.evidence
                if (ref := source_cell_ref(evidence.source))
                and _source_ref_is_renderable(report, ref)
            )
        )
        if presentation == "drawer":
            if check.status != "not_tested":
                drawers.append(DrawerItem(check=check, anchors=refs))
            continue

        roles = TARGET_EVIDENCE_ROLES[check.check_type]
        target = next(
            (
                source_cell_ref(evidence.source)
                for evidence in check.evidence
                if evidence.role in roles
            ),
            None,
        )
        if (
            target is not None
            and target.is_exact_cell
            and _source_ref_is_renderable(report, target)
            and check.status != "not_tested"
        ):
            grouped.setdefault(target, []).append(check)
        elif check.status != "not_tested":
            drawers.append(DrawerItem(check=check, anchors=()))

    cells = tuple(
        CellAnnotation(
            target=target,
            status=max(
                items,
                key=lambda item: _DISPLAY_SEVERITY.get(item.status, 0),
            ).status,
            checks=tuple(items),
        )
        for target, items in grouped.items()
    )
    return WorkbenchAnnotations(cells=cells, drawers=tuple(drawers))


def _source_ref_is_renderable(report: FullReport, ref: SourceCellRef) -> bool:
    table = _table_for_source_ref(report, ref)
    if table is None:
        return False
    if ref.row_index is None:
        return True
    if ref.row_index < 0 or ref.row_index >= len(table.rows):
        return False
    if ref.column_index is None:
        return True
    return 0 <= ref.column_index < len(table.rows[ref.row_index])


def _table_for_source_ref(report: FullReport, ref: SourceCellRef) -> ReportTable | None:
    sections = report.statements if ref.scope == "statement" else report.notes
    for section in sections:
        if not _section_matches_source_ref(section, ref):
            continue
        for block in section.blocks:
            if block.table is not None and block.table.index == ref.table_index:
                return block.table
    return None


def _section_matches_source_ref(section: ReportSection, ref: SourceCellRef) -> bool:
    source_name = section.section_id.split(":", 1)[-1]
    if source_name == ref.name:
        return True
    if ref.scope == "note":
        return section.note_no == ref.name
    kind = statement_kind_from_title(section.title) or statement_kind_from_source(section.section_id)
    return ref.name in _STATEMENT_ALIASES.get(kind, ())


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


def check_display_title(check: CheckResult) -> str:
    title = check.title.strip()
    original_title = title
    replacements = (
        ("FS to note match", "재무제표-주석 대사"),
        ("CFS to note match", "현금흐름표-주석 대사"),
        ("note to note match", "주석 간 금액 대사"),
        ("BS equation", "재무상태표 등식"),
        ("total check", "합계 검증"),
        ("column total", "열 합계 검증"),
    )
    for source, target in replacements:
        title = title.replace(source, target)
    if title != original_title and check.check_type in CHECK_DISPLAY_NAMES:
        return CHECK_DISPLAY_NAMES[check.check_type]
    if re.search(r"[A-Za-z_]", title):
        return CHECK_DISPLAY_NAMES.get(check.check_type, "기타 검증")
    return title or CHECK_DISPLAY_NAMES.get(check.check_type, "기타 검증")


def check_display_reason(check: CheckResult) -> str:
    if check.parse_uncertain_reason == "AMBIGUOUS_MULTIPLE":
        return _DISPLAY_REASON_TEXTS["multiple candidate note amounts found"]
    reason = _DISPLAY_REASON_TEXTS.get(check.reason, check.reason).strip()
    reason = reason.replace("BS", "재무상태표").replace("SCE", "자본변동표")
    if re.search(r"[A-Za-z_]", reason):
        return _GENERIC_REASON_BY_STATUS.get(check.status, "검증 결과를 확인해야 합니다.")
    return reason or _GENERIC_REASON_BY_STATUS.get(check.status, "검증 결과를 확인해야 합니다.")


def check_status_label(status: str) -> str:
    return _STATUS_LABELS.get(status, "확인 필요")


def check_status_compact_label(status: str) -> str:
    return _STATUS_COMPACT_LABELS.get(status, "확인 필요")


def evidence_display_label(label: str) -> str:
    """Return an auditor-facing evidence label without engine vocabulary."""
    display = label.strip()
    for prefix, replacement in _EVIDENCE_PREFIX_LABELS:
        if display.startswith(prefix):
            display = replacement + display[len(prefix):]
            break
    for code, replacement in _EVIDENCE_CODE_LABELS.items():
        display = display.replace(code, replacement)
    duplicate_role_words = (
        ("전기 기말 기말", "전기 기말"),
        ("당기 기초 기초", "당기 기초"),
        ("기능별 배부 합계 합계", "기능별 배부 합계"),
        ("성격별 비용 제외 제외", "성격별 비용 제외"),
    )
    for duplicated, normalized in duplicate_role_words:
        if display.startswith(duplicated):
            display = normalized + display[len(duplicated):]
    return display or "검증 근거"


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
