"""Extract normalized reconciliation inputs from parsed DART reports."""

from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import combinations

from dart_footing_reconciler import amount_locator
from dart_footing_reconciler.amount_locator import TargetAmountRole
from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.document import FullReport, ReportSection
from dart_footing_reconciler.layout_variants import LayoutClassification, classify_layout
from dart_footing_reconciler.note_inventory import NoteTableInventoryItem, build_note_inventory
from dart_footing_reconciler.orientation import TableOrientation, detect_orientation
from dart_footing_reconciler.scope import primary_note_sections
from dart_footing_reconciler.table_semantics import (
    amount_from_current_period,
    balance_amount,
    current_period_columns,
    row_amount_prefer_current,
)
from dart_footing_reconciler.taxonomy import classify_report


@dataclass(frozen=True)
class StatementLineInput:
    account_key: str
    label: str
    amount: int
    source: str


@dataclass(frozen=True)
class CfsLineInput:
    account_key: str
    movement_role: str
    label: str
    amount: int
    source: str


@dataclass(frozen=True)
class NoteBalanceInput:
    account_key: str
    balance_role: str
    note_no: str
    label: str
    amount: int
    source: str
    unit_multiplier: int = 1
    layout_key: str = ""
    layout_confidence: float = 0.0
    layout_evidence: tuple[str, ...] = ()
    orientation_key: str = ""
    orientation_confidence: float = 0.0
    orientation_evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class NoteMovementInput:
    account_key: str
    movement_role: str
    note_no: str
    label: str
    amount: int
    source: str
    unit_multiplier: int = 1
    table_class: str = "unsupported"
    period_role: str = "current"
    exclusion_reason: str = ""
    layout_key: str = ""
    layout_confidence: float = 0.0
    layout_evidence: tuple[str, ...] = ()
    orientation_key: str = ""
    orientation_confidence: float = 0.0
    orientation_evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class FunctionalExpenseInput:
    account_key: str
    expense_role: str
    classification: str
    label: str
    amount: int
    source: str
    unit_multiplier: int = 1


@dataclass(frozen=True)
class ReconciliationInputs:
    statement_lines: list[StatementLineInput]
    cfs_lines: list[CfsLineInput]
    note_balances: list[NoteBalanceInput]
    note_movements: list[NoteMovementInput]
    functional_expenses: list[FunctionalExpenseInput]


def extract_reconciliation_inputs(report: FullReport) -> ReconciliationInputs:
    scoped_report = FullReport(
        report.source,
        report.company,
        report.statements,
        primary_note_sections(report.notes),
    )
    classified = classify_report(scoped_report)
    note_account_by_section: dict[tuple[str, str], str] = {}
    note_account_by_table: dict[str, str] = {}
    for topic in classified.note_topics:
        note_account_by_section.setdefault((topic.section_id, topic.title), topic.topic_key)
        if "/table:" in topic.source:
            note_account_by_table.setdefault(topic.source, topic.topic_key)

    cfs_lines = _extract_cfs_lines(report)
    note_movements = _extract_note_movements(scoped_report, note_account_by_section, note_account_by_table)
    note_movements = _include_unscoped_financing_cashflow_movements(
        note_movements, report, scoped_report, cfs_lines
    )
    layout_lookup = _layout_metadata_lookup(scoped_report)
    note_balances = _attach_balance_layout_metadata(
        _extract_note_balances(
            scoped_report,
            note_account_by_section,
            note_account_by_table,
            layout_lookup,
        ),
        layout_lookup,
    )
    note_movements = _attach_movement_layout_metadata(note_movements, layout_lookup)

    return ReconciliationInputs(
        statement_lines=[
            StatementLineInput(line.account_key, line.label, line.amount, line.source)
            for line in classified.statement_lines
            if line.statement_title != "현금흐름표"
        ],
        cfs_lines=cfs_lines,
        note_balances=note_balances,
        note_movements=note_movements,
        functional_expenses=_extract_functional_expenses(scoped_report),
    )


@dataclass(frozen=True)
class _LayoutMetadata:
    item: NoteTableInventoryItem
    layout: LayoutClassification
    orientation: TableOrientation
    layout_key: str
    layout_confidence: float
    layout_evidence: tuple[str, ...]
    orientation_key: str
    orientation_confidence: float
    orientation_evidence: tuple[str, ...]


@dataclass(frozen=True)
class _BalanceSelection:
    account_key: str
    row_idx: int
    amount: int
    col_idx: int
    source: str
    unit_multiplier: int


_ASSET_LOCATOR_ACCOUNT_KEYS = frozenset(
    {"property_plant_equipment", "intangible_assets", "investment_property"}
)


def _layout_metadata_lookup(report: FullReport) -> dict[str, _LayoutMetadata]:
    lookup: dict[str, _LayoutMetadata] = {}
    for item in build_note_inventory(report).tables:
        layout = classify_layout(item)
        orientation = detect_orientation(headers=item.headers, row_labels=item.row_labels)
        lookup[item.source] = _LayoutMetadata(
            item,
            layout,
            orientation,
            layout.key,
            layout.confidence,
            layout.evidence,
            orientation.key,
            orientation.confidence,
            orientation.evidence,
        )
    return lookup


def _attach_balance_layout_metadata(
    balances: list[NoteBalanceInput],
    lookup: dict[str, _LayoutMetadata],
) -> list[NoteBalanceInput]:
    return [
        replace(balance, **_layout_replace_kwargs(_source_table(balance.source), lookup))
        for balance in balances
    ]


def _attach_movement_layout_metadata(
    movements: list[NoteMovementInput],
    lookup: dict[str, _LayoutMetadata],
) -> list[NoteMovementInput]:
    return [
        replace(movement, **_layout_replace_kwargs(_source_table(movement.source), lookup))
        for movement in movements
    ]


def _layout_replace_kwargs(
    table_source: str,
    lookup: dict[str, _LayoutMetadata],
) -> dict[str, object]:
    metadata = lookup.get(table_source)
    if metadata is None:
        return {}
    return {
        "layout_key": metadata.layout_key,
        "layout_confidence": metadata.layout_confidence,
        "layout_evidence": metadata.layout_evidence,
        "orientation_key": metadata.orientation_key,
        "orientation_confidence": metadata.orientation_confidence,
        "orientation_evidence": metadata.orientation_evidence,
    }


def _source_table(source: str) -> str:
    return source.split("/row:", 1)[0]


def _extract_cfs_lines(report: FullReport) -> list[CfsLineInput]:
    lines: list[CfsLineInput] = []
    processed_cashflow_statement = False
    for section in report.statements:
        if section.title != "현금흐름표":
            continue
        if processed_cashflow_statement:
            continue
        processed_cashflow_statement = True
        first_table_index: int | None = None
        for block in section.blocks:
            table = block.table
            if table is None or not table.rows:
                continue
            if first_table_index is None:
                first_table_index = table.index
            if table.index != first_table_index:
                continue
            headers = table.rows[0]
            for row_idx, row in enumerate(table.rows[1:], start=1):
                if not row:
                    continue
                label = row[0]
                movement = _classify_cfs_movement(label)
                if movement is None:
                    continue
                amount, col_idx = _cfs_line_amount(row, headers)
                if amount is None or col_idx is None:
                    continue
                amount *= table.unit_multiplier
                amount = _cashflow_directional_amount(amount, movement[1])
                if amount == 0:
                    continue
                lines.append(
                    CfsLineInput(
                        account_key=movement[0],
                        movement_role=movement[1],
                        label=label,
                        amount=amount,
                        source=_source(section, table.index, row_idx, col_idx),
                    )
                )
    return lines


def _cfs_line_amount(row: list[str], headers: list[str]) -> tuple[int | None, int | None]:
    if current_period_columns(headers):
        return amount_from_current_period(row, headers)
    return _row_amount(row, headers)


