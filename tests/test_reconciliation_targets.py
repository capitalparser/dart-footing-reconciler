from dart_footing_reconciler.reconciliation_targets import RECONCILIATION_TARGETS


def test_reconciliation_targets_include_primary_balance_and_cashflow_assertions():
    keys = {target.key for target in RECONCILIATION_TARGETS}

    assert "property_plant_equipment.balance" in keys
    assert "property_plant_equipment.acquisitions_cashflow" in keys
    assert "property_plant_equipment.disposals_cashflow" in keys
    assert "property_plant_equipment.depreciation_expense_allocation" in keys
    assert "intangible_assets.balance" in keys
    assert "intangible_assets.acquisitions_cashflow" in keys
    assert "intangible_assets.disposals_cashflow" in keys
    assert "intangible_assets.amortization_expense_allocation" in keys
    assert "lease_liabilities.financing_cashflow" in keys
    assert "borrowings.financing_cashflow" in keys
    assert "bonds.financing_cashflow" in keys
    assert "prior_year.ending_to_current_beginning" in keys
    assert "supporting.table_totals" in keys
