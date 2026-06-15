from dart_footing_reconciler.formula_discovery import (
    discover_asset_component_total_formulas,
    discover_component_net_formula,
    discover_credit_risk_exposure_formula,
    discover_credit_risk_exposure_formulas,
    discover_debt_split_formula,
    discover_defined_benefit_rollforward_formulas,
    discover_dividend_payout_formulas,
    discover_discontinued_operation_cashflow_formula,
    discover_discontinued_operation_income_formulas,
    discover_employee_benefit_expense_formulas,
    discover_earnings_per_share_formulas,
    discover_expense_summary_formula,
    discover_financial_category_column_formulas,
    discover_financial_category_formulas,
    discover_financial_fair_value_formula,
    discover_financial_fair_value_level_formulas,
    discover_inventory_carrying_formulas,
    discover_lease_expense_formulas,
    discover_lease_liability_split_formula,
    discover_liquidity_maturity_formulas,
    discover_net_debt_bridge_formulas,
    discover_provision_column_total_formulas,
    discover_receivable_aging_bucket_formulas,
    discover_receivable_carrying_formulas,
    discover_rollforward_formula,
    discover_tax_expense_composition_formulas,
)
from dart_footing_reconciler.verification_candidates import VerificationCandidate


def _candidate(role, amount, confidence=0.9, unit_multiplier=1):
    return VerificationCandidate(
        account_key="property_plant_equipment",
        role=role,
        label=role,
        raw_amount=amount,
        unit_multiplier=unit_multiplier,
        amount=amount,
        note_no="11",
        table_source="note:11/table:0",
        row_index=1,
        column_index=1,
        layout_key="asset_current_period_carrying_amount",
        orientation_key="row_oriented",
        confidence=confidence,
        evidence=("evidence",),
    )


def _account_candidate(account_key, role, amount, unit_multiplier=1):
    return VerificationCandidate(
        account_key=account_key,
        role=role,
        label=f"{account_key} {role}",
        raw_amount=amount,
        unit_multiplier=unit_multiplier,
        amount=amount,
        note_no="29",
        table_source="note:29/table:0",
        row_index=1,
        column_index=1,
        layout_key="net_debt_bridge",
        orientation_key="mixed",
        confidence=0.9,
        evidence=("evidence",),
    )


def _tax_candidate(period, role, label, amount, column_index):
    return VerificationCandidate(
        account_key="income_tax_expense",
        role=role,
        label=f"{label} {period}",
        raw_amount=amount,
        unit_multiplier=1,
        amount=amount,
        note_no="35",
        table_source="note:35/table:0",
        row_index=1,
        column_index=column_index,
        layout_key="tax_expense_composition_summary",
        orientation_key="column_oriented",
        confidence=0.9,
        evidence=("evidence",),
    )


def _eps_candidate(account_key, role, amount, row_index):
    return VerificationCandidate(
        account_key=account_key,
        role=role,
        label=f"{account_key} {role}",
        raw_amount=amount,
        unit_multiplier=1,
        amount=amount,
        note_no="24",
        table_source="note:24/table:121",
        row_index=row_index,
        column_index=1,
        layout_key="earnings_per_share_summary",
        orientation_key="row_oriented",
        confidence=0.9,
        evidence=("evidence",),
    )


def _dividend_candidate(period, role, amount, row_index):
    return VerificationCandidate(
        account_key=f"dividend_payout:{period}",
        role=role,
        label=f"{role} {period}",
        raw_amount=amount,
        unit_multiplier=1,
        amount=amount,
        note_no="6",
        table_source="note:6/table:350",
        row_index=row_index,
        column_index=2,
        layout_key="dividend_payout_summary",
        orientation_key="period_oriented",
        confidence=0.9,
        evidence=("evidence",),
    )


def test_discovers_rollforward_formula_from_candidates():
    formula = discover_rollforward_formula(
        [
            _candidate("beginning", 100),
            _candidate("additions", 50),
            _candidate("depreciation", 10),
            _candidate("ending", 140),
        ],
        tolerance=0,
    )

    assert formula.status == "matched"
    assert formula.expected == 140
    assert formula.actual == 140
    assert formula.difference == 0
    assert formula.formula_key == "rollforward"


