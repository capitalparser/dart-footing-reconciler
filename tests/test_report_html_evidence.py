"""Per-account verification-state badge tests for _render_table_rows."""
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
from dart_footing_reconciler.report_html import _render_sidebar, _render_table_rows, _row_result_map_for_table
from dart_footing_reconciler.review_backlog import ReviewBacklog


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


def test_note_nav_badge_counts_statement_check_evidence_pointing_to_note_table():
    note_table = ReportTable(
        19,
        [["구분", "공시금액"], ["기타유동금융부채", "17,600,000"]],
        "19. 기타금융부채",
        SourceLocation("note:19", 0, 19),
    )
    note = ReportSection(
        "note:19",
        "기타금융부채",
        "note",
        "19",
        [ReportBlock("table", "", note_table, note_table.location)],
    )
    report = FullReport("s.html", "Co", [], [note])
    result = CheckResult(
        "bs-note-19",
        "fs_note_ref_amount_match",
        MATCHED,
        "report",
        "19",
        "기타유동금융부채 본문-주석 금액 대사",
        17_600_000,
        17_600_000,
        0,
        1,
        "일치",
        [
            CheckEvidence("본문", 17_600_000, "statement:bs/table:0/row:1/col:1"),
            CheckEvidence("주석", 17_600_000, "note:19/table:19/row:1/col:1"),
        ],
    )

    html = _render_sidebar(report, [result], {}, ReviewBacklog(()))

    assert 'data-target="panel-note-19"' in html
    assert "19. 기타금융부채" in html
    assert '<span class="nav-badge nb-ok">✓</span>' in html


def test_humanize_source_resolves_note_text_block_without_internal_terms():
    from dart_footing_reconciler.report_html import _humanize_source

    note = ReportSection(
        "note:9",
        "기타자산",
        "note",
        "9",
        [ReportBlock("text", "수선충당예치금 설명", None, SourceLocation("note:9", 0))],
    )
    report = FullReport("s.html", "Co", [], [note])

    out = _humanize_source(report, "note:9:block2")

    assert out == "주석9 · 본문 문단 3"
    assert "note:" not in out
    assert "block" not in out


def test_humanize_source_resolves_note_period_tags_without_internal_terms():
    from dart_footing_reconciler.report_html import _humanize_source

    note = ReportSection(
        "note:11",
        "유형자산",
        "note",
        "11",
        [ReportBlock("text", "당기 유형자산", None, SourceLocation("note:11", 0))],
    )
    report = FullReport("s.html", "Co", [], [note])

    assert _humanize_source(report, "note:11/current") == "주석11 · 당기"
    assert _humanize_source(report, "prior:note:11/current") == "전기 보고서 주석11 · 당기"
    assert _humanize_source(report, "prior:note:11/table:3/ending") == "전기 보고서 주석11 · 기말"
    comparative = _humanize_source(report, "note:11/comparative")

    assert comparative == "주석11 · 비교기간"
    assert "note:" not in comparative
    assert "comparative" not in comparative


def test_table_rows_show_per_account_state_and_mich_for_uncovered():
    table = _t([["구분", "당기"], ["유형자산", "100"], ["재고자산", "50"], ["자산", ""]])
    report = _t_report(table)
    html = _render_table_rows(table, {1: _chk(MATCHED)}, show_state=True, report=report)
    assert "검증완료" in html          # row 1 has a matched check
    assert "미검증" not in html        # rows outside validation scope stay blank
    assert html.count("acct-state") == 1   # group header and uncovered rows get no badge


def test_statement_gap_badge_uses_red_attention_label():
    table = _t([["구분", "당기"], ["재고자산", "100"]])
    gap = CheckResult(
        "gap",
        "fs_note_match",
        UNEXPLAINED_GAP,
        "report",
        "7",
        "재고자산 대사",
        100,
        90,
        -10,
        1,
        "차이",
        [CheckEvidence("재고자산", 100, "statement:bs/table:0/row:1/col:1")],
    )

    html = _render_table_rows(table, {1: gap}, show_state=True)

    assert '<span class="acct-state as-warn">확인필요</span>' in html
    assert "검토필요" not in html


def test_status_badges_distinguish_explained_uncertain_and_not_tested():
    from dart_footing_reconciler.report_html import _status_to_badge_class, _status_to_badge_label

    assert _status_to_badge_class(EXPLAINABLE_GAP) == "badge-exp"
    assert _status_to_badge_label(EXPLAINABLE_GAP) == "설명차이"
    assert _status_to_badge_label(UNEXPLAINED_GAP) == "확인필요"
    assert _status_to_badge_label(PARSE_UNCERTAIN) == "파싱불확실"
    assert _status_to_badge_label(NOT_TESTED) == "미검증"


def test_unverified_statement_row_opens_inline_review_hint():
    table = _t([["구분", "당기"], ["재고자산 (주7)", "50"]])
    report = _t_report(table)
    html = _render_table_rows(table, {}, id_prefix="panel-bs", show_state=True, report=report)

    assert "panel-bs-unverified-1" in html
    assert "직접 금액대사는 아직 연결되지 않았습니다" in html
    assert "주석번호 확인: 주7" in html


def test_statement_row_prefers_own_note_match_over_subtotal_component():
    table = _t([["구분", "당기"], ["유동자산", "300"], ["재고자산 (주7)", "50"]])
    subtotal = CheckResult(
        "subtotal",
        "statement_subtotal",
        MATCHED,
        "report",
        "cross_statement",
        "재무상태표 유동자산 본문 소계",
        300,
        300,
        0,
        1,
        "소계 일치",
        [
            CheckEvidence("유동자산", 300, "statement:bs/table:0/row:1/col:1", role="total"),
            CheckEvidence("재고자산 (주7)", 50, "statement:bs/table:0/row:2/col:1", role="component"),
        ],
    )
    note_match = CheckResult(
        "inventory-note",
        "fs_note_match",
        MATCHED,
        "report",
        "7",
        "재고자산 FS to note match",
        50,
        50,
        0,
        1,
        "본문 금액과 주석 금액 일치",
        [
            CheckEvidence("재고자산 (주7)", 50, "statement:bs/table:0/row:2/col:1"),
            CheckEvidence("주석 7 재고자산", 50, "note:7/table:7/row:1/col:1"),
        ],
    )

    row_map = _row_result_map_for_table([subtotal, note_match], table)

    assert 1 not in row_map
    assert row_map[2].check_type == "fs_note_match"


