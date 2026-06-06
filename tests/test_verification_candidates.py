from dart_footing_reconciler.document import ReportTable, SourceLocation
from dart_footing_reconciler.layout_variants import LayoutClassification
from dart_footing_reconciler.orientation import TableOrientation
from dart_footing_reconciler.verification_candidates import (
    extract_verification_candidates,
)


def test_extracts_row_oriented_rollforward_candidates_with_unit_multiplier():
    table = ReportTable(
        0,
        [
            ["구분", "토지", "합계"],
            ["기초", "100", "100"],
            ["취득", "50", "50"],
            ["기말", "150", "150"],
        ],
        "11. 유형자산",
        SourceLocation("note:11", 0, 0),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="11",
        title="유형자산",
        table=table,
        layout=LayoutClassification(
            "asset_current_period_carrying_amount",
            0.75,
            ("layout",),
            "note:11/table:0",
        ),
        orientation=TableOrientation("row_oriented", 0.9, ("movement labels in rows",)),
    )

    ending = next(candidate for candidate in candidates if candidate.role == "ending")
    assert ending.raw_amount == 150
    assert ending.unit_multiplier == 1000
    assert ending.amount == 150_000
    assert ending.table_source == "note:11/table:0"
    assert ending.row_index == 3
    assert ending.column_index == 2
    assert ending.layout_key == "asset_current_period_carrying_amount"
    assert ending.orientation_key == "row_oriented"


def test_extracts_period_oriented_current_period_candidate():
    table = ReportTable(
        1,
        [["구분", "당기", "전기"], ["장부금액", "200", "180"]],
        "12. 무형자산",
        SourceLocation("note:12", 0, 1),
        unit_multiplier=1_000_000,
    )

    candidates = extract_verification_candidates(
        note_no="12",
        title="무형자산",
        table=table,
        layout=LayoutClassification(
            "asset_current_period_carrying_amount",
            0.75,
            ("layout",),
            "note:12/table:1",
        ),
        orientation=TableOrientation("period_oriented", 0.8, ("period labels in columns",)),
    )

    assert [(candidate.role, candidate.amount, candidate.column_index) for candidate in candidates] == [
        ("ending", 200_000_000, 1)
    ]


def test_extracts_earnings_per_share_candidates_with_row_unit_overrides():
    table = ReportTable(
        121,
        [
            ["", "보통주"],
            ["지배기업의 보통주에 귀속되는 계속영업당기순이익(손실)", "8,671,234"],
            ["가중평균유통보통주식수", "4,277,208"],
            ["계속영업기본주당이익(손실)", "2,027"],
        ],
        "24. 주당순손익 및 배당금",
        SourceLocation("note:24", 0, 121),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="24",
        title="주당순손익 및 배당금",
        table=table,
        layout=LayoutClassification(
            "earnings_per_share_summary",
            0.85,
            ("earnings per share rows",),
            "note:24/table:121",
        ),
        orientation=TableOrientation("row_oriented", 0.85, ("earnings per share rows",)),
    )

    assert [
        (
            candidate.account_key,
            candidate.role,
            candidate.raw_amount,
            candidate.unit_multiplier,
            candidate.amount,
            candidate.row_index,
            candidate.column_index,
        )
        for candidate in candidates
    ] == [
        ("continuing_basic_eps", "eps_profit", 8_671_234, 1000, 8_671_234_000, 1, 1),
        ("continuing_basic_eps", "weighted_average_shares", 4_277_208, 1, 4_277_208, 2, 1),
        ("continuing_basic_eps", "earnings_per_share", 2_027, 1, 2_027, 3, 1),
    ]


def test_extracts_dividend_payout_candidates_by_period_columns():
    table = ReportTable(
        350,
        [
            ["구 분", "주식의 종류", "당기", "전기", "전전기"],
            ["구 분", "주식의 종류", "제44기", "제43기", "제42기"],
            ["(연결)당기순이익(백만원)", "(연결)당기순이익(백만원)", "29,040", "34,053", "-2,470"],
            ["현금배당금총액(백만원)", "현금배당금총액(백만원)", "17,109", "37,326", "10,664"],
            ["(연결)현금배당성향(%)", "(연결)현금배당성향(%)", "58.9", "109.6", "-"],
        ],
        "6. 배당에 관한 사항",
        SourceLocation("note:6", 0, 350),
        unit_multiplier=1,
    )

    candidates = extract_verification_candidates(
        note_no="6",
        title="배당에 관한 사항",
        table=table,
        layout=LayoutClassification(
            "dividend_payout_summary",
            0.85,
            ("dividend payout ratio rows",),
            "note:6/table:350",
        ),
        orientation=TableOrientation("period_oriented", 0.8, ("period labels in columns",)),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("dividend_payout:당기", "dividend_net_income", 29_040, 2, 2),
        ("dividend_payout:전기", "dividend_net_income", 34_053, 2, 3),
        ("dividend_payout:전전기", "dividend_net_income", -2_470, 2, 4),
        ("dividend_payout:당기", "cash_dividends", 17_109, 3, 2),
        ("dividend_payout:전기", "cash_dividends", 37_326, 3, 3),
        ("dividend_payout:전전기", "cash_dividends", 10_664, 3, 4),
        ("dividend_payout:당기", "dividend_payout_ratio_tenths", 589, 4, 2),
        ("dividend_payout:전기", "dividend_payout_ratio_tenths", 1_096, 4, 3),
    ]


def test_extracts_lease_liability_current_noncurrent_summary_candidates():
    table = ReportTable(
        34,
        [
            ["", "공시금액"],
            ["유동 리스부채", "1,000"],
            ["비유동 리스부채", "2,000"],
            ["합계", "3,000"],
        ],
        "34. 리스",
        SourceLocation("note:34", 0, 34),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="34",
        title="리스",
        table=table,
        layout=LayoutClassification(
            "lease_liability_current_noncurrent_summary",
            0.85,
            ("layout",),
            "note:34/table:34",
        ),
        orientation=TableOrientation(
            "row_oriented",
            0.85,
            ("lease liability split rows", "amount column"),
        ),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.label, candidate.amount, candidate.row_index)
        for candidate in candidates
    ] == [
        ("lease_liabilities", "lease_liability_split_component", "유동 리스부채", 1_000_000, 1),
        ("lease_liabilities", "lease_liability_split_component", "비유동 리스부채", 2_000_000, 2),
        ("lease_liabilities", "ending", "합계", 3_000_000, 3),
    ]


def test_extracts_column_oriented_asset_measure_summary_account_row_candidate():
    table = ReportTable(
        2,
        [
            ["", "총장부금액", "감가상각누계액 및 상각누계액", "장부금액 합계"],
            ["투자부동산", "1,000", "200", "800"],
        ],
        "13. 투자부동산",
        SourceLocation("note:13", 0, 2),
        unit_multiplier=1_000_000,
    )

    candidates = extract_verification_candidates(
        note_no="13",
        title="투자부동산",
        table=table,
        layout=LayoutClassification(
            "asset_measure_summary",
            0.85,
            ("asset topic in title or rows",),
            "note:13/table:2",
        ),
        orientation=TableOrientation("column_oriented", 0.9, ("measure labels in columns",)),
    )

    assert [(candidate.role, candidate.amount, candidate.row_index, candidate.column_index) for candidate in candidates] == [
        ("ending", 800_000_000, 1, 3)
    ]
    assert candidates[0].account_key == "investment_property"


def test_extracts_asset_component_column_summary_candidates():
    table = ReportTable(
        94,
        [
            ["", "", "", "", "상각자산", "개발 중인 무형자산", "장부금액"],
            ["무형자산 및 영업권", "자본화된 개발비 지출액", "부문", "차량부품", "26,765", "37,868", "64,633"],
            ["무형자산 및 영업권", "자본화된 개발비 지출액", "부문", "특수", "3,326", "519", "3,845"],
            ["무형자산 및 영업권 합계", "무형자산 및 영업권 합계", "무형자산 및 영업권 합계", "무형자산 및 영업권 합계", "30,091", "38,387", "68,478"],
        ],
        "13. 무형자산 및 영업권",
        SourceLocation("note:13", 0, 94),
        unit_multiplier=1_000_000,
    )

    candidates = extract_verification_candidates(
        note_no="13",
        title="무형자산 및 영업권",
        table=table,
        layout=LayoutClassification(
            "asset_component_column_summary",
            0.85,
            ("asset component columns",),
            "note:13/table:94",
        ),
        orientation=TableOrientation(
            "column_oriented",
            0.85,
            ("asset component columns",),
        ),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.label, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("asset_component_row:차량부품", "asset_component", "차량부품 상각자산", 26_765_000_000, 1, 4),
        ("asset_component_row:차량부품", "asset_component", "차량부품 개발 중인 무형자산", 37_868_000_000, 1, 5),
        ("asset_component_row:차량부품", "asset_component_total", "차량부품 장부금액", 64_633_000_000, 1, 6),
        ("asset_component_row:특수", "asset_component", "특수 상각자산", 3_326_000_000, 2, 4),
        ("asset_component_row:특수", "asset_component", "특수 개발 중인 무형자산", 519_000_000, 2, 5),
        ("asset_component_row:특수", "asset_component_total", "특수 장부금액", 3_845_000_000, 2, 6),
        ("asset_component_row:무형자산 및 영업권 합계", "asset_component", "무형자산 및 영업권 합계 상각자산", 30_091_000_000, 3, 4),
        ("asset_component_row:무형자산 및 영업권 합계", "asset_component", "무형자산 및 영업권 합계 개발 중인 무형자산", 38_387_000_000, 3, 5),
        ("asset_component_row:무형자산 및 영업권 합계", "asset_component_total", "무형자산 및 영업권 합계 장부금액", 68_478_000_000, 3, 6),
    ]


def test_extracts_asset_cost_accumulated_summary_component_candidates():
    table = ReportTable(
        3,
        [
            ["", "취득원가", "감가상각누계액 및 상각누계액"],
            ["토지", "100", "0"],
            ["건물", "200", "(50)"],
            ["합계", "300", "(50)"],
        ],
        "13. 투자부동산",
        SourceLocation("note:13", 0, 3),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="13",
        title="투자부동산",
        table=table,
        layout=LayoutClassification(
            "asset_cost_accumulated_summary",
            0.85,
            ("asset topic in title or rows",),
            "note:13/table:3",
        ),
        orientation=TableOrientation("column_oriented", 0.9, ("measure labels in columns",)),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("investment_property", "gross_cost", 300_000, 3, 1),
        ("investment_property", "accumulated_depreciation", -50_000, 3, 2),
    ]


def test_extracts_asset_cost_accumulated_summary_component_net_candidates():
    table = ReportTable(
        3,
        [
            ["계 정 과 목", "취득원가", "상각누계액", "손상차손누계액", "기 말"],
            ["회 원 권", "1,405,264", "-", "(435,261)", "970,003"],
            ["소프트웨어", "1,238,823", "(1,178,732)", "-", "60,091"],
            ["합 계", "2,644,087", "(1,178,732)", "(435,261)", "1,030,094"],
        ],
        "7. 무형자산",
        SourceLocation("note:7", 0, 3),
        unit_multiplier=1,
    )

    candidates = extract_verification_candidates(
        note_no="7",
        title="무형자산",
        table=table,
        layout=LayoutClassification(
            "asset_cost_accumulated_summary",
            0.85,
            ("headers include gross amount",),
            "note:7/table:3",
        ),
        orientation=TableOrientation("column_oriented", 0.9, ("measure labels in columns",)),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("intangible_assets", "gross_cost", 2_644_087, 3, 1),
        ("intangible_assets", "accumulated_depreciation", -1_178_732, 3, 2),
        ("intangible_assets", "accumulated_impairment", -435_261, 3, 3),
        ("intangible_assets", "ending", 1_030_094, 3, 4),
    ]


def test_extracts_mixed_asset_movement_columns_from_total_row():
    table = ReportTable(
        3,
        [
            ["", "", "기초", "처분", "감가상각", "기말"],
            ["유형자산", "토지", "100", "(10)", "0", "90"],
            ["유형자산 합계", "유형자산 합계", "100", "(10)", "0", "90"],
        ],
        "11. 유형자산",
        SourceLocation("note:11", 0, 3),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="11",
        title="유형자산",
        table=table,
        layout=LayoutClassification(
            "asset_movement_columns",
            0.85,
            ("movement labels in headers",),
            "note:11/table:3",
        ),
        orientation=TableOrientation("mixed", 0.75, ("movement labels in columns",)),
    )

    assert [(candidate.role, candidate.amount, candidate.row_index, candidate.column_index) for candidate in candidates] == [
        ("beginning", 100_000, 2, 2),
        ("disposals", -10_000, 2, 3),
        ("depreciation", 0, 2, 4),
        ("ending", 90_000, 2, 5),
    ]


def test_extracts_mixed_asset_movement_columns_with_embedded_asset_headers():
    table = ReportTable(
        4,
        [
            ["", "", "기초 유형자산", "취득", "감가상각", "제거", "기말 유형자산"],
            ["유형자산", "토지", "100", "20", "0", "(5)", "115"],
            ["유형자산 합계", "유형자산 합계", "100", "20", "0", "(5)", "115"],
        ],
        "11. 유형자산",
        SourceLocation("note:11", 0, 4),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="11",
        title="유형자산",
        table=table,
        layout=LayoutClassification(
            "asset_movement_columns",
            0.85,
            ("movement labels in headers",),
            "note:11/table:4",
        ),
        orientation=TableOrientation("mixed", 0.75, ("movement labels in columns",)),
    )

    assert [(candidate.role, candidate.amount, candidate.column_index) for candidate in candidates] == [
        ("beginning", 100_000, 2),
        ("additions", 20_000, 3),
        ("depreciation", 0, 4),
        ("disposals", -5_000, 5),
        ("ending", 115_000, 6),
    ]


