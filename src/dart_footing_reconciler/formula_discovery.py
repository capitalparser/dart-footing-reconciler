"""Generate verification formulas from source-backed candidates."""

from __future__ import annotations

from dataclasses import dataclass

from dart_footing_reconciler.checks import MATCHED, PARSE_UNCERTAIN, UNEXPLAINED_GAP
from dart_footing_reconciler.verification_candidates import VerificationCandidate


@dataclass(frozen=True)
class VerificationFormula:
    formula_key: str
    target_role: str
    expected: int | None
    actual: int | None
    difference: int | None
    tolerance: int
    status: str
    terms: tuple[VerificationCandidate, ...]
    reason: str


def discover_rollforward_formula(
    candidates: list[VerificationCandidate],
    *,
    tolerance: int,
) -> VerificationFormula:
    if any(candidate.confidence < 0.7 for candidate in candidates):
        return VerificationFormula(
            "rollforward",
            "ending",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "low-confidence layout or orientation evidence blocks matched formula",
        )
    beginning = _single_amount(candidates, "beginning")
    ending = _single_amount(candidates, "ending")
    if beginning is None or ending is None:
        return VerificationFormula(
            "rollforward",
            "ending",
            ending,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "missing beginning or ending candidate",
        )
    if any(candidate.role == "signed_movement" for candidate in candidates):
        return _discover_signed_rollforward_formula(candidates, beginning, ending, tolerance)
    actual = beginning
    actual += _sum_role(candidates, "additions")
    actual -= _sum_role(candidates, "depreciation")
    actual -= _sum_role(candidates, "disposals")
    actual -= _sum_role(candidates, "impairment")
    actual += _sum_role(candidates, "transfers")
    difference = actual - ending
    effective_tolerance = _effective_tolerance(candidates, tolerance)
    status = MATCHED if abs(difference) <= effective_tolerance else UNEXPLAINED_GAP
    reason = (
        "roll-forward candidates close to ending amount"
        if status == MATCHED
        else "roll-forward candidates do not close to ending amount"
    )
    return VerificationFormula(
        "rollforward",
        "ending",
        ending,
        actual,
        difference,
        effective_tolerance,
        status,
        tuple(candidates),
        reason,
    )


def discover_component_net_formula(
    candidates: list[VerificationCandidate],
    *,
    tolerance: int,
) -> VerificationFormula:
    if any(candidate.confidence < 0.7 for candidate in candidates):
        return VerificationFormula(
            "component_net",
            "ending",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "low-confidence layout or orientation evidence blocks matched formula",
        )
    gross_cost = _single_amount(candidates, "gross_cost")
    ending = _single_amount(candidates, "ending")
    if gross_cost is None or ending is None:
        return VerificationFormula(
            "component_net",
            "ending",
            ending,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "missing gross cost or ending candidate",
        )
    actual = gross_cost
    actual += _sum_role(candidates, "accumulated_depreciation")
    actual += _sum_role(candidates, "accumulated_impairment")
    difference = actual - ending
    status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP
    reason = (
        "component net candidates close to ending amount"
        if status == MATCHED
        else "component net candidates do not close to ending amount"
    )
    return VerificationFormula(
        "component_net",
        "ending",
        ending,
        actual,
        difference,
        tolerance,
        status,
        tuple(candidates),
        reason,
    )


def discover_debt_split_formula(
    candidates: list[VerificationCandidate],
    *,
    tolerance: int,
) -> VerificationFormula:
    if any(candidate.confidence < 0.7 for candidate in candidates):
        return VerificationFormula(
            "debt_split",
            "ending",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "low-confidence layout or orientation evidence blocks matched formula",
        )
    debt_total = _single_amount(candidates, "debt_total")
    ending = _single_amount(candidates, "ending")
    face_amount = _single_amount(candidates, "face_amount")
    if (debt_total is None and face_amount is None) or ending is None:
        return VerificationFormula(
            "debt_split",
            "ending",
            ending,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "missing debt total or ending candidate",
        )
    component_actual = debt_total if debt_total is not None else 0
    formula_key = "debt_split"
    if face_amount is not None:
        component_actual = face_amount + _sum_role(candidates, "debt_discount")
        formula_key = "debt_component_split"
        component_difference = component_actual - debt_total if debt_total is not None else 0
        if debt_total is not None and abs(component_difference) > tolerance:
            return VerificationFormula(
                formula_key,
                "debt_total",
                debt_total,
                component_actual,
                component_difference,
                tolerance,
                UNEXPLAINED_GAP,
                tuple(candidates),
                "debt face amount and discount do not close to debt total",
            )
    actual = component_actual + _sum_role(candidates, "current_portion")
    difference = actual - ending
    status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP
    reason = (
        "debt total and current portion close to ending amount"
        if status == MATCHED
        else "debt total and current portion do not close to ending amount"
    )
    return VerificationFormula(
        formula_key,
        "ending",
        ending,
        actual,
        difference,
        tolerance,
        status,
        tuple(candidates),
        reason,
    )


def discover_earnings_per_share_formulas(
    candidates: list[VerificationCandidate],
    *,
    tolerance: int,
) -> list[VerificationFormula]:
    grouped: dict[str, list[VerificationCandidate]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate.account_key, []).append(candidate)
    formulas: list[VerificationFormula] = []
    for account_key in sorted(grouped, key=_first_position(grouped)):
        account_candidates = grouped[account_key]
        formulas.append(
            _discover_earnings_per_share_formula(account_candidates, tolerance=tolerance)
        )
    return formulas


def discover_dividend_payout_formulas(
    candidates: list[VerificationCandidate],
    *,
    tolerance: int,
) -> list[VerificationFormula]:
    grouped: dict[str, list[VerificationCandidate]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate.account_key, []).append(candidate)
    formulas: list[VerificationFormula] = []
    for account_key in sorted(grouped, key=_first_position(grouped)):
        account_candidates = grouped[account_key]
        formulas.append(_discover_dividend_payout_formula(account_candidates, tolerance=tolerance))
    return formulas


