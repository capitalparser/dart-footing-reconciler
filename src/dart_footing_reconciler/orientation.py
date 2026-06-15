"""Detect semantic orientation of DART note tables."""

from __future__ import annotations

from dataclasses import dataclass

from dart_footing_reconciler.table_semantics import compact


@dataclass(frozen=True)
class TableOrientation:
    key: str
    confidence: float
    evidence: tuple[str, ...]


MOVEMENT_LABELS = (
    "기초",
    "취득",
    "증가",
    "추가",
    "처분",
    "제거",
    "감가상각",
    "상각",
    "손상",
    "대체",
    "기말",
)
MEASURE_LABELS = (
    "취득원가",
    "감가상각누계액",
    "상각누계액",
    "손상차손누계액",
    "정부보조금",
    "장부금액",
    "장부가액",
    "순장부금액",
    "합계",
    "총계",
)
PERIOD_LABELS = ("당기", "당기말", "당기말현재", "당기현재", "전기", "전기말", "전기말현재")


def detect_orientation(
    *,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> TableOrientation:
    normalized_headers = tuple(compact(header) for header in headers)
    normalized_rows = tuple(compact(label) for label in row_labels)
    header_movements = _count_movement_matches(normalized_headers)
    row_movements = _count_movement_matches(normalized_rows)
    header_measures = _count_matches(normalized_headers, MEASURE_LABELS)
    row_measures = _count_matches(normalized_rows, MEASURE_LABELS)
    header_periods = _count_matches(normalized_headers, PERIOD_LABELS)
    row_periods = _count_matches(normalized_rows, PERIOD_LABELS)
    header_financial_categories = _count_financial_category_matches(normalized_headers)
    row_financial_accounts = _count_financial_account_matches(normalized_rows)
    header_financial_fair_value_amounts = _count_financial_fair_value_amount_matches(
        normalized_headers
    )
    header_financial_fair_value_levels = _count_financial_fair_value_level_matches(
        normalized_headers
    )
    row_tax_expense_components = _count_tax_expense_component_row_matches(normalized_rows)
    row_tax_expense_totals = _count_tax_expense_total_row_matches(normalized_rows)
    row_loss_allowance_movements = _count_loss_allowance_movement_matches(normalized_rows)
    header_receivable_accounts = _count_receivable_account_matches(normalized_headers)
    row_aging_statuses = _count_aging_status_matches(normalized_rows)
    header_receivable_aging_buckets = _count_receivable_aging_bucket_header_matches(
        normalized_headers
    )
    row_receivable_aging_measures = _count_receivable_aging_measure_row_matches(
        normalized_rows
    )
    header_inventory_measures = _count_inventory_measure_matches(normalized_headers)
    row_inventory_accounts = _count_inventory_account_matches(normalized_rows)
    header_inventory_allowance_amounts = _count_inventory_allowance_amount_header_matches(
        normalized_headers
    )
    row_inventory_allowance_movements = _count_inventory_allowance_movement_matches(
        normalized_rows
    )
    header_functional_expenses = _count_functional_expense_header_matches(normalized_headers)
    row_depreciation_expenses = _count_depreciation_expense_matches(normalized_rows)
    row_research_development_expenses = _count_research_development_expense_matches(
        normalized_rows
    )
    header_depreciation_expenses = _count_depreciation_expense_matches(normalized_headers)
    row_functional_items = _count_matches(normalized_rows, ("기능별항목",))
    header_debt_instruments = _count_debt_instrument_header_matches(normalized_headers)
    row_debt_details = _count_debt_detail_row_matches(normalized_rows)
    header_debt_component_columns = _count_debt_component_column_matches(normalized_headers)
    header_provision_movements = _count_provision_movement_header_matches(normalized_headers)
    row_provision_accounts = _count_provision_account_matches(normalized_rows)
    header_provision_accounts = _count_provision_account_matches(normalized_headers)
    row_provision_movements = _count_provision_movement_row_matches(normalized_rows)
    header_provision_current_noncurrent = _count_provision_current_noncurrent_header_matches(
        normalized_headers
    )
    row_provision_total = _count_provision_total_row_matches(normalized_rows)
    header_defined_benefit_accounts = _count_defined_benefit_account_header_matches(normalized_headers)
    row_defined_benefit_movements = _count_defined_benefit_movement_row_matches(normalized_rows)
    header_expense_amounts = _count_expense_amount_header_matches(normalized_headers)
    row_selling_admin_expenses = _count_selling_admin_expense_row_matches(normalized_rows)
    header_financial_liabilities = _count_financial_liability_header_matches(normalized_headers)
    net_debt_bridge_rows = _has_net_debt_bridge_rows(normalized_rows)
    header_credit_risk_amounts = _count_credit_risk_amount_header_matches(normalized_headers)
    row_credit_risk_assets = _count_credit_risk_asset_row_matches(normalized_rows)
    header_credit_risk_exposure_components = _count_credit_risk_exposure_component_header_matches(
        normalized_headers
    )
    header_credit_risk_exposure_totals = _count_credit_risk_exposure_total_header_matches(
        normalized_headers
    )
    row_credit_risk_exposures = _count_credit_risk_exposure_row_matches(normalized_rows)
    header_maturity_buckets = _count_maturity_bucket_header_matches(normalized_headers)
    row_maturity_liabilities = _count_maturity_liability_row_matches(normalized_rows)
    row_lease_liability_maturity = _count_lease_liability_maturity_row_matches(
        normalized_rows
    )
    row_lease_liability_split = _count_lease_liability_split_row_matches(normalized_rows)
    row_employee_benefit_expected_payments = _count_employee_benefit_expected_payment_rows(
        normalized_rows
    )
    row_employee_benefit_expected_contributions = (
        _count_employee_benefit_expected_contribution_rows(normalized_rows)
    )
    header_lease_asset_totals = _count_lease_asset_total_header_matches(normalized_headers)
    row_lease_expenses = _count_lease_expense_row_matches(normalized_rows)
    header_discontinued_operations = _count_discontinued_operation_header_matches(normalized_headers)
    row_discontinued_operation_income = _count_discontinued_operation_income_row_matches(normalized_rows)
    row_discontinued_operation_cashflows = _count_discontinued_operation_cashflow_row_matches(normalized_rows)
    row_eps_profit = _count_eps_profit_rows(normalized_rows)
    row_eps_shares = _count_eps_share_rows(normalized_rows)
    row_eps_results = _count_eps_result_rows(normalized_rows)
    header_asset_topics = _count_matches(
        normalized_headers,
        ("유형자산", "무형자산", "투자부동산", "사용권자산", "영업권"),
    )
    row_asset_topics = _count_matches(
        normalized_rows,
        ("유형자산", "무형자산", "투자부동산", "사용권자산", "영업권"),
    )
    row_asset_movement_details = _count_asset_movement_detail_rows(normalized_rows)
    header_asset_component_columns = _count_asset_component_header_matches(normalized_headers)
    header_asset_component_totals = _count_asset_component_total_header_matches(normalized_headers)

    if header_movements >= 2 and row_measures >= 1:
        return TableOrientation(
            "mixed",
            0.75,
            ("movement labels in columns", "measure labels in rows"),
        )
    if header_movements >= 3 and row_asset_topics >= 1 and _has_asset_change_header(
        normalized_headers
    ):
        return TableOrientation(
            "mixed",
            0.75,
            ("movement labels in columns", "asset labels in rows"),
        )
    if header_movements >= 2 and row_periods >= 2:
        return TableOrientation(
            "row_oriented",
            0.85,
            ("movement labels in columns", "period labels in rows"),
        )
    if header_asset_topics >= 1 and row_asset_movement_details >= 3:
        return TableOrientation(
            "row_oriented",
            0.85,
            ("asset account amount column", "asset movement detail rows"),
        )
    if (
        header_asset_component_columns >= 1
        and header_asset_component_totals >= 1
        and row_asset_topics >= 1
    ):
        return TableOrientation(
            "column_oriented",
            0.85,
            ("asset component columns", "asset labels in rows"),
        )
    if header_asset_topics >= 1 and row_measures >= 2:
        return TableOrientation(
            "mixed",
            0.75,
            ("asset labels in columns", "measure labels in rows"),
        )
    if row_loss_allowance_movements >= 3 and header_financial_categories >= 1:
        return TableOrientation(
            "row_oriented",
            0.85,
            ("loss allowance movement labels in rows", "financial asset category headers"),
        )
    if header_financial_fair_value_amounts >= 1 and row_financial_accounts >= 2:
        return TableOrientation(
            "row_oriented",
            0.85,
            ("financial fair value amount column", "financial account labels in rows"),
        )
    if header_financial_fair_value_levels >= 2 and row_financial_accounts >= 1:
        return TableOrientation(
            "column_oriented",
            0.85,
            ("fair value hierarchy level columns", "financial account labels in rows"),
        )
    if header_periods >= 1 and row_tax_expense_components >= 2 and row_tax_expense_totals >= 1:
        return TableOrientation(
            "column_oriented",
            0.85,
            ("tax expense component rows", "period amount columns"),
        )
    if header_financial_categories >= 2 and row_financial_accounts >= 2:
        return TableOrientation(
            "column_oriented",
            0.85,
            ("financial category labels in columns", "account labels in rows"),
        )
    if header_receivable_accounts >= 2 and row_aging_statuses >= 2:
        return TableOrientation(
            "column_oriented",
            0.85,
            ("receivable account labels in columns", "aging status labels in rows"),
        )
    if header_receivable_aging_buckets >= 2 and row_receivable_aging_measures >= 2:
        return TableOrientation(
            "row_oriented",
            0.85,
            ("receivable aging bucket columns", "gross and allowance rows"),
        )
    if header_inventory_measures >= 1 and row_inventory_accounts >= 2:
        return TableOrientation(
            "column_oriented",
            0.85,
            ("inventory carrying amount column", "inventory account labels in rows"),
        )
    if header_inventory_allowance_amounts >= 1 and row_inventory_allowance_movements >= 3:
        return TableOrientation(
            "row_oriented",
            0.85,
            ("inventory allowance movement labels in rows", "inventory allowance amount column"),
        )
    if (
        header_functional_expenses >= 2
        and (row_depreciation_expenses >= 1 or row_research_development_expenses >= 1)
    ):
        return TableOrientation(
            "column_oriented",
            0.85,
            ("functional expense columns", "depreciation or amortization rows"),
        )
    if header_depreciation_expenses >= 1 and row_functional_items >= 1:
        return TableOrientation(
            "column_oriented",
            0.85,
            ("single functional expense row", "depreciation or amortization amount header"),
        )
    if header_debt_component_columns >= 3 and row_debt_details >= 1:
        return TableOrientation(
            "row_oriented",
            0.85,
            ("debt component columns", "debt instrument summary row"),
        )
    if header_debt_instruments >= 1 and row_debt_details >= 2:
        return TableOrientation(
            "row_oriented",
            0.85,
            ("debt instrument columns", "debt detail rows"),
        )
    if header_expense_amounts >= 1 and row_selling_admin_expenses >= 2:
        return TableOrientation(
            "column_oriented",
            0.85,
            ("expense amount column", "selling admin expense rows"),
        )
    if header_provision_movements >= 3 and row_provision_accounts >= 1:
        return TableOrientation(
            "mixed",
            0.85,
            ("provision movement columns", "provision account rows"),
        )
    if header_provision_accounts >= 2 and row_provision_movements >= 2:
        return TableOrientation(
            "row_oriented",
            0.85,
            ("provision account columns", "provision movement rows"),
        )
    if header_provision_current_noncurrent >= 1 and row_provision_accounts >= 2 and row_provision_total >= 1:
        return TableOrientation(
            "column_oriented",
            0.85,
            ("provision current and non-current columns", "provision total row"),
        )
    if header_defined_benefit_accounts >= 2 and row_defined_benefit_movements >= 3:
        return TableOrientation(
            "mixed",
            0.85,
            ("defined benefit account columns", "benefit obligation movement rows"),
        )
    if header_financial_liabilities >= 2 and net_debt_bridge_rows:
        return TableOrientation(
            "mixed",
            0.85,
            ("financial liability account columns", "net debt movement rows"),
        )
    if header_credit_risk_amounts >= 1 and row_credit_risk_assets >= 2:
        return TableOrientation(
            "column_oriented",
            0.85,
            ("credit risk exposure amount column", "financial asset rows"),
        )
    if (
        row_credit_risk_exposures >= 1
        and header_credit_risk_exposure_components >= 2
        and header_credit_risk_exposure_totals >= 1
    ):
        return TableOrientation(
            "column_oriented",
            0.85,
            ("credit risk exposure row", "financial asset exposure columns include total"),
        )
    if header_maturity_buckets >= 2 and row_lease_liability_maturity >= 1:
        return TableOrientation(
            "column_oriented",
            0.85,
            ("maturity bucket columns", "lease liability maturity rows"),
        )
    if row_lease_liability_split >= 3 and len(normalized_headers) >= 2:
        return TableOrientation(
            "row_oriented",
            0.85,
            ("lease liability split rows", "amount column"),
        )
    if header_maturity_buckets >= 2 and row_maturity_liabilities >= 2:
        return TableOrientation(
            "column_oriented",
            0.85,
            ("maturity bucket columns", "financial liability rows"),
        )
    if header_maturity_buckets >= 2 and row_employee_benefit_expected_payments >= 1:
        return TableOrientation(
            "row_oriented",
            0.85,
            ("maturity bucket columns", "employee benefit expected payment row"),
        )
    if header_maturity_buckets >= 2 and row_employee_benefit_expected_contributions >= 1:
        return TableOrientation(
            "row_oriented",
            0.85,
            ("maturity bucket columns", "employee benefit expected contribution row"),
        )
    if header_lease_asset_totals >= 1 and row_lease_expenses >= 2:
        return TableOrientation(
            "column_oriented",
            0.85,
            ("lease expense rows", "lease asset total column"),
        )
    if header_discontinued_operations >= 1 and row_discontinued_operation_income >= 5:
        return TableOrientation(
            "column_oriented",
            0.85,
            ("discontinued operation header", "discontinued operation income rows"),
        )
    if header_discontinued_operations >= 1 and row_discontinued_operation_cashflows >= 3:
        return TableOrientation(
            "column_oriented",
            0.85,
            ("discontinued operation header", "discontinued operation cash flow rows"),
        )
    if row_eps_profit >= 1 and row_eps_shares >= 1 and row_eps_results >= 1:
        return TableOrientation(
            "row_oriented",
            0.85,
            ("earnings per share rows", "share class amount column"),
        )
    if row_movements >= 2 and header_measures >= 1:
        return TableOrientation(
            "row_oriented",
            0.9,
            ("movement labels in rows", "measure or total labels in columns"),
        )
    if header_measures >= 2 and row_movements == 0:
        return TableOrientation(
            "column_oriented",
            0.9,
            ("measure labels in columns", "entity/account labels in rows"),
        )
    if header_periods >= 1:
        return TableOrientation(
            "period_oriented",
            0.8,
            ("period labels in columns",),
        )
    return TableOrientation("unknown", 0.0, ())


def _count_matches(values: tuple[str, ...], aliases: tuple[str, ...]) -> int:
    return sum(1 for value in values if any(alias in value for alias in aliases))


def _count_movement_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_movement_label(value))


