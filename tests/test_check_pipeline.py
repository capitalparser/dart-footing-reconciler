from collections import Counter
from pathlib import Path

from dart_footing_reconciler.check_pipeline import assemble_report_checks, assemble_report_harness_runs
from dart_footing_reconciler.cli import _run_workpaper_checks
from dart_footing_reconciler.corpus import _run_checks
from dart_footing_reconciler.document import parse_full_report


INVENI = Path("out/corpus/run_2026-06-06-inveni-one/raw/inveni_2024_20250310000926.html")


def _norm(checks):
    return sorted(
        (
            check.check_id,
            check.check_type,
            check.status,
            check.expected,
            check.actual,
            tuple((evidence.source, evidence.amount) for evidence in check.evidence),
        )
        for check in checks
    )


def test_corpus_and_workpaper_checks_are_identical():
    report = parse_full_report(INVENI)
    a = _norm(_run_checks(report, None, tolerance=1))
    b = _norm(_run_workpaper_checks(report, None, tolerance=1))
    assert a == b, [item for item in a if item not in b][:5]


def test_assemble_includes_fs_and_cfs_note_matches():
    report = parse_full_report(INVENI)
    types = Counter(
        check.check_type for check in assemble_report_checks(report, None, tolerance=1)
    )
    assert types["fs_note_match"] >= 5, types
    assert types["cfs_note_match"] >= 1, types


def test_assemble_includes_prior_column_matches():
    report = parse_full_report(INVENI)
    types = Counter(
        check.check_type for check in assemble_report_checks(report, None, tolerance=1)
    )

    assert types["prior_column_fs_note"] + types["prior_column_rollforward"] >= 1, types


def test_assemble_includes_statement_ties():
    from collections import Counter
    report = parse_full_report(INVENI)
    types = Counter(
        check.check_type for check in assemble_report_checks(report, None, tolerance=1)
    )
    # BS equation: INVENI에는 부채총계 행 없을 수 있으므로 >= 1 (MATCHED or PARSE_UNCERTAIN)
    assert types["statement_bs_equation"] >= 1, types
    # cash_tie: BS 현금 ↔ CF 기말 현금 대사
    assert types["statement_cash_tie"] >= 1, types
    # equity_tie: BS 자본총계 ↔ SCE 기말
    assert types["statement_equity_tie"] >= 1, types


def test_assemble_report_harness_runs_exposes_primary_layers():
    report = parse_full_report(INVENI)
    runs = assemble_report_harness_runs(report, None, tolerance=1)

    layer_by_id = {run.harness_id: run.layer for run in runs}
    assert layer_by_id["statement_note"] == "statement_note"
    assert layer_by_id["note_internal"] == "note_internal"
    assert layer_by_id["statement_cross"] == "statement_cross"
    assert layer_by_id["prior_report"] == "prior_report"


def test_assemble_report_checks_flattens_harness_runs():
    report = parse_full_report(INVENI)
    flattened = _norm(assemble_report_checks(report, None, tolerance=1))
    from_runs = _norm(
        [
            check
            for run in assemble_report_harness_runs(report, None, tolerance=1)
            for check in run.checks
        ]
    )

    assert flattened == from_runs


def _scoped_section(section_id, title, kind, note_no, scope):
    from dart_footing_reconciler.document import ReportSection

    return ReportSection(section_id, title, kind, note_no, [], scope)


def test_split_report_by_scope_two_scopes():
    from dart_footing_reconciler.document import FullReport
    from dart_footing_reconciler.check_pipeline import split_report_by_scope

    report = FullReport(
        source="s.html",
        company="Sample",
        statements=[
            _scoped_section("statement:재무상태표", "재무상태표", "statement", "", "consolidated"),
            _scoped_section("statement:재무상태표", "재무상태표", "statement", "", "separate"),
        ],
        notes=[
            _scoped_section("note:1", "일반사항", "note", "1", "consolidated"),
            _scoped_section("note:1", "일반사항", "note", "1", "separate"),
        ],
    )
    slices = split_report_by_scope(report)
    assert len(slices) == 2
    assert [s.statements[0].scope for s in slices] == ["consolidated", "separate"]
    assert all(
        {b.scope for b in s.statements} == {b.scope for b in s.notes} for s in slices
    )


def test_assemble_report_harness_runs_threads_consolidation_basis_to_context(monkeypatch):
    from dart_footing_reconciler.checks import CheckResult
    from dart_footing_reconciler.document import FullReport

    class BasisHarness:
        harness_id = "basis"
        layer = "statement_note"

        def run(self, context):
            return [
                CheckResult(
                    check_id=f"basis:{context.consolidation_basis}",
                    check_type="basis_probe",
                    status="matched",
                    scope="report",
                    note_no="",
                    title="basis probe",
                    expected=1,
                    actual=1,
                    difference=0,
                    tolerance=1,
                    reason="matched",
                    evidence=[],
                    consolidation_basis=context.consolidation_basis,
                )
            ]

    monkeypatch.setattr(
        "dart_footing_reconciler.check_pipeline.default_report_harnesses",
        lambda: [BasisHarness()],
    )
    report = FullReport(
        source="s.html",
        company="Sample",
        statements=[
            _scoped_section("statement:재무상태표", "재무상태표", "statement", "", "consolidated"),
            _scoped_section("statement:재무상태표", "재무상태표", "statement", "", "separate"),
        ],
        notes=[
            _scoped_section("note:1", "일반사항", "note", "1", "consolidated"),
            _scoped_section("note:1", "일반사항", "note", "1", "separate"),
        ],
    )

    runs = assemble_report_harness_runs(report, None, tolerance=1)

    assert [run.checks[0].consolidation_basis for run in runs] == [
        "consolidated",
        "separate",
    ]


def test_split_report_by_scope_single_scope_passthrough():
    from dart_footing_reconciler.document import FullReport
    from dart_footing_reconciler.check_pipeline import split_report_by_scope

    report = FullReport(
        source="s.html",
        company="Sample",
        statements=[_scoped_section("statement:재무상태표", "재무상태표", "statement", "", "")],
        notes=[_scoped_section("note:1", "일반사항", "note", "1", "separate")],
    )
    slices = split_report_by_scope(report)
    assert len(slices) == 1
    assert slices[0] is report
