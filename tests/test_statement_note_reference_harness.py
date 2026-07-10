from collections import Counter

from dart_footing_reconciler.check_pipeline import default_report_harnesses
from dart_footing_reconciler.checks import MATCHED, UNEXPLAINED_GAP
from dart_footing_reconciler.document import (
    FullReport,
    ReportBlock,
    ReportSection,
    ReportTable,
    SourceLocation,
)
from dart_footing_reconciler.statement_note_reference_harness import (
    StatementNoteReferenceHarness,
    check_statement_note_references,
)
from dart_footing_reconciler.verification_harness import (
    LAYER_STATEMENT_NOTE,
    VerificationContext,
)


def _section(
    section_id: str,
    title: str,
    kind: str,
    note_no: str,
    table: ReportTable,
    *,
    scope: str = "consolidated",
) -> ReportSection:
    return ReportSection(
        section_id,
        title,
        kind,
        note_no,
        [ReportBlock("table", "", table, table.location)],
        scope=scope,
    )


def _bs(label: str = "유형자산 (주12)", amount: str = "100") -> ReportSection:
    table = ReportTable(
        0,
        [["구분", "당기"], [label, amount]],
        "재무상태표",
        SourceLocation("statement:bs", 0, 0),
    )
    return _section("statement:bs", "재무상태표", "statement", "", table)


def _note(note_no: str, title: str, row_label: str, amount: str = "100") -> ReportSection:
    table_index = int(note_no.split("-", 1)[0])
    table = ReportTable(
        table_index,
        [["구분", "당기"], [row_label, amount]],
        f"{note_no}. {title}",
        SourceLocation(f"note:{note_no}", 0, table_index),
    )
    return _section(f"note:{note_no}", title, "note", note_no, table)


def test_reference_accuracy_matches_when_displayed_note_contains_account_evidence():
    report = FullReport(
        "s.html",
        "Co",
        [_bs()],
        [_note("12", "유형자산", "기말 유형자산")],
    )

    checks = check_statement_note_references(
        report,
        tolerance=1,
        consolidation_basis="consolidated",
    )

    accuracy = [
        check for check in checks
        if check.check_type == "statement_note_reference_accuracy"
    ]
    assert len(accuracy) == 1
    assert accuracy[0].status == MATCHED
    assert accuracy[0].note_no == "12"
    assert accuracy[0].account_key == "property_plant_equipment"
    assert accuracy[0].consolidation_basis == "consolidated"
    assert accuracy[0].evidence[0].role == "statement_anchor"
    assert accuracy[0].evidence[0].source.startswith("statement:")
    assert accuracy[0].evidence[1].role == "displayed_note_reference"
    assert accuracy[0].evidence[2].role == "note_account_evidence"


def test_reference_accuracy_reads_displayed_note_from_separate_note_column():
    statement = _section(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "주석", "당기"], ["유형자산", "12", "100"]],
            "재무상태표",
            SourceLocation("statement:bs", 0, 0),
        ),
    )
    report = FullReport(
        "s.html",
        "Co",
        [statement],
        [_note("12", "유형자산", "기말 유형자산")],
    )

    checks = check_statement_note_references(report, tolerance=1)

    accuracy = [
        check for check in checks
        if check.check_type == "statement_note_reference_accuracy"
    ]
    assert len(accuracy) == 1
    assert accuracy[0].status == MATCHED
    assert accuracy[0].evidence[1].source == "statement:bs/table:0/row:1/col:1"


def test_reference_accuracy_reads_juseok_keyword_variant_in_statement_label():
    report = FullReport(
        "s.html",
        "Co",
        [_bs("유형자산 (주석 12)", "100")],
        [_note("12", "유형자산", "기말 유형자산")],
    )

    checks = check_statement_note_references(report, tolerance=1)

    accuracy = [
        check for check in checks
        if check.check_type == "statement_note_reference_accuracy"
    ]
    assert len(accuracy) == 1
    assert accuracy[0].status == MATCHED


def test_reference_accuracy_gaps_when_displayed_note_has_no_account_evidence():
    report = FullReport(
        "s.html",
        "Co",
        [_bs()],
        [_note("12", "차입금", "기말 차입금")],
    )

    checks = check_statement_note_references(report, tolerance=1)

    accuracy = [
        check for check in checks
        if check.check_type == "statement_note_reference_accuracy"
    ]
    assert len(accuracy) == 1
    assert accuracy[0].status == UNEXPLAINED_GAP
    assert accuracy[0].parse_uncertain_reason is None
    assert "주석 12" in accuracy[0].reason
    assert accuracy[0].evidence[0].source.startswith("statement:")


