"""Data-driven review backlog for validation improvement.

This module does not create new verdicts. It classifies uncertain or gap
``CheckResult`` rows into accountant-readable backend-improvement buckets so the
next extraction/matching work can be driven by reviewed evidence rather than
company-specific patches.
"""

from __future__ import annotations

from dataclasses import dataclass

from dart_footing_reconciler.checks import (
    CheckResult,
    PARSE_UNCERTAIN,
    UNEXPLAINED_GAP,
)
from dart_footing_reconciler.document import FullReport
from dart_footing_reconciler.note_semantics import (
    NoteSemanticTable,
    build_note_semantic_extraction,
)
from dart_footing_reconciler.semantic_layer import SemanticDataset, build_semantic_dataset


@dataclass(frozen=True)
class ReviewBacklogRule:
    rule_id: str
    category: str
    statuses: tuple[str, ...]
    check_types: tuple[str, ...]
    parse_reasons: tuple[str, ...]
    semantic_flags: tuple[str, ...]
    reviewer_question: str
    backend_action: str
    priority: int = 50


@dataclass(frozen=True)
class ReviewBacklogItem:
    item_id: str
    rule_id: str
    category: str
    priority: int
    check_id: str
    check_type: str
    status: str
    title: str
    note_no: str
    account_key: str
    evidence_labels: tuple[str, ...]
    evidence_sources: tuple[str, ...]
    semantic_table_sources: tuple[str, ...]
    semantic_flags: tuple[str, ...]
    reviewer_question: str
    backend_action: str
    reason: str


@dataclass(frozen=True)
class ReviewBacklog:
    items: tuple[ReviewBacklogItem, ...]

    def by_category(self) -> dict[str, tuple[ReviewBacklogItem, ...]]:
        grouped: dict[str, list[ReviewBacklogItem]] = {}
        for item in self.items:
            grouped.setdefault(item.category, []).append(item)
        return {category: tuple(items) for category, items in grouped.items()}


BACKLOG_RULES: tuple[ReviewBacklogRule, ...] = (
    ReviewBacklogRule(
        rule_id="table_structure_backlog",
        category="표 구조 해석 보강",
        statuses=(UNEXPLAINED_GAP, PARSE_UNCERTAIN),
        check_types=("total_check", "note_layout_formula_check", "note_note_match"),
        parse_reasons=(),
        semantic_flags=(
            "multi_header_unresolved",
            "orientation_unknown",
            "low_orientation_confidence",
            "unknown_layout",
            "low_layout_confidence",
            "maturity_total_missing",
        ),
        reviewer_question="표의 머리글·행·합계 구조 때문에 금액 관계를 확정하지 못한 항목인가?",
        backend_action="표 머리글, 병합셀, 합계열 해석 기준을 보강하고 같은 양식이 다시 나오면 자동 확인되도록 표본 테스트에 추가",
        priority=10,
    ),
    ReviewBacklogRule(
        rule_id="label_candidate_gap",
        category="후보 사전 보강",
        statuses=(PARSE_UNCERTAIN,),
        check_types=(),
        parse_reasons=("LABEL_NOT_FOUND", "LOW_CONFIDENCE_MATCH"),
        semantic_flags=(),
        reviewer_question="본문 계정과 주석 표의 표현 차이 때문에 후보를 찾지 못했는가?",
        backend_action="계정 라벨/동의어 후보 사전을 보강하고 계정별로 원문 근거가 있는 후보 표현을 추가",
        priority=20,
    ),
    ReviewBacklogRule(
        rule_id="candidate_selection_backlog",
        category="후보 선택 기준 보강",
        statuses=(PARSE_UNCERTAIN,),
        check_types=(),
        parse_reasons=("AMBIGUOUS_MULTIPLE", "LOW_CONFIDENCE_MATCH"),
        semantic_flags=(),
        reviewer_question="후보는 있으나 어떤 금액을 대표값으로 볼지 선택 기준이 부족한가?",
        backend_action="후보 선택 기준에 기간, 유동/비유동, 총액/순액, 장부금액 역할을 추가",
        priority=30,
    ),
    ReviewBacklogRule(
        rule_id="statement_note_mapping_backlog",
        category="본문-주석 매핑 보강",
        statuses=(UNEXPLAINED_GAP, PARSE_UNCERTAIN),
        check_types=("fs_note_match", "fs_note_ref_amount_match", "primary_balance_reconciliation"),
        parse_reasons=(),
        semantic_flags=(),
        reviewer_question="본문 계정과 주석 후보의 범위·기간·유동성 구분이 서로 같은가?",
        backend_action="본문 계정과 주석 후보 매칭 기준에 주석번호, 계정 묶음, 기간, 유동/비유동 범위를 추가",
        priority=40,
    ),
    ReviewBacklogRule(
        rule_id="note_note_mapping_backlog",
        category="주석간 대사 기준 보강",
        statuses=(UNEXPLAINED_GAP, PARSE_UNCERTAIN),
        check_types=("note_note_match", "cfs_note_match", "cashflow_reconciliation"),
        parse_reasons=(),
        semantic_flags=(),
        reviewer_question="두 주석이 같은 거래/계정 범위를 말하는지 확인할 기준이 부족한가?",
        backend_action="주석 간 관계 묶음과 금액 역할(기초/기말/증가/감소/합계)을 후보 데이터에 추가",
        priority=50,
    ),
    ReviewBacklogRule(
        rule_id="unclassified_review_backlog",
        category="미분류 검토",
        statuses=(UNEXPLAINED_GAP, PARSE_UNCERTAIN),
        check_types=(),
        parse_reasons=(),
        semantic_flags=(),
        reviewer_question="현재 규칙표로는 원인을 충분히 분류하지 못한 검토 항목인가?",
        backend_action="사례를 검토해 새 검토 유형 또는 기존 유형의 조건으로 편입",
        priority=90,
    ),
)


