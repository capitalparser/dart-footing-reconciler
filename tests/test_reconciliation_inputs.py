from dart_footing_reconciler.document import (
    FullReport,
    ReportBlock,
    ReportSection,
    ReportTable,
    SourceLocation,
)
from dart_footing_reconciler.reconciliation_inputs import extract_reconciliation_inputs


def _section(section_id, title, kind, note_no, rows):
    table = ReportTable(0, rows, title, SourceLocation(section_id, 0, 0))
    return ReportSection(
        section_id,
        title,
        kind,
        note_no,
        [ReportBlock("table", "", table, table.location)],
    )


def test_extract_reconciliation_inputs_separates_statement_note_and_cfs_sources():
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
            ),
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산의 취득", "(300)"]],
            ),
        ],
        [
            _section(
                "note:11",
                "유형자산",
                "note",
                "11",
                [["구분", "합계"], ["기초", "800"], ["취득", "300"], ["기말", "1,000"]],
            ),
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert inputs.statement_lines[0].account_key == "property_plant_equipment"
    assert inputs.cfs_lines[0].account_key == "property_plant_equipment"
    assert inputs.cfs_lines[0].movement_role == "acquisition"
    assert inputs.note_balances[0].balance_role == "ending"
    assert inputs.note_movements[0].movement_role == "acquisition"


def test_extract_reconciliation_inputs_marks_financing_cashflow_table_class():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            ReportSection(
                "note:20",
                "차입금",
                "note",
                "20",
                [
                    ReportBlock(
                        "table",
                        "",
                        ReportTable(
                            0,
                            [
                                ["구분", "차입", "상환"],
                                ["차입금", "100", "(40)"],
                            ],
                            "재무활동에서 생기는 부채의 변동",
                            SourceLocation("note:20", 0, 0),
                        ),
                        SourceLocation("note:20", 0, 0),
                    )
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    movements = [movement for movement in inputs.note_movements if movement.movement_role == "financing_cashflow"]
    assert movements
    assert {movement.table_class for movement in movements} == {"financing_cashflow_reconciliation"}


def test_extract_reconciliation_inputs_excludes_asset_receivable_payable_cfs_rows_from_primary_asset_cashflows():
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
                    ["기타채무(유형자산 취득)의 증가(감소)", "(57)"],
                    ["기타채권(유형자산 처분)의 감소(증가)", "58"],
                    ["유형자산의 취득", "(300)"],
                    ["유형자산의 처분", "20"],
                ],
            )
        ],
        [],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [(line.label, line.movement_role, line.amount) for line in inputs.cfs_lines] == [
        ("유형자산의 취득", "acquisition", -300),
        ("유형자산의 처분", "disposal", 20),
    ]


def test_extract_reconciliation_inputs_excludes_asset_subtype_cfs_rows_from_primary_asset_cashflows():
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
                    ["건설중인 유형자산의 취득", "(57)"],
                    ["기타유형자산의 처분", "58"],
                    ["기타무형자산의 취득", "(11)"],
                    ["무형자산 등의 처분", "7"],
                    ["유형자산의 취득", "(300)"],
                    ["무형자산의 취득", "(40)"],
                ],
            )
        ],
        [],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [(line.label, line.account_key, line.movement_role, line.amount) for line in inputs.cfs_lines] == [
        ("유형자산의 취득", "property_plant_equipment", "acquisition", -300),
        ("무형자산의 취득", "intangible_assets", "acquisition", -40),
    ]


def test_extract_reconciliation_inputs_reads_lease_repayment_from_rou_cashflow_note():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:15",
                "사용권자산 3) 현금흐름표에 인식한 금액",
                "note",
                "15",
                [
                    ["구분", "당기"],
                    ["리스부채의 상환", "1,450"],
                    ["이자비용", "50"],
                ],
            ),
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    lease_movements = [
        movement
        for movement in inputs.note_movements
        if movement.account_key == "lease_liabilities"
        and movement.movement_role == "financing_cashflow"
    ]
    assert [(movement.label, movement.amount) for movement in lease_movements] == [
        ("리스부채의 상환", -1450),
    ]


def test_extract_reconciliation_inputs_classifies_borrowing_decrease_as_repayment():
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
                    ["단기차입금의 증가", "1,000"],
                    ["단기차입금의 감소", "300"],
                    ["장기차입금의 차입", "500"],
                    ["장기차입금의 상환", "(200)"],
                ],
            )
        ],
        [],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [(line.label, line.movement_role, line.amount) for line in inputs.cfs_lines] == [
        ("단기차입금의 증가", "proceeds", 1000),
        ("단기차입금의 감소", "repayment", -300),
        ("장기차입금의 차입", "proceeds", 500),
        ("장기차입금의 상환", "repayment", -200),
    ]


def test_extract_reconciliation_inputs_classifies_bond_borrowing_as_proceeds():
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
                    ["단기사채의 차입", "166,421"],
                    ["사채의 차입", "99,579"],
                    ["사채의 상환", "(20,000)"],
                ],
            )
        ],
        [],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [
        (line.label, line.account_key, line.movement_role, line.amount)
        for line in inputs.cfs_lines
    ] == [
        ("단기사채의 차입", "bonds", "proceeds", 166421),
        ("사채의 차입", "bonds", "proceeds", 99579),
        ("사채의 상환", "bonds", "repayment", -20000),
    ]


def test_extract_reconciliation_inputs_treats_bond_issuance_fee_payment_as_financing_outflow():
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
                    ["사채의 발행", "140,000"],
                    ["사채발행비 지급", "448"],
                    ["사채발행비용", "50"],
                    ["사채의 상환", "(80,000)"],
                ],
            )
        ],
        [],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [
        (line.label, line.account_key, line.movement_role, line.amount)
        for line in inputs.cfs_lines
    ] == [
        ("사채의 발행", "bonds", "proceeds", 140000),
        ("사채발행비 지급", "bonds", "repayment", -448),
        ("사채의 상환", "bonds", "repayment", -80000),
    ]


def test_extract_reconciliation_inputs_excludes_non_principal_debt_fee_and_refund_rows():
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
                    ["단기차입금의 차입", "70,000"],
                    ["차입금중도상환수수료의 지급", "(251)"],
                    ["회사채의 발행", "229,234"],
                    ["사채발행분담금의 반환", "2"],
                    ["사채의 상환", "(140,000)"],
                ],
            )
        ],
        [],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [
        (line.label, line.account_key, line.movement_role, line.amount)
        for line in inputs.cfs_lines
    ] == [
        ("단기차입금의 차입", "borrowings", "proceeds", 70000),
        ("회사채의 발행", "bonds", "proceeds", 229234),
        ("사채의 상환", "bonds", "repayment", -140000),
    ]


