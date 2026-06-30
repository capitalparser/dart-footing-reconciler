from dart_footing_reconciler.checks import ALL_STATUSES
from dart_footing_reconciler.disclosure_completeness import review_disclosure_completeness
from dart_footing_reconciler.document import (
    FullReport,
    ReportBlock,
    ReportSection,
    ReportTable,
    SourceLocation,
)


def _table(index: int, rows: list[list[str]], heading: str, *, note_no: str = "17") -> ReportTable:
    return ReportTable(
        index,
        rows,
        heading,
        SourceLocation(f"note:{note_no}", 0, index),
        unit_multiplier=1000,
    )


def _statement(rows: list[list[str]]) -> ReportSection:
    table = ReportTable(
        0,
        rows,
        "재무상태표",
        SourceLocation("statement:bs", 0, 0),
    )
    return ReportSection(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        [ReportBlock("table", "", table, table.location)],
        scope="consolidated",
    )


def _note(
    note_no: str,
    title: str,
    tables: list[ReportTable] | None = None,
    texts: list[str] | None = None,
) -> ReportSection:
    blocks: list[ReportBlock] = []
    for text in texts or []:
        location = SourceLocation(f"note:{note_no}", len(blocks))
        blocks.append(ReportBlock("text", text, None, location))
    for table in tables or []:
        blocks.append(ReportBlock("table", "", table, table.location))
    return ReportSection(f"note:{note_no}", title, "note", note_no, blocks, scope="consolidated")


def _report(notes: list[ReportSection], statements: list[ReportSection] | None = None) -> FullReport:
    return FullReport("sample.html", "Sample Co", statements or [], notes)


def test_source_backed_lease_liability_without_maturity_analysis_emits_reviewer_memo():
    report = _report(
        [
            _note(
                "17",
                "리스",
                [
                    _table(
                        1,
                        [
                            ["구분", "당기"],
                            ["유동 리스부채", "100"],
                            ["비유동 리스부채", "250"],
                            ["리스부채 합계", "350"],
                        ],
                        "17. 리스부채",
                    )
                ],
            )
        ]
    )

    result = review_disclosure_completeness(report)

    assert len(result.reviewer_memos) == 1
    memo = result.reviewer_memos[0]
    assert memo.finding_class == "disclosure_omission_candidate"
    assert memo.status == "needs_review"
    assert memo.priority == "low"
    assert memo.observed_item == "리스부채 금액"
    assert memo.expected_disclosure == "리스부채 만기분석"
    assert "리스부채 만기분석 공시는 확인되지 않았습니다" in memo.message
    assert "서술형 공시 가능" in memo.false_positive_risks
    assert memo.observed_evidence
    evidence = memo.observed_evidence[0]
    assert evidence.label == "유동 리스부채"
    assert evidence.raw_value == "100"
    assert evidence.amount == 100
    assert evidence.scaled_amount == 100_000
    assert evidence.unit_multiplier == 1000
    assert evidence.location == SourceLocation("note:17", 0, 1, 1, 1)
    assert "disclosure_omission_candidate" not in ALL_STATUSES


def test_lease_maturity_table_suppresses_omission_candidate():
    report = _report(
        [
            _note(
                "17",
                "리스",
                [
                    _table(
                        1,
                        [
                            ["구분", "당기"],
                            ["리스부채 합계", "350"],
                        ],
                        "17. 리스부채",
                    ),
                    _table(
                        2,
                        [
                            ["", "1년 이내", "1년 초과 5년 이내", "5년 초과", "합계"],
                            ["최소리스료", "120", "210", "20", "350"],
                            ["리스부채에 대한 이자비용", "10", "20", "5", "35"],
                            ["최소리스료의 현재가치", "100", "200", "15", "315"],
                        ],
                        "17. 리스 만기분석",
                    ),
                ],
            )
        ]
    )

    result = review_disclosure_completeness(report)

    assert result.reviewer_memos == ()
    assert result.interpretation_backlog == ()


def test_liquidity_maturity_table_with_lease_row_suppresses_omission_candidate():
    report = _report(
        [
            _note(
                "17",
                "리스",
                [_table(1, [["구분", "당기"], ["리스부채 합계", "350"]], "17. 리스부채")],
            ),
            _note(
                "31",
                "재무위험관리",
                [
                    _table(
                        2,
                        [
                            ["", "3개월 이내", "3개월 초과 1년 이내", "1년 초과 2년 이내", "합계"],
                            ["차입금 및 사채", "10", "20", "30", "60"],
                            ["리스부채", "40", "50", "60", "150"],
                            ["합계", "50", "70", "90", "210"],
                        ],
                        "31. 유동성위험 만기분석",
                        note_no="31",
                    )
                ],
            ),
        ]
    )

    result = review_disclosure_completeness(report)

    assert result.reviewer_memos == ()
    assert result.interpretation_backlog == ()


def test_narrative_only_lease_maturity_language_suppresses_omission_candidate():
    report = _report(
        [
            _note(
                "17",
                "리스",
                [_table(1, [["구분", "당기"], ["리스부채 합계", "350"]], "17. 리스부채")],
                texts=[
                    "리스부채의 계약상 만기는 1년 이내, 1년 초과 5년 이내 및 5년 초과로 구분하여 관리합니다."
                ],
            )
        ]
    )

    result = review_disclosure_completeness(report)

    assert result.reviewer_memos == ()
    assert result.interpretation_backlog == ()


