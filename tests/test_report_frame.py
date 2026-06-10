from html import escape

from dart_footing_reconciler.checks import CheckEvidence, CheckResult
from dart_footing_reconciler.document import FullReport, ReportBlock, ReportSection, ReportTable, SourceLocation
from dart_footing_reconciler.report_frame import (
    CANONICAL_STATEMENT_ORDER,
    build_report_frame,
    check_layer,
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

    expected_kinds = [kind for kind in CANONICAL_STATEMENT_ORDER if kind != "appropriation"]
    assert [section.kind for section in frame.statement_sections] == expected_kinds
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


def test_report_frame_preserves_parsed_note_order_not_numeric_note_order():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section("note:20", "먼저 나온 주석", "note", "20", _table("note:20", 0, "20. 먼저 나온 주석")),
            _section("note:3", "나중에 나온 주석", "note", "3", _table("note:3", 1, "3. 나중에 나온 주석")),
        ],
    )

    frame = build_report_frame(report, [])

    assert [note.note_no for note in frame.notes] == ["20", "3"]


def test_report_frame_classifies_statement_note_layer():
    check = CheckResult(
        "fs-note",
        "fs_note_match",
        "matched",
        "report",
        "11",
        "FS-note match",
        100,
        100,
        0,
        1,
        "matched",
        [
            CheckEvidence("재무상태표", 100, "statement:bs/table:0/row:1/col:1"),
            CheckEvidence("주석", 100, "note:11/table:0/row:1/col:1"),
        ],
    )

    assert check_layer(check) == "statement_note"


def test_report_frame_classifies_note_internal_layer():
    check = CheckResult(
        "total",
        "total_check",
        "matched",
        "table",
        "11",
        "주석 합계 검증",
        100,
        100,
        0,
        1,
        "matched",
        [CheckEvidence("합계", 100, "note:11/table:0/row:1/col:1")],
    )

    assert check_layer(check) == "note_internal"


def test_html_report_uses_evidence_cockpit_app_shell() -> None:
    bs_table = _table("statement:bs", 0, "재무상태표")
    note_table = _table("note:11", 1, "11. 유형자산")
    report = FullReport(
        "sample.html",
        "Sample Co",
        [_section("statement:bs", "재무상태표", "statement", "", bs_table)],
        [_section("note:11", "유형자산", "note", "11", note_table)],
    )

    html = render_audit_reconciliation_html(report, [])

    assert '<body data-cockpit-profile="evidence_cockpit" data-cockpit-shell="side-app">' in html
    assert '<a href="#summary" aria-current="page">요약</a>' in html
    assert '<a href="#financial-position">진행현황</a>' in html
    assert '<a href="#review-queue" data-view-link="review">주의 필요</a>' in html
    assert '<a href="#notes">근거</a>' in html
    assert '<a href="#review-queue" data-view-link="review">다음 행동</a>' in html
    for label in ("현재 상태", "왜 중요한가", "다음 행동"):
        assert label in html
    assert '<section class="section-brief" aria-label="감사 조서 방향">' in html
    assert "감사 대사" in html


def test_html_report_applies_cockpit_design_kit_visual_contract() -> None:
    html = render_audit_reconciliation_html(FullReport("sample.html", "Sample Co", [], []), [])

    assert '<aside class="report-sidebar side-nav">' in html
    assert 'data-switcher="main"' in html
    assert 'data-panel="working"' in html
    assert 'data-panel="review"' in html
    assert "--accent: #0066ff;" in html
    assert "--surface-2: #f4f4f5;" in html
    assert "--border: #e1e2e4;" in html
    assert ".section-brief { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 12px 0; }" in html
    assert ".section-brief article { background: var(--surface); border: 1px solid var(--border); border-left: 3px solid var(--accent); border-radius: 12px;" in html
    assert ".report-nav a[aria-current] { color: var(--accent); border-color: var(--accent); background: var(--accent-dim); font-weight: 800; }" in html


