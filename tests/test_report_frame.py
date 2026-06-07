from html import escape

from dart_footing_reconciler.checks import CheckEvidence, CheckResult
from dart_footing_reconciler.document import FullReport, ReportBlock, ReportSection, ReportTable, SourceLocation
from dart_footing_reconciler.report_frame import (
    CANONICAL_STATEMENT_ORDER,
    build_report_frame,
)
from dart_footing_reconciler.report_html import render_audit_reconciliation_html


def _section(section_id, title, kind, note_no, table):
    return ReportSection(
        section_id,
        title,
        kind,
        note_no,
        [ReportBlock("table", "", table, table.location)],
    )


def _table(section_id: str, index: int, heading: str) -> ReportTable:
    return ReportTable(
        index,
        [["구분", "당기"], ["유형자산", "100"]],
        heading,
        SourceLocation(section_id, 0, index),
    )


def test_report_frame_orders_statement_sections_by_report_form():
    statements = [
        _section("statement:cfs", "현금흐름표", "statement", "", _table("statement:cfs", 0, "현금흐름표")),
        _section("statement:bs", "재무상태표", "statement", "", _table("statement:bs", 0, "재무상태표")),
        _section("statement:sce", "자본변동표", "statement", "", _table("statement:sce", 0, "자본변동표")),
        _section("statement:pl", "손익계산서", "statement", "", _table("statement:pl", 0, "손익계산서")),
    ]
    frame = build_report_frame(FullReport("sample.html", "Sample Co", statements, []), [])

    assert [section.kind for section in frame.statement_sections] == list(CANONICAL_STATEMENT_ORDER)
    assert [section.title for section in frame.statement_sections] == ["재무상태표", "손익계산서", "자본변동표", "현금흐름표"]


def test_report_frame_maps_checks_to_statement_and_note_tables_from_evidence_sources():
    bs_table = _table("statement:bs", 0, "재무상태표")
    note_table = _table("note:11", 0, "유형자산")
    report = FullReport(
        "sample.html",
        "Sample Co",
        [_section("statement:bs", "재무상태표", "statement", "", bs_table)],
        [_section("note:11", "유형자산", "note", "11", note_table)],
    )
    check = CheckResult(
        "bs-note",
        "primary_balance_reconciliation",
        "matched",
        "report",
        "11",
        "property_plant_equipment.balance",
        100,
        100,
        0,
        0,
        "financial statement line agrees to note ending balance",
        [
            CheckEvidence("재무상태표 유형자산", 100, "statement:bs/table:0/row:1/col:1"),
            CheckEvidence("주석 11 유형자산", 100, "note:11/table:0/row:1/col:1"),
        ],
    )

    frame = build_report_frame(report, [check])

    statement_table = frame.statement_sections[0].tables[0]
    note_frame = frame.notes[0].tables[0]
    assert statement_table.check_groups["재무제표-주석 대사"] == (check,)
    assert note_frame.check_groups["재무제표-주석 대사"] == (check,)


def test_report_frame_marks_prior_reconciliation_not_performed_without_prior_checks():
    frame = build_report_frame(FullReport("sample.html", "Sample Co", [], []), [])

    assert frame.prior_reconciliation.status == "not_performed"
    assert frame.prior_reconciliation.message == "전기대사 미수행: prior-html 미제공"


def test_report_frame_keeps_text_only_notes_for_note_workspace():
    note = ReportSection(
        "note:1",
        "일반사항",
        "note",
        "1",
        [ReportBlock("text", "회사의 일반사항입니다.", None, SourceLocation("note:1", 0))],
    )

    frame = build_report_frame(FullReport("sample.html", "Sample Co", [], [note]), [])

    assert len(frame.notes) == 1
    assert frame.notes[0].note_no == "1"
    assert frame.notes[0].tables == ()


