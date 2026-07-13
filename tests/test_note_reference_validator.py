"""말 주기 주석 참조 검증 테스트.

커버리지:
  TC1  정상 참조 — 주석 존재 + 내용 있음 → verdict "valid"
  TC2  broken_ref — 참조 주석 번호가 실제 주석에 없음
  TC3  empty_note — 주석 존재하나 블록이 모두 비어있음
  TC4  복수 참조 — 한 말 주기에 "주석 11,13 참조" → NoteRefResult 두 개
  TC5  false positive 방지 — "주석" 키워드 없는 일반 말 주기 → 결과 없음
  TC6  다양한 패턴 통합 — 실제 DART 텍스트 패턴 추출 정확도 검증
  TC7  check_note_references — CheckResult 상태·타입·필드 검증
"""

from __future__ import annotations

import pytest

from dart_footing_reconciler.checks import MATCHED, UNEXPLAINED_GAP
from dart_footing_reconciler.checks_note_references import check_note_references
from dart_footing_reconciler.document import (
    FullReport,
    ReportBlock,
    ReportSection,
    ReportTable,
    SourceLocation,
)
from dart_footing_reconciler.note_reference_validator import (
    FOOTNOTE_MARKER_RE,
    extract_note_numbers,
    strip_footnote_markers,
    validate_all_note_refs,
    validate_note_refs_in_text,
)


# ---------------------------------------------------------------------------
# 헬퍼 팩토리
# ---------------------------------------------------------------------------

def _make_note(
    note_no: str,
    title: str,
    *,
    text: str = "",
    has_table: bool = False,
) -> ReportSection:
    """간단한 주석 섹션 생성."""
    blocks: list[ReportBlock] = []
    if text:
        blocks.append(ReportBlock("text", text, None, SourceLocation(f"note:{note_no}", 0)))
    if has_table:
        table = ReportTable(
            0,
            [["구분", "금액"], ["자산", "1,000"]],
            f"주석 {note_no} 테이블",
            SourceLocation(f"note:{note_no}", len(blocks), 0),
        )
        blocks.append(ReportBlock("table", "", table, table.location))
    return ReportSection(f"note:{note_no}", title, "note", note_no, blocks)


def _make_statement_with_footnote(footnote_text: str) -> ReportSection:
    """하단 말 주기 텍스트를 포함한 재무상태표 섹션 생성."""
    section_id = "statement:재무상태표"
    table = ReportTable(
        0,
        [["구분", "당기", "전기"], ["자산총계", "10,000", "9,000"]],
        "재무상태표",
        SourceLocation(section_id, 0, 0),
    )
    blocks = [
        ReportBlock("table", "", table, table.location),
        ReportBlock("text", footnote_text, None, SourceLocation(section_id, 1)),
    ]
    return ReportSection(section_id, "재무상태표", "statement", "", blocks)


def _make_report(
    statements: list[ReportSection] | None = None,
    notes: list[ReportSection] | None = None,
) -> FullReport:
    return FullReport(
        source="test.html",
        company="테스트",
        statements=statements or [],
        notes=notes or [],
    )


# ---------------------------------------------------------------------------
# TC1: 정상 참조 — 주석 존재 + 내용 있음
# ---------------------------------------------------------------------------

def test_valid_note_reference_returns_valid_verdict():
    note14 = _make_note("14", "관계기업투자", has_table=True)
    text = "(*2) 관계기업에서 기타포괄손익-공정가치 측정 금융자산으로 재분류하였습니다(주석 14 참조)."

    results = validate_note_refs_in_text(text, [note14], "statement:재무상태표:block1")

    assert len(results) == 1
    r = results[0]
    assert r.note_number == 14
    assert r.note_exists is True
    assert r.note_has_content is True
    assert r.verdict == "valid"
    assert r.context_match is None  # 맥락 매칭 미구현 → None


# ---------------------------------------------------------------------------
# TC2: broken_ref — 참조된 주석 번호가 주석 목록에 없음
# ---------------------------------------------------------------------------

def test_broken_reference_when_note_number_absent():
    note11 = _make_note("11", "유형자산", has_table=True)
    text = "이 금액은 주석 99 참조."  # 주석 99는 존재하지 않음

    results = validate_note_refs_in_text(text, [note11], "note:11:block0")

    assert len(results) == 1
    r = results[0]
    assert r.note_number == 99
    assert r.note_exists is False
    assert r.note_has_content is False
    assert r.verdict == "broken_ref"


# ---------------------------------------------------------------------------
# TC3: empty_note — 주석은 존재하나 내용이 모두 비어있음
# ---------------------------------------------------------------------------

def test_empty_note_when_note_exists_but_has_no_content():
    # 빈 블록 목록의 주석 (empty blocks)
    empty_note = ReportSection("note:7", "매출채권", "note", "7", [])
    text = "매출채권 손상에 대한 회계정책은 주석 7 참조."

    results = validate_note_refs_in_text(text, [empty_note], "note:2:block0")

    assert len(results) == 1
    r = results[0]
    assert r.note_number == 7
    assert r.note_exists is True
    assert r.note_has_content is False
    assert r.verdict == "empty_note"


# ---------------------------------------------------------------------------
# TC4: 복수 참조 — 한 말 주기에 여러 주석 번호
# ---------------------------------------------------------------------------

def test_multiple_note_refs_in_single_footnote():
    note11 = _make_note("11", "유형자산", has_table=True)
    note13 = _make_note("13", "리스", has_table=True)
    note32 = _make_note("32", "담보", text="담보 내역 기재")
    # 주석 99는 없음 → broken_ref 추가 케이스로도 활용
    text = "(*) 유형자산 일부가 담보로 제공되어 있습니다(주석 11,13,32 참조)."

    results = validate_note_refs_in_text(text, [note11, note13, note32], "statement:block1")

    note_numbers = sorted(r.note_number for r in results)
    assert note_numbers == [11, 13, 32]
    verdicts = {r.note_number: r.verdict for r in results}
    assert verdicts[11] == "valid"
    assert verdicts[13] == "valid"
    assert verdicts[32] == "valid"


