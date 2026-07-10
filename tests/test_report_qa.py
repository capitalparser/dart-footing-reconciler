from dart_footing_reconciler.checks import CheckEvidence, CheckResult, MATCHED, UNEXPLAINED_GAP
from dart_footing_reconciler.document import FullReport, ReportBlock, ReportSection, ReportTable, SourceLocation
from dart_footing_reconciler.report_qa import QA_FAIL, QA_PASS, build_validation_qa_report


def _section(section_id: str, title: str, kind: str, note_no: str, table: ReportTable) -> ReportSection:
    return ReportSection(
        section_id,
        title,
        kind,
        note_no,
        [ReportBlock("table", "", table, table.location)],
    )


def _table(index: int, rows: list[list[str]], title: str = "테스트") -> ReportTable:
    return ReportTable(index, rows, title, SourceLocation("test", 0, index))


def _check(
    check_type: str,
    source: str,
    *,
    status: str = MATCHED,
    note_no: str = "",
    check_id: str | None = None,
) -> CheckResult:
    return CheckResult(
        check_id=check_id or check_type,
        check_type=check_type,
        status=status,
        scope="report",
        note_no=note_no,
        title=check_type,
        expected=100,
        actual=100,
        difference=0,
        tolerance=1,
        reason="테스트",
        evidence=[CheckEvidence("검증 금액", 100, source)],
    )


def test_validation_qa_fails_when_total_family_missing():
    note = _section(
        "note:12",
        "유형자산",
        "note",
        "12",
        _table(
            0,
            [
                ["구분", "건물", "기계장치", "합계"],
                ["기초", "40", "60", "100"],
                ["취득", "10", "20", "30"],
                ["합계", "50", "80", "130"],
            ],
        ),
    )
    report = FullReport("t.html", "회사", [], [note])

    qa = build_validation_qa_report(report, [])

    assert qa.status == QA_FAIL
    assert any(item.category == "total_coverage" and item.expected_family == "합계검증" for item in qa.items)


def test_validation_qa_accepts_appropriation_formula_as_total_coverage():
    note = _section(
        "note:25",
        "이익잉여금처분계산서",
        "note",
        "25",
        _table(
            0,
            [
                ["구분", "당기"],
                ["미처분이익잉여금", "90"],
                ["임의적립금 이입액", "10"],
                ["처분가능이익", "100"],
                ["합계", "100"],
            ],
        ),
    )
    report = FullReport("t.html", "회사", [], [note])
    checks = [_check("appropriation_formula_check", "note:25/table:0/row:3/col:1")]

    qa = build_validation_qa_report(report, checks)

    assert any(
        item.category == "total_coverage"
        and item.expected_family == "합계검증"
        and item.status == QA_PASS
        and "appropriation_formula_check" in item.check_types
        for item in qa.items
    )


def test_validation_qa_accepts_unexplained_gap_when_family_and_evidence_exist():
    cf = _section(
        "statement:cf",
        "현금흐름표",
        "statement",
        "",
        _table(0, [["구분", "당기"], ["유형자산의 취득", "(500)"]]),
    )
    note = _section(
        "note:12",
        "유형자산",
        "note",
        "12",
        _table(1, [["구분", "당기"], ["취득", "400"]]),
    )
    report = FullReport("t.html", "회사", [cf], [note])
    checks = [
        _check(
            "cashflow_reconciliation",
            "statement:cf/table:0/row:1/col:1;note:12/table:1/row:1/col:1",
            status=UNEXPLAINED_GAP,
            note_no="12",
        )
    ]

    qa = build_validation_qa_report(report, checks)

    assert qa.status == QA_PASS
    assert not [item for item in qa.items if item.status == QA_FAIL]


def test_validation_qa_cashflow_coverage_requires_cashflow_reconciliation_family():
    cf = _section(
        "statement:cf",
        "현금흐름표",
        "statement",
        "",
        _table(0, [["구분", "당기"], ["유형자산의 취득", "(500)"]]),
    )
    report = FullReport("t.html", "회사", [cf], [])
    checks = [_check("statement_cash_tie", "statement:cf/table:0/row:1/col:1")]

    qa = build_validation_qa_report(report, checks)

    assert qa.status == QA_FAIL
    assert any(
        item.category == "cashflow_coverage"
        and item.expected_family == "현금흐름표 대사"
        and item.status == QA_FAIL
        for item in qa.items
    )


