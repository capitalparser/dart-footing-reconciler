"""Desktop source-workbench contracts for the audit HTML renderer."""

from dataclasses import replace
from pathlib import Path

from bs4 import BeautifulSoup

from dart_footing_reconciler.checks import (
    CheckEvidence,
    CheckResult,
    MATCHED,
    NOT_TESTED,
    PARSE_UNCERTAIN,
    UNEXPLAINED_GAP,
)
from dart_footing_reconciler.document import (
    FullReport,
    ReportBlock,
    ReportSection,
    ReportTable,
    SourceLocation,
)
from dart_footing_reconciler.report_html import export_audit_reconciliation_html


def _section(
    section_id: str,
    title: str,
    kind: str,
    note_no: str,
    table_index: int,
    amount: str,
) -> ReportSection:
    table = ReportTable(
        table_index,
        [["구분", "당기"], ["유형자산", amount]],
        title,
        SourceLocation(section_id, 0, table_index),
    )
    return ReportSection(
        section_id,
        title,
        kind,
        note_no,
        [ReportBlock("table", "", table, table.location)],
    )


def _report() -> FullReport:
    return FullReport(
        "test.html",
        "테스트(주)",
        [_section("statement:bs", "재무상태표", "statement", "", 0, "100")],
        [_section("note:11", "유형자산", "note", "11", 1, "90")],
    )


def _cross_check(status: str = UNEXPLAINED_GAP) -> CheckResult:
    return CheckResult(
        "private-fs-note",
        "fs_note_match",
        status,
        "report",
        "11",
        "재무제표-주석 대사",
        100,
        90,
        -10,
        1,
        "financial statement amount does not agree to note amount",
        [
            CheckEvidence("재무제표", 100, "statement:bs/table:0/row:1/col:1"),
            CheckEvidence("주석", 90, "note:11/table:1/row:1/col:1"),
        ],
    )


def _render(tmp_path: Path, checks: list[CheckResult]) -> str:
    output = tmp_path / "report.html"
    export_audit_reconciliation_html(_report(), checks, output)
    return output.read_text(encoding="utf-8")


def test_report_html_uses_source_workbench_navigation_and_drawer(tmp_path: Path):
    content = _render(tmp_path, [_cross_check()])

    assert 'class="audit-workbench"' in content
    assert 'class="source-nav"' in content
    assert 'class="source-stage"' in content
    assert 'id="reconciliation-drawer"' in content
    assert "재무제표 본문" in content
    assert "각 주석" in content
    assert "대사 결과" in content
    assert "필요한 행동" in content
    assert 'data-drawer-item="0"' in content
    assert 'data-open-drawer="0"' in content
    assert "재무제표 금액" in content
    assert "주석 11 금액" in content
    assert "차이" in content
    assert 'data-source-jump="0"' in content
    assert 'data-source-jump="1"' not in content
    assert "대시보드" not in content
    assert "진행상황" not in content
    assert "검증 범례" not in content


def test_drawer_amounts_show_full_values_in_vertical_rows(tmp_path: Path):
    content = _render(tmp_path, [_cross_check()])

    assert ".drawer-amounts{display:grid;grid-template-columns:1fr" in content
    assert ".drawer-amounts div{display:flex;align-items:baseline;justify-content:space-between" in content
    assert ".drawer-amounts dd{margin:0;white-space:nowrap" in content


def test_report_header_and_drawer_share_one_result_filter_population(tmp_path: Path):
    uncertain = CheckResult(
        "uncertain",
        "note_reference_check",
        PARSE_UNCERTAIN,
        "report",
        "11",
        "주석 참조 확인",
        None,
        None,
        None,
        0,
        "원문 확인 필요",
        [],
    )
    content = _render(
        tmp_path,
        [
            _cross_check(),
            uncertain,
            replace(_cross_check(MATCHED), check_id="matched-fs-note"),
        ],
    )

    assert 'data-result-filter="all" aria-pressed="true">전체 <strong>3</strong>' in content
    assert 'data-result-filter="matched" aria-pressed="false">일치 <strong>1</strong>' in content
    assert 'data-result-filter="attention" aria-pressed="false">확인 필요 <strong>1</strong>' in content
    assert (
        'data-result-filter="source_review" aria-pressed="false">'
        '원문 확인 필요 <strong>1</strong>'
    ) in content
    assert 'data-drawer-category="attention"' in content
    assert 'data-drawer-category="source_review"' in content
    assert 'data-drawer-category="matched"' in content
    assert "data-open-status=" not in content


def test_not_tested_result_does_not_mark_a_source_cell(tmp_path: Path):
    check = CheckResult(
        "not-tested",
        "total_check",
        NOT_TESTED,
        "note",
        "11",
        "표 합계 검증",
        None,
        None,
        None,
        1,
        "no reliable total label found",
        [CheckEvidence("유형자산", 90, "note:11/table:1/row:1/col:1", role="target")],
    )

    content = _render(tmp_path, [check])
    soup = BeautifulSoup(content, "html.parser")

    assert soup.select(".source-table .cell-check") == []
    assert soup.select(".source-nav .nav-state") == []


def test_evidence_less_check_renders_in_drawer_with_source_action(tmp_path: Path):
    check = CheckResult(
        "global-note-ref",
        "note_reference_check",
        MATCHED,
        "report",
        "",
        "전역 주석 참조 검증",
        None,
        None,
        None,
        0,
        "근거 표 없이 말 주기 참조를 확인",
        [],
    )

    content = _render(tmp_path, [check])

    assert 'data-drawer-item="0"' in content
    assert "전역 주석 참조 검증" in content
    assert "근거 표 없이 말 주기 참조를 확인" in content
    assert "확인 위치를 자동으로 찾지 못했습니다." in content


def test_report_hides_internal_metadata_and_runtime_terms(tmp_path: Path):
    content = _render(tmp_path, [_cross_check()])

    for forbidden in (
        "private-fs-note",
        "fs_note_match",
        "statement:bs/table",
        "LOCAL VERIFY",
        "PyOdide",
        "파싱 불확실",
        "스택 트레이스",
    ):
        assert forbidden not in content


def test_print_stylesheet_repeats_table_headers(tmp_path: Path):
    content = _render(tmp_path, [_cross_check()])

    assert "@media print" in content
    assert "table-header-group" in content