def _extract_note_balances(
    report: FullReport,
    note_account_by_section: dict[tuple[str, str], str],
    note_account_by_table: dict[str, str],
    layout_lookup: dict[str, _LayoutMetadata],
) -> list[NoteBalanceInput]:
    balances: list[NoteBalanceInput] = []
    for section in report.notes:
        for block in section.blocks:
            table = block.table
            if table is None or not table.rows:
                continue
            account_key = note_account_by_table.get(
                _table_source(section, table.index),
                note_account_by_section.get((section.section_id, section.title)),
            )
            metadata = layout_lookup.get(_table_source(section, table.index))
            asset_located = _asset_table_balance_amount(
                report.company,
                section,
                metadata,
                table,
                account_key,
            )
            for row_idx, row in enumerate(table.rows[1:], start=1):
                if not row:
                    continue
                row_account_key = account_key
                label = row[0]
                trade_receivable_label = None
                is_asset_located_row = (
                    asset_located is not None
                    and row_account_key == asset_located.account_key
                    and row_idx == asset_located.row_idx
                )
                if (
                    row_account_key is None
                    or not (
                        is_asset_located_row
                        or _is_ending_balance_row(row_account_key, row[0], table, row_idx)
                    )
                ):
                    trade_receivable_label = _trade_receivable_row_label(row)
                    if trade_receivable_label is None:
                        continue
                    row_account_key = "trade_receivables"
                    label = trade_receivable_label
                if trade_receivable_label is None:
                    if _is_intangible_ending_row_with_goodwill_columns(
                        row_account_key, row[0], table
                    ):
                        extra_amount, extra_col_idx = _intangible_excluding_goodwill_balance_amount(
                            row, table.rows
                        )
                        if extra_amount is not None and extra_col_idx is not None:
                            balances.append(
                                NoteBalanceInput(
                                    row_account_key,
                                    "ending",
                                    section.note_no,
                                    label,
                                    extra_amount * table.unit_multiplier,
                                    _source(section, table.index, row_idx, extra_col_idx),
                                    table.unit_multiplier,
                                )
                            )
                    if row_account_key == "trade_receivables":
                        label = _trade_receivable_balance_label(row)
                        amount, col_idx = _trade_receivable_balance_amount(row, table.rows)
                    elif is_asset_located_row and asset_located is not None:
                        balances.append(
                            NoteBalanceInput(
                                row_account_key,
                                "ending",
                                section.note_no,
                                label,
                                asset_located.amount,
                                asset_located.source,
                                asset_located.unit_multiplier,
                            )
                        )
                        continue
                    elif _is_asset_total_balance_row(row_account_key, row[0], table):
                        located = _asset_total_balance_amount(
                            report.company,
                            section,
                            metadata,
                            table,
                            row_idx,
                            row_account_key,
                        )
                        if located is not None:
                            balances.append(
                                NoteBalanceInput(
                                    row_account_key,
                                    "ending",
                                    section.note_no,
                                    label,
                                    located.amount,
                                    located.source,
                                    located.unit_multiplier,
                                )
                            )
                            continue
                        amount, col_idx = None, None
                    elif _is_asset_ending_row_with_total_column(
                        row_account_key, row[0], table
                    ):
                        located = _asset_family_total_balance_amount(
                            report.company,
                            section,
                            metadata,
                            table,
                            row_idx,
                            row_account_key,
                        )
                        if located is not None:
                            balances.append(
                                NoteBalanceInput(
                                    row_account_key,
                                    "ending",
                                    section.note_no,
                                    label,
                                    located.amount,
                                    located.source,
                                    located.unit_multiplier,
                                )
                            )
                            continue
                        amount, col_idx = None, None
                    else:
                        amount, col_idx = balance_amount(row, table.rows[0])
                else:
                    amount, col_idx = _trade_receivable_row_amount(row, trade_receivable_label)
                if amount is None or col_idx is None:
                    continue
                amount *= table.unit_multiplier
                balances.append(
                    NoteBalanceInput(
                        row_account_key,
                        "ending",
                        section.note_no,
                        label,
                        amount,
                        _source(section, table.index, row_idx, col_idx),
                        table.unit_multiplier,
                    )
                )
    return balances


def _trade_receivable_row_label(row: list[str]) -> str | None:
    for cell in row[:4]:
        normalized = _normalize(cell)
        if (
            "매출채권" in normalized
            and "계약자산" not in normalized
            and "대손" not in normalized
            and "손실충당" not in normalized
        ):
            return cell
    return None


def _trade_receivable_row_amount(row: list[str], label: str) -> tuple[int | None, int | None]:
    try:
        label_idx = row.index(label)
    except ValueError:
        label_idx = 0
    for col_idx in range(label_idx + 1, len(row)):
        amount = parse_amount(row[col_idx])
        if amount not in (None, 0):
            return amount, col_idx
    return None, None


def _trade_receivable_balance_label(row: list[str]) -> str:
    labels: list[str] = []
    for cell in row[:3]:
        normalized = _normalize(cell)
        if not normalized or parse_amount(cell) is not None:
            continue
        if normalized in {_normalize(label) for label in labels}:
            continue
        labels.append(cell)
    return " / ".join(labels) if labels else row[0]


def _trade_receivable_balance_amount(row: list[str], rows: list[list[str]]) -> tuple[int | None, int | None]:
    headers = rows[0] if rows else []
    amount, col_idx = _trade_receivable_current_net_amount(row, rows)
    if amount is not None and col_idx is not None:
        return amount, col_idx
    receivable_columns = [
        idx
        for idx, header in enumerate(headers)
        if idx < len(row) and "매출채권" in _normalize(header)
    ]
    if len(receivable_columns) > 1:
        values: list[tuple[int, int]] = []
        for col_idx in receivable_columns:
            amount = parse_amount(row[col_idx])
            if amount is not None:
                values.append((amount, col_idx))
        if values:
            return sum(amount for amount, _ in values), values[0][1]
    return balance_amount(row, headers)


def _trade_receivable_current_net_amount(
    row: list[str], rows: list[list[str]]
) -> tuple[int | None, int | None]:
    if len(rows) < 2:
        return None, None
    current_aliases = {"당기", "당기말", "당기말현재", "당기현재", "당년도", "당해"}
    net_aliases = {"순액", "순장부금액", "장부금액", "장부가액", "장부금액합계"}
    current_header = rows[0]
    detail_header = rows[1]
    for col_idx, header in enumerate(current_header):
        if col_idx >= len(row) or col_idx >= len(detail_header):
            continue
        if _normalize(header) not in current_aliases:
            continue
        if _normalize(detail_header[col_idx]) not in net_aliases:
            continue
        amount = parse_amount(row[col_idx])
        if amount is not None:
            return amount, col_idx
    return None, None


def _asset_total_balance_amount(
    company: str,
    section: ReportSection,
    metadata: _LayoutMetadata | None,
    table,
    row_idx: int,
    account_key: str,
) -> _BalanceSelection | None:
    if _asset_locator_enabled(company, account_key, metadata):
        return _locate_asset_balance_amount(
            section,
            metadata,
            table,
            account_key,
            TargetAmountRole.NET_CARRYING_AMOUNT,
        )
    return _legacy_asset_total_balance_amount(section, table, row_idx, account_key)


def _legacy_asset_total_balance_amount(
    section: ReportSection,
    table,
    row_idx: int,
    account_key: str,
) -> _BalanceSelection | None:
    rows = table.rows
    row = rows[row_idx]
    for col_idx in _asset_total_carrying_amount_columns(rows, account_key):
        if col_idx >= len(row):
            continue
        amount = parse_amount(row[col_idx])
        if amount is not None:
            return _balance_selection(section, table, row_idx, col_idx, amount, account_key)
    amount, col_idx = balance_amount(row, rows[0] if rows else [])
    if amount is None or col_idx is None:
        return None
    return _balance_selection(section, table, row_idx, col_idx, amount, account_key)