def test_discovers_earnings_per_share_formula_with_rounded_won_result():
    formulas = discover_earnings_per_share_formulas(
        [
            _eps_candidate("continuing_basic_eps", "eps_profit", 8_671_234_000, 1),
            _eps_candidate("continuing_basic_eps", "weighted_average_shares", 4_277_208, 2),
            _eps_candidate("continuing_basic_eps", "earnings_per_share", 2_027, 3),
        ],
        tolerance=1,
    )

    assert [
        (formula.formula_key, formula.status, formula.expected, formula.actual, formula.difference)
        for formula in formulas
    ] == [("earnings_per_share", "matched", 2_027, 2_027, 0)]


def test_discovers_dividend_payout_ratio_formula_in_tenth_percent_units():
    formulas = discover_dividend_payout_formulas(
        [
            _dividend_candidate("당기", "dividend_net_income", 29_040, 2),
            _dividend_candidate("당기", "cash_dividends", 17_109, 3),
            _dividend_candidate("당기", "dividend_payout_ratio_tenths", 589, 4),
            _dividend_candidate("전기", "dividend_net_income", 34_053, 2),
            _dividend_candidate("전기", "cash_dividends", 37_326, 3),
            _dividend_candidate("전기", "dividend_payout_ratio_tenths", 1_096, 4),
        ],
        tolerance=1,
    )

    assert [
        (formula.formula_key, formula.status, formula.expected, formula.actual, formula.difference)
        for formula in formulas
    ] == [
        ("dividend_payout_ratio", "matched", 589, 589, 0),
        ("dividend_payout_ratio", "matched", 1_096, 1_096, 0),
    ]


def test_discovers_lease_liability_split_formula():
    formula = discover_lease_liability_split_formula(
        [
            _account_candidate("lease_liabilities", "lease_liability_split_component", 100),
            _account_candidate("lease_liabilities", "lease_liability_split_component", 200),
            _account_candidate("lease_liabilities", "ending", 300),
        ],
        tolerance=1,
    )

    assert (
        formula.formula_key,
        formula.status,
        formula.expected,
        formula.actual,
        formula.difference,
    ) == ("lease_liability_split_total", "matched", 300, 300, 0)


def test_discovers_signed_loss_allowance_rollforward_formula_from_financial_asset_rows():
    formula = discover_rollforward_formula(
        [
            _account_candidate("trade_receivables_loss_allowance", "beginning", -205_922_000, 1000),
            _account_candidate("trade_receivables_loss_allowance", "signed_movement", 66_473_000, 1000),
            _account_candidate("trade_receivables_loss_allowance", "signed_movement", 2_866_000, 1000),
            _account_candidate("trade_receivables_loss_allowance", "signed_movement", -105_000, 1000),
            _account_candidate("trade_receivables_loss_allowance", "signed_movement", 0, 1000),
            _account_candidate("trade_receivables_loss_allowance", "ending", -136_687_000, 1000),
        ],
        tolerance=0,
    )

    assert formula.status == "matched"
    assert formula.expected == -136_687_000
    assert formula.actual == -136_688_000
    assert formula.difference == -1_000


def test_rollforward_formula_reports_unexplained_gap_when_not_closed():
    formula = discover_rollforward_formula(
        [
            _candidate("beginning", 100),
            _candidate("additions", 50),
            _candidate("ending", 120),
        ],
        tolerance=0,
    )

    assert formula.status == "unexplained_gap"
    assert formula.expected == 120
    assert formula.actual == 150
    assert formula.difference == 30


def test_rollforward_formula_blocks_low_confidence_candidates():
    formula = discover_rollforward_formula(
        [
            _candidate("beginning", 100, confidence=0.4),
            _candidate("ending", 100),
        ],
        tolerance=0,
    )

    assert formula.status == "parse_uncertain"
    assert "low-confidence" in formula.reason


