"""Per-account verification-state badge tests for _render_table_rows."""
import re

from bs4 import BeautifulSoup
import pytest

from dart_footing_reconciler.checks import (
    CheckEvidence,
    CheckResult,
    EXPLAINABLE_GAP,
    MATCHED,
    NOT_TESTED,
    PARSE_UNCERTAIN,
    UNEXPLAINED_GAP,
)
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
    assert 'data-cell="t28r1c1"' in html
    r = CheckResult("c", "t", MATCHED, "report", "8", "t", 100, 100, 0, 1, "ok",
                    [CheckEvidence("매출채권 합계", 100, "note:8/table:28/row:1/col:1")])
    dd = _render_drilldown(r, report)
    assert 'data-jump="panel-note-8"' in dd and 'data-jump-cell="t28r1c1"' in dd


def test_check_evidence_role_defaults_empty_and_accepts_value():
    from dart_footing_reconciler.checks import CheckEvidence
    assert CheckEvidence("a", 1, "s").role == ""
    assert CheckEvidence("a", 1, "s", role="component").role == "component"


def test_drilldown_renders_component_breakdown():
    from dart_footing_reconciler.report_html import _render_drilldown
    from dart_footing_reconciler.checks import CheckResult, CheckEvidence
    report = _report_with_note()
    r = CheckResult("c", "total_check", UNEXPLAINED_GAP, "note", "8", "합계검증", 300, 290, -10, 1, "차이",
                    [CheckEvidence("합계", 290, "note:8/table:28/row:1/col:1", role="total"),
                     CheckEvidence("유동", 100, "note:8/table:28/row:1/col:1", role="component"),
                     CheckEvidence("비유동", 200, "note:8/table:28/row:1/col:1", role="component")])
    dd = _render_drilldown(r, report)
    assert "구성요소 합산" in dd
    assert "기대" in dd and "300" in dd


def test_drilldown_renders_verification_method_and_tolerance():
    from dart_footing_reconciler.report_html import _render_drilldown
    from dart_footing_reconciler.checks import CheckResult, CheckEvidence
    report = _report_with_note()
    r = CheckResult("c", "total_check", MATCHED, "note", "8", "합계검증", 300, 300, 0, 1, "일치",
                    [CheckEvidence("합계", 300, "note:8/table:28/row:1/col:1", role="total")])

    dd = _render_drilldown(r, report)

    assert "검증 방법" in dd
    assert "표 안의 구성요소 합계 = 표시된 합계" in dd
    assert "허용오차 ±1 (표시 단위)" in dd


def test_drilldown_renders_krw_tolerance_for_scaled_checks():
    from dart_footing_reconciler.report_html import _render_drilldown
    from dart_footing_reconciler.checks import CheckResult, CheckEvidence
    report = _report_with_note()
    r = CheckResult("c", "fs_note_match", MATCHED, "note", "8", "주석대사", 300, 300, 0, 1000, "일치",
                    [CheckEvidence("합계", 300, "note:8/table:28/row:1/col:1")])

    dd = _render_drilldown(r, report)

    assert "허용오차 ±1,000원" in dd


def test_html_report_renders_verification_legend_panel(tmp_path):
    from dart_footing_reconciler.report_html import export_audit_reconciliation_html
    from dart_footing_reconciler.checks import CheckResult, CheckEvidence
    report = _report_with_note()
    r = CheckResult("c", "total_check", MATCHED, "note", "8", "합계검증", 300, 300, 0, 1, "일치",
                    [CheckEvidence("합계", 300, "note:8/table:28/row:1/col:1", role="total")])
    out = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [r], out)
    content = out.read_text(encoding="utf-8")

    assert 'id="panel-legend"' in content
    assert "검증 범례" in content


