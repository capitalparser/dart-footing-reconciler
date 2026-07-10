from dart_footing_reconciler._match_helpers import _is_prior_period_table
from dart_footing_reconciler.checks_note_note import check_note_note_matches
from dart_footing_reconciler.document import FullReport, ReportBlock, ReportSection, ReportTable, SourceLocation
from dart_footing_reconciler.label_resolver import AMBIGUOUS_MULTIPLE


def _note(note_no, title, table):
    return ReportSection(f"note:{note_no}", title, "note", note_no, [ReportBlock("table", "", table, table.location)])


def test_prior_period_table_detection_handles_quarter_standalone_tables():
    assert _is_prior_period_table("유형자산 변동내역 전분기 (단위 : 원)")
    assert _is_prior_period_table("무형자산 변동내역 전분기말")
    assert _is_prior_period_table("사용권자산 전반기 (단위 : 천원)")

    assert not _is_prior_period_table("유형자산 변동내역 당분기 (단위 : 원)")
    assert not _is_prior_period_table("유형자산 당분기 및 전분기 (단위 : 원)")


def test_check_note_note_matches_depreciation_between_ppe_and_expense_notes():
    ppe = _note("11", "유형자산", ReportTable(0, [["구분", "합계"], ["감가상각비", "300"]], "11. 유형자산", SourceLocation("note:11", 0, 0)))
    expense = _note("25", "비용의 성격별 분류", ReportTable(1, [["구분", "합계"], ["감가상각비", "300"]], "25. 비용", SourceLocation("note:25", 0, 1)))
    report = FullReport("sample.html", "Sample Co", [], [ppe, expense])
    results = check_note_note_matches(report, tolerance=0)
    assert results[0].check_type == "note_note_match"
    assert results[0].status == "matched"


def test_note_note_ties_depreciation_to_expense_breakdown():
    ppe = _note(
        "11",
        "유형자산",
        ReportTable(
            0,
            [["구분", "당기"], ["감가상각비", "100"]],
            "11. 유형자산",
            SourceLocation("note:11", 0, 0),
        ),
    )
    expense = _note(
        "25",
        "비용의 성격별 분류",
        ReportTable(
            1,
            [["구분", "당기"], ["감가상각비", "100"]],
            "25. 비용",
            SourceLocation("note:25", 0, 1),
        ),
    )

    results = check_note_note_matches(FullReport("s.html", "Co", [], [ppe, expense]), tolerance=0)

    matched = [result for result in results if result.status == "matched"]
    assert matched, [(result.note_no, result.status) for result in results]
    assert any(source.startswith("note:11/") for source in [e.source for e in matched[0].evidence])
    assert any(source.startswith("note:25/") for source in [e.source for e in matched[0].evidence])


def test_note_note_ties_depreciation_to_expense_nature_combined_label():
    ppe = _note(
        "12",
        "유형자산",
        ReportTable(
            0,
            [["구분", "당기"], ["감가상각비, 유형자산", "100"]],
            "12. 유형자산",
            SourceLocation("note:12", 0, 0),
        ),
    )
    expense = _note(
        "25",
        "비용의 성격별 분류",
        ReportTable(
            1,
            [["구분", "당기"], ["감가상각 및 무형자산상각 등", "120"]],
            "25. 비용의 성격별 분류",
            SourceLocation("note:25", 0, 1),
        ),
    )

    results = check_note_note_matches(FullReport("s.html", "Co", [], [ppe, expense]), tolerance=0)

    assert any(
        result.check_id.startswith("note_note:depreciation_expense_nature:")
        and result.status == "unexplained_gap"
        and {e.source.split("/table:", 1)[0] for e in result.evidence} == {"note:12", "note:25"}
        for result in results
    )


def test_check_note_note_reports_parse_uncertain_for_multiple_candidates():
    ppe = _note(
        "11",
        "유형자산",
        ReportTable(0, [["구분", "합계"], ["감가상각비", "300"], ["감가상각비 제조", "200"]], "11. 유형자산", SourceLocation("note:11", 0, 0)),
    )
    expense = _note(
        "25",
        "비용",
        ReportTable(1, [["구분", "합계"], ["감가상각비", "300"], ["감가상각비 제조", "200"]], "25. 비용", SourceLocation("note:25", 0, 1)),
    )

    results = check_note_note_matches(FullReport("sample.html", "Sample Co", [], [ppe, expense]), tolerance=0)

    assert results[0].status == "parse_uncertain"
    assert results[0].parse_uncertain_reason == AMBIGUOUS_MULTIPLE


def test_check_note_note_requires_all_multiple_candidates_to_agree():
    ppe = _note(
        "11",
        "유형자산",
        ReportTable(0, [["구분", "합계"], ["감가상각비", "300"], ["감가상각비 제조", "200"]], "11. 유형자산", SourceLocation("note:11", 0, 0)),
    )
    expense = _note(
        "25",
        "비용",
        ReportTable(1, [["구분", "합계"], ["감가상각비", "300"], ["사용권자산 감가상각비", "900"]], "25. 비용", SourceLocation("note:25", 0, 1)),
    )

    results = check_note_note_matches(FullReport("sample.html", "Sample Co", [], [ppe, expense]), tolerance=0)

    assert results[0].status == "parse_uncertain"
    assert results[0].parse_uncertain_reason == AMBIGUOUS_MULTIPLE


