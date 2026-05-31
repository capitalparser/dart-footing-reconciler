"""Cross-note bridge checks built from reproducible reconciliation formulas."""

from __future__ import annotations

from dart_footing_reconciler.checks import CheckResult, MATCHED
from dart_footing_reconciler.checks_reconciliation import check_reconciliation_targets
from dart_footing_reconciler.document import FullReport

_ASSET_CASHFLOW_TARGET_LABELS = {
    "property_plant_equipment.acquisitions_cashflow": "유형자산 취득 주석 연결 대사",
    "property_plant_equipment.disposals_cashflow": "유형자산 처분 주석 연결 대사",
    "intangible_assets.acquisitions_cashflow": "무형자산 취득 주석 연결 대사",
    "intangible_assets.disposals_cashflow": "무형자산 처분 주석 연결 대사",
    "investment_property.acquisitions_cashflow": "투자부동산 취득 주석 연결 대사",
    "investment_property.disposals_cashflow": "투자부동산 처분 주석 연결 대사",
}


def check_asset_note_bridges(report: FullReport, *, tolerance: int = 1) -> list[CheckResult]:
    results: list[CheckResult] = []
    for check in check_reconciliation_targets(report, tolerance=tolerance):
        if check.check_type != "cashflow_reconciliation":
            continue
        title = _ASSET_CASHFLOW_TARGET_LABELS.get(check.title)
        if title is None:
            continue
        if not _has_statement_and_note_evidence(check):
            continue
        results.append(
            CheckResult(
                check_id=f"asset_note_bridge:{check.title}",
                check_type="asset_note_bridge_check",
                status=check.status,
                scope=check.scope,
                note_no=check.note_no,
                title=title,
                expected=check.expected,
                actual=check.actual,
                difference=check.difference,
                tolerance=check.tolerance,
                reason=_bridge_reason(check),
                evidence=check.evidence,
            )
        )
    return results


def _has_statement_and_note_evidence(check: CheckResult) -> bool:
    has_statement = any(evidence.source.startswith("statement:") for evidence in check.evidence)
    has_note = any(evidence.source.startswith("note:") for evidence in check.evidence)
    return has_statement and has_note


def _bridge_reason(check: CheckResult) -> str:
    if check.status == MATCHED:
        return "자산 주석과 관련 주석 금액이 현금흐름표 산식으로 연결됨"
    return "자산 주석과 관련 주석 금액의 현금흐름표 연결 산식에 후속 확인 필요"