def build_review_backlog(report: FullReport, checks: list[CheckResult]) -> ReviewBacklog:
    dataset = build_semantic_dataset(report)
    note_semantics = build_note_semantic_extraction(report)
    note_tables_by_source = {table.source: table for table in note_semantics.tables}

    items = [
        _item_for_check(dataset, note_tables_by_source, check)
        for check in checks
        if check.status in {UNEXPLAINED_GAP, PARSE_UNCERTAIN}
    ]
    return ReviewBacklog(tuple(sorted((item for item in items if item is not None), key=_item_sort_key)))


def _item_for_check(
    dataset: SemanticDataset,
    note_tables_by_source: dict[str, NoteSemanticTable],
    check: CheckResult,
) -> ReviewBacklogItem | None:
    evidence_sources = tuple(evidence.source for evidence in check.evidence if evidence.source)
    evidence_labels = tuple(evidence.label for evidence in check.evidence if evidence.label)
    semantic_sources = _semantic_table_sources(dataset, evidence_sources)
    flags = _semantic_flags(note_tables_by_source, semantic_sources)
    rule = _select_rule(check, flags)
    if rule is None:
        return None
    return ReviewBacklogItem(
        item_id=f"{rule.rule_id}:{check.check_id}",
        rule_id=rule.rule_id,
        category=rule.category,
        priority=rule.priority,
        check_id=check.check_id,
        check_type=check.check_type,
        status=check.status,
        title=check.title,
        note_no=check.note_no,
        account_key=check.account_key,
        evidence_labels=evidence_labels,
        evidence_sources=evidence_sources,
        semantic_table_sources=semantic_sources,
        semantic_flags=flags,
        reviewer_question=rule.reviewer_question,
        backend_action=rule.backend_action,
        reason=check.reason,
    )


def _select_rule(check: CheckResult, semantic_flags: tuple[str, ...]) -> ReviewBacklogRule | None:
    for rule in BACKLOG_RULES:
        if _rule_matches(rule, check, semantic_flags):
            return rule
    return None


def _rule_matches(
    rule: ReviewBacklogRule,
    check: CheckResult,
    semantic_flags: tuple[str, ...],
) -> bool:
    if check.status not in rule.statuses:
        return False
    if rule.check_types and check.check_type not in rule.check_types:
        return False
    if rule.parse_reasons and (check.parse_uncertain_reason or "") not in rule.parse_reasons:
        return False
    if rule.semantic_flags and not set(rule.semantic_flags).intersection(semantic_flags):
        return False
    return True


def _semantic_table_sources(dataset: SemanticDataset, evidence_sources: tuple[str, ...]) -> tuple[str, ...]:
    sources: list[str] = []
    for source in evidence_sources:
        table = dataset.table_for_source(source)
        if table is not None and table.source not in sources:
            sources.append(table.source)
    return tuple(sources)


def _semantic_flags(
    note_tables_by_source: dict[str, NoteSemanticTable],
    semantic_sources: tuple[str, ...],
) -> tuple[str, ...]:
    flags: list[str] = []
    for source in semantic_sources:
        table = note_tables_by_source.get(source)
        if table is None:
            continue
        for flag in table.uncertainty_flags:
            if flag not in flags:
                flags.append(flag)
    return tuple(flags)


def _item_sort_key(item: ReviewBacklogItem) -> tuple[int, str, str]:
    return (item.priority, item.category, item.check_id)