def test_html_statement_and_note_tables_use_compact_fixed_layout() -> None:
    html = render_audit_reconciliation_html(FullReport("sample.html", "Sample Co", [], []), [])

    assert ".source-table { width: 100%; min-width: 100%; table-layout: fixed; font-size: 11px; }" in html
    assert ".statement-validation-table { width: 100%; min-width: 100%; table-layout: fixed; font-size: 11px; }" in html
    assert ".statement-validation-status { width: 18%; max-width: 190px; white-space: normal; }" in html
    assert ".statement-validation-note { width: 22%; max-width: 240px; white-space: normal; }" in html
    assert ".statement-validation-reason, .leadsheet-note-display { display: -webkit-box; -webkit-line-clamp: 2;" in html
    assert ".raw-note-table { width: 100%; min-width: 100%; table-layout: fixed; border-collapse: collapse; font-size: 11px; }" in html
    assert ".frame-check-table { width: 100%; min-width: 100%; table-layout: fixed; font-size: 11px; }" in html
    assert ".statement-validation-table { width: max-content;" not in html
    assert ".raw-note-table { width: max-content;" not in html
    assert ".source-table { min-width: 620px; }" not in html


def test_html_report_uses_swarmlens_objective_cockpit_reference() -> None:
    checks = [
        CheckResult(
            "bs-note",
            "primary_balance_reconciliation",
            "unexplained_gap",
            "statement",
            "11",
            "재무상태표 유형자산",
            1_000,
            900,
            100,
            0,
            "본문 금액과 주석 장부금액이 다릅니다.",
            [CheckEvidence("재무상태표 유형자산", 1_000, "statement:bs/table:0/row:1/col:1")],
        ),
        CheckResult(
            "note-total",
            "total_check",
            "matched",
            "note",
            "11",
            "유형자산 주석 합계",
            1_000,
            1_000,
            0,
            0,
            "구성항목 합계와 일치합니다.",
            [CheckEvidence("합계", 1_000, "note:11/table:0/row:5/col:1")],
        ),
        CheckResult(
            "cf-note",
            "cashflow_reconciliation",
            "explainable_gap",
            "cashflow",
            "11",
            "유형자산 취득",
            700,
            800,
            -100,
            0,
            "비현금거래 차이내역 확인 필요",
            [CheckEvidence("현금흐름표 유형자산 취득", 800, "statement:cf/table:0/row:8/col:1")],
        ),
        CheckResult(
            "note-layout",
            "note_layout_formula_check",
            "parse_uncertain",
            "note",
            "11",
            "유형자산 변동표 구조",
            None,
            None,
            None,
            0,
            "합계 행과 기간 열을 먼저 해석해야 합니다.",
            [],
        ),
    ]

    html = render_audit_reconciliation_html(FullReport("sample.html", "Sample Co", [], []), checks)

    assert 'data-cockpit-ref="swarmlens-objective-cockpit"' in html
    assert "검증 목표 Cockpit" in html
    for label in ("원문 수집", "시멘틱 매핑", "하네스 실행", "검토 큐"):
        assert label in html
    for objective in ("본문-주석 대사", "주석 내부 검산", "현금흐름표-주석", "표 구조 해석"):
        assert objective in html
    assert "경보 우선순위" in html
    assert "중요도 = 차이 + 구조 + 근거" in html


def test_html_report_sidebar_review_links_activate_review_panel() -> None:
    html = render_audit_reconciliation_html(FullReport("sample.html", "Sample Co", [], []), [])

    assert 'href="#financial-position">진행현황</a>' in html
    assert 'href="#notes">근거</a>' in html
    assert 'href="#review-queue" data-view-link="review"' in html
    assert 'href="#coverage" data-view-link="review"' in html
    assert 'const navLinks = [...document.querySelectorAll(\'.report-nav a[href^="#"]\')];' in html
    assert 'target.closest("[data-view-panel]")' in html
    assert "setView(targetPanel.dataset.viewPanel);" in html
    assert 'syncViewForHash(window.location.hash || "#summary", { scroll: Boolean(window.location.hash) });' in html
    assert 'window.addEventListener("hashchange", () => syncViewForHash(window.location.hash || "#summary"));' in html