def test_appropriation_statement_renders_panel_and_places_formula_check(tmp_path):
    from dart_footing_reconciler.report_html import export_audit_reconciliation_html
    from dart_footing_reconciler.checks import CheckResult, CheckEvidence

    table = ReportTable(
        0,
        [
            ["구분", "당기"],
            ["미처분이익잉여금", "1,000"],
            ["이익잉여금처분액", "400"],
            ["차기이월미처분이익잉여금", "600"],
        ],
        "이익잉여금처분계산서",
        SourceLocation("statement:이익잉여금처분계산서", 0, 0),
    )
    section = ReportSection(
        "statement:이익잉여금처분계산서",
        "이익잉여금처분계산서",
        "statement",
        "",
        [ReportBlock("table", "", table, table.location)],
    )
    report = FullReport("s.html", "Co", [section], [])
    check = CheckResult(
        "appropriation-formula",
        "appropriation_formula_check",
        MATCHED,
        "report",
        "",
        "처분계산서 산식 검증",
        600,
        600,
        0,
        1,
        "처분계산서 산식이 일치",
        [
            CheckEvidence(
                "차기이월미처분이익잉여금",
                600,
                "statement:이익잉여금처분계산서/table:0/row:3/col:1",
            )
        ],
    )
    out = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [check], out)
    content = out.read_text(encoding="utf-8")

    assert 'id="panel-appropriation"' in content
    panel_start = content.index('id="panel-appropriation"')
    assert "처분계산서 산식 검증" in content[panel_start:]


def test_appropriation_statement_title_variant_routes_to_appropriation_panel(tmp_path):
    from dart_footing_reconciler.report_html import export_audit_reconciliation_html
    from dart_footing_reconciler.checks import CheckResult, CheckEvidence

    table = ReportTable(
        0,
        [
            ["구분", "당기"],
            ["미처분이익잉여금", "1,000"],
            ["이익잉여금처분액", "400"],
            ["차기이월미처분이익잉여금", "600"],
        ],
        "이익잉여금처분계산서(안)",
        SourceLocation("statement:이익잉여금처분계산서(안)", 0, 0),
    )
    section = ReportSection(
        "statement:이익잉여금처분계산서(안)",
        "이익잉여금처분계산서(안)",
        "statement",
        "",
        [ReportBlock("table", "", table, table.location)],
    )
    report = FullReport("s.html", "Co", [section], [])
    check = CheckResult(
        "appropriation-formula-variant",
        "appropriation_formula_check",
        MATCHED,
        "report",
        "",
        "처분계산서 안 산식 검증",
        600,
        600,
        0,
        1,
        "처분계산서 산식이 일치",
        [
            CheckEvidence(
                "차기이월미처분이익잉여금",
                600,
                "statement:이익잉여금처분계산서(안)/table:0/row:3/col:1",
            )
        ],
    )
    out = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [check], out)
    content = out.read_text(encoding="utf-8")

    panel_start = content.index('id="panel-appropriation"')
    assert "처분계산서 안 산식 검증" in content[panel_start:]


def test_html_report_surfaces_broken_evidence_anchor_count(tmp_path):
    from dart_footing_reconciler.report_html import export_audit_reconciliation_html
    from dart_footing_reconciler.checks import CheckResult, CheckEvidence

    report = FullReport("s.html", "Co", [], [])
    check = CheckResult(
        "broken-anchor",
        "total_check",
        MATCHED,
        "note",
        "99",
        "깨진 근거 검증",
        100,
        100,
        0,
        1,
        "일치",
        [CheckEvidence("합계", 100, "note:99/table:7/row:3/col:2")],
    )
    out = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [check], out)
    content = out.read_text(encoding="utf-8")

    assert "근거 연결 실패 1건" in content


def _report_with_multi_table_note():
    t0 = ReportTable(
        0,
        [["구분", "당기"], ["첫 표 금액", "100"]],
        "5. 첫 번째 표",
        SourceLocation("note:5", 0, 0),
    )
    t1 = ReportTable(
        1,
        [["구분", "당기"], ["둘째 표 금액", "200"]],
        "5. 두 번째 표",
        SourceLocation("note:5", 1, 1),
    )
    note = ReportSection(
        "note:5",
        "다중 표 주석",
        "note",
        "5",
        [
            ReportBlock("table", "", t0, t0.location),
            ReportBlock("table", "", t1, t1.location),
        ],
    )
    return FullReport("s.html", "Co", [], [note])


