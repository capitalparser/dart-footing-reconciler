"""Deterministic note table layout classification."""

from __future__ import annotations

import re
from dataclasses import dataclass

from dart_footing_reconciler.note_inventory import NoteTableInventoryItem


@dataclass(frozen=True)
class LayoutClassification:
    key: str
    confidence: float
    evidence: tuple[str, ...]
    source: str


def classify_layout(item: NoteTableInventoryItem) -> LayoutClassification:
    headers = tuple(_compact(header) for header in item.headers)
    row_labels = tuple(_compact(label) for label in item.row_labels)
    title = _compact(f"{item.title} {item.heading}")

    if _is_asset_cost_accumulated_grant_total(title, headers):
        return LayoutClassification(
            key="asset_cost_accumulated_grant_total",
            confidence=0.9,
            evidence=(
                "title contains asset topic",
                "headers include 취득원가",
                "headers include 감가상각누계액",
                "headers include 정부보조금",
                "headers include 합계",
            ),
            source=item.source,
        )

    if _is_asset_component_column_summary(title, headers, row_labels):
        return LayoutClassification(
            key="asset_component_column_summary",
            confidence=0.85,
            evidence=(
                "asset topic in title or rows",
                "asset component columns",
                "headers include carrying amount",
            ),
            source=item.source,
        )

    if _is_investment_property_simple_net(title, headers, row_labels):
        return LayoutClassification(
            key="asset_investment_property_simple_net",
            confidence=0.75,
            evidence=(
                "title contains investment property",
                "headers repeat investment property family",
                "headers include investment property family total",
                "rows include investment property account",
            ),
            source=item.source,
        )

    if _is_asset_carrying_amount_total(title, headers, row_labels):
        return LayoutClassification(
            key="asset_carrying_amount_total",
            confidence=0.8,
            evidence=(
                "title contains asset topic",
                "headers include carrying amount or total",
                "rows include 기말 or 합계",
            ),
            source=item.source,
        )

    if _is_asset_measure_summary(title, headers, row_labels):
        return LayoutClassification(
            key="asset_measure_summary",
            confidence=0.85,
            evidence=(
                "asset topic in title or rows",
                "headers include gross amount",
                "headers include accumulated depreciation or amortization",
                "headers include carrying amount",
            ),
            source=item.source,
        )

    if _is_asset_cost_accumulated_summary(title, headers, row_labels):
        return LayoutClassification(
            key="asset_cost_accumulated_summary",
            confidence=0.85,
            evidence=(
                "asset topic in title or rows",
                "headers include gross amount",
                "headers include accumulated depreciation or amortization",
                "rows include total",
            ),
            source=item.source,
        )

    if _is_asset_stacked_measure_summary(headers, row_labels):
        return LayoutClassification(
            key="asset_stacked_measure_summary",
            confidence=0.85,
            evidence=(
                "asset topic in headers",
                "measure labels in rows",
                "rows include carrying amount total",
            ),
            source=item.source,
        )

    if _is_asset_movement_columns(title, headers, row_labels):
        return LayoutClassification(
            key="asset_movement_columns",
            confidence=0.85,
            evidence=(
                "asset topic in title or rows",
                "movement labels in headers",
                "asset labels in rows",
            ),
            source=item.source,
        )

    if _is_asset_period_rollforward_summary(title, headers, row_labels):
        return LayoutClassification(
            key="asset_period_rollforward_summary",
            confidence=0.85,
            evidence=(
                "title contains asset topic",
                "movement labels in headers",
                "period labels in rows",
            ),
            source=item.source,
        )

    if _is_asset_two_label_row_rollforward_summary(title, headers, row_labels):
        return LayoutClassification(
            key="asset_two_label_row_rollforward_summary",
            confidence=0.85,
            evidence=(
                "title contains asset topic",
                "asset account amount column",
                "movement labels in secondary row labels",
            ),
            source=item.source,
        )

    if _is_asset_row_movement_total(headers, row_labels):
        return LayoutClassification(
            key="asset_row_movement_total",
            confidence=0.85,
            evidence=(
                "asset movement labels in rows",
                "headers include asset total",
                "asset topic in rows",
            ),
            source=item.source,
        )

    if _is_asset_current_period_carrying_amount(title, headers, row_labels):
        return LayoutClassification(
            key="asset_current_period_carrying_amount",
            confidence=0.75,
            evidence=(
                "title contains asset topic",
                "headers include current period",
                "rows include carrying amount",
            ),
            source=item.source,
        )

    if _is_financial_fair_value_level_summary(title, headers, row_labels):
        return LayoutClassification(
            key="financial_fair_value_level_summary",
            confidence=0.85,
            evidence=(
                "title contains financial instruments",
                "fair value hierarchy level columns",
                "headers include total",
            ),
            source=item.source,
        )

    if _is_tax_expense_composition_summary(title, headers, row_labels):
        return LayoutClassification(
            key="tax_expense_composition_summary",
            confidence=0.85,
            evidence=(
                "title contains income tax topic",
                "period amount columns",
                "tax expense component rows",
            ),
            source=item.source,
        )

    if _is_financial_instrument_category_summary(title, headers, row_labels):
        total_evidence = (
            "financial category total header"
            if any(
                "범주합계" in header
                or header in {"금융자산", "금융부채", "합계", "총계"}
                for header in headers
            )
            else "financial category total row"
        )
        return LayoutClassification(
            key="financial_instrument_category_summary",
            confidence=0.85,
            evidence=(
                "title contains financial instruments",
                "financial instrument categories in headers",
                "account labels in rows",
                total_evidence,
            ),
            source=item.source,
        )

    if _is_financial_instrument_fair_value_summary(title, headers, row_labels):
        return LayoutClassification(
            key="financial_instrument_fair_value_summary",
            confidence=0.85,
            evidence=(
                "title contains financial instruments",
                "fair value amount column",
                "financial account rows include total",
            ),
            source=item.source,
        )

    if _is_receivable_present_value_carrying_summary(title, headers, row_labels):
        return LayoutClassification(
            key="receivable_present_value_carrying_summary",
            confidence=0.85,
            evidence=(
                "title contains receivables",
                "receivable present value discount columns",
                "receivable account labels in rows",
            ),
            source=item.source,
        )

    if _is_receivable_carrying_amount_summary(title, headers, row_labels):
        row_evidence = (
            "two label columns carry receivable account context"
            if _has_two_label_receivable_shape(headers, row_labels)
            else "receivable account labels in rows"
        )
        return LayoutClassification(
            key="receivable_carrying_amount_summary",
            confidence=0.85,
            evidence=(
                "title contains receivables",
                "receivable carrying amount columns",
                row_evidence,
            ),
            source=item.source,
        )

    if _is_loss_allowance_rollforward(title, headers, row_labels):
        return LayoutClassification(
            key="loss_allowance_rollforward",
            confidence=0.85,
            evidence=(
                "title contains receivables",
                "headers indicate financial asset categories",
                "loss allowance movement labels in rows",
            ),
            source=item.source,
        )

    if _is_receivable_loss_allowance_aging_summary(title, headers, row_labels):
        return LayoutClassification(
            key="receivable_loss_allowance_aging_summary",
            confidence=0.85,
            evidence=(
                "title contains receivables",
                "receivable aging bucket columns",
                "gross and loss allowance rows",
            ),
            source=item.source,
        )

    if _is_receivable_aging_status_summary(title, headers, row_labels):
        return LayoutClassification(
            key="receivable_aging_status_summary",
            confidence=0.85,
            evidence=(
                "title contains receivables",
                "receivable account labels in headers",
                "aging status rows include total",
            ),
            source=item.source,
        )

    if _is_inventory_allowance_rollforward(title, headers, row_labels):
        return LayoutClassification(
            key="inventory_allowance_rollforward",
            confidence=0.85,
            evidence=(
                "title contains inventories",
                "inventory allowance amount column",
                "inventory allowance movement labels in rows",
            ),
            source=item.source,
        )

    if _is_inventory_carrying_amount_summary(title, headers, row_labels):
        return LayoutClassification(
            key="inventory_carrying_amount_summary",
            confidence=0.85,
            evidence=(
                "title contains inventories",
                "inventory carrying amount column",
                "rows include inventory total",
            ),
            source=item.source,
        )

    if _is_functional_expense_allocation(title, headers, row_labels):
        return LayoutClassification(
            key="functional_expense_allocation",
            confidence=0.8,
            evidence=("functional expense columns", "depreciation or amortization rows"),
            source=item.source,
        )

    if _is_functional_expense_research_allocation(headers, row_labels):
        return LayoutClassification(
            key="functional_expense_research_allocation",
            confidence=0.85,
            evidence=("functional expense columns", "research and development expense row"),
            source=item.source,
        )

    if _is_functional_expense_single_row_allocation(title, headers, row_labels):
        return LayoutClassification(
            key="functional_expense_single_row_allocation",
            confidence=0.85,
            evidence=(
                "asset topic in title",
                "single functional expense row",
                "depreciation or amortization amount header",
            ),
            source=item.source,
        )

    if _is_employee_benefit_expense_allocation(title, headers, row_labels):
        return LayoutClassification(
            key="employee_benefit_expense_allocation",
            confidence=0.85,
            evidence=(
                "title contains employee benefits",
                "period amount columns",
                "employee benefit expense allocation rows",
            ),
            source=item.source,
        )

    if _is_selling_admin_expense_summary(title, headers, row_labels):
        return LayoutClassification(
            key="selling_admin_expense_summary",
            confidence=0.85,
            evidence=(
                "title contains selling and administrative expenses",
                "expense amount column",
                "rows include expense total",
            ),
            source=item.source,
        )

    if _is_operating_expense_summary(title, headers, row_labels):
        return LayoutClassification(
            key="operating_expense_summary",
            confidence=0.85,
            evidence=(
                "title contains operating expenses",
                "operating expense amount column",
                "rows include expense total",
            ),
            source=item.source,
        )

    if _is_debt_instrument_detail_summary(title, headers, row_labels):
        debt_shape_evidence = (
            "debt component columns"
            if _has_debt_component_column_shape(headers, row_labels)
            else "debt detail rows"
        )
        return LayoutClassification(
            key="debt_instrument_detail_summary",
            confidence=0.85,
            evidence=(
                "title contains borrowings or bonds",
                "debt instrument total column",
                debt_shape_evidence,
            ),
            source=item.source,
        )

    if _is_provision_current_noncurrent_summary(title, headers, row_labels):
        return LayoutClassification(
            key="provision_current_noncurrent_summary",
            confidence=0.85,
            evidence=(
                "title contains provisions",
                "provision current and non-current columns",
                "provision component rows",
                "provision total row",
            ),
            source=item.source,
        )

    if _is_provision_rollforward(title, headers, row_labels):
        return LayoutClassification(
            key="provision_rollforward",
            confidence=0.85,
            evidence=(
                "title contains provisions",
                "provision movement columns",
                "provision account rows",
                "provision account columns",
            ),
            source=item.source,
        )

    if _is_defined_benefit_rollforward(title, headers, row_labels):
        return LayoutClassification(
            key="defined_benefit_rollforward",
            confidence=0.85,
            evidence=(
                "title contains defined benefit topic",
                "defined benefit account columns",
                "benefit obligation movement rows",
            ),
            source=item.source,
        )

    if _is_employee_benefit_maturity_summary(title, headers, row_labels):
        row_evidence = (
            "employee benefit expected contribution row"
            if any(_is_employee_benefit_expected_contribution_row(row) for row in row_labels)
            else "employee benefit expected payment row"
        )
        return LayoutClassification(
            key="employee_benefit_maturity_summary",
            confidence=0.85,
            evidence=(
                "title contains defined benefit topic",
                "maturity bucket columns",
                row_evidence,
                "headers include total",
            ),
            source=item.source,
        )

    if _is_lease_liability_current_noncurrent_summary(title, headers, row_labels):
        return LayoutClassification(
            key="lease_liability_current_noncurrent_summary",
            confidence=0.85,
            evidence=(
                "title contains lease topic",
                "current and non-current lease liability rows",
                "rows include lease liability total",
                "headers include amount column",
            ),
            source=item.source,
        )

    if _is_lease_liability_maturity_summary(title, headers, row_labels):
        return LayoutClassification(
            key="lease_liability_maturity_summary",
            confidence=0.85,
            evidence=(
                "title contains lease topic",
                "maturity bucket columns",
                "lease liability maturity rows",
                "headers include total",
            ),
            source=item.source,
        )

    if _is_net_debt_bridge(title, headers, row_labels):
        return LayoutClassification(
            key="net_debt_bridge",
            confidence=0.85,
            evidence=(
                "title contains cash flow or debt bridge topic",
                "financial liability account columns",
                "net debt movement rows",
            ),
            source=item.source,
        )

    if _is_credit_risk_exposure_summary(title, headers, row_labels):
        return LayoutClassification(
            key="credit_risk_exposure_summary",
            confidence=0.85,
            evidence=(
                "title contains financial risk or credit risk topic",
                "credit risk exposure amount column",
                "credit risk exposure row",
                "financial asset rows",
                "rows include total",
            ),
            source=item.source,
        )

    if _is_liquidity_maturity_analysis(title, headers, row_labels):
        return LayoutClassification(
            key="liquidity_maturity_analysis",
            confidence=0.85,
            evidence=(
                "title contains liquidity risk or maturity analysis topic",
                "maturity bucket columns",
                "financial liability rows",
                "headers include total",
            ),
            source=item.source,
        )

    if _is_lease_expense_summary(title, headers, row_labels):
        return LayoutClassification(
            key="lease_expense_summary",
            confidence=0.85,
            evidence=(
                "title contains lease topic",
                "lease asset total column",
                "lease expense rows",
            ),
            source=item.source,
        )

    if _is_discontinued_operation_income_statement(title, headers, row_labels):
        return LayoutClassification(
            key="discontinued_operation_income_statement",
            confidence=0.85,
            evidence=(
                "title or headers contain discontinued operation topic",
                "discontinued operation income rows",
                "rows include intermediate profit totals",
            ),
            source=item.source,
        )

    if _is_discontinued_operation_cashflow_summary(title, headers, row_labels):
        return LayoutClassification(
            key="discontinued_operation_cashflow_summary",
            confidence=0.85,
            evidence=(
                "title or headers contain discontinued operation topic",
                "discontinued operation cash flow rows",
                "rows include cash flow total",
            ),
            source=item.source,
        )

    if _is_dividend_payout_summary(title, headers, row_labels):
        return LayoutClassification(
            key="dividend_payout_summary",
            confidence=0.85,
            evidence=(
                "title or rows contain dividend topic",
                "dividend payout ratio rows",
                "period columns",
            ),
            source=item.source,
        )

    if _is_earnings_per_share_summary(title, headers, row_labels):
        return LayoutClassification(
            key="earnings_per_share_summary",
            confidence=0.85,
            evidence=(
                "title or rows contain earnings per share topic",
                "earnings per share rows",
                "weighted-average share count row",
            ),
            source=item.source,
        )

    return LayoutClassification(
        key="unknown_layout",
        confidence=0.0,
        evidence=(),
        source=item.source,
    )


