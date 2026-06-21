from __future__ import annotations

import ast
import inspect
from copy import deepcopy
from pathlib import Path

import pytest

from dart_footing_reconciler import amount_locator
from dart_footing_reconciler.amount_locator import (
    Abstain,
    LocatedAmount,
    NotApplicable,
    TargetAmountRole,
    locate,
)
from dart_footing_reconciler.checks import NOT_TESTED, PARSE_UNCERTAIN
from dart_footing_reconciler.document import ReportTable, SourceLocation, parse_full_report
from dart_footing_reconciler.layout_variants import LayoutClassification, classify_layout
from dart_footing_reconciler.note_inventory import (
    NoteTableInventoryItem,
    build_note_inventory,
)
from dart_footing_reconciler.orientation import TableOrientation


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
        rows=deepcopy(rows),
        heading="",
        location=SourceLocation("note:12", 0, int(source.rsplit(":", 1)[1])),
        unit_multiplier=unit_multiplier,
    )


def _layout(key: str, confidence: float = 0.8) -> LayoutClassification:
    return LayoutClassification(key=key, confidence=confidence, evidence=(), source="test")


def _orientation(key: str = "column_oriented") -> TableOrientation:
    return TableOrientation(key=key, confidence=0.9, evidence=())


def _fixture(company: str, filename: str, source: str):
    report = parse_full_report(FIXTURE_DIR / filename, company=company)
    items = {item.source: item for item in build_note_inventory(report).tables}
    tables = {
        f"note:{section.note_no}/table:{block.table.index}": block.table
        for section in report.notes
        for block in section.blocks
        if block.table is not None
    }
    return deepcopy(items[source]), deepcopy(tables[source])


def _status_for_locator_result(result: object) -> str:
    if isinstance(result, NotApplicable):
        return NOT_TESTED
    return PARSE_UNCERTAIN


def test_unknown_layout_low_confidence_abstains_instead_of_locating_unseen_asset_table():
    rows = [
        ["", "장부금액"],
        ["유형자산 합계", "60"],
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
        TargetAmountRole.NET_CARRYING_AMOUNT,
        layout=_layout("unknown_layout", confidence=0.0),
        orientation=_orientation(),
    )

    assert isinstance(result, Abstain)
    assert result.reason_code == "LOW_CONFIDENCE_MATCH"


def test_asset_net_layout_registry_is_deterministic_tuple():
    assert isinstance(amount_locator._ASSET_NET_LAYOUT_KEYS, tuple)
    assert "unknown_layout" not in amount_locator._ASSET_NET_LAYOUT_KEYS


def test_table_helper_copies_rows_to_prevent_cross_test_mutation():
    rows = [["", "장부금액"], ["유형자산 합계", "60"]]
    table = _table(rows, source="note:9/table:0")

    rows[1][1] = "999"

    assert table.rows[1][1] == "60"


@pytest.mark.parametrize("layout_key", amount_locator._ASSET_NET_LAYOUT_KEYS)
def test_each_asset_net_layout_key_has_positive_net_cell_pin(layout_key: str):
    if layout_key == "asset_investment_property_simple_net":
        rows = [
            ["", "투자부동산", "투자부동산", "투자부동산 합계"],
            ["", "토지", "건물", "투자부동산 합계"],
            ["", "장부금액 합계", "장부금액 합계", "투자부동산 합계"],
            ["투자부동산", "40", "20", "60"],
        ]
        account_key = "investment_property"
        expected_col = 3
        item = _item(
            source="note:11/table:0",
            note_no="11",
            title="투자부동산",
            heading="11. 투자부동산 당기 (단위 : 천원)",
            rows=rows,
        )
        table = _table(rows, source="note:11/table:0")
    else:
        rows = [
            ["", "총장부금액", "감가상각누계액", "장부금액 합계"],
            ["유형자산 합계", "100", "(40)", "60"],
        ]
        account_key = "property_plant_equipment"
        expected_col = 3
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
        account_key,
        TargetAmountRole.NET_CARRYING_AMOUNT,
        layout=_layout(layout_key),
        orientation=_orientation(),
    )

    assert isinstance(result, LocatedAmount)
    assert result.col_index == expected_col
    assert result.raw_amount == 60
    assert result.evidence[2:] == (layout_key, "asset_net_carrying_cell")


