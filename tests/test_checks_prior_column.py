from dart_footing_reconciler.checks_prior_column import check_prior_column_matches
from dart_footing_reconciler.document import (
    FullReport,
    ReportBlock,
    ReportSection,
    ReportTable,
    SourceLocation,
)


def _section(section_id, title, kind, note_no, table):
    return ReportSection(
        section_id,
        title,
        kind,
        note_no,
        [ReportBlock("table", "", table, table.location)],
    )


def test_prior_column_fs_note_matches_prior_period():
    bs = _section(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "당기", "전기"], ["유형자산(순액)", "1,000", "800"]],
            "재무상태표",
            SourceLocation("statement:bs", 0, 0),
        ),
    )
    note = _section(
        "note:11",
        "유형자산",
        "note",
        "11",
        ReportTable(
            1,
            [["구분", "당기", "전기"], ["기말 장부금액", "1,000", "800"]],
            "11. 유형자산",
            SourceLocation("note:11", 0, 1),
        ),
    )

    results = check_prior_column_matches(FullReport("s.html", "Co", [bs], [note]), tolerance=0)

    pc1 = [result for result in results if result.check_type == "prior_column_fs_note"]
    assert pc1
    assert pc1[0].status == "matched"
    assert pc1[0].expected == 800
    assert pc1[0].actual == 800
    assert any(source.startswith("statement:bs/") and "col:2" in source for source in [e.source for e in pc1[0].evidence])
    assert any(source.startswith("note:11/") and "col:2" in source for source in [e.source for e in pc1[0].evidence])


def test_prior_column_rollforward_beginning_ties_to_prior_bs():
    bs = _section(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "당기", "전기"], ["유형자산(순액)", "1,000", "800"]],
            "재무상태표",
            SourceLocation("statement:bs", 0, 0),
        ),
    )
    roll = _section(
        "note:11",
        "유형자산",
        "note",
        "11",
        ReportTable(
            1,
            [
                ["구분", "당기"],
                ["기초 장부금액", "800"],
                ["취득", "300"],
                ["감가상각", "-100"],
                ["기말 장부금액", "1,000"],
            ],
            "11. 유형자산 증감",
            SourceLocation("note:11", 0, 1),
        ),
    )

    results = check_prior_column_matches(FullReport("s.html", "Co", [bs], [roll]), tolerance=0)

    pc2 = [result for result in results if result.check_type == "prior_column_rollforward"]
    assert pc2
    assert pc2[0].status == "matched"
    assert pc2[0].expected == 800
    assert pc2[0].actual == 800


def test_prior_column_rollforward_does_not_tie_liability_to_right_of_use_asset():
    bs = _section(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "당기", "전기"], ["리스부채", "1,200", "1,000"]],
            "재무상태표",
            SourceLocation("statement:bs", 0, 0),
        ),
    )
    lease_note = _section(
        "note:34",
        "리스",
        "note",
        "34",
        ReportTable(
            1,
            [["구분", "당기"], ["기초 사용권자산", "1,000"], ["기말 사용권자산", "1,200"]],
            "34. 리스 사용권자산",
            SourceLocation("note:34", 0, 1),
        ),
    )

    results = check_prior_column_matches(
        FullReport("s.html", "Co", [bs], [lease_note]), tolerance=0
    )

    assert not [result for result in results if result.check_type == "prior_column_rollforward"]


def test_prior_column_rollforward_allows_large_balance_rounding_under_one_thousand():
    bs = _section(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "당기", "전기"], ["유형자산(순액)", "17,000", "11,893,348,076,900"]],
            "재무상태표",
            SourceLocation("statement:bs", 0, 0),
        ),
    )
    roll = _section(
        "note:13",
        "유형자산",
        "note",
        "13",
        ReportTable(
            1,
            [["구분", "합계"], ["기초 장부금액", "11,893,348,077"]],
            "13. 유형자산 변동내역 (단위 : 천원)",
            SourceLocation("note:13", 0, 1),
            unit_multiplier=1000,
        ),
    )

    results = check_prior_column_matches(FullReport("s.html", "Co", [bs], [roll]), tolerance=1)

    pc2 = [result for result in results if result.check_type == "prior_column_rollforward"]
    assert pc2
    assert pc2[0].status == "matched"
    assert pc2[0].difference == 100
