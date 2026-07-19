import pytest
from bs4 import BeautifulSoup
from pdfminer.pdfdocument import PDFEncryptionError
from pdfplumber.utils.exceptions import PdfminerException
from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from dart_footing_reconciler.attachment_ingestion import (
    AttachmentIngestionError,
    parse_report_attachment,
)
from dart_footing_reconciler import pdf_ingestion
from dart_footing_reconciler.pdf_ingestion import extract_pdf_markup


GRID_STYLE = TableStyle(
    [
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("FONTNAME", (0, 0), (-1, -1), "HYSMyeongJo-Medium"),
    ]
)
BORDERLESS_STYLE = TableStyle([("FONTNAME", (0, 0), (-1, -1), "HYSMyeongJo-Medium")])


def _native_financial_pdf(path):
    pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = "HYSMyeongJo-Medium"
    doc = SimpleDocTemplate(str(path))
    doc.build(
        [
            Paragraph("재무상태표", styles["Heading1"]),
            Table(
                [["구분", "당기"], ["자산총계", "1,000"]],
                style=GRID_STYLE,
            ),
            Spacer(1, 12),
            Paragraph("재무제표 주석", styles["Heading1"]),
            Paragraph("8. 매출채권", styles["Heading2"]),
            Table([["구분", "금액"], ["합계", "100"]], style=GRID_STYLE),
        ]
    )


def _native_note_only_pdf(path):
    pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = "HYSMyeongJo-Medium"
    doc = SimpleDocTemplate(str(path))
    doc.build(
        [
            Paragraph("재무제표 주석", styles["Heading1"]),
            Paragraph("1. 일반사항", styles["Heading2"]),
            Table([["구분", "금액"], ["자본금", "100"]], style=GRID_STYLE),
        ]
    )


def _unsupported_english_statement_pdf(path):
    pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = "HYSMyeongJo-Medium"
    doc = SimpleDocTemplate(str(path))
    doc.build(
        [
            Paragraph("1. STATEMENTS OF FINANCIAL POSITION", styles["Heading1"]),
            Table(
                [["Description", "Current"], ["Total assets", "1,000"]],
                style=GRID_STYLE,
            ),
        ]
    )


def _borderless_financial_pdf(path):
    pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = "HYSMyeongJo-Medium"
    doc = SimpleDocTemplate(str(path))
    doc.build(
        [
            Paragraph("재무상태표", styles["Heading1"]),
            Table(
                [["구분", "당기"], ["자산총계", "1,000"]],
                style=GRID_STYLE,
            ),
            Spacer(1, 12),
            Paragraph("재무제표 주석", styles["Heading1"]),
            Paragraph("8. 매출채권", styles["Heading2"]),
            Table(
                [["구분", "금액"], ["합계", "100"]],
                style=GRID_STYLE,
            ),
            PageBreak(),
            Table(
                [
                    ["구분", "당기"],
                    ["추가자산", "200"],
                    ["추가부채", "300"],
                ],
                style=BORDERLESS_STYLE,
            ),
        ]
    )


def _special_character_pdf(path):
    pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = "HYSMyeongJo-Medium"
    doc = SimpleDocTemplate(str(path))
    doc.build(
        [
            Paragraph("Narrative &amp; &lt;tag&gt;", styles["BodyText"]),
            Table(
                [["A&B", "Amount"], ["Total", "<100>"]],
                style=GRID_STYLE,
            ),
        ]
    )


def _mixed_geometry_pdf(path):
    page = Canvas(str(path))
    page.setFont("Helvetica", 10)
    rows = [
        (700, "Opening", "100", "90"),
        (680, "Increase", "25", "20"),
        (660, "Closing", "125", "110"),
    ]
    for y, label, current, prior in rows:
        page.drawString(72, y, label)
        page.drawRightString(350, y, current)
        page.drawRightString(430, y, prior)
    for x in (280, 360, 440):
        page.line(x, 650, x, 715)
    for y in (650, 670, 690, 715):
        page.line(280, y, 440, y)
    page.save()


def _encrypt_pdf(plain, encrypted, *, user_password, owner_password=None):
    reader = PdfReader(plain)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(user_password, owner_password=owner_password)
    with encrypted.open("wb") as stream:
        writer.write(stream)


