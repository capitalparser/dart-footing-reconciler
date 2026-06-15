"""Layout-aware note formula checks."""

from __future__ import annotations

from dart_footing_reconciler.checks import CheckEvidence, CheckResult, MATCHED
from dart_footing_reconciler.document import FullReport
from dart_footing_reconciler.formula_discovery import discover_asset_component_total_formulas
from dart_footing_reconciler.formula_discovery import discover_credit_risk_exposure_formulas
from dart_footing_reconciler.formula_discovery import discover_debt_split_formula
from dart_footing_reconciler.formula_discovery import discover_dividend_payout_formulas
from dart_footing_reconciler.formula_discovery import discover_employee_benefit_expense_formulas
from dart_footing_reconciler.formula_discovery import discover_earnings_per_share_formulas
from dart_footing_reconciler.formula_discovery import discover_expense_summary_formula
from dart_footing_reconciler.formula_discovery import discover_financial_category_column_formulas
from dart_footing_reconciler.formula_discovery import discover_financial_category_formulas
from dart_footing_reconciler.formula_discovery import discover_rollforward_formula
from dart_footing_reconciler.formula_discovery import discover_financial_fair_value_level_formulas
from dart_footing_reconciler.formula_discovery import discover_financial_fair_value_formula
from dart_footing_reconciler.formula_discovery import discover_inventory_carrying_formulas
from dart_footing_reconciler.formula_discovery import discover_liquidity_maturity_formulas
from dart_footing_reconciler.formula_discovery import discover_lease_liability_split_formula
from dart_footing_reconciler.formula_discovery import discover_provision_column_total_formulas
from dart_footing_reconciler.formula_discovery import discover_receivable_aging_bucket_formulas
from dart_footing_reconciler.formula_discovery import discover_receivable_carrying_formulas
from dart_footing_reconciler.formula_discovery import discover_tax_expense_composition_formulas
from dart_footing_reconciler.layout_variants import classify_layout
from dart_footing_reconciler.note_inventory import build_note_inventory
from dart_footing_reconciler.orientation import detect_orientation
from dart_footing_reconciler.verification_candidates import extract_verification_candidates


