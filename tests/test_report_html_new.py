"""Focused contracts for the desktop audit-workbench HTML renderer."""

from dataclasses import replace
from pathlib import Path
import re

from dart_footing_reconciler.checks import (
    CheckEvidence,
    CheckResult,
    MATCHED,
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
from dart_footing_reconciler.report_html import _tie_results, export_audit_reconciliation_html
from dart_footing_reconciler.checks_note_references import check_note_references


def _table(index: int, section_id: str, amount: str = "100") -> ReportTable:
    return ReportTable(
        index,
        [["구분", "당기"], ["합계", amount]],
        "테스트",
        SourceLocation(section_id, 0, index),
    )


def _section(section_id: str, title: str, kind: str, note_no: str, index: int) -> ReportSection:
    table = _table(index, section_id)
    return ReportSection(
        section_id,
        title,
        kind,
        note_no,
        [ReportBlock("table", "", table, table.location)],
    )


def _result(check_id: str, status: str, source: str, check_type: str = "fs_note_match") -> CheckResult:
    return CheckResult(
        check_id,
        check_type,
        status,
        "report",
        "",
        "검증 결과",
        100,
        100,
        0,
        1,
        "ok",
        [CheckEvidence("합계", 100, source)],
    )


def test_tie_results_groups_by_statement_and_note_source():
    results = [
        _result("eq1", MATCHED, "statement:bs/table:0/row:1"),
        _result("eq2", MATCHED, "statement:cf/table:1/row:1"),
        _result("n1", MATCHED, "note:12/table:2/row:1"),
    ]

    tied = _tie_results(results)

    assert len(tied["bs"]) == 1
    assert len(tied["cf"]) == 1
    assert len(tied["note:12"]) == 1


def test_export_creates_desktop_workbench_html(tmp_path: Path):
    report = FullReport(
        "test.html",
        "테스트(주)",
        [_section("statement:bs", "재무상태표", "statement", "", 0)],
        [],
    )
    output = tmp_path / "report.html"

    result_path = export_audit_reconciliation_html(report, [], output)
    content = output.read_text(encoding="utf-8")

    assert result_path == output
    assert content.startswith("<!DOCTYPE html>")
    assert 'data-report-profile="audit-workbench"' in content
    assert ".audit-workbench{display:grid;grid-template-columns:260px minmax(620px,1fr) 400px" in content
    assert "@media (max-width" not in content


def test_pdf_page_provenance_humanizes_existing_source_labels(tmp_path: Path):
    table_location = SourceLocation(
        "note:15",
        0,
        12,
        page_number=37,
        bbox=(42.0, 110.0, 553.0, 420.0),
        input_format="pdf",
    )
    table = ReportTable(
        12,
        [["구분", "금액"], ["요약 경영성과 (*1)", "100"]],
        "종속기업 요약",
        table_location,
    )
    note = ReportSection(
        "note:15",
        "종속기업",
        "note",
        "15",
        [
            ReportBlock("table", "", table, table_location),
            ReportBlock(
                "text",
                "(*1) 내부거래 제거 전 금액입니다.",
                None,
                SourceLocation(
                    "note:15",
                    1,
                    page_number=38,
                    bbox=(42.0, 430.0, 553.0, 470.0),
                    input_format="pdf",
                ),
                raw_text="(*1) 내부거래 제거 전 금액입니다.",
                text_segments=("(*1) 내부거래 제거 전 금액입니다.",),
                raw_tag="p",
                wrapper_class="nb",
            ),
        ],
    )
    report = FullReport("test.pdf", "회사", [], [note])
    check = _result("pdf-source", MATCHED, "note:15/table:12/row:1/col:1")
    output = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [check], output)
    content = output.read_text(encoding="utf-8")

    assert content.count("PDF 37쪽") >= 2
    assert "PDF 38쪽" in content
    assert "42.0" not in content
    assert "110.0" not in content
    assert "bbox" not in content
    assert "input_format" not in content
    assert "재무제표 해당 셀" not in content
    assert "좌표" not in content


def test_non_pdf_page_provenance_keeps_existing_source_labels(tmp_path: Path):
    location = SourceLocation(
        "note:15",
        0,
        12,
        page_number=37,
        input_format="html",
    )
    table = ReportTable(
        12,
        [["구분", "금액"], ["합계", "100"]],
        "기존 HTML 주석",
        location,
    )
    note = ReportSection(
        "note:15",
        "종속기업",
        "note",
        "15",
        [ReportBlock("table", "", table, location)],
    )
    report = FullReport("test.html", "회사", [], [note])
    output = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [], output)
    content = output.read_text(encoding="utf-8")

    assert "기존 HTML 주석" in content
    assert "PDF 37쪽" not in content
    assert "source-page-label" not in content


