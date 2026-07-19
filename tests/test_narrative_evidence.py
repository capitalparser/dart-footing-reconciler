from dart_footing_reconciler.document import (
    FullReport,
    ReportBlock,
    ReportSection,
    ReportTable,
    SourceLocation,
)
from dart_footing_reconciler.narrative_evidence import build_narrative_evidence


def _note(
    note_no: str,
    table_rows: list[list[str]],
    narratives: list[tuple[str, tuple[str, ...]]],
    *,
    scope: str = "consolidated",
) -> ReportSection:
    table = ReportTable(
        int(note_no),
        table_rows,
        f"주석 {note_no}",
        SourceLocation(f"note:{note_no}", 0, int(note_no)),
        unit_multiplier=1,
    )
    blocks = [ReportBlock("table", "", table, table.location)]
    for text, segments in narratives:
        blocks.append(
            ReportBlock(
                "text",
                text,
                None,
                SourceLocation(f"note:{note_no}", len(blocks)),
                raw_text="\n".join(segments),
                text_segments=segments,
                raw_tag="p",
                wrapper_class="nb",
            )
        )
    return ReportSection(
        f"note:{note_no}",
        f"주석 {note_no}",
        "note",
        note_no,
        blocks,
        scope,
    )


def test_exact_marker_attaches_narrative_to_preceding_table():
    note = _note(
        "15",
        [["구분", "금액"], ["대체 등 (*)", "100"]],
        [("(*) 유형자산으로 대체된 금액이 포함됩니다.", ("(*) 유형자산으로 대체된 금액이 포함됩니다.",))],
    )

    dataset = build_narrative_evidence(FullReport("s.html", "Co", [], [note]))

    assert dataset.segments[0].source.source_key == "note:15@consolidated/block:1/segment:0"
    assert dataset.segments[0].marker == "(*)"
    assert dataset.attachments[0].table_source == "note:15/table:15"
    assert dataset.attachments[0].direction == "backward"
    assert dataset.attachments[0].confidence == 1.0


def test_marker_amount_and_explicit_note_reference_become_typed_facts():
    note = _note(
        "16",
        [["구분", "금액"], ["우리은행 차입금", "18,000,000"]],
        [
            (
                "[주2] 우리은행 차입금 18,000,000천원은 합병으로 이관되었습니다(주석 31 참조).",
                (
                    "[주2] 우리은행 차입금 18,000,000천원은 합병으로 이관되었습니다(주석 31 참조).",
                ),
            )
        ],
        scope="separate",
    )

    dataset = build_narrative_evidence(FullReport("s.html", "Co", [], [note]))

    assert dataset.attachments[0].confidence == 0.9
    assert dataset.attachments[0].evidence == "adjacent_explicit_marker"
    assert dataset.note_references[0].note_no == "31"
    assert dataset.note_references[0].source.scope == "separate"
    assert dataset.amount_mentions[0].amount == 18_000_000_000
    assert dataset.amount_mentions[0].role == "borrowing_transferred_by_merger"


def test_markerless_backward_language_requires_shared_table_noun():
    note = _note(
        "19",
        [["구분", "금액"], ["장ㆍ단기차입금", "100"]],
        [("한편, 상기 장ㆍ단기차입금은 유형자산을 담보로 제공합니다(주석 34 참조).", ("한편, 상기 장ㆍ단기차입금은 유형자산을 담보로 제공합니다(주석 34 참조).",))],
    )

    dataset = build_narrative_evidence(FullReport("s.html", "Co", [], [note]))

    assert dataset.attachments[0].confidence == 0.7
    assert dataset.attachments[0].evidence == "backward_reference_with_shared_noun"
    assert dataset.note_references[0].note_no == "34"


def test_inline_next_heading_is_split_from_preceding_table_narrative():
    text = (
        "상기 요약 재무정보는 내부거래 제거 전 금액입니다. "
        "1-3 종속기업의 변동내역 당분기 변동은 다음과 같습니다."
    )
    note = _note(
        "1",
        [["회사", "자산"], ["종속기업", "100"]],
        [(text, (text,))],
    )

    dataset = build_narrative_evidence(FullReport("s.html", "Co", [], [note]))

    assert [segment.text for segment in dataset.segments] == [
        "상기 요약 재무정보는 내부거래 제거 전 금액입니다.",
        "1-3 종속기업의 변동내역 당분기 변동은 다음과 같습니다.",
    ]
    assert len(dataset.attachments) == 1
    assert dataset.attachments[0].segment_source.endswith("/segment:0")


def test_shareholder_approval_disclaimer_is_preserved_but_not_reconciled():
    note = _note(
        "20",
        [["구분", "금액"], ["미처분이익잉여금", "100"]],
        [("※ 상기 재무제표는 주주총회 승인 전 재무제표입니다.", ("※ 상기 재무제표는 주주총회 승인 전 재무제표입니다.",))],
    )

    dataset = build_narrative_evidence(FullReport("s.html", "Co", [], [note]))
    source_key = dataset.segments[0].source.source_key

    assert dataset.segments[0].is_disclaimer is True
    assert dataset.attachments == ()
    assert dataset.reconciliation_candidates_for(source_key) == ()