def _discover_dividend_payout_formula(
    candidates: list[VerificationCandidate],
    *,
    tolerance: int,
) -> VerificationFormula:
    if any(candidate.confidence < 0.7 for candidate in candidates):
        return VerificationFormula(
            "dividend_payout_ratio",
            "dividend_payout_ratio_tenths",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "low-confidence layout or orientation evidence blocks matched formula",
        )
    net_income = _single_amount(candidates, "dividend_net_income")
    cash_dividends = _single_amount(candidates, "cash_dividends")
    ratio = _single_amount(candidates, "dividend_payout_ratio_tenths")
    if net_income is None or cash_dividends is None or ratio is None or net_income == 0:
        return VerificationFormula(
            "dividend_payout_ratio",
            "dividend_payout_ratio_tenths",
            ratio,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "missing net income, cash dividends, or payout ratio candidate",
        )
    actual = _round_divide_to_won(cash_dividends * 1000, net_income)
    difference = actual - ratio
    status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP
    reason = (
        "cash dividends divided by net income closes to payout ratio"
        if status == MATCHED
        else "cash dividends divided by net income does not close to payout ratio"
    )
    return VerificationFormula(
        "dividend_payout_ratio",
        "dividend_payout_ratio_tenths",
        ratio,
        actual,
        difference,
        tolerance,
        status,
        tuple(candidates),
        reason,
    )


def _discover_earnings_per_share_formula(
    candidates: list[VerificationCandidate],
    *,
    tolerance: int,
) -> VerificationFormula:
    if any(candidate.confidence < 0.7 for candidate in candidates):
        return VerificationFormula(
            "earnings_per_share",
            "earnings_per_share",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "low-confidence layout or orientation evidence blocks matched formula",
        )
    profit = _single_amount(candidates, "eps_profit")
    shares = _single_amount(candidates, "weighted_average_shares")
    eps = _single_amount(candidates, "earnings_per_share")
    if profit is None or shares is None or eps is None or shares == 0:
        return VerificationFormula(
            "earnings_per_share",
            "earnings_per_share",
            eps,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "missing profit, weighted-average shares, or EPS candidate",
        )
    actual = _round_divide_to_won(profit, shares)
    difference = actual - eps
    status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP
    reason = (
        "profit divided by weighted-average shares closes to EPS"
        if status == MATCHED
        else "profit divided by weighted-average shares does not close to EPS"
    )
    return VerificationFormula(
        "earnings_per_share",
        "earnings_per_share",
        eps,
        actual,
        difference,
        tolerance,
        status,
        tuple(candidates),
        reason,
    )


def discover_expense_summary_formula(
    candidates: list[VerificationCandidate],
    *,
    tolerance: int,
) -> VerificationFormula:
    if any(candidate.confidence < 0.7 for candidate in candidates):
        return VerificationFormula(
            "expense_summary_total",
            "expense_total",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "low-confidence layout or orientation evidence blocks matched formula",
        )
    total = _single_amount(candidates, "expense_total")
    if total is None:
        return VerificationFormula(
            "expense_summary_total",
            "expense_total",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "missing expense total candidate",
        )
    actual = _sum_role(candidates, "expense_component")
    difference = actual - total
    status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP
    reason = (
        "expense component candidates close to total amount"
        if status == MATCHED
        else "expense component candidates do not close to total amount"
    )
    return VerificationFormula(
        "expense_summary_total",
        "expense_total",
        total,
        actual,
        difference,
        tolerance,
        status,
        tuple(candidates),
        reason,
    )


def discover_credit_risk_exposure_formula(
    candidates: list[VerificationCandidate],
    *,
    tolerance: int,
) -> VerificationFormula:
    if any(candidate.confidence < 0.7 for candidate in candidates):
        return VerificationFormula(
            "credit_risk_exposure_total",
            "credit_exposure_total",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "low-confidence layout or orientation evidence blocks matched formula",
        )
    total = _single_amount(candidates, "credit_exposure_total")
    if total is None:
        return VerificationFormula(
            "credit_risk_exposure_total",
            "credit_exposure_total",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "missing credit exposure total candidate",
        )
    actual = _sum_role(candidates, "credit_exposure_component")
    difference = actual - total
    status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP
    reason = (
        "credit risk exposure components close to total amount"
        if status == MATCHED
        else "credit risk exposure components do not close to total amount"
    )
    return VerificationFormula(
        "credit_risk_exposure_total",
        "credit_exposure_total",
        total,
        actual,
        difference,
        tolerance,
        status,
        tuple(candidates),
        reason,
    )


def discover_credit_risk_exposure_formulas(
    candidates: list[VerificationCandidate],
    *,
    tolerance: int,
) -> list[VerificationFormula]:
    grouped: dict[tuple[str, int], list[VerificationCandidate]] = {}
    for candidate in candidates:
        grouped.setdefault((candidate.table_source, candidate.row_index), []).append(candidate)
    row_formulas: list[VerificationFormula] = []
    for group_key in sorted(grouped, key=_first_position(grouped)):
        row_candidates = grouped[group_key]
        if any(candidate.role == "credit_exposure_component" for candidate in row_candidates) and any(
            candidate.role == "credit_exposure_total" for candidate in row_candidates
        ):
            row_formulas.append(
                discover_credit_risk_exposure_formula(row_candidates, tolerance=tolerance)
            )
    if row_formulas:
        return row_formulas
    if any(candidate.role == "credit_exposure_component" for candidate in candidates) and any(
        candidate.role == "credit_exposure_total" for candidate in candidates
    ):
        return [discover_credit_risk_exposure_formula(candidates, tolerance=tolerance)]
    return []


