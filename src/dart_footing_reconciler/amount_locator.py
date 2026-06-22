"""Canonical Amount Locator — single arbiter for cell selection.

SCAFFOLD (interface + signatures only). Implementation is handed to Codex per
``docs/superpowers/specs/2026-06-21-canonical-amount-locator.md``,
``docs/adr/0008-canonical-amount-locator.md``, and the cross-model review
corrections in ``docs/adr/0009-locator-review-findings.md``.

This module answers exactly one question:

    "which cell carries the <Target Amount Role> amount for <Core Account>
     in <this note table>?"

It is the single source of truth for *cell selection*. It does NOT classify
accounts (``taxonomy``), does NOT run arithmetic (``checks_*``), and does NOT
choose which of several located note amounts to pair to a statement line — that
is ``checks_fs_note._select_note_hit_by_label`` (the B-2a balance-row filter),
which stays in the check layer (ADR-0009 F2). The locator's real wins are
**B-5** (`net_carrying_amount` cell) and **B-2b** (`current_/noncurrent_portion`
cell); B-2a/B-4 stay check-layer pairing decisions that merely benefit from
cleaner located cells.

Three outcomes (ADR-0009 F8):
- ``LocatedAmount`` — a cell was selected with confidence.
- ``Abstain``       — tried but ambiguous → caller emits ``parse_uncertain``.
- ``NotApplicable`` — the role/account does not apply to this table → caller
                      emits ``not_tested`` (honest coverage, not abstention).

Migration is strangler-fig: ship UNWIRED first (Phase 1, corpus unchanged), then
route ``reconciliation_inputs`` / ``taxonomy._generic_note_row_amount`` /
``verification_candidates`` one path per corpus-gated phase.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING, Callable

from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.label_resolver import PARSE_UNCERTAIN_REASONS
from dart_footing_reconciler.layout_variants import classify_layout
from dart_footing_reconciler.orientation import detect_orientation

if TYPE_CHECKING:  # type-only references; avoid import cycles
    from dart_footing_reconciler.document import ReportTable
    from dart_footing_reconciler.layout_variants import LayoutClassification
    from dart_footing_reconciler.note_inventory import NoteTableInventoryItem
    from dart_footing_reconciler.orientation import TableOrientation


class TargetAmountRole(Enum):
    """Caller verification intent — a closed vocabulary (CONTEXT.md, ADR-0008).

    Orthogonal to the three role vocabularies of ADR-0006 §S2 (movement role /
    AccountRole / orientation groups); it is *composed from* them, not merged
    (orthogonality guarded by test, ADR-0009 F8). Adding a value requires an ADR
    amendment.
    """

    PERIOD_END_BALANCE = "period_end_balance"      # 기말 잔액 (note_to_bs)
    NET_CARRYING_AMOUNT = "net_carrying_amount"     # 순장부금액 (B-5 family)
    CASH_LIKE_MOVEMENT = "cash_like_movement"       # 현금 유발 증감 (note_to_cf)
    DISCLOSED_TOTAL = "disclosed_total"             # 공시 합계/소계 (Footing internal)
    EXPENSE_ALLOCATION = "expense_allocation"       # 비용 배분 (note_to_pl)
    CURRENT_PORTION = "current_portion"             # 유동분 (B-2b level-aware)
    NONCURRENT_PORTION = "noncurrent_portion"       # 비유동분 (B-2b level-aware)


@dataclass(frozen=True)
class LocatedAmount:
    """A confidently selected amount, with every contributing cell's source.

    For a single-cell result, ``(row_index, col_index)`` is the cell and
    ``component_sources`` is empty. For a category-matrix row-sum (ADR-0009 F4),
    ``amount`` is the sum, ``(row_index, col_index)`` is the anchor (the summary
    row), and ``component_sources`` lists every summed cell's Source Location.
    """

    account_key: str
    role: TargetAmountRole
    row_index: int
    col_index: int
    raw_amount: int                      # before unit scaling
    unit_multiplier: int
    amount: int                          # raw_amount * unit_multiplier (or the row sum)
    confidence: float                    # [0.0, 1.0]
    source: str                          # anchor Source Location (reconciliation_inputs._source format)
    component_sources: tuple[str, ...]   # () for single-cell; each summed cell for row-sum
    evidence: tuple[str, ...]            # row label, column header, archetype key, strategy id


@dataclass(frozen=True)
class Abstain:
    """Tried but ambiguous → caller emits ``parse_uncertain`` with this code.

    ``reason_code`` MUST be in PARSE_UNCERTAIN_REASONS (the PR #12 reason-code
    instrumentation expects it). Use for tried-but-uncertain cases only:
    AMBIGUOUS_MULTIPLE / COLUMN_NOT_DETECTED / LOW_CONFIDENCE_MATCH /
    AMOUNT_PARSE_FAILED. Role-inapplicable is NOT an Abstain — see NotApplicable.
    """

    account_key: str
    role: TargetAmountRole
    reason_code: str           # ∈ label_resolver.PARSE_UNCERTAIN_REASONS
    detail: str                # free Korean text, human-readable

    def __post_init__(self) -> None:
        if self.reason_code not in PARSE_UNCERTAIN_REASONS:
            raise ValueError(
                f"reason_code {self.reason_code!r} not in PARSE_UNCERTAIN_REASONS"
            )


@dataclass(frozen=True)
class NotApplicable:
    """The role/account does not apply to this table → caller emits ``not_tested``.

    Distinct from Abstain (ADR-0009 F8): this is honest coverage ("no applicable
    check ran"), not a failed attempt. E.g. asking ``cash_like_movement`` of a
    pure balance table, or ``net_carrying_amount`` of a non-asset table.
    """

    account_key: str
    role: TargetAmountRole
    detail: str                # why the role does not apply


LocateResult = LocatedAmount | Abstain | NotApplicable


@dataclass(frozen=True)
class _LocateContext:
    item: NoteTableInventoryItem
    table: ReportTable
    account_key: str
    role: TargetAmountRole
    layout: LayoutClassification
    orientation: TableOrientation
    scope: str | None
    expected_amount: int | None

# A per-(archetype, role) cell-selection strategy: returns a LocateResult.
# The strategy registry is the SSOT for "성격마다 파싱"; locate() is a thin
# dispatcher over it. Codex fills the registry per spec §3 AFTER recording the
# acceptance fixtures' actual classify_layout keys (Phase 0.5, ADR-0009 F3).
CellStrategy = Callable[[_LocateContext], LocateResult]

_LOW_CONFIDENCE_FLOOR = 0.5
_PHASE1_UNIMPLEMENTED_ROLES = (
    TargetAmountRole.CURRENT_PORTION,
    TargetAmountRole.NONCURRENT_PORTION,
)
_ORIENTATION_EXEMPT_LAYOUT_KEYS = ("asset_investment_property_simple_net",)
_SUPPORTED_ORIENTATION_KEYS = (
    "column_oriented",
    "mixed",
    "period_oriented",
    "row_oriented",
)


def locate(
    item: NoteTableInventoryItem,
    table: ReportTable,
    account_key: str,
    role: TargetAmountRole,
    *,
    layout: LayoutClassification | None = None,
    orientation: TableOrientation | None = None,
    scope: str | None = None,
    expected_amount: int | None = None,
) -> LocatedAmount | Abstain | NotApplicable:
    """Locate the cell(s) for ``role`` of ``account_key`` in ``table``.

    Contract (see spec §2; ADR-0009 corrections):
    - ``item`` (NoteTableInventoryItem) carries title/headers/row_labels, which
      ``layout_variants.classify_layout`` and ``orientation.detect_orientation``
      require — a bare ReportTable cannot produce them (ADR-0009 F1). ``layout``/
      ``orientation`` are reused if passed (wired callers already hold them),
      else derived from ``item``.
    - ``scope`` ("consolidated"|"separate") *drives column selection* for
      mirror-column tables, not merely confidence (ADR-0009 F6).
    - ``expected_amount`` is an optional tie-breaker among structurally-valid
      candidates ONLY — never used to fabricate a cell (ADR-0009 F5). Taxonomy's
      amount-validated path passes it in Phase 3.
    - Returns ``LocatedAmount`` only when a cell is selected with confidence;
      ``Abstain`` on ambiguity; ``NotApplicable`` when the role does not apply.
      Never fabricates a cell.

    Implementation: Codex, per spec §3-§5 and ADR-0009. This scaffold defines the
    interface only.
    """
    resolved_layout = layout or classify_layout(item)
    if orientation is None:
        orientation = detect_orientation(headers=item.headers, row_labels=item.row_labels)

    if _is_prior_period_table(item.heading):
        return NotApplicable(
            account_key,
            role,
            "prior-period mirror table; current-period locator does not select cells",
        )
    if _has_mixed_unit_rows(table):
        return Abstain(
            account_key,
            role,
            "AMOUNT_PARSE_FAILED",
            "row-level unit markers are mixed inside one table",
        )

    if role in _PHASE1_UNIMPLEMENTED_ROLES:
        return Abstain(
            account_key,
            role,
            "COLUMN_NOT_DETECTED",
            f"role {role.value} is registered but not implemented in locator Phase 1",
        )

    strategy = _STRATEGIES.get((resolved_layout.key, role))
    if strategy is None:
        if _is_low_confidence_asset_attempt(resolved_layout, table, account_key, role):
            return Abstain(
                account_key,
                role,
                "LOW_CONFIDENCE_MATCH",
                f"layout confidence {resolved_layout.confidence:.2f} is below locator floor",
            )
        return NotApplicable(
            account_key,
            role,
            f"role {role.value} is not applicable to layout {resolved_layout.key}",
        )

    if not _orientation_supported(resolved_layout.key, orientation):
        return Abstain(
            account_key,
            role,
            "COLUMN_NOT_DETECTED",
            f"orientation {orientation.key} is unsupported for layout {resolved_layout.key}",
        )

    ctx = _LocateContext(
        item=item,
        table=table,
        account_key=account_key,
        role=role,
        layout=resolved_layout,
        orientation=orientation,
        scope=scope,
        expected_amount=expected_amount,
    )
    result = strategy(ctx)
    if (
        isinstance(result, LocatedAmount)
        and resolved_layout.confidence < _LOW_CONFIDENCE_FLOOR
    ):
        return _abstain(
            ctx,
            "LOW_CONFIDENCE_MATCH",
            f"layout confidence {resolved_layout.confidence:.2f} is below locator floor",
        )
    return result


def _orientation_supported(
    layout_key: str,
    orientation: TableOrientation,
) -> bool:
    if orientation.key in _SUPPORTED_ORIENTATION_KEYS:
        return True
    return layout_key in _ORIENTATION_EXEMPT_LAYOUT_KEYS and orientation.key == "unknown"


def _is_low_confidence_asset_attempt(
    layout: LayoutClassification,
    table: ReportTable,
    account_key: str,
    role: TargetAmountRole,
) -> bool:
    if layout.confidence >= _LOW_CONFIDENCE_FLOOR:
        return False
    if role not in {
        TargetAmountRole.NET_CARRYING_AMOUNT,
        TargetAmountRole.PERIOD_END_BALANCE,
    }:
        return False
    return any(_row_has_account(row, account_key) for row in table.rows[1:])


def _locate_asset_net_carrying(ctx: _LocateContext) -> LocateResult:
    row_idx = _select_asset_total_or_ending_row(ctx)
    if isinstance(row_idx, Abstain):
        return row_idx

    row = ctx.table.rows[row_idx]
    if _is_category_matrix_row(ctx.table.rows, row_idx, ctx.account_key):
        component_cols = _category_component_columns(ctx.table.rows, row_idx, ctx.account_key)
        if not component_cols:
            return _abstain(
                ctx,
                "COLUMN_NOT_DETECTED",
                "category-matrix component columns not detected",
            )
        components: list[tuple[int, int]] = []
        for col_idx in component_cols:
            if col_idx >= len(row):
                continue
            amount = parse_amount(row[col_idx])
            if amount is not None:
                components.append((col_idx, amount))
        if not components:
            return _abstain(ctx, "AMOUNT_PARSE_FAILED", "category row amounts not parseable")
        anchor_col = _family_total_column(ctx.table.rows, ctx.account_key)
        anchor_amount = (
            parse_amount(row[anchor_col])
            if anchor_col is not None and anchor_col < len(row)
            else None
        )
        raw_amount = sum(amount for _, amount in components)
        if anchor_amount is not None and raw_amount != anchor_amount:
            if abs(raw_amount - anchor_amount) <= 1:
                raw_amount = anchor_amount
            else:
                return _abstain(
                    ctx,
                    "COLUMN_NOT_DETECTED",
                    "category component sum does not match family-total anchor",
                )
        if anchor_col is None or anchor_col >= len(row) or anchor_amount is None:
            anchor_col = components[0][0]
        return _located(
            ctx,
            row_idx,
            anchor_col,
            raw_amount,
            "category_matrix_row_sum",
            component_sources=tuple(
                _source(ctx.item, ctx.table.index, row_idx, col_idx)
                for col_idx, _ in components
            ),
        )

    col_candidates = _net_carrying_columns(
        ctx.table.rows,
        ctx.account_key,
        ctx.scope,
        prefer_family_total=ctx.layout.key == "asset_investment_property_simple_net",
    )
    if not col_candidates:
        return _abstain(ctx, "COLUMN_NOT_DETECTED", "net carrying column not detected")
    if len(col_candidates) > 1:
        return _abstain(ctx, "AMBIGUOUS_MULTIPLE", "multiple net carrying columns detected")
    col_idx = col_candidates[0]
    if col_idx >= len(row):
        return _abstain(ctx, "COLUMN_NOT_DETECTED", "net carrying column outside row")
    raw_amount = parse_amount(row[col_idx])
    if raw_amount is None:
        return _abstain(ctx, "AMOUNT_PARSE_FAILED", "net carrying amount not parseable")
    return _located(ctx, row_idx, col_idx, raw_amount, "asset_net_carrying_cell")


def _locate_asset_period_end(ctx: _LocateContext) -> LocateResult:
    row_idx = _select_asset_total_or_ending_row(ctx)
    if isinstance(row_idx, Abstain):
        return row_idx
    col_candidates = _ending_columns(ctx.table.rows, ctx.scope)
    if not col_candidates:
        return _abstain(ctx, "COLUMN_NOT_DETECTED", "ending column not detected")
    if len(col_candidates) > 1:
        return _abstain(ctx, "AMBIGUOUS_MULTIPLE", "multiple ending columns detected")
    col_idx = col_candidates[0]
    row = ctx.table.rows[row_idx]
    if col_idx >= len(row):
        return _abstain(ctx, "COLUMN_NOT_DETECTED", "ending column outside row")
    raw_amount = parse_amount(row[col_idx])
    if raw_amount is None:
        return _abstain(ctx, "AMOUNT_PARSE_FAILED", "ending amount not parseable")
    return _located(ctx, row_idx, col_idx, raw_amount, "asset_period_end_cell")


def _locate_rollforward_net(ctx: _LocateContext) -> LocateResult:
    row_idx = _select_asset_total_or_ending_row(ctx)
    if isinstance(row_idx, Abstain):
        return row_idx
    col_candidates = _ending_columns(ctx.table.rows, ctx.scope)
    if not col_candidates:
        return _abstain(ctx, "COLUMN_NOT_DETECTED", "ending column not detected")
    if len(col_candidates) > 1:
        return _abstain(ctx, "AMBIGUOUS_MULTIPLE", "multiple ending columns detected")
    col_idx = col_candidates[0]
    row = ctx.table.rows[row_idx]
    if col_idx >= len(row):
        return _abstain(ctx, "COLUMN_NOT_DETECTED", "ending column outside row")
    raw_amount = parse_amount(row[col_idx])
    if raw_amount is None:
        return _abstain(ctx, "AMOUNT_PARSE_FAILED", "ending amount not parseable")
    return _located(ctx, row_idx, col_idx, raw_amount, "rollforward_ending_cell")


def _locate_lease_period_end(ctx: _LocateContext) -> LocateResult:
    row_idx = _select_account_total_row(ctx, "lease liability total row")
    if isinstance(row_idx, Abstain):
        return row_idx
    row = ctx.table.rows[row_idx]
    col_candidates = _amount_columns(ctx.table.rows, row_idx, ctx.scope)
    if not col_candidates:
        return _abstain(ctx, "COLUMN_NOT_DETECTED", "lease liability amount column absent")
    if len(col_candidates) > 1:
        return _abstain(ctx, "AMBIGUOUS_MULTIPLE", "multiple lease liability amount columns")
    col_idx = col_candidates[0]
    raw_amount = parse_amount(row[col_idx])
    if raw_amount is None:
        return _abstain(ctx, "AMOUNT_PARSE_FAILED", "lease liability amount not parseable")
    return _located(ctx, row_idx, col_idx, raw_amount, "lease_period_end_total")


def _located(
    ctx: _LocateContext,
    row_idx: int,
    col_idx: int,
    raw_amount: int,
    strategy_id: str,
    *,
    component_sources: tuple[str, ...] = (),
) -> LocatedAmount:
    source = _source(ctx.item, ctx.table.index, row_idx, col_idx)
    return LocatedAmount(
        account_key=ctx.account_key,
        role=ctx.role,
        row_index=row_idx,
        col_index=col_idx,
        raw_amount=raw_amount,
        unit_multiplier=ctx.table.unit_multiplier,
        amount=raw_amount * ctx.table.unit_multiplier,
        confidence=min(0.99, max(0.0, ctx.layout.confidence)),
        source=source,
        component_sources=component_sources,
        evidence=(
            _row_label(ctx.table.rows, row_idx),
            _column_label(ctx.table.rows, col_idx),
            ctx.layout.key,
            strategy_id,
        ),
    )


def _abstain(ctx: _LocateContext, reason_code: str, detail: str) -> Abstain:
    return Abstain(ctx.account_key, ctx.role, reason_code, detail)


def _source(item: NoteTableInventoryItem, table_index: int, row_idx: int, col_idx: int) -> str:
    section = item.source.split("/table:", 1)[0]
    return f"{section}/table:{table_index}/row:{row_idx}/col:{col_idx}"


def _row_label(rows: list[list[str]], row_idx: int) -> str:
    if row_idx >= len(rows) or not rows[row_idx]:
        return ""
    labels = [cell for cell in rows[row_idx][:2] if cell and parse_amount(cell) is None]
    return " / ".join(dict.fromkeys(labels))


def _column_label(rows: list[list[str]], col_idx: int) -> str:
    labels = [
        row[col_idx]
        for row in _header_rows(rows)
        if col_idx < len(row) and row[col_idx] and parse_amount(row[col_idx]) is None
    ]
    return " / ".join(dict.fromkeys(labels))


def _select_asset_total_or_ending_row(ctx: _LocateContext) -> int | Abstain:
    total_rows = _account_total_row_candidates(ctx.table.rows, ctx.account_key)
    if not total_rows and _item_has_account(ctx.item, ctx.account_key):
        total_rows = [
            row_idx
            for row_idx, row in enumerate(ctx.table.rows[1:], start=1)
            if _row_is_generic_total(row) and _row_has_amount(row)
        ]
    if len(total_rows) == 1:
        return total_rows[0]
    if len(total_rows) > 1:
        ending_matches = [
            row_idx for row_idx in total_rows if _row_has_ending(ctx.table.rows[row_idx])
        ]
        if len(ending_matches) == 1:
            return ending_matches[0]
        return _abstain(ctx, "AMBIGUOUS_MULTIPLE", "multiple asset total rows detected")

    ending_rows = [
        row_idx
        for row_idx, row in enumerate(ctx.table.rows[1:], start=1)
        if _row_has_account(row, ctx.account_key) and _row_has_ending(row)
    ]
    if not ending_rows and _item_has_account(ctx.item, ctx.account_key):
        ending_rows = [
            row_idx
            for row_idx, row in enumerate(ctx.table.rows[1:], start=1)
            if _row_has_ending(row) and _row_has_amount(row)
        ]
    if len(ending_rows) == 1:
        return ending_rows[0]
    if len(ending_rows) > 1:
        return _abstain(ctx, "AMBIGUOUS_MULTIPLE", "multiple asset ending rows detected")
    return _abstain(ctx, "COLUMN_NOT_DETECTED", "asset total or ending row absent")


def _select_account_total_row(ctx: _LocateContext, label: str) -> int | Abstain:
    rows = _account_total_row_candidates(ctx.table.rows, ctx.account_key)
    if len(rows) == 1:
        return rows[0]
    if len(rows) > 1:
        return _abstain(ctx, "AMBIGUOUS_MULTIPLE", f"multiple {label}s detected")
    return _abstain(ctx, "COLUMN_NOT_DETECTED", f"{label} absent")


def _account_total_row_candidates(rows: list[list[str]], account_key: str) -> list[int]:
    matches: list[int] = []
    for row_idx, row in enumerate(rows[1:], start=1):
        if not _row_has_account(row, account_key):
            continue
        if _row_is_total(row, account_key) or _single_account_data_row(rows, row_idx, account_key):
            matches.append(row_idx)
    return matches


def _row_has_account(row: list[str], account_key: str) -> bool:
    normalized_cells = [_normalize(cell) for cell in row[:3] if parse_amount(cell) is None]
    aliases = _account_aliases(account_key)
    return any(any(alias in cell for alias in aliases) for cell in normalized_cells)


def _row_is_total(row: list[str], account_key: str) -> bool:
    normalized = " ".join(_normalize(cell) for cell in row[:3] if parse_amount(cell) is None)
    if "합계" in normalized or "총계" in normalized:
        return True
    return account_key == "investment_property" and normalized == "투자부동산"


def _row_is_generic_total(row: list[str]) -> bool:
    labels = [_normalize(cell) for cell in row[:3] if parse_amount(cell) is None]
    return any(label in {"합계", "총계"} for label in labels)


def _row_has_amount(row: list[str]) -> bool:
    return any(parse_amount(cell) is not None for cell in row[1:])


def _item_has_account(item: NoteTableInventoryItem, account_key: str) -> bool:
    normalized = _normalize(f"{item.title} {item.heading}")
    aliases = _account_aliases(account_key)
    return any(alias in normalized for alias in aliases)


def _single_account_data_row(
    rows: list[list[str]],
    row_idx: int,
    account_key: str,
) -> bool:
    if account_key != "investment_property":
        return False
    data_rows = [
        row
        for row in rows[1:]
        if any(parse_amount(cell) is not None for cell in row[1:])
    ]
    return len(data_rows) == 1 and rows[row_idx] == data_rows[0]


def _row_has_ending(row: list[str]) -> bool:
    return any("기말" in _normalize(cell) or "당기말" in _normalize(cell) for cell in row[:3])


def _net_carrying_columns(
    rows: list[list[str]],
    account_key: str,
    scope: str | None,
    *,
    prefer_family_total: bool = False,
) -> list[int]:
    scoped = _scope_filtered_columns(rows, range(_max_cols(_header_rows(rows))), scope)
    family_cols = sorted(
        col_idx
        for col_idx in scoped
        if col_idx > 0
        and _column_has_family_total(rows, col_idx, account_key)
        and _column_has_family_net_context(rows, col_idx)
    )
    if prefer_family_total and family_cols:
        return family_cols
    net_cols = sorted(
        col_idx
        for col_idx in scoped
        if col_idx > 0
        and _column_has_net_label(rows, col_idx)
        and not _column_has_excluded_net_label(rows, col_idx)
        and not _column_has_opening_or_prior_label(rows, col_idx)
    )
    if net_cols:
        return net_cols
    return family_cols


def _family_total_column(rows: list[list[str]], account_key: str) -> int | None:
    cols = sorted(
        col_idx
        for col_idx in range(_max_cols(_header_rows(rows)))
        if col_idx > 0
        and _column_has_family_total(rows, col_idx, account_key)
        and not _column_has_excluded_net_label(rows, col_idx)
    )
    return cols[0] if len(cols) == 1 else None


def _ending_columns(rows: list[list[str]], scope: str | None) -> list[int]:
    scoped = _scope_filtered_columns(rows, range(_max_cols(_header_rows(rows))), scope)
    return sorted(
        col_idx
        for col_idx in scoped
        if _column_has_current_ending_label(rows, col_idx)
        and not _column_has_opening_or_prior_label(rows, col_idx)
    )


def _amount_columns(rows: list[list[str]], row_idx: int, scope: str | None) -> list[int]:
    if row_idx >= len(rows):
        return []
    row = rows[row_idx]
    scoped = _scope_filtered_columns(rows, range(len(row)), scope)
    amount_cols = sorted(
        col_idx for col_idx in scoped if parse_amount(row[col_idx]) is not None
    )
    if len(amount_cols) == 1:
        return amount_cols
    generic_cols = sorted(
        col_idx
        for col_idx in amount_cols
        if any(
            part in {"공시금액", "금액", "합계", "장부금액합계"}
            for part in _column_parts(rows, col_idx)
        )
    )
    return generic_cols


def _is_category_matrix_row(
    rows: list[list[str]],
    row_idx: int,
    account_key: str,
) -> bool:
    if row_idx >= len(rows) or not _row_has_ending(rows[row_idx]):
        return False
    component_cols = _category_component_columns(rows, row_idx, account_key)
    return len(component_cols) >= 2


def _category_component_columns(
    rows: list[list[str]],
    row_idx: int,
    account_key: str,
) -> list[int]:
    if row_idx >= len(rows):
        return []
    row = rows[row_idx]
    cols: list[int] = []
    for col_idx in range(1, len(row)):
        if parse_amount(row[col_idx]) is None:
            continue
        parts = _column_parts(rows, col_idx)
        if not parts:
            continue
        if _column_has_family_total(rows, col_idx, account_key):
            continue
        if _column_has_excluded_net_label(rows, col_idx):
            continue
        if _column_has_subtotal_label(rows, col_idx):
            continue
        cols.append(col_idx)
    return sorted(cols)


def _column_has_net_label(rows: list[list[str]], col_idx: int) -> bool:
    net_aliases = {
        "합계",
        "장부금액",
        "순장부금액",
        "장부가액",
        "장부금액합계",
        "순장부금액합계",
        "장부가액합계",
    }
    return any(
        any(alias in part for alias in net_aliases)
        for part in _column_parts(rows, col_idx)
    )


def _column_has_excluded_net_label(rows: list[list[str]], col_idx: int) -> bool:
    gross_aliases = {
        "총장부금액",
        "취득원가",
        "취득원가합계",
        "기초",
        "기초장부금액",
        "전기",
        "전기말",
        "감가상각누계액",
        "감가상각누계",
        "상각누계액",
        "상각누계",
        "손상차손누계액",
        "손상차손누계",
        "정부보조금",
    }
    return any(
        any(alias in part for alias in gross_aliases)
        for part in _column_parts(rows, col_idx)
    )


def _column_has_subtotal_label(rows: list[list[str]], col_idx: int) -> bool:
    return any(
        any(alias in part for alias in ("소계", "부분합", "subtotal"))
        for part in _column_parts(rows, col_idx)
    )


def _column_has_current_ending_label(rows: list[list[str]], col_idx: int) -> bool:
    return any(
        any(alias in part for alias in ("기말", "당기말", "당기말현재"))
        for part in _column_parts(rows, col_idx)
    )


def _column_has_opening_or_prior_label(rows: list[list[str]], col_idx: int) -> bool:
    return any(
        any(alias in part for alias in ("기초", "전기", "전기말"))
        for part in _column_parts(rows, col_idx)
    )


def _column_has_family_net_context(rows: list[list[str]], col_idx: int) -> bool:
    if _column_has_excluded_net_label(rows, col_idx):
        return False
    if _column_has_net_label(rows, col_idx):
        return True
    if any(
        _column_has_excluded_net_label(rows, sibling_col)
        for sibling_col in range(_max_cols(_header_rows(rows)))
        if sibling_col != col_idx
    ):
        return True
    return any(
        _column_has_net_label(rows, sibling_col)
        and not _column_has_excluded_net_label(rows, sibling_col)
        for sibling_col in range(_max_cols(_header_rows(rows)))
    )


def _column_has_family_total(
    rows: list[list[str]],
    col_idx: int,
    account_key: str,
) -> bool:
    aliases = _family_total_aliases(account_key)
    return any(
        any(alias in part for alias in aliases)
        for part in _column_parts(rows, col_idx)
    )


def _scope_filtered_columns(
    rows: list[list[str]],
    columns: range | list[int],
    scope: str | None,
) -> list[int]:
    candidates = sorted(columns)
    if scope not in {"consolidated", "separate"}:
        return candidates
    scoped = sorted(
        col_idx
        for col_idx in candidates
        if _column_scope(rows, col_idx) == scope
    )
    any_scope_marker = any(_column_has_scope_marker(rows, col_idx) for col_idx in candidates)
    if any_scope_marker:
        return scoped
    return candidates


def _column_has_scope_marker(rows: list[list[str]], col_idx: int) -> bool:
    parts = _column_parts(rows, col_idx)
    return any(
        marker in part
        for marker in ("연결", "consolidated", "별도", "개별", "separate")
        for part in parts
    )


def _column_scope(rows: list[list[str]], col_idx: int) -> str | None:
    parts = _column_parts(rows, col_idx)
    has_consolidated = any(
        marker in part for marker in ("연결", "consolidated") for part in parts
    )
    has_separate = any(
        marker in part for marker in ("별도", "개별", "separate") for part in parts
    )
    if has_consolidated == has_separate:
        return None
    return "consolidated" if has_consolidated else "separate"


def _header_rows(rows: list[list[str]]) -> list[list[str]]:
    return rows[:4]


def _max_cols(rows: list[list[str]]) -> int:
    return max((len(row) for row in rows), default=0)


def _column_parts(rows: list[list[str]], col_idx: int) -> tuple[str, ...]:
    parts = [
        _normalize(row[col_idx])
        for row in _header_rows(rows)
        if col_idx < len(row) and row[col_idx] and parse_amount(row[col_idx]) is None
    ]
    return tuple(dict.fromkeys(part for part in parts if part))


def _account_aliases(account_key: str) -> set[str]:
    return {
        "property_plant_equipment": {"유형자산", "유형자산합계"},
        "intangible_assets": {
            "무형자산",
            "무형자산과영업권",
            "무형자산및영업권",
            "영업권이외의무형자산",
        },
        "investment_property": {"투자부동산", "투자부동산합계"},
        "lease_liabilities": {"리스부채", "리스부채합계"},
    }.get(account_key, set())


def _family_total_aliases(account_key: str) -> set[str]:
    return {
        "property_plant_equipment": {"유형자산합계", "유형자산총계"},
        "intangible_assets": {
            "무형자산합계",
            "무형자산총계",
            "무형자산과영업권합계",
            "무형자산및영업권합계",
            "영업권이외의무형자산합계",
        },
        "investment_property": {"투자부동산합계", "투자부동산총계"},
    }.get(account_key, set())


def _normalize(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def _has_mixed_unit_rows(table: ReportTable) -> bool:
    unit_markers = {
        _normalize(cell)
        for row in table.rows
        for cell in row
        if "단위" in cell and any(unit in cell for unit in ("원", "천원", "백만원", "억원"))
    }
    return len(unit_markers) > 1


def _is_prior_period_table(heading: str) -> bool:
    normalized = _normalize(heading)
    if "당기" in normalized:
        return False
    if any(
        alias in normalized
        for alias in (
            "전기대비",
            "전기비교",
            "전기말잔액포함",
            "전기말포함",
        )
    ):
        return False
    return bool(
        re.search(
            r"(^|[^0-9A-Za-z가-힣])(?:[0-9]+|[①②])?\s*전기(?:중|말)?(?!대비|비교|말잔액|말포함)(?=$|[^0-9A-Za-z가-힣])",
            heading,
        )
        or re.search(
            r"(^|[^0-9A-Za-z가-힣])전년도(?=$|[^0-9A-Za-z가-힣])",
            heading,
        )
    )


_ASSET_NET_LAYOUT_KEYS = (
    "asset_carrying_amount_total",
    "asset_cost_accumulated_grant_total",
    "asset_cost_accumulated_summary",
    "asset_measure_summary",
    "asset_component_column_summary",
    "asset_stacked_measure_summary",
    "asset_investment_property_simple_net",
)

_STRATEGIES: Mapping[tuple[str, TargetAmountRole], CellStrategy] = MappingProxyType(
    {
        **{
            (key, TargetAmountRole.NET_CARRYING_AMOUNT): _locate_asset_net_carrying
            for key in _ASSET_NET_LAYOUT_KEYS
        },
        **{
            (key, TargetAmountRole.PERIOD_END_BALANCE): _locate_asset_period_end
            for key in _ASSET_NET_LAYOUT_KEYS
        },
        ("asset_movement_columns", TargetAmountRole.NET_CARRYING_AMOUNT): (
            _locate_rollforward_net
        ),
        ("asset_movement_columns", TargetAmountRole.PERIOD_END_BALANCE): (
            _locate_rollforward_net
        ),
        (
            "asset_period_rollforward_summary",
            TargetAmountRole.NET_CARRYING_AMOUNT,
        ): _locate_rollforward_net,
        (
            "asset_period_rollforward_summary",
            TargetAmountRole.PERIOD_END_BALANCE,
        ): _locate_rollforward_net,
        (
            "lease_liability_current_noncurrent_summary",
            TargetAmountRole.PERIOD_END_BALANCE,
        ): _locate_lease_period_end,
        ("lease_liability_maturity_summary", TargetAmountRole.PERIOD_END_BALANCE): (
            _locate_lease_period_end
        ),
    }
)