def test_extracts_asset_period_rollforward_summary_candidates():
    table = ReportTable(
        21,
        [
            ["구분", "기초", "처분", "기말"],
            ["당기", "64,487,052", "-", "64,487,052"],
            ["전기", "67,148,934", "(2,661,882)", "64,487,052"],
        ],
        "8. 유형자산",
        SourceLocation("note:8", 0, 21),
        unit_multiplier=1,
    )

    candidates = extract_verification_candidates(
        note_no="8",
        title="유형자산",
        table=table,
        layout=LayoutClassification(
            "asset_period_rollforward_summary",
            0.85,
            ("movement labels in headers", "period labels in rows"),
            "note:8/table:21",
        ),
        orientation=TableOrientation(
            "row_oriented",
            0.85,
            ("movement labels in columns", "period labels in rows"),
        ),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("asset_period_rollforward:당기", "beginning", 64_487_052, 1, 1),
        ("asset_period_rollforward:당기", "ending", 64_487_052, 1, 3),
        ("asset_period_rollforward:전기", "beginning", 67_148_934, 2, 1),
        ("asset_period_rollforward:전기", "signed_movement", -2_661_882, 2, 2),
        ("asset_period_rollforward:전기", "ending", 64_487_052, 2, 3),
    ]


def test_extracts_asset_two_label_row_rollforward_summary_candidates():
    table = ReportTable(
        82,
        [
            ["", "", "취득 완료 투자부동산"],
            ["투자부동산의 변동에 대한 조정", "투자부동산의 변동에 대한 조정", ""],
            ["투자부동산의 변동에 대한 조정", "기초", "6,699"],
            ["투자부동산의 변동에 대한 조정", "감가상각비", "(31)"],
            ["투자부동산의 변동에 대한 조정", "대체", "(4,281)"],
            ["투자부동산의 변동에 대한 조정", "기타(환율효과 등)", "711"],
            ["투자부동산의 변동에 대한 조정", "기말", "3,098"],
        ],
        "12. 투자부동산",
        SourceLocation("note:12", 0, 82),
        unit_multiplier=1_000_000,
    )

    candidates = extract_verification_candidates(
        note_no="12",
        title="투자부동산",
        table=table,
        layout=LayoutClassification(
            "asset_two_label_row_rollforward_summary",
            0.85,
            ("movement labels in secondary row labels",),
            "note:12/table:82",
        ),
        orientation=TableOrientation(
            "row_oriented",
            0.85,
            ("asset movement detail rows",),
        ),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("investment_property", "beginning", 6_699_000_000, 2, 2),
        ("investment_property", "signed_movement", -31_000_000, 3, 2),
        ("investment_property", "signed_movement", -4_281_000_000, 4, 2),
        ("investment_property", "signed_movement", 711_000_000, 5, 2),
        ("investment_property", "ending", 3_098_000_000, 6, 2),
    ]


def test_extracts_row_oriented_right_of_use_asset_candidates_from_lease_note():
    table = ReportTable(
        5,
        [
            ["", "부동산", "차량운반구", "자산 합계"],
            ["기초 사용권자산", "100", "10", "110"],
            ["취득", "20", "5", "25"],
            ["종료", "(10)", "0", "(10)"],
            ["리스변경", "3", "0", "3"],
            ["감가상각비", "(30)", "(2)", "(32)"],
            ["기말 사용권자산", "83", "13", "96"],
        ],
        "34. 리스",
        SourceLocation("note:34", 0, 5),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="34",
        title="리스",
        table=table,
        layout=LayoutClassification(
            "asset_row_movement_total",
            0.85,
            ("asset movement labels in rows",),
            "note:34/table:5",
        ),
        orientation=TableOrientation("row_oriented", 0.9, ("movement labels in rows",)),
    )

    assert [(candidate.role, candidate.amount, candidate.row_index) for candidate in candidates] == [
        ("beginning", 110_000, 1),
        ("additions", 25_000, 2),
        ("disposals", -10_000, 3),
        ("transfers", 3_000, 4),
        ("depreciation", -32_000, 5),
        ("ending", 96_000, 6),
    ]


def test_extracts_stacked_measure_summary_ending_candidate():
    table = ReportTable(
        6,
        [
            ["", "", "영업권 이외의 무형자산"],
            ["장부금액", "취득원가", "50,333"],
            ["장부금액", "상각누계액과 손상차손누계액", "(32,995)"],
            ["장부금액", "정부보조금", "(223)"],
            ["장부금액 합계", "장부금액 합계", "17,115"],
        ],
        "20. 무형자산",
        SourceLocation("note:20", 0, 6),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="20",
        title="무형자산",
        table=table,
        layout=LayoutClassification(
            "asset_stacked_measure_summary",
            0.85,
            ("asset topic in headers",),
            "note:20/table:6",
        ),
        orientation=TableOrientation("mixed", 0.75, ("asset labels in columns",)),
    )

    assert [(candidate.role, candidate.amount, candidate.row_index, candidate.column_index) for candidate in candidates] == [
        ("ending", 17_115_000, 4, 2)
    ]
    assert candidates[0].account_key == "intangible_assets"


def test_extracts_financial_category_summary_balance_candidates():
    table = ReportTable(
        7,
        [
            [
                "",
                "당기손익인식금융자산",
                "기타포괄손익-공정가치 측정 금융자산",
                "상각후원가측정 금융자산",
                "금융자산",
                "범주 합계",
            ],
            ["현금및현금성자산", "-", "-", "100", "100", "100"],
            ["매출채권", "-", "-", "250", "250", "250"],
            ["기타유동금융자산", "10", "20", "30", "60", "60"],
        ],
        "4. 범주별 금융상품",
        SourceLocation("note:4", 0, 7),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="4",
        title="범주별 금융상품",
        table=table,
        layout=LayoutClassification(
            "financial_instrument_category_summary",
            0.85,
            ("financial instrument categories in headers",),
            "note:4/table:7",
        ),
        orientation=TableOrientation(
            "column_oriented",
            0.85,
            ("financial category labels in columns",),
        ),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("cash_and_cash_equivalents", "financial_category_component", 100_000, 1, 3),
        ("cash_and_cash_equivalents", "ending", 100_000, 1, 5),
        ("trade_receivables", "financial_category_component", 250_000, 2, 3),
        ("trade_receivables", "ending", 250_000, 2, 5),
        ("other_current_financial_assets", "financial_category_component", 10_000, 3, 1),
        ("other_current_financial_assets", "financial_category_component", 20_000, 3, 2),
        ("other_current_financial_assets", "financial_category_component", 30_000, 3, 3),
        ("other_current_financial_assets", "ending", 60_000, 3, 5),
    ]


def test_extracts_financial_category_summary_with_plain_total_header():
    table = ReportTable(
        18,
        [
            ["구분", "상각후원가측정 금융자산", "당기손익-공정가치측정 금융자산", "상각후원가측정 금융부채", "당기손익-공정가치측정 금융부채", "합 계"],
            ["금융자산", "", "", "", "", ""],
            ["현금및현금성자산", "100", "", "", "", "100"],
            ["매출채권", "250", "", "", "", "250"],
            ["기타금융자산", "30", "20", "", "", "50"],
            ["합계", "380", "20", "", "", "400"],
            ["금융부채", "", "", "", "", ""],
            ["매입채무", "", "", "70", "", "70"],
            ["파생상품부채", "", "", "", "5", "5"],
            ["합계", "", "", "70", "5", "75"],
        ],
        "6. 범주별 금융상품",
        SourceLocation("note:6", 0, 18),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="6",
        title="범주별 금융상품",
        table=table,
        layout=LayoutClassification(
            "financial_instrument_category_summary",
            0.85,
            ("financial instrument categories in headers",),
            "note:6/table:18",
        ),
        orientation=TableOrientation(
            "column_oriented",
            0.85,
            ("financial category labels in columns",),
        ),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("cash_and_cash_equivalents", "financial_category_component", 100_000, 2, 1),
        ("cash_and_cash_equivalents", "ending", 100_000, 2, 5),
        ("trade_receivables", "financial_category_component", 250_000, 3, 1),
        ("trade_receivables", "ending", 250_000, 3, 5),
        ("other_financial_assets", "financial_category_component", 30_000, 4, 1),
        ("other_financial_assets", "financial_category_component", 20_000, 4, 2),
        ("other_financial_assets", "ending", 50_000, 4, 5),
        ("trade_payables", "financial_category_component", 70_000, 7, 3),
        ("trade_payables", "ending", 70_000, 7, 5),
        ("derivative_liabilities", "financial_category_component", 5_000, 8, 4),
        ("derivative_liabilities", "ending", 5_000, 8, 5),
    ]


def test_extracts_financial_category_summary_two_label_column_rows():
    table = ReportTable(
        50,
        [
            ["", "", "당기손익인식금융부채", "상각후원가로 측정하는 금융부채, 범주", "기타금융부채", "금융부채, 범주 합계"],
            ["금융부채", "금융부채", "7,179,749", "3,560,241,259", "1,447,632,719", "5,015,053,727"],
            ["금융부채", "매입채무", "0", "833,568,146", "0", "833,568,146"],
            ["금융부채", "차입금", "0", "2,058,139,672", "0", "2,058,139,672"],
            ["금융부채", "기타금융부채", "7,179,749", "668,533,441", "0", "675,713,190"],
            ["금융부채", "리스부채", "0", "0", "1,447,632,719", "1,447,632,719"],
        ],
        "7. 범주별 금융상품",
        SourceLocation("note:7", 0, 50),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="7",
        title="범주별 금융상품",
        table=table,
        layout=LayoutClassification(
            "financial_instrument_category_summary",
            0.85,
            ("financial instrument categories in headers",),
            "note:7/table:50",
        ),
        orientation=TableOrientation(
            "column_oriented",
            0.85,
            ("financial category labels in columns",),
        ),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("trade_payables", "financial_category_component", 833_568_146_000, 2, 3),
        ("trade_payables", "ending", 833_568_146_000, 2, 5),
        ("borrowings", "financial_category_component", 2_058_139_672_000, 3, 3),
        ("borrowings", "ending", 2_058_139_672_000, 3, 5),
        ("other_financial_liabilities", "financial_category_component", 7_179_749_000, 4, 2),
        ("other_financial_liabilities", "financial_category_component", 668_533_441_000, 4, 3),
        ("other_financial_liabilities", "ending", 675_713_190_000, 4, 5),
        ("lease_liabilities", "financial_category_component", 1_447_632_719_000, 5, 4),
        ("lease_liabilities", "ending", 1_447_632_719_000, 5, 5),
    ]


def test_extracts_financial_category_column_total_candidates():
    table = ReportTable(
        46,
        [
            [
                "구분",
                "상각후원가측정 금융자산",
                "당기손익-공정가치측정 금융자산",
                "기타포괄손익-공정가치측정 금융자산",
            ],
            ["현금및현금성자산", "100", "", ""],
            ["매출채권", "250", "", ""],
            ["기타금융자산", "30", "20", "10"],
            ["합계", "380", "20", "10"],
        ],
        "6. 범주별 금융상품",
        SourceLocation("note:6", 0, 46),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="6",
        title="범주별 금융상품",
        table=table,
        layout=LayoutClassification(
            "financial_instrument_category_summary",
            0.85,
            ("financial instrument categories in headers",),
            "note:6/table:46",
        ),
        orientation=TableOrientation(
            "column_oriented",
            0.85,
            ("financial category labels in columns",),
        ),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("financial_category:상각후원가측정금융자산", "financial_category_column_component", 100_000, 1, 1),
        ("financial_category:상각후원가측정금융자산", "financial_category_column_component", 250_000, 2, 1),
        ("financial_category:상각후원가측정금융자산", "financial_category_column_component", 30_000, 3, 1),
        ("financial_category:상각후원가측정금융자산", "financial_category_column_total", 380_000, 4, 1),
        ("financial_category:당기손익-공정가치측정금융자산", "financial_category_column_component", 20_000, 3, 2),
        ("financial_category:당기손익-공정가치측정금융자산", "financial_category_column_total", 20_000, 4, 2),
        ("financial_category:기타포괄손익-공정가치측정금융자산", "financial_category_column_component", 10_000, 3, 3),
        ("financial_category:기타포괄손익-공정가치측정금융자산", "financial_category_column_total", 10_000, 4, 3),
    ]


def test_extracts_financial_fair_value_summary_candidates():
    table = ReportTable(
        200,
        [
            ["", "공정가치"],
            ["현금및현금성자산", "83,682,420"],
            ["단기금융상품", "20,000,000"],
            ["매출채권및기타채권 (주1)", "93,397,239"],
            ["기타비유동금융자산", "7,976,518"],
            ["금융자산", "205,056,177"],
        ],
        "34. 금융상품",
        SourceLocation("note:34", 0, 200),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="34",
        title="금융상품",
        table=table,
        layout=LayoutClassification(
            "financial_instrument_fair_value_summary",
            0.85,
            ("fair value amount column",),
            "note:34/table:200",
        ),
        orientation=TableOrientation("row_oriented", 0.85, ("financial fair value amount column",)),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("cash_and_cash_equivalents", "fair_value_component", 83_682_420_000, 1, 1),
        ("short_term_financial_instruments", "fair_value_component", 20_000_000_000, 2, 1),
        ("trade_other_receivables", "fair_value_component", 93_397_239_000, 3, 1),
        ("other_noncurrent_financial_assets", "fair_value_component", 7_976_518_000, 4, 1),
        ("financial_assets", "fair_value_total", 205_056_177_000, 5, 1),
    ]


def test_extracts_financial_fair_value_level_summary_candidates():
    table = ReportTable(
        52,
        [
            ["구 분", "금융상품", "(수준1)", "(수준2)", "(수준3)", "합 계"],
            ["금융자산", "당기손익-공정가치측정금융자산", "127", "700", "3,803", "4,630"],
            ["금융자산", "파생상품(위험회피목적)", "-", "134", "-", "134"],
            ["금융자산", "합 계", "127", "834", "3,803", "4,764"],
            ["금융부채", "파생상품부채(위험회피목적)", "-", "266", "-", "266"],
        ],
        "6. 금융상품 공정가치",
        SourceLocation("note:6", 0, 52),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="6",
        title="금융상품 공정가치",
        table=table,
        layout=LayoutClassification(
            "financial_fair_value_level_summary",
            0.85,
            ("fair value hierarchy level columns",),
            "note:6/table:52",
        ),
        orientation=TableOrientation(
            "column_oriented",
            0.85,
            ("fair value hierarchy level columns", "financial account labels in rows"),
        ),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.label, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("financial_assets_fvtpl", "fair_value_level_component", "당기손익-공정가치측정금융자산 (수준1)", 127_000, 1, 2),
        ("financial_assets_fvtpl", "fair_value_level_component", "당기손익-공정가치측정금융자산 (수준2)", 700_000, 1, 3),
        ("financial_assets_fvtpl", "fair_value_level_component", "당기손익-공정가치측정금융자산 (수준3)", 3_803_000, 1, 4),
        ("financial_assets_fvtpl", "fair_value_total", "당기손익-공정가치측정금융자산 합 계", 4_630_000, 1, 5),
        ("derivative_assets", "fair_value_level_component", "파생상품(위험회피목적) (수준2)", 134_000, 2, 3),
        ("derivative_assets", "fair_value_total", "파생상품(위험회피목적) 합 계", 134_000, 2, 5),
        ("financial_assets", "fair_value_level_component", "합 계 (수준1)", 127_000, 3, 2),
        ("financial_assets", "fair_value_level_component", "합 계 (수준2)", 834_000, 3, 3),
        ("financial_assets", "fair_value_level_component", "합 계 (수준3)", 3_803_000, 3, 4),
        ("financial_assets", "fair_value_total", "합 계 합 계", 4_764_000, 3, 5),
        ("derivative_liabilities", "fair_value_level_component", "파생상품부채(위험회피목적) (수준2)", 266_000, 4, 3),
        ("derivative_liabilities", "fair_value_total", "파생상품부채(위험회피목적) 합 계", 266_000, 4, 5),
    ]