def _asset_family_total_balance_amount(
    company: str,
    section: ReportSection,
    metadata: _LayoutMetadata | None,
    table,
    row_idx: int,
    account_key: str,
) -> _BalanceSelection | None:
    if _asset_locator_enabled(company, account_key, metadata):
        return _locate_asset_balance_amount(
            section,
            metadata,
            table,
            account_key,
            TargetAmountRole.NET_CARRYING_AMOUNT,
        )
    return _legacy_asset_family_total_balance_amount(section, table, row_idx, account_key)


def _legacy_asset_family_total_balance_amount(
    section: ReportSection,
    table,
    row_idx: int,
    account_key: str,
) -> _BalanceSelection | None:
    rows = table.rows
    row = rows[row_idx]
    for col_idx in _asset_family_total_columns(rows, account_key):
        if col_idx >= len(row):
            continue
        amount = parse_amount(row[col_idx])
        if amount is not None:
            return _balance_selection(section, table, row_idx, col_idx, amount, account_key)
    amount, col_idx = balance_amount(row, rows[0] if rows else [])
    if amount is None or col_idx is None:
        return None
    return _balance_selection(section, table, row_idx, col_idx, amount, account_key)


def _asset_locator_enabled(
    company: str,
    account_key: str,
    metadata: _LayoutMetadata | None,
) -> bool:
    if not bool(company) or account_key not in _ASSET_LOCATOR_ACCOUNT_KEYS:
        return False
    if metadata is None:
        return False
    return metadata.layout_key != "unknown_layout" and metadata.orientation_key != "unknown"


def _asset_table_balance_amount(
    company: str,
    section: ReportSection,
    metadata: _LayoutMetadata | None,
    table,
    account_key: str | None,
) -> _BalanceSelection | None:
    if account_key is None or not _asset_locator_enabled(company, account_key, metadata):
        return None
    return _locate_asset_balance_amount(
        section,
        metadata,
        table,
        account_key,
        TargetAmountRole.NET_CARRYING_AMOUNT,
    )


def _locate_asset_balance_amount(
    section: ReportSection,
    metadata: _LayoutMetadata | None,
    table,
    account_key: str,
    role: TargetAmountRole,
) -> _BalanceSelection | None:
    if metadata is None:
        return None
    result = amount_locator.locate(
        metadata.item,
        table,
        account_key,
        role,
        layout=metadata.layout,
        orientation=metadata.orientation,
        scope=section.scope or None,
    )
    if not isinstance(result, amount_locator.LocatedAmount):
        return None
    return _BalanceSelection(
        account_key=account_key,
        row_idx=result.row_index,
        amount=result.amount,
        col_idx=result.col_index,
        source=result.source,
        unit_multiplier=result.unit_multiplier,
    )


def _balance_selection(
    section: ReportSection,
    table,
    row_idx: int,
    col_idx: int,
    raw_amount: int,
    account_key: str,
) -> _BalanceSelection:
    return _BalanceSelection(
        account_key=account_key,
        row_idx=row_idx,
        amount=raw_amount * table.unit_multiplier,
        col_idx=col_idx,
        source=_source(section, table.index, row_idx, col_idx),
        unit_multiplier=table.unit_multiplier,
    )


def _intangible_excluding_goodwill_balance_amount(
    row: list[str], rows: list[list[str]]
) -> tuple[int | None, int | None]:
    values: list[tuple[int, int]] = []
    for col_idx in _intangible_excluding_goodwill_carrying_columns(rows):
        if col_idx >= len(row):
            continue
        amount = parse_amount(row[col_idx])
        if amount is not None:
            values.append((amount, col_idx))
    if values:
        return sum(amount for amount, _ in values), values[0][1]
    return balance_amount(row, rows[0] if rows else [])


def _asset_total_carrying_amount_columns(
    rows: list[list[str]], account_key: str
) -> list[int]:
    if not rows:
        return []
    header_rows = rows[:4]
    max_cols = max((len(row) for row in header_rows), default=0)
    current_aliases = {"당기", "당기말", "당기말현재", "당기현재", "당년도", "당해"}
    carrying_aliases = {
        "장부금액",
        "순장부금액",
        "장부가액",
        "장부금액합계",
        "순장부금액합계",
        "장부가액합계",
        "합계",
    }
    family_total_aliases = _asset_family_total_header_aliases(account_key)
    current_carrying: list[int] = []
    current_family_total: list[int] = []
    carrying_only: list[int] = []
    family_total_only: list[int] = []
    for col_idx in range(max_cols):
        header_parts = [
            _normalize(row[col_idx])
            for row in header_rows
            if col_idx < len(row) and row[col_idx] and parse_amount(row[col_idx]) is None
        ]
        if not header_parts:
            continue
        has_current = any(
            part in current_aliases or ("당" in part and "전" not in part)
            for part in header_parts
        )
        has_carrying = any(part in carrying_aliases for part in header_parts)
        has_family_total = any(part in family_total_aliases for part in header_parts)
        if has_current and has_carrying:
            current_carrying.append(col_idx)
        elif has_current and has_family_total:
            current_family_total.append(col_idx)
        elif has_carrying:
            carrying_only.append(col_idx)
        elif has_family_total:
            family_total_only.append(col_idx)
    return current_carrying or current_family_total or carrying_only or family_total_only


def _intangible_excluding_goodwill_carrying_columns(rows: list[list[str]]) -> list[int]:
    if not rows:
        return []
    header_rows = rows[:5]
    max_cols = max((len(row) for row in header_rows), default=0)
    carrying_aliases = {
        "장부금액",
        "순장부금액",
        "장부가액",
        "장부금액합계",
        "순장부금액합계",
        "장부가액합계",
        "합계",
    }
    columns: list[int] = []
    for col_idx in range(max_cols):
        header_parts = [
            _normalize(row[col_idx])
            for row in header_rows
            if col_idx < len(row) and row[col_idx] and parse_amount(row[col_idx]) is None
        ]
        if not header_parts:
            continue
        terminal_header = header_parts[-1]
        has_non_goodwill_intangible = any(
            "영업권이외의무형자산" in part for part in header_parts
        )
        has_carrying = terminal_header in carrying_aliases
        if has_non_goodwill_intangible and has_carrying:
            columns.append(col_idx)
    return columns


def _asset_family_total_columns(rows: list[list[str]], account_key: str) -> list[int]:
    if not rows:
        return []
    header_rows = rows[:4]
    max_cols = max((len(row) for row in header_rows), default=0)
    aliases = _asset_family_total_header_aliases(account_key)
    columns: list[int] = []
    for col_idx in range(max_cols):
        header_parts = [
            _normalize(row[col_idx])
            for row in header_rows
            if col_idx < len(row) and row[col_idx]
        ]
        if any(part in aliases for part in header_parts):
            columns.append(col_idx)
    return columns


def _asset_family_total_header_aliases(account_key: str) -> set[str]:
    aliases = {
        "property_plant_equipment": {"유형자산합계", "유형자산총계"},
        "intangible_assets": {
            "무형자산합계",
            "무형자산총계",
            "무형자산및영업권",
            "영업권이외의무형자산합계",
        },
        "investment_property": {"투자부동산합계", "투자부동산총계"},
    }
    return aliases.get(account_key, set())