@pytest.mark.parametrize("layout_key", amount_locator._ASSET_NET_LAYOUT_KEYS)
def test_each_asset_net_layout_key_abstains_on_gross_only_family_total(layout_key: str):
    if layout_key == "asset_investment_property_simple_net":
        rows = [
            ["", "투자부동산 합계"],
            ["", "총장부금액"],
            ["투자부동산", "100"],
        ]
        account_key = "investment_property"
        item = _item(
            source="note:11/table:0",
            note_no="11",
            title="투자부동산",
            heading="11. 투자부동산 당기 (단위 : 천원)",
            rows=rows,
        )
        table = _table(rows, source="note:11/table:0")
    else:
        rows = [
            ["", "유형자산 합계"],
            ["", "총장부금액"],
            ["유형자산 합계", "100"],
        ]
        account_key = "property_plant_equipment"
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
        account_key,
        TargetAmountRole.NET_CARRYING_AMOUNT,
        layout=_layout(layout_key),
        orientation=_orientation(),
    )

    assert isinstance(result, Abstain)
    assert result.reason_code == "COLUMN_NOT_DETECTED"


def test_period_end_without_current_ending_column_abstains_instead_of_net_fallback():
    rows = [
        ["", "기초", "증감", "장부금액"],
        ["유형자산 합계", "100", "20", "120"],
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
        TargetAmountRole.PERIOD_END_BALANCE,
        layout=_layout("asset_carrying_amount_total"),
        orientation=_orientation(),
    )

    assert isinstance(result, Abstain)
    assert result.reason_code == "COLUMN_NOT_DETECTED"


def test_net_carrying_prefers_explicit_net_column_over_gross_family_total():
    rows = [
        ["", "유형자산 합계", "유형자산"],
        ["", "총장부금액", "장부금액"],
        ["유형자산 합계", "100", "60"],
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
        TargetAmountRole.NET_CARRYING_AMOUNT,
        layout=_layout("asset_carrying_amount_total"),
        orientation=_orientation(),
    )

    assert isinstance(result, LocatedAmount)
    assert result.col_index == 2
    assert result.raw_amount == 60


def test_category_matrix_skips_subtotal_column_and_matches_family_anchor():
    rows = [
        ["", "산업재산권", "회원권", "소계", "개발비", "무형자산 및 영업권 합계"],
        ["기말 무형자산 및 영업권", "10", "20", "30", "40", "70"],
    ]
    item = _item(rows=rows)
    table = _table(rows)

    result = locate(
        item,
        table,
        "intangible_assets",
        TargetAmountRole.NET_CARRYING_AMOUNT,
        layout=_layout("asset_component_column_summary"),
        orientation=_orientation(),
    )

    assert isinstance(result, LocatedAmount)
    assert result.raw_amount == 70
    assert result.component_sources == (
        "note:12/table:0/row:1/col:1",
        "note:12/table:0/row:1/col:2",
        "note:12/table:0/row:1/col:4",
    )


def test_category_matrix_abstains_when_component_sum_misses_family_anchor():
    rows = [
        ["", "산업재산권", "회원권", "부분합", "개발비", "무형자산 및 영업권 합계"],
        ["기말 무형자산 및 영업권", "10", "20", "30", "40", "75"],
    ]
    item = _item(rows=rows)
    table = _table(rows)

    result = locate(
        item,
        table,
        "intangible_assets",
        TargetAmountRole.NET_CARRYING_AMOUNT,
        layout=_layout("asset_component_column_summary"),
        orientation=_orientation(),
    )

    assert isinstance(result, Abstain)
    assert result.reason_code == "COLUMN_NOT_DETECTED"


