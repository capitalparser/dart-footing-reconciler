"""Extract source-backed normalized verification candidates from note tables."""

from __future__ import annotations

from dataclasses import dataclass

from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.document import ReportTable
from dart_footing_reconciler.layout_variants import LayoutClassification
from dart_footing_reconciler.orientation import TableOrientation
from dart_footing_reconciler.table_semantics import compact, current_period_columns


@dataclass(frozen=True)
class VerificationCandidate:
    account_key: str
    role: str
    label: str
    raw_amount: int
    unit_multiplier: int
    amount: int
    note_no: str
    table_source: str
    row_index: int
    column_index: int
    layout_key: str
    orientation_key: str
    confidence: float
    evidence: tuple[str, ...]


def extract_verification_candidates(
    *,
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    if layout.key == "unknown_layout" or orientation.key == "unknown":
        return []
    if layout.confidence < 0.7 or orientation.confidence < 0.7:
        return []
    if not table.rows:
        return []

    if layout.key == "defined_benefit_rollforward":
        return _defined_benefit_rollforward_candidates(note_no, title, table, layout, orientation)

    if layout.key == "financial_fair_value_level_summary":
        return _financial_fair_value_level_summary_candidates(
            note_no,
            title,
            table,
            layout,
            orientation,
        )

    if layout.key == "tax_expense_composition_summary":
        return _tax_expense_composition_summary_candidates(
            note_no,
            title,
            table,
            layout,
            orientation,
        )

    if layout.key == "inventory_allowance_rollforward":
        return _inventory_allowance_rollforward_candidates(note_no, title, table, layout, orientation)

    if layout.key == "provision_current_noncurrent_summary":
        return _provision_current_noncurrent_summary_candidates(
            note_no,
            title,
            table,
            layout,
            orientation,
        )

    if layout.key == "provision_rollforward":
        return _provision_rollforward_candidates(note_no, title, table, layout, orientation)

    if layout.key == "lease_liability_current_noncurrent_summary":
        return _lease_liability_current_noncurrent_summary_candidates(
            note_no,
            title,
            table,
            layout,
            orientation,
        )

    if orientation.key == "row_oriented":
        return _row_oriented_candidates(note_no, title, table, layout, orientation)
    if orientation.key == "period_oriented":
        return _period_oriented_candidates(note_no, title, table, layout, orientation)
    if orientation.key == "column_oriented":
        return _column_oriented_candidates(note_no, title, table, layout, orientation)
    if orientation.key == "mixed":
        return _mixed_candidates(note_no, title, table, layout, orientation)
    return []


def _row_oriented_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    if len(table.rows) < 2:
        return []
    if layout.key == "receivable_loss_allowance_aging_summary":
        return _receivable_loss_allowance_aging_candidates(
            note_no,
            title,
            table,
            layout,
            orientation,
        )
    if layout.key == "asset_period_rollforward_summary":
        return _asset_period_rollforward_summary_candidates(
            note_no,
            title,
            table,
            layout,
            orientation,
        )
    if layout.key == "asset_two_label_row_rollforward_summary":
        return _asset_two_label_row_rollforward_summary_candidates(
            note_no,
            title,
            table,
            layout,
            orientation,
        )
    if layout.key == "loss_allowance_rollforward":
        return _loss_allowance_rollforward_candidates(note_no, title, table, layout, orientation)
    if layout.key == "financial_instrument_fair_value_summary":
        return _financial_fair_value_summary_candidates(note_no, title, table, layout, orientation)
    if layout.key == "employee_benefit_maturity_summary":
        return _employee_benefit_maturity_summary_candidates(
            note_no,
            title,
            table,
            layout,
            orientation,
        )
    if layout.key == "debt_instrument_detail_summary":
        return _debt_instrument_detail_candidates(note_no, title, table, layout, orientation)
    if layout.key == "earnings_per_share_summary":
        return _earnings_per_share_candidates(note_no, title, table, layout, orientation)
    col_idx = _preferred_total_column(table.rows[0])
    if col_idx is None:
        return []
    candidates: list[VerificationCandidate] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if col_idx >= len(row) or not row:
            continue
        role = _candidate_role(row[0])
        if role is None:
            continue
        raw_amount = parse_amount(row[col_idx])
        if raw_amount is None:
            continue
        candidates.append(
            _candidate(
                note_no,
                title,
                table,
                layout,
                orientation,
                role,
                row[0],
                raw_amount,
                row_idx,
                col_idx,
            )
        )
    return candidates


def _loss_allowance_rollforward_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    account_columns = _loss_allowance_account_columns(table.rows)
    if not account_columns:
        return []
    candidates: list[VerificationCandidate] = []
    for row_idx, row in enumerate(table.rows):
        if not row:
            continue
        role = _loss_allowance_role(row[0])
        if role is None:
            continue
        for col_idx, account_key in account_columns:
            if col_idx >= len(row):
                continue
            raw_amount = parse_amount(row[col_idx])
            if raw_amount is None:
                continue
            candidates.append(
                _candidate(
                    note_no,
                    title,
                    table,
                    layout,
                    orientation,
                    role,
                    row[0],
                    raw_amount,
                    row_idx,
                    col_idx,
                    account_key=account_key,
                )
            )
    return candidates


def _debt_instrument_detail_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    component_candidates = _debt_component_column_candidates(
        note_no,
        title,
        table,
        layout,
        orientation,
    )
    if component_candidates:
        return component_candidates
    col_idx = _preferred_debt_total_column(table.rows)
    if col_idx is None:
        return []
    candidates: list[VerificationCandidate] = []
    account_key = _debt_account_key(title, table.rows)
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if not row or col_idx >= len(row):
            continue
        role = _debt_detail_role(row[0])
        if role is None:
            continue
        raw_amount = parse_amount(row[col_idx])
        if raw_amount is None:
            continue
        candidates.append(
            _candidate(
                note_no,
                title,
                table,
                layout,
                orientation,
                role,
                row[0],
                raw_amount,
                row_idx,
                col_idx,
                account_key=account_key,
            )
        )
    return candidates


def _debt_component_column_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    if len(table.rows) < 2:
        return []
    role_columns = [
        (idx, role)
        for idx, header in enumerate(table.rows[0])
        if (role := _debt_component_header_role(header)) is not None
    ]
    if len(role_columns) < 3:
        return []
    total_row = _debt_component_total_row(table.rows[1:])
    if total_row is None:
        return []
    row_idx, row = total_row
    account_key = _debt_account_key(title, table.rows)
    candidates: list[VerificationCandidate] = []
    for col_idx, role in role_columns:
        if col_idx >= len(row):
            continue
        raw_amount = parse_amount(row[col_idx])
        if raw_amount is None:
            continue
        candidates.append(
            _candidate(
                note_no,
                title,
                table,
                layout,
                orientation,
                role,
                table.rows[0][col_idx],
                raw_amount,
                row_idx,
                col_idx,
                account_key=account_key,
            )
        )
    return candidates


def _debt_component_total_row(rows: list[list[str]]) -> tuple[int, list[str]] | None:
    for offset, row in enumerate(rows, start=1):
        if any("합계" in compact(cell) for cell in row[:3]):
            return offset, row
    return None


def _earnings_per_share_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    if len(table.rows) < 2:
        return []
    col_idx = _preferred_eps_amount_column(table.rows[0])
    if col_idx is None:
        return []
    candidates: list[VerificationCandidate] = []
    current_account_key: str | None = None
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if not row or col_idx >= len(row):
            continue
        role = _eps_role(row[0])
        if role is None:
            continue
        if role == "eps_profit":
            current_account_key = _eps_account_key(row[0])
        if current_account_key is None:
            continue
        raw_amount = parse_amount(row[col_idx])
        if raw_amount is None:
            continue
        unit_multiplier = table.unit_multiplier if role == "eps_profit" else 1
        candidates.append(
            _candidate(
                note_no,
                title,
                table,
                layout,
                orientation,
                role,
                row[0],
                raw_amount,
                row_idx,
                col_idx,
                account_key=current_account_key,
                unit_multiplier=unit_multiplier,
            )
        )
    return candidates


def _dividend_payout_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    period_columns = _dividend_period_columns(table.rows)
    if not period_columns:
        return []
    candidates: list[VerificationCandidate] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if not row:
            continue
        role = _dividend_payout_role(row[0])
        if role is None:
            continue
        for col_idx, period in period_columns:
            if col_idx >= len(row):
                continue
            raw_amount = parse_amount(row[col_idx])
            if raw_amount is None:
                continue
            candidates.append(
                _candidate(
                    note_no,
                    title,
                    table,
                    layout,
                    orientation,
                    role,
                    f"{row[0]} {period}".strip(),
                    raw_amount,
                    row_idx,
                    col_idx,
                    account_key=f"dividend_payout:{period}",
                    unit_multiplier=1,
                )
            )
    return candidates


def _period_oriented_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    if len(table.rows) < 2:
        return []
    if layout.key == "employee_benefit_expense_allocation":
        return _employee_benefit_expense_allocation_candidates(
            note_no,
            title,
            table,
            layout,
            orientation,
        )
    if layout.key == "dividend_payout_summary":
        return _dividend_payout_candidates(note_no, title, table, layout, orientation)
    current_columns = current_period_columns(table.rows[0])
    if not current_columns:
        return []
    col_idx = current_columns[0]
    candidates: list[VerificationCandidate] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if col_idx >= len(row) or not row:
            continue
        role = _candidate_role(row[0])
        if role is None:
            continue
        raw_amount = parse_amount(row[col_idx])
        if raw_amount is None:
            continue
        candidates.append(
            _candidate(
                note_no,
                title,
                table,
                layout,
                orientation,
                role,
                row[0],
                raw_amount,
                row_idx,
                col_idx,
            )
        )
    return candidates


def _column_oriented_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    if len(table.rows) < 2:
        return []
    if layout.key == "financial_instrument_category_summary":
        return _financial_category_summary_candidates(note_no, title, table, layout, orientation)
    if layout.key == "receivable_carrying_amount_summary":
        return _receivable_carrying_amount_candidates(note_no, title, table, layout, orientation)
    if layout.key == "receivable_present_value_carrying_summary":
        return _receivable_present_value_carrying_candidates(
            note_no,
            title,
            table,
            layout,
            orientation,
        )
    if layout.key == "receivable_aging_status_summary":
        return _receivable_aging_summary_candidates(note_no, title, table, layout, orientation)
    if layout.key == "functional_expense_allocation":
        return _functional_expense_allocation_candidates(note_no, title, table, layout, orientation)
    if layout.key == "functional_expense_research_allocation":
        return _functional_expense_research_allocation_candidates(
            note_no,
            title,
            table,
            layout,
            orientation,
        )
    if layout.key == "employee_benefit_expense_allocation":
        return _employee_benefit_expense_allocation_candidates(
            note_no,
            title,
            table,
            layout,
            orientation,
        )
    if layout.key == "functional_expense_single_row_allocation":
        return _functional_expense_single_row_allocation_candidates(
            note_no,
            title,
            table,
            layout,
            orientation,
        )
    if layout.key == "selling_admin_expense_summary":
        return _expense_amount_summary_candidates(
            note_no,
            title,
            table,
            layout,
            orientation,
            account_key="selling_general_admin",
        )
    if layout.key == "operating_expense_summary":
        return _expense_amount_summary_candidates(
            note_no,
            title,
            table,
            layout,
            orientation,
            account_key="operating_expenses",
        )
    if layout.key == "credit_risk_exposure_summary":
        return _credit_risk_exposure_summary_candidates(note_no, title, table, layout, orientation)
    if layout.key == "liquidity_maturity_analysis":
        return _liquidity_maturity_analysis_candidates(note_no, title, table, layout, orientation)
    if layout.key == "lease_liability_maturity_summary":
        return _lease_liability_maturity_summary_candidates(
            note_no,
            title,
            table,
            layout,
            orientation,
        )
    if layout.key == "lease_expense_summary":
        return _lease_expense_summary_candidates(note_no, title, table, layout, orientation)
    if layout.key == "discontinued_operation_income_statement":
        return _discontinued_operation_income_candidates(note_no, title, table, layout, orientation)
    if layout.key == "discontinued_operation_cashflow_summary":
        return _discontinued_operation_cashflow_candidates(note_no, title, table, layout, orientation)
    if layout.key == "asset_cost_accumulated_summary":
        return _asset_cost_accumulated_summary_candidates(note_no, title, table, layout, orientation)
    if layout.key == "asset_component_column_summary":
        return _asset_component_column_summary_candidates(note_no, title, table, layout, orientation)
    if layout.key == "inventory_carrying_amount_summary":
        return _inventory_carrying_amount_summary_candidates(
            note_no,
            title,
            table,
            layout,
            orientation,
        )
    col_idx = _preferred_total_column(table.rows[0])
    if col_idx is None:
        return []
    candidates: list[VerificationCandidate] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if not row or col_idx >= len(row):
            continue
        normalized_label = row[0].replace(" ", "")
        if (
            normalized_label not in {"합계", "총계"}
            and not _is_inventory_carrying_amount_summary_row(normalized_label, layout.key)
            and not _is_asset_measure_summary_row(
                normalized_label,
                layout.key,
            )
        ):
            continue
        raw_amount = parse_amount(row[col_idx])
        if raw_amount is None:
            continue
        candidates.append(
            _candidate(
                note_no,
                title,
                table,
                layout,
                orientation,
                "ending",
                row[0],
                raw_amount,
                row_idx,
                col_idx,
            )
        )
    return candidates


def _financial_category_summary_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    col_idx = _preferred_financial_total_column(table.rows[0])
    if col_idx is None:
        return _financial_category_column_total_candidates(note_no, title, table, layout, orientation)
    component_columns = _financial_category_component_columns(table.rows[0], col_idx)
    candidates: list[VerificationCandidate] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if not row or col_idx >= len(row):
            continue
        row_label = _financial_category_row_label(row)
        account_key = _financial_account_key(row_label)
        if account_key is None:
            continue
        for component_col_idx in component_columns:
            if component_col_idx >= len(row):
                continue
            raw_component = parse_amount(row[component_col_idx])
            if raw_component is None:
                continue
            if raw_component == 0:
                continue
            label = f"{row_label} {table.rows[0][component_col_idx]}".strip()
            candidates.append(
                _candidate(
                    note_no,
                    title,
                    table,
                    layout,
                    orientation,
                    "financial_category_component",
                    label,
                    raw_component,
                    row_idx,
                    component_col_idx,
                    account_key=account_key,
                )
            )
        raw_amount = parse_amount(row[col_idx])
        if raw_amount is None:
            continue
        candidates.append(
            _candidate(
                note_no,
                title,
                table,
                layout,
                orientation,
                "ending",
                row_label,
                raw_amount,
                row_idx,
                col_idx,
                account_key=account_key,
            )
        )
    return candidates


def _financial_category_column_total_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    if len(table.rows) < 3:
        return []
    component_columns = [
        idx
        for idx, header in enumerate(table.rows[0])
        if _is_financial_category_component_header(compact(header))
    ]
    if not component_columns:
        return []
    total_row_idx = _financial_category_total_row_index(table.rows)
    if total_row_idx is None:
        return []
    total_row = table.rows[total_row_idx]
    candidates: list[VerificationCandidate] = []
    for col_idx in component_columns:
        if col_idx >= len(total_row):
            continue
        raw_total = parse_amount(total_row[col_idx])
        if raw_total is None:
            continue
        account_key = f"financial_category:{compact(table.rows[0][col_idx])}"
        for row_idx, row in enumerate(table.rows[1:total_row_idx], start=1):
            if col_idx >= len(row):
                continue
            row_label = _financial_category_row_label(row)
            if _financial_account_key(row_label) is None:
                continue
            raw_component = parse_amount(row[col_idx])
            if raw_component is None or raw_component == 0:
                continue
            candidates.append(
                _candidate(
                    note_no,
                    title,
                    table,
                    layout,
                    orientation,
                    "financial_category_column_component",
                    f"{row_label} {table.rows[0][col_idx]}".strip(),
                    raw_component,
                    row_idx,
                    col_idx,
                    account_key=account_key,
                )
            )
        candidates.append(
            _candidate(
                note_no,
                title,
                table,
                layout,
                orientation,
                "financial_category_column_total",
                f"{total_row[0]} {table.rows[0][col_idx]}".strip(),
                raw_total,
                total_row_idx,
                col_idx,
                account_key=account_key,
            )
        )
    return candidates


def _financial_fair_value_summary_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    col_idx = _financial_fair_value_amount_column(table.rows[0])
    if col_idx is None:
        return []
    candidates: list[VerificationCandidate] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if not row or col_idx >= len(row):
            continue
        role = _financial_fair_value_role(row[0])
        account_key = _financial_account_key(row[0])
        if role is None or account_key is None:
            continue
        raw_amount = parse_amount(row[col_idx])
        if raw_amount is None:
            continue
        candidates.append(
            _candidate(
                note_no,
                title,
                table,
                layout,
                orientation,
                role,
                row[0],
                raw_amount,
                row_idx,
                col_idx,
                account_key=account_key,
            )
        )
    return candidates


def _financial_fair_value_level_summary_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    if len(table.rows) < 2:
        return []
    headers = table.rows[0]
    total_col = _fair_value_level_total_column(headers)
    level_cols = _fair_value_level_component_columns(headers, total_col)
    if total_col is None or not level_cols:
        return []
    candidates: list[VerificationCandidate] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if total_col >= len(row):
            continue
        account_label = _financial_fair_value_level_row_label(row)
        account_key = _financial_fair_value_level_account_key(row)
        if account_label is None or account_key is None:
            continue
        row_candidates: list[VerificationCandidate] = []
        for col_idx in level_cols:
            if col_idx >= len(row):
                continue
            raw_amount = parse_amount(row[col_idx])
            if raw_amount is None:
                continue
            row_candidates.append(
                _candidate(
                    note_no,
                    title,
                    table,
                    layout,
                    orientation,
                    "fair_value_level_component",
                    f"{account_label} {headers[col_idx]}".strip(),
                    raw_amount,
                    row_idx,
                    col_idx,
                    account_key=account_key,
                )
            )
        raw_total = parse_amount(row[total_col])
        if raw_total is None:
            continue
        row_candidates.append(
            _candidate(
                note_no,
                title,
                table,
                layout,
                orientation,
                "fair_value_total",
                f"{account_label} {headers[total_col]}".strip(),
                raw_total,
                row_idx,
                total_col,
                account_key=account_key,
            )
        )
        if any(candidate.role == "fair_value_level_component" for candidate in row_candidates):
            candidates.extend(row_candidates)
    return candidates


def _tax_expense_composition_summary_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    if len(table.rows) < 2:
        return []
    headers = table.rows[0]
    period_cols = _tax_expense_period_columns(headers)
    if not period_cols:
        return []
    candidates: list[VerificationCandidate] = []
    for col_idx in period_cols:
        col_candidates: list[VerificationCandidate] = []
        for row_idx, row in enumerate(table.rows[1:], start=1):
            if col_idx >= len(row) or not row:
                continue
            role = _tax_expense_role(row[0])
            if role is None:
                continue
            raw_amount = parse_amount(row[col_idx])
            if raw_amount is None:
                continue
            col_candidates.append(
                _candidate(
                    note_no,
                    title,
                    table,
                    layout,
                    orientation,
                    role,
                    f"{row[0]} {headers[col_idx]}".strip(),
                    raw_amount,
                    row_idx,
                    col_idx,
                    account_key="income_tax_expense",
                )
            )
            if role == "tax_expense_total":
                break
        if (
            sum(1 for candidate in col_candidates if candidate.role == "tax_expense_component") >= 2
            and any(candidate.role == "tax_expense_total" for candidate in col_candidates)
        ):
            candidates.extend(col_candidates)
    return candidates


def _receivable_carrying_amount_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    col_idx = _preferred_total_column(table.rows[0])
    if col_idx is None:
        return []
    component_columns = _receivable_carrying_component_columns(table.rows[0], col_idx)
    candidates: list[VerificationCandidate] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if not row or col_idx >= len(row):
            continue
        row_label = _receivable_row_label(row)
        account_key = _receivable_account_key_for_row(row)
        if account_key is None:
            continue
        for component_col_idx in component_columns:
            if component_col_idx >= len(row):
                continue
            raw_component = parse_amount(row[component_col_idx])
            if raw_component is None:
                continue
            if raw_component == 0 and component_col_idx != component_columns[0]:
                continue
            label = f"{row_label} {table.rows[0][component_col_idx]}".strip()
            candidates.append(
                _candidate(
                    note_no,
                    title,
                    table,
                    layout,
                    orientation,
                    "receivable_carrying_component",
                    label,
                    raw_component,
                    row_idx,
                    component_col_idx,
                    account_key=account_key,
                )
            )
        raw_amount = parse_amount(row[col_idx])
        if raw_amount is None:
            continue
        candidates.append(
            _candidate(
                note_no,
                title,
                table,
                layout,
                orientation,
                "ending",
                row_label,
                raw_amount,
                row_idx,
                col_idx,
                account_key=account_key,
            )
        )
    return candidates


def _receivable_present_value_carrying_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    if len(table.rows) < 2:
        return []
    total_col_idx = _preferred_total_column(table.rows[0])
    if total_col_idx is None:
        return []
    component_columns = _receivable_carrying_component_columns(table.rows[0], total_col_idx)
    if not component_columns:
        return []
    candidates: list[VerificationCandidate] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if not row or total_col_idx >= len(row):
            continue
        row_label = _receivable_row_label(row)
        account_key = _receivable_account_key(row_label)
        if account_key is None:
            continue
        for component_col_idx in component_columns:
            if component_col_idx >= len(row):
                continue
            raw_component = parse_amount(row[component_col_idx])
            if raw_component is None:
                continue
            if raw_component == 0 and component_col_idx != component_columns[0]:
                continue
            label = f"{row_label} {table.rows[0][component_col_idx]}".strip()
            candidates.append(
                _candidate(
                    note_no,
                    title,
                    table,
                    layout,
                    orientation,
                    "receivable_carrying_component",
                    label,
                    raw_component,
                    row_idx,
                    component_col_idx,
                    account_key=account_key,
                )
            )
        raw_amount = parse_amount(row[total_col_idx])
        if raw_amount is None:
            continue
        candidates.append(
            _candidate(
                note_no,
                title,
                table,
                layout,
                orientation,
                "ending",
                row_label,
                raw_amount,
                row_idx,
                total_col_idx,
                account_key=account_key,
            )
        )
    return candidates


def _receivable_row_label(row: list[str]) -> str:
    if len(row) >= 2:
        primary = compact(row[0])
        secondary = compact(row[1])
        if (
            primary
            and secondary
            and primary != secondary
            and secondary not in {"소계", "합계", "총계"}
            and _receivable_account_key(row[1]) is not None
        ):
            return row[1]
    return row[0]


def _receivable_account_key_for_row(row: list[str]) -> str | None:
    row_label = _receivable_row_label(row)
    account_key = _receivable_account_key(row_label)
    if account_key is not None:
        return account_key
    if len(row) < 2:
        return None
    context = compact(row[0])
    label = compact(row[1])
    is_current = "유동" in context and "비유동" not in context
    is_noncurrent = "비유동" in context or "장기" in context
    if "미수금" in label:
        if is_current:
            return "short_term_other_receivables"
        if is_noncurrent:
            return "long_term_other_receivables"
    if "대여금" in label:
        if is_current:
            return "short_term_loans"
        if is_noncurrent:
            return "long_term_loans"
    if "보증금" in label:
        if is_current:
            return "short_term_deposits"
        if is_noncurrent:
            return "long_term_deposits"
    return None


def _receivable_aging_summary_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    if len(table.rows) < 2:
        return []
    total_row = _aging_status_total_row(table.rows[1:])
    if total_row is None:
        return []
    row_idx, row = total_row
    candidates: list[VerificationCandidate] = []
    for col_idx, header in enumerate(table.rows[0]):
        if col_idx >= len(row):
            continue
        account_key = _receivable_account_key(header)
        if account_key is None:
            continue
        raw_amount = parse_amount(row[col_idx])
        if raw_amount is None:
            continue
        candidates.append(
            _candidate(
                note_no,
                title,
                table,
                layout,
                orientation,
                "ending",
                header,
                raw_amount,
                row_idx,
                col_idx,
                account_key=account_key,
            )
        )
    return candidates


def _receivable_loss_allowance_aging_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    if len(table.rows) < 2:
        return []
    columns = _receivable_aging_bucket_columns(table.rows[0])
    if not columns:
        return []
    candidates: list[VerificationCandidate] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if not row:
            continue
        account_key = _receivable_aging_account_key(row[0])
        if account_key is None:
            continue
        for col_idx, role in columns:
            if col_idx >= len(row):
                continue
            raw_amount = parse_amount(row[col_idx])
            if raw_amount is None:
                continue
            candidates.append(
                _candidate(
                    note_no,
                    title,
                    table,
                    layout,
                    orientation,
                    role,
                    f"{row[0]} {table.rows[0][col_idx]}".strip(),
                    raw_amount,
                    row_idx,
                    col_idx,
                    account_key=account_key,
                )
            )
    return candidates


def _asset_period_rollforward_summary_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    if len(table.rows) < 2:
        return []
    candidates: list[VerificationCandidate] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if not row:
            continue
        period = compact(row[0])
        if period not in {"당기", "전기"}:
            continue
        account_key = f"asset_period_rollforward:{period}"
        for col_idx, header in enumerate(table.rows[0]):
            if col_idx >= len(row):
                continue
            role = _asset_period_rollforward_role(header)
            if role is None:
                continue
            raw_amount = parse_amount(row[col_idx])
            if raw_amount is None:
                continue
            candidates.append(
                _candidate(
                    note_no,
                    title,
                    table,
                    layout,
                    orientation,
                    role,
                    f"{row[0]} {header}".strip(),
                    raw_amount,
                    row_idx,
                    col_idx,
                    account_key=account_key,
                )
            )
    return candidates


def _asset_two_label_row_rollforward_summary_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    if len(table.rows) < 2:
        return []
    amount_col = _asset_two_label_amount_column(table.rows[0])
    if amount_col is None:
        return []
    account_key = _account_key(title)
    candidates: list[VerificationCandidate] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if len(row) <= max(1, amount_col):
            continue
        role = _asset_two_label_row_rollforward_role(row[1])
        if role is None:
            continue
        raw_amount = parse_amount(row[amount_col])
        if raw_amount is None:
            continue
        candidates.append(
            _candidate(
                note_no,
                title,
                table,
                layout,
                orientation,
                role,
                row[1],
                raw_amount,
                row_idx,
                amount_col,
                account_key=account_key,
            )
        )
    return candidates


def _functional_expense_allocation_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    col_idx = _preferred_functional_expense_total_column(table.rows[0])
    if col_idx is None:
        return []
    candidates: list[VerificationCandidate] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if not row or col_idx >= len(row) or not _is_depreciation_expense_label(row[0]):
            continue
        raw_amount = parse_amount(row[col_idx])
        if raw_amount is None:
            continue
        candidates.append(
            _candidate(
                note_no,
                title,
                table,
                layout,
                orientation,
                "expense_allocation_total",
                row[0],
                raw_amount,
                row_idx,
                col_idx,
            )
        )
    return candidates


def _functional_expense_research_allocation_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    candidates: list[VerificationCandidate] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if not row or not _is_research_development_expense_label(row[0]):
            continue
        for col_idx, header in enumerate(table.rows[0]):
            if col_idx >= len(row):
                continue
            role = _functional_expense_formula_role(header)
            if role is None:
                continue
            raw_amount = parse_amount(row[col_idx])
            if raw_amount is None:
                continue
            candidates.append(
                _candidate(
                    note_no,
                    title,
                    table,
                    layout,
                    orientation,
                    role,
                    header,
                    raw_amount,
                    row_idx,
                    col_idx,
                    account_key="research_development_expense",
                )
            )
    return candidates


def _employee_benefit_expense_allocation_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    if not table.rows:
        return []
    columns = [
        (idx, compact(header))
        for idx, header in enumerate(table.rows[0])
        if compact(header) in {"당기", "전기", "당기말", "전기말"}
    ]
    if not columns:
        return []
    candidates: list[VerificationCandidate] = []
    for col_idx, period in columns:
        account_key = f"employee_benefit_expense:{period}"
        for row_idx, row in enumerate(table.rows[1:], start=1):
            if not row or col_idx >= len(row):
                continue
            row_label = row[0]
            role = _employee_benefit_expense_role(row_label)
            if role is None:
                continue
            raw_amount = parse_amount(row[col_idx])
            if raw_amount is None:
                continue
            candidates.append(
                _candidate(
                    note_no,
                    title,
                    table,
                    layout,
                    orientation,
                    role,
                    f"{row_label} {period}",
                    raw_amount,
                    row_idx,
                    col_idx,
                    account_key=account_key,
                )
            )
    return candidates


def _functional_expense_single_row_allocation_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    if len(table.rows) < 2:
        return []
    col_idx = _single_row_functional_expense_amount_column(table.rows[0])
    if col_idx is None:
        return []
    candidates: list[VerificationCandidate] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if not row or col_idx >= len(row) or "기능별항목" not in compact(row[0]):
            continue
        raw_amount = parse_amount(row[col_idx])
        if raw_amount is None:
            continue
        function_label = row[1] if len(row) > 1 else row[0]
        candidates.append(
            _candidate(
                note_no,
                title,
                table,
                layout,
                orientation,
                "expense_allocation_total",
                f"{function_label} {table.rows[0][col_idx]}".strip(),
                raw_amount,
                row_idx,
                col_idx,
            )
        )
    return candidates


def _expense_amount_summary_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
    *,
    account_key: str,
) -> list[VerificationCandidate]:
    col_idx = _preferred_expense_amount_column(table.rows[0])
    if col_idx is None:
        return []
    candidates: list[VerificationCandidate] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if not row or col_idx >= len(row):
            continue
        role = _expense_summary_role(row[0])
        if role is None:
            continue
        raw_amount = parse_amount(row[col_idx])
        if raw_amount is None:
            continue
        candidates.append(
            _candidate(
                note_no,
                title,
                table,
                layout,
                orientation,
                role,
                row[0],
                raw_amount,
                row_idx,
                col_idx,
                account_key=account_key,
            )
        )
    return candidates


