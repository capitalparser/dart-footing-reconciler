from __future__ import annotations

import json
import shutil
from http.client import HTTPConnection
from http.server import HTTPServer
from pathlib import Path
from threading import Thread

import pytest
from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

from dart_footing_reconciler import verify_server
from dart_footing_reconciler.attachment_ingestion import AttachmentIngestionError
from dart_footing_reconciler.cli import _build_verify_server
from dart_footing_reconciler.verify_server import _MAX_REQUEST_BYTES


SAMPLE_REPORT = b"""
<p>\xec\x9e\xac\xeb\xac\xb4\xec\x83\x81\xed\x83\x9c\xed\x91\x9c</p>
<table>
  <tr><th>\xea\xb5\xac\xeb\xb6\x84</th><th>\xeb\x8b\xb9\xea\xb8\xb0</th></tr>
  <tr><td>\xec\x9e\x90\xec\x82\xb0\xec\xb4\x9d\xea\xb3\x84</td><td>1,000</td></tr>
</table>
<p>\xec\x9e\xac\xeb\xac\xb4\xec\xa0\x9c\xed\x91\x9c \xec\xa3\xbc\xec\x84\x9d</p>
<p>8. \xeb\xa7\xa4\xec\xb6\x9c\xec\xb1\x84\xea\xb6\x8c</p>
<table>
  <tr><th>\xea\xb5\xac\xeb\xb6\x84</th><th>\xea\xb8\x88\xec\x95\xa1</th></tr>
  <tr><td>\xed\x95\xa9\xea\xb3\x84</td><td>100</td></tr>
</table>
"""

ATTACHMENT_ERROR_CASES = [
    (
        "ATTACHMENT_FORMAT_UNSUPPORTED",
        "지원하지 않는 첨부 형식입니다.",
        "DART DSD/XML/HTML 원문 또는 텍스트 선택이 가능한 PDF를 선택하세요.",
    ),
    (
        "ATTACHMENT_SOURCE_NOT_FOUND",
        "첨부 파일을 찾을 수 없습니다.",
        "파일을 다시 선택해 업로드하세요.",
    ),
    (
        "ATTACHMENT_SOURCE_NOT_FILE",
        "첨부 경로는 파일이어야 합니다.",
        "DART 원문 파일 하나를 선택하세요.",
    ),
    (
        "ATTACHMENT_ENCODING_UNDETERMINED",
        "첨부 파일의 문자 인코딩을 판별할 수 없습니다.",
        "DART에서 DSD/XML/HTML 원문을 다시 내려받아 선택하세요.",
    ),
    (
        "ATTACHMENT_DECODE_FAILED",
        "PDF 첨부가 손상되었거나 읽을 수 없습니다.",
        "DART에서 원문 파일을 다시 내려받아 선택하세요.",
    ),
    (
        "REPORT_STRUCTURE_NOT_FOUND",
        "재무제표 본문과 검증 가능한 금액 표를 찾지 못했습니다.",
        "재무제표 본문과 주석이 포함된 DART 원문 파일을 선택하세요.",
    ),
    (
        "PDF_ENCRYPTED",
        "암호화된 PDF는 검증할 수 없습니다.",
        "암호가 없는 DART PDF 또는 DSD/XML/HTML 원문을 선택하세요.",
    ),
    (
        "PDF_OCR_REQUIRED",
        "텍스트를 읽을 수 없는 PDF입니다. OCR 처리된 PDF가 필요합니다.",
        (
            "DART에서 텍스트 선택이 가능한 PDF 또는 DSD/XML/HTML 원문을 "
            "내려받아 다시 선택하세요."
        ),
    ),
    (
        "PDF_TABLES_NOT_FOUND",
        "PDF에서 검증 가능한 표를 찾지 못했습니다.",
        "표가 포함된 DART PDF 또는 DSD/XML/HTML 원문을 선택하세요.",
    ),
]


