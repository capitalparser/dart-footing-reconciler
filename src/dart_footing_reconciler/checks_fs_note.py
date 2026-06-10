"""Financial statement to note matching checks."""

from __future__ import annotations

from dart_footing_reconciler.amount_compare import amounts_agree, display_unit_tolerance
from dart_footing_reconciler.checks import CheckEvidence, CheckResult, MATCHED, UNEXPLAINED_GAP
from dart_footing_reconciler.document import FullReport
from dart_footing_reconciler.taxonomy import (
    ClassifiedNoteAmount,
    ClassifiedStatementLine,
    TAXONOMY,
    classify_report,
)

FS_NOTE_ACCOUNT_KEYS = (
    "property_plant_equipment",
    "intangible_assets",
    "investment_property",
    "borrowings",
    "bonds",
    "lease_liabilities",
    "revenue",
    "cost_of_sales",
    "selling_general_admin",
    "income_tax_expense_benefit",
    "earnings_per_share",
    "depreciation_expense",
    "dividends",
    "cash_and_cash_equivalents_increase",
)


def check_fs_note_matches(report: FullReport, *, tolerance: int = 1) -> list[CheckResult]:
    results: list[CheckResult] = []
    classified = classify_report(report)
    for account_key in FS_NOTE_ACCOUNT_KEYS:
        fs_hits = [
            line for line in classified.statement_lines if line.account_key == account_key
        ]
        note_hits = [
            amount for amount in classified.note_amounts if amount.account_key == account_key
        ]
        note_hits = [hit for hit in note_hits if _plausible_amount(hit.amount)]
        if not fs_hits or not note_hits:
            continue
        fs_hit = fs_hits[0]
        note_hit = _select_note_hit_by_label(note_hits, account_key)
        if note_hit is None:
            # 라벨 근거 없이 첫 후보로 페어링하면 거짓 차이를 만든다.
            # 의미 기반 라벨 매칭이 실패하면 검증 후보로 보지 않는다.
            continue
        difference = note_hit.amount - fs_hit.amount
        status = MATCHED if amounts_agree(fs_hit.amount, note_hit.amount, tolerance) else UNEXPLAINED_GAP
        effective_tolerance = display_unit_tolerance(fs_hit.amount, note_hit.amount, tolerance)
        matched_reason = (
            "financial statement amount agrees to note amount"
            if difference == 0
            else "financial statement amount agrees within display-unit rounding"
        )
        results.append(
            CheckResult(
                check_id=f"fs_note:{account_key}:{note_hit.note_no}",
                check_type="fs_note_match",
                status=status,
                scope="report",
                note_no=note_hit.note_no,
                title=f"{fs_hit.display_name} FS to note match",
                expected=fs_hit.amount,
                actual=note_hit.amount,
                difference=difference,
                tolerance=effective_tolerance,
                reason=matched_reason
                if status == MATCHED
                else "financial statement amount does not agree to note amount",
                evidence=[
                    CheckEvidence(_statement_evidence_label(fs_hit), fs_hit.amount, fs_hit.source),
                    CheckEvidence(_note_evidence_label(note_hit), note_hit.amount, note_hit.source),
                ],
            )
        )
    return results


def _statement_evidence_label(hit: ClassifiedStatementLine) -> str:
    return f"{hit.statement_title} {hit.label}"


def _note_evidence_label(hit: ClassifiedNoteAmount) -> str:
    return f"주석 {hit.note_no} {hit.note_title} {hit.label}"


_NOTE_LABEL_PRIORITY = ("기말장부금액", "기말잔액", "합계", "소계")


def _select_note_hit_by_label(
    note_hits: list[ClassifiedNoteAmount], account_key: str
) -> ClassifiedNoteAmount | None:
    """Pick the semantically strongest note row without considering amount value."""
    if not note_hits:
        return None

    priority = _label_priority_for_account(account_key)
    ranked = [
        (rank, index, hit)
        for index, hit in enumerate(note_hits)
        if (rank := _label_rank(hit.label, priority)) is not None
    ]
    if not ranked:
        return None
    ranked.sort(key=lambda item: (item[0], item[1]))
    return ranked[0][2]


# DART 원화 공시에서 1경(1e16)원을 넘는 단일 금액은 셀 병합/병기 텍스트의
# 파싱 잔재로 본다. 거짓 페어링 방지를 위한 보수적 상한.
_MAX_PLAUSIBLE_AMOUNT = 10**16


def _plausible_amount(amount: int | None) -> bool:
    return amount is not None and abs(amount) < _MAX_PLAUSIBLE_AMOUNT


def _label_priority_for_account(account_key: str) -> tuple[str, ...]:
    aliases: list[str] = list(_NOTE_LABEL_PRIORITY)
    entry = next((item for item in TAXONOMY if item.key == account_key), None)
    if entry is not None:
        aliases.extend(entry.note_amount_aliases)
    return tuple(dict.fromkeys(_normalize_label(alias) for alias in aliases if alias))


def _label_rank(label: str, priority: tuple[str, ...]) -> int | None:
    normalized = _normalize_label(label)
    for index, alias in enumerate(priority):
        if alias and alias in normalized:
            return index
    return None


def _normalize_label(value: str) -> str:
    return "".join(value.split())