def check_layout_formula_assertions(
    report: FullReport,
    *,
    tolerance: int = 1,
) -> list[CheckResult]:
    inventory = build_note_inventory(report)
    tables_by_source = {
        f"note:{note.note_no}/table:{block.table.index}": block.table
        for note in report.notes
        for block in note.blocks
        if block.table is not None
    }
    results: list[CheckResult] = []
    for item in inventory.tables:
        layout = classify_layout(item)
        if layout.key not in {
            "credit_risk_exposure_summary",
            "defined_benefit_rollforward",
            "debt_instrument_detail_summary",
            "dividend_payout_summary",
            "earnings_per_share_summary",
            "employee_benefit_expense_allocation",
            "employee_benefit_maturity_summary",
            "asset_component_column_summary",
            "asset_period_rollforward_summary",
            "asset_two_label_row_rollforward_summary",
            "inventory_allowance_rollforward",
            "financial_instrument_fair_value_summary",
            "financial_fair_value_level_summary",
            "financial_instrument_category_summary",
            "functional_expense_research_allocation",
            "inventory_carrying_amount_summary",
            "lease_liability_current_noncurrent_summary",
            "loss_allowance_rollforward",
            "lease_liability_maturity_summary",
            "net_debt_bridge",
            "provision_current_noncurrent_summary",
            "provision_rollforward",
            "receivable_carrying_amount_summary",
            "receivable_loss_allowance_aging_summary",
            "receivable_present_value_carrying_summary",
            "tax_expense_composition_summary",
        }:
            continue
        table = tables_by_source.get(item.source)
        if table is None:
            continue
        orientation = detect_orientation(headers=item.headers, row_labels=item.row_labels)
        candidates = extract_verification_candidates(
            note_no=item.note_no,
            title=item.title,
            table=table,
            layout=layout,
            orientation=orientation,
        )
        if not candidates:
            continue
        if layout.key == "credit_risk_exposure_summary":
            for formula in discover_credit_risk_exposure_formulas(
                candidates,
                tolerance=tolerance,
            ):
                account_key = _row_account_key(formula)
                results.append(
                    _formula_check_result(item, layout.key, formula, tolerance, account_key)
                )
            continue
        if layout.key == "debt_instrument_detail_summary":
            formula = discover_debt_split_formula(candidates, tolerance=tolerance)
            if (
                formula.status == MATCHED
                and formula.expected is not None
                and formula.actual is not None
            ):
                account_key = formula.terms[0].account_key if formula.terms else "table"
                results.append(
                    _formula_check_result(item, layout.key, formula, tolerance, account_key)
                )
            continue
        if layout.key == "earnings_per_share_summary":
            for formula in discover_earnings_per_share_formulas(
                candidates,
                tolerance=tolerance,
            ):
                if formula.status != MATCHED:
                    continue
                account_key = formula.terms[0].account_key if formula.terms else "table"
                results.append(
                    _formula_check_result(item, layout.key, formula, tolerance, account_key)
                )
            continue
        if layout.key == "dividend_payout_summary":
            for formula in discover_dividend_payout_formulas(
                candidates,
                tolerance=tolerance,
            ):
                if formula.status != MATCHED:
                    continue
                account_key = formula.terms[0].account_key if formula.terms else "table"
                results.append(
                    _formula_check_result(item, layout.key, formula, tolerance, account_key)
                )
            continue
        if layout.key == "financial_instrument_fair_value_summary":
            formula = discover_financial_fair_value_formula(candidates, tolerance=tolerance)
            results.append(
                _formula_check_result(item, layout.key, formula, tolerance)
            )
            continue
        if layout.key == "financial_fair_value_level_summary":
            for formula in discover_financial_fair_value_level_formulas(
                candidates,
                tolerance=tolerance,
            ):
                account_key = formula.terms[0].account_key if formula.terms else "table"
                results.append(
                    _formula_check_result(item, layout.key, formula, tolerance, account_key)
                )
            continue
        if layout.key == "tax_expense_composition_summary":
            for formula in discover_tax_expense_composition_formulas(
                candidates,
                tolerance=tolerance,
            ):
                account_key = _period_account_key(formula)
                results.append(
                    _formula_check_result(item, layout.key, formula, tolerance, account_key)
                )
            continue
        if layout.key == "financial_instrument_category_summary":
            for formula in discover_financial_category_formulas(
                candidates,
                tolerance=tolerance,
            ):
                account_key = formula.terms[0].account_key if formula.terms else "table"
                results.append(
                    _formula_check_result(item, layout.key, formula, tolerance, account_key)
                )
            for formula in discover_financial_category_column_formulas(
                candidates,
                tolerance=tolerance,
            ):
                if formula.status != MATCHED:
                    continue
                account_key = formula.terms[0].account_key if formula.terms else "table"
                results.append(
                    _formula_check_result(item, layout.key, formula, tolerance, account_key)
                )
            continue
        if layout.key in {
            "receivable_carrying_amount_summary",
            "receivable_present_value_carrying_summary",
        }:
            for formula in discover_receivable_carrying_formulas(
                candidates,
                tolerance=tolerance,
            ):
                if layout.key == "receivable_carrying_amount_summary" and formula.status != MATCHED:
                    continue
                account_key = formula.terms[0].account_key if formula.terms else "table"
                results.append(
                    _formula_check_result(item, layout.key, formula, tolerance, account_key)
                )
            continue
        if layout.key == "receivable_loss_allowance_aging_summary":
            for formula in discover_receivable_aging_bucket_formulas(
                candidates,
                tolerance=tolerance,
            ):
                if formula.status != MATCHED:
                    continue
                account_key = formula.terms[0].account_key if formula.terms else "table"
                results.append(
                    _formula_check_result(item, layout.key, formula, tolerance, account_key)
                )
            continue
        if layout.key == "asset_period_rollforward_summary":
            for account_key, account_candidates in _candidate_groups(candidates).items():
                formula = discover_rollforward_formula(account_candidates, tolerance=tolerance)
                if formula.status != MATCHED:
                    continue
                results.append(
                    _formula_check_result(item, layout.key, formula, tolerance, account_key)
                )
            continue
        if layout.key == "asset_two_label_row_rollforward_summary":
            for account_key, account_candidates in _candidate_groups(candidates).items():
                formula = discover_rollforward_formula(account_candidates, tolerance=tolerance)
                if formula.status != MATCHED:
                    continue
                results.append(
                    _formula_check_result(item, layout.key, formula, tolerance, account_key)
                )
            continue
        if layout.key == "asset_component_column_summary":
            for formula in discover_asset_component_total_formulas(
                candidates,
                tolerance=tolerance,
            ):
                account_key = formula.terms[0].account_key if formula.terms else "table"
                results.append(
                    _formula_check_result(item, layout.key, formula, tolerance, account_key)
                )
            continue
        if layout.key == "inventory_carrying_amount_summary":
            for formula in discover_inventory_carrying_formulas(
                candidates,
                tolerance=tolerance,
            ):
                account_key = formula.terms[0].account_key if formula.terms else "table"
                results.append(
                    _formula_check_result(item, layout.key, formula, tolerance, account_key)
                )
            continue
        if layout.key == "functional_expense_research_allocation":
            formula = discover_expense_summary_formula(candidates, tolerance=tolerance)
            results.append(_formula_check_result(item, layout.key, formula, tolerance))
            continue
        if layout.key == "employee_benefit_expense_allocation":
            for formula in discover_employee_benefit_expense_formulas(
                candidates,
                tolerance=tolerance,
            ):
                if formula.status != MATCHED:
                    continue
                account_key = formula.terms[0].account_key if formula.terms else "table"
                results.append(
                    _formula_check_result(item, layout.key, formula, tolerance, account_key)
                )
            continue
        if layout.key == "employee_benefit_maturity_summary":
            for formula in discover_liquidity_maturity_formulas(
                candidates,
                tolerance=tolerance,
            ):
                account_key = formula.terms[0].account_key if formula.terms else "table"
                results.append(
                    _formula_check_result(item, layout.key, formula, tolerance, account_key)
                )
            continue
        if layout.key == "lease_liability_maturity_summary":
            for formula in discover_liquidity_maturity_formulas(
                candidates,
                tolerance=tolerance,
            ):
                account_key = formula.terms[0].account_key if formula.terms else "table"
                results.append(
                    _formula_check_result(item, layout.key, formula, tolerance, account_key)
                )
            continue
        if layout.key == "lease_liability_current_noncurrent_summary":
            formula = discover_lease_liability_split_formula(candidates, tolerance=tolerance)
            results.append(_formula_check_result(item, layout.key, formula, tolerance))
            continue
        if layout.key == "provision_current_noncurrent_summary":
            for formula in discover_provision_column_total_formulas(
                candidates,
                tolerance=tolerance,
            ):
                account_key = formula.terms[0].account_key if formula.terms else "table"
                results.append(
                    _formula_check_result(item, layout.key, formula, tolerance, account_key)
                )
            continue
        for account_key, account_candidates in _candidate_groups(candidates).items():
            formula = discover_rollforward_formula(account_candidates, tolerance=tolerance)
            results.append(_formula_check_result(item, layout.key, formula, tolerance, account_key))
    return results