def test_statement_subtotal_is_marked_in_table_not_bound_to_sidebar():
    table = _t([["구분", "당기"], ["유동자산", "300"], ["재고자산", "50"], ["현금", "250"]])
    subtotal = CheckResult(
        "subtotal",
        "statement_subtotal",
        MATCHED,
        "report",
        "cross_statement",
        "재무상태표 유동자산 본문 소계",
        300,
        300,
        0,
        1,
        "소계 일치",
        [
            CheckEvidence("유동자산", 300, "statement:bs/table:0/row:1", role="total"),
            CheckEvidence("재고자산", 50, "statement:bs/table:0/row:2", role="component"),
            CheckEvidence("현금", 250, "statement:bs/table:0/row:3", role="component"),
        ],
    )

    html = _render_table_rows(
        table,
        _row_result_map_for_table([subtotal], table),
        show_state=True,
        total_results=[subtotal],
    )

    marker = '<tr class="total-only-row total-mark total-ok"'
    assert marker in html
    total_row = html.split(marker, 1)[1].split("</tr>", 1)[0]
    assert "onclick=" not in total_row
    assert "검증완료" in html


def test_unverified_statement_row_shows_referenced_note_review_summary():
    table = _t([["구분", "당기"], ["재고자산 (주7)", "50"]])
    note_table = ReportTable(
        7,
        [["구분", "당기"], ["재고자산", "50"]],
        "7. 재고자산",
        SourceLocation("note:7", 0, 7),
    )
    note = ReportSection(
        "note:7",
        "재고자산",
        "note",
        "7",
        [ReportBlock("table", "", note_table, note_table.location)],
        scope="consolidated",
    )
    unrelated_note = ReportSection(
        "note:7",
        "진행률 적용 수주계약",
        "note",
        "7",
        [ReportBlock("table", "", note_table, note_table.location)],
        scope="consolidated",
    )
    base_statement = _t_report(table).statements[0]
    statement = ReportSection(
        base_statement.section_id,
        base_statement.title,
        base_statement.kind,
        base_statement.note_no,
        base_statement.blocks,
        scope="consolidated",
    )
    report = FullReport("s.html", "Co", [statement], [note, unrelated_note])
    note_check = CheckResult(
        "note-total",
        "total_check",
        MATCHED,
        "note",
        "7",
        "재고자산 합계검증",
        50,
        50,
        0,
        1,
        "주석 내부 합계 일치",
        [CheckEvidence("재고자산", 50, "note:7/table:7/row:1/col:1")],
    )

    html = _render_table_rows(
        table,
        {},
        id_prefix="panel-bs",
        show_state=True,
        report=report,
        all_results=[note_check],
    )

    assert "주석번호 확인: 주7" in html
    assert html.count("주석 7 열기") == 1
    assert "주석 내 검증 1건" in html
    assert "주석 검증완료" in html
    assert "주석 검증완료 · 참조 주석 검증 특이사항 없음." in html
    assert "합계검증 1건(검증완료 1)은 주석 원문 표의 색상 테두리에서 확인합니다." in html


def test_referenced_note_review_status_surfaces_review_items():
    table = _t([["구분", "당기"], ["유동파생상품자산 (주33)", "0"]])
    note_table = ReportTable(
        33,
        [["구분", "당기"], ["파생상품자산", "10"]],
        "33. 금융위험관리",
        SourceLocation("note:33", 0, 33),
    )
    note = ReportSection(
        "note:33",
        "금융위험관리",
        "note",
        "33",
        [ReportBlock("table", "", note_table, note_table.location)],
        scope="consolidated",
    )
    statement = ReportSection(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        [ReportBlock("table", "", table, table.location)],
        scope="consolidated",
    )
    report = FullReport("s.html", "Co", [statement], [note])
    note_review = CheckResult(
        "note-review",
        "note_note_match",
        UNEXPLAINED_GAP,
        "note",
        "33",
        "파생상품 주석간대사",
        0,
        10,
        10,
        1,
        "주석 간 금액 차이 발생",
        [CheckEvidence("파생상품자산", 10, "note:33/table:33/row:1/col:1")],
    )

    html = _render_table_rows(
        table,
        {},
        id_prefix="panel-bs",
        show_state=True,
        report=report,
        all_results=[note_review],
    )

    assert "확인필요" in html
    assert "미검증</td></tr>" not in html
    assert "확인필요 · 참조 주석에 확인필요 항목이 있습니다." in html
    assert "파생상품 주석간대사" in html
    assert "차이 10" in html
    assert "주석 간 금액 차이 발생" in html


def test_statement_row_drilldown_does_not_embed_disclosure_review_as_source_content():
    table = _t([["구분", "당기"], ["유형자산 (주12)", "100"]])
    statement = ReportSection(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        [ReportBlock("table", "", table, table.location)],
        scope="consolidated",
    )
    note12_table = ReportTable(
        12,
        [["구분", "당기"], ["기말 유형자산", "100"]],
        "12. 유형자산",
        SourceLocation("note:12", 0, 12),
    )
    note14_table = ReportTable(
        14,
        [["구분", "당기"], ["기말 유형자산", "20"]],
        "14. 유형자산 및 사용권자산",
        SourceLocation("note:14", 0, 14),
    )
    note12 = ReportSection(
        "note:12",
        "유형자산",
        "note",
        "12",
        [ReportBlock("table", "", note12_table, note12_table.location)],
        scope="consolidated",
    )
    note14 = ReportSection(
        "note:14",
        "유형자산 및 사용권자산",
        "note",
        "14",
        [ReportBlock("table", "", note14_table, note14_table.location)],
        scope="consolidated",
    )
    report = FullReport("s.html", "Co", [statement], [note12, note14])
    note_match = CheckResult(
        "ppe-note",
        "fs_note_match",
        MATCHED,
        "report",
        "12",
        "유형자산 본문-주석 금액 대사",
        100,
        100,
        0,
        1,
        "본문 금액과 주석 금액 일치",
        [
            CheckEvidence("유형자산 (주12)", 100, "statement:bs/table:0/row:1/col:1"),
            CheckEvidence("주석 12 유형자산", 100, "note:12/table:12/row:1/col:1"),
        ],
    )

    html = _render_table_rows(
        table,
        _row_result_map_for_table([note_match], table),
        id_prefix="panel-bs",
        show_state=True,
        report=report,
        all_results=[note_match],
        statement_scope="consolidated",
        statement_kind="bs",
    )

    assert "유형자산 본문-주석 금액 대사" in html
    assert "주석 12 유형자산" in html
    assert "statement-disclosure-review" not in html
    assert "공시계정 주석번호 검토" not in html
    assert "공시계정 주석번호 정확성" not in html
    assert "공시계정 주석번호 완전성" not in html
    assert "본문 번호 미기재 후보" not in html