def test_native_pdf_produces_report_with_page_and_bbox(tmp_path):
    path = tmp_path / "report.pdf"
    _native_financial_pdf(path)

    parsed = parse_report_attachment(path, company="Sample Co")

    assert parsed.input_format == "pdf"
    assert parsed.report.statements
    assert parsed.report.notes
    assert parsed.diagnostics == ()
    locations = [
        block.location
        for section in [*parsed.report.statements, *parsed.report.notes]
        for block in section.blocks
    ]
    assert all(location.input_format == "pdf" for location in locations)
    assert all(location.page_number == 1 for location in locations)
    assert all(
        location.bbox is not None
        for location in locations
        if location.table_index is not None
    )
    statement_table = parsed.report.statements[0].blocks[0].table
    note_table = parsed.report.notes[0].blocks[0].table
    assert statement_table is not None
    assert note_table is not None
    assert statement_table.rows[1] == ["자산총계", "1,000"]
    assert note_table.rows[1] == ["합계", "100"]
    for table in (statement_table, note_table):
        assert table.location.page_number == 1
        assert table.location.bbox is not None


def test_pdf_semantic_gate_rejects_amount_bearing_note_without_statement(tmp_path):
    path = tmp_path / "note-only.pdf"
    _native_note_only_pdf(path)

    with pytest.raises(AttachmentIngestionError) as exc:
        parse_report_attachment(path)

    assert exc.value.code == "REPORT_STRUCTURE_NOT_FOUND"


def test_pdf_semantic_gate_rejects_unsupported_english_statement_with_numeric_table(
    tmp_path,
):
    path = tmp_path / "unsupported-english.pdf"
    _unsupported_english_statement_pdf(path)

    with pytest.raises(AttachmentIngestionError) as exc:
        parse_report_attachment(path)

    assert exc.value.code == "REPORT_STRUCTURE_NOT_FOUND"


def test_pdf_semantic_gate_accepts_amount_bearing_korean_statement(tmp_path):
    path = tmp_path / "korean-statement.pdf"
    _native_financial_pdf(path)

    parsed = parse_report_attachment(path)

    assert len(parsed.report.statements) == 1


def test_native_pdf_markup_removes_table_words_from_narrative_and_orders_blocks(
    tmp_path,
):
    path = tmp_path / "ordered.pdf"
    _native_financial_pdf(path)

    extraction = extract_pdf_markup(path)
    soup = BeautifulSoup(extraction.markup, "lxml")
    blocks = soup.find_all(["p", "table"])
    order_keys = []
    for block in blocks:
        x0, top, _x1, _bottom = (
            float(part) for part in block["data-pdf-bbox"].split(",")
        )
        order_keys.append((top, x0))

    assert extraction.markup.count("자산총계") == 1
    assert extraction.markup.count("1,000") == 1
    assert extraction.markup.count("합계") == 1
    assert extraction.markup.count(">100<") == 1
    assert order_keys == sorted(order_keys)


def test_pdf_markup_escapes_narrative_and_table_cells(tmp_path):
    path = tmp_path / "special-characters.pdf"
    _special_character_pdf(path)

    markup = extract_pdf_markup(path).markup

    assert "Narrative &amp; &lt;tag&gt;" in markup
    assert "<td>A&amp;B</td>" in markup
    assert "<td>&lt;100&gt;</td>" in markup


def test_image_only_pdf_requires_ocr(tmp_path):
    path = tmp_path / "scan.pdf"
    page = Canvas(str(path))
    scanned_page = Image.new("RGB", (600, 800), "white")
    page.drawImage(ImageReader(scanned_page), 0, 0, width=600, height=800)
    page.save()

    with pytest.raises(AttachmentIngestionError) as exc:
        parse_report_attachment(path)

    assert exc.value.code == "PDF_OCR_REQUIRED"


def test_encrypted_pdf_is_rejected(tmp_path):
    plain = tmp_path / "plain.pdf"
    encrypted = tmp_path / "encrypted.pdf"
    _native_financial_pdf(plain)
    _encrypt_pdf(plain, encrypted, user_password="secret")

    with pytest.raises(AttachmentIngestionError) as exc:
        parse_report_attachment(encrypted)

    assert exc.value.code == "PDF_ENCRYPTED"


def test_owner_password_only_pdf_is_rejected_even_when_empty_user_password_opens(
    tmp_path,
):
    plain = tmp_path / "plain.pdf"
    encrypted = tmp_path / "owner-password-only.pdf"
    _native_financial_pdf(plain)
    _encrypt_pdf(
        plain,
        encrypted,
        user_password="",
        owner_password="owner-secret",
    )

    with pytest.raises(AttachmentIngestionError) as exc:
        parse_report_attachment(encrypted)

    assert exc.value.code == "PDF_ENCRYPTED"