def test_extract_reconciliation_inputs_keeps_duplicate_note_numbers_topic_safe():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:18:lease",
                "리스부채",
                "note",
                "18",
                [["구분", "합계"], ["상환", "300"]],
            ),
            _section(
                "note:18:borrowings",
                "차입금",
                "note",
                "18",
                [["구분", "합계"], ["차입", "700"]],
            ),
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [
        (movement.account_key, movement.movement_role, movement.amount)
        for movement in inputs.note_movements
    ] == [
        ("lease_liabilities", "repayment", 300),
        ("borrowings", "proceeds", 700),
    ]


def test_extract_reconciliation_inputs_treats_carrying_amount_aliases_as_ending_balance():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:11",
                "유형자산",
                "note",
                "11",
                [
                    ["구분", "합계"],
                    ["장부금액", "1,000"],
                    ["순장부금액", "900"],
                    ["장부가액", "800"],
                ],
            ),
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [
        (balance.account_key, balance.balance_role, balance.label, balance.amount)
        for balance in inputs.note_balances
    ] == [
        ("property_plant_equipment", "ending", "장부금액", 1000),
        ("property_plant_equipment", "ending", "순장부금액", 900),
        ("property_plant_equipment", "ending", "장부가액", 800),
    ]


def test_extract_reconciliation_inputs_does_not_treat_beginning_carrying_amount_as_ending_balance():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:16",
                "유형자산",
                "note",
                "16",
                [
                    ["구분", "합계"],
                    ["기초장부가액", "7,596,997"],
                    ["기말장부가액", "10,212,008"],
                ],
            ),
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [
        (balance.account_key, balance.balance_role, balance.label, balance.amount)
        for balance in inputs.note_balances
    ] == [
        ("property_plant_equipment", "ending", "기말장부가액", 10_212_008),
    ]


def test_extract_reconciliation_inputs_classifies_borrowing_cfs_repayment_before_proceeds():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["차입금의 상환", "(300)"]],
            ),
        ],
        [],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [
        (line.account_key, line.movement_role, line.amount) for line in inputs.cfs_lines
    ] == [
        ("borrowings", "repayment", -300),
    ]


def test_extract_reconciliation_inputs_classifies_lease_liability_decrease_as_repayment():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["리스부채의 감소", "(300)"]],
            ),
        ],
        [],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [(line.account_key, line.movement_role, line.amount) for line in inputs.cfs_lines] == [
        ("lease_liabilities", "repayment", -300),
    ]


def test_extract_reconciliation_inputs_normalizes_positive_repayment_cash_outflows():
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
                    ["단기차입금의 상환", "300"],
                    ["리스부채의 감소", "200"],
                    ["사채상환손실", "100"],
                    ["사채발행비용", "50"],
                ],
            ),
        ],
        [],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [(line.account_key, line.movement_role, line.amount, line.label) for line in inputs.cfs_lines] == [
        ("borrowings", "repayment", -300, "단기차입금의 상환"),
        ("lease_liabilities", "repayment", -200, "리스부채의 감소"),
    ]


def test_extract_reconciliation_inputs_classifies_borrowing_note_repayment_before_proceeds():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:18",
                "차입금",
                "note",
                "18",
                [["구분", "합계"], ["차입금의 상환", "300"]],
            ),
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [
        (movement.account_key, movement.movement_role, movement.amount)
        for movement in inputs.note_movements
    ] == [
        ("borrowings", "repayment", 300),
    ]


def test_extract_reconciliation_inputs_prefers_current_period_amounts_over_rightmost_prior_period():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기", "전기"], ["유형자산의 취득", "(300)", "(999)"]],
            ),
        ],
        [
            _section(
                "note:11",
                "유형자산",
                "note",
                "11",
                [
                    ["구분", "당기", "전기"],
                    ["기말", "1,000", "9,999"],
                    ["취득", "300", "999"],
                ],
            ),
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [(line.label, line.amount) for line in inputs.cfs_lines] == [
        ("유형자산의 취득", -300),
    ]
    assert [(balance.label, balance.amount) for balance in inputs.note_balances] == [
        ("기말", 1000),
    ]
    assert [(movement.label, movement.amount) for movement in inputs.note_movements] == [
        ("취득", 300),
    ]


def test_extract_reconciliation_inputs_skips_cfs_row_when_current_period_amount_is_blank():
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
                    ["구분", "제 52 기", "제 51 기", "제 50 기"],
                    ["단기차입금의 증가", "", "27,571,613", "163,987,542"],
                    ["단기차입금의 상환", "(8,400,000)", "(66,293,958)", "(183,658,526)"],
                ],
            ),
        ],
        [],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [(line.label, line.amount) for line in inputs.cfs_lines] == [
        ("단기차입금의 상환", -8_400_000),
    ]


