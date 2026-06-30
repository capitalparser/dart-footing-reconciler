from dart_footing_reconciler.document import (
    FullReport,
    ReportBlock,
    ReportSection,
    ReportTable,
    SourceLocation,
)
from dart_footing_reconciler.note_semantics import build_note_semantic_extraction


def _table(
    index: int,
    rows: list[list[str]],
    heading: str,
    *,
    note_no: str = "17",
    unit_multiplier: int = 1000,
) -> ReportTable:
    return ReportTable(
        index,
        rows,
        heading,
        SourceLocation(f"note:{note_no}", 0, index),
        unit_multiplier=unit_multiplier,
    )


def _note(note_no: str, title: str, tables: list[ReportTable]) -> ReportSection:
    return ReportSection(
        f"note:{note_no}",
        title,
        "note",
        note_no,
        [ReportBlock("table", "", table, table.location) for table in tables],
        scope="consolidated",
    )


def _report(notes: list[ReportSection]) -> FullReport:
    return FullReport("sample.html", "Sample Co", [], notes)


def test_note_semantics_resolves_second_row_maturity_headers():
    report = _report(
        [
            _note(
                "17",
                "리스",
                [
                    _table(
                        2,
                        [
                            ["", "", "", "", ""],
                            ["", "1년 이내", "1년 초과 5년 이내", "5년 초과", "합계"],
                            ["리스부채", "100", "200", "50", "350"],
                        ],
                        "17. 리스",
                    )
                ],
            )
        ]
    )

    extraction = build_note_semantic_extraction(report)
    table = extraction.table_by_source("note:17/table:2")

    assert table is not None
    assert table.source_location == SourceLocation("note:17", 0, 2)
    assert table.consolidation_basis == "consolidated"
    assert table.disclosure_families == ("lease_liability_schedule",)
    assert table.detected_relation_types == ("maturity_bucket_sum",)
    assert table.layout_key == "lease_liability_maturity_summary"
    assert table.orientation_key == "column_oriented"
    assert table.uncertainty_flags == ()
    assert table.fingerprint.normalized_section_topic == "리스"
    assert table.fingerprint.normalized_header_tokens == (
        "1년이내",
        "1년초과5년이내",
        "5년초과",
        "합계",
    )
    assert table.fingerprint.row_count_bucket == "3-5"
    assert table.fingerprint.unit_pattern == "x1000"
    assert table.fingerprint.detected_relation_types == ("maturity_bucket_sum",)


def test_note_semantics_resolves_nested_liquidity_risk_maturity_header_rows():
    report = _report(
        [
            _note(
                "4",
                "재무위험관리",
                [
                    _table(
                        37,
                        [
                            ["", "", "위험", "위험", "위험", "위험", "위험"],
                            ["", "", "유동성위험", "유동성위험", "유동성위험", "유동성위험", "유동성위험"],
                            ["", "", "합계 구간", "합계 구간", "합계 구간", "합계 구간", "합계 구간 합계"],
                            ["", "", "6개월 이하", "6개월 초과 12개월 이하", "1년 초과 5년 이하", "5년 초과", "합계 구간 합계"],
                            ["차입금", "차입금", "1", "2", "3", "0", "6"],
                            ["매입채무", "매입채무", "4", "0", "0", "0", "4"],
                            ["리스부채", "리스부채", "5", "6", "20", "1", "32"],
                        ],
                        "4. 재무위험관리 유동성위험 당기",
                        note_no="4",
                    )
                ],
            )
        ]
    )

    extraction = build_note_semantic_extraction(report)
    table = extraction.table_by_source("note:4/table:37")

    assert table is not None
    assert table.layout_key == "liquidity_maturity_analysis"
    assert table.orientation_key == "column_oriented"
    assert table.uncertainty_flags == ()
    assert table.fingerprint.normalized_header_tokens == (
        "6개월이하",
        "6개월초과12개월이하",
        "1년초과5년이하",
        "5년초과",
        "합계구간합계",
    )
    assert table.fingerprint.normalized_stub_labels[:3] == ("차입금", "매입채무", "리스부채")
    assert table.detected_relation_types == ("maturity_bucket_sum",)
    assert table.disclosure_families == ("lease_liability_schedule", "maturity_analysis")