def _count_financial_category_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_financial_category_label(value))


def _count_financial_fair_value_amount_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if value == "공정가치")


def _count_financial_fair_value_level_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_financial_fair_value_level_header(value))


def _count_financial_account_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_financial_account_label(value))


def _count_loss_allowance_movement_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_loss_allowance_movement_label(value))


def _count_receivable_account_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_receivable_account_label(value))


def _count_aging_status_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if "연체상태" in value)


def _count_receivable_aging_bucket_header_matches(values: tuple[str, ...]) -> int:
    return sum(
        1
        for value in values
        if "연체" in value or "회수기간" in value or "손상채권" in value
    )


def _count_receivable_aging_measure_row_matches(values: tuple[str, ...]) -> int:
    return sum(
        1
        for value in values
        if "총장부금액" in value or "손실충당금" in value or "대손충당금" in value
    )


def _count_inventory_measure_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if any(alias in value for alias in ("총장부금액", "장부금액합계", "장부가액합계")))


def _count_asset_component_header_matches(values: tuple[str, ...]) -> int:
    return sum(
        1
        for value in values
        if any(
            alias in value
            for alias in (
                "상각자산",
                "미상각자산",
                "개발중인무형자산",
                "개발중인자산",
                "건설중인자산",
            )
        )
    )