def test_html_report_sidebar_aria_current_is_updated_from_hash() -> None:
    html = render_audit_reconciliation_html(FullReport("sample.html", "Sample Co", [], []), [])

    assert 'aria-current="page"' in html
    assert "function setCurrentNav(hash, activeLink = null)" in html
    assert "function canonicalNavLink(hash)" in html
    assert 'activeLink?.getAttribute("href") === activeHash' in html
    assert 'const selected = link === currentLink;' in html
    assert 'link.setAttribute("aria-current", "location");' in html
    assert 'link.removeAttribute("aria-current");' in html
    assert "activeLink: link" in html
    assert 'if (link.getAttribute("href") === activeHash) {' not in html


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
    note_panel = html[html.index('id="note-panel-note-1-11"') :]

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
    note_panel = html[html.index('id="note-panel-note-1-11"') :]
    comparison_grid = note_panel[note_panel.index('class="note-comparison-grid"') :]
    comparison_grid = comparison_grid[: comparison_grid.index('class="note-document-flow"')]

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
    note_panel = html[html.index('id="note-panel-note-1-11"') :]
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
    note_panel = html[html.index('id="note-panel-note-1-11"') :]

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
    long_panel = html[html.index('id="note-panel-note-1-1"') : html.index('id="note-panel-note-2-2"')]
    short_panel = html[html.index('id="note-panel-note-2-2"') :]

    assert "<details" in long_panel
    assert "주석 원문 문단 전체" in long_panel
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
    note_panel = html[html.index('id="note-panel-note-1-11"') :]
    total_panel = note_panel[note_panel.index("<h4>합계 검증</h4>") :]

    assert "합계 검증" in total_panel
    assert "유형자산 합계 검증" in total_panel
    assert "연결된 자동 검증 결과가 없습니다" not in total_panel[: total_panel.index("</div>", total_panel.index("frame-check-group"))]


def test_total_issue_cells_use_point_signal_not_risk_soft_fill():
    note_table = ReportTable(
        0,
        [["구분", "토지", "건물", "합계"], ["기초", "600", "400", "900"]],
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
        [CheckEvidence("주석 11 합계", 900, "note:11/table:0/row:1/col:3")],
    )

    html = render_audit_reconciliation_html(report, [check])

    assert "total-issue-cell" in html
    assert "background: var(--risk-soft)" not in html
    assert ".total-issue-cell { position: relative; outline: 2px solid var(--risk);" in html
    assert "box-shadow: inset 3px 0 0 var(--risk);" in html
    assert ".total-issue-cell::before" in html


def test_note_validation_is_embedded_in_source_table_with_technical_details_collapsed():
    note_table = ReportTable(
        0,
        [["구분", "합계"], ["기말 장부금액", "900"]],
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
        "fs-note-ppe",
        "fs_note_match",
        "unexplained_gap",
        "report",
        "11",
        "유형자산 FS to note match",
        1_000,
        900,
        -100,
        0,
        "financial statement amount does not agree to note amount",
        [
            CheckEvidence("재무상태표 유형자산", 1_000, "statement:bs/table:0/row:1/col:1"),
            CheckEvidence("주석 11 유형자산", 900, "note:11/table:0/row:1/col:1"),
        ],
    )

    html = render_audit_reconciliation_html(report, [check])
    note_panel = html[html.index('id="note-panel-note-1-11"') :]
    note_panel = note_panel[: note_panel.index("</section>")]

    assert "validation-source-cell" in note_panel
    assert "검증 결과" in note_panel
    assert "재무제표 본문-주석" in note_panel
    assert '<details class="validation-technical-details">' in note_panel
    assert '<table class="frame-check-table">' in note_panel
    assert note_panel.index("validation-source-cell") < note_panel.index(
        "validation-technical-details"
    )


def test_note_internal_panel_hides_intro_only_not_tested_rows():
    long_heading = (
        '1. 지배기업의 개요 (연결) 삼성SDI 주식회사(이하 "지배기업")는 1970년 1월 20일 '
        "자본금 200백만원으로 설립되었으며, 경기도 용인시 기흥구 공세로 150-20에 본사를 "
        "두고 있습니다."
    )
    note_table = ReportTable(
        0,
        [["사업장", "소재지"], ["본사", "용인"]],
        long_heading,
        SourceLocation("note:1", 0, 0),
    )
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [_section("note:1", "지배기업의 개요", "note", "1", note_table)],
    )
    check = CheckResult(
        "total-note-1-not-tested",
        "total_check",
        "not_tested",
        "note",
        "1",
        long_heading,
        None,
        None,
        None,
        0,
        "no reliable total label found",
        [],
    )

    html = render_audit_reconciliation_html(report, [check])

    assert "검증대상 없음" in html
    assert f"<td>{escape(long_heading)}</td>" not in html
    assert "검토 상태와 원천 근거 보완 필요 여부가 남아 있음." not in html