def test_extracts_tax_expense_composition_summary_candidates():
    table = ReportTable(
        139,
        [
            ["구 분", "당기", "전기"],
            ["법인세등 부담액", "11,977,263", "11,998,514"],
            ["일시적차이 등으로 인한 이연법인세 변동액", "483,495", "(1,697,799)"],
            ["자본에 직접 가감된 법인세부담액", "183,151", "1,023,122"],
            ["법인세비용", "12,643,908", "11,323,837"],
        ],
        "35. 법인세비용",
        SourceLocation("note:35", 0, 139),
    )

    candidates = extract_verification_candidates(
        note_no="35",
        title="법인세비용",
        table=table,
        layout=LayoutClassification(
            "tax_expense_composition_summary",
            0.85,
            ("tax expense component rows",),
            "note:35/table:139",
        ),
        orientation=TableOrientation(
            "column_oriented",
            0.85,
            ("tax expense component rows", "period amount columns"),
        ),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.label, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("income_tax_expense", "tax_expense_component", "법인세등 부담액 당기", 11_977_263, 1, 1),
        ("income_tax_expense", "tax_expense_component", "일시적차이 등으로 인한 이연법인세 변동액 당기", 483_495, 2, 1),
        ("income_tax_expense", "tax_expense_component", "자본에 직접 가감된 법인세부담액 당기", 183_151, 3, 1),
        ("income_tax_expense", "tax_expense_total", "법인세비용 당기", 12_643_908, 4, 1),
        ("income_tax_expense", "tax_expense_component", "법인세등 부담액 전기", 11_998_514, 1, 2),
        ("income_tax_expense", "tax_expense_component", "일시적차이 등으로 인한 이연법인세 변동액 전기", -1_697_799, 2, 2),
        ("income_tax_expense", "tax_expense_component", "자본에 직접 가감된 법인세부담액 전기", 1_023_122, 3, 2),
        ("income_tax_expense", "tax_expense_total", "법인세비용 전기", 11_323_837, 4, 2),
    ]


def test_extracts_receivable_carrying_amount_summary_candidates():
    table = ReportTable(
        8,
        [
            ["", "총장부금액", "손상차손누계액", "장부금액 합계"],
            ["유동매출채권", "1,000", "(100)", "900"],
            ["단기미수금", "200", "-", "200"],
            ["단기대여금", "300", "-", "300"],
        ],
        "8. 매출채권 및 기타채권",
        SourceLocation("note:8", 0, 8),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="8",
        title="매출채권 및 기타채권",
        table=table,
        layout=LayoutClassification(
            "receivable_carrying_amount_summary",
            0.85,
            ("receivable carrying amount columns",),
            "note:8/table:8",
        ),
        orientation=TableOrientation("column_oriented", 0.9, ("measure labels in columns",)),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("trade_receivables", "receivable_carrying_component", 1_000_000, 1, 1),
        ("trade_receivables", "receivable_carrying_component", -100_000, 1, 2),
        ("trade_receivables", "ending", 900_000, 1, 3),
        ("short_term_other_receivables", "receivable_carrying_component", 200_000, 2, 1),
        ("short_term_other_receivables", "ending", 200_000, 2, 3),
        ("short_term_loans", "receivable_carrying_component", 300_000, 3, 1),
        ("short_term_loans", "ending", 300_000, 3, 3),
    ]


def test_extracts_receivable_carrying_loss_allowance_formula_candidates():
    table = ReportTable(
        27,
        [
            ["", "총장부금액", "차감: 손실충당금", "장부금액 합계"],
            ["유동매출채권", "1,434,687", "(4,647)", "1,430,040"],
            ["비유동매출채권", "468", "(428)", "40"],
        ],
        "5. 매출채권, 대여금 및 기타채권",
        SourceLocation("note:5", 0, 27),
        unit_multiplier=1_000_000,
    )

    candidates = extract_verification_candidates(
        note_no="5",
        title="매출채권, 대여금 및 기타채권",
        table=table,
        layout=LayoutClassification(
            "receivable_carrying_amount_summary",
            0.85,
            ("receivable carrying amount columns",),
            "note:5/table:27",
        ),
        orientation=TableOrientation("column_oriented", 0.9, ("measure labels in columns",)),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("trade_receivables", "receivable_carrying_component", 1_434_687_000_000, 1, 1),
        ("trade_receivables", "receivable_carrying_component", -4_647_000_000, 1, 2),
        ("trade_receivables", "ending", 1_430_040_000_000, 1, 3),
        ("trade_receivables", "receivable_carrying_component", 468_000_000, 2, 1),
        ("trade_receivables", "receivable_carrying_component", -428_000_000, 2, 2),
        ("trade_receivables", "ending", 40_000_000, 2, 3),
    ]


def test_extracts_receivable_carrying_two_label_column_candidates():
    table = ReportTable(
        29,
        [
            ["", "", "총장부금액", "차감: 손실충당금", "장부금액 합계"],
            ["유동", "유동", "104,390", "(6,206)", "98,184"],
            ["유동", "미수금", "104,390", "(6,206)", "98,184"],
            ["유동", "대여금", "0", "0", "0"],
            ["기타 비유동채권", "장기미수금", "33,214", "0", "33,214"],
            ["기타 비유동채권", "보증금", "16,278", "0", "16,278"],
        ],
        "5. 매출채권, 대여금 및 기타채권",
        SourceLocation("note:5", 0, 29),
        unit_multiplier=1_000_000,
    )

    candidates = extract_verification_candidates(
        note_no="5",
        title="매출채권, 대여금 및 기타채권",
        table=table,
        layout=LayoutClassification(
            "receivable_carrying_amount_summary",
            0.85,
            ("receivable carrying amount columns",),
            "note:5/table:29",
        ),
        orientation=TableOrientation("column_oriented", 0.9, ("measure labels in columns",)),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("short_term_other_receivables", "receivable_carrying_component", 104_390_000_000, 2, 2),
        ("short_term_other_receivables", "receivable_carrying_component", -6_206_000_000, 2, 3),
        ("short_term_other_receivables", "ending", 98_184_000_000, 2, 4),
        ("short_term_loans", "receivable_carrying_component", 0, 3, 2),
        ("short_term_loans", "ending", 0, 3, 4),
        ("long_term_other_receivables", "receivable_carrying_component", 33_214_000_000, 4, 2),
        ("long_term_other_receivables", "ending", 33_214_000_000, 4, 4),
        ("long_term_deposits", "receivable_carrying_component", 16_278_000_000, 5, 2),
        ("long_term_deposits", "ending", 16_278_000_000, 5, 4),
    ]


def test_extracts_receivable_present_value_carrying_summary_formula_candidates():
    table = ReportTable(
        8,
        [
            ["", "총장부금액", "차감: 현재가치할인차금", "손실충당금", "장부금액 합계"],
            ["유동매출채권", "1,000", "0", "(100)", "900"],
            ["장기미수금", "2,000", "(300)", "0", "1,700"],
            ["매출채권 및 기타유동채권", "", "", "", "900"],
        ],
        "8. 매출채권 및 기타채권",
        SourceLocation("note:8", 0, 8),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="8",
        title="매출채권 및 기타채권",
        table=table,
        layout=LayoutClassification(
            "receivable_present_value_carrying_summary",
            0.85,
            ("receivable present value discount columns",),
            "note:8/table:8",
        ),
        orientation=TableOrientation("column_oriented", 0.9, ("measure labels in columns",)),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("trade_receivables", "receivable_carrying_component", 1_000_000, 1, 1),
        ("trade_receivables", "receivable_carrying_component", -100_000, 1, 3),
        ("trade_receivables", "ending", 900_000, 1, 4),
        ("long_term_other_receivables", "receivable_carrying_component", 2_000_000, 2, 1),
        ("long_term_other_receivables", "receivable_carrying_component", -300_000, 2, 2),
        ("long_term_other_receivables", "ending", 1_700_000, 2, 4),
        ("trade_receivables", "ending", 900_000, 3, 4),
    ]


def test_extracts_receivable_present_value_carrying_summary_two_label_rows():
    table = ReportTable(
        8,
        [
            ["", "", "총장부금액", "손상차손누계액", "현재가치할인차금", "장부금액 합계"],
            ["매출채권 및 기타유동채권", "유동매출채권", "1,000", "(100)", "0", "900"],
            ["매출채권 및 기타유동채권", "단기미수금", "500", "0", "(20)", "480"],
            ["매출채권 및 기타유동채권", "소계", "1,500", "(100)", "(20)", "1,380"],
        ],
        "8. 매출채권 및 기타채권",
        SourceLocation("note:8", 0, 8),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="8",
        title="매출채권 및 기타채권",
        table=table,
        layout=LayoutClassification(
            "receivable_present_value_carrying_summary",
            0.85,
            ("receivable present value discount columns",),
            "note:8/table:8",
        ),
        orientation=TableOrientation("column_oriented", 0.9, ("measure labels in columns",)),
    )

    assert [
        (candidate.account_key, candidate.label, candidate.role, candidate.amount)
        for candidate in candidates
        if candidate.role == "ending"
    ] == [
        ("trade_receivables", "유동매출채권", "ending", 900_000),
        ("short_term_other_receivables", "단기미수금", "ending", 480_000),
        ("trade_receivables", "매출채권 및 기타유동채권", "ending", 1_380_000),
    ]


def test_extracts_loss_allowance_rollforward_candidates_from_account_header_row():
    table = ReportTable(
        9,
        [
            ["", "금융자산, 분류", "금융자산, 분류"],
            ["", "매출채권", "미수금"],
            ["", "장부금액", "장부금액"],
            ["", "손상차손누계액", "손상차손누계액"],
            ["기초 손실충당금", "100", "20"],
            ["기대신용손실", "30", "5"],
            ["환입액", "(10)", "(3)"],
            ["제각", "(40)", "0"],
            ["기말 손실충당금", "80", "22"],
        ],
        "8. 매출채권 및 기타채권",
        SourceLocation("note:8", 0, 9),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="8",
        title="매출채권 및 기타채권",
        table=table,
        layout=LayoutClassification(
            "loss_allowance_rollforward",
            0.85,
            ("loss allowance movement labels in rows",),
            "note:8/table:9",
        ),
        orientation=TableOrientation("row_oriented", 0.85, ("loss allowance movement labels in rows",)),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("trade_receivables_loss_allowance", "beginning", 100_000, 4, 1),
        ("other_receivables_loss_allowance", "beginning", 20_000, 4, 2),
        ("trade_receivables_loss_allowance", "signed_movement", 30_000, 5, 1),
        ("other_receivables_loss_allowance", "signed_movement", 5_000, 5, 2),
        ("trade_receivables_loss_allowance", "signed_movement", -10_000, 6, 1),
        ("other_receivables_loss_allowance", "signed_movement", -3_000, 6, 2),
        ("trade_receivables_loss_allowance", "signed_movement", -40_000, 7, 1),
        ("other_receivables_loss_allowance", "signed_movement", 0, 7, 2),
        ("trade_receivables_loss_allowance", "ending", 80_000, 8, 1),
        ("other_receivables_loss_allowance", "ending", 22_000, 8, 2),
    ]


def test_extracts_loss_allowance_rollforward_candidates_from_stacked_financial_asset_rows():
    table = ReportTable(
        22,
        [
            ["", "금융상품"],
            ["", "매출채권"],
            ["", "장부금액"],
            ["", "손상차손누계액"],
            ["기초금융자산", "(205,922)"],
            ["기대신용손실전(환)입, 금융자산", "66,473"],
            ["제거에 따른 감소, 금융자산", "2,866"],
            ["외화환산에 따른 증가(감소), 금융자산", "(105)"],
            ["기타 변동에 따른 증가(감소), 금융자산", "0"],
            ["기말금융자산", "(136,687)"],
        ],
        "5. 매출채권 및 기타채권",
        SourceLocation("note:5", 0, 22),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="5",
        title="매출채권 및 기타채권",
        table=table,
        layout=LayoutClassification(
            "loss_allowance_rollforward",
            0.85,
            ("loss allowance movement labels in rows",),
            "note:5/table:22",
        ),
        orientation=TableOrientation("row_oriented", 0.85, ("loss allowance movement labels in rows",)),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("trade_receivables_loss_allowance", "beginning", -205_922_000, 4, 1),
        ("trade_receivables_loss_allowance", "signed_movement", 66_473_000, 5, 1),
        ("trade_receivables_loss_allowance", "signed_movement", 2_866_000, 6, 1),
        ("trade_receivables_loss_allowance", "signed_movement", -105_000, 7, 1),
        ("trade_receivables_loss_allowance", "signed_movement", 0, 8, 1),
        ("trade_receivables_loss_allowance", "ending", -136_687_000, 9, 1),
    ]


def test_does_not_extract_loss_allowance_candidates_without_allowance_measure_row():
    table = ReportTable(
        22,
        [
            ["", "금융상품"],
            ["", "매출채권"],
            ["", "장부금액"],
            ["기초금융자산", "1,000"],
            ["기대신용손실전(환)입, 금융자산", "10"],
            ["기말금융자산", "1,010"],
        ],
        "5. 매출채권 및 기타채권",
        SourceLocation("note:5", 0, 22),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="5",
        title="매출채권 및 기타채권",
        table=table,
        layout=LayoutClassification(
            "loss_allowance_rollforward",
            0.85,
            ("loss allowance movement labels in rows",),
            "note:5/table:22",
        ),
        orientation=TableOrientation("row_oriented", 0.85, ("loss allowance movement labels in rows",)),
    )

    assert candidates == []


