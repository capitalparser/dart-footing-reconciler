"""Per-account verification-state badge tests for _render_table_rows."""
from dart_footing_reconciler.checks import CheckEvidence, CheckResult, MATCHED, UNEXPLAINED_GAP, PARSE_UNCERTAIN
from dart_footing_reconciler.document import FullReport, ReportBlock, ReportSection, ReportTable, SourceLocation
from dart_footing_reconciler.report_html import _render_table_rows


def _t(rows):
    return ReportTable(0, rows, "재무상태표", SourceLocation("statement:bs", 0, 0))


def _chk(status):
    return CheckResult("c", "t", status, "report", "", "t", 100, 100, 0, 1, "ok",
                       [CheckEvidence("유형자산", 100, "statement:bs/table:0/row:1/col:1")])


def _t_report(table):
    """Wrap a ReportTable in a minimal FullReport for threading."""
    section = ReportSection(
        "statement:bs", "재무상태표", "statement", "",
        [ReportBlock("table", "", table, table.location)],
    )
    return FullReport("s.html", "Co", [section], [])


def test_table_rows_show_per_account_state_and_mich_for_uncovered():
    table = _t([["구분", "당기"], ["유형자산", "100"], ["재고자산", "50"], ["자산", ""]])
    report = _t_report(table)
    html = _render_table_rows(table, {1: _chk(MATCHED)}, show_state=True, report=report)
    assert "검증완료" in html          # row 1 has a matched check
    assert "미검증" in html            # row 2 (재고자산) has an amount but no check
    assert html.count("acct-state") == 2   # group header (자산, no amount) gets no badge


def test_table_rows_no_state_column_by_default():
    table = _t([["구분", "당기"], ["유형자산", "100"]])
    html = _render_table_rows(table, {})
    assert "acct-state" not in html and "검증</th>" not in html


def test_display_check_title_strips_note_prefix_and_koreanizes():
    from dart_footing_reconciler.report_html import _display_check_title
    from dart_footing_reconciler.document import ReportSection
    sec = ReportSection("note:4", "영업부문 (연결)", "note", "4", [])
    title = "4. 영업부문 (연결) 보고부문에 대한 공시 당기 (단위 : 백만원) total check"
    out = _display_check_title(title, sec)
    assert out.startswith("보고부문에 대한 공시")
    assert "4. 영업부문" not in out
    assert "total check" not in out
    assert "합계검증" in out


# ── Task 4: _humanize_source tests ───────────────────────────────────────────

def _report_with_note():
    t = ReportTable(
        28,
        [["구분", "총장부금액"], ["매출채권 합계", "100"]],
        "8. 매출채권",
        SourceLocation("note:8", 0, 28),
    )
    note = ReportSection(
        "note:8", "매출채권 및 기타채권", "note", "8",
        [ReportBlock("table", "", t, t.location)],
    )
    return FullReport("s.html", "Co", [], [note])


def test_humanize_source_resolves_note_row_and_column():
    from dart_footing_reconciler.report_html import _humanize_source
    report = _report_with_note()
    out = _humanize_source(report, "note:8/table:28/row:1/col:1")
    assert "주석8" in out and "매출채권 합계" in out and "총장부금액" in out
    assert "table:28" not in out


def test_humanize_source_falls_back_without_crash():
    from dart_footing_reconciler.report_html import _humanize_source
    report = _report_with_note()
    out = _humanize_source(report, "note:99/table:5/row:3/col:2")
    assert isinstance(out, str) and out


def test_drilldown_source_is_clickable_jump_and_cells_have_addresses():
    from dart_footing_reconciler.report_html import _render_table_rows, _render_drilldown
    from dart_footing_reconciler.checks import CheckResult, CheckEvidence, MATCHED
    report = _report_with_note()
    table = report.notes[0].blocks[0].table
    html = _render_table_rows(table, {}, report=report, id_prefix="dd")
    assert 'data-cell="r1c1"' in html
    r = CheckResult("c", "t", MATCHED, "report", "8", "t", 100, 100, 0, 1, "ok",
                    [CheckEvidence("매출채권 합계", 100, "note:8/table:28/row:1/col:1")])
    dd = _render_drilldown(r, report)
    assert 'data-jump="panel-note-8"' in dd and 'data-jump-cell="r1c1"' in dd
