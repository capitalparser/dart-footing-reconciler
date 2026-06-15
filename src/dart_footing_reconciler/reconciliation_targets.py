from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReconciliationTarget:
    key: str
    account_key: str
    assertion_type: str
    statement_source: str
    note_source: str
    required_adjustments: tuple[str, ...] = ()
    supporting: bool = False


RECONCILIATION_TARGETS: tuple[ReconciliationTarget, ...] = (
    ReconciliationTarget(
        "property_plant_equipment.balance",
        "property_plant_equipment",
        "balance",
        "statement_financial_position",
        "note_ending_carrying_amount",
    ),
    ReconciliationTarget(
        "property_plant_equipment.acquisitions_cashflow",
        "property_plant_equipment",
        "cashflow_acquisition",
        "statement_cash_flows",
        "note_cash_like_acquisitions",
        ("unpaid_acquisitions", "leases", "business_combinations", "transfers"),
    ),
    ReconciliationTarget(
        "property_plant_equipment.disposals_cashflow",
        "property_plant_equipment",
        "cashflow_disposal",
        "statement_cash_flows",
        "note_disposal_proceeds_evidence",
        ("carrying_amount", "disposal_gain_loss"),
    ),
    ReconciliationTarget(
        "intangible_assets.balance",
        "intangible_assets",
        "balance",
        "statement_financial_position",
        "note_ending_carrying_amount",
    ),
    ReconciliationTarget(
        "intangible_assets.acquisitions_cashflow",
        "intangible_assets",
        "cashflow_acquisition",
        "statement_cash_flows",
        "note_cash_like_acquisitions",
        ("unpaid_acquisitions", "transfers"),
    ),
    ReconciliationTarget(
        "intangible_assets.disposals_cashflow",
        "intangible_assets",
        "cashflow_disposal",
        "statement_cash_flows",
        "note_disposal_proceeds_evidence",
        ("carrying_amount", "disposal_gain_loss"),
    ),
    ReconciliationTarget(
        "trade_receivables.balance",
        "trade_receivables",
        "balance",
        "statement_financial_position",
        "note_trade_receivables_detail",
    ),
    ReconciliationTarget(
        "property_plant_equipment.depreciation_expense_allocation",
        "property_plant_equipment",
        "expense_allocation",
        "note_expense_by_nature",
        "note_asset_depreciation_allocation",
    ),
    ReconciliationTarget(
        "intangible_assets.amortization_expense_allocation",
        "intangible_assets",
        "expense_allocation",
        "note_expense_by_nature",
        "note_asset_amortization_allocation",
    ),
    ReconciliationTarget(
        "lease_liabilities.financing_cashflow",
        "lease_liabilities",
        "cashflow_financing_net",
        "statement_cash_flows",
        "note_financing_liability_cashflow",
    ),
    ReconciliationTarget(
        "borrowings.financing_cashflow",
        "borrowings",
        "cashflow_financing_net",
        "statement_cash_flows",
        "note_financing_liability_cashflow",
    ),
    ReconciliationTarget(
        "bonds.financing_cashflow",
        "bonds",
        "cashflow_financing_net",
        "statement_cash_flows",
        "note_financing_liability_cashflow",
    ),
    ReconciliationTarget(
        "prior_year.ending_to_current_beginning",
        "all_movement_accounts",
        "prior_ending_to_current_beginning",
        "prior_year_note_ending",
        "current_year_note_beginning",
    ),
    ReconciliationTarget(
        "supporting.table_totals",
        "all_note_tables",
        "table_total",
        "note_components",
        "note_displayed_total",
        supporting=True,
    ),
)
