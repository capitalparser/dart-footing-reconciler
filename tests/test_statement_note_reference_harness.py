from dart_footing_reconciler.checks import MATCHED, PARSE_UNCERTAIN, UNEXPLAINED_GAP
from dart_footing_reconciler.document import (
    FullReport,
    ReportBlock,
    ReportSection,
    ReportTable,
    SourceLocation,
)
from dart_footing_reconciler.statement_note_reference_harness import (
    check_statement_note_references,
)


def _section(
    section_id: str,
    title: str,
    kind: str,
    note_no: str,
    table: ReportTable | None = None,
    *,
    text: str = "",
    scope: str = "consolidated",
) -> ReportSection:
    blocks: list[ReportBlock] = []
    if table is not None:
        blocks.append(ReportBlock("table", "", table, table.location))
    if text:
        blocks.append(ReportBlock("text", text, None, SourceLocation(section_id, len(blocks))))
    return ReportSection(section_id, title, kind, note_no, blocks, scope)


def _statement(*rows: list[str]) -> ReportSection:
    table = ReportTable(
        0,
        [["구분", "당기"], *rows],
        "재무상태표",
        SourceLocation("statement:bs", 0, 0),
    )
    return _section("statement:bs", "재무상태표", "statement", "", table)


def _note(note_no: str, title: str, rows: list[list[str]]) -> ReportSection:
    index = int(note_no.split("-", 1)[0])
    table = ReportTable(
        index,
        rows,
        f"{note_no}. {title}",
        SourceLocation(f"note:{note_no}", 0, index),
    )
    return _section(f"note:{note_no}", title, "note", note_no, table)


def _note_text(note_no: str, title: str, text: str) -> ReportSection:
    return _section(f"note:{note_no}", title, "note", note_no, text=text)


def test_row_reconciliation_uses_displayed_note_amount_and_emits_one_result():
    report = FullReport(
        "s.html",
        "Co",
        [_statement(["유형자산 (주10,20)", "100"])],
        [
            _note("10", "유형자산", [["구분", "당기"], ["기말 장부금액", "100"]]),
            _note_text("20", "약정사항", "유형자산 담보 제공 내역"),
        ],
    )

    checks = check_statement_note_references(report, tolerance=1)

    assert len(checks) == 1
    check = checks[0]
    assert check.status == MATCHED
    assert check.title == "유형자산 주석 금액 대사"
    assert (check.expected, check.actual, check.difference) == (100, 100, 0)
    assert check.note_no == "10"
    assert {item.role for item in check.evidence} >= {
        "statement_amount",
        "displayed_note_reference",
        "note_amount",
        "related_note_reference",
    }
    assert check.evidence[0].source == "statement:bs/table:0/row:1/col:1"
    assert any(
        item.role == "note_amount" and item.source == "note:10/table:10/row:1/col:1"
        for item in check.evidence
    )


def test_row_reconciliation_reports_numeric_mismatch_without_selecting_by_equality():
    report = FullReport(
        "s.html",
        "Co",
        [_statement(["유형자산 (주10)", "100"])],
        [_note("10", "유형자산", [["구분", "당기"], ["기말 장부금액", "120"]])],
    )

    check = check_statement_note_references(report, tolerance=1)[0]

    assert check.status == UNEXPLAINED_GAP
    assert (check.expected, check.actual, check.difference) == (100, 120, -20)


def test_row_reconciliation_uses_net_carrying_total_column_not_gross_amount():
    report = FullReport(
        "s.html",
        "Co",
        [_statement(["유형자산 (주10)", "100"])],
        [
            _note(
                "10",
                "유형자산",
                [
                    ["구분", "총장부금액", "감가상각누계액", "장부금액 합계"],
                    ["기말 유형자산", "180", "(80)", "100"],
                ],
            )
        ],
    )

    check = check_statement_note_references(report, tolerance=1)[0]

    assert check.status == MATCHED
    assert check.actual == 100
    assert any(
        item.role == "note_amount" and item.source.endswith("/row:1/col:3")
        for item in check.evidence
    )


def test_row_reconciliation_does_not_pick_between_equal_rank_amounts():
    report = FullReport(
        "s.html",
        "Co",
        [_statement(["유형자산 (주10)", "100"])],
        [
            _note(
                "10",
                "유형자산",
                [["구분", "당기"], ["기말 장부금액", "100"], ["기말 장부금액", "120"]],
            )
        ],
    )

    check = check_statement_note_references(report, tolerance=1)[0]

    assert check.status == PARSE_UNCERTAIN
    assert check.actual is None
    assert check.parse_uncertain_reason == "AMBIGUOUS_MULTIPLE"
    assert sum(item.role == "candidate_note_amount" for item in check.evidence) == 2


def test_every_material_statement_row_with_refs_gets_one_result_without_taxonomy():
    report = FullReport(
        "s.html",
        "Co",
        [_statement(["회사고유공시계정 (주9)", "700"])],
        [_note_text("9", "회사고유공시", "관련 설명")],
    )

    checks = check_statement_note_references(report, tolerance=1)

    assert len(checks) == 1
    assert checks[0].status == PARSE_UNCERTAIN
    assert checks[0].expected == 700
    assert checks[0].actual is None
    assert checks[0].parse_uncertain_reason == "LABEL_NOT_FOUND"


