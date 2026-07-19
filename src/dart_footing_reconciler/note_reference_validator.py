"""
재무제표 텍스트 블록의 말 주기 주석 참조 번호를 추출하고,
실제 주석 섹션에 해당 내용이 존재하는지 검증.

말 주기(footnote) 패턴 예시:
  (*) 유형자산 담보 제공 내역(주석 11,13,32 참조)
  (주석 21 참조)
  주석 7, 손상에 대한 회계정책은 주석 4.1.2 참조
  주석 제15호 참고
  주석 3에서 설명하고 있습니다
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from dart_footing_reconciler.amounts import FOOTNOTE_MARKER_RE, strip_footnote_markers  # noqa: F401
from dart_footing_reconciler.document import FullReport, ReportSection

# FOOTNOTE_MARKER_RE, strip_footnote_markers 는 amounts 모듈에 정의되어 있으며
# 이 모듈에서 re-export 함으로써 공개 API를 일원화.
# 사용처:
#   - amounts.parse_amount(): 금액 파싱 전 마커 제거 (핵심 버그픽스)
#   - 외부 코드: from dart_footing_reconciler.note_reference_validator import strip_footnote_markers

# ---------------------------------------------------------------------------
# 주석 참조 추출 패턴
# ---------------------------------------------------------------------------
_NOTE_KEYWORD = r"(?:주석|註|주)"
_NOTE_NUMBER = r"\d+(?:[.-]\d+)*"
_NOTE_NUMBER_GROUP = (
    rf"{_NOTE_NUMBER}"
    rf"(?:\s*(?:[,，ㆍ·/]|및|와|과)\s*{_NOTE_NUMBER})*"
)
# ``[주1]``은 DART 페이지/서식 표식으로 쓰이는 경우가 많아 제외한다.
# ``(주3,10)``처럼 계정명에 붙는 실제 참조는 포함한다.
_PATTERN_NOTE_REF = re.compile(
    rf"(?<![0-9A-Za-z가-힣\[]){_NOTE_KEYWORD}\s*제?\s*"
    rf"({_NOTE_NUMBER_GROUP})\s*(?:호|번)?"
)
_PLAIN_NOTE_NUMBER_GROUP_RE = re.compile(rf"^\s*{_NOTE_NUMBER_GROUP}\s*$")
_DIGIT_RE = re.compile(r"\d+")


# ---------------------------------------------------------------------------
# 결과 모델
# ---------------------------------------------------------------------------
@dataclass
class NoteRefResult:
    ref_text: str               # 원문 말 주기 텍스트 (참조가 등장한 블록)
    note_number: int            # 참조된 주석 번호 (주 번호 정수, 예: 4.1.2 → 4)
    note_exists: bool           # 해당 주석 번호 존재 여부
    note_has_content: bool      # 주석 내용이 비어있지 않은지
    context_match: Optional[bool]  # 맥락 키워드 매칭 (None = 미검사)
    verdict: str                # "valid" | "broken_ref" | "empty_note"
    source: str                 # 참조 위치 식별자 (section_id:blockN)


# ---------------------------------------------------------------------------
# 번호 추출
# ---------------------------------------------------------------------------

def extract_note_ref_tokens(text: str) -> list[str]:
    """본문에서 표시된 주석번호를 등장 순서대로 추출한다.

    소수점·하이픈 하위번호는 현재 주석 섹션 인덱스와 동일하게 첫 번호로
    정규화한다. 주식 수량의 접미사 ``주``는 뒤에 번호가 없어 일치하지 않는다.
    """
    found: list[str] = []
    seen: set[str] = set()
    for match in _PATTERN_NOTE_REF.finditer(text or ""):
        for token in _tokens_from_number_group(match.group(1)):
            if token not in seen:
                seen.add(token)
                found.append(token)
    return found


def extract_plain_note_ref_tokens(text: str) -> list[str]:
    """주석번호 전용 열의 숫자-only 셀에서 번호를 추출한다."""
    if not _PLAIN_NOTE_NUMBER_GROUP_RE.fullmatch(text or ""):
        return []
    return _tokens_from_number_group(text)


def extract_note_numbers(text: str) -> list[int]:
    """텍스트에서 참조된 주석 번호(정수) 목록을 추출. 중복 제거, 정렬."""
    return sorted({int(token) for token in extract_note_ref_tokens(text)})


def _tokens_from_number_group(raw: str) -> list[str]:
    tokens: list[str] = []
    for segment in re.split(r"\s*(?:[,，ㆍ·/]|및|와|과)\s*", raw or ""):
        digits = _DIGIT_RE.findall(segment)
        if digits:
            tokens.append(digits[0])
    return tokens


# ---------------------------------------------------------------------------
# 주석 인덱스 구성
# ---------------------------------------------------------------------------

def _build_note_index(notes: list[ReportSection]) -> dict[int, list[ReportSection]]:
    """note_no 첫 정수 → 섹션 목록 인덱스 구성."""
    index: dict[int, list[ReportSection]] = {}
    for section in notes:
        try:
            primary = int(re.split(r"[-.]", section.note_no, maxsplit=1)[0])
        except (ValueError, IndexError):
            continue
        index.setdefault(primary, []).append(section)
    return index


def _note_has_content(sections: list[ReportSection]) -> bool:
    """해당 주석 섹션 목록 중 하나라도 비어있지 않으면 True."""
    for section in sections:
        for block in section.blocks:
            if block.kind == "table" and block.table and block.table.rows:
                return True
            if block.kind == "text" and block.text.strip():
                return True
    return False


# ---------------------------------------------------------------------------
# 검증 함수
# ---------------------------------------------------------------------------

def validate_note_refs_in_text(
    ref_text: str,
    notes: list[ReportSection],
    source: str,
    *,
    note_index: dict[int, list[ReportSection]] | None = None,
) -> list[NoteRefResult]:
    """텍스트 블록 하나에서 주석 참조를 추출하고 실제 주석과 교차 검증."""
    if note_index is None:
        note_index = _build_note_index(notes)

    note_numbers = extract_note_numbers(ref_text)
    results: list[NoteRefResult] = []
    for num in note_numbers:
        matched = note_index.get(num, [])
        note_exists = bool(matched)
        note_has_content = _note_has_content(matched) if note_exists else False

        if not note_exists:
            verdict = "broken_ref"
        elif not note_has_content:
            verdict = "empty_note"
        else:
            verdict = "valid"

        results.append(
            NoteRefResult(
                ref_text=ref_text,
                note_number=num,
                note_exists=note_exists,
                note_has_content=note_has_content,
                context_match=None,
                verdict=verdict,
                source=source,
            )
        )
    return results


def validate_section_note_refs(
    section: ReportSection,
    notes: list[ReportSection],
    *,
    note_index: dict[int, list[ReportSection]] | None = None,
) -> list[NoteRefResult]:
    """섹션 내 모든 텍스트 블록에서 주석 참조를 검증."""
    if note_index is None:
        note_index = _build_note_index(notes)

    results: list[NoteRefResult] = []
    for block_idx, block in enumerate(section.blocks):
        if block.kind != "text" or not block.text.strip():
            continue
        source = f"{section.section_id}:block{block_idx}"
        results.extend(
            validate_note_refs_in_text(
                block.text, notes, source, note_index=note_index
            )
        )
    return results


def validate_all_note_refs(report: FullReport) -> list[NoteRefResult]:
    """보고서 전체(재무제표 + 주석) 섹션의 말 주기 주석 참조를 검증."""
    notes = report.notes
    note_index = _build_note_index(notes)
    results: list[NoteRefResult] = []
    for section in report.statements + report.notes:
        results.extend(
            validate_section_note_refs(section, notes, note_index=note_index)
        )
    return results
