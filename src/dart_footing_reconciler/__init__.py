"""DART DSD/HTML footing and cash flow reconciliation."""

from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.excel import export_company_workbook, export_validation_workbook
from dart_footing_reconciler.footing import foot_table
from dart_footing_reconciler.html_tables import extract_tables
from dart_footing_reconciler.scan import scan_html
from dart_footing_reconciler.validation import run_manifest

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "export_company_workbook",
    "export_validation_workbook",
    "extract_tables",
    "foot_table",
    "parse_amount",
    "run_manifest",
    "scan_html",
]
