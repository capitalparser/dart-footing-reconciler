from dart_footing_reconciler.document import (
    FullReport,
    ReportBlock,
    ReportSection,
    ReportTable,
    SourceLocation,
)
from dart_footing_reconciler.checks_reconciliation import check_reconciliation_targets
from dart_footing_reconciler.label_resolver import LOW_CONFIDENCE_MATCH


def _section(section_id, title, kind, note_no, rows):
    table = ReportTable(0, rows, title, SourceLocation(section_id, 0, 0))
    return ReportSection(
        section_id,
        title,
        kind,
        note_no,
        [ReportBlock("table", "", table, table.location)],
    )


def _section_with_unit(section_id, title, kind, note_no, rows, unit_multiplier):
    table = ReportTable(
        0,
        rows,
        title,
        SourceLocation(section_id, 0, 0),
        unit_multiplier=unit_multiplier,
    )
    return ReportSection(
        section_id,
        title,
        kind,
        note_no,
        [ReportBlock("table", "", table, table.location)],
    )


def test_check_reconciliation_targets_keeps_matched_financing_evidence_clean_after_subset_selection():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                    [["구분", "당기"], ["차입금의 차입", "100"], ["차입금의 상환", "(40)"]],
            )
        ],
        [
            _section(
                "note:20",
                "차입금 재무활동에서 생기는 부채의 변동",
                "note",
                "20",
                [
                    ["구분", "차입", "상환", "증가"],
                    ["차입금", "100", "(40)", "3"],
                ],
            )
        ],
    )

    result = next(
        check for check in check_reconciliation_targets(report, tolerance=0)
        if check.title == "borrowings.financing_cashflow"
    )

    assert result.status == "matched"
    assert result.actual == 60
    assert "후보 제외" not in result.reason
    assert not any("excluded note 20" in evidence.label for evidence in result.evidence)


def test_check_reconciliation_targets_matches_bs_to_note_ending_balance():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:bs",
                "재무상태표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산", "1,000"]],
            )
        ],
        [
            _section(
                "note:11",
                "유형자산",
                "note",
                "11",
                [["구분", "합계"], ["기말 장부금액", "1,000"]],
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)

    assert [result.check_id for result in results] == [
        "reconciliation:property_plant_equipment.balance"
    ]
    assert results[0].check_type == "primary_balance_reconciliation"
    assert results[0].status == "matched"
    assert [(e.label, e.amount) for e in results[0].evidence] == [
        ("statement 유형자산", 1000),
        ("note 11 기말 장부금액", 1000),
    ]


def test_check_reconciliation_targets_reports_unexplained_gap_for_balance_difference():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:bs",
                "재무상태표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산", "1,000"]],
            )
        ],
        [
            _section(
                "note:11",
                "유형자산",
                "note",
                "11",
                [["구분", "합계"], ["기말 장부금액", "980"]],
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)

    assert results[0].status == "unexplained_gap"
    assert results[0].expected == 1000
    assert results[0].actual == 980
    assert results[0].difference == -20


def test_check_reconciliation_targets_flags_balance_candidate_when_difference_exceeds_statement_amount():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:bs",
                "재무상태표",
                "statement",
                "",
                [["구분", "당기"], ["무형자산", "100,000"]],
            )
        ],
        [
            _section(
                "note:15",
                "무형자산",
                "note",
                "15",
                [["구분", "합계"], ["기말 장부금액", "672,900"]],
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)

    assert results[0].status == "parse_uncertain"
    assert results[0].expected == 100_000
    assert results[0].actual == 672_900
    assert results[0].difference == 572_900
    assert "candidate difference exceeds statement amount" in results[0].reason
    assert results[0].parse_uncertain_reason == LOW_CONFIDENCE_MATCH


def test_check_reconciliation_targets_matches_asset_total_row_with_carrying_amount_column():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:bs",
                "재무상태표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산", "245,745,777,000"]],
            )
        ],
        [
            _section_with_unit(
                "note:8",
                "유형자산",
                "note",
                "8",
                [
                    ["구분", "당기말", "당기말", "당기말", "당기말", "전기말"],
                    ["구분", "취득원가", "감가상각 누계액", "정부보조금", "장부금액", "장부금액"],
                    ["토지", "64,487,052", "-", "-", "64,487,052", "64,487,052"],
                    ["합계", "302,969,470", "(57,111,821)", "(111,872)", "245,745,777", "235,596,169"],
                ],
                1000,
            ),
            _section_with_unit(
                "note:8:fair-value",
                "유형자산 공정가치 측정",
                "note",
                "8",
                [["구분", "수준 3"], ["당기말", "64,487,052"], ["전기말", "64,487,052"]],
                1000,
            ),
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    ppe = [
        result
        for result in results
        if result.check_id == "reconciliation:property_plant_equipment.balance"
    ]

    assert len(ppe) == 1
    assert ppe[0].status == "matched"
    assert ppe[0].expected == 245_745_777_000
    assert ppe[0].actual == 245_745_777_000
    assert ppe[0].difference == 0
    assert [(e.label, e.amount) for e in ppe[0].evidence] == [
        ("statement 유형자산", 245_745_777_000),
        ("note 8 합계", 245_745_777_000),
    ]


def test_check_reconciliation_targets_matches_asset_total_row_with_unit_and_period_header_bands():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:bs",
                "재무상태표",
                "statement",
                "",
                [["구분", "당기"], ["무형자산", "1,416,620,042"]],
            )
        ],
        [
            _section(
                "note:15",
                "무형자산",
                "note",
                "15",
                [
                    ["(단위 : 원)", "(단위 : 원)", "(단위 : 원)", "(단위 : 원)", "(단위 : 원)", "(단위 : 원)", "(단위 : 원)"],
                    ["과 목", "제 60(당) 기말", "제 60(당) 기말", "제 60(당) 기말", "제 59(전) 기말", "제 59(전) 기말", "제 59(전) 기말"],
                    ["과 목", "취득원가", "상각누계액", "합 계", "취득원가", "상각누계액", "합 계"],
                    ["회원권", "816,620,042", "-", "816,620,042", "891,456,969", "-", "891,456,969"],
                    ["특허권", "600,000,000", "-", "600,000,000", "-", "-", "-"],
                    ["합 계", "1,416,620,042", "-", "1,416,620,042", "891,456,969", "-", "891,456,969"],
                ],
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    intangible = [
        result
        for result in results
        if result.check_id == "reconciliation:intangible_assets.balance"
    ]

    assert len(intangible) == 1
    assert intangible[0].status == "matched"
    assert intangible[0].expected == 1_416_620_042
    assert intangible[0].actual == 1_416_620_042
    assert intangible[0].difference == 0


def test_check_reconciliation_targets_matches_intangible_balance_excluding_goodwill_from_combined_table():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:bs",
                "재무상태표",
                "statement",
                "",
                [["구분", "당기"], ["무형자산", "27,646,934,000"]],
            )
        ],
        [
            _section_with_unit(
                "note:10",
                "무형자산",
                "note",
                "10",
                [
                    ["", "", "무형자산 및 영업권", "무형자산 및 영업권", "무형자산 및 영업권 합계"],
                    ["", "", "영업권", "영업권 이외의 무형자산", "무형자산 및 영업권 합계"],
                    ["", "", "영업권", "개발비", "무형자산 및 영업권 합계"],
                    ["", "", "장부금액 합계", "장부금액 합계", "무형자산 및 영업권 합계"],
                    ["기말 무형자산 및 영업권", "기말 무형자산 및 영업권", "50,274,935", "27,646,934", "77,921,869"],
                ],
                1000,
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    intangible = [
        result
        for result in results
        if result.check_id == "reconciliation:intangible_assets.balance"
    ]

    assert len(intangible) == 1
    assert intangible[0].status == "matched"
    assert intangible[0].actual == 27_646_934_000
    assert [(e.label, e.amount) for e in intangible[0].evidence] == [
        ("statement 무형자산", 27_646_934_000),
        ("note 10 기말 무형자산 및 영업권", 27_646_934_000),
    ]


def test_check_reconciliation_targets_preserves_combined_intangible_and_goodwill_total_candidate():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:bs",
                "재무상태표",
                "statement",
                "",
                [["구분", "당기"], ["무형자산", "77,921,869,000"]],
            )
        ],
        [
            _section_with_unit(
                "note:10",
                "무형자산",
                "note",
                "10",
                [
                    ["", "", "무형자산 및 영업권", "무형자산 및 영업권", "무형자산 및 영업권 합계"],
                    ["", "", "영업권", "영업권 이외의 무형자산", "무형자산 및 영업권 합계"],
                    ["", "", "영업권", "개발비", "무형자산 및 영업권 합계"],
                    ["", "", "장부금액 합계", "장부금액 합계", "무형자산 및 영업권 합계"],
                    ["기말 무형자산 및 영업권", "기말 무형자산 및 영업권", "50,274,935", "27,646,934", "77,921,869"],
                ],
                1000,
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    intangible = [
        result
        for result in results
        if result.check_id == "reconciliation:intangible_assets.balance"
    ]

    assert len(intangible) == 1
    assert intangible[0].status == "matched"
    assert intangible[0].actual == 77_921_869_000


def test_check_reconciliation_targets_matches_asset_ending_row_with_asset_family_total_column():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:bs",
                "재무상태표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산", "1,289,154,000,000"]],
            )
        ],
        [
            _section_with_unit(
                "note:12",
                "유형자산",
                "note",
                "12",
                [
                    ["", "총장부금액", "감가상각누계액 및 상각누계액", "손상차손누계액", "유형자산 합계"],
                    ["기초 유형자산", "1,939,380", "(725,161)", "(9,699)", "1,204,520"],
                    ["기말 유형자산", "2,082,524", "(783,671)", "(9,699)", "1,289,154"],
                ],
                1_000_000,
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    ppe = [
        result
        for result in results
        if result.check_id == "reconciliation:property_plant_equipment.balance"
    ]

    assert len(ppe) == 1
    assert ppe[0].status == "matched"
    assert ppe[0].expected == 1_289_154_000_000
    assert ppe[0].actual == 1_289_154_000_000
    assert ppe[0].difference == 0


def test_check_reconciliation_targets_prefers_ppe_total_after_government_grant_column():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:bs",
                "재무상태표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산", "245,745,777,000"]],
            )
        ],
        [
            _section_with_unit(
                "note:8",
                "유형자산",
                "note",
                "8",
                [
                    ["구분", "취득원가", "감가상각누계액", "정부보조금", "합계"],
                    ["토지", "64,487,052", "-", "-", "64,487,052"],
                    ["합계", "302,969,470", "(57,111,821)", "(111,872)", "245,745,777"],
                ],
                1000,
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    ppe = [
        result
        for result in results
        if result.check_id == "reconciliation:property_plant_equipment.balance"
    ]

    assert len(ppe) == 1
    assert ppe[0].status == "matched"
    assert ppe[0].actual == 245_745_777_000


def test_check_reconciliation_targets_nets_trade_receivable_allowance_balance():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:bs",
                "재무상태표",
                "statement",
                "",
                [["구분", "당기"], ["매출채권", "970"]],
            )
        ],
        [
            _section(
                "note:8",
                "매출채권",
                "note",
                "8",
                [
                    ["구분", "당기"],
                    ["총 장부금액", "1,000"],
                    ["기말 손실충당금", "30"],
                ],
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    receivables = [
        result
        for result in results
        if result.check_id == "reconciliation:trade_receivables.balance"
    ]

    assert len(receivables) == 1
    assert receivables[0].status == "matched"
    assert receivables[0].expected == 970
    assert receivables[0].actual == 970
    assert receivables[0].difference == 0
    assert [(e.label, e.amount) for e in receivables[0].evidence] == [
        ("statement 매출채권", 970),
        ("note 8 총 장부금액 + 기말 손실충당금", 970),
    ]


def test_check_reconciliation_targets_sums_trade_receivable_current_noncurrent_with_hidden_allowance_label():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:bs",
                "재무상태표",
                "statement",
                "",
                [["구분", "당기"], ["매출채권", "587,499,958"]],
            )
        ],
        [
            _section(
                "note:8",
                "매출채권",
                "note",
                "8",
                [
                    ["", "", "유동매출채권", "비유동매출채권"],
                    ["장부금액", "총장부금액", "599,658,192", "2,742,878"],
                    ["장부금액", "손상차손누계액", "(14,901,112)", ""],
                ],
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    receivables = [
        result
        for result in results
        if result.check_id == "reconciliation:trade_receivables.balance"
    ]

    assert len(receivables) == 1
    assert receivables[0].status == "matched"
    assert receivables[0].expected == 587_499_958
    assert receivables[0].actual == 587_499_958
    assert receivables[0].difference == 0
    assert [(e.label, e.amount) for e in receivables[0].evidence] == [
        ("statement 매출채권", 587_499_958),
        ("note 8 장부금액 / 총장부금액 + 장부금액 / 손상차손누계액", 587_499_958),
    ]


def test_check_reconciliation_targets_combines_trade_receivable_current_and_noncurrent_aggregate_rows_in_wide_detail_table():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:bs",
                "재무상태표",
                "statement",
                "",
                [["구분", "당기"], ["매출채권 및 기타채권", "1,917,006"]],
            )
        ],
        [
            _section(
                "note:7",
                "매출채권및기타채권",
                "note",
                "7",
                [
                    ["", "", "총장부금액", "현재가치할인차금", "손상차손누계액", "장부금액 합계"],
                    ["매출채권 및 기타유동채권", "매출채권 및 기타유동채권", "", "", "", ""],
                    ["매출채권 및 기타유동채권", "유동매출채권", "425,516", "0", "(1,392)", ""],
                    ["매출채권 및 기타유동채권", "단기미수금", "154,076", "", "(17,702)", ""],
                    ["매출채권 및 기타유동채권", "단기금융상품", "", "", "", "3,687"],
                    ["매출채권 및 기타유동채권", "단기미수수익", "", "", "", "3,031"],
                    ["매출채권 및 기타유동채권", "단기보증금", "199,520", "(2,744)", "0", ""],
                    ["매출채권 및 기타유동채권", "단기대여금", "", "", "", "0"],
                    ["매출채권 및 기타유동채권", "단기금융리스채권", "", "", "", "83,052"],
                    ["매출채권 및 기타유동채권", "매출채권 및 기타유동채권 합계", "", "", "", "847,044"],
                    ["매출채권 및 기타비유동채권", "매출채권 및 기타비유동채권", "", "", "", ""],
                    ["매출채권 및 기타비유동채권", "비유동매출채권", "2,816", "0", "(569)", ""],
                    ["매출채권 및 기타비유동채권", "장기미수금", "1,799", "", "(53)", ""],
                    ["매출채권 및 기타비유동채권", "장기금융상품", "", "", "", "79,067"],
                    ["매출채권 및 기타비유동채권", "장기미수수익", "", "", "", "19"],
                    ["매출채권 및 기타비유동채권", "장기보증금", "784,489", "(111,184)", "(17)", ""],
                    ["매출채권 및 기타비유동채권", "장기대여금", "", "", "", "30"],
                    ["매출채권 및 기타비유동채권", "장기금융리스채권", "", "", "", "313,565"],
                    ["매출채권 및 기타비유동채권", "매출채권 및 기타비유동채권 합계", "", "", "", "1,069,962"],
                ],
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    receivables = [
        result
        for result in results
        if result.check_id == "reconciliation:trade_receivables.balance"
    ]

    assert len(receivables) == 1
    assert receivables[0].status == "matched"
    assert receivables[0].expected == 1_917_006
    assert receivables[0].actual == 1_917_006
    assert receivables[0].difference == 0
    assert [(e.label, e.amount) for e in receivables[0].evidence] == [
        ("statement 매출채권 및 기타채권", 1_917_006),
        (
            "note 7 매출채권 및 기타유동채권 / 매출채권 및 기타유동채권 합계"
            " + 매출채권 및 기타비유동채권 / 매출채권 및 기타비유동채권 합계",
            1_917_006,
        ),
    ]


def test_check_reconciliation_targets_combines_current_trade_receivables_and_other_current_receivables():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:bs",
                "재무상태표",
                "statement",
                "",
                [["구분", "당기"], ["매출채권 및 기타유동채권", "110,483,379,000"]],
            )
        ],
        [
            _section_with_unit(
                "note:7",
                "매출채권 및 기타채권",
                "note",
                "7",
                [
                    ["", "총장부금액", "손상차손누계액", "현재가치할인차금", "장부금액 합계"],
                    ["유동매출채권", "120,675,640", "(13,857,580)", "", "106,818,060"],
                    ["기타 유동채권", "3,483,951", "(341,655)", "(41,028)", "3,101,268"],
                    ["유동 계약자산 외의 유동 미수수익", "564,051", "", "", "564,051"],
                    ["기타 비유동채권", "0", "0", "0", "0"],
                ],
                1000,
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    receivables = [
        result
        for result in results
        if result.check_id == "reconciliation:trade_receivables.balance"
    ]

    assert len(receivables) == 1
    assert receivables[0].status == "matched"
    assert receivables[0].expected == 110_483_379_000
    assert receivables[0].actual == 110_483_379_000
    assert receivables[0].difference == 0
    assert [(e.label, e.amount) for e in receivables[0].evidence] == [
        ("statement 매출채권 및 기타유동채권", 110_483_379_000),
        (
            "note 7 유동매출채권 + 기타 유동채권 + 유동 계약자산 외의 유동 미수수익",
            110_483_379_000,
        ),
    ]


def test_check_reconciliation_targets_allows_thousand_won_rounding_when_tolerance_is_default():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:bs",
                "재무상태표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산", "1,000,095"]],
            )
        ],
        [
            _section_with_unit(
                "note:11",
                "유형자산",
                "note",
                "11",
                [["구분", "합계"], ["기말 장부금액", "1,000"]],
                1000,
            )
        ],
    )

    results = check_reconciliation_targets(report)

    assert results[0].status == "matched"
    assert results[0].tolerance == 1000