def _credit_risk_exposure_summary_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    row_candidates = _credit_risk_exposure_row_summary_candidates(
        note_no,
        title,
        table,
        layout,
        orientation,
    )
    if row_candidates:
        return row_candidates
    col_idx = _preferred_credit_risk_amount_column(table.rows[0])
    if col_idx is None:
        return []
    candidates: list[VerificationCandidate] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if not row or col_idx >= len(row):
            continue
        role = _credit_risk_exposure_role(row[0])
        if role is None:
            continue
        raw_amount = parse_amount(row[col_idx])
        if raw_amount is None:
            continue
        account_key = (
            "credit_risk_exposure"
            if role == "credit_exposure_total"
            else _credit_risk_asset_account_key(row[0])
        )
        if account_key is None:
            continue
        candidates.append(
            _candidate(
                note_no,
                title,
                table,
                layout,
                orientation,
                role,
                row[0],
                raw_amount,
                row_idx,
                col_idx,
                account_key=account_key,
            )
        )
    return candidates


def _credit_risk_exposure_row_summary_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    if len(table.rows) < 2:
        return []
    headers = table.rows[0]
    total_col = _credit_risk_exposure_total_column(headers)
    if total_col is None or total_col < 2:
        return []
    candidates: list[VerificationCandidate] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        row_label = compact(" ".join(row[:2])) if row else ""
        if "신용위험에대한최대노출정도" not in row_label:
            continue
        row_candidates: list[VerificationCandidate] = []
        for col_idx in range(1, total_col):
            if col_idx >= len(row):
                continue
            raw_amount = parse_amount(row[col_idx])
            if raw_amount is None:
                continue
            header_label = headers[col_idx]
            row_candidates.append(
                _candidate(
                    note_no,
                    title,
                    table,
                    layout,
                    orientation,
                    "credit_exposure_component",
                    header_label,
                    raw_amount,
                    row_idx,
                    col_idx,
                    account_key=_credit_risk_asset_account_key(header_label)
                    or "credit_risk_exposure_component",
                )
            )
        if total_col >= len(row):
            continue
        raw_total = parse_amount(row[total_col])
        if raw_total is None:
            continue
        row_candidates.append(
            _candidate(
                note_no,
                title,
                table,
                layout,
                orientation,
                "credit_exposure_total",
                headers[total_col],
                raw_total,
                row_idx,
                total_col,
                account_key="credit_risk_exposure",
            )
        )
        if sum(1 for candidate in row_candidates if candidate.role == "credit_exposure_component") >= 2:
            candidates.extend(row_candidates)
    return candidates