def test_duplicate_statement_and_note_panels_keep_unique_ids(tmp_path: Path):
    report = FullReport(
        "test.html",
        "회사",
        [
            ReportSection(
                "statement:bs",
                "재무상태표",
                "statement",
                "",
                [ReportBlock("table", "", _table(0, "statement:bs"), SourceLocation("statement:bs", 0, 0))],
                "consolidated",
            ),
            ReportSection(
                "statement:bs",
                "재무상태표",
                "statement",
                "",
                [ReportBlock("table", "", _table(1, "statement:bs"), SourceLocation("statement:bs", 0, 1))],
                "separate",
            ),
        ],
        [
            _section("note:13", "연결 유형자산", "note", "13", 2),
            _section("note:13", "별도 유형자산", "note", "13", 3),
        ],
    )
    output = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [], output)
    content = output.read_text(encoding="utf-8")
    panel_ids = re.findall(r'<section class="source-panel" id="([^"]+)"', content)

    assert len(panel_ids) == len(set(panel_ids))
    assert len(panel_ids) == 4


def test_duplicate_note_nav_does_not_repeat_scope_already_in_title(tmp_path: Path):
    consolidated = replace(
        _section("note:13", "유형자산 (연결)", "note", "13", 13),
        scope="consolidated",
    )
    separate = replace(
        _section("note:13", "유형자산", "note", "13", 14),
        scope="separate",
    )
    report = FullReport("test.html", "회사", [], [consolidated, separate])
    output = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [], output)
    content = output.read_text(encoding="utf-8")

    assert "주석 13 (연결) 유형자산" in content
    assert "주석 13 (연결) 유형자산 (연결)" not in content


def test_mixed_scope_report_renders_one_scope_switch_for_all_workbench_regions(tmp_path: Path):
    consolidated_statement = replace(
        _section("statement:bs", "재무상태표", "statement", "", 0),
        scope="consolidated",
    )
    separate_statement = replace(
        _section("statement:bs", "재무상태표", "statement", "", 1),
        scope="separate",
    )
    consolidated_note = replace(
        _section("note:13", "유형자산", "note", "13", 2),
        scope="consolidated",
    )
    separate_note = replace(
        _section("note:13", "유형자산", "note", "13", 3),
        scope="separate",
    )
    report = FullReport(
        "test.html",
        "회사",
        [consolidated_statement, separate_statement],
        [consolidated_note, separate_note],
    )
    checks = [
        replace(
            _result("consolidated", MATCHED, "statement:bs/table:0/row:1/col:1"),
            consolidation_basis="consolidated",
        ),
        replace(
            _result("separate", UNEXPLAINED_GAP, "statement:bs/table:1/row:1/col:1"),
            consolidation_basis="separate",
        ),
    ]
    output = tmp_path / "report.html"

    export_audit_reconciliation_html(report, checks, output)
    content = output.read_text(encoding="utf-8")

    assert 'class="report-scope-switch"' in content
    assert 'data-report-scope="consolidated" aria-pressed="true"' in content
    assert 'data-report-scope="separate" aria-pressed="false"' in content
    assert content.count('data-scope-view="consolidated"') >= 3
    assert content.count('data-scope-view="separate"') >= 3
    assert 'data-scope-count="consolidated"' in content
    assert 'data-scope-count="separate"' in content
    assert "function activateReportScope(scope, options)" in content


def test_single_scope_report_hides_scope_switch(tmp_path: Path):
    report = FullReport(
        "test.html",
        "회사",
        [replace(_section("statement:bs", "재무상태표", "statement", "", 0), scope="separate")],
        [],
    )
    output = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [], output)
    content = output.read_text(encoding="utf-8")

    assert 'class="report-scope-switch"' not in content
    assert 'data-active-report-scope="separate"' in content


def test_workbench_navigation_resets_stale_context_and_exposes_skip_link(tmp_path: Path):
    report = FullReport(
        "test.html",
        "회사",
        [
            replace(
                _section("statement:bs", "재무상태표", "statement", "", 0),
                scope="consolidated",
            ),
            replace(
                _section("statement:cf", "현금흐름표", "statement", "", 1),
                scope="separate",
            ),
        ],
        [],
    )
    output = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [], output)
    content = output.read_text(encoding="utf-8")

    assert '<a class="skip-link" href="#main-content">본문으로 건너뛰기</a>' in content
    assert '<main class="source-stage" id="main-content" tabindex="-1">' in content
    assert 'id="workbench-status" class="sr-only" aria-live="polite"' in content
    assert '<h2 tabindex="-1">재무상태표' in content
    assert "function activatePanel(panelId, options)" in content
    assert "stage.scrollTop = 0;" in content
    assert "if (!settings.preserveDrawer) {" in content
    assert "activeDrawerCategory = 'all';" in content
    assert "syncResultFilterButtons();" in content
    assert "closeDrawer(false);" in content
    assert "if (settings.focusHeading && heading) heading.focus();" in content
    assert (
        "activatePanel(panelId, {preserveDrawer:true, resetScroll:false, "
        "focusHeading:false});"
    ) in content