def discover_financial_fair_value_formula(
    candidates: list[VerificationCandidate],
    *,
    tolerance: int,
) -> VerificationFormula:
    if any(candidate.confidence < 0.7 for candidate in candidates):
        return VerificationFormula(
            "financial_fair_value_total",
            "fair_value_total",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "low-confidence layout or orientation evidence blocks matched formula",
        )
    total = _single_amount(candidates, "fair_value_total")
    if total is None:
        return VerificationFormula(
            "financial_fair_value_total",
            "fair_value_total",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "missing fair value total candidate",
        )
    actual = _sum_role(candidates, "fair_value_component")
    difference = actual - total
    effective_tolerance = _effective_tolerance(candidates, tolerance)
    status = MATCHED if abs(difference) <= effective_tolerance else UNEXPLAINED_GAP
    reason = (
        "financial fair value components close to total amount"
        if status == MATCHED
        else "financial fair value components do not close to total amount"
    )
    return VerificationFormula(
        "financial_fair_value_total",
        "fair_value_total",
        total,
        actual,
        difference,
        effective_tolerance,
        status,
        tuple(candidates),
        reason,
    )


def discover_financial_fair_value_level_formulas(
    candidates: list[VerificationCandidate],
    *,
    tolerance: int,
) -> list[VerificationFormula]:
    grouped: dict[tuple[str, int, str], list[VerificationCandidate]] = {}
    for candidate in candidates:
        grouped.setdefault(
            (candidate.table_source, candidate.row_index, candidate.account_key),
            [],
        ).append(candidate)
    formulas: list[VerificationFormula] = []
    for group_key in sorted(grouped, key=_first_position(grouped)):
        row_candidates = grouped[group_key]
        if any(candidate.role == "fair_value_level_component" for candidate in row_candidates) and any(
            candidate.role == "fair_value_total" for candidate in row_candidates
        ):
            formulas.append(_discover_financial_fair_value_level_formula(row_candidates, tolerance))
    return formulas


def discover_asset_component_total_formulas(
    candidates: list[VerificationCandidate],
    *,
    tolerance: int,
) -> list[VerificationFormula]:
    grouped: dict[tuple[str, int, str], list[VerificationCandidate]] = {}
    for candidate in candidates:
        grouped.setdefault(
            (candidate.table_source, candidate.row_index, candidate.account_key),
            [],
        ).append(candidate)
    formulas: list[VerificationFormula] = []
    for group_key in sorted(grouped, key=_first_position(grouped)):
        row_candidates = grouped[group_key]
        if any(candidate.role == "asset_component" for candidate in row_candidates) and any(
            candidate.role == "asset_component_total" for candidate in row_candidates
        ):
            formulas.append(_discover_asset_component_total_formula(row_candidates, tolerance))
    return formulas


def discover_tax_expense_composition_formulas(
    candidates: list[VerificationCandidate],
    *,
    tolerance: int,
) -> list[VerificationFormula]:
    grouped: dict[tuple[str, int, str], list[VerificationCandidate]] = {}
    for candidate in candidates:
        grouped.setdefault(
            (candidate.table_source, candidate.column_index, candidate.account_key),
            [],
        ).append(candidate)
    formulas: list[VerificationFormula] = []
    for group_key in sorted(grouped, key=_first_position(grouped)):
        period_candidates = grouped[group_key]
        if _has_tax_expense_composition_formula_shape(period_candidates):
            formulas.append(_discover_tax_expense_composition_formula(period_candidates, tolerance))
    return formulas


def discover_financial_category_formulas(
    candidates: list[VerificationCandidate],
    *,
    tolerance: int,
) -> list[VerificationFormula]:
    grouped: dict[tuple[str, int, str], list[VerificationCandidate]] = {}
    for candidate in candidates:
        grouped.setdefault(
            (candidate.table_source, candidate.row_index, candidate.account_key),
            [],
        ).append(candidate)
    formulas: list[VerificationFormula] = []
    for group_key in sorted(grouped, key=_first_position(grouped)):
        account_candidates = grouped[group_key]
        if (
            any(candidate.role == "ending" for candidate in account_candidates)
            and any(
                candidate.role == "financial_category_component"
                for candidate in account_candidates
            )
        ):
            formulas.append(
                _discover_financial_category_formula(account_candidates, tolerance)
            )
    return formulas


def discover_financial_category_column_formulas(
    candidates: list[VerificationCandidate],
    *,
    tolerance: int,
) -> list[VerificationFormula]:
    grouped: dict[tuple[str, int, str], list[VerificationCandidate]] = {}
    for candidate in candidates:
        grouped.setdefault(
            (candidate.table_source, candidate.column_index, candidate.account_key),
            [],
        ).append(candidate)
    formulas: list[VerificationFormula] = []
    for group_key in sorted(grouped, key=_first_position(grouped)):
        column_candidates = grouped[group_key]
        if (
            any(candidate.role == "financial_category_column_total" for candidate in column_candidates)
            and any(
                candidate.role == "financial_category_column_component"
                for candidate in column_candidates
            )
        ):
            formulas.append(
                _discover_financial_category_column_formula(column_candidates, tolerance)
            )
    return formulas


def discover_employee_benefit_expense_formulas(
    candidates: list[VerificationCandidate],
    *,
    tolerance: int,
) -> list[VerificationFormula]:
    grouped: dict[tuple[str, int, str], list[VerificationCandidate]] = {}
    for candidate in candidates:
        grouped.setdefault(
            (candidate.table_source, candidate.column_index, candidate.account_key),
            [],
        ).append(candidate)
    formulas: list[VerificationFormula] = []
    for group_key in sorted(grouped, key=_first_position(grouped)):
        period_candidates = grouped[group_key]
        if (
            any(candidate.role == "employee_benefit_expense_total" for candidate in period_candidates)
            and any(
                candidate.role == "employee_benefit_expense_component"
                for candidate in period_candidates
            )
        ):
            formulas.append(
                _discover_employee_benefit_expense_formula(period_candidates, tolerance)
            )
    return formulas