def test_maturity_like_table_that_is_not_confidently_interpreted_goes_to_backlog_not_memo():
    report = _report(
        [
            _note(
                "17",
                "리스",
                [
                    _table(1, [["구분", "당기"], ["리스부채 합계", "350"]], "17. 리스부채"),
                    _table(
                        2,
                        [
                            ["구분", "1년 이내", "1년 초과 5년 이내", "5년 초과"],
                            ["리스부채", "100", "200", "50"],
                        ],
                        "17. 리스",
                    ),
                ],
            )
        ]
    )

    result = review_disclosure_completeness(report)

    assert result.reviewer_memos == ()
    assert len(result.interpretation_backlog) == 1
    backlog = result.interpretation_backlog[0]
    assert backlog.topic == "리스부채 만기분석"
    assert "만기분석 유사 표" in backlog.reason


def test_maturity_analysis_heading_with_lease_row_goes_to_backlog_not_memo():
    report = _report(
        [
            _note(
                "12",
                "차입금",
                [
                    _table(
                        1,
                        [
                            ["구분", "당기"],
                            ["총 리스부채", "350"],
                        ],
                        "12. 차입금",
                    ),
                    _table(
                        2,
                        [
                            ["", "2025년", "2026년", "2027년", "2028년", "2029년 이후", "합계"],
                            ["장기차입금, 미할인현금흐름", "1", "2", "3", "4", "5", "15"],
                            ["총 리스부채", "10", "20", "30", "40", "50", "150"],
                        ],
                        "12. 차입금 차입금의 만기분석에 대한 공시",
                    ),
                ],
            )
        ]
    )

    result = review_disclosure_completeness(report)

    assert result.reviewer_memos == ()
    assert len(result.interpretation_backlog) == 1


def test_multirow_header_maturity_table_goes_to_backlog_not_memo():
    report = _report(
        [
            _note(
                "17",
                "리스",
                [
                    _table(1, [["구분", "당기"], ["리스부채 합계", "350"]], "17. 리스부채"),
                    _table(
                        2,
                        [
                            ["", "", "", "", ""],
                            ["", "1년 이내", "1년 초과 5년 이내", "5년 초과", "합계"],
                            ["리스부채", "100", "200", "50", "350"],
                        ],
                        "17. 리스",
                    ),
                ],
            )
        ]
    )

    result = review_disclosure_completeness(report)

    assert result.reviewer_memos == ()
    assert len(result.interpretation_backlog) == 1


def test_residual_maturity_annual_columns_go_to_backlog_not_memo():
    report = _report(
        [
            _note(
                "17",
                "리스",
                [
                    _table(
                        1,
                        [
                            ["구분", "당기"],
                            ["총 리스부채", "350"],
                        ],
                        "17. 리스부채",
                    ),
                    _table(
                        2,
                        [
                            ["구분", "2025년", "2026년", "2027년", "2028년 이후", "합계"],
                            ["리스부채", "100", "120", "80", "50", "350"],
                        ],
                        "17. 리스부채 잔존만기",
                    ),
                ],
            )
        ]
    )

    result = review_disclosure_completeness(report)

    assert result.reviewer_memos == ()
    assert len(result.interpretation_backlog) == 1


def test_liquidity_risk_table_with_lease_row_but_unclear_columns_goes_to_backlog():
    report = _report(
        [
            _note(
                "4",
                "재무위험관리",
                [
                    _table(
                        1,
                        [
                            ["", "", "위험", "위험", "위험"],
                            ["", "", "", "", ""],
                            ["차입금", "100", "200", "300", "600"],
                            ["매입채무", "10", "20", "30", "60"],
                            ["리스부채", "1", "2", "3", "6"],
                        ],
                        "4. 재무위험관리 유동성위험 당기",
                        note_no="4",
                    )
                ],
            )
        ]
    )

    result = review_disclosure_completeness(report)

    assert result.reviewer_memos == ()
    assert len(result.interpretation_backlog) == 1


def test_rou_asset_without_explicit_lease_liability_amount_does_not_trigger():
    report = _report(
        [
            _note(
                "17",
                "리스",
                [
                    _table(
                        1,
                        [
                            ["구분", "당기"],
                            ["사용권자산", "500"],
                            ["단기리스료", "20"],
                        ],
                        "17. 리스",
                    )
                ],
            )
        ],
        statements=[_statement([["구분", "당기"], ["기타금융부채", "350"]])],
    )

    result = review_disclosure_completeness(report)

    assert result.reviewer_memos == ()
    assert result.interpretation_backlog == ()


def test_cashflow_lease_repayment_and_variable_lease_expense_do_not_trigger():
    report = _report(
        [
            _note(
                "17",
                "리스",
                [
                    _table(
                        1,
                        [
                            ["구분", "당기"],
                            ["리스부채 측정에 포함되지 않은 변동리스료", "20"],
                            ["리스부채 등의 인식으로 인한 사용권자산의 증감", "500"],
                        ],
                        "17. 리스",
                    )
                ],
            )
        ],
        statements=[
            ReportSection(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [
                    ReportBlock(
                        "table",
                        "",
                        ReportTable(
                            0,
                            [["구분", "당기"], ["리스부채의 감소", "100"]],
                            "현금흐름표",
                            SourceLocation("statement:cf", 0, 0),
                        ),
                        SourceLocation("statement:cf", 0, 0),
                    )
                ],
                scope="consolidated",
            )
        ],
    )

    result = review_disclosure_completeness(report)

    assert result.reviewer_memos == ()
    assert result.interpretation_backlog == ()
