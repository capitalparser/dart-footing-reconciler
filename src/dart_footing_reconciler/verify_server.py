"""Loopback-only static and attachment verification server."""

from __future__ import annotations

import json
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path, PureWindowsPath
from tempfile import TemporaryDirectory
from typing import NamedTuple

from dart_footing_reconciler.attachment_ingestion import AttachmentIngestionError
from dart_footing_reconciler.verify_app import verify_attachment

_MAX_REQUEST_BYTES = 32 * 1024 * 1024


class _ErrorResponse(NamedTuple):
    status: int
    error: str
    message: str
    next_action: str


_REQUEST_ERRORS = {
    "REQUEST_PATH_NOT_FOUND": _ErrorResponse(
        404,
        "REQUEST_PATH_NOT_FOUND",
        "요청 경로를 찾을 수 없습니다.",
        "POST /api/verify 경로로 파일을 전송하세요.",
    ),
    "CONTENT_LENGTH_REQUIRED": _ErrorResponse(
        411,
        "CONTENT_LENGTH_REQUIRED",
        "Content-Length 헤더가 필요합니다.",
        "업로드 크기를 포함해 파일을 다시 전송하세요.",
    ),
    "CONTENT_LENGTH_INVALID": _ErrorResponse(
        400,
        "CONTENT_LENGTH_INVALID",
        "Content-Length는 숫자여야 합니다.",
        "올바른 업로드 크기를 포함해 파일을 다시 전송하세요.",
    ),
    "UPLOAD_TOO_LARGE": _ErrorResponse(
        413,
        "UPLOAD_TOO_LARGE",
        "전체 multipart 요청은 32 MiB 이하여야 합니다.",
        "32 MiB 미만의 첨부 파일을 선택해 다시 요청하세요.",
    ),
    "UPLOAD_FILE_TOO_LARGE": _ErrorResponse(
        413,
        "UPLOAD_FILE_TOO_LARGE",
        "디코딩된 첨부 파일은 32 MiB 이하여야 합니다.",
        (
            "multipart 경계 정보를 포함한 전체 요청이 32 MiB 이내가 되도록 "
            "더 작은 파일을 선택하세요."
        ),
    ),
    "MULTIPART_REQUIRED": _ErrorResponse(
        415,
        "MULTIPART_REQUIRED",
        "multipart/form-data 형식의 업로드가 필요합니다.",
        "file 필드에 DART 원문 파일 하나를 첨부하세요.",
    ),
    "MULTIPART_INVALID": _ErrorResponse(
        400,
        "MULTIPART_INVALID",
        "multipart 업로드 내용을 읽을 수 없습니다.",
        "file 필드에 DART 원문 파일 하나를 다시 첨부하세요.",
    ),
    "UPLOAD_FILE_REQUIRED": _ErrorResponse(
        400,
        "UPLOAD_FILE_REQUIRED",
        "file 필드의 첨부 파일이 필요합니다.",
        "file 필드에 DART 원문 파일 하나를 첨부하세요.",
    ),
    "UPLOAD_FILE_COUNT_INVALID": _ErrorResponse(
        400,
        "UPLOAD_FILE_COUNT_INVALID",
        "첨부 파일은 하나만 업로드할 수 있습니다.",
        "file 필드에 DART 원문 파일 하나만 첨부하세요.",
    ),
    "UPLOAD_FILENAME_INVALID": _ErrorResponse(
        400,
        "UPLOAD_FILENAME_INVALID",
        "안전하지 않은 파일 이름입니다.",
        "경로 문자가 없는 원본 파일 이름으로 다시 선택하세요.",
    ),
    "UPLOAD_EMPTY": _ErrorResponse(
        400,
        "UPLOAD_EMPTY",
        "빈 파일은 검증할 수 없습니다.",
        "내용이 있는 DART 원문 파일을 선택하세요.",
    ),
    "VERIFICATION_INTERNAL_ERROR": _ErrorResponse(
        500,
        "VERIFICATION_INTERNAL_ERROR",
        "파일 검증 중 오류가 발생했습니다.",
        "원본 파일을 다시 선택하고 문제가 계속되면 애플리케이션을 재시작하세요.",
    ),
}


