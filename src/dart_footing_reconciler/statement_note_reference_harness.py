"""Row-scoped financial-statement to displayed-note amount reconciliation."""

from __future__ import annotations

import re
from dataclasses import dataclass

from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.checks import (
    CheckEvidence,
    CheckResult,
    MATCHED,
    PARSE_UNCERTAIN,
    UNEXPLAINED_GAP,
)
from dart_footing_reconciler.document import FullReport, ReportSection, ReportTable
from dart_footing_reconciler.note_reference_validator import strip_footnote_markers
from dart_footing_reconciler.semantic_layer import (
    SemanticNoteReferenceFact,
    build_semantic_dataset,
)
from dart_footing_reconciler.table_semantics import row_amount_prefer_current
from dart_footing_reconciler.taxonomy import ClassifiedNoteAmount, classify_report
from dart_footing_reconciler.verification_harness import (
    LAYER_STATEMENT_NOTE,
    VerificationContext,
)


@dataclass(frozen=True)
class StatementReferenceRow:
    label: str
    amount: int
    amount_source: str
    row_source: str
    statement_title: str
    account_key: str
    confidence: float
    references: tuple[SemanticNoteReferenceFact, ...]


@dataclass(frozen=True)
class NoteAmountCandidate:
    note_no: str
    label: str
    amount: int
    source: str
    account_key: str
    confidence: float
    unit_multiplier: int
    rank: tuple[int, int, int]


class StatementNoteReferenceHarness:
    """Compare each referenced statement row with amounts in those notes."""

    harness_id = "statement_note_reference"
    layer = LAYER_STATEMENT_NOTE

    def run(self, context: VerificationContext) -> list[CheckResult]:
        return check_statement_note_references(
            context.report,
            tolerance=context.tolerance,
            consolidation_basis=context.consolidation_basis,
        )


def check_statement_note_references(
    report: FullReport,
    *,
    tolerance: int = 0,
    consolidation_basis: str = "unknown",
) -> list[CheckResult]:
    """Emit exactly one result for each material statement row with references."""
    classified = classify_report(report)
    rows = _statement_reference_rows(report, classified.statement_lines)
    note_sections = _note_sections_by_no(report.notes)
    results: list[CheckResult] = []
    for row in rows:
        displayed = tuple(dict.fromkeys(ref.note_no for ref in row.references))
        candidates = _candidate_amounts(
            report,
            row,
            displayed,
            classified.note_amounts,
        )
        missing_candidates = _missing_note_candidates(
            report,
            row,
            displayed,
            classified.note_amounts,
        )
        results.append(
            _result_for_row(
                row,
                displayed,
                candidates,
                missing_candidates,
                note_sections,
                tolerance=tolerance,
                consolidation_basis=consolidation_basis,
            )
        )
    return results


def _statement_reference_rows(report: FullReport, statement_lines) -> list[StatementReferenceRow]:
    semantic = build_semantic_dataset(report)
    classified_by_row = {_row_source(line.source): line for line in statement_lines}
    tables = _statement_tables(report)
    rows: list[StatementReferenceRow] = []
    references_by_row: dict[str, list[SemanticNoteReferenceFact]] = {}
    for reference in semantic.note_references:
        references_by_row.setdefault(reference.row_source, []).append(reference)
    for row_source, refs in references_by_row.items():
        statement_refs = tuple(ref for ref in refs if ref.section_kind == "statement")
        if not statement_refs:
            continue
        parsed = _parse_row_source(row_source)
        if parsed is None:
            continue
        section_id, table_index, row_index = parsed
        table_entry = tables.get((section_id, table_index))
        if table_entry is None:
            continue
        statement_title, table = table_entry
        if "현금흐름표" in statement_title:
            continue
        if row_index <= 0 or row_index >= len(table.rows):
            continue
        raw_row = table.rows[row_index]
        if not raw_row:
            continue
        line = classified_by_row.get(row_source)
        if line is not None:
            amount = line.amount
            amount_source = line.source
        else:
            amount, col_index = row_amount_prefer_current(raw_row, table.rows[0])
            if amount is None or col_index is None:
                continue
            amount *= table.unit_multiplier
            amount_source = f"{row_source}/col:{col_index}"
        label = _clean_statement_label(raw_row[0])
        rows.append(
            StatementReferenceRow(
                label=label,
                amount=amount,
                amount_source=amount_source,
                row_source=row_source,
                statement_title=statement_title,
                account_key=line.account_key if line is not None else "unknown",
                confidence=line.confidence if line is not None else 0.0,
                references=statement_refs,
            )
        )
    return rows