def test_income_tax_note_disclosure_advisory_belongs_to_pre_tax_profit_row():
    from dart_footing_reconciler.report_html import _render_statement_disclosure_review

    table = ReportTable(
        0,
        [
            ["구분", "당기"],
            ["법인세비용차감전순이익 (주24)", "1,000"],
            ["법인세비용 (주24)", "200"],
        ],
        "손익계산서",
        SourceLocation("statement:is", 0, 0),
    )
    statement = ReportSection(
        "statement:is",
        "손익계산서",
        "statement",
        "",
        [ReportBlock("table", "", table, table.location)],
        scope="consolidated",
    )
    note_table = ReportTable(
        24,
        [
            ["구분", "금액"],
            ["법인세비용차감전순이익", "1,000"],
            ["적용세율로 계산한 법인세비용", "200"],
        ],
        "24. 법인세비용",
        SourceLocation("note:24", 0, 24),
    )
    note = ReportSection(
        "note:24",
        "법인세비용",
        "note",
        "24",
        [ReportBlock("table", "", note_table, note_table.location)],
        scope="consolidated",
    )
    report = FullReport("s.html", "Co", [statement], [note])

    pbtco_html = _render_statement_disclosure_review(
        "법인세비용차감전순이익 (주24)",
        report,
        "consolidated",
        "is",
    )
    tax_expense_html = _render_statement_disclosure_review(
        "법인세비용 (주24)",
        report,
        "consolidated",
        "is",
    )

    assert "공시계정 주석번호 정확성" in pbtco_html
    assert "본문 주석번호 주24" in pbtco_html
    assert "주석 24 법인세비용" in pbtco_html
    assert tax_expense_html == ""


def test_statement_structure_rows_are_not_labeled_unverified():
    table = _t([["구분", "당기"], ["매출총이익", "100"], ["당기법인세자산", "20"]])
    report = _t_report(table)

    html = _render_table_rows(table, {}, id_prefix="panel-is", show_state=True, report=report)

    assert "본문항목" not in html
    assert "매출총이익" in html
    assert "당기법인세자산" in html
    assert "미검증" not in html


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


def _report_with_statement_and_note():
    stmt_table = ReportTable(
        0,
        [["구분", "당기"], ["유형자산 (주12)", "100"]],
        "재무상태표",
        SourceLocation("statement:bs", 0, 0),
    )
    statement = ReportSection(
        "statement:bs", "재무상태표", "statement", "",
        [ReportBlock("table", "", stmt_table, stmt_table.location)],
    )
    note_table = ReportTable(
        12,
        [["구분", "장부금액 합계"], ["기말 유형자산", "100"]],
        "12. 유형자산",
        SourceLocation("note:12", 0, 12),
    )
    note = ReportSection(
        "note:12", "유형자산", "note", "12",
        [ReportBlock("table", "", note_table, note_table.location)],
    )
    return FullReport("s.html", "Co", [statement], [note])


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


def test_humanize_source_resolves_statement_alias_row_and_column():
    from dart_footing_reconciler.report_html import _humanize_source
    report = _report_with_statement_and_note()
    out = _humanize_source(report, "statement:bs/table:0/row:1/col:1")
    assert "재무상태표" in out
    assert "유형자산 (주12)" in out
    assert "당기" in out
    assert "statement:bs" not in out


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
    assert 'data-jump-table="28"' in dd


def test_body_match_drilldown_distinguishes_target_from_note_evidence():
    from dart_footing_reconciler.report_html import _render_drilldown
    from dart_footing_reconciler.checks import CheckResult, CheckEvidence, MATCHED
    report = _report_with_statement_and_note()
    r = CheckResult(
        "c",
        "fs_note_ref_amount_match",
        MATCHED,
        "report",
        "12",
        "유형자산 본문-주석 금액 대사",
        100,
        100,
        0,
        1,
        "본문 금액과 참조 주석의 당기 금액이 일치",
        [
            CheckEvidence("재무상태표 유형자산 (주12)", 100, "statement:bs/table:0/row:1/col:1"),
            CheckEvidence("주석 12 유형자산 기말 유형자산", 100, "note:12/table:12/row:1/col:1"),
        ],
    )
    dd = _render_drilldown(r, report)
    assert "특이사항 없음" in dd
    assert "비교한 내용" in dd
    assert "재무제표 본문 금액" in dd
    assert "주석 공시 금액" in dd
    assert "엔진 판정: 기준값 100 · 대사값 100 · 차이 0 · 허용오차 1" in dd
    assert "검증 대상(본문)" not in dd
    assert "대사 근거(주석)" in dd
    assert "주석12 · '기말 유형자산' · 장부금액 합계" in dd


def test_attention_drilldown_explains_compared_sources_in_review_rail_template():
    from dart_footing_reconciler.report_html import _render_attention_panel
    from dart_footing_reconciler.checks import CheckResult, CheckEvidence
    report = _report_with_statement_and_note()
    r = CheckResult(
        "gap",
        "fs_note_match",
        UNEXPLAINED_GAP,
        "report",
        "12",
        "유형자산 본문-주석 금액 대사",
        100,
        90,
        -10,
        1,
        "financial statement amount does not agree to note amount",
        [
            CheckEvidence("재무상태표 유형자산 (주12)", 100, "statement:bs/table:0/row:1/col:1"),
            CheckEvidence("주석 12 유형자산 기말 유형자산", 90, "note:12/table:12/row:1/col:1"),
        ],
    )

    html = _render_attention_panel([r], report)

    assert 'class="check-row attn-row"' in html
    assert 'aria-label="비교한 내용"' in html
    assert "본문-주석 금액 대사" in html
    assert "재무제표 본문 금액" in html
    assert "주석 공시 금액" in html
    assert "기준 100" in html
    assert "대사 90" in html
    assert "엔진 판정: 기준값 100 · 대사값 90 · 차이 -10 · 허용오차 1" in html