def test_category_matrix_excludes_contra_columns_from_components():
    rows = [
        ["", "취득원가", "상각누계액", "개발비", "회원권", "무형자산 및 영업권 합계"],
        ["기말 무형자산 및 영업권", "100", "(30)", "40", "20", "60"],
    ]
    item = _item(rows=rows)
    table = _table(rows)

    result = locate(
        item,
        table,
        "intangible_assets",
        TargetAmountRole.NET_CARRYING_AMOUNT,
        layout=_layout("asset_component_column_summary"),
        orientation=_orientation(),
    )

    assert isinstance(result, LocatedAmount)
    assert result.raw_amount == 60
    assert result.component_sources == (
        "note:12/table:0/row:1/col:3",
        "note:12/table:0/row:1/col:4",
    )


def test_inline_scope_marker_selects_matching_glued_net_column():
    rows = [
        ["", "연결 장부금액", "별도 장부금액"],
        ["유형자산 합계", "100", "60"],
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
        TargetAmountRole.NET_CARRYING_AMOUNT,
        layout=_layout("asset_carrying_amount_total"),
        orientation=_orientation(),
        scope="separate",
    )

    assert isinstance(result, LocatedAmount)
    assert result.col_index == 2
    assert result.raw_amount == 60


def test_scope_marker_ambiguity_abstains_when_scope_not_unique():
    rows = [
        ["", "연결 별도 장부금액", "장부금액"],
        ["유형자산 합계", "100", "60"],
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
        TargetAmountRole.NET_CARRYING_AMOUNT,
        layout=_layout("asset_carrying_amount_total"),
        orientation=_orientation(),
        scope="consolidated",
    )

    assert isinstance(result, Abstain)
    assert result.reason_code == "COLUMN_NOT_DETECTED"


def test_current_tables_with_prior_comparison_text_are_not_prior_period_exclusions():
    rows = [
        ["", "장부금액"],
        ["유형자산 합계", "60"],
    ]
    item = _item(
        source="note:9/table:0",
        note_no="9",
        title="유형자산",
        heading="9. 유형자산 당기 변동 (전기 대비) (단위 : 천원)",
        rows=rows,
    )
    table = _table(rows, source="note:9/table:0")

    result = locate(
        item,
        table,
        "property_plant_equipment",
        TargetAmountRole.NET_CARRYING_AMOUNT,
        layout=_layout("asset_carrying_amount_total"),
        orientation=_orientation(),
    )

    assert isinstance(result, LocatedAmount)


def test_standalone_prior_period_table_remains_not_applicable():
    rows = [
        ["", "장부금액"],
        ["유형자산 합계", "60"],
    ]
    item = _item(
        source="note:9/table:0",
        note_no="9",
        title="유형자산",
        heading="9. 유형자산 전기 (단위 : 천원)",
        rows=rows,
    )
    table = _table(rows, source="note:9/table:0")

    result = locate(
        item,
        table,
        "property_plant_equipment",
        TargetAmountRole.NET_CARRYING_AMOUNT,
        layout=_layout("asset_carrying_amount_total"),
        orientation=_orientation(),
    )

    assert isinstance(result, NotApplicable)


def test_multiple_net_columns_abstain_with_ambiguous_reason():
    rows = [
        ["", "장부금액", "순장부금액"],
        ["유형자산 합계", "60", "60"],
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
        TargetAmountRole.NET_CARRYING_AMOUNT,
        layout=_layout("asset_carrying_amount_total"),
        orientation=_orientation(),
    )

    assert isinstance(result, Abstain)
    assert result.reason_code == "AMBIGUOUS_MULTIPLE"


def test_parse_failure_on_identified_cell_uses_amount_parse_failed_reason():
    rows = [
        ["", "장부금액"],
        ["유형자산 합계", "금액없음"],
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
        TargetAmountRole.NET_CARRYING_AMOUNT,
        layout=_layout("asset_carrying_amount_total"),
        orientation=_orientation(),
    )

    assert isinstance(result, Abstain)
    assert result.reason_code == "AMOUNT_PARSE_FAILED"