@pytest.mark.parametrize("wrapped_at", ["args", "context", "cause"])
def test_wrapped_pdf_encryption_error_is_rejected_as_encrypted(
    tmp_path,
    monkeypatch,
    wrapped_at,
):
    path = tmp_path / "unsupported-encryption.pdf"
    path.write_bytes(b"%PDF-1.7\n")
    encryption_error = PDFEncryptionError("Unknown encryption filter")
    if wrapped_at == "args":
        wrapped = PdfminerException(encryption_error)
    else:
        wrapped = PdfminerException(RuntimeError("wrapped pdfminer failure"))
        setattr(wrapped, f"__{wrapped_at}__", encryption_error)

    def raise_wrapped_encryption_error(_source):
        raise wrapped

    monkeypatch.setattr(
        pdf_ingestion.pdfplumber,
        "open",
        raise_wrapped_encryption_error,
    )

    with pytest.raises(AttachmentIngestionError) as exc:
        parse_report_attachment(path)

    assert exc.value.code == "PDF_ENCRYPTED"
    assert exc.value.__cause__ is wrapped


@pytest.mark.parametrize(
    "contents",
    [
        b"%PDF-1.7\n",
        b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog",
    ],
    ids=["header-only", "truncated"],
)
def test_malformed_pdf_maps_to_attachment_decode_failed(tmp_path, contents):
    path = tmp_path / "malformed.pdf"
    path.write_bytes(contents)

    with pytest.raises(AttachmentIngestionError) as exc:
        parse_report_attachment(path)

    assert exc.value.code == "ATTACHMENT_DECODE_FAILED"
    assert "손상" in str(exc.value) or "읽을 수 없는" in str(exc.value)
    assert exc.value.__cause__ is not None


def test_text_table_fallback_adds_page_diagnostic_to_parsed_attachment(tmp_path):
    path = tmp_path / "borderless.pdf"
    _borderless_financial_pdf(path)

    parsed = parse_report_attachment(path)

    assert parsed.report.statements
    assert parsed.report.notes
    assert [(item.code, item.page) for item in parsed.diagnostics] == [
        ("PDF_TABLE_STRUCTURE_INFERRED", 2)
    ]
    assert parsed.diagnostics[0].message == (
        "선으로 구분된 표 경계를 찾지 못해 텍스트 정렬을 기준으로 "
        "표 구조를 추정했습니다."
    )


def test_mixed_geometry_pdf_recovers_labels_from_outside_ruled_amount_grid(tmp_path):
    path = tmp_path / "mixed-geometry.pdf"
    _mixed_geometry_pdf(path)

    extraction = extract_pdf_markup(path)
    soup = BeautifulSoup(extraction.markup, "lxml")
    tables = soup.find_all("table")

    assert len(tables) == 1
    rows = [
        [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]
        for row in tables[0].find_all("tr")
    ]
    assert rows == [
        ["Opening", "100", "90"],
        ["Increase", "25", "20"],
        ["Closing", "125", "110"],
    ]
    assert [(item.code, item.page) for item in extraction.diagnostics] == [
        ("PDF_TABLE_FRAGMENT_RECOVERED", 1)
    ]


def test_table_candidate_scoring_counts_amounts_and_first_two_column_labels():
    rows = [["Opening", "100", "90"], ["Closing", "125", "110"]]

    assert pdf_ingestion._amount_count(rows) == 4
    assert pdf_ingestion._label_count(rows) == 2


def test_table_candidate_overlap_uses_intersection_over_smaller_area():
    fragment = (280.0, 100.0, 440.0, 200.0)
    recovered = (72.0, 80.0, 440.0, 220.0)
    separate = (72.0, 300.0, 440.0, 400.0)

    assert pdf_ingestion._bbox_overlap_ratio(fragment, recovered) == pytest.approx(1.0)
    assert pdf_ingestion._bbox_overlap_ratio(fragment, separate) == 0.0


def test_select_table_candidates_replaces_overlapping_numeric_fragment():
    line = [
        (
            (280.0, 100.0, 440.0, 200.0),
            [["100", "90"], ["125", "110"]],
        )
    ]
    text = [
        (
            (72.0, 80.0, 440.0, 220.0),
            [["Opening", "100", "90"], ["Closing", "125", "110"]],
        )
    ]

    selected, recovered = pdf_ingestion._select_table_candidates(line, text)

    assert selected == text
    assert recovered is True


def test_select_table_candidates_keeps_line_when_text_coverage_is_not_better():
    line = [
        (
            (280.0, 100.0, 440.0, 200.0),
            [["100", "90"], ["125", "110"]],
        )
    ]
    text = [
        (
            (72.0, 80.0, 440.0, 220.0),
            [["Opening", "100"], ["Closing", "125"]],
        )
    ]

    selected, recovered = pdf_ingestion._select_table_candidates(line, text)

    assert selected == line
    assert recovered is False