def test_multi_table_note_anchor_target_cell_is_rendered_and_not_broken(tmp_path):
    from dart_footing_reconciler.report_html import export_audit_reconciliation_html
    from dart_footing_reconciler.checks import CheckResult, CheckEvidence

    report = _report_with_multi_table_note()
    check = CheckResult(
        "multi-note-anchor",
        "total_check",
        MATCHED,
        "note",
        "5",
        "두 번째 표 합계 검증",
        200,
        200,
        0,
        1,
        "일치",
        [CheckEvidence("둘째 표 금액", 200, "note:5/table:1/row:1/col:1")],
    )
    out = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [check], out)
    content = out.read_text(encoding="utf-8")

    assert "5. 두 번째 표" in content
    assert 'data-cell="t1r1c1"' in content
    assert 'data-jump-cell="t1r1c1"' in content
    assert "근거 연결 실패 0건" in content


def test_existing_table_anchor_with_out_of_range_row_counts_broken(tmp_path):
    from dart_footing_reconciler.report_html import export_audit_reconciliation_html
    from dart_footing_reconciler.checks import CheckResult, CheckEvidence

    report = _report_with_multi_table_note()
    check = CheckResult(
        "range-broken-anchor",
        "total_check",
        MATCHED,
        "note",
        "5",
        "범위 밖 근거 검증",
        200,
        200,
        0,
        1,
        "일치",
        [CheckEvidence("둘째 표 금액", 200, "note:5/table:1/row:9/col:1")],
    )
    out = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [check], out)
    content = out.read_text(encoding="utf-8")

    assert "근거 연결 실패 1건" in content


def test_prior_year_table_level_sources_do_not_count_as_broken_anchors():
    from dart_footing_reconciler.report_html import _broken_evidence_anchor_count
    from dart_footing_reconciler.checks import CheckResult, CheckEvidence

    report = _report_with_multi_table_note()
    amount_match = CheckResult(
        "prior-amount",
        "prior_year_amount_match",
        MATCHED,
        "prior_year",
        "5",
        "전기 금액 대사",
        100,
        100,
        0,
        1,
        "일치",
        [
            CheckEvidence("current comparative", 100, "note:5/comparative"),
            CheckEvidence("prior current", 100, "note:5/current"),
        ],
    )
    beginning_match = CheckResult(
        "prior-beginning",
        "prior_year_beginning_balance_match",
        MATCHED,
        "prior_year",
        "5",
        "전기 기초 대사",
        100,
        100,
        0,
        1,
        "일치",
        [
            CheckEvidence("prior ending", 100, "note:5/table:0/ending"),
            CheckEvidence("current beginning", 100, "note:5/table:0/beginning"),
        ],
    )

    assert _broken_evidence_anchor_count(report, [amount_match, beginning_match]) == 0


def test_header_row_anchor_counts_broken_when_header_has_no_rendered_cell():
    from dart_footing_reconciler.report_html import _broken_evidence_anchor_count
    from dart_footing_reconciler.checks import CheckResult, CheckEvidence

    report = _report_with_multi_table_note()
    check = CheckResult(
        "header-anchor",
        "total_check",
        MATCHED,
        "note",
        "5",
        "헤더 근거 검증",
        200,
        200,
        0,
        1,
        "일치",
        [CheckEvidence("헤더", 200, "note:5/table:0/row:0/col:1")],
    )

    assert _broken_evidence_anchor_count(report, [check]) == 1


def test_tableless_statement_panel_still_renders_tied_check_summary(tmp_path):
    from dart_footing_reconciler.report_html import export_audit_reconciliation_html
    from dart_footing_reconciler.checks import CheckResult, CheckEvidence

    section = ReportSection(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        [ReportBlock("text", "표 파싱 실패", None, SourceLocation("statement:bs", 0))],
    )
    report = FullReport("s.html", "Co", [section], [])
    check = CheckResult(
        "statement-bs-equation",
        "statement_bs_equation",
        MATCHED,
        "report",
        "bs",
        "재무상태표 기본등식",
        100,
        100,
        0,
        1,
        "일치",
        [CheckEvidence("자산총계", 100, "statement:bs/table:0/row:1/col:1")],
    )
    out = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [check], out)
    content = out.read_text(encoding="utf-8")

    assert "재무상태표 기본등식" in content
    assert "배치되지 않은 검증 0건" in content