def test_header_counts_gap_and_uncertain_without_verdict_dashboard(tmp_path: Path):
    report = FullReport(
        "test.html",
        "회사",
        [_section("statement:bs", "재무상태표", "statement", "", 0)],
        [],
    )
    checks = [
        _result("gap", UNEXPLAINED_GAP, "statement:bs/table:0/row:1/col:1"),
        _result("unc", PARSE_UNCERTAIN, "statement:bs/table:0/row:1/col:1"),
    ]
    output = tmp_path / "report.html"

    export_audit_reconciliation_html(report, checks, output)
    content = output.read_text(encoding="utf-8")

    assert "확인 필요 <strong>1</strong>" in content
    assert "원문 확인 필요 <strong>1</strong>" in content
    assert 'data-result-filter="attention"' in content
    assert 'data-result-filter="source_review"' in content
    assert "verdict-banner" not in content


def test_drawer_linked_statement_cell_is_visibly_marked_and_results_are_navigable(tmp_path: Path):
    report = FullReport(
        "test.html",
        "회사",
        [_section("statement:bs", "재무상태표", "statement", "", 0)],
        [],
    )
    checks = [
        _result("first", MATCHED, "statement:bs/table:0/row:1/col:1"),
        _result("second", UNEXPLAINED_GAP, "statement:bs/table:0/row:1/col:1"),
    ]
    output = tmp_path / "report.html"

    export_audit_reconciliation_html(report, checks, output)
    content = output.read_text(encoding="utf-8")

    assert 'class="source-cell cell-reconciliation"' in content
    assert 'data-drawer-status="matched"' in content
    assert 'data-drawer-status="unexplained_gap"' in content
    assert 'data-drawer-prev' in content
    assert 'data-drawer-next' in content
    assert 'data-drawer-position' in content


def test_statement_account_row_opens_its_linked_validation_results(tmp_path: Path):
    report = FullReport(
        "test.html",
        "회사",
        [_section("statement:bs", "재무상태표", "statement", "", 0)],
        [],
    )
    checks = [_result("row-result", MATCHED, "statement:bs/table:0/row:1/col:1")]
    output = tmp_path / "report.html"

    export_audit_reconciliation_html(report, checks, output)
    content = output.read_text(encoding="utf-8")

    assert re.search(
        r'<tr class="[^"]*source-row-reconciliation[^"]*" data-row="t0r1"',
        content,
    )
    assert 'aria-label="합계 행 검증 결과 1건"' in content
    assert '<span class="row-result-count">검증 완료</span>' in content


def test_multiple_statement_results_use_semantic_row_count_without_cell_duplicate(
    tmp_path: Path,
):
    report = FullReport(
        "test.html",
        "회사",
        [_section("statement:bs", "재무상태표", "statement", "", 0)],
        [],
    )
    checks = [
        _result("row-result-1", MATCHED, "statement:bs/table:0/row:1/col:1"),
        _result("row-result-2", MATCHED, "statement:bs/table:0/row:1/col:1"),
    ]
    output = tmp_path / "report.html"

    export_audit_reconciliation_html(report, checks, output)
    content = output.read_text(encoding="utf-8")

    assert '<span class="row-result-count">검증 완료 · 2건</span>' in content
    assert "대사 2건" not in content
    assert 'class="cell-reconciliation-count" aria-hidden="true">2</span>' not in content


def test_multiple_note_results_name_reconciliation_count(tmp_path: Path):
    report = FullReport(
        "test.html",
        "회사",
        [],
        [_section("note:13", "유형자산", "note", "13", 13)],
    )
    checks = [
        _result("note-result-1", MATCHED, "note:13/table:13/row:1/col:1"),
        _result("note-result-2", MATCHED, "note:13/table:13/row:1/col:1"),
    ]
    output = tmp_path / "report.html"

    export_audit_reconciliation_html(report, checks, output)
    content = output.read_text(encoding="utf-8")

    assert (
        '<span class="cell-reconciliation-count" aria-label="대사 2건">'
        "대사 2건</span>"
    ) in content


