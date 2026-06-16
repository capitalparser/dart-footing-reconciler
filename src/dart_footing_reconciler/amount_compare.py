"""Amount comparison helpers for displayed financial statement precision."""

from __future__ import annotations


#: Default display step assumed when the caller does not know the disclosure
#: unit. Korean note tables are most often rounded from a thousand-won source.
DEFAULT_DISPLAY_UNIT = 1_000
#: A loose display-rounding tolerance only makes sense once the balance is much
#: larger than the display step. We require the balance to be at least this many
#: display steps (≈0.1% relative bound) before absorbing sub-unit differences.
DISPLAY_UNIT_MATERIALITY_RATIO = 1_000

# Backwards-compatible aliases (1,000-won source assumption: gate 1M, tol 999).
DISPLAY_UNIT_ROUNDING_THRESHOLD = DEFAULT_DISPLAY_UNIT * DISPLAY_UNIT_MATERIALITY_RATIO
DISPLAY_UNIT_ROUNDING_TOLERANCE = DEFAULT_DISPLAY_UNIT - 1


def display_unit_tolerance(
    expected: int | None,
    actual: int | None,
    base_tolerance: int,
    *,
    display_unit: int = DEFAULT_DISPLAY_UNIT,
) -> int:
    """Return comparison tolerance including sub-display-unit rounding.

    Statement-to-note checks compare statement KRW amounts with note amounts
    disclosed in KRW but rounded from a coarser source table (천원, 백만원 …).
    A difference below one display step is presentation precision, not a
    reconciliation gap — the note physically cannot show finer detail. ``display_unit``
    is that step in KRW (e.g. 1,000,000 for a 백만원 note); pass the note's
    ``unit_multiplier``. The loose band only applies to balances at least
    :data:`DISPLAY_UNIT_MATERIALITY_RATIO` display steps large, so small-unit
    metrics such as EPS stay on the explicit caller tolerance.
    """
    if expected is None or actual is None:
        return base_tolerance
    if display_unit <= 1:
        return base_tolerance
    materiality_gate = display_unit * DISPLAY_UNIT_MATERIALITY_RATIO
    if min(abs(expected), abs(actual)) >= materiality_gate:
        return max(base_tolerance, display_unit - 1)
    return base_tolerance


def amounts_agree(
    expected: int,
    actual: int,
    base_tolerance: int,
    *,
    display_unit: int = DEFAULT_DISPLAY_UNIT,
) -> bool:
    return abs(actual - expected) <= display_unit_tolerance(
        expected, actual, base_tolerance, display_unit=display_unit
    )