def test_note_note_depreciation_ignores_right_of_use_candidate():
    ppe = _note(
        "12",
        "유형자산",
        ReportTable(
            0,
            [["구분", "합계"], ["감가상각비, 유형자산", "(300)"]],
            "12. 유형자산",
            SourceLocation("note:12", 0, 0),
        ),
    )
    expense = _note(
        "28-1",
        "비용의 성격별 분류",
        ReportTable(
            1,
            [["구분", "합계"], ["감가상각비", "300"], ["감가상각비, 사용권자산", "20"]],
            "28-1. 비용의 성격별 분류",
            SourceLocation("note:28-1", 0, 1),
        ),
    )

    results = check_note_note_matches(FullReport("sample.html", "Sample Co", [], [ppe, expense]), tolerance=0)

    depreciation = [
        result for result in results if result.check_id.startswith("note_note:depreciation_expense:")
    ]
    assert depreciation and depreciation[0].status == "matched"
    assert depreciation[0].expected == 300
    assert depreciation[0].actual == 300
    depreciation_nature = [
        result for result in results if result.check_id.startswith("note_note:depreciation_expense_nature:")
    ]
    assert depreciation_nature and depreciation_nature[0].status == "matched"
    assert depreciation_nature[0].expected == 300
    assert depreciation_nature[0].actual == 300


def test_note_note_amortization_prefers_intangible_candidate():
    intangible = _note(
        "13",
        "무형자산",
        ReportTable(
            0,
            [["구분", "합계"], ["무형자산상각비", "(90)"]],
            "13. 무형자산",
            SourceLocation("note:13", 0, 0),
        ),
    )
    expense = _note(
        "28-1",
        "비용의 성격별 분류",
        ReportTable(
            1,
            [["구분", "합계"], ["감가상각비", "300"], ["감가상각비, 사용권자산", "20"], ["무형자산상각비", "90"]],
            "28-1. 비용의 성격별 분류",
            SourceLocation("note:28-1", 0, 1),
        ),
    )

    results = check_note_note_matches(
        FullReport("sample.html", "Sample Co", [], [intangible, expense]), tolerance=0
    )

    amortization = [
        result for result in results if result.check_id.startswith("note_note:amortization_expense:")
    ]
    assert amortization and amortization[0].status == "matched"
    assert amortization[0].expected == 90
    assert amortization[0].actual == 90


def test_check_note_note_matches_when_all_multiple_candidates_agree():
    ppe = _note(
        "11",
        "유형자산",
        ReportTable(0, [["구분", "합계"], ["감가상각비", "(300)"], ["감가상각비 배부합계", "300"]], "11. 유형자산", SourceLocation("note:11", 0, 0)),
    )
    expense = _note(
        "25",
        "비용",
        ReportTable(1, [["구분", "합계"], ["감가상각비", "300"]], "25. 비용", SourceLocation("note:25", 0, 1)),
    )

    results = check_note_note_matches(FullReport("sample.html", "Sample Co", [], [ppe, expense]), tolerance=0)

    assert results[0].status == "matched"
    assert results[0].expected == 300
    assert results[0].actual == 300
    assert len(results[0].evidence) == 3


def test_check_note_note_matches_current_period_amount_when_prior_table_is_separate():
    ppe = _note(
        "11",
        "유형자산",
        ReportTable(
            0,
            [["구분", "합계"], ["감가상각비", "(300)"]],
            "유형자산의 변동내역 당기",
            SourceLocation("note:11", 0, 0),
        ),
    )
    ppe.blocks.append(
        ReportBlock(
            "table",
            "",
            ReportTable(
                1,
                [["구분", "합계"], ["감가상각비", "(200)"]],
                "유형자산의 변동내역 전기",
                SourceLocation("note:11", 0, 1),
            ),
            SourceLocation("note:11", 0, 1),
        )
    )
    expense = _note(
        "25",
        "비용",
        ReportTable(
            2,
            [["구분", "합계"], ["감가상각비", "300"]],
            "비용의 성격별 분류 당기",
            SourceLocation("note:25", 0, 2),
        ),
    )

    results = check_note_note_matches(FullReport("sample.html", "Sample Co", [], [ppe, expense]), tolerance=0)

    assert results[0].status == "matched"
    assert results[0].expected == 300
    assert results[0].actual == 300


def test_check_note_note_matches_current_quarter_amount_when_prior_quarter_table_is_separate():
    ppe = _note(
        "10",
        "유형자산",
        ReportTable(
            0,
            [["구분", "합계"], ["감가상각비, 유형자산", "(300)"]],
            "유형자산 변동내역 당분기",
            SourceLocation("note:10", 0, 0),
        ),
    )
    ppe.blocks.append(
        ReportBlock(
            "table",
            "",
            ReportTable(
                1,
                [["구분", "합계"], ["감가상각비, 유형자산", "(200)"]],
                "유형자산 변동내역 전분기",
                SourceLocation("note:10", 0, 1),
            ),
            SourceLocation("note:10", 0, 1),
        )
    )
    expense = _note(
        "25-1",
        "비용의 성격별 분류",
        ReportTable(
            2,
            [["구분", "공시금액"], ["감가상각비", "300"], ["감가상각비, 사용권자산", "10"]],
            "비용의 성격별 분류 당분기",
            SourceLocation("note:25-1", 0, 2),
        ),
    )

    results = check_note_note_matches(FullReport("sample.html", "Sample Co", [], [ppe, expense]), tolerance=0)

    depreciation = [
        result for result in results if result.check_id.startswith("note_note:depreciation_expense:")
    ]
    assert depreciation and depreciation[0].status == "matched"
    assert depreciation[0].expected == 300
    assert depreciation[0].actual == 300
