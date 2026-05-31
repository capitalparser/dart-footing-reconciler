from dart_footing_reconciler.document import ReportSection
from dart_footing_reconciler.scope import primary_note_sections


def _note(idx: int, title: str) -> ReportSection:
    return ReportSection(f"note:{idx}", title, "note", str(idx), [])


def test_primary_note_sections_prefers_explicit_consolidated_block_when_present():
    consolidated = [_note(idx, f"주석 {idx} (연결)") for idx in range(1, 11)]
    separate = [_note(idx, f"주석 {idx}") for idx in range(11, 16)]

    assert primary_note_sections(consolidated + separate) == consolidated


def test_primary_note_sections_keeps_all_notes_when_consolidated_marker_is_sparse():
    notes = [_note(1, "연결재무제표 작성기준"), _note(2, "매출채권"), _note(3, "유형자산")]

    assert primary_note_sections(notes) == notes


def test_primary_note_sections_uses_leading_block_before_embedded_statement_appendix():
    consolidated_notes = [_note(idx, f"연결 주석 {idx}") for idx in range(1, 13)]
    statement_appendix = ReportSection("note:4-1", "재무상태표", "note", "4-1", [])
    separate_notes = [_note(idx, f"별도 주석 {idx}") for idx in range(13, 25)]

    assert primary_note_sections(consolidated_notes + [statement_appendix] + separate_notes) == consolidated_notes
