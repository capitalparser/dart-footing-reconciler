"""Tests for the new evidence_cockpit HTML renderer."""
from pathlib import Path
from dart_footing_reconciler.checks import CheckEvidence, CheckResult, MATCHED, UNEXPLAINED_GAP, PARSE_UNCERTAIN
from dart_footing_reconciler.document import (
    FullReport, ReportBlock, ReportSection, ReportTable, SourceLocation,
)
from dart_footing_reconciler.report_html import (
    export_audit_reconciliation_html,
    _backlog_title_label,
    _tie_results,
)


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


def test_duplicate_statement_sections_are_rendered_as_separate_panels(tmp_path: Path):
    table_con = ReportTable(
        0,
        [["구분", "당기"], ["자산총계", "1,000"]],
        "재무상태표",
        SourceLocation("statement:재무상태표", 0, 0),
    )
    table_sep = ReportTable(
        5,
        [["구분", "당기"], ["자산총계", "900"]],
        "재무상태표",
        SourceLocation("statement:재무상태표", 1, 5),
    )
    bs_con = ReportSection(
        "statement:재무상태표",
        "재무상태표",
        "statement",
        "",
        [ReportBlock("table", "", table_con, table_con.location)],
        scope="consolidated",
    )
    bs_sep = ReportSection(
        "statement:재무상태표",
        "재무상태표",
        "statement",
        "",
        [ReportBlock("table", "", table_sep, table_sep.location)],
        scope="separate",
    )
    report = FullReport("t.html", "회사", [bs_con, bs_sep], [])
    checks = [
        _result("con", MATCHED, "statement:bs/table:0/row:1"),
        _result("sep", MATCHED, "statement:bs/table:5/row:1"),
    ]

    out = tmp_path / "r.html"
    export_audit_reconciliation_html(report, checks, out)
    content = out.read_text(encoding="utf-8")

    assert 'id="panel-bs"' in content
    assert 'id="panel-bs-t5"' in content
    assert "재무상태표 (연결)" in content
    assert "재무상태표 (별도)" in content


def test_duplicate_note_numbers_are_rendered_as_separate_panels(tmp_path: Path):
    con_table = ReportTable(
        12,
        [["구분", "당기"], ["유형자산", "100"]],
        "12. 유형자산 (연결)",
        SourceLocation("note:12", 0, 12),
    )
    sep_table = ReportTable(
        42,
        [["구분", "당기"], ["유형자산", "90"]],
        "12. 유형자산",
        SourceLocation("note:12", 1, 42),
    )
    con_note = ReportSection(
        "note:12",
        "유형자산 (연결)",
        "note",
        "12",
        [ReportBlock("table", "", con_table, con_table.location)],
        scope="consolidated",
    )
    sep_note = ReportSection(
        "note:12",
        "유형자산",
        "note",
        "12",
        [ReportBlock("table", "", sep_table, sep_table.location)],
        scope="separate",
    )
    report = FullReport("t.html", "회사", [], [con_note, sep_note])
    checks = [
        _result("con-note", MATCHED, "note:12/table:12/row:1/col:1", note_no="12"),
        _result("sep-note", MATCHED, "note:12/table:42/row:1/col:1", note_no="12"),
    ]

    out = tmp_path / "r.html"
    export_audit_reconciliation_html(report, checks, out)
    content = out.read_text(encoding="utf-8")

    assert 'id="panel-note-12-con"' in content
    assert 'id="panel-note-12-sep"' in content
    assert 'data-target="panel-note-12-con"' in content
    assert 'data-target="panel-note-12-sep"' in content
    assert 'data-jump="panel-note-12-con"' in content
    assert 'data-jump="panel-note-12-sep"' in content