def test_missing_section_check_routes_to_other_panel_and_unplaced_count_matches(tmp_path):
    from dart_footing_reconciler.report_html import export_audit_reconciliation_html
    from dart_footing_reconciler.checks import CheckResult, CheckEvidence

    report = FullReport("s.html", "Co", [], [])
    check = CheckResult(
        "missing-note",
        "total_check",
        MATCHED,
        "note",
        "99",
        "없는 주석 합계 검증",
        100,
        100,
        0,
        1,
        "일치",
        [CheckEvidence("합계", 100, "note:99/table:0/row:1/col:1")],
    )
    out = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [check], out)
    content = out.read_text(encoding="utf-8")

    assert "배치되지 않은 검증 1건" in content
    assert 'id="panel-other"' in content
    assert "없는 주석 합계 검증" in content


def test_well_formed_note_check_has_zero_unplaced_count(tmp_path):
    from dart_footing_reconciler.report_html import export_audit_reconciliation_html
    from dart_footing_reconciler.checks import CheckResult, CheckEvidence

    report = _report_with_note()
    check = CheckResult(
        "placed-note",
        "total_check",
        MATCHED,
        "note",
        "8",
        "매출채권 합계 검증",
        100,
        100,
        0,
        1,
        "일치",
        [CheckEvidence("매출채권 합계", 100, "note:8/table:28/row:1/col:1")],
    )
    out = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [check], out)
    content = out.read_text(encoding="utf-8")

    assert "배치되지 않은 검증 0건" in content


def test_evidenceless_note_reference_check_routes_by_note_no(tmp_path):
    from dart_footing_reconciler.report_html import export_audit_reconciliation_html
    from dart_footing_reconciler.checks import CheckResult

    report = _report_with_note()
    check = CheckResult(
        "note-ref-8",
        "note_reference_check",
        MATCHED,
        "report",
        "8",
        "말 주기 주석 참조 검증 — 주석 8",
        None,
        None,
        None,
        0,
        "주석 8 존재하고 내용 확인됨",
        [],
    )
    out = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [check], out)
    content = out.read_text(encoding="utf-8")

    panel_start = content.index('id="panel-note-8"')
    assert "말 주기 주석 참조 검증" in content[panel_start:]
    assert "배치되지 않은 검증 0건" in content


def _report_with_duplicate_note_numbers():
    consolidated_table = ReportTable(
        130,
        [["구분", "당기"], ["연결 표 금액", "100"]],
        "13. 연결 유형자산",
        SourceLocation("note:13", 0, 130),
    )
    separate_table = ReportTable(
        131,
        [["구분", "당기"], ["별도 표 금액", "200"]],
        "13. 별도 유형자산",
        SourceLocation("note:13", 1, 131),
    )
    consolidated = ReportSection(
        "note:13",
        "유형자산",
        "note",
        "13",
        [ReportBlock("table", "", consolidated_table, consolidated_table.location)],
        scope="consolidated",
    )
    separate = ReportSection(
        "note:13",
        "유형자산",
        "note",
        "13",
        [ReportBlock("table", "", separate_table, separate_table.location)],
        scope="separate",
    )
    return FullReport("s.html", "Co", [], [consolidated, separate])


def _separate_note_check() -> CheckResult:
    return CheckResult(
        "separate-note-13",
        "total_check",
        MATCHED,
        "note",
        "13",
        "별도 표 검증",
        200,
        200,
        0,
        1,
        "일치",
        [CheckEvidence("별도 표 금액", 200, "note:13/table:131/row:1/col:1")],
    )


def test_note_reference_check_routes_to_duplicate_note_panel_by_referring_scope(tmp_path):
    from dart_footing_reconciler.checks_note_references import check_note_references
    from dart_footing_reconciler.report_html import export_audit_reconciliation_html

    report = _report_with_duplicate_note_numbers()
    statement = ReportSection(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        [
            ReportBlock(
                "text",
                "별도 재무상태표 금액은 주석 13 참조.",
                None,
                SourceLocation("statement:bs", 0),
            )
        ],
        scope="separate",
    )
    report = FullReport(report.source, report.company, [statement], report.notes)
    checks = check_note_references(report)
    out = tmp_path / "report.html"

    export_audit_reconciliation_html(report, checks, out)
    content = out.read_text(encoding="utf-8")

    separate_panel_start = content.index('id="panel-note-13-separate"')
    consolidated_panel_start = content.index('id="panel-note-13-consolidated"')
    assert "말 주기 주석 참조 검증" in content[separate_panel_start:]
    assert "말 주기 주석 참조 검증" not in content[
        consolidated_panel_start:separate_panel_start
    ]
    assert "배치되지 않은 검증 0건" in content


