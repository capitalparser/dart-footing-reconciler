from dart_footing_reconciler.document import (
    FullReport,
    ReportBlock,
    ReportSection,
    ReportTable,
    SourceLocation,
)
from dart_footing_reconciler.taxonomy import classify_report


def _section(section_id, title, kind, note_no, table):
    return ReportSection(
        section_id,
        title,
        kind,
        note_no,
        [ReportBlock("table", "", table, table.location)],
    )


def test_classify_report_maps_statement_accounts_and_note_topics_to_canonical_keys():
    statement = _section(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "당기"], ["유형자산(순액)", "1,000"], ["무형자산", "200"]],
            "재무상태표",
            SourceLocation("statement:bs", 0, 0),
        ),
    )
    notes = [
        _section(
            "note:11",
            "유형자산 및 사용권자산",
            "note",
            "11",
            ReportTable(
                1,
                [["구분", "합계"], ["기말 장부금액", "1,000"]],
                "11. 유형자산 및 사용권자산",
                SourceLocation("note:11", 0, 1),
            ),
        ),
        _section(
            "note:12",
            "무형자산",
            "note",
            "12",
            ReportTable(
                2,
                [["구분", "합계"], ["기말 장부금액", "200"]],
                "12. 무형자산",
                SourceLocation("note:12", 0, 2),
            ),
        ),
    ]

    classified = classify_report(FullReport("sample.html", "Sample Co", [statement], notes))

    assert [(line.account_key, line.label, line.amount) for line in classified.statement_lines] == [
        ("property_plant_equipment", "유형자산(순액)", 1000),
        ("intangible_assets", "무형자산", 200),
    ]
    assert [(topic.topic_key, topic.note_no, topic.title) for topic in classified.note_topics] == [
        ("property_plant_equipment", "11", "유형자산 및 사용권자산"),
        ("intangible_assets", "12", "무형자산"),
    ]


def test_classify_report_does_not_overmatch_revenue_related_substrings():
    statements = [
        _section(
            "statement:pl",
            "손익계산서",
            "statement",
            "",
            ReportTable(
                0,
                [["구분", "당기"], ["매출액", "1,000"], ["기타수익", "30"], ["금융수익", "20"]],
                "손익계산서",
                SourceLocation("statement:pl", 0, 0),
            ),
        )
    ]
    notes = [
        _section(
            "note:7",
            "매출채권 및 계약자산",
            "note",
            "7",
            ReportTable(1, [["구분", "금액"], ["매출채권", "100"]], "7. 매출채권", SourceLocation("note:7", 0, 1)),
        ),
        _section(
            "note:24",
            "법인세비용(수익) 및 이연법인세",
            "note",
            "24",
            ReportTable(2, [["구분", "금액"], ["법인세수익", "50"]], "24. 법인세", SourceLocation("note:24", 0, 2)),
        ),
        _section(
            "note:29",
            "고객과의 계약에서 생기는 수익과 계약자산 및 계약부채",
            "note",
            "29",
            ReportTable(3, [["구분", "금액"], ["매출액", "1,000"]], "29. 수익", SourceLocation("note:29", 0, 3)),
        ),
    ]

    classified = classify_report(FullReport("sample.html", "Sample Co", statements, notes))

    assert [(line.account_key, line.label) for line in classified.statement_lines] == [
        ("revenue", "매출액"),
        ("other_operating_income", "기타수익"),
        ("finance_income", "금융수익"),
    ]
    assert [(topic.topic_key, topic.note_no) for topic in classified.note_topics] == [
        ("trade_receivables", "7"),
        ("income_tax_expense_benefit", "24"),
        ("revenue", "29")
    ]


def test_classify_report_maps_trade_receivables_inside_trade_and_other_receivables_note():
    statements = [
        _section(
            "statement:bs",
            "재무상태표",
            "statement",
            "",
            ReportTable(
                0,
                [["구분", "당기"], ["매출채권", "300"]],
                "재무상태표",
                SourceLocation("statement:bs", 0, 0),
            ),
        )
    ]
    notes = [
        _section(
            "note:8",
            "매출채권 및 기타채권",
            "note",
            "8",
            ReportTable(
                1,
                [["구분", "금액"], ["매출채권", "300"], ["미수금", "50"], ["대손충당금", "(10)"]],
                "8. 매출채권 및 기타채권",
                SourceLocation("note:8", 0, 1),
            ),
        )
    ]

    classified = classify_report(FullReport("sample.html", "Sample Co", statements, notes))

    assert [(line.account_key, line.label) for line in classified.statement_lines] == [
        ("trade_receivables", "매출채권")
    ]
    assert [(topic.topic_key, topic.note_no, topic.title) for topic in classified.note_topics] == [
        ("trade_receivables", "8", "매출채권 및 기타채권")
    ]
    assert [(amount.account_key, amount.label, amount.amount) for amount in classified.note_amounts] == [
        ("trade_receivables", "매출채권", 300)
    ]


