
from dart_footing_reconciler.checks import CheckEvidence, CheckResult
from dart_footing_reconciler.document import FullReport, ReportBlock, ReportSection, ReportTable, SourceLocation
from dart_footing_reconciler.report_frame import (
    CANONICAL_STATEMENT_ORDER,
    CHECK_DISPLAY_NAMES,
    CHECK_GROUP_ORDER,
    CHECK_GROUPS,
    CHECK_LAYERS,
    CHECK_METHOD_DESCRIPTIONS,
    CHECK_PRESENTATIONS,
    build_report_frame,
    check_group,
    check_layer,
    check_status_compact_label,
    evidence_display_label,
)


ENGINE_CHECK_TYPES = {
    "appropriation_formula_check",
    "asset_note_bridge_check",
    "cashflow_reconciliation",
    "cfs_note_match",
    "expense_allocation",
    "fs_note_match",
    "note_balance_bridge_check",
    "note_internal_consistency_check",
    "note_layout_formula_check",
    "note_note_match",
    "note_note_reconciliation",
    "note_reference_check",
    "note_rollforward_check",
    "primary_balance_reconciliation",
    "prior_column_fs_note",
    "prior_column_rollforward",
    "prior_year_amount_match",
    "prior_year_beginning_balance_match",
    "prior_year_structure_change",
    "statement_bs_equation",
    "statement_cash_tie",
    "statement_equity_tie",
    "statement_note_row_reconciliation",
    "total_check",
}


def test_evidence_display_label_humanizes_engine_prefixes_and_exclusion_codes():
    labels = {
        "statement 유형자산": "재무제표 유형자산",
        "cfs 유형자산의 취득": "현금흐름표 유형자산의 취득",
        "note 11 취득": "주석 11 취득",
        "excluded note 20 이자비용 (financing_adjustment_not_cash)": (
            "대사 제외 주석 20 이자비용 (비현금 재무조정)"
        ),
        "nature 감가상각비": "성격별 비용 감가상각비",
        "nature exclusion 개발비": "성격별 비용 제외 개발비",
        "allocation 제조원가": "기능별 배부 제조원가",
        "allocation total 감가상각비": "기능별 배부 합계 감가상각비",
    }

    assert {label: evidence_display_label(label) for label in labels} == labels


def test_evidence_display_label_removes_period_role_word_duplication():
    assert evidence_display_label("prior ending 기말 장부금액") == "전기 기말 장부금액"
    assert evidence_display_label("current beginning 기초 장부금액") == "당기 기초 장부금액"


def test_compact_status_label_uses_auditor_facing_interpretation_term():
    assert check_status_compact_label("parse_uncertain") == "해석 확인"


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


def test_strong_cashflow_checks_share_cashflow_note_group():
    from dataclasses import replace

    base = CheckResult(
        "cashflow",
        "cashflow_reconciliation",
        "matched",
        "report",
        "11",
        "현금흐름 대사",
        100,
        100,
        0,
        1,
        "matched",
        [],
    )

    assert check_group(base) == "현금흐름표-주석 대사"
    assert check_group(replace(base, check_type="asset_note_bridge_check")) == "현금흐름표-주석 대사"


def test_check_type_registries_are_self_consistent_for_known_check_types():
    assert set(CHECK_GROUPS) == ENGINE_CHECK_TYPES
    assert set(CHECK_LAYERS) == ENGINE_CHECK_TYPES
    assert set(CHECK_PRESENTATIONS) == ENGINE_CHECK_TYPES

    for check_type in ENGINE_CHECK_TYPES:
        check = CheckResult(
            f"{check_type}:sample",
            check_type,
            "matched",
            "report",
            "",
            check_type,
            100,
            100,
            0,
            1,
            "matched",
            [],
        )
        assert check_group(check) == CHECK_GROUPS[check_type]
        assert check_layer(check) == CHECK_LAYERS[check_type]