def test_note_reference_check_with_unresolved_referring_scope_stays_unplaced(tmp_path):
    from dart_footing_reconciler.report_html import export_audit_reconciliation_html

    report = _report_with_duplicate_note_numbers()
    check = CheckResult(
        "note_ref:statement:missing:block0:note13",
        "note_reference_check",
        MATCHED,
        "report",
        "13",
        "말 주기 주석 참조 검증 — 주석 13",
        None,
        None,
        None,
        0,
        "주석 13 존재하고 내용 확인됨",
        [],
    )
    out = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [check], out)
    content = out.read_text(encoding="utf-8")

    assert "배치되지 않은 검증 1건" in content
    assert 'id="panel-other"' in content
    assert "말 주기 주석 참조 검증" in content


def test_note_reference_check_routes_primary_number_to_first_scoped_subnote(tmp_path):
    from dart_footing_reconciler.checks_note_references import check_note_references
    from dart_footing_reconciler.report_html import export_audit_reconciliation_html

    def note(note_no, title, scope, table_index):
        table = ReportTable(
            table_index,
            [["구분", "당기"], [title, "100"]],
            title,
            SourceLocation(f"note:{note_no}", 0, table_index),
        )
        return ReportSection(
            f"note:{note_no}",
            title,
            "note",
            note_no,
            [ReportBlock("table", "", table, table.location)],
            scope=scope,
        )

    statement = ReportSection(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        [
            ReportBlock(
                "text",
                "별도 재무상태표 금액은 주석 5 참조.",
                None,
                SourceLocation("statement:bs", 0),
            )
        ],
        scope="separate",
    )
    report = FullReport(
        "s.html",
        "Co",
        [statement],
        [
            note("5-1", "5-1 연결 금융위험관리", "consolidated", 501),
            note("5-2", "5-2 연결 금융위험관리", "consolidated", 502),
            note("5-1", "5-1 별도 금융위험관리", "separate", 511),
            note("5-2", "5-2 별도 금융위험관리", "separate", 512),
        ],
    )
    out = tmp_path / "report.html"

    export_audit_reconciliation_html(report, check_note_references(report), out)
    content = out.read_text(encoding="utf-8")

    separate_first_panel = content.index('id="panel-note-5-1-separate"')
    separate_second_panel = content.index('id="panel-note-5-2-separate"')
    assert "말 주기 주석 참조 검증" in content[
        separate_first_panel:separate_second_panel
    ]
    assert "배치되지 않은 검증 0건" in content


def test_duplicate_note_numbers_render_unique_panels_and_route_jumps_to_table_owner(tmp_path):
    from dart_footing_reconciler.report_html import export_audit_reconciliation_html

    report = _report_with_duplicate_note_numbers()
    out = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [_separate_note_check()], out)
    content = out.read_text(encoding="utf-8")
    soup = BeautifulSoup(content, "html.parser")

    panel_ids = re.findall(r'<div class="panel(?: [^"]*)?" id="([^"]+)"', content)
    assert len(panel_ids) == len(set(panel_ids))
    assert "panel-note-13-consolidated" in panel_ids
    assert "panel-note-13-separate" in panel_ids
    assert "주석 13 (연결)" in content
    assert "주석 13 (별도)" in content

    jump = soup.find("span", attrs={"data-jump-cell": "t131r1c1"})
    assert jump is not None
    assert jump["data-jump"] == "panel-note-13-separate"
    separate_panel = soup.find(id="panel-note-13-separate")
    assert separate_panel is not None
    assert separate_panel.find(attrs={"data-cell": "t131r1c1"}) is not None
    consolidated_panel = soup.find(id="panel-note-13-consolidated")
    assert consolidated_panel is not None
    assert "별도 표 검증" not in consolidated_panel.get_text(" ", strip=True)
    assert "근거 연결 실패 0건" in content


