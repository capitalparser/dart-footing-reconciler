from dart_footing_reconciler.checks import CheckEvidence, CheckResult
from dart_footing_reconciler.coverage import build_coverage_report
from dart_footing_reconciler.layout_variants import LayoutClassification
from dart_footing_reconciler.note_inventory import NoteInventory, NoteTableInventoryItem


def _table(note_no, table_index, title):
    return NoteTableInventoryItem(
        company="Sample Co",
        section_id=f"note:{note_no}",
        note_no=str(note_no),
        title=title,
        table_index=table_index,
        source=f"note:{note_no}/table:{table_index}",
        heading=title,
        unit_multiplier=1,
        row_count=2,
        column_count=2,
        headers=("구분", "합계"),
        row_labels=("기말",),
    )


def test_coverage_counts_known_unknown_and_validated_tables():
    inventory = NoteInventory(
        company="Sample Co",
        note_count=2,
        tables=(_table(11, 0, "유형자산"), _table(31, 1, "기타")),
    )
    layouts = {
        "note:11/table:0": LayoutClassification(
            "asset_carrying_amount_total", 0.8, ("evidence",), "note:11/table:0"
        ),
        "note:31/table:1": LayoutClassification(
            "unknown_layout", 0.0, (), "note:31/table:1"
        ),
    }
    checks = [
        CheckResult(
            check_id="reconciliation:property_plant_equipment.balance",
            check_type="primary_balance_reconciliation",
            status="matched",
            scope="primary",
            note_no="11",
            title="유형자산 balance",
            expected=100,
            actual=100,
            difference=0,
            tolerance=0,
            reason="matched",
            evidence=[CheckEvidence("note", 100, "note:11/table:0/row:1/col:1")],
        )
    ]

    report = build_coverage_report(inventory, layouts, checks)

    assert report.company == "Sample Co"
    assert report.total_notes == 2
    assert report.total_tables == 2
    assert report.known_layout_tables == 1
    assert report.unknown_layout_tables == 1
    assert report.validated_tables == 1
    assert report.unvalidated_tables == 1