def test_duplicate_note_numbers_with_same_scope_get_unique_panel_ids(tmp_path: Path):
    first_table = ReportTable(
        6,
        [["구분", "당기"], ["매출채권", "100"]],
        "6. 매출채권및기타채권 (연결)",
        SourceLocation("note:6", 0, 6),
    )
    second_table = ReportTable(
        60,
        [["구분", "당기"], ["재공품", "90"]],
        "6. 재고자산 보유 및 실사내역",
        SourceLocation("note:6", 1, 60),
    )
    first_note = ReportSection(
        "note:6",
        "매출채권및기타채권 (연결)",
        "note",
        "6",
        [ReportBlock("table", "", first_table, first_table.location)],
        scope="consolidated",
    )
    second_note = ReportSection(
        "note:6",
        "재고자산의 보유 및 실사내역 등(연결재무제표 기준)",
        "note",
        "6",
        [ReportBlock("table", "", second_table, second_table.location)],
        scope="consolidated",
    )
    report = FullReport("t.html", "회사", [], [first_note, second_note])
    checks = [
        _result("first-note", MATCHED, "note:6/table:6/row:1/col:1", note_no="6"),
        _result("second-note", MATCHED, "note:6/table:60/row:1/col:1", note_no="6"),
    ]

    out = tmp_path / "r.html"
    export_audit_reconciliation_html(report, checks, out)
    content = out.read_text(encoding="utf-8")

    import re

    panel_ids = re.findall(r'id="(panel-note-6-con[^"]*)"', content)
    assert len(panel_ids) == 2
    assert len(set(panel_ids)) == 2
    assert "panel-note-6-con" in panel_ids
    second_panel_id = next(panel_id for panel_id in panel_ids if panel_id != "panel-note-6-con")
    assert f'data-target="{second_panel_id}"' in content
    assert f'data-jump="{second_panel_id}" data-jump-cell="r1c1" data-jump-table="60"' in content


def test_scope_split_report_shell_renders_consolidated_and_separate_views(tmp_path: Path):
    bs_con_table = ReportTable(
        0,
        [["구분", "당기"], ["자산총계", "1,000"]],
        "재무상태표",
        SourceLocation("statement:bs", 0, 0),
    )
    bs_sep_table = ReportTable(
        10,
        [["구분", "당기"], ["자산총계", "900"]],
        "재무상태표",
        SourceLocation("statement:bs", 1, 10),
    )
    note_con_table = ReportTable(
        20,
        [["구분", "금액"], ["연결 유형자산", "100"]],
        "12. 유형자산 (연결)",
        SourceLocation("note:12", 0, 20),
    )
    note_sep_table = ReportTable(
        30,
        [["구분", "금액"], ["별도 유형자산", "90"]],
        "12. 유형자산",
        SourceLocation("note:12", 1, 30),
    )
    report = FullReport(
        "t.html",
        "회사",
        [
            ReportSection(
                "statement:bs",
                "재무상태표",
                "statement",
                "",
                [ReportBlock("table", "", bs_con_table, bs_con_table.location)],
                scope="consolidated",
            ),
            ReportSection(
                "statement:bs",
                "재무상태표",
                "statement",
                "",
                [ReportBlock("table", "", bs_sep_table, bs_sep_table.location)],
                scope="separate",
            ),
        ],
        [
            ReportSection(
                "note:12",
                "유형자산 (연결)",
                "note",
                "12",
                [ReportBlock("table", "", note_con_table, note_con_table.location)],
                scope="consolidated",
            ),
            ReportSection(
                "note:12",
                "유형자산",
                "note",
                "12",
                [ReportBlock("table", "", note_sep_table, note_sep_table.location)],
                scope="separate",
            ),
        ],
    )
    checks = [
        _result("con-bs", MATCHED, "statement:bs/table:0/row:1"),
        _result("sep-bs", MATCHED, "statement:bs/table:10/row:1"),
        _result("scope-attn", UNEXPLAINED_GAP, "note:12/table:20/row:1/col:1", note_no="12"),
        _result("scope-attn", UNEXPLAINED_GAP, "note:12/table:30/row:1/col:1", note_no="12"),
    ]

    out = tmp_path / "r.html"
    export_audit_reconciliation_html(report, checks, out)
    content = out.read_text(encoding="utf-8")

    assert "연결보고서" in content
    assert "별도보고서" in content
    assert 'data-report-scope="consolidated"' in content
    assert 'data-report-scope="separate"' in content
    assert 'id="panel-summary-con"' in content
    assert 'id="panel-summary-sep"' in content
    assert "재무상태표 (연결)" in content
    assert "재무상태표 (별도)" in content
    assert "12. 유형자산 (연결)" in content
    assert "12. 유형자산 (별도)" in content
    assert 'class="nav-item active" data-target="panel-summary-con" aria-current="page"' in content
    assert 'class="nav-item active" data-target="panel-summary-sep" aria-current="page"' in content
    assert "dd-panel-attention-con-0-scope-attn" in content
    assert "dd-panel-attention-sep-0-scope-attn" in content
    import re

    ids = re.findall(r'id="([^"]+)"', content)
    assert len(ids) == len(set(ids))


