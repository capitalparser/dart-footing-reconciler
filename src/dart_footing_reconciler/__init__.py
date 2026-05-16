"""DART DSD/HTML footing and cash flow reconciliation."""

from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.footing import foot_table
from dart_footing_reconciler.html_tables import extract_tables
from dart_footing_reconciler.scan import scan_html

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "extract_tables",
    "foot_table",
    "parse_amount",
    "scan_html",
]
