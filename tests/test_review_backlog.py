from dart_footing_reconciler.checks import (
    CheckEvidence,
    CheckResult,
    PARSE_UNCERTAIN,
    UNEXPLAINED_GAP,
)
from dart_footing_reconciler.document import (
    FullReport,
    ReportBlock,
    ReportSection,
    ReportTable,
    SourceLocation,
)
from dart_footing_reconciler.review_backlog import BACKLOG_RULES, build_review_backlog


def _table(section_id: str, index: int, rows: list[list[str]], heading: str) -> ReportTable:
    return ReportTable(index, rows, heading, SourceLocation(section_id, 0, index))


def _note(note_no: str, title: str, table: ReportTable) -> ReportSection:
    return ReportSection(
        f"note:{note_no}",
        title,
        "note",
        note_no,
        [ReportBlock("table", "", table, table.location)],
        scope="consolidated",
    )


def _report(notes: list[ReportSection]) -> FullReport:
    return FullReport("sample.html", "Sample Co", [], notes)


def test_backlog_rules_are_data_driven_and_company_free():
    assert BACKLOG_RULES
    for rule in BACKLOG_RULES:
        assert rule.rule_id
        assert rule.category
        assert rule.reviewer_question
        assert rule.backend_action
        assert not hasattr(rule, "company")
        assert not hasattr(rule, "company_name")


def test_parse_uncertain_label_gap_becomes_candidate_dictionary_backlog():
    table = _table("note:12", 3, [["구분", "당기"], ["기말 유형자산", "100"]], "12. 유형자산")
    report = _report([_note("12", "유형자산", table)])
    check = CheckResult(
        "asset-label",
        "fs_note_match",
        PARSE_UNCERTAIN,
        "report",
        "12",
        "유형자산 본문-주석 금액 대사",
        None,
        None,
        None,
        1,
        "공시에서 해당 계정과목을 찾지 못했습니다.",
        [CheckEvidence("유형자산", None, "note:12/table:3/row:1/col:1")],
        parse_uncertain_reason="LABEL_NOT_FOUND",
        account_key="property_plant_equipment",
    )

    backlog = build_review_backlog(report, [check])

    assert len(backlog.items) == 1
    item = backlog.items[0]
    assert item.rule_id == "label_candidate_gap"
    assert item.category == "후보 사전 보강"
    assert item.account_key == "property_plant_equipment"
    assert item.check_id == "asset-label"
    assert item.evidence_sources == ("note:12/table:3/row:1/col:1",)
    assert "동의어" in item.backend_action
    assert item.semantic_table_sources == ("note:12/table:3",)


def test_unresolved_multi_header_table_becomes_structure_backlog():
    table = _table(
        "note:33",
        8,
        [
            ["", "", ""],
            ["", "당기", "전기"],
            ["파생상품자산", "100", "90"],
        ],
        "33. 금융상품",
    )
    report = _report([_note("33", "금융상품", table)])
    check = CheckResult(
        "derivative-layout",
        "note_layout_formula_check",
        UNEXPLAINED_GAP,
        "note",
        "33",
        "파생상품 표 구조 검토",
        90,
        100,
        10,
        1,
        "표 구조 해석이 불충분합니다.",
        [CheckEvidence("파생상품자산", 100, "note:33/table:8/row:2/col:1")],
    )

    backlog = build_review_backlog(report, [check])

    assert len(backlog.items) == 1
    item = backlog.items[0]
    assert item.rule_id == "table_structure_backlog"
    assert item.category == "표 구조 해석 보강"
    assert "multi_header_unresolved" in item.semantic_flags
    assert item.semantic_table_sources == ("note:33/table:8",)
    assert "머리글" in item.backend_action


def test_statement_note_gap_becomes_mapping_backlog():
    table = _table("note:6", 1, [["구분", "당기"], ["계약자산", "100"]], "6. 매출채권")
    report = _report([_note("6", "매출채권", table)])
    check = CheckResult(
        "contract-asset-map",
        "fs_note_ref_amount_match",
        UNEXPLAINED_GAP,
        "report",
        "6",
        "계약자산 본문-주석 금액 대사",
        100,
        80,
        -20,
        1,
        "본문 금액과 참조 주석 금액이 다릅니다.",
        [
            CheckEvidence("계약자산 (주6)", 100, "statement:bs/table:0/row:1/col:1"),
            CheckEvidence("주석 6 계약자산", 80, "note:6/table:1/row:1/col:1"),
        ],
        account_key="contract_assets",
    )

    backlog = build_review_backlog(report, [check])

    assert len(backlog.items) == 1
    item = backlog.items[0]
    assert item.rule_id == "statement_note_mapping_backlog"
    assert item.category == "본문-주석 매핑 보강"
    assert item.account_key == "contract_assets"
    assert item.evidence_sources == (
        "statement:bs/table:0/row:1/col:1",
        "note:6/table:1/row:1/col:1",
    )
    assert "본문 계정과 주석 후보" in item.reviewer_question