def test_classify_report_uses_net_carrying_amount_after_loss_allowance():
    notes = [
        _section(
            "note:8",
            "매출채권 및 계약자산",
            "note",
            "8",
            ReportTable(
                1,
                [
                    ["", "", "총장부금액", "대손충당금"],
                    ["유동 매출채권 및 계약자산", "유동매출채권", "1,477,463,774", "(44,303,549)", "1,433,160,225"],
                ],
                "8. 매출채권 및 계약자산 (1) 장부금액과 대손충당금의 내역",
                SourceLocation("note:8", 0, 1),
                unit_multiplier=1000,
            ),
        )
    ]

    classified = classify_report(FullReport("sample.html", "Sample Co", [], notes))

    assert [(amount.account_key, amount.label, amount.amount) for amount in classified.note_amounts] == [
        ("trade_receivables", "유동 매출채권 및 계약자산", 1433160225000)
    ]


def test_classify_report_uses_fsc_acode_when_label_is_not_canonical():
    statements = [
        _section(
            "statement:bs",
            "재무상태표",
            "statement",
            "",
            ReportTable(
                0,
                [["구분", "당기"], ["영업채권", "300"]],
                "재무상태표",
                SourceLocation("statement:bs", 0, 0),
                row_acodes=[
                    ["||||", "||||"],
                    ["||||", "ifrs-full_CurrentTradeReceivables|CFY|0|KRW|"],
                ],
            ),
        )
    ]

    classified = classify_report(FullReport("sample.html", "Sample Co", statements, []))

    assert [(line.account_key, line.label, line.amount) for line in classified.statement_lines] == [
        ("trade_receivables", "영업채권", 300)
    ]
    assert classified.statement_lines[0].evidence == "statement acode matched canonical FSC code: ifrs-full_CurrentTradeReceivables"


def test_classify_report_maps_cash_and_cash_equivalents_to_canonical_account():
    statements = [
        _section(
            "statement:bs",
            "재무상태표",
            "statement",
            "",
            ReportTable(
                0,
                [["구분", "당기"], ["현금및현금성자산", "290,135"]],
                "재무상태표",
                SourceLocation("statement:bs", 0, 0),
                row_acodes=[
                    ["||||", "||||"],
                    ["||||", "ifrs-full_CashAndCashEquivalents|CFY|0|KRW|"],
                ],
            ),
        )
    ]

    classified = classify_report(FullReport("sample.html", "Sample Co", statements, []))

    assert [(line.account_key, line.display_name, line.amount) for line in classified.statement_lines] == [
        ("cash_and_cash_equivalents", "현금및현금성자산", 290135)
    ]
    assert (
        classified.statement_lines[0].evidence
        == "statement acode matched canonical FSC code: ifrs-full_CashAndCashEquivalents"
    )


def test_classify_report_keeps_entity_extension_acode_as_generic_statement_account():
    statements = [
        _section(
            "statement:oci",
            "포괄손익계산서",
            "statement",
            "",
            ReportTable(
                0,
                [["구분", "당기"], ["파생상품평가손익", "484"]],
                "포괄손익계산서",
                SourceLocation("statement:oci", 0, 0),
                row_acodes=[
                    ["||||", "||||"],
                    ["||||", "entity001234_GainLossOnValuationOfDerivativesNetOfTax|CFY|0|KRW|"],
                ],
            ),
        )
    ]

    classified = classify_report(FullReport("sample.html", "Sample Co", statements, []))

    assert [(line.display_name, line.amount) for line in classified.statement_lines] == [
        ("파생상품평가손익", 484)
    ]
    assert classified.statement_lines[0].account_key.startswith("fsc:entity001234")