@pytest.fixture
def running_server(tmp_path):
    app_dir = tmp_path / "dart-verify"
    app_dir.mkdir()
    (app_dir / "index.html").write_text("<html>static app</html>", encoding="utf-8")
    httpd, _url = _build_verify_server(app_dir, 0)
    thread = Thread(
        target=lambda: httpd.serve_forever(poll_interval=0.01),
        daemon=True,
    )
    thread.start()
    try:
        yield httpd
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


@pytest.fixture
def managed_temp_paths(monkeypatch):
    real_temporary_directory = verify_server.TemporaryDirectory
    observed_directories: list[Path] = []

    class TrackingTemporaryDirectory:
        def __init__(self, *args, **kwargs):
            self.delegate = real_temporary_directory(*args, **kwargs)

        def __enter__(self):
            directory = Path(self.delegate.__enter__())
            observed_directories.append(directory)
            return str(directory)

        def __exit__(self, *args):
            return self.delegate.__exit__(*args)

    monkeypatch.setattr(verify_server, "TemporaryDirectory", TrackingTemporaryDirectory)
    return observed_directories


def _multipart_body(
    files: list[tuple[str, str, bytes]],
    *,
    boundary: str = "dart-boundary",
) -> tuple[str, bytes]:
    chunks: list[bytes] = []
    for field_name, filename, payload in files:
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                (
                    "Content-Disposition: form-data; "
                    f'name="{field_name}"; filename="{filename}"\r\n'
                ).encode(),
                b"Content-Type: application/octet-stream\r\n\r\n",
                payload,
                b"\r\n",
            ]
        )
    chunks.append(f"--{boundary}--\r\n".encode())
    return f"multipart/form-data; boundary={boundary}", b"".join(chunks)


def _raw_multipart_body(
    *,
    content_disposition: str,
    payload: bytes,
    transfer_encoding: str = "8bit",
    boundary: str = "raw-boundary",
) -> tuple[str, bytes]:
    body = (
        (
            f"--{boundary}\r\n"
            f"Content-Disposition: {content_disposition}\r\n"
            "Content-Type: application/octet-stream\r\n"
            f"Content-Transfer-Encoding: {transfer_encoding}\r\n\r\n"
        ).encode()
        + payload
        + f"\r\n--{boundary}--\r\n".encode()
    )
    return f"multipart/form-data; boundary={boundary}", body


def _request(httpd, method, path, *, body=None, headers=None):
    status, response_headers, response_body = _request_with_headers(
        httpd,
        method,
        path,
        body=body,
        headers=headers,
    )
    return status, response_headers["content-type"], response_body


def _request_with_headers(httpd, method, path, *, body=None, headers=None):
    connection = HTTPConnection(*httpd.server_address, timeout=5)
    try:
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        response_headers = {
            name.lower(): value for name, value in response.getheaders()
        }
        return response.status, response_headers, response.read()
    finally:
        connection.close()


def _post_file(httpd, filename: str, payload: bytes):
    content_type, body = _multipart_body([("file", filename, payload)])
    return _request(
        httpd,
        "POST",
        "/api/verify",
        body=body,
        headers={"Content-Type": content_type},
    )


def _json(body: bytes) -> dict[str, str]:
    return json.loads(body.decode("utf-8"))


def test_post_verify_returns_existing_audit_workbench_html(running_server):
    content_type, request_body = _multipart_body(
        [("file", "company.dsd", SAMPLE_REPORT)]
    )
    status, headers, body = _request_with_headers(
        running_server,
        "POST",
        "/api/verify",
        body=request_body,
        headers={"Content-Type": content_type},
    )

    assert status == 200
    assert headers["content-type"] == "text/html; charset=utf-8"
    assert headers["content-length"] == str(len(body))
    assert headers["cache-control"] == "no-store"
    assert body
    assert b'data-report-profile="audit-workbench"' in body


def test_verify_server_processes_one_request_at_a_time(running_server):
    assert type(running_server) is HTTPServer


def test_verify_server_preserves_static_head_requests(running_server):
    status, headers, body = _request_with_headers(
        running_server,
        "HEAD",
        "/index.html",
    )

    assert status == 200
    assert headers["content-length"] == str(len(b"<html>static app</html>"))
    assert body == b""