def test_note_table_card_summary_compacts_long_intro_heading():
    long_heading = (
        '1. 지배기업의 개요 (연결) 삼성SDI 주식회사(이하 "지배기업")는 1970년 1월 20일 '
        "자본금 200백만원으로 설립되었습니다."
    )
    note_table = ReportTable(
        0,
        [["사업장", "소재지"], ["본사", "용인"]],
        long_heading,
        SourceLocation("note:1", 0, 0),
    )
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [_section("note:1", "지배기업의 개요", "note", "1", note_table)],
    )

    html = render_audit_reconciliation_html(report, [])

    assert "<span>지배기업의 개요 (연결)</span>" in html
    assert f"<span>{escape(long_heading.removeprefix('1. '))}</span>" not in html
    assert f'<span class="raw-note-heading">{escape(long_heading)}</span>' in html


def test_note_internal_gap_and_structure_rows_use_compact_titles_and_status_logic():
    long_title = (
        "6. 영업부문 (연결) 3) 당기말 현재 고객과의 계약으로 인한 계약부채와 전기말 "
        "계약부채 중 당기에 수익으로 인식한 금액은 다음과 같습니다."
    )
    note_table = ReportTable(
        0,
        [["구분", "당기"], ["계약부채", "900"]],
        "6. 영업부문 (연결)",
        SourceLocation("note:6", 0, 0),
    )
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [_section("note:6", "영업부문", "note", "6", note_table)],
    )
    checks = [
        CheckResult(
            "total-note-6-gap",
            "total_check",
            "explainable_gap",
            "note",
            "6",
            long_title,
            1_000,
            900,
            -100,
            0,
            "차이내역 확인 필요",
            [CheckEvidence("주석 6 계약부채", 900, "note:6/table:0/row:1/col:1")],
        ),
        CheckResult(
            "total-note-6-structure",
            "total_check",
            "parse_uncertain",
            "note",
            "6",
            long_title,
            None,
            None,
            None,
            0,
            "no reliable total label found",
            [],
        ),
    ]

    html = render_audit_reconciliation_html(report, checks)

    assert "차이내역 확인 필요" in html
    assert "표 구조 해석 필요" in html
    assert "주석 6 · 영업부문 (연결)" in html
    assert f"<td>{escape(long_title)}</td>" not in html


def test_note_internal_total_gap_action_is_specific_not_fallback_text():
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
        "total-note-11-gap",
        "total_check",
        "unexplained_gap",
        "note",
        "11",
        "유형자산 합계 검증",
        1_000,
        900,
        -100,
        0,
        "row total does not agree",
        [CheckEvidence("주석 11 합계", 900, "note:11/table:0/row:3/col:1")],
    )

    html = render_audit_reconciliation_html(report, [check])

    assert "합계 차이 확인 필요" in html
    assert "표시 소계/합계와 구성항목 합계를 원문 표에서 재계산하세요." in html
    assert "검토 상태와 원천 근거 보완 필요 여부가 남아 있음." not in html


def test_statement_validation_is_embedded_in_source_table_not_separate_panel():
    statement_table = ReportTable(
        0,
        [["구분", "당기"], ["유형자산", "1,000"]],
        "재무상태표",
        SourceLocation("statement:bs", 0, 0),
    )
    report = FullReport(
        "sample.html",
        "Sample Co",
        [_section("statement:bs", "재무상태표", "statement", "", statement_table)],
        [],
    )
    check = CheckResult(
        "fs-note-ppe",
        "primary_balance_reconciliation",
        "unexplained_gap",
        "report",
        "11",
        "유형자산 FS to note match",
        1_000,
        900,
        100,
        0,
        "financial statement amount does not agree to note amount",
        [CheckEvidence("재무상태표 유형자산", 1_000, "statement:bs/table:0/row:1/col:1")],
    )

    html = render_audit_reconciliation_html(report, [check])
    section = html[html.index('id="financial-position"') : html.index('id="income-statement"')]
    source_table = section[section.index('<table class="source-table statement-validation-table">') :]
    source_table = source_table[: source_table.index("</table>")]

    assert "statement-validation-cell" in source_table
    assert "재무제표-주석 대사" in source_table
    assert "실질 차이 확인 필요" in source_table
    assert "차이 100" in source_table
    assert "검증 패널" not in section
    assert "statement-row-verification-table" not in section