def test_note_panel_renders_fs_note_statement_preview_and_group():
    bs_table = ReportTable(
        0,
        [["구분", "당기"], ["유형자산", "1,000"]],
        "재무상태표",
        SourceLocation("statement:bs", 0, 0),
    )
    note_table = ReportTable(
        1,
        [["구분", "당기"], ["기말 장부금액", "1,000"]],
        "11. 유형자산",
        SourceLocation("note:11", 0, 1),
    )
    report = FullReport(
        "sample.html",
        "Sample Co",
        [_section("statement:bs", "재무상태표", "statement", "", bs_table)],
        [_section("note:11", "유형자산", "note", "11", note_table)],
    )
    check = CheckResult(
        "fs-note",
        "fs_note_match",
        "matched",
        "report",
        "11",
        "유형자산 FS to note match",
        1_000,
        1_000,
        0,
        0,
        "재무제표 금액과 주석 금액이 일치",
        [
            CheckEvidence("재무상태표 유형자산", 1_000, "statement:bs/table:0/row:1/col:1"),
            CheckEvidence("주석 11 기말 장부금액", 1_000, "note:11/table:1/row:1/col:1"),
        ],
    )

    html_without_check = render_audit_reconciliation_html(report, [])
    html = render_audit_reconciliation_html(report, [check])
    note_panel = html[html.index('id="note-panel-note-11"') :]

    assert "재무제표 원문 근거" in note_panel
    assert "재무제표-주석 대사" in note_panel
    assert html.count("연결된 자동 검증 결과가 없습니다") < html_without_check.count("연결된 자동 검증 결과가 없습니다")


def test_note_panel_compacts_empty_comparison_axes_for_single_fs_note_check():
    bs_table = ReportTable(
        0,
        [["구분", "당기"], ["유형자산", "1,000"]],
        "재무상태표",
        SourceLocation("statement:bs", 0, 0),
    )
    note_table = ReportTable(
        1,
        [["구분", "당기"], ["기말 장부금액", "1,000"]],
        "11. 유형자산",
        SourceLocation("note:11", 0, 1),
    )
    report = FullReport(
        "sample.html",
        "Sample Co",
        [_section("statement:bs", "재무상태표", "statement", "", bs_table)],
        [_section("note:11", "유형자산", "note", "11", note_table)],
    )
    check = CheckResult(
        "fs-note",
        "fs_note_match",
        "matched",
        "report",
        "11",
        "유형자산 FS to note match",
        1_000,
        1_000,
        0,
        0,
        "재무제표 금액과 주석 금액이 일치",
        [
            CheckEvidence("재무상태표 유형자산", 1_000, "statement:bs/table:0/row:1/col:1"),
            CheckEvidence("주석 11 기말 장부금액", 1_000, "note:11/table:1/row:1/col:1"),
        ],
    )

    html = render_audit_reconciliation_html(report, [check])
    note_panel = html[html.index('id="note-panel-note-11"') :]
    comparison_grid = note_panel[note_panel.index('class="note-comparison-grid"') :]
    comparison_grid = comparison_grid[: comparison_grid.index('class="note-total-table-list"')]

    assert "<h4>재무상태표 연결</h4>" in comparison_grid
    assert "재무제표 원문 근거" in comparison_grid
    assert "자동 대사 없음:" in comparison_grid
    for axis in ("손익계산서", "자본변동표", "현금흐름표", "다른 주석", "합계 검증", "전기 대사"):
        assert axis in comparison_grid[comparison_grid.index("자동 대사 없음:") :]
    assert comparison_grid.count("검증 결과가 없습니다") == 0


def test_note_panel_renders_prior_column_check_under_prior_group():
    note_table = ReportTable(
        0,
        [["구분", "당기", "전기"], ["기말 장부금액", "1,000", "900"]],
        "11. 유형자산",
        SourceLocation("note:11", 0, 0),
    )
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [_section("note:11", "유형자산", "note", "11", note_table)],
    )
    check = CheckResult(
        "prior-note",
        "prior_column_fs_note",
        "unexplained_gap",
        "report",
        "11",
        "유형자산 전기 재무제표-주석 대사",
        900,
        800,
        -100,
        0,
        "전기 재무제표 금액과 주석 금액 차이",
        [
            CheckEvidence("전기 재무상태표 유형자산", 900, "statement:bs/table:0/row:1/col:2"),
            CheckEvidence("주석 11 전기 기말 장부금액", 800, "note:11/table:0/row:1/col:2"),
        ],
    )

    html = render_audit_reconciliation_html(report, [check])
    note_panel = html[html.index('id="note-panel-note-11"') :]
    prior_panel = note_panel[note_panel.index("<h4>전기 대사</h4>") :]

    assert "전기대사" in prior_panel
    assert "유형자산 전기 재무제표-주석 대사" in prior_panel
    assert "연결된 자동 검증 결과가 없습니다" not in prior_panel[: prior_panel.index("</div>", prior_panel.index("frame-check-group"))]


