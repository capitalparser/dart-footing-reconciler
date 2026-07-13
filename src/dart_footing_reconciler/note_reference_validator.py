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
# 주석 참조 추출 패턴 (우선순위 순)
# ---------------------------------------------------------------------------
# 주석 참조 키워드. bare "주"는 "(주12)" 또는 독립 토큰 "주 12"만
# 허용한다. "보통주 3,343주", "[주1]" 같은 주식 수량/표 각주 오탐을
# 막기 위해 한글·영문·숫자 뒤의 "주"와 대괄호 각주는 제외한다.
_NOTE_KEYWORD = r"(?:주석|註|[Nn]ote|\(\s*주|(?<![0-9A-Za-z가-힣])주\s+)"
_NOTE_NUMBER = r"\d+(?:[.-]\d+)?"
_NOTE_NUMBER_GROUP = (
    rf"{_NOTE_NUMBER}"
    rf"(?:\s*(?:[,，ㆍ·/]|및|와|과)\s*{_NOTE_NUMBER})*"
)
_PATTERN_NOTE_REF = re.compile(
    rf"{_NOTE_KEYWORD}\s*제?\s*({_NOTE_NUMBER_GROUP})\s*(?:호|번)?"
)
_DIGIT_RE = re.compile(r"\d+")
_PLAIN_NOTE_NUMBER_GROUP_RE = re.compile(
    rf"^\s*{_NOTE_NUMBER_GROUP}\s*$"
)


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
    """텍스트에서 참조된 주석 번호 토큰을 등장 순서대로 추출.

    DB/semantic layer에서 재사용하기 위한 정규화 함수다. "4.1.2"와
    "12-1"은 주 번호 단위 검증을 위해 leading number("4", "12")로
    정규화한다.
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
    """주석번호 전용 셀("12", "5, 17")에서 번호 토큰을 추출.

    이 함수는 헤더/컨텍스트가 이미 "주석"임을 확인한 호출자만 사용해야
    한다. 금액 셀을 주석번호로 오인하지 않기 위해 일반 텍스트에서는
    호출하지 않는다.
    """
    if not _PLAIN_NOTE_NUMBER_GROUP_RE.match(text or ""):
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

    # 주석 본문 안의 ``(주1)``, ``[주2]``는 대개 해당 표의 로컬 각주다.
    # 이를 보고서의 주석 1/2 참조로 해석하면 존재하는 낮은 번호 주석과
    # 우연히 매칭되는 오탐이 발생한다. 재무제표의 말 주기 표기는 유효한
    # 참조이므로 source가 note일 때만 로컬 각주 마커를 먼저 제거한다.
    # 명시적인 ``주석 12 참조``는 strip 대상이 아니어서 그대로 검증된다.
    candidate_text = (
        strip_footnote_markers(ref_text)
        if source.startswith("note:")
        else ref_text
    )
    note_numbers = extract_note_numbers(candidate_text)
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
        if block.kind == "text" and block.text.strip():
            source = f"{section.section_id}:block{block_idx}"
            results.extend(
                validate_note_refs_in_text(
                    block.text, notes, source, note_index=note_index
                )
            )
            continue
        if block.kind != "table" or block.table is None:
            continue
        table = block.table
        headers = table.rows[0] if table.rows else []
        for row_idx, row in enumerate(table.rows):
            for col_idx, cell in enumerate(row):
                header = headers[col_idx] if col_idx < len(headers) else ""
                if not extract_note_ref_tokens(cell) and not (
                    _is_note_reference_header(header)
                    and extract_plain_note_ref_tokens(cell)
                ):
                    continue
                source = (
                    f"{section.section_id}/table:{table.index}"
                    f"/row:{row_idx}/col:{col_idx}"
                )
                text = cell if extract_note_ref_tokens(cell) else f"주석 {cell}"
                results.extend(
                    validate_note_refs_in_text(text, notes, source, note_index=note_index)
                )
    return results


def _is_note_reference_header(value: str) -> bool:
    return bool(re.search(r"(?:주석|註|[Nn]ote)", value or ""))


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