def _inventory_carrying_amount_summary_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    if len(table.rows) < 2:
        return []
    total_col_idx = _preferred_total_column(table.rows[0])
    if total_col_idx is None:
        return []
    component_columns = _inventory_carrying_component_columns(table.rows[0], total_col_idx)
    if not component_columns:
        return _inventory_carrying_amount_total_candidates(
            note_no,
            title,
            table,
            layout,
            orientation,
            total_col_idx,
        )
    candidates: list[VerificationCandidate] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if not row or total_col_idx >= len(row):
            continue
        row_label = _inventory_row_label(row)
        account_key = _inventory_account_key(row_label)
        if account_key is None:
            continue
        for component_col_idx in component_columns:
            if component_col_idx >= len(row):
                continue
            raw_component = parse_amount(row[component_col_idx])
            if raw_component is None:
                continue
            if raw_component == 0 and component_col_idx != component_columns[0]:
                continue
            label = f"{row_label} {table.rows[0][component_col_idx]}".strip()
            candidates.append(
                _candidate(
                    note_no,
                    title,
                    table,
                    layout,
                    orientation,
                    "inventory_carrying_component",
                    label,
                    raw_component,
                    row_idx,
                    component_col_idx,
                    account_key=account_key,
                )
            )
        raw_amount = parse_amount(row[total_col_idx])
        if raw_amount is None:
            continue
        candidates.append(
            _candidate(
                note_no,
                title,
                table,
                layout,
                orientation,
                "ending",
                row_label,
                raw_amount,
                row_idx,
                total_col_idx,
                account_key=account_key,
            )
        )
    return candidates


def _inventory_carrying_amount_total_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
    total_col_idx: int,
) -> list[VerificationCandidate]:
    candidates: list[VerificationCandidate] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if not row or total_col_idx >= len(row):
            continue
        if _inventory_account_key(row[0]) != "inventories":
            continue
        raw_amount = parse_amount(row[total_col_idx])
        if raw_amount is None:
            continue
        candidates.append(
            _candidate(
                note_no,
                title,
                table,
                layout,
                orientation,
                "ending",
                row[0],
                raw_amount,
                row_idx,
                total_col_idx,
                account_key="inventories",
            )
        )
    return candidates


