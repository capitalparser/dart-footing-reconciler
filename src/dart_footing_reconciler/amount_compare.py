"""Amount comparison helpers for displayed financial statement precision."""

from __future__ import annotations


DISPLAY_UNIT_ROUNDING_THRESHOLD = 1_000_000
DISPLAY_UNIT_ROUNDING_TOLERANCE = 999


def display_unit_tolerance(expected: int | None, actual: int | None, base_tolerance: int) -> int:
    """Return comparison tolerance including sub-thousand display rounding.

    Statement-to-note checks often compare statement KRW amounts with note
    amounts disclosed in KRW but rounded from a thousand-won source table. For
    material balances, a difference below 1,000 KRW is display precision, not a
    reconciliation gap. Small-unit metrics such as EPS stay on the explicit
    caller tolerance.
    """
    if expected is None or actual is None:
        return base_tolerance
    if min(abs(expected), abs(actual)) >= DISPLAY_UNIT_ROUNDING_THRESHOLD:
        return max(base_tolerance, DISPLAY_UNIT_ROUNDING_TOLERANCE)
    return base_tolerance


def amounts_agree(expected: int, actual: int, base_tolerance: int) -> bool:
    return abs(actual - expected) <= display_unit_tolerance(expected, actual, base_tolerance)