def test_classify_report_links_cash_statement_account_to_matching_note_row():
    statements = [
        _section(
            "statement:bs",
            "재무상태표",
            "statement",
            "",
            ReportTable(
                0,
                [["구분", "당기"], ["현금및현금성자산", "290,135,224,989"]],
                "재무상태표",
                SourceLocation("statement:bs", 0, 0),
                row_acodes=[
                    ["||||", "||||"],
                    ["||||", "ifrs-full_CashAndCashEquivalents|CFY|0|KRW|"],
                ],
            ),
        )
    ]
    notes = [
        _section(
            "note:7",
            "금융상품",
            "note",
            "7",
            ReportTable(
                1,
                [["구분", "금액"], ["현금및현금성자산", "290,135,225"]],
                "금융자산의 범주별 장부금액",
                SourceLocation("note:7", 0, 1),
                unit_multiplier=1000,
            ),
        )
    ]

    classified = classify_report(FullReport("sample.html", "Sample Co", statements, notes))

    assert [(amount.account_key, amount.label, amount.amount) for amount in classified.note_amounts] == [
        ("cash_and_cash_equivalents", "현금및현금성자산", 290135225000)
    ]


def test_classify_report_prefers_carrying_amount_table_over_risk_exposure_policy_table():
    statements = [
        _section(
            "statement:bs",
            "재무상태표",
            "statement",
            "",
            ReportTable(
                0,
                [["구분", "당기"], ["당기손익-공정가치측정금융자산", "1,220,780,098"]],
                "재무상태표",
                SourceLocation("statement:bs", 0, 0),
                row_acodes=[
                    ["||||", "||||"],
                    ["||||", "ifrs-full_CurrentFinancialAssetsAtFairValueThroughProfitOrLoss|CFY|0|KRW|"],
                ],
            ),
        )
    ]
    notes = [
        _section(
            "note:policy:risk",
            "중요한 회계정책",
            "note",
            "2",
            ReportTable(
                1,
                [["", "최대노출금액"], ["당기손익-공정가치측정금융자산", "1,220,780"]],
                "2. 중요한 회계정책 (2) 신용위험",
                SourceLocation("note:policy:risk", 0, 1),
                unit_multiplier=1000,
            ),
        ),
        _section(
            "note:financial-assets",
            "금융상품",
            "note",
            "7",
            ReportTable(
                2,
                [
                    ["", "상각후원가", "당기손익인식금융자산", "합계"],
                    ["당기손익-공정가치측정금융자산", "0", "1,220,780", "49,153,191"],
                ],
                "금융자산의 범주별 장부금액",
                SourceLocation("note:financial-assets", 0, 2),
                unit_multiplier=1000,
            ),
        ),
    ]

    classified = classify_report(FullReport("sample.html", "Sample Co", statements, notes))

    assert [(topic.note_no, topic.title) for topic in classified.note_topics] == [
        ("7", "금융자산의 범주별 장부금액 당기손익-공정가치측정금융자산")
    ]
    assert [(amount.note_no, amount.amount) for amount in classified.note_amounts] == [
        ("7", 1220780000)
    ]


def test_classify_report_does_not_link_structural_subtotals_by_amount_only():
    statements = [
        _section(
            "statement:bs",
            "재무상태표",
            "statement",
            "",
            ReportTable(
                0,
                [["구분", "당기"], ["부채총계", "5,000"]],
                "재무상태표",
                SourceLocation("statement:bs", 0, 0),
                row_acodes=[
                    ["||||", "||||"],
                    ["||||", "ifrs-full_Liabilities|CFY|0|KRW|"],
                ],
            ),
        )
    ]
    notes = [
        _section(
            "note:30",
            "자본위험관리",
            "note",
            "30",
            ReportTable(
                1,
                [["구분", "금액"], ["부채총계", "5,000"]],
                "자본위험관리",
                SourceLocation("note:30", 0, 1),
            ),
        )
    ]

    classified = classify_report(FullReport("sample.html", "Sample Co", statements, notes))

    assert [(line.display_name, line.amount) for line in classified.statement_lines] == [
        ("부채총계", 5000)
    ]
    assert classified.note_topics == []
    assert classified.note_amounts == []