def _statement_tables(report: FullReport) -> dict[tuple[str, int], tuple[str, ReportTable]]:
    result: dict[tuple[str, int], tuple[str, ReportTable]] = {}
    for section in report.statements:
        for block in section.blocks:
            if block.table is not None:
                result[(section.section_id, block.table.index)] = (section.title, block.table)
    return result


def _candidate_amounts(
    report: FullReport,
    row: StatementReferenceRow,
    displayed_note_numbers: tuple[str, ...],
    note_amounts: list[ClassifiedNoteAmount],
) -> list[NoteAmountCandidate]:
    direct = _direct_note_candidates(report, row, displayed_note_numbers)
    if direct:
        return sorted(direct, key=lambda item: (item.rank, item.source), reverse=True)
    if row.account_key == "unknown":
        return []
    candidates: list[NoteAmountCandidate] = []
    for amount in note_amounts:
        if amount.account_key != row.account_key:
            continue
        if not any(_note_no_matches_ref(amount.note_no, ref) for ref in displayed_note_numbers):
            continue
        candidates.append(
            NoteAmountCandidate(
                note_no=amount.note_no,
                label=amount.label,
                amount=amount.amount,
                source=amount.source,
                account_key=amount.account_key,
                confidence=amount.confidence,
                unit_multiplier=amount.unit_multiplier,
                rank=_candidate_rank(row, amount),
            )
        )
    return sorted(candidates, key=lambda item: (item.rank, item.source), reverse=True)


def _direct_note_candidates(
    report: FullReport,
    row: StatementReferenceRow,
    displayed_note_numbers: tuple[str, ...],
) -> list[NoteAmountCandidate]:
    candidates: list[NoteAmountCandidate] = []
    for section in report.notes:
        if not any(
            _note_no_matches_ref(section.note_no, ref)
            for ref in displayed_note_numbers
        ):
            continue
        for block in section.blocks:
            table = block.table
            if table is None or not table.rows:
                continue
            headers = table.rows[0]
            for row_index, note_row in enumerate(table.rows[1:], start=1):
                if not note_row:
                    continue
                label_rank, candidate_label = _direct_label_rank(
                    row.label,
                    section.title,
                    note_row,
                )
                if label_rank == 0:
                    continue
                candidate_label = _most_specific_row_label(note_row, candidate_label)
                amount, column_index = _reconciliation_row_amount(note_row, headers)
                if amount is None or column_index is None:
                    continue
                amount *= table.unit_multiplier
                role_rank = _role_rank(row.statement_title, candidate_label)
                candidates.append(
                    NoteAmountCandidate(
                        note_no=section.note_no,
                        label=candidate_label,
                        amount=amount,
                        source=(
                            f"{section.section_id}/table:{table.index}/"
                            f"row:{row_index}/col:{column_index}"
                        ),
                        account_key=row.account_key,
                        confidence=0.95,
                        unit_multiplier=table.unit_multiplier,
                        rank=(label_rank, role_rank, 95),
                    )
                )
    return candidates


def _missing_note_candidates(
    report: FullReport,
    row: StatementReferenceRow,
    displayed_note_numbers: tuple[str, ...],
    note_amounts: list[ClassifiedNoteAmount],
) -> list[NoteAmountCandidate]:
    all_note_numbers = tuple(
        dict.fromkeys(section.note_no for section in report.notes if section.note_no)
    )
    candidates = [
        candidate
        for candidate in _direct_note_candidates(report, row, all_note_numbers)
        if _normalize(candidate.label) == _normalize(row.label)
        and not any(
            _note_no_matches_ref(candidate.note_no, ref)
            for ref in displayed_note_numbers
        )
    ]
    if row.account_key != "unknown":
        for amount in note_amounts:
            if amount.account_key != row.account_key or amount.confidence < 0.9:
                continue
            if _normalize(amount.label) != _normalize(row.label):
                continue
            if any(
                _note_no_matches_ref(amount.note_no, ref)
                for ref in displayed_note_numbers
            ):
                continue
            candidates.append(
                NoteAmountCandidate(
                    note_no=amount.note_no,
                    label=amount.label,
                    amount=amount.amount,
                    source=amount.source,
                    account_key=amount.account_key,
                    confidence=amount.confidence,
                    unit_multiplier=amount.unit_multiplier,
                    rank=_candidate_rank(row, amount),
                )
            )
    best_by_note: dict[str, NoteAmountCandidate] = {}
    for candidate in candidates:
        current = best_by_note.get(candidate.note_no)
        if current is None or (candidate.rank, candidate.source) > (
            current.rank,
            current.source,
        ):
            best_by_note[candidate.note_no] = candidate
    return sorted(best_by_note.values(), key=lambda item: (item.note_no, item.source))