def _formula_check_result(item, layout_key, formula, tolerance, account_key="table"):
    return CheckResult(
        check_id=(
            f"layout_formula:{item.note_no}:table{item.table_index}:"
            f"{layout_key}:{account_key}:{formula.formula_key}"
        ),
        check_type="note_layout_formula_check",
        status=formula.status,
        scope="note",
        note_no=item.note_no,
        title=_formula_title(layout_key, formula.formula_key, account_key),
        expected=formula.expected,
        actual=formula.actual,
        difference=formula.difference,
        tolerance=formula.tolerance,
        reason=(
            "layout-aware note formula closes"
            if formula.status == MATCHED
            else formula.reason
        ),
        evidence=[
            CheckEvidence(
                term.label,
                term.amount,
                f"{term.table_source}/row:{term.row_index}/col:{term.column_index}",
            )
            for term in formula.terms
        ],
    )


def _candidate_groups(candidates):
    grouped = {}
    for candidate in candidates:
        grouped.setdefault(candidate.account_key, []).append(candidate)
    return {
        key: grouped[key]
        for key in sorted(
            grouped,
            key=lambda key: min(
                (candidate.row_index, candidate.column_index) for candidate in grouped[key]
            ),
        )
    }


def _period_account_key(formula) -> str:
    for term in formula.terms:
        if term.role == "tax_expense_total":
            period = term.label.rsplit(" ", 1)[-1]
            return f"{term.account_key}:{period}"
    if formula.terms:
        return formula.terms[0].account_key
    return "table"


def _row_account_key(formula) -> str:
    if formula.terms:
        return f"row{formula.terms[0].row_index}"
    return "table"