def test_attention_note_reference_row_says_it_is_not_amount_reconciliation():
    from dart_footing_reconciler.report_html import _render_attention_panel
    from dart_footing_reconciler.checks import CheckResult, CheckEvidence
    report = _report_with_statement_and_note()
    r = CheckResult(
        "note-ref",
        "note_reference_check",
        UNEXPLAINED_GAP,
        "report",
        "12",
        "말 주기 주석 참조 검증 — 주석 12",
        None,
        None,
        None,
        1,
        "displayed footnote marker does not resolve cleanly",
        [CheckEvidence("유형자산(주12)", None, "note:12/table:12/row:1/col:0", role="note_reference_source")],
    )

    html = _render_attention_panel([r], report)

    assert "주석 참조 대사" in html
    assert "금액 대사 아님" in html
    assert "표시된 주석 참조" in html
    assert "실제 주석/원문 위치" in html


def test_prior_year_amount_drilldown_names_baseline_and_comparison_sides():
    from dart_footing_reconciler.report_html import _render_drilldown, _render_source_jump_cell
    from dart_footing_reconciler.checks import CheckResult, CheckEvidence
    report = _report_with_note()
    r = CheckResult(
        "prior-gap",
        "prior_year_amount_match",
        UNEXPLAINED_GAP,
        "report",
        "8",
        "공동기업및관계기업투자",
        20_311_691_981,
        20_230_150_755,
        -81_541_226,
        1,
        "prior amount does not match comparative disclosure",
        [
            CheckEvidence(
                "한화청주에코파크전문투자형사모특별자산투자신탁1호",
                20_230_150_755,
                "note:8/comparative",
            ),
            CheckEvidence(
                "한화청주에코파크전문투자형사모특별자산투자신탁1호",
                20_311_691_981,
                "prior:note:11/current",
            ),
        ],
    )

    dd = _render_drilldown(r, report)

    assert "전기 보고서 당기 금액(기준)" in dd
    assert "당기 보고서 비교기간 금액(대사)" in dd
    assert "전기 보고서 주석11 · 당기" in dd
    assert dd.index("20,311,691,981") < dd.index("20,230,150,755")
    assert "엔진 판정: 기준값 20,311,691,981 · 대사값 20,230,150,755" in dd
    prior_cell = _render_source_jump_cell("prior:note:11/current", report)
    assert "전기 보고서 주석11 · 당기" in prior_cell
    assert "src-jump" not in prior_cell


def test_note_panel_keeps_statement_completeness_out_of_note_body():
    from dart_footing_reconciler.report_html import _render_note_panel
    report = _report_with_statement_and_note()
    note = report.notes[0]
    html = _render_note_panel(note, [_chk(MATCHED)], "panel-note-12", report=report)

    assert "주석 원문" in html
    assert "본문 공시계정 연결" not in html
    assert "completeness-table" not in html


def test_note_panel_does_not_insert_missing_statement_reference_callout():
    from dart_footing_reconciler.report_html import _render_note_panel
    note_table = ReportTable(
        12,
        [["구분", "장부금액 합계"], ["기말 유형자산", "100"]],
        "12. 유형자산",
        SourceLocation("note:12", 0, 12),
    )
    note = ReportSection(
        "note:12", "유형자산", "note", "12",
        [ReportBlock("table", "", note_table, note_table.location)],
    )
    report = FullReport("s.html", "Co", [], [note])

    html = _render_note_panel(note, [_chk(MATCHED)], "panel-note-12", report=report)

    assert "주석 원문" in html
    assert "본문 공시계정 연결" not in html
    assert "재무제표 본문 공시계정" not in html


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
    assert "확인필요" in html
    assert "검증완료" not in html.split("유형자산")[0]


def test_review_runtime_routes_drilldown_to_side_panel():
    from dart_footing_reconciler.report_html import _inline_js

    js = _inline_js()

    assert "showReview" in js
    assert "review-rail-body" in js
    assert "review-source-active" in js
    assert "clearReviewRail" in js
    assert "document.body.classList.add('review-open')" in js
    assert "document.body.classList.remove('review-open')" in js


def test_dashboard_status_runtime_filters_and_jumps_to_source():
    from dart_footing_reconciler.report_html import _inline_js

    js = _inline_js()

    assert "data-status-filter" in js
    assert "data-status-item" in js
    assert "jumpToCheckSource" in js
    assert "jumpToCell(el)" in js


def test_review_css_reserves_note_body_space_and_keeps_source_rows_compact():
    from dart_footing_reconciler.report_html import _inline_css

    css = _inline_css()

    assert "grid-template-columns:258px minmax(760px,1fr)" in css
    assert "body.review-open .review-rail" in css
    assert "--review-rail-width:min(560px,calc(100vw - 280px))" in css
    assert "body.review-open main{padding-right:calc(30px + var(--review-rail-width));}" in css
    assert ".note-source-original table:not(.nb) tr > :first-child{text-align:left;white-space:nowrap;" in css
    assert ".note-source-original table:not(.nb) thead tr:first-child > th" in css
    assert ".note-source-original table:not(.nb) tr:first-child > th" not in css
    assert ".review-rail-body{font-size:13px;color:#172554;overflow-x:hidden;}" in css
    assert ".review-rail .src-tbl th,.review-rail .src-tbl td{white-space:normal;overflow-wrap:anywhere;}" in css
    assert "statement-disclosure-review" not in css


def test_note_tab_runtime_opens_filtered_group_detail():
    from dart_footing_reconciler.report_html import _inline_js

    js = _inline_js()

    assert "openNoteGroupForFilter" in js
    assert "data-note-group" in js
    assert "showReview(detail.id, row)" in js