def _extract_note_movements(
    report: FullReport,
    note_account_by_section: dict[tuple[str, str], str],
    note_account_by_table: dict[str, str],
) -> list[NoteMovementInput]:
    movements: list[NoteMovementInput] = []
    for section in report.notes:
        for block in section.blocks:
            table = block.table
            if table is None or not table.rows:
                continue
            if _is_prior_period_table(table.heading):
                continue
            movements.extend(_extract_financing_cashflow_note_movements(section, table))
            movements.extend(_extract_lease_interest_financing_adjustments(section, table))
            movements.extend(_extract_noncash_asset_cashflow_adjustments(section, table))
            movements.extend(_extract_asset_disposal_adjustments(section, table))
            movements.extend(_extract_right_of_use_asset_acquisition_adjustments(section, table))
            account_key = note_account_by_table.get(
                _table_source(section, table.index),
                note_account_by_section.get((section.section_id, section.title)),
            )
            if account_key is None:
                continue
            if account_key == "property_plant_equipment" and _is_right_of_use_asset_table(table.heading):
                continue
            movements.extend(_extract_rollforward_column_movements(section, table, account_key))
            for row_idx, row in enumerate(table.rows[1:], start=1):
                if not row:
                    continue
                movement_role = _classify_note_movement(account_key, row[0])
                if movement_role is None:
                    continue
                amount, col_idx = _row_amount(row, table.rows[0])
                if amount is None or col_idx is None:
                    continue
                amount *= table.unit_multiplier
                movements.append(
                    NoteMovementInput(
                        account_key,
                        movement_role,
                        section.note_no,
                        row[0],
                        amount,
                        _source(section, table.index, row_idx, col_idx),
                        table.unit_multiplier,
                    )
                )
    return movements


def _extract_lease_interest_financing_adjustments(section: ReportSection, table) -> list[NoteMovementInput]:
    heading = _normalize(f"{section.title} {table.heading}")
    if "리스부채" not in heading:
        return []

    movements: list[NoteMovementInput] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        label = _row_label(row)
        normalized = _normalize(label)
        if "리스부채에대한이자비용" not in normalized:
            continue
        amount, col_idx = _row_amount(row, _cashflow_note_amount_headers(table.rows))
        if amount is None or col_idx is None:
            continue
        movements.append(
            NoteMovementInput(
                "lease_liabilities",
                "financing_cashflow",
                section.note_no,
                "리스부채 이자비용 조정",
                abs(amount) * table.unit_multiplier,
                _source(section, table.index, row_idx, col_idx),
                table.unit_multiplier,
            )
        )
    return movements


def _include_unscoped_financing_cashflow_movements(
    scoped_movements: list[NoteMovementInput],
    report: FullReport,
    scoped_report: FullReport,
    cfs_lines: list[CfsLineInput],
) -> list[NoteMovementInput]:
    if len(scoped_report.notes) == len(report.notes):
        return scoped_movements

    movements = list(scoped_movements)
    seen_sources = {movement.source for movement in movements}
    scoped_financing_accounts = {
        movement.account_key
        for movement in scoped_movements
        if movement.movement_role == "financing_cashflow"
    }
    expected_by_account = {
        account_key: sum(line.amount for line in cfs_lines if line.account_key == account_key)
        for account_key in scoped_financing_accounts
    }
    candidates_by_account: dict[str, list[NoteMovementInput]] = {
        account_key: [] for account_key in scoped_financing_accounts
    }
    for section in report.notes:
        for block in section.blocks:
            table = block.table
            if table is None or not table.rows or _is_prior_period_table(table.heading):
                continue
            for movement in _extract_financing_cashflow_note_movements(section, table):
                if movement.source in seen_sources:
                    continue
                if movement.account_key not in candidates_by_account:
                    continue
                candidates_by_account[movement.account_key].append(movement)

    for account_key, candidates in candidates_by_account.items():
        expected = expected_by_account.get(account_key)
        if expected is None:
            continue
        for movement in _matching_financing_cashflow_candidates(candidates, expected):
            if movement.source in seen_sources:
                continue
            seen_sources.add(movement.source)
            movements.append(movement)
    return movements


def _matching_financing_cashflow_candidates(
    candidates: list[NoteMovementInput], expected: int
) -> list[NoteMovementInput]:
    for candidate in candidates:
        if candidate.amount == expected:
            return [candidate]
    if len(candidates) > 10:
        return []
    for subset_size in range(2, len(candidates) + 1):
        for subset in combinations(candidates, subset_size):
            if sum(movement.amount for movement in subset) == expected:
                return list(subset)
    return []


def _extract_rollforward_column_movements(
    section: ReportSection, table, account_key: str
) -> list[NoteMovementInput]:
    if not table.rows:
        return []
    headers = table.rows[0]
    movements: list[NoteMovementInput] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        label = _rollforward_row_label(row)
        if account_key == "property_plant_equipment":
            movements.extend(
                _right_of_use_asset_disposal_column_movements(section, table, row, row_idx, label)
            )
            movements.extend(
                _government_grant_disposal_column_movements(section, table, row, row_idx, label)
            )
        if _is_accumulated_depreciation_disposal_row(label):
            movements.extend(
                _accumulated_depreciation_disposal_movements(
                    section, table, row, row_idx, label, account_key
                )
            )
            continue
        if not _is_rollforward_total_row(label, account_key):
            continue
        for col_idx, header in enumerate(headers):
            if col_idx >= len(row):
                continue
            movement_role = _classify_rollforward_movement_header(header)
            if movement_role is None:
                continue
            amount = parse_amount(row[col_idx])
            if amount is None or amount == 0:
                continue
            movements.append(
                NoteMovementInput(
                    account_key,
                    movement_role,
                    section.note_no,
                    f"{label} {header}".strip(),
                    amount * table.unit_multiplier,
                    _source(section, table.index, row_idx, col_idx),
                    table.unit_multiplier,
                    table_class=_rollforward_table_class(account_key),
                )
            )
    return movements


def _rollforward_table_class(account_key: str) -> str:
    if account_key == "intangible_assets":
        return "intangible_rollforward"
    if account_key == "investment_property":
        return "investment_property_rollforward"
    return "asset_rollforward"


def _is_accumulated_depreciation_disposal_row(label: str) -> bool:
    normalized = _normalize(label)
    return any(alias in normalized for alias in ("감가상각누계", "상각누계"))


def _accumulated_depreciation_disposal_movements(
    section: ReportSection,
    table,
    row: list[str],
    row_idx: int,
    label: str,
    account_key: str,
) -> list[NoteMovementInput]:
    movements: list[NoteMovementInput] = []
    for col_idx, header in enumerate(table.rows[0]):
        if col_idx >= len(row) or "처분" not in _normalize(header):
            continue
        amount = parse_amount(row[col_idx])
        if amount is None or amount == 0:
            continue
        movements.append(
            NoteMovementInput(
                account_key,
                "accumulated_depreciation_disposal",
                section.note_no,
                f"{label} {header}".strip(),
                amount * table.unit_multiplier,
                _source(section, table.index, row_idx, col_idx),
                table.unit_multiplier,
                table_class=_rollforward_table_class(account_key),
            )
        )
    return movements


def _right_of_use_asset_disposal_column_movements(
    section: ReportSection, table, row: list[str], row_idx: int, label: str
) -> list[NoteMovementInput]:
    if "처분" not in _normalize(label):
        return []

    movements: list[NoteMovementInput] = []
    for col_idx, header in enumerate(table.rows[0]):
        if col_idx >= len(row) or "사용권자산" not in _normalize(header):
            continue
        amount = parse_amount(row[col_idx])
        if amount is None or amount == 0:
            continue
        movements.append(
            NoteMovementInput(
                "property_plant_equipment",
                "right_of_use_noncash_disposal",
                section.note_no,
                "사용권자산 처분",
                amount * table.unit_multiplier,
                _source(section, table.index, row_idx, col_idx),
                table.unit_multiplier,
                table_class="asset_rollforward",
            )
        )
    return movements


