from dart_footing_reconciler.checks import CheckEvidence, CheckResult
from dart_footing_reconciler.document import FullReport, ReportBlock, ReportSection, ReportTable, SourceLocation
from dart_footing_reconciler.note_internal_harness import NoteInternalHarness
from dart_footing_reconciler.verification_harness import LAYER_NOTE_INTERNAL, VerificationContext


def _check(check_id: str, check_type: str) -> CheckResult:
    return CheckResult(
        check_id=check_id,
        check_type=check_type,
        status="matched",
        scope="report",
        note_no="1",
        title=check_id,
        expected=100,
        actual=100,
        difference=0,
        tolerance=1,
        reason="matched",
        evidence=[CheckEvidence("주석", 100, "note:1/table:0/row:1/col:1")],
    )


def _report_with_note_table() -> FullReport:
    table = ReportTable(
        0,
        [["구분", "당기"], ["합계", "100"]],
        "1. 테스트 주석",
        SourceLocation("note:1", 0, 0),
    )
    note = ReportSection(
        "note:1",
        "테스트 주석",
        "note",
        "1",
        [ReportBlock("table", "", table, table.location)],
    )
    return FullReport("sample.html", "Sample", [], [note])


def test_note_internal_harness_exposes_layer_identity():
    harness = NoteInternalHarness()

    assert harness.harness_id == "note_internal"
    assert harness.layer == LAYER_NOTE_INTERNAL


def test_note_internal_harness_runs_note_content_checks(monkeypatch):
    calls: list[str] = []

    def fake_totals(table, *, note_no, tolerance):
        calls.append(f"totals:{note_no}")
        return [_check("total", "total_check")]

    def fake_assertions(report, *, tolerance):
        calls.append("assertions")
        return [_check("assertion", "note_rollforward_check")]

    def fake_formulas(report, *, tolerance):
        calls.append("formulas")
        return [_check("formula", "note_layout_formula_check")]

    def fake_note_note(report, *, tolerance):
        calls.append("note-note")
        return [_check("note-note", "note_note_match")]

    monkeypatch.setattr("dart_footing_reconciler.note_internal_harness.check_table_totals", fake_totals)
    monkeypatch.setattr("dart_footing_reconciler.note_internal_harness.check_note_assertions", fake_assertions)
    monkeypatch.setattr("dart_footing_reconciler.note_internal_harness.check_layout_formula_assertions", fake_formulas)
    monkeypatch.setattr("dart_footing_reconciler.note_internal_harness.check_note_note_matches", fake_note_note)

    context = VerificationContext(_report_with_note_table(), None, tolerance=1)
    checks = NoteInternalHarness().run(context)

    assert calls == ["totals:1", "assertions", "formulas", "note-note"]
    assert [check.check_type for check in checks] == [
        "total_check",
        "note_rollforward_check",
        "note_layout_formula_check",
        "note_note_match",
    ]


def test_appropriation_formula_check_with_transfer_in():
    """이입액이 있는 처분계산서: 차기이월 = 미처분 + 이입액 - 처분액."""
    from dart_footing_reconciler.document import (
        FullReport,
        ReportBlock,
        ReportSection,
        ReportTable,
        SourceLocation,
    )
    from dart_footing_reconciler.note_internal_harness import NoteInternalHarness
    from dart_footing_reconciler.verification_harness import VerificationContext

    table = ReportTable(
        0,
        [
            ["구 분", "당기"],
            ["I. 미처분이익잉여금(미처리결손금)", "(753,371,078)"],
            ["II. 임의적립금 등의 이입액", "900,000,000"],
            ["III. 이익잉여금처분액", "118,171,275"],
            ["IV. 차기이월미처분이익잉여금", "28,457,647"],
        ],
        "이익잉여금처분계산서",
        SourceLocation("statement:이익잉여금처분계산서", 0, 0),
    )
    section = ReportSection(
        "statement:이익잉여금처분계산서",
        "이익잉여금처분계산서",
        "statement",
        "",
        [ReportBlock("table", "", table, table.location)],
        "separate",
    )
    report = FullReport("sample.html", "Sample Co", [section], [])
    checks = NoteInternalHarness().run(VerificationContext(report=report, prior_report=None, tolerance=1))
    formula = [c for c in checks if c.check_type == "appropriation_formula_check"]
    assert len(formula) == 1
    assert formula[0].status == "matched"
    assert formula[0].difference == 0
    assert all(
        e.source.startswith("statement:이익잉여금처분계산서/table:0/")
        for e in formula[0].evidence
    )


def test_appropriation_formula_check_flags_gap():
    from dart_footing_reconciler.document import (
        FullReport,
        ReportBlock,
        ReportSection,
        ReportTable,
        SourceLocation,
    )
    from dart_footing_reconciler.note_internal_harness import NoteInternalHarness
    from dart_footing_reconciler.verification_harness import VerificationContext

    table = ReportTable(
        0,
        [
            ["과목", "당기"],
            ["Ⅰ. 미처분이익잉여금", "100"],
            ["Ⅱ. 이익잉여금처분액", "40"],
            ["Ⅲ. 차기이월미처분이익잉여금 (Ⅰ-Ⅱ)", "70"],
        ],
        "이익잉여금처분계산서",
        SourceLocation("statement:이익잉여금처분계산서", 0, 0),
    )
    section = ReportSection(
        "statement:이익잉여금처분계산서",
        "이익잉여금처분계산서",
        "statement",
        "",
        [ReportBlock("table", "", table, table.location)],
        "separate",
    )
    report = FullReport("sample.html", "Sample Co", [section], [])
    checks = NoteInternalHarness().run(VerificationContext(report=report, prior_report=None, tolerance=1))
    formula = [c for c in checks if c.check_type == "appropriation_formula_check"]
    assert len(formula) == 1
    assert formula[0].status == "unexplained_gap"
    assert formula[0].difference == 10