def test_select_table_candidates_retains_eligible_non_overlapping_text_table():
    line = [
        (
            (280.0, 100.0, 440.0, 200.0),
            [["100", "90"], ["125", "110"]],
        )
    ]
    overlapping_worse = (
        (72.0, 80.0, 440.0, 220.0),
        [["Opening", "100"], ["Closing", "125"]],
    )
    non_overlapping = (
        (72.0, 300.0, 440.0, 400.0),
        [["Other", "50"], ["Total", "50"]],
    )

    selected, recovered = pdf_ingestion._select_table_candidates(
        line,
        [overlapping_worse, non_overlapping],
    )

    assert line[0] in selected
    assert non_overlapping in selected
    assert overlapping_worse not in selected
    assert recovered is False


def test_select_table_candidates_resolves_shared_conflict_component_once():
    line_a = (
        (280.0, 100.0, 440.0, 200.0),
        [["100", "90"]],
    )
    line_b = (
        (280.0, 220.0, 440.0, 320.0),
        [["200", "180"]],
    )
    text_a = (
        (72.0, 80.0, 430.0, 210.0),
        [["Alpha", "100", "90"]],
    )
    text_a_and_b = (
        (72.0, 90.0, 430.0, 310.0),
        [["Alpha", "100", "90"], ["Beta", "200", "180"]],
    )

    selected, recovered = pdf_ingestion._select_table_candidates(
        [line_a, line_b],
        [text_a, text_a_and_b],
    )

    assert selected == [text_a_and_b]
    assert sum(pdf_ingestion._amount_count(rows) for _bbox, rows in selected) == 4
    assert recovered is True


def test_select_table_candidates_preserves_line_set_on_label_coverage_tie():
    line = (
        (280.0, 100.0, 440.0, 200.0),
        [["100", "90"], ["125", "110"]],
    )
    text = (
        (72.0, 80.0, 440.0, 220.0),
        [["100", "90"], ["125", "110"]],
    )

    selected, recovered = pdf_ingestion._select_table_candidates([line], [text])

    assert selected == [line]
    assert recovered is False


def test_select_table_candidates_requires_replacement_to_cover_numeric_fragment():
    numeric_fragment = (
        (280.0, 100.0, 440.0, 200.0),
        [["100", "90"]],
    )
    labeled_line = (
        (280.0, 220.0, 440.0, 320.0),
        [["Existing label", ""]],
    )
    connecting_text = (
        (72.0, 190.0, 430.0, 230.0),
        [["Bridge", ""]],
    )
    labeled_only_improvement = (
        (72.0, 240.0, 430.0, 300.0),
        [["Primary label", ""], ["Secondary label", ""]],
    )

    selected, recovered = pdf_ingestion._select_table_candidates(
        [numeric_fragment, labeled_line],
        [connecting_text, labeled_only_improvement],
    )

    assert selected == [numeric_fragment, labeled_line]
    assert recovered is False


def test_select_table_candidates_falls_back_before_oversized_component_search(
    monkeypatch,
):
    line = (
        (280.0, 100.0, 440.0, 200.0),
        [["100", "90"]],
    )
    text_candidates = [
        (
            (72.0 - index, 80.0, 440.0, 220.0),
            [[f"Label {index}", "100", "90"]],
        )
        for index in range(pdf_ingestion._MAX_CONFLICT_TEXT_CANDIDATES + 1)
    ]

    def fail_if_component_search_runs(*_args):
        raise AssertionError("oversized component must not enter candidate-set search")

    monkeypatch.setattr(
        pdf_ingestion,
        "_best_component_replacement",
        fail_if_component_search_runs,
    )

    selected, recovered = pdf_ingestion._select_table_candidates(
        [line],
        text_candidates,
    )

    assert selected == [line]
    assert recovered is False


def test_table_serialization_drops_blank_only_rows_but_preserves_partial_rows():
    markup = pdf_ingestion._serialize_table(
        1,
        (10.0, 20.0, 30.0, 40.0),
        [["Label", "100"], ["Subtotal", ""], ["", ""]],
    )
    soup = BeautifulSoup(markup, "lxml")
    rows = [
        [cell.get_text(" ", strip=True) for cell in row.find_all("td")]
        for row in soup.find_all("tr")
    ]

    assert rows == [["Label", "100"], ["Subtotal", ""]]


def test_native_pdf_without_tables_is_rejected(tmp_path):
    path = tmp_path / "narrative.pdf"
    page = Canvas(str(path))
    page.drawString(72, 720, "Native financial report without tabular data")
    page.save()

    with pytest.raises(AttachmentIngestionError) as exc:
        parse_report_attachment(path)

    assert exc.value.code == "PDF_TABLES_NOT_FOUND"
