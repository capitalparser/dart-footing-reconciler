from pathlib import Path

import pytest

from dart_footing_reconciler.document import parse_full_report
from dart_footing_reconciler.narrative_evidence import build_narrative_evidence


RAW = Path("/Users/kjun/vault/01_Projects/09_dart_footing_reconciler/out")


def _dataset(company: str, relative_path: str):
    path = RAW / relative_path
    if not path.exists():
        pytest.skip(f"external DART fixture unavailable: {path}")
    return build_narrative_evidence(parse_full_report(path, company=company))


def _segment(dataset, needle: str, *, scope: str | None = None):
    matches = [
        item
        for item in dataset.segments
        if needle.replace(" ", "") in item.text.replace(" ", "")
        and (scope is None or item.source.scope == scope)
    ]
    assert matches, needle
    return matches[0]


@pytest.mark.parametrize(
    ("company", "path", "needle"),
    [
        (
            "아모레퍼시픽",
            "corpus/run_2026-06-22-nonfinancial-expansion/raw/아모레퍼시픽_2024_20250317000429.html",
            "주주총회 승인전 별도재무제표",
        ),
        (
            "POSCO홀딩스",
            "corpus/run_2026-06-22-nonfinancial-expansion/raw/POSCO홀딩스_2024_20250312001016.html",
            "주주총회 승인전 재무제표",
        ),
    ],
)
def test_approval_disclaimer_is_not_a_reconciliation_candidate(
    company: str, path: str, needle: str
):
    dataset = _dataset(company, path)
    segment = _segment(dataset, needle)

    assert segment.is_disclaimer is True
    assert not any(
        item.segment_source == segment.source.source_key
        for item in dataset.attachments
    )
    assert dataset.reconciliation_candidates_for(segment.source.source_key) == ()


@pytest.mark.parametrize(
    ("company", "path", "needle", "scope", "table_source", "confidence"),
    [
        (
            "CJ제일제당",
            "corpus/run_2026-06-22-nonfinancial-expansion/raw/CJ제일제당_2024_20250317000648.html",
            "해당 재무정보는 SCHWAN'S 그룹의 연결기준 금액",
            "consolidated",
            "note:1/table:5",
            1.0,
        ),
        (
            "대한항공",
            "corpus/run_2026-06-22-nonfinancial-expansion/raw/대한항공_2024_20250318001334.html",
            "상기 요약 경영성과는 내부거래를 제거하기 전 금액",
            "consolidated",
            "note:12/table:38",
            0.7,
        ),
        (
            "삼성SDI",
            "corpus/run_2026-06-08-statement-ties-baseline/raw/삼성sdi_2024_20250311001275.html",
            "대체 등에는 자가사용에 따라 유형자산으로 대체",
            "consolidated",
            "note:15/table:109",
            0.9,
        ),
        (
            "현대자동차",
            "corpus/run_2026-06-08-statement-ties-baseline/raw/현대자동차_2024_20250312001148.html",
            "개발비 상각비가 포함되지 아니함",
            "consolidated",
            "note:11/table:81",
            1.0,
        ),
        (
            "더존비즈온",
            "corpus/run_2026-06-08-statement-ties-baseline/raw/더존비즈온_2024_20250317001028.html",
            "우리은행 차입금 18,000,000천원",
            "separate",
            "note:16/table:278",
            0.9,
        ),
        (
            "한일시멘트",
            "corpus/run_2026-06-08-statement-ties-baseline/raw/한일시멘트_2024_20250317000951.html",
            "상기 장ㆍ단기차입금 등에 대하여 유형자산 등을 담보",
            "consolidated",
            "note:19/table:138",
            0.7,
        ),
        (
            "SK이터닉스",
            "sk_eternix/2026_q1_financial.html",
            "상기 요약 재무정보는 사업결합시 발생한 영업권",
            "consolidated",
            "note:1/table:6",
            0.7,
        ),
    ],
)
def test_table_adjacent_narrative_attaches_to_expected_real_table(
    company: str,
    path: str,
    needle: str,
    scope: str,
    table_source: str,
    confidence: float,
):
    dataset = _dataset(company, path)
    segment = _segment(dataset, needle, scope=scope)
    attachments = [
        item
        for item in dataset.attachments
        if item.segment_source == segment.source.source_key
    ]

    assert [(item.table_source, item.confidence) for item in attachments] == [
        (table_source, confidence)
    ]


def test_kepco_narrative_amount_keeps_explicit_unit_and_role():
    dataset = _dataset(
        "한국전력공사",
        "corpus/run_2026-06-22-nonfinancial-expansion/raw/한국전력공사_2024_20250318000747.html",
    )
    segment = _segment(dataset, "성공불융자 1,197백만원")
    mentions = [
        item
        for item in dataset.amount_mentions
        if item.source.source_key == segment.source.source_key
    ]

    assert [(item.amount, item.role) for item in mentions] == [
        (1_197_000_000, "borrowing_amount")
    ]


def test_hanil_cross_note_reference_is_source_backed():
    dataset = _dataset(
        "한일시멘트",
        "corpus/run_2026-06-08-statement-ties-baseline/raw/한일시멘트_2024_20250317000951.html",
    )
    segment = _segment(dataset, "상기 장ㆍ단기차입금 등에 대하여 유형자산 등을 담보")
    references = [
        item
        for item in dataset.note_references
        if item.source.source_key == segment.source.source_key
    ]

    assert [(item.note_no, item.source.scope) for item in references] == [
        ("34", "consolidated")
    ]
