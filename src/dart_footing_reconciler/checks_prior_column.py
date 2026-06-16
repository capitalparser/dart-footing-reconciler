"""Same-file prior-period column reconciliation checks."""

from __future__ import annotations

from dataclasses import dataclass

from dart_footing_reconciler.amount_compare import amounts_agree, display_unit_tolerance
from dart_footing_reconciler.checks import CheckEvidence, CheckResult, MATCHED, UNEXPLAINED_GAP
from dart_footing_reconciler.checks_fs_note import FS_NOTE_ACCOUNT_KEYS
from dart_footing_reconciler.document import FullReport, ReportSection, ReportTable
from dart_footing_reconciler.report_frame import statement_kind_from_source, statement_kind_from_title
from dart_footing_reconciler.scope import primary_note_sections
from dart_footing_reconciler.table_semantics import (
    amount_from_prior_period,
    balance_amount,
    compact,
    row_amount_prefer_current,
)
from dart_footing_reconciler.taxonomy import TAXONOMY, TaxonomyEntry


_ENDING_NOTE_LABEL_PRIORITY = ("기말장부금액", "기말잔액", "장부금액", "순장부금액", "합계")
_BEGINNING_LABELS = ("기초장부금액", "기초잔액", "기초금액", "전기말", "기초")
_ROLLFORWARD_TOKENS = ("변동내역", "증감", "장부금액", "변동")


@dataclass(frozen=True)
class _AmountHit:
    account_key: str
    display_name: str
    amount: int
    label: str
    source: str
    section_title: str
    note_no: str = ""
    #: Disclosure step of the source table in KRW (amount already scaled by it),
    #: kept so note-side comparisons can allow sub-display-unit rounding.
    unit_multiplier: int = 1


def check_prior_column_matches(report: FullReport, *, tolerance: int = 1) -> list[CheckResult]:
    """Compare prior-period statement columns with same-file note evidence."""
    results: list[CheckResult] = []
    entries = [entry for entry in TAXONOMY if entry.key in FS_NOTE_ACCOUNT_KEYS]
    scoped_report = FullReport(
        report.source,
        report.company,
        report.statements,
        primary_note_sections(report.notes),
    )
    for entry in entries:
        fs_hit = _find_prior_statement_hit(scoped_report, entry)
        if fs_hit is None:
            continue
        note_hit = _find_prior_note_hit(scoped_report, entry)
        if note_hit is not None:
            results.append(_fs_note_result(entry, fs_hit, note_hit, tolerance))
        beginning_hit = _find_rollforward_beginning_hit(scoped_report, entry)
        if beginning_hit is not None:
            results.append(_rollforward_result(entry, fs_hit, beginning_hit, tolerance))
    return results


def _find_prior_statement_hit(report: FullReport, entry: TaxonomyEntry) -> _AmountHit | None:
    for section in report.statements:
        if not _section_matches_statement(section, entry):
            continue
        kind = statement_kind_from_title(section.title) or statement_kind_from_source(section.section_id)
        for table in _tables(section):
            for row_idx, row in enumerate(table.rows[1:], start=1):
                if not row or not _matches_any(row[0], entry.statement_aliases):
                    continue
                amount, col_idx = amount_from_prior_period(row, table.rows[0])
                if amount is None or col_idx is None:
                    continue
                source_prefix = f"statement:{_statement_source_alias(kind)}" if kind else section.section_id
                return _AmountHit(
                    account_key=entry.key,
                    display_name=entry.display_name,
                    amount=amount * table.unit_multiplier,
                    label=row[0],
                    source=f"{source_prefix}/table:{table.index}/row:{row_idx}/col:{col_idx}",
                    section_title=section.title,
                )
    return None


def _find_prior_note_hit(report: FullReport, entry: TaxonomyEntry) -> _AmountHit | None:
    hits: list[_AmountHit] = []
    for section in report.notes:
        if not _section_matches_note(section, entry):
            continue
        for table in _tables(section):
            if not _table_matches_note(table, entry):
                continue
            for row_idx, row in enumerate(table.rows[1:], start=1):
                if not row or not _matches_note_amount_label(row[0], entry):
                    continue
                # PC1 requires an explicit prior-period column; single-period note tables stay out.
                amount, col_idx = amount_from_prior_period(row, table.rows[0])
                if amount is None or col_idx is None:
                    continue
                hits.append(
                    _AmountHit(
                        account_key=entry.key,
                        display_name=entry.display_name,
                        amount=amount * table.unit_multiplier,
                        label=row[0],
                        source=f"note:{section.note_no}/table:{table.index}/row:{row_idx}/col:{col_idx}",
                        section_title=section.title,
                        note_no=section.note_no,
                        unit_multiplier=table.unit_multiplier,
                    )
                )
    return _select_note_hit_by_label(hits, entry)


