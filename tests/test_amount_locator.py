from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from dart_footing_reconciler import amount_locator
from dart_footing_reconciler.amount_locator import (
    LocatedAmount,
    NotApplicable,
    TargetAmountRole,
    locate,
)
from dart_footing_reconciler.checks import NOT_TESTED, PARSE_UNCERTAIN
from dart_footing_reconciler.document import ReportTable, SourceLocation, parse_full_report
from dart_footing_reconciler.layout_variants import classify_layout
from dart_footing_reconciler.note_inventory import (
    NoteTableInventoryItem,
    build_note_inventory,
)


FIXTURE_DIR = Path("out/corpus/run_2026-06-08-statement-ties-baseline/raw")


def _item(
    *,
    source: str = "note:12/table:0",
    note_no: str = "12",
    title: str = "무형자산",
    heading: str = "12. 무형자산 당기 (단위 : 천원)",
    rows: list[list[str]],
    unit_multiplier: int = 1000,
) -> NoteTableInventoryItem:
    headers = tuple(rows[0]) if rows else ()
    row_labels = tuple(row[0] for row in rows[1:] if row)
    return NoteTableInventoryItem(
        company="테스트",
        section_id=f"note:{note_no}",
        note_no=note_no,
        title=title,
        table_index=int(source.rsplit(":", 1)[1]),
        source=source,
        heading=heading,
        unit_multiplier=unit_multiplier,
        row_count=len(rows),
        column_count=max((len(row) for row in rows), default=0),
        headers=headers,
        row_labels=row_labels,
    )


def _table(
    rows: list[list[str]],
    *,
    source: str = "note:12/table:0",
    unit_multiplier: int = 1000,
) -> ReportTable:
    return ReportTable(
        index=int(source.rsplit(":", 1)[1]),
        rows=rows,
        heading="",
        location=SourceLocation("note:12", 0, int(source.rsplit(":", 1)[1])),
        unit_multiplier=unit_multiplier,
    )


def _fixture(company: str, filename: str, source: str):
    report = parse_full_report(FIXTURE_DIR / filename, company=company)
    items = {item.source: item for item in build_note_inventory(report).tables}
    tables = {
        f"note:{section.note_no}/table:{block.table.index}": block.table
        for section in report.notes
        for block in section.blocks
        if block.table is not None
    }
    return items[source], tables[source]


def _status_for_locator_result(result: object) -> str:
    if isinstance(result, NotApplicable):
        return NOT_TESTED
    return PARSE_UNCERTAIN


def test_category_matrix_row_sum_preserves_component_sources():
    rows = [
        ["", "산업재산권", "회원권", "개발비", "무형자산 및 영업권 합계"],
        ["기초의 무형자산 및 영업권", "1", "2", "3", "6"],
        ["기말 무형자산 및 영업권", "10", "20", "30", "60"],
    ]
    item = _item(rows=rows)
    table = _table(rows)

    result = locate(
        item,
        table,
        "intangible_assets",
        TargetAmountRole.NET_CARRYING_AMOUNT,
        layout=classify_layout(item),
        scope="consolidated",
    )

    assert isinstance(result, LocatedAmount)
    assert result.row_index == 2
    assert result.col_index == 4
    assert result.raw_amount == 60
    assert result.unit_multiplier == 1000
    assert result.amount == 60_000
    assert result.source == "note:12/table:0/row:2/col:4"
    assert result.component_sources == (
        "note:12/table:0/row:2/col:1",
        "note:12/table:0/row:2/col:2",
        "note:12/table:0/row:2/col:3",
    )


