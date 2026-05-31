"""말 주기 주석 참조 검증 check — 재무제표 텍스트 블록에서 추출된 주석 번호가
실제 주석 섹션에 존재하는지 교차 검증."""

from __future__ import annotations

from dart_footing_reconciler.checks import (
    CheckResult,
    MATCHED,
    NOT_TESTED,
    UNEXPLAINED_GAP,
)
from dart_footing_reconciler.document import FullReport
from dart_footing_reconciler.note_reference_validator import (
    NoteRefResult,
    validate_all_note_refs,
)

_VERDICT_TO_STATUS: dict[str, str] = {
    "valid": MATCHED,
    "broken_ref": UNEXPLAINED_GAP,
    "empty_note": UNEXPLAINED_GAP,
}


def check_note_references(report: FullReport, *, tolerance: int = 0) -> list[CheckResult]:
    """재무제표 말 주기의 주석 참조 번호를 추출하여 실제 주석과 교차 검증.

    각 텍스트 블록-주석 번호 조합마다 하나의 CheckResult를 생성.
    동일 check_id 중복은 제거(안전 장치).
    """
    ref_results = validate_all_note_refs(report)
    seen: set[str] = set()
    results: list[CheckResult] = []

    for ref in ref_results:
        check_id = f"note_ref:{ref.source}:note{ref.note_number}"
        if check_id in seen:
            continue
        seen.add(check_id)

        status = _VERDICT_TO_STATUS.get(ref.verdict, NOT_TESTED)
        results.append(
            CheckResult(
                check_id=check_id,
                check_type="note_reference_check",
                status=status,
                scope="report",
                note_no=str(ref.note_number),
                title=f"말 주기 주석 참조 검증 — 주석 {ref.note_number}",
                expected=None,
                actual=None,
                difference=None,
                tolerance=tolerance,
                reason=_reason(ref),
                evidence=[],
            )
        )
    return results


def _reason(ref: NoteRefResult) -> str:
    if ref.verdict == "valid":
        return f"주석 {ref.note_number} 존재하고 내용 확인됨"
    if ref.verdict == "broken_ref":
        return f"주석 {ref.note_number} 미존재 — 말 주기 참조 끊김"
    if ref.verdict == "empty_note":
        return f"주석 {ref.note_number} 존재하나 내용 비어있음"
    return "검증 불가"