def test_reference_accuracy_accepts_subnote_number_for_displayed_primary_ref():
    report = FullReport(
        "s.html",
        "Co",
        [_bs()],
        [_note("12-1", "유형자산", "기말 유형자산")],
    )

    checks = check_statement_note_references(report, tolerance=1)

    accuracy = [
        check for check in checks
        if check.check_type == "statement_note_reference_accuracy"
    ]
    assert len(accuracy) == 1
    assert accuracy[0].status == MATCHED
    assert accuracy[0].note_no == "12"
    assert accuracy[0].evidence[-1].source.startswith("note:12-1/")


def test_reference_accuracy_accepts_financial_instruments_topic_note_for_borrowings():
    report = FullReport(
        "s.html",
        "Co",
        [_bs("단기차입금 (주5,17)", "100")],
        [
            _note("5", "금융상품", "금융상품 공정가치", "0"),
            _note("17", "사채 및 차입금", "단기차입금", "100"),
        ],
    )

    checks = check_statement_note_references(report, tolerance=1)

    accuracy = [
        check for check in checks
        if check.check_type == "statement_note_reference_accuracy"
    ]
    by_note = {check.note_no: check for check in accuracy}
    assert by_note["5"].status == MATCHED
    assert "관련 공시 주석" in by_note["5"].reason
    assert by_note["5"].evidence[-1].role == "note_account_evidence"
    assert by_note["17"].status == MATCHED


def test_reference_accuracy_accepts_financial_asset_topic_note_for_deposits():
    report = FullReport(
        "s.html",
        "Co",
        [_bs("단기금융상품 (주5,10)", "100")],
        [
            _note("5", "금융상품", "금융상품 공정가치", "0"),
            _note("10", "장ㆍ단기금융자산", "사용이 제한된 금융상품", "100"),
        ],
    )

    checks = check_statement_note_references(report, tolerance=1)

    by_note = {
        check.note_no: check for check in checks
        if check.check_type == "statement_note_reference_accuracy"
    }
    assert by_note["10"].status == MATCHED
    assert "관련 공시 주석" in by_note["10"].reason


def test_reference_accuracy_accepts_tax_note_for_deferred_tax_liability():
    report = FullReport(
        "s.html",
        "Co",
        [_bs("이연법인세부채 (주30)", "100")],
        [_note("30", "법인세비용", "일시적차이", "100")],
    )

    checks = check_statement_note_references(report, tolerance=1)

    accuracy = [
        check for check in checks
        if check.check_type == "statement_note_reference_accuracy"
    ]
    assert accuracy[0].status == MATCHED
    assert "관련 공시 주석" in accuracy[0].reason


def test_reference_accuracy_accepts_trade_receivable_note_for_contract_assets():
    report = FullReport(
        "s.html",
        "Co",
        [_bs("계약자산 (주6,27)", "100")],
        [
            _note("6", "매출채권및기타채권", "계약자산 성격의 금액", "100"),
            _note("27", "영업부문", "고객과의 계약에서 생기는 수익", "100"),
        ],
    )

    checks = check_statement_note_references(report, tolerance=1)

    by_note = {
        check.note_no: check for check in checks
        if check.check_type == "statement_note_reference_accuracy"
    }
    assert by_note["6"].status == MATCHED
    assert by_note["27"].status == MATCHED


def test_reference_completeness_does_not_guess_additional_revenue_notes():
    report = FullReport(
        "s.html",
        "Co",
        [
            _section(
                "statement:is",
                "포괄손익계산서",
                "statement",
                "",
                ReportTable(
                    0,
                    [["구분", "당기"], ["매출액 (주24,27)", "100"]],
                    "포괄손익계산서",
                    SourceLocation("statement:is", 0, 0),
                ),
            )
        ],
        [
            _section(
                "note:15",
                "건설형 공사계약",
                "note",
                "15",
                ReportTable(
                    15,
                    [["구분", "당기"], ["누적공사수익 합계", "100"]],
                    "15. 건설형 공사계약 고객과의 계약에서 생기는 수익의 구분에 대한 공시",
                    SourceLocation("note:15", 0, 15),
                ),
            ),
            _note("24", "특수관계자 거래", "특수관계자 매출", "100"),
            _note("27", "영업부문", "고객과의 계약에서 생기는 수익", "100"),
        ],
    )

    checks = check_statement_note_references(report, tolerance=1)

    completeness = [
        check for check in checks
        if check.check_type == "statement_note_reference_completeness"
    ]
    assert completeness == []