def test_extracts_receivable_aging_summary_total_row_candidates():
    table = ReportTable(
        10,
        [
            ["", "", "매출채권", "단기미수금", "단기대여금", "장기대여금", "장기보증금"],
            ["연체상태", "미연체채권", "100", "20", "30", "40", "50"],
            ["연체상태", "손상채권", "10", "2", "0", "0", "0"],
            ["연체상태 합계", "연체상태 합계", "110", "22", "30", "40", "50"],
        ],
        "8. 매출채권 및 기타채권",
        SourceLocation("note:8", 0, 10),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="8",
        title="매출채권 및 기타채권",
        table=table,
        layout=LayoutClassification(
            "receivable_aging_status_summary",
            0.85,
            ("aging status rows include total",),
            "note:8/table:10",
        ),
        orientation=TableOrientation("column_oriented", 0.85, ("receivable account labels in columns",)),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("trade_receivables", "ending", 110_000, 3, 2),
        ("short_term_other_receivables", "ending", 22_000, 3, 3),
        ("short_term_loans", "ending", 30_000, 3, 4),
        ("long_term_loans", "ending", 40_000, 3, 5),
        ("long_term_deposits", "ending", 50_000, 3, 6),
    ]


def test_extracts_receivable_loss_allowance_aging_bucket_candidates():
    table = ReportTable(
        50,
        [
            ["구 분", "6개월 이내 연체 및 정상", "6개월 초과 1년 이내 연체", "1년 초과 연체", "합 계"],
            ["총 장부금액", "194,209,849", "8,119,664", "29,657", "202,359,170"],
            ["손실충당금", "1,158", "69,660", "29,657", "100,475"],
            ["기대 손실률", "0.00", "0.86", "100.00", "0.05"],
        ],
        "8. 매출채권",
        SourceLocation("note:8", 0, 50),
        unit_multiplier=1,
    )

    candidates = extract_verification_candidates(
        note_no="8",
        title="매출채권",
        table=table,
        layout=LayoutClassification(
            "receivable_loss_allowance_aging_summary",
            0.85,
            ("receivable aging bucket columns",),
            "note:8/table:50",
        ),
        orientation=TableOrientation("row_oriented", 0.9, ("amount rows with aging bucket columns",)),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.label, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("trade_receivables_gross_aging", "aging_bucket_component", "총 장부금액 6개월 이내 연체 및 정상", 194_209_849, 1, 1),
        ("trade_receivables_gross_aging", "aging_bucket_component", "총 장부금액 6개월 초과 1년 이내 연체", 8_119_664, 1, 2),
        ("trade_receivables_gross_aging", "aging_bucket_component", "총 장부금액 1년 초과 연체", 29_657, 1, 3),
        ("trade_receivables_gross_aging", "aging_bucket_total", "총 장부금액 합 계", 202_359_170, 1, 4),
        ("trade_receivables_loss_allowance_aging", "aging_bucket_component", "손실충당금 6개월 이내 연체 및 정상", 1_158, 2, 1),
        ("trade_receivables_loss_allowance_aging", "aging_bucket_component", "손실충당금 6개월 초과 1년 이내 연체", 69_660, 2, 2),
        ("trade_receivables_loss_allowance_aging", "aging_bucket_component", "손실충당금 1년 초과 연체", 29_657, 2, 3),
        ("trade_receivables_loss_allowance_aging", "aging_bucket_total", "손실충당금 합 계", 100_475, 2, 4),
    ]


