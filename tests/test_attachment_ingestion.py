import pytest
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from dart_footing_reconciler.attachment_ingestion import (
    AttachmentIngestionError,
    detect_attachment_format,
    parse_report_attachment,
)


REPORT_BODY = """
<p>재무상태표</p>
<table><tr><th>구분</th><th>당기</th></tr><tr><td>자산총계</td><td>1,000</td></tr></table>
<p>재무제표 주석</p>
<p>8. 매출채권</p>
<table><tr><th>구분</th><th>금액</th></tr><tr><td>합계</td><td>100</td></tr></table>
"""

NOTE_ONLY_BODY = """
<p>재무제표 주석</p>
<p>1. 일반사항</p>
<table><tr><th>구분</th><th>금액</th></tr><tr><td>자본금</td><td>100</td></tr></table>
"""


def _structured_markup(input_format: str, body: str = REPORT_BODY) -> str:
    if input_format == "dsd":
        return f'<?xml version="1.0" encoding="UTF-8"?>\n<DOCUMENT>{body}</DOCUMENT>'
    if input_format == "xml":
        return f'<?xml version="1.0" encoding="UTF-8"?>\n<REPORT>{body}</REPORT>'
    if input_format == "html":
        return f"<!doctype html><html><head><title>DART</title></head><body>{body}</body></html>"
    raise AssertionError(f"unsupported test format: {input_format}")


def _native_financial_pdf(path) -> None:
    pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = "HYSMyeongJo-Medium"
    table_style = TableStyle(
        [
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("FONTNAME", (0, 0), (-1, -1), "HYSMyeongJo-Medium"),
        ]
    )
    SimpleDocTemplate(str(path)).build(
        [
            Paragraph("재무상태표", styles["Heading1"]),
            Table([["구분", "당기"], ["자산총계", "1,000"]], style=table_style),
            Spacer(1, 12),
            Paragraph("재무제표 주석", styles["Heading1"]),
            Paragraph("8. 매출채권", styles["Heading2"]),
            Table([["구분", "금액"], ["합계", "100"]], style=table_style),
        ]
    )


@pytest.mark.parametrize(
    "suffix,encoding,markup",
    [
        ("html", "utf-8", _structured_markup("html")),
        ("dsd", "cp949", _structured_markup("dsd")),
        ("xml", "utf-8", _structured_markup("xml")),
    ],
)
def test_equivalent_structured_attachments_produce_equivalent_reports(
    tmp_path, suffix, encoding, markup
):
    path = tmp_path / f"report.{suffix}"
    path.write_bytes(markup.encode(encoding))

    parsed = parse_report_attachment(path, company="Sample Co")

    assert parsed.input_format == suffix
    assert [section.title for section in parsed.report.statements] == ["재무상태표"]
    assert [(note.note_no, note.title) for note in parsed.report.notes] == [
        ("8", "매출채권")
    ]
    assert parsed.report.notes[0].blocks[0].location.input_format == suffix


@pytest.mark.parametrize(
    "filename,content_format",
    [
        ("report.html", "xml"),
        ("report.xml", "dsd"),
        ("report.dsd", "html"),
    ],
)
def test_strong_structured_content_wins_and_adds_one_mismatch_diagnostic(
    tmp_path,
    filename,
    content_format,
):
    path = tmp_path / filename
    path.write_text(_structured_markup(content_format), encoding="utf-8")

    parsed = parse_report_attachment(path)

    assert parsed.input_format == content_format
    assert len(parsed.diagnostics) == 1
    assert parsed.diagnostics[0].code == "ATTACHMENT_FORMAT_MISMATCH"
    assert parsed.diagnostics[0].message == (
        "파일 확장자와 내용 형식이 달라 내용에서 확인된 형식을 사용했습니다."
    )
    locations = [
        location
        for section in [*parsed.report.statements, *parsed.report.notes]
        for block in section.blocks
        for location in (
            block.location,
            block.table.location if block.table is not None else None,
        )
        if location is not None
    ]
    assert locations
    assert {location.input_format for location in locations} == {content_format}


@pytest.mark.parametrize(
    "content_format,markup",
    [
        ("xml", _structured_markup("xml")),
        ("dsd", f"<DART>{REPORT_BODY}</DART>"),
        ("html", _structured_markup("html")),
    ],
)
def test_unknown_suffix_accepts_strong_structured_content_without_mismatch(
    tmp_path,
    content_format,
    markup,
):
    path = tmp_path / f"report-{content_format}.bin"
    path.write_text(markup, encoding="utf-8")

    parsed = parse_report_attachment(path)

    assert parsed.input_format == content_format
    assert parsed.diagnostics == ()