def _formula_title(layout_key: str, formula_key: str, account_key: str) -> str:
    if layout_key == "inventory_allowance_rollforward" and formula_key == "signed_rollforward":
        return "재고자산 평가충당금 증감표 검산"
    if layout_key == "provision_rollforward" and formula_key == "signed_rollforward":
        return f"충당부채 증감표 검산 - {account_key}"
    if layout_key == "defined_benefit_rollforward" and formula_key == "signed_rollforward":
        return f"확정급여 변동표 검산 - {account_key}"
    if layout_key == "asset_period_rollforward_summary" and formula_key in {
        "rollforward",
        "signed_rollforward",
    }:
        period = account_key.rsplit(":", 1)[-1] if ":" in account_key else account_key
        return f"자산 기간별 증감표 검산 - {period}"
    if layout_key == "asset_two_label_row_rollforward_summary" and formula_key == "signed_rollforward":
        return f"자산 두 라벨 행 증감표 검산 - {account_key}"
    if layout_key == "asset_component_column_summary" and formula_key == "asset_component_total":
        label = account_key.split(":", 1)[1] if ":" in account_key else account_key
        return f"자산 구성열 합계 검산 - {label}"
    if layout_key == "debt_instrument_detail_summary" and formula_key in {
        "debt_split",
        "debt_component_split",
    }:
        return f"차입금/사채 상세표 검산 - {account_key}"
    if layout_key == "earnings_per_share_summary" and formula_key == "earnings_per_share":
        return f"주당이익 산식 검산 - {account_key}"
    if layout_key == "dividend_payout_summary" and formula_key == "dividend_payout_ratio":
        period = account_key.rsplit(":", 1)[-1] if ":" in account_key else account_key
        return f"현금배당성향 검산 - {period}"
    if layout_key == "loss_allowance_rollforward" and formula_key == "signed_rollforward":
        return f"손실충당금 변동표 검산 - {account_key}"
    if layout_key == "credit_risk_exposure_summary" and formula_key == "credit_risk_exposure_total":
        return "신용위험 최대노출 합계 검산"
    if layout_key == "financial_instrument_fair_value_summary" and formula_key == "financial_fair_value_total":
        return "금융상품 공정가치 합계 검산"
    if layout_key == "financial_fair_value_level_summary" and formula_key == "financial_fair_value_level_total":
        return f"금융상품 공정가치 수준별 합계 검산 - {account_key}"
    if layout_key == "tax_expense_composition_summary" and formula_key == "tax_expense_composition_total":
        period = account_key.rsplit(":", 1)[-1] if ":" in account_key else account_key
        return f"법인세비용 구성 검산 - {period}"
    if layout_key == "financial_instrument_category_summary" and formula_key == "financial_category_total":
        return f"금융상품 범주별 합계 검산 - {account_key}"
    if layout_key == "financial_instrument_category_summary" and formula_key == "financial_category_column_total":
        category = account_key.split(":", 1)[1] if ":" in account_key else account_key
        return f"금융상품 범주별 열 합계 검산 - {category}"
    if layout_key in {
        "receivable_carrying_amount_summary",
        "receivable_present_value_carrying_summary",
    } and formula_key == "receivable_carrying_total":
        return f"매출채권 장부금액 구성 검산 - {account_key}"
    if layout_key == "receivable_loss_allowance_aging_summary" and formula_key == "receivable_aging_bucket_total":
        label = {
            "trade_receivables_gross_aging": "총 장부금액",
            "trade_receivables_loss_allowance_aging": "손실충당금",
        }.get(account_key, account_key)
        return f"매출채권 연체구간 합계 검산 - {label}"
    if layout_key == "inventory_carrying_amount_summary" and formula_key == "inventory_carrying_total":
        return f"재고자산 장부금액 구성 검산 - {account_key}"
    if layout_key == "functional_expense_research_allocation" and formula_key == "expense_summary_total":
        return "연구개발비 기능별 배부 합계 검산"
    if layout_key == "employee_benefit_expense_allocation" and formula_key == "employee_benefit_expense_total":
        period = account_key.rsplit(":", 1)[-1] if ":" in account_key else account_key
        return f"퇴직급여 비용 배부 합계 검산 - {period}"
    if layout_key == "employee_benefit_maturity_summary" and formula_key == "liquidity_maturity_total":
        if account_key == "defined_benefit_expected_contributions":
            return "확정급여 예상기여금 만기 합계 검산"
        return "확정급여 지급예상액 만기 합계 검산"
    if layout_key == "lease_liability_maturity_summary" and formula_key == "liquidity_maturity_total":
        return f"리스부채 만기 합계 검산 - {account_key}"
    if layout_key == "lease_liability_current_noncurrent_summary" and formula_key == "lease_liability_split_total":
        return "리스부채 유동/비유동 합계 검산"
    if layout_key == "provision_current_noncurrent_summary" and formula_key == "provision_column_total":
        return f"충당부채 유동/비유동 구성 합계 검산 - {account_key}"
    if layout_key == "net_debt_bridge" and formula_key == "signed_rollforward":
        return f"재무활동 부채 변동표 검산 - {account_key}"
    return f"{layout_key} {formula_key} 검산"
