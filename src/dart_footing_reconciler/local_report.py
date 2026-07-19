"""Local attachment report loading and footing workflow."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dart_footing_reconciler.attachment_ingestion import (
    AttachmentIngestionError,
    decode_attachment_text,
    detect_attachment_format,
)
from dart_footing_reconciler.checks import SCHEMA_VERSION, status_summary
from dart_footing_reconciler.scan import scan_html


@dataclass(frozen=True)
class LocalReport:
    """Decoded local report content ready for parser entrypoints."""

    source: Path
    input_format: str
    text: str


class LocalReportError(ValueError):
    """Base error for local report input problems."""


class UnsupportedReportFormatError(LocalReportError):
    """Raised when a local report format is outside the supported parser boundary."""


def load_local_report(source: str | Path) -> LocalReport:
    """Load a local DART report attachment without network access."""
    path = Path(source)
    _reject_network_source(path)
    if not path.exists():
        raise LocalReportError("source must be a local file path that exists")
    if not path.is_file():
        raise LocalReportError("source must be a local file path, not a directory")

    data = path.read_bytes()
    if _is_pdf(path, data):
        raise UnsupportedReportFormatError(
            "PDF footing is not supported yet; attach the DART DSD or HTML report instead."
        )

    text = _decode_text(data, path=path)
    return LocalReport(source=path, input_format=_input_format(path, data, text), text=text)


def foot_local_report(
    source: str | Path,
    *,
    tolerance: int = 1,
    include_all: bool = False,
) -> dict[str, Any]:
    """Run footing checks for a supported local DART report attachment."""
    report = load_local_report(source)
    results = scan_html(report.text, tolerance=tolerance, include_all=include_all)
    return {
        "schema_version": SCHEMA_VERSION,
        "source": str(report.source),
        "input_format": report.input_format,
        "summary": _summary(results),
        "results": [asdict(result) for result in results],
    }


def _reject_network_source(path: Path) -> None:
    """Reject URL-like input so footing remains a local attachment workflow."""
    parsed = urlparse(str(path))
    if parsed.scheme in {"http", "https"}:
        raise LocalReportError("source must be a local file path, not a network URL")


def _is_pdf(path: Path, data: bytes) -> bool:
    """Return whether the file is a PDF by extension or file signature."""
    return path.suffix.lower() == ".pdf" or data.lstrip().startswith(b"%PDF")


def _input_format(path: Path, data: bytes, text: str) -> str:
    """Classify the local report format for result metadata."""
    try:
        return detect_attachment_format(path, data, text)
    except AttachmentIngestionError as exc:
        if exc.code == "ATTACHMENT_FORMAT_UNSUPPORTED":
            return "html"
        raise


def _decode_text(data: bytes, *, path: Path | None = None) -> str:
    """Decode DART text using common Korean disclosure encodings."""
    try:
        return decode_attachment_text(data, path=path)
    except AttachmentIngestionError as exc:
        raise LocalReportError(str(exc)) from exc


def _summary(results: list[Any]) -> dict[str, int]:
    """Summarize footing statuses for CLI and package consumers (all 5 statuses)."""
    return status_summary(results)