def _liquidity_maturity_analysis_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    columns = _maturity_analysis_columns(table.rows[0])
    if not columns:
        return []
    candidates: list[VerificationCandidate] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if not row:
            continue
        account_key = _maturity_liability_account_key(row[0])
        if account_key is None:
            continue
        for col_idx, role in columns:
            if col_idx >= len(row):
                continue
            raw_amount = parse_amount(row[col_idx])
            if raw_amount is None:
                continue
            label = f"{row[0]} {table.rows[0][col_idx]}".strip()
            candidates.append(
                _candidate(
                    note_no,
                    title,
                    table,
                    layout,
                    orientation,
                    role,
                    label,
                    raw_amount,
                    row_idx,
                    col_idx,
                    account_key=account_key,
            )
        )
    return candidates


def _employee_benefit_maturity_summary_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    columns = _maturity_analysis_columns(table.rows[0])
    if not columns:
        return []
    candidates: list[VerificationCandidate] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if not row:
            continue
        account_key = _employee_benefit_maturity_account_key(row[0])
        if account_key is None:
            continue
        row_candidates: list[VerificationCandidate] = []
        for col_idx, role in columns:
            if col_idx >= len(row):
                continue
            raw_amount = parse_amount(row[col_idx])
            if raw_amount is None:
                continue
            label = f"{row[0]} {table.rows[0][col_idx]}".strip()
            row_candidates.append(
                _candidate(
                    note_no,
                    title,
                    table,
                    layout,
                    orientation,
                    role,
                    label,
                    raw_amount,
                    row_idx,
                    col_idx,
                    account_key=account_key,
                )
            )
        component_count = sum(
            1 for candidate in row_candidates if candidate.role == "maturity_component"
        )
        if component_count >= 2:
            candidates.extend(row_candidates)
    return candidates


def _lease_liability_maturity_summary_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    columns = _maturity_analysis_columns(table.rows[0])
    if not columns:
        return []
    candidates: list[VerificationCandidate] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if not row:
            continue
        account_key = _lease_liability_maturity_account_key(row[0])
        if account_key is None:
            continue
        row_candidates: list[VerificationCandidate] = []
        for col_idx, role in columns:
            if col_idx >= len(row):
                continue
            raw_amount = parse_amount(row[col_idx])
            if raw_amount is None:
                continue
            label = f"{row[0]} {table.rows[0][col_idx]}".strip()
            row_candidates.append(
                _candidate(
                    note_no,
                    title,
                    table,
                    layout,
                    orientation,
                    role,
                    label,
                    raw_amount,
                    row_idx,
                    col_idx,
                    account_key=account_key,
                )
            )
        component_count = sum(
            1 for candidate in row_candidates if candidate.role == "maturity_component"
        )
        if component_count >= 2:
            candidates.extend(row_candidates)
    return candidates


def _lease_liability_current_noncurrent_summary_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    if len(table.rows) < 2:
        return []
    col_idx = _preferred_total_column(table.rows[0])
    if col_idx is None:
        return []
    candidates: list[VerificationCandidate] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if col_idx >= len(row) or not row:
            continue
        role = _lease_liability_split_role(row[0])
        if role is None:
            continue
        raw_amount = parse_amount(row[col_idx])
        if raw_amount is None:
            continue
        candidates.append(
            _candidate(
                note_no,
                title,
                table,
                layout,
                orientation,
                role,
                row[0],
                raw_amount,
                row_idx,
                col_idx,
                account_key="lease_liabilities",
            )
        )
    if not any(candidate.role == "ending" for candidate in candidates):
        return []
    if sum(1 for candidate in candidates if candidate.role == "lease_liability_split_component") < 2:
        return []
    return candidates


def _lease_expense_summary_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    header_idx = _lease_expense_header_row_index(table.rows)
    if header_idx is None:
        return []
    headers = table.rows[header_idx]
    total_col = _lease_expense_total_column(headers)
    if total_col is None:
        return []
    component_cols = [
        idx
        for idx, header in enumerate(headers)
        if idx != total_col and idx > 0 and compact(header)
    ]
    candidates: list[VerificationCandidate] = []
    for row_idx, row in enumerate(table.rows[header_idx + 1 :], start=header_idx + 1):
        if not row:
            continue
        account_key = _lease_expense_account_key(row[0])
        if account_key is None:
            continue
        for col_idx in component_cols:
            if col_idx >= len(row):
                continue
            raw_amount = parse_amount(row[col_idx])
            if raw_amount is None:
                continue
            candidates.append(
                _candidate(
                    note_no,
                    title,
                    table,
                    layout,
                    orientation,
                    "lease_expense_component",
                    f"{row[0]} {headers[col_idx]}".strip(),
                    raw_amount,
                    row_idx,
                    col_idx,
                    account_key=account_key,
                )
            )
        if total_col >= len(row):
            continue
        raw_total = parse_amount(row[total_col])
        if raw_total is None:
            continue
        candidates.append(
            _candidate(
                note_no,
                title,
                table,
                layout,
                orientation,
                "lease_expense_total",
                f"{row[0]} {headers[total_col]}".strip(),
                raw_total,
                row_idx,
                total_col,
                account_key=account_key,
            )
        )
    return candidates


def _discontinued_operation_income_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    col_idx = _discontinued_operation_amount_column(table.rows[0])
    if col_idx is None:
        return []
    candidates: list[VerificationCandidate] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if not row or col_idx >= len(row):
            continue
        primary = row[0]
        secondary = row[1] if len(row) > 1 else ""
        role = _discontinued_operation_income_role(primary, secondary)
        if role is None:
            continue
        raw_amount = parse_amount(row[col_idx])
        if raw_amount is None:
            continue
        candidates.append(
            _candidate(
                note_no,
                title,
                table,
                layout,
                orientation,
                role,
                " ".join(label for label in (primary, secondary) if label).strip(),
                raw_amount,
                row_idx,
                col_idx,
                account_key="discontinued_operations",
            )
        )
    return candidates


def _discontinued_operation_cashflow_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    col_idx = _discontinued_operation_amount_column(table.rows[0])
    if col_idx is None:
        return []
    candidates: list[VerificationCandidate] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if not row or col_idx >= len(row):
            continue
        role = _discontinued_operation_cashflow_role(row[0])
        if role is None:
            continue
        raw_amount = parse_amount(row[col_idx])
        if raw_amount is None:
            continue
        candidates.append(
            _candidate(
                note_no,
                title,
                table,
                layout,
                orientation,
                role,
                row[0],
                raw_amount,
                row_idx,
                col_idx,
                account_key="discontinued_operations_cashflows",
            )
        )
    return candidates


def _asset_cost_accumulated_summary_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    total_row = _plain_total_row(table.rows[1:])
    if total_row is None:
        return []
    row_idx, row = total_row
    candidates: list[VerificationCandidate] = []
    for col_idx, header in enumerate(table.rows[0]):
        if col_idx >= len(row):
            continue
        role = _asset_measure_role(header)
        if role is None:
            continue
        raw_amount = parse_amount(row[col_idx])
        if raw_amount is None:
            continue
        candidates.append(
            _candidate(
                note_no,
                title,
                table,
                layout,
                orientation,
                role,
                header,
                raw_amount,
                row_idx,
                col_idx,
            )
        )
    return candidates


def _asset_component_column_summary_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    if len(table.rows) < 2:
        return []
    total_col_idx = _asset_component_total_column(table.rows[0])
    if total_col_idx is None:
        return []
    component_columns = [
        idx
        for idx, header in enumerate(table.rows[0])
        if idx != total_col_idx and _is_asset_component_header(header)
    ]
    if not component_columns:
        return []
    first_component_col = min(component_columns)
    candidates: list[VerificationCandidate] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if not row or total_col_idx >= len(row):
            continue
        row_label = _asset_component_row_label(row, first_component_col)
        if row_label is None:
            continue
        account_key = f"asset_component_row:{row_label}"
        row_candidates: list[VerificationCandidate] = []
        for component_col_idx in component_columns:
            if component_col_idx >= len(row):
                continue
            raw_component = parse_amount(row[component_col_idx])
            if raw_component is None:
                continue
            row_candidates.append(
                _candidate(
                    note_no,
                    title,
                    table,
                    layout,
                    orientation,
                    "asset_component",
                    f"{row_label} {table.rows[0][component_col_idx]}".strip(),
                    raw_component,
                    row_idx,
                    component_col_idx,
                    account_key=account_key,
                )
            )
        raw_total = parse_amount(row[total_col_idx])
        if raw_total is None:
            continue
        row_candidates.append(
            _candidate(
                note_no,
                title,
                table,
                layout,
                orientation,
                "asset_component_total",
                f"{row_label} {table.rows[0][total_col_idx]}".strip(),
                raw_total,
                row_idx,
                total_col_idx,
                account_key=account_key,
            )
        )
        if sum(1 for candidate in row_candidates if candidate.role == "asset_component") >= 1:
            candidates.extend(row_candidates)
    return candidates


def _is_asset_measure_summary_row(label: str, layout_key: str) -> bool:
    if layout_key != "asset_measure_summary":
        return False
    return any(
        topic in label
        for topic in ("유형자산", "무형자산", "투자부동산", "사용권자산")
    )


def _is_inventory_carrying_amount_summary_row(label: str, layout_key: str) -> bool:
    return layout_key == "inventory_carrying_amount_summary" and label == "재고자산"


def _mixed_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    if len(table.rows) < 2:
        return []
    if layout.key == "asset_stacked_measure_summary":
        return _stacked_measure_summary_candidates(note_no, title, table, layout, orientation)
    if layout.key == "provision_rollforward":
        return _provision_rollforward_candidates(note_no, title, table, layout, orientation)
    if layout.key == "net_debt_bridge":
        return _net_debt_bridge_candidates(note_no, title, table, layout, orientation)
    if layout.key != "asset_movement_columns":
        return []
    total_row = _asset_total_row(table.rows[1:])
    if total_row is None:
        return []
    row_idx, row = total_row
    candidates: list[VerificationCandidate] = []
    for col_idx, header in enumerate(table.rows[0]):
        if col_idx >= len(row):
            continue
        role = _candidate_role(header)
        if role is None:
            continue
        raw_amount = parse_amount(row[col_idx])
        if raw_amount is None:
            continue
        candidates.append(
            _candidate(
                note_no,
                title,
                table,
                layout,
                orientation,
                role,
                header,
                raw_amount,
                row_idx,
                col_idx,
            )
        )
    return candidates


def _provision_rollforward_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    account_columns = _provision_account_columns(table.rows[0])
    if account_columns:
        return _row_oriented_provision_rollforward_candidates(
            note_no,
            title,
            table,
            layout,
            orientation,
            account_columns,
        )
    candidates: list[VerificationCandidate] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if not row or not any("충당부채" in compact(label) for label in row[:2]):
            continue
        for col_idx, header in enumerate(table.rows[0]):
            if col_idx >= len(row):
                continue
            role = _provision_role(header)
            if role is None:
                continue
            raw_amount = parse_amount(row[col_idx])
            if raw_amount is None:
                continue
            candidates.append(
                _candidate(
                    note_no,
                    title,
                    table,
                    layout,
                    orientation,
                    role,
                    header,
                    raw_amount,
                    row_idx,
                    col_idx,
                    account_key="provisions",
                )
            )
    return candidates


def _row_oriented_provision_rollforward_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
    account_columns: list[tuple[int, str]],
) -> list[VerificationCandidate]:
    candidates: list[VerificationCandidate] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if not row:
            continue
        row_label = " ".join(label for label in row[:2] if label).strip()
        role = _provision_row_role(row_label)
        if role is None:
            continue
        for col_idx, account_key in account_columns:
            if col_idx >= len(row):
                continue
            raw_amount = parse_amount(row[col_idx])
            if raw_amount is None:
                continue
            candidates.append(
                _candidate(
                    note_no,
                    title,
                    table,
                    layout,
                    orientation,
                    role,
                    f"{table.rows[0][col_idx]} {row_label}".strip(),
                    raw_amount,
                    row_idx,
                    col_idx,
                    account_key=account_key,
                )
            )
    return candidates