def test_discovers_signed_rollforward_formula_from_signed_movements():
    formula = discover_rollforward_formula(
        [
            _candidate("beginning", 100),
            _candidate("signed_movement", 30),
            _candidate("signed_movement", -10),
            _candidate("signed_movement", -40),
            _candidate("ending", 80),
        ],
        tolerance=0,
    )

    assert formula.status == "matched"
    assert formula.formula_key == "signed_rollforward"
    assert formula.expected == 80
    assert formula.actual == 80
    assert formula.difference == 0


def test_discovers_signed_rollforward_accepts_one_display_unit_rounding_difference():
    formula = discover_rollforward_formula(
        [
            _candidate("beginning", 100_000_000, unit_multiplier=1_000_000),
            _candidate("signed_movement", 24_000_000, unit_multiplier=1_000_000),
            _candidate("ending", 125_000_000, unit_multiplier=1_000_000),
        ],
        tolerance=0,
    )

    assert formula.status == "matched"
    assert formula.expected == 125_000_000
    assert formula.actual == 124_000_000
    assert formula.difference == -1_000_000
    assert formula.tolerance == 1_000_000


def test_discovers_component_net_formula_from_cost_accumulated_candidates():
    formula = discover_component_net_formula(
        [
            _candidate("gross_cost", 2_644_087),
            _candidate("accumulated_depreciation", -1_178_732),
            _candidate("accumulated_impairment", -435_261),
            _candidate("ending", 1_030_094),
        ],
        tolerance=0,
    )

    assert formula.status == "matched"
    assert formula.formula_key == "component_net"
    assert formula.expected == 1_030_094
    assert formula.actual == 1_030_094
    assert formula.difference == 0


def test_discovers_debt_split_formula_from_total_and_current_portion():
    formula = discover_debt_split_formula(
        [
            _candidate("debt_total", 6_294_460),
            _candidate("current_portion", -1_223_560),
            _candidate("ending", 5_070_900),
        ],
        tolerance=0,
    )

    assert formula.status == "matched"
    assert formula.formula_key == "debt_split"
    assert formula.expected == 5_070_900
    assert formula.actual == 5_070_900
    assert formula.difference == 0


def test_discovers_debt_component_formula_before_split_when_face_amount_exists():
    formula = discover_debt_split_formula(
        [
            _candidate("face_amount", 160_000_000),
            _candidate("debt_discount", -227_737),
            _candidate("debt_total", 159_772_263),
            _candidate("current_portion", -50_000_000),
            _candidate("ending", 109_772_263),
        ],
        tolerance=0,
    )

    assert formula.status == "matched"
    assert formula.formula_key == "debt_component_split"
    assert formula.expected == 109_772_263
    assert formula.actual == 109_772_263
    assert formula.difference == 0


def test_discovers_debt_component_split_without_intermediate_debt_total():
    formula = discover_debt_split_formula(
        [
            _candidate("face_amount", 466_697_117),
            _candidate("debt_discount", -3_339_418),
            _candidate("current_portion", -58_973_133),
            _candidate("ending", 404_384_566),
        ],
        tolerance=0,
    )

    assert formula.status == "matched"
    assert formula.formula_key == "debt_component_split"
    assert formula.expected == 404_384_566
    assert formula.actual == 404_384_566
    assert formula.difference == 0


def test_discovers_expense_summary_formula_from_components_and_total():
    formula = discover_expense_summary_formula(
        [
            _candidate("expense_component", 100),
            _candidate("expense_component", 30),
            _candidate("expense_component", 20),
            _candidate("expense_total", 150),
        ],
        tolerance=0,
    )

    assert formula.status == "matched"
    assert formula.formula_key == "expense_summary_total"
    assert formula.expected == 150
    assert formula.actual == 150
    assert formula.difference == 0