def test_post_verify_maps_image_only_pdf_to_safe_korean_json(
    running_server,
    tmp_path,
):
    path = tmp_path / "scan.pdf"
    page = Canvas(str(path))
    page.drawImage(
        ImageReader(Image.new("RGB", (600, 800), "white")),
        0,
        0,
        width=600,
        height=800,
    )
    page.save()

    status, content_type, body = _post_file(
        running_server,
        "scan.pdf",
        path.read_bytes(),
    )

    assert status == 422
    assert content_type == "application/json; charset=utf-8"
    assert _json(body) == {
        "error": "PDF_OCR_REQUIRED",
        "message": "텍스트를 읽을 수 없는 PDF입니다. OCR 처리된 PDF가 필요합니다.",
        "next_action": (
            "DART에서 텍스트 선택이 가능한 PDF 또는 DSD/XML/HTML 원문을 "
            "내려받아 다시 선택하세요."
        ),
    }


def test_post_verify_rejects_oversized_length_before_reading_body(running_server):
    connection = HTTPConnection(*running_server.server_address, timeout=5)
    try:
        connection.putrequest("POST", "/api/verify")
        connection.putheader("Content-Length", str(_MAX_REQUEST_BYTES + 1))
        connection.putheader(
            "Content-Type",
            "multipart/form-data; boundary=not-sent",
        )
        connection.endheaders()
        response = connection.getresponse()
        body = response.read()
    finally:
        connection.close()

    assert response.status == 413
    assert _json(body) == {
        "error": "UPLOAD_TOO_LARGE",
        "message": "전체 multipart 요청은 32 MiB 이하여야 합니다.",
        "next_action": "32 MiB 미만의 첨부 파일을 선택해 다시 요청하세요.",
    }


def test_post_verify_rejects_huge_decimal_length_without_integer_conversion(
    running_server,
):
    connection = HTTPConnection(*running_server.server_address, timeout=5)
    try:
        connection.putrequest("POST", "/api/verify")
        connection.putheader("Content-Length", "9" * 5000)
        connection.putheader("Content-Type", "multipart/form-data; boundary=x")
        connection.endheaders()
        response = connection.getresponse()
        body = response.read()
    finally:
        connection.close()

    assert response.status == 413
    assert _json(body)["error"] == "UPLOAD_TOO_LARGE"


def test_bounded_content_length_normalizes_leading_zeros_before_comparison():
    assert verify_server._bounded_content_length("0000000001") == 1
    assert (
        verify_server._bounded_content_length("0" * 5000 + str(_MAX_REQUEST_BYTES + 1))
        is None
    )


def test_post_verify_does_not_classify_leading_zero_length_as_too_large(
    running_server,
):
    connection = HTTPConnection(*running_server.server_address, timeout=5)
    try:
        connection.putrequest("POST", "/api/verify")
        connection.putheader("Content-Length", "0000000001")
        connection.putheader("Content-Type", "application/octet-stream")
        connection.endheaders()
        response = connection.getresponse()
        body = response.read()
    finally:
        connection.close()

    assert response.status == 415
    assert _json(body)["error"] == "MULTIPART_REQUIRED"


@pytest.mark.parametrize(
    ("content_length", "expected_status", "expected_error"),
    [
        (None, 411, "CONTENT_LENGTH_REQUIRED"),
        ("not-a-number", 400, "CONTENT_LENGTH_INVALID"),
    ],
)
def test_post_verify_requires_numeric_content_length(
    running_server,
    content_length,
    expected_status,
    expected_error,
):
    connection = HTTPConnection(*running_server.server_address, timeout=5)
    try:
        connection.putrequest("POST", "/api/verify")
        connection.putheader("Content-Type", "multipart/form-data; boundary=x")
        if content_length is not None:
            connection.putheader("Content-Length", content_length)
        connection.endheaders()
        response = connection.getresponse()
        body = response.read()
    finally:
        connection.close()

    assert response.status == expected_status
    assert _json(body)["error"] == expected_error