def test_extracts_inventory_carrying_amount_summary_total_candidate():
    table = ReportTable(
        11,
        [
            ["", "총장부금액"],
            ["유동제품", "0"],
            ["원재료 및 저장품", "894,025"],
            ["미착품", "0"],
            ["기타재고", "256,610"],
            ["합계", "1,150,635"],
        ],
        "10. 재고자산",
        SourceLocation("note:10", 0, 11),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="10",
        title="재고자산",
        table=table,
        layout=LayoutClassification(
            "inventory_carrying_amount_summary",
            0.85,
            ("inventory carrying amount column",),
            "note:10/table:11",
        ),
        orientation=TableOrientation("column_oriented", 0.85, ("inventory carrying amount column",)),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [("inventories", "ending", 1_150_635_000, 5, 1)]


def test_extracts_inventory_carrying_amount_summary_inventory_total_row_candidate():
    table = ReportTable(
        28,
        [
            ["", "총장부금액", "재고자산 평가충당금", "장부금액 합계"],
            ["상품", "10,000", "(100)", "9,900"],
            ["제품", "20,000", "(200)", "19,800"],
            ["반제품", "5,000", "0", "5,000"],
            ["재공품", "7,000", "(50)", "6,950"],
            ["원재료", "30,000", "(300)", "29,700"],
            ["저장품", "1,000", "0", "1,000"],
            ["미착품", "100", "0", "100"],
            ["재고자산", "73,100", "(650)", "72,450"],
        ],
        "6. 재고자산",
        SourceLocation("note:6", 0, 28),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="6",
        title="재고자산",
        table=table,
        layout=LayoutClassification(
            "inventory_carrying_amount_summary",
            0.85,
            ("inventory carrying amount column",),
            "note:6/table:28",
        ),
        orientation=TableOrientation("column_oriented", 0.85, ("inventory carrying amount column",)),
    )

    extracted = [
        (candidate.account_key, candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ]
    assert ("inventories", "ending", 72_450_000, 8, 3) in extracted
    assert ("inventory_goods", "inventory_carrying_component", 10_000_000, 1, 1) in extracted


def test_extracts_inventory_carrying_amount_summary_formula_candidates():
    table = ReportTable(
        8,
        [
            ["", "총장부금액", "재고자산 평가충당금", "장부금액 합계"],
            ["유동상품", "1,000", "(100)", "900"],
            ["유동제품", "2,000", "0", "2,000"],
            ["유동재고자산", "3,000", "(100)", "2,900"],
            ["재고자산 순감액(환입)", "", "", "50"],
        ],
        "8. 재고자산",
        SourceLocation("note:8", 0, 8),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="8",
        title="재고자산",
        table=table,
        layout=LayoutClassification(
            "inventory_carrying_amount_summary",
            0.85,
            ("inventory carrying amount column",),
            "note:8/table:8",
        ),
        orientation=TableOrientation("column_oriented", 0.9, ("inventory carrying amount column",)),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("inventory_goods", "inventory_carrying_component", 1_000_000, 1, 1),
        ("inventory_goods", "inventory_carrying_component", -100_000, 1, 2),
        ("inventory_goods", "ending", 900_000, 1, 3),
        ("inventory_finished_goods", "inventory_carrying_component", 2_000_000, 2, 1),
        ("inventory_finished_goods", "ending", 2_000_000, 2, 3),
        ("inventories", "inventory_carrying_component", 3_000_000, 3, 1),
        ("inventories", "inventory_carrying_component", -100_000, 3, 2),
        ("inventories", "ending", 2_900_000, 3, 3),
    ]


def test_extracts_inventory_carrying_amount_summary_two_label_rows():
    table = ReportTable(
        8,
        [
            ["", "", "취득원가", "충당금", "장부금액 합계"],
            ["재고자산 합계", "제품 및 상품", "1,000", "(100)", "900"],
            ["재고자산 합계", "재공품", "2,000", "0", "2,000"],
        ],
        "8. 재고자산",
        SourceLocation("note:8", 0, 8),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="8",
        title="재고자산",
        table=table,
        layout=LayoutClassification(
            "inventory_carrying_amount_summary",
            0.85,
            ("inventory carrying amount column",),
            "note:8/table:8",
        ),
        orientation=TableOrientation("column_oriented", 0.9, ("inventory carrying amount column",)),
    )

    assert [
        (candidate.account_key, candidate.label, candidate.role, candidate.amount)
        for candidate in candidates
    ] == [
        ("inventory_goods", "제품 및 상품 취득원가", "inventory_carrying_component", 1_000_000),
        ("inventory_goods", "제품 및 상품 충당금", "inventory_carrying_component", -100_000),
        ("inventory_goods", "제품 및 상품", "ending", 900_000),
        ("inventory_work_in_process", "재공품 취득원가", "inventory_carrying_component", 2_000_000),
        ("inventory_work_in_process", "재공품", "ending", 2_000_000),
    ]


def test_extracts_functional_expense_allocation_total_candidate():
    table = ReportTable(
        12,
        [
            ["", "판매비와 일반관리비", "매출원가", "기능별 항목 합계"],
            ["감가상각비, 유형자산", "23,643", "3,642", "27,285"],
        ],
        "12. 유형자산",
        SourceLocation("note:12", 0, 12),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="12",
        title="유형자산",
        table=table,
        layout=LayoutClassification(
            "functional_expense_allocation",
            0.85,
            ("functional expense columns",),
            "note:12/table:12",
        ),
        orientation=TableOrientation("column_oriented", 0.85, ("functional expense columns",)),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [("property_plant_equipment", "expense_allocation_total", 27_285_000, 1, 3)]


def test_extracts_functional_expense_research_allocation_formula_candidates():
    table = ReportTable(
        75,
        [
            ["", "매출원가", "판매비와 일반관리비", "기능별 항목 합계"],
            ["연구와 개발 비용", "16,738,912", "1,284,890", "18,023,802"],
        ],
        "10. 무형자산",
        SourceLocation("note:10", 0, 75),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="10",
        title="무형자산",
        table=table,
        layout=LayoutClassification(
            "functional_expense_research_allocation",
            0.85,
            ("research and development expense row",),
            "note:10/table:75",
        ),
        orientation=TableOrientation("column_oriented", 0.85, ("functional expense columns",)),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.label, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("research_development_expense", "expense_component", "매출원가", 16_738_912_000, 1, 1),
        ("research_development_expense", "expense_component", "판매비와 일반관리비", 1_284_890_000, 1, 2),
        ("research_development_expense", "expense_total", "기능별 항목 합계", 18_023_802_000, 1, 3),
    ]


def test_extracts_functional_expense_single_row_allocation_candidate():
    table = ReportTable(
        13,
        [
            ["", "", "감가상각비, 유형자산"],
            ["기능별 항목", "영업비용", "580,870"],
        ],
        "10. 유형자산(별도)",
        SourceLocation("note:10", 0, 13),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="10",
        title="유형자산(별도)",
        table=table,
        layout=LayoutClassification(
            "functional_expense_single_row_allocation",
            0.85,
            ("single functional expense row",),
            "note:10/table:13",
        ),
        orientation=TableOrientation("column_oriented", 0.85, ("single functional expense row",)),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.label, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("property_plant_equipment", "expense_allocation_total", "영업비용 감가상각비, 유형자산", 580_870_000, 1, 2)
    ]


def test_extracts_single_row_amortization_allocation_candidate():
    table = ReportTable(
        14,
        [
            ["", "", "무형자산상각비"],
            ["기능별 항목", "영업비용", "1,031,602"],
        ],
        "11. 무형자산(별도)",
        SourceLocation("note:11", 0, 14),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="11",
        title="무형자산(별도)",
        table=table,
        layout=LayoutClassification(
            "functional_expense_single_row_allocation",
            0.85,
            ("single functional expense row",),
            "note:11/table:14",
        ),
        orientation=TableOrientation("column_oriented", 0.85, ("single functional expense row",)),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.label, candidate.amount)
        for candidate in candidates
    ] == [
        ("intangible_assets", "expense_allocation_total", "영업비용 무형자산상각비", 1_031_602_000)
    ]


def test_extracts_employee_benefit_expense_allocation_candidates():
    table = ReportTable(
        62,
        [
            ["구분", "당기", "전기"],
            ["판관비에 포함된 금액", "2,548,827", "2,723,163"],
            ["매출원가에 포함된 금액", "641,676", "628,174"],
            ["합계", "3,190,503", "3,351,337"],
        ],
        "16. 퇴직급여제도",
        SourceLocation("note:16", 0, 62),
        unit_multiplier=1,
    )

    candidates = extract_verification_candidates(
        note_no="16",
        title="퇴직급여제도",
        table=table,
        layout=LayoutClassification(
            "employee_benefit_expense_allocation",
            0.85,
            ("employee benefit expense allocation rows",),
            "note:16/table:62",
        ),
        orientation=TableOrientation("period_oriented", 0.85, ("period columns",)),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.label, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("employee_benefit_expense:당기", "employee_benefit_expense_component", "판관비에 포함된 금액 당기", 2_548_827, 1, 1),
        ("employee_benefit_expense:당기", "employee_benefit_expense_component", "매출원가에 포함된 금액 당기", 641_676, 2, 1),
        ("employee_benefit_expense:당기", "employee_benefit_expense_total", "합계 당기", 3_190_503, 3, 1),
        ("employee_benefit_expense:전기", "employee_benefit_expense_component", "판관비에 포함된 금액 전기", 2_723_163, 1, 2),
        ("employee_benefit_expense:전기", "employee_benefit_expense_component", "매출원가에 포함된 금액 전기", 628_174, 2, 2),
        ("employee_benefit_expense:전기", "employee_benefit_expense_total", "합계 전기", 3_351_337, 3, 2),
    ]


def test_extracts_selling_admin_expense_summary_candidates():
    table = ReportTable(
        13,
        [
            ["", "금액"],
            ["급여, 판관비", "100"],
            ["감가상각비, 판관비", "30"],
            ["기타판매비와관리비", "20"],
            ["합계", "150"],
        ],
        "26. 판매비와 관리비",
        SourceLocation("note:26", 0, 13),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="26",
        title="판매비와 관리비",
        table=table,
        layout=LayoutClassification(
            "selling_admin_expense_summary",
            0.85,
            ("expense amount column",),
            "note:26/table:13",
        ),
        orientation=TableOrientation("column_oriented", 0.85, ("expense amount column",)),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.label, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("selling_general_admin", "expense_component", "급여, 판관비", 100_000, 1, 1),
        ("selling_general_admin", "expense_component", "감가상각비, 판관비", 30_000, 2, 1),
        ("selling_general_admin", "expense_component", "기타판매비와관리비", 20_000, 3, 1),
        ("selling_general_admin", "expense_total", "합계", 150_000, 4, 1),
    ]


def test_extracts_operating_expense_summary_candidates():
    table = ReportTable(
        14,
        [
            ["", "금액"],
            ["가스매출원가", "18,228,713"],
            ["금융매출원가", "27,734,813"],
            ["급여, 판관비", "3,409,843"],
            ["감가상각비, 판관비", "1,290,295"],
            ["기타판매비와관리비", "437,513"],
            ["합계", "51,101,178"],
        ],
        "22. 영업비용(별도)",
        SourceLocation("note:22", 0, 14),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="22",
        title="영업비용(별도)",
        table=table,
        layout=LayoutClassification(
            "operating_expense_summary",
            0.85,
            ("operating expense amount column",),
            "note:22/table:14",
        ),
        orientation=TableOrientation("column_oriented", 0.85, ("expense amount column",)),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.label, candidate.amount)
        for candidate in candidates
    ] == [
        ("operating_expenses", "expense_component", "가스매출원가", 18_228_713_000),
        ("operating_expenses", "expense_component", "금융매출원가", 27_734_813_000),
        ("operating_expenses", "expense_component", "급여, 판관비", 3_409_843_000),
        ("operating_expenses", "expense_component", "감가상각비, 판관비", 1_290_295_000),
        ("operating_expenses", "expense_component", "기타판매비와관리비", 437_513_000),
        ("operating_expenses", "expense_total", "합계", 51_101_178_000),
    ]


def test_extracts_debt_instrument_detail_split_candidates():
    table = ReportTable(
        13,
        [
            ["", "차입금명칭", "차입금명칭", "차입금명칭 합계"],
            ["만기일", "", "2029-06-15", ""],
            ["연이자율", "0.0175", "", ""],
            ["차입금", "", "6,294,460", "6,294,460"],
            ["1년이내 만기도래분", "", "", "(1,223,560)"],
            ["비유동성 차입금(사채 제외)", "", "", "5,070,900"],
        ],
        "15. 차입금 및 사채",
        SourceLocation("note:15", 0, 13),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="15",
        title="차입금 및 사채",
        table=table,
        layout=LayoutClassification(
            "debt_instrument_detail_summary",
            0.85,
            ("debt instrument total column",),
            "note:15/table:13",
        ),
        orientation=TableOrientation("row_oriented", 0.85, ("debt detail rows",)),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("borrowings", "debt_total", 6_294_460_000, 3, 3),
        ("borrowings", "current_portion", -1_223_560_000, 4, 3),
        ("borrowings", "ending", 5_070_900_000, 5, 3),
    ]


def test_extracts_bond_detail_component_and_split_candidates():
    table = ReportTable(
        14,
        [
            ["", "차입금명칭", "차입금명칭", "차입금명칭"],
            ["", "무기명식 이권부 무보증사채", "무기명식 이권부 무보증사채", "무기명식 이권부 무보증사채"],
            ["", "범위", "범위", "범위 합계"],
            ["만기일", "", "", "2025.02.18 ~ 2027.03.15"],
            ["연이자율", "0.0314", "0.0409", ""],
            ["명목금액", "", "", "160,000,000"],
            ["사채할인발행차금", "", "", "(227,737)"],
            ["소계", "", "", "159,772,263"],
            ["1년이내 만기도래분", "", "", "(50,000,000)"],
            ["합계", "", "", "109,772,263"],
        ],
        "15. 차입금 및 사채",
        SourceLocation("note:15", 0, 14),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="15",
        title="차입금 및 사채",
        table=table,
        layout=LayoutClassification(
            "debt_instrument_detail_summary",
            0.85,
            ("debt instrument total column",),
            "note:15/table:14",
        ),
        orientation=TableOrientation("row_oriented", 0.85, ("debt detail rows",)),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("bonds", "face_amount", 160_000_000_000, 5, 3),
        ("bonds", "debt_discount", -227_737_000, 6, 3),
        ("bonds", "debt_total", 159_772_263_000, 7, 3),
        ("bonds", "current_portion", -50_000_000_000, 8, 3),
        ("bonds", "ending", 109_772_263_000, 9, 3),
    ]


def test_extracts_bond_detail_component_column_candidates():
    table = ReportTable(
        104,
        [
            ["", "", "", "발행일", "만기일", "차입금, 이자율", "명목금액", "차감: 유동성사채", "차감: 사채할인발행차금", "비유동 사채의 비유동성 부분"],
            ["차입금명칭", "사채", "제82-2회공모사채", "2019-04-16", "2024-04-16", "0.0000", "0", "", "", ""],
            ["차입금명칭", "사채", "제83-2회공모사채", "2020-02-20", "2025-02-20", "0.0198", "50,000", "", "", ""],
            ["차입금명칭", "사채", "제85-2회공모사채", "2021-04-12", "2026-04-12", "0.0196", "50,000", "", "", ""],
            ["차입금명칭 합계", "차입금명칭 합계", "차입금명칭 합계", "", "", "", "100,000", "(50,000)", "(68)", "49,932"],
        ],
        "15. 차입금 및 사채",
        SourceLocation("note:15", 0, 104),
        unit_multiplier=1_000_000,
    )

    candidates = extract_verification_candidates(
        note_no="15",
        title="차입금 및 사채",
        table=table,
        layout=LayoutClassification(
            "debt_instrument_detail_summary",
            0.85,
            ("debt component columns",),
            "note:15/table:104",
        ),
        orientation=TableOrientation("row_oriented", 0.85, ("debt component columns",)),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("bonds", "face_amount", 100_000_000_000, 4, 6),
        ("bonds", "current_portion", -50_000_000_000, 4, 7),
        ("bonds", "debt_discount", -68_000_000, 4, 8),
        ("bonds", "ending", 49_932_000_000, 4, 9),
    ]


def test_extracts_borrowing_detail_present_value_and_current_split_candidates():
    table = ReportTable(
        135,
        [
            ["", "차입금명칭", "차입금명칭", "차입금명칭 합계"],
            ["차입금, 만기", "", "2032-12-20", ""],
            ["차입금, 이자율", "0.0198", "0.0492", ""],
            ["명목금액", "", "270,060,586", "466,697,117"],
            ["현재가치할인차금", "", "", "(3,339,418)"],
            [
                "유동 금융기관 차입금 및 비유동 금융기관 차입금(사채 제외)의 유동성 대체 부분",
                "",
                "",
                "(58,973,133)",
            ],
            [
                "비유동 금융기관 차입금(사채 제외)의 비유동성 대체 부분",
                "",
                "",
                "404,538,406",
            ],
        ],
        "20. 차입금",
        SourceLocation("note:20", 0, 135),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="20",
        title="차입금",
        table=table,
        layout=LayoutClassification(
            "debt_instrument_detail_summary",
            0.85,
            ("debt instrument total column",),
            "note:20/table:135",
        ),
        orientation=TableOrientation("row_oriented", 0.85, ("debt detail rows",)),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("borrowings", "face_amount", 466_697_117_000, 3, 3),
        ("borrowings", "debt_discount", -3_339_418_000, 4, 3),
        ("borrowings", "current_portion", -58_973_133_000, 5, 3),
        ("borrowings", "ending", 404_538_406_000, 6, 3),
    ]


def test_extracts_provision_rollforward_signed_candidates():
    table = ReportTable(
        15,
        [
            ["", "", "기초", "전입", "연중 사용액", "연결범위변동", "매각예정분류", "기말"],
            ["기타충당부채", "하자보수충당부채", "887,348", "247,168", "(194,215)", "(940,301)", "0", "0"],
        ],
        "17. 충당부채",
        SourceLocation("note:17", 0, 15),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="17",
        title="충당부채",
        table=table,
        layout=LayoutClassification(
            "provision_rollforward",
            0.85,
            ("provision movement columns",),
            "note:17/table:15",
        ),
        orientation=TableOrientation("mixed", 0.85, ("provision movement columns",)),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("provisions", "beginning", 887_348_000, 1, 2),
        ("provisions", "signed_movement", 247_168_000, 1, 3),
        ("provisions", "signed_movement", -194_215_000, 1, 4),
        ("provisions", "signed_movement", -940_301_000, 1, 5),
        ("provisions", "signed_movement", 0, 1, 6),
        ("provisions", "ending", 0, 1, 7),
    ]


def test_extracts_row_oriented_provision_rollforward_candidates_by_account_column():
    table = ReportTable(
        19,
        [
            ["", "", "사후처리, 복구, 정화 비용을 위한 충당부채", "기타장기종업원급여부채", "기타충당부채 합계"],
            ["기초 기타충당부채", "기초 기타충당부채", "778,101", "1,697,795", "2,646,682"],
            ["기타충당부채의 변동에 대한 조정", "기타충당부채의 변동에 대한 조정", "", "", ""],
            ["기타충당부채의 변동에 대한 조정", "당기에 추가된 충당부채 합계, 기타충당부채", "279,165", "312,625", "626,071"],
            ["기타충당부채의 변동에 대한 조정", "사용된 충당부채, 기타충당부채", "0", "(150,000)", "(194,728)"],
            ["기말 기타충당부채", "기말 기타충당부채", "1,057,266", "1,860,420", "3,071,025"],
        ],
        "18. 충당부채",
        SourceLocation("note:18", 0, 19),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="18",
        title="충당부채",
        table=table,
        layout=LayoutClassification(
            "provision_rollforward",
            0.85,
            ("provision account columns",),
            "note:18/table:19",
        ),
        orientation=TableOrientation("row_oriented", 0.85, ("movement labels in rows",)),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("restoration_provision", "beginning", 778_101_000, 1, 2),
        ("long_term_employee_benefit_provision", "beginning", 1_697_795_000, 1, 3),
        ("provisions_total", "beginning", 2_646_682_000, 1, 4),
        ("restoration_provision", "signed_movement", 279_165_000, 3, 2),
        ("long_term_employee_benefit_provision", "signed_movement", 312_625_000, 3, 3),
        ("provisions_total", "signed_movement", 626_071_000, 3, 4),
        ("restoration_provision", "signed_movement", 0, 4, 2),
        ("long_term_employee_benefit_provision", "signed_movement", -150_000_000, 4, 3),
        ("provisions_total", "signed_movement", -194_728_000, 4, 4),
        ("restoration_provision", "ending", 1_057_266_000, 5, 2),
        ("long_term_employee_benefit_provision", "ending", 1_860_420_000, 5, 3),
        ("provisions_total", "ending", 3_071_025_000, 5, 4),
    ]


def test_extracts_provision_current_noncurrent_summary_candidates():
    table = ReportTable(
        87,
        [
            ["", "", "유동", "비유동"],
            ["복구충당부채", "복구충당부채", "100", "1,000"],
            ["판매보증충당부채", "판매보증충당부채", "30", "2,000"],
            ["기타장기종업원급여부채", "기타장기종업원급여부채", "12", "3,000"],
            ["기타충당부채 합계", "기타충당부채 합계", "142", "6,000"],
        ],
        "17. 충당부채",
        SourceLocation("note:17", 0, 87),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="17",
        title="충당부채",
        table=table,
        layout=LayoutClassification(
            "provision_current_noncurrent_summary",
            0.85,
            ("provision current and non-current columns", "provision total row"),
            "note:17/table:87",
        ),
        orientation=TableOrientation(
            "column_oriented",
            0.85,
            ("provision current and non-current columns", "provision total row"),
        ),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.label, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("current_provisions", "provision_column_component", "복구충당부채 유동", 100_000, 1, 2),
        ("current_provisions", "provision_column_component", "판매보증충당부채 유동", 30_000, 2, 2),
        ("current_provisions", "provision_column_component", "기타장기종업원급여부채 유동", 12_000, 3, 2),
        ("current_provisions", "provision_column_total", "기타충당부채 합계 유동", 142_000, 4, 2),
        ("noncurrent_provisions", "provision_column_component", "복구충당부채 비유동", 1_000_000, 1, 3),
        ("noncurrent_provisions", "provision_column_component", "판매보증충당부채 비유동", 2_000_000, 2, 3),
        ("noncurrent_provisions", "provision_column_component", "기타장기종업원급여부채 비유동", 3_000_000, 3, 3),
        ("noncurrent_provisions", "provision_column_total", "기타충당부채 합계 비유동", 6_000_000, 4, 3),
    ]


def test_extracts_defined_benefit_rollforward_candidates_by_account_column():
    table = ReportTable(
        16,
        [
            ["", "", "확정급여채무의 현재가치", "사외적립자산"],
            ["기초금액", "기초금액", "2,898,415", "3,795,757"],
            ["당기근무원가", "당기근무원가", "481,755", "0"],
            ["이자비용(수익)", "이자비용(수익)", "149,452", "(197,702)"],
            ["재측정요소:", "재측정요소:", "", ""],
            ["재측정요소:", "경험조정효과", "(248,861)", "0"],
            ["재측정요소:", "재무적 가정 변경 효과", "1,259,954", "0"],
            ["재측정요소:", "이자수익과 실제수익의 차이", "0", "(55,973)"],
            ["재측정요소:", "총 재측정손익", "1,011,093", "(55,973)"],
            ["납입액", "납입액", "0", "0"],
            ["전입(전출)액", "전입(전출)액", "(191,125)", "(191,125)"],
            ["중간/중도인출로 인한 지급", "중간/중도인출로 인한 지급", "(18,579)", "(18,579)"],
            ["퇴직급여지급액", "퇴직급여지급액", "(95,001)", "(95,001)"],
            ["기말금액", "기말금액", "4,236,010", "3,632,781"],
        ],
        "13. 순확정급여부채(자산)(별도)",
        SourceLocation("note:13", 0, 16),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="13",
        title="순확정급여부채(자산)(별도)",
        table=table,
        layout=LayoutClassification(
            "defined_benefit_rollforward",
            0.85,
            ("defined benefit account columns",),
            "note:13/table:16",
        ),
        orientation=TableOrientation("mixed", 0.85, ("defined benefit account columns",)),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("defined_benefit_obligation", "beginning", 2_898_415_000, 1, 2),
        ("plan_assets", "beginning", 3_795_757_000, 1, 3),
        ("defined_benefit_obligation", "signed_movement", 481_755_000, 2, 2),
        ("plan_assets", "signed_movement", 0, 2, 3),
        ("defined_benefit_obligation", "signed_movement", 149_452_000, 3, 2),
        ("plan_assets", "signed_movement", -197_702_000, 3, 3),
        ("defined_benefit_obligation", "signed_movement", -248_861_000, 5, 2),
        ("plan_assets", "signed_movement", 0, 5, 3),
        ("defined_benefit_obligation", "signed_movement", 1_259_954_000, 6, 2),
        ("plan_assets", "signed_movement", 0, 6, 3),
        ("defined_benefit_obligation", "signed_movement", 0, 7, 2),
        ("plan_assets", "signed_movement", -55_973_000, 7, 3),
        ("defined_benefit_obligation", "signed_movement", 0, 9, 2),
        ("plan_assets", "signed_movement", 0, 9, 3),
        ("defined_benefit_obligation", "signed_movement", -191_125_000, 10, 2),
        ("plan_assets", "signed_movement", -191_125_000, 10, 3),
        ("defined_benefit_obligation", "signed_movement", -18_579_000, 11, 2),
        ("plan_assets", "signed_movement", -18_579_000, 11, 3),
        ("defined_benefit_obligation", "signed_movement", -95_001_000, 12, 2),
        ("plan_assets", "signed_movement", -95_001_000, 12, 3),
        ("defined_benefit_obligation", "ending", 4_236_010_000, 13, 2),
        ("plan_assets", "ending", 3_632_781_000, 13, 3),
    ]


def test_defined_benefit_layout_does_not_fall_back_to_generic_column_candidate():
    table = ReportTable(
        17,
        [["", "금액"], ["기초금액", "100"], ["기말금액", "90"]],
        "13. 순확정급여부채",
        SourceLocation("note:13", 0, 17),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="13",
        title="순확정급여부채",
        table=table,
        layout=LayoutClassification(
            "defined_benefit_rollforward",
            0.85,
            ("defined benefit account columns",),
            "note:13/table:17",
        ),
        orientation=TableOrientation("column_oriented", 0.85, ("expense amount column",)),
    )

    assert candidates == []


def test_extracts_inventory_allowance_rollforward_signed_candidates():
    table = ReportTable(
        18,
        [
            ["", "재고자산 평가충당금"],
            ["기초재고자산", "(3,969,701)"],
            ["재고자산 평가손실환입", "427,066"],
            ["재고자산 평가손실", "(961,511)"],
            ["재고자산 폐기", "0"],
            ["기타 (주1)", "(1,553)"],
            ["기말재고자산", "(4,505,699)"],
        ],
        "6. 재고자산",
        SourceLocation("note:6", 0, 18),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="6",
        title="재고자산",
        table=table,
        layout=LayoutClassification(
            "inventory_allowance_rollforward",
            0.85,
            ("inventory allowance amount column",),
            "note:6/table:18",
        ),
        orientation=TableOrientation(
            "row_oriented",
            0.85,
            ("inventory allowance movement labels in rows",),
        ),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("inventory_valuation_allowance", "beginning", -3_969_701_000, 1, 1),
        ("inventory_valuation_allowance", "signed_movement", 427_066_000, 2, 1),
        ("inventory_valuation_allowance", "signed_movement", -961_511_000, 3, 1),
        ("inventory_valuation_allowance", "signed_movement", 0, 4, 1),
        ("inventory_valuation_allowance", "signed_movement", -1_553_000, 5, 1),
        ("inventory_valuation_allowance", "ending", -4_505_699_000, 6, 1),
    ]


def test_extracts_net_debt_bridge_candidates_by_liability_column():
    table = ReportTable(
        16,
        [
            ["", "유동성사채", "리스 부채", "장기 차입금"],
            ["기초 순부채", "100", "50", "70"],
            ["현금흐름", "(20)", "(10)", "30"],
            ["이자비용", "5", "3", "0"],
            ["기말 순부채", "85", "43", "100"],
        ],
        "29. 영업으로부터 창출된 현금",
        SourceLocation("note:29", 0, 16),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="29",
        title="영업으로부터 창출된 현금",
        table=table,
        layout=LayoutClassification(
            "net_debt_bridge",
            0.85,
            ("net debt movement rows",),
            "note:29/table:16",
        ),
        orientation=TableOrientation(
            "mixed",
            0.85,
            ("financial liability account columns", "net debt movement rows"),
        ),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.label, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("current_bonds", "beginning", "유동성사채 기초 순부채", 100_000, 1, 1),
        ("lease_liabilities", "beginning", "리스 부채 기초 순부채", 50_000, 1, 2),
        ("long_term_borrowings", "beginning", "장기 차입금 기초 순부채", 70_000, 1, 3),
        ("current_bonds", "signed_movement", "유동성사채 현금흐름", -20_000, 2, 1),
        ("lease_liabilities", "signed_movement", "리스 부채 현금흐름", -10_000, 2, 2),
        ("long_term_borrowings", "signed_movement", "장기 차입금 현금흐름", 30_000, 2, 3),
        ("current_bonds", "signed_movement", "유동성사채 이자비용", 5_000, 3, 1),
        ("lease_liabilities", "signed_movement", "리스 부채 이자비용", 3_000, 3, 2),
        ("long_term_borrowings", "signed_movement", "장기 차입금 이자비용", 0, 3, 3),
        ("current_bonds", "ending", "유동성사채 기말 순부채", 85_000, 4, 1),
        ("lease_liabilities", "ending", "리스 부채 기말 순부채", 43_000, 4, 2),
        ("long_term_borrowings", "ending", "장기 차입금 기말 순부채", 100_000, 4, 3),
    ]


def test_extracts_financing_debt_bridge_candidates_by_liability_column():
    table = ReportTable(
        20,
        [
            ["", "단기차입금", "장기차입금", "사채", "리스부채", "미지급배당금"],
            ["재무활동에서 생기는 기초 부채", "19,135", "117,608", "146,640", "6,517", "3"],
            ["차입금의 증가, 재무활동에서 생기는 부채", "104,568", "41,236", "0", "0", "0"],
            ["차입금의 감소, 재무활동에서 생기는 부채", "(54,502)", "(37,159)", "(78,010)", "(2,308)", "0"],
            ["그 밖의 변동, 재무활동에서 생기는 부채의 증가(감소)", "0", "283", "1,321", "2,104", "23,631"],
            ["재무활동에서 생기는 기말 부채", "69,201", "121,968", "69,951", "6,313", "23,634"],
        ],
        "37. 현금흐름표",
        SourceLocation("note:37", 0, 20),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="37",
        title="현금흐름표",
        table=table,
        layout=LayoutClassification(
            "net_debt_bridge",
            0.85,
            ("net debt movement rows",),
            "note:37/table:20",
        ),
        orientation=TableOrientation(
            "mixed",
            0.85,
            ("financial liability account columns", "net debt movement rows"),
        ),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("short_term_borrowings", "beginning", 19_135_000, 1, 1),
        ("long_term_borrowings", "beginning", 117_608_000, 1, 2),
        ("bonds", "beginning", 146_640_000, 1, 3),
        ("lease_liabilities", "beginning", 6_517_000, 1, 4),
        ("dividends_payable", "beginning", 3_000, 1, 5),
        ("short_term_borrowings", "signed_movement", 104_568_000, 2, 1),
        ("long_term_borrowings", "signed_movement", 41_236_000, 2, 2),
        ("bonds", "signed_movement", 0, 2, 3),
        ("lease_liabilities", "signed_movement", 0, 2, 4),
        ("dividends_payable", "signed_movement", 0, 2, 5),
        ("short_term_borrowings", "signed_movement", -54_502_000, 3, 1),
        ("long_term_borrowings", "signed_movement", -37_159_000, 3, 2),
        ("bonds", "signed_movement", -78_010_000, 3, 3),
        ("lease_liabilities", "signed_movement", -2_308_000, 3, 4),
        ("dividends_payable", "signed_movement", 0, 3, 5),
        ("short_term_borrowings", "signed_movement", 0, 4, 1),
        ("long_term_borrowings", "signed_movement", 283_000, 4, 2),
        ("bonds", "signed_movement", 1_321_000, 4, 3),
        ("lease_liabilities", "signed_movement", 2_104_000, 4, 4),
        ("dividends_payable", "signed_movement", 23_631_000, 4, 5),
        ("short_term_borrowings", "ending", 69_201_000, 5, 1),
        ("long_term_borrowings", "ending", 121_968_000, 5, 2),
        ("bonds", "ending", 69_951_000, 5, 3),
        ("lease_liabilities", "ending", 6_313_000, 5, 4),
        ("dividends_payable", "ending", 23_634_000, 5, 5),
    ]


def test_extracts_financing_debt_bridge_current_and_noncurrent_lease_columns_separately():
    table = ReportTable(
        21,
        [
            ["", "리스 부채", "유동성리스부채", "리스 부채(비유동)"],
            ["재무활동에서 생기는 기초 부채", "100", "30", "70"],
            ["재무현금흐름, 재무활동에서 생기는 부채의 증가(감소)", "(20)", "(10)", "0"],
            ["유동성대체", "0", "15", "(15)"],
            ["기타", "5", "2", "3"],
            ["재무활동에서 생기는 기말 부채", "85", "37", "58"],
        ],
        "34. 현금흐름표",
        SourceLocation("note:34", 0, 21),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="34",
        title="현금흐름표",
        table=table,
        layout=LayoutClassification(
            "net_debt_bridge",
            0.85,
            ("net debt movement rows",),
            "note:34/table:21",
        ),
        orientation=TableOrientation(
            "mixed",
            0.85,
            ("financial liability account columns", "net debt movement rows"),
        ),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("lease_liabilities", "beginning", 100_000, 1, 1),
        ("current_lease_liabilities", "beginning", 30_000, 1, 2),
        ("noncurrent_lease_liabilities", "beginning", 70_000, 1, 3),
        ("lease_liabilities", "signed_movement", -20_000, 2, 1),
        ("current_lease_liabilities", "signed_movement", -10_000, 2, 2),
        ("noncurrent_lease_liabilities", "signed_movement", 0, 2, 3),
        ("lease_liabilities", "signed_movement", 0, 3, 1),
        ("current_lease_liabilities", "signed_movement", 15_000, 3, 2),
        ("noncurrent_lease_liabilities", "signed_movement", -15_000, 3, 3),
        ("lease_liabilities", "signed_movement", 5_000, 4, 1),
        ("current_lease_liabilities", "signed_movement", 2_000, 4, 2),
        ("noncurrent_lease_liabilities", "signed_movement", 3_000, 4, 3),
        ("lease_liabilities", "ending", 85_000, 5, 1),
        ("current_lease_liabilities", "ending", 37_000, 5, 2),
        ("noncurrent_lease_liabilities", "ending", 58_000, 5, 3),
    ]


def test_extracts_financing_debt_bridge_bond_columns_separately():
    table = ReportTable(
        22,
        [
            ["", "단기사채", "유동성장기사채", "사채(유동)", "사채(비유동)", "전환사채 및 교환사채"],
            ["재무활동에서 생기는 기초 부채", "10", "20", "30", "40", "50"],
            ["재무현금흐름, 재무활동에서 생기는 부채의 증가(감소)", "5", "(5)", "(10)", "20", "0"],
            ["그 밖의 변동, 재무활동에서 생기는 부채의 증가(감소)", "1", "2", "3", "4", "(7)"],
            ["재무활동에서 생기는 기말 부채", "16", "17", "23", "64", "43"],
        ],
        "38. 현금흐름표",
        SourceLocation("note:38", 0, 22),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="38",
        title="현금흐름표",
        table=table,
        layout=LayoutClassification(
            "net_debt_bridge",
            0.85,
            ("net debt movement rows",),
            "note:38/table:22",
        ),
        orientation=TableOrientation(
            "mixed",
            0.85,
            ("financial liability account columns", "net debt movement rows"),
        ),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("short_term_bonds", "beginning", 10_000, 1, 1),
        ("current_long_term_bonds", "beginning", 20_000, 1, 2),
        ("current_bonds", "beginning", 30_000, 1, 3),
        ("noncurrent_bonds", "beginning", 40_000, 1, 4),
        ("convertible_exchangeable_bonds", "beginning", 50_000, 1, 5),
        ("short_term_bonds", "signed_movement", 5_000, 2, 1),
        ("current_long_term_bonds", "signed_movement", -5_000, 2, 2),
        ("current_bonds", "signed_movement", -10_000, 2, 3),
        ("noncurrent_bonds", "signed_movement", 20_000, 2, 4),
        ("convertible_exchangeable_bonds", "signed_movement", 0, 2, 5),
        ("short_term_bonds", "signed_movement", 1_000, 3, 1),
        ("current_long_term_bonds", "signed_movement", 2_000, 3, 2),
        ("current_bonds", "signed_movement", 3_000, 3, 3),
        ("noncurrent_bonds", "signed_movement", 4_000, 3, 4),
        ("convertible_exchangeable_bonds", "signed_movement", -7_000, 3, 5),
        ("short_term_bonds", "ending", 16_000, 4, 1),
        ("current_long_term_bonds", "ending", 17_000, 4, 2),
        ("current_bonds", "ending", 23_000, 4, 3),
        ("noncurrent_bonds", "ending", 64_000, 4, 4),
        ("convertible_exchangeable_bonds", "ending", 43_000, 4, 5),
    ]


def test_extracts_financing_debt_bridge_current_and_noncurrent_rental_deposit_columns_separately():
    table = ReportTable(
        23,
        [
            ["", "유동 임대보증금", "비유동 임대보증금", "임대보증금"],
            ["재무활동에서 생기는 기초 부채", "100", "70", "30"],
            ["재무현금흐름, 재무활동에서 생기는 부채의 증가(감소)", "(90)", "80", "10"],
            ["그 밖의 변동, 재무활동에서 생기는 부채의 증가(감소)", "5", "3", "2"],
            ["재무활동에서 생기는 기말 부채", "15", "153", "42"],
        ],
        "35. 영업으로부터 창출된 현금 등",
        SourceLocation("note:35", 0, 23),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="35",
        title="영업으로부터 창출된 현금 등",
        table=table,
        layout=LayoutClassification(
            "net_debt_bridge",
            0.85,
            ("net debt movement rows",),
            "note:35/table:23",
        ),
        orientation=TableOrientation(
            "mixed",
            0.85,
            ("financial liability account columns", "net debt movement rows"),
        ),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("current_rental_deposits", "beginning", 100_000, 1, 1),
        ("noncurrent_rental_deposits", "beginning", 70_000, 1, 2),
        ("rental_deposits", "beginning", 30_000, 1, 3),
        ("current_rental_deposits", "signed_movement", -90_000, 2, 1),
        ("noncurrent_rental_deposits", "signed_movement", 80_000, 2, 2),
        ("rental_deposits", "signed_movement", 10_000, 2, 3),
        ("current_rental_deposits", "signed_movement", 5_000, 3, 1),
        ("noncurrent_rental_deposits", "signed_movement", 3_000, 3, 2),
        ("rental_deposits", "signed_movement", 2_000, 3, 3),
        ("current_rental_deposits", "ending", 15_000, 4, 1),
        ("noncurrent_rental_deposits", "ending", 153_000, 4, 2),
        ("rental_deposits", "ending", 42_000, 4, 3),
    ]


def test_extracts_financing_debt_bridge_skips_duplicate_aggregate_movement_rows():
    table = ReportTable(
        24,
        [
            ["", "", "차입금", "사채", "리스 부채"],
            ["기초 재무활동에서 생기는 부채", "기초 재무활동에서 생기는 부채", "100", "200", "300"],
            ["재무현금흐름, 재무활동에서 생기는 부채의 증가(감소)", "재무현금흐름, 재무활동에서 생기는 부채의 증가(감소)", "10", "20", "(30)"],
            ["재무현금흐름, 재무활동에서 생기는 부채의 증가(감소)", "재무현금흐름, 재무활동에서 생기는 부채의 증가", "70", "120", "0"],
            ["재무현금흐름, 재무활동에서 생기는 부채의 증가(감소)", "재무현금흐름, 재무활동에서 생기는 부채의 감소", "(60)", "(100)", "(30)"],
            ["비현금흐름, 재무활동에서 생기는 부채의 증가(감소)", "비현금흐름, 재무활동에서 생기는 부채의 증가(감소)", "5", "6", "7"],
            ["비현금흐름, 재무활동에서 생기는 부채의 증가(감소)", "상각, 재무활동에서 생기는 부채의 증가(감소)", "2", "3", "4"],
            ["비현금흐름, 재무활동에서 생기는 부채의 증가(감소)", "대체, 재무활동에서 생기는 부채의 증가(감소)", "3", "3", "3"],
            ["기말 재무활동에서 생기는 부채", "기말 재무활동에서 생기는 부채", "115", "226", "307"],
        ],
        "43. 현금흐름표",
        SourceLocation("note:43", 0, 24),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="43",
        title="현금흐름표",
        table=table,
        layout=LayoutClassification(
            "net_debt_bridge",
            0.85,
            ("net debt movement rows",),
            "note:43/table:24",
        ),
        orientation=TableOrientation(
            "mixed",
            0.85,
            ("financial liability account columns", "net debt movement rows"),
        ),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("borrowings", "beginning", 100_000, 1, 2),
        ("bonds", "beginning", 200_000, 1, 3),
        ("lease_liabilities", "beginning", 300_000, 1, 4),
        ("borrowings", "signed_movement", 70_000, 3, 2),
        ("bonds", "signed_movement", 120_000, 3, 3),
        ("lease_liabilities", "signed_movement", 0, 3, 4),
        ("borrowings", "signed_movement", -60_000, 4, 2),
        ("bonds", "signed_movement", -100_000, 4, 3),
        ("lease_liabilities", "signed_movement", -30_000, 4, 4),
        ("borrowings", "signed_movement", 2_000, 6, 2),
        ("bonds", "signed_movement", 3_000, 6, 3),
        ("lease_liabilities", "signed_movement", 4_000, 6, 4),
        ("borrowings", "signed_movement", 3_000, 7, 2),
        ("bonds", "signed_movement", 3_000, 7, 3),
        ("lease_liabilities", "signed_movement", 3_000, 7, 4),
        ("borrowings", "ending", 115_000, 8, 2),
        ("bonds", "ending", 226_000, 8, 3),
        ("lease_liabilities", "ending", 307_000, 8, 4),
    ]


def test_extracts_credit_risk_exposure_summary_candidates():
    table = ReportTable(
        17,
        [
            ["", "신용위험"],
            ["현금성자산", "100"],
            ["단기당기손익-공정가치측정금융자산", "200"],
            ["매출채권", "300"],
            ["기타비유동금융자산", "50"],
            ["합계", "650"],
        ],
        "31. 재무위험관리",
        SourceLocation("note:31", 0, 17),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="31",
        title="재무위험관리",
        table=table,
        layout=LayoutClassification(
            "credit_risk_exposure_summary",
            0.85,
            ("credit risk exposure amount column",),
            "note:31/table:17",
        ),
        orientation=TableOrientation(
            "column_oriented",
            0.85,
            ("credit risk exposure amount column", "financial asset rows"),
        ),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.label, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("cash_and_cash_equivalents", "credit_exposure_component", "현금성자산", 100_000, 1, 1),
        ("financial_assets_fvtpl_current", "credit_exposure_component", "단기당기손익-공정가치측정금융자산", 200_000, 2, 1),
        ("trade_receivables", "credit_exposure_component", "매출채권", 300_000, 3, 1),
        ("other_noncurrent_financial_assets", "credit_exposure_component", "기타비유동금융자산", 50_000, 4, 1),
        ("credit_risk_exposure", "credit_exposure_total", "합계", 650_000, 5, 1),
    ]


def test_extracts_credit_risk_exposure_candidates_from_standalone_company_labels():
    table = ReportTable(
        18,
        [
            ["", "신용위험"],
            ["현금성자산", "100"],
            ["단기대여금", "20"],
            ["미수금", "30"],
            ["미수수익", "40"],
            ["기타금융자산", "50"],
            ["당기손익-공정가치측정금융자산", "60"],
            ["기타포괄손익-공정가치측정금융자산", "70"],
            ["파생상품자산", "80"],
            ["장기대여금", "90"],
            ["장기보증금", "100"],
            ["합계", "550"],
        ],
        "28. 재무위험관리(별도)",
        SourceLocation("note:28", 0, 18),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="28",
        title="재무위험관리(별도)",
        table=table,
        layout=LayoutClassification(
            "credit_risk_exposure_summary",
            0.85,
            ("credit risk exposure amount column",),
            "note:28/table:18",
        ),
        orientation=TableOrientation(
            "column_oriented",
            0.85,
            ("credit risk exposure amount column", "financial asset rows"),
        ),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount)
        for candidate in candidates
    ] == [
        ("cash_and_cash_equivalents", "credit_exposure_component", 100_000),
        ("short_term_loans", "credit_exposure_component", 20_000),
        ("short_term_other_receivables", "credit_exposure_component", 30_000),
        ("short_term_accrued_income", "credit_exposure_component", 40_000),
        ("other_financial_assets", "credit_exposure_component", 50_000),
        ("financial_assets_fvtpl", "credit_exposure_component", 60_000),
        ("financial_assets_fvoci", "credit_exposure_component", 70_000),
        ("derivative_assets", "credit_exposure_component", 80_000),
        ("long_term_loans", "credit_exposure_component", 90_000),
        ("long_term_deposits", "credit_exposure_component", 100_000),
        ("credit_risk_exposure", "credit_exposure_total", 550_000),
    ]