def test_note_panel_renders_source_blocks_and_groups_checks_by_review_type():
    from dart_footing_reconciler.report_html import _render_note_panel
    from dart_footing_reconciler.checks import PARSE_UNCERTAIN

    table1 = ReportTable(
        1,
        [["구분", "당기"], ["유동", "100"], ["비유동", "200"], ["합계", "300"]],
        "12. 차입금 첫 번째 표",
        SourceLocation("note:12", 1, 1),
    )
    table2 = ReportTable(
        2,
        [["구분", "당기"], ["담보", "50"]],
        "12. 차입금 두 번째 표",
        SourceLocation("note:12", 3, 2),
    )
    section = ReportSection(
        "note:12",
        "차입금",
        "note",
        "12",
        [
            ReportBlock("text", "차입금 원문 설명", None, SourceLocation("note:12", 0)),
            ReportBlock("table", "", table1, table1.location),
            ReportBlock("text", "담보 제공 내역 설명", None, SourceLocation("note:12", 2)),
            ReportBlock("table", "", table2, table2.location),
        ],
    )
    report = FullReport("s.html", "Co", [], [section])
    results = [
        CheckResult(
            "total",
            "total_check",
            MATCHED,
            "note",
            "12",
            "합계검증 상세",
            300,
            300,
            0,
            1,
            "일치",
            [CheckEvidence("합계", 300, "note:12/table:1/row:3/col:1")],
        ),
        CheckResult(
            "body",
            "fs_note_match",
            UNEXPLAINED_GAP,
            "note",
            "12",
            "본문대사 상세",
            300,
            290,
            -10,
            1,
            "차이",
            [CheckEvidence("차입금", 290, "note:12/table:1/row:3/col:1")],
        ),
        CheckResult(
            "note",
            "note_note_match",
            PARSE_UNCERTAIN,
            "note",
            "12",
            "주석간대사 상세",
            None,
            None,
            None,
            1,
            "불확실",
            [CheckEvidence("담보", None, "note:12/table:2/row:1/col:1")],
            parse_uncertain_reason="LABEL_NOT_FOUND",
        ),
    ]

    html = _render_note_panel(section, results, panel_id="panel-note-12", report=report)

    assert "차입금 원문 설명" in html
    assert "담보 제공 내역 설명" in html
    assert "차입금 첫 번째 표" in html
    assert "차입금 두 번째 표" in html
    assert "total-cell total-ok" in html
    assert 'data-note-filter="total"' not in html
    assert '<span class="check-name">합계검증 상세</span>' not in html
    assert "본문대사" in html
    assert "주석간대사" in html
    assert html.count("note-check-group") == 2
    assert html.index('aria-label="주석 검증"') < html.index('aria-label="주석 원문"')


def test_note_panel_prefers_raw_source_html_for_note_body():
    from dart_footing_reconciler.report_html import _render_note_panel

    table = ReportTable(
        12,
        [["구분", "총액", "순액"], ["기말", "1,500", "1,000"]],
        "12. 유형자산",
        SourceLocation("note:12", 0, 12),
    )
    section = ReportSection(
        "note:12",
        "유형자산",
        "note",
        "12",
        [
            ReportBlock(
                "table",
                "",
                table,
                SourceLocation("note:12", 0, 12),
                raw_html=(
                    '<table><tr><th rowspan="2" data-cell-keys="r0c0 r1c0">구분</th>'
                    '<th colspan="2" data-cell-keys="r0c1 r0c2">장부금액</th></tr>'
                    '<tr><th data-cell-keys="r1c1">총액</th>'
                    '<th data-cell-keys="r1c2">순액</th></tr>'
                    '<tr><td data-cell-keys="r2c0">기말</td>'
                    '<td data-cell-keys="r2c1">1,500</td>'
                    '<td data-cell-keys="r2c2">1,000</td></tr></table>'
                ),
            )
        ],
    )

    html = _render_note_panel(section, [], "panel-note-12")

    assert "note-source-original" in html
    assert 'colspan="2"' in html
    assert 'rowspan="2"' in html
    assert "statement-caption" not in html


def test_note_panel_hides_xbrl_disclosure_caption_rows_from_raw_source_html():
    from dart_footing_reconciler.report_html import _render_note_panel

    table = ReportTable(
        19,
        [["", "공시금액"], ["보통예금", "40,077"]],
        "5-3. 현금및현금성자산",
        SourceLocation("note:5-3", 0, 19),
    )
    section = ReportSection(
        "note:5-3",
        "현금및현금성자산",
        "note",
        "5-3",
        [
            ReportBlock(
                "table",
                "",
                table,
                SourceLocation("note:5-3", 0, 19),
                raw_html=(
                    '<table class="nb"><tbody>'
                    '<tr><td colspan="2" data-cell-keys="r0c0 r0c1">현금및현금성자산 공시</td></tr>'
                    '<tr><td colspan="2" data-cell-keys="r0c0 r0c1">리스부채 만기분석 내역에 대한 공시, 합계</td></tr>'
                    '<tr><td colspan="2" data-cell-keys="r0c0 r0c1">차입금에 대한 세부 정보</td></tr>'
                    '<tr><td data-cell-keys="r1c0">당기</td>'
                    '<td align="RIGHT" data-cell-keys="r1c1">(단위 : 원)</td></tr>'
                    '<tr><td data-cell-keys="r9c0">(주1)</td>'
                    '<td data-cell-keys="r9c1">실제 각주 설명입니다.</td></tr>'
                    '</tbody></table>'
                    '<table border="1"><thead><tr>'
                    '<th data-cell-keys="r0c0">　</th>'
                    '<th data-cell-keys="r0c1">공시금액</th>'
                    '</tr></thead><tbody><tr>'
                    '<td data-cell-keys="r1c0">보통예금</td>'
                    '<td align="RIGHT" data-cell-keys="r1c1">40,077</td>'
                    '</tr></tbody></table>'
                ),
            )
        ],
    )

    html = _render_note_panel(section, [], "panel-note-5-3")

    assert "현금및현금성자산 공시" not in html
    assert "리스부채 만기분석 내역에 대한 공시, 합계" not in html
    assert "차입금에 대한 세부 정보" not in html
    assert "당기" not in html
    assert "(단위 : 원)" not in html
    assert "실제 각주 설명입니다." in html
    assert "공시금액" in html
    assert "보통예금" in html
    assert 'data-cell-keys="r1c1"' in html