def test_unique_note_number_keeps_plain_panel_id(tmp_path):
    from dart_footing_reconciler.report_html import export_audit_reconciliation_html

    table = ReportTable(
        13,
        [["구분", "당기"], ["단일 표 금액", "100"]],
        "13. 유형자산",
        SourceLocation("note:13", 0, 13),
    )
    note = ReportSection(
        "note:13",
        "유형자산",
        "note",
        "13",
        [ReportBlock("table", "", table, table.location)],
        scope="consolidated",
    )
    report = FullReport("s.html", "Co", [], [note])
    check = CheckResult(
        "single-note-13",
        "total_check",
        MATCHED,
        "note",
        "13",
        "단일 표 검증",
        100,
        100,
        0,
        1,
        "일치",
        [CheckEvidence("단일 표 금액", 100, "note:13/table:13/row:1/col:1")],
    )
    out = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [check], out)
    content = out.read_text(encoding="utf-8")

    assert 'id="panel-note-13"' in content
    assert 'id="panel-note-13-consolidated"' not in content
    assert 'data-jump="panel-note-13"' in content


def _report_with_duplicate_note_four():
    consolidated_table = ReportTable(
        40,
        [["구분", "당기"], ["연결 금액", "100"]],
        "4. 연결 주석",
        SourceLocation("note:4", 0, 40),
    )
    separate_table = ReportTable(
        41,
        [["구분", "당기"], ["별도 금액", "200"]],
        "4. 별도 주석",
        SourceLocation("note:4", 1, 41),
    )
    consolidated = ReportSection(
        "note:4",
        "주석 4",
        "note",
        "4",
        [ReportBlock("table", "", consolidated_table, consolidated_table.location)],
        scope="consolidated",
    )
    separate = ReportSection(
        "note:4",
        "주석 4",
        "note",
        "4",
        [ReportBlock("table", "", separate_table, separate_table.location)],
        scope="separate",
    )
    return FullReport("s.html", "Co", [], [consolidated, separate])


def test_evidence_less_total_check_uses_check_id_table_hint_for_duplicate_note_panel(tmp_path):
    from dart_footing_reconciler.report_html import export_audit_reconciliation_html

    report = _report_with_duplicate_note_four()
    check = CheckResult(
        "total:4:table41:not_tested",
        "total_check",
        NOT_TESTED,
        "note",
        "4",
        "별도 table 41 coverage",
        None,
        None,
        None,
        1,
        "no reliable total label found",
        [],
    )
    out = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [check], out)
    content = out.read_text(encoding="utf-8")
    soup = BeautifulSoup(content, "html.parser")

    separate_panel = soup.find(id="panel-note-4-separate")
    assert separate_panel is not None
    assert "별도 table 41 coverage" in separate_panel.get_text(" ", strip=True)
    consolidated_panel = soup.find(id="panel-note-4-consolidated")
    assert consolidated_panel is not None
    assert "별도 table 41 coverage" not in consolidated_panel.get_text(" ", strip=True)
    assert "배치되지 않은 검증 0건" in content


def test_evidence_less_duplicate_note_check_without_table_hint_stays_other(tmp_path):
    from dart_footing_reconciler.report_html import export_audit_reconciliation_html

    report = _report_with_duplicate_note_four()
    check = CheckResult(
        "total:4:not_tested",
        "total_check",
        NOT_TESTED,
        "note",
        "4",
        "ambiguous duplicate note coverage",
        None,
        None,
        None,
        1,
        "no reliable total label found",
        [],
    )
    out = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [check], out)
    content = out.read_text(encoding="utf-8")
    soup = BeautifulSoup(content, "html.parser")

    other_panel = soup.find(id="panel-other")
    assert other_panel is not None
    assert "ambiguous duplicate note coverage" in other_panel.get_text(" ", strip=True)
    assert "배치되지 않은 검증 1건" in content