def test_discovers_employee_benefit_expense_formulas_by_period():
    formulas = discover_employee_benefit_expense_formulas(
        [
            _account_candidate(
                "employee_benefit_expense:당기",
                "employee_benefit_expense_component",
                2_548_827,
            ),
            _account_candidate(
                "employee_benefit_expense:당기",
                "employee_benefit_expense_component",
                641_676,
            ),
            _account_candidate(
                "employee_benefit_expense:당기",
                "employee_benefit_expense_total",
                3_190_503,
            ),
            _account_candidate(
                "employee_benefit_expense:전기",
                "employee_benefit_expense_component",
                2_723_163,
            ),
            _account_candidate(
                "employee_benefit_expense:전기",
                "employee_benefit_expense_component",
                628_174,
            ),
            _account_candidate(
                "employee_benefit_expense:전기",
                "employee_benefit_expense_total",
                3_351_337,
            ),
        ],
        tolerance=0,
    )

    assert [(formula.formula_key, formula.status, formula.actual, formula.expected) for formula in formulas] == [
        ("employee_benefit_expense_total", "matched", 3_190_503, 3_190_503),
        ("employee_benefit_expense_total", "matched", 3_351_337, 3_351_337),
    ]


def test_discovers_net_debt_bridge_formulas_by_account():
    formulas = discover_net_debt_bridge_formulas(
        [
            _account_candidate("current_bonds", "beginning", 100),
            _account_candidate("lease_liabilities", "beginning", 50),
            _account_candidate("long_term_borrowings", "beginning", 70),
            _account_candidate("current_bonds", "signed_movement", -20),
            _account_candidate("lease_liabilities", "signed_movement", -10),
            _account_candidate("long_term_borrowings", "signed_movement", 30),
            _account_candidate("current_bonds", "signed_movement", 5),
            _account_candidate("lease_liabilities", "signed_movement", 3),
            _account_candidate("long_term_borrowings", "signed_movement", 0),
            _account_candidate("current_bonds", "ending", 85),
            _account_candidate("lease_liabilities", "ending", 43),
            _account_candidate("long_term_borrowings", "ending", 100),
        ],
        tolerance=0,
    )

    assert [(formula.formula_key, formula.status, formula.actual, formula.expected) for formula in formulas] == [
        ("signed_rollforward", "matched", 85, 85),
        ("signed_rollforward", "matched", 43, 43),
        ("signed_rollforward", "matched", 100, 100),
    ]
    assert [formula.terms[0].account_key for formula in formulas] == [
        "current_bonds",
        "lease_liabilities",
        "long_term_borrowings",
    ]


def test_discovers_defined_benefit_rollforward_formulas_by_account():
    formulas = discover_defined_benefit_rollforward_formulas(
        [
            _account_candidate("defined_benefit_obligation", "beginning", 100),
            _account_candidate("plan_assets", "beginning", 70),
            _account_candidate("defined_benefit_obligation", "signed_movement", 30),
            _account_candidate("plan_assets", "signed_movement", -10),
            _account_candidate("defined_benefit_obligation", "signed_movement", -5),
            _account_candidate("plan_assets", "signed_movement", 2),
            _account_candidate("defined_benefit_obligation", "ending", 125),
            _account_candidate("plan_assets", "ending", 62),
        ],
        tolerance=0,
    )

    assert [(formula.formula_key, formula.status, formula.actual, formula.expected) for formula in formulas] == [
        ("signed_rollforward", "matched", 125, 125),
        ("signed_rollforward", "matched", 62, 62),
    ]
    assert [formula.terms[0].account_key for formula in formulas] == [
        "defined_benefit_obligation",
        "plan_assets",
    ]


def test_discovers_provision_column_total_formulas_by_current_noncurrent_column():
    formulas = discover_provision_column_total_formulas(
        [
            _account_candidate("current_provisions", "provision_column_component", 100),
            _account_candidate("current_provisions", "provision_column_component", 30),
            _account_candidate("current_provisions", "provision_column_total", 130),
            _account_candidate("noncurrent_provisions", "provision_column_component", 1000),
            _account_candidate("noncurrent_provisions", "provision_column_component", 2000),
            _account_candidate("noncurrent_provisions", "provision_column_total", 3000),
        ],
        tolerance=0,
    )

    assert [(formula.formula_key, formula.status, formula.actual, formula.expected) for formula in formulas] == [
        ("provision_column_total", "matched", 130, 130),
        ("provision_column_total", "matched", 3000, 3000),
    ]
    assert [formula.terms[0].account_key for formula in formulas] == [
        "current_provisions",
        "noncurrent_provisions",
    ]