def _direct_label_rank(
    statement_label: str,
    note_title: str,
    row: list[str],
) -> tuple[int, str]:
    target = _normalize(statement_label)
    text_cells = [cell.strip() for cell in row if cell.strip() and parse_amount(cell) is None]
    normalized_cells = [(_normalize(cell), cell) for cell in text_cells]
    for normalized, original in normalized_cells:
        if normalized and normalized == target:
            return 4, original
    for normalized, original in normalized_cells:
        if target and normalized and (target in normalized or normalized in target):
            if min(len(target), len(normalized)) >= 4:
                return 3, original
    note_context = _normalize(note_title)
    if target and (target in note_context or note_context in target):
        for normalized, original in normalized_cells:
            if _is_generic_balance_label(normalized):
                return 2, original
    return 0, ""


def _is_generic_balance_label(normalized: str) -> bool:
    return any(
        token in normalized
        for token in ("합계", "총계", "기말", "당기말", "장부금액", "공시금액")
    )


def _most_specific_row_label(row: list[str], fallback: str) -> str:
    labels = [cell.strip() for cell in row if cell.strip() and parse_amount(cell) is None]
    return labels[-1] if labels else fallback


def _reconciliation_row_amount(
    row: list[str],
    headers: list[str],
) -> tuple[int | None, int | None]:
    preferred: list[int] = []
    for index, header in enumerate(headers):
        normalized = _normalize(header)
        if any(
            token in normalized
            for token in ("장부금액합계", "순장부금액", "범주합계", "공시금액")
        ) or normalized.endswith("합계"):
            preferred.append(index)
    for index in reversed(preferred):
        if index >= len(row):
            continue
        amount = parse_amount(row[index])
        if amount is not None:
            return amount, index
    return row_amount_prefer_current(row, headers)


def _candidate_rank(
    row: StatementReferenceRow,
    amount: ClassifiedNoteAmount,
) -> tuple[int, int, int]:
    statement_label = _normalize(row.label)
    note_label = _normalize(amount.label)
    if statement_label and note_label == statement_label:
        label_rank = 3
    elif statement_label and note_label and (
        statement_label in note_label or note_label in statement_label
    ):
        label_rank = 2
    else:
        label_rank = 0
    role_rank = _role_rank(row.statement_title, amount.label)
    confidence_rank = round(amount.confidence * 100)
    return label_rank, role_rank, confidence_rank


def _role_rank(statement_title: str, label: str) -> int:
    normalized = _normalize(label)
    if "재무상태표" in statement_title:
        if any(token in normalized for token in ("기말장부금액", "당기말", "기말잔액")):
            return 3
        if any(token in normalized for token in ("장부금액", "순장부금액", "합계", "기말")):
            return 2
    if any(token in normalized for token in ("합계", "당기", "누계")):
        return 1
    return 0