def _government_grant_disposal_column_movements(
    section: ReportSection, table, row: list[str], row_idx: int, label: str
) -> list[NoteMovementInput]:
    normalized_label = _normalize(label)
    if "정부보조금" not in normalized_label or "차감전" in normalized_label:
        return []

    movements: list[NoteMovementInput] = []
    for col_idx, header in enumerate(table.rows[0]):
        if col_idx >= len(row) or "처분" not in _normalize(header):
            continue
        amount = parse_amount(row[col_idx])
        if amount is None or amount == 0:
            continue
        movements.append(
            NoteMovementInput(
                "property_plant_equipment",
                "government_grant_disposal",
                section.note_no,
                "정부보조금 처분",
                amount * table.unit_multiplier,
                _source(section, table.index, row_idx, col_idx),
                table.unit_multiplier,
                table_class="asset_rollforward",
            )
        )
    return movements


def _rollforward_row_label(row: list[str]) -> str:
    labels: list[str] = []
    for cell in row:
        if parse_amount(cell) is not None:
            break
        if cell.strip():
            labels.append(cell)
    return labels[-1] if labels else _row_label(row)


def _is_rollforward_total_row(label: str, account_key: str) -> bool:
    normalized = _normalize(label)
    if "합계" not in normalized:
        return False
    if account_key == "property_plant_equipment":
        return "유형자산" in normalized
    if account_key == "intangible_assets":
        return "무형자산" in normalized
    if account_key == "investment_property":
        return "투자부동산" in normalized
    return False


def _classify_rollforward_movement_header(header: str) -> str | None:
    normalized = _normalize(header)
    if not normalized or any(alias in normalized for alias in ("취득원가", "기초", "기말", "장부금액")):
        return None
    if "사업결합" in normalized and any(alias in normalized for alias in ("취득", "증가")):
        return "business_combination"
    if "취득" in normalized:
        return "acquisition"
    if "처분" in normalized and "손상" in normalized:
        return None
    if "처분" in normalized:
        return "disposal"
    return None


def _extract_asset_disposal_adjustments(section: ReportSection, table) -> list[NoteMovementInput]:
    heading = _normalize(table.heading)
    if not _is_asset_disposal_adjustment_table(heading):
        return []

    movements: list[NoteMovementInput] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        label = _asset_disposal_adjustment_label(row)
        normalized = _normalize(label)
        account_keys = _asset_disposal_adjustment_account_keys(normalized)
        if not account_keys:
            continue

        if "손실" in normalized:
            movement_role = "disposal_loss"
        elif "이익" in normalized or "손익" in normalized:
            movement_role = "disposal_gain_loss"
        else:
            continue

        amount, col_idx = _asset_disposal_adjustment_amount(row, table.rows[0])
        if amount is None or col_idx is None:
            continue
        for account_key in account_keys:
            movements.append(
                NoteMovementInput(
                    account_key,
                    movement_role,
                    section.note_no,
                    label,
                    amount * table.unit_multiplier,
                    _source(section, table.index, row_idx, col_idx),
                    table.unit_multiplier,
                )
            )
    return movements


def _asset_disposal_adjustment_amount(row: list[str], headers: list[str]) -> tuple[int | None, int | None]:
    if current_period_columns(headers):
        return amount_from_current_period(row, headers)
    return _row_amount(row, headers)


def _asset_disposal_adjustment_label(row: list[str]) -> str:
    for cell in row[:3]:
        normalized = _normalize(cell)
        if _asset_disposal_adjustment_account_keys(normalized):
            return cell
    return _row_label(row)


def _asset_disposal_adjustment_account_keys(normalized_label: str) -> tuple[str, ...]:
    if "유무형자산처분" in normalized_label or "유ㆍ무형자산처분" in normalized_label:
        return ("property_plant_equipment", "intangible_assets")
    if "유형자산처분" in normalized_label:
        return ("property_plant_equipment",)
    if "무형자산처분" in normalized_label:
        return ("intangible_assets",)
    return ()


def _extract_right_of_use_asset_acquisition_adjustments(section: ReportSection, table) -> list[NoteMovementInput]:
    heading = _normalize(table.heading)
    if "사용권자산" not in heading:
        return []

    movements: list[NoteMovementInput] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        label = row[0] if row else ""
        normalized = _normalize(label)
        if not any(alias in normalized for alias in ("취득", "자본적지출", "신규")):
            continue
        if any(alias in normalized for alias in ("처분", "감가상각", "상각", "손상", "기초", "기말")):
            continue
        amount, col_idx = _row_amount(row, table.rows[0])
        if amount is None or col_idx is None:
            continue
        movements.append(
            NoteMovementInput(
                "property_plant_equipment",
                "right_of_use_noncash_acquisition",
                section.note_no,
                label,
                amount * table.unit_multiplier,
                _source(section, table.index, row_idx, col_idx),
                table.unit_multiplier,
            )
        )
    return movements


def _is_asset_disposal_adjustment_table(normalized_heading: str) -> bool:
    operating_cashflow_headings = (
        "영업으로부터창출된현금",
        "영업에서창출된현금흐름",
        "영업으로부터창출된현금흐름",
        "영업활동현금흐름",
        "영업활동으로인한현금흐름",
        "영업활동으로부터의현금흐름",
        "영업활동으로부터창출된현금흐름",
    )
    income_expense_headings = (
        "기타수익",
        "기타비용",
        "기타손익",
        "기타영업외수익",
        "기타영업외비용",
        "영업외수익",
        "영업외비용",
    )
    cashflow_note_headings = (
        "현금흐름표",
        "연결현금흐름표",
    )
    return (
        any(alias in normalized_heading for alias in operating_cashflow_headings)
        or any(alias in normalized_heading for alias in income_expense_headings)
        or any(alias in normalized_heading for alias in cashflow_note_headings)
    )


def _extract_noncash_asset_cashflow_adjustments(section: ReportSection, table) -> list[NoteMovementInput]:
    heading = _normalize(table.heading)
    if "현금" not in heading or not any(alias in heading for alias in ("유입", "유출", "비현금")):
        return []

    movements: list[NoteMovementInput] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        label = _noncash_asset_label(row)
        normalized = _normalize(label)
        account_keys = _noncash_asset_account_keys(normalized)
        if not account_keys:
            continue
        movement_role = _noncash_asset_movement_role(normalized)
        if movement_role is None:
            continue
        amount, col_idx = _noncash_asset_amount(row, table.rows)
        if amount is None or col_idx is None:
            continue
        for account_key in account_keys:
            movement_amount = amount * table.unit_multiplier
            movements.append(
                NoteMovementInput(
                    account_key,
                    movement_role,
                    section.note_no,
                    label,
                    movement_amount,
                    _source(section, table.index, row_idx, col_idx),
                    table.unit_multiplier,
                )
            )
            if _is_terse_positive_asset_payable(normalized, movement_amount):
                movements.append(
                    NoteMovementInput(
                        account_key,
                        "noncash_payable_decrease_candidate",
                        section.note_no,
                        label,
                        movement_amount,
                        _source(section, table.index, row_idx, col_idx),
                        table.unit_multiplier,
                    )
                )
    return movements


def _is_terse_positive_asset_payable(normalized_label: str, amount: int) -> bool:
    return (
        amount > 0
        and "미지급" in normalized_label
        and "취득" in normalized_label
        and ("유형자산" in normalized_label or "무형자산" in normalized_label)
        and not any(alias in normalized_label for alias in ("증가", "감소", "변동", "관련", "따른"))
    )


def _noncash_asset_label(row: list[str]) -> str:
    for cell in row:
        if parse_amount(cell) is not None:
            break
        normalized = _normalize(cell)
        if not normalized or normalized in {"거래내역", "구분", "내용"}:
            continue
        return cell
    return row[0] if row else ""