def test_post_verify_rejects_wrong_path(running_server):
    status, headers, body = _request_with_headers(
        running_server,
        "POST",
        "/wrong",
        body=b"",
    )

    assert status == 404
    assert headers["content-type"] == "application/json; charset=utf-8"
    assert headers["content-length"] == str(len(body))
    assert headers["cache-control"] == "no-store"
    assert _json(body)["error"] == "REQUEST_PATH_NOT_FOUND"


def test_post_verify_rejects_wrong_content_type(running_server):
    status, _content_type, body = _request(
        running_server,
        "POST",
        "/api/verify",
        body=SAMPLE_REPORT,
        headers={"Content-Type": "application/octet-stream"},
    )

    assert status == 415
    assert _json(body)["error"] == "MULTIPART_REQUIRED"


def test_post_verify_requires_exactly_one_file_field(running_server):
    content_type, body = _multipart_body(
        [("file", "one.dsd", SAMPLE_REPORT), ("file", "two.dsd", SAMPLE_REPORT)]
    )

    status, _response_type, response_body = _request(
        running_server,
        "POST",
        "/api/verify",
        body=body,
        headers={"Content-Type": content_type},
    )

    assert status == 400
    assert _json(response_body)["error"] == "UPLOAD_FILE_COUNT_INVALID"


def test_post_verify_rejects_additional_filename_part(running_server):
    content_type, body = _multipart_body(
        [
            ("file", "company.dsd", SAMPLE_REPORT),
            ("metadata", "metadata.txt", b"metadata"),
        ]
    )

    status, _response_type, response_body = _request(
        running_server,
        "POST",
        "/api/verify",
        body=body,
        headers={"Content-Type": content_type},
    )

    assert status == 400
    assert _json(response_body)["error"] == "UPLOAD_FILE_COUNT_INVALID"


def test_post_verify_rejects_multipart_parser_defects(running_server):
    content_type, body = _multipart_body([("file", "company.dsd", SAMPLE_REPORT)])
    malformed_body = body.rsplit(b"--dart-boundary--", maxsplit=1)[0]

    status, _response_type, response_body = _request(
        running_server,
        "POST",
        "/api/verify",
        body=malformed_body,
        headers={"Content-Type": content_type},
    )

    assert status == 400
    assert _json(response_body)["error"] == "MULTIPART_INVALID"


def test_post_verify_rejects_structured_content_disposition_defects(running_server):
    content_type, body = _raw_multipart_body(
        content_disposition=('form-data; name="file"; filename="unterminated'),
        payload=SAMPLE_REPORT,
    )

    status, _response_type, response_body = _request(
        running_server,
        "POST",
        "/api/verify",
        body=body,
        headers={"Content-Type": content_type},
    )

    assert status == 400
    assert _json(response_body)["error"] == "MULTIPART_INVALID"


@pytest.mark.parametrize("invalid_base64", [b"a", b"abc"])
def test_post_verify_rechecks_base64_defects_after_payload_decode(
    running_server,
    invalid_base64,
):
    content_type, body = _raw_multipart_body(
        content_disposition='form-data; name="file"; filename="company.dsd"',
        payload=invalid_base64,
        transfer_encoding="base64",
    )

    status, _response_type, response_body = _request(
        running_server,
        "POST",
        "/api/verify",
        body=body,
        headers={"Content-Type": content_type},
    )

    assert status == 400
    assert _json(response_body)["error"] == "MULTIPART_INVALID"


def test_post_verify_rejects_multipart_with_zero_parts(running_server):
    boundary = "empty-boundary"
    body = f"--{boundary}--\r\n".encode()

    status, _response_type, response_body = _request(
        running_server,
        "POST",
        "/api/verify",
        body=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )

    assert status == 400
    assert _json(response_body)["error"] == "MULTIPART_INVALID"


