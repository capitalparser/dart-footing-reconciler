from dart_footing_reconciler import (
    __version__,
    build_coverage_report,
    build_note_inventory,
    build_note_semantic_extraction,
    classify_layout,
    classify_validation_relevance,
    detect_orientation,
    discover_component_net_formula,
    discover_credit_risk_exposure_formula,
    discover_credit_risk_exposure_formulas,
    discover_debt_split_formula,
    discover_defined_benefit_rollforward_formulas,
    discover_discontinued_operation_cashflow_formula,
    discover_discontinued_operation_income_formulas,
    discover_employee_benefit_expense_formulas,
    discover_expense_summary_formula,
    discover_financial_category_column_formulas,
    discover_financial_category_formulas,
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
    extract_verification_candidates,
    foot_local_report,
    review_disclosure_completeness,
)


def test_version() -> None:
    assert __version__ == "0.1.0"


def test_package_exposes_local_attachment_footing(tmp_path) -> None:
    source = tmp_path / "report.html"
    source.write_text(
        """
        <p>14. 유형자산</p>
        <p>당기 중 유형자산의 변동내용은 다음과 같습니다.</p>
        <table>
          <tr><th>구분</th><th>합계</th></tr>
          <tr><td>기초</td><td>1,000</td></tr>
          <tr><td>취득</td><td>250</td></tr>
          <tr><td>감가상각비</td><td>100</td></tr>
          <tr><td>기말</td><td>1,150</td></tr>
        </table>
        """,
        encoding="utf-8",
    )

    payload = foot_local_report(source)

    assert payload["input_format"] == "html"
    assert payload["summary"]["matched"] == 1


def test_package_exposes_note_coverage_helpers() -> None:
    assert callable(build_note_inventory)
    assert callable(build_note_semantic_extraction)
    assert callable(classify_layout)
    assert callable(build_coverage_report)
    assert callable(detect_orientation)
    assert callable(extract_verification_candidates)
    assert callable(discover_component_net_formula)
    assert callable(discover_credit_risk_exposure_formula)
    assert callable(discover_credit_risk_exposure_formulas)
    assert callable(discover_debt_split_formula)
    assert callable(discover_defined_benefit_rollforward_formulas)
    assert callable(discover_discontinued_operation_cashflow_formula)
    assert callable(discover_discontinued_operation_income_formulas)
    assert callable(discover_employee_benefit_expense_formulas)
    assert callable(discover_expense_summary_formula)
    assert callable(discover_financial_category_column_formulas)
    assert callable(discover_financial_category_formulas)
    assert callable(discover_financial_fair_value_level_formulas)
    assert callable(discover_inventory_carrying_formulas)
    assert callable(discover_lease_expense_formulas)
    assert callable(discover_lease_liability_split_formula)
    assert callable(discover_liquidity_maturity_formulas)
    assert callable(discover_net_debt_bridge_formulas)
    assert callable(discover_provision_column_total_formulas)
    assert callable(discover_receivable_aging_bucket_formulas)
    assert callable(discover_receivable_carrying_formulas)
    assert callable(discover_rollforward_formula)
    assert callable(discover_tax_expense_composition_formulas)
    assert callable(classify_validation_relevance)
    assert callable(review_disclosure_completeness)