def test_classify_report_links_generic_fsc_account_to_note_candidate_by_label_without_amount():
    statements = [
        _section(
            "statement:bs",
            "재무상태표",
            "statement",
            "",
            ReportTable(
                0,
                [["구분", "당기"], ["계약부채", "900"]],
                "재무상태표",
                SourceLocation("statement:bs", 0, 0),
                row_acodes=[
                    ["||||", "||||"],
                    ["||||", "ifrs-full_ContractLiabilities|CFY|0|KRW|"],
                ],
            ),
        )
    ]
    notes = [
        _section(
            "note:20",
            "고객과의 계약에서 생기는 수익",
            "note",
            "20",
            ReportTable(
                1,
                [["구분", "전기"], ["계약부채", "800"]],
                "계약자산 및 계약부채",
                SourceLocation("note:20", 0, 1),
            ),
        )
    ]

    classified = classify_report(FullReport("sample.html", "Sample Co", statements, notes))

    assert ("fsc:ifrs-fullcontractliabilities", "계약자산 및 계약부채") in [
        (topic.topic_key, topic.title) for topic in classified.note_topics
    ]
    assert classified.note_amounts == []


def test_classify_report_links_generic_fsc_account_to_note_candidate_by_core_label():
    statements = [
        _section(
            "statement:bs",
            "재무상태표",
            "statement",
            "",
            ReportTable(
                0,
                [["구분", "당기"], ["이연법인세자산", "900"]],
                "재무상태표",
                SourceLocation("statement:bs", 0, 0),
                row_acodes=[
                    ["||||", "||||"],
                    ["||||", "ifrs-full_DeferredTaxAssets|CFY|0|KRW|"],
                ],
            ),
        )
    ]
    notes = [
        _section(
            "note:24",
            "법인세비용 및 이연법인세",
            "note",
            "24",
            ReportTable(
                1,
                [["구분", "금액"], ["일시적차이", "100"]],
                "이연법인세 변동내역",
                SourceLocation("note:24", 0, 1),
            ),
        )
    ]

    classified = classify_report(FullReport("sample.html", "Sample Co", statements, notes))

    assert ("income_tax_expense_benefit", "법인세비용 및 이연법인세") in [
        (topic.topic_key, topic.title) for topic in classified.note_topics
    ]


def test_classify_report_maps_balance_sheet_tax_contract_and_other_asset_accounts():
    statements = [
        _section(
            "statement:bs",
            "재무상태표",
            "statement",
            "",
            ReportTable(
                0,
                [
                    ["구분", "당기"],
                    ["미청구공사", "74,336"],
                    ["기타유동자산", "21,981"],
                    ["당기법인세자산", "938"],
                    ["이연법인세자산", "17,465"],
                    ["당기법인세부채", "25,824"],
                    ["이연법인세부채", "6,300"],
                ],
                "재무상태표",
                SourceLocation("statement:bs", 0, 0),
            ),
        )
    ]
    notes = [
        _section(
            "note:26",
            "고객과의 계약에서 생기는 수익",
            "note",
            "26",
            ReportTable(
                1,
                [["구분", "금액"], ["미청구공사", "74,336"]],
                "고객과의 계약체결원가나 계약이행원가 중에서 인식한 자산의 공시",
                SourceLocation("note:26", 0, 1),
            ),
        ),
        _section(
            "note:11",
            "기타유동자산 및 기타비유동자산",
            "note",
            "11",
            ReportTable(
                2,
                [["구분", "금액"], ["기타유동자산", "21,981"]],
                "기타유동자산 및 기타비유동자산 내역",
                SourceLocation("note:11", 0, 2),
            ),
        ),
        _section(
            "note:31",
            "법인세",
            "note",
            "31",
            ReportTable(
                3,
                [
                    ["구분", "금액"],
                    ["회수가능성이 높은 법인세자산", "938"],
                    ["순이연법인세자산", "17,465"],
                    ["이연법인세부채", "6,300"],
                ],
                "법인세 불확실성과 이연법인세자산과 부채의 회수 및 결제 시기",
                SourceLocation("note:31", 0, 3),
            ),
        ),
    ]

    classified = classify_report(FullReport("sample.html", "Sample Co", statements, notes))

    assert [(line.account_key, line.label) for line in classified.statement_lines] == [
        ("contract_assets", "미청구공사"),
        ("other_assets", "기타유동자산"),
        ("current_tax_assets", "당기법인세자산"),
        ("deferred_tax_assets", "이연법인세자산"),
        ("current_tax_liabilities", "당기법인세부채"),
        ("deferred_tax_liabilities", "이연법인세부채"),
    ]
    assert ("contract_assets", "26") in [
        (topic.topic_key, topic.note_no) for topic in classified.note_topics
    ]
    assert ("other_assets", "11") in [
        (topic.topic_key, topic.note_no) for topic in classified.note_topics
    ]
    assert ("deferred_tax_assets", "31") in [
        (topic.topic_key, topic.note_no) for topic in classified.note_topics
    ]
    assert ("deferred_tax_liabilities", "31") in [
        (topic.topic_key, topic.note_no) for topic in classified.note_topics
    ]
    assert ("current_tax_assets", "회수가능성이 높은 법인세자산", 938) in [
        (amount.account_key, amount.label, amount.amount) for amount in classified.note_amounts
    ]
    assert ("deferred_tax_assets", "순이연법인세자산", 17465) in [
        (amount.account_key, amount.label, amount.amount) for amount in classified.note_amounts
    ]
    assert ("deferred_tax_liabilities", "이연법인세부채", 6300) in [
        (amount.account_key, amount.label, amount.amount) for amount in classified.note_amounts
    ]