def _provision_current_noncurrent_summary_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    if len(table.rows) < 3:
        return []
    amount_columns = _provision_current_noncurrent_columns(table.rows[0])
    if not amount_columns:
        return []
    total_row = _provision_total_row(table.rows)
    if total_row is None:
        return []
    total_row_idx, total = total_row
    component_rows = [
        (row_idx, row)
        for row_idx, row in enumerate(table.rows[1:], start=1)
        if row_idx != total_row_idx and _is_provision_component_label(" ".join(row[:2]))
    ]
    if len(component_rows) < 2:
        return []
    candidates: list[VerificationCandidate] = []
    for col_idx, account_key in amount_columns:
        col_candidates: list[VerificationCandidate] = []
        header = table.rows[0][col_idx]
        for row_idx, row in component_rows:
            if col_idx >= len(row):
                continue
            raw_amount = parse_amount(row[col_idx])
            if raw_amount is None:
                continue
            col_candidates.append(
                _candidate(
                    note_no,
                    title,
                    table,
                    layout,
                    orientation,
                    "provision_column_component",
                    f"{_provision_row_label(row)} {header}".strip(),
                    raw_amount,
                    row_idx,
                    col_idx,
                    account_key=account_key,
                )
            )
        if col_idx >= len(total):
            continue
        raw_total = parse_amount(total[col_idx])
        if raw_total is None:
            continue
        col_candidates.append(
            _candidate(
                note_no,
                title,
                table,
                layout,
                orientation,
                "provision_column_total",
                f"{_provision_row_label(total)} {header}".strip(),
                raw_total,
                total_row_idx,
                col_idx,
                account_key=account_key,
            )
        )
        if sum(1 for candidate in col_candidates if candidate.role == "provision_column_component") >= 2:
            candidates.extend(col_candidates)
    return candidates


def _defined_benefit_rollforward_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    account_columns = _defined_benefit_account_columns(table.rows[0])
    if not account_columns:
        return []
    has_remeasurement_detail = _has_defined_benefit_remeasurement_detail(
        table.rows,
        account_columns,
    )
    candidates: list[VerificationCandidate] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if not row:
            continue
        row_label = " ".join(label for label in row[:2] if label).strip()
        if has_remeasurement_detail and "총재측정손익" in compact(row_label):
            continue
        role = _defined_benefit_rollforward_role(row_label)
        if role is None:
            continue
        for col_idx, account_key in account_columns:
            if col_idx >= len(row):
                continue
            raw_amount = parse_amount(row[col_idx])
            if raw_amount is None:
                continue
            candidates.append(
                _candidate(
                    note_no,
                    title,
                    table,
                    layout,
                    orientation,
                    role,
                    f"{table.rows[0][col_idx]} {row_label}".strip(),
                    raw_amount,
                    row_idx,
                    col_idx,
                    account_key=account_key,
                )
            )
    return candidates


def _inventory_allowance_rollforward_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    col_idx = _inventory_allowance_amount_column(table.rows[0])
    if col_idx is None:
        return []
    candidates: list[VerificationCandidate] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if col_idx >= len(row) or not row:
            continue
        role = _inventory_allowance_rollforward_role(row[0])
        if role is None:
            continue
        raw_amount = parse_amount(row[col_idx])
        if raw_amount is None:
            continue
        candidates.append(
            _candidate(
                note_no,
                title,
                table,
                layout,
                orientation,
                role,
                row[0],
                raw_amount,
                row_idx,
                col_idx,
                account_key="inventory_valuation_allowance",
            )
        )
    return candidates


def _has_defined_benefit_remeasurement_detail(
    rows: list[list[str]],
    account_columns: list[tuple[int, str]],
) -> bool:
    for row in rows[1:]:
        if not row:
            continue
        label = compact(" ".join(part for part in row[:2] if part))
        if "재측정" not in label or "총재측정손익" in label:
            continue
        for col_idx, _account_key in account_columns:
            if col_idx < len(row) and parse_amount(row[col_idx]) is not None:
                return True
    return False


def _net_debt_bridge_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    account_columns = _net_debt_account_columns(table.rows[0])
    if not account_columns:
        return []
    candidates: list[VerificationCandidate] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if not row:
            continue
        role = _net_debt_bridge_role(row[0])
        if role is None:
            continue
        if role == "signed_movement" and _is_duplicate_aggregate_movement_row(
            table.rows,
            row_idx,
        ):
            continue
        for col_idx, account_key in account_columns:
            if col_idx >= len(row):
                continue
            raw_amount = parse_amount(row[col_idx])
            if raw_amount is None:
                continue
            label = f"{table.rows[0][col_idx]} {row[0]}".strip()
            candidates.append(
                _candidate(
                    note_no,
                    title,
                    table,
                    layout,
                    orientation,
                    role,
                    label,
                    raw_amount,
                    row_idx,
                    col_idx,
                    account_key=account_key,
                )
            )
    return candidates


def _is_duplicate_aggregate_movement_row(rows: list[list[str]], row_idx: int) -> bool:
    row = rows[row_idx]
    if len(row) < 2:
        return False
    primary = compact(row[0])
    secondary = compact(row[1])
    if not primary or primary != secondary:
        return False
    return any(
        len(other) > 1
        and compact(other[0]) == primary
        and compact(other[1]) not in {"", primary}
        for other in rows[row_idx + 1 :]
    )


def _stacked_measure_summary_candidates(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
) -> list[VerificationCandidate]:
    total_row = _stacked_measure_total_row(table.rows[1:])
    if total_row is None:
        return []
    asset_columns = _asset_header_columns(table.rows[0])
    if not asset_columns:
        return []
    row_idx, row = total_row
    candidates: list[VerificationCandidate] = []
    for col_idx in asset_columns:
        if col_idx >= len(row):
            continue
        raw_amount = parse_amount(row[col_idx])
        if raw_amount is None:
            continue
        candidates.append(
            _candidate(
                note_no,
                title,
                table,
                layout,
                orientation,
                "ending",
                table.rows[0][col_idx],
                raw_amount,
                row_idx,
                col_idx,
            )
        )
    return candidates


def _asset_total_row(rows: list[list[str]]) -> tuple[int, list[str]] | None:
    for row_idx, row in enumerate(rows, start=1):
        label = " ".join(row[:2]).replace(" ", "")
        if "합계" in label and any(
            topic in label for topic in ("유형자산", "무형자산", "투자부동산", "사용권자산")
        ):
            return row_idx, row
    return None


def _plain_total_row(rows: list[list[str]]) -> tuple[int, list[str]] | None:
    for row_idx, row in enumerate(rows, start=1):
        label = compact(row[0]) if row else ""
        if label in {"합계", "총계"}:
            return row_idx, row
    return None


def _stacked_measure_total_row(rows: list[list[str]]) -> tuple[int, list[str]] | None:
    for row_idx, row in enumerate(rows, start=1):
        label = compact(" ".join(row[:2]))
        if any(alias in label for alias in ("장부금액합계", "장부가액합계", "순장부금액합계")):
            return row_idx, row
    return None


def _aging_status_total_row(rows: list[list[str]]) -> tuple[int, list[str]] | None:
    for row_idx, row in enumerate(rows, start=1):
        label = compact(" ".join(row[:2]))
        if "연체상태합계" in label:
            return row_idx, row
    return None


def _receivable_aging_bucket_columns(headers: list[str]) -> list[tuple[int, str]]:
    columns: list[tuple[int, str]] = []
    for idx, header in enumerate(headers):
        normalized = compact(header)
        if not normalized or normalized in {"구분", "구"}:
            continue
        if normalized in {"합계", "합"}:
            columns.append((idx, "aging_bucket_total"))
        elif _is_receivable_aging_bucket_header(normalized):
            columns.append((idx, "aging_bucket_component"))
    return columns


def _receivable_aging_account_key(label: str) -> str | None:
    normalized = compact(label)
    if "총장부금액" in normalized:
        return "trade_receivables_gross_aging"
    if "손실충당금" in normalized or "대손충당금" in normalized:
        return "trade_receivables_loss_allowance_aging"
    return None


def _is_receivable_aging_bucket_header(value: str) -> bool:
    normalized = compact(value)
    return "연체" in normalized or "회수기간" in normalized or "손상채권" in normalized


def _asset_header_columns(headers: list[str]) -> list[int]:
    return [
        idx
        for idx, header in enumerate(headers)
        if any(topic in compact(header) for topic in ("유형자산", "무형자산", "투자부동산", "사용권자산", "영업권"))
    ]


def _asset_two_label_amount_column(headers: list[str]) -> int | None:
    for idx, header in enumerate(headers):
        if _account_key(header) != "unknown":
            return idx
    return len(headers) - 1 if len(headers) >= 3 else None


def _candidate(
    note_no: str,
    title: str,
    table: ReportTable,
    layout: LayoutClassification,
    orientation: TableOrientation,
    role: str,
    label: str,
    raw_amount: int,
    row_idx: int,
    col_idx: int,
    *,
    account_key: str | None = None,
    unit_multiplier: int | None = None,
) -> VerificationCandidate:
    effective_unit_multiplier = table.unit_multiplier if unit_multiplier is None else unit_multiplier
    return VerificationCandidate(
        account_key=account_key or _account_key(title),
        role=role,
        label=label,
        raw_amount=raw_amount,
        unit_multiplier=effective_unit_multiplier,
        amount=raw_amount * effective_unit_multiplier,
        note_no=note_no,
        table_source=f"note:{note_no}/table:{table.index}",
        row_index=row_idx,
        column_index=col_idx,
        layout_key=layout.key,
        orientation_key=orientation.key,
        confidence=min(layout.confidence, orientation.confidence),
        evidence=layout.evidence + orientation.evidence,
    )


def _preferred_total_column(headers: list[str]) -> int | None:
    for aliases in (("합계", "총계"), ("장부금액", "순장부금액", "장부가액")):
        for idx, header in enumerate(headers):
            normalized = header.replace(" ", "")
            if any(alias in normalized for alias in aliases):
                return idx
    return len(headers) - 1 if len(headers) > 1 else None


def _asset_component_total_column(headers: list[str]) -> int | None:
    for idx, header in enumerate(headers):
        normalized = compact(header)
        if "장부금액" in normalized or "장부가액" in normalized:
            return idx
    return None


def _is_asset_component_header(value: str) -> bool:
    normalized = compact(value)
    return any(
        alias in normalized
        for alias in (
            "상각자산",
            "미상각자산",
            "개발중인무형자산",
            "개발중인자산",
            "건설중인자산",
        )
    )


def _asset_component_row_label(row: list[str], first_component_col: int) -> str | None:
    label_cells = row[:first_component_col]
    for cell in label_cells:
        normalized = compact(cell)
        if normalized and ("합계" in normalized or "총계" in normalized):
            return cell.strip()
    for cell in reversed(label_cells):
        normalized = compact(cell)
        if not normalized or _is_generic_asset_component_row_label(normalized):
            continue
        return cell.strip()
    return None


def _is_generic_asset_component_row_label(value: str) -> bool:
    return value in {
        "부문",
        "구분",
        "분류",
        "자본화된개발비지출액",
        "무형자산및영업권",
        "무형자산",
        "영업권",
        "유형자산",
        "투자부동산",
        "사용권자산",
    }


def _preferred_financial_total_column(headers: list[str]) -> int | None:
    for idx, header in enumerate(headers):
        normalized = compact(header)
        normalized_key = normalized.replace(",", "")
        if any(alias in normalized_key for alias in ("범주합계", "금융자산합계", "금융부채합계")):
            return idx
    for aliases in (("금융자산", "금융부채"), ("합계",)):
        for idx, header in enumerate(headers):
            normalized_key = compact(header).replace(",", "")
            if any(alias == normalized_key for alias in aliases):
                return idx
    return None