def _noncash_asset_amount(row: list[str], rows: list[list[str]]) -> tuple[int | None, int | None]:
    return _row_amount(row, _cashflow_note_amount_headers(rows))


def _cashflow_note_amount_headers(rows: list[list[str]]) -> list[str]:
    if not rows:
        return []
    for header in rows[:3]:
        normalized = [_normalize(cell) for cell in header]
        if any(cell in {"당기", "당기말", "당년도"} for cell in normalized):
            return header
    return rows[0]


def _noncash_asset_account_keys(normalized_label: str) -> tuple[str, ...]:
    if "사용권자산" in normalized_label:
        return ("property_plant_equipment",)
    if any(alias in normalized_label for alias in ("유무형자산", "유ㆍ무형자산", "유무형")):
        return ("property_plant_equipment", "intangible_assets")
    if "무형자산" in normalized_label:
        return ("intangible_assets",)
    if "유형자산" in normalized_label or "건설중인자산" in normalized_label:
        return ("property_plant_equipment",)
    return ()


def _noncash_asset_movement_role(normalized_label: str) -> str | None:
    if "사용권자산" in normalized_label and any(
        alias in normalized_label for alias in ("추가", "인식", "취득")
    ):
        return "right_of_use_noncash_acquisition"
    if (
        "사용권자산" in normalized_label
        and "리스부채" in normalized_label
        and "대체" in normalized_label
    ):
        return "right_of_use_noncash_acquisition"
    if _is_payable_increase_only_noncash_acquisition(normalized_label):
        return "noncash_payable_addback"
    if ("미지급" in normalized_label or "지급어음" in normalized_label) and "취득" in normalized_label:
        return "noncash_payable"
    if "미수" in normalized_label and "처분" in normalized_label:
        return "noncash_receivable"
    if "무형자산" in normalized_label and "대체" in normalized_label:
        return "noncash_transfer_acquisition"
    return None


def _is_payable_increase_only_noncash_acquisition(normalized_label: str) -> bool:
    return (
        "미지급" in normalized_label
        and "취득" in normalized_label
        and "따른" in normalized_label
        and "증가" in normalized_label
        and "감소" not in normalized_label
        and "증감" not in normalized_label
    )


def _extract_financing_cashflow_note_movements(section: ReportSection, table) -> list[NoteMovementInput]:
    heading = _normalize(table.heading)
    first_row = _normalize(" ".join(table.rows[0])) if table.rows else ""
    movements = _extract_direct_lease_cashflow_note_movements(section, table)
    movements.extend(_extract_bond_principal_repayment_movements(section, table))
    if (
        "재무활동에서생기는부채" not in heading
        and "재무활동현금흐름" not in first_row
    ):
        return movements

    for row_idx, row in enumerate(table.rows[1:], start=1):
        row_movements = _financing_cashflow_row_amounts(row, table.rows[0])
        if row_movements:
            for account_key, amount, col_idx in row_movements:
                movements.append(
                    NoteMovementInput(
                        account_key,
                        "financing_cashflow",
                        section.note_no,
                        "재무활동현금흐름 " + _financing_liability_label(account_key),
                        amount * table.unit_multiplier,
                        _source(section, table.index, row_idx, col_idx),
                        table.unit_multiplier,
                        table_class="financing_cashflow_reconciliation",
                    )
                )
            continue

        account_key = _financing_liability_account_key(row)
        if account_key is None:
            continue
        for amount, col_idx in _financing_cashflow_amounts(row, table.rows[0]):
            movements.append(
                NoteMovementInput(
                    account_key,
                    "financing_cashflow",
                    section.note_no,
                    "재무활동현금흐름 " + _financing_liability_label(account_key),
                    amount * table.unit_multiplier,
                    _source(section, table.index, row_idx, col_idx),
                    table.unit_multiplier,
                    table_class="financing_cashflow_reconciliation",
                )
            )
    return movements


def _extract_bond_principal_repayment_movements(
    section: ReportSection, table
) -> list[NoteMovementInput]:
    heading = _normalize(f"{section.title} {table.heading}")
    if "사채" not in heading:
        return []
    if not table.rows:
        return []

    repayment_columns = [
        col_idx
        for col_idx, header in enumerate(table.rows[0])
        if "상환" in _normalize(header) and "감소" in _normalize(header)
    ]
    if not repayment_columns:
        return []

    movements: list[NoteMovementInput] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        normalized_label = _normalize(row[0] if row else "")
        if normalized_label not in {"원금", "사채원금", "권면총액"}:
            continue
        for col_idx in repayment_columns:
            if col_idx >= len(row):
                continue
            amount = parse_amount(row[col_idx])
            if amount is None or amount == 0:
                continue
            movements.append(
                NoteMovementInput(
                    "bonds",
                    "financing_cashflow",
                    section.note_no,
                    "사채 원금 상환",
                    -abs(amount) * table.unit_multiplier,
                    _source(section, table.index, row_idx, col_idx),
                    table.unit_multiplier,
                    table_class="financing_cashflow_reconciliation",
                )
            )
    return movements


def _extract_direct_lease_cashflow_note_movements(
    section: ReportSection, table
) -> list[NoteMovementInput]:
    heading = _normalize(f"{section.title} {table.heading}")
    if "사용권자산" not in heading or "현금흐름표" not in heading:
        return []

    movements: list[NoteMovementInput] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        normalized_label = _normalize(" ".join(cell for cell in row if cell))
        if "리스부채" not in normalized_label or not any(
            alias in normalized_label for alias in ("상환", "지급")
        ):
            continue
        if "이자" in normalized_label:
            continue
        amount, col_idx = _row_amount(row, _cashflow_note_amount_headers(table.rows))
        if amount is None or col_idx is None:
            continue
        movements.append(
            NoteMovementInput(
                "lease_liabilities",
                "financing_cashflow",
                section.note_no,
                row[0],
                -abs(amount) * table.unit_multiplier,
                _source(section, table.index, row_idx, col_idx),
                table.unit_multiplier,
                table_class="financing_cashflow_reconciliation",
            )
        )
    return movements


def _is_right_of_use_asset_table(heading: str) -> bool:
    normalized = _normalize(heading)
    return "사용권자산" in normalized


def _financing_liability_account_key(row: list[str]) -> str | None:
    normalized = _normalize(" ".join(row[:3]))
    if any(alias in normalized for alias in ("상각", "외화환산", "유동성대체", "사업결합", "기타")):
        return None
    if "차입금" in normalized and "재무활동에서생기는부채" != normalized:
        return "borrowings"
    if "사채" in normalized:
        return "bonds"
    if "리스부채" in normalized:
        return "lease_liabilities"
    return None


def _financing_liability_label(account_key: str) -> str:
    labels = {
        "borrowings": "차입금",
        "bonds": "사채",
        "lease_liabilities": "리스부채",
    }
    return labels.get(account_key, account_key)


def _financing_cashflow_row_amounts(
    row: list[str], headers: list[str]
) -> list[tuple[str, int, int]]:
    normalized_label = _normalize(" ".join(row[:3]))
    if "재무활동에서생기는부채" not in normalized_label:
        return []
    if not any(
        token in normalized_label
        for token in (
            "현금흐름",
            "차입금의증가",
            "차입금의감소",
            "새로운차입금",
            "차입금의상환",
            "사채의증가",
            "사채의감소",
            "리스부채의증가",
            "리스부채의감소",
        )
    ):
        return []

    movements: list[tuple[str, int, int]] = []
    for col_idx, header in enumerate(headers):
        if col_idx >= len(row):
            continue
        account_key = _financing_liability_account_key([header])
        if account_key is None:
            continue
        amount = parse_amount(row[col_idx])
        if amount is None or amount == 0:
            continue
        amount = _directional_financing_cashflow_amount(amount, normalized_label)
        movements.append((account_key, amount, col_idx))
    return movements


