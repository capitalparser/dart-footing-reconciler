from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from dart_footing_reconciler.check_pipeline import assemble_report_checks
from dart_footing_reconciler.checks import MATCHED, PARSE_UNCERTAIN, UNEXPLAINED_GAP
from dart_footing_reconciler.document import parse_full_report
from dart_footing_reconciler.local_report import UnsupportedReportFormatError
from dart_footing_reconciler.verify_app import verify_html_report


FIXTURE = Path("out/corpus/run_2026-06-06-inveni-one/raw/inveni_2024_20250310000926.html")


def test_verify_html_report_returns_evidence_cockpit_with_direct_check_counts() -> None:
    html_text = FIXTURE.read_text(encoding="utf-8")

    cockpit_html = verify_html_report(html_text, company="INVENI", tolerance=1)

    report = parse_full_report(FIXTURE, company="INVENI")
    checks = assemble_report_checks(report, None, tolerance=1)
    counts = Counter(check.status for check in checks)

    assert cockpit_html.startswith("<!DOCTYPE html>")
    assert 'data-cockpit-profile="evidence_cockpit"' in cockpit_html
    assert 'class="verdict-banner' in cockpit_html
    assert _kpi_tile(counts[MATCHED], "검증 완료") in cockpit_html
    assert _kpi_tile(counts[UNEXPLAINED_GAP], "검토 필요") in cockpit_html
    assert _kpi_tile(counts[PARSE_UNCERTAIN], "파싱 불확실") in cockpit_html
    assert _kpi_tile(len(checks), "전체") in cockpit_html


def test_verify_html_report_rejects_pdf_signature_with_engine_message() -> None:
    with pytest.raises(UnsupportedReportFormatError, match="PDF footing is not supported"):
        verify_html_report("%PDF-1.7\n%...")


def _kpi_tile(value: int, label: str) -> str:
    return f'<div class="kpi-val">{value}</div><div class="kpi-name">{label}</div>'