def test_note_panel_hides_xbrl_top_aggregate_rows_from_raw_table_html():
    from dart_footing_reconciler.report_html import _render_note_panel

    table = ReportTable(
        21,
        [
            ["", "", "", "상각후원가로 측정하는 금융자산, 범주", "금융자산, 범주 합계"],
            ["금융자산", "", "", "262,720,895,248", "287,100,059,662"],
            ["금융자산", "유동 금융자산 합계", "", "203,333,767,751", "203,333,767,751"],
            ["", "유동 금융자산 합계", "현금및현금성자산", "88,494,004,913", "88,494,004,913"],
        ],
        "5-1. 금융상품",
        SourceLocation("note:5-1", 0, 21),
    )
    section = ReportSection(
        "note:5-1",
        "금융상품",
        "note",
        "5-1",
        [
            ReportBlock(
                "table",
                "",
                table,
                SourceLocation("note:5-1", 0, 21),
                raw_html=(
                    '<table border="1"><thead><tr>'
                    '<th data-cell-keys="r0c0"></th>'
                    '<th data-cell-keys="r0c1"></th>'
                    '<th data-cell-keys="r0c2"></th>'
                    '<th data-cell-keys="r0c3">상각후원가로 측정하는 금융자산, 범주</th>'
                    '<th data-cell-keys="r0c4">금융자산, 범주 합계</th>'
                    '</tr></thead><tbody>'
                    '<tr><td colspan="3" data-cell-keys="r1c0 r1c1 r1c2">금융자산</td>'
                    '<td align="RIGHT" data-cell-keys="r1c3">262,720,895,248</td>'
                    '<td align="RIGHT" data-cell-keys="r1c4">287,100,059,662</td></tr>'
                    '<tr><td rowspan="2" data-cell-keys="r2c0 r3c0">금융자산</td>'
                    '<td colspan="2" data-cell-keys="r2c1 r2c2">유동 금융자산 합계</td>'
                    '<td align="RIGHT" data-cell-keys="r2c3">203,333,767,751</td>'
                    '<td align="RIGHT" data-cell-keys="r2c4">203,333,767,751</td></tr>'
                    '<tr><td data-cell-keys="r3c1">유동 금융자산 합계</td>'
                    '<td data-cell-keys="r3c2">현금및현금성자산</td>'
                    '<td align="RIGHT" data-cell-keys="r3c3">88,494,004,913</td>'
                    '<td align="RIGHT" data-cell-keys="r3c4">88,494,004,913</td></tr>'
                    '</tbody></table>'
                ),
            )
        ],
    )

    html = _render_note_panel(section, [], "panel-note-5-1")

    assert "262,720,895,248" not in html
    assert "287,100,059,662" not in html
    assert "금융자산, 범주 합계" in html
    assert "유동 금융자산 합계" in html
    assert "현금및현금성자산" in html
    assert 'data-cell-keys="r2c3"' in html


def test_note_panel_preserves_sentence_style_nb_explanatory_rows():
    from dart_footing_reconciler.report_html import _render_note_panel

    table = ReportTable(
        30,
        [["", "공시금액"], ["재고자산평가손실", "0"]],
        "7. 재고자산",
        SourceLocation("note:7", 0, 30),
    )
    section = ReportSection(
        "note:7",
        "재고자산",
        "note",
        "7",
        [
            ReportBlock(
                "table",
                "",
                table,
                SourceLocation("note:7", 0, 30),
                raw_html=(
                    '<table class="nb"><tbody>'
                    '<tr><td data-cell-keys="r0c0">당기 중 매출원가에 반영된 재고자산평가손실은 없습니다.</td></tr>'
                    '</tbody></table>'
                    '<table border="1"><thead><tr>'
                    '<th data-cell-keys="r0c0">　</th><th data-cell-keys="r0c1">공시금액</th>'
                    '</tr></thead><tbody><tr>'
                    '<td data-cell-keys="r1c0">재고자산평가손실</td><td data-cell-keys="r1c1">0</td>'
                    '</tr></tbody></table>'
                ),
            )
        ],
    )

    html = _render_note_panel(section, [], "panel-note-7")

    assert "당기 중 매출원가에 반영된 재고자산평가손실은 없습니다." in html


def test_note_panel_preserves_raw_text_html_for_note_body():
    from dart_footing_reconciler.report_html import _render_note_panel

    section = ReportSection(
        "note:1",
        "일반사항",
        "note",
        "1",
        [
            ReportBlock(
                "text",
                "회사의 개요입니다.",
                None,
                SourceLocation("note:1", 0),
                raw_html="<p><b>회사의 개요</b><br/>회사의 개요입니다.</p>",
            )
        ],
    )

    html = _render_note_panel(section, [], "panel-note-1")

    assert "note-text-original" in html
    assert "<b>회사의 개요</b><br/>회사의 개요입니다." in html
    assert "note-text-block" not in html


def test_note_panel_marks_total_check_on_raw_source_cell():
    from dart_footing_reconciler.report_html import _render_note_panel

    table = ReportTable(
        12,
        [["구분", "당기"], ["법인세비용", "200"], ["합계", "1,000"]],
        "12. 유형자산",
        SourceLocation("note:12", 0, 12),
    )
    section = ReportSection(
        "note:12",
        "유형자산",
        "note",
        "12",
        [
            ReportBlock(
                "table",
                "",
                table,
                SourceLocation("note:12", 0, 12),
                raw_html=(
                    '<table><tr><th data-cell-keys="r0c0">구분</th>'
                    '<th data-cell-keys="r0c1">당기</th></tr>'
                    '<tr><td data-cell-keys="r1c0">법인세비용</td>'
                    '<td data-cell-keys="r1c1">200</td></tr>'
                    '<tr><td data-cell-keys="r2c0">합계</td>'
                    '<td data-cell-keys="r2c1">1,000</td></tr></table>'
                ),
            )
        ],
    )
    result = CheckResult(
        "total",
        "total_check",
        UNEXPLAINED_GAP,
        "note",
        "12",
        "합계검증",
        900,
        1000,
        100,
        1,
        "불일치",
        [
            CheckEvidence("법인세비용", 200, "note:12/table:12/row:1/col:1"),
            CheckEvidence("합계", 1000, "note:12/table:12/row:2/col:1"),
        ],
    )

    html = _render_note_panel(section, [result], "panel-note-12")

    assert "total-cell total-warn" in html
    assert html.count("total-cell total-warn") == 2
    assert "합계검증 이상" in html
    assert "note-check-group" not in html


