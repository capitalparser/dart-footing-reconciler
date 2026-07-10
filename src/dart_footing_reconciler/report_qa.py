"""Coverage QA for report validation outputs.

This layer checks whether the validation engine attempted the required audit
families and whether their evidence still points to source tables. It does not
turn normal reviewer findings, such as unexplained gaps, into QA failures.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.checks import CheckResult
from dart_footing_reconciler.checks_note_note import check_note_note_matches
from dart_footing_reconciler.document import FullReport, ReportSection, ReportTable

QA_PASS = "pass"
QA_WARN = "warn"
QA_FAIL = "fail"

_QA_SEVERITY = {QA_PASS: 0, QA_WARN: 1, QA_FAIL: 2}


@dataclass(frozen=True)
class ValidationQAFamily:
    category: str
    label: str
    check_types: tuple[str, ...]


@dataclass(frozen=True)
class ValidationQAItem:
    item_id: str
    category: str
    status: str
    target: str
    expected_family: str
    reason: str
    evidence_sources: tuple[str, ...] = ()
    check_ids: tuple[str, ...] = ()
    check_types: tuple[str, ...] = ()
    severity: int = 50


@dataclass(frozen=True)
class ValidationQAReport:
    items: tuple[ValidationQAItem, ...]

    @property
    def status(self) -> str:
        if not self.items:
            return QA_PASS
        return max((item.status for item in self.items), key=lambda status: _QA_SEVERITY.get(status, 0))

    def status_counts(self) -> dict[str, int]:
        counts = Counter(item.status for item in self.items)
        return {QA_PASS: counts[QA_PASS], QA_WARN: counts[QA_WARN], QA_FAIL: counts[QA_FAIL]}

    def by_category(self) -> dict[str, tuple[ValidationQAItem, ...]]:
        grouped: dict[str, list[ValidationQAItem]] = {}
        for item in self.items:
            grouped.setdefault(item.category, []).append(item)
        return {category: tuple(items) for category, items in grouped.items()}

    def open_items(self) -> tuple[ValidationQAItem, ...]:
        return tuple(item for item in self.items if item.status != QA_PASS)


CORE_FAMILIES = (
    ValidationQAFamily(
        category="statement_body_coverage",
        label="재무제표 본문 검증",
        check_types=(
            "statement_bs_equation",
            "statement_subtotal",
            "statement_cash_tie",
            "statement_equity_tie",
        ),
    ),
    ValidationQAFamily(
        category="total_coverage",
        label="합계검증",
        check_types=(
            "total_check",
            "statement_subtotal",
            "note_layout_formula_check",
            "note_rollforward_check",
            "appropriation_formula_check",
        ),
    ),
    ValidationQAFamily(
        category="fs_note_coverage",
        label="재무제표 본문-주석 대사",
        check_types=(
            "fs_note_match",
            "fs_note_ref_amount_match",
            "primary_balance_reconciliation",
            "note_reference_check",
            "statement_note_reference_accuracy",
            "statement_note_reference_completeness",
            "prior_column_fs_note",
            "prior_column_rollforward",
        ),
    ),
    ValidationQAFamily(
        category="note_note_coverage",
        label="주석간 대사",
        check_types=("note_note_match",),
    ),
    ValidationQAFamily(
        category="cashflow_coverage",
        label="현금흐름표 대사",
        check_types=(
            "cashflow_reconciliation",
            "cfs_note_match",
            "asset_note_bridge_check",
        ),
    ),
    ValidationQAFamily(
        category="prior_period_coverage",
        label="전기 숫자 검증",
        check_types=(
            "prior_column_fs_note",
            "prior_column_rollforward",
            "prior_year_amount_match",
            "prior_year_beginning_balance_match",
            "prior_year_structure_change",
        ),
    ),
)

_CORE_CHECK_TYPES = frozenset(check_type for family in CORE_FAMILIES for check_type in family.check_types)
_FRONTEND_CONTRACT_CATEGORY = "frontend_contract"
_COMPLETION_READINESS_CATEGORY = "completion_readiness"


def build_validation_qa_report(
    report: FullReport,
    checks: list[CheckResult],
    *,
    prior_report: FullReport | None = None,
) -> ValidationQAReport:
    items: list[ValidationQAItem] = []
    expected = _expected_families(report, prior_report=prior_report)
    for family in CORE_FAMILIES:
        if family.category not in expected:
            continue
        family_checks = [check for check in checks if check.check_type in family.check_types]
        items.append(_family_coverage_item(family, family_checks))

    items.extend(_evidence_integrity_items(report, prior_report, checks))
    items.append(_frontend_contract_item(items))
    items.append(_completion_readiness_item(items))
    return ValidationQAReport(tuple(sorted(items, key=_item_sort_key)))


def _expected_families(
    report: FullReport,
    *,
    prior_report: FullReport | None = None,
) -> set[str]:
    expected: set[str] = set()
    if _has_statement_body_targets(report):
        expected.add("statement_body_coverage")
    if _has_total_validation_targets(report):
        expected.add("total_coverage")
    if _has_statement_note_targets(report):
        expected.add("fs_note_coverage")
    if _has_note_note_targets(report):
        expected.add("note_note_coverage")
    if _has_cashflow_targets(report):
        expected.add("cashflow_coverage")
    if prior_report is not None or _has_prior_period_targets(report):
        expected.add("prior_period_coverage")
    return expected


def _family_coverage_item(
    family: ValidationQAFamily,
    family_checks: list[CheckResult],
) -> ValidationQAItem:
    if not family_checks:
        return ValidationQAItem(
            item_id=f"missing:{family.category}",
            category=family.category,
            status=QA_FAIL,
            target=family.label,
            expected_family=family.label,
            reason="검증 대상이 감지되었지만 이 검증군의 결과가 없습니다.",
            check_types=family.check_types,
            severity=90,
        )
    sources = tuple(_unique_sources(family_checks))
    return ValidationQAItem(
        item_id=f"present:{family.category}",
        category=family.category,
        status=QA_PASS,
        target=family.label,
        expected_family=family.label,
        reason=f"{len(family_checks)}개 검증 결과가 있습니다.",
        evidence_sources=sources[:8],
        check_ids=tuple(check.check_id for check in family_checks[:8]),
        check_types=tuple(sorted({check.check_type for check in family_checks})),
        severity=10,
    )


def _evidence_integrity_items(
    report: FullReport,
    prior_report: FullReport | None,
    checks: list[CheckResult],
) -> list[ValidationQAItem]:
    items: list[ValidationQAItem] = []
    for check in checks:
        if check.check_type not in _CORE_CHECK_TYPES:
            continue
        if not _check_requires_source_evidence(check):
            continue
        if not check.evidence:
            items.append(
                ValidationQAItem(
                    item_id=f"evidence-missing:{check.check_id}",
                    category="evidence_integrity",
                    status=QA_FAIL,
                    target=check.title or check.check_id,
                    expected_family=_family_label_for_check(check.check_type),
                    reason="핵심 검증 결과에 근거 source가 없습니다.",
                    check_ids=(check.check_id,),
                    check_types=(check.check_type,),
                    severity=95,
                )
            )
            continue
        for source in _unique_sources([check]):
            problem = _source_problem(report, prior_report, source)
            if problem is None:
                continue
            items.append(
                ValidationQAItem(
                    item_id=f"evidence-broken:{check.check_id}:{source}",
                    category="evidence_integrity",
                    status=QA_FAIL,
                    target=check.title or check.check_id,
                    expected_family=_family_label_for_check(check.check_type),
                    reason=problem,
                    evidence_sources=(source,),
                    check_ids=(check.check_id,),
                    check_types=(check.check_type,),
                    severity=95,
                )
            )
    if not items and any(check.check_type in _CORE_CHECK_TYPES for check in checks):
        items.append(
            ValidationQAItem(
                item_id="evidence-integrity:present",
                category="evidence_integrity",
                status=QA_PASS,
                target="핵심 검증 근거",
                expected_family="근거 위치 무결성",
                reason="핵심 검증 결과의 source 좌표가 원문 표에 연결됩니다.",
                severity=10,
            )
        )
    return items


def _frontend_contract_item(items: list[ValidationQAItem]) -> ValidationQAItem:
    problems: list[str] = []
    for item in items:
        if item.status not in _QA_SEVERITY:
            problems.append(f"{item.item_id}: status")
        if not item.category:
            problems.append(f"{item.item_id}: category")
        if not item.expected_family:
            problems.append(f"{item.item_id}: expected_family")
        if not item.target:
            problems.append(f"{item.item_id}: target")
        if not item.reason:
            problems.append(f"{item.item_id}: reason")
    if problems:
        return ValidationQAItem(
            item_id="frontend-contract:broken",
            category=_FRONTEND_CONTRACT_CATEGORY,
            status=QA_FAIL,
            target="검증 결과 표시 계약",
            expected_family="백엔드-프론트 표시 계약",
            reason="프론트 QA 패널이 표시할 필수 필드가 누락되었습니다: " + ", ".join(problems[:5]),
            severity=92,
        )
    return ValidationQAItem(
        item_id="frontend-contract:present",
        category=_FRONTEND_CONTRACT_CATEGORY,
        status=QA_PASS,
        target="검증 결과 표시 계약",
        expected_family="백엔드-프론트 표시 계약",
        reason="백엔드 검증군, 상태, 사유, 근거 필드가 프론트 QA 패널 표시 계약을 충족합니다.",
        severity=10,
    )


def _completion_readiness_item(items: list[ValidationQAItem]) -> ValidationQAItem:
    open_items = [item for item in items if item.status != QA_PASS]
    if open_items:
        return ValidationQAItem(
            item_id="completion-readiness:open",
            category=_COMPLETION_READINESS_CATEGORY,
            status=QA_FAIL,
            target="검증 작업 완료 여부",
            expected_family="작업 완료 기준",
            reason=f"미완료: 검증 로직/근거/프론트 표시 기준 미충족 항목 {len(open_items)}건이 남아 있습니다.",
            check_ids=tuple(item.item_id for item in open_items[:8]),
            check_types=tuple(sorted({check_type for item in open_items for check_type in item.check_types})),
            severity=100,
        )
    return ValidationQAItem(
        item_id="completion-readiness:ready",
        category=_COMPLETION_READINESS_CATEGORY,
        status=QA_PASS,
        target="검증 작업 완료 여부",
        expected_family="작업 완료 기준",
        reason="검증 로직, 근거 좌표, 프론트 표시 계약이 완료 기준을 충족합니다.",
        severity=10,
    )


def _check_requires_source_evidence(check: CheckResult) -> bool:
    return check.expected is not None or check.actual is not None or check.difference is not None


def _source_problem(
    report: FullReport,
    prior_report: FullReport | None,
    source: str,
) -> str | None:
    if not source:
        return "빈 근거 source입니다."
    parsed_any = False
    for part in source.split(";"):
        ref = part.strip()
        if not ref:
            continue
        source_context, ref_body = _split_source_context(ref)
        source_reports = _source_reports_for_context(report, prior_report, source_context)
        if source_reports is None:
            return f"전기 보고서 근거 source이지만 prior_report가 없습니다: {ref}"
        parsed = _parse_table_source(ref)
        if parsed is None:
            # Section/body-level references are acceptable for note-reference
            # checks because they point to text, not a numeric table cell.
            if _parse_section_source(ref_body) is not None:
                parsed_any = True
                continue
            return f"근거 source 형식을 해석할 수 없습니다: {ref}"
        parsed_any = True
        scope, table_idx, row_idx, col_idx = parsed
        table = _table_by_index(source_reports, scope, table_idx)
        if table is None:
            return f"근거 표를 찾을 수 없습니다: {ref}"
        if row_idx is not None and (row_idx < 0 or row_idx >= len(table.rows)):
            return f"근거 행이 표 범위를 벗어납니다: {ref}"
        if col_idx is not None:
            if row_idx is None:
                max_cols = max((len(row) for row in table.rows), default=0)
            else:
                max_cols = len(table.rows[row_idx])
            if col_idx < 0 or col_idx >= max_cols:
                return f"근거 열이 표 범위를 벗어납니다: {ref}"
    if not parsed_any:
        return "근거 source가 비어 있습니다."
    return None


def _split_source_context(source: str) -> tuple[str, str]:
    if (source or "").startswith("prior:"):
        return "prior", source[len("prior:"):]
    return "current", source or ""


def _source_reports_for_context(
    report: FullReport,
    prior_report: FullReport | None,
    context: str,
) -> tuple[FullReport, ...] | None:
    if context == "prior":
        if prior_report is None:
            return None
        return (prior_report,)
    return (report,)


def _parse_table_source(source: str) -> tuple[str, int, int | None, int | None] | None:
    _, source = _split_source_context(source)
    m = re.match(
        r"^(statement|note):([^/]+)/table:(\d+)"
        r"(?:(?:/row:(\d+))?(?:/col:(\d+))?|/(?:beginning|ending|current|comparative|prior))$",
        source,
    )
    if not m:
        m = re.match(r"^(statement|note):([^/]+)/table:(\d+)$", source)
    if not m:
        return None
    scope, _, table_idx, row_idx, col_idx = m.groups()
    return scope, int(table_idx), int(row_idx) if row_idx else None, int(col_idx) if col_idx else None


def _parse_section_source(source: str) -> tuple[str, str] | None:
    _, source = _split_source_context(source)
    m = re.match(
        r"^(statement|note):([^/:]+)(?:(?::block\d+|/block:\d+)|/(?:beginning|ending|current|comparative|prior))?$",
        source,
    )
    if not m:
        return None
    return m.group(1), m.group(2)


def _table_by_index(
    source_reports: tuple[FullReport, ...],
    scope: str,
    table_idx: int,
) -> ReportTable | None:
    for report in source_reports:
        sections = report.statements if scope == "statement" else report.notes
        for section in sections:
            for block in section.blocks:
                if block.table is not None and block.table.index == table_idx:
                    return block.table
    return None


def _has_statement_body_targets(report: FullReport) -> bool:
    for section in report.statements:
        title = _compact(section.title)
        row_labels = {
            _structural_statement_label(row[0])
            for table in _section_tables(section)
            for row in table.rows[1:]
            if row
        }
        if "재무상태표" in title and {
            "자산총계",
            "부채총계",
            "자본총계",
        } <= row_labels:
            return True
        if "현금흐름표" in title and any(label.startswith("기말현금및현금성자산") for label in row_labels):
            return True
        if "자본변동표" in title and any("기말" in label and "자본" in label for label in row_labels):
            return True
        if row_labels & {
            "유동자산",
            "비유동자산",
            "유동부채",
            "비유동부채",
            "투자활동현금흐름",
            "재무활동현금흐름",
        }:
            return True
    return False


def _has_total_validation_targets(report: FullReport) -> bool:
    return any(_table_has_total_target(table) for table in _all_tables(report))


def _table_has_total_target(table: ReportTable) -> bool:
    for row in table.rows:
        if not any(parse_amount(cell) is not None for cell in row):
            continue
        labels = [cell for cell in row if parse_amount(cell) is None]
        if any(_is_total_label(label) for label in labels):
            return True
    for row in table.rows[: min(4, len(table.rows))]:
        for cell in row:
            if parse_amount(cell) is None and _is_total_label(cell):
                return True
    return False


def _has_statement_note_targets(report: FullReport) -> bool:
    if not report.statements or not report.notes:
        return False
    for section in report.statements:
        if "현금흐름" in section.title:
            continue
        for table in _section_tables(section):
            for row in table.rows:
                if any(_cell_has_note_ref(cell) for cell in row) and any(parse_amount(cell) is not None for cell in row):
                    return True
    statement_text = " ".join(
        _compact(cell)
        for section in report.statements
        if "현금흐름" not in section.title
        for table in _section_tables(section)
        for row in table.rows
        for cell in row
    )
    note_titles = [_compact(section.title) for section in report.notes]
    return any(title and title in statement_text for title in note_titles)


def _has_note_note_targets(report: FullReport) -> bool:
    return bool(check_note_note_matches(report, tolerance=1))


def _has_cashflow_targets(report: FullReport) -> bool:
    cf_sections = [section for section in report.statements if "현금흐름" in section.title]
    if not cf_sections:
        return False
    movement_terms = (
        "유형자산",
        "무형자산",
        "투자부동산",
        "사용권자산",
        "차입금",
        "사채",
        "리스",
        "상환",
        "취득",
        "처분",
    )
    action_terms = ("취득", "처분", "상환", "차입", "지급", "수취")
    for section in cf_sections:
        for table in _section_tables(section):
            for row in table.rows:
                row_text = _compact(" ".join(row))
                if any(term in row_text for term in movement_terms) and any(term in row_text for term in action_terms):
                    return True
    return False


def _has_prior_period_targets(report: FullReport) -> bool:
    return any(_table_has_prior_period_target(table) for table in _all_tables(report))


def _table_has_prior_period_target(table: ReportTable) -> bool:
    if not table.rows:
        return False
    candidate_headers = table.rows[: min(4, len(table.rows))]
    prior_header = any(
        _is_prior_period_header(cell)
        for row in candidate_headers
        for cell in row[1:]
        if parse_amount(cell) is None
    )
    if not prior_header:
        return False
    return any(any(parse_amount(cell) is not None for cell in row[1:]) for row in table.rows[1:])


def _all_tables(report: FullReport) -> list[ReportTable]:
    return [table for section in report.statements + report.notes for table in _section_tables(section)]


def _section_tables(section: ReportSection) -> list[ReportTable]:
    return [block.table for block in section.blocks if block.table is not None]


def _is_total_label(value: str) -> bool:
    label = _compact(value)
    if label in {"계", "합계", "소계", "총계"}:
        return True
    return label.endswith(("합계", "소계", "총계"))


def _structural_statement_label(value: str) -> str:
    return _compact(re.sub(r"\([^)]*\)", "", value or ""))


def _is_prior_period_header(value: str) -> bool:
    label = _compact(value)
    return any(token in label for token in ("전기", "전년", "전년도", "비교", "전기말"))


def _cell_has_note_ref(value: str) -> bool:
    text = _compact(value)
    return bool(re.search(r"(?:주석?|註)\d+", text) or re.search(r"\(주\d+\)", text))


def _compact(value: str) -> str:
    return re.sub(r"[\s,·ㆍ\-.()（）]", "", value or "")


def _unique_sources(checks: list[CheckResult]) -> list[str]:
    seen: set[str] = set()
    sources: list[str] = []
    for check in checks:
        for evidence in check.evidence:
            for source in evidence.source.split(";"):
                source = source.strip()
                if source and source not in seen:
                    seen.add(source)
                    sources.append(source)
    return sources


def _family_label_for_check(check_type: str) -> str:
    for family in CORE_FAMILIES:
        if check_type in family.check_types:
            return family.label
    return "핵심 검증"


def _item_sort_key(item: ValidationQAItem) -> tuple[int, str, str]:
    return (-item.severity, item.category, item.item_id)
