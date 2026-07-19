"""말 주기 주석 참조 검증 check — 재무제표 텍스트 블록에서 추출된 주석 번호가
실제 주석 섹션에 존재하는지 교차 검증."""

from __future__ import annotations

from dart_footing_reconciler.checks import (
    CheckEvidence,
    CheckResult,
    MATCHED,
    UNEXPLAINED_GAP,
)
from dart_footing_reconciler.document import FullReport, ReportSection
from dart_footing_reconciler.narrative_evidence import (
    NarrativeNoteReference,
    build_narrative_evidence,
)


def check_note_references(report: FullReport, *, tolerance: int = 0) -> list[CheckResult]:
    """재무제표 말 주기의 주석 참조 번호를 추출하여 실제 주석과 교차 검증.

    각 텍스트 블록-주석 번호 조합마다 하나의 CheckResult를 생성.
    동일 check_id 중복은 제거(안전 장치).
    """
    ref_results = build_narrative_evidence(report).note_references
    seen: set[str] = set()
    results: list[CheckResult] = []

    for ref in ref_results:
        check_id = f"note_ref:{ref.source.source_key}:note{ref.note_no}"
        if check_id in seen:
            continue
        seen.add(check_id)

        targets = _target_notes(report, ref)
        has_content = any(_note_has_content(target) for target in targets)
        verdict = "valid" if has_content else "empty_note" if targets else "broken_ref"
        status = MATCHED if verdict == "valid" else UNEXPLAINED_GAP
        evidence = [
            CheckEvidence(
                ref.text,
                None,
                ref.source.source_key,
                role="narrative_reference",
            )
        ]
        target = _single_target_for_evidence(targets, ref.source.scope)
        if target is not None and target.blocks:
            block_index = target.blocks[0].location.block_index
            target_scope = target.scope or "unknown"
            evidence.append(
                CheckEvidence(
                    f"주석 {ref.note_no}",
                    None,
                    f"{target.section_id}@{target_scope}/block:{block_index}",
                    role="referenced_note",
                )
            )
        results.append(
            CheckResult(
                check_id=check_id,
                check_type="note_reference_check",
                status=status,
                scope="report",
                note_no=ref.note_no,
                title=f"말 주기 주석 참조 검증 — 주석 {ref.note_no}",
                expected=None,
                actual=None,
                difference=None,
                tolerance=tolerance,
                reason=_reason(verdict, ref.note_no),
                evidence=evidence,
                consolidation_basis=ref.source.scope,
            )
        )
    return results


def _target_notes(
    report: FullReport, reference: NarrativeNoteReference
) -> list[ReportSection]:
    primary = reference.note_no.split("-", 1)[0].split(".", 1)[0]
    candidates = [
        note
        for note in report.notes
        if note.note_no.split("-", 1)[0].split(".", 1)[0] == primary
    ]
    if reference.source.scope not in {"", "unknown"}:
        return [note for note in candidates if note.scope == reference.source.scope]
    return candidates


def _single_target_for_evidence(
    targets: list[ReportSection], source_scope: str
) -> ReportSection | None:
    if not targets:
        return None
    if source_scope not in {"", "unknown"}:
        return targets[0]
    scopes = {target.scope or "unknown" for target in targets}
    return targets[0] if len(scopes) == 1 else None


def _note_has_content(note: ReportSection) -> bool:
    return any(
        (block.table is not None and bool(block.table.rows))
        or (block.kind == "text" and bool(block.text.strip()))
        for block in note.blocks
    )


def _reason(verdict: str, note_no: str) -> str:
    if verdict == "valid":
        return f"주석 {note_no} 존재하고 내용 확인됨"
    if verdict == "broken_ref":
        return f"주석 {note_no} 미존재 — 말 주기 참조 끊김"
    if verdict == "empty_note":
        return f"주석 {note_no} 존재하나 내용 비어있음"
    return "검증 불가"
