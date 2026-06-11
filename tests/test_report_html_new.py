"""Tests for the new evidence_cockpit HTML renderer."""
from pathlib import Path
from dart_footing_reconciler.checks import CheckEvidence, CheckResult, MATCHED, UNEXPLAINED_GAP, PARSE_UNCERTAIN
from dart_footing_reconciler.document import (
    FullReport, ReportBlock, ReportSection, ReportTable, SourceLocation,
)
from dart_footing_reconciler.report_html import export_audit_reconciliation_html, _tie_results


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

def _result(check_id: str, status: str, source: str, note_no: str = "") -> CheckResult:
    return CheckResult(
        check_id=check_id, check_type="test", status=status,
        scope="report", note_no=note_no, title=check_id,
        expected=100, actual=100, difference=0, tolerance=1,
        reason="ok",
        evidence=[CheckEvidence("자산총계", 100, source)],
    )


def test_tie_results_groups_by_statement_kind():
    results = [
        _result("eq1", MATCHED, "statement:bs/table:0/row:1"),
        _result("eq2", MATCHED, "statement:cf/table:0/row:2"),
        _result("eq3", MATCHED, "statement:bs/table:0/row:3"),
    ]
    tied = _tie_results(results)
    assert len(tied["bs"]) == 2
    assert len(tied["cf"]) == 1

def test_tie_results_groups_note():
    results = [
        _result("n1", MATCHED, "note:12/table:0/row:1", note_no="12"),
        _result("n2", MATCHED, "note:13/table:0/row:2", note_no="13"),
    ]
    tied = _tie_results(results)
    assert len(tied.get("note:12", [])) == 1
    assert len(tied.get("note:13", [])) == 1

def test_export_creates_html_file(tmp_path: Path):
    bs = _stmt_section("statement:재무상태표", "재무상태표",
                       [["구분", "당기", "전기"], ["자산총계", "1,000", "900"]])
    report = FullReport("test.html", "테스트(주)", [bs], [])
    checks = [_result("eq1", MATCHED, "statement:bs/table:0/row:1")]
    out = tmp_path / "report.html"
    export_audit_reconciliation_html(report, checks, out)
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "테스트(주)" in content

def test_export_returns_path(tmp_path: Path):
    report = FullReport("t.html", "회사", [], [])
    result_path = export_audit_reconciliation_html(report, [], tmp_path / "r.html")
    assert result_path == tmp_path / "r.html"


def test_drilldown_ids_are_unique_across_panels(tmp_path: Path):
    bs = _stmt_section("statement:재무상태표", "재무상태표",
                       [["구분", "당기"], ["자산총계", "1,000"]])
    ifs = _stmt_section("statement:손익계산서", "손익계산서",
                        [["구분", "당기"], ["매출액", "500"]])
    report = FullReport("t.html", "회사", [bs, ifs], [])
    checks = [
        _result("eq1", MATCHED, "statement:bs/table:0/row:1"),
        _result("eq2", MATCHED, "statement:is/table:0/row:1"),
    ]
    out = tmp_path / "r.html"
    export_audit_reconciliation_html(report, checks, out)
    content = out.read_text(encoding="utf-8")
    # Both panels have a drilldown; their ids must differ
    import re
    ids = re.findall(r'id="(dd-[^"]+)"', content)
    assert len(ids) == len(set(ids)), f"Duplicate drilldown IDs: {ids}"


def test_check_id_single_quote_escaped_in_js(tmp_path: Path):
    note = _note_section("12", [["구분", "당기"], ["합계", "100"]])
    report = FullReport("t.html", "회사", [], [note])
    bad_id = "note_12'foo"
    checks = [CheckResult(
        check_id=bad_id, check_type="test", status=MATCHED,
        scope="report", note_no="12", title="test",
        expected=100, actual=100, difference=0, tolerance=1, reason="ok",
        evidence=[CheckEvidence("합계", 100, "note:12/table:0/row:1")],
    )]
    out = tmp_path / "r.html"
    export_audit_reconciliation_html(report, checks, out)
    content = out.read_text(encoding="utf-8")
    assert "note_12'foo" not in content  # raw single-quote must not appear in JS