def _financial_category_component_columns(
    headers: list[str],
    total_col_idx: int,
) -> list[int]:
    columns: list[int] = []
    for idx, header in enumerate(headers):
        if idx == total_col_idx:
            continue
        normalized = compact(header)
        if not normalized or normalized in {"금융자산", "금융부채", "구분", "구분"}:
            continue
        if "합계" in normalized or "총계" in normalized:
            continue
        if _is_financial_category_component_header(normalized):
            columns.append(idx)
    return columns


def _is_financial_category_component_header(value: str) -> bool:
    return any(
        alias in value
        for alias in (
            "당기손익",
            "기타포괄손익",
            "공정가치",
            "상각후원가",
            "기타금융",
            "위험회피",
        )
    )


def _financial_category_row_label(row: list[str]) -> str:
    if len(row) >= 2:
        primary = compact(row[0])
        secondary = compact(row[1])
        if primary in {"금융자산", "금융부채", "총금융자산", "총금융부채"} and secondary == primary:
            return ""
        if (
            primary in {"금융자산", "금융부채", "총금융자산", "총금융부채"}
            and secondary
            and secondary != primary
            and _financial_account_key(row[1]) is not None
        ):
            return row[1]
    return row[0]


def _financial_category_total_row_index(rows: list[list[str]]) -> int | None:
    for row_idx, row in enumerate(rows[1:], start=1):
        if not row:
            continue
        label = compact(_financial_category_row_label(row))
        if label in {"합계", "총계", "금융자산", "금융부채", "총금융자산", "총금융부채"}:
            return row_idx
    return None


def _financial_fair_value_amount_column(headers: list[str]) -> int | None:
    for idx, header in enumerate(headers):
        if compact(header) == "공정가치":
            return idx
    return None


def _fair_value_level_component_columns(headers: list[str], total_col: int | None) -> list[int]:
    return [
        idx
        for idx, header in enumerate(headers)
        if idx != total_col and _is_fair_value_level_header(header)
    ]


def _fair_value_level_total_column(headers: list[str]) -> int | None:
    for idx, header in enumerate(headers):
        normalized = compact(header)
        if normalized in {"합계", "합"}:
            return idx
    return None


def _is_fair_value_level_header(value: str) -> bool:
    normalized = compact(value).replace("(", "").replace(")", "")
    return normalized in {"수준1", "수준2", "수준3"} or normalized.startswith("수준")


def _tax_expense_period_columns(headers: list[str]) -> list[int]:
    return [
        idx
        for idx, header in enumerate(headers)
        if compact(header) in {"당기", "전기", "당분기", "전분기"}
    ]


def _tax_expense_role(label: str) -> str | None:
    normalized = compact(label)
    if _is_tax_expense_total_row(normalized):
        return "tax_expense_total"
    if _is_tax_expense_component_row(normalized):
        return "tax_expense_component"
    return None


def _is_tax_expense_component_row(value: str) -> bool:
    if _is_tax_expense_total_row(value):
        return False
    return (
        _is_current_tax_expense_component_row(value)
        or _is_deferred_tax_expense_component_row(value)
        or _is_capital_tax_expense_component_row(value)
        or _is_other_tax_expense_component_row(value)
    )


def _is_tax_expense_total_row(value: str) -> bool:
    normalized = value.replace("(", "").replace(")", "")
    return normalized in {"법인세비용", "법인세비용합계", "법인세비용수익"}


def _is_current_tax_expense_component_row(value: str) -> bool:
    if "법인세율" in value or "세율로계산" in value:
        return False
    return "법인세" in value and any(
        alias in value for alias in ("부담액", "부담내역", "추납", "환급", "조정액", "조정사항", "당기법인세비용")
    )


def _is_deferred_tax_expense_component_row(value: str) -> bool:
    if "기초" in value or "기말" in value:
        return False
    return "이연법인세" in value and any(
        alias in value for alias in ("변동액", "변동")
    )


def _is_capital_tax_expense_component_row(value: str) -> bool:
    return "자본에직접" in value and "법인세" in value


def _is_other_tax_expense_component_row(value: str) -> bool:
    return value.startswith("기타") or value in {"기타"}


def _financial_fair_value_level_row_label(row: list[str]) -> str | None:
    if len(row) > 1 and compact(row[1]):
        return row[1]
    if row and compact(row[0]):
        return row[0]
    return None


def _financial_fair_value_level_account_key(row: list[str]) -> str | None:
    label = _financial_fair_value_level_row_label(row)
    if label is None:
        return None
    normalized_label = compact(label)
    if normalized_label in {"합계", "합"} and row:
        section = compact(row[0])
        if "금융자산" in section:
            return "financial_assets"
        if "금융부채" in section:
            return "financial_liabilities"
    if "파생상품" in normalized_label and "부채" not in normalized_label:
        return "derivative_assets"
    if "당기손익" in normalized_label and "금융자산" in normalized_label:
        return "financial_assets_fvtpl"
    if "기타포괄손익" in normalized_label and "금융자산" in normalized_label:
        return "financial_assets_fvoci"
    return _financial_account_key(label)


def _receivable_carrying_component_columns(
    headers: list[str],
    total_col_idx: int,
) -> list[int]:
    columns: list[int] = []
    for idx, header in enumerate(headers):
        if idx == total_col_idx:
            continue
        normalized = compact(header)
        if not normalized or normalized in {"구분"}:
            continue
        if any(
            alias in normalized
            for alias in (
                "총장부금액",
                "현재가치할인차금",
                "손상차손누계액",
                "대손충당금",
                "손실충당금",
                "이연대출부대수익",
                "이연대출부대비용",
            )
        ):
            columns.append(idx)
    return columns


def _inventory_carrying_component_columns(
    headers: list[str],
    total_col_idx: int,
) -> list[int]:
    columns: list[int] = []
    for idx, header in enumerate(headers):
        if idx == total_col_idx:
            continue
        normalized = compact(header)
        if not normalized or normalized == "구분":
            continue
        if any(
            alias in normalized
            for alias in (
                "총장부금액",
                "취득원가",
                "평가전금액",
                "재고자산평가충당금",
                "평가충당금",
                "평가손실충당금",
                "평가손실누계액",
                "손상차손누계액",
                "손실충당금",
                "충당금",
            )
        ):
            columns.append(idx)
    return columns


def _preferred_functional_expense_total_column(headers: list[str]) -> int | None:
    for idx, header in enumerate(headers):
        if "기능별항목합계" in compact(header):
            return idx
    return _preferred_total_column(headers)


def _single_row_functional_expense_amount_column(headers: list[str]) -> int | None:
    for idx, header in enumerate(headers):
        if _is_depreciation_expense_label(header):
            return idx
    return None


def _functional_expense_formula_role(header: str) -> str | None:
    normalized = compact(header)
    if normalized in {"기능별항목합계", "합계", "총계"}:
        return "expense_total"
    if normalized in {"매출원가", "판매비와일반관리비", "판매비와관리비"}:
        return "expense_component"
    return None


def _employee_benefit_expense_role(label: str) -> str | None:
    normalized = compact(label)
    if normalized in {"합계", "총계"} or normalized.endswith("합계"):
        return "employee_benefit_expense_total"
    if any(
        alias in normalized
        for alias in ("판관비", "판매비", "관리비", "매출원가", "제조원가")
    ):
        return "employee_benefit_expense_component"
    return None


def _preferred_debt_total_column(rows: list[list[str]]) -> int | None:
    for row in rows[:4]:
        for idx, label in enumerate(row):
            normalized = compact(label)
            if any(alias in normalized for alias in ("차입금명칭합계", "범위합계", "합계")):
                return idx
    headers = rows[0] if rows else []
    return len(headers) - 1 if len(headers) > 1 else None


def _preferred_expense_amount_column(headers: list[str]) -> int | None:
    for idx, header in enumerate(headers):
        if compact(header) in {"금액", "공시금액"}:
            return idx
    return _preferred_total_column(headers)


def _preferred_credit_risk_amount_column(headers: list[str]) -> int | None:
    for idx, header in enumerate(headers):
        if "신용위험" in compact(header):
            return idx
    return None


def _credit_risk_exposure_total_column(headers: list[str]) -> int | None:
    for idx, header in enumerate(headers):
        normalized = compact(header)
        if "금융상품합계" in normalized or normalized in {"합계", "총계"}:
            return idx
    return None


def _maturity_analysis_columns(headers: list[str]) -> list[tuple[int, str]]:
    columns: list[tuple[int, str]] = []
    for idx, header in enumerate(headers):
        normalized = compact(header)
        if not normalized:
            continue
        if "합계" in normalized:
            columns.append((idx, "maturity_total"))
        elif _is_maturity_bucket_header(normalized):
            columns.append((idx, "maturity_component"))
    return columns


def _lease_expense_header_row_index(rows: list[list[str]]) -> int | None:
    for idx, row in enumerate(rows[:4]):
        normalized = [compact(cell) for cell in row]
        if any("자산합계" in cell for cell in normalized) and any(
            cell and "자산" not in cell for cell in normalized[1:]
        ):
            return idx
    for idx, row in enumerate(rows[:4]):
        if any("자산합계" in compact(cell) for cell in row):
            return idx
    return None


def _lease_expense_total_column(headers: list[str]) -> int | None:
    for idx, header in enumerate(headers):
        if "자산합계" in compact(header):
            return idx
    return None


def _discontinued_operation_amount_column(headers: list[str]) -> int | None:
    for idx, header in enumerate(headers):
        if "중단영업" in compact(header):
            return idx
    return len(headers) - 1 if len(headers) > 1 else None


def _is_depreciation_expense_label(label: str) -> bool:
    normalized = compact(label)
    return any(alias in normalized for alias in ("감가상각비", "상각비", "무형자산상각비", "사용권자산상각비"))


def _is_research_development_expense_label(label: str) -> bool:
    normalized = compact(label)
    return ("연구" in normalized and "개발" in normalized) or "경상연구개발비" in normalized


def _asset_measure_role(label: str) -> str | None:
    normalized = compact(label)
    if "총장부금액" in normalized or "취득원가" in normalized:
        return "gross_cost"
    if "손상차손누계" in normalized or "손상누계" in normalized:
        return "accumulated_impairment"
    if "감가상각누계" in normalized or "상각누계" in normalized:
        return "accumulated_depreciation"
    if normalized in {"기말", "기말금액", "기말잔액"} or "장부금액" in normalized or "장부가액" in normalized:
        return "ending"
    return None


def _candidate_role(label: str) -> str | None:
    normalized = label.replace(" ", "")
    if "기초" in normalized:
        return "beginning"
    if "기말" in normalized or "장부금액" in normalized or "장부가액" in normalized:
        return "ending"
    if "취득" in normalized or "증가" in normalized:
        return "additions"
    if "처분" in normalized or "감소" in normalized or "제거" in normalized or "종료" in normalized:
        return "disposals"
    if "감가상각" in normalized or "상각" in normalized:
        return "depreciation"
    if "손상" in normalized:
        return "impairment"
    if (
        "대체" in normalized
        or "리스변경" in normalized
        or "매각예정" in normalized
        or "연결범위" in normalized
        or "기타변동" in normalized
    ):
        return "transfers"
    return None


def _debt_detail_role(label: str) -> str | None:
    normalized = compact(label)
    if "유동성" in normalized and "대체부분" in normalized:
        if "비유동성" in normalized and normalized.startswith("비유동"):
            return "ending"
        return "current_portion"
    if "명목금액" in normalized:
        return "face_amount"
    if "사채할인발행차금" in normalized or "현재가치할인차금" in normalized:
        return "debt_discount"
    if normalized in {"차입금", "소계"}:
        return "debt_total"
    if "1년이내만기도래분" in normalized:
        return "current_portion"
    if (
        "비유동성차입금" in normalized
        or ("비유동" in normalized and ("사채" in normalized or "차입금" in normalized))
        or normalized == "합계"
    ):
        return "ending"
    return None


