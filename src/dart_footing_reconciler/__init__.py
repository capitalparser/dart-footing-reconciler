"""DART DSD/HTML footing and cash flow reconciliation."""

from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.audit_workbook import export_audit_workbook
from dart_footing_reconciler.coverage import build_coverage_report
from dart_footing_reconciler.document import parse_full_report
from dart_footing_reconciler.excel import export_company_workbook, export_validation_workbook
from dart_footing_reconciler.formula_discovery import (
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
)
from dart_footing_reconciler.footing import foot_table
from dart_footing_reconciler.html_tables import extract_tables
from dart_footing_reconciler.layout_variants import classify_layout
from dart_footing_reconciler.local_report import foot_local_report, load_local_report
from dart_footing_reconciler.note_inventory import build_note_inventory
from dart_footing_reconciler.orientation import detect_orientation
from dart_footing_reconciler.scan import scan_html
from dart_footing_reconciler.taxonomy import classify_report
from dart_footing_reconciler.validation import run_manifest
from dart_footing_reconciler.validation_relevance import classify_validation_relevance
from dart_footing_reconciler.verification_candidates import extract_verification_candidates

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "build_coverage_report",
    "build_note_inventory",
    "classify_layout",
    "detect_orientation",
    "discover_component_net_formula",
    "discover_credit_risk_exposure_formula",
    "discover_credit_risk_exposure_formulas",
    "discover_debt_split_formula",
    "discover_defined_benefit_rollforward_formulas",
    "discover_discontinued_operation_cashflow_formula",
    "discover_discontinued_operation_income_formulas",
    "discover_employee_benefit_expense_formulas",
    "discover_expense_summary_formula",
    "discover_financial_category_column_formulas",
    "discover_financial_category_formulas",
    "discover_financial_fair_value_level_formulas",
    "discover_inventory_carrying_formulas",
    "discover_lease_expense_formulas",
    "discover_lease_liability_split_formula",
    "discover_liquidity_maturity_formulas",
    "discover_net_debt_bridge_formulas",
    "discover_provision_column_total_formulas",
    "discover_receivable_aging_bucket_formulas",
    "discover_receivable_carrying_formulas",
    "discover_rollforward_formula",
    "discover_tax_expense_composition_formulas",
    "classify_validation_relevance",
    "export_audit_workbook",
    "export_company_workbook",
    "export_validation_workbook",
    "extract_tables",
    "extract_verification_candidates",
    "foot_local_report",
    "foot_table",
    "load_local_report",
    "parse_amount",
    "parse_full_report",
    "run_manifest",
    "scan_html",
    "classify_report",
]