def _find_rollforward_beginning_hit(report: FullReport, entry: TaxonomyEntry) -> _AmountHit | None:
    for section in report.notes:
        if not _section_matches_note(section, entry):
            continue
        for table in _tables(section):
            if not _looks_like_rollforward(section, table, entry):
                continue
            for row_idx, row in enumerate(table.rows[1:], start=1):
                if not row or not _matches_beginning_label(row[0]):
                    continue
                if not _beginning_row_matches_account(row, table.rows[0], table, entry):
                    continue
                amount, col_idx = row_amount_prefer_current(row, table.rows[0])
                if amount is None or col_idx is None:
                    amount, col_idx = balance_amount(row, table.rows[0])
                if amount is None or col_idx is None:
                    continue
                return _AmountHit(
                    account_key=entry.key,
                    display_name=entry.display_name,
                    amount=amount * table.unit_multiplier,
                    label=row[0],
                    source=f"note:{section.note_no}/table:{table.index}/row:{row_idx}/col:{col_idx}",
                    section_title=section.title,
                    note_no=section.note_no,
                    unit_multiplier=table.unit_multiplier,
                )
    return None


def _fs_note_result(
    entry: TaxonomyEntry, fs_hit: _AmountHit, note_hit: _AmountHit, tolerance: int
) -> CheckResult:
    difference = note_hit.amount - fs_hit.amount
    status = (
        MATCHED
        if amounts_agree(fs_hit.amount, note_hit.amount, tolerance, display_unit=note_hit.unit_multiplier)
        else UNEXPLAINED_GAP
    )
    effective_tolerance = display_unit_tolerance(
        fs_hit.amount, note_hit.amount, tolerance, display_unit=note_hit.unit_multiplier
    )
    matched_reason = (
        "prior-period financial statement amount agrees to note amount"
        if difference == 0
        else "prior-period financial statement amount agrees within display-unit rounding"
    )
    return CheckResult(
        check_id=f"prior_column_fs_note:{entry.key}:{note_hit.note_no}",
        check_type="prior_column_fs_note",
        status=status,
        scope="report",
        note_no=note_hit.note_no,
        title=f"{entry.display_name} 전기 재무제표-주석 대사",
        expected=fs_hit.amount,
        actual=note_hit.amount,
        difference=difference,
        tolerance=effective_tolerance,
        reason=matched_reason
        if status == MATCHED
        else "prior-period financial statement amount does not agree to note amount",
        evidence=[
            CheckEvidence(f"전기 {fs_hit.section_title} {fs_hit.label}", fs_hit.amount, fs_hit.source),
            CheckEvidence(f"주석 {note_hit.note_no} 전기 {note_hit.label}", note_hit.amount, note_hit.source),
        ],
    )


def _rollforward_result(
    entry: TaxonomyEntry, fs_hit: _AmountHit, beginning_hit: _AmountHit, tolerance: int
) -> CheckResult:
    difference = beginning_hit.amount - fs_hit.amount
    status = (
        MATCHED
        if amounts_agree(
            fs_hit.amount, beginning_hit.amount, tolerance, display_unit=beginning_hit.unit_multiplier
        )
        else UNEXPLAINED_GAP
    )
    effective_tolerance = display_unit_tolerance(
        fs_hit.amount, beginning_hit.amount, tolerance, display_unit=beginning_hit.unit_multiplier
    )
    matched_reason = (
        "roll-forward beginning balance agrees to prior-period statement balance"
        if difference == 0
        else "roll-forward beginning balance agrees within display-unit rounding"
    )
    return CheckResult(
        check_id=f"prior_column_rollforward:{entry.key}:{beginning_hit.note_no}",
        check_type="prior_column_rollforward",
        status=status,
        scope="report",
        note_no=beginning_hit.note_no,
        title=f"{entry.display_name} 기초-전기말 대사",
        expected=fs_hit.amount,
        actual=beginning_hit.amount,
        difference=difference,
        tolerance=effective_tolerance,
        reason=matched_reason
        if status == MATCHED
        else "roll-forward beginning balance does not agree to prior-period statement balance",
        evidence=[
            CheckEvidence(f"전기 {fs_hit.section_title} {fs_hit.label}", fs_hit.amount, fs_hit.source),
            CheckEvidence(
                f"주석 {beginning_hit.note_no} {beginning_hit.label}",
                beginning_hit.amount,
                beginning_hit.source,
            ),
        ],
    )


