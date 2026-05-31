"""Fetch public DART viewer HTML for a filing financial section."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DART_BASE = "https://dart.fss.or.kr"
USER_AGENT = "Mozilla/5.0 (compatible; dart-footing-reconciler/0.1)"


@dataclass(frozen=True)
class DartViewerParams:
    rcp_no: str
    dcm_no: str
    ele_id: str
    offset: str
    length: str
    dtd: str


def fetch_financial_section(rcp_no: str, output_path: str | Path) -> Path:
    """Download the `III. 재무에 관한 사항` DART viewer HTML for a receipt no."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    main_html = fetch_url(main_url(rcp_no))
    params = financial_section_params(main_html)
    output.write_text(fetch_url(viewer_url(params)), encoding="utf-8")
    return output


def main_url(rcp_no: str) -> str:
    return f"{DART_BASE}/dsaf001/main.do?{urlencode({'rcpNo': rcp_no})}"


def viewer_url(params: DartViewerParams) -> str:
    query = urlencode({
        'rcpNo': params.rcp_no,
        'dcmNo': params.dcm_no,
        'eleId': params.ele_id,
        'offset': params.offset,
        'length': params.length,
        'dtd': params.dtd,
    })
    return f"{DART_BASE}/report/viewer.do?{query}"


def fetch_url(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=30) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def financial_section_params(main_html: str) -> DartViewerParams:
    """Extract viewer params for the financial section from DART tree JavaScript."""
    text_match = re.search(r"""node\d+\['text'\]\s*=\s*["']III\.\s*재무에 관한 사항["'];""", main_html)
    if text_match is None:
        raise ValueError("DART main page does not contain 'III. 재무에 관한 사항'")

    window = main_html[text_match.start() : text_match.start() + 1400]
    values = {
        field: _field_value(window, field)
        for field in ("rcpNo", "dcmNo", "eleId", "offset", "length", "dtd")
    }
    missing = [field for field, value in values.items() if value is None]
    if missing:
        raise ValueError(f"DART financial section metadata missing: {', '.join(missing)}")
    return DartViewerParams(
        rcp_no=values["rcpNo"] or "",
        dcm_no=values["dcmNo"] or "",
        ele_id=values["eleId"] or "",
        offset=values["offset"] or "",
        length=values["length"] or "",
        dtd=values["dtd"] or "",
    )


def _field_value(source: str, field: str) -> str | None:
    match = re.search(rf"""node\d+\['{field}'\]\s*=\s*["']([^"']+)["'];""", source)
    return match.group(1) if match is not None else None