def test_statement_validation_cell_shows_compact_match_numbers_not_formula_table():
    statement_table = ReportTable(
        0,
        [["구분", "당기"], ["유형자산의 처분", "800"]],
        "현금흐름표",
        SourceLocation("statement:cfs", 0, 0),
    )
    report = FullReport(
        "sample.html",
        "Sample Co",
        [_section("statement:cfs", "현금흐름표", "statement", "", statement_table)],
        [],
    )
    check = CheckResult(
        "cf-note",
        "cashflow_reconciliation",
        "matched",
        "note",
        "13",
        "유형자산 처분",
        800,
        799,
        -1,
        0,
        "주석 처분 장부금액 799 = 799; 현금흐름표 유형자산의 처분 800; 차이 1; 현금흐름표 금액과 직접 대사됨",
        [CheckEvidence("현금흐름표 유형자산 처분", 800, "statement:cfs/table:0/row:1/col:1")],
    )

    html = render_audit_reconciliation_html(report, [check])
    section = html[html.index('id="cash-flows"') : html.index('id="notes"')]
    source_table = section[section.index('<table class="source-table statement-validation-table">') :]
    status_cell = source_table[source_table.index('class="statement-validation-status"') :]
    status_cell = status_cell[: status_cell.index("</td>")]

    assert "본문 800 ↔ 주석/산식 799" in status_cell
    assert "차이 (1)" in status_cell
    assert '<table class="formula-table">' not in status_cell
    assert "주석 처분 장부금액 799 = 799" not in status_cell


def test_note_table_without_checks_is_labeled_as_no_candidate_not_error():
    note_table = ReportTable(
        0,
        [["구분", "당기"], ["보고부문", "전지"]],
        "영업부문",
        SourceLocation("note:6", 0, 0),
    )
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [_section("note:6", "영업부문", "note", "6", note_table)],
    )

    html = render_audit_reconciliation_html(report, [])
    note_panel = html[html.index('id="note-panel-note-1-6"') :]
    note_panel = note_panel[: note_panel.index("</section>")]

    assert "검증 후보 없음" in note_panel
    assert "주석 검증 대상 없음" not in note_panel
    assert "자동화 보완 필요" not in note_panel
    assert "이 주석 표에 배치된 자동 검증 결과가 없습니다." not in note_panel


def test_scope_groups_render_in_company_report_order():
    """연결/별도 스코프가 모두 있으면 그룹별로 본문→주석 순서로 렌더링됨."""
    def scoped_statement(table_index, scope):
        table = ReportTable(
            table_index,
            [["구분", "당기"], ["자산총계", "1,000"]],
            "재무상태표",
            SourceLocation("statement:재무상태표", 0, table_index),
        )
        return ReportSection(
            "statement:재무상태표",
            "재무상태표",
            "statement",
            "",
            [ReportBlock("table", "", table, table.location)],
            scope,
        )

    def scoped_note(table_index, scope):
        table = ReportTable(
            table_index,
            [["구분", "당기"], ["기말", "1,000"]],
            "1. 일반사항",
            SourceLocation("note:1", 0, table_index),
        )
        return ReportSection(
            "note:1",
            "일반사항",
            "note",
            "1",
            [ReportBlock("table", "", table, table.location)],
            scope,
        )

    report = FullReport(
        "sample.html",
        "Sample Co",
        [scoped_statement(0, "consolidated"), scoped_statement(1, "separate")],
        [scoped_note(2, "consolidated"), scoped_note(3, "separate")],
    )
    html = render_audit_reconciliation_html(report, [])

    assert 'data-report-scope="consolidated"' in html
    assert html.count('class="scope-group"') == 2
    assert "연결 재무제표 및 주석" in html
    assert "별도 재무제표 및 주석" in html
    assert 'id="financial-position"' in html
    assert 'id="financial-position-separate"' in html
    assert 'id="notes"' in html
    assert 'id="notes-separate"' in html
    # 본문이 주석보다 먼저 (각 그룹 내)
    consolidated = html[html.index("연결 재무제표 및 주석") : html.index("별도 재무제표 및 주석")]
    assert consolidated.index('id="financial-position"') < consolidated.index('id="notes"')