def test_workbench_annotations_split_internal_cells_from_cross_table_drawer():
    from dart_footing_reconciler.report_frame import build_workbench_annotations

    bs_table = _table("statement:bs", 0, "재무상태표")
    note_table = _table("note:11", 1, "유형자산")
    report = FullReport(
        "sample.html",
        "Sample Co",
        [_section("statement:bs", "재무상태표", "statement", "", bs_table)],
        [_section("note:11", "유형자산", "note", "11", note_table)],
    )
    internal = CheckResult(
        "total:11:table1:row1:col1",
        "total_check",
        "matched",
        "note",
        "11",
        "표 합계",
        100,
        100,
        0,
        1,
        "row total agrees",
        [CheckEvidence("합계", 100, "note:11/table:1/row:1/col:1", role="target")],
    )
    cross = CheckResult(
        "fs-note",
        "fs_note_match",
        "unexplained_gap",
        "report",
        "11",
        "재무제표-주석 대사",
        100,
        90,
        -10,
        1,
        "gap",
        [
            CheckEvidence("재무제표", 100, "statement:bs/table:0/row:1/col:1"),
            CheckEvidence("주석", 90, "note:11/table:1/row:1/col:1"),
        ],
    )

    model = build_workbench_annotations(report, [internal, cross])

    assert [
        (item.target.table_index, item.target.row_index, item.target.column_index)
        for item in model.cells
    ] == [(1, 1, 1)]
    assert [item.check for item in model.drawers] == [cross]
    assert [
        (ref.table_index, ref.row_index, ref.column_index)
        for ref in model.drawers[0].anchors
    ] == [(0, 1, 1), (1, 1, 1)]


def test_cell_annotations_keep_all_checks_and_choose_worst_status():
    from dataclasses import replace

    from dart_footing_reconciler.report_frame import build_workbench_annotations

    note_table = _table("note:11", 1, "유형자산")
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [_section("note:11", "유형자산", "note", "11", note_table)],
    )
    base = CheckResult(
        "matched",
        "total_check",
        "matched",
        "note",
        "11",
        "표 합계",
        100,
        100,
        0,
        1,
        "matched",
        [CheckEvidence("합계", 100, "note:11/table:1/row:1/col:1", role="target")],
    )
    uncertain = replace(base, check_id="uncertain", status="parse_uncertain")
    gap = replace(base, check_id="gap", status="unexplained_gap")

    annotation = build_workbench_annotations(report, [base, uncertain, gap]).cells[0]

    assert annotation.status == "unexplained_gap"
    assert annotation.count == 3
    assert annotation.checks == (base, uncertain, gap)


def test_workbench_keeps_unanchored_cross_check_in_drawer():
    from dart_footing_reconciler.report_frame import build_workbench_annotations

    check = CheckResult(
        "note-reference",
        "note_reference_check",
        "parse_uncertain",
        "report",
        "",
        "주석 참조 확인",
        None,
        None,
        None,
        0,
        "원문 위치 확인 필요",
        [],
    )

    model = build_workbench_annotations(FullReport("sample.html", "Sample", [], []), [check])

    assert len(model.drawers) == 1
    assert model.drawers[0].check is check
    assert model.drawers[0].anchors == ()


def test_workbench_drawer_deduplicates_repeated_evidence_anchor_without_losing_other_side():
    from dart_footing_reconciler.report_frame import build_workbench_annotations

    bs_table = _table("statement:bs", 0, "재무상태표")
    note_table = _table("note:11", 1, "유형자산")
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
        "재무제표-주석 대사",
        100,
        100,
        0,
        1,
        "matched",
        [
            CheckEvidence("재무제표", 100, "statement:bs/table:0/row:1/col:1"),
            CheckEvidence("재무제표 반복", 100, "statement:bs/table:0/row:1/col:1"),
            CheckEvidence("주석", 100, "note:11/table:1/row:1/col:1"),
        ],
    )

    anchors = build_workbench_annotations(report, [check]).drawers[0].anchors

    assert [(anchor.scope, anchor.table_index) for anchor in anchors] == [
        ("statement", 0),
        ("note", 1),
    ]


