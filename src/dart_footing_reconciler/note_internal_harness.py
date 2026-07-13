"""Note-content internal verification harness."""

from __future__ import annotations

import dataclasses
import re

from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.checks import (
    MATCHED,
    UNEXPLAINED_GAP,
    CheckEvidence,
    CheckResult,
)
from dart_footing_reconciler.checks_note_note import check_note_note_matches
from dart_footing_reconciler.checks_totals import check_table_totals
from dart_footing_reconciler.layout_formula_assertions import check_layout_formula_assertions
from dart_footing_reconciler.note_assertions import check_note_assertions
from dart_footing_reconciler.report_frame import statement_kind_from_title
from dart_footing_reconciler.verification_harness import LAYER_NOTE_INTERNAL, VerificationContext


class NoteInternalHarness:
    """Run checks whose evidence and arithmetic live inside note contents."""

    harness_id = "note_internal"
    layer = LAYER_NOTE_INTERNAL

    def run(self, context: VerificationContext) -> list[CheckResult]:
        results: list[CheckResult] = []
        for note in context.report.notes:
            for block in note.blocks:
                if block.table is not None:
                    results.extend(
                        check_table_totals(
                            block.table,
                            note_no=note.note_no,
                            tolerance=context.tolerance,
                        )
                    )
        results.extend(_appropriation_total_checks(context))
        results.extend(check_note_assertions(context.report, tolerance=context.tolerance))
        results.extend(check_layout_formula_assertions(context.report, tolerance=context.tolerance))
        results.extend(check_note_note_matches(context.report, tolerance=context.tolerance))
        return results


def _appropriation_total_checks(context: VerificationContext) -> list[CheckResult]:
    """이익잉여금처분계산서(결손금처리계산서) 표의 내부 합계 검증.

    check_table_totals는 note 기준 source 문자열을 만들기 때문에, 본문 섹션
    section_id 기준 source로 재작성해 report frame이 해당 본문 표에 검증
    결과를 붙일 수 있게 한다.
    """
    results: list[CheckResult] = []
    for section in context.report.statements:
        if statement_kind_from_title(section.title) != "appropriation":
            continue
        for block in section.blocks:
            if block.table is None:
                continue
            for check in check_table_totals(
                block.table, note_no="", tolerance=context.tolerance
            ):
                evidence = [
                    dataclasses.replace(
                        item,
                        source=item.source.replace("note:/", f"{section.section_id}/", 1),
                    )
                    for item in check.evidence
                ]
                results.append(
                    dataclasses.replace(
                        check,
                        check_id=f"appropriation:{check.check_id}",
                        evidence=evidence,
                    )
                )
            results.extend(
                _appropriation_formula_checks(
                    section, block.table, tolerance=context.tolerance
                )
            )
    return results


def _appropriation_row_label(value: str) -> str:
    """로마숫자/번호 열거 마커와 후행 산식 괄호를 제거한 처분계산서 행 라벨."""
    compact = re.sub(r"\s+", "", value)
    compact = re.sub(r"^(?:[IVXⅠ-Ⅻivx]+|\d+)\s*\.", "", compact)
    compact = re.sub(r"\([IVXⅠ-Ⅻ+\-−–]+\)$", "", compact)
    return compact


def _appropriation_formula_checks(section, table, *, tolerance: int) -> list[CheckResult]:
    """처분계산서 산식 검증.

    차기이월미처분이익잉여금 = 미처분이익잉여금 + 임의적립금 등의 이입액(있으면)
    - 이익잉여금처분액. 결손금처리계산서는 동일 구조의 처리액 라벨로 대응한다.
    상위(로마숫자) 라벨만 prefix 매칭하며, 라벨이 모두 식별될 때만 검증한다.
    """
    rows = getattr(table, "rows", None) or []
    if len(rows) < 3:
        return []
    opening_idx = movement_idx = closing_idx = None
    addition_indices: list[int] = []
    for row_idx, row in enumerate(rows):
        if not row:
            continue
        label = _appropriation_row_label(row[0])
        if closing_idx is None and label.startswith("차기이월"):
            closing_idx = row_idx
        elif opening_idx is None and label.startswith(("미처분이익잉여금", "미처리결손금")):
            opening_idx = row_idx
        elif movement_idx is None and label.startswith(("이익잉여금처분액", "결손금처리액")):
            movement_idx = row_idx
        elif "이입액" in label and not label.startswith(("전기이월",)):
            addition_indices.append(row_idx)
    if opening_idx is None or movement_idx is None or closing_idx is None:
        return []
    results: list[CheckResult] = []
    width = max(len(row) for row in rows)
    source_base = f"{section.section_id}/table:{table.index}"
    for col in range(1, width):
        def amount_at(row_idx: int) -> int | None:
            row = rows[row_idx]
            return parse_amount(row[col]) if col < len(row) else None

        opening = amount_at(opening_idx)
        movement = amount_at(movement_idx)
        closing = amount_at(closing_idx)
        if opening is None or movement is None or closing is None:
            continue
        additions = [(idx, amount_at(idx)) for idx in addition_indices]
        addition_total = sum(amount for _idx, amount in additions if amount is not None)
        expected = opening + addition_total - movement
        difference = closing - expected
        status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP
        evidence = [
            CheckEvidence(rows[opening_idx][0], opening, f"{source_base}/row:{opening_idx}/col:{col}"),
            *[
                CheckEvidence(rows[idx][0], amount, f"{source_base}/row:{idx}/col:{col}")
                for idx, amount in additions
                if amount is not None
            ],
            CheckEvidence(rows[movement_idx][0], movement, f"{source_base}/row:{movement_idx}/col:{col}"),
            CheckEvidence(rows[closing_idx][0], closing, f"{source_base}/row:{closing_idx}/col:{col}"),
        ]
        results.append(
            CheckResult(
                check_id=f"appropriation_formula:table{table.index}:col{col}",
                check_type="appropriation_formula_check",
                status=status,
                scope="report",
                note_no="",
                title="차기이월미처분이익잉여금 = 미처분이익잉여금 + 이입액 - 처분액",
                expected=expected,
                actual=closing,
                difference=difference,
                tolerance=tolerance,
                reason=(
                    "처분계산서 산식이 일치"
                    if status == MATCHED
                    else "처분계산서 산식이 일치하지 않음"
                ),
                evidence=evidence,
            )
        )
    return results