def _result_for_row(
    row: StatementReferenceRow,
    displayed: tuple[str, ...],
    candidates: list[NoteAmountCandidate],
    missing_candidates: list[NoteAmountCandidate],
    note_sections: dict[str, list[ReportSection]],
    *,
    tolerance: int,
    consolidation_basis: str,
) -> CheckResult:
    top_candidates = _top_candidates(candidates)
    selected = _preferred_exact_candidate(candidates, row.amount)
    if selected is None:
        selected = _single_amount_candidate(top_candidates, row.amount)
    missing_refs = [ref for ref in displayed if not _sections_for_ref(note_sections, ref)]
    evidence = [
        CheckEvidence(row.label, row.amount, row.amount_source, role="statement_amount")
    ]
    evidence.extend(
        CheckEvidence(
            f"본문 표시 주석 {ref.note_no}",
            None,
            ref.cell_source,
            role="displayed_note_reference",
        )
        for ref in row.references
    )
    missing_evidence = [
        CheckEvidence(
            f"주석 {candidate.note_no} {candidate.label}".strip(),
            candidate.amount,
            candidate.source,
            role="missing_note_reference",
        )
        for candidate in missing_candidates
    ]

    if selected is not None:
        effective_tolerance = max(tolerance, selected.unit_multiplier - 1)
        difference = row.amount - selected.amount
        status = MATCHED if abs(difference) <= effective_tolerance else UNEXPLAINED_GAP
        reason = (
            f"재무제표 {row.label} 금액과 주석 {selected.note_no} "
            f"{selected.label} 금액이 일치함"
            if status == MATCHED
            else (
                f"재무제표 {row.label} 금액과 주석 {selected.note_no} "
                f"{selected.label} 금액에 차이가 있음"
            )
        )
        evidence.append(
            CheckEvidence(
                f"주석 {selected.note_no} {selected.label}".strip(),
                selected.amount,
                selected.source,
                role="note_amount",
            )
        )
        selected_primary = selected.note_no.split("-", 1)[0].split(".", 1)[0]
        for ref in displayed:
            if ref == selected_primary or _note_no_matches_ref(selected.note_no, ref):
                continue
            sections = _sections_for_ref(note_sections, ref)
            if sections:
                evidence.append(
                    CheckEvidence(
                        f"주석 {ref} {sections[0].title}".strip(),
                        None,
                        sections[0].section_id,
                        role="related_note_reference",
                    )
                )
        evidence.extend(missing_evidence)
        parse_uncertain_reason = None
        if status == MATCHED and missing_evidence:
            status = PARSE_UNCERTAIN
            reason = "재무제표 옆에 표시되지 않은 관련 주석번호가 확인됨"
            parse_uncertain_reason = "MISSING_DISPLAYED_NOTE_REFERENCE"
        return _check_result(
            row,
            note_no=selected_primary,
            status=status,
            expected=row.amount,
            actual=selected.amount,
            difference=difference,
            tolerance=effective_tolerance,
            reason=reason,
            evidence=evidence,
            consolidation_basis=consolidation_basis,
            parse_uncertain_reason=parse_uncertain_reason,
        )

    if top_candidates:
        for candidate in top_candidates:
            evidence.append(
                CheckEvidence(
                    f"주석 {candidate.note_no} {candidate.label}".strip(),
                    candidate.amount,
                    candidate.source,
                    role="candidate_note_amount",
                )
            )
        evidence.extend(missing_evidence)
        return _check_result(
            row,
            note_no=",".join(displayed),
            status=PARSE_UNCERTAIN,
            expected=row.amount,
            actual=None,
            difference=None,
            tolerance=tolerance,
            reason="주석에서 같은 우선순위의 금액 후보가 여러 개 확인됨",
            evidence=evidence,
            consolidation_basis=consolidation_basis,
            parse_uncertain_reason="AMBIGUOUS_MULTIPLE",
        )

    if missing_refs and len(missing_refs) == len(displayed):
        evidence.extend(missing_evidence)
        return _check_result(
            row,
            note_no=",".join(displayed),
            status=UNEXPLAINED_GAP,
            expected=row.amount,
            actual=None,
            difference=None,
            tolerance=tolerance,
            reason="재무제표에 표시된 주석 원문을 찾지 못함",
            evidence=evidence,
            consolidation_basis=consolidation_basis,
            parse_uncertain_reason="TABLE_NOT_FOUND",
        )

    for ref in displayed:
        sections = _sections_for_ref(note_sections, ref)
        if sections:
            evidence.append(
                CheckEvidence(
                    f"주석 {ref} {sections[0].title}".strip(),
                    None,
                    sections[0].section_id,
                    role="related_note_reference",
                )
            )
    evidence.extend(missing_evidence)
    return _check_result(
        row,
        note_no=",".join(displayed),
        status=PARSE_UNCERTAIN,
        expected=row.amount,
        actual=None,
        difference=None,
        tolerance=tolerance,
        reason="표시된 주석에서 직접 비교할 계정 금액을 찾지 못함",
        evidence=evidence,
        consolidation_basis=consolidation_basis,
        parse_uncertain_reason="LABEL_NOT_FOUND",
    )