def _count_asset_component_total_header_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if "장부금액" in value or "장부가액" in value)


def _count_inventory_account_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_inventory_account_label(value))


def _count_inventory_allowance_amount_header_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if "재고자산평가충당금" in value)


def _count_inventory_allowance_movement_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_inventory_allowance_movement_label(value))


def _count_functional_expense_header_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_functional_expense_header(value))


def _count_depreciation_expense_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_depreciation_expense_label(value))


def _count_research_development_expense_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_research_development_expense_label(value))


def _count_debt_instrument_header_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if "차입금명칭" in value)


def _count_debt_detail_row_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_debt_detail_row_label(value))


def _count_debt_component_column_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_debt_component_column(value))


def _count_provision_movement_header_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_provision_movement_header(value))


def _count_provision_account_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_provision_account_label(value))


def _count_provision_movement_row_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_provision_movement_row(value))


def _count_provision_current_noncurrent_header_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_provision_current_noncurrent_header(value))


def _count_provision_total_row_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_provision_total_row(value))


def _count_defined_benefit_account_header_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_defined_benefit_account_header(value))


def _count_defined_benefit_movement_row_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_defined_benefit_movement_row(value))


def _count_expense_amount_header_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if value in {"금액", "공시금액"})


def _count_selling_admin_expense_row_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_selling_admin_expense_row_label(value))


