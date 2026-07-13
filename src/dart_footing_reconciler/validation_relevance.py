"""Classify whether an untrusted note table is relevant to validation work."""

from __future__ import annotations

from dataclasses import dataclass

from dart_footing_reconciler.table_semantics import compact


@dataclass(frozen=True)
class ValidationRelevance:
    key: str
    validation_relevant: bool
    evidence: tuple[str, ...]


def classify_validation_relevance(
    *,
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> ValidationRelevance:
    text = " ".join(
        [
            compact(title),
            " ".join(compact(header) for header in headers),
            " ".join(compact(label) for label in row_labels[:12]),
        ]
    )
    if _is_disclosure_only_asset_table(text):
        return ValidationRelevance(
            "non_validation_note_table",
            False,
            ("asset disclosure table without reconciliation target",),
        )
    if _is_expense_allocation_table(text):
        return ValidationRelevance(
            "expense_allocation_candidate",
            True,
            ("expense allocation labels",),
        )
    if _contains_any(text, ("유형자산", "무형자산", "투자부동산", "사용권자산")) and _contains_any(
        text,
        ("기초", "취득", "증가", "처분", "감가상각", "상각", "손상", "대체", "기말", "장부금액", "장부가액"),
    ):
        return ValidationRelevance(
            "asset_rollforward_candidate",
            True,
            ("asset movement topic", "movement or carrying amount labels"),
        )
    if _contains_any(text, ("현금흐름", "투자활동", "재무활동")) and _contains_any(
        text,
        ("취득", "처분", "상환", "차입", "증가", "감소"),
    ):
        return ValidationRelevance(
            "cashflow_bridge_candidate",
            True,
            ("cash-flow bridge topic", "cash movement labels"),
        )
    if _contains_any(
        text,
        (
            "재고자산",
            "매출채권",
            "기타수취채권",
            "차입금",
            "사채",
            "리스부채",
            "충당부채",
            "퇴직급여",
        ),
    ) and _contains_any(text, ("당기", "전기", "기말", "합계", "총계", "장부금액", "잔액")):
        return ValidationRelevance(
            "balance_reconciliation_candidate",
            True,
            ("balance reconciliation topic", "period or balance labels"),
        )
    return ValidationRelevance("non_validation_note_table", False, ())


def _contains_any(text: str, aliases: tuple[str, ...]) -> bool:
    return any(alias in text for alias in aliases)


def _is_expense_allocation_table(text: str) -> bool:
    return _contains_any(
        text,
        ("비용의성격", "성격별비용", "매출원가", "판매비와관리비", "판매비와일반관리비", "연구개발비", "기능별항목"),
    )


def _is_disclosure_only_asset_table(text: str) -> bool:
    return _contains_any(
        text,
        (
            "담보제공자산",
            "담보설정금액",
            "약정액",
            "공시금액",
            "특수관계자",
            "추정내용연수",
            "상각방법",
            "실현가능성",
            "임대수익과처분대금",
            "송금",
            "제약",
        ),
    )
