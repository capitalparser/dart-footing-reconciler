"""In-browser verification entrypoints for the offline DART verify app."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from dart_footing_reconciler.check_pipeline import assemble_report_checks
from dart_footing_reconciler.document import FullReport, parse_full_report
from dart_footing_reconciler.local_report import UnsupportedReportFormatError
from dart_footing_reconciler.report_html import _ReportMeta, _build_html

_PDF_ERROR_MESSAGE = (
    "PDF footing is not supported yet; attach the DART DSD or HTML report instead."
)


def verify_html_report(
    html_text: str,
    *,
    company: str = "",
    prior_text: str | None = None,
    tolerance: int = 1,
) -> str:
    """Return evidence_cockpit HTML for a DART HTML/DSD report."""
    report = _parse_report_text(html_text, company=company, filename="current.html")
    prior_report = (
        _parse_report_text(prior_text, company=company, filename="prior.html")
        if prior_text is not None
        else None
    )
    checks = assemble_report_checks(report, prior_report, tolerance=tolerance)
    meta = _ReportMeta(company=company or report.company or "회사", period="")
    return _build_html(report, checks, meta)


def _parse_report_text(html_text: str, *, company: str, filename: str) -> FullReport:
    if html_text.lstrip().startswith("%PDF"):
        raise UnsupportedReportFormatError(_PDF_ERROR_MESSAGE)
    with TemporaryDirectory(prefix="dart-verify-") as tmpdir:
        path = Path(tmpdir) / filename
        path.write_text(html_text, encoding="utf-8")
        return parse_full_report(path, company=company)