_ATTACHMENT_ERRORS = {
    "ATTACHMENT_FORMAT_UNSUPPORTED": _ErrorResponse(
        422,
        "ATTACHMENT_FORMAT_UNSUPPORTED",
        "지원하지 않는 첨부 형식입니다.",
        "DART DSD/XML/HTML 원문 또는 텍스트 선택이 가능한 PDF를 선택하세요.",
    ),
    "ATTACHMENT_SOURCE_NOT_FOUND": _ErrorResponse(
        422,
        "ATTACHMENT_SOURCE_NOT_FOUND",
        "첨부 파일을 찾을 수 없습니다.",
        "파일을 다시 선택해 업로드하세요.",
    ),
    "ATTACHMENT_SOURCE_NOT_FILE": _ErrorResponse(
        422,
        "ATTACHMENT_SOURCE_NOT_FILE",
        "첨부 경로는 파일이어야 합니다.",
        "DART 원문 파일 하나를 선택하세요.",
    ),
    "ATTACHMENT_ENCODING_UNDETERMINED": _ErrorResponse(
        422,
        "ATTACHMENT_ENCODING_UNDETERMINED",
        "첨부 파일의 문자 인코딩을 판별할 수 없습니다.",
        "DART에서 DSD/XML/HTML 원문을 다시 내려받아 선택하세요.",
    ),
    "ATTACHMENT_DECODE_FAILED": _ErrorResponse(
        422,
        "ATTACHMENT_DECODE_FAILED",
        "PDF 첨부가 손상되었거나 읽을 수 없습니다.",
        "DART에서 원문 파일을 다시 내려받아 선택하세요.",
    ),
    "REPORT_STRUCTURE_NOT_FOUND": _ErrorResponse(
        422,
        "REPORT_STRUCTURE_NOT_FOUND",
        "재무제표 본문과 검증 가능한 금액 표를 찾지 못했습니다.",
        "재무제표 본문과 주석이 포함된 DART 원문 파일을 선택하세요.",
    ),
    "PDF_ENCRYPTED": _ErrorResponse(
        422,
        "PDF_ENCRYPTED",
        "암호화된 PDF는 검증할 수 없습니다.",
        "암호가 없는 DART PDF 또는 DSD/XML/HTML 원문을 선택하세요.",
    ),
    "PDF_OCR_REQUIRED": _ErrorResponse(
        422,
        "PDF_OCR_REQUIRED",
        "텍스트를 읽을 수 없는 PDF입니다. OCR 처리된 PDF가 필요합니다.",
        (
            "DART에서 텍스트 선택이 가능한 PDF 또는 DSD/XML/HTML 원문을 "
            "내려받아 다시 선택하세요."
        ),
    ),
    "PDF_TABLES_NOT_FOUND": _ErrorResponse(
        422,
        "PDF_TABLES_NOT_FOUND",
        "PDF에서 검증 가능한 표를 찾지 못했습니다.",
        "표가 포함된 DART PDF 또는 DSD/XML/HTML 원문을 선택하세요.",
    ),
}

_UNKNOWN_ATTACHMENT_ERROR = _ErrorResponse(
    422,
    "ATTACHMENT_VERIFICATION_FAILED",
    "첨부 파일을 검증할 수 없습니다.",
    "DART 원문 파일을 다시 내려받아 선택하세요.",
)


def build_verify_server(
    directory: str | Path,
    port: int,
) -> tuple[HTTPServer, str]:
    """Build a loopback-only static server with one verification POST endpoint."""
    app_dir = Path(directory)
    if not (app_dir / "index.html").exists():
        from typer import BadParameter

        raise BadParameter(
            f"{app_dir}/index.html not found; run build-verify-app first"
        )
    handler = _verify_request_handler(app_dir)
    httpd = HTTPServer(("127.0.0.1", port), handler)
    bound_port = httpd.server_address[1]
    return httpd, f"http://127.0.0.1:{bound_port}/index.html"