def _count_financial_liability_header_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_financial_liability_header(value))


def _count_credit_risk_amount_header_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_credit_risk_exposure_amount_header(value))


def _count_credit_risk_asset_row_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_credit_risk_asset_row(value))


def _count_credit_risk_exposure_component_header_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_credit_risk_exposure_component_header(value))


def _count_credit_risk_exposure_total_header_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_credit_risk_exposure_total_header(value))


def _count_credit_risk_exposure_row_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if "신용위험에대한최대노출정도" in value)


def _count_eps_profit_rows(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_eps_profit_row(value))


def _count_eps_share_rows(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if "가중평균유통보통주식수" in value)


def _count_eps_result_rows(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_eps_result_row(value))


def _count_maturity_bucket_header_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_maturity_bucket_header(value))


def _count_maturity_liability_row_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_maturity_liability_row(value))


def _count_lease_liability_maturity_row_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_lease_liability_maturity_row(value))


def _count_lease_liability_split_row_matches(values: tuple[str, ...]) -> int:
    return sum(
        1
        for value in values
        if _is_current_lease_liability_row(value)
        or _is_noncurrent_lease_liability_row(value)
        or _is_total_lease_liability_row(value)
    )


def _count_tax_expense_component_row_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_tax_expense_component_row(value))


def _count_tax_expense_total_row_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_tax_expense_total_row(value))