def test_check_reconciliation_targets_limits_thousand_unit_rounding_to_under_one_thousand():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:bs",
                "재무상태표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산", "1,000,950"]],
            )
        ],
        [
            _section_with_unit(
                "note:11",
                "유형자산",
                "note",
                "11",
                [["구분", "합계"], ["기말 장부금액", "1,000"]],
                1000,
            )
        ],
    )

    results = check_reconciliation_targets(report)

    assert results[0].status == "matched"
    assert results[0].tolerance == 1000


def test_check_reconciliation_targets_allows_exact_display_unit_boundary_for_note_precision():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:bs",
                "재무상태표",
                "statement",
                "",
                [["구분", "당기"], ["무형자산", "1,966,684,000,000"]],
            )
        ],
        [
            _section_with_unit(
                "note:15",
                "무형자산",
                "note",
                "15",
                [["구분", "장부금액"], ["합계", "1,966,683"]],
                1_000_000,
            )
        ],
    )

    results = check_reconciliation_targets(report)

    assert results[0].status == "matched"
    assert results[0].difference == -1_000_000
    assert results[0].tolerance == 1_000_000


def test_check_reconciliation_targets_does_not_allow_million_tolerance_for_thousand_unit_amount():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산의 처분", "28,452,324"]],
            )
        ],
        [
            _section_with_unit(
                "note:11",
                "유형자산",
                "note",
                "11",
                [["구분", "합계"], ["처분", "(28,040)"]],
                1000,
            )
        ],
    )

    results = check_reconciliation_targets(report)

    disposal = [result for result in results if result.title == "property_plant_equipment.disposals_cashflow"]
    assert disposal[0].status == "unexplained_gap"
    assert disposal[0].tolerance == 1000