def test_multiple_total_checks_name_validation_count(tmp_path: Path):
    report = FullReport(
        "test.html",
        "회사",
        [],
        [_section("note:3-1", "금융상품", "note", "3-1", 7)],
    )
    checks = [
        CheckResult(
            f"layout:row-total:{index}",
            "note_layout_formula_check",
            MATCHED,
            "note",
            "3-1",
            "행 합계 검증",
            100,
            100,
            0,
            1,
            "matched",
            [
                CheckEvidence(
                    "합계",
                    100,
                    "note:3-1/table:7/row:1/col:1",
                    role="target",
                )
            ],
        )
        for index in range(2)
    ]
    output = tmp_path / "report.html"

    export_audit_reconciliation_html(report, checks, output)
    content = output.read_text(encoding="utf-8")

    assert (
        '<span class="cell-check-count" aria-label="합계 검증 2건">'
        "합계 검증 2건</span>"
    ) in content


def test_note_row_does_not_become_a_whole_row_drawer_trigger(tmp_path: Path):
    report = FullReport(
        "test.html",
        "회사",
        [],
        [_section("note:13", "유형자산", "note", "13", 0)],
    )
    checks = [_result("note-result", MATCHED, "note:13/table:0/row:1/col:1")]
    output = tmp_path / "report.html"

    export_audit_reconciliation_html(report, checks, output)
    content = output.read_text(encoding="utf-8")

    assert 'class="source-row source-row-reconciliation"' not in content
    assert '<span class="row-result-count">' not in content


def test_last_column_row_total_uses_visible_inset_border_and_audit_label(tmp_path: Path):
    report = FullReport(
        "test.html",
        "회사",
        [],
        [_section("note:3-1", "금융상품", "note", "3-1", 7)],
    )
    check = CheckResult(
        "layout:row-total",
        "note_layout_formula_check",
        MATCHED,
        "note",
        "3-1",
        "행 합계 검증",
        100,
        100,
        0,
        1,
        "matched",
        [CheckEvidence("합계", 100, "note:3-1/table:7/row:1/col:1", role="target")],
    )
    output = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [check], output)
    content = output.read_text(encoding="utf-8")

    assert 'class="source-cell cell-check cell-matched"' in content
    assert 'aria-label="행 합계 검증 일치"' in content
    assert 'data-validation-label="합계 검증 일치"' in content
    assert '<table class="source-table source-table-sticky-total">' in content


def test_explicit_total_row_distinguishes_missing_validation_from_checked_cell(
    tmp_path: Path,
):
    table = ReportTable(
        0,
        [["계정", "당기"], ["현금", "40"], ["자산총계", "40"]],
        "재무상태표",
        SourceLocation("statement:bs", 0, 0),
    )
    statement = ReportSection(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        [ReportBlock("table", "", table, table.location)],
    )
    report = FullReport("test.html", "회사", [statement], [])
    output = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [], output)
    content = output.read_text(encoding="utf-8")

    assert 'class="source-row source-row-total-unchecked"' in content
    assert '<span class="total-result-missing">합계 검증 결과 없음</span>' in content
    assert 'data-validation-label="합계 검증 일치"' not in content


def test_total_row_names_note_reconciliation_separately_from_missing_footing(
    tmp_path: Path,
):
    table = ReportTable(
        0,
        [["계정", "당기"], ["자산총계", "100"]],
        "재무상태표",
        SourceLocation("statement:bs", 0, 0),
    )
    statement = ReportSection(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        [ReportBlock("table", "", table, table.location)],
    )
    note = _section("note:10", "자산", "note", "10", 10)
    report = FullReport("test.html", "회사", [statement], [note])
    check = CheckResult(
        "statement-note-row",
        "statement_note_row_reconciliation",
        MATCHED,
        "report",
        "10",
        "자산총계 주석 금액 대사",
        100,
        100,
        0,
        1,
        "일치",
        [
            CheckEvidence(
                "자산총계",
                100,
                "statement:bs/table:0/row:1/col:1",
                role="statement_amount",
            ),
            CheckEvidence(
                "본문 표시 주석 10",
                None,
                "statement:bs/table:0/row:1/col:0",
                role="displayed_note_reference",
            ),
            CheckEvidence(
                "주석 10 자산총계",
                100,
                "note:10/table:10/row:1/col:1",
                role="note_amount",
            ),
        ],
    )
    output = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [check], output)
    content = output.read_text(encoding="utf-8")

    assert '<span class="row-result-count">주석 대사 완료</span>' in content
    assert '<span class="total-result-missing">합계 검증 결과 없음</span>' in content
    assert "검증 완료 검증 결과 없음" not in content


def test_total_row_names_statement_equation_separately_from_missing_footing(
    tmp_path: Path,
):
    report = FullReport(
        "test.html",
        "회사",
        [_section("statement:bs", "재무상태표", "statement", "", 0)],
        [],
    )
    check = _result(
        "statement-equation",
        MATCHED,
        "statement:bs/table:0/row:1/col:1",
        check_type="statement_bs_equation",
    )
    output = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [check], output)
    content = output.read_text(encoding="utf-8")

    assert '<span class="row-result-count">재무제표 등식 일치</span>' in content
    assert '<span class="total-result-missing">합계 검증 결과 없음</span>' in content
    assert "검증 완료 합계 검증 결과 없음" not in content


