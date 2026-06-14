"""Semantic dataset layer over parsed DART report tables."""

from __future__ import annotations

from dataclasses import dataclass

from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.document import FullReport, ReportSection, ReportTable
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
class SemanticDataset:
    company: str
    tables: tuple[SemanticTable, ...]
    amount_facts: tuple[SemanticAmountFact, ...]
    _tables_by_source: dict[str, SemanticTable]
    _amount_facts_by_table: dict[str, tuple[SemanticAmountFact, ...]]

    def table_for_source(self, source: str) -> SemanticTable | None:
        table_source = _table_source_for(source)
        if not table_source:
            return None
        return self._tables_by_source.get(table_source)

    def amount_facts_for_table(self, source: str) -> tuple[SemanticAmountFact, ...]:
        table_source = _table_source_for(source) or source
        return self._amount_facts_by_table.get(table_source, ())


def build_semantic_dataset(report: FullReport) -> SemanticDataset:
    order_index = build_report_order_index(report)
    raw_tables = _raw_tables_by_source(report)
    semantic_tables: list[SemanticTable] = []
    amount_facts: list[SemanticAmountFact] = []

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

    return SemanticDataset(
        company=report.company,
        tables=tuple(semantic_tables),
        amount_facts=tuple(amount_facts),
        _tables_by_source={table.source: table for table in semantic_tables},
        _amount_facts_by_table=_group_amount_facts_by_table(amount_facts),
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