def test_extracts_credit_risk_exposure_row_summary_candidates():
    table = ReportTable(
        134,
        [
            ["", "현금및현금성자산", "파생상품자산", "매출채권", "금융보증계약", "금융상품 합계"],
            ["신용위험에 대한 최대 노출정도", "6,767,898", "962,876", "10,849,398", "3,832,003", "21,412,175"],
        ],
        "23. 금융상품",
        SourceLocation("note:23", 0, 134),
        unit_multiplier=1_000_000,
    )

    candidates = extract_verification_candidates(
        note_no="23",
        title="금융상품",
        table=table,
        layout=LayoutClassification(
            "credit_risk_exposure_summary",
            0.85,
            ("credit risk exposure row", "financial asset exposure columns include total"),
            "note:23/table:134",
        ),
        orientation=TableOrientation(
            "column_oriented",
            0.85,
            ("credit risk exposure row", "financial asset exposure columns include total"),
        ),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.label, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("cash_and_cash_equivalents", "credit_exposure_component", "현금및현금성자산", 6_767_898_000_000, 1, 1),
        ("derivative_assets", "credit_exposure_component", "파생상품자산", 962_876_000_000, 1, 2),
        ("trade_receivables", "credit_exposure_component", "매출채권", 10_849_398_000_000, 1, 3),
        ("credit_risk_exposure_component", "credit_exposure_component", "금융보증계약", 3_832_003_000_000, 1, 4),
        ("credit_risk_exposure", "credit_exposure_total", "금융상품 합계", 21_412_175_000_000, 1, 5),
    ]


