import pytest

from dart_footing_reconciler.amounts import (
    FOOTNOTE_MARKER_RE,
    parse_amount,
    strip_footnote_markers,
)


def test_parse_amount_handles_korean_report_number_formats() -> None:
    assert parse_amount("1,234") == 1234
    assert parse_amount("(1,234)") == -1234
    assert parse_amount("△1,234") == -1234
    assert parse_amount("-") is None
    assert parse_amount("") is None


def test_parse_amount_ignores_unit_annotations() -> None:
    assert parse_amount("1,234천원") == 1234
    assert parse_amount("  ( 9,876 ) ") == -9876


# ---------------------------------------------------------------------------
# 말주기 마커 포함 셀 — parse_amount 버그픽스 검증
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cell,expected", [
    # (*N) 형태 — 기존 버그: (*1) → 음수 + 마커 숫자 합산
    ("1,234(*1)", 1234),
    ("1,234(*12)", 1234),
    ("(*1)", None),                   # 마커만 → None
    # (주N) 형태
    ("1,234(주1)", 1234),
    ("9,876(주12)", 9876),
    ("(주3)", None),                  # 마커만 → None
    # [주N] 형태
    ("1,234[주1]", 1234),
    ("5,000[주 2]", 5000),
    # 원문자 형태 — 금액 파싱에는 영향 없지만 레이블 클리닝에 사용
    ("①", None),
    # 마커 + 음수 — 실제 음수 셀에 마커가 붙은 경우
    ("(1,234)(*1)", -1234),
    ("(1,234)(주1)", -1234),
    # 여러 마커 연속
    ("1,234(*1)(*2)", 1234),
])
def test_parse_amount_strips_footnote_markers(cell: str, expected: int | None) -> None:
    assert parse_amount(cell) == expected


# ---------------------------------------------------------------------------
# strip_footnote_markers 직접 검증
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    # (*N)
    ("기초(*1)", "기초"),
    ("1,234(*12)", "1,234"),
    # (주N)
    ("유형자산(주1)", "유형자산"),
    ("(주 3)", ""),
    # [주N]
    ("Clean H2 Infra Fund [주1]", "Clean H2 Infra Fund"),
    # 주N 단독 (주석N 과 구별)
    ("주1", ""),
    ("주 2", ""),
    # 주석N 은 제거하지 않음
    ("주석35 참조", "주석35 참조"),
    # 원문자 — strip()으로 선행 공백 제거됨
    ("① 당기", "당기"),
    ("②", ""),
    # 마커 없음 → 변경 없음
    ("유형자산", "유형자산"),
    ("1,234", "1,234"),
    ("(1,234)", "(1,234)"),           # 음수 괄호 — 제거하지 않음
    # 복합 마커
    ("기초(*1)(주2)", "기초"),
])
def test_strip_footnote_markers(text: str, expected: str) -> None:
    assert strip_footnote_markers(text) == expected


def test_footnote_marker_re_is_compiled() -> None:
    """FOOTNOTE_MARKER_RE 가 공개 API로 노출되는지 확인."""
    assert FOOTNOTE_MARKER_RE is not None
    assert FOOTNOTE_MARKER_RE.pattern  # 비어있지 않은 패턴
