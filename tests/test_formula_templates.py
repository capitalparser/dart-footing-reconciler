"""Tests for formula_templates module and its integration with checks_reconciliation."""

from dart_footing_reconciler.formula_templates import (
    extract_note_label_amount_pairs,
    is_subtotal_row_label,
    match_formula_template,
)
from dart_footing_reconciler.document import (
    FullReport,
    ReportBlock,
    ReportSection,
    ReportTable,
    SourceLocation,
)
from dart_footing_reconciler.checks_reconciliation import check_reconciliation_targets


# ---------------------------------------------------------------------------
# is_subtotal_row_label
# ---------------------------------------------------------------------------


def test_is_subtotal_row_label_matches_exact():
    assert is_subtotal_row_label("합계") is True
    assert is_subtotal_row_label("소계") is True
    assert is_subtotal_row_label("소합계") is True
    assert is_subtotal_row_label("자산총계") is True
    assert is_subtotal_row_label("부채총계") is True


def test_is_subtotal_row_label_normalises_whitespace():
    assert is_subtotal_row_label("소 계") is True
    assert is_subtotal_row_label(" 합 계 ") is True


def test_is_subtotal_row_label_rejects_partial_match():
    # "취득합계" should NOT be treated as a subtotal row
    assert is_subtotal_row_label("취득합계") is False
    assert is_subtotal_row_label("장부금액합계") is False
    assert is_subtotal_row_label("취득") is False


# ---------------------------------------------------------------------------
# extract_note_label_amount_pairs
# ---------------------------------------------------------------------------


def test_extract_note_label_amount_pairs_basic():
    rows = [
        ["구분", "당기"],
        ["취득", "1,000"],
        ["처분", "(200)"],
        ["합계", "800"],
    ]
    pairs = extract_note_label_amount_pairs(rows)
    assert ("취득", 1000) in pairs
    assert ("처분", -200) in pairs
    assert ("합계", 800) in pairs


def test_extract_note_label_amount_pairs_applies_unit_multiplier():
    rows = [["취득", "500"], ["처분", "(100)"]]
    pairs = extract_note_label_amount_pairs(rows, unit_multiplier=1000)
    assert ("취득", 500_000) in pairs
    assert ("처분", -100_000) in pairs


def test_extract_note_label_amount_pairs_skips_empty_label_rows():
    rows = [["", "1,000"], ["취득", "500"]]
    pairs = extract_note_label_amount_pairs(rows)
    assert len(pairs) == 1
    assert pairs[0][0] == "취득"


def test_extract_note_label_amount_pairs_picks_last_numeric_cell():
    # Multi-column: label | prev period | curr period
    rows = [["취득", "300", "500"]]
    pairs = extract_note_label_amount_pairs(rows)
    # Should pick the LAST parseable column (500 = current period)
    assert ("취득", 500) in pairs


# ---------------------------------------------------------------------------
# match_formula_template – ppe_acquisition
# ---------------------------------------------------------------------------


def test_match_formula_template_ppe_acquisition_exact():
    """취득 1,000 → CFS 1,000 with no adjustments."""
    note_rows = [("취득", 1_000)]
    result = match_formula_template(1_000, note_rows, "ppe_acquisition", tolerance=0)
    assert result.matched is True
    assert result.formula_applied == "ppe_acquisition"
    assert result.formula_total == 1_000
    assert result.residual == 0
    assert "취득" in result.matched_labels


def test_match_formula_template_ppe_acquisition_with_payable_increase():
    """취득 1,000 - 미지급금증가 200 = CFS 800."""
    note_rows = [
        ("취득", 1_000),
        ("미지급금증가", 200),
    ]
    result = match_formula_template(800, note_rows, "ppe_acquisition", tolerance=0)
    assert result.matched is True
    assert result.formula_total == 800
    assert result.residual == 0


def test_match_formula_template_ppe_acquisition_with_payable_decrease():
    """취득 1,000 + 미지급금감소 200 = CFS 1,200."""
    note_rows = [
        ("취득", 1_000),
        ("미지급금감소", 200),
    ]
    result = match_formula_template(1_200, note_rows, "ppe_acquisition", tolerance=0)
    assert result.matched is True
    assert result.formula_total == 1_200