def _count_employee_benefit_expected_payment_rows(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_employee_benefit_expected_payment_row(value))


def _count_employee_benefit_expected_contribution_rows(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_employee_benefit_expected_contribution_row(value))


def _count_lease_asset_total_header_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if "자산합계" in value)


def _count_lease_expense_row_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_lease_expense_row(value))


def _count_discontinued_operation_header_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if "중단영업" in value)


def _count_discontinued_operation_income_row_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_discontinued_operation_income_row(value))


def _count_discontinued_operation_cashflow_row_matches(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_discontinued_operation_cashflow_row(value))


def _count_asset_movement_detail_rows(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if "변동" in value and "조정" in value)


def _has_net_debt_bridge_rows(values: tuple[str, ...]) -> bool:
    joined = " ".join(values)
    has_net_debt_rollforward = (
        "기초순부채" in joined
        and "기말순부채" in joined
        and any(alias in joined for alias in ("현금흐름", "리스현금흐름"))
    )
    has_financing_debt_rollforward = (
        _has_financing_debt_beginning(values)
        and _has_financing_debt_ending(values)
        and sum(1 for value in values if _is_financing_debt_movement(value)) >= 1
    )
    return has_net_debt_rollforward or has_financing_debt_rollforward


def _has_financing_debt_beginning(values: tuple[str, ...]) -> bool:
    return any("재무활동에서생기는" in value and "기초" in value and "부채" in value for value in values)