def test_empty_prior_axis_uses_compact_empty_comparison_line():
    note_table = ReportTable(
        0,
        [["구분", "당기"], ["기말 장부금액", "1,000"]],
        "11. 유형자산",
        SourceLocation("note:11", 0, 0),
    )
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [_section("note:11", "유형자산", "note", "11", note_table)],
    )

    html = render_audit_reconciliation_html(report, [])
    note_panel = html[html.index('id="note-panel-note-11"') :]

    assert "<h4>전기 대사</h4>" not in note_panel
    assert "자동 대사 없음:" in note_panel
    assert "전기 대사" in note_panel[note_panel.index("자동 대사 없음:") :]
    assert "전기 대사 자동 검증 결과가 없습니다" not in note_panel
    assert "연결된 자동 검증 결과가 없습니다" not in note_panel


def test_long_note_text_is_collapsed_behind_details():
    long_text = "긴 주석 문단입니다. " * 70
    long_note = ReportSection(
        "note:1",
        "일반사항",
        "note",
        "1",
        [ReportBlock("text", long_text, None, SourceLocation("note:1", 0))],
    )
    short_note = ReportSection(
        "note:2",
        "중요한 회계정책",
        "note",
        "2",
        [ReportBlock("text", "짧은 주석 문단입니다.", None, SourceLocation("note:2", 0))],
    )

    html = render_audit_reconciliation_html(
        FullReport("sample.html", "Sample Co", [], [long_note, short_note]),
        [],
    )
    long_panel = html[html.index('id="note-panel-note-1"') : html.index('id="note-panel-note-2"')]
    short_panel = html[html.index('id="note-panel-note-2"') :]

    assert "<details" in long_panel
    assert "주석 원문 전체" in long_panel
    assert escape(long_text.strip()) in long_panel
    assert "<details" not in short_panel
    assert "짧은 주석 문단입니다." in short_panel


def test_report_frame_groups_cfs_note_match_as_cashflow_note_reconciliation():
    cfs_table = _table("statement:cf", 0, "현금흐름표")
    note_table = _table("note:11", 0, "유형자산")
    report = FullReport(
        "sample.html",
        "Sample Co",
        [_section("statement:cf", "현금흐름표", "statement", "", cfs_table)],
        [_section("note:11", "유형자산", "note", "11", note_table)],
    )
    check = CheckResult(
        "cfs-note",
        "cfs_note_match",
        "matched",
        "report",
        "11",
        "유형자산 취득 현금흐름표-주석 대사",
        100,
        100,
        0,
        0,
        "현금흐름표 금액과 주석 금액이 일치",
        [
            CheckEvidence("현금흐름표 유형자산 취득", -100, "statement:cf/table:0/row:1/col:1"),
            CheckEvidence("주석 11 취득", 100, "note:11/table:0/row:1/col:1"),
        ],
    )

    frame = build_report_frame(report, [check])

    assert frame.statement_sections[0].tables[0].check_groups["현금흐름표-주석 대사"] == (check,)
    assert frame.notes[0].tables[0].check_groups["현금흐름표-주석 대사"] == (check,)


def test_note_panel_surfaces_note_footing_checks_in_total_panel():
    note_table = ReportTable(
        0,
        [["구분", "당기"], ["토지", "600"], ["건물", "400"], ["합계", "900"]],
        "11. 유형자산",
        SourceLocation("note:11", 0, 0),
    )
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [_section("note:11", "유형자산", "note", "11", note_table)],
    )
    check = CheckResult(
        "total-note-11",
        "total_check",
        "unexplained_gap",
        "note",
        "11",
        "유형자산 합계 검증",
        1_000,
        900,
        -100,
        0,
        "하위 항목 합계와 표시 합계가 다름",
        [CheckEvidence("주석 11 합계", 900, "note:11/table:0/row:3/col:1")],
    )

    html = render_audit_reconciliation_html(report, [check])
    note_panel = html[html.index('id="note-panel-note-11"') :]
    total_panel = note_panel[note_panel.index("<h4>합계 검증</h4>") :]

    assert "합계 검증" in total_panel
    assert "유형자산 합계 검증" in total_panel
    assert "연결된 자동 검증 결과가 없습니다" not in total_panel[: total_panel.index("</div>", total_panel.index("frame-check-group"))]