def test_extract_reconciliation_inputs_classifies_asset_cashflow_adjustment_rows():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:11",
                "유형자산",
                "note",
                "11",
                [
                    ["구분", "합계"],
                    ["처분", "900"],
                    ["처분금액", "980"],
                    ["처분손익", "150"],
                    ["처분손실", "20"],
                    ["비현금거래-미수금", "30"],
                    ["비현금거래-미지급금", "200"],
                    ["미수금", "40"],
                    ["미지급금", "50"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [(movement.movement_role, movement.label, movement.amount) for movement in inputs.note_movements] == [
        ("disposal", "처분", 900),
        ("disposal_proceeds", "처분금액", 980),
        ("disposal_gain_loss", "처분손익", 150),
        ("disposal_loss", "처분손실", 20),
        ("noncash_receivable", "비현금거래-미수금", 30),
        ("noncash_payable", "비현금거래-미지급금", 200),
        ("noncash_receivable", "미수금", 40),
        ("noncash_payable", "미지급금", 50),
    ]


def test_extract_reconciliation_inputs_uses_table_inferred_note_topic_for_balances_and_movements():
    trade_table = ReportTable(
        0,
        [["구분", "합계"], ["영업채권", "1,000"]],
        "금융자산의 범주별 장부금액",
        SourceLocation("note:1", 0, 0),
        row_acodes=[
            ["||||", "||||"],
            ["||||", "ifrs-full_TradeReceivables|CFY|0|KRW|"],
        ],
    )
    ppe_table = ReportTable(
        1,
        [["구분", "합계"], ["취득", "300"], ["기말", "1,500"]],
        "유형자산의 변동내역",
        SourceLocation("note:1", 1, 1),
    )
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            ReportSection(
                "note:1",
                "일반사항",
                "note",
                "1",
                [
                    ReportBlock("table", "", trade_table, trade_table.location),
                    ReportBlock("table", "", ppe_table, ppe_table.location),
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [(balance.account_key, balance.label, balance.amount) for balance in inputs.note_balances] == [
        ("trade_receivables", "영업채권", 1000),
        ("property_plant_equipment", "기말", 1500),
    ]
    assert [(movement.account_key, movement.label, movement.amount) for movement in inputs.note_movements] == [
        ("property_plant_equipment", "취득", 300),
    ]


def test_extract_reconciliation_inputs_keeps_canonical_topic_when_generic_topic_shares_table():
    table = ReportTable(
        0,
        [["구분", "금액"], ["매출채권", "300"], ["계약자산", "100"]],
        "매출채권 및 계약자산",
        SourceLocation("note:8", 0, 0),
        row_acodes=[
            ["||||", "||||"],
            ["||||", "ifrs-full_TradeReceivables|CFY|0|KRW|"],
            ["||||", "ifrs-full_ContractAssets|CFY|0|KRW|"],
        ],
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
                [["구분", "당기"], ["매출채권", "300"], ["계약자산", "100"]],
            )
        ],
        [
            ReportSection(
                "note:8",
                "매출채권 및 계약자산",
                "note",
                "8",
                [ReportBlock("table", "", table, table.location)],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert ("trade_receivables", "매출채권", 300) in [
        (balance.account_key, balance.label, balance.amount) for balance in inputs.note_balances
    ]


def test_extract_reconciliation_inputs_normalizes_note_unit_to_won():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            ReportSection(
                "note:11",
                "유형자산",
                "note",
                "11",
                [
                    ReportBlock(
                        "table",
                        "",
                        ReportTable(
                            0,
                            [["구분", "합계"], ["기말", "1,000"]],
                            "유형자산",
                            SourceLocation("note:11", 0, 0),
                            unit_multiplier=1000,
                        ),
                        SourceLocation("note:11", 0, 0),
                    )
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [(balance.account_key, balance.amount) for balance in inputs.note_balances] == [
        ("property_plant_equipment", 1_000_000)
    ]


def test_extract_reconciliation_inputs_reads_financing_liability_cashflow_note_column():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:36",
                "현금흐름",
                "note",
                "36",
                [
                    ["", "", "재무활동현금흐름", "비현금흐름"],
                    ["재무활동에서 생기는 부채", "차입금", "1,000", "(400)", "10", "610"],
                    ["재무활동에서 생기는 부채", "사채", "800", "(100)", "5", "705"],
                    ["재무활동에서 생기는 부채", "리스 부채", "700", "(300)", "20", "420"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [
        (movement.account_key, movement.movement_role, movement.amount)
        for movement in inputs.note_movements
    ] == [
        ("borrowings", "financing_cashflow", -400),
        ("bonds", "financing_cashflow", -100),
        ("lease_liabilities", "financing_cashflow", -300),
    ]


def test_extract_reconciliation_inputs_reads_named_financing_cashflow_column():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:36",
                "재무활동에서 생기는 부채",
                "note",
                "36",
                [
                    ["", "", "기초", "사업결합", "증가", "현금흐름", "기타", "기말"],
                    ["재무활동에서 생기는 부채", "단기차입금", "13,124", "32,000", "0", "45,200", "163", "90,487"],
                    ["재무활동에서 생기는 부채", "유동성장기차입금", "68,500", "0", "0", "(21,667)", "0", "46,833"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [
        (movement.account_key, movement.movement_role, movement.amount)
        for movement in inputs.note_movements
    ] == [
        ("borrowings", "financing_cashflow", 45200),
        ("borrowings", "financing_cashflow", -21667),
    ]


def test_extract_reconciliation_inputs_reads_financing_borrowing_and_repayment_columns():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:37",
                "현금흐름표 재무활동에서 생기는 부채의 조정",
                "note",
                "37",
                [
                    [
                        "",
                        "",
                        "재무활동에서 생기는 기초 부채",
                        "차입",
                        "상환",
                        "이자비용",
                        "대체",
                        "재무활동에서 생기는 기말 부채",
                    ],
                    ["재무활동에서 생기는 부채", "단기차입금", "12,966", "5,000", "(5,948)", "0", "0", "12,018"],
                    ["재무활동에서 생기는 부채", "유동성사채", "14,997", "0", "(15,000)", "3", "0", "0"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [
        (movement.account_key, movement.movement_role, movement.amount, movement.source)
        for movement in inputs.note_movements
    ] == [
        ("borrowings", "financing_cashflow", 5000, "note:37/table:0/row:1/col:3"),
        ("borrowings", "financing_cashflow", -5948, "note:37/table:0/row:1/col:4"),
        ("bonds", "financing_cashflow", -15000, "note:37/table:0/row:2/col:4"),
    ]


def test_extract_reconciliation_inputs_reads_bond_principal_repayment_from_bond_rollforward():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
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

    inputs = extract_reconciliation_inputs(report)

    assert ("bonds", "financing_cashflow", -3000, "note:38/table:0/row:1/col:2") in [
        (movement.account_key, movement.movement_role, movement.amount, movement.source)
        for movement in inputs.note_movements
    ]


def test_extract_reconciliation_inputs_reads_split_financing_cashflow_increase_and_decrease_columns():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:39",
                "재무활동에서 생기는 부채",
                "note",
                "39",
                [
                    [
                        "",
                        "",
                        "재무활동에서 생기는 기초 부채",
                        "재무현금흐름, 재무활동에서 생기는 부채의 증가",
                        "재무현금흐름, 재무활동에서 생기는 부채의 감소",
                        "비현금흐름",
                        "재무활동에서 생기는 기말 부채",
                    ],
                    ["재무활동에서 생기는 부채", "단기차입금", "90,355", "187,479", "(202,694)", "693", "75,833"],
                    ["재무활동에서 생기는 부채", "사채", "42,242", "33,325", "(266)", "5,608", "36,475"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [
        (movement.account_key, movement.movement_role, movement.amount, movement.source)
        for movement in inputs.note_movements
    ] == [
        ("borrowings", "financing_cashflow", 187479, "note:39/table:0/row:1/col:3"),
        ("borrowings", "financing_cashflow", -202694, "note:39/table:0/row:1/col:4"),
        ("bonds", "financing_cashflow", 33325, "note:39/table:0/row:2/col:3"),
        ("bonds", "financing_cashflow", -266, "note:39/table:0/row:2/col:4"),
    ]


def test_extract_reconciliation_inputs_reads_simple_financing_increase_and_decrease_columns():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:31",
                "현금흐름표 31.3 재무활동에서 생기는 부채의 조정내용",
                "note",
                "31",
                [
                    ["구 분", "기초", "증가", "감소", "대체", "외화환산", "기타변동", "기말"],
                    ["단기차입금", "73,944,862", "65,534,356", "(71,682,404)", "24,800,000", "5,898,774", "-", "98,495,588"],
                    ["장기차입금", "168,592,692", "25,000,000", "(750,000)", "(46,642,692)", "-", "-", "146,200,000"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [
        (movement.account_key, movement.movement_role, movement.amount, movement.source)
        for movement in inputs.note_movements
    ] == [
        ("borrowings", "financing_cashflow", 65534356, "note:31/table:0/row:1/col:2"),
        ("borrowings", "financing_cashflow", -71682404, "note:31/table:0/row:1/col:3"),
        ("borrowings", "financing_cashflow", 25000000, "note:31/table:0/row:2/col:2"),
        ("borrowings", "financing_cashflow", -750000, "note:31/table:0/row:2/col:3"),
    ]


def test_extract_reconciliation_inputs_reads_financing_inflow_and_outflow_columns():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:35",
                "현금흐름표 재무활동에서 생기는 부채의 조정내용",
                "note",
                "35",
                [
                    ["구 분", "기초", "유입", "유출", "대체", "기말"],
                    ["단기차입금", "20,586", "75,788", "(46,830)", "-", "49,544"],
                    ["장기차입금", "-", "8,000", "-", "-", "8,000"],
                    ["리스부채", "3,013", "-", "(1,337)", "893", "2,569"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [
        (movement.account_key, movement.movement_role, movement.amount, movement.source)
        for movement in inputs.note_movements
    ] == [
        ("borrowings", "financing_cashflow", 75788, "note:35/table:0/row:1/col:2"),
        ("borrowings", "financing_cashflow", -46830, "note:35/table:0/row:1/col:3"),
        ("borrowings", "financing_cashflow", 8000, "note:35/table:0/row:2/col:2"),
        ("lease_liabilities", "financing_cashflow", -1337, "note:35/table:0/row:3/col:3"),
    ]


def test_extract_reconciliation_inputs_preserves_signed_combined_financing_cashflow_column():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:35",
                "재무활동에서 생기는 부채",
                "note",
                "35",
                [
                    [
                        "",
                        "",
                        "재무활동에서 생기는 기초 부채",
                        "재무현금흐름, 재무활동에서 생기는 부채의 증가(감소)",
                        "그 밖의 변동",
                        "재무활동에서 생기는 기말 부채",
                    ],
                    ["재무활동에서 생기는 부채", "금융기관 차입금", "7,151,365", "464,287", "496,808", "8,112,460"],
                    ["재무활동에서 생기는 부채", "사채", "2,676,399", "(387,216)", "3,780", "2,292,964"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [
        (movement.account_key, movement.movement_role, movement.amount)
        for movement in inputs.note_movements
    ] == [
        ("borrowings", "financing_cashflow", 464287),
        ("bonds", "financing_cashflow", -387216),
    ]


def test_extract_reconciliation_inputs_reads_lease_interest_financing_adjustment():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:17",
                "리스부채",
                "note",
                "17",
                [
                    ["", "공시금액"],
                    ["리스부채에 대한 이자비용", "3,282"],
                    ["리스 현금유출", "19,411"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [
        (movement.account_key, movement.movement_role, movement.label, movement.amount)
        for movement in inputs.note_movements
        if movement.account_key == "lease_liabilities"
    ] == [
        ("lease_liabilities", "financing_cashflow", "리스부채 이자비용 조정", 3282),
    ]


def test_extract_reconciliation_inputs_excludes_bond_discount_amortization_from_financing_cashflow():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:36",
                "재무활동에서 생기는 부채의 조정",
                "note",
                "36",
                [
                    ["", "", "단기사채", "사채", "재무활동에서 생기는 부채 합계"],
                    ["재무활동에서 생기는 부채의 변동", "현금흐름", "146,421", "99,579", "245,000"],
                    ["재무활동에서 생기는 부채의 변동", "사채할인발행차금상각", "2,948", "22", "2,970"],
                ],
            ),
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [
        (movement.account_key, movement.movement_role, movement.amount, movement.source)
        for movement in inputs.note_movements
        if movement.account_key == "bonds"
    ] == [
        ("bonds", "financing_cashflow", 146421, "note:36/table:0/row:1/col:2"),
        ("bonds", "financing_cashflow", 99579, "note:36/table:0/row:1/col:3"),
    ]


def test_extract_reconciliation_inputs_reads_financing_cashflow_rows_with_account_columns():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:37",
                "현금흐름표 재무활동에서 생기는 부채의 조정",
                "note",
                "37",
                [
                    ["", "단기차입금", "장기차입금", "사채", "리스부채"],
                    ["재무활동에서 생기는 기초 부채", "19,135", "117,608", "146,640", "6,517"],
                    ["차입금의 증가, 재무활동에서 생기는 부채", "104,568", "41,236", "0", "0"],
                    ["차입금의 감소, 재무활동에서 생기는 부채", "(54,502)", "(37,159)", "(78,010)", "(2,308)"],
                    ["재무활동에서 생기는 기말 부채", "69,201", "121,968", "69,951", "6,312"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [
        (movement.account_key, movement.movement_role, movement.amount, movement.source)
        for movement in inputs.note_movements
    ] == [
        ("borrowings", "financing_cashflow", 104568, "note:37/table:0/row:2/col:1"),
        ("borrowings", "financing_cashflow", 41236, "note:37/table:0/row:2/col:2"),
        ("borrowings", "financing_cashflow", -54502, "note:37/table:0/row:3/col:1"),
        ("borrowings", "financing_cashflow", -37159, "note:37/table:0/row:3/col:2"),
        ("bonds", "financing_cashflow", -78010, "note:37/table:0/row:3/col:3"),
        ("lease_liabilities", "financing_cashflow", -2308, "note:37/table:0/row:3/col:4"),
    ]


def test_extract_reconciliation_inputs_reads_new_borrowing_and_repayment_rows_with_account_columns():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:27",
                "연결현금흐름표 재무활동에서 생기는 부채의 조정",
                "note",
                "27",
                [
                    ["", "리스 부채", "단기차입금", "장기 차입금"],
                    ["재무활동에서 생기는 기초 부채", "6,286,875", "13,964,000", "129,688,479"],
                    ["새로운 차입금, 재무활동에서 생기는 부채의 증가", "", "3,073,019", "69,987,204"],
                    ["차입금의 상환, 재무활동에서 생기는 부채의 감소", "", "(8,073,019)", "(25,705,040)"],
                    ["재무활동에서 생기는 기말 부채", "13,253,682", "8,964,000", "173,983,898"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [
        (movement.account_key, movement.movement_role, movement.amount, movement.source)
        for movement in inputs.note_movements
    ] == [
        ("borrowings", "financing_cashflow", 3_073_019, "note:27/table:0/row:2/col:2"),
        ("borrowings", "financing_cashflow", 69_987_204, "note:27/table:0/row:2/col:3"),
        ("borrowings", "financing_cashflow", -8_073_019, "note:27/table:0/row:3/col:2"),
        ("borrowings", "financing_cashflow", -25_705_040, "note:27/table:0/row:3/col:3"),
    ]


def test_extract_reconciliation_inputs_reads_direct_financing_cashflow_column_and_skips_prior_table():
    current_table = ReportTable(
        0,
        [
            ["구분", "기초", "재무활동 현금흐름", "기타", "기말"],
            ["단기차입금", "-", "700,151", "(43,675)", "656,476"],
            ["리스부채", "10,121,320", "(8,119,050)", "9,312,419", "11,314,689"],
        ],
        "재무활동 관련 부채의 변동 (1) 당기 중 재무활동에서 생기는 부채의 변동",
        SourceLocation("note:37", 0, 0),
        unit_multiplier=1000,
    )
    prior_table = ReportTable(
        1,
        [
            ["구분", "기초", "재무활동 현금흐름", "기타", "기말"],
            ["단기차입금", "13,540,762", "(13,565,901)", "25,139", "-"],
            ["리스부채", "11,427,324", "(7,291,451)", "5,985,447", "10,121,320"],
        ],
        "재무활동 관련 부채의 변동 (1) 당기 중 재무활동에서 생기는 부채의 변동 (2) 전기 중 재무활동에서 생기는 부채의 변동",
        SourceLocation("note:37", 1, 1),
        unit_multiplier=1000,
    )
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            ReportSection(
                "note:37",
                "재무활동 관련 부채의 변동",
                "note",
                "37",
                [
                    ReportBlock("table", "", current_table, current_table.location),
                    ReportBlock("table", "", prior_table, prior_table.location),
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [
        (movement.account_key, movement.movement_role, movement.amount)
        for movement in inputs.note_movements
    ] == [
        ("borrowings", "financing_cashflow", 700_151_000),
        ("lease_liabilities", "financing_cashflow", -8_119_050_000),
    ]


def test_extract_reconciliation_inputs_skips_financing_table_marked_current_then_prior():
    current_table = ReportTable(
        0,
        [
            ["구분", "기초", "재무활동 현금흐름", "기타", "기말"],
            ["단기차입금", "-", "20,369,080", "-", "20,369,080"],
            ["장기차입금", "5,000,000", "(2,000,000)", "-", "3,000,000"],
        ],
        "재무활동에서 생기는 부채의 변동 (당기)",
        SourceLocation("note:34", 0, 0),
        unit_multiplier=1000,
    )
    prior_table = ReportTable(
        1,
        [
            ["구분", "기초", "재무활동 현금흐름", "기타", "기말"],
            ["단기차입금", "1,000,080", "(1,000,080)", "-", "-"],
            ["장기차입금", "-", "-", "-", "-"],
        ],
        "현금흐름표 재무활동에서 생기는 부채의 변동 (당기) (전기)",
        SourceLocation("note:34", 1, 1),
        unit_multiplier=1000,
    )
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            ReportSection(
                "note:34",
                "재무활동에서 생기는 부채의 변동",
                "note",
                "34",
                [
                    ReportBlock("table", "", current_table, current_table.location),
                    ReportBlock("table", "", prior_table, prior_table.location),
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [
        (movement.account_key, movement.movement_role, movement.amount)
        for movement in inputs.note_movements
    ] == [
        ("borrowings", "financing_cashflow", 20_369_080_000),
        ("borrowings", "financing_cashflow", -2_000_000_000),
    ]


def test_extract_reconciliation_inputs_keeps_current_tables_that_compare_current_and_prior_periods():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            ReportSection(
                "note:11",
                "유형자산",
                "note",
                "11",
                [
                    ReportBlock(
                        "table",
                        "",
                        ReportTable(
                            0,
                            [["구분", "합계"], ["취득", "300"], ["기말", "1,000"]],
                            "유형자산 (1) 당기말 및 전기말 현재 구성내역 (2) 당기와 전기 중 변동내역",
                            SourceLocation("note:11", 0, 0),
                        ),
                        SourceLocation("note:11", 0, 0),
                    )
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [(movement.account_key, movement.movement_role, movement.amount) for movement in inputs.note_movements] == [
        ("property_plant_equipment", "acquisition", 300),
    ]


def test_extract_reconciliation_inputs_reads_expense_by_nature_and_functional_allocation():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:15",
                "유형자산",
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
                    ["성격별 비용 합계", "무형자산상각비", "200"],
                ],
            ),
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [
        (expense.account_key, expense.classification, expense.label, expense.amount)
        for expense in inputs.functional_expenses
    ] == [
        ("property_plant_equipment", "cost_of_sales", "매출원가", 700),
        ("property_plant_equipment", "selling_admin", "판매비와 일반관리비", 300),
        ("property_plant_equipment", "allocation_total", "기능별 항목", 1000),
        ("property_plant_equipment", "nature_total", "감가상각비", 1000),
        ("intangible_assets", "nature_total", "무형자산상각비", 200),
    ]


def test_extract_reconciliation_inputs_does_not_treat_cost_or_loss_rows_as_cash_movements():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산처분손실", "100"], ["유형자산의 처분", "200"]],
            )
        ],
        [
            _section(
                "note:13",
                "유형자산",
                "note",
                "13",
                [["구분", "합계"], ["취득원가", "1,000"], ["취득", "300"], ["처분", "(200)"]],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [(line.label, line.movement_role) for line in inputs.cfs_lines] == [
        ("유형자산의 처분", "disposal")
    ]
    assert [(movement.label, movement.movement_role) for movement in inputs.note_movements] == [
        ("취득", "acquisition"),
        ("처분", "disposal"),
    ]


def test_extract_reconciliation_inputs_does_not_treat_combined_disposal_impairment_rows_as_cash_disposal():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:13",
                "유형자산",
                "note",
                "13",
                [
                    ["구분", "합계"],
                    ["취득", "300"],
                    ["처분/폐기/손상", "(200)"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [(movement.label, movement.movement_role) for movement in inputs.note_movements] == [
        ("취득", "acquisition"),
    ]


def test_extract_reconciliation_inputs_excludes_zero_amount_cfs_rows_from_primary_cashflows():
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
                    ["무형자산의 처분", "0"],
                    ["교환사채의 발행", "-"],
                    ["전환사채의 상환", "0"],
                    ["유형자산의 처분", "200"],
                ],
            )
        ],
        [],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [
        (line.label, line.account_key, line.movement_role, line.amount)
        for line in inputs.cfs_lines
    ] == [
        ("유형자산의 처분", "property_plant_equipment", "disposal", 200),
    ]


def test_extract_reconciliation_inputs_does_not_treat_asset_purchase_commitments_as_acquisitions():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:11",
                "유형자산",
                "note",
                "11",
                [
                    ["구분", "금액"],
                    ["유형자산을 취득하기 위한 약정액", "1,000"],
                    ["취득", "300"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [(movement.movement_role, movement.label, movement.amount) for movement in inputs.note_movements] == [
        ("acquisition", "취득", 300),
    ]


def test_extract_reconciliation_inputs_distinguishes_business_combination_from_cash_acquisition():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:13",
                "유형자산",
                "note",
                "13",
                [
                    ["구분", "합계"],
                    ["사업결합을 통한 취득, 유형자산", "100"],
                    ["사업결합을 통한 취득 이외의 증가, 유형자산", "300"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [(movement.label, movement.movement_role, movement.amount) for movement in inputs.note_movements] == [
        ("사업결합을 통한 취득, 유형자산", "business_combination", 100),
        ("사업결합을 통한 취득 이외의 증가, 유형자산", "acquisition", 300),
    ]


def test_extract_reconciliation_inputs_reads_operating_cashflow_note_disposal_adjustments():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:33",
                "영업활동현금흐름",
                "note",
                "33",
                [
                    ["구분", "당기"],
                    ["유형자산처분손실", "10"],
                    ["유형자산처분이익", "(30)"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [(movement.account_key, movement.movement_role, movement.amount) for movement in inputs.note_movements] == [
        ("property_plant_equipment", "disposal_loss", 10),
        ("property_plant_equipment", "disposal_gain_loss", -30),
    ]


def test_extract_reconciliation_inputs_reads_income_statement_note_disposal_adjustments():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:28",
                "기타수익 및 기타비용",
                "note",
                "28",
                [
                    ["구분", "내역", "당기"],
                    ["기타수익", "유형자산처분이익", "31"],
                    ["기타비용", "유형자산처분손실", "151"],
                    ["기타수익", "무형자산처분이익", "7"],
                    ["기타비용", "무형자산처분손실", "11"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [(movement.account_key, movement.movement_role, movement.amount) for movement in inputs.note_movements] == [
        ("property_plant_equipment", "disposal_gain_loss", 31),
        ("property_plant_equipment", "disposal_loss", 151),
        ("intangible_assets", "disposal_gain_loss", 7),
        ("intangible_assets", "disposal_loss", 11),
    ]


def test_extract_reconciliation_inputs_reads_misc_gain_loss_note_disposal_adjustments():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:23",
                "기타손익",
                "note",
                "23",
                [
                    ["계정과목", "당기", "전기"],
                    ["유형자산처분이익", "31,907", "413"],
                    ["유형자산처분손실", "-", "(776)"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [
        (movement.account_key, movement.movement_role, movement.amount)
        for movement in inputs.note_movements
    ] == [
        ("property_plant_equipment", "disposal_gain_loss", 31_907),
    ]


def test_extract_reconciliation_inputs_reads_cashflow_note_disposal_loss_adjustments():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:31",
                "현금흐름표",
                "note",
                "31",
                [
                    ["구분", "당기", "전기"],
                    ["조정", "", ""],
                    ["무형자산처분손실", "15,000", "-"],
                    ["유무형자산처분이익", "(35,174)", "(113,628)"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [
        (movement.account_key, movement.movement_role, movement.amount)
        for movement in inputs.note_movements
    ] == [
        ("intangible_assets", "disposal_loss", 15_000),
        ("property_plant_equipment", "disposal_gain_loss", -35_174),
        ("intangible_assets", "disposal_gain_loss", -35_174),
    ]


def test_extract_reconciliation_inputs_reads_noncash_asset_payable_adjustments():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:31",
                "현금의 유입과 유출이 없는 거래",
                "note",
                "31",
                [
                    ["구분", "당기", "전기"],
                    ["유형자산 취득 관련 미지급금 증가", "(1,209)"],
                    ["무형자산 취득 관련 미지급금 변동", "22", "(58)"],
                    ["유무형자산 취득 관련 미지급금 변동", "999"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [(movement.account_key, movement.movement_role, movement.amount) for movement in inputs.note_movements] == [
        ("property_plant_equipment", "noncash_payable", -1209),
        ("intangible_assets", "noncash_payable", 22),
        ("property_plant_equipment", "noncash_payable", 999),
        ("intangible_assets", "noncash_payable", 999),
    ]


def test_extract_reconciliation_inputs_reads_asset_note_payable_adjustments():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:31",
                "현금의 유입과 유출이 없는 거래",
                "note",
                "31",
                [
                    ["구분", "당기"],
                    ["유형자산 취득관련 지급어음의 증가(감소)", "(412)"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [(movement.account_key, movement.movement_role, movement.amount) for movement in inputs.note_movements] == [
        ("property_plant_equipment", "noncash_payable", -412),
    ]


def test_extract_reconciliation_inputs_reads_noncash_asset_payable_current_column_when_header_is_second_row():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:36",
                "현금흐름표 현금의 유입과 유출이 없는 중요한 거래",
                "note",
                "36",
                [
                    ["(단위: 천원)", "(단위: 천원)", "(단위: 천원)"],
                    ["거래내용", "당기", "전기"],
                    ["유형자산 취득 미지급금", "3,035", "120,139"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [
        (movement.account_key, movement.movement_role, movement.amount, movement.source)
        for movement in inputs.note_movements
    ] == [
        (
            "property_plant_equipment",
            "noncash_payable",
            3035,
            "note:36/table:0/row:2/col:1",
        ),
        (
            "property_plant_equipment",
            "noncash_payable_decrease_candidate",
            3035,
            "note:36/table:0/row:2/col:1",
        ),
    ]


def test_extract_reconciliation_inputs_reads_noncash_intangible_transfer_adjustments():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:31",
                "현금의 유입과 유출이 없는 거래",
                "note",
                "31",
                [
                    ["구분", "당기"],
                    ["건설중인자산의 무형자산 대체", "600"],
                    ["리스부채의 유동성 대체", "1,000"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [(movement.account_key, movement.movement_role, movement.amount) for movement in inputs.note_movements] == [
        ("intangible_assets", "noncash_transfer_acquisition", 600),
    ]


def test_extract_reconciliation_inputs_reads_noncash_transfer_label_from_detail_column():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:25",
                "현금흐름표 현금의 유입과 유출이 없는 중요한 거래 내역",
                "note",
                "25",
                [
                    ["", "", "공시금액"],
                    ["거래내역", "거래내역", ""],
                    ["거래내역", "선급금의 무형자산 대체", "6,867"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [
        (movement.account_key, movement.movement_role, movement.label, movement.amount, movement.source)
        for movement in inputs.note_movements
    ] == [
        (
            "intangible_assets",
            "noncash_transfer_acquisition",
            "선급금의 무형자산 대체",
            6867,
            "note:25/table:0/row:2/col:2",
        )
    ]


def test_extract_reconciliation_inputs_reads_asset_rollforward_transfer_adjustments():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:10",
                "유형자산",
                "note",
                "10",
                [
                    ["", "건설중인자산", "유형자산 합계"],
                    ["취득", "2,180", "14,401"],
                    ["재고자산과의 대체에 따른 증가(감소), 유형자산", "(48)", "(48)"],
                    ["무형자산과의 대체에 따른 증가(감소), 유형자산", "(115)", "(115)"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [
        (movement.account_key, movement.movement_role, movement.label, movement.amount)
        for movement in inputs.note_movements
    ] == [
        ("property_plant_equipment", "acquisition", "취득", 14_401),
        (
            "property_plant_equipment",
            "rollforward_transfer_acquisition",
            "재고자산과의 대체에 따른 증가(감소), 유형자산",
            -48,
        ),
        (
            "property_plant_equipment",
            "rollforward_transfer_acquisition",
            "무형자산과의 대체에 따른 증가(감소), 유형자산",
            -115,
        ),
    ]


def test_extract_reconciliation_inputs_keeps_disposal_and_transfer_row_as_disposal():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:13",
                "유형자산",
                "note",
                "13",
                [
                    ["구분", "유형자산 합계"],
                    ["취득", "154,940"],
                    ["처분 및 대체 등", "(3,415)"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [
        (movement.account_key, movement.movement_role, movement.label, movement.amount)
        for movement in inputs.note_movements
    ] == [
        ("property_plant_equipment", "acquisition", "취득", 154_940),
        ("property_plant_equipment", "disposal", "처분 및 대체 등", -3_415),
    ]


def test_extract_reconciliation_inputs_reads_right_of_use_asset_additions_from_noncash_transaction_table():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:31",
                "현금의 유출입이 없는 주요 거래 내역",
                "note",
                "31",
                [
                    ["구분", "당기"],
                    ["사용권자산의 추가", "7,476,211"],
                    ["리스부채의 유동성 대체", "1,000"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [
        (movement.account_key, movement.movement_role, movement.label, movement.amount)
        for movement in inputs.note_movements
    ] == [
        (
            "property_plant_equipment",
            "right_of_use_noncash_acquisition",
            "사용권자산의 추가",
            7_476_211,
        )
    ]


def test_extract_reconciliation_inputs_reads_right_of_use_asset_lease_liability_transfer_as_noncash_acquisition():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:35",
                "영업으로부터 창출된 현금 등 현금유출입이 없는 거래",
                "note",
                "35",
                [
                    ["", "공시금액"],
                    ["리스부채의 유동성 대체", "3,239,129"],
                    ["사용권자산 리스부채로의 대체", "536,747"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [
        (movement.account_key, movement.movement_role, movement.label, movement.amount)
        for movement in inputs.note_movements
    ] == [
        (
            "property_plant_equipment",
            "right_of_use_noncash_acquisition",
            "사용권자산 리스부채로의 대체",
            536_747,
        )
    ]


def test_extract_reconciliation_inputs_reads_right_of_use_asset_disposal_from_ppe_rollforward():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:13",
                "유형자산",
                "note",
                "13",
                [
                    ["", "기계장치", "사용권자산", "유형자산 합계"],
                    ["기초", "2,000", "300", "2,300"],
                    ["처분", "(492)", "(6)", "(528)"],
                    ["기말", "1,508", "294", "1,772"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert sorted([
        (movement.account_key, movement.movement_role, movement.label, movement.amount, movement.source)
        for movement in inputs.note_movements
    ]) == sorted([
        ("property_plant_equipment", "disposal", "처분", -528, "note:13/table:0/row:2/col:3"),
        (
            "property_plant_equipment",
            "right_of_use_noncash_disposal",
            "사용권자산 처분",
            -6,
            "note:13/table:0/row:2/col:2",
        ),
    ])


def test_extract_reconciliation_inputs_reads_government_grant_disposal_from_ppe_rollforward():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
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
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert sorted([
        (movement.account_key, movement.movement_role, movement.label, movement.amount, movement.source)
        for movement in inputs.note_movements
    ]) == sorted([
        ("property_plant_equipment", "disposal", "유형자산 합계 처분", -90, "note:11/table:0/row:3/col:6"),
        (
            "property_plant_equipment",
            "government_grant_disposal",
            "정부보조금 처분",
            10,
            "note:11/table:0/row:2/col:6",
        ),
    ])


def test_extract_reconciliation_inputs_reads_rollforward_movement_columns_from_total_row():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:10",
                "유형자산",
                "note",
                "10",
                [
                    ["", "", "기초", "취득 등", "상각", "처분", "기말"],
                    ["유형자산", "토지", "100", "0", "0", "0", "100"],
                    ["유형자산", "건설중인자산", "50", "68", "0", "0", "118"],
                    ["유형자산 합계", "유형자산 합계", "150", "68", "(10)", "(2)", "206"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [
        (movement.account_key, movement.movement_role, movement.label, movement.amount)
        for movement in inputs.note_movements
    ] == [
        ("property_plant_equipment", "acquisition", "유형자산 합계 취득 등", 68),
        ("property_plant_equipment", "disposal", "유형자산 합계 처분", -2),
    ]


def test_extract_reconciliation_inputs_excludes_combined_disposal_impairment_columns():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:10",
                "유형자산",
                "note",
                "10",
                [
                    ["", "", "기초", "취득", "처분, 손상 및 폐기", "기말"],
                    ["유형자산 합계", "유형자산 합계", "1,000", "300", "(200)", "1,100"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [
        (movement.account_key, movement.movement_role, movement.label, movement.amount)
        for movement in inputs.note_movements
    ] == [
        ("property_plant_equipment", "acquisition", "유형자산 합계 취득", 300),
    ]


def test_extract_reconciliation_inputs_excludes_government_grant_acquisition_rows():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:10",
                "유형자산",
                "note",
                "10",
                [
                    ["구분", "금액"],
                    ["취득 시 인식한 정부보조금", "10"],
                    ["취득 및 자본적지출", "1,000"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [(movement.movement_role, movement.label, movement.amount) for movement in inputs.note_movements] == [
        ("acquisition", "취득 및 자본적지출", 1000),
    ]


def test_extract_reconciliation_inputs_excludes_right_of_use_table_from_ppe_cashflow_movements():
    ppe_table = ReportTable(
        0,
        [["구분", "유형자산 합계"], ["취득", "1,000"]],
        "유형자산의 변동내역 당기",
        SourceLocation("note:12", 0, 0),
    )
    rou_table = ReportTable(
        1,
        [["구분", "자산 합계"], ["취득", "300"]],
        "사용권자산에 대한 양적 정보 공시 당기",
        SourceLocation("note:12", 0, 1),
    )
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            ReportSection(
                "note:12",
                "유형자산",
                "note",
                "12",
                [
                    ReportBlock("table", "", ppe_table, ppe_table.location),
                    ReportBlock("table", "", rou_table, rou_table.location),
                ],
            ),
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [(movement.account_key, movement.movement_role, movement.amount) for movement in inputs.note_movements] == [
        ("property_plant_equipment", "acquisition", 1000),
        ("property_plant_equipment", "right_of_use_noncash_acquisition", 300),
    ]


def test_extract_reconciliation_inputs_prefers_net_carrying_amount_for_trade_receivables():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:8",
                "매출채권 및 계약자산",
                "note",
                "8",
                [
                    ["", "총장부금액", "손상차손누계액", "장부금액 합계"],
                    ["유동매출채권", "3,038,640,727", "(90,942,023)", "2,947,698,704"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [(balance.label, balance.amount) for balance in inputs.note_balances] == [
        ("유동매출채권", 2_947_698_704)
    ]


def test_extract_reconciliation_inputs_reads_current_other_receivables_in_trade_receivable_note():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
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
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert [(balance.label, balance.amount) for balance in inputs.note_balances] == [
        ("유동매출채권", 106_818_060),
        ("기타 유동채권", 3_101_268),
        ("유동 계약자산 외의 유동 미수수익", 564_051),
        ("기타 비유동채권", 0),
    ]


def test_extract_reconciliation_inputs_sums_current_trade_receivable_current_and_noncurrent_columns():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:8",
                "매출채권",
                "note",
                "8",
                [
                    ["구분", "당기말", "당기말", "전기말", "전기말"],
                    ["구분", "유동", "비유동", "유동", "비유동"],
                    ["외상매출금", "60,387,183", "2,290,878", "43,664,600", "3,216,689"],
                    ["대손충당금", "(6,917,939)", "(885,450)", "(2,547,852)", "(1,483,109)"],
                    ["합계", "53,469,244", "1,405,428", "41,116,748", "1,733,580"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert ("합계", 54_874_672) in [
        (balance.label, balance.amount) for balance in inputs.note_balances
    ]


def test_extract_reconciliation_inputs_prefers_current_net_amount_in_trade_receivable_header_band():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
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
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert ("매출채권", 42_023_856) in [
        (balance.label, balance.amount) for balance in inputs.note_balances
    ]
    assert ("합계", 46_021_945) in [
        (balance.label, balance.amount) for balance in inputs.note_balances
    ]
    assert ("합계", 92_043_890) not in [
        (balance.label, balance.amount) for balance in inputs.note_balances
    ]


def test_extract_reconciliation_inputs_reads_trade_receivables_from_financial_instrument_rows():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:37",
                "금융상품의 공정가치 및 범주별 분류",
                "note",
                "37",
                [
                    ["", "", "장부금액", "공정가치"],
                    ["상각후원가측정", "현금및현금성자산", "12,681", "-"],
                    ["상각후원가측정", "매출채권및기타채권", "215,158", "-"],
                    ["상각후원가측정", "기타금융자산", "3,821", "-"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert ("trade_receivables", "매출채권및기타채권", 215158) in [
        (balance.account_key, balance.label, balance.amount)
        for balance in inputs.note_balances
    ]


def test_extract_reconciliation_inputs_reads_trade_receivables_from_fourth_financial_instrument_label_cell():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:10",
                "금융상품",
                "note",
                "10",
                [
                    ["구분", "분류", "계정", "항목", "당기말"],
                    ["금융자산, 범주", "상각후원가로 측정하는 금융자산", "금융상품", "매출채권", "268,201,105"],
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert ("trade_receivables", "매출채권", 268_201_105) in [
        (balance.account_key, balance.label, balance.amount)
        for balance in inputs.note_balances
    ]


def test_extract_reconciliation_inputs_reads_intangible_balance_excluding_goodwill_from_combined_table():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
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
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert ("intangible_assets", "기말 무형자산 및 영업권", 27_646_934) in [
        (balance.account_key, balance.label, balance.amount)
        for balance in inputs.note_balances
    ]