def test_reference_completeness_does_not_guess_additional_trade_receivable_notes():
    report = FullReport(
        "s.html",
        "Co",
        [_bs("장기매출채권및기타채권 (주5,6,24)", "100")],
        [
            _note("5", "금융상품", "금융상품 공정가치", "0"),
            _note("6", "매출채권및기타채권", "장기매출채권", "100"),
            _note("24", "특수관계자 거래", "특수관계자 채권", "100"),
            _section(
                "note:27",
                "영업부문",
                "note",
                "27",
                ReportTable(
                    27,
                    [["구분", "당기"], ["매출채권", "100"]],
                    "27. 영업부문 고객과의 계약에서 생기는 매출채권, 계약자산 및 계약부채 공시",
                    SourceLocation("note:27", 0, 27),
                ),
            ),
        ],
    )

    checks = check_statement_note_references(report, tolerance=1)

    completeness = [
        check for check in checks
        if check.check_type == "statement_note_reference_completeness"
    ]
    assert completeness == []


def test_reference_completeness_flags_related_note_missing_from_body_refs():
    report = FullReport(
        "s.html",
        "Co",
        [_bs()],
        [
            _note("12", "유형자산", "기말 유형자산"),
            _note("14", "유형자산 및 사용권자산", "기말 유형자산", "20"),
        ],
    )

    checks = check_statement_note_references(report, tolerance=1)

    completeness = [
        check for check in checks
        if check.check_type == "statement_note_reference_completeness"
    ]
    assert len(completeness) == 1
    assert completeness[0].status == UNEXPLAINED_GAP
    assert completeness[0].note_no == "14"
    assert completeness[0].evidence[0].role == "statement_anchor"
    assert completeness[0].evidence[0].source.startswith("statement:")
    assert completeness[0].evidence[-1].source.startswith("note:14/")


def test_reference_completeness_ignores_generic_amount_rows_in_unrelated_notes():
    report = FullReport(
        "s.html",
        "Co",
        [_bs()],
        [
            _note("12", "유형자산", "기말 유형자산"),
            _note("6", "매출채권및기타채권", "기말금융자산", "20"),
            _note("9", "기타자산", "유동성장기수선충당예치금", "30"),
        ],
    )

    checks = check_statement_note_references(report, tolerance=1)

    completeness = [
        check for check in checks
        if check.check_type == "statement_note_reference_completeness"
    ]
    assert completeness == []


def test_reference_completeness_flags_account_row_without_displayed_note_number():
    report = FullReport(
        "s.html",
        "Co",
        [_bs("유형자산", "100")],
        [_note("12", "유형자산", "기말 유형자산")],
    )

    checks = check_statement_note_references(report, tolerance=1)

    assert [check.check_type for check in checks] == [
        "statement_note_reference_completeness"
    ]
    assert checks[0].status == UNEXPLAINED_GAP
    assert checks[0].note_no == "12"
    assert "본문 행에 주석번호가 없습니다" in checks[0].reason


def test_reference_harness_runs_existence_and_account_reference_checks():
    statement = ReportSection(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        [
            ReportBlock(
                "table",
                "",
                ReportTable(
                    0,
                    [["구분", "당기"], ["유형자산 (주12)", "100"]],
                    "재무상태표",
                    SourceLocation("statement:bs", 0, 0),
                ),
                SourceLocation("statement:bs", 0, 0),
            ),
            ReportBlock(
                "text",
                "유형자산 담보 제공 내역은 주석 12 참조.",
                None,
                SourceLocation("statement:bs", 1),
            ),
        ],
        scope="consolidated",
    )
    report = FullReport(
        "s.html",
        "Co",
        [statement],
        [_note("12", "유형자산", "기말 유형자산")],
    )

    checks = StatementNoteReferenceHarness().run(
        VerificationContext(report, None, tolerance=1, consolidation_basis="consolidated")
    )

    types = Counter(check.check_type for check in checks)
    assert types["note_reference_check"] == 2
    assert types["statement_note_reference_accuracy"] == 1
    assert all(check.evidence[0].source.startswith("statement:") for check in checks)


def test_reference_harness_is_in_default_pipeline():
    harnesses = default_report_harnesses()

    layer_by_id = {harness.harness_id: harness.layer for harness in harnesses}
    assert layer_by_id["statement_note_reference"] == LAYER_STATEMENT_NOTE