def _has_financing_debt_ending(values: tuple[str, ...]) -> bool:
    return any("재무활동에서생기는" in value and "기말" in value and "부채" in value for value in values)


def _is_financing_debt_movement(value: str) -> bool:
    if "재무활동에서생기는" not in value and "현금흐름변동" not in value:
        return False
    if "기초" in value or "기말" in value:
        return False
    return any(alias in value for alias in ("증가", "감소", "지급", "변동", "현금흐름"))


def _is_movement_label(value: str) -> bool:
    if any(measure in value for measure in ("취득원가", "상각누계", "손상차손누계")):
        return False
    return any(alias in value for alias in MOVEMENT_LABELS)


def _is_financial_category_label(value: str) -> bool:
    return any(
        alias in value
        for alias in (
            "당기손익",
            "기타포괄손익",
            "공정가치",
            "상각후원가",
            "금융자산",
            "금융부채",
            "금융상품",
            "범주합계",
        )
    )


def _is_financial_account_label(value: str) -> bool:
    return any(
        alias in value
        for alias in (
            "현금및현금성자산",
            "매출채권",
            "대여금",
            "미수금",
            "금융자산",
            "금융부채",
            "차입금",
            "사채",
            "리스부채",
            "매입채무",
        )
    )


def _is_loss_allowance_movement_label(value: str) -> bool:
    return any(
        alias in value
        for alias in (
            "기초손실충당금",
            "기말손실충당금",
            "기초금융자산",
            "기말금융자산",
            "기대신용손실",
            "손실충당금전입",
            "환입액",
            "제각",
            "제거에따른감소",
            "외화환산에따른증가",
            "기타변동에따른증가",
            "매각예정대체",
            "기타",
        )
    )


def _is_receivable_account_label(value: str) -> bool:
    return any(alias in value for alias in ("매출채권", "미수금", "미수수익", "대여금", "보증금"))


def _is_inventory_account_label(value: str) -> bool:
    return any(alias in value for alias in ("재고자산", "제품", "상품", "원재료", "저장품", "미착품", "미완성주택", "기타재고", "합계"))


def _is_inventory_allowance_movement_label(value: str) -> bool:
    return any(
        alias in value
        for alias in (
            "기초재고자산",
            "평가손실환입",
            "평가손실",
            "재고자산폐기",
            "기타",
            "기말재고자산",
        )
    )


def _is_functional_expense_header(value: str) -> bool:
    return any(alias in value for alias in ("매출원가", "판매비와일반관리비", "판매비와관리비", "기능별항목합계"))


def _is_depreciation_expense_label(value: str) -> bool:
    return any(alias in value for alias in ("감가상각비", "상각비", "무형자산상각비", "사용권자산상각비"))