def test_validation_qa_fails_when_core_check_has_broken_evidence_source():
    cf = _section(
        "statement:cf",
        "현금흐름표",
        "statement",
        "",
        _table(0, [["구분", "당기"], ["유형자산의 취득", "(500)"]]),
    )
    note = _section(
        "note:12",
        "유형자산",
        "note",
        "12",
        _table(1, [["구분", "당기"], ["취득", "400"]]),
    )
    report = FullReport("t.html", "회사", [cf], [note])
    checks = [
        _check(
            "cashflow_reconciliation",
            "statement:cf/table:0/row:1/col:1;note:12/table:99/row:1/col:1",
            status=UNEXPLAINED_GAP,
            note_no="12",
        )
    ]

    qa = build_validation_qa_report(report, checks)

    assert qa.status == QA_FAIL
    assert any(item.category == "evidence_integrity" for item in qa.items)


def test_validation_qa_fails_when_statement_note_family_missing():
    bs = _section(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        _table(0, [["구분", "당기"], ["유형자산 (주석 12)", "100"]]),
    )
    note = _section(
        "note:12",
        "유형자산",
        "note",
        "12",
        _table(1, [["구분", "당기"], ["기말 장부금액", "100"]]),
    )
    report = FullReport("t.html", "회사", [bs], [note])

    qa = build_validation_qa_report(report, [])

    assert qa.status == QA_FAIL
    assert any(
        item.category == "fs_note_coverage" and item.expected_family == "재무제표 본문-주석 대사"
        for item in qa.items
    )


def test_validation_qa_fails_when_note_note_family_missing():
    asset_note = _section(
        "note:12",
        "유형자산",
        "note",
        "12",
        _table(0, [["구분", "당기"], ["감가상각비", "100"]]),
    )
    expense_note = _section(
        "note:20",
        "비용의 성격별 분류",
        "note",
        "20",
        _table(1, [["구분", "당기"], ["감가상각비", "100"]]),
    )
    report = FullReport("t.html", "회사", [], [asset_note, expense_note])

    qa = build_validation_qa_report(report, [])

    assert qa.status == QA_FAIL
    assert any(item.category == "note_note_coverage" and item.expected_family == "주석간 대사" for item in qa.items)


def test_validation_qa_does_not_require_note_note_when_only_broad_terms_exist():
    asset_note = _section(
        "note:12",
        "유형자산",
        "note",
        "12",
        _table(0, [["구분", "당기"], ["취득", "100"]]),
    )
    expense_note = _section(
        "note:20",
        "비용의 성격별 분류",
        "note",
        "20",
        _table(1, [["구분", "당기"], ["취득", "100"]]),
    )
    report = FullReport("t.html", "회사", [], [asset_note, expense_note])

    qa = build_validation_qa_report(report, [])

    assert not [item for item in qa.items if item.category == "note_note_coverage"]


def test_validation_qa_fails_when_statement_body_family_missing():
    bs = _section(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        _table(
            0,
            [
                ["구분", "당기"],
                ["자산총계", "130"],
                ["부채총계", "50"],
                ["자본총계", "80"],
            ],
        ),
    )
    report = FullReport("t.html", "회사", [bs], [])

    qa = build_validation_qa_report(report, [])

    assert qa.status == QA_FAIL
    assert any(
        item.category == "statement_body_coverage" and item.expected_family == "재무제표 본문 검증"
        for item in qa.items
    )


def test_validation_qa_accepts_statement_body_family_when_check_exists():
    bs = _section(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        _table(
            0,
            [
                ["구분", "당기"],
                ["자산총계", "130"],
                ["부채총계", "50"],
                ["자본총계", "80"],
            ],
        ),
    )
    report = FullReport("t.html", "회사", [bs], [])
    checks = [
        _check("statement_bs_equation", "statement:bs/table:0/row:1"),
        _check("statement_subtotal", "statement:bs/table:0/row:1"),
    ]

    qa = build_validation_qa_report(report, checks)

    assert any(
        item.category == "statement_body_coverage" and item.status == QA_PASS
        for item in qa.items
    )


