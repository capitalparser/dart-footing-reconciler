from dart_footing_reconciler.checks_prior_year import check_prior_year_reconciliation
from dart_footing_reconciler.document import FullReport, ReportBlock, ReportSection, ReportTable, SourceLocation


def _note(note_no, title, rows):
    table = ReportTable(0, rows, f"{note_no}. {title}", SourceLocation(f"note:{note_no}", 0, 0))
    return ReportSection(f"note:{note_no}", title, "note", note_no, [ReportBlock("table", "", table, table.location)])


def test_prior_year_reconciles_current_comparative_to_prior_current_amount():
    current_note = _note("11", "유형자산", [["구분", "당기", "전기"], ["기말", "1,200", "1,000"]])
    prior_note = _note("10", "유형자산", [["구분", "당기"], ["기말", "1,000"]])
    current = FullReport("current.html", "Sample Co", [], [current_note])
    prior = FullReport("prior.html", "Sample Co", [], [prior_note])
    results = check_prior_year_reconciliation(current, prior, tolerance=0)
    amount_results = [result for result in results if result.check_type == "prior_year_amount_match"]
    assert amount_results[0].status == "matched"


def test_prior_year_detects_note_number_and_row_structure_changes():
    current_note = _note(
        "11",
        "유형자산",
        [["구분", "당기", "전기"], ["토지", "600", "500"], ["건물", "600", "500"], ["기계장치", "0", "0"]],
    )
    prior_note = _note("10", "유형자산", [["구분", "당기"], ["토지", "500"], ["건물", "500"]])
    current = FullReport("current.html", "Sample Co", [], [current_note])
    prior = FullReport("prior.html", "Sample Co", [], [prior_note])
    results = check_prior_year_reconciliation(current, prior, tolerance=0)
    structure = [result for result in results if result.check_type == "prior_year_structure_change"]
    assert structure
    assert "note number changed from 10 to 11" in structure[0].reason
    assert any("기계장치" in result.reason for result in structure)


def test_prior_year_detects_removed_row_and_amount_mismatch():
    current_note = _note("11", "유형자산", [["구분", "당기", "전기"], ["토지", "600", "501"]])
    prior_note = _note("11", "유형자산", [["구분", "당기"], ["토지", "500"], ["건물", "500"]])

    results = check_prior_year_reconciliation(
        FullReport("current.html", "Sample Co", [], [current_note]),
        FullReport("prior.html", "Sample Co", [], [prior_note]),
        tolerance=0,
    )

    assert any(result.status == "unexplained_gap" for result in results)
    assert any("건물" in result.reason for result in results if result.check_type == "prior_year_structure_change")