@pytest.mark.parametrize(
    "role",
    [TargetAmountRole.CURRENT_PORTION, TargetAmountRole.NONCURRENT_PORTION],
)
def test_current_noncurrent_roles_abstain_as_unimplemented_in_phase_1(role: TargetAmountRole):
    rows = [
        ["", "금액"],
        ["유동리스부채", "10"],
        ["비유동리스부채", "90"],
        ["리스부채 합계", "100"],
    ]
    item = _item(
        source="note:10/table:0",
        note_no="10",
        title="리스",
        heading="10. 리스부채의 유동 및 비유동 구분 당기 (단위 : 천원)",
        rows=rows,
    )
    table = _table(rows, source="note:10/table:0")

    result = locate(
        item,
        table,
        "lease_liabilities",
        role,
        layout=_layout("lease_liability_current_noncurrent_summary", confidence=0.85),
        orientation=_orientation("row_oriented"),
    )

    assert isinstance(result, Abstain)
    assert result.reason_code == "COLUMN_NOT_DETECTED"


def test_unsupported_unknown_orientation_abstains_before_asset_strategy():
    rows = [
        ["", "장부금액"],
        ["유형자산 합계", "60"],
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
        TargetAmountRole.NET_CARRYING_AMOUNT,
        layout=_layout("asset_carrying_amount_total"),
        orientation=_orientation("unknown"),
    )

    assert isinstance(result, Abstain)
    assert result.reason_code == "COLUMN_NOT_DETECTED"


def test_mixed_unit_markers_in_later_cells_abstain_with_parse_failed():
    rows = [
        ["", "장부금액", "(단위: 원)"],
        ["유형자산 합계", "60", "(단위: 백만원)"],
    ]
    item = _item(
        source="note:9/table:0",
        note_no="9",
        title="유형자산",
        heading="9. 유형자산 당기",
        rows=rows,
    )
    table = _table(rows, source="note:9/table:0")

    result = locate(
        item,
        table,
        "property_plant_equipment",
        TargetAmountRole.NET_CARRYING_AMOUNT,
        layout=_layout("asset_carrying_amount_total"),
        orientation=_orientation(),
    )

    assert isinstance(result, Abstain)
    assert result.reason_code == "AMOUNT_PARSE_FAILED"


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
        "layout_key",
        "strategy_id",
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
            "asset_carrying_amount_total",
            "asset_net_carrying_cell",
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
            "asset_carrying_amount_total",
            "category_matrix_row_sum",
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
            "asset_carrying_amount_total",
            "asset_net_carrying_cell",
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
            "asset_carrying_amount_total",
            "asset_net_carrying_cell",
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
            "asset_investment_property_simple_net",
            "asset_net_carrying_cell",
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
            "asset_investment_property_simple_net",
            "asset_net_carrying_cell",
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
            "lease_liability_current_noncurrent_summary",
            "lease_period_end_total",
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
            "lease_liability_current_noncurrent_summary",
            "lease_period_end_total",
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
    layout_key: str,
    strategy_id: str,
    row_index: int,
    col_index: int,
    raw_amount: int,
):
    item, table = _fixture(company, filename, source)
    layout = classify_layout(item)

    result = locate(
        item,
        table,
        account_key,
        role,
        layout=layout,
        scope="consolidated" if "(연결)" in item.title else "separate",
    )

    assert layout.key == layout_key
    assert isinstance(result, LocatedAmount)
    assert (result.row_index, result.col_index) == (row_index, col_index)
    assert result.raw_amount == raw_amount
    assert result.unit_multiplier == 1000
    assert result.amount == raw_amount * 1000
    assert result.source == f"{source}/row:{row_index}/col:{col_index}"
    assert result.evidence[2:] == (layout_key, strategy_id)


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
