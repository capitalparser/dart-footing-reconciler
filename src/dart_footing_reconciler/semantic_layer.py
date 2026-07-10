"""Semantic dataset layer over parsed DART report tables."""

from __future__ import annotations

from dataclasses import dataclass

from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.document import FullReport, ReportSection, ReportTable
from dart_footing_reconciler.note_reference_validator import (
    extract_note_ref_tokens,
    extract_plain_note_ref_tokens,
)
from dart_footing_reconciler.report_order import build_report_order_index
from dart_footing_reconciler.signatures import SignatureMatch, emit_signatures
from dart_footing_reconciler.table_semantics import (
    CURRENT_PERIOD_TOKENS,
    PRIOR_PERIOD_TOKENS,
    compact,
)


@dataclass(frozen=True)
class SemanticTable:
    company: str
    source: str
    order: int
    section_kind: str
    statement_kind: str
    section_id: str
    section_title: str
    note_no: str
    table_index: int
    heading: str
    row_count: int
    column_count: int
    unit_multiplier: int
    headers: tuple[str, ...]
    row_labels: tuple[str, ...]
    signatures: tuple[SignatureMatch, ...]


@dataclass(frozen=True)
class SemanticAmountFact:
    """A placement fact: a parsed amount located in a table, with its display
    role/period and cell provenance.

    NOT account-resolved. Account-keyed reconciliation lives in
    ``taxonomy`` + ``reconciliation_inputs`` (see ADR-0006). This deliberately
    omits ``account_key``/``confidence`` — they were never populated here and
    advertised an SSOT linkage this layer does not provide.
    """

    fact_id: str
    table_source: str
    cell_source: str
    label: str
    amount: int
    period: str
    role: str


@dataclass(frozen=True)
class SemanticNoteReferenceFact:
    """A DB-shaped note-reference fact extracted from a source table cell.

    One row means: this parsed table row displayed a reference to ``note_no`` at
    ``cell_source``. It is intentionally independent from account mapping so
    statement-note, note-note, and QA checks can share the same reference layer.
    """

    reference_id: str
    table_source: str
    row_source: str
    cell_source: str
    section_kind: str
    note_no: str
    raw_text: str
    context: str
    confidence: float


@dataclass(frozen=True)
class SemanticDataset:
    company: str
    tables: tuple[SemanticTable, ...]
    amount_facts: tuple[SemanticAmountFact, ...]
    note_references: tuple[SemanticNoteReferenceFact, ...]
    _tables_by_source: dict[str, SemanticTable]
    _amount_facts_by_table: dict[str, tuple[SemanticAmountFact, ...]]
    _note_references_by_row: dict[str, tuple[SemanticNoteReferenceFact, ...]]

    def table_for_source(self, source: str) -> SemanticTable | None:
        table_source = _table_source_for(source)
        if not table_source:
            return None
        return self._tables_by_source.get(table_source)

    def amount_facts_for_table(self, source: str) -> tuple[SemanticAmountFact, ...]:
        table_source = _table_source_for(source) or source
        return self._amount_facts_by_table.get(table_source, ())

    def note_references_for_row(self, source: str) -> tuple[SemanticNoteReferenceFact, ...]:
        row_source = _row_source_for(source)
        if not row_source:
            return ()
        return self._note_references_by_row.get(row_source, ())


def build_semantic_dataset(report: FullReport) -> SemanticDataset:
    order_index = build_report_order_index(report)
    raw_tables = _raw_tables_by_source(report)
    semantic_tables: list[SemanticTable] = []
    amount_facts: list[SemanticAmountFact] = []
    note_references: list[SemanticNoteReferenceFact] = []

    for entry in order_index.entries:
        table = raw_tables.get(entry.source)
        if table is None:
            continue
        semantic_tables.append(
            SemanticTable(
                company=report.company,
                source=entry.source,
                order=entry.order,
                section_kind=entry.section_kind,
                statement_kind=entry.statement_kind,
                section_id=entry.section_id,
                section_title=entry.section_title,
                note_no=entry.note_no,
                table_index=entry.table_index,
                heading=table.heading,
                row_count=len(table.rows),
                column_count=max((len(row) for row in table.rows), default=0),
                unit_multiplier=table.unit_multiplier,
                headers=tuple(table.rows[0]) if table.rows else (),
                row_labels=tuple(row[0] for row in table.rows[1:] if row),
                signatures=tuple(emit_signatures(table)),
            )
        )
        amount_facts.extend(_amount_facts_for_table(entry.source, table))
        note_references.extend(
            _note_reference_facts_for_table(entry.source, entry.section_kind, table)
        )

    return SemanticDataset(
        company=report.company,
        tables=tuple(semantic_tables),
        amount_facts=tuple(amount_facts),
        note_references=tuple(note_references),
        _tables_by_source={table.source: table for table in semantic_tables},
        _amount_facts_by_table=_group_amount_facts_by_table(amount_facts),
        _note_references_by_row=_group_note_references_by_row(note_references),
    )


def _raw_tables_by_source(report: FullReport) -> dict[str, ReportTable]:
    tables: dict[str, ReportTable] = {}
    for section in [*report.statements, *report.notes]:
        for table in _section_tables(section):
            tables[f"{section.section_id}/table:{table.index}"] = table
    return tables