def test_post_verify_rejects_wrong_file_field(running_server):
    content_type, body = _multipart_body([("document", "company.dsd", SAMPLE_REPORT)])

    status, _response_type, response_body = _request(
        running_server,
        "POST",
        "/api/verify",
        body=body,
        headers={"Content-Type": content_type},
    )

    assert status == 400
    assert _json(response_body)["error"] == "UPLOAD_FILE_REQUIRED"


def test_post_verify_rejects_empty_upload(running_server):
    status, _content_type, body = _post_file(running_server, "empty.dsd", b"")

    assert status == 400
    assert _json(body)["error"] == "UPLOAD_EMPTY"


@pytest.mark.parametrize(
    ("filename", "expected_error"),
    [
        ("../company.dsd", "UPLOAD_FILENAME_INVALID"),
        ("..\\company.dsd", "UPLOAD_FILENAME_INVALID"),
        ("C:company.dsd", "UPLOAD_FILENAME_INVALID"),
        ("company\x00.dsd", "MULTIPART_INVALID"),
    ],
)
def test_post_verify_rejects_filename_traversal(
    running_server,
    filename,
    expected_error,
):
    status, _content_type, body = _post_file(running_server, filename, SAMPLE_REPORT)

    assert status == 400
    assert _json(body)["error"] == expected_error


@pytest.mark.parametrize("encoded_separator", ["%2F", "%5C"])
def test_post_verify_rejects_rfc_encoded_filename_traversal(
    running_server,
    encoded_separator,
):
    boundary = "encoded-boundary"
    body = (
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; '
            f"filename*=UTF-8''..{encoded_separator}company.dsd\r\n"
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode()
        + SAMPLE_REPORT
        + f"\r\n--{boundary}--\r\n".encode()
    )

    status, _content_type, response_body = _request(
        running_server,
        "POST",
        "/api/verify",
        body=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )

    assert status == 400
    assert _json(response_body)["error"] == "UPLOAD_FILENAME_INVALID"


def test_post_verify_bounds_decoded_file_payload(running_server, monkeypatch):
    monkeypatch.setattr(
        verify_server,
        "_decode_file_payload",
        lambda _part: b"x" * (_MAX_REQUEST_BYTES + 1),
    )

    status, _content_type, body = _post_file(
        running_server,
        "company.dsd",
        SAMPLE_REPORT,
    )

    assert status == 413
    assert _json(body) == {
        "error": "UPLOAD_FILE_TOO_LARGE",
        "message": "디코딩된 첨부 파일은 32 MiB 이하여야 합니다.",
        "next_action": (
            "multipart 경계 정보를 포함한 전체 요청이 32 MiB 이내가 되도록 "
            "더 작은 파일을 선택하세요."
        ),
    }


def test_post_verify_uses_basename_temp_path_and_cleans_it_up(
    running_server,
    monkeypatch,
    managed_temp_paths,
):
    observed_paths: list[Path] = []

    def fake_verify_attachment(source, **_kwargs):
        path = Path(source)
        assert path.name == "company.dsd"
        assert path.exists()
        observed_paths.append(path)
        return '<html data-report-profile="audit-workbench"></html>'

    monkeypatch.setattr(verify_server, "verify_attachment", fake_verify_attachment)

    status, _content_type, _body = _post_file(
        running_server,
        "company.dsd",
        SAMPLE_REPORT,
    )

    assert status == 200
    assert observed_paths
    assert observed_paths[0].parent == managed_temp_paths[0]
    assert observed_paths[0].name == "company.dsd"
    assert not observed_paths[0].exists()
    assert not managed_temp_paths[0].exists()


@pytest.mark.parametrize(
    ("error_kind", "expected_status"),
    [("attachment", 422), ("internal", 500)],
)
def test_post_verify_cleans_temp_artifacts_on_error(
    running_server,
    monkeypatch,
    managed_temp_paths,
    error_kind,
    expected_status,
):
    observed_paths: list[Path] = []

    def fail_verification(source, **_kwargs):
        observed_paths.append(Path(source))
        if error_kind == "attachment":
            raise AttachmentIngestionError(
                "REPORT_STRUCTURE_NOT_FOUND",
                "unsafe /tmp/package.py traceback",
            )
        raise RuntimeError("unsafe /Library/package.py traceback")

    monkeypatch.setattr(verify_server, "verify_attachment", fail_verification)

    status, _content_type, _body = _post_file(
        running_server,
        "company.dsd",
        SAMPLE_REPORT,
    )

    assert status == expected_status
    assert observed_paths
    assert observed_paths[0].parent == managed_temp_paths[0]
    assert not observed_paths[0].exists()
    assert not managed_temp_paths[0].exists()