def test_check_reconciliation_targets_matches_trade_receivables_in_other_receivables_note():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:bs",
                "재무상태표",
                "statement",
                "",
                [["구분", "당기"], ["매출채권", "300"]],
            )
        ],
        [
            _section(
                "note:8",
                "매출채권 및 기타채권",
                "note",
                "8",
                [["구분", "금액"], ["매출채권", "300"], ["미수금", "50"]],
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    receivables = [
        result
        for result in results
        if result.check_id == "reconciliation:trade_receivables.balance"
    ]

    assert len(receivables) == 1
    assert receivables[0].status == "matched"
    assert receivables[0].expected == 300
    assert receivables[0].actual == 300
    assert [(e.label, e.amount) for e in receivables[0].evidence] == [
        ("statement 매출채권", 300),
        ("note 8 매출채권", 300),
    ]


def test_check_reconciliation_targets_matches_trade_receivable_financial_instrument_category_row():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:bs",
                "재무상태표",
                "statement",
                "",
                [["구분", "당기"], ["매출채권", "268,201,105"]],
            )
        ],
        [
            _section(
                "note:12",
                "매출채권 및 기타채권",
                "note",
                "12",
                [["구분", "당기말"], ["매출채권", "271,607,154"]],
            ),
            _section(
                "note:10",
                "금융상품",
                "note",
                "10",
                [
                    ["구분", "분류", "계정", "항목", "당기말"],
                    ["금융자산, 범주", "상각후원가로 측정하는 금융자산", "금융상품", "매출채권", "268,201,105"],
                ],
            ),
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    receivables = [
        result
        for result in results
        if result.check_id == "reconciliation:trade_receivables.balance"
    ]

    assert len(receivables) == 1
    assert receivables[0].status == "matched"
    assert receivables[0].actual == 268_201_105
    assert [(e.label, e.amount) for e in receivables[0].evidence] == [
        ("statement 매출채권", 268_201_105),
        ("note 10 매출채권", 268_201_105),
    ]


def test_check_reconciliation_targets_sums_statement_lines_and_chooses_closest_note_balance():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:bs",
                "재무상태표",
                "statement",
                "",
                [["구분", "당기"], ["매출채권", "300"], ["장기매출채권", "700"]],
            )
        ],
        [
            _section(
                "note:18",
                "매출채권",
                "note",
                "8",
                [["구분", "합계"], ["매출채권", "900"], ["매출채권", "1,000"]],
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    lease = [
        result
        for result in results
        if result.check_id == "reconciliation:trade_receivables.balance"
    ]

    assert [(result.status, result.expected, result.actual) for result in lease] == [
        ("matched", 1000, 1000)
    ]


def test_check_reconciliation_targets_matches_trade_receivables_using_current_net_header_band():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:bs",
                "재무상태표",
                "statement",
                "",
                [
                    ["구분", "당기"],
                    ["매출채권 및 기타유동채권", "46,021,945"],
                    ["장기매출채권 및 기타비유동채권", "1,051,497"],
                ],
            )
        ],
        [
            _section(
                "note:4",
                "매출채권 및 기타채권",
                "note",
                "4",
                [
                    ["계정과목", "당기말", "당기말", "당기말", "전기말", "전기말", "전기말"],
                    ["계정과목", "총액", "대손충당금", "순액", "총액", "대손충당금", "순액"],
                    ["매출채권", "42,023,856", "-", "42,023,856", "60,933,277", "-", "60,933,277"],
                    ["미수금", "880,134", "-", "880,134", "51,353", "-", "51,353"],
                    ["미수수익", "237,114", "-", "237,114", "280,742", "-", "280,742"],
                    ["합계", "46,021,945", "-", "46,021,945", "65,666,465", "-", "65,666,465"],
                    ["장기보증금", "1,051,497", "-", "1,051,497", "1,191,120", "-", "1,191,120"],
                ],
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    receivables = [
        result
        for result in results
        if result.check_id == "reconciliation:trade_receivables.balance"
    ]

    assert len(receivables) == 1
    assert receivables[0].status == "matched"
    assert receivables[0].expected == 47_073_442
    assert receivables[0].actual == 47_073_442
    assert [(e.label, e.amount) for e in receivables[0].evidence] == [
        (
            "statement 매출채권 및 기타유동채권 + 장기매출채권 및 기타비유동채권",
            47_073_442,
        ),
        ("note 4 합계 + 장기보증금", 47_073_442),
    ]


def test_check_reconciliation_targets_nets_trade_receivable_allowances_in_current_receivable_note():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:bs",
                "재무상태표",
                "statement",
                "",
                [["구분", "당기"], ["매출채권 및 기타유동채권", "84,844,441,793"]],
            )
        ],
        [
            _section_with_unit(
                "note:9",
                "매출채권 및 기타채권",
                "note",
                "9",
                [
                    ["구 분", "당기말", "당기말"],
                    ["구 분", "유동", "비유동"],
                    ["매출채권", "84,924,256", "-"],
                    ["대손충당금", "(204,523)", "-"],
                    ["미수금", "123,579", "-"],
                    ["대손충당금", "(330)", "-"],
                    ["미수수익", "1,460", "-"],
                ],
                1000,
            )
        ],
    )

    results = check_reconciliation_targets(report)
    receivables = [
        result
        for result in results
        if result.check_id == "reconciliation:trade_receivables.balance"
    ]

    assert len(receivables) == 1
    assert receivables[0].status == "matched"
    assert receivables[0].expected == 84_844_441_793
    assert receivables[0].actual == 84_844_442_000
    assert receivables[0].difference == 207
    assert [(e.label, e.amount) for e in receivables[0].evidence] == [
        ("statement 매출채권 및 기타유동채권", 84_844_441_793),
        (
            "note 9 매출채권 + 대손충당금 + 미수금 + 대손충당금 + 미수수익",
            84_844_442_000,
        ),
    ]


def test_check_reconciliation_targets_dedupes_trade_receivable_parent_child_statement_lines():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:bs",
                "재무상태표",
                "statement",
                "",
                [
                    ["구분", "당기"],
                    ["매출채권 및 기타유동채권", "99,314,506,212"],
                    ["매출채권", "99,314,506,212"],
                    ["장기매출채권 및 기타비유동채권, 총액", "811,974,906"],
                    ["장기매출채권, 총액", "811,974,906"],
                ],
            )
        ],
        [
            _section_with_unit(
                "note:11",
                "매출채권",
                "note",
                "11",
                [["구분", "당기말"], ["매출채권", "100,126,482"]],
                1000,
            )
        ],
    )

    results = check_reconciliation_targets(report)
    receivables = [
        result
        for result in results
        if result.check_id == "reconciliation:trade_receivables.balance"
    ]

    assert len(receivables) == 1
    assert receivables[0].status == "matched"
    assert receivables[0].expected == 100_126_481_118
    assert receivables[0].actual == 100_126_482_000
    assert receivables[0].tolerance == 1_000_000
    assert [(e.label, e.amount) for e in receivables[0].evidence] == [
        (
            "statement 매출채권 및 기타유동채권 + 장기매출채권 및 기타비유동채권, 총액",
            100_126_481_118,
        ),
        ("note 11 매출채권", 100_126_482_000),
    ]


def test_check_reconciliation_targets_combines_note_balances_from_same_table():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:bs",
                "재무상태표",
                "statement",
                "",
                [["구분", "당기"], ["매출채권", "300"], ["장기매출채권", "700"]],
            )
        ],
        [
            _section(
                "note:8",
                "매출채권",
                "note",
                "8",
                [["구분", "당기"], ["유동성 매출채권", "300"], ["비유동성 매출채권", "700"]],
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    receivables = [
        result
        for result in results
        if result.check_id == "reconciliation:trade_receivables.balance"
    ]

    assert [(result.status, result.expected, result.actual) for result in receivables] == [
        ("matched", 1000, 1000)
    ]
    assert receivables[0].evidence[1].label == "note 8 유동성 매출채권 + 비유동성 매출채권"


def test_check_reconciliation_targets_combines_trade_receivable_balances_from_same_note():
    current_table = ReportTable(
        0,
        [["구분", "당기"], ["합계", "385,840"]],
        "매출채권 및 기타채권",
        SourceLocation("note:10", 0, 0),
    )
    noncurrent_table = ReportTable(
        1,
        [["구분", "당기"], ["합계", "4,541"]],
        "장기매출채권 및 기타비유동채권",
        SourceLocation("note:10", 1, 1),
    )
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:bs",
                "재무상태표",
                "statement",
                "",
                [
                    ["구분", "당기"],
                    ["매출채권 및 기타채권", "385,840"],
                    ["장기매출채권 및 기타비유동채권", "4,541"],
                ],
            )
        ],
        [
            ReportSection(
                "note:10",
                "매출채권 및 기타채권",
                "note",
                "10",
                [
                    ReportBlock("table", "", current_table, current_table.location),
                    ReportBlock("table", "", noncurrent_table, noncurrent_table.location),
                ],
            )
        ],
    )

    result = [
        result
        for result in check_reconciliation_targets(report, tolerance=0)
        if result.check_id == "reconciliation:trade_receivables.balance"
    ][0]

    assert result.status == "matched"
    assert result.actual == 390381
    assert result.evidence[1].label == "note 10 합계 + 합계"