def test_unclassified_statement_row_matches_direct_label_amount_in_displayed_note():
    report = FullReport(
        "s.html",
        "Co",
        [_statement(["회사고유공시계정 (주9)", "700"])],
        [_note("9", "회사고유공시", [["구분", "당기"], ["회사고유공시계정", "700"]])],
    )

    check = check_statement_note_references(report, tolerance=1)[0]

    assert check.status == MATCHED
    assert check.actual == 700
    assert any(item.role == "note_amount" for item in check.evidence)


def test_cashflow_rows_are_left_to_the_separate_cashflow_reconciliation_harness():
    table = ReportTable(
        3,
        [["구분", "당기"], ["당기순이익조정을 위한 가감 (주29)", "100"]],
        "현금흐름표",
        SourceLocation("statement:cf", 0, 3),
    )
    cashflow = _section("statement:cf", "현금흐름표", "statement", "", table)
    report = FullReport(
        "s.html",
        "Co",
        [cashflow],
        [_note("29", "현금흐름", [["구분", "당기"], ["조정 합계", "100"]])],
    )

    assert check_statement_note_references(report, tolerance=1) == []


def test_missing_displayed_note_is_a_gap_with_statement_and_reference_sources():
    report = FullReport(
        "s.html",
        "Co",
        [_statement(["유형자산 (주99)", "100"])],
        [],
    )

    check = check_statement_note_references(report, tolerance=1)[0]

    assert check.status == UNEXPLAINED_GAP
    assert check.parse_uncertain_reason == "TABLE_NOT_FOUND"
    assert {item.role for item in check.evidence} == {
        "statement_amount",
        "displayed_note_reference",
    }


def test_two_referenced_statement_rows_emit_two_results_not_one_per_note():
    report = FullReport(
        "s.html",
        "Co",
        [
            _statement(
                ["유형자산 (주10,20)", "100"],
                ["무형자산 (주11,20)", "50"],
            )
        ],
        [
            _note("10", "유형자산", [["구분", "당기"], ["기말 장부금액", "100"]]),
            _note("11", "무형자산", [["구분", "당기"], ["기말 장부금액", "50"]]),
            _note_text("20", "약정사항", "자산 관련 약정"),
        ],
    )

    checks = check_statement_note_references(report, tolerance=1)

    assert len(checks) == 2
    assert [check.expected for check in checks] == [100, 50]
    assert all(check.status == MATCHED for check in checks)


def test_exact_account_in_undisplayed_note_is_reported_as_missing_reference():
    report = FullReport(
        "s.html",
        "Co",
        [_statement(["유형자산 (주10)", "100"])],
        [
            _note("10", "유형자산", [["구분", "당기"], ["유형자산", "100"]]),
            _note("12", "담보", [["구분", "당기"], ["유형자산", "100"]]),
        ],
    )

    check = check_statement_note_references(report, tolerance=1)[0]

    assert check.status == PARSE_UNCERTAIN
    assert (check.expected, check.actual, check.difference) == (100, 100, 0)
    missing = [item for item in check.evidence if item.role == "missing_note_reference"]
    assert [(item.label, item.source) for item in missing] == [
        ("주석 12 유형자산", "note:12/table:12/row:1/col:1")
    ]


def test_similar_detail_label_is_not_reported_as_missing_reference():
    report = FullReport(
        "s.html",
        "Co",
        [_statement(["유형자산 (주10)", "100"])],
        [
            _note("10", "유형자산", [["구분", "당기"], ["유형자산", "100"]]),
            _note("12", "투자활동", [["구분", "당기"], ["유형자산 취득", "100"]]),
        ],
    )

    check = check_statement_note_references(report, tolerance=1)[0]

    assert check.status == MATCHED
    assert not any(item.role == "missing_note_reference" for item in check.evidence)


def test_same_taxonomy_family_with_different_account_label_is_not_missing():
    report = FullReport(
        "s.html",
        "Co",
        [_statement(["유형자산 (주10)", "100"])],
        [
            _note("10", "유형자산", [["구분", "당기"], ["유형자산", "100"]]),
            _note(
                "12-1",
                "사용권자산",
                [["구분", "당기"], ["기말 사용권자산", "100"]],
            ),
        ],
    )

    check = check_statement_note_references(report, tolerance=1)[0]

    assert check.status == MATCHED
    assert not any(item.role == "missing_note_reference" for item in check.evidence)


def test_account_in_another_displayed_note_is_not_missing():
    report = FullReport(
        "s.html",
        "Co",
        [_statement(["유형자산 (주10,12)", "100"])],
        [
            _note("10", "유형자산", [["구분", "당기"], ["유형자산", "100"]]),
            _note("12", "담보", [["구분", "당기"], ["유형자산", "100"]]),
        ],
    )

    check = check_statement_note_references(report, tolerance=1)[0]

    assert check.status == MATCHED
    assert not any(item.role == "missing_note_reference" for item in check.evidence)
    assert any(item.role == "related_note_reference" for item in check.evidence)
