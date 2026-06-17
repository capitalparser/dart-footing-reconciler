"""Cockpit-compliance tests for the evidence_cockpit HTML renderer.

These pin the design-kit contract the renderer must satisfy:
 - reader-orientation brief (현재 상태 / 왜 중요한가 / 다음 행동)
 - five common cockpit tabs (요약 / 진행현황 / 주의 필요 / 근거 / 다음 행동)
 - consolidated 주의 필요 view (unexplained gaps + parse-uncertain in one place)
 - 진행현황 coverage view and 다음 행동 view
 - print stylesheet that repeats table headers

Hard invariant: adding these views must NOT change the five status counts.
"""
from pathlib import Path

from dart_footing_reconciler.checks import (
    CheckEvidence, CheckResult, MATCHED, UNEXPLAINED_GAP, PARSE_UNCERTAIN, NOT_TESTED,
)
from dart_footing_reconciler.document import (
    FullReport, ReportBlock, ReportSection, ReportTable, SourceLocation,
)
from dart_footing_reconciler.report_html import export_audit_reconciliation_html


def _table(idx: int, rows: list[list[str]]) -> ReportTable:
    return ReportTable(idx, rows, "테스트", SourceLocation("s", 0, idx))


def _stmt_section(section_id: str, title: str, rows: list[list[str]]) -> ReportSection:
    t = _table(0, rows)
    return ReportSection(section_id, title, "statement", "",
                         [ReportBlock("table", "", t, t.location)])


def _note_section(note_no: str, rows: list[list[str]]) -> ReportSection:
    t = _table(0, rows)
    return ReportSection(f"note:{note_no}", f"주석 {note_no}", "note", note_no,
                         [ReportBlock("table", "", t, t.location)])


def _result(check_id: str, status: str, source: str, note_no: str = "",
            title: str | None = None) -> CheckResult:
    return CheckResult(
        check_id=check_id, check_type="test", status=status,
        scope="report", note_no=note_no, title=title or check_id,
        expected=100, actual=100, difference=0, tolerance=1,
        reason="ok",
        evidence=[CheckEvidence("자산총계", 100, source)],
    )


def _uncertain(check_id: str, source: str, title: str) -> CheckResult:
    return CheckResult(
        check_id=check_id, check_type="test", status=PARSE_UNCERTAIN,
        scope="report", note_no="", title=title,
        expected=None, actual=None, difference=None, tolerance=1,
        reason="파싱 불확실",
        evidence=[CheckEvidence("자산총계", None, source)],
        parse_uncertain_reason="LABEL_NOT_FOUND",
    )


def _mixed_report(tmp_path: Path) -> str:
    bs = _stmt_section("statement:재무상태표", "재무상태표",
                       [["구분", "당기", "전기"], ["자산총계", "1,000", "900"]])
    note = _note_section("12", [["구분", "당기"], ["차입금", "500"]])
    report = FullReport("test.html", "테스트(주)", [bs], [note])
    checks = [
        _result("eq1", MATCHED, "statement:bs/table:0/row:1", title="자산=부채+자본"),
        _result("gap1", UNEXPLAINED_GAP, "note:12/table:0/row:1",
                note_no="12", title="차입금 대사 차이"),
        _uncertain("unc1", "note:12/table:0/row:1", "파싱 실패 항목"),
    ]
    out = tmp_path / "report.html"
    export_audit_reconciliation_html(report, checks, out)
    return out.read_text(encoding="utf-8")


def test_reader_orientation_terms_present(tmp_path: Path):
    content = _mixed_report(tmp_path)
    for term in ("현재 상태", "왜 중요한가", "다음 행동"):
        assert term in content, f"missing reader-orientation term: {term}"


def test_common_cockpit_tabs_present(tmp_path: Path):
    content = _mixed_report(tmp_path)
    for tab in ("요약", "진행현황", "주의 필요", "근거", "다음 행동"):
        assert tab in content, f"missing cockpit tab: {tab}"


def test_print_stylesheet_repeats_headers(tmp_path: Path):
    content = _mixed_report(tmp_path)
    assert "@media print" in content
    assert "table-header-group" in content


def test_attention_panel_consolidates_gap_and_uncertain(tmp_path: Path):
    content = _mixed_report(tmp_path)
    assert 'id="panel-attention"' in content
    # one unexplained gap + one parse-uncertain => two consolidated attention rows
    assert content.count("attn-row") == 2
    assert "차입금 대사 차이" in content
    assert "파싱 실패 항목" in content


def test_attention_panel_has_filter_pills(tmp_path: Path):
    content = _mixed_report(tmp_path)
    assert 'data-filter-control="#panel-attention"' in content
    assert 'data-filter="all"' in content


def test_progress_panel_present(tmp_path: Path):
    content = _mixed_report(tmp_path)
    assert 'id="panel-progress"' in content


def test_next_actions_panel_present(tmp_path: Path):
    content = _mixed_report(tmp_path)
    assert 'id="panel-next"' in content


def test_kpi_counts_unchanged_by_cockpit_views(tmp_path: Path):
    """The five status counts in the verdict banner must equal the raw inputs.

    1 matched + 1 unexplained + 1 parse_uncertain (+0 explainable +0 not_tested).
    Consolidating those same results into the attention/progress views must not
    inflate or drop any count.
    """
    content = _mixed_report(tmp_path)
    # KPI tiles render value then name; assert each status tile shows the right count.
    assert '<div class="kpi-val">1</div><div class="kpi-name">검증 완료</div>' in content
    assert '<div class="kpi-val">1</div><div class="kpi-name">검토 필요</div>' in content
    assert '<div class="kpi-val">1</div><div class="kpi-name">파싱 불확실</div>' in content