def test_scope_split_runtime_switches_scope_before_panel_navigation():
    from dart_footing_reconciler.report_html import _inline_js

    js = _inline_js()

    assert "setReportScope" in js
    assert "data-report-scope" in js
    assert "closest('.report-scope-shell')" in js
    assert "activatePanel(panelId, true)" in js


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


def test_attention_panel_ids_are_unique_when_check_ids_repeat():
    from dart_footing_reconciler.report_html import _render_attention_panel

    results = [
        _result("same-id", UNEXPLAINED_GAP, "note:6/table:6/row:1/col:1", note_no="6"),
        _result("same-id", UNEXPLAINED_GAP, "note:7/table:7/row:1/col:1", note_no="7"),
    ]

    html = _render_attention_panel(results)

    import re

    ids = re.findall(r'id="((?:tri-)?dd-panel-attention-[^"]+)"', html)
    assert len(ids) == 4
    assert len(ids) == len(set(ids))


def test_verdict_banner_all_matched(tmp_path: Path):
    """Verdict banner shows 'PASS equivalent' when all checks matched."""
    bs = _stmt_section("statement:재무상태표", "재무상태표",
                       [["구분", "당기"], ["자산총계", "1,000"]])
    report = FullReport("t.html", "회사", [bs], [])
    checks = [_result("eq1", MATCHED, "statement:bs/table:0/row:1")]
    out = tmp_path / "r.html"
    export_audit_reconciliation_html(report, checks, out)
    content = out.read_text(encoding="utf-8")
    assert "이상 없음" in content
    assert "verdict-ok" in content


def test_verdict_banner_gap(tmp_path: Path):
    """Verdict banner shows warning when there's an unexplained gap."""
    bs = _stmt_section("statement:재무상태표", "재무상태표",
                       [["구분", "당기"], ["자산총계", "1,000"]])
    report = FullReport("t.html", "회사", [bs], [])
    checks = [_result("eq1", UNEXPLAINED_GAP, "statement:bs/table:0/row:1")]
    out = tmp_path / "r.html"
    export_audit_reconciliation_html(report, checks, out)
    content = out.read_text(encoding="utf-8")
    assert "확인 필요" in content
    assert "verdict-warn" in content


def test_verdict_banner_parse_uncertain(tmp_path: Path):
    """Verdict banner shows uncertain state when there's a parse uncertain result."""
    bs = _stmt_section("statement:재무상태표", "재무상태표",
                       [["구분", "당기"], ["자산총계", "1,000"]])
    report = FullReport("t.html", "회사", [bs], [])
    checks = [_result("eq1", PARSE_UNCERTAIN, "statement:bs/table:0/row:1")]
    out = tmp_path / "r.html"
    export_audit_reconciliation_html(report, checks, out)
    content = out.read_text(encoding="utf-8")
    assert "확인 필요" in content


def test_statement_panel_tick_classes_on_verified_rows(tmp_path: Path):
    """Rows with matching CheckResults get the correct CSS class."""
    bs = _stmt_section("statement:재무상태표", "재무상태표",
                       [["구분", "당기"], ["자산총계", "1,000"], ["부채총계", "600"]])
    report = FullReport("t.html", "회사", [bs], [])
    checks = [
        _result("eq1", MATCHED, "statement:bs/table:0/row:1"),
        _result("eq2", UNEXPLAINED_GAP, "statement:bs/table:0/row:2"),
    ]
    out = tmp_path / "r.html"
    export_audit_reconciliation_html(report, checks, out)
    content = out.read_text(encoding="utf-8")
    assert "verified-ok" in content
    assert "verified-warn" in content


def test_drilldown_rows_present(tmp_path: Path):
    """Each verified row has a corresponding review detail template."""
    bs = _stmt_section("statement:재무상태표", "재무상태표",
                       [["구분", "당기"], ["자산총계", "1,000"]])
    report = FullReport("t.html", "회사", [bs], [])
    checks = [_result("eq1", MATCHED, "statement:bs/table:0/row:1")]
    out = tmp_path / "r.html"
    export_audit_reconciliation_html(report, checks, out)
    content = out.read_text(encoding="utf-8")
    assert 'id="review-rail"' in content
    assert "dd-inner" in content
    assert "dd-row" in content
    assert "showReview" in content


