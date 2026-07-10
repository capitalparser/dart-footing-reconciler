"""Statement-row note reference accuracy and completeness checks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from dart_footing_reconciler.checks import (
    CheckEvidence,
    CheckResult,
    MATCHED,
    PARSE_UNCERTAIN,
    UNEXPLAINED_GAP,
)
from dart_footing_reconciler.checks_note_references import check_note_references
from dart_footing_reconciler.document import FullReport, ReportSection, ReportTable
from dart_footing_reconciler.note_reference_validator import extract_note_ref_tokens
from dart_footing_reconciler.semantic_layer import (
    SemanticDataset,
    SemanticNoteReferenceFact,
    build_semantic_dataset,
)
from dart_footing_reconciler.taxonomy import (
    ClassifiedNoteAmount,
    ClassifiedNoteTopic,
    ClassifiedStatementLine,
    TAXONOMY,
    classify_report,
)
from dart_footing_reconciler.verification_harness import (
    LAYER_STATEMENT_NOTE,
    VerificationContext,
)


@dataclass(frozen=True)
class StatementAccountRow:
    statement_id: str
    row_index: int
    account_key: str
    label: str
    amount: int | None
    displayed_note_numbers: tuple[str, ...]
    source: str
    period: str | None
    consolidation_basis: str | None
    balance_level: str | None
    confidence: float
    displayed_note_references: tuple[SemanticNoteReferenceFact, ...] = ()


@dataclass(frozen=True)
class NoteAccountEvidence:
    note_no: str
    account_key: str
    label: str
    amount: int | None
    evidence_kind: Literal[
        "balance",
        "movement",
        "maturity",
        "expense_breakdown",
        "tax_reconciliation",
        "policy_text",
        "reference_topic",
        "other",
    ]
    confidence: Literal["strong", "medium", "weak"]
    source: str


class StatementNoteReferenceHarness:
    """Run note-existence and account-level statement-note reference checks."""

    harness_id = "statement_note_reference"
    layer = LAYER_STATEMENT_NOTE

    def run(self, context: VerificationContext) -> list[CheckResult]:
        results = check_note_references(context.report, tolerance=context.tolerance)
        results.extend(
            check_statement_note_references(
                context.report,
                tolerance=context.tolerance,
                consolidation_basis=context.consolidation_basis,
            )
        )
        return results


def check_statement_note_references(
    report: FullReport,
    *,
    tolerance: int = 0,
    consolidation_basis: str = "unknown",
) -> list[CheckResult]:
    """Validate that statement row note numbers point at account-specific notes.

    This check deliberately does not reuse semantic candidates as pass verdicts:
    ``matched`` requires source-backed note account amount evidence. Topic-only
    evidence is surfaced as ``parse_uncertain``.
    """
    classified = classify_report(report)
    semantic = build_semantic_dataset(report)
    statement_rows = _statement_account_rows(
        report,
        classified.statement_lines,
        semantic,
        consolidation_basis=consolidation_basis,
    )
    note_evidence = _note_account_evidence_index(
        report,
        classified.note_amounts,
        classified.note_topics,
    )
    note_sections = _note_sections_by_no(report.notes)

    results: list[CheckResult] = []
    for row in statement_rows:
        if row.displayed_note_numbers:
            for note_no in row.displayed_note_numbers:
                results.append(
                    _accuracy_result(
                        row,
                        note_no,
                        note_sections.get(note_no, []),
                        [
                            *_evidence_for_ref(note_evidence, row.account_key, note_no),
                            *_reference_topic_evidence(
                                row,
                                note_no,
                                note_sections.get(note_no, []),
                            ),
                        ],
                        tolerance,
                    )
                )
        results.extend(
            _completeness_results(
                row,
                note_evidence,
                tolerance,
            )
        )
    return results


def _statement_account_rows(
    report: FullReport,
    statement_lines: list[ClassifiedStatementLine],
    semantic: SemanticDataset,
    *,
    consolidation_basis: str,
) -> list[StatementAccountRow]:
    rows: list[StatementAccountRow] = []
    for line in statement_lines:
        source = _parse_source(line.source)
        row_index = int(source["row"]) if source else -1
        displayed_note_references = _displayed_note_references_for_line(
            report,
            semantic,
            line,
        )
        rows.append(
            StatementAccountRow(
                statement_id=str(source["section"]) if source else "",
                row_index=row_index,
                account_key=line.account_key,
                label=line.label,
                amount=line.amount,
                displayed_note_numbers=tuple(
                    dict.fromkeys(ref.note_no for ref in displayed_note_references)
                ),
                source=line.source,
                period="current",
                consolidation_basis=consolidation_basis,
                balance_level="unknown",
                confidence=line.confidence,
                displayed_note_references=tuple(displayed_note_references),
            )
        )
    return rows


def _displayed_note_references_for_line(
    report: FullReport,
    semantic: SemanticDataset,
    line: ClassifiedStatementLine,
) -> tuple[SemanticNoteReferenceFact, ...]:
    refs = list(semantic.note_references_for_row(line.source))
    if not refs:
        refs = _fallback_label_note_references(line)
    refs.sort(key=lambda ref: (ref.cell_source, ref.note_no))
    deduped: list[SemanticNoteReferenceFact] = []
    seen: set[str] = set()
    for ref in refs:
        if ref.section_kind != "statement":
            continue
        if not _reference_row_matches_statement_line(report, line, ref):
            continue
        if ref.note_no in seen:
            continue
        seen.add(ref.note_no)
        deduped.append(ref)
    return tuple(deduped)


def _fallback_label_note_references(
    line: ClassifiedStatementLine,
) -> list[SemanticNoteReferenceFact]:
    parsed = _parse_source(line.source)
    if parsed is None:
        return []
    table_source = f"{parsed['section']}/table:{parsed['table']}"
    row_source = f"{table_source}/row:{parsed['row']}"
    refs: list[SemanticNoteReferenceFact] = []
    for note_no in extract_note_ref_tokens(line.label):
        refs.append(
            SemanticNoteReferenceFact(
                reference_id=f"{row_source}:label:note{note_no}",
                table_source=table_source,
                row_source=row_source,
                cell_source=line.source,
                section_kind="statement",
                note_no=note_no,
                raw_text=line.label,
                context="statement_label_fallback",
                confidence=0.75,
            )
        )
    return refs


def _reference_row_matches_statement_line(
    report: FullReport,
    line: ClassifiedStatementLine,
    ref: SemanticNoteReferenceFact,
) -> bool:
    line_source = _parse_source(line.source)
    if line_source is None:
        return True
    ref_source = _parse_source(ref.cell_source)
    if ref_source is None:
        return True
    if (
        line_source["section"] != ref_source["section"]
        or line_source["table"] != ref_source["table"]
        or line_source["row"] != ref_source["row"]
    ):
        return False
    row = _row_for_source(report, line.source)
    if not row:
        return True
    return _normalize_context(line.label) in _normalize_context(" ".join(row))


def _row_for_source(report: FullReport, source: str) -> list[str] | None:
    parsed = _parse_source(source)
    if parsed is None:
        return None
    section_id = str(parsed["section"])
    table_index = int(parsed["table"])
    row_index = int(parsed["row"])
    for section in report.statements:
        if section.section_id != section_id:
            continue
        for block in section.blocks:
            if block.table is None or block.table.index != table_index:
                continue
            if 0 <= row_index < len(block.table.rows):
                return block.table.rows[row_index]
    return None


def _note_account_evidence_index(
    report: FullReport,
    note_amounts: list[ClassifiedNoteAmount],
    note_topics: list[ClassifiedNoteTopic],
) -> dict[tuple[str, str], list[NoteAccountEvidence]]:
    index: dict[tuple[str, str], list[NoteAccountEvidence]] = {}
    seen_sources: set[tuple[str, str, str]] = set()
    for amount in note_amounts:
        if not _amount_has_account_context(report, amount):
            continue
        evidence = NoteAccountEvidence(
            note_no=amount.note_no,
            account_key=amount.account_key,
            label=amount.label,
            amount=amount.amount,
            evidence_kind=_amount_evidence_kind(amount),
            confidence=_confidence_bucket(amount.confidence),
            source=amount.source,
        )
        index.setdefault((evidence.account_key, evidence.note_no), []).append(evidence)
        seen_sources.add((evidence.account_key, evidence.note_no, evidence.source))
    for topic in note_topics:
        source = topic.source or topic.section_id
        key = (topic.topic_key, topic.note_no, source)
        if key in seen_sources:
            continue
        evidence = NoteAccountEvidence(
            note_no=topic.note_no,
            account_key=topic.topic_key,
            label=topic.title,
            amount=None,
            evidence_kind="policy_text",
            confidence=_confidence_bucket(topic.confidence),
            source=source,
        )
        index.setdefault((evidence.account_key, evidence.note_no), []).append(evidence)
    for values in index.values():
        values.sort(key=_note_evidence_sort_key)
    return index


def _amount_has_account_context(report: FullReport, amount: ClassifiedNoteAmount) -> bool:
    aliases = _context_aliases_for_account(amount.account_key)
    if not aliases:
        return False
    section, table = _source_section_and_table(report, amount.source)
    context_parts = [amount.note_title]
    if section is not None:
        context_parts.append(section.title)
    if table is not None:
        context_parts.append(table.heading)
    context = _normalize_context(" ".join(context_parts))
    return any(alias in context for alias in aliases)


def _source_section_and_table(
    report: FullReport,
    source: str,
) -> tuple[ReportSection | None, ReportTable | None]:
    parsed = _parse_source(source)
    if parsed is None:
        return None, None
    section_id = str(parsed["section"])
    table_index = int(parsed["table"])
    for section in report.notes:
        if section.section_id != section_id:
            continue
        for block in section.blocks:
            if block.table is not None and block.table.index == table_index:
                return section, block.table
        return section, None
    return None, None


_GENERIC_CONTEXT_ALIASES = frozenset(
    {
        "자산",
        "부채",
        "금융",
        "금융상품",
        "기타",
        "유동",
        "비유동",
        "단기",
        "장기",
        "합계",
        "소계",
        "기말",
        "기초",
        "장부금액",
        "기말장부금액",
        "순장부금액",
        "장부가액",
    }
)


def _context_aliases_for_account(account_key: str) -> tuple[str, ...]:
    entry = next((item for item in TAXONOMY if item.key == account_key), None)
    if entry is None:
        return ()
    aliases = [
        entry.display_name,
        *entry.statement_aliases,
        *entry.note_title_aliases,
    ]
    normalized = [
        _normalize_context(alias)
        for alias in aliases
        if _normalize_context(alias) and _normalize_context(alias) not in _GENERIC_CONTEXT_ALIASES
    ]
    return tuple(dict.fromkeys(normalized))


def _normalize_context(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", value or "").lower()


def _accuracy_result(
    row: StatementAccountRow,
    note_no: str,
    note_sections: list[ReportSection],
    evidence_candidates: list[NoteAccountEvidence],
    tolerance: int,
) -> CheckResult:
    amount_evidence = [item for item in evidence_candidates if item.amount is not None]
    topic_evidence = [item for item in evidence_candidates if item.amount is None]
    reference_topic_evidence = [
        item for item in topic_evidence
        if item.evidence_kind == "reference_topic" and item.confidence == "strong"
    ]
    if row.confidence < 0.75:
        status = PARSE_UNCERTAIN
        reason = f"본문 계정 매핑 신뢰도가 낮아 주석 {note_no} 정확성 검증을 보류"
        parse_uncertain_reason = "weak_account_mapping"
        note_evidence = topic_evidence[:1] or amount_evidence[:1]
    elif amount_evidence and amount_evidence[0].confidence == "strong":
        status = MATCHED
        reason = f"본문 주석번호 주{note_no}에서 {row.label} 관련 계정 금액 근거를 확인"
        parse_uncertain_reason = None
        note_evidence = amount_evidence[:1]
    elif reference_topic_evidence:
        status = MATCHED
        reason = f"본문 주석번호 주{note_no}에서 {row.label} 관련 공시 주석을 확인"
        parse_uncertain_reason = None
        note_evidence = reference_topic_evidence[:1]
    elif evidence_candidates:
        status = PARSE_UNCERTAIN
        reason = f"주석 {note_no}에 계정 후보는 있으나 금액 근거가 충분하지 않음"
        parse_uncertain_reason = "weak_account_mapping"
        note_evidence = topic_evidence[:1] or amount_evidence[:1]
    elif note_sections:
        status = UNEXPLAINED_GAP
        reason = f"본문에는 주석 {note_no}가 표시되어 있으나 해당 계정 근거를 찾지 못함"
        parse_uncertain_reason = None
        note_evidence = [_note_section_placeholder(note_sections[0])]
    else:
        status = UNEXPLAINED_GAP
        reason = f"본문에는 주석 {note_no}가 표시되어 있으나 주석 원문을 찾지 못함"
        parse_uncertain_reason = "missing_note_ref"
        note_evidence = []
    evidence = _statement_evidence(row, role="statement_anchor")
    displayed_ref = _displayed_reference_for_note(row, note_no)
    evidence.append(
        CheckEvidence(
            _displayed_reference_label(note_no, displayed_ref),
            None,
            displayed_ref.cell_source if displayed_ref is not None else row.source,
            role="displayed_note_reference",
        )
    )
    evidence.extend(_check_evidence_from_note(item) for item in note_evidence)
    return CheckResult(
        check_id=_check_id(row, "accuracy", note_no),
        check_type="statement_note_reference_accuracy",
        status=status,
        scope="report",
        note_no=note_no,
        title=f"{row.label} 주석번호 정확성",
        expected=None,
        actual=None,
        difference=None,
        tolerance=tolerance,
        reason=reason,
        evidence=evidence,
        parse_uncertain_reason=parse_uncertain_reason,
        account_key=row.account_key,
        consolidation_basis=row.consolidation_basis or "unknown",
        report_period=row.period or "unknown",
        balance_level=row.balance_level or "unknown",
    )


_COMPLETENESS_ACCOUNT_KEYS = frozenset(
    {
        "property_plant_equipment",
        "intangible_assets",
        "investment_property",
        "borrowings",
        "bonds",
        "lease_liabilities",
    }
)


def _completeness_results(
    row: StatementAccountRow,
    note_evidence: dict[tuple[str, str], list[NoteAccountEvidence]],
    tolerance: int,
) -> list[CheckResult]:
    if row.account_key not in _COMPLETENESS_ACCOUNT_KEYS:
        return []
    displayed = set(row.displayed_note_numbers)
    missing: list[NoteAccountEvidence] = []
    for (account_key, note_no), candidates in note_evidence.items():
        if account_key != row.account_key or _note_no_matches_any_ref(note_no, displayed):
            continue
        amount_candidates = [
            item for item in candidates
            if item.amount is not None and item.confidence == "strong"
        ]
        if amount_candidates:
            missing.append(amount_candidates[0])
    missing.sort(key=lambda item: (int(item.note_no) if item.note_no.isdigit() else 10**9, item.note_no))
    return [
        _completeness_result(row, candidate, tolerance)
        for candidate in missing
    ]


def _completeness_result(
    row: StatementAccountRow,
    candidate: NoteAccountEvidence,
    tolerance: int,
) -> CheckResult:
    if row.displayed_note_numbers:
        reason = (
            f"{row.label} 관련 주석 {candidate.note_no} 근거가 있으나 "
            "본문 행 주석번호에 포함되지 않음"
        )
    else:
        reason = (
            f"본문 행에 주석번호가 없습니다. {row.label} 관련 주석 "
            f"{candidate.note_no} 근거를 확인하세요"
        )
    evidence = _statement_evidence(row, role="statement_anchor")
    if row.displayed_note_numbers:
        displayed = ", ".join(f"주{note_no}" for note_no in row.displayed_note_numbers)
    else:
        displayed = "없음"
    evidence.append(
        CheckEvidence(
            f"본문 표시 주석번호: {displayed}",
            None,
            row.source,
            role="displayed_note_reference",
        )
    )
    evidence.append(_check_evidence_from_note(candidate))
    return CheckResult(
        check_id=_check_id(row, "completeness", candidate.note_no),
        check_type="statement_note_reference_completeness",
        status=UNEXPLAINED_GAP,
        scope="report",
        note_no=candidate.note_no,
        title=f"{row.label} 주석 참조 완전성",
        expected=None,
        actual=None,
        difference=None,
        tolerance=tolerance,
        reason=reason,
        evidence=evidence,
        account_key=row.account_key,
        consolidation_basis=row.consolidation_basis or "unknown",
        report_period=row.period or "unknown",
        balance_level=row.balance_level or "unknown",
    )


def _note_sections_by_no(
    notes: list[ReportSection],
) -> dict[str, list[ReportSection]]:
    index: dict[str, list[ReportSection]] = {}
    for section in notes:
        if not section.note_no:
            continue
        primary = section.note_no.split("-", 1)[0].split(".", 1)[0]
        index.setdefault(primary, []).append(section)
        if section.note_no != primary:
            index.setdefault(section.note_no, []).append(section)
    return index


def _evidence_for_ref(
    note_evidence: dict[tuple[str, str], list[NoteAccountEvidence]],
    account_key: str,
    ref: str,
) -> list[NoteAccountEvidence]:
    matches: list[NoteAccountEvidence] = []
    for (candidate_account_key, note_no), candidates in note_evidence.items():
        if candidate_account_key == account_key and _note_no_matches_ref(note_no, ref):
            matches.extend(candidates)
    return sorted(matches, key=_note_evidence_sort_key)


_REFERENCE_TOPIC_RULES = (
    (
        frozenset({
            "trade_receivables",
            "contract_assets",
            "other_financial_assets",
            "financial_deposits",
            "borrowings",
            "bonds",
            "finance_income",
            "finance_costs",
        }),
        ("금융상품",),
    ),
    (
        frozenset({
            "trade_receivables",
            "borrowings",
            "bonds",
            "revenue",
            "cost_of_sales",
            "selling_general_admin",
        }),
        ("특수관계자",),
    ),
    (
        frozenset({"property_plant_equipment", "intangible_assets", "borrowings", "bonds"}),
        ("우발사항", "약정사항"),
    ),
    (
        frozenset({"borrowings", "bonds"}),
        ("사채및차입금", "차입금", "사채"),
    ),
    (
        frozenset({"deferred_tax_assets", "deferred_tax_liabilities", "income_tax_expense_benefit"}),
        ("법인세",),
    ),
    (
        frozenset({"financial_deposits", "other_financial_assets"}),
        ("장단기금융자산", "금융자산"),
    ),
    (
        frozenset({"contract_assets", "trade_receivables"}),
        ("매출채권및기타채권",),
    ),
    (
        frozenset({"contract_assets", "revenue"}),
        ("영업부문", "고객과의계약"),
    ),
    (
        frozenset({"cost_of_sales", "selling_general_admin"}),
        ("비용의성격별분류", "성격별분류"),
    ),
    (
        frozenset({"earnings_per_share"}),
        ("주당이익",),
    ),
)


def _reference_topic_evidence(
    row: StatementAccountRow,
    note_no: str,
    note_sections: list[ReportSection],
) -> list[NoteAccountEvidence]:
    if not note_sections:
        return []
    normalized_titles = [
        _normalize_context(f"{section.note_no} {section.title}")
        for section in note_sections
    ]
    for account_keys, title_tokens in _REFERENCE_TOPIC_RULES:
        if row.account_key not in account_keys:
            continue
        normalized_tokens = tuple(_normalize_context(token) for token in title_tokens)
        if not any(
            any(token and token in title for token in normalized_tokens)
            for title in normalized_titles
        ):
            continue
        section = note_sections[0]
        return [
            NoteAccountEvidence(
                note_no=note_no,
                account_key=row.account_key,
                label=section.title,
                amount=None,
                evidence_kind="reference_topic",
                confidence="strong",
                source=section.section_id,
            )
        ]
    return []


def _note_no_matches_any_ref(note_no: str, refs: set[str]) -> bool:
    return any(_note_no_matches_ref(note_no, ref) for ref in refs)


def _note_no_matches_ref(note_no: str, ref: str) -> bool:
    return note_no == ref or note_no.startswith(f"{ref}-")


def _displayed_reference_for_note(
    row: StatementAccountRow,
    note_no: str,
) -> SemanticNoteReferenceFact | None:
    for ref in row.displayed_note_references:
        if ref.note_no == note_no:
            return ref
    return None


def _displayed_reference_label(
    note_no: str,
    ref: SemanticNoteReferenceFact | None,
) -> str:
    if ref is None or not ref.raw_text:
        return f"본문 주석번호 주{note_no}"
    return f"본문 주석번호 주{note_no}: {ref.raw_text}"


def _note_section_placeholder(section: ReportSection) -> NoteAccountEvidence:
    return NoteAccountEvidence(
        note_no=section.note_no,
        account_key="unknown",
        label=section.title,
        amount=None,
        evidence_kind="other",
        confidence="weak",
        source=section.section_id,
    )


def _statement_evidence(row: StatementAccountRow, *, role: str) -> list[CheckEvidence]:
    return [CheckEvidence(row.label, row.amount, row.source, role=role)]


def _check_evidence_from_note(evidence: NoteAccountEvidence) -> CheckEvidence:
    label = f"주석 {evidence.note_no} {evidence.label}".strip()
    return CheckEvidence(
        label,
        evidence.amount,
        evidence.source,
        role="note_account_evidence",
    )


def _check_id(row: StatementAccountRow, kind: str, note_no: str) -> str:
    source = _parse_source(row.source)
    if source is None:
        source_key = re.sub(r"[^0-9A-Za-z가-힣:_-]+", "_", row.source)
    else:
        source_key = f"{source['section']}:table{source['table']}:row{source['row']}"
    return f"statement_note_ref_{kind}:{row.account_key}:{source_key}:note{note_no}"


def _note_refs_from_label(label: str) -> list[str]:
    return extract_note_ref_tokens(label)


def _amount_evidence_kind(amount: ClassifiedNoteAmount) -> Literal[
    "balance",
    "movement",
    "maturity",
    "expense_breakdown",
    "tax_reconciliation",
    "policy_text",
    "other",
]:
    text = f"{amount.note_title} {amount.label}"
    if any(token in text for token in ("만기", "상환", "유동성")):
        return "maturity"
    if any(token in text for token in ("증가", "감소", "취득", "처분", "상각")):
        return "movement"
    if any(token in text for token in ("법인세", "세율", "차감전")):
        return "tax_reconciliation"
    if any(token in text for token in ("매출원가", "판매비", "관리비", "비용")):
        return "expense_breakdown"
    return "balance"


def _confidence_bucket(confidence: float) -> Literal["strong", "medium", "weak"]:
    if confidence >= 0.75:
        return "strong"
    if confidence >= 0.55:
        return "medium"
    return "weak"


def _note_evidence_sort_key(evidence: NoteAccountEvidence) -> tuple[int, int, str]:
    confidence_rank = {"strong": 0, "medium": 1, "weak": 2}[evidence.confidence]
    kind_rank = 0 if evidence.amount is not None else 1
    return confidence_rank, kind_rank, evidence.source


def _parse_source(source: str) -> dict[str, int | str] | None:
    try:
        section, table_part, row_part, col_part = source.rsplit("/", 3)
        if not (
            table_part.startswith("table:")
            and row_part.startswith("row:")
            and col_part.startswith("col:")
        ):
            return None
        return {
            "section": section,
            "table": int(table_part.removeprefix("table:")),
            "row": int(row_part.removeprefix("row:")),
            "col": int(col_part.removeprefix("col:")),
        }
    except (TypeError, ValueError):
        return None
