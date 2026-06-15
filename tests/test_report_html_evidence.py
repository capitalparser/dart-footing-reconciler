"""Per-account verification-state badge tests for _render_table_rows."""
from dart_footing_reconciler.checks import CheckEvidence, CheckResult, MATCHED, UNEXPLAINED_GAP, PARSE_UNCERTAIN
from dart_footing_reconciler.document import ReportTable, SourceLocation
from dart_footing_reconciler.report_html import _render_table_rows


def _t(rows):
    return ReportTable(0, rows, "재무상태표", SourceLocation("statement:bs", 0, 0))


def _chk(status):
    return CheckResult("c", "t", status, "report", "", "t", 100, 100, 0, 1, "ok",
                       [CheckEvidence("유형자산", 100, "statement:bs/table:0/row:1/col:1")])


def test_table_rows_show_per_account_state_and_mich_for_uncovered():
    table = _t([["구분", "당기"], ["유형자산", "100"], ["재고자산", "50"], ["자산", ""]])
    html = _render_table_rows(table, {1: _chk(MATCHED)}, show_state=True)
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