def test_wide_source_table_exposes_scroll_cue_and_sticky_description_column(
    tmp_path: Path,
):
    table = ReportTable(
        7,
        [
            ["구분", "당기 취득금액", "당기 처분금액", "기말 장부금액 합계"],
            ["토지", "1", "2", "3"],
        ],
        "유형자산",
        SourceLocation("note:7", 0, 7),
    )
    note = ReportSection(
        "note:7",
        "유형자산",
        "note",
        "7",
        [ReportBlock("table", "", table, table.location)],
    )
    output = tmp_path / "report.html"

    export_audit_reconciliation_html(
        FullReport("test.html", "회사", [], [note]),
        [],
        output,
    )
    content = output.read_text(encoding="utf-8")

    assert 'class="source-table-scroll" data-horizontal-scroll' in content
    assert (
        '<span class="source-table-scroll-hint">'
        "가로로 이동하여 전체 금액 확인</span>"
    ) in content
    assert (
        ".source-table th{background:var(--surface-2);font-size:11px;"
        "font-weight:800;color:var(--muted);text-align:center;white-space:normal;"
        "word-break:keep-all;min-width:96px;}"
    ) in content
    assert (
        ".source-table th:first-child,.source-table td:first-child{"
        "position:sticky;left:0;"
    ) in content
    assert (
        ".audit-workbench .source-table{width:max-content;min-width:100%;}"
        in content
    )
    assert ".source-table td:not(:first-child){min-width:118px;}" in content
    assert "function updateHorizontalScrollCue(container)" in content
    assert ".cell-matched{box-shadow:inset 0 0 0 3px var(--ok);}" in content
    assert ".cell-matched{outline:3px solid var(--ok);}" not in content


def test_cross_table_validation_groups_are_visible_on_every_evidence_section(tmp_path: Path):
    statement = _section("statement:bs", "재무상태표", "statement", "", 0)
    note_13 = _section("note:13", "유형자산", "note", "13", 1)
    note_25 = _section("note:25", "비용", "note", "25", 2)
    report = FullReport("test.html", "회사", [statement], [note_13, note_25])
    fs_note = CheckResult(
        "fs-note",
        "fs_note_match",
        MATCHED,
        "report",
        "13",
        "재무제표-주석 대사",
        100,
        100,
        0,
        1,
        "matched",
        [
            CheckEvidence("재무제표", 100, "statement:bs/table:0/row:1/col:1"),
            CheckEvidence("주석", 100, "note:13/table:1/row:1/col:1"),
        ],
    )
    note_note = replace(
        fs_note,
        check_id="note-note",
        check_type="note_note_match",
        note_no="25",
        title="주석 간 대사",
        evidence=[
            CheckEvidence("주석 13", 100, "note:13/table:1/row:1/col:1"),
            CheckEvidence("주석 25", 100, "note:25/table:2/row:1/col:1"),
        ],
    )
    output = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [fs_note, note_note], output)
    content = output.read_text(encoding="utf-8")

    assert content.count('data-validation-group="재무제표-주석 대사"') == 2
    assert content.count('data-validation-group="주석끼리 대사"') == 2
    assert content.count('data-open-drawer="0"') >= 2
    assert 'data-drawer-indexes="0,1"' in content
    assert 'data-open-drawer="1"' in content


def test_cashflow_row_and_drawer_name_the_cashflow_note_validation(tmp_path: Path):
    cashflow = _section("statement:cf", "현금흐름표", "statement", "", 0)
    note = _section("note:11", "유형자산", "note", "11", 1)
    report = FullReport("test.html", "회사", [cashflow], [note])
    check = CheckResult(
        "cashflow",
        "cashflow_reconciliation",
        MATCHED,
        "report",
        "11",
        "유형자산 취득 대사",
        100,
        100,
        0,
        1,
        "matched",
        [
            CheckEvidence("현금흐름표", -100, "statement:cf/table:0/row:1/col:1"),
            CheckEvidence("주석", 100, "note:11/table:1/row:1/col:1"),
        ],
    )
    output = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [check], output)
    content = output.read_text(encoding="utf-8")

    assert '<span class="row-result-count">주석과 일치</span>' in content
    assert '<div class="drawer-group">현금흐름표-주석 대사</div>' in content
    assert content.count('data-validation-group="현금흐름표-주석 대사"') == 2
    assert '<h3>유형자산 취득</h3>' in content
    assert '<dt>현금흐름표 금액</dt>' in content
    assert '<dt>주석 11 변동금액</dt>' in content
    assert '<h4>주석 위치</h4>' in content
    assert '<h4>원문 위치</h4>' not in content
    assert ">현금흐름표<" not in content.split('<h4>주석 위치</h4>', 1)[1]