def test_unknown_suffix_without_strong_signature_remains_unsupported(tmp_path):
    path = tmp_path / "report.bin"
    path.write_text(REPORT_BODY, encoding="utf-8")

    with pytest.raises(AttachmentIngestionError) as exc:
        parse_report_attachment(path)

    assert exc.value.code == "ATTACHMENT_FORMAT_UNSUPPORTED"


@pytest.mark.parametrize("content_format", ["html", "dsd", "xml"])
def test_matching_suffix_and_strong_content_has_no_mismatch(
    tmp_path,
    content_format,
):
    path = tmp_path / f"report.{content_format}"
    path.write_text(_structured_markup(content_format), encoding="utf-8")

    parsed = parse_report_attachment(path)

    assert parsed.input_format == content_format
    assert parsed.diagnostics == ()


def test_html_fragment_keeps_suffix_fallback_without_mismatch(tmp_path):
    path = tmp_path / "fragment.html"
    path.write_text(REPORT_BODY, encoding="utf-8")

    parsed = parse_report_attachment(path)

    assert parsed.input_format == "html"
    assert parsed.diagnostics == ()


@pytest.mark.parametrize(
    "suffix,encoding,markup",
    [
        ("html", "utf-8", _structured_markup("html", NOTE_ONLY_BODY)),
        ("dsd", "cp949", _structured_markup("dsd", NOTE_ONLY_BODY)),
        ("xml", "utf-8", _structured_markup("xml", NOTE_ONLY_BODY)),
    ],
)
def test_structured_note_only_attachment_remains_supported(
    tmp_path,
    suffix,
    encoding,
    markup,
):
    path = tmp_path / f"note-only.{suffix}"
    path.write_bytes(markup.encode(encoding))

    parsed = parse_report_attachment(path)

    assert parsed.input_format == suffix
    assert parsed.diagnostics == ()
    assert parsed.report.statements == []
    assert [(note.note_no, note.title) for note in parsed.report.notes] == [
        ("1", "일반사항")
    ]


def test_pdf_signature_wins_over_html_extension(tmp_path):
    path = tmp_path / "wrong.html"
    path.write_bytes(b"%PDF-1.7\n")
    assert detect_attachment_format(path, path.read_bytes()) == "pdf"


@pytest.mark.parametrize("suffix", ["html", "xml", "dsd"])
def test_pdf_signature_behind_structured_suffix_adds_one_mismatch_diagnostic(
    tmp_path,
    suffix,
):
    pdf_path = tmp_path / "source.pdf"
    _native_financial_pdf(pdf_path)
    disguised_path = tmp_path / f"report.{suffix}"
    disguised_path.write_bytes(pdf_path.read_bytes())

    parsed = parse_report_attachment(disguised_path)

    assert parsed.input_format == "pdf"
    assert [diagnostic.code for diagnostic in parsed.diagnostics].count(
        "ATTACHMENT_FORMAT_MISMATCH"
    ) == 1
    assert {diagnostic.code for diagnostic in parsed.diagnostics} == {
        "ATTACHMENT_FORMAT_MISMATCH"
    }
    locations = [
        block.location
        for section in [*parsed.report.statements, *parsed.report.notes]
        for block in section.blocks
    ]
    assert locations
    assert {location.input_format for location in locations} == {"pdf"}


def test_structurally_empty_attachment_is_rejected(tmp_path):
    path = tmp_path / "empty.xml"
    path.write_text("<DOCUMENT><p>설명만 있습니다.</p></DOCUMENT>", encoding="utf-8")

    with pytest.raises(AttachmentIngestionError) as exc:
        parse_report_attachment(path)

    assert exc.value.code == "REPORT_STRUCTURE_NOT_FOUND"


def test_attachment_with_section_but_no_usable_table_is_rejected(tmp_path):
    path = tmp_path / "empty.html"
    path.write_text("<p>재무상태표</p><p>설명만 있습니다.</p>", encoding="utf-8")

    with pytest.raises(AttachmentIngestionError) as exc:
        parse_report_attachment(path)

    assert exc.value.code == "REPORT_STRUCTURE_NOT_FOUND"


@pytest.mark.parametrize(
    "table_markup",
    [
        "<table><tr><th>구분</th><th>당기</th></tr></table>",
        (
            "<table><tr><th>구분</th><th>당기</th></tr>"
            "<tr><td></td><td></td></tr></table>"
        ),
    ],
    ids=["header-only", "blank-body"],
)
def test_attachment_rejects_table_without_amount_bearing_data_row(
    tmp_path, table_markup
):
    path = tmp_path / "empty.html"
    path.write_text(f"<p>재무상태표</p>{table_markup}", encoding="utf-8")

    with pytest.raises(AttachmentIngestionError) as exc:
        parse_report_attachment(path)

    assert exc.value.code == "REPORT_STRUCTURE_NOT_FOUND"