def _section_tables(section: ReportSection) -> list[ReportTable]:
    return [
        block.table
        for block in section.blocks
        if block.table is not None and getattr(block.table, "rows", None)
    ]


def _table_source_for(source: str) -> str:
    if "/table:" not in source:
        return ""
    prefix, tail = source.split("/table:", 1)
    table_index = tail.split("/", 1)[0]
    return f"{prefix}/table:{table_index}"


def _row_source_for(source: str) -> str:
    table_source = _table_source_for(source)
    if not table_source or "/row:" not in source:
        return ""
    row_index = source.split("/row:", 1)[1].split("/", 1)[0]
    return f"{table_source}/row:{row_index}"


def _amount_facts_for_table(table_source: str, table: ReportTable) -> list[SemanticAmountFact]:
    if not table.rows:
        return []
    headers = table.rows[0]
    facts: list[SemanticAmountFact] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if not row:
            continue
        label = row[0]
        for col_idx in range(1, len(row)):
            amount = parse_amount(row[col_idx])
            if amount is None:
                continue
            facts.append(
                SemanticAmountFact(
                    fact_id=f"{table_source}:r{row_idx}:c{col_idx}",
                    table_source=table_source,
                    cell_source=f"{table_source}/row:{row_idx}/col:{col_idx}",
                    label=label,
                    amount=amount,
                    period=_period_for_column(headers, col_idx),
                    role=_role_for_label(label),
                )
            )
    return facts


def _note_reference_facts_for_table(
    table_source: str,
    section_kind: str,
    table: ReportTable,
) -> list[SemanticNoteReferenceFact]:
    rows = table.rows or []
    if not rows:
        return []
    headers = rows[0]
    facts: list[SemanticNoteReferenceFact] = []
    seen: set[tuple[str, str, str]] = set()
    for row_idx, row in enumerate(rows):
        for col_idx, cell in enumerate(row):
            explicit_tokens = extract_note_ref_tokens(cell)
            header = headers[col_idx] if col_idx < len(headers) else ""
            header_tokens = (
                extract_plain_note_ref_tokens(cell)
                if not explicit_tokens and _is_note_reference_header(header)
                else []
            )
            tokens = explicit_tokens or header_tokens
            if not tokens:
                continue
            context = "explicit_note_reference" if explicit_tokens else "note_reference_column"
            confidence = 0.95 if explicit_tokens else 0.9
            cell_source = f"{table_source}/row:{row_idx}/col:{col_idx}"
            row_source = f"{table_source}/row:{row_idx}"
            for note_no in tokens:
                key = (row_source, cell_source, note_no)
                if key in seen:
                    continue
                seen.add(key)
                facts.append(
                    SemanticNoteReferenceFact(
                        reference_id=f"{cell_source}:note{note_no}",
                        table_source=table_source,
                        row_source=row_source,
                        cell_source=cell_source,
                        section_kind=section_kind,
                        note_no=note_no,
                        raw_text=cell,
                        context=context,
                        confidence=confidence,
                    )
                )
    return facts


def _is_note_reference_header(value: str) -> bool:
    normalized = compact(value).lower()
    return normalized in {"주석", "주석번호", "관련주석", "참조주석", "note", "notes", "註"}


def _period_for_column(headers: list[str], col_idx: int) -> str:
    if col_idx >= len(headers):
        return "unknown"
    normalized = compact(headers[col_idx])
    if normalized in CURRENT_PERIOD_TOKENS:
        return "current"
    if normalized in PRIOR_PERIOD_TOKENS:
        return "prior"
    if "당기" in normalized:
        return "current"
    if "전기" in normalized:
        return "prior"
    return "unknown"


def _role_for_label(label: str) -> str:
    """Classify a row label's movement role (beginning/ending/total/movement).

    This is one of three intentionally-distinct role vocabularies (ADR-0006 S2),
    each scoped to its layer — do not merge them:
    - here: rollforward *movement* role of a note row (beginning/ending/...);
    - ``label_resolver.AccountRole``: which *statement account* a row is
      (asset_total/cash_end/...);
    - ``orientation`` MOVEMENT/MEASURE/PERIOD label groups: table *structure*
      detection, not a per-row role.
    """
    normalized = compact(label)
    if normalized.startswith("기초") or normalized in {"전기말", "전기말잔액"}:
        return "beginning"
    if normalized.startswith("기말") or normalized in {"당기말", "당기말잔액"}:
        return "ending"
    if normalized in {"합계", "소계", "총계", "계"}:
        return "total"
    return "movement"


def _group_amount_facts_by_table(
    facts: list[SemanticAmountFact],
) -> dict[str, tuple[SemanticAmountFact, ...]]:
    grouped: dict[str, list[SemanticAmountFact]] = {}
    for fact in facts:
        grouped.setdefault(fact.table_source, []).append(fact)
    return {source: tuple(items) for source, items in grouped.items()}


def _group_note_references_by_row(
    facts: list[SemanticNoteReferenceFact],
) -> dict[str, tuple[SemanticNoteReferenceFact, ...]]:
    grouped: dict[str, list[SemanticNoteReferenceFact]] = {}
    for fact in facts:
        grouped.setdefault(fact.row_source, []).append(fact)
    return {source: tuple(items) for source, items in grouped.items()}