def _tables(section: ReportSection) -> list[ReportTable]:
    return [block.table for block in section.blocks if block.table is not None and block.table.rows]


def _section_matches_statement(section: ReportSection, entry: TaxonomyEntry) -> bool:
    text = compact(section.title)
    return any(compact(title) in text for title in entry.statement_titles)


def _section_matches_note(section: ReportSection, entry: TaxonomyEntry) -> bool:
    return _matches_any(section.title, entry.note_title_aliases)


def _table_matches_note(table: ReportTable, entry: TaxonomyEntry) -> bool:
    return _matches_any(table.heading, entry.note_title_aliases) or bool(table.heading)


def _matches_note_amount_label(label: str, entry: TaxonomyEntry) -> bool:
    if any(_matches(label, excluded) for excluded in entry.note_amount_exclusions):
        return False
    return _matches_any(label, entry.note_amount_aliases) or _label_rank(label) is not None


def _select_note_hit_by_label(hits: list[_AmountHit], entry: TaxonomyEntry) -> _AmountHit | None:
    if not hits:
        return None
    aliases = tuple(
        dict.fromkeys(
            compact(alias)
            for alias in (*_ENDING_NOTE_LABEL_PRIORITY, *entry.note_amount_aliases)
            if alias
        )
    )
    ranked = [
        (rank, index, hit)
        for index, hit in enumerate(hits)
        if (rank := _label_rank(hit.label, aliases)) is not None
    ]
    if not ranked:
        return hits[0]
    ranked.sort(key=lambda item: (item[0], item[1]))
    return ranked[0][2]


def _label_rank(label: str, aliases: tuple[str, ...] = _ENDING_NOTE_LABEL_PRIORITY) -> int | None:
    normalized = compact(label)
    for index, alias in enumerate(aliases):
        if alias and compact(alias) in normalized:
            return index
    return None


def _looks_like_rollforward(section: ReportSection, table: ReportTable, entry: TaxonomyEntry) -> bool:
    text = compact(f"{section.title} {table.heading}")
    has_topic = _matches_any(text, entry.note_title_aliases)
    has_rollforward_text = any(token in text for token in _ROLLFORWARD_TOKENS)
    has_beginning = any(row and _matches_beginning_label(row[0]) for row in table.rows[1:])
    return has_topic and has_beginning and (has_rollforward_text or _has_ending_row(table))


def _has_ending_row(table: ReportTable) -> bool:
    ending_aliases = ("기말", "기말장부금액", "기말잔액", "당기말")
    return any(row and any(compact(row[0]).startswith(alias) for alias in ending_aliases) for row in table.rows[1:])


def _matches_beginning_label(label: str) -> bool:
    normalized = compact(label)
    return any(normalized.startswith(compact(alias)) for alias in _BEGINNING_LABELS)


def _beginning_row_matches_account(
    row: list[str], headers: list[str], table: ReportTable, entry: TaxonomyEntry
) -> bool:
    if entry.key in {"property_plant_equipment", "intangible_assets", "investment_property"}:
        return True
    label = compact(row[0])
    context = compact(" ".join([table.heading, *headers, *row]))
    if "사용권자산" in label and entry.key == "lease_liabilities":
        return False
    required_tokens = {
        "borrowings": ("차입금", "차입", "부채", "순부채"),
        "bonds": ("사채", "부채", "순부채"),
        "lease_liabilities": ("리스부채", "부채", "순부채"),
    }.get(entry.key)
    if required_tokens is None:
        return False
    return any(token in context for token in required_tokens)


def _matches_any(value: str, aliases: tuple[str, ...]) -> bool:
    return any(_matches(value, alias) for alias in aliases)


def _matches(value: str, alias: str) -> bool:
    normalized_value = compact(value)
    normalized_alias = compact(alias)
    return bool(normalized_alias) and normalized_alias in normalized_value


def _statement_source_alias(kind: str) -> str:
    return {
        "financial_position": "bs",
        "income_statement": "is",
        "changes_in_equity": "sce",
        "cash_flows": "cf",
    }.get(kind, kind)
