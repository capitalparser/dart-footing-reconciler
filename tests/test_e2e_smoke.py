"""End-to-end smoke test: parse → checks → evidence_cockpit HTML export."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from dart_footing_reconciler.checks_statement_ties import check_statement_ties
from dart_footing_reconciler.document import (
    FullReport, ReportBlock, ReportSection, ReportTable, SourceLocation,
)
from dart_footing_reconciler.report_html import export_audit_reconciliation_html


# ── Fixture discovery ─────────────────────────────────────────────────────────

def _find_dart_fixture() -> Path | None:
    env_path = os.environ.get("DART_FIXTURE_HTML")
    if env_path:
        p = Path(env_path)
        return p if p.exists() else None
    base = Path(__file__).parent
    for pattern in ["fixtures/*.html", "data/*.html", "*.html"]:
        hits = sorted(base.glob(pattern))
        if hits:
            return hits[0]
    return None


_FIXTURE = _find_dart_fixture()


# ── Synthetic pipeline test (always runs in CI) ───────────────────────────────

def _synthetic_report() -> FullReport:
    """Minimal but realistic FullReport for pipeline smoke test."""
    loc = SourceLocation("statement:재무상태표", 0, 0)
    bs_table = ReportTable(
        index=0,
        rows=[
            ["구분", "당기", "전기"],
            ["자산총계", "1,000,000", "900,000"],
            ["부채총계", "600,000", "550,000"],
            ["자본총계", "400,000", "350,000"],
        ],
        heading="재무상태표",
        location=loc,
    )
    bs_block = ReportBlock("table", "", bs_table, loc)
    bs_section = ReportSection(
        section_id="statement:재무상태표",
        title="재무상태표",
        kind="statement",
        note_no="",
        blocks=[bs_block],
    )
    return FullReport(
        source="test.html",
        company="테스트(주)",
        statements=[bs_section],
        notes=[],
    )


def test_synthetic_pipeline(tmp_path: Path) -> None:
    """Full pipeline with synthetic FullReport — always runs in CI."""
    report = _synthetic_report()
    checks = check_statement_ties(report, tolerance=1)

    out = tmp_path / "report.html"
    result_path = export_audit_reconciliation_html(report, checks, out)

    assert result_path == out
    assert out.exists()
    content = out.read_text(encoding="utf-8")

    assert "<!DOCTYPE html>" in content
    assert "테스트(주)" in content
    assert "verdict-banner" in content
    # At least one check was produced
    assert len(checks) > 0
    # HTML contains some verification result class
    has_result = any(cls in content for cls in ("verified-ok", "verified-warn", "verified-uncertain"))
    assert has_result, "Expected at least one verified row CSS class in output"


# ── Real DART fixture test (skipped in CI if no fixture) ─────────────────────

@pytest.mark.skipif(
    _FIXTURE is None,
    reason="No real DART fixture — set DART_FIXTURE_HTML or add tests/fixtures/*.html",
)
def test_e2e_real_fixture(tmp_path: Path) -> None:
    """Full pipeline with a real DART filing — requires a fixture file."""
    from dart_footing_reconciler.document import parse_full_report  # noqa: PLC0415

    assert _FIXTURE is not None  # for type checker
    report = parse_full_report(_FIXTURE, company=_FIXTURE.stem)
    checks = check_statement_ties(report, tolerance=1)

    out = tmp_path / "report.html"
    export_audit_reconciliation_html(report, checks, out)

    content = out.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert report.company in content
    assert "verdict-banner" in content
    assert len(checks) > 0
