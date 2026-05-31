"""Amount parsing for DART-style financial tables."""

from __future__ import annotations

import re

_DIGIT_RE = re.compile(r"\d")

# ---------------------------------------------------------------------------
# 말주기 마커 (인라인 셀 주석 참조) 패턴
# ---------------------------------------------------------------------------
# 코퍼스(run_2026-05-27-hundred-v82, 100개 보고서) 전수 조사 결과:
#   (*N)   : 가장 일반적 — (*1) 1,510건, (*2) 837건 등
#   (주N)  : 동등하게 일반적 — (주1) 1,312건, (주2) 440건 등
#   [주N]  : 괄호 변형 — [주1] 14건, [주2] 12건
#   주N    : 단독 형태 — 주1 1,460건 ('주석N'에서는 주 뒤에 바로 숫자가 오지 않아 안전)
#   ①②... : 원문자 — ① 771건, ② 759건 등
#
# 제외 패턴:
#   注N     : 코퍼스 미발견
#   (N)    : 과도하게 모호함 — '(1,234)' 음수 표기와 충돌
#   *N)    : (*N)의 부분 문자열이므로 별도 패턴 불필요
#
# 중요: 이 패턴들을 금액 파싱 전에 제거해야 다음 오류를 방지함:
#   parse_amount("1,234(*1)") → (*) 때문에 음수로 잘못 처리되고
#                               마커 숫자 1이 금액에 합산되는 버그
FOOTNOTE_MARKER_RE = re.compile(
    r"\(\*\d+\)"                            # (*1), (*12)
    r"|\(주\s*\d+\)"                        # (주1), (주12)
    r"|\[주\s*\d+\]"                        # [주1], [주2]
    r"|(?<!석)주\s*\d+"                     # 주1, 주2 단독 (주석N 제외: 주 뒤가 아닌 석 뒤)
    r"|[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]",  # 원문자
    re.UNICODE,
)


def strip_footnote_markers(text: str) -> str:
    """셀 텍스트에서 인라인 말주기 마커를 제거하고 여백을 정리."""
    return FOOTNOTE_MARKER_RE.sub("", text).strip()


def parse_amount(value: str | None) -> int | None:
    """Parse a Korean DART report amount cell.

    DART tables commonly use commas, parentheses, triangle signs, dashes,
    annotations, and unit text in the same cell. This parser intentionally
    returns integers in the displayed table unit, rather than scaling by
    Korean units such as thousand won.

    말주기 마커(예: (*1), (주2), ①)는 금액 파싱 전에 자동으로 제거됨.
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

    # 말주기 마커 제거 — 음수 감지 전에 수행해야 (*1), (주N) 오탐을 막을 수 있음
    text = strip_footnote_markers(text)
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