def discover_receivable_carrying_formulas(
    candidates: list[VerificationCandidate],
    *,
    tolerance: int,
) -> list[VerificationFormula]:
    grouped: dict[tuple[str, int, str], list[VerificationCandidate]] = {}
    for candidate in candidates:
        grouped.setdefault(
            (candidate.table_source, candidate.row_index, candidate.account_key),
            [],
        ).append(candidate)
    formulas: list[VerificationFormula] = []
    for group_key in sorted(grouped, key=_first_position(grouped)):
        row_candidates = grouped[group_key]
        if any(candidate.role == "receivable_carrying_component" for candidate in row_candidates) and any(
            candidate.role == "ending" for candidate in row_candidates
        ):
            formulas.append(_discover_receivable_carrying_formula(row_candidates, tolerance))
    return formulas


def discover_receivable_aging_bucket_formulas(
    candidates: list[VerificationCandidate],
    *,
    tolerance: int,
) -> list[VerificationFormula]:
    grouped: dict[tuple[str, int, str], list[VerificationCandidate]] = {}
    for candidate in candidates:
        grouped.setdefault(
            (candidate.table_source, candidate.row_index, candidate.account_key),
            [],
        ).append(candidate)
    formulas: list[VerificationFormula] = []
    for group_key in sorted(grouped, key=_first_position(grouped)):
        row_candidates = grouped[group_key]
        if (
            any(candidate.role == "aging_bucket_component" for candidate in row_candidates)
            and any(candidate.role == "aging_bucket_total" for candidate in row_candidates)
        ):
            formulas.append(_discover_receivable_aging_bucket_formula(row_candidates, tolerance))
    return formulas


def discover_inventory_carrying_formulas(
    candidates: list[VerificationCandidate],
    *,
    tolerance: int,
) -> list[VerificationFormula]:
    grouped: dict[tuple[str, int, str], list[VerificationCandidate]] = {}
    for candidate in candidates:
        grouped.setdefault(
            (candidate.table_source, candidate.row_index, candidate.account_key),
            [],
        ).append(candidate)
    formulas: list[VerificationFormula] = []
    for group_key in sorted(grouped, key=_first_position(grouped)):
        row_candidates = grouped[group_key]
        if any(candidate.role == "inventory_carrying_component" for candidate in row_candidates) and any(
            candidate.role == "ending" for candidate in row_candidates
        ):
            formulas.append(_discover_inventory_carrying_formula(row_candidates, tolerance))
    return formulas


def discover_net_debt_bridge_formulas(
    candidates: list[VerificationCandidate],
    *,
    tolerance: int,
) -> list[VerificationFormula]:
    grouped: dict[str, list[VerificationCandidate]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate.account_key, []).append(candidate)
    formulas: list[VerificationFormula] = []
    for account_key in sorted(grouped, key=_first_position(grouped)):
        account_candidates = grouped[account_key]
        if any(candidate.role == "beginning" for candidate in account_candidates) and any(
            candidate.role == "ending" for candidate in account_candidates
        ):
            formulas.append(
                discover_rollforward_formula(account_candidates, tolerance=tolerance)
            )
    return formulas


def discover_defined_benefit_rollforward_formulas(
    candidates: list[VerificationCandidate],
    *,
    tolerance: int,
) -> list[VerificationFormula]:
    grouped: dict[str, list[VerificationCandidate]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate.account_key, []).append(candidate)
    formulas: list[VerificationFormula] = []
    for account_key in sorted(grouped, key=_first_position(grouped)):
        account_candidates = grouped[account_key]
        if any(candidate.role == "beginning" for candidate in account_candidates) and any(
            candidate.role == "ending" for candidate in account_candidates
        ):
            formulas.append(
                discover_rollforward_formula(account_candidates, tolerance=tolerance)
            )
    return formulas


def discover_provision_column_total_formulas(
    candidates: list[VerificationCandidate],
    *,
    tolerance: int,
) -> list[VerificationFormula]:
    grouped: dict[str, list[VerificationCandidate]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate.account_key, []).append(candidate)
    formulas: list[VerificationFormula] = []
    for account_key in sorted(grouped, key=_first_position(grouped)):
        account_candidates = grouped[account_key]
        if any(candidate.role == "provision_column_component" for candidate in account_candidates) and any(
            candidate.role == "provision_column_total" for candidate in account_candidates
        ):
            formulas.append(
                _discover_provision_column_total_formula(account_candidates, tolerance)
            )
    return formulas


def discover_liquidity_maturity_formulas(
    candidates: list[VerificationCandidate],
    *,
    tolerance: int,
) -> list[VerificationFormula]:
    grouped: dict[tuple[str, int, str], list[VerificationCandidate]] = {}
    for candidate in candidates:
        grouped.setdefault(
            (candidate.table_source, candidate.row_index, candidate.account_key),
            [],
        ).append(candidate)
    formulas: list[VerificationFormula] = []
    for group_key in sorted(grouped, key=_first_position(grouped)):
        account_candidates = grouped[group_key]
        if any(candidate.role == "maturity_total" for candidate in account_candidates):
            formulas.append(
                _discover_liquidity_maturity_formula(account_candidates, tolerance)
            )
    return formulas