def _is_research_development_expense_label(value: str) -> bool:
    return ("연구" in value and "개발" in value) or "경상연구개발비" in value


def _is_debt_detail_row_label(value: str) -> bool:
    return any(
        alias in value
        for alias in (
            "차입금",
            "명목금액",
            "사채할인발행차금",
            "소계",
            "1년이내만기도래분",
            "비유동성차입금",
            "합계",
        )
    )


def _is_debt_component_column(value: str) -> bool:
    return any(
        alias in value
        for alias in (
            "명목금액",
            "유동성사채",
            "유동성차입금",
            "사채할인발행차금",
            "현재가치할인차금",
            "비유동사채",
            "비유동성부분",
        )
    )


def _is_provision_movement_header(value: str) -> bool:
    return any(
        alias in value
        for alias in ("기초", "전입", "연중사용액", "사용액", "연결범위변동", "매각예정분류", "기말")
    )


def _is_provision_account_label(value: str) -> bool:
    return any(
        alias in value
        for alias in (
            "충당부채",
            "복구",
            "사후처리",
            "정화",
            "장기종업원급여부채",
            "제품보증",
            "판매보증",
            "반품",
        )
    )


def _is_provision_movement_row(value: str) -> bool:
    return any(alias in value for alias in ("기초", "기말", "추가", "증가", "환입", "사용", "변동"))


def _is_provision_current_noncurrent_header(value: str) -> bool:
    return (
        value in {"유동", "비유동"}
        or "유동충당부채" in value
        or "비유동충당부채" in value
    )


def _is_provision_total_row(value: str) -> bool:
    return "충당부채" in value and ("합계" in value or "총계" in value)


def _is_defined_benefit_account_header(value: str) -> bool:
    return "확정급여채무" in value or "사외적립자산" in value


def _is_defined_benefit_movement_row(value: str) -> bool:
    return any(
        alias in value
        for alias in (
            "기초",
            "당기근무원가",
            "이자비용",
            "재측정",
            "납입액",
            "전입",
            "전출",
            "지급",
            "기말",
        )
    )


def _is_selling_admin_expense_row_label(value: str) -> bool:
    return any(
        alias in value
        for alias in (
            "판관비",
            "판매비와관리비",
            "급여",
            "상여",
            "퇴직급여",
            "복리후생비",
            "지급수수료",
            "감가상각비",
            "합계",
        )
    )


def _is_financial_liability_header(value: str) -> bool:
    return any(alias in value for alias in ("차입금", "사채", "리스부채"))


def _is_financial_fair_value_level_header(value: str) -> bool:
    normalized = value.replace("(", "").replace(")", "")
    return normalized in {"수준1", "수준2", "수준3"} or normalized.startswith("수준")


def _is_credit_risk_asset_row(value: str) -> bool:
    return any(
        alias in value
        for alias in (
            "현금성자산",
            "현금및현금성자산",
            "공정가치측정금융자산",
            "매출채권",
            "대여금",
            "기타유동금융자산",
            "기타비유동금융자산",
            "파생상품자산",
        )
    )


def _is_credit_risk_exposure_amount_header(value: str) -> bool:
    return value in {"신용위험", "신용위험익스포저", "신용위험노출액"}


def _is_credit_risk_exposure_total_header(value: str) -> bool:
    return "금융상품합계" in value or value in {"합계", "총계"}


def _is_credit_risk_exposure_component_header(value: str) -> bool:
    if not value or _is_credit_risk_exposure_total_header(value):
        return False
    return any(
        alias in value
        for alias in (
            "현금",
            "금융상품",
            "금융자산",
            "매출채권",
            "기타채권",
            "대여금",
            "미수금",
            "보증금",
            "파생상품",
            "채무증권",
            "유가증권",
            "예금",
            "리스채권",
            "대출채권",
            "금융보증",
            "대출약정",
        )
    )


