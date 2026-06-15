from dart_footing_reconciler.checks import CheckEvidence, CheckResult
from dart_footing_reconciler.document import FullReport
from dart_footing_reconciler.supporting_harnesses import PriorReportHarness, StatementCrossHarness
from dart_footing_reconciler.verification_harness import (
    LAYER_PRIOR_REPORT,
    LAYER_STATEMENT_CROSS,
    VerificationContext,
)


def _check(check_id: str, check_type: str) -> CheckResult:
    return CheckResult(
        check_id=check_id,
        check_type=check_type,
        status="matched",
        scope="report",
        note_no="",
        title=check_id,
        expected=100,
        actual=100,
        difference=0,
        tolerance=1,
        reason="matched",
        evidence=[CheckEvidence("본문", 100, "statement:bs/table:0/row:1/col:1")],
    )


def test_statement_cross_harness_wraps_statement_ties(monkeypatch):
    def fake_statement_ties(report, *, tolerance):
        return [_check("bs-equation", "statement_bs_equation")]

    monkeypatch.setattr("dart_footing_reconciler.supporting_harnesses.check_statement_ties", fake_statement_ties)

    context = VerificationContext(FullReport("sample.html", "Sample", [], []), None, tolerance=1)
    harness = StatementCrossHarness()

    assert harness.harness_id == "statement_cross"
    assert harness.layer == LAYER_STATEMENT_CROSS
    assert [check.check_type for check in harness.run(context)] == ["statement_bs_equation"]


def test_prior_report_harness_skips_when_prior_report_is_missing(monkeypatch):
    called = False

    def fake_prior(current_report, prior_report, *, tolerance):
        nonlocal called
        called = True
        return [_check("prior", "prior_year_beginning_balance_match")]

    monkeypatch.setattr("dart_footing_reconciler.supporting_harnesses.check_prior_year_reconciliation", fake_prior)

    context = VerificationContext(FullReport("sample.html", "Sample", [], []), None, tolerance=1)
    harness = PriorReportHarness()

    assert harness.harness_id == "prior_report"
    assert harness.layer == LAYER_PRIOR_REPORT
    assert harness.run(context) == []
    assert called is False


def test_prior_report_harness_runs_when_prior_report_exists(monkeypatch):
    def fake_prior(current_report, prior_report, *, tolerance):
        return [_check("prior", "prior_year_beginning_balance_match")]

    monkeypatch.setattr("dart_footing_reconciler.supporting_harnesses.check_prior_year_reconciliation", fake_prior)

    current = FullReport("current.html", "Sample", [], [])
    prior = FullReport("prior.html", "Sample", [], [])
    context = VerificationContext(current, prior, tolerance=1)

    assert [check.check_type for check in PriorReportHarness().run(context)] == [
        "prior_year_beginning_balance_match"
    ]