def _financing_cashflow_amount(row: list[str], headers: list[str]) -> tuple[int | None, int | None]:
    amounts = _financing_cashflow_amounts(row, headers)
    if not amounts:
        return None, None
    return amounts[0]


def _financing_cashflow_amounts(row: list[str], headers: list[str]) -> list[tuple[int, int]]:
    amounts: list[tuple[int, int]] = []
    for col_idx, header in enumerate(headers):
        normalized_header = _normalize(header)
        if col_idx < len(row) and "현금흐름" in normalized_header and "비현금" not in normalized_header:
            amount = parse_amount(row[col_idx])
            if amount is not None and _is_direct_financing_cashflow_column(headers, col_idx):
                amounts.append((_directional_financing_cashflow_amount(amount, normalized_header), col_idx))
        elif col_idx < len(row) and _is_financing_cashflow_action_column(normalized_header):
            amount = parse_amount(row[col_idx])
            if amount is not None and amount != 0:
                amounts.append((_directional_financing_cashflow_amount(amount, normalized_header), col_idx))
        elif "재무활동현금흐름" in normalized_header:
            for next_col_idx in range(col_idx + 1, len(row)):
                amount = parse_amount(row[next_col_idx])
                if amount is not None:
                    amounts.append((_directional_financing_cashflow_amount(amount, normalized_header), next_col_idx))
                    break
    if amounts:
        return amounts
    numeric_cells: list[tuple[int, int]] = []
    for col_idx, cell in enumerate(row):
        amount = parse_amount(cell)
        if amount is not None:
            numeric_cells.append((col_idx, amount))
    if len(numeric_cells) < 2:
        return []
    col_idx, amount = numeric_cells[1]
    return [(amount, col_idx)]


def _is_financing_cashflow_action_column(normalized_header: str) -> bool:
    if not normalized_header:
        return False
    return normalized_header in {
        "증가",
        "감소",
        "유입",
        "유출",
        "차입",
        "차입금차입",
        "차입금의차입",
        "발행",
        "사채발행",
        "사채의발행",
        "상환",
        "차입금상환",
        "차입금의상환",
        "사채상환",
        "사채의상환",
    }


def _directional_financing_cashflow_amount(amount: int, normalized_label: str) -> int:
    if "상환" in normalized_label and amount > 0:
        return -amount
    if "유출" in normalized_label and amount > 0:
        return -amount
    if "유입" in normalized_label and "유출" not in normalized_label and amount < 0:
        return abs(amount)
    if "감소" in normalized_label and "증가" not in normalized_label and amount > 0:
        return -amount
    if "증가" in normalized_label and "감소" not in normalized_label and amount < 0:
        return abs(amount)
    if (
        any(alias in normalized_label for alias in ("차입", "발행"))
        and not any(alias in normalized_label for alias in ("상환", "감소"))
        and amount < 0
    ):
        return abs(amount)
    return amount


def _is_direct_financing_cashflow_column(headers: list[str], col_idx: int) -> bool:
    normalized_header = _normalize(headers[col_idx])
    if normalized_header == "현금흐름":
        return True
    if col_idx > 0 and _normalize(headers[col_idx - 1]) in {"", "구분"}:
        return False
    return any("기초" in _normalize(header) for header in headers[:col_idx])


def _extract_functional_expenses(report: FullReport) -> list[FunctionalExpenseInput]:
    expenses: list[FunctionalExpenseInput] = []
    for section in report.notes:
        for block in section.blocks:
            table = block.table
            if table is None or not table.rows:
                continue
            if _is_prior_period_table(table.heading):
                continue
            table_kind = _functional_expense_table_kind(section, table)
            if table_kind is None:
                continue
            for row_idx, row in enumerate(table.rows[1:], start=1):
                extracted = _functional_expense_from_row(table_kind, section, table, row_idx, row)
                if extracted is not None:
                    expenses.append(extracted)
    return expenses


def _functional_expense_table_kind(section: ReportSection, table) -> str | None:
    heading = _normalize(f"{section.title} {table.heading}")
    first_row = _normalize(" ".join(table.rows[0])) if table.rows else ""
    if "비용의성격별분류" in heading:
        return "nature"
    if "감가상각비가포함된항목" in heading or (
        "유형자산" in heading and "감가상각비" in first_row
    ):
        return "ppe_allocation"
    if "투자부동산" in heading and "감가상각" in _normalize(" ".join(cell for row in table.rows[:12] for cell in row)):
        return "investment_property_depreciation"
    if (
        "무형자산상각액이포함" in heading
        or "무형자산상각비의기능별배분" in heading
        or ("무형자산" in heading and "무형자산상각비" in first_row)
    ):
        return "intangible_allocation"
    return None


def _functional_expense_from_row(
    table_kind: str, section: ReportSection, table, row_idx: int, row: list[str]
) -> FunctionalExpenseInput | None:
    label = (
        _investment_property_depreciation_label(row)
        if table_kind == "investment_property_depreciation"
        else _row_label(row)
    )
    normalized = _normalize(label)
    if not normalized:
        return None

    if table_kind == "nature":
        if normalized == "감가상각비":
            account_key = "property_plant_equipment"
            expense_role = "depreciation"
        elif normalized == "무형자산상각비":
            account_key = "intangible_assets"
            expense_role = "amortization"
        elif normalized in {"사용권자산상각비", "사용권자산감가상각비"}:
            account_key = "right_of_use_assets"
            expense_role = "depreciation"
        else:
            return None
        classification = "nature_total"
    elif table_kind == "ppe_allocation":
        account_key = "property_plant_equipment"
        expense_role = "depreciation"
        classification = _expense_classification(label)
        if classification is None:
            return None
    elif table_kind == "intangible_allocation":
        account_key = "intangible_assets"
        expense_role = "amortization"
        classification = _expense_classification(label)
        if classification is None:
            return None
    elif table_kind == "investment_property_depreciation":
        if "감가상각" not in normalized:
            return None
        account_key = "investment_property"
        expense_role = "depreciation"
        classification = "nature_exclusion"
        label = "투자부동산 감가상각비"
    else:
        return None

    amount, col_idx = _row_amount(row, table.rows[0])
    if amount is None or col_idx is None:
        return None
    return FunctionalExpenseInput(
        account_key,
        expense_role,
        classification,
        label,
        amount * table.unit_multiplier,
        _source(section, table.index, row_idx, col_idx),
        table.unit_multiplier,
    )


def _investment_property_depreciation_label(row: list[str]) -> str:
    for cell in row:
        normalized = _normalize(cell)
        if "감가상각" in normalized:
            return cell
    return row[0] if row else ""


def _row_label(row: list[str]) -> str:
    for cell in reversed(row[:-1]):
        if cell.strip():
            return cell
    return row[0] if row else ""


def _expense_classification(label: str) -> str | None:
    normalized = _normalize(label)
    if normalized in {"기능별항목", "합계", "계"} or ("기능별항목" in normalized and "합계" in normalized):
        return "allocation_total"
    if "매출원가" in normalized or "제조원가" in normalized:
        return "cost_of_sales"
    if "판매비" in normalized or "관리비" in normalized:
        return "selling_admin"
    if "연구개발" in normalized:
        return "research_development"
    return "other_function" if normalized else None