def _is_maturity_bucket_header(value: str) -> bool:
    return any(
        alias in value
        for alias in ("3개월", "개월", "1년", "2년", "5년", "10년", "초과", "이내", "미만", "이상", "~")
    )


def _is_maturity_liability_row(value: str) -> bool:
    return any(
        alias in value
        for alias in ("매입채무", "기타채무", "미지급금", "미지급비용", "차입금", "사채", "금융부채", "리스부채", "합계")
    )


def _is_employee_benefit_expected_payment_row(value: str) -> bool:
    return (
        ("지급" in value and "예상" in value and "급여" in value)
        or ("확정급여" in value and "지급액" in value)
    )


def _is_employee_benefit_expected_contribution_row(value: str) -> bool:
    return "예상" in value and "기여금" in value


def _is_lease_liability_maturity_row(value: str) -> bool:
    return any(
        alias in value
        for alias in ("리스부채", "최소리스료", "최소리스료의현재가치", "할인되지않은리스부채")
    )


def _is_current_lease_liability_row(value: str) -> bool:
    return "비유동" not in value and (
        "유동리스부채" in value or "유동성리스부채" in value
    )


def _is_noncurrent_lease_liability_row(value: str) -> bool:
    return "비유동" in value and "리스부채" in value


def _is_total_lease_liability_row(value: str) -> bool:
    return ("리스부채" in value and ("합계" in value or "총" in value)) or value == "합계"


def _is_tax_expense_component_row(value: str) -> bool:
    if _is_tax_expense_total_row(value):
        return False
    return (
        _is_current_tax_expense_component_row(value)
        or _is_deferred_tax_expense_component_row(value)
        or _is_capital_tax_expense_component_row(value)
    )


def _is_tax_expense_total_row(value: str) -> bool:
    normalized = value.replace("(", "").replace(")", "")
    return normalized in {"법인세비용", "법인세비용합계", "법인세비용수익"}


def _is_current_tax_expense_component_row(value: str) -> bool:
    if "법인세율" in value or "세율로계산" in value:
        return False
    return "법인세" in value and any(
        alias in value for alias in ("부담액", "부담내역", "추납액", "환급액")
    )


def _is_deferred_tax_expense_component_row(value: str) -> bool:
    if "기초" in value or "기말" in value:
        return False
    return "이연법인세" in value and any(
        alias in value for alias in ("변동액", "변동")
    )


def _is_capital_tax_expense_component_row(value: str) -> bool:
    return "자본에직접" in value and "법인세" in value


def _is_lease_expense_row(value: str) -> bool:
    return any(
        alias in value
        for alias in ("감가상각비", "리스부채에대한이자비용", "단기리스료", "소액자산리스료")
    )


def _is_discontinued_operation_income_row(value: str) -> bool:
    return any(
        alias in value
        for alias in (
            "매출액",
            "매출원가",
            "매출총이익",
            "판매비와관리비",
            "영업이익",
            "기타이익",
            "기타손실",
            "금융수익",
            "금융비용",
            "법인세비용차감전",
            "중단영업이익",
            "중단영업처분이익",
            "중단영업순이익",
        )
    )


def _is_discontinued_operation_cashflow_row(value: str) -> bool:
    return any(
        alias in value
        for alias in (
            "중단영업영업활동현금흐름",
            "중단영업투자활동현금흐름",
            "중단영업재무활동현금흐름",
            "영업활동현금흐름",
            "투자활동현금흐름",
            "재무활동현금흐름",
        )
    )


def _is_eps_profit_row(value: str) -> bool:
    return (
        ("당기순이익" in value or "당기순손익" in value)
        and "주당" not in value
        and "배당" not in value
    )


def _is_eps_result_row(value: str) -> bool:
    return "주당" in value and ("이익" in value or "손익" in value)


def _has_asset_change_header(values: tuple[str, ...]) -> bool:
    return any(
        any(alias in value for alias in ("취득", "추가", "처분", "제거", "감가상각", "상각", "손상", "대체"))
        for value in values
    )