def test_validation_qa_fails_when_prior_period_family_missing():
    bs = _section(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        _table(0, [["구분", "당기", "전기"], ["유형자산", "100", "90"]]),
    )
    report = FullReport("t.html", "회사", [bs], [])

    qa = build_validation_qa_report(report, [])

    assert qa.status == QA_FAIL
    assert any(
        item.category == "prior_period_coverage" and item.expected_family == "전기 숫자 검증"
        for item in qa.items
    )


def test_validation_qa_accepts_prior_period_family_and_role_sources():
    bs = _section(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        _table(0, [["구분", "당기", "전기"], ["유형자산", "100", "90"]]),
    )
    note = _section(
        "note:12",
        "자산 변동",
        "note",
        "12",
        _table(
            1,
            [
                ["구분", "당기", "전기"],
                ["기초", "90", "80"],
                ["기말", "100", "90"],
            ],
        ),
    )
    report = FullReport("t.html", "회사", [bs], [note])
    checks = [
        _check(
            "prior_column_fs_note",
            "statement:bs/table:0/row:1/col:2;note:12/table:1/row:2/col:2",
        ),
        _check(
            "prior_year_beginning_balance_match",
            "note:12/table:1/ending;note:12/table:1/beginning",
        ),
    ]

    qa = build_validation_qa_report(report, checks)

    assert not [item for item in qa.items if item.category == "evidence_integrity" and item.status == QA_FAIL]
    assert any(
        item.category == "prior_period_coverage" and item.status == QA_PASS
        for item in qa.items
    )


def test_validation_qa_reports_frontend_contract_and_completion_readiness_pass():
    bs = _section(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        _table(
            0,
            [
                ["구분", "당기"],
                ["자산총계", "130"],
                ["부채총계", "50"],
                ["자본총계", "80"],
            ],
        ),
    )
    report = FullReport("t.html", "회사", [bs], [])
    checks = [
        _check("statement_bs_equation", "statement:bs/table:0/row:1"),
        _check("statement_subtotal", "statement:bs/table:0/row:1"),
    ]

    qa = build_validation_qa_report(report, checks)

    assert qa.status == QA_PASS
    assert any(
        item.category == "frontend_contract"
        and item.expected_family == "백엔드-프론트 표시 계약"
        and item.status == QA_PASS
        for item in qa.items
    )
    assert any(
        item.category == "completion_readiness"
        and item.expected_family == "작업 완료 기준"
        and item.status == QA_PASS
        for item in qa.items
    )


def test_validation_qa_completion_readiness_fails_when_required_logic_is_missing():
    note = _section(
        "note:12",
        "유형자산",
        "note",
        "12",
        _table(
            0,
            [
                ["구분", "건물", "기계장치", "합계"],
                ["기초", "40", "60", "100"],
                ["합계", "40", "60", "100"],
            ],
        ),
    )
    report = FullReport("t.html", "회사", [], [note])

    qa = build_validation_qa_report(report, [])

    assert qa.status == QA_FAIL
    assert any(
        item.category == "completion_readiness"
        and item.expected_family == "작업 완료 기준"
        and item.status == QA_FAIL
        and "미완료" in item.reason
        for item in qa.items
    )


def test_validation_qa_accepts_prior_report_evidence_sources():
    current_note = _section(
        "note:11",
        "유형자산",
        "note",
        "11",
        _table(0, [["구분", "당기"], ["기초", "100"]]),
    )
    prior_note = _section(
        "note:10",
        "유형자산",
        "note",
        "10",
        _table(5, [["구분", "당기"], ["기말", "100"]]),
    )
    report = FullReport("current.html", "회사", [], [current_note])
    prior_report = FullReport("prior.html", "회사", [], [prior_note])
    checks = [
        _check(
            "prior_year_beginning_balance_match",
            "prior:note:10/table:5/ending;note:11/table:0/beginning",
            check_id="prior_beginning:11:0",
        )
    ]

    qa = build_validation_qa_report(report, checks, prior_report=prior_report)

    assert not [item for item in qa.items if item.category == "evidence_integrity" and item.status == QA_FAIL]
    assert any(item.category == "prior_period_coverage" and item.status == QA_PASS for item in qa.items)
