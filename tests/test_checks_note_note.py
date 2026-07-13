from dart_footing_reconciler.checks_note_note import check_note_note_matches
from dart_footing_reconciler.document import FullReport, ReportBlock, ReportSection, ReportTable, SourceLocation
from dart_footing_reconciler.label_resolver import AMBIGUOUS_MULTIPLE


def _note(note_no, title, table):
    return ReportSection(f"note:{note_no}", title, "note", note_no, [ReportBlock("table", "", table, table.location)])


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


def test_note_note_does_not_emit_same_source_relation():
    tax = _note(
        "20",
        "이연법인세",
        ReportTable(
            0,
            [["구분", "당기"], ["일시적차이", "100"]],
            "20. 이연법인세",
            SourceLocation("note:20", 0, 0),
        ),
    )

    results = check_note_note_matches(
        FullReport("sample.html", "Sample Co", [], [tax]),
        tolerance=0,
    )

    assert not any("tax_temporary_difference" in result.check_id for result in results)


def test_note_note_does_not_emit_same_source_relation_without_label_exclusions():
    shared = _note(
        "11",
        "유형자산 및 비용",
        ReportTable(
            0,
            [["구분", "당기"], ["감가상각비", "100"]],
            "11. 유형자산 및 비용",
            SourceLocation("note:11", 0, 0),
        ),
    )

    results = check_note_note_matches(
        FullReport("sample.html", "Sample Co", [], [shared]),
        tolerance=0,
    )

    assert not any("depreciation_expense:" in result.check_id for result in results)


def test_note_note_tax_relation_requires_non_deferred_tax_right_section():
    first = _note(
        "20",
        "이연법인세",
        ReportTable(
            0,
            [["구분", "당기"], ["일시적차이", "100"]],
            "20. 이연법인세",
            SourceLocation("note:20", 0, 0),
        ),
    )
    second = _note(
        "21",
        "이연법인세자산 및 부채",
        ReportTable(
            1,
            [["구분", "당기"], ["일시적차이", "100"]],
            "21. 이연법인세자산 및 부채",
            SourceLocation("note:21", 0, 1),
        ),
    )

    results = check_note_note_matches(
        FullReport("sample.html", "Sample Co", [], [first, second]),
        tolerance=0,
    )

    assert not any("tax_temporary_difference" in result.check_id for result in results)


def test_note_note_tax_relation_uses_distinct_note_sources():
    deferred_tax = _note(
        "20",
        "이연법인세",
        ReportTable(
            0,
            [["구분", "당기"], ["일시적차이", "100"]],
            "20. 이연법인세",
            SourceLocation("note:20", 0, 0),
        ),
    )
    tax_expense = _note(
        "30",
        "법인세비용",
        ReportTable(
            1,
            [["구분", "당기"], ["일시적차이", "100"]],
            "30. 법인세비용",
            SourceLocation("note:30", 0, 1),
        ),
    )

    results = check_note_note_matches(
        FullReport("sample.html", "Sample Co", [], [deferred_tax, tax_expense]),
        tolerance=0,
    )

    relation = next(
        result for result in results if "tax_temporary_difference" in result.check_id
    )
    assert relation.check_id == "note_note:tax_temporary_difference:20:30"
    assert relation.status == "matched"
    assert len({evidence.source for evidence in relation.evidence}) == 2


def test_note_note_lease_uses_exact_current_noncurrent_label_boundaries():
    lease = _note(
        "21",
        "리스부채",
        ReportTable(
            0,
            [
                ["구분", "당기"],
                ["유동 리스부채", "100"],
                ["비유동 리스부채", "200"],
                ["비유동 리스부채의 유동성대체부분", "999"],
            ],
            "21. 리스부채",
            SourceLocation("note:21", 0, 0),
        ),
    )

    results = check_note_note_matches(
        FullReport("sample.html", "Sample Co", [], [lease]),
        tolerance=0,
    )

    relation = next(
        result
        for result in results
        if "lease_liability_current_noncurrent" in result.check_id
    )
    assert relation.status == "unexplained_gap"
    assert relation.expected == 100
    assert relation.actual == 200
    assert [evidence.label for evidence in relation.evidence] == [
        "유동 리스부채",
        "비유동 리스부채",
    ]
    assert len({evidence.source for evidence in relation.evidence}) == 2


def test_note_note_lease_equal_distinct_rows_still_matches():
    lease = _note(
        "21",
        "리스부채",
        ReportTable(
            0,
            [
                ["구분", "당기"],
                ["유동 리스부채", "100"],
                ["비유동 리스부채", "100"],
            ],
            "21. 리스부채",
            SourceLocation("note:21", 0, 0),
        ),
    )

    results = check_note_note_matches(
        FullReport("sample.html", "Sample Co", [], [lease]),
        tolerance=0,
    )

    relation = next(
        result
        for result in results
        if "lease_liability_current_noncurrent" in result.check_id
    )
    assert relation.status == "matched"
    assert len(relation.evidence) == 2
    assert len({evidence.source for evidence in relation.evidence}) == 2


def test_note_note_lease_movement_row_does_not_satisfy_current_level():
    lease = _note(
        "21",
        "리스부채",
        ReportTable(
            0,
            [
                ["구분", "당기"],
                ["리스부채의 유동성 대체", "100"],
                ["비유동 리스부채", "100"],
            ],
            "21. 리스부채",
            SourceLocation("note:21", 0, 0),
        ),
    )

    results = check_note_note_matches(
        FullReport("sample.html", "Sample Co", [], [lease]),
        tolerance=0,
    )

    assert not any(
        "lease_liability_current_noncurrent" in result.check_id
        for result in results
    )


def test_note_note_lease_noncurrent_row_alone_abstains():
    lease = _note(
        "21",
        "리스부채",
        ReportTable(
            0,
            [["구분", "당기"], ["비유동 리스부채", "100"]],
            "21. 리스부채",
            SourceLocation("note:21", 0, 0),
        ),
    )

    results = check_note_note_matches(
        FullReport("sample.html", "Sample Co", [], [lease]),
        tolerance=0,
    )

    assert not any(
        "lease_liability_current_noncurrent" in result.check_id
        for result in results
    )