def test_cashflow_drawer_distinguishes_same_named_locations_in_multiple_tables(
    tmp_path: Path,
):
    cashflow = _section("statement:cf", "현금흐름표", "statement", "", 0)
    note_tables = [
        ReportTable(
            index,
            [["구분", "합계"], ["취득/증가", amount]],
            "사용권자산",
            SourceLocation("note:12-1", 0, index),
        )
        for index, amount in ((1, "100"), (2, "90"))
    ]
    note = ReportSection(
        "note:12-1",
        "사용권자산",
        "note",
        "12-1",
        [
            ReportBlock("table", "", table, table.location)
            for table in note_tables
        ],
    )
    report = FullReport("test.html", "회사", [cashflow], [note])
    check = CheckResult(
        "cashflow",
        "cashflow_reconciliation",
        MATCHED,
        "report",
        "12-1",
        "사용권자산 취득 대사",
        190,
        190,
        0,
        1,
        "matched",
        [
            CheckEvidence("현금흐름표", 190, "statement:cf/table:0/row:1/col:1"),
            CheckEvidence("주석", 100, "note:12-1/table:1/row:1/col:1"),
            CheckEvidence("주석", 90, "note:12-1/table:2/row:1/col:1"),
        ],
    )
    output = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [check], output)
    content = output.read_text(encoding="utf-8")

    assert "(첫 번째 표)" in content
    assert "(두 번째 표)" in content


def test_statement_note_drawer_explains_comparison_note_roles_and_actions(tmp_path: Path):
    statement = _section("statement:bs", "재무상태표", "statement", "", 0)
    note_10 = _section("note:10", "유형자산", "note", "10", 10)
    note_12 = _section("note:12", "담보", "note", "12", 12)
    report = FullReport("test.html", "회사", [statement], [note_10, note_12])
    check = CheckResult(
        "statement-note-row",
        "statement_note_row_reconciliation",
        PARSE_UNCERTAIN,
        "report",
        "10",
        "유형자산 주석 금액 대사",
        100,
        100,
        0,
        1,
        "재무제표 옆에 표시되지 않은 관련 주석번호가 확인됨",
        [
            CheckEvidence(
                "유형자산",
                100,
                "statement:bs/table:0/row:1/col:1",
                role="statement_amount",
            ),
            CheckEvidence(
                "본문 표시 주석 10",
                None,
                "statement:bs/table:0/row:1/col:0",
                role="displayed_note_reference",
            ),
            CheckEvidence(
                "주석 10 기말 장부금액",
                100,
                "note:10/table:10/row:1/col:1",
                role="note_amount",
            ),
            CheckEvidence(
                "주석 10 기말 장부금액",
                100,
                "note:10/table:10/row:1/col:1",
                role="note_amount",
            ),
            CheckEvidence(
                "주석 12 유형자산",
                100,
                "note:12/table:12/row:1/col:1",
                role="missing_note_reference",
            ),
        ],
        parse_uncertain_reason="MISSING_DISPLAYED_NOTE_REFERENCE",
        consolidation_basis="consolidated",
        report_period="current",
        account_key="property_plant_equipment",
    )
    output = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [check], output)
    content = output.read_text(encoding="utf-8")

    assert "주석번호 완전성" in content
    assert "표시됨" in content
    assert "금액 대사" in content
    assert "누락" in content
    assert "주석 10" in content
    assert "주석 12" in content
    assert "재무제표 해당 셀" not in content
    assert "<h4>주석 위치</h4>" in content
    assert "실재성 · 주석 10" in content
    assert content.count("실재성 · 주석 10") == 1
    assert "완전성 누락 · 주석 12" in content
    assert 'class="drawer-source drawer-note-location-existence"' in content
    assert 'class="drawer-source drawer-note-location-completeness"' in content
    assert "무엇을 대사했나요" not in content
    assert "사용한 주석" not in content
    assert "검증한 내용" not in content
    assert "원문 위치" not in content
    assert "property_plant_equipment" not in content
    assert "금액 일치 · 주석번호 확인 필요" in content
    assert "<dt>주석 10 금액</dt>" in content
    assert "<h4>후속작업</h4>" in content
    row = re.search(
        r'<tr class="[^"]*source-row-reconciliation[^"]*" data-row="t0r1"(?P<attrs>[^>]*)>',
        content,
    )
    assert row is not None
    assert 'data-open-drawer="0"' in row.group("attrs")


