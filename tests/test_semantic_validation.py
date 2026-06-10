from dart_footing_reconciler.checks import CheckEvidence, CheckResult
from dart_footing_reconciler.document import (
    FullReport,
    ReportBlock,
    ReportSection,
    ReportTable,
    SourceLocation,
)
from dart_footing_reconciler.semantic_validation import build_semantic_validation_report


def _section(section_id: str, title: str, kind: str, note_no: str, table: ReportTable) -> ReportSection:
    return ReportSection(section_id, title, kind, note_no, [ReportBlock("table", "", table, table.location)])


def _table(section_id: str, index: int) -> ReportTable:
    return ReportTable(index, [["구분", "당기"], ["합계", "100"]], section_id, SourceLocation(section_id, 0, index))


def _check(check_id: str, source: str) -> CheckResult:
    return CheckResult(
        check_id=check_id,
        check_type="total_check",
        status="matched",
        scope="report",
        note_no="",
        title=check_id,
        expected=100,
        actual=100,
        difference=0,
        tolerance=0,
        reason="matched",
        evidence=[CheckEvidence("합계", 100, source)],
    )


def test_semantic_validation_places_checks_in_company_report_order():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section("note:20", "먼저 나온 주석", "note", "20", _table("note:20", 0)),
            _section("note:3", "나중에 나온 주석", "note", "3", _table("note:3", 1)),
        ],
    )
    checks = [
        _check("second", "note:3/table:1/row:1/col:1"),
        _check("first", "note:20/table:0/row:1/col:1"),
    ]

    validation = build_semantic_validation_report(report, checks)

    assert [placement.check.check_id for placement in validation.placements] == ["first", "second"]
    assert validation.placements[0].table.source == "note:20/table:0"
    assert validation.placements[1].table.source == "note:3/table:1"


def test_semantic_validation_keeps_unplaced_checks_last():
    report = FullReport("sample.html", "Sample Co", [], [])
    validation = build_semantic_validation_report(report, [_check("orphan", "generated:no-source")])

    assert validation.placements[0].check.check_id == "orphan"
    assert validation.placements[0].table is None
    assert validation.placements[0].order is None


def test_semantic_validation_emits_note_internal_candidates():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [_section("note:9", "합계 주석", "note", "9", _table("note:9", 0))],
    )

    validation = build_semantic_validation_report(report, [])

    internal_candidates = [
        candidate
        for candidate in validation.candidates
        if candidate.layer == "note_internal"
    ]
    assert [candidate.attempt_id for candidate in internal_candidates] == ["internal_table_total"]
    assert internal_candidates[0].table_source == "note:9/table:0"
    assert internal_candidates[0].evidence_sources == ("note:9/table:0/row:1/col:1",)