def test_role_inapplicable_maps_to_not_tested_not_parse_uncertain():
    rows = [
        ["", "총장부금액", "감가상각누계액", "장부금액 합계"],
        ["유형자산 합계", "100", "(40)", "60"],
    ]
    item = _item(
        source="note:9/table:0",
        note_no="9",
        title="유형자산",
        heading="9. 유형자산 당기 (단위 : 천원)",
        rows=rows,
    )
    table = _table(rows, source="note:9/table:0")

    result = locate(
        item,
        table,
        "property_plant_equipment",
        TargetAmountRole.CASH_LIKE_MOVEMENT,
        layout=classify_layout(item),
    )

    assert isinstance(result, NotApplicable)
    assert _status_for_locator_result(result) == NOT_TESTED
    assert _status_for_locator_result(result) != PARSE_UNCERTAIN


@pytest.mark.parametrize(
    (
        "company",
        "filename",
        "source",
        "account_key",
        "role",
        "row_index",
        "col_index",
        "raw_amount",
    ),
    [
        (
            "CJ대한통운",
            "cj대한통운_2024_20250317000953.html",
            "note:18/table:371",
            "intangible_assets",
            TargetAmountRole.NET_CARRYING_AMOUNT,
            7,
            4,
            394_197_655,
        ),
        (
            "CJ대한통운",
            "cj대한통운_2024_20250317000953.html",
            "note:18/table:373",
            "intangible_assets",
            TargetAmountRole.NET_CARRYING_AMOUNT,
            7,
            7,
            394_197_655,
        ),
        (
            "더존비즈온",
            "더존비즈온_2024_20250317001028.html",
            "note:9/table:45",
            "property_plant_equipment",
            TargetAmountRole.NET_CARRYING_AMOUNT,
            10,
            4,
            361_132_861,
        ),
        (
            "더존비즈온",
            "더존비즈온_2024_20250317001028.html",
            "note:9/table:240",
            "property_plant_equipment",
            TargetAmountRole.NET_CARRYING_AMOUNT,
            10,
            4,
            349_190_629,
        ),
        (
            "더존비즈온",
            "더존비즈온_2024_20250317001028.html",
            "note:11/table:58",
            "investment_property",
            TargetAmountRole.NET_CARRYING_AMOUNT,
            4,
            7,
            222_521_190,
        ),
        (
            "더존비즈온",
            "더존비즈온_2024_20250317001028.html",
            "note:11/table:253",
            "investment_property",
            TargetAmountRole.NET_CARRYING_AMOUNT,
            4,
            7,
            231_147_730,
        ),
        (
            "더존비즈온",
            "더존비즈온_2024_20250317001028.html",
            "note:10/table:51",
            "lease_liabilities",
            TargetAmountRole.PERIOD_END_BALANCE,
            3,
            1,
            13_389_242,
        ),
        (
            "더존비즈온",
            "더존비즈온_2024_20250317001028.html",
            "note:10/table:246",
            "lease_liabilities",
            TargetAmountRole.PERIOD_END_BALANCE,
            3,
            1,
            9_139_922,
        ),
    ],
)
def test_real_fixture_regression_pins_known_correct_net_cells(
    company: str,
    filename: str,
    source: str,
    account_key: str,
    role: TargetAmountRole,
    row_index: int,
    col_index: int,
    raw_amount: int,
):
    item, table = _fixture(company, filename, source)

    result = locate(
        item,
        table,
        account_key,
        role,
        layout=classify_layout(item),
        scope="consolidated" if "(연결)" in item.title else "separate",
    )

    assert isinstance(result, LocatedAmount)
    assert (result.row_index, result.col_index) == (row_index, col_index)
    assert result.raw_amount == raw_amount
    assert result.unit_multiplier == 1000
    assert result.amount == raw_amount * 1000
    assert result.source == f"{source}/row:{row_index}/col:{col_index}"


def test_target_amount_role_is_closed_and_orthogonal_to_existing_role_enums():
    assert {role.value for role in TargetAmountRole} == {
        "period_end_balance",
        "net_carrying_amount",
        "cash_like_movement",
        "disclosed_total",
        "expense_allocation",
        "current_portion",
        "noncurrent_portion",
    }

    tree = ast.parse(inspect.getsource(amount_locator))
    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert "AccountRole" not in imported_names
    assert "_role_for_label" not in imported_names