def test_note_semantics_uses_second_stub_column_for_grouped_liability_rows():
    report = _report(
        [
            _note(
                "23",
                "금융상품",
                [
                    _table(
                        142,
                        [
                            ["", "", "위험", "위험", "위험", "위험"],
                            ["", "", "유동성위험", "유동성위험", "유동성위험", "유동성위험"],
                            ["", "", "합계 구간", "합계 구간", "합계 구간", "합계 구간 합계"],
                            ["", "", "1년 미만", "1년~5년", "5년 초과", "합계 구간 합계"],
                            [
                                "비파생금융부채, 계약상 현금흐름",
                                "비파생금융부채, 계약상 현금흐름",
                                "100",
                                "200",
                                "30",
                                "330",
                            ],
                            [
                                "비파생금융부채, 계약상 현금흐름",
                                "차입금",
                                "40",
                                "200",
                                "30",
                                "270",
                            ],
                            [
                                "비파생금융부채, 계약상 현금흐름",
                                "총 리스부채",
                                "20",
                                "50",
                                "40",
                                "110",
                            ],
                        ],
                        "23. 금융상품 비파생금융부채의 만기분석에 대한 공시",
                        note_no="23",
                    )
                ],
            )
        ]
    )

    extraction = build_note_semantic_extraction(report)
    table = extraction.table_by_source("note:23/table:142")

    assert table is not None
    assert table.layout_key == "liquidity_maturity_analysis"
    assert table.orientation_key == "column_oriented"
    assert table.uncertainty_flags == ()
    assert table.fingerprint.normalized_stub_labels == (
        "비파생금융부채,계약상현금흐름",
        "차입금",
        "총리스부채",
    )
    assert table.disclosure_families == ("lease_liability_schedule", "maturity_analysis")


def test_note_semantics_resolves_annual_year_lease_maturity_columns():
    report = _report(
        [
            _note(
                "12",
                "차입금",
                [
                    _table(
                        90,
                        [
                            ["", "2025년", "2026년", "2027년", "2028년", "2029년 이후", "합계 구간 합계"],
                            ["장기차입금, 미할인현금흐름", "1", "2", "3", "4", "5", "15"],
                            ["총 리스부채", "10", "20", "30", "40", "50", "150"],
                        ],
                        "12. 차입금 차입금의 만기분석에 대한 공시",
                        note_no="12",
                        unit_multiplier=1_000_000,
                    )
                ],
            )
        ]
    )

    extraction = build_note_semantic_extraction(report)
    table = extraction.table_by_source("note:12/table:90")

    assert table is not None
    assert table.layout_key == "liquidity_maturity_analysis"
    assert table.orientation_key == "column_oriented"
    assert table.uncertainty_flags == ()
    assert table.fingerprint.normalized_header_tokens == (
        "2025년",
        "2026년",
        "2027년",
        "2028년",
        "2029년이후",
        "합계구간합계",
    )
    assert table.fingerprint.normalized_stub_labels == ("장기차입금,미할인현금흐름", "총리스부채")
    assert table.disclosure_families == ("lease_liability_schedule", "maturity_analysis")


def test_note_semantics_fingerprints_layout_patterns_not_company_names():
    report = _report(
        [
            _note(
                "31",
                "재무위험관리",
                [
                    _table(
                        3,
                        [
                            ["구분", "3개월 이내", "1년 이내", "1년 초과", "합계"],
                            ["차입금 및 사채", "10", "20", "30", "60"],
                            ["리스부채", "40", "50", "60", "150"],
                            ["합계", "50", "70", "90", "210"],
                        ],
                        "31. 유동성위험 만기분석",
                        note_no="31",
                    )
                ],
            )
        ]
    )

    extraction = build_note_semantic_extraction(report)
    table = extraction.table_by_source("note:31/table:3")

    assert table is not None
    assert table.company == "Sample Co"
    assert table.fingerprint.normalized_section_topic == "재무위험관리"
    assert table.fingerprint.company == ""
    assert table.fingerprint.column_axis_schema == "column_oriented"
    assert table.detected_relation_types == ("maturity_bucket_sum",)
    assert "maturity_analysis" in table.disclosure_families


def test_note_semantics_does_not_treat_lease_receivable_schedule_as_lease_liability():
    report = _report(
        [
            _note(
                "8",
                "매출채권 및 계약자산",
                [
                    _table(
                        60,
                        [
                            ["", "1년 이내", "1년 초과 5년 이내", "5년 초과", "합계 구간 합계"],
                            ["매출채권(리스채권)", "10", "20", "30", "60"],
                        ],
                        "8. 금융리스채권의 만기분석 공시",
                        note_no="8",
                    )
                ],
            )
        ]
    )

    extraction = build_note_semantic_extraction(report)
    table = extraction.table_by_source("note:8/table:60")

    assert table is not None
    assert "lease_liability_schedule" not in table.disclosure_families
    assert table.disclosure_families == ("maturity_analysis",)
