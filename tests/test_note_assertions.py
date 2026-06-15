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


def test_rollforward_attaches_movement_components_without_changing_result():
    from dart_footing_reconciler.note_assertions import check_note_assertions
    from dart_footing_reconciler.document import FullReport, ReportBlock, ReportSection, ReportTable, SourceLocation
    t = ReportTable(0, [["구분", "합계"], ["기초장부금액", "300"], ["취득", "30"],
                        ["감가상각비", "(15)"], ["기말장부금액", "315"]],
                    "유형자산의 변동내역 당기", SourceLocation("note:11", 0, 0))
    note = ReportSection("note:11", "유형자산", "note", "11", [ReportBlock("table", "", t, t.location)])
    results = check_note_assertions(FullReport("s", "Co", [], [note]), tolerance=0)
    r = next(x for x in results if x.check_type == "note_rollforward_check")
    roles = {e.role for e in r.evidence}
    assert "beginning" in roles and "ending" in roles and "movement" in roles
    assert r.expected == 315 and r.actual == 315 and r.status == "matched"


def test_rollforward_skips_subcolumns_blank_in_beginning_and_ending():
    """셀트리온 type: 영업권[내부|외부|합계]. 내부/외부 열은 기초·기말이 빈칸이고
    값은 합계 열에 있다. blank_as_zero로 빈 기초/기말 하위 열을 0/0으로 잡아
    movement(사업결합)와 비교하면 거짓 차이가 난다 → 그 열은 제외해야 한다."""
    table = ReportTable(
        0,
        [
            ["구분", "내부창출", "외부취득", "영업권 합계"],
            ["기초", "", "", "1,000"],
            ["사업결합", "", "300", "300"],
            ["기말", "", "", "1,300"],
        ],
        "무형자산의 변동내역 당기",
        SourceLocation("note:13", 0, 0),
    )
    report = FullReport("s.html", "Co", [], [_note("13", "무형자산", table)])

    results = check_note_assertions(report, tolerance=0)

    assert all(r.status != "unexplained_gap" for r in results), [
        (r.title, r.expected, r.actual) for r in results
    ]
    totals = [r for r in results if "합계" in r.title]
    assert totals and totals[0].status == "matched" and totals[0].actual == 1300


# ── Finding 2: workbook evidence text stable (exclude component/movement) ────

def test_workbook_evidence_text_excludes_breakdown_roles():
    from dart_footing_reconciler.audit_workbook import _evidence_text
    from dart_footing_reconciler.checks import CheckResult, CheckEvidence, MATCHED
    r = CheckResult("c", "t", MATCHED, "note", "11", "t", 100, 100, 0, 1, "ok", [
        CheckEvidence("기초 합계", 80, "note:11/t/r1/c1", role="beginning"),
        CheckEvidence("기말 합계", 100, "note:11/t/r5/c1", role="ending"),
        CheckEvidence("취득", 20, "note:11/t/r2/c1", role="movement"),
    ])
    txt = _evidence_text(r, {})
    assert "기초" in txt and "기말" in txt and "취득" not in txt


def test_rollforward_signed_net_change_row_not_force_negated():
    """'증가(감소)' 순변동 행은 부호가 이미 반영돼 있으므로, 라벨에 '감소'가
    있어도 양수 값을 강제로 음수화하면 안 된다 (현대차 무형자산 거짓 gap)."""
    table = ReportTable(
        0,
        [
            ["구분", "합계"],
            ["기초장부금액", "700"],
            ["취득", "0"],
            ["기타변동에 따른 증가(감소)", "26"],
            ["기말장부금액", "726"],
        ],
        "무형자산의 변동내역 당기",
        SourceLocation("note:11", 0, 0),
    )
    report = FullReport("s.html", "Co", [], [_note("11", "무형자산", table)])
    results = check_note_assertions(report, tolerance=0)
    rf = [r for r in results if r.check_type == "note_rollforward_check"]
    assert rf and rf[0].expected == 726 and rf[0].status == "matched", [
        (r.expected, r.status) for r in rf
    ]
