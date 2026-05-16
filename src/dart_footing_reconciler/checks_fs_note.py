"""Financial statement to note matching checks."""

from __future__ import annotations

from dart_footing_reconciler._match_helpers import find_note_amounts, find_statement_amounts
from dart_footing_reconciler.checks import CheckEvidence, CheckResult, MATCHED, UNEXPLAINED_GAP
from dart_footing_reconciler.document import FullReport

FS_NOTE_KEYWORDS = {
    "유형자산": ("유형자산", "장부금액"),
    "무형자산": ("무형자산", "장부금액"),
    "투자부동산": ("투자부동산", "장부금액"),
    "차입금": ("차입금", "기말"),
    "사채": ("사채", "기말"),
    "리스부채": ("리스", "기말"),
    "매출액": ("수익", "매출액"),
    "감가상각비": ("비용", "감가상각비"),
    "배당": ("배당", "배당"),
    "현금및현금성자산의증가": ("현금", "현금및현금성자산의증가"),
}


def check_fs_note_matches(report: FullReport, *, tolerance: int = 1) -> list[CheckResult]:
    results: list[CheckResult] = []
    for fs_label, note_keywords in FS_NOTE_KEYWORDS.items():
        fs_hits = find_statement_amounts(report, fs_label)
        note_hits = find_note_amounts(report, note_keywords[0], note_keywords[1])
        if not fs_hits or not note_hits:
            continue
        fs_hit = fs_hits[0]
        note_hit = note_hits[0]
        difference = note_hit.amount - fs_hit.amount
        status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP
        results.append(
            CheckResult(
                check_id=f"fs_note:{fs_label}:{note_hit.note_no}",
                check_type="fs_note_match",
                status=status,
                scope="report",
                note_no=note_hit.note_no,
                title=f"{fs_label} FS to note match",
                expected=fs_hit.amount,
                actual=note_hit.amount,
                difference=difference,
                tolerance=tolerance,
                reason="financial statement amount agrees to note amount"
                if status == MATCHED
                else "financial statement amount does not agree to note amount",
                evidence=[
                    CheckEvidence(fs_hit.label, fs_hit.amount, fs_hit.source),
                    CheckEvidence(note_hit.label, note_hit.amount, note_hit.source),
                ],
            )
        )
    return results