def discover_lease_expense_formulas(
    candidates: list[VerificationCandidate],
    *,
    tolerance: int,
) -> list[VerificationFormula]:
    grouped: dict[tuple[str, int, str], list[VerificationCandidate]] = {}
    for candidate in candidates:
        grouped.setdefault(
            (candidate.table_source, candidate.row_index, candidate.account_key),
            [],
        ).append(candidate)
    formulas: list[VerificationFormula] = []
    for group_key in sorted(grouped, key=_first_position(grouped)):
        row_candidates = grouped[group_key]
        if any(candidate.role == "lease_expense_component" for candidate in row_candidates) and any(
            candidate.role == "lease_expense_total" for candidate in row_candidates
        ):
            formulas.append(_discover_lease_expense_formula(row_candidates, tolerance))
    return formulas


def discover_lease_liability_split_formula(
    candidates: list[VerificationCandidate],
    *,
    tolerance: int,
) -> VerificationFormula:
    if any(candidate.confidence < 0.7 for candidate in candidates):
        return VerificationFormula(
            "lease_liability_split_total",
            "ending",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "low-confidence layout or orientation evidence blocks matched formula",
        )
    total = _single_amount(candidates, "ending")
    if total is None:
        return VerificationFormula(
            "lease_liability_split_total",
            "ending",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "missing lease liability total candidate",
        )
    actual = _sum_role(candidates, "lease_liability_split_component")
    difference = actual - total
    effective_tolerance = _effective_tolerance(candidates, tolerance)
    status = MATCHED if abs(difference) <= effective_tolerance else UNEXPLAINED_GAP
    reason = (
        "current and non-current lease liabilities close to total amount"
        if status == MATCHED
        else "current and non-current lease liabilities do not close to total amount"
    )
    return VerificationFormula(
        "lease_liability_split_total",
        "ending",
        total,
        actual,
        difference,
        effective_tolerance,
        status,
        tuple(candidates),
        reason,
    )


def discover_discontinued_operation_income_formulas(
    candidates: list[VerificationCandidate],
    *,
    tolerance: int,
) -> list[VerificationFormula]:
    formulas: list[VerificationFormula] = []
    specs = (
        (
            "discontinued_gross_profit",
            "gross_profit",
            ("revenue", "cost_of_sales"),
            lambda amounts: amounts["revenue"] - amounts["cost_of_sales"],
            "revenue less cost of sales closes to gross profit",
            "revenue less cost of sales does not close to gross profit",
        ),
        (
            "discontinued_operating_profit",
            "operating_profit",
            ("gross_profit", "selling_admin"),
            lambda amounts: amounts["gross_profit"] - amounts["selling_admin"],
            "gross profit less selling/admin expense closes to operating profit",
            "gross profit less selling/admin expense does not close to operating profit",
        ),
        (
            "discontinued_pre_tax_profit",
            "pre_tax_profit",
            (
                "operating_profit",
                "other_income",
                "other_loss",
                "finance_income",
                "finance_cost",
            ),
            lambda amounts: (
                amounts["operating_profit"]
                + amounts["other_income"]
                - amounts["other_loss"]
                + amounts["finance_income"]
                - amounts["finance_cost"]
            ),
            "operating profit plus non-operating items closes to pre-tax profit",
            "operating profit plus non-operating items does not close to pre-tax profit",
        ),
        (
            "discontinued_after_tax_profit",
            "discontinued_profit",
            ("pre_tax_profit", "tax_expense"),
            lambda amounts: amounts["pre_tax_profit"] - amounts["tax_expense"],
            "pre-tax profit less tax expense closes to discontinued profit",
            "pre-tax profit less tax expense does not close to discontinued profit",
        ),
        (
            "discontinued_net_profit",
            "net_discontinued_profit",
            ("discontinued_profit", "disposal_gain"),
            lambda amounts: amounts["discontinued_profit"] + amounts["disposal_gain"],
            "discontinued profit plus disposal gain closes to net discontinued profit",
            "discontinued profit plus disposal gain does not close to net discontinued profit",
        ),
        (
            "discontinued_attribution",
            "net_discontinued_profit",
            ("parent_attribution", "noncontrolling_attribution"),
            lambda amounts: amounts["parent_attribution"] + amounts["noncontrolling_attribution"],
            "parent and non-controlling attribution closes to net discontinued profit",
            "parent and non-controlling attribution does not close to net discontinued profit",
        ),
    )
    for (
        formula_key,
        target_role,
        component_roles,
        calculate,
        matched_reason,
        gap_reason,
    ) in specs:
        roles = (target_role,) + component_roles
        if not all(any(candidate.role == role for candidate in candidates) for role in roles):
            continue
        formulas.append(
            _discover_role_formula(
                candidates,
                formula_key=formula_key,
                target_role=target_role,
                component_roles=component_roles,
                calculate=calculate,
                matched_reason=matched_reason,
                gap_reason=gap_reason,
                tolerance=tolerance,
            )
        )
    return formulas


def discover_discontinued_operation_cashflow_formula(
    candidates: list[VerificationCandidate],
    *,
    tolerance: int,
) -> VerificationFormula:
    return _discover_role_formula(
        candidates,
        formula_key="discontinued_operation_cashflow_total",
        target_role="cashflow_total",
        component_roles=(
            "operating_cashflow",
            "investing_cashflow",
            "financing_cashflow",
        ),
        calculate=lambda amounts: (
            amounts["operating_cashflow"]
            + amounts["investing_cashflow"]
            + amounts["financing_cashflow"]
        ),
        matched_reason="discontinued operation cash flow activities close to total",
        gap_reason="discontinued operation cash flow activities do not close to total",
        tolerance=tolerance,
    )