def test_extracts_liquidity_maturity_analysis_candidates_by_row():
    table = ReportTable(
        19,
        [
            ["", "3개월 이내", "3개월 초과 1년 이내", "1년 초과 2년 이내", "2년 초과", "합계 구간 합계"],
            ["차입금 및 사채", "10", "20", "30", "40", "100"],
            ["리스부채", "1", "2", "3", "4", "10"],
            ["합계", "11", "22", "33", "44", "110"],
        ],
        "31. 재무위험관리",
        SourceLocation("note:31", 0, 19),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="31",
        title="재무위험관리",
        table=table,
        layout=LayoutClassification(
            "liquidity_maturity_analysis",
            0.85,
            ("maturity bucket columns",),
            "note:31/table:19",
        ),
        orientation=TableOrientation(
            "column_oriented",
            0.85,
            ("maturity bucket columns", "financial liability rows"),
        ),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.label, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("borrowings_and_bonds", "maturity_component", "차입금 및 사채 3개월 이내", 10_000, 1, 1),
        ("borrowings_and_bonds", "maturity_component", "차입금 및 사채 3개월 초과 1년 이내", 20_000, 1, 2),
        ("borrowings_and_bonds", "maturity_component", "차입금 및 사채 1년 초과 2년 이내", 30_000, 1, 3),
        ("borrowings_and_bonds", "maturity_component", "차입금 및 사채 2년 초과", 40_000, 1, 4),
        ("borrowings_and_bonds", "maturity_total", "차입금 및 사채 합계 구간 합계", 100_000, 1, 5),
        ("lease_liabilities", "maturity_component", "리스부채 3개월 이내", 1_000, 2, 1),
        ("lease_liabilities", "maturity_component", "리스부채 3개월 초과 1년 이내", 2_000, 2, 2),
        ("lease_liabilities", "maturity_component", "리스부채 1년 초과 2년 이내", 3_000, 2, 3),
        ("lease_liabilities", "maturity_component", "리스부채 2년 초과", 4_000, 2, 4),
        ("lease_liabilities", "maturity_total", "리스부채 합계 구간 합계", 10_000, 2, 5),
        ("maturity_analysis_total", "maturity_component", "합계 3개월 이내", 11_000, 3, 1),
        ("maturity_analysis_total", "maturity_component", "합계 3개월 초과 1년 이내", 22_000, 3, 2),
        ("maturity_analysis_total", "maturity_component", "합계 1년 초과 2년 이내", 33_000, 3, 3),
        ("maturity_analysis_total", "maturity_component", "합계 2년 초과", 44_000, 3, 4),
        ("maturity_analysis_total", "maturity_total", "합계 합계 구간 합계", 110_000, 3, 5),
    ]


def test_extracts_employee_benefit_maturity_summary_candidates():
    table = ReportTable(
        122,
        [
            ["", "1년 이내", "1년 초과 5년 이내", "5년 초과 10년 이내", "10년 초과", "합계 구간 합계"],
            ["확정급여제도에서 지급될 것으로 예상되는 급여 지급액 추정치", "8,537,047", "45,919,845", "12,261,563", "42,020,488", "108,738,943"],
        ],
        "19. 퇴직급여제도",
        SourceLocation("note:19", 0, 122),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="19",
        title="퇴직급여제도",
        table=table,
        layout=LayoutClassification(
            "employee_benefit_maturity_summary",
            0.85,
            ("employee benefit expected payment row",),
            "note:19/table:122",
        ),
        orientation=TableOrientation(
            "row_oriented",
            0.85,
            ("maturity bucket columns", "employee benefit expected payment row"),
        ),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.label, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("defined_benefit_expected_payments", "maturity_component", "확정급여제도에서 지급될 것으로 예상되는 급여 지급액 추정치 1년 이내", 8_537_047_000, 1, 1),
        ("defined_benefit_expected_payments", "maturity_component", "확정급여제도에서 지급될 것으로 예상되는 급여 지급액 추정치 1년 초과 5년 이내", 45_919_845_000, 1, 2),
        ("defined_benefit_expected_payments", "maturity_component", "확정급여제도에서 지급될 것으로 예상되는 급여 지급액 추정치 5년 초과 10년 이내", 12_261_563_000, 1, 3),
        ("defined_benefit_expected_payments", "maturity_component", "확정급여제도에서 지급될 것으로 예상되는 급여 지급액 추정치 10년 초과", 42_020_488_000, 1, 4),
        ("defined_benefit_expected_payments", "maturity_total", "확정급여제도에서 지급될 것으로 예상되는 급여 지급액 추정치 합계 구간 합계", 108_738_943_000, 1, 5),
    ]


def test_extracts_employee_benefit_maturity_tilde_and_over_buckets():
    table = ReportTable(
        175,
        [
            ["", "1년 미만", "1~2년 미만", "2~5년 미만", "5년 이상", "합계 구간 합계"],
            ["확정급여제도에서 지급될 것으로 예상되는 급여 지급액 추정치", "31,401", "43,100", "77,935", "192,473", "344,909"],
        ],
        "24. 순확정급여부채",
        SourceLocation("note:24", 0, 175),
        unit_multiplier=1_000_000,
    )

    candidates = extract_verification_candidates(
        note_no="24",
        title="순확정급여부채",
        table=table,
        layout=LayoutClassification(
            "employee_benefit_maturity_summary",
            0.85,
            ("employee benefit expected payment row",),
            "note:24/table:175",
        ),
        orientation=TableOrientation(
            "row_oriented",
            0.85,
            ("maturity bucket columns", "employee benefit expected payment row"),
        ),
    )

    assert [(candidate.role, candidate.amount, candidate.column_index) for candidate in candidates] == [
        ("maturity_component", 31_401_000_000, 1),
        ("maturity_component", 43_100_000_000, 2),
        ("maturity_component", 77_935_000_000, 3),
        ("maturity_component", 192_473_000_000, 4),
        ("maturity_total", 344_909_000_000, 5),
    ]


