"""Scope helpers for reports that include consolidated and separate notes."""

from __future__ import annotations

from dart_footing_reconciler.document import ReportSection


def primary_note_sections(notes: list[ReportSection]) -> list[ReportSection]:
    consolidated = [note for note in notes if _explicitly_consolidated(note.title)]
    if len(consolidated) >= 10 and len(consolidated) < len(notes):
        return consolidated
    first_statement_appendix = _first_embedded_statement_index(notes)
    if first_statement_appendix is not None:
        leading_notes = notes[:first_statement_appendix]
        trailing_notes = notes[first_statement_appendix + 1 :]
        if len(leading_notes) >= 10 and len(trailing_notes) >= 10:
            return leading_notes
    return notes


def _explicitly_consolidated(title: str) -> bool:
    normalized = title.replace(" ", "")
    return "(연결)" in normalized


def _first_embedded_statement_index(notes: list[ReportSection]) -> int | None:
    for idx, note in enumerate(notes):
        if _looks_like_embedded_statement_note(note):
            return idx
    return None


def _looks_like_embedded_statement_note(note: ReportSection) -> bool:
    normalized_title = note.title.replace(" ", "")
    normalized_no = note.note_no.replace(" ", "")
    statement_titles = ("재무상태표", "손익계산서", "포괄손익계산서", "자본변동표", "현금흐름표")
    if not any(title in normalized_title for title in statement_titles):
        return False
    return "-" in normalized_no or normalized_no.startswith(("4", "5"))