def test_statement_note_drawer_names_unresolved_amount_instead_of_dash(tmp_path: Path):
    report = FullReport(
        "test.html",
        "회사",
        [_section("statement:bs", "재무상태표", "statement", "", 0)],
        [_section("note:10", "유형자산", "note", "10", 10)],
    )
    check = CheckResult(
        "statement-note-row",
        "statement_note_row_reconciliation",
        PARSE_UNCERTAIN,
        "report",
        "10",
        "유형자산 주석 금액 대사",
        100,
        None,
        None,
        1,
        "표시된 주석에서 직접 비교할 계정 금액을 찾지 못함",
        [
            CheckEvidence(
                "유형자산",
                100,
                "statement:bs/table:0/row:1/col:1",
                role="statement_amount",
            ),
            CheckEvidence(
                "본문 표시 주석 10",
                None,
                "statement:bs/table:0/row:1/col:0",
                role="displayed_note_reference",
            ),
        ],
        parse_uncertain_reason="LABEL_NOT_FOUND",
    )
    output = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [check], output)
    content = output.read_text(encoding="utf-8")

    assert "주석 금액 확인 필요" in content
    assert "지정된 주석에서 해당 계정의 합계 또는 기말금액을 확인하세요" in content


def test_statement_note_drawer_separates_amount_and_reference_completion(tmp_path: Path):
    report = FullReport(
        "test.html",
        "회사",
        [_section("statement:bs", "재무상태표", "statement", "", 0)],
        [_section("note:10", "유형자산", "note", "10", 10)],
    )
    check = CheckResult(
        "statement-note-row",
        "statement_note_row_reconciliation",
        MATCHED,
        "report",
        "10",
        "유형자산 주석 금액 대사",
        100,
        100,
        0,
        1,
        "일치",
        [
            CheckEvidence(
                "유형자산",
                100,
                "statement:bs/table:0/row:1/col:1",
                role="statement_amount",
            ),
            CheckEvidence(
                "본문 표시 주석 10",
                None,
                "statement:bs/table:0/row:1/col:0",
                role="displayed_note_reference",
            ),
            CheckEvidence(
                "주석 10 기말 장부금액",
                100,
                "note:10/table:10/row:1/col:1",
                role="note_amount",
            ),
        ],
    )
    output = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [check], output)
    content = output.read_text(encoding="utf-8")

    assert "금액 일치 · 주석번호 확인 완료" in content
    assert "추가로 확인할 사항이 없습니다." in content


def test_table_narrative_renders_source_card_and_cross_note_jumps(tmp_path: Path):
    source_table = ReportTable(
        12,
        [["구분", "금액"], ["요약 경영성과 (*1)", "100"]],
        "종속기업 요약",
        SourceLocation("note:12", 0, 12),
    )
    source_note = ReportSection(
        "note:12",
        "종속기업",
        "note",
        "12",
        [
            ReportBlock("table", "", source_table, source_table.location),
            ReportBlock(
                "text",
                "(*1) 내부거래 제거 전 금액이며 주석 46 참조.",
                None,
                SourceLocation("note:12", 1),
                raw_text="(*1) 내부거래 제거 전 금액이며 주석 46 참조.",
                text_segments=("(*1) 내부거래 제거 전 금액이며 주석 46 참조.",),
                raw_tag="p",
                wrapper_class="nb",
            ),
        ],
        scope="consolidated",
    )
    target_table = ReportTable(
        46,
        [["구분", "금액"], ["관련 내용", "100"]],
        "관련 주석",
        SourceLocation("note:46", 0, 46),
    )
    target_note = ReportSection(
        "note:46",
        "사업결합",
        "note",
        "46",
        [ReportBlock("table", "", target_table, target_table.location)],
        scope="consolidated",
    )
    report = FullReport("test.html", "회사", [], [source_note, target_note])
    output = tmp_path / "report.html"

    export_audit_reconciliation_html(report, check_note_references(report), output)
    content = output.read_text(encoding="utf-8")

    assert 'class="source-narrative"' in content
    assert (
        'data-source-block="note:12@consolidated/block:1/segment:0"'
        in content
    )
    assert '<span class="source-narrative-marker">(*1)</span>' in content
    assert 'data-jump-block="note:12@consolidated/block:1/segment:0"' in content
    assert 'data-jump-block="note:46@consolidated/block:0"' in content
    assert ">참조 주석 46<" in content
    assert "<h4>참조 문장</h4>" in content
    assert "내부거래 제거 전 금액이며 주석 46 참조." in content
    assert "<h4>주석 위치</h4>" in content
    assert "기준 금액" not in content
    assert "비교 금액" not in content
    assert "원문 위치" not in content
    assert "추가 조치가 필요하지 않습니다." not in content


