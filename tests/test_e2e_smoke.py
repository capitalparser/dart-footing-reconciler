"""End-to-end smoke test: fixture parse → checks → evidence_cockpit HTML export.

If no real DART HTML fixture is found the test is skipped, so it is safe in
clean CI environments.  When a fixture IS present, the full pipeline must
produce a valid evidence_cockpit HTML with no regressions.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from dart_footing_reconciler.check_pipeline import assemble_report_checks
from dart_footing_reconciler.checks_statement_ties import check_statement_ties
from dart_footing_reconciler.document import parse_full_report
from dart_footing_reconciler.report_html import export_audit_reconciliation_html

# ── Fixture discovery ─────────────────────────────────────────────────────────

_SEARCH_ROOTS = [
    Path(__file__).parent / "fixtures",
    Path(__file__).parent / "data",
    Path(__file__).parent,
]

_ENV_VAR = "DART_FIXTURE_HTML"


def _find_fixture() -> Path | None:
    """Return the first .html file found in known test data locations."""
    import os

    env = os.environ.get(_ENV_VAR)
    if env:
        p = Path(env)
        if p.is_file():
            return p

    for root in _SEARCH_ROOTS:
        if not root.is_dir():
            continue
        candidates = sorted(root.glob("*.html"))
        if candidates:
            return candidates[0]

    return None


_FIXTURE = _find_fixture()

_SKIP_REASON = (
    "No DART HTML fixture found. "
    f"Place a file in tests/fixtures/*.html or set {_ENV_VAR}=<path>."
)


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.skipif(_FIXTURE is None, reason="fixture present — skip-guard not needed")
def test_no_fixture_guard() -> None:
    """Always passes when no fixture is present; documents the skip contract."""
    assert _FIXTURE is None


@pytest.mark.skipif(_FIXTURE is None, reason=_SKIP_REASON)
def test_e2e_parse_checks_export(tmp_path: Path) -> None:
    """Full pipeline: parse → statement-ties check → HTML export → assertions."""
    assert _FIXTURE is not None  # for type checker

    # Step 1 — parse
    report = parse_full_report(_FIXTURE, company=_FIXTURE.stem)
    assert report is not None
    assert isinstance(report.company, str)

    # Step 2 — run statement-ties checks (always available)
    ties = check_statement_ties(report)
    assert isinstance(ties, list)

    # Step 3 — run full check suite (harness pipeline)
    all_checks = assemble_report_checks(report, None, tolerance=1)
    assert isinstance(all_checks, list)

    # Combine both check sets (ties may already be in all_checks via
    # StatementCrossHarness, but combining is idempotent for assertions)
    combined = all_checks if all_checks else ties

    # Step 4 — export HTML
    out = tmp_path / "smoke_report.html"
    result_path = export_audit_reconciliation_html(
        report,
        combined,
        out,
        company_name=report.company,
    )

    # Step 5 — structural assertions
    assert result_path.exists(), "export_audit_reconciliation_html must return existing path"
    assert result_path.stat().st_size > 0, "output file must not be empty"

    content = result_path.read_text(encoding="utf-8")

    assert "<!DOCTYPE html>" in content, "must be a valid HTML5 document"
    assert "evidence_cockpit" in content or "sidebar-bg" in content, (
        "must carry PAS evidence_cockpit design token"
    )
    assert report.company in content, (
        f"company name '{report.company}' must appear in output"
    )
    assert "verdict-banner" in content, "must include verdict-banner section"

    # At least one row should carry a verification status class
    verified_rows = re.findall(
        r'class="[^"]*verified-(ok|warn|uncertain)[^"]*"', content
    )
    assert len(verified_rows) > 0, (
        "output must contain at least one verified-ok/verified-warn/verified-uncertain row"
    )
