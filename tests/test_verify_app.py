from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from dart_footing_reconciler.check_pipeline import assemble_report_checks
from dart_footing_reconciler.checks import (
    EXPLAINABLE_GAP,
    MATCHED,
    NOT_TESTED,
    PARSE_UNCERTAIN,
    UNEXPLAINED_GAP,
)
from dart_footing_reconciler.document import parse_full_report
from dart_footing_reconciler.report_html import _filter_results_for_scope
from dart_footing_reconciler.local_report import UnsupportedReportFormatError
from dart_footing_reconciler.verify_app import verify_html_report


FIXTURE = Path("out/corpus/run_2026-06-06-inveni-one/raw/inveni_2024_20250310000926.html")


def test_verify_html_report_returns_evidence_cockpit_with_direct_check_counts() -> None:
    html_text = FIXTURE.read_text(encoding="utf-8")

    cockpit_html = verify_html_report(html_text, company="INVENI", tolerance=1)

    report = parse_full_report(FIXTURE, company="INVENI")
    checks = assemble_report_checks(report, None, tolerance=1)

    assert cockpit_html.startswith("<!DOCTYPE html>")
    assert 'data-cockpit-profile="evidence_cockpit"' in cockpit_html
    assert 'class="panel summary-panel verdict-banner' in cockpit_html
    assert 'data-report-scope="consolidated"' in cockpit_html
    assert 'data-report-scope="separate"' in cockpit_html

    for scope in ("consolidated", "separate"):
        scoped_checks = _filter_results_for_scope(checks, report, scope)
        counts = Counter(check.status for check in scoped_checks)
        assert _status_card(counts[MATCHED], "검증완료") in cockpit_html
        assert _status_card(counts[EXPLAINABLE_GAP], "설명차이") in cockpit_html
        assert _status_card(counts[UNEXPLAINED_GAP] + counts[PARSE_UNCERTAIN], "확인필요") in cockpit_html
        assert _status_card(counts[NOT_TESTED], "미검증") in cockpit_html


def test_verify_html_report_includes_report_html_legend_panel() -> None:
    html_text = FIXTURE.read_text(encoding="utf-8")

    cockpit_html = verify_html_report(html_text, company="INVENI", tolerance=1)

    assert 'id="panel-legend"' in cockpit_html
    assert "검증 범례" in cockpit_html


def test_verify_html_report_rejects_pdf_signature_with_engine_message() -> None:
    with pytest.raises(UnsupportedReportFormatError, match="PDF footing is not supported"):
        verify_html_report("%PDF-1.7\n%...")


def _status_card(value: int, label: str) -> str:
    return f'<span class="status-value">{value}</span>\n  <span class="status-label">{label}</span>'