def test_match_formula_template_ppe_acquisition_ignores_subtotals():
    """소계 rows are excluded from the primary sum."""
    note_rows = [
        ("취득", 800),
        ("취득 기타", 200),
        ("소계", 1_000),  # should be excluded
    ]
    result = match_formula_template(1_000, note_rows, "ppe_acquisition", tolerance=0)
    assert result.matched is True
    # If subtotal were included, primary_total = 800+200+1000 = 2000 (wrong)
    assert result.formula_total == 1_000


def test_match_formula_template_ppe_acquisition_no_match():
    """No match when note has no 취득 row."""
    note_rows = [("처분", 500), ("감가상각", 100)]
    result = match_formula_template(1_000, note_rows, "ppe_acquisition", tolerance=0)
    assert result.matched is False
    assert result.formula_applied == ""
    assert result.tried_template == "ppe_acquisition"


def test_match_formula_template_within_default_tolerance():
    """Match within default 1,000원 tolerance."""
    note_rows = [("취득", 1_000_500)]  # 500원 rounding gap
    result = match_formula_template(1_000_000, note_rows, "ppe_acquisition")
    assert result.matched is True
    assert result.residual == 500


def test_match_formula_template_unknown_template_returns_no_match():
    result = match_formula_template(1_000, [("취득", 1_000)], "nonexistent_key")
    assert result.matched is False
    assert result.tried_template == "nonexistent_key"


# ---------------------------------------------------------------------------
# match_formula_template – borrowing_net
# ---------------------------------------------------------------------------


def test_match_formula_template_borrowing_net_proceeds_minus_repayment():
    """차입 100 - 상환 40 = CFS net 60."""
    note_rows = [("차입", 100), ("상환", 40)]
    result = match_formula_template(60, note_rows, "borrowing_net", tolerance=0)
    assert result.matched is True
    assert result.formula_total == 60


def test_match_formula_template_borrowing_net_multiple_rows():
    note_rows = [
        ("단기차입", 100),
        ("장기차입", 50),
        ("단기차입 상환", 80),
    ]
    result = match_formula_template(70, note_rows, "borrowing_net", tolerance=0)
    assert result.matched is True
    assert result.formula_total == 70


# ---------------------------------------------------------------------------
# Integration: check_reconciliation_targets formula-template upgrade
# ---------------------------------------------------------------------------


def _section(section_id, title, kind, note_no, rows):
    table = ReportTable(0, rows, title, SourceLocation(section_id, 0, 0))
    return ReportSection(
        section_id, title, kind, note_no,
        [ReportBlock("table", "", table, table.location)],
    )


def _section_with_unit(section_id, title, kind, note_no, rows, unit_multiplier):
    table = ReportTable(
        0, rows, title, SourceLocation(section_id, 0, 0),
        unit_multiplier=unit_multiplier,
    )
    return ReportSection(
        section_id, title, kind, note_no,
        [ReportBlock("table", "", table, table.location)],
    )


def test_formula_template_upgrade_ppe_acquisition_with_transfer_label():
    """Acquisition note uses '취득/자본적지출' label — classified normally,
    but a 대체 adjustment in the same table closes a residual gap.

    This verifies the formula template fallback is invoked when the
    primary result is not MATCHED and finds the 대체 row that
    _classify_note_movement already captures as rollforward_transfer_acquisition
    but might not be applied with the right sign in all scenarios.
    """
    # CFS: 취득 800
    # Note: 취득 1,000, 대체 200 → formula: 1000 - 200 = 800
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산의 취득", "(800)"]],
            )
        ],
        [
            _section(
                "note:11",
                "유형자산",
                "note",
                "11",
                [
                    ["구분", "합계"],
                    ["취득", "1,000"],
                    ["대체", "200"],
                ],
            )
        ],
    )
    results = check_reconciliation_targets(report, tolerance=0)
    acq = [r for r in results if r.title == "property_plant_equipment.acquisitions_cashflow"]
    assert len(acq) == 1
    assert acq[0].status == "matched"
    assert acq[0].expected == 800


def test_formula_template_does_not_downgrade_already_matched_result():
    """When primary reconciliation already MATCHED, template fallback is a no-op."""
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["유형자산의 취득", "(1,000)"]],
            )
        ],
        [
            _section(
                "note:11",
                "유형자산",
                "note",
                "11",
                [["구분", "합계"], ["취득", "1,000"]],
            )
        ],
    )
    results = check_reconciliation_targets(report, tolerance=0)
    acq = [r for r in results if r.title == "property_plant_equipment.acquisitions_cashflow"]
    assert acq[0].status == "matched"
    # Reason should be the standard bridge reason, not the template reason
    assert "공식 템플릿" not in acq[0].reason