def test_discovers_asset_component_total_formulas_by_row():
    formulas = discover_asset_component_total_formulas(
        [
            _account_candidate("asset_component_row:차량부품", "asset_component", 26_765),
            _account_candidate("asset_component_row:차량부품", "asset_component", 37_868),
            _account_candidate("asset_component_row:차량부품", "asset_component_total", 64_633),
            _account_candidate("asset_component_row:특수", "asset_component", 3_326),
            _account_candidate("asset_component_row:특수", "asset_component", 519),
            _account_candidate("asset_component_row:특수", "asset_component_total", 3_845),
        ],
        tolerance=0,
    )

    assert [(formula.formula_key, formula.status, formula.actual, formula.expected) for formula in formulas] == [
        ("asset_component_total", "matched", 64_633, 64_633),
        ("asset_component_total", "matched", 3_845, 3_845),
    ]
    assert [formula.terms[0].account_key for formula in formulas] == [
        "asset_component_row:차량부품",
        "asset_component_row:특수",
    ]


def test_discovers_credit_risk_exposure_formula_from_components_and_total():
    formula = discover_credit_risk_exposure_formula(
        [
            _candidate("credit_exposure_component", 100),
            _candidate("credit_exposure_component", 200),
            _candidate("credit_exposure_component", 300),
            _candidate("credit_exposure_total", 600),
        ],
        tolerance=0,
    )

    assert formula.status == "matched"
    assert formula.formula_key == "credit_risk_exposure_total"
    assert formula.expected == 600
    assert formula.actual == 600
    assert formula.difference == 0


def test_discovers_credit_risk_exposure_formulas_by_exposure_row():
    row_one = [
        _account_candidate("cash_and_cash_equivalents", "credit_exposure_component", 100),
        _account_candidate("trade_receivables", "credit_exposure_component", 200),
        _account_candidate("credit_risk_exposure", "credit_exposure_total", 300),
    ]
    row_two = [
        _account_candidate("cash_and_cash_equivalents", "credit_exposure_component", 70),
        _account_candidate("trade_receivables", "credit_exposure_component", 30),
        _account_candidate("credit_risk_exposure", "credit_exposure_total", 100),
    ]
    row_two = [
        candidate.__class__(
            **{
                **candidate.__dict__,
                "row_index": 2,
            }
        )
        for candidate in row_two
    ]

    formulas = discover_credit_risk_exposure_formulas(row_one + row_two, tolerance=0)

    assert [(formula.formula_key, formula.status, formula.actual, formula.expected) for formula in formulas] == [
        ("credit_risk_exposure_total", "matched", 300, 300),
        ("credit_risk_exposure_total", "matched", 100, 100),
    ]
    assert [formula.terms[0].row_index for formula in formulas] == [1, 2]


def test_discovers_financial_fair_value_formula_from_components_and_total():
    formula = discover_financial_fair_value_formula(
        [
            _account_candidate("cash_and_cash_equivalents", "fair_value_component", 83_682_420),
            _account_candidate("short_term_financial_instruments", "fair_value_component", 20_000_000),
            _account_candidate("trade_other_receivables", "fair_value_component", 93_397_239),
            _account_candidate("other_noncurrent_financial_assets", "fair_value_component", 7_976_518),
            _account_candidate("financial_assets", "fair_value_total", 205_056_177),
        ],
        tolerance=0,
    )

    assert formula.status == "matched"
    assert formula.formula_key == "financial_fair_value_total"
    assert formula.expected == 205_056_177
    assert formula.actual == 205_056_177
    assert formula.difference == 0


def test_discovers_financial_fair_value_level_formulas_by_row():
    formulas = discover_financial_fair_value_level_formulas(
        [
            _account_candidate("financial_assets_fvtpl", "fair_value_level_component", 127),
            _account_candidate("financial_assets_fvtpl", "fair_value_level_component", 700),
            _account_candidate("financial_assets_fvtpl", "fair_value_level_component", 3_803),
            _account_candidate("financial_assets_fvtpl", "fair_value_total", 4_630),
        ],
        tolerance=0,
    )

    assert [
        (formula.formula_key, formula.status, formula.expected, formula.actual, formula.difference)
        for formula in formulas
    ] == [("financial_fair_value_level_total", "matched", 4_630, 4_630, 0)]