def test_parse_uncertain_panel_present(tmp_path: Path):
    """Parse uncertain panel rendered when there are uncertain results."""
    bs = _stmt_section("statement:재무상태표", "재무상태표",
                       [["구분", "당기"], ["자산총계", "1,000"]])
    report = FullReport("t.html", "회사", [bs], [])
    # Need to use CheckResult directly to set parse_uncertain_reason
    from dart_footing_reconciler.checks import CheckResult, CheckEvidence
    checks = [CheckResult(
        check_id="eq1", check_type="test", status=PARSE_UNCERTAIN,
        scope="report", note_no="bs", title="파싱 실패 항목",
        expected=None, actual=None, difference=None, tolerance=1,
        reason="파싱 불확실",
        evidence=[CheckEvidence("자산총계", None, "statement:bs/table:0/row:1")],
        parse_uncertain_reason="LABEL_NOT_FOUND",
    )]
    out = tmp_path / "r.html"
    export_audit_reconciliation_html(report, checks, out)
    content = out.read_text(encoding="utf-8")
    assert "panel-parse-diag" in content
    assert "LABEL_NOT_FOUND" in content
    assert "파싱 진단" in content


def test_review_backlog_panel_surfaces_data_driven_backend_queue(tmp_path: Path):
    note = _note_section("12", [["구분", "당기"], ["기말 유형자산", "100"]])
    report = FullReport("t.html", "회사", [], [note])
    checks = [CheckResult(
        check_id="asset-label",
        check_type="fs_note_match",
        status=PARSE_UNCERTAIN,
        scope="report",
        note_no="12",
        title="유형자산 본문-주석 금액 대사",
        expected=None,
        actual=None,
        difference=None,
        tolerance=1,
        reason="공시에서 해당 계정과목을 찾지 못했습니다.",
        evidence=[CheckEvidence("유형자산", None, "note:12/table:0/row:1/col:1")],
        parse_uncertain_reason="LABEL_NOT_FOUND",
        account_key="property_plant_equipment",
    )]
    out = tmp_path / "r.html"

    export_audit_reconciliation_html(report, checks, out)
    content = out.read_text(encoding="utf-8")

    assert 'data-target="panel-review-backlog"' in content
    assert "검증 고도화 큐" in content
    assert "후보 사전 보강" in content
    assert "계정 라벨/동의어 후보 사전" in content
    assert "원문 해석 확인 필요" in content
    assert "관련 계정" in content
    assert "유형자산" in content
    assert "property_plant_equipment" not in content


def test_validation_qa_panel_surfaces_missing_core_validation_logic(tmp_path: Path):
    note = _note_section(
        "12",
        [
            ["구분", "건물", "기계장치", "합계"],
            ["기초", "40", "60", "100"],
            ["취득", "10", "20", "30"],
            ["합계", "50", "80", "130"],
        ],
    )
    report = FullReport("t.html", "회사", [], [note])
    out = tmp_path / "r.html"

    export_audit_reconciliation_html(report, [], out)
    content = out.read_text(encoding="utf-8")

    assert 'data-target="panel-validation-qa"' in content
    assert "검증 커버리지 QA" in content
    assert "QA 실패" in content
    assert "합계검증" in content


def test_validation_qa_panel_uses_audit_labels_for_statement_and_prior_categories(tmp_path: Path):
    bs = _stmt_section(
        "statement:bs",
        "재무상태표",
        [
            ["구분", "당기", "전기"],
            ["자산총계", "130", "120"],
            ["부채총계", "50", "45"],
            ["자본총계", "80", "75"],
        ],
    )
    report = FullReport("t.html", "회사", [bs], [])
    out = tmp_path / "r.html"

    export_audit_reconciliation_html(report, [], out)
    content = out.read_text(encoding="utf-8")

    assert "재무제표 본문 검증" in content
    assert "전기 숫자 검증" in content
    assert "statement body coverage" not in content
    assert "prior period coverage" not in content