def test_broken_narrative_note_reference_drawer_states_user_action(tmp_path: Path):
    note = ReportSection(
        "note:19",
        "차입금",
        "note",
        "19",
        [
            ReportBlock(
                "text",
                "상기 차입금은 유형자산을 담보로 제공합니다(주석 34 참조).",
                None,
                SourceLocation("note:19", 0),
                text_segments=(
                    "상기 차입금은 유형자산을 담보로 제공합니다(주석 34 참조).",
                ),
            )
        ],
        scope="consolidated",
    )
    report = FullReport("test.html", "회사", [], [note])
    output = tmp_path / "report.html"

    export_audit_reconciliation_html(report, check_note_references(report), output)
    content = output.read_text(encoding="utf-8")

    assert "주석 34 참조" in content
    assert "<h4>후속작업</h4>" in content
    assert "참조된 주석 34가 보고서에 존재하는지 확인" in content
    assert "번호가 잘못되었다면 말 주기 문장을 수정" in content


def test_opening_drawer_item_synchronizes_filter_to_result_category(tmp_path: Path):
    report = FullReport(
        "test.html",
        "회사",
        [_section("statement:bs", "재무상태표", "statement", "", 0)],
        [],
    )
    checks = [
        _result("matched", MATCHED, "statement:bs/table:0/row:1/col:1"),
        _result("gap", UNEXPLAINED_GAP, "statement:bs/table:0/row:1/col:1"),
    ]
    output = tmp_path / "report.html"

    export_audit_reconciliation_html(report, checks, output)
    content = output.read_text(encoding="utf-8")
    open_drawer = re.search(
        r"function openDrawer\(index, trigger, keepCategory\) \{(?P<body>.*?)\n  \}\n  function drawerItems",
        content,
        re.DOTALL,
    )

    assert open_drawer is not None
    assert "if (!keepCategory) syncDrawerCategory(target);" in open_drawer.group("body")
    assert "function syncDrawerCategory(target)" in content
    assert "button.getAttribute('data-result-filter') === activeDrawerCategory" in content


def test_drawer_navigation_uses_active_scope_and_result_filter(tmp_path: Path):
    report = FullReport(
        "test.html",
        "회사",
        [_section("statement:bs", "재무상태표", "statement", "", 0)],
        [],
    )
    checks = [
        _result("matched", MATCHED, "statement:bs/table:0/row:1/col:1"),
        _result("gap", UNEXPLAINED_GAP, "statement:bs/table:0/row:1/col:1"),
        _result("uncertain", PARSE_UNCERTAIN, "statement:bs/table:0/row:1/col:1"),
    ]
    output = tmp_path / "report.html"

    export_audit_reconciliation_html(report, checks, output)
    content = output.read_text(encoding="utf-8")

    assert "var activeDrawerCategory = 'all';" in content
    assert "function setDrawerCategory(category, trigger)" in content
    assert "if (activeDrawerCategory === 'all') return true;" in content
    assert (
        "item.getAttribute('data-drawer-category') === activeDrawerCategory"
        in content
    )
    assert "var items = drawerItems();" in content
    assert "document.querySelectorAll('[data-result-filter]')" in content


def test_parse_uncertain_result_uses_drawer_action_without_reason_code(tmp_path: Path):
    report = FullReport(
        "test.html",
        "회사",
        [_section("statement:bs", "재무상태표", "statement", "", 0)],
        [],
    )
    check = CheckResult(
        "uncertain",
        "note_reference_check",
        PARSE_UNCERTAIN,
        "report",
        "",
        "자동 해석 확인 항목",
        None,
        None,
        None,
        1,
        "multiple candidate note amounts found",
        [],
        parse_uncertain_reason="AMBIGUOUS_MULTIPLE",
    )
    output = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [check], output)
    content = output.read_text(encoding="utf-8")

    assert "비교할 후보가 여러 개여서 자동으로 확정하지 못했습니다." in content
    assert "원문 표의 머리글과 병합 구조를 확인해 비교 대상을 확정하세요." in content
    assert "AMBIGUOUS_MULTIPLE" not in content


def test_check_id_with_html_and_javascript_characters_is_not_rendered(tmp_path: Path):
    report = FullReport(
        "test.html",
        "회사",
        [],
        [_section("note:12", "주석 12", "note", "12", 0)],
    )
    bad_id = 'note_12\'"foo><img src=q onerror=alert(1)>'
    check = _result(bad_id, MATCHED, "note:12/table:0/row:1/col:1")
    output = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [check], output)
    content = output.read_text(encoding="utf-8")

    assert bad_id not in content
    assert "onerror=alert" not in content


def test_section_key_normalizes_statement_ids():
    from dart_footing_reconciler.report_html import _section_key

    assert _section_key(_result("a", MATCHED, "statement:재무상태표/table:0/row:1")) == "bs"
    assert _section_key(_result("b", MATCHED, "statement:손익계산서/table:1/row:1")) == "is"
    assert _section_key(_result("c", MATCHED, "statement:bs/table:0/row:1")) == "bs"