def _classify_cfs_movement(label: str) -> tuple[str, str] | None:
    normalized = _normalize(label)
    if "처분손실" in normalized or "처분이익" in normalized or "처분손익" in normalized:
        return None
    if "상환손실" in normalized or "상환이익" in normalized or "발행비용" in normalized:
        return None
    if "차입금" in normalized and "중도상환수수료" in normalized:
        return None
    if "사채" in normalized and "발행분담금" in normalized and "반환" in normalized:
        return None
    if any(alias in normalized for alias in ("기타채무", "기타채권", "미지급", "미수")) and any(
        alias in normalized for alias in ("유형자산", "무형자산")
    ):
        return None
    if any(
        alias in normalized
        for alias in ("건설중인유형자산", "기타유형자산", "기타무형자산", "무형자산등")
    ):
        return None
    if "유형자산" in normalized and "취득" in normalized:
        return "property_plant_equipment", "acquisition"
    if "유형자산" in normalized and "처분" in normalized:
        return "property_plant_equipment", "disposal"
    if "무형자산" in normalized and "취득" in normalized:
        return "intangible_assets", "acquisition"
    if "무형자산" in normalized and "처분" in normalized:
        return "intangible_assets", "disposal"
    if "차입금" in normalized and "순증감" in normalized:
        return "borrowings", "net_change"
    if "차입금" in normalized and ("상환" in normalized or "감소" in normalized):
        return "borrowings", "repayment"
    if "차입금" in normalized and ("차입" in normalized or "증가" in normalized):
        return "borrowings", "proceeds"
    if "사채" in normalized and "발행비" in normalized and "지급" in normalized:
        return "bonds", "repayment"
    if "사채" in normalized and ("발행" in normalized or "차입" in normalized):
        return "bonds", "proceeds"
    if "사채" in normalized and ("상환" in normalized or "redemption" in normalized):
        return "bonds", "repayment"
    if "리스부채" in normalized and ("상환" in normalized or "감소" in normalized):
        return "lease_liabilities", "repayment"
    return None


def _cashflow_directional_amount(amount: int, movement_role: str) -> int:
    if movement_role in {"acquisition", "repayment"} and amount > 0:
        return -amount
    if movement_role in {"disposal", "proceeds"} and amount < 0:
        return abs(amount)
    return amount


def _classify_note_movement(account_key: str, label: str) -> str | None:
    normalized = _normalize(label)
    if account_key in {"property_plant_equipment", "intangible_assets", "investment_property"}:
        if "약정" in normalized:
            return None
        if "정부보조금" in normalized:
            return None
        if "취득원가" in normalized:
            return None
        if "사업결합" in normalized and "이외" not in normalized:
            return "business_combination"
        if any(alias in normalized for alias in ("처분금액", "처분대가", "매각금액")):
            return "disposal_proceeds"
        if "처분손실" in normalized:
            return "disposal_loss"
        if "처분이익" in normalized or "처분손익" in normalized:
            return "disposal_gain_loss"
        if "미수금" in normalized:
            return "noncash_receivable"
        if "미지급" in normalized:
            return "noncash_payable"
        if "취득" in normalized:
            return "acquisition"
        if "처분" in normalized and "손상" in normalized:
            return None
        if "처분" in normalized:
            return "disposal"
        if "대체" in normalized:
            return "rollforward_transfer_acquisition"
    if account_key == "borrowings":
        if "상환" in normalized:
            return "repayment"
        if "차입" in normalized:
            return "proceeds"
    if account_key == "bonds":
        if "발행" in normalized:
            return "proceeds"
        if "상환" in normalized or "redemption" in normalized:
            return "repayment"
    if account_key == "lease_liabilities" and "상환" in normalized:
        return "repayment"
    return None


def _balance_role(account_key: str, label: str) -> str | None:
    normalized = _normalize(label)
    if "기초" in normalized:
        return "beginning"
    if account_key == "trade_receivables":
        if any(alias in normalized for alias in ("손실충당금", "대손충당금", "충당금", "손상차손누계액")):
            return "ending"
        if normalized in {"합계", "장부금액합계"}:
            return "ending"
        if normalized in {
            "기타유동채권",
            "기타비유동채권",
            "유동계약자산외의유동미수수익",
            "미수금",
            "유동미수금",
            "비유동미수금",
            "미수수익",
            "유동미수수익",
            "비유동미수수익",
            "단기보증금",
            "장기보증금",
        }:
            return "ending"
        if (
            "매출채권" in normalized
            or normalized in {"외상매출금", "받을어음"}
        ) and not any(excluded in normalized for excluded in ("계약자산", "손실충당", "대손충당")):
            return "ending"
    ending_aliases = ("기말", "장부금액", "순장부금액", "장부가액")
    if any(alias in normalized for alias in ending_aliases):
        return "ending"
    return None


def _is_ending_balance_row(account_key: str, label: str, table, row_idx: int) -> bool:
    if _balance_role(account_key, label) == "ending":
        return True
    if _is_asset_total_balance_row(account_key, label, table):
        return True
    return account_key == "trade_receivables" and _row_has_acode_concept(
        table, row_idx, ("tradereceivables", "currenttradereceivables", "noncurrenttradereceivables")
    )


def _is_asset_total_balance_row(account_key: str, label: str, table) -> bool:
    if account_key not in {
        "property_plant_equipment",
        "intangible_assets",
        "investment_property",
    }:
        return False
    normalized_label = _normalize(label)
    if normalized_label not in {"합계", "총계"}:
        return False
    return bool(_asset_total_carrying_amount_columns(table.rows, account_key))


def _is_asset_ending_row_with_total_column(account_key: str, label: str, table) -> bool:
    if account_key != "property_plant_equipment":
        return False
    if _balance_role(account_key, label) != "ending":
        return False
    return bool(_asset_family_total_columns(table.rows, account_key))


def _is_intangible_ending_row_with_goodwill_columns(account_key: str, label: str, table) -> bool:
    if account_key != "intangible_assets":
        return False
    normalized_label = _normalize(label)
    if "영업권" not in normalized_label:
        return False
    if _balance_role(account_key, label) != "ending":
        return False
    return bool(_intangible_excluding_goodwill_carrying_columns(table.rows))


def _row_amount(row: list[str], headers: list[str]) -> tuple[int | None, int | None]:
    return row_amount_prefer_current(row, headers)


def _matches_any(value: str, aliases: tuple[str, ...]) -> bool:
    normalized = _normalize(value)
    return any(alias in normalized for alias in aliases)


def _source(section: ReportSection, table_index: int, row_idx: int, col_idx: int) -> str:
    return f"{section.section_id}/table:{table_index}/row:{row_idx}/col:{col_idx}"


def _table_source(section: ReportSection, table_index: int) -> str:
    return f"{section.section_id}/table:{table_index}"


def _row_has_acode_concept(table, row_idx: int, concepts: tuple[str, ...]) -> bool:
    if not table.row_acodes or row_idx >= len(table.row_acodes):
        return False
    normalized = set(concepts)
    for acode in table.row_acodes[row_idx]:
        concept = acode.split("|", 1)[0].lower().replace("ifrs-full_", "").replace("_", "")
        if concept in normalized:
            return True
    return False


def _normalize(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def _is_prior_period_table(heading: str) -> bool:
    normalized = _normalize(heading)
    if normalized.endswith("당기전기") and any(
        alias in normalized for alias in ("재무활동에서생기는부채", "재무활동관련부채")
    ):
        return True
    if any(alias in normalized for alias in ("당기및전기", "당기와전기", "당기말및전기말")):
        return False
    if any(alias in normalized for alias in ("2전기", "②전기")):
        return True
    prior_positions = [
        normalized.rfind(alias)
        for alias in ("전기중", "전기말", "전년도", "전기")
        if alias in normalized
    ]
    if not prior_positions:
        return False
    current_positions = [
        normalized.rfind(alias)
        for alias in ("당기중", "당기말", "당년도", "당기")
        if alias in normalized
    ]
    if not current_positions:
        return True
    if any(alias in normalized for alias in ("전기중", "전기말")):
        return max(prior_positions) > max(current_positions)
    return False