def _preferred_eps_amount_column(headers: list[str]) -> int | None:
    for idx, header in enumerate(headers):
        if "보통주" in compact(header):
            return idx
    return 1 if len(headers) > 1 else None


def _eps_role(label: str) -> str | None:
    normalized = compact(label)
    if _is_eps_profit_row(normalized):
        return "eps_profit"
    if "가중평균유통보통주식수" in normalized:
        return "weighted_average_shares"
    if _is_eps_result_row(normalized):
        return "earnings_per_share"
    return None


def _eps_account_key(label: str) -> str:
    normalized = compact(label)
    if "계속영업" in normalized:
        return "continuing_basic_eps"
    if "중단영업" in normalized:
        return "discontinued_basic_eps"
    return "basic_eps"


def _dividend_period_columns(rows: list[list[str]]) -> list[tuple[int, str]]:
    if not rows:
        return []
    columns: list[tuple[int, str]] = []
    for idx, header in enumerate(rows[0]):
        period = _dividend_period_label(header)
        if period is not None:
            columns.append((idx, period))
    if columns:
        return columns
    if len(rows) < 2:
        return []
    for idx, header in enumerate(rows[1]):
        period = _dividend_period_label(header)
        if period is not None:
            columns.append((idx, period))
    return columns


def _dividend_period_label(label: str) -> str | None:
    normalized = compact(label)
    if normalized in {"당기", "당분기"}:
        return "당기"
    if normalized in {"전기", "전분기"}:
        return "전기"
    if normalized in {"전전기", "전전분기"}:
        return "전전기"
    return None


def _dividend_payout_role(label: str) -> str | None:
    normalized = compact(label)
    if "현금배당성향" in normalized:
        return "dividend_payout_ratio_tenths"
    if "현금배당금총액" in normalized:
        return "cash_dividends"
    if "연결" in normalized and "당기순이익" in normalized:
        return "dividend_net_income"
    return None


def _is_eps_profit_row(value: str) -> bool:
    return (
        ("당기순이익" in value or "당기순손익" in value)
        and "주당" not in value
        and "배당" not in value
    )


def _is_eps_result_row(value: str) -> bool:
    return "주당" in value and ("이익" in value or "손익" in value)


def _debt_component_header_role(label: str) -> str | None:
    normalized = compact(label)
    if "명목금액" in normalized:
        return "face_amount"
    if "유동성사채" in normalized or "유동성차입금" in normalized:
        return "current_portion"
    if "사채할인발행차금" in normalized or "현재가치할인차금" in normalized:
        return "debt_discount"
    if "비유동" in normalized and ("사채" in normalized or "차입금" in normalized):
        return "ending"
    return None


def _provision_role(label: str) -> str | None:
    normalized = compact(label)
    if "기초" in normalized:
        return "beginning"
    if "기말" in normalized:
        return "ending"
    if any(alias in normalized for alias in ("전입", "연중사용액", "사용액", "연결범위변동", "매각예정분류")):
        return "signed_movement"
    return None


def _asset_period_rollforward_role(label: str) -> str | None:
    normalized = compact(label)
    if not normalized or normalized in {"구분", "계정과목"}:
        return None
    if "기초" in normalized:
        return "beginning"
    if "기말" in normalized:
        return "ending"
    if normalized:
        return "signed_movement"
    return None


def _asset_two_label_row_rollforward_role(label: str) -> str | None:
    normalized = compact(label)
    if not normalized or "변동에대한조정" in normalized:
        return None
    if "기초" in normalized:
        return "beginning"
    if "기말" in normalized:
        return "ending"
    return "signed_movement"


def _provision_row_role(label: str) -> str | None:
    normalized = compact(label)
    if "기초" in normalized:
        return "beginning"
    if "기말" in normalized:
        return "ending"
    if normalized:
        return "signed_movement"
    return None


def _net_debt_bridge_role(label: str) -> str | None:
    normalized = compact(label)
    if "기초순부채" in normalized or (
        "재무활동에서생기는" in normalized and "기초" in normalized and "부채" in normalized
    ):
        return "beginning"
    if "기말순부채" in normalized or (
        "재무활동에서생기는" in normalized and "기말" in normalized and "부채" in normalized
    ):
        return "ending"
    if normalized:
        return "signed_movement"
    return None


def _defined_benefit_rollforward_role(label: str) -> str | None:
    normalized = compact(label)
    if "기초" in normalized:
        return "beginning"
    if "기말" in normalized:
        return "ending"
    if normalized:
        return "signed_movement"
    return None


def _inventory_allowance_rollforward_role(label: str) -> str | None:
    normalized = compact(label)
    if "기초" in normalized:
        return "beginning"
    if "기말" in normalized:
        return "ending"
    if normalized:
        return "signed_movement"
    return None


def _expense_summary_role(label: str) -> str | None:
    normalized = compact(label)
    if normalized in {"합계", "총계"}:
        return "expense_total"
    return "expense_component" if normalized else None


def _credit_risk_exposure_role(label: str) -> str | None:
    normalized = compact(label)
    if normalized in {"합계", "총계"}:
        return "credit_exposure_total"
    return "credit_exposure_component" if normalized else None


def _discontinued_operation_income_role(primary: str, secondary: str) -> str | None:
    normalized_primary = compact(primary)
    normalized_secondary = compact(secondary)
    joined = normalized_primary + normalized_secondary
    if "비지배지분" in joined:
        return "noncontrolling_attribution"
    if "지배기업" in joined or "소유주에게귀속" in joined:
        return "parent_attribution"
    if "중단영업처분이익" in joined or "중단영업처분손익" in joined:
        return "disposal_gain"
    if "중단영업순이익" in normalized_primary or "중단영업순손익" in normalized_primary:
        return "net_discontinued_profit"
    if "중단영업이익" in normalized_primary or "중단영업손실" in normalized_primary:
        return "discontinued_profit"
    if "법인세비용차감전" in joined:
        return "pre_tax_profit"
    if "법인세비용" in joined:
        return "tax_expense"
    if "매출총이익" in joined:
        return "gross_profit"
    if "매출원가" in joined:
        return "cost_of_sales"
    if "매출액" in joined:
        return "revenue"
    if "판매비와관리비" in joined or "판매비와일반관리비" in joined:
        return "selling_admin"
    if "영업이익" in joined or "영업손실" in joined:
        return "operating_profit"
    if "기타이익" in joined or "기타수익" in joined:
        return "other_income"
    if "기타손실" in joined or "기타비용" in joined:
        return "other_loss"
    if "금융수익" in joined:
        return "finance_income"
    if "금융비용" in joined:
        return "finance_cost"
    return None


def _discontinued_operation_cashflow_role(label: str) -> str | None:
    normalized = compact(label)
    if normalized in {"합계", "총계"}:
        return "cashflow_total"
    if "영업활동현금흐름" in normalized:
        return "operating_cashflow"
    if "투자활동현금흐름" in normalized:
        return "investing_cashflow"
    if "재무활동현금흐름" in normalized:
        return "financing_cashflow"
    return None


def _account_key(title: str) -> str:
    normalized = title.replace(" ", "")
    if "유형자산" in normalized:
        return "property_plant_equipment"
    if "무형자산" in normalized:
        return "intangible_assets"
    if "투자부동산" in normalized:
        return "investment_property"
    if "재고자산" in normalized:
        return "inventories"
    return "unknown"


def _debt_account_key(title: str, rows: list[list[str]]) -> str:
    normalized_title = compact(title)
    if "차입금" in normalized_title and "사채" not in normalized_title:
        return "borrowings"
    if any(compact(cell) == "사채" for row in rows[:8] for cell in row[:3]):
        return "bonds"
    joined = compact(title + " " + " ".join(" ".join(row) for row in rows[:8]))
    if "사채" in joined and "차입금" not in normalized_title:
        return "bonds"
    if "사채" in joined and any("명목금액" in compact(row[0]) if row else False for row in rows):
        return "bonds"
    if "차입금" in joined:
        return "borrowings"
    if "사채" in joined:
        return "bonds"
    return "unknown"


def _financial_account_key(label: str) -> str | None:
    normalized = compact(label)
    if normalized in {"금융자산", "총금융자산"}:
        return "financial_assets"
    if normalized in {"금융부채", "총금융부채"}:
        return "financial_liabilities"
    if "현금및현금성자산" in normalized:
        return "cash_and_cash_equivalents"
    if "단기금융상품" in normalized:
        return "short_term_financial_instruments"
    if "장기금융상품" in normalized:
        return "long_term_financial_instruments"
    if "단기투자자산" in normalized:
        return "short_term_investments"
    if "장기투자자산" in normalized:
        return "long_term_investments"
    if "관계기업및공동기업투자" in normalized:
        return "associates_joint_ventures_investments"
    if "매출채권및기타채권" in normalized or "매출채권및기타유동채권" in normalized:
        return "trade_other_receivables"
    if "매출채권" in normalized:
        return "trade_receivables"
    if "미수금" in normalized:
        return "other_receivables"
    if "보증금" in normalized:
        return "deposits"
    if "기타유동금융자산" in normalized:
        return "other_current_financial_assets"
    if "기타비유동금융자산" in normalized:
        return "other_noncurrent_financial_assets"
    if "기타금융자산" in normalized:
        return "other_financial_assets"
    if "당기손익" in normalized and "금융자산" in normalized:
        return "profit_loss_fair_value_financial_assets"
    if "기타포괄손익" in normalized and "금융자산" in normalized:
        return "oci_fair_value_financial_assets"
    if "단기대여금" in normalized:
        return "short_term_loans"
    if "장기대여금" in normalized:
        return "long_term_loans"
    if "단기미수금" in normalized:
        return "short_term_other_receivables"
    if "장기미수금" in normalized:
        return "long_term_other_receivables"
    if "매입채무" in normalized:
        return "trade_payables"
    if "차입금" in normalized:
        return "borrowings"
    if "사채" in normalized:
        return "bonds"
    if "리스부채" in normalized:
        return "lease_liabilities"
    if "기타금융부채" in normalized:
        return "other_financial_liabilities"
    if "파생상품자산" in normalized:
        return "derivative_assets"
    if "파생상품부채" in normalized:
        return "derivative_liabilities"
    return None


def _financial_fair_value_role(label: str) -> str | None:
    normalized = compact(label)
    if normalized in {"금융자산", "총금융자산", "금융부채", "총금융부채"}:
        return "fair_value_total"
    return "fair_value_component" if normalized else None


def _credit_risk_asset_account_key(label: str) -> str | None:
    normalized = compact(label)
    if "현금성자산" in normalized or "현금및현금성자산" in normalized:
        return "cash_and_cash_equivalents"
    if "단기당기손익" in normalized and "금융자산" in normalized:
        return "financial_assets_fvtpl_current"
    if "장기당기손익" in normalized and "금융자산" in normalized:
        return "financial_assets_fvtpl_noncurrent"
    if "당기손익" in normalized and "금융자산" in normalized:
        return "financial_assets_fvtpl"
    if "기타포괄손익" in normalized and "금융자산" in normalized:
        return "financial_assets_fvoci"
    if "매출채권" in normalized:
        return "trade_receivables"
    if "단기대여금" in normalized:
        return "short_term_loans"
    if "장기대여금" in normalized:
        return "long_term_loans"
    if "미수금" in normalized:
        return "short_term_other_receivables"
    if "미수수익" in normalized:
        return "short_term_accrued_income"
    if "기타유동금융자산" in normalized:
        return "other_current_financial_assets"
    if "기타비유동금융자산" in normalized:
        return "other_noncurrent_financial_assets"
    if "기타금융자산" in normalized:
        return "other_financial_assets"
    if "파생상품자산" in normalized:
        return "derivative_assets"
    if "장기보증금" in normalized:
        return "long_term_deposits"
    if "단기보증금" in normalized:
        return "short_term_deposits"
    if "대여금" in normalized:
        return "loans"
    return _financial_account_key(label)