def test_validation_qa_panel_keeps_completion_criteria_visible_when_passing(tmp_path: Path):
    bs = _stmt_section(
        "statement:bs",
        "재무상태표",
        [
            ["구분", "당기"],
            ["자산총계", "130"],
            ["부채총계", "50"],
            ["자본총계", "80"],
        ],
    )
    report = FullReport("t.html", "회사", [bs], [])
    checks = [
        CheckResult(
            check_id="statement_bs_equation:current",
            check_type="statement_bs_equation",
            status=MATCHED,
            scope="report",
            note_no="bs",
            title="재무상태표 기본등식",
            expected=130,
            actual=130,
            difference=0,
            tolerance=1,
            reason="BS equation 성립",
            evidence=[CheckEvidence("자산총계", 130, "statement:bs/table:0/row:1")],
        ),
        CheckResult(
            check_id="statement_subtotal:bs:current",
            check_type="statement_subtotal",
            status=MATCHED,
            scope="report",
            note_no="cross_statement",
            title="재무상태표 본문 소계",
            expected=130,
            actual=130,
            difference=0,
            tolerance=1,
            reason="재무제표 본문 소계가 하위 항목 합계와 일치",
            evidence=[CheckEvidence("자산총계", 130, "statement:bs/table:0/row:1")],
        )
    ]
    out = tmp_path / "r.html"

    export_audit_reconciliation_html(report, checks, out)
    content = out.read_text(encoding="utf-8")

    assert "백엔드-프론트 표시 계약" in content
    assert "작업 완료 기준" in content
    assert "QA 통과" in content
    assert "검증 로직, 근거 좌표, 프론트 표시 계약이 완료 기준을 충족합니다." in content


def test_review_backlog_title_translates_cfs_before_fs():
    assert _backlog_title_label("차입금의차입 CFS to note match") == "차입금의차입 현금흐름표-주석 대사"


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


def test_section_key_normalizes_korean_statement_id():
    from dart_footing_reconciler.report_html import _section_key
    r = _result("fsn", MATCHED, "statement:재무상태표/table:0/row:10/col:1")
    assert _section_key(r) == "bs"
    r2 = _result("t", MATCHED, "statement:손익계산서/table:1/row:1/col:1")
    assert _section_key(r2) == "is"
    r3 = _result("t", MATCHED, "statement:bs/table:0/row:1")  # short code still works
    assert _section_key(r3) == "bs"


def test_comprehensive_income_statement_keeps_own_statement_panel(tmp_path: Path):
    oci = _stmt_section(
        "statement:포괄손익계산서",
        "포괄손익계산서",
        [["구분", "당기"], ["당기순이익", "1,000"]],
    )
    report = FullReport("t.html", "회사", [oci], [])
    checks = [_result("oci-row", MATCHED, "statement:oci/table:0/row:1")]
    out = tmp_path / "r.html"

    export_audit_reconciliation_html(report, checks, out)
    content = out.read_text(encoding="utf-8")

    assert 'id="panel-oci"' in content
    assert 'data-target="panel-oci"' in content
    assert 'id="panel-is"' not in content


def test_workpaper_frontend_controls_are_rendered(tmp_path: Path):
    bs = _stmt_section(
        "statement:재무상태표",
        "재무상태표",
        [["구분", "당기"], ["자산총계", "1,000"]],
    )
    report = FullReport("t.html", "회사", [bs], [])
    checks = [_result("bs-row", MATCHED, "statement:bs/table:0/row:1")]
    out = tmp_path / "r.html"

    export_audit_reconciliation_html(report, checks, out)
    content = out.read_text(encoding="utf-8")

    assert 'class="workpaper-actions"' in content
    assert 'class="workpaper-status-strip"' in content
    assert 'data-status-search' in content
    assert 'data-workpaper-search' in content
    assert "jumpToActiveUtilityPanel" in content
    assert "applyWorkbenchSearch" in content
    assert "원문 테이블 유지" in content
    assert 'class="nav-item active" data-target="panel-summary" aria-current="page"' in content
    assert 'class="nav-item active" data-target="panel-bs"' not in content


def test_check_id_double_quote_safe_in_html_attr(tmp_path: Path):
    """check_id containing HTML-special chars must not break out of id= attributes."""
    note = _note_section("12", [["구분", "당기"], ["합계", "100"]])
    report = FullReport("t.html", "회사", [], [note])
    bad_id = 'note_12"foo><img src=q onerror=alert(1)>'
    checks = [CheckResult(
        check_id=bad_id, check_type="test", status=MATCHED,
        scope="report", note_no="12", title="test",
        expected=100, actual=100, difference=0, tolerance=1, reason="ok",
        evidence=[CheckEvidence("합계", 100, "note:12/table:0/row:1")],
    )]
    out = tmp_path / "r.html"
    export_audit_reconciliation_html(report, checks, out)
    content = out.read_text(encoding="utf-8")
    assert 'onerror=alert' not in content
    assert '"foo' not in content