def test_check_reconciliation_targets_accepts_large_balance_source_rounding():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:bs",
                "재무상태표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산", "529,469,000,000"]],
            )
        ],
        [
            _section_with_unit(
                "note:11",
                "유형자산",
                "note",
                "11",
                [["구분", "합계"], ["기말 유형자산", "529,468,672"]],
                1000,
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=1)
    ppe = [
        result
        for result in results
        if result.check_id == "reconciliation:property_plant_equipment.balance"
    ]

    assert ppe[0].status == "matched"
    assert ppe[0].difference == -328000


def test_check_reconciliation_targets_does_not_sum_consolidated_and_separate_statement_tables():
    first_table = ReportTable(
        0,
        [["구분", "당기"], ["매출채권", "300"], ["장기매출채권", "700"]],
        "재무상태표",
        SourceLocation("statement:bs", 0, 0),
    )
    second_table = ReportTable(
        1,
        [["구분", "당기"], ["매출채권", "30"], ["장기매출채권", "70"]],
        "재무상태표",
        SourceLocation("statement:bs", 1, 1),
    )
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            ReportSection(
                "statement:bs",
                "재무상태표",
                "statement",
                "",
                [
                    ReportBlock("table", "", first_table, first_table.location),
                    ReportBlock("table", "", second_table, second_table.location),
                ],
            )
        ],
        [
            _section(
                "note:8",
                "매출채권",
                "note",
                "8",
                [["구분", "합계"], ["매출채권", "1,000"]],
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    receivables = [
        result
        for result in results
        if result.check_id == "reconciliation:trade_receivables.balance"
    ]

    assert [(result.status, result.expected, result.actual) for result in receivables] == [
        ("matched", 1000, 1000)
    ]


def test_check_reconciliation_targets_matches_cfs_acquisition_to_note_cash_movement():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산의 취득", "(1,000)"]],
            )
        ],
        [
            _section(
                "note:11",
                "유형자산",
                "note",
                "11",
                [["구분", "합계"], ["취득", "1,000"]],
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    acquisition = [
        result
        for result in results
        if result.check_id
        == "reconciliation:property_plant_equipment.acquisitions_cashflow"
    ]

    assert len(acquisition) == 1
    assert acquisition[0].check_type == "cashflow_reconciliation"
    assert acquisition[0].status == "matched"
    assert acquisition[0].expected == 1000
    assert acquisition[0].actual == 1000
    assert acquisition[0].difference == 0
    assert [(e.label, e.amount) for e in acquisition[0].evidence] == [
        ("cfs 유형자산의 취득", -1000),
        ("note 11 취득", 1000),
    ]


def test_check_reconciliation_targets_chooses_closest_acquisition_note_movement():
    zero_table = ReportTable(
        0,
        [["구분", "당기"], ["취득", "0"]],
        "무형자산",
        SourceLocation("note:12", 0, 0),
    )
    current_table = ReportTable(
        1,
        [["구분", "당기"], ["취득", "1,000"]],
        "무형자산",
        SourceLocation("note:12", 1, 1),
    )
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["무형자산의 취득", "(1,000)"]],
            )
        ],
        [
            ReportSection(
                "note:12",
                "무형자산",
                "note",
                "12",
                [
                    ReportBlock("table", "", zero_table, zero_table.location),
                    ReportBlock("table", "", current_table, current_table.location),
                ],
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    acquisition = [
        result
        for result in results
        if result.check_id == "reconciliation:intangible_assets.acquisitions_cashflow"
    ]

    assert acquisition[0].status == "matched"
    assert acquisition[0].actual == 1000
    assert [(e.label, e.amount, e.source) for e in acquisition[0].evidence] == [
        ("cfs 무형자산의 취득", -1000, "statement:cf/table:0/row:1/col:1"),
        ("note 12 취득", 1000, "note:12/table:1/row:1/col:1"),
    ]


def test_check_reconciliation_targets_reports_unexplained_gap_without_cashflow_adjustments():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산의 처분", "1,000"]],
            )
        ],
        [
            _section(
                "note:11",
                "유형자산",
                "note",
                "11",
                [["구분", "합계"], ["처분", "900"]],
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    disposal = [
        result
        for result in results
        if result.check_id == "reconciliation:property_plant_equipment.disposals_cashflow"
    ]

    assert len(disposal) == 1
    assert disposal[0].check_type == "cashflow_reconciliation"
    assert disposal[0].status == "unexplained_gap"
    assert disposal[0].expected == 1000
    assert disposal[0].actual == 900
    assert disposal[0].difference == -100
    assert disposal[0].reason == (
        "주석 처분 장부금액 900 = 900; "
        "현금흐름표 유형자산의 처분 1,000; "
        "차이 (100); 현금흐름표 금액과 직접 대사되지 않음"
    )


def test_check_reconciliation_targets_adjusts_disposal_to_cash_basis():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산의 처분", "1,000"]],
            )
        ],
        [
            _section(
                "note:11",
                "유형자산",
                "note",
                "11",
                [
                    ["구분", "합계"],
                    ["처분", "900"],
                    ["처분손익", "150"],
                    ["비현금거래-미수금", "50"],
                ],
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    disposal = [
        result
        for result in results
        if result.check_id == "reconciliation:property_plant_equipment.disposals_cashflow"
    ]

    assert len(disposal) == 1
    assert disposal[0].status == "matched"
    assert disposal[0].expected == 1000
    assert disposal[0].actual == 1000
    assert disposal[0].difference == 0
    assert disposal[0].reason == (
        "주석 처분 장부금액 900 + 처분손익 150 - 비현금거래-미수금 50 = 1,000; "
        "현금흐름표 유형자산의 처분 1,000; "
        "차이 0; 현금흐름표 금액과 직접 대사됨"
    )
    assert [(e.label, e.amount) for e in disposal[0].evidence] == [
        ("cfs 유형자산의 처분", 1000),
        ("note 11 처분", 900),
        ("note 11 처분손익", 150),
        ("note 11 비현금거래-미수금", 50),
    ]


def test_check_reconciliation_targets_keeps_disposal_primary_with_adjustment_formula():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산의 처분", "1,000"]],
            )
        ],
        [
            _section(
                "note:11",
                "유형자산",
                "note",
                "11",
                [
                    ["구분", "합계"],
                    ["처분", "900"],
                    ["처분", "990"],
                    ["처분손익", "100"],
                ],
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    disposal = [
        result
        for result in results
        if result.check_id == "reconciliation:property_plant_equipment.disposals_cashflow"
    ]

    assert disposal[0].status == "matched"
    assert disposal[0].actual == 1000
    assert [(e.label, e.amount) for e in disposal[0].evidence] == [
        ("cfs 유형자산의 처분", 1000),
        ("note 11 처분", 900),
        ("note 11 처분손익", 100),
    ]


def test_check_reconciliation_targets_selects_disposal_primary_that_matches_with_adjustments():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["무형자산의 처분", "277"]],
            )
        ],
        [
            _section(
                "note:12",
                "무형자산",
                "note",
                "12",
                [
                    ["구분", "합계"],
                    ["처분", "1"],
                    ["처분", "202"],
                ],
            ),
            _section(
                "note:27",
                "기타수익 및 기타비용",
                "note",
                "27",
                [
                    ["구분", "당기"],
                    ["무형자산처분이익", "101"],
                    ["무형자산처분손실", "26"],
                ],
            ),
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    disposal = [
        result
        for result in results
        if result.check_id == "reconciliation:intangible_assets.disposals_cashflow"
    ]

    assert len(disposal) == 1
    assert disposal[0].status == "matched"
    assert disposal[0].expected == 277
    assert disposal[0].actual == 277
    assert disposal[0].difference == 0
    assert [(e.label, e.amount) for e in disposal[0].evidence] == [
        ("cfs 무형자산의 처분", 277),
        ("note 12 처분", 202),
        ("note 27 무형자산처분이익", 101),
        ("note 27 무형자산처분손실", 26),
    ]


def test_check_reconciliation_targets_selects_disposal_adjustment_subset():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산의 처분", "172"]],
            )
        ],
        [
            _section(
                "note:11",
                "유형자산",
                "note",
                "11",
                [["구분", "합계"], ["처분", "292"]],
            ),
            _section(
                "note:28",
                "기타수익 및 기타비용",
                "note",
                "28",
                [
                    ["구분", "당기"],
                    ["기타수익 유형자산처분이익", "31"],
                    ["기타비용 유형자산처분손실", "151"],
                ],
            ),
            _section(
                "note:33",
                "영업활동현금흐름",
                "note",
                "33",
                [["구분", "당기"], ["조정 유형자산처분손익", "120"]],
            ),
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    disposal = [
        result
        for result in results
        if result.check_id == "reconciliation:property_plant_equipment.disposals_cashflow"
    ]

    assert len(disposal) == 1
    assert disposal[0].status == "matched"
    assert disposal[0].expected == 172
    assert disposal[0].actual == 172
    assert disposal[0].difference == 0
    assert disposal[0].reason == (
        "주석 처분 장부금액 292 + 처분손익 31 - 처분손실 151 = 172; "
        "현금흐름표 유형자산의 처분 172; "
        "차이 0; 현금흐름표 금액과 직접 대사됨"
    )
    assert [(e.label, e.amount) for e in disposal[0].evidence] == [
        ("cfs 유형자산의 처분", 172),
        ("note 11 처분", 292),
        ("note 28 기타수익 유형자산처분이익", 31),
        ("note 28 기타비용 유형자산처분손실", 151),
    ]


def test_check_reconciliation_targets_does_not_double_count_duplicate_disposal_adjustments():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["무형자산의 처분", "686"]],
            )
        ],
        [
            _section(
                "note:17",
                "무형자산",
                "note",
                "17",
                [["구분", "합계"], ["처분", "750"]],
            ),
            _section(
                "note:31",
                "기타수익 및 기타비용",
                "note",
                "31",
                [
                    ["구분", "당기"],
                    ["무형자산처분이익", "2"],
                    ["무형자산처분손실", "33"],
                ],
            ),
            _section(
                "note:36",
                "영업활동현금흐름",
                "note",
                "36",
                [["구분", "당기"], ["무형자산처분손실", "33"]],
            ),
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    disposal = [
        result
        for result in results
        if result.check_id == "reconciliation:intangible_assets.disposals_cashflow"
    ]

    assert len(disposal) == 1
    assert disposal[0].status == "explainable_gap"
    assert disposal[0].actual == 717
    assert disposal[0].reason == (
        "주석 처분 장부금액 750 - 처분손실 33 = 717; "
        "현금흐름표 무형자산의 처분 686; "
        "차이 31; 현금흐름표 금액과 직접 대사되지 않음"
    )
    assert [(e.label, e.amount) for e in disposal[0].evidence] == [
        ("cfs 무형자산의 처분", 686),
        ("note 17 처분", 750),
        ("note 31 무형자산처분손실", 33),
    ]


def test_check_reconciliation_targets_matches_cashflow_bridge_with_small_residual():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["무형자산의 처분", "686"]],
            )
        ],
        [
            _section(
                "note:17",
                "무형자산",
                "note",
                "17",
                [["구분", "합계"], ["처분", "750"]],
            ),
            _section(
                "note:31",
                "기타수익 및 기타비용",
                "note",
                "31",
                [["구분", "당기"], ["무형자산처분손실", "33"]],
            ),
        ],
    )

    disposal = [
        result
        for result in check_reconciliation_targets(report)
        if result.check_id == "reconciliation:intangible_assets.disposals_cashflow"
    ]

    assert len(disposal) == 1
    assert disposal[0].status == "matched"
    assert disposal[0].actual == 717
    assert disposal[0].tolerance == 35
    assert disposal[0].reason == (
        "주석 처분 장부금액 750 - 처분손실 33 = 717; "
        "현금흐름표 무형자산의 처분 686; "
        "차이 31; 허용오차 35 이내로 현금흐름표 금액과 대사됨"
    )


def test_check_reconciliation_targets_prefers_direct_disposal_proceeds_when_disclosed():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산의 처분", "1,000"]],
            )
        ],
        [
            _section(
                "note:11",
                "유형자산",
                "note",
                "11",
                [
                    ["구분", "합계"],
                    ["처분", "900"],
                    ["처분금액", "1,000"],
                    ["처분손익", "150"],
                ],
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    disposal = [
        result
        for result in results
        if result.check_id == "reconciliation:property_plant_equipment.disposals_cashflow"
    ]

    assert len(disposal) == 1
    assert disposal[0].status == "matched"
    assert disposal[0].actual == 1000
    assert disposal[0].reason == (
        "주석 처분금액 1,000 = 1,000; "
        "현금흐름표 유형자산의 처분 1,000; "
        "차이 0; 현금흐름표 금액과 직접 대사됨"
    )
    assert [(e.label, e.amount) for e in disposal[0].evidence] == [
        ("cfs 유형자산의 처분", 1000),
        ("note 11 처분금액", 1000),
    ]


def test_check_reconciliation_targets_accumulates_rounding_tolerance_for_cashflow_formula_components():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산의 처분", "2,114,020,686"]],
            )
        ],
        [
            _section_with_unit(
                "note:11",
                "유형자산",
                "note",
                "11",
                [["구분", "합계"], ["처분", "6,228,444"]],
                1000,
            ),
            _section_with_unit(
                "note:29",
                "기타수익",
                "note",
                "29",
                [["구분", "당기"], ["유형자산처분이익", "317,771"]],
                1000,
            ),
            _section_with_unit(
                "note:30",
                "기타비용",
                "note",
                "30",
                [["구분", "당기"], ["유형자산처분손실", "4,432,193"]],
                1000,
            ),
        ],
    )

    results = check_reconciliation_targets(report)
    disposal = [
        result
        for result in results
        if result.check_id == "reconciliation:property_plant_equipment.disposals_cashflow"
    ]

    assert disposal[0].status == "matched"
    assert disposal[0].actual == 2114022000
    assert disposal[0].difference == 1314
    assert disposal[0].tolerance == 3000


