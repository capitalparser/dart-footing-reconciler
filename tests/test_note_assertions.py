from dart_footing_reconciler.document import FullReport, ReportBlock, ReportSection, ReportTable, SourceLocation
from dart_footing_reconciler.note_assertions import check_note_assertions


def _note(note_no: str, title: str, table: ReportTable) -> ReportSection:
    return ReportSection(
        f"note:{note_no}",
        title,
        "note",
        note_no,
        [ReportBlock("table", "", table, table.location)],
    )


def test_check_note_assertions_foots_asset_rollforward_table():
    table = ReportTable(
        0,
        [
            ["구분", "토지", "건물", "합계"],
            ["기초장부금액", "100", "200", "300"],
            ["취득", "10", "20", "30"],
            ["처분", "", "(5)", "(5)"],
            ["감가상각비", "", "(15)", "(15)"],
            ["기말장부금액", "110", "200", "310"],
        ],
        "유형자산의 변동내역 당기",
        SourceLocation("note:11", 0, 0),
    )
    report = FullReport("sample.html", "Sample Co", [], [_note("11", "유형자산", table)])

    results = check_note_assertions(report, tolerance=0)

    assert [(result.check_type, result.status, result.title) for result in results] == [
        ("note_rollforward_check", "matched", "유형자산 증감표 검산 - 토지"),
        ("note_rollforward_check", "matched", "유형자산 증감표 검산 - 건물"),
        ("note_rollforward_check", "matched", "유형자산 증감표 검산 - 합계"),
    ]
    total_result = results[-1]
    assert total_result.expected == 310
    assert total_result.actual == 310
    assert any(evidence.label == "기초장부금액 합계" for evidence in total_result.evidence)
    assert any(evidence.label == "기말장부금액 합계" for evidence in total_result.evidence)


def test_check_note_assertions_treats_positive_depreciation_as_decrease():
    table = ReportTable(
        0,
        [
            ["구분", "건물", "합계"],
            ["기초장부금액", "200", "200"],
            ["취득", "20", "20"],
            ["감가상각비", "15", "15"],
            ["기말장부금액", "205", "205"],
        ],
        "유형자산의 변동내역 당기",
        SourceLocation("note:11", 0, 0),
    )
    report = FullReport("sample.html", "Sample Co", [], [_note("11", "유형자산", table)])

    result = check_note_assertions(report, tolerance=0)[0]

    assert result.status == "matched"
    assert result.expected == 205
    assert result.actual == 205


def test_check_note_assertions_reports_each_column_gap_independently():
    table = ReportTable(
        0,
        [
            ["구분", "토지", "건물", "합계"],
            ["기초장부금액", "100", "200", "300"],
            ["취득", "10", "20", "30"],
            ["기말장부금액", "110", "201", "311"],
        ],
        "유형자산의 변동내역 당기",
        SourceLocation("note:11", 0, 0),
    )
    report = FullReport("sample.html", "Sample Co", [], [_note("11", "유형자산", table)])

    results = check_note_assertions(report, tolerance=0)

    assert [(result.title, result.status, result.difference) for result in results] == [
        ("유형자산 증감표 검산 - 토지", "matched", 0),
        ("유형자산 증감표 검산 - 건물", "unexplained_gap", -19),
        ("유형자산 증감표 검산 - 합계", "unexplained_gap", -19),
    ]
