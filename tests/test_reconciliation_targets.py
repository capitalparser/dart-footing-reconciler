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
    assert "bonds.issuance_cashflow" in keys
    assert "bonds.redemption_cashflow" in keys
    assert "bonds.financing_cashflow" in keys
    assert "prior_year.ending_to_current_beginning" in keys
    assert "supporting.table_totals" in keys

    bond_net = next(
        target
        for target in RECONCILIATION_TARGETS
        if target.key == "bonds.financing_cashflow"
    )
    assert bond_net.account_key == "bonds"
    assert bond_net.assertion_type == "cashflow_financing_net"
    assert bond_net.statement_source == "statement_cash_flows"
    assert bond_net.note_source == "note_financing_liability_cashflow"


def test_investment_property_cashflow_targets_registered():
    keys = {target.key for target in RECONCILIATION_TARGETS}

    assert "investment_property.acquisitions_cashflow" in keys
    assert "investment_property.disposals_cashflow" in keys

    acq = next(
        target
        for target in RECONCILIATION_TARGETS
        if target.key == "investment_property.acquisitions_cashflow"
    )
    assert acq.account_key == "investment_property"
    assert acq.assertion_type == "cashflow_acquisition"
    assert acq.statement_source == "statement_cash_flows"
    assert acq.note_source == "note_cash_like_acquisitions"
    assert acq.required_adjustments == ("unpaid_acquisitions", "transfers")

    disposal = next(
        target
        for target in RECONCILIATION_TARGETS
        if target.key == "investment_property.disposals_cashflow"
    )
    assert disposal.account_key == "investment_property"
    assert disposal.assertion_type == "cashflow_disposal"
    assert disposal.statement_source == "statement_cash_flows"
    assert disposal.note_source == "note_disposal_proceeds_evidence"
    assert disposal.required_adjustments == (
        "carrying_amount",
        "disposal_gain_loss",
    )