def test_check_reconciliation_targets_adjusts_acquisition_for_noncash_payable():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산의 취득", "(800)"]],
            )
        ],
        [
            _section(
                "note:11",
                "유형자산",
                "note",
                "11",
                [
                    ["구분", "합계"],
                    ["취득", "1,000"],
                    ["비현금거래-미지급금", "200"],
                ],
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    acquisition = [
        result
        for result in results
        if result.check_id
        == "reconciliation:property_plant_equipment.acquisitions_cashflow"
    ]

    assert len(acquisition) == 1
    assert acquisition[0].status == "matched"
    assert acquisition[0].expected == 800
    assert acquisition[0].actual == 800
    assert acquisition[0].difference == 0
    assert acquisition[0].reason == (
        "주석 취득 1,000 - 비현금거래-미지급금 증가 200 = 800; "
        "현금흐름표 유형자산의 취득 800; "
        "차이 0; 현금흐름표 금액과 직접 대사됨"
    )


def test_check_reconciliation_targets_adds_negative_payable_delta_to_cash_acquisition():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산의 취득", "(1,200)"]],
            )
        ],
        [
            _section(
                "note:11",
                "유형자산",
                "note",
                "11",
                [
                    ["구분", "합계"],
                    ["취득", "1,000"],
                    ["유형자산 취득 관련 미지급금 증가", "(200)"],
                ],
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    acquisition = [
        result
        for result in results
        if result.check_id
        == "reconciliation:property_plant_equipment.acquisitions_cashflow"
    ]

    assert acquisition[0].status == "matched"
    assert acquisition[0].expected == 1200
    assert acquisition[0].actual == 1200
    assert acquisition[0].difference == 0
    assert acquisition[0].reason == (
        "주석 취득 1,000 + 비현금거래-미지급금 감소 200 = 1,200; "
        "현금흐름표 유형자산의 취득 1,200; "
        "차이 0; 현금흐름표 금액과 직접 대사됨"
    )


def test_check_reconciliation_targets_treats_negative_increase_decrease_payable_as_decrease():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산의 취득", "(1,200)"]],
            )
        ],
        [
            _section(
                "note:11",
                "유형자산",
                "note",
                "11",
                [
                    ["구분", "합계"],
                    ["취득", "1,000"],
                ],
            ),
            _section(
                "note:31",
                "현금의 유입과 유출이 없는 거래",
                "note",
                "31",
                [["구분", "당기"], ["유형자산 취득관련 미지급금의 증가(감소)", "(200)"]],
            ),
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    acquisition = [
        result
        for result in results
        if result.check_id
        == "reconciliation:property_plant_equipment.acquisitions_cashflow"
    ]

    assert acquisition[0].status == "matched"
    assert acquisition[0].actual == 1200
    assert acquisition[0].reason == (
        "주석 취득 1,000 + 비현금거래-미지급금 감소 200 = 1,200; "
        "현금흐름표 유형자산의 취득 1,200; "
        "차이 0; 현금흐름표 금액과 직접 대사됨"
    )


def test_check_reconciliation_targets_uses_combined_asset_payable_only_when_formula_improves():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [
                    ["구분", "당기"],
                    ["유형자산의 취득", "(1,200)"],
                    ["무형자산의 취득", "(300)"],
                ],
            )
        ],
        [
            _section(
                "note:11",
                "유형자산",
                "note",
                "11",
                [["구분", "합계"], ["취득", "1,000"]],
            ),
            _section(
                "note:12",
                "무형자산",
                "note",
                "12",
                [["구분", "합계"], ["취득", "300"]],
            ),
            _section(
                "note:31",
                "현금의 유입과 유출이 없는 거래",
                "note",
                "31",
                [["구분", "당기"], ["유ㆍ무형자산 취득 관련 미지급금 변동", "(200)"]],
            ),
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    by_id = {result.check_id: result for result in results}

    ppe = by_id["reconciliation:property_plant_equipment.acquisitions_cashflow"]
    intangible = by_id["reconciliation:intangible_assets.acquisitions_cashflow"]
    assert ppe.status == "matched"
    assert ppe.actual == 1200
    assert [(e.label, e.amount) for e in ppe.evidence] == [
        ("cfs 유형자산의 취득", -1200),
        ("note 11 취득", 1000),
        ("note 31 유ㆍ무형자산 취득 관련 미지급금 변동", -200),
    ]
    assert intangible.status == "matched"
    assert intangible.actual == 300
    assert [(e.label, e.amount) for e in intangible.evidence] == [
        ("cfs 무형자산의 취득", -300),
        ("note 12 취득", 300),
    ]


def test_check_reconciliation_targets_uses_payable_decrease_increase_label_direction():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["무형자산의 취득", "(1,200)"]],
            )
        ],
        [
            _section(
                "note:12",
                "무형자산",
                "note",
                "12",
                [
                    ["구분", "합계"],
                    ["취득", "1,000"],
                ],
            ),
            _section(
                "note:31",
                "현금의 유입과 유출이 없는 거래",
                "note",
                "31",
                [["구분", "당기"], ["무형자산 취득 미지급금의 감소(증가)", "200"]],
            ),
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    acquisition = [
        result
        for result in results
        if result.check_id == "reconciliation:intangible_assets.acquisitions_cashflow"
    ]

    assert acquisition[0].status == "matched"
    assert acquisition[0].actual == 1200
    assert acquisition[0].reason == (
        "주석 취득 1,000 + 비현금거래-미지급금 감소 200 = 1,200; "
        "현금흐름표 무형자산의 취득 1,200; "
        "차이 0; 현금흐름표 금액과 직접 대사됨"
    )


def test_check_reconciliation_targets_treats_specific_negative_payable_change_as_increase():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["무형자산의 취득", "(800)"]],
            )
        ],
        [
            _section(
                "note:12",
                "무형자산",
                "note",
                "12",
                [
                    ["구분", "합계"],
                    ["취득", "1,000"],
                ],
            ),
            _section(
                "note:31",
                "현금의 유입과 유출이 없는 거래",
                "note",
                "31",
                [["구분", "당기"], ["무형자산 취득 관련 미지급금의 변동", "(200)"]],
            ),
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    acquisition = [
        result
        for result in results
        if result.check_id == "reconciliation:intangible_assets.acquisitions_cashflow"
    ]

    assert acquisition[0].status == "matched"
    assert acquisition[0].actual == 800
    assert acquisition[0].reason == (
        "주석 취득 1,000 - 비현금거래-미지급금 증가 200 = 800; "
        "현금흐름표 무형자산의 취득 800; "
        "차이 0; 현금흐름표 금액과 직접 대사됨"
    )


def test_check_reconciliation_targets_keeps_terse_negative_payable_change_as_decrease():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산의 취득", "(1,200)"]],
            )
        ],
        [
            _section(
                "note:11",
                "유형자산",
                "note",
                "11",
                [
                    ["구분", "합계"],
                    ["취득", "1,000"],
                ],
            ),
            _section(
                "note:31",
                "현금의 유입과 유출이 없는 거래",
                "note",
                "31",
                [["구분", "당기"], ["유형자산 취득 미지급금 변동", "(200)"]],
            ),
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    acquisition = [
        result
        for result in results
        if result.check_id == "reconciliation:property_plant_equipment.acquisitions_cashflow"
    ]

    assert acquisition[0].status == "matched"
    assert acquisition[0].actual == 1200
    assert acquisition[0].reason == (
        "주석 취득 1,000 + 비현금거래-미지급금 감소 200 = 1,200; "
        "현금흐름표 유형자산의 취득 1,200; "
        "차이 0; 현금흐름표 금액과 직접 대사됨"
    )


def test_check_reconciliation_targets_treats_terse_positive_asset_payable_as_decrease():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산의 취득", "(1,300)"]],
            )
        ],
        [
            _section(
                "note:11",
                "유형자산",
                "note",
                "11",
                [
                    ["구분", "합계"],
                    ["취득", "1,000"],
                ],
            ),
            _section(
                "note:31",
                "현금의 유입과 유출이 없는 거래",
                "note",
                "31",
                [["구분", "당기"], ["유형자산취득 미지급금", "300"]],
            ),
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    acquisition = [
        result
        for result in results
        if result.check_id
        == "reconciliation:property_plant_equipment.acquisitions_cashflow"
    ]

    assert acquisition[0].status == "matched"
    assert acquisition[0].actual == 1300
    assert acquisition[0].reason == (
        "주석 취득 1,000 + 비현금거래-미지급금 감소 300 = 1,300; "
        "현금흐름표 유형자산의 취득 1,300; "
        "차이 0; 현금흐름표 금액과 직접 대사됨"
    )


def test_check_reconciliation_targets_adds_payable_increase_only_noncash_acquisition_when_it_completes_formula():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["무형자산의 취득", "(1,200)"]],
            )
        ],
        [
            _section(
                "note:12",
                "무형자산",
                "note",
                "12",
                [
                    ["구분", "합계"],
                    ["취득", "1,000"],
                ],
            ),
            _section(
                "note:31",
                "현금의 유입과 유출이 없는 거래",
                "note",
                "31",
                [["구분", "당기"], ["무형자산 취득에 따른 미지급금 증가", "200"]],
            ),
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    acquisition = [
        result
        for result in results
        if result.check_id == "reconciliation:intangible_assets.acquisitions_cashflow"
    ]

    assert acquisition[0].status == "matched"
    assert acquisition[0].actual == 1200
    assert acquisition[0].reason == (
        "주석 취득 1,000 + 비현금거래-미지급금 증가 200 = 1,200; "
        "현금흐름표 무형자산의 취득 1,200; "
        "차이 0; 현금흐름표 금액과 직접 대사됨"
    )
    assert [(e.label, e.amount) for e in acquisition[0].evidence] == [
        ("cfs 무형자산의 취득", -1200),
        ("note 12 취득", 1000),
        ("note 31 무형자산 취득에 따른 미지급금 증가", 200),
    ]


def test_check_reconciliation_targets_excludes_right_of_use_asset_acquisition_from_ppe_cash_basis():
    ppe_table = ReportTable(
        0,
        [["구분", "유형자산", "사용권자산", "합계"], ["취득", "1,000", "300", "1,300"]],
        "유형자산의 변동내역 당기",
        SourceLocation("note:11", 0, 0),
    )
    rou_table = ReportTable(
        1,
        [["구분", "사용권자산"], ["일반취득 및 자본적지출", "300"]],
        "사용권자산에 대한 양적 정보 공시 당기",
        SourceLocation("note:11", 1, 1),
    )
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산의 취득", "(1,000)"]],
            )
        ],
        [
            ReportSection(
                "note:11",
                "유형자산",
                "note",
                "11",
                [
                    ReportBlock("table", "", ppe_table, ppe_table.location),
                    ReportBlock("table", "", rou_table, rou_table.location),
                ],
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    acquisition = [
        result
        for result in results
        if result.check_id == "reconciliation:property_plant_equipment.acquisitions_cashflow"
    ]

    assert acquisition[0].status == "matched"
    assert acquisition[0].actual == 1000
    assert acquisition[0].reason == (
        "주석 취득 1,300 - 사용권자산 비현금 취득 300 = 1,000; "
        "현금흐름표 유형자산의 취득 1,000; "
        "차이 0; 현금흐름표 금액과 직접 대사됨"
    )


def test_check_reconciliation_targets_includes_right_of_use_asset_when_cfs_line_is_combined_ppe_and_rou_acquisition():
    ppe_table = ReportTable(
        0,
        [["구분", "유형자산"], ["취득", "1,000"]],
        "유형자산의 변동내역 당기",
        SourceLocation("note:11", 0, 0),
    )
    rou_table = ReportTable(
        1,
        [["구분", "사용권자산"], ["일반취득 및 자본적지출", "300"]],
        "사용권자산에 대한 양적 정보 공시 당기",
        SourceLocation("note:11", 1, 1),
    )
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산 및 사용권자산의 취득", "(1,300)"]],
            )
        ],
        [
            ReportSection(
                "note:11",
                "유형자산",
                "note",
                "11",
                [
                    ReportBlock("table", "", ppe_table, ppe_table.location),
                    ReportBlock("table", "", rou_table, rou_table.location),
                ],
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    acquisition = [
        result
        for result in results
        if result.check_id == "reconciliation:property_plant_equipment.acquisitions_cashflow"
    ]

    assert acquisition[0].status == "matched"
    assert acquisition[0].actual == 1300
    assert acquisition[0].reason == (
        "주석 취득 1,000 + 사용권자산 취득 300 = 1,300; "
        "현금흐름표 유형자산 및 사용권자산의 취득 1,300; "
        "차이 0; 현금흐름표 금액과 직접 대사됨"
    )


def test_check_reconciliation_targets_excludes_right_of_use_asset_disposal_from_ppe_cash_basis():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산의 처분", "1,230"]],
            )
        ],
        [
            _section(
                "note:13",
                "유형자산",
                "note",
                "13",
                [
                    ["", "기계장치", "사용권자산", "유형자산 합계"],
                    ["처분", "(492)", "(6)", "(528)"],
                ],
            ),
            _section(
                "note:28",
                "기타손익",
                "note",
                "28",
                [
                    ["구분", "당기"],
                    ["유형자산처분이익", "882"],
                    ["유형자산처분손실", "174"],
                ],
            ),
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    disposal = [
        result
        for result in results
        if result.check_id == "reconciliation:property_plant_equipment.disposals_cashflow"
    ]

    assert disposal[0].status == "matched"
    assert disposal[0].actual == 1230
    assert disposal[0].reason == (
        "주석 처분 장부금액 528 - 사용권자산 비현금 처분 6 + 처분손익 882 - 처분손실 174 = 1,230; "
        "현금흐름표 유형자산의 처분 1,230; "
        "차이 0; 현금흐름표 금액과 직접 대사됨"
    )


def test_check_reconciliation_targets_subtracts_positive_net_disposal_gain_loss_adjustment():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산의 처분", "800"]],
            )
        ],
        [
            _section(
                "note:13",
                "유형자산",
                "note",
                "13",
                [
                    ["", "기계장치", "사용권자산", "유형자산 합계"],
                    ["처분", "(5,000)", "(1,000)", "(6,000)"],
                ],
            ),
            _section(
                "note:33",
                "영업활동현금흐름",
                "note",
                "33",
                [["구분", "당기"], ["유형자산처분손익", "4,200"]],
            ),
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    disposal = [
        result
        for result in results
        if result.check_id == "reconciliation:property_plant_equipment.disposals_cashflow"
    ]

    assert disposal[0].status == "matched"
    assert disposal[0].actual == 800
    assert disposal[0].reason == (
        "주석 처분 장부금액 6,000 - 사용권자산 비현금 처분 1,000 - 처분손익 4,200 = 800; "
        "현금흐름표 유형자산의 처분 800; "
        "차이 0; 현금흐름표 금액과 직접 대사됨"
    )
    assert [(e.label, e.amount) for e in disposal[0].evidence] == [
        ("cfs 유형자산의 처분", 800),
        ("note 13 처분", -6000),
        ("note 13 사용권자산 처분", -1000),
        ("note 33 유형자산처분손익", 4200),
    ]


def test_check_reconciliation_targets_subtracts_accumulated_depreciation_disposal_from_gross_cost_disposal():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산의 처분", "2,800"]],
            )
        ],
        [
            _section(
                "note:13",
                "유형자산",
                "note",
                "13",
                [
                    ["구분", "처분"],
                    ["유형자산 취득원가 합계", "(5,000)"],
                    ["유형자산 감가상각누계액 합계", "3,000"],
                ],
            ),
            _section(
                "note:28",
                "기타손익",
                "note",
                "28",
                [["구분", "당기"], ["유형자산처분이익", "800"]],
            ),
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    disposal = [
        result
        for result in results
        if result.check_id == "reconciliation:property_plant_equipment.disposals_cashflow"
    ]

    assert disposal[0].status == "matched"
    assert disposal[0].actual == 2800
    assert disposal[0].reason == (
        "주석 처분 장부금액 5,000 - 감가상각누계액 처분 3,000 + 처분손익 800 = 2,800; "
        "현금흐름표 유형자산의 처분 2,800; "
        "차이 0; 현금흐름표 금액과 직접 대사됨"
    )
    assert [(e.label, e.amount) for e in disposal[0].evidence] == [
        ("cfs 유형자산의 처분", 2800),
        ("note 13 유형자산 취득원가 합계 처분", -5000),
        ("note 13 유형자산 감가상각누계액 합계 처분", 3000),
        ("note 28 유형자산처분이익", 800),
    ]


def test_check_reconciliation_targets_adds_government_grant_disposal_to_ppe_cash_basis():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산의 처분", "50"]],
            )
        ],
        [
            _section(
                "note:11",
                "유형자산",
                "note",
                "11",
                [
                    ["", "", "", "", "기초", "취득", "처분", "감가상각비", "기말"],
                    ["유형자산", "건물", "장부금액", "총장부금액, 정부보조금 차감 전", "1,000", "0", "(100)", "0", "900"],
                    ["유형자산", "건물", "장부금액", "정부보조금", "(20)", "0", "10", "0", "(10)"],
                    ["유형자산 합계", "유형자산 합계", "유형자산 합계", "유형자산 합계", "980", "0", "(90)", "0", "890"],
                ],
            ),
            _section(
                "note:28",
                "기타손익",
                "note",
                "28",
                [
                    ["구분", "당기"],
                    ["유형자산처분이익", "20"],
                    ["유형자산처분손실", "70"],
                ],
            ),
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    disposal = [
        result
        for result in results
        if result.check_id == "reconciliation:property_plant_equipment.disposals_cashflow"
    ]

    assert disposal[0].status == "matched"
    assert disposal[0].actual == 50
    assert disposal[0].reason == (
        "주석 처분 장부금액 90 + 정부보조금 처분 10 + 처분손익 20 - 처분손실 70 = 50; "
        "현금흐름표 유형자산의 처분 50; "
        "차이 0; 현금흐름표 금액과 직접 대사됨"
    )


def test_check_reconciliation_targets_excludes_noncash_transfer_from_acquisition_cash_basis():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["무형자산의 취득", "(650)"]],
            )
        ],
        [
            _section(
                "note:12",
                "무형자산",
                "note",
                "12",
                [
                    ["구분", "합계"],
                    ["당기취득(계정대체 포함)", "1,250"],
                ],
            ),
            _section(
                "note:31",
                "현금의 유입과 유출이 없는 거래",
                "note",
                "31",
                [["구분", "당기"], ["건설중인자산의 무형자산 대체", "600"]],
            ),
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    acquisition = [
        result
        for result in results
        if result.check_id == "reconciliation:intangible_assets.acquisitions_cashflow"
    ]

    assert acquisition[0].status == "matched"
    assert acquisition[0].actual == 650
    assert acquisition[0].reason == (
        "주석 취득 1,250 - 비현금거래-대체취득 600 = 650; "
        "현금흐름표 무형자산의 취득 650; "
        "차이 0; 현금흐름표 금액과 직접 대사됨"
    )


def test_check_reconciliation_targets_excludes_prepayment_to_intangible_transfer_from_cash_acquisition():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["무형자산의 취득", "(2,133)"]],
            )
        ],
        [
            _section(
                "note:12",
                "무형자산",
                "note",
                "12",
                [
                    ["", "개발비", "산업재산권", "무형자산 합계"],
                    ["취득", "2,133", "7", "2,140"],
                ],
            ),
            _section(
                "note:25",
                "현금흐름표 현금의 유입과 유출이 없는 중요한 거래 내역",
                "note",
                "25",
                [
                    ["", "", "공시금액"],
                    ["거래내역", "거래내역", ""],
                    ["거래내역", "선급금의 무형자산 대체", "7"],
                ],
            ),
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    acquisition = [
        result
        for result in results
        if result.check_id == "reconciliation:intangible_assets.acquisitions_cashflow"
    ]

    assert acquisition[0].status == "matched"
    assert acquisition[0].actual == 2133
    assert acquisition[0].reason == (
        "주석 취득 2,140 - 비현금거래-대체취득 7 = 2,133; "
        "현금흐름표 무형자산의 취득 2,133; "
        "차이 0; 현금흐름표 금액과 직접 대사됨"
    )


def test_check_reconciliation_targets_applies_signed_rollforward_transfer_to_acquisition_cash_basis():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산의 취득", "(950)"]],
            )
        ],
        [
            _section(
                "note:10",
                "유형자산",
                "note",
                "10",
                [
                    ["", "건설중인자산", "유형자산 합계"],
                    ["취득", "300", "1,000"],
                    ["재고자산과의 대체에 따른 증가(감소), 유형자산", "(50)", "(50)"],
                ],
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    acquisition = [
        result
        for result in results
        if result.check_id == "reconciliation:property_plant_equipment.acquisitions_cashflow"
    ]

    assert acquisition[0].status == "matched"
    assert acquisition[0].actual == 950
    assert acquisition[0].reason == (
        "주석 취득 1,000 - 변동표 대체 감소 50 = 950; "
        "현금흐름표 유형자산의 취득 950; "
        "차이 0; 현금흐름표 금액과 직접 대사됨"
    )


def test_check_reconciliation_targets_excludes_business_combination_acquisition_from_cash_basis():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산의 취득", "(300)"]],
            )
        ],
        [
            _section(
                "note:11",
                "유형자산",
                "note",
                "11",
                [
                    ["구분", "합계"],
                    ["취득", "1,000"],
                    ["사업결합을 통한 취득", "700"],
                ],
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    acquisition = [
        result
        for result in results
        if result.check_id
        == "reconciliation:property_plant_equipment.acquisitions_cashflow"
    ]

    assert len(acquisition) == 1
    assert acquisition[0].status == "matched"
    assert acquisition[0].expected == 300
    assert acquisition[0].actual == 300
    assert acquisition[0].difference == 0
    assert acquisition[0].reason == (
        "주석 취득 1,000 - 사업결합 취득 700 = 300; "
        "현금흐름표 유형자산의 취득 300; "
        "차이 0; 현금흐름표 금액과 직접 대사됨"
    )
    assert [(e.label, e.amount) for e in acquisition[0].evidence] == [
        ("cfs 유형자산의 취득", -300),
        ("note 11 취득", 1000),
        ("note 11 사업결합을 통한 취득", 700),
    ]


def test_check_reconciliation_targets_does_not_force_business_combination_adjustment_when_direct_acquisition_matches():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산의 취득", "(1,000)"]],
            )
        ],
        [
            _section(
                "note:11",
                "유형자산",
                "note",
                "11",
                [
                    ["구분", "합계"],
                    ["취득", "1,000"],
                    ["사업결합을 통한 취득", "700"],
                ],
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    acquisition = [
        result
        for result in results
        if result.check_id
        == "reconciliation:property_plant_equipment.acquisitions_cashflow"
    ]

    assert acquisition[0].status == "matched"
    assert acquisition[0].expected == 1000
    assert acquisition[0].actual == 1000
    assert acquisition[0].difference == 0
    assert [(e.label, e.amount) for e in acquisition[0].evidence] == [
        ("cfs 유형자산의 취득", -1000),
        ("note 11 취득", 1000),
    ]


def test_check_reconciliation_targets_matches_financing_liability_net_cashflow_note():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["차입금의 차입", "1,000"], ["차입금의 상환", "(1,300)"]],
            )
        ],
        [
            _section(
                "note:36",
                "현금흐름",
                "note",
                "36",
                [
                    ["", "", "재무활동현금흐름", "비현금흐름"],
                    ["재무활동에서 생기는 부채", "차입금", "2,000", "(300)", "10", "1,710"],
                ],
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    financing = [
        result
        for result in results
        if result.check_id == "reconciliation:borrowings.financing_cashflow"
    ]

    assert len(financing) == 1
    assert financing[0].status == "matched"
    assert financing[0].expected == -300
    assert financing[0].actual == -300
    assert financing[0].difference == 0
    assert [(e.label, e.amount) for e in financing[0].evidence] == [
        ("cfs 차입금의 차입", 1000),
        ("cfs 차입금의 상환", -1300),
        ("note 36 재무활동현금흐름 차입금", -300),
    ]


def test_check_reconciliation_targets_selects_matching_financing_cashflow_subset():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["차입금의 상환", "(1,800)"]],
            )
        ],
        [
            _section(
                "note:30",
                "현금흐름표 재무활동에서 생기는 부채의 조정",
                "note",
                "30",
                [
                    ["구분", "단기차입금"],
                    ["재무활동에서 생기는 기초 부채", "5,000"],
                    ["차입금의 증가, 재무활동에서 생기는 부채", "1,800"],
                    ["차입금의 감소, 재무활동에서 생기는 부채", "(1,800)"],
                    ["재무활동에서 생기는 기말 부채", "5,000"],
                ],
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    financing = [
        result
        for result in results
        if result.check_id == "reconciliation:borrowings.financing_cashflow"
    ]

    assert len(financing) == 1
    assert financing[0].status == "matched"
    assert financing[0].expected == -1800
    assert financing[0].actual == -1800
    assert financing[0].difference == 0
    assert [(e.label, e.amount) for e in financing[0].evidence] == [
        ("cfs 차입금의 상환", -1800),
        ("note 30 재무활동현금흐름 차입금", -1800),
    ]


def test_check_reconciliation_targets_preserves_signed_borrowing_net_change_cashflow():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["단기차입금의 순증감", "(19,093)"]],
            )
        ],
        [
            _section(
                "note:31",
                "현금흐름표 재무활동에서 생기는 부채의 조정",
                "note",
                "31",
                [
                    ["구분", "단기차입금", "리스부채"],
                    ["재무활동에서 생기는 기초 부채", "119,331", "23,179"],
                    ["재무현금흐름, 재무활동에서 생기는 부채의 증가(감소)", "(19,093)", "(10,063)"],
                    ["비현금증감, 재무활동에서 생기는 부채의 증가(감소)", "0", "7,075"],
                    ["재무활동에서 생기는 기말 부채", "103,600", "22,651"],
                ],
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    financing = [
        result
        for result in results
        if result.check_id == "reconciliation:borrowings.financing_cashflow"
    ]

    assert len(financing) == 1
    assert financing[0].status == "matched"
    assert financing[0].expected == -19093
    assert financing[0].actual == -19093
    assert financing[0].difference == 0
    assert [(e.label, e.amount) for e in financing[0].evidence] == [
        ("cfs 단기차입금의 순증감", -19093),
        ("note 31 재무활동현금흐름 차입금", -19093),
    ]


def test_check_reconciliation_targets_reconciles_lease_principal_using_interest_adjustment():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["리스부채의 원금 상환", "(14,880)"]],
            )
        ],
        [
            _section(
                "note:17",
                "리스부채",
                "note",
                "17",
                [["", "공시금액"], ["리스부채에 대한 이자비용", "3,282"]],
            ),
            _section(
                "note:35",
                "현금흐름표 재무활동에서 생기는 부채의 조정",
                "note",
                "35",
                [
                    ["", "", "리스 부채"],
                    ["기초, 재무활동에서 생기는 부채", "기초, 재무활동에서 생기는 부채", "29,534"],
                    ["재무활동에서 생기는 부채의 변동", "재무현금흐름, 재무활동에서 생기는 부채의 증가(감소)", "(18,162)"],
                    ["기말, 재무활동에서 생기는 부채", "기말, 재무활동에서 생기는 부채", "79,797"],
                ],
            ),
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    financing = [
        result
        for result in results
        if result.check_id == "reconciliation:lease_liabilities.financing_cashflow"
    ]

    assert len(financing) == 1
    assert financing[0].status == "matched"
    assert financing[0].expected == -14880
    assert financing[0].actual == -14880
    assert financing[0].difference == 0
    assert [(e.label, e.amount) for e in financing[0].evidence] == [
        ("cfs 리스부채의 원금 상환", -14880),
        ("note 17 리스부채 이자비용 조정", 3282),
        ("note 35 재무활동현금흐름 리스부채", -18162),
    ]


def test_check_reconciliation_targets_does_not_create_lease_financing_check_from_interest_only():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["리스부채의 원금 상환", "(14,880)"]],
            )
        ],
        [
            _section(
                "note:17",
                "리스부채",
                "note",
                "17",
                [["", "공시금액"], ["리스부채에 대한 이자비용", "3,282"]],
            ),
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)

    assert not [
        result
        for result in results
        if result.check_id == "reconciliation:lease_liabilities.financing_cashflow"
    ]


