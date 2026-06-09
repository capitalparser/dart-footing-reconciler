from collections import Counter
from pathlib import Path

from dart_footing_reconciler.check_pipeline import assemble_report_checks
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