def _top_candidates(candidates: list[NoteAmountCandidate]) -> list[NoteAmountCandidate]:
    if not candidates:
        return []
    top_rank = max(candidate.rank for candidate in candidates)
    return [candidate for candidate in candidates if candidate.rank == top_rank]


def _single_amount_candidate(
    candidates: list[NoteAmountCandidate],
    expected_amount: int,
) -> NoteAmountCandidate | None:
    if not candidates:
        return None
    if len({candidate.amount for candidate in candidates}) != 1:
        matching = [candidate for candidate in candidates if candidate.amount == expected_amount]
        table_sources = {candidate.source.split("/row:", 1)[0] for candidate in candidates}
        if matching and len(table_sources) > 1:
            return sorted(matching, key=lambda item: item.source)[0]
        return None
    return sorted(candidates, key=lambda item: item.source)[0]


def _preferred_exact_candidate(
    candidates: list[NoteAmountCandidate],
    expected_amount: int,
) -> NoteAmountCandidate | None:
    matching = [candidate for candidate in candidates if candidate.amount == expected_amount]
    if not matching:
        return None
    table_sources = {candidate.source.split("/row:", 1)[0] for candidate in candidates}
    if len(table_sources) > 1:
        return sorted(matching, key=lambda item: (-item.rank[0], item.source))[0]
    label_counts: dict[str, int] = {}
    for candidate in candidates:
        key = _normalize(candidate.label)
        label_counts[key] = label_counts.get(key, 0) + 1
    uniquely_labeled = [
        candidate
        for candidate in matching
        if label_counts.get(_normalize(candidate.label), 0) == 1
    ]
    if uniquely_labeled:
        return sorted(uniquely_labeled, key=lambda item: (-item.rank[0], item.source))[0]
    return None


def _check_result(
    row: StatementReferenceRow,
    *,
    note_no: str,
    status: str,
    expected: int | None,
    actual: int | None,
    difference: int | None,
    tolerance: int,
    reason: str,
    evidence: list[CheckEvidence],
    consolidation_basis: str,
    parse_uncertain_reason: str | None = None,
) -> CheckResult:
    source_key = row.row_source.replace("/", ":")
    return CheckResult(
        check_id=f"statement_note_row:{source_key}",
        check_type="statement_note_row_reconciliation",
        status=status,
        scope="report",
        note_no=note_no,
        title=f"{row.label} 주석 금액 대사",
        expected=expected,
        actual=actual,
        difference=difference,
        tolerance=tolerance,
        reason=reason,
        evidence=evidence,
        parse_uncertain_reason=parse_uncertain_reason,
        account_key=row.account_key,
        consolidation_basis=consolidation_basis,
        report_period="current",
        balance_level="unknown",
    )


def _note_sections_by_no(
    notes: list[ReportSection],
) -> dict[str, list[ReportSection]]:
    result: dict[str, list[ReportSection]] = {}
    for section in notes:
        if not section.note_no:
            continue
        primary = section.note_no.split("-", 1)[0].split(".", 1)[0]
        result.setdefault(primary, []).append(section)
        if section.note_no != primary:
            result.setdefault(section.note_no, []).append(section)
    return result


def _sections_for_ref(
    index: dict[str, list[ReportSection]],
    ref: str,
) -> list[ReportSection]:
    return index.get(ref, [])


def _note_no_matches_ref(note_no: str, ref: str) -> bool:
    return note_no == ref or note_no.startswith(f"{ref}-") or note_no.startswith(f"{ref}.")


def _row_source(source: str) -> str:
    return source.rsplit("/col:", 1)[0] if "/col:" in source else source


def _parse_row_source(source: str) -> tuple[str, int, int] | None:
    match = re.fullmatch(r"(.+)/table:(\d+)/row:(\d+)", source)
    if match is None:
        return None
    return match.group(1), int(match.group(2)), int(match.group(3))


def _normalize(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", value or "").lower()


def _clean_statement_label(value: str) -> str:
    without_refs = re.sub(
        r"\(\s*(?:주석|주|註)\s*\d+(?:\s*[,，ㆍ·/]\s*\d+)*\s*\)",
        "",
        value or "",
    )
    return strip_footnote_markers(without_refs).strip() or (value or "").strip()
