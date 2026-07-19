from __future__ import annotations

import pytest

from dart_footing_reconciler.local_report import UnsupportedReportFormatError
from dart_footing_reconciler.verify_app import verify_attachment, verify_html_report


SAMPLE_REPORT = """
<p>재무상태표</p>
<table>
  <tr><th>구분</th><th>당기</th></tr>
  <tr><td>자산총계</td><td>1,000</td></tr>
</table>
<p>재무제표 주석</p>
<p>8. 매출채권 및 기타채권</p>
<table>
  <tr><th>구분</th><th>금액</th></tr>
  <tr><td>유동</td><td>40</td></tr>
  <tr><td>비유동</td><td>60</td></tr>
  <tr><td>합계</td><td>100</td></tr>
</table>
"""


def test_verify_html_report_returns_desktop_source_workbench() -> None:
    report_html = verify_html_report(SAMPLE_REPORT, company="샘플회사", tolerance=1)

    assert report_html.startswith("<!DOCTYPE html>")
    assert 'data-report-profile="audit-workbench"' in report_html
    assert 'class="source-nav"' in report_html
    assert 'class="source-stage"' in report_html
    assert 'class="reconciliation-drawer"' in report_html
    assert "재무제표 본문" in report_html
    assert "각 주석" in report_html


def test_verify_attachment_returns_audit_workbench_for_dsd(tmp_path) -> None:
    source = tmp_path / "company.dsd"
    source.write_text(SAMPLE_REPORT, encoding="utf-8")

    report_html = verify_attachment(source, company="회사")

    assert report_html
    assert 'data-report-profile="audit-workbench"' in report_html


def test_verify_html_report_omits_legacy_dashboard_and_runtime_language() -> None:
    report_html = verify_html_report(SAMPLE_REPORT, company="샘플회사", tolerance=1)

    assert 'id="panel-legend"' not in report_html
    assert "검증 범례" not in report_html
    assert "PyOdide" not in report_html
    assert "LOCAL VERIFY" not in report_html
    assert "React" not in report_html
    assert "Next.js" not in report_html


def test_verify_html_report_rejects_pdf_signature_with_engine_message() -> None:
    with pytest.raises(
        UnsupportedReportFormatError, match="PDF footing is not supported"
    ):
        verify_html_report("%PDF-1.7\n%...")