def test_check_reconciliation_targets_selects_bond_principal_repayment_from_bond_rollforward():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["사채의 상환", "(3,000)"]],
            )
        ],
        [
            _section(
                "note:38",
                "신주인수권부사채",
                "note",
                "38",
                [
                    ["구 분", "기초", "상환에 따른 감소", "상각/평가", "기말"],
                    ["원금", "105,000", "(3,000)", "-", "102,000"],
                    ["사채상환할증금", "22,749", "(650)", "-", "22,099"],
                    ["신주인수권부사채", "101,952", "(3,091)", "9,214", "108,076"],
                ],
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    financing = [
        result
        for result in results
        if result.check_id == "reconciliation:bonds.financing_cashflow"
    ]

    assert len(financing) == 1
    assert financing[0].status == "matched"
    assert financing[0].expected == -3000
    assert financing[0].actual == -3000
    assert [(e.label, e.amount) for e in financing[0].evidence] == [
        ("cfs 사채의 상환", -3000),
        ("note 38 사채 원금 상환", -3000),
    ]


def test_check_reconciliation_targets_keeps_financing_cashflow_movements_when_no_subset_matches():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["차입금의 상환", "(1,800)"]],
            )
        ],
        [
            _section(
                "note:30",
                "현금흐름표 재무활동에서 생기는 부채의 조정",
                "note",
                "30",
                [
                    ["구분", "단기차입금"],
                    ["재무활동에서 생기는 기초 부채", "5,000"],
                    ["차입금의 증가, 재무활동에서 생기는 부채", "1,000"],
                    ["차입금의 감소, 재무활동에서 생기는 부채", "(1,300)"],
                    ["재무활동에서 생기는 기말 부채", "4,700"],
                ],
            )
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    financing = [
        result
        for result in results
        if result.check_id == "reconciliation:borrowings.financing_cashflow"
    ]

    assert len(financing) == 1
    assert financing[0].status == "unexplained_gap"
    assert financing[0].expected == -1800
    assert financing[0].actual == -300
    assert financing[0].difference == 1500
    assert [(e.label, e.amount) for e in financing[0].evidence] == [
        ("cfs 차입금의 상환", -1800),
        ("note 30 재무활동현금흐름 차입금", 1000),
        ("note 30 재무활동현금흐름 차입금", -1300),
    ]


def test_check_reconciliation_targets_uses_duplicate_scope_financing_table_when_it_matches_cfs():
    consolidated_notes = [
        _section(
            f"note:{idx}:consolidated",
            f"Dummy note {idx} (연결)",
            "note",
            str(idx),
            [["구분", "당기"], ["dummy", "0"]],
        )
        for idx in range(1, 10)
    ]
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["리스부채의 상환", "(60)"]],
            )
        ],
        [
            *consolidated_notes,
            _section(
                "note:31:consolidated",
                "재무활동에서 생기는 부채의 조정 (연결)",
                "note",
                "31",
                [
                    ["", "", "당기초", "현금흐름", "기타", "당기말"],
                    ["재무활동에서 생기는 부채", "리스부채", "0", "(153)", "153", "0"],
                ],
            ),
            _section(
                "note:31:separate",
                "재무활동에서 생기는 부채의 조정",
                "note",
                "31",
                [
                    ["", "", "당기초", "현금흐름", "기타", "당기말"],
                    ["재무활동에서 생기는 부채", "리스부채", "0", "(60)", "60", "0"],
                ],
            ),
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    financing = [
        result
        for result in results
        if result.check_id == "reconciliation:lease_liabilities.financing_cashflow"
    ]

    assert len(financing) == 1
    assert financing[0].status == "matched"
    assert financing[0].expected == -60
    assert financing[0].actual == -60
    assert financing[0].difference == 0
    assert [(e.label, e.amount) for e in financing[0].evidence] == [
        ("cfs 리스부채의 상환", -60),
        ("note 31 재무활동현금흐름 리스부채", -60),
    ]


def test_check_reconciliation_targets_prefers_rou_lease_repayment_cashflow_note():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["리스부채의 상환", "(1,450)"]],
            )
        ],
        [
            _section(
                "note:15",
                "사용권자산 3) 현금흐름표에 인식한 금액",
                "note",
                "15",
                [
                    ["구분", "당기"],
                    ["리스부채의 상환", "1,450"],
                ],
            ),
            _section(
                "note:36",
                "재무활동에서 생기는 부채의 조정",
                "note",
                "36",
                [
                    ["", "", "당기초", "현금흐름", "기타", "당기말"],
                    ["재무활동에서 생기는 부채", "리스부채", "0", "(1,957)", "1,957", "0"],
                ],
            ),
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    financing = [
        result
        for result in results
        if result.check_id == "reconciliation:lease_liabilities.financing_cashflow"
    ]

    assert len(financing) == 1
    assert financing[0].status == "matched"
    assert financing[0].expected == -1450
    assert financing[0].actual == -1450
    assert financing[0].difference == 0
    assert [(e.label, e.amount) for e in financing[0].evidence] == [
        ("cfs 리스부채의 상환", -1450),
        ("note 15 리스부채의 상환", -1450),
    ]


def test_check_reconciliation_targets_matches_expense_by_nature_to_asset_allocation():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:15",
                "유형자산 감가상각비가 포함된 항목",
                "note",
                "15",
                [
                    ["", "", "감가상각비"],
                    ["기능별 항목", "매출원가", "700"],
                    ["기능별 항목", "판매비와 일반관리비", "300"],
                    ["기능별 항목", "기능별 항목", "1,000"],
                ],
            ),
            _section(
                "note:31",
                "비용의 성격별 분류",
                "note",
                "31",
                [
                    ["", "", "공시금액"],
                    ["성격별 비용 합계", "감가상각비", "1,000"],
                ],
            ),
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    allocation = [
        result
        for result in results
        if result.check_id
        == "reconciliation:property_plant_equipment.depreciation_expense_allocation"
    ]

    assert len(allocation) == 1
    assert allocation[0].check_type == "expense_allocation"
    assert allocation[0].status == "matched"
    assert allocation[0].expected == 1000
    assert allocation[0].actual == 1000
    assert allocation[0].difference == 0