def _discover_lease_expense_formula(
    candidates: list[VerificationCandidate],
    tolerance: int,
) -> VerificationFormula:
    if any(candidate.confidence < 0.7 for candidate in candidates):
        return VerificationFormula(
            "lease_expense_total",
            "lease_expense_total",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "low-confidence layout or orientation evidence blocks matched formula",
        )
    total = _single_amount(candidates, "lease_expense_total")
    if total is None:
        return VerificationFormula(
            "lease_expense_total",
            "lease_expense_total",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "missing lease expense total candidate",
        )
    actual = _sum_role(candidates, "lease_expense_component")
    difference = actual - total
    status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP
    reason = (
        "lease expense components close to row total"
        if status == MATCHED
        else "lease expense components do not close to row total"
    )
    return VerificationFormula(
        "lease_expense_total",
        "lease_expense_total",
        total,
        actual,
        difference,
        tolerance,
        status,
        tuple(candidates),
        reason,
    )


def _discover_role_formula(
    candidates: list[VerificationCandidate],
    *,
    formula_key: str,
    target_role: str,
    component_roles: tuple[str, ...],
    calculate,
    matched_reason: str,
    gap_reason: str,
    tolerance: int,
) -> VerificationFormula:
    terms = tuple(
        candidate
        for candidate in candidates
        if candidate.role == target_role or candidate.role in component_roles
    )
    if any(candidate.confidence < 0.7 for candidate in terms):
        return VerificationFormula(
            formula_key,
            target_role,
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            terms,
            "low-confidence layout or orientation evidence blocks matched formula",
        )
    target = _single_amount(candidates, target_role)
    amounts = {role: _single_amount(candidates, role) for role in component_roles}
    if target is None or any(amount is None for amount in amounts.values()):
        return VerificationFormula(
            formula_key,
            target_role,
            target,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            terms,
            "missing unique target or component candidate",
        )
    actual = calculate(amounts)
    difference = actual - target
    status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP
    reason = matched_reason if status == MATCHED else gap_reason
    return VerificationFormula(
        formula_key,
        target_role,
        target,
        actual,
        difference,
        tolerance,
        status,
        terms,
        reason,
    )


def _discover_liquidity_maturity_formula(
    candidates: list[VerificationCandidate],
    tolerance: int,
) -> VerificationFormula:
    if any(candidate.confidence < 0.7 for candidate in candidates):
        return VerificationFormula(
            "liquidity_maturity_total",
            "maturity_total",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "low-confidence layout or orientation evidence blocks matched formula",
        )
    total = _single_amount(candidates, "maturity_total")
    if total is None:
        return VerificationFormula(
            "liquidity_maturity_total",
            "maturity_total",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "missing maturity total candidate",
        )
    actual = _sum_role(candidates, "maturity_component")
    difference = actual - total
    effective_tolerance = _effective_tolerance(candidates, tolerance)
    status = MATCHED if abs(difference) <= effective_tolerance else UNEXPLAINED_GAP
    reason = (
        "maturity bucket components close to row total"
        if status == MATCHED
        else "maturity bucket components do not close to row total"
    )
    return VerificationFormula(
        "liquidity_maturity_total",
        "maturity_total",
        total,
        actual,
        difference,
        effective_tolerance,
        status,
        tuple(candidates),
        reason,
    )


def _discover_provision_column_total_formula(
    candidates: list[VerificationCandidate],
    tolerance: int,
) -> VerificationFormula:
    if any(candidate.confidence < 0.7 for candidate in candidates):
        return VerificationFormula(
            "provision_column_total",
            "provision_column_total",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "low-confidence layout or orientation evidence blocks matched formula",
        )
    total = _single_amount(candidates, "provision_column_total")
    if total is None:
        return VerificationFormula(
            "provision_column_total",
            "provision_column_total",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "missing provision column total candidate",
        )
    actual = _sum_role(candidates, "provision_column_component")
    difference = actual - total
    effective_tolerance = _effective_tolerance(candidates, tolerance)
    status = MATCHED if abs(difference) <= effective_tolerance else UNEXPLAINED_GAP
    reason = (
        "provision component rows close to column total"
        if status == MATCHED
        else "provision component rows do not close to column total"
    )
    return VerificationFormula(
        "provision_column_total",
        "provision_column_total",
        total,
        actual,
        difference,
        effective_tolerance,
        status,
        tuple(candidates),
        reason,
    )


def _discover_financial_category_formula(
    candidates: list[VerificationCandidate],
    tolerance: int,
) -> VerificationFormula:
    if any(candidate.confidence < 0.7 for candidate in candidates):
        return VerificationFormula(
            "financial_category_total",
            "ending",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "low-confidence layout or orientation evidence blocks matched formula",
        )
    total = _single_amount(candidates, "ending")
    if total is None:
        return VerificationFormula(
            "financial_category_total",
            "ending",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "missing financial category total candidate",
        )
    actual = _sum_role(candidates, "financial_category_component")
    difference = actual - total
    effective_tolerance = _effective_tolerance(candidates, tolerance)
    status = MATCHED if abs(difference) <= effective_tolerance else UNEXPLAINED_GAP
    reason = (
        "financial category components close to total amount"
        if status == MATCHED
        else "financial category components do not close to total amount"
    )
    return VerificationFormula(
        "financial_category_total",
        "ending",
        total,
        actual,
        difference,
        effective_tolerance,
        status,
        tuple(candidates),
        reason,
    )


def _discover_financial_category_column_formula(
    candidates: list[VerificationCandidate],
    tolerance: int,
) -> VerificationFormula:
    if any(candidate.confidence < 0.7 for candidate in candidates):
        return VerificationFormula(
            "financial_category_column_total",
            "financial_category_column_total",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "low-confidence layout or orientation evidence blocks matched formula",
        )
    total = _single_amount(candidates, "financial_category_column_total")
    if total is None:
        return VerificationFormula(
            "financial_category_column_total",
            "financial_category_column_total",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "missing financial category column total candidate",
        )
    actual = _sum_role(candidates, "financial_category_column_component")
    difference = actual - total
    effective_tolerance = _effective_tolerance(candidates, tolerance)
    status = MATCHED if abs(difference) <= effective_tolerance else UNEXPLAINED_GAP
    reason = (
        "financial category column components close to total amount"
        if status == MATCHED
        else "financial category column components do not close to total amount"
    )
    return VerificationFormula(
        "financial_category_column_total",
        "financial_category_column_total",
        total,
        actual,
        difference,
        effective_tolerance,
        status,
        tuple(candidates),
        reason,
    )