def test_discovers_tax_expense_composition_formulas_by_period():
    current_components = [
        _tax_candidate("당기", "tax_expense_component", "법인세등 부담액", 11_977_263, 1),
        _tax_candidate("당기", "tax_expense_component", "일시적차이 등으로 인한 이연법인세 변동액", 483_495, 1),
        _tax_candidate("당기", "tax_expense_component", "자본에 직접 가감된 법인세부담액", 183_151, 1),
        _tax_candidate("당기", "tax_expense_total", "법인세비용", 12_643_908, 1),
    ]
    prior_components = [
        _tax_candidate("전기", "tax_expense_component", "법인세등 부담액", 11_998_514, 2),
        _tax_candidate("전기", "tax_expense_component", "일시적차이 등으로 인한 이연법인세 변동액", -1_697_799, 2),
        _tax_candidate("전기", "tax_expense_component", "자본에 직접 가감된 법인세부담액", 1_023_122, 2),
        _tax_candidate("전기", "tax_expense_total", "법인세비용", 11_323_837, 2),
    ]

    formulas = discover_tax_expense_composition_formulas(
        current_components + prior_components,
        tolerance=1,
    )

    assert [
        (formula.formula_key, formula.status, formula.actual, formula.expected)
        for formula in formulas
    ] == [
        ("tax_expense_composition_total", "matched", 12_643_909, 12_643_908),
        ("tax_expense_composition_total", "matched", 11_323_837, 11_323_837),
    ]
    assert [formula.terms[0].column_index for formula in formulas] == [1, 2]


def test_discovers_financial_category_formulas_by_account_row():
    formulas = discover_financial_category_formulas(
        [
            _account_candidate("other_current_financial_assets", "financial_category_component", 10),
            _account_candidate("other_current_financial_assets", "financial_category_component", 20),
            _account_candidate("other_current_financial_assets", "financial_category_component", 30),
            _account_candidate("other_current_financial_assets", "ending", 60),
            _account_candidate("trade_receivables", "financial_category_component", 250),
            _account_candidate("trade_receivables", "ending", 250),
        ],
        tolerance=0,
    )

    assert [(formula.formula_key, formula.status, formula.actual, formula.expected) for formula in formulas] == [
        ("financial_category_total", "matched", 60, 60),
        ("financial_category_total", "matched", 250, 250),
    ]
    assert [formula.terms[0].account_key for formula in formulas] == [
        "other_current_financial_assets",
        "trade_receivables",
    ]


def test_discovers_financial_category_column_formulas_by_category_column():
    formulas = discover_financial_category_column_formulas(
        [
            _account_candidate(
                "financial_category:상각후원가측정금융자산",
                "financial_category_column_component",
                100,
            ),
            _account_candidate(
                "financial_category:상각후원가측정금융자산",
                "financial_category_column_component",
                250,
            ),
            _account_candidate(
                "financial_category:상각후원가측정금융자산",
                "financial_category_column_component",
                30,
            ),
            _account_candidate(
                "financial_category:상각후원가측정금융자산",
                "financial_category_column_total",
                380,
            ),
            _account_candidate(
                "financial_category:당기손익-공정가치측정금융자산",
                "financial_category_column_component",
                20,
            ),
            _account_candidate(
                "financial_category:당기손익-공정가치측정금융자산",
                "financial_category_column_total",
                20,
            ),
        ],
        tolerance=0,
    )

    assert [(formula.formula_key, formula.status, formula.actual, formula.expected) for formula in formulas] == [
        ("financial_category_column_total", "matched", 380, 380),
        ("financial_category_column_total", "matched", 20, 20),
    ]