def test_post_verify_enforces_managed_temp_target_invariant(
    running_server,
    monkeypatch,
    tmp_path,
):
    managed_dir = tmp_path / "managed-upload"

    class ControlledTemporaryDirectory:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            managed_dir.mkdir()
            return str(managed_dir)

        def __exit__(self, *_args):
            shutil.rmtree(managed_dir, ignore_errors=True)

    monkeypatch.setattr(
        verify_server, "TemporaryDirectory", ControlledTemporaryDirectory
    )
    monkeypatch.setattr(verify_server, "_is_safe_filename", lambda _filename: True)
    escaped_target = tmp_path / "escaped.dsd"

    try:
        status, _content_type, body = _post_file(
            running_server,
            "../escaped.dsd",
            SAMPLE_REPORT,
        )

        assert status == 400
        assert _json(body)["error"] == "UPLOAD_FILENAME_INVALID"
        assert not escaped_target.exists()
    finally:
        escaped_target.unlink(missing_ok=True)


@pytest.mark.parametrize(
    ("error_code", "message", "next_action"),
    ATTACHMENT_ERROR_CASES,
)
def test_post_verify_maps_all_attachment_errors_to_safe_json(
    running_server,
    monkeypatch,
    error_code,
    message,
    next_action,
):
    def fail_verification(*_args, **_kwargs):
        raise AttachmentIngestionError(
            error_code,
            "unsafe traceback exception /tmp/package.py /Library/module.py",
        )

    monkeypatch.setattr(verify_server, "verify_attachment", fail_verification)

    status, _content_type, body = _post_file(
        running_server,
        "company.dsd",
        SAMPLE_REPORT,
    )

    assert status == 422
    assert _json(body) == {
        "error": error_code,
        "message": message,
        "next_action": next_action,
    }
    _assert_no_internal_details(body)


def test_post_verify_maps_unknown_attachment_error_to_safe_fallback(
    running_server,
    monkeypatch,
):
    def fail_verification(*_args, **_kwargs):
        raise AttachmentIngestionError(
            "PRIVATE_LIBRARY_ERROR",
            "unsafe traceback exception /tmp/package.py /Library/module.py",
        )

    monkeypatch.setattr(verify_server, "verify_attachment", fail_verification)

    status, _content_type, body = _post_file(
        running_server,
        "company.dsd",
        SAMPLE_REPORT,
    )

    assert status == 422
    assert _json(body) == {
        "error": "ATTACHMENT_VERIFICATION_FAILED",
        "message": "첨부 파일을 검증할 수 없습니다.",
        "next_action": "DART 원문 파일을 다시 내려받아 선택하세요.",
    }
    _assert_no_internal_details(body)


def test_post_verify_hides_internal_exception_details(running_server, monkeypatch):
    def fail_verification(*_args, **_kwargs):
        raise RuntimeError("secret /Library/internal/package.py traceback")

    monkeypatch.setattr(verify_server, "verify_attachment", fail_verification)

    status, _content_type, body = _post_file(
        running_server,
        "company.dsd",
        SAMPLE_REPORT,
    )
    payload = _json(body)

    assert status == 500
    assert payload["error"] == "VERIFICATION_INTERNAL_ERROR"
    _assert_no_internal_details(body)


def _assert_no_internal_details(body: bytes) -> None:
    response_text = body.decode("utf-8").lower()
    for forbidden in (
        "traceback",
        "exception",
        "package",
        "library",
        "/tmp/",
        "/users/",
    ):
        assert forbidden not in response_text
