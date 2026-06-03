"""DART DSD/HTML footing and cash flow reconciliation."""

from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.audit_workbook import export_audit_workbook
from dart_footing_reconciler.document import parse_full_report
from dart_footing_reconciler.excel import export_company_workbook, export_validation_workbook
from dart_footing_reconciler.footing import foot_table
from dart_footing_reconciler.html_tables import extract_tables
from dart_footing_reconciler.local_report import foot_local_report, load_local_report
from dart_footing_reconciler.scan import scan_html
from dart_footing_reconciler.taxonomy import classify_report
from dart_footing_reconciler.validation import run_manifest

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "export_audit_workbook",
    "export_company_workbook",
    "export_validation_workbook",
    "extract_tables",
    "foot_local_report",
    "foot_table",
    "load_local_report",
    "parse_amount",
    "parse_full_report",
    "run_manifest",
    "scan_html",
    "classify_report",
]