def _maturity_liability_account_key(label: str) -> str | None:
    normalized = compact(label)
    if normalized in {"합계", "총계"}:
        return "maturity_analysis_total"
    if "차입금" in normalized and "사채" in normalized:
        return "borrowings_and_bonds"
    if "리스부채" in normalized:
        return "lease_liabilities"
    if "미지급비용" in normalized:
        return "accrued_expenses"
    if "미지급금" in normalized:
        return "other_payables"
    if "매입채무" in normalized or "기타채무" in normalized:
        return "trade_and_other_payables"
    if "기타금융부채" in normalized:
        return "other_financial_liabilities"
    if "금융부채" in normalized:
        return "financial_liabilities"
    if "차입금" in normalized:
        return "borrowings"
    if "사채" in normalized:
        return "bonds"
    return None


def _is_employee_benefit_expected_payment_row(value: str) -> bool:
    normalized = compact(value)
    return (
        ("지급" in normalized and "예상" in normalized and "급여" in normalized)
        or ("확정급여" in normalized and "지급액" in normalized)
    )


def _employee_benefit_maturity_account_key(label: str) -> str | None:
    normalized = compact(label)
    if _is_employee_benefit_expected_payment_row(normalized):
        return "defined_benefit_expected_payments"
    if "예상" in normalized and "기여금" in normalized:
        return "defined_benefit_expected_contributions"
    return None


def _lease_liability_maturity_account_key(label: str) -> str | None:
    normalized = compact(label)
    if any(alias in normalized for alias in ("받게될", "받을", "수취", "채권", "순투자", "무보증잔존가치")):
        return None
    if "최소리스료" in normalized and "현재가치" in normalized:
        return "lease_liability_present_value"
    if "이자비용" in normalized:
        return "lease_liability_interest"
    if "최소리스료" in normalized:
        return "minimum_lease_payments"
    if "할인되지않은리스부채" in normalized or "총리스부채" in normalized:
        return "undiscounted_lease_liabilities"
    if "리스부채" in normalized:
        return "lease_liabilities"
    return None


def _lease_liability_split_role(label: str) -> str | None:
    normalized = compact(label)
    if ("리스부채" in normalized and ("합계" in normalized or "총" in normalized)) or normalized == "합계":
        return "ending"
    if "비유동" in normalized and "리스부채" in normalized:
        return "lease_liability_split_component"
    if "비유동" not in normalized and (
        "유동리스부채" in normalized or "유동성리스부채" in normalized
    ):
        return "lease_liability_split_component"
    return None


def _lease_expense_account_key(label: str) -> str | None:
    normalized = compact(label)
    if "감가상각비" in normalized and "사용권자산" in normalized:
        return "right_of_use_asset_depreciation"
    if "리스부채에대한이자비용" in normalized:
        return "lease_interest_expense"
    if "단기리스료" in normalized:
        return "short_term_lease_expense"
    if "소액자산리스료" in normalized:
        return "low_value_asset_lease_expense"
    return None


def _is_maturity_bucket_header(value: str) -> bool:
    return any(
        alias in value
        for alias in ("3개월", "개월", "1년", "2년", "5년", "10년", "초과", "이내", "미만", "이상", "~")
    )


def _net_debt_account_columns(headers: list[str]) -> list[tuple[int, str]]:
    return [
        (idx, account_key)
        for idx, header in enumerate(headers)
        if (account_key := _net_debt_account_key(header)) is not None
    ]


def _defined_benefit_account_columns(headers: list[str]) -> list[tuple[int, str]]:
    return [
        (idx, account_key)
        for idx, header in enumerate(headers)
        if (account_key := _defined_benefit_account_key(header)) is not None
    ]


def _provision_account_columns(headers: list[str]) -> list[tuple[int, str]]:
    return [
        (idx, account_key)
        for idx, header in enumerate(headers)
        if (account_key := _provision_account_key(header)) is not None
    ]


def _provision_current_noncurrent_columns(headers: list[str]) -> list[tuple[int, str]]:
    columns: list[tuple[int, str]] = []
    for idx, header in enumerate(headers):
        normalized = compact(header)
        if "비유동" in normalized:
            columns.append((idx, "noncurrent_provisions"))
        elif normalized == "유동" or "유동충당부채" in normalized:
            columns.append((idx, "current_provisions"))
    return columns


def _provision_total_row(rows: list[list[str]]) -> tuple[int, list[str]] | None:
    for row_idx, row in enumerate(rows[1:], start=1):
        if _is_provision_total_label(" ".join(row[:2])):
            return row_idx, row
    return None


def _provision_row_label(row: list[str]) -> str:
    if len(row) > 1 and compact(row[1]):
        return row[1]
    return row[0] if row else ""


def _is_provision_component_label(label: str) -> bool:
    normalized = compact(label)
    return _provision_account_key(normalized) is not None and not _is_provision_total_label(normalized)


def _is_provision_total_label(label: str) -> bool:
    normalized = compact(label)
    return "충당부채" in normalized and ("합계" in normalized or "총계" in normalized)


def _provision_account_key(label: str) -> str | None:
    normalized = compact(label)
    if not any(
        alias in normalized
        for alias in (
            "충당부채",
            "복구",
            "사후처리",
            "정화",
            "장기종업원급여부채",
            "제품보증",
            "판매보증",
            "반품",
        )
    ):
        return None
    if "합계" in normalized or normalized == "기타충당부채":
        return "provisions_total"
    if "복구" in normalized or "사후처리" in normalized or "정화" in normalized:
        return "restoration_provision"
    if "장기종업원" in normalized:
        return "long_term_employee_benefit_provision"
    if "제품보증" in normalized or "판매보증" in normalized:
        return "product_warranty_provision"
    if "반품" in normalized:
        return "returns_provision"
    return "other_provisions"


def _inventory_allowance_amount_column(headers: list[str]) -> int | None:
    for idx, header in enumerate(headers):
        if "재고자산평가충당금" in compact(header):
            return idx
    return None


def _defined_benefit_account_key(label: str) -> str | None:
    normalized = compact(label)
    if "확정급여채무" in normalized:
        return "defined_benefit_obligation"
    if "사외적립자산" in normalized:
        return "plan_assets"
    return None


def _net_debt_account_key(label: str) -> str | None:
    normalized = compact(label)
    if "전환사채" in normalized and "교환사채" in normalized:
        return "convertible_exchangeable_bonds"
    if "전환사채" in normalized:
        return "convertible_bonds"
    if "교환사채" in normalized:
        return "exchangeable_bonds"
    if "유동성장기사채" in normalized:
        return "current_long_term_bonds"
    if "단기사채" in normalized:
        return "short_term_bonds"
    if "유동성사채" in normalized:
        return "current_bonds"
    if "비유동사채" in normalized:
        return "noncurrent_bonds"
    if "사채" in normalized and ("유동" in normalized or "유동성" in normalized) and "비유동" not in normalized:
        return "current_bonds"
    if "비유동" in normalized and "사채" in normalized:
        return "noncurrent_bonds"
    if "유동성리스부채" in normalized:
        return "current_lease_liabilities"
    if "비유동" in normalized and "리스부채" in normalized:
        return "noncurrent_lease_liabilities"
    if "리스부채" in normalized:
        return "lease_liabilities"
    if "단기차입금" in normalized:
        return "short_term_borrowings"
    if "유동성장기차입금" in normalized or "유동성장기부채" in normalized:
        return "current_long_term_borrowings"
    if "장기차입금" in normalized:
        return "long_term_borrowings"
    if "미지급배당금" in normalized:
        return "dividends_payable"
    if "임대보증금" in normalized and ("유동" in normalized or "유동성" in normalized) and "비유동" not in normalized:
        return "current_rental_deposits"
    if "비유동" in normalized and "임대보증금" in normalized:
        return "noncurrent_rental_deposits"
    if "임대보증금" in normalized:
        return "rental_deposits"
    if "사채" in normalized:
        return "bonds"
    if "차입금" in normalized:
        return "borrowings"
    return None


def _receivable_account_key(label: str) -> str | None:
    normalized = compact(label)
    if "매출채권" in normalized:
        return "trade_receivables"
    if "단기미수금" in normalized:
        return "short_term_other_receivables"
    if "장기미수금" in normalized:
        return "long_term_other_receivables"
    if "단기미수수익" in normalized:
        return "short_term_accrued_income"
    if "장기미수수익" in normalized:
        return "long_term_accrued_income"
    if "단기대여금" in normalized:
        return "short_term_loans"
    if "장기대여금" in normalized:
        return "long_term_loans"
    if "장기보증금" in normalized:
        return "long_term_deposits"
    if "단기보증금" in normalized:
        return "short_term_deposits"
    return None


def _inventory_account_key(label: str) -> str | None:
    normalized = compact(label)
    if not normalized:
        return None
    if "순감액" in normalized or "평가손실" in normalized or "대체" in normalized:
        return None
    if "재고자산" in normalized and any(alias in normalized for alias in ("합계", "총", "유동", "비유동")):
        return "inventories"
    if normalized in {"합계", "총계", "재고자산"}:
        return "inventories"
    if "상품" in normalized:
        return "inventory_goods"
    if "제품" in normalized:
        return "inventory_finished_goods"
    if "재공품" in normalized or "반제품" in normalized:
        return "inventory_work_in_process"
    if "원재료" in normalized or "저장품" in normalized:
        return "inventory_raw_materials"
    if "미착품" in normalized or "운송중" in normalized:
        return "inventory_in_transit"
    if "외주가공" in normalized:
        return "inventory_outsourced_processing"
    if "용지" in normalized:
        return "inventory_land"
    if "기타" in normalized and "재고" in normalized:
        return "other_inventories"
    return None


def _inventory_row_label(row: list[str]) -> str:
    if len(row) >= 2:
        primary = compact(row[0])
        secondary = compact(row[1])
        if (
            primary
            and secondary
            and primary != secondary
            and secondary not in {"소계", "합계", "총계"}
            and _inventory_account_key(row[1]) is not None
        ):
            return row[1]
    return row[0]


def _loss_allowance_account_columns(rows: list[list[str]]) -> list[tuple[int, str]]:
    if not _has_loss_allowance_measure_row(rows):
        return []
    for row in rows[:4]:
        mapped = [
            (idx, account_key)
            for idx, label in enumerate(row)
            if (account_key := _loss_allowance_account_key(label)) is not None
        ]
        if mapped:
            return mapped
    return []


def _has_loss_allowance_measure_row(rows: list[list[str]]) -> bool:
    return any(any("손상차손누계액" in compact(cell) for cell in row) for row in rows[:4])


def _loss_allowance_account_key(label: str) -> str | None:
    normalized = compact(label)
    if "매출채권" in normalized:
        return "trade_receivables_loss_allowance"
    if "미수금" in normalized:
        return "other_receivables_loss_allowance"
    if "대여금" in normalized:
        return "loans_loss_allowance"
    if "보증금" in normalized:
        return "deposits_loss_allowance"
    return None


def _loss_allowance_role(label: str) -> str | None:
    normalized = compact(label)
    if "기초손실충당금" in normalized or "기초금융자산" in normalized:
        return "beginning"
    if "기말손실충당금" in normalized or "기말금융자산" in normalized:
        return "ending"
    if any(
        alias in normalized
        for alias in (
            "기대신용손실",
            "손실충당금전입",
            "환입액",
            "제각",
            "제거에따른감소",
            "외화환산에따른증가",
            "기타변동에따른증가",
            "매각예정대체",
            "기타",
        )
    ):
        return "signed_movement"
    return None
