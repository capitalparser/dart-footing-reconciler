"""Amount parsing for DART-style financial tables."""

from __future__ import annotations

import re

_DIGIT_RE = re.compile(r"\d")


def parse_amount(value: str | None) -> int | None:
    """Parse a Korean DART report amount cell.

    DART tables commonly use commas, parentheses, triangle signs, dashes,
    annotations, and unit text in the same cell. This parser intentionally
    returns integers in the displayed table unit, rather than scaling by
    Korean units such as thousand won.
    """
    if value is None:
        return None

    text = (
        value.replace("\xa0", " ")
        .replace("&nbsp;", " ")
        .replace("−", "-")
        .replace("△", "-")
        .strip()
    )
    if not text or text in {"-", "－", "—"}:
        return None

    negative = False
    if "(" in text and ")" in text:
        negative = True
    if text.startswith("-"):
        negative = True

    if not _DIGIT_RE.search(text):
        return None

    digits = re.sub(r"[^0-9]", "", text)
    if not digits:
        return None

    amount = int(digits)
    return -amount if negative else amount