def _is_asset_cost_accumulated_grant_total(
    title: str,
    headers: tuple[str, ...],
) -> bool:
    return (
        _has_asset_topic(title)
        and any("취득원가" in header for header in headers)
        and any("감가상각누계액" in header or "상각누계액" in header for header in headers)
        and any("정부보조금" in header for header in headers)
        and any(header in {"합계", "총계"} for header in headers)
    )


def _is_asset_carrying_amount_total(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    return (
        _has_asset_topic(title)
        and any(any(alias in header for alias in ("장부금액", "장부가액", "합계")) for header in headers)
        and any(any(alias in row for alias in ("기말", "합계", "총계")) for row in row_labels)
    )


def _is_asset_component_column_summary(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    joined_rows = " ".join(row_labels)
    return (
        (_has_asset_topic(title) or _has_asset_topic(joined_rows))
        and any(_is_asset_component_header(header) for header in headers)
        and any("장부금액" in header or "장부가액" in header for header in headers)
        and any(_has_asset_topic(row) or "합계" in row or "총계" in row for row in row_labels)
    )


def _is_investment_property_simple_net(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    return (
        "투자부동산" in title
        and sum(1 for header in headers if "투자부동산" in header) >= 2
        and any("투자부동산합계" in header or "투자부동산총계" in header for header in headers)
        and any("투자부동산" in row for row in row_labels)
    )


def _is_asset_measure_summary(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    joined_rows = " ".join(row_labels)
    return (
        (_has_asset_topic(title) or _has_asset_topic(joined_rows))
        and any("총장부금액" in header or "취득원가" in header for header in headers)
        and any("감가상각누계" in header or "상각누계" in header for header in headers)
        and any("장부금액" in header or "장부가액" in header for header in headers)
    )


def _is_asset_cost_accumulated_summary(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    joined_rows = " ".join(row_labels)
    return (
        (_has_asset_topic(title) or _has_asset_topic(joined_rows))
        and any("총장부금액" in header or "취득원가" in header for header in headers)
        and any("감가상각누계" in header or "상각누계" in header for header in headers)
        and any(row in {"합계", "총계"} for row in row_labels)
    )


def _is_asset_stacked_measure_summary(
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    return (
        any(_has_asset_topic(header) for header in headers)
        and sum(1 for row in row_labels if any(alias in row for alias in ("장부금액", "장부가액"))) >= 2
        and any(
            any(alias in row for alias in ("장부금액합계", "장부가액합계", "순장부금액합계"))
            for row in row_labels
        )
    )


def _is_asset_movement_columns(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    joined_rows = " ".join(row_labels)
    movement_headers = sum(1 for header in headers if _is_movement_header(header))
    return (
        (_has_asset_topic(title) or _has_asset_topic(joined_rows))
        and movement_headers >= 2
        and _has_asset_topic(joined_rows)
    )


def _is_asset_row_movement_total(
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    joined_rows = " ".join(row_labels)
    row_movements = sum(1 for row in row_labels if _is_movement_header(row))
    return (
        _has_asset_topic(joined_rows)
        and row_movements >= 3
        and any("합계" in header or "총계" in header for header in headers)
    )


def _is_asset_period_rollforward_summary(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    movement_headers = sum(1 for header in headers if _is_movement_header(header))
    return (
        _has_asset_topic(title)
        and movement_headers >= 2
        and any("기초" in header for header in headers)
        and any("기말" in header for header in headers)
        and sum(1 for row in row_labels if row in {"당기", "전기"}) >= 2
    )


def _is_asset_two_label_row_rollforward_summary(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    return (
        _has_asset_topic(title)
        and any(_has_asset_topic(header) for header in headers)
        and sum(1 for row in row_labels if "변동" in row and "조정" in row) >= 3
    )


def _is_asset_current_period_carrying_amount(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    return (
        _has_asset_topic(title)
        and any(header in {"당기", "당기말", "당기말현재", "당기현재"} for header in headers)
        and any(any(alias in row for alias in ("장부금액", "장부가액", "순장부금액")) for row in row_labels)
    )


def _is_functional_expense_allocation(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    joined_rows = " ".join(row_labels)
    return (
        _count_functional_expense_headers(headers) >= 2
        and any(
            alias in joined_rows
            for alias in ("감가상각비", "상각비", "무형자산상각비", "사용권자산상각비")
        )
    )


def _is_functional_expense_research_allocation(
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    return (
        _count_functional_expense_headers(headers) >= 2
        and any(_is_research_development_expense_row(row) for row in row_labels)
    )


def _is_functional_expense_single_row_allocation(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    return (
        _has_asset_topic(title)
        and any("기능별항목" in row for row in row_labels)
        and sum(1 for header in headers if _is_depreciation_or_amortization_header(header)) >= 1
    )


def _is_employee_benefit_expense_allocation(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    return (
        any(alias in title for alias in ("퇴직급여", "종업원급여", "확정급여"))
        and _count_period_headers(headers) >= 2
        and sum(1 for row in row_labels if _is_employee_benefit_expense_component_row(row)) >= 2
        and any(row in {"합계", "총계"} for row in row_labels)
    )


def _is_financial_instrument_category_summary(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    category_headers = sum(1 for header in headers if _is_financial_category_header(header))
    account_rows = sum(1 for row in row_labels if _is_financial_account_row(row))
    has_total_header = any(
        "범주합계" in header
        or header in {"금융자산", "금융부채", "합계", "총계"}
        for header in headers
    )
    has_total_row = any(_is_financial_category_total_row(row) for row in row_labels)
    return (
        ("금융상품" in title or category_headers >= 3)
        and category_headers >= 2
        and (has_total_header or has_total_row)
        and account_rows >= 2
    )


def _is_financial_category_total_row(value: str) -> bool:
    return value in {"합계", "총계", "금융자산", "금융부채", "총금융자산", "총금융부채"}


def _is_financial_instrument_fair_value_summary(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    return (
        "금융상품" in title
        and any(header == "공정가치" for header in headers)
        and sum(1 for row in row_labels if _is_financial_account_row(row)) >= 2
        and any(row in {"금융자산", "총금융자산", "금융부채", "총금융부채"} for row in row_labels)
    )


def _is_financial_fair_value_level_summary(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    return (
        "금융상품" in title
        and "공정가치" in title
        and _count_fair_value_level_headers(headers) >= 2
        and any("합계" in header or "합" in header for header in headers)
        and any("금융자산" in row or "금융부채" in row for row in row_labels)
    )


def _is_tax_expense_composition_summary(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    return (
        "법인세" in title
        and _count_period_headers(headers) >= 1
        and not any(_is_tax_rate_reconciliation_row(row) for row in row_labels)
        and not any(_is_complex_capital_tax_detail_row(row) for row in row_labels)
        and any(_is_tax_expense_total_row(row) for row in row_labels)
        and any(_is_current_tax_expense_component_row(row) for row in row_labels)
        and any(_is_deferred_tax_expense_component_row(row) for row in row_labels)
    )


def _is_earnings_per_share_summary(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    joined_rows = " ".join(row_labels)
    return (
        ("주당" in title or "주당" in joined_rows)
        and any("보통주" in header for header in headers)
        and any("가중평균유통보통주식수" in row for row in row_labels)
        and any(_is_eps_profit_row(row) for row in row_labels)
        and any(_is_eps_result_row(row) for row in row_labels)
    )


def _is_dividend_payout_summary(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    joined_rows = " ".join(row_labels)
    return (
        ("배당" in title or "배당" in joined_rows)
        and _count_period_headers(headers) >= 1
        and any("당기순이익" in row for row in row_labels)
        and any("현금배당금총액" in row for row in row_labels)
        and any("현금배당성향" in row for row in row_labels)
    )


def _is_receivable_carrying_amount_summary(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    joined_rows = " ".join(row_labels)
    return (
        ("매출채권" in title or "기타채권" in title or "매출채권" in joined_rows)
        and any("총장부금액" in header for header in headers)
        and any(
            "손상차손누계액" in header
            or "대손충당금" in header
            or "손실충당금" in header
            for header in headers
        )
        and any("장부금액합계" in header or "장부가액합계" in header for header in headers)
        and (
            sum(1 for row in row_labels if _is_receivable_account_row(row)) >= 2
            or _has_two_label_receivable_shape(headers, row_labels)
        )
    )


def _has_two_label_receivable_shape(
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    return (
        len(headers) >= 5
        and all(header in {"", "구분"} for header in headers[:2])
        and sum(
            1
            for row in row_labels
            if row in {"유동", "비유동", "기타비유동채권"}
            or "비유동채권" in row
        )
        >= 2
    )


def _is_receivable_present_value_carrying_summary(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    joined_rows = " ".join(row_labels)
    return (
        ("매출채권" in title or "기타채권" in title or "매출채권" in joined_rows)
        and any("총장부금액" in header for header in headers)
        and any("현재가치할인차금" in header for header in headers)
        and any("장부금액합계" in header or "장부가액합계" in header for header in headers)
        and sum(1 for row in row_labels if _is_receivable_account_row(row)) >= 2
    )


def _is_loss_allowance_rollforward(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    return (
        ("매출채권" in title or "기타채권" in title)
        and any("금융자산" in header or "금융상품" in header or "분류" in header for header in headers)
        and _count_loss_allowance_movements(row_labels) >= 3
        and (
            _has_loss_allowance_context(title, row_labels)
            or _has_financial_asset_allowance_movement_shape(row_labels)
        )
    )


def _is_receivable_aging_status_summary(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    return (
        ("매출채권" in title or "기타채권" in title)
        and sum(1 for header in headers if _is_receivable_account_row(header)) >= 2
        and any("연체상태합계" in row for row in row_labels)
    )


def _is_receivable_loss_allowance_aging_summary(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    return (
        ("매출채권" in title or "기타채권" in title)
        and any(_is_receivable_aging_bucket_header(header) for header in headers)
        and any("합계" in header or "합" == header for header in headers)
        and any("총장부금액" in row for row in row_labels)
        and any("손실충당금" in row or "대손충당금" in row for row in row_labels)
    )


def _is_inventory_carrying_amount_summary(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    joined_rows = " ".join(row_labels)
    return (
        ("재고자산" in title or _has_inventory_topic(joined_rows))
        and any("총장부금액" in header or "장부금액합계" in header for header in headers)
        and any(_is_inventory_total_row(row) for row in row_labels)
        and _has_inventory_topic(joined_rows)
    )


def _is_inventory_allowance_rollforward(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    return (
        "재고자산" in title
        and any("재고자산평가충당금" in header for header in headers)
        and _count_inventory_allowance_movements(row_labels) >= 3
        and any("기초" in row for row in row_labels)
        and any("기말" in row for row in row_labels)
    )


def _is_inventory_total_row(label: str) -> bool:
    return (
        label in {"합계", "총계", "재고자산"}
        or "재고자산합계" in label
        or label
        in {"유동재고자산", "비유동재고자산", "총유동재고자산", "총비유동재고자산", "총재고자산"}
    )


def _is_debt_instrument_detail_summary(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    return (
        ("차입금" in title or "사채" in title)
        and (
            (
                any("차입금명칭" in header for header in headers)
                and (
                    any("합계" in header for header in headers)
                    or any(row in {"소계", "합계", "총계"} for row in row_labels)
                )
                and _count_debt_detail_rows(row_labels) >= 2
            )
            or _has_debt_component_column_shape(headers, row_labels)
        )
    )


def _has_debt_component_column_shape(
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    return (
        any("명목금액" in header for header in headers)
        and any("유동성사채" in header or "유동성차입금" in header for header in headers)
        and any("사채할인발행차금" in header or "현재가치할인차금" in header for header in headers)
        and any("비유동" in header and ("사채" in header or "차입금" in header) for header in headers)
        and any("차입금명칭합계" in row or "합계" in row for row in row_labels)
    )


def _is_selling_admin_expense_summary(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    joined_rows = " ".join(row_labels)
    return (
        ("판매비와관리비" in title or "판매비와일반관리비" in title)
        and any(header in {"금액", "공시금액"} for header in headers)
        and any(row in {"합계", "총계"} for row in row_labels)
        and _count_selling_admin_expense_rows(row_labels) >= 2
        and ("판관비" in joined_rows or "판매비와관리비" in joined_rows)
    )


def _is_operating_expense_summary(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    joined_rows = " ".join(row_labels)
    return (
        "영업비용" in title
        and any(header in {"금액", "공시금액"} for header in headers)
        and any(row in {"합계", "총계"} for row in row_labels)
        and _count_operating_expense_rows(row_labels) >= 2
        and any(alias in joined_rows for alias in ("매출원가", "판관비", "판매비와관리비"))
    )


def _is_provision_rollforward(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    if "충당부채" not in title:
        return False
    column_movement_shape = (
        _count_provision_movement_headers(headers) >= 3
        and any("충당부채" in row for row in row_labels)
    )
    row_movement_shape = (
        _count_provision_account_headers(headers) >= 2
        and any("기초" in row for row in row_labels)
        and any("기말" in row for row in row_labels)
        and any("충당부채" in row for row in row_labels)
    )
    return column_movement_shape or row_movement_shape


def _is_provision_current_noncurrent_summary(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    return (
        "충당부채" in title
        and _count_provision_current_noncurrent_headers(headers) >= 1
        and sum(1 for row in row_labels if _is_provision_component_row(row)) >= 2
        and any(_is_provision_total_row(row) for row in row_labels)
    )


def _is_defined_benefit_rollforward(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    return (
        any("확정급여채무" in header for header in headers)
        and any("사외적립자산" in header for header in headers)
        and any("기초" in row for row in row_labels)
        and any("기말" in row for row in row_labels)
        and (
            "확정급여" in title
            or "순확정급여" in title
            or "퇴직급여" in title
            or any("순확정급여" in row or "당기근무원가" in row for row in row_labels)
        )
    )


def _is_net_debt_bridge(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    return (
        (
            "재무활동에서생기는부채" in title
            or "영업으로부터창출된현금" in title
            or "현금흐름표" in title
            or "현금흐름" in title
        )
        and _count_financial_liability_headers(headers) >= 2
        and _has_net_debt_bridge_rows(row_labels)
    )


def _is_credit_risk_exposure_summary(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    vertical_amount_column = (
        (
            "익스포저" in title
            or "신용위험익스포저" in title
            or _has_single_credit_risk_amount_column(headers)
        )
        and any(_is_credit_risk_exposure_amount_header(header) for header in headers)
        and sum(1 for row in row_labels if _is_credit_risk_asset_row(row)) >= 2
        and any(row in {"합계", "총계"} for row in row_labels)
    )
    horizontal_exposure_row = (
        _has_credit_risk_exposure_row(row_labels)
        and _has_credit_risk_exposure_total_header(headers)
        and sum(1 for header in headers if _is_credit_risk_exposure_component_header(header)) >= 2
    )
    return vertical_amount_column or horizontal_exposure_row


def _is_liquidity_maturity_analysis(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    return (
        ("유동성위험" in title or "만기분석" in title or _has_maturity_analysis_shape(headers, row_labels))
        and _count_maturity_bucket_headers(headers) >= 2
        and any("합계" in header for header in headers)
        and sum(1 for row in row_labels if _is_maturity_liability_row(row)) >= 2
    )


def _is_employee_benefit_maturity_summary(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    return (
        ("퇴직급여" in title or "확정급여" in title or "종업원급여" in title)
        and _count_maturity_bucket_headers(headers) >= 2
        and any("합계" in header for header in headers)
        and any(_is_employee_benefit_maturity_row(row) for row in row_labels)
    )


def _is_lease_liability_maturity_summary(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    return (
        "리스" in title
        and _count_maturity_bucket_headers(headers) >= 2
        and any("합계" in header for header in headers)
        and any(_is_lease_liability_maturity_row(row) for row in row_labels)
    )


def _is_lease_liability_current_noncurrent_summary(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    return (
        "리스" in title
        and _has_amount_column(headers)
        and _count_maturity_bucket_headers(headers) < 2
        and any(_is_current_lease_liability_row(row) for row in row_labels)
        and any(_is_noncurrent_lease_liability_row(row) for row in row_labels)
        and any(_is_total_lease_liability_row(row) for row in row_labels)
    )


def _is_lease_expense_summary(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    return (
        "리스" in title
        and any("자산합계" in header for header in headers)
        and sum(1 for row in row_labels if _is_lease_expense_row(row)) >= 2
    )


def _is_discontinued_operation_income_statement(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    joined_rows = " ".join(row_labels)
    return (
        ("중단영업" in title or any("중단영업" in header for header in headers))
        and sum(1 for row in row_labels if _is_discontinued_operation_income_row(row)) >= 5
        and any("매출총이익" in row for row in row_labels)
        and any("법인세비용차감전" in row for row in row_labels)
        and "중단영업순이익" in joined_rows
    )


def _is_discontinued_operation_cashflow_summary(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    return (
        ("중단영업" in title or any("중단영업" in header for header in headers))
        and sum(1 for row in row_labels if _is_discontinued_operation_cashflow_row(row)) >= 3
        and any(row in {"합계", "총계"} for row in row_labels)
    )


def _has_asset_topic(value: str) -> bool:
    return any(topic in value for topic in ("유형자산", "무형자산", "투자부동산", "사용권자산", "영업권"))


def _is_asset_component_header(value: str) -> bool:
    return any(
        alias in value
        for alias in (
            "상각자산",
            "미상각자산",
            "개발중인무형자산",
            "개발중인자산",
            "건설중인자산",
        )
    )


def _is_movement_header(value: str) -> bool:
    return any(alias in value for alias in ("기초", "취득", "증가", "처분", "감가상각", "상각", "손상", "대체", "기말"))


def _is_financial_category_header(value: str) -> bool:
    return any(
        alias in value
        for alias in (
            "당기손익",
            "기타포괄손익",
            "공정가치",
            "상각후원가",
            "금융자산",
            "금융부채",
            "범주합계",
        )
    )


def _is_financial_account_row(value: str) -> bool:
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


def _is_receivable_account_row(value: str) -> bool:
    return any(alias in value for alias in ("매출채권", "미수금", "미수수익", "대여금", "보증금"))


def _is_receivable_aging_bucket_header(value: str) -> bool:
    normalized = value.replace(" ", "")
    return "연체" in normalized or "회수기간" in normalized or "손상채권" in normalized


def _has_inventory_topic(value: str) -> bool:
    return any(alias in value for alias in ("재고자산", "제품", "상품", "원재료", "저장품", "미착품", "미완성주택", "기타재고"))


def _count_functional_expense_headers(headers: tuple[str, ...]) -> int:
    return sum(
        1
        for header in headers
        if any(alias in header for alias in ("매출원가", "판매비와일반관리비", "판매비와관리비", "기능별항목합계"))
    )


def _is_research_development_expense_row(value: str) -> bool:
    return ("연구" in value and "개발" in value) or "경상연구개발비" in value


def _count_loss_allowance_movements(values: tuple[str, ...]) -> int:
    return sum(
        1
        for value in values
        if _is_loss_allowance_movement(value)
    )


def _has_loss_allowance_context(title: str, values: tuple[str, ...]) -> bool:
    return "손실충당금" in title or any(
        "손실충당금" in value or "손상차손누계액" in value for value in values
    )


def _has_financial_asset_allowance_movement_shape(values: tuple[str, ...]) -> bool:
    return any("기초금융자산" in value for value in values) and any(
        "기말금융자산" in value for value in values
    )


def _is_loss_allowance_movement(value: str) -> bool:
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


def _count_inventory_allowance_movements(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_inventory_allowance_movement(value))


def _is_inventory_allowance_movement(value: str) -> bool:
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


def _count_debt_detail_rows(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_debt_detail_row(value))


def _count_provision_movement_headers(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_provision_movement_header(value))


def _count_provision_account_headers(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_provision_account_header(value))


def _count_provision_current_noncurrent_headers(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_provision_current_noncurrent_header(value))


def _is_provision_account_header(value: str) -> bool:
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


def _is_provision_current_noncurrent_header(value: str) -> bool:
    return (
        value in {"유동", "비유동"}
        or "유동충당부채" in value
        or "비유동충당부채" in value
    )


def _is_provision_component_row(value: str) -> bool:
    return _is_provision_account_header(value) and not _is_provision_total_row(value)


def _is_provision_total_row(value: str) -> bool:
    return "충당부채" in value and ("합계" in value or "총계" in value)


def _count_selling_admin_expense_rows(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_selling_admin_expense_row(value))


def _count_operating_expense_rows(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_operating_expense_row(value))


def _is_employee_benefit_expense_component_row(value: str) -> bool:
    return any(alias in value for alias in ("판관비", "판매비", "관리비", "매출원가", "제조원가"))


def _count_financial_liability_headers(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_financial_liability_header(value))


def _count_maturity_bucket_headers(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_maturity_bucket_header(value))


def _count_fair_value_level_headers(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_fair_value_level_header(value))


def _count_period_headers(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_period_header(value))


def _has_maturity_analysis_shape(
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    return (
        _count_maturity_bucket_headers(headers) >= 2
        and any("합계" in header for header in headers)
        and sum(1 for row in row_labels if _is_maturity_liability_row(row)) >= 3
    )


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


def _is_debt_detail_row(value: str) -> bool:
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


def _is_selling_admin_expense_row(value: str) -> bool:
    return any(
        alias in value
        for alias in (
            "급여",
            "상여",
            "퇴직급여",
            "복리후생비",
            "지급수수료",
            "감가상각비",
            "대손상각비",
            "판매비와관리비",
            "판관비",
            "합계",
        )
    )


def _is_operating_expense_row(value: str) -> bool:
    return any(
        alias in value
        for alias in (
            "매출원가",
            "판관비",
            "판매비와관리비",
            "급여",
            "상여",
            "퇴직급여",
            "복리후생비",
            "감가상각비",
            "무형자산상각비",
            "지급수수료",
            "합계",
        )
    )


def _is_depreciation_or_amortization_header(value: str) -> bool:
    return any(alias in value for alias in ("감가상각비", "상각비", "무형자산상각비"))


def _is_provision_movement_header(value: str) -> bool:
    return any(
        alias in value
        for alias in ("기초", "전입", "연중사용액", "사용액", "연결범위변동", "매각예정분류", "기말")
    )


def _is_financial_liability_header(value: str) -> bool:
    return any(alias in value for alias in ("차입금", "사채", "리스부채"))


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


def _has_credit_risk_exposure_row(values: tuple[str, ...]) -> bool:
    return any("신용위험에대한최대노출정도" in value for value in values)


def _has_credit_risk_exposure_total_header(values: tuple[str, ...]) -> bool:
    return any(_is_credit_risk_exposure_total_header(value) for value in values)


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


def _is_fair_value_level_header(value: str) -> bool:
    normalized = value.replace("(", "").replace(")", "")
    return normalized in {"수준1", "수준2", "수준3"} or normalized.startswith("수준")


def _is_period_header(value: str) -> bool:
    return value in {"당기", "전기", "당기말", "전기말", "당분기", "전분기"}


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
        alias in value for alias in ("부담액", "부담내역", "추납액", "환급액", "당기법인세비용")
    )


def _is_deferred_tax_expense_component_row(value: str) -> bool:
    if "기초" in value or "기말" in value:
        return False
    return "이연법인세" in value and any(
        alias in value for alias in ("변동액", "변동")
    )


def _is_capital_tax_expense_component_row(value: str) -> bool:
    return "자본에직접" in value and "법인세" in value


def _is_tax_rate_reconciliation_row(value: str) -> bool:
    return any(
        alias in value
        for alias in ("법인세비용차감전", "적용세율", "유효세율", "법인세율로계산", "세율로계산")
    )


def _is_complex_capital_tax_detail_row(value: str) -> bool:
    return any(
        alias in value
        for alias in ("순확정급여", "기타포괄손익", "위험회피", "외환차이", "회계정책변경")
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


def _is_employee_benefit_maturity_row(value: str) -> bool:
    return (
        _is_employee_benefit_expected_payment_row(value)
        or _is_employee_benefit_expected_contribution_row(value)
    )


def _is_lease_liability_maturity_row(value: str) -> bool:
    return any(
        alias in value
        for alias in ("리스부채", "최소리스료", "최소리스료의현재가치", "할인되지않은리스부채")
    )


def _is_lease_expense_row(value: str) -> bool:
    return any(
        alias in value
        for alias in ("감가상각비", "리스부채에대한이자비용", "단기리스료", "소액자산리스료")
    )


def _has_amount_column(headers: tuple[str, ...]) -> bool:
    return any(
        alias in header
        for header in headers
        for alias in ("공시금액", "금액", "당기", "당기말", "합계")
    ) or len(headers) == 2


def _is_current_lease_liability_row(value: str) -> bool:
    return "비유동" not in value and (
        "유동리스부채" in value or "유동성리스부채" in value
    )


def _is_noncurrent_lease_liability_row(value: str) -> bool:
    return "비유동" in value and "리스부채" in value


def _is_total_lease_liability_row(value: str) -> bool:
    return ("리스부채" in value and ("합계" in value or "총" in value)) or value == "합계"


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


def _has_single_credit_risk_amount_column(headers: tuple[str, ...]) -> bool:
    non_empty = [header for header in headers if header]
    return non_empty in (["신용위험"], ["신용위험익스포저"], ["신용위험노출액"])


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", value or "")
