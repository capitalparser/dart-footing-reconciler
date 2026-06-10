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