def test_extracts_employee_benefit_expected_contribution_maturity_candidates():
    table = ReportTable(
        122,
        [
            ["", "1년 이내", "1년 초과 2년 이내", "2년 초과 5년 이내", "5년 초과", "합계 구간 합계"],
            ["다음 연차보고기간 동안에 납부할 것으로 예상되는 기여금에 대한 추정치", "13,535", "22,099", "63,885", "271,840", "371,359"],
            ["확정급여채무의 가중평균만기", "", "", "", "", "8년9개월"],
        ],
        "18. 퇴직급여제도",
        SourceLocation("note:18", 0, 122),
        unit_multiplier=1_000_000,
    )

    candidates = extract_verification_candidates(
        note_no="18",
        title="퇴직급여제도",
        table=table,
        layout=LayoutClassification(
            "employee_benefit_maturity_summary",
            0.85,
            ("employee benefit expected contribution row",),
            "note:18/table:122",
        ),
        orientation=TableOrientation(
            "row_oriented",
            0.85,
            ("maturity bucket columns", "employee benefit expected contribution row"),
        ),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.label, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("defined_benefit_expected_contributions", "maturity_component", "다음 연차보고기간 동안에 납부할 것으로 예상되는 기여금에 대한 추정치 1년 이내", 13_535_000_000, 1, 1),
        ("defined_benefit_expected_contributions", "maturity_component", "다음 연차보고기간 동안에 납부할 것으로 예상되는 기여금에 대한 추정치 1년 초과 2년 이내", 22_099_000_000, 1, 2),
        ("defined_benefit_expected_contributions", "maturity_component", "다음 연차보고기간 동안에 납부할 것으로 예상되는 기여금에 대한 추정치 2년 초과 5년 이내", 63_885_000_000, 1, 3),
        ("defined_benefit_expected_contributions", "maturity_component", "다음 연차보고기간 동안에 납부할 것으로 예상되는 기여금에 대한 추정치 5년 초과", 271_840_000_000, 1, 4),
        ("defined_benefit_expected_contributions", "maturity_total", "다음 연차보고기간 동안에 납부할 것으로 예상되는 기여금에 대한 추정치 합계 구간 합계", 371_359_000_000, 1, 5),
    ]


def test_skips_employee_benefit_expected_contribution_total_only_maturity_row():
    table = ReportTable(
        96,
        [
            ["", "합계 구간 합계"],
            ["다음 연차보고기간 동안에 납부할 것으로 예상되는 기여금에 대한 추정치", "6,194,801"],
        ],
        "21. 퇴직급여",
        SourceLocation("note:21", 0, 96),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="21",
        title="퇴직급여",
        table=table,
        layout=LayoutClassification(
            "employee_benefit_maturity_summary",
            0.85,
            ("employee benefit expected contribution row",),
            "note:21/table:96",
        ),
        orientation=TableOrientation(
            "row_oriented",
            0.85,
            ("maturity bucket columns", "employee benefit expected contribution row"),
        ),
    )

    assert candidates == []


def test_extracts_lease_liability_maturity_summary_candidates():
    table = ReportTable(
        132,
        [
            ["", "1년 이내", "1년 초과 5년 이내", "5년 초과", "합계 구간 합계"],
            ["최소리스료", "76,705,355", "48,461,726", "3,894,487", "129,061,568"],
            ["리스부채에 대한 이자비용", "18,865,338", "31,254,580", "627,365", "50,747,283"],
            ["최소리스료의 현재가치", "57,840,017", "17,207,146", "3,267,122", "78,314,285"],
        ],
        "15. 사용권자산 및 리스부채",
        SourceLocation("note:15", 0, 132),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="15",
        title="사용권자산 및 리스부채",
        table=table,
        layout=LayoutClassification(
            "lease_liability_maturity_summary",
            0.85,
            ("lease liability maturity rows",),
            "note:15/table:132",
        ),
        orientation=TableOrientation(
            "column_oriented",
            0.85,
            ("maturity bucket columns", "lease liability maturity rows"),
        ),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.label, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("minimum_lease_payments", "maturity_component", "최소리스료 1년 이내", 76_705_355_000, 1, 1),
        ("minimum_lease_payments", "maturity_component", "최소리스료 1년 초과 5년 이내", 48_461_726_000, 1, 2),
        ("minimum_lease_payments", "maturity_component", "최소리스료 5년 초과", 3_894_487_000, 1, 3),
        ("minimum_lease_payments", "maturity_total", "최소리스료 합계 구간 합계", 129_061_568_000, 1, 4),
        ("lease_liability_interest", "maturity_component", "리스부채에 대한 이자비용 1년 이내", 18_865_338_000, 2, 1),
        ("lease_liability_interest", "maturity_component", "리스부채에 대한 이자비용 1년 초과 5년 이내", 31_254_580_000, 2, 2),
        ("lease_liability_interest", "maturity_component", "리스부채에 대한 이자비용 5년 초과", 627_365_000, 2, 3),
        ("lease_liability_interest", "maturity_total", "리스부채에 대한 이자비용 합계 구간 합계", 50_747_283_000, 2, 4),
        ("lease_liability_present_value", "maturity_component", "최소리스료의 현재가치 1년 이내", 57_840_017_000, 3, 1),
        ("lease_liability_present_value", "maturity_component", "최소리스료의 현재가치 1년 초과 5년 이내", 17_207_146_000, 3, 2),
        ("lease_liability_present_value", "maturity_component", "최소리스료의 현재가치 5년 초과", 3_267_122_000, 3, 3),
        ("lease_liability_present_value", "maturity_total", "최소리스료의 현재가치 합계 구간 합계", 78_314_285_000, 3, 4),
    ]


def test_skips_lease_liability_maturity_rows_without_component_buckets():
    table = ReportTable(
        111,
        [
            ["", "", "1년 이내", "1년 초과 5년 이내", "5년 초과", "합계 구간 합계"],
            ["총 리스부채", "총 리스부채", "481,644", "1,153,118", "771,458", "2,406,220"],
            ["리스부채", "리스부채", "", "0", "", "2,064,060"],
            ["리스부채", "유동 리스부채", "", "", "", "476,446"],
            ["리스부채", "비유동 리스부채", "", "", "", "1,587,614"],
        ],
        "19. 리스",
        SourceLocation("note:19", 0, 111),
        unit_multiplier=1_000_000,
    )

    candidates = extract_verification_candidates(
        note_no="19",
        title="리스",
        table=table,
        layout=LayoutClassification(
            "lease_liability_maturity_summary",
            0.85,
            ("lease liability maturity rows",),
            "note:19/table:111",
        ),
        orientation=TableOrientation(
            "column_oriented",
            0.85,
            ("maturity bucket columns", "lease liability maturity rows"),
        ),
    )

    assert [(candidate.account_key, candidate.role, candidate.amount, candidate.row_index) for candidate in candidates] == [
        ("undiscounted_lease_liabilities", "maturity_component", 481_644_000_000, 1),
        ("undiscounted_lease_liabilities", "maturity_component", 1_153_118_000_000, 1),
        ("undiscounted_lease_liabilities", "maturity_component", 771_458_000_000, 1),
        ("undiscounted_lease_liabilities", "maturity_total", 2_406_220_000_000, 1),
    ]


def test_extracts_liquidity_maturity_analysis_accrued_payable_rows():
    table = ReportTable(
        20,
        [
            ["", "3개월 이내", "3개월 초과 1년 이내", "2년 초과", "합계 구간 합계"],
            ["미지급금", "10", "0", "0", "10"],
            ["사채", "1", "2", "3", "6"],
            ["미지급비용", "4", "0", "0", "4"],
        ],
        "28. 재무위험관리(별도)",
        SourceLocation("note:28", 0, 20),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="28",
        title="재무위험관리(별도)",
        table=table,
        layout=LayoutClassification(
            "liquidity_maturity_analysis",
            0.85,
            ("maturity bucket columns",),
            "note:28/table:20",
        ),
        orientation=TableOrientation(
            "column_oriented",
            0.85,
            ("maturity bucket columns", "financial liability rows"),
        ),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.amount)
        for candidate in candidates
    ] == [
        ("other_payables", "maturity_component", 10_000),
        ("other_payables", "maturity_component", 0),
        ("other_payables", "maturity_component", 0),
        ("other_payables", "maturity_total", 10_000),
        ("bonds", "maturity_component", 1_000),
        ("bonds", "maturity_component", 2_000),
        ("bonds", "maturity_component", 3_000),
        ("bonds", "maturity_total", 6_000),
        ("accrued_expenses", "maturity_component", 4_000),
        ("accrued_expenses", "maturity_component", 0),
        ("accrued_expenses", "maturity_component", 0),
        ("accrued_expenses", "maturity_total", 4_000),
    ]


def test_extracts_lease_expense_summary_candidates_from_stacked_headers():
    table = ReportTable(
        21,
        [
            ["", "자산", "자산", "자산 합계"],
            ["", "사용권자산", "사용권자산", "자산 합계"],
            ["", "부동산", "차량운반구", "자산 합계"],
            ["감가상각비, 사용권자산", "100", "20", "120"],
            ["리스부채에 대한 이자비용(금융비용에 포함)", "", "", "30"],
            ["단기리스료", "", "", "4"],
        ],
        "34. 리스",
        SourceLocation("note:34", 0, 21),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="34",
        title="리스",
        table=table,
        layout=LayoutClassification(
            "lease_expense_summary",
            0.85,
            ("lease expense rows",),
            "note:34/table:21",
        ),
        orientation=TableOrientation(
            "column_oriented",
            0.85,
            ("lease expense rows", "lease asset total column"),
        ),
    )

    assert [
        (candidate.account_key, candidate.role, candidate.label, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("right_of_use_asset_depreciation", "lease_expense_component", "감가상각비, 사용권자산 부동산", 100_000, 3, 1),
        ("right_of_use_asset_depreciation", "lease_expense_component", "감가상각비, 사용권자산 차량운반구", 20_000, 3, 2),
        ("right_of_use_asset_depreciation", "lease_expense_total", "감가상각비, 사용권자산 자산 합계", 120_000, 3, 3),
        ("lease_interest_expense", "lease_expense_total", "리스부채에 대한 이자비용(금융비용에 포함) 자산 합계", 30_000, 4, 3),
        ("short_term_lease_expense", "lease_expense_total", "단기리스료 자산 합계", 4_000, 5, 3),
    ]


def test_extracts_discontinued_operation_income_statement_candidates():
    table = ReportTable(
        22,
        [
            ["", "", "중단영업"],
            ["매출액", "매출액", "86,773,808"],
            ["매출원가", "매출원가", "71,401,947"],
            ["매출총이익", "매출총이익", "15,371,861"],
            ["판매비와관리비", "판매비와관리비", "16,214,619"],
            ["영업이익(손실)", "영업이익(손실)", "(842,758)"],
            ["기타이익", "기타이익", "738,185"],
            ["기타손실", "기타손실", "129,922"],
            ["금융수익", "금융수익", "555,985"],
            ["금융비용", "금융비용", "2,158,514"],
            ["법인세비용차감전순이익(손실)", "법인세비용차감전순이익(손실)", "(1,837,024)"],
            ["중단영업 법인세비용(수익)", "중단영업 법인세비용(수익)", "137,049"],
            ["중단영업이익(손실)", "중단영업이익(손실)", "(1,974,073)"],
            ["중단영업처분이익", "중단영업처분이익", "21,874,959"],
            ["중단영업순이익", "중단영업순이익", "19,900,886"],
            ["중단영업순이익", "지배기업의 소유주에게 귀속될 중단영업손익", "20,368,366"],
            ["중단영업순이익", "비지배지분에 귀속될 중단영업이익(손실)", "(467,480)"],
        ],
        "35. 매각예정처분자산(부채)집단과 중단영업",
        SourceLocation("note:35", 0, 22),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="35",
        title="매각예정처분자산(부채)집단과 중단영업",
        table=table,
        layout=LayoutClassification(
            "discontinued_operation_income_statement",
            0.85,
            ("discontinued operation income rows",),
            "note:35/table:22",
        ),
        orientation=TableOrientation(
            "column_oriented",
            0.85,
            ("discontinued operation income rows",),
        ),
    )

    assert [
        (candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("revenue", 86_773_808_000, 1, 2),
        ("cost_of_sales", 71_401_947_000, 2, 2),
        ("gross_profit", 15_371_861_000, 3, 2),
        ("selling_admin", 16_214_619_000, 4, 2),
        ("operating_profit", -842_758_000, 5, 2),
        ("other_income", 738_185_000, 6, 2),
        ("other_loss", 129_922_000, 7, 2),
        ("finance_income", 555_985_000, 8, 2),
        ("finance_cost", 2_158_514_000, 9, 2),
        ("pre_tax_profit", -1_837_024_000, 10, 2),
        ("tax_expense", 137_049_000, 11, 2),
        ("discontinued_profit", -1_974_073_000, 12, 2),
        ("disposal_gain", 21_874_959_000, 13, 2),
        ("net_discontinued_profit", 19_900_886_000, 14, 2),
        ("parent_attribution", 20_368_366_000, 15, 2),
        ("noncontrolling_attribution", -467_480_000, 16, 2),
    ]


def test_extracts_discontinued_operation_cashflow_summary_candidates():
    table = ReportTable(
        23,
        [
            ["", "중단영업"],
            ["중단영업영업활동현금흐름", "10"],
            ["중단영업투자활동현금흐름", "(3)"],
            ["중단영업재무활동현금흐름", "2"],
            ["합계", "9"],
        ],
        "35. 매각예정처분자산(부채)집단과 중단영업",
        SourceLocation("note:35", 0, 23),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="35",
        title="매각예정처분자산(부채)집단과 중단영업",
        table=table,
        layout=LayoutClassification(
            "discontinued_operation_cashflow_summary",
            0.85,
            ("discontinued operation cash flow rows",),
            "note:35/table:23",
        ),
        orientation=TableOrientation(
            "column_oriented",
            0.85,
            ("discontinued operation cash flow rows",),
        ),
    )

    assert [
        (candidate.role, candidate.amount, candidate.row_index, candidate.column_index)
        for candidate in candidates
    ] == [
        ("operating_cashflow", 10_000, 1, 1),
        ("investing_cashflow", -3_000, 2, 1),
        ("financing_cashflow", 2_000, 3, 1),
        ("cashflow_total", 9_000, 4, 1),
    ]


def test_unknown_orientation_returns_no_candidates():
    table = ReportTable(
        2,
        [["구분", "내용"], ["회사", "샘플"]],
        "1. 일반사항",
        SourceLocation("note:1", 0, 2),
    )

    candidates = extract_verification_candidates(
        note_no="1",
        title="일반사항",
        table=table,
        layout=LayoutClassification("unknown_layout", 0.0, (), "note:1/table:2"),
        orientation=TableOrientation("unknown", 0.0, ()),
    )

    assert candidates == []