def test_note_panel_marks_rollforward_ending_cell_on_raw_source_table():
    from dart_footing_reconciler.report_html import _render_note_panel

    table = ReportTable(
        10,
        [["구분", "토지"], ["기초", "100"], ["취득", "30"], ["기말", "130"]],
        "10. 유형자산",
        SourceLocation("note:10", 0, 10),
    )
    section = ReportSection(
        "note:10",
        "유형자산",
        "note",
        "10",
        [
            ReportBlock(
                "table",
                "",
                table,
                SourceLocation("note:10", 0, 10),
                raw_html=(
                    '<table><tr><th data-cell-keys="r0c0">구분</th>'
                    '<th data-cell-keys="r0c1">토지</th></tr>'
                    '<tr><td data-cell-keys="r1c0">기초</td>'
                    '<td data-cell-keys="r1c1">100</td></tr>'
                    '<tr><td data-cell-keys="r2c0">취득</td>'
                    '<td data-cell-keys="r2c1">30</td></tr>'
                    '<tr><td data-cell-keys="r3c0">기말</td>'
                    '<td data-cell-keys="r3c1">130</td></tr></table>'
                ),
            )
        ],
    )
    result = CheckResult(
        "rollforward",
        "note_rollforward_check",
        MATCHED,
        "note",
        "10",
        "유형자산 증감표 검산 - 토지",
        130,
        130,
        0,
        1,
        "일치",
        [
            CheckEvidence("기초 토지", 100, "note:10/table:10/row:1/col:1", role="beginning"),
            CheckEvidence("기말 토지", 130, "note:10/table:10/row:3/col:1", role="ending"),
            CheckEvidence("취득 토지", 30, "note:10/table:10/row:2/col:1", role="movement"),
        ],
    )

    html = _render_note_panel(section, [result], "panel-note-10")

    assert 'data-cell-keys="r3c1"' in html
    assert "total-cell total-ok" in html
    assert html.count("total-cell total-ok") == 1
    assert "합계검증 적정" in html


def test_note_panel_marks_row_total_column_cell_on_raw_source_table():
    from dart_footing_reconciler.report_html import _render_note_panel

    table = ReportTable(
        12,
        [["구분", "제품", "상품", "합계"], ["수익", "100", "200", "300"]],
        "12. 수익",
        SourceLocation("note:12", 0, 12),
    )
    section = ReportSection(
        "note:12",
        "수익",
        "note",
        "12",
        [
            ReportBlock(
                "table",
                "",
                table,
                SourceLocation("note:12", 0, 12),
                raw_html=(
                    '<table><tr><th data-cell-keys="r0c0">구분</th>'
                    '<th data-cell-keys="r0c1">제품</th>'
                    '<th data-cell-keys="r0c2">상품</th>'
                    '<th data-cell-keys="r0c3">합계</th></tr>'
                    '<tr><td data-cell-keys="r1c0">수익</td>'
                    '<td data-cell-keys="r1c1">100</td>'
                    '<td data-cell-keys="r1c2">200</td>'
                    '<td data-cell-keys="r1c3">300</td></tr></table>'
                ),
            )
        ],
    )
    result = CheckResult(
        "total",
        "total_check",
        MATCHED,
        "note",
        "12",
        "수익 행 합계",
        300,
        300,
        0,
        1,
        "일치",
        [
            CheckEvidence("수익", 300, "note:12/table:12/row:1/col:3"),
            CheckEvidence("제품", 100, "note:12/table:12/row:1/col:1", role="component"),
            CheckEvidence("상품", 200, "note:12/table:12/row:1/col:2", role="component"),
        ],
    )

    html = _render_note_panel(section, [result], "panel-note-12")

    assert "total-cell total-ok" in html
    assert html.count("total-cell total-ok") == 1
    assert "합계검증 적정" in html


def test_note_total_mark_exposes_copyable_formula_on_raw_source_cell():
    from dart_footing_reconciler.report_html import _render_note_panel

    table = ReportTable(
        12,
        [["구분", "제품", "상품", "합계"], ["수익", "100", "200", "300"]],
        "12. 수익",
        SourceLocation("note:12", 0, 12),
    )
    section = ReportSection(
        "note:12",
        "수익",
        "note",
        "12",
        [
            ReportBlock(
                "table",
                "",
                table,
                SourceLocation("note:12", 0, 12),
                raw_html=(
                    '<table><tr><th data-cell-keys="r0c0">구분</th>'
                    '<th data-cell-keys="r0c1">제품</th>'
                    '<th data-cell-keys="r0c2">상품</th>'
                    '<th data-cell-keys="r0c3">합계</th></tr>'
                    '<tr><td data-cell-keys="r1c0">수익</td>'
                    '<td data-cell-keys="r1c1">100</td>'
                    '<td data-cell-keys="r1c2">200</td>'
                    '<td data-cell-keys="r1c3">300</td></tr></table>'
                ),
            )
        ],
    )
    result = CheckResult(
        "total",
        "total_check",
        MATCHED,
        "note",
        "12",
        "수익 행 합계",
        300,
        300,
        0,
        1,
        "일치",
        [
            CheckEvidence("수익", 300, "note:12/table:12/row:1/col:3", role="total"),
            CheckEvidence("제품", 100, "note:12/table:12/row:1/col:1", role="component"),
            CheckEvidence("상품", 200, "note:12/table:12/row:1/col:2", role="component"),
        ],
    )

    html = _render_note_panel(section, [result], "panel-note-12")

    assert "total-formula-popover" in html
    assert "total-formula-table" in html
    assert "data-total-formula" in html
    assert "copyFormula(this,event)" in html
    assert "제품(100) + 상품(200) = 300" in html
    assert "역할\t항목\t금액" in html
    assert "구성요소\t제품\t100" in html


