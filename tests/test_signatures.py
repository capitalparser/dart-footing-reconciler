# tests/test_signatures.py
from dart_footing_reconciler.document import ReportTable, SourceLocation
from dart_footing_reconciler.signatures import emit_signatures


def _table(rows: list[list[str]], heading: str = "테스트표") -> ReportTable:
    return ReportTable(0, rows, heading, SourceLocation("note:1", 0, 0))


def test_emit_rollforward_axis_on_기초기말_rows():
    table = _table([
        ["구분", "금액"],
        ["기초장부금액", "1,000"],
        ["취득", "200"],
        ["처분", "(50)"],
        ["기말장부금액", "1,150"],
    ])
    matches = emit_signatures(table)
    sigs = {m.signature for m in matches}
    assert "rollforward_axis" in sigs


def test_emit_internal_closure_on_합계_column_header():
    table = _table([
        ["구분", "A", "B", "합계"],
        ["항목1", "100", "200", "300"],
    ])
    matches = emit_signatures(table)
    sigs = {m.signature for m in matches}
    assert "internal_closure" in sigs


def test_emit_internal_closure_on_합계_row():
    table = _table([
        ["구분", "금액"],
        ["항목1", "100"],
        ["합계", "100"],
    ])
    matches = emit_signatures(table)
    sigs = {m.signature for m in matches}
    assert "internal_closure" in sigs


def test_emit_statement_core_match_on_유형자산_label():
    table = _table([
        ["구분", "당기"],
        ["유형자산", "5,000"],
    ])
    matches = emit_signatures(table)
    sigs = {m.signature for m in matches}
    assert "statement_core_match" in sigs


def test_qualitative_table_has_no_signatures():
    table = _table([
        ["내용"],
        ["본 회사는 K-IFRS 제1001호에 따라 재무제표를 작성하였음."],
    ])
    matches = emit_signatures(table)
    assert not matches


def test_signature_match_has_confidence_field():
    table = _table([
        ["구분", "금액"],
        ["기초장부금액", "1,000"],
        ["기말장부금액", "1,000"],
    ])
    matches = emit_signatures(table)
    for m in matches:
        assert 0.0 <= m.confidence <= 1.0