def test_discovers_receivable_carrying_formulas_by_account_row():
    formulas = discover_receivable_carrying_formulas(
        [
            _account_candidate("trade_receivables", "receivable_carrying_component", 1000),
            _account_candidate("trade_receivables", "receivable_carrying_component", -100),
            _account_candidate("trade_receivables", "ending", 900),
            _account_candidate("long_term_other_receivables", "receivable_carrying_component", 2000),
            _account_candidate("long_term_other_receivables", "receivable_carrying_component", -300),
            _account_candidate("long_term_other_receivables", "ending", 1700),
        ],
        tolerance=0,
    )

    assert [(formula.formula_key, formula.status, formula.actual, formula.expected) for formula in formulas] == [
        ("receivable_carrying_total", "matched", 900, 900),
        ("receivable_carrying_total", "matched", 1700, 1700),
    ]
    assert [formula.terms[0].account_key for formula in formulas] == [
        "trade_receivables",
        "long_term_other_receivables",
    ]


def test_discovers_receivable_aging_bucket_formulas_by_measure_row():
    formulas = discover_receivable_aging_bucket_formulas(
        [
            _account_candidate("trade_receivables_gross_aging", "aging_bucket_component", 194_209_849),
            _account_candidate("trade_receivables_gross_aging", "aging_bucket_component", 8_119_664),
            _account_candidate("trade_receivables_gross_aging", "aging_bucket_component", 29_657),
            _account_candidate("trade_receivables_gross_aging", "aging_bucket_total", 202_359_170),
            _account_candidate("trade_receivables_loss_allowance_aging", "aging_bucket_component", 1_158),
            _account_candidate("trade_receivables_loss_allowance_aging", "aging_bucket_component", 69_660),
            _account_candidate("trade_receivables_loss_allowance_aging", "aging_bucket_component", 29_657),
            _account_candidate("trade_receivables_loss_allowance_aging", "aging_bucket_total", 100_475),
        ],
        tolerance=0,
    )

    assert [(formula.formula_key, formula.status, formula.actual, formula.expected) for formula in formulas] == [
        ("receivable_aging_bucket_total", "matched", 202_359_170, 202_359_170),
        ("receivable_aging_bucket_total", "matched", 100_475, 100_475),
    ]


def test_discovers_inventory_carrying_formulas_by_account_row():
    formulas = discover_inventory_carrying_formulas(
        [
            _account_candidate("inventory_goods", "inventory_carrying_component", 1000),
            _account_candidate("inventory_goods", "inventory_carrying_component", -100),
            _account_candidate("inventory_goods", "ending", 900),
            _account_candidate("inventory_finished_goods", "inventory_carrying_component", 2000),
            _account_candidate("inventory_finished_goods", "ending", 2000),
        ],
        tolerance=0,
    )

    assert [(formula.formula_key, formula.status, formula.actual, formula.expected) for formula in formulas] == [
        ("inventory_carrying_total", "matched", 900, 900),
        ("inventory_carrying_total", "matched", 2000, 2000),
    ]


def test_discovers_liquidity_maturity_formulas_by_account_row():
    formulas = discover_liquidity_maturity_formulas(
        [
            _account_candidate("borrowings_and_bonds", "maturity_component", 10),
            _account_candidate("lease_liabilities", "maturity_component", 1),
            _account_candidate("borrowings_and_bonds", "maturity_component", 20),
            _account_candidate("lease_liabilities", "maturity_component", 2),
            _account_candidate("borrowings_and_bonds", "maturity_total", 30),
            _account_candidate("lease_liabilities", "maturity_total", 3),
        ],
        tolerance=0,
    )

    assert [(formula.formula_key, formula.status, formula.actual, formula.expected) for formula in formulas] == [
        ("liquidity_maturity_total", "matched", 30, 30),
        ("liquidity_maturity_total", "matched", 3, 3),
    ]
    assert [formula.terms[0].account_key for formula in formulas] == [
        "borrowings_and_bonds",
        "lease_liabilities",
    ]