def test_classify_report_prefers_current_fiscal_period_column():
    statements = [
        _section(
            "statement:bs",
            "재무상태표",
            "statement",
            "",
            ReportTable(
                0,
                [["", "제 114 기", "제 113 기", "제 112 기"], ["유형자산", "3,000", "2,000", "1,000"]],
                "재무상태표",
                SourceLocation("statement:bs", 0, 0),
            ),
        )
    ]

    classified = classify_report(FullReport("sample.html", "Sample Co", statements, []))

    assert [(line.account_key, line.amount) for line in classified.statement_lines] == [
        ("property_plant_equipment", 3000)
    ]


def test_classify_report_does_not_treat_profit_or_loss_category_as_current_period():
    notes = [
        _section(
            "note:7",
            "매출채권",
            "note",
            "7",
            ReportTable(
                0,
                [
                    ["", "상각후원가", "당기손익인식금융자산"],
                    ["매출채권", "1,000", "0", "1,000"],
                ],
                "금융자산의 범주별 장부금액",
                SourceLocation("note:7", 0, 0),
            ),
        )
    ]

    classified = classify_report(FullReport("sample.html", "Sample Co", [], notes))

    assert [(amount.account_key, amount.amount) for amount in classified.note_amounts] == [
        ("trade_receivables", 1000)
    ]


def test_classify_report_infers_note_amounts_from_table_heading_and_acode():
    notes = [
        _section(
            "note:1",
            "일반사항",
            "note",
            "1",
            ReportTable(
                1,
                [["구분", "합계"], ["영업채권", "1,000"]],
                "금융자산의 범주별 장부금액",
                SourceLocation("note:1", 0, 1),
                row_acodes=[
                    ["||||", "||||"],
                    ["||||", "ifrs-full_TradeReceivables|CFY|0|KRW|"],
                ],
            ),
        )
    ]

    classified = classify_report(FullReport("sample.html", "Sample Co", [], notes))

    assert [(topic.topic_key, topic.title) for topic in classified.note_topics] == [
        ("trade_receivables", "금융자산의 범주별 장부금액")
    ]
    assert [(amount.account_key, amount.label, amount.amount) for amount in classified.note_amounts] == [
        ("trade_receivables", "영업채권", 1000)
    ]


def test_classify_report_maps_income_tax_expense_and_benefit_variants():
    statements = [
        _section(
            "statement:pl",
            "손익계산서",
            "statement",
            "",
            ReportTable(
                0,
                [
                    ["구분", "당기"],
                    ["법인세비용(수익)", "(50)"],
                    ["법인세수익", "20"],
                ],
                "손익계산서",
                SourceLocation("statement:pl", 0, 0),
            ),
        )
    ]
    notes = [
        _section(
            "note:24",
            "법인세비용(수익) 및 이연법인세",
            "note",
            "24",
            ReportTable(
                1,
                [
                    ["구분", "금액"],
                    ["법인세비용차감전순이익", "1,000"],
                    ["각 나라의 국내법인세율로 계산된 법인세비용", "200"],
                    ["당기법인세비용", "100"],
                    ["이연법인세수익", "(150)"],
                    ["법인세비용(수익) 합계", "(50)"],
                ],
                "24. 법인세",
                SourceLocation("note:24", 0, 1),
            ),
        )
    ]

    classified = classify_report(FullReport("sample.html", "Sample Co", statements, notes))

    assert [(line.account_key, line.label) for line in classified.statement_lines] == [
        ("income_tax_expense_benefit", "법인세비용(수익)"),
        ("income_tax_expense_benefit", "법인세수익"),
    ]
    assert [(topic.topic_key, topic.note_no) for topic in classified.note_topics] == [
        ("income_tax_expense_benefit", "24")
    ]
    assert [(amount.account_key, amount.label) for amount in classified.note_amounts] == [
        ("income_tax_expense_benefit", "당기법인세비용"),
        ("income_tax_expense_benefit", "이연법인세수익"),
        ("income_tax_expense_benefit", "법인세비용(수익) 합계"),
    ]