def test_statement_total_mark_exposes_copyable_formula_on_rendered_cell():
    table = _t([["구분", "제품", "상품", "합계"], ["수익", "100", "200", "300"]])
    result = CheckResult(
        "total",
        "total_check",
        MATCHED,
        "note",
        "12",
        "수익 행 합계",
        300,
        300,
        0,
        1,
        "일치",
        [
            CheckEvidence("수익", 300, "note:12/table:0/row:1/col:3", role="total"),
            CheckEvidence("제품", 100, "note:12/table:0/row:1/col:1", role="component"),
            CheckEvidence("상품", 200, "note:12/table:0/row:1/col:2", role="component"),
        ],
    )

    html = _render_table_rows(table, {}, total_results=[result])

    assert "total-formula-popover" in html
    assert "total-formula-table" in html
    assert "제품(100) + 상품(200) = 300" in html
    assert "복사" in html


def test_appropriation_formula_check_marks_closing_cell_as_total_surface():
    table = _t(
        [
            ["구분", "당기"],
            ["미처분이익잉여금", "100"],
            ["이익잉여금처분액", "30"],
            ["차기이월미처분이익잉여금", "70"],
        ]
    )
    result = CheckResult(
        "appropriation",
        "appropriation_formula_check",
        MATCHED,
        "report",
        "",
        "처분계산서 산식",
        70,
        70,
        0,
        1,
        "일치",
        [
            CheckEvidence("미처분이익잉여금", 100, "statement:bs/table:0/row:1/col:1"),
            CheckEvidence("이익잉여금처분액", 30, "statement:bs/table:0/row:2/col:1"),
            CheckEvidence("차기이월미처분이익잉여금", 70, "statement:bs/table:0/row:3/col:1"),
        ],
    )

    html = _render_table_rows(table, {}, total_results=[result])

    assert "total-cell total-ok" in html
    assert html.count("total-cell total-ok") == 1
    assert "합계검증 적정" in html


def test_note_panel_suppresses_repeated_xbrl_group_leading_cell():
    from bs4 import BeautifulSoup
    from dart_footing_reconciler.report_html import _render_note_panel

    table = ReportTable(
        19,
        [
            ["", "", "공시금액"],
            ["기타유동금융부채", "", "17,600,000"],
            ["기타유동금융부채", "단기예수보증금", "17,600,000"],
        ],
        "19. 기타금융부채",
        SourceLocation("note:19", 0, 19),
    )
    section = ReportSection(
        "note:19",
        "기타금융부채",
        "note",
        "19",
        [
            ReportBlock(
                "table",
                "",
                table,
                SourceLocation("note:19", 0, 19),
                raw_html=(
                    '<table border="1"><thead><tr>'
                    '<th data-cell-keys="r0c0"></th><th data-cell-keys="r0c1"></th>'
                    '<th data-cell-keys="r0c2">공시금액</th></tr></thead><tbody>'
                    '<tr><td colspan="2" data-cell-keys="r1c0 r1c1">기타유동금융부채</td>'
                    '<td data-cell-keys="r1c2">17,600,000</td></tr>'
                    '<tr><td data-cell-keys="r2c0">기타유동금융부채</td>'
                    '<td data-cell-keys="r2c1">단기예수보증금</td>'
                    '<td data-cell-keys="r2c2">17,600,000</td></tr>'
                    '</tbody></table>'
                ),
            )
        ],
    )

    html = _render_note_panel(section, [], "panel-note-19")
    soup = BeautifulSoup(html, "html.parser")
    repeated = soup.select_one('[data-cell-keys~="r2c0"]')

    assert repeated is not None
    assert repeated.get_text(strip=True) == ""
    assert "xbrl-repeated-group-cell" in repeated.get("class", [])
    assert soup.select_one('[data-cell-keys~="r2c1"]').get_text(strip=True) == "단기예수보증금"


def test_note_panel_renders_single_row_xbrl_detail_table_as_reader_rows():
    from dart_footing_reconciler.report_html import _render_note_panel

    table = ReportTable(
        12,
        [
            ["", "토지", "토지", "토지", "건물", "건물", "건물", "유형자산 합계"],
            ["유형자산", "100", "0", "100", "200", "(50)", "150", "250"],
        ],
        "12. 유형자산",
        SourceLocation("note:12", 0, 12),
    )
    section = ReportSection(
        "note:12",
        "유형자산",
        "note",
        "12",
        [
            ReportBlock(
                "table",
                "",
                table,
                SourceLocation("note:12", 0, 12),
                raw_html=(
                    '<table border="1"><thead>'
                    '<tr><th data-cell-keys="r0c0"></th>'
                    '<th colspan="6" data-cell-keys="r0c1 r0c2 r0c3 r0c4 r0c5 r0c6">유형자산</th>'
                    '<th rowspan="3" data-cell-keys="r0c7 r1c7 r2c7">유형자산 합계</th></tr>'
                    '<tr><th data-cell-keys="r1c0"></th>'
                    '<th colspan="3" data-cell-keys="r1c1 r1c2 r1c3">토지</th>'
                    '<th colspan="3" data-cell-keys="r1c4 r1c5 r1c6">건물</th></tr>'
                    '<tr><th data-cell-keys="r2c0"></th>'
                    '<th data-cell-keys="r2c1">총장부금액</th>'
                    '<th data-cell-keys="r2c2">감가상각누계액 및 상각누계액</th>'
                    '<th data-cell-keys="r2c3">장부금액 합계</th>'
                    '<th data-cell-keys="r2c4">총장부금액</th>'
                    '<th data-cell-keys="r2c5">감가상각누계액 및 상각누계액</th>'
                    '<th data-cell-keys="r2c6">장부금액 합계</th></tr>'
                    '</thead><tbody><tr>'
                    '<td data-cell-keys="r3c0">유형자산</td>'
                    '<td data-cell-keys="r3c1">100</td><td data-cell-keys="r3c2">0</td>'
                    '<td data-cell-keys="r3c3">100</td><td data-cell-keys="r3c4">200</td>'
                    '<td data-cell-keys="r3c5">(50)</td><td data-cell-keys="r3c6">150</td>'
                    '<td data-cell-keys="r3c7">250</td></tr></tbody></table>'
                ),
            )
        ],
    )

    html = _render_note_panel(section, [], "panel-note-12")

    assert "xbrl-reader-table" in html
    assert "<td>토지</td>" in html
    assert "<td>건물</td>" in html
    assert "유형자산</td><td data-cell-keys=\"r3c1\"" not in html