# ---------------------------------------------------------------------------
# TC5: false positive 방지 — "주석" 키워드 없는 일반 말 주기
# ---------------------------------------------------------------------------

def test_no_results_for_plain_footnote_without_note_reference():
    note5 = _make_note("5", "현금", has_table=True)
    text = "(*) 당기 및 전기 중 사내근로복지기금 출연금이 포함되어 있습니다."  # 주석 없음

    results = validate_note_refs_in_text(text, [note5], "statement:block2")

    assert results == []


# ---------------------------------------------------------------------------
# TC6: 다양한 패턴 통합 — extract_note_numbers 정확도
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected_numbers", [
    # 명시적 참조
    ("(주석 21 참조).", [21]),
    ("주석 11,13,32 참조", [11, 13, 32]),
    ("주석 제15호 참고", [15]),
    ("주석 8번 참조", [8]),
    # 동사절 연결
    ("주석 3에서 설명하고 있습니다", [3]),
    ("신용위험 방법은 주석 4.1.2 참조", [4]),
    # 공백 없는 형태
    ("사업결합(주석35)(*1)", [35]),
    # 복합 — 두 개의 독립 참조
    ("주석 7, 손상에 대한 회계정책은 주석 4.1.2 참조", [4, 7]),
    # 주석 키워드 없음 → 빈 결과
    ("(*) 전기말 대비 증가하였습니다.", []),
])
def test_extract_note_numbers_patterns(text: str, expected_numbers: list[int]):
    assert extract_note_numbers(text) == sorted(expected_numbers)


# ---------------------------------------------------------------------------
# TC7: check_note_references — CheckResult 통합 검증
# ---------------------------------------------------------------------------

def test_check_note_references_produces_correct_check_results():
    note14 = _make_note("14", "관계기업투자", has_table=True)
    footnote = "재분류하였습니다(주석 14 참조). 또한 주석 99는 미참조 오류."
    stmt = _make_statement_with_footnote(footnote)
    report = _make_report(statements=[stmt], notes=[note14])

    results = check_note_references(report)

    by_note_no = {r.note_no: r for r in results}

    # 주석 14: valid → MATCHED
    assert "14" in by_note_no
    r14 = by_note_no["14"]
    assert r14.status == MATCHED
    assert r14.check_type == "note_reference_check"
    assert r14.expected is None
    assert r14.actual is None
    assert r14.difference is None

    # 주석 99: broken_ref → UNEXPLAINED_GAP
    assert "99" in by_note_no
    r99 = by_note_no["99"]
    assert r99.status == UNEXPLAINED_GAP
    assert "미존재" in r99.reason


# ---------------------------------------------------------------------------
# TC8: validate_all_note_refs — 재무제표 + 주석 전체 스캔
# ---------------------------------------------------------------------------

def test_validate_all_note_refs_scans_both_statements_and_notes():
    note5 = _make_note("5", "현금", has_table=True)
    note_with_ref = _make_note("2", "유의적 추정", text="손상 방법은 주석 5를 참조합니다.")
    stmt = _make_statement_with_footnote("(*) 현금성자산 내역(주석 5 참조).")
    report = _make_report(statements=[stmt], notes=[note_with_ref, note5])

    results = validate_all_note_refs(report)

    # 재무제표 말 주기 + 주석 텍스트 블록 모두 감지
    sources = {r.source for r in results}
    stmt_sources = [s for s in sources if "statement" in s]
    note_sources = [s for s in sources if "note:2" in s]
    assert stmt_sources, "재무제표 말 주기에서 참조 미감지"
    assert note_sources, "주석 텍스트 블록에서 참조 미감지"

    verdicts = {r.verdict for r in results}
    assert "valid" in verdicts  # 주석 5는 실제 존재


# ---------------------------------------------------------------------------
# TC9: FOOTNOTE_MARKER_RE / strip_footnote_markers — re-export 확인 및 패턴 검증
# ---------------------------------------------------------------------------

def test_footnote_marker_re_is_reexported():
    """note_reference_validator 에서 FOOTNOTE_MARKER_RE 가 re-export 되는지 확인."""
    assert FOOTNOTE_MARKER_RE is not None
    assert FOOTNOTE_MARKER_RE.pattern


@pytest.mark.parametrize("raw,cleaned", [
    # (*N) — 코퍼스 최다 빈도 패턴
    ("기초(*1)", "기초"),
    ("1,234(*12)", "1,234"),
    # (주N) — 동등 빈도
    ("유형자산(주1)", "유형자산"),
    ("합계(주 3)", "합계"),
    # [주N] — 괄호 변형
    ("Clean H2 Infra Fund [주1]", "Clean H2 Infra Fund"),
    # 주N 단독 — 주석N 과 구별됨
    ("주1", ""),
    ("주 2", ""),
    ("주석35 참조", "주석35 참조"),   # 주석N → 제거 안 함
    # 원문자 — strip()으로 선행 공백 제거됨
    ("① 당기", "당기"),
    ("②", ""),
    # 음수 괄호는 제거하지 않음
    ("(1,234)", "(1,234)"),
    # 복합 — (*N)+(주N) 연속
    ("기초(*1)(주2)", "기초"),
])
def test_strip_footnote_markers_via_reexport(raw: str, cleaned: str):
    """note_reference_validator 에서 임포트한 strip_footnote_markers 동작 검증."""
    assert strip_footnote_markers(raw) == cleaned
