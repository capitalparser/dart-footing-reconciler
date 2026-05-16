from dart_footing_reconciler.checks_cfs_note import check_cfs_note_matches
from dart_footing_reconciler.document import FullReport, ReportBlock, ReportSection, ReportTable, SourceLocation


def _section(section_id, title, kind, note_no, table):
    return ReportSection(section_id, title, kind, note_no, [ReportBlock("table", "", table, table.location)])


def test_check_cfs_note_matches_ppe_acquisition_to_investing_cash_flow():
    cfs = _section("statement:cfs", "현금흐름표", "statement", "", ReportTable(0, [["구분", "당기"], ["유형자산의 취득", "(500)"]], "현금흐름표", SourceLocation("statement:cfs", 0, 0)))
    ppe = _section("note:11", "유형자산", "note", "11", ReportTable(1, [["구분", "합계"], ["취득", "500"]], "11. 유형자산", SourceLocation("note:11", 0, 1)))
    report = FullReport("sample.html", "Sample Co", [cfs], [ppe])
    results = check_cfs_note_matches(report, tolerance=0)
    assert results[0].check_type == "cfs_note_match"
    assert results[0].scope == "investing"
    assert results[0].status == "matched"


def test_check_cfs_note_matches_operating_and_financing():
    cfs = _section(
        "statement:cfs",
        "현금흐름표",
        "statement",
        "",
        ReportTable(0, [["구분", "당기"], ["감가상각비", "300"], ["차입금의 상환", "(700)"]], "현금흐름표", SourceLocation("statement:cfs", 0, 0)),
    )
    notes = [
        _section("note:11", "유형자산", "note", "11", ReportTable(1, [["구분", "합계"], ["감가상각비", "300"]], "11. 유형자산", SourceLocation("note:11", 0, 1))),
        _section("note:20", "차입금", "note", "20", ReportTable(2, [["구분", "합계"], ["상환", "700"]], "20. 차입금", SourceLocation("note:20", 0, 2))),
    ]

    results = check_cfs_note_matches(FullReport("sample.html", "Sample Co", [cfs], notes), tolerance=0)

    assert {result.scope for result in results if result.status == "matched"} == {"operating", "financing"}