def _discover_employee_benefit_expense_formula(
    candidates: list[VerificationCandidate],
    tolerance: int,
) -> VerificationFormula:
    if any(candidate.confidence < 0.7 for candidate in candidates):
        return VerificationFormula(
            "employee_benefit_expense_total",
            "employee_benefit_expense_total",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "low-confidence layout or orientation evidence blocks matched formula",
        )
    total = _single_amount(candidates, "employee_benefit_expense_total")
    if total is None:
        return VerificationFormula(
            "employee_benefit_expense_total",
            "employee_benefit_expense_total",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "missing employee benefit expense total candidate",
        )
    actual = _sum_role(candidates, "employee_benefit_expense_component")
    difference = actual - total
    effective_tolerance = _effective_tolerance(candidates, tolerance)
    status = MATCHED if abs(difference) <= effective_tolerance else UNEXPLAINED_GAP
    reason = (
        "employee benefit expense components close to total amount"
        if status == MATCHED
        else "employee benefit expense components do not close to total amount"
    )
    return VerificationFormula(
        "employee_benefit_expense_total",
        "employee_benefit_expense_total",
        total,
        actual,
        difference,
        effective_tolerance,
        status,
        tuple(candidates),
        reason,
    )


def _discover_financial_fair_value_level_formula(
    candidates: list[VerificationCandidate],
    tolerance: int,
) -> VerificationFormula:
    if any(candidate.confidence < 0.7 for candidate in candidates):
        return VerificationFormula(
            "financial_fair_value_level_total",
            "fair_value_total",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "low-confidence layout or orientation evidence blocks matched formula",
        )
    total = _single_amount(candidates, "fair_value_total")
    if total is None:
        return VerificationFormula(
            "financial_fair_value_level_total",
            "fair_value_total",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "missing fair value hierarchy total candidate",
        )
    actual = _sum_role(candidates, "fair_value_level_component")
    difference = actual - total
    effective_tolerance = _effective_tolerance(candidates, tolerance)
    status = MATCHED if abs(difference) <= effective_tolerance else UNEXPLAINED_GAP
    reason = (
        "fair value hierarchy level components close to row total"
        if status == MATCHED
        else "fair value hierarchy level components do not close to row total"
    )
    return VerificationFormula(
        "financial_fair_value_level_total",
        "fair_value_total",
        total,
        actual,
        difference,
        effective_tolerance,
        status,
        tuple(candidates),
        reason,
    )


def _discover_asset_component_total_formula(
    candidates: list[VerificationCandidate],
    tolerance: int,
) -> VerificationFormula:
    if any(candidate.confidence < 0.7 for candidate in candidates):
        return VerificationFormula(
            "asset_component_total",
            "asset_component_total",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "low-confidence layout or orientation evidence blocks matched formula",
        )
    total = _single_amount(candidates, "asset_component_total")
    if total is None:
        return VerificationFormula(
            "asset_component_total",
            "asset_component_total",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "missing asset component total candidate",
        )
    actual = _sum_role(candidates, "asset_component")
    difference = actual - total
    effective_tolerance = _effective_tolerance(candidates, tolerance)
    status = MATCHED if abs(difference) <= effective_tolerance else UNEXPLAINED_GAP
    reason = (
        "asset component columns close to row total"
        if status == MATCHED
        else "asset component columns do not close to row total"
    )
    return VerificationFormula(
        "asset_component_total",
        "asset_component_total",
        total,
        actual,
        difference,
        effective_tolerance,
        status,
        tuple(candidates),
        reason,
    )


def _discover_tax_expense_composition_formula(
    candidates: list[VerificationCandidate],
    tolerance: int,
) -> VerificationFormula:
    if any(candidate.confidence < 0.7 for candidate in candidates):
        return VerificationFormula(
            "tax_expense_composition_total",
            "tax_expense_total",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "low-confidence layout or orientation evidence blocks matched formula",
        )
    total = _single_amount(candidates, "tax_expense_total")
    if total is None:
        return VerificationFormula(
            "tax_expense_composition_total",
            "tax_expense_total",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "missing tax expense total candidate",
        )
    actual = _sum_role(candidates, "tax_expense_component")
    difference = actual - total
    effective_tolerance = _effective_tolerance(candidates, tolerance)
    status = MATCHED if abs(difference) <= effective_tolerance else UNEXPLAINED_GAP
    reason = (
        "tax expense components close to period total"
        if status == MATCHED
        else "tax expense components do not close to period total"
    )
    return VerificationFormula(
        "tax_expense_composition_total",
        "tax_expense_total",
        total,
        actual,
        difference,
        effective_tolerance,
        status,
        tuple(candidates),
        reason,
    )


def _has_tax_expense_composition_formula_shape(
    candidates: list[VerificationCandidate],
) -> bool:
    labels = tuple(candidate.label.replace(" ", "") for candidate in candidates)
    return (
        any(candidate.role == "tax_expense_total" for candidate in candidates)
        and sum(1 for candidate in candidates if candidate.role == "tax_expense_component") >= 2
        and any(_is_current_tax_expense_component_label(label) for label in labels)
        and any(_is_deferred_tax_expense_component_label(label) for label in labels)
    )