def test_workbench_routes_invalid_internal_target_to_drawer_for_manual_source_review():
    from dart_footing_reconciler.report_frame import build_workbench_annotations

    note_table = _table("note:11", 1, "유형자산")
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [_section("note:11", "유형자산", "note", "11", note_table)],
    )
    check = CheckResult(
        "total:11:broken",
        "total_check",
        "matched",
        "note",
        "11",
        "표 합계",
        100,
        100,
        0,
        1,
        "row total agrees",
        [CheckEvidence("합계", 100, "note:11/table:1/row:9/col:1", role="target")],
    )

    model = build_workbench_annotations(report, [check])

    assert model.cells == ()
    assert len(model.drawers) == 1
    assert model.drawers[0].check is check
    assert model.drawers[0].anchors == ()


def test_unknown_check_type_uses_evidence_source_fallback_without_raising():
    check = CheckResult(
        "made-up",
        "made_up_check_type",
        "matched",
        "report",
        "",
        "unknown check",
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

    assert check_group(check) == "재무제표-주석 대사"
    assert check_layer(check) == "statement_note"


def test_check_method_descriptions_match_registered_check_types():
    assert set(CHECK_METHOD_DESCRIPTIONS) == set(CHECK_GROUPS)
    assert CHECK_DISPLAY_NAMES.keys() == CHECK_GROUPS.keys()


def test_check_display_copy_hides_internal_english_terms():
    from dart_footing_reconciler.checks import CheckResult, MATCHED, PARSE_UNCERTAIN
    from dart_footing_reconciler.report_frame import (
        check_display_reason,
        check_display_title,
        check_status_label,
    )

    matched = CheckResult(
        "private:id",
        "fs_note_match",
        MATCHED,
        "report",
        "11",
        "리스부채 FS to note match (current)",
        100,
        100,
        0,
        1,
        "financial statement amount agrees to note amount",
        [],
    )
    uncertain = CheckResult(
        "private:uncertain",
        "note_note_match",
        PARSE_UNCERTAIN,
        "note",
        "11",
        "ppe note to note match",
        None,
        None,
        None,
        1,
        "multiple candidate note amounts found",
        [],
        parse_uncertain_reason="AMBIGUOUS_MULTIPLE",
    )

    assert check_display_title(matched) == "재무제표-주석 대사"
    assert check_display_reason(matched) == "재무제표 금액과 주석 금액이 일치함"
    assert check_display_title(uncertain) == "주석 간 금액 대사"
    assert check_display_reason(uncertain) == "비교할 후보가 여러 개여서 자동으로 확정하지 못했습니다."
    assert check_status_label(PARSE_UNCERTAIN) == "자동 해석 확인"


def test_check_group_values_are_in_display_order_registry():
    assert set(CHECK_GROUPS.values()) <= set(CHECK_GROUP_ORDER)


def test_check_method_descriptions_match_producer_semantics():
    assert (
        CHECK_METHOD_DESCRIPTIONS["prior_column_rollforward"]
        == "주석 증감표의 기초 장부금액 = 재무제표 전기 열 금액"
    )
    assert (
        CHECK_METHOD_DESCRIPTIONS["prior_column_fs_note"]
        == "당기 공시 안의 재무제표 전기 열 금액 = 주석 전기 열 금액"
    )
    assert (
        CHECK_METHOD_DESCRIPTIONS["asset_note_bridge_check"]
        == "자산 주석의 취득·처분 금액 ↔ 현금흐름표 투자활동 취득·처분 라인"
    )
    assert (
        CHECK_METHOD_DESCRIPTIONS["expense_allocation"]
        == "성격별 비용 주석의 상각비 = 기능별 배분 주석의 합계"
    )
    assert CHECK_METHOD_DESCRIPTIONS["cfs_note_match"].endswith(" (부호 무시, 크기 비교)")
    assert (
        CHECK_METHOD_DESCRIPTIONS["statement_note_row_reconciliation"]
        == "재무제표 계정의 당기 금액 = 본문에 표시된 주석의 해당 계정 금액"
    )


def test_table_unit_tolerance_registry_contains_internal_table_arithmetic_checks():
    from dart_footing_reconciler.report_frame import TABLE_UNIT_TOLERANCE_CHECK_TYPES

    assert {
        "total_check",
        "note_rollforward_check",
        "note_layout_formula_check",
        "appropriation_formula_check",
    } <= TABLE_UNIT_TOLERANCE_CHECK_TYPES