def test_classify_report_maps_cost_of_sales_and_sga_to_expense_by_nature_note():
    statements = [
        _section(
            "statement:pl",
            "손익계산서",
            "statement",
            "",
            ReportTable(
                0,
                [
                    ["구분", "당기"],
                    ["매출원가", "(700)"],
                    ["판매 및 일반관리비", "(200)"],
                ],
                "손익계산서",
                SourceLocation("statement:pl", 0, 0),
                row_acodes=[
                    ["||||", "||||"],
                    ["||||", "ifrs-full_CostOfSales|CFY|0|KRW|"],
                    ["||||", "ifrs-full_SellingGeneralAndAdministrativeExpense|CFY|0|KRW|"],
                ],
            ),
        )
    ]
    notes = [
        _section(
            "note:31",
            "비용의 성격별 분류",
            "note",
            "31",
            ReportTable(
                1,
                [["", "", "공시금액"], ["성격별 비용 합계", "성격별 비용 합계", "900"]],
                "31. 비용의 성격별 분류",
                SourceLocation("note:31", 0, 1),
            ),
        )
    ]

    classified = classify_report(FullReport("sample.html", "Sample Co", statements, notes))

    assert [(line.account_key, line.label) for line in classified.statement_lines] == [
        ("cost_of_sales", "매출원가"),
        ("selling_general_admin", "판매 및 일반관리비"),
    ]
    topics = [(topic.topic_key, topic.note_no) for topic in classified.note_topics]
    assert ("cost_of_sales", "31") in topics
    assert ("selling_general_admin", "31") in topics


def test_classify_report_expands_parenthetical_profit_loss_variants():
    statements = [
        _section(
            "statement:pl",
            "손익계산서",
            "statement",
            "",
            ReportTable(
                0,
                [
                    ["구분", "당기"],
                    ["기본주당손실", "(120)"],
                    ["희석주당이익", "80"],
                ],
                "손익계산서",
                SourceLocation("statement:pl", 0, 0),
            ),
        )
    ]
    notes = [
        _section(
            "note:40",
            "주당이익(손실)",
            "note",
            "40",
            ReportTable(
                1,
                [["구분", "금액"], ["기본주당손실", "(120)"], ["희석주당이익", "80"]],
                "40. 주당이익",
                SourceLocation("note:40", 0, 1),
            ),
        )
    ]

    classified = classify_report(FullReport("sample.html", "Sample Co", statements, notes))

    assert [(line.account_key, line.label) for line in classified.statement_lines] == [
        ("earnings_per_share", "기본주당손실"),
        ("earnings_per_share", "희석주당이익"),
    ]
    assert [(topic.topic_key, topic.title) for topic in classified.note_topics] == [
        ("earnings_per_share", "주당이익(손실)")
    ]
    assert [(amount.account_key, amount.label) for amount in classified.note_amounts] == [
        ("earnings_per_share", "기본주당손실"),
        ("earnings_per_share", "희석주당이익"),
    ]


def test_classify_report_keeps_duplicate_note_numbers_with_different_topics_separate():
    notes = [
        _section(
            "note:18",
            "리스부채 (연결)",
            "note",
            "18",
            ReportTable(0, [["구분", "합계"], ["기말", "300"]], "18. 리스부채", SourceLocation("note:18", 0, 0)),
        ),
        _section(
            "note:18",
            "차입금",
            "note",
            "18",
            ReportTable(1, [["구분", "합계"], ["기말", "700"]], "18. 차입금", SourceLocation("note:18", 0, 1)),
        ),
    ]

    classified = classify_report(FullReport("sample.html", "Sample Co", [], notes))

    assert [(amount.account_key, amount.note_title, amount.amount) for amount in classified.note_amounts] == [
        ("lease_liabilities", "리스부채 (연결)", 300),
        ("borrowings", "차입금", 700),
    ]