def _is_current_tax_expense_component_label(label: str) -> bool:
    if "법인세율" in label or "세율로계산" in label:
        return False
    return "법인세" in label and any(
        alias in label for alias in ("부담액", "부담내역", "추납", "환급", "조정액", "조정사항", "당기법인세비용")
    )


def _is_deferred_tax_expense_component_label(label: str) -> bool:
    if "기초" in label or "기말" in label:
        return False
    return "이연법인세" in label and any(
        alias in label for alias in ("변동액", "변동")
    )


def _discover_receivable_carrying_formula(
    candidates: list[VerificationCandidate],
    tolerance: int,
) -> VerificationFormula:
    if any(candidate.confidence < 0.7 for candidate in candidates):
        return VerificationFormula(
            "receivable_carrying_total",
            "ending",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "low-confidence layout or orientation evidence blocks matched formula",
        )
    total = _single_amount(candidates, "ending")
    if total is None:
        return VerificationFormula(
            "receivable_carrying_total",
            "ending",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "missing receivable carrying amount candidate",
        )
    actual = _sum_role(candidates, "receivable_carrying_component")
    difference = actual - total
    effective_tolerance = _effective_tolerance(candidates, tolerance)
    status = MATCHED if abs(difference) <= effective_tolerance else UNEXPLAINED_GAP
    reason = (
        "receivable carrying components close to carrying amount"
        if status == MATCHED
        else "receivable carrying components do not close to carrying amount"
    )
    return VerificationFormula(
        "receivable_carrying_total",
        "ending",
        total,
        actual,
        difference,
        effective_tolerance,
        status,
        tuple(candidates),
        reason,
    )


def _discover_inventory_carrying_formula(
    candidates: list[VerificationCandidate],
    tolerance: int,
) -> VerificationFormula:
    if any(candidate.confidence < 0.7 for candidate in candidates):
        return VerificationFormula(
            "inventory_carrying_total",
            "ending",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "low-confidence layout or orientation evidence blocks matched formula",
        )
    total = _single_amount(candidates, "ending")
    if total is None:
        return VerificationFormula(
            "inventory_carrying_total",
            "ending",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "missing inventory carrying amount candidate",
        )
    actual = _sum_role(candidates, "inventory_carrying_component")
    difference = actual - total
    effective_tolerance = _effective_tolerance(candidates, tolerance)
    status = MATCHED if abs(difference) <= effective_tolerance else UNEXPLAINED_GAP
    reason = (
        "inventory carrying components close to carrying amount"
        if status == MATCHED
        else "inventory carrying components do not close to carrying amount"
    )
    return VerificationFormula(
        "inventory_carrying_total",
        "ending",
        total,
        actual,
        difference,
        effective_tolerance,
        status,
        tuple(candidates),
        reason,
    )


def _discover_receivable_aging_bucket_formula(
    candidates: list[VerificationCandidate],
    tolerance: int,
) -> VerificationFormula:
    if any(candidate.confidence < 0.7 for candidate in candidates):
        return VerificationFormula(
            "receivable_aging_bucket_total",
            "aging_bucket_total",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "low-confidence layout or orientation evidence blocks matched formula",
        )
    total = _single_amount(candidates, "aging_bucket_total")
    if total is None:
        return VerificationFormula(
            "receivable_aging_bucket_total",
            "aging_bucket_total",
            None,
            None,
            None,
            tolerance,
            PARSE_UNCERTAIN,
            tuple(candidates),
            "missing receivable aging bucket total candidate",
        )
    actual = _sum_role(candidates, "aging_bucket_component")
    difference = actual - total
    effective_tolerance = _effective_tolerance(candidates, tolerance)
    status = MATCHED if abs(difference) <= effective_tolerance else UNEXPLAINED_GAP
    reason = (
        "receivable aging bucket components close to total amount"
        if status == MATCHED
        else "receivable aging bucket components do not close to total amount"
    )
    return VerificationFormula(
        "receivable_aging_bucket_total",
        "aging_bucket_total",
        total,
        actual,
        difference,
        effective_tolerance,
        status,
        tuple(candidates),
        reason,
    )


def _discover_signed_rollforward_formula(
    candidates: list[VerificationCandidate],
    beginning: int,
    ending: int,
    tolerance: int,
) -> VerificationFormula:
    actual = beginning + _sum_role(candidates, "signed_movement")
    difference = actual - ending
    effective_tolerance = _effective_tolerance(candidates, tolerance)
    status = MATCHED if abs(difference) <= effective_tolerance else UNEXPLAINED_GAP
    reason = (
        "signed roll-forward candidates close to ending amount"
        if status == MATCHED
        else "signed roll-forward candidates do not close to ending amount"
    )
    return VerificationFormula(
        "signed_rollforward",
        "ending",
        ending,
        actual,
        difference,
        effective_tolerance,
        status,
        tuple(candidates),
        reason,
    )


def _effective_tolerance(candidates: list[VerificationCandidate], tolerance: int) -> int:
    return max([tolerance, *(candidate.unit_multiplier for candidate in candidates)])


def _single_amount(candidates: list[VerificationCandidate], role: str) -> int | None:
    values = [candidate.amount for candidate in candidates if candidate.role == role]
    if len(values) != 1:
        return None
    return values[0]


def _sum_role(candidates: list[VerificationCandidate], role: str) -> int:
    return sum(candidate.amount for candidate in candidates if candidate.role == role)


def _round_divide_to_won(numerator: int, denominator: int) -> int:
    sign = -1 if numerator * denominator < 0 else 1
    return sign * ((abs(numerator) + abs(denominator) // 2) // abs(denominator))


def _first_position(grouped: dict[object, list[VerificationCandidate]]):
    positions = {
        account_key: min(
            (candidate.row_index, candidate.column_index) for candidate in account_candidates
        )
        for account_key, account_candidates in grouped.items()
    }
    return positions.__getitem__
