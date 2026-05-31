"""Semantic helpers for company-specific DART table layouts."""

from __future__ import annotations

import re

from dart_footing_reconciler.amounts import parse_amount


def compact(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def current_period_columns(headers: list[str]) -> list[int]:
    explicit = [
        idx
        for idx, header in enumerate(headers)
        if compact(header) in {"당기", "당기말", "당년도", "당해", "당기말현재", "당기현재"}
    ]
    if explicit:
        return explicit
    fiscal_columns = fiscal_period_columns(headers)
    if not fiscal_columns:
        return []
    current_period = max(period for _, period in fiscal_columns)
    return [idx for idx, period in fiscal_columns if period == current_period]


def prior_period_columns(headers: list[str]) -> list[int]:
    explicit = [
        idx
        for idx, header in enumerate(headers)
        if compact(header) in {"전기", "전기말", "전년도", "전기말현재", "전기현재"}
    ]
    if explicit:
        return explicit
    fiscal_columns = fiscal_period_columns(headers)
    periods = sorted({period for _, period in fiscal_columns}, reverse=True)
    if len(periods) < 2:
        return []
    prior_period = periods[1]
    return [idx for idx, period in fiscal_columns if period == prior_period]


def fiscal_period_columns(headers: list[str]) -> list[tuple[int, int]]:
    columns: list[tuple[int, int]] = []
    for idx, header in enumerate(headers):
        match = re.search(r"제\s*(\d+)\s*기", header)
        if match is not None:
            columns.append((idx, int(match.group(1))))
    return columns


def amount_from_current_period(row: list[str], headers: list[str]) -> tuple[int | None, int | None]:
    return amount_from_columns(row, current_period_columns(headers))


def amount_from_prior_period(row: list[str], headers: list[str]) -> tuple[int | None, int | None]:
    return amount_from_columns(row, prior_period_columns(headers))


def amount_from_columns(row: list[str], columns: list[int]) -> tuple[int | None, int | None]:
    for col_idx in columns:
        if col_idx >= len(row):
            continue
        amount = parse_amount(row[col_idx])
        if amount is not None:
            return amount, col_idx
    return None, None


def row_amount_prefer_current(row: list[str], headers: list[str]) -> tuple[int | None, int | None]:
    amount, col_idx = amount_from_current_period(row, headers)
    if amount is not None and col_idx is not None:
        return amount, col_idx
    for col_idx, header in enumerate(headers):
        if col_idx < len(row) and _is_generic_amount_header(header):
            amount = parse_amount(row[col_idx])
            if amount is not None:
                return amount, col_idx
    for col_idx in range(len(row) - 1, 0, -1):
        amount = parse_amount(row[col_idx])
        if amount is not None:
            return amount, col_idx
    return None, None


def balance_amount(row: list[str], headers: list[str]) -> tuple[int | None, int | None]:
    current_columns = current_period_columns(headers)
    if len(current_columns) > 1:
        values: list[tuple[int, int]] = []
        for col_idx in current_columns:
            if col_idx >= len(row):
                continue
            amount = parse_amount(row[col_idx])
            if amount is not None:
                values.append((col_idx, amount))
        if values:
            return sum(amount for _, amount in values), values[0][0]

    for aliases in (
        ("장부금액합계", "순장부금액합계", "장부가액합계"),
        ("장부금액", "순장부금액", "장부가액"),
        ("합계",),
    ):
        for col_idx, header in enumerate(headers):
            if col_idx < len(row) and compact(header) in aliases:
                amount = parse_amount(row[col_idx])
                if amount is not None:
                    return amount, col_idx

    return row_amount_prefer_current(row, headers)


def _is_generic_amount_header(value: str) -> bool:
    normalized = compact(value)
    return any(alias in normalized for alias in ("기말", "합계", "장부금액", "장부가액", "금액"))