def test_check_reconciliation_targets_excludes_development_cost_from_nature_allocation_basis():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:15",
                "유형자산 감가상각비가 포함된 항목",
                "note",
                "15",
                [
                    ["", "", "감가상각비"],
                    ["기능별 항목", "제조원가", "700"],
                    ["기능별 항목", "판매비와관리비", "300"],
                    ["기능별 항목", "개발비", "20"],
                    ["기능별 항목", "합계", "1,020"],
                ],
            ),
            _section(
                "note:31",
                "비용의 성격별 분류",
                "note",
                "31",
                [
                    ["", "", "공시금액"],
                    ["성격별 비용 합계", "감가상각비", "1,000"],
                ],
            ),
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    allocation = [
        result
        for result in results
        if result.check_id
        == "reconciliation:property_plant_equipment.depreciation_expense_allocation"
    ]

    assert len(allocation) == 1
    assert allocation[0].status == "matched"
    assert allocation[0].expected == 1000
    assert allocation[0].actual == 1000
    assert allocation[0].difference == 0
    assert allocation[0].reason == (
        "제조원가 700 + 판매비와관리비 300 = 1,000; "
        "성격별 비용 감가상각비 1,000; "
        "개발비 20은 성격별 비용 대사 기준에서 제외; "
        "차이 0; 성격별 비용 주석과 자산 주석 기능별 배부가 직접 대사됨"
    )


