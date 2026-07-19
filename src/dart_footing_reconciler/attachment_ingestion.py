"""Common local attachment ingestion for structured DART report formats."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.document import (
    FullReport,
    ReportTable,
    parse_full_report_text,
)


@dataclass(frozen=True)
class AttachmentDiagnostic:
    code: str
    message: str
    page: int | None = None


class AttachmentIngestionError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ParsedAttachment:
    source: Path
    input_format: str
    report: FullReport
    diagnostics: tuple[AttachmentDiagnostic, ...] = ()


_STRUCTURED_SUFFIX_FORMATS = {
    ".dsd": "dsd",
    ".xml": "xml",
    ".html": "html",
    ".htm": "html",
}
_XML_DECLARATION_RE = re.compile(r"^<\?xml\b[^>]*\?>", re.IGNORECASE | re.DOTALL)
_ROOT_RE = re.compile(r"^<([a-z][\w:.-]*)(?=[\s>/])", re.IGNORECASE)
_HTML_DOCTYPE_RE = re.compile(r"^<!doctype\s+html(?=[\s>])", re.IGNORECASE)


def detect_attachment_format(path: Path, data: bytes, text: str | None = None) -> str:
    """Detect a report attachment format, preferring content signatures."""
    input_format, _strong_format = _detect_attachment_format(path, data, text)
    return input_format


def _detect_attachment_format(
    path: Path,
    data: bytes,
    text: str | None = None,
) -> tuple[str, str | None]:
    stripped = data.lstrip()
    if path.suffix.lower() == ".pdf" or stripped.startswith(b"%PDF"):
        return "pdf", "pdf"

    decoded = text if text is not None else decode_attachment_text(data, path=path)
    strong_format = _strong_structured_format(decoded)
    if strong_format is not None:
        return strong_format, strong_format

    suffix_format = _STRUCTURED_SUFFIX_FORMATS.get(path.suffix.lower())
    if suffix_format is not None:
        return suffix_format, None

    raise AttachmentIngestionError(
        "ATTACHMENT_FORMAT_UNSUPPORTED",
        "지원하지 않는 첨부 형식입니다.",
    )


def _strong_structured_format(text: str) -> str | None:
    prefix = text[:4096].lstrip("\ufeff \t\r\n")
    if _HTML_DOCTYPE_RE.match(prefix):
        return "html"

    xml_declaration = _XML_DECLARATION_RE.match(prefix)
    after_declaration = (
        prefix[xml_declaration.end() :].lstrip() if xml_declaration else prefix
    )
    root_match = _ROOT_RE.match(after_declaration)
    root = root_match.group(1).lower() if root_match else ""
    if root in {"document", "dart"}:
        return "dsd"
    if xml_declaration and root:
        return "xml"
    if root in {"html", "head", "body"}:
        return "html"
    return None


def _format_mismatch_diagnostics(
    path: Path,
    strong_format: str | None,
) -> tuple[AttachmentDiagnostic, ...]:
    suffix_format = _STRUCTURED_SUFFIX_FORMATS.get(path.suffix.lower())
    if strong_format is None or suffix_format is None or suffix_format == strong_format:
        return ()
    return (
        AttachmentDiagnostic(
            code="ATTACHMENT_FORMAT_MISMATCH",
            message=(
                "파일 확장자와 내용 형식이 달라 내용에서 확인된 형식을 사용했습니다."
            ),
        ),
    )


def parse_report_attachment(
    source: str | Path,
    *,
    company: str = "",
) -> ParsedAttachment:
    """Parse one local DART attachment through the common report contract."""
    path = Path(source)
    if not path.exists():
        raise AttachmentIngestionError(
            "ATTACHMENT_SOURCE_NOT_FOUND",
            "첨부 파일을 찾을 수 없습니다.",
        )
    if not path.is_file():
        raise AttachmentIngestionError(
            "ATTACHMENT_SOURCE_NOT_FILE",
            "첨부 경로는 파일이어야 합니다.",
        )

    data = path.read_bytes()
    stripped = data.lstrip()
    if path.suffix.lower() == ".pdf" or stripped.startswith(b"%PDF"):
        input_format, strong_format = _detect_attachment_format(path, data)
        text = None
    else:
        text = decode_attachment_text(data, path=path)
        input_format, strong_format = _detect_attachment_format(path, data, text)

    if input_format == "pdf":
        extraction = _extract_pdf_markup(path)
        markup = extraction.markup
        diagnostics = (
            *extraction.diagnostics,
            *_format_mismatch_diagnostics(path, strong_format),
        )
    else:
        markup = text or ""
        diagnostics = _format_mismatch_diagnostics(path, strong_format)

    report = parse_full_report_text(
        markup,
        source=str(path),
        company=company,
        input_format=input_format,
    )
    if not _has_usable_report_structure(report, input_format=input_format):
        raise AttachmentIngestionError(
            "REPORT_STRUCTURE_NOT_FOUND",
            "재무제표 본문과 검증 가능한 금액 표를 찾지 못했습니다.",
        )
    return ParsedAttachment(path, input_format, report, diagnostics)


def decode_attachment_text(data: bytes, *, path: Path | None = None) -> str:
    """Decode a structured DART attachment using common Korean encodings."""
    for encoding in ("utf-8", "utf-8-sig", "cp949", "euc-kr"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    decoded = data.decode("utf-8", errors="replace")
    if decoded and decoded.count("\ufffd") / len(decoded) > 0.001:
        raise AttachmentIngestionError(
            "ATTACHMENT_ENCODING_UNDETERMINED",
            f"인코딩 판별 실패 — 원본 인코딩 확인 필요: {path}",
        )
    return decoded


def _extract_pdf_markup(path: Path):
    from dart_footing_reconciler.pdf_ingestion import extract_pdf_markup

    return extract_pdf_markup(path)


def _has_usable_report_structure(report: FullReport, *, input_format: str) -> bool:
    sections = (
        report.statements
        if input_format == "pdf"
        else [*report.statements, *report.notes]
    )
    return any(
        block.table is not None and is_usable_report_table(block.table)
        for section in sections
        for block in section.blocks
    )


def is_usable_report_table(table: ReportTable) -> bool:
    """Return whether a parsed table has an amount-bearing data row."""
    if len(table.rows) < 2:
        return False
    return any(
        any(parse_amount(cell) is not None for cell in row[1:])
        for row in table.rows[1:]
    )