def test_discovers_employee_benefit_maturity_formula():
    formulas = discover_liquidity_maturity_formulas(
        [
            _account_candidate("defined_benefit_expected_payments", "maturity_component", 8_537_047_000),
            _account_candidate("defined_benefit_expected_payments", "maturity_component", 45_919_845_000),
            _account_candidate("defined_benefit_expected_payments", "maturity_component", 12_261_563_000),
            _account_candidate("defined_benefit_expected_payments", "maturity_component", 42_020_488_000),
            _account_candidate("defined_benefit_expected_payments", "maturity_total", 108_738_943_000),
        ],
        tolerance=0,
    )

    assert [(formula.formula_key, formula.status, formula.actual, formula.expected) for formula in formulas] == [
        ("liquidity_maturity_total", "matched", 108_738_943_000, 108_738_943_000)
    ]
    assert formulas[0].terms[0].account_key == "defined_benefit_expected_payments"


def test_discovers_liquidity_maturity_formula_uses_unit_tolerance():
    formulas = discover_liquidity_maturity_formulas(
        [
            _account_candidate("defined_benefit_expected_payments", "maturity_component", 100_000, unit_multiplier=1000),
            _account_candidate("defined_benefit_expected_payments", "maturity_component", 200_000, unit_multiplier=1000),
            _account_candidate("defined_benefit_expected_payments", "maturity_total", 301_000, unit_multiplier=1000),
        ],
        tolerance=1,
    )

    assert [(formula.status, formula.actual, formula.expected, formula.difference, formula.tolerance) for formula in formulas] == [
        ("matched", 300_000, 301_000, -1_000, 1000)
    ]


def test_discovers_lease_expense_formula_for_component_row():
    formulas = discover_lease_expense_formulas(
        [
            _account_candidate("right_of_use_asset_depreciation", "lease_expense_component", 100),
            _account_candidate("right_of_use_asset_depreciation", "lease_expense_component", 20),
            _account_candidate("right_of_use_asset_depreciation", "lease_expense_total", 120),
            _account_candidate("lease_interest_expense", "lease_expense_total", 30),
        ],
        tolerance=0,
    )

    assert [(formula.formula_key, formula.status, formula.actual, formula.expected) for formula in formulas] == [
        ("lease_expense_total", "matched", 120, 120)
    ]


def test_discovers_discontinued_operation_income_statement_formulas():
    formulas = discover_discontinued_operation_income_formulas(
        [
            _candidate("revenue", 86_773_808),
            _candidate("cost_of_sales", 71_401_947),
            _candidate("gross_profit", 15_371_861),
            _candidate("selling_admin", 16_214_619),
            _candidate("operating_profit", -842_758),
            _candidate("other_income", 738_185),
            _candidate("other_loss", 129_922),
            _candidate("finance_income", 555_985),
            _candidate("finance_cost", 2_158_514),
            _candidate("pre_tax_profit", -1_837_024),
            _candidate("tax_expense", 137_049),
            _candidate("discontinued_profit", -1_974_073),
            _candidate("disposal_gain", 21_874_959),
            _candidate("net_discontinued_profit", 19_900_886),
            _candidate("parent_attribution", 20_368_366),
            _candidate("noncontrolling_attribution", -467_480),
        ],
        tolerance=0,
    )

    assert [
        (formula.formula_key, formula.status, formula.actual, formula.expected)
        for formula in formulas
    ] == [
        ("discontinued_gross_profit", "matched", 15_371_861, 15_371_861),
        ("discontinued_operating_profit", "matched", -842_758, -842_758),
        ("discontinued_pre_tax_profit", "matched", -1_837_024, -1_837_024),
        ("discontinued_after_tax_profit", "matched", -1_974_073, -1_974_073),
        ("discontinued_net_profit", "matched", 19_900_886, 19_900_886),
        ("discontinued_attribution", "matched", 19_900_886, 19_900_886),
    ]


def test_discovers_discontinued_operation_cashflow_formula():
    formula = discover_discontinued_operation_cashflow_formula(
        [
            _candidate("operating_cashflow", 10),
            _candidate("investing_cashflow", -3),
            _candidate("financing_cashflow", 2),
            _candidate("cashflow_total", 9),
        ],
        tolerance=0,
    )

    assert formula.status == "matched"
    assert formula.formula_key == "discontinued_operation_cashflow_total"
    assert formula.expected == 9
    assert formula.actual == 9
    assert formula.difference == 0