def _verify_request_handler(directory: Path):
    class VerifyRequestHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(directory), **kwargs)

        def do_POST(self) -> None:
            if self.path != "/api/verify":
                self._write_error(_REQUEST_ERRORS["REQUEST_PATH_NOT_FOUND"])
                return

            content_length = self.headers.get("Content-Length")
            if content_length is None:
                self._write_error(_REQUEST_ERRORS["CONTENT_LENGTH_REQUIRED"])
                return
            if not content_length.isascii() or not content_length.isdecimal():
                self._write_error(_REQUEST_ERRORS["CONTENT_LENGTH_INVALID"])
                return
            body_length = _bounded_content_length(content_length)
            if body_length is None:
                self._write_error(_REQUEST_ERRORS["UPLOAD_TOO_LARGE"])
                return

            content_type = self.headers.get("Content-Type", "")
            if self.headers.get_content_type() != "multipart/form-data":
                self._write_error(_REQUEST_ERRORS["MULTIPART_REQUIRED"])
                return

            body = self.rfile.read(body_length)
            message = _parse_multipart(content_type, body)
            if message is None:
                self._write_error(_REQUEST_ERRORS["MULTIPART_INVALID"])
                return
            file_parts = [
                part for part in message.iter_parts() if part.get_filename() is not None
            ]
            if len(file_parts) > 1:
                self._write_error(_REQUEST_ERRORS["UPLOAD_FILE_COUNT_INVALID"])
                return
            if (
                len(file_parts) != 1
                or file_parts[0].get_content_disposition() != "form-data"
                or file_parts[0].get_param(
                    "name",
                    header="content-disposition",
                )
                != "file"
            ):
                self._write_error(_REQUEST_ERRORS["UPLOAD_FILE_REQUIRED"])
                return

            part = file_parts[0]
            filename = part.get_filename() or ""
            raw_disposition = next(
                (
                    value
                    for name, value in part.raw_items()
                    if name.lower() == "content-disposition"
                ),
                "",
            )
            if not _is_safe_filename(filename) or "\\" in raw_disposition:
                self._write_error(_REQUEST_ERRORS["UPLOAD_FILENAME_INVALID"])
                return
            payload = _decode_file_payload(part)
            if _has_email_defects(message):
                self._write_error(_REQUEST_ERRORS["MULTIPART_INVALID"])
                return
            if not payload:
                self._write_error(_REQUEST_ERRORS["UPLOAD_EMPTY"])
                return
            if len(payload) > _MAX_REQUEST_BYTES:
                self._write_error(_REQUEST_ERRORS["UPLOAD_FILE_TOO_LARGE"])
                return

            try:
                with TemporaryDirectory(prefix="dart-verify-upload-") as tmpdir:
                    managed_directory = Path(tmpdir)
                    source = _safe_upload_target(managed_directory, filename)
                    if source is None:
                        self._write_error(_REQUEST_ERRORS["UPLOAD_FILENAME_INVALID"])
                        return
                    source.write_bytes(payload)
                    html = verify_attachment(source, company=source.stem)
            except AttachmentIngestionError as exc:
                self._write_error(
                    _ATTACHMENT_ERRORS.get(exc.code, _UNKNOWN_ATTACHMENT_ERROR)
                )
                return
            except Exception:
                self._write_error(_REQUEST_ERRORS["VERIFICATION_INTERNAL_ERROR"])
                return
            self._write_response(
                200,
                "text/html; charset=utf-8",
                html.encode("utf-8"),
            )

        def _write_error(self, response: _ErrorResponse) -> None:
            payload = json.dumps(
                {
                    "error": response.error,
                    "message": response.message,
                    "next_action": response.next_action,
                },
                ensure_ascii=False,
            ).encode("utf-8")
            self._write_response(
                response.status,
                "application/json; charset=utf-8",
                payload,
            )

        def _write_response(
            self,
            status: int,
            content_type: str,
            body: bytes,
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *args) -> None:
            return

    return VerifyRequestHandler


def _parse_multipart(content_type: str, body: bytes) -> EmailMessage | None:
    try:
        message = BytesParser(policy=policy.default).parsebytes(
            b"Content-Type: "
            + content_type.encode("ascii")
            + b"\r\nMIME-Version: 1.0\r\n\r\n"
            + body
        )
    except (UnicodeEncodeError, ValueError):
        return None
    if (
        not isinstance(message, EmailMessage)
        or not message.is_multipart()
        or _has_email_defects(message)
        or not list(message.iter_parts())
    ):
        return None
    return message


def _has_email_defects(message: EmailMessage) -> bool:
    return any(
        part.defects or any(getattr(header, "defects", ()) for header in part.values())
        for part in message.walk()
    )


def _decode_file_payload(part: EmailMessage) -> bytes:
    return part.get_payload(decode=True) or b""


def _bounded_content_length(content_length: str) -> int | None:
    normalized = content_length.lstrip("0") or "0"
    maximum_length = str(_MAX_REQUEST_BYTES)
    if len(normalized) > len(maximum_length) or (
        len(normalized) == len(maximum_length) and normalized > maximum_length
    ):
        return None
    return int(normalized)


def _safe_upload_target(directory: Path, filename: str) -> Path | None:
    target = directory / filename
    if target.parent != directory or target.name != filename:
        return None
    return target


def _is_safe_filename(filename: str) -> bool:
    return (
        bool(filename)
        and not any(candidate in filename for candidate in ("/", "\\", "\x00"))
        and filename not in {".", ".."}
        and not PureWindowsPath(filename).drive
    )