def _report_with_duplicate_balance_sheets():
    consolidated_table = ReportTable(
        220,
        [["구분", "당기"], ["연결 자산총계", "100"]],
        "연결 재무상태표",
        SourceLocation("statement:bs", 0, 220),
    )
    separate_table = ReportTable(
        221,
        [["구분", "당기"], ["별도 자산총계", "200"]],
        "별도 재무상태표",
        SourceLocation("statement:bs", 1, 221),
    )
    consolidated = ReportSection(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        [ReportBlock("table", "", consolidated_table, consolidated_table.location)],
        scope="consolidated",
    )
    separate = ReportSection(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        [ReportBlock("table", "", separate_table, separate_table.location)],
        scope="separate",
    )
    return FullReport("s.html", "Co", [consolidated, separate], [])


def _separate_balance_sheet_check() -> CheckResult:
    return CheckResult(
        "separate-bs-equation",
        "statement_bs_equation",
        MATCHED,
        "report",
        "bs",
        "별도 재무상태표 기본등식",
        200,
        200,
        0,
        1,
        "일치",
        [CheckEvidence("별도 자산총계", 200, "statement:bs/table:221/row:1/col:1")],
    )


def test_duplicate_statement_kinds_render_unique_panels_and_route_jumps_to_table_owner(tmp_path):
    from dart_footing_reconciler.report_html import export_audit_reconciliation_html

    report = _report_with_duplicate_balance_sheets()
    out = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [_separate_balance_sheet_check()], out)
    content = out.read_text(encoding="utf-8")
    soup = BeautifulSoup(content, "html.parser")

    panel_ids = re.findall(r'<div class="panel(?: [^"]*)?" id="([^"]+)"', content)
    assert len(panel_ids) == len(set(panel_ids))
    assert "panel-bs-consolidated" in panel_ids
    assert "panel-bs-separate" in panel_ids
    assert "재무상태표 (연결)" in content
    assert "재무상태표 (별도)" in content

    jump = soup.find("span", attrs={"data-jump-cell": "t221r1c1"})
    assert jump is not None
    assert jump["data-jump"] == "panel-bs-separate"
    separate_panel = soup.find(id="panel-bs-separate")
    assert separate_panel is not None
    assert separate_panel.find(attrs={"data-cell": "t221r1c1"}) is not None
    assert "별도 재무상태표 기본등식" in separate_panel.get_text(" ", strip=True)
    consolidated_panel = soup.find(id="panel-bs-consolidated")
    assert consolidated_panel is not None
    assert "별도 재무상태표 기본등식" not in consolidated_panel.get_text(" ", strip=True)
    assert "배치되지 않은 검증 0건" in content
    assert "근거 연결 실패 0건" in content


def test_unique_statement_kind_keeps_plain_panel_id(tmp_path):
    from dart_footing_reconciler.report_html import export_audit_reconciliation_html

    table = ReportTable(
        220,
        [["구분", "당기"], ["자산총계", "100"]],
        "재무상태표",
        SourceLocation("statement:bs", 0, 220),
    )
    section = ReportSection(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        [ReportBlock("table", "", table, table.location)],
        scope="consolidated",
    )
    report = FullReport("s.html", "Co", [section], [])
    check = CheckResult(
        "single-bs-equation",
        "statement_bs_equation",
        MATCHED,
        "report",
        "bs",
        "재무상태표 기본등식",
        100,
        100,
        0,
        1,
        "일치",
        [CheckEvidence("자산총계", 100, "statement:bs/table:220/row:1/col:1")],
    )
    out = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [check], out)
    content = out.read_text(encoding="utf-8")

    assert 'id="panel-bs"' in content
    assert 'id="panel-bs-consolidated"' not in content
    assert 'data-jump="panel-bs"' in content


def test_evidence_enrichment_does_not_change_status_counts():
    from collections import Counter
    from pathlib import Path
    from dart_footing_reconciler.document import parse_full_report
    from dart_footing_reconciler.check_pipeline import assemble_report_checks
    fx = Path("out/corpus/run_2026-06-06-inveni-one/raw/inveni_2024_20250310000926.html")
    checks = assemble_report_checks(parse_full_report(fx, company="INVENI"), None, tolerance=1)
    counts = Counter(c.status for c in checks)
    for c in checks:
        if c.expected is not None and c.actual is not None and c.difference is not None:
            assert c.actual - c.expected == c.difference
    assert sum(counts.values()) == len(checks)