def test_check_reconciliation_targets_excludes_research_development_cost_from_nature_allocation_basis():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:15",
                "무형자산 상각비가 포함된 항목",
                "note",
                "15",
                [
                    ["", "", "무형자산상각비"],
                    ["기능별 항목", "매출원가", "400"],
                    ["기능별 항목", "판매비와관리비", "200"],
                    ["기능별 항목", "연구비", "30"],
                    ["기능별 항목", "합계", "630"],
                ],
            ),
            _section(
                "note:31",
                "비용의 성격별 분류",
                "note",
                "31",
                [
                    ["", "", "공시금액"],
                    ["성격별 비용 합계", "무형자산상각비", "600"],
                ],
            ),
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    allocation = [
        result
        for result in results
        if result.check_id
        == "reconciliation:intangible_assets.amortization_expense_allocation"
    ]

    assert len(allocation) == 1
    assert allocation[0].status == "matched"
    assert allocation[0].expected == 600
    assert allocation[0].actual == 600
    assert allocation[0].difference == 0
    assert "연구비 30은 성격별 비용 대사 기준에서 제외" in allocation[0].reason


def test_check_reconciliation_targets_excludes_investment_property_depreciation_from_ppe_nature_basis():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:10",
                "유형자산 감가상각비가 포함된 항목",
                "note",
                "10",
                [
                    ["", "", "감가상각비"],
                    ["기능별 항목", "매출원가", "700"],
                    ["기능별 항목", "판매비와관리비", "300"],
                    ["기능별 항목", "합계", "1,000"],
                ],
            ),
            _section(
                "note:11",
                "투자부동산",
                "note",
                "11",
                [
                    ["", "", "토지", "건물", "합계"],
                    ["투자부동산의 변동에 대한 조정", "기초", "0", "3,000", "3,000"],
                    ["투자부동산의 변동에 대한 조정", "감가상각비, 투자부동산", "0", "(200)", "(200)"],
                    ["투자부동산의 변동에 대한 조정", "기말", "0", "2,800", "2,800"],
                ],
            ),
            _section(
                "note:31",
                "비용의 성격별 분류",
                "note",
                "31",
                [
                    ["", "", "공시금액"],
                    ["성격별 비용 합계", "감가상각비", "1,200"],
                ],
            ),
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    allocation = [
        result
        for result in results
        if result.check_id
        == "reconciliation:property_plant_equipment.depreciation_expense_allocation"
    ]

    assert len(allocation) == 1
    assert allocation[0].status == "matched"
    assert allocation[0].expected == 1000
    assert allocation[0].actual == 1000
    assert allocation[0].difference == 0
    assert allocation[0].reason == (
        "매출원가 700 + 판매비와관리비 300 = 1,000; "
        "성격별 비용 감가상각비 1,200 - 투자부동산 감가상각비 200 = 1,000; "
        "차이 0; 성격별 비용 주석과 자산 주석 기능별 배부가 직접 대사됨"
    )


def test_check_reconciliation_targets_keeps_investment_property_depreciation_when_it_does_not_reconcile():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:10",
                "유형자산 감가상각비가 포함된 항목",
                "note",
                "10",
                [
                    ["", "", "감가상각비"],
                    ["기능별 항목", "매출원가", "700"],
                    ["기능별 항목", "판매비와관리비", "300"],
                    ["기능별 항목", "합계", "1,000"],
                ],
            ),
            _section(
                "note:11",
                "투자부동산",
                "note",
                "11",
                [
                    ["", "", "토지", "건물", "합계"],
                    ["투자부동산의 변동에 대한 조정", "감가상각비, 투자부동산", "0", "(50)", "(50)"],
                ],
            ),
            _section(
                "note:31",
                "비용의 성격별 분류",
                "note",
                "31",
                [
                    ["", "", "공시금액"],
                    ["성격별 비용 합계", "감가상각비", "1,200"],
                ],
            ),
        ],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    allocation = [
        result
        for result in results
        if result.check_id
        == "reconciliation:property_plant_equipment.depreciation_expense_allocation"
    ]

    assert allocation[0].status == "unexplained_gap"
    assert allocation[0].expected == 1200
    assert allocation[0].actual == 1000
    assert allocation[0].reason == (
        "매출원가 700 + 판매비와관리비 300 = 1,000; "
        "성격별 비용 감가상각비 1,200; "
        "차이 (200); 성격별 비용 주석과 자산 주석 기능별 배부가 직접 대사되지 않음"
    )


def test_check_reconciliation_targets_skips_when_statement_or_note_missing():
    statement_only = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:bs",
                "재무상태표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산", "1,000"]],
            )
        ],
        [],
    )
    note_only = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:11",
                "유형자산",
                "note",
                "11",
                [["구분", "합계"], ["기말 장부금액", "1,000"]],
            )
        ],
    )

    assert check_reconciliation_targets(statement_only, tolerance=0) == []
    assert check_reconciliation_targets(note_only, tolerance=0) == []