# ── Finding 1: worst-state per-account badge ─────────────────────────────────

def test_statement_row_shows_worst_state_when_multiple_checks():
    from dart_footing_reconciler.report_html import _render_statement_panel
    from dart_footing_reconciler.checks import CheckResult, CheckEvidence, MATCHED
    from dart_footing_reconciler.document import ReportSection, ReportBlock, ReportTable, SourceLocation, FullReport
    t = ReportTable(0, [["구분", "당기"], ["유형자산", "100"]], "재무상태표", SourceLocation("statement:bs", 0, 0))
    sec = ReportSection("statement:bs", "재무상태표", "statement", "", [ReportBlock("table", "", t, t.location)])
    matched = CheckResult("m", "t", MATCHED, "report", "", "ok", 100, 100, 0, 1, "ok",
                          [CheckEvidence("유형자산", 100, "statement:bs/table:0/row:1/col:1")])
    gap = CheckResult("g", "t", UNEXPLAINED_GAP, "report", "", "gap", 100, 90, -10, 1, "gap",
                      [CheckEvidence("유형자산", 90, "statement:bs/table:0/row:1/col:1")])
    html = _render_statement_panel(sec, [matched, gap], panel_id="panel-bs", label="재무상태표",
                                   report=FullReport("s", "Co", [sec], []))
    assert "검토필요" in html
    assert "검증완료" not in html.split("유형자산")[0]


def test_explainable_gap_uses_distinct_badge_and_statement_row_state(tmp_path):
    from dart_footing_reconciler.report_html import export_audit_reconciliation_html

    table = _t([["구분", "당기"], ["유형자산", "100"]])
    report = _t_report(table)
    explainable = CheckResult(
        "explainable",
        "test",
        EXPLAINABLE_GAP,
        "report",
        "",
        "설명된 차이 검증",
        100,
        90,
        -10,
        1,
        "조정 근거가 확인됨",
        [
            CheckEvidence(
                "유형자산",
                90,
                "statement:bs/table:0/row:1/col:1",
            )
        ],
    )
    output = tmp_path / "explainable.html"

    export_audit_reconciliation_html(report, [explainable], output)
    html = output.read_text(encoding="utf-8")

    assert 'class="verified-exp"' in html
    assert '<span class="acct-state as-exp">설명차이</span>' in html
    assert '<span class="badge badge-exp">△ 설명된 차이</span>' in html
    assert 'class="nav-badge nb-exp">△ 1</span>' in html
    assert 'class="callout exp">△ 조정 근거가 확인됨</div>' in html
    assert "attn-row" not in html


@pytest.mark.parametrize(
    ("first_status", "second_status", "expected_class"),
    [
        (MATCHED, EXPLAINABLE_GAP, "verified-exp"),
        (EXPLAINABLE_GAP, PARSE_UNCERTAIN, "verified-uncertain"),
        (EXPLAINABLE_GAP, UNEXPLAINED_GAP, "verified-warn"),
    ],
)
def test_statement_row_status_priority_is_order_independent(
    first_status,
    second_status,
    expected_class,
):
    from dart_footing_reconciler.report_html import _render_statement_panel

    table = _t([["구분", "당기"], ["유형자산", "100"]])
    report = _t_report(table)
    section = report.statements[0]

    def result(check_id, status):
        return CheckResult(
            check_id,
            "test",
            status,
            "report",
            "",
            check_id,
            100,
            100,
            0,
            1,
            status,
            [
                CheckEvidence(
                    "유형자산",
                    100,
                    "statement:bs/table:0/row:1/col:1",
                )
            ],
        )

    for statuses in (
        (first_status, second_status),
        (second_status, first_status),
    ):
        html = _render_statement_panel(
            section,
            [result("first", statuses[0]), result("second", statuses[1])],
            panel_id="panel-bs",
            label="재무상태표",
            report=report,
        )
        row = BeautifulSoup(html, "html.parser").select_one(
            'tr[data-check-row="1"]'
        )
        assert row is not None
        assert expected_class in row.get("class", [])
