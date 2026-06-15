"""Evidence-cockpit HTML renderer for DART audit reconciliation reports.

Public API (backward compatible):
    export_audit_reconciliation_html(report, checks, output_path) -> Path
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.checks import (
    CheckResult, MATCHED, EXPLAINABLE_GAP, UNEXPLAINED_GAP, PARSE_UNCERTAIN, NOT_TESTED,
)
from dart_footing_reconciler.document import FullReport, ReportSection, ReportTable


# ── Public API ───────────────────────────────────────────────────────────────

def export_audit_reconciliation_html(
    report: FullReport,
    checks: list[CheckResult],
    output_path: str | Path,
    *,
    company_name: str = "",
    period_label: str = "",
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    meta = _ReportMeta(
        company=company_name or report.company or "회사",
        period=period_label,
    )
    output.write_text(_build_html(report, checks, meta), encoding="utf-8")
    return output


class _ReportMeta(NamedTuple):
    company: str
    period: str


# ── Tie results ──────────────────────────────────────────────────────────────

def _tie_results(results: list[CheckResult]) -> dict[str, list[CheckResult]]:
    """Group CheckResults by section key from first evidence source.

    Keys: "bs" | "is" | "sce" | "cf" | "note:{note_no}" | "other"
    """
    grouped: dict[str, list[CheckResult]] = {}
    for result in results:
        key = _section_key(result)
        grouped.setdefault(key, []).append(result)
    return grouped


_STMT_KEY_ALIASES = {
    "재무상태표": "bs", "손익계산서": "is", "포괄손익계산서": "oci",
    "자본변동표": "sce", "현금흐름표": "cf",
}

_STMT_KEY_LABELS = {
    "bs": "재무상태표", "재무상태표": "재무상태표", "is": "손익계산서", "손익계산서": "손익계산서",
    "oci": "포괄손익계산서", "포괄손익계산서": "포괄손익계산서", "sce": "자본변동표",
    "자본변동표": "자본변동표", "cf": "현금흐름표", "현금흐름표": "현금흐름표",
}


def _section_key(result: CheckResult) -> str:
    if result.evidence:
        src = result.evidence[0].source
        m = re.match(r"statement:(\w+)", src)
        if m:
            return _STMT_KEY_ALIASES.get(m.group(1), m.group(1))
        m = re.match(r"note:(\w+)", src)
        if m:
            return f"note:{m.group(1)}"
    if result.note_no and result.note_no not in ("", "bs", "cf", "sce", "cross_statement"):
        return f"note:{result.note_no}"
    return "other"


def _parse_source(source: str):
    """Return (scope, name, table_idx, row, col) or None. row/col may be None."""
    m = re.match(r"(statement|note):([^/]+)/table:(\d+)(?:/row:(\d+))?(?:/col:(\d+))?", source or "")
    if not m:
        return None
    scope, name, t_idx, row, col = m.groups()
    return (scope, name, int(t_idx), int(row) if row else None, int(col) if col else None)


def _source_table(report: FullReport, scope: str, name: str, t_idx: int) -> ReportTable | None:
    sections = report.statements if scope == "statement" else report.notes
    for s in sections:
        sid_tail = s.section_id.split(":")[-1]
        if name in (sid_tail, s.note_no, s.title) or name in s.section_id:
            for b in s.blocks:
                if b.table is not None and b.table.index == t_idx:
                    return b.table
    return None


def _humanize_source(report: FullReport, source: str) -> str:
    parsed = _parse_source(source)
    if parsed is None:
        return source or "—"
    scope, name, t_idx, row, col = parsed
    table = _source_table(report, scope, name, t_idx)
    head = (f"주석{name}" if scope == "note" else _STMT_KEY_LABELS.get(name, name))
    if table is None or row is None or row >= len(table.rows):
        return head
    row_label = (table.rows[row][0] if table.rows[row] else "").strip()
    col_head = ""
    if col is not None and table.rows and col < len(table.rows[0]):
        col_head = table.rows[0][col].strip()
    parts = [head, f"'{row_label}'" if row_label else "", col_head]
    return " · ".join(p for p in parts if p)


# ── Build HTML ────────────────────────────────────────────────────────────────

def _build_html(report: FullReport, results: list[CheckResult], meta: _ReportMeta) -> str:
    tied = _tie_results(results)
    uncertain_results = [r for r in results if r.status == PARSE_UNCERTAIN]

    sidebar_html = _render_sidebar(report, results, tied)
    banner_html = _render_verdict_banner(results)

    panels: list[str] = []

    _STMT_KINDS = [
        ("재무상태표", "bs", "재무상태표"),
        ("손익계산서", "is", "손익계산서"),
        ("포괄손익계산서", "oci", "포괄손익계산서"),
        ("자본변동표", "sce", "자본변동표"),
        ("현금흐름표", "cf", "현금흐름표"),
    ]
    rendered_kinds: set[str] = set()
    for title_frag, kind, label in _STMT_KINDS:
        if kind in rendered_kinds:
            continue
        section = _find_section(report.statements, title_frag)
        if section is None:
            continue
        rendered_kinds.add(kind)
        panels.append(_render_statement_panel(
            section, tied.get(kind, []), panel_id=f"panel-{kind}", label=label, report=report,
        ))

    for section in report.notes:
        note_no = section.note_no or section.section_id
        panels.append(_render_note_panel(
            section, tied.get(f"note:{note_no}", []), panel_id=f"panel-note-{note_no}", report=report,
        ))

    if uncertain_results:
        panels.append(_render_parse_uncertain_panel(uncertain_results))

    content = "\n".join(panels)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DART 수치검증 — {_esc(meta.company)}</title>
{_inline_css()}
</head>
<body data-cockpit-profile="evidence_cockpit" data-cockpit-shell="side-app">
<div class="shell">
{sidebar_html}
<main id="main-content">
{banner_html}
{content}
</main>
</div>
{_inline_js()}
</body>
</html>"""


# ── Sidebar ───────────────────────────────────────────────────────────────────

def _render_sidebar(report: FullReport, results: list[CheckResult], tied: dict[str, list[CheckResult]]) -> str:

    def _badge(kind_key: str) -> str:
        items = tied.get(kind_key, [])
        if not items:
            return ""
        warn = sum(1 for r in items if r.status == UNEXPLAINED_GAP)
        unc = sum(1 for r in items if r.status == PARSE_UNCERTAIN)
        if warn:
            return f'<span class="nav-badge nb-warn">⚠ {warn}</span>'
        if unc:
            return f'<span class="nav-badge nb-unc">? {unc}</span>'
        return '<span class="nav-badge nb-ok">✓</span>'

    stmt_items = ""
    _STMT_MAP = [
        ("재무상태표", "bs"), ("손익계산서", "is"),
        ("포괄손익계산서", "oci"),
        ("자본변동표", "sce"), ("현금흐름표", "cf"),
    ]
    for label, kind in _STMT_MAP:
        section = _find_section(report.statements, label)
        if section is None:
            continue
        b = _badge(kind)
        stmt_items += f'<div class="nav-item" data-target="panel-{kind}">{_esc(label)} {b}</div>\n'

    note_items = ""
    for section in report.notes:
        note_no = section.note_no or section.section_id
        b = _badge(f"note:{note_no}")
        note_items += (
            f'<div class="nav-item" data-target="panel-note-{_esc(note_no)}">'
            f'{_esc(section.note_no)}. {_esc(section.title)} {b}'
            f'</div>\n'
        )

    uncertain_count = sum(1 for r in results if r.status == PARSE_UNCERTAIN)
    diag_item = ""
    if uncertain_count:
        diag_item = (
            f'<div class="nav-item" data-target="panel-parse-diag">'
            f'파싱 진단 <span class="nav-badge nb-unc">? {uncertain_count}</span>'
            f'</div>'
        )

    return f"""<aside>
  <div class="sidebar-brand">
    <div class="sidebar-brand-name">DART 수치 검증</div>
    <div class="sidebar-brand-sub">{_esc(report.company)}</div>
  </div>
  <div class="sidebar-section">요약</div>
  <div class="nav-item active" data-target="panel-summary">전체 결과 요약</div>
  <hr class="sidebar-divider">
  <div class="sidebar-section">재무제표 본문</div>
  {stmt_items}
  <hr class="sidebar-divider">
  <div class="sidebar-section">주석</div>
  {note_items}
  {diag_item}
</aside>"""


# ── Verdict Banner ────────────────────────────────────────────────────────────

def _render_verdict_banner(results: list[CheckResult]) -> str:
    matched = sum(1 for r in results if r.status == MATCHED)
    explained = sum(1 for r in results if r.status == EXPLAINABLE_GAP)
    gaps = sum(1 for r in results if r.status == UNEXPLAINED_GAP)
    uncertain = sum(1 for r in results if r.status == PARSE_UNCERTAIN)
    not_tested = sum(1 for r in results if r.status == NOT_TESTED)
    total = len(results)

    if not results:
        verdict_label = "검증 항목 없음"
        verdict_class = "verdict-none"
    elif gaps > 0:
        verdict_label = "검토 필요"
        verdict_class = "verdict-warn"
    elif uncertain > 0:
        verdict_label = "확인 필요"
        verdict_class = "verdict-unc"
    else:
        verdict_label = "이상 없음"
        verdict_class = "verdict-ok"

    # All five statuses are surfaced so explainable gaps and — critically —
    # not-tested coverage are never hidden behind a clean-looking verdict.
    return f"""<div class="verdict-banner {verdict_class}" id="panel-summary">
  <div class="verdict-label">{verdict_label}</div>
  <div class="kpi-strip">
    <div class="kpi-tile kpi-ok"><div class="kpi-val">{matched}</div><div class="kpi-name">검증 완료</div></div>
    <div class="kpi-tile kpi-exp"><div class="kpi-val">{explained}</div><div class="kpi-name">설명된 차이</div></div>
    <div class="kpi-tile kpi-warn"><div class="kpi-val">{gaps}</div><div class="kpi-name">검토 필요</div></div>
    <div class="kpi-tile kpi-unc"><div class="kpi-val">{uncertain}</div><div class="kpi-name">파싱 불확실</div></div>
    <div class="kpi-tile kpi-nt"><div class="kpi-val">{not_tested}</div><div class="kpi-name">미검증</div></div>
    <div class="kpi-tile"><div class="kpi-val">{total}</div><div class="kpi-name">전체</div></div>
  </div>
</div>"""


# ── Statement Panel ───────────────────────────────────────────────────────────

def _render_statement_panel(
    section: ReportSection,
    results: list[CheckResult],
    panel_id: str,
    label: str,
    report: FullReport | None = None,
) -> str:
    table = _first_table(section)
    if table is None:
        return (
            f'<div class="panel" id="{_esc(panel_id)}">'
            f'<div class="panel-title">{_esc(label)}</div>'
            f'<p class="empty-state">공시에서 찾을 수 없음</p></div>'
        )

    row_map: dict[int, CheckResult] = {}
    for result in results:
        for ev in result.evidence:
            m = re.search(r"/row:(\d+)", ev.source)
            if m:
                idx = int(m.group(1))
                if idx not in row_map:
                    row_map[idx] = result

    rows_html = _render_table_rows(table, row_map, id_prefix=panel_id, show_state=True, report=report)
    check_summary = _render_check_summary(results) if results else ""

    return f"""<div class="panel" id="{_esc(panel_id)}">
  <div class="panel-title">{_esc(label)}</div>
  <div class="panel-sub">원문 보고서 형태 · 검증 행 클릭 시 근거 확인</div>
  <div class="statement-wrap">
    <div class="statement-caption"><span>{_esc(label)}</span></div>
    <table class="fs-table">
      {rows_html}
    </table>
  </div>
  {check_summary}
</div>"""


def _render_table_rows(
    table: ReportTable,
    row_map: dict[int, CheckResult],
    *,
    id_prefix: str = "dd",
    show_state: bool = False,
    report: FullReport | None = None,
) -> str:
    html_parts: list[str] = []
    if not table.rows:
        return ""

    header = table.rows[0]
    if show_state:
        header_cells = '<th class="state-col">검증</th>' + "".join(f"<th>{_esc(c)}</th>" for c in header)
    else:
        header_cells = "".join(f"<th>{_esc(c)}</th>" for c in header)
    html_parts.append(f"<thead><tr>{header_cells}</tr></thead><tbody>")

    for i, row in enumerate(table.rows[1:], start=1):
        result = row_map.get(i)
        # Determine whether this row has any amount value (non-blank, non-None)
        has_amount = any(parse_amount(c) is not None for c in row)
        if result is not None:
            css_class = _status_to_row_class(result.status)
            dd_id = f"{id_prefix}-{i}"
            cells = "".join(f"<td>{_esc(c)}</td>" for c in row)
            if show_state:
                state_cell = f'<td class="state-col">{_account_state_badge(result.status)}</td>'
                dd_colspan = len(row) + 1
                html_parts.append(
                    f'<tr class="{css_class}" data-check-row="{i}" '
                    f'onclick="toggleDD(\'{dd_id}\')">{state_cell}{cells}</tr>'
                )
            else:
                dd_colspan = len(row)
                html_parts.append(
                    f'<tr class="{css_class}" data-check-row="{i}" '
                    f'onclick="toggleDD(\'{dd_id}\')">{cells}</tr>'
                )
            html_parts.append(
                f'<tr class="dd-row">'
                f'<td colspan="{dd_colspan}" class="dd-cell">'
                f'<div class="dd-inner" id="{dd_id}">'
                f'{_render_drilldown(result, report)}'
                f'</div></td></tr>'
            )
        elif has_amount:
            cells = "".join(f"<td>{_esc(c)}</td>" for c in row)
            if show_state:
                state_cell = f'<td class="state-col">{_account_state_badge(None)}</td>'
                html_parts.append(f"<tr>{state_cell}{cells}</tr>")
            else:
                html_parts.append(f"<tr>{cells}</tr>")
        else:
            cells = "".join(f"<td>{_esc(c)}</td>" for c in row)
            if show_state:
                state_cell = '<td class="state-col"></td>'
                html_parts.append(f"<tr>{state_cell}{cells}</tr>")
            else:
                html_parts.append(f"<tr>{cells}</tr>")

    html_parts.append("</tbody>")
    return "\n".join(html_parts)


def _status_to_row_class(status: str) -> str:
    if status == MATCHED:
        return "verified-ok"
    if status == UNEXPLAINED_GAP:
        return "verified-warn"
    return "verified-uncertain"


def _render_drilldown(result: CheckResult, report: FullReport | None = None) -> str:
    callout_class = "ok" if result.status == MATCHED else "warn"
    callout_icon = "✓" if result.status == MATCHED else "⚠"
    ev_rows = ""
    raw_rows = ""
    for ev in result.evidence:
        amount_str = f"{ev.amount:,}" if ev.amount is not None else "—"
        human = _humanize_source(report, ev.source) if report is not None else (ev.source or "—")
        ev_rows += f"<tr><td>{_esc(ev.label)}</td><td>{amount_str}</td><td class='src-ref'>{_esc(human)}</td></tr>"
        raw_rows += f"<div>{_esc(ev.label)}: <code>{_esc(ev.source)}</code></div>"
    uncertain_note = ""
    if result.parse_uncertain_reason:
        uncertain_note = f'<div class="callout unc">파싱 사유: {_esc(result.parse_uncertain_reason)}</div>'
    return f"""<div class="dd-title">{_esc(result.title)}</div>
<table class="src-tbl">
  <thead><tr><th>항목</th><th>금액</th><th>근거 위치</th></tr></thead>
  <tbody>{ev_rows}</tbody>
</table>
<div class="callout {callout_class}">{callout_icon} {_esc(result.reason)}</div>
{uncertain_note}
<details class="tech-detail"><summary>기술 세부정보</summary>{raw_rows}</details>"""


def _render_check_summary(results: list[CheckResult]) -> str:
    if not results:
        return ""
    rows = ""
    for result in results:
        badge_class = _status_to_badge_class(result.status)
        badge_label = _status_to_badge_label(result.status)
        exp_str = f"{result.expected:,}" if result.expected is not None else "—"
        act_str = f"{result.actual:,}" if result.actual is not None else "—"
        diff_str = f"차이 {result.difference:,}" if result.difference is not None else ""
        rows += f"""<div class="check-row">
  <span class="check-name">{_esc(result.title)}</span>
  <span class="check-vals"><span>{exp_str}</span><span>{act_str}</span><span>{diff_str}</span></span>
  <span class="badge {badge_class}">{badge_label}</span>
</div>"""
    return f'<div class="check-summary"><div class="check-summary-head">검증 결과</div>{rows}</div>'


# ── Note Panel ────────────────────────────────────────────────────────────────

def _display_check_title(title: str, section: ReportSection) -> str:
    """Drop the redundant note-no/title prefix (the panel already names the note)
    and Koreanize trailing English check phrases."""
    out = title
    prefixes = []
    if section.note_no:
        prefixes.append(f"{section.note_no}. {section.title}")
        prefixes.append(f"{section.note_no}.{section.title}")
    prefixes.append(section.title)
    for p in prefixes:
        if p and out.startswith(p):
            out = out[len(p):]
            break
    out = out.replace("total check", "합계검증").replace("column total", "열 합계검증")
    return out.strip(" ·-—") or title


def _render_note_panel(
    section: ReportSection,
    results: list[CheckResult],
    panel_id: str,
    report: FullReport | None = None,
) -> str:
    table = _first_table(section)
    table_html = ""
    if table is not None:
        rows_html = _render_table_rows(table, {}, report=report)
        table_html = f'<div class="statement-wrap"><table class="fs-table">{rows_html}</table></div>'

    check_rows = ""
    for result in results:
        badge_class = _status_to_badge_class(result.status)
        badge_label = _status_to_badge_label(result.status)
        exp_str = f"{result.expected:,}" if result.expected is not None else "—"
        act_str = f"{result.actual:,}" if result.actual is not None else "—"
        diff_str = f"차이 {result.difference:,}" if result.difference is not None else ""
        dd_id = f"dd-note-{_safe_id(result.check_id)}"
        title_disp = _display_check_title(result.title, section)
        check_rows += f"""<div class="check-row" onclick="toggleDD('{dd_id}')">
  <span class="expand-tri" id="tri-{dd_id}">▶</span>
  <span class="check-name">{_esc(title_disp)}</span>
  <span class="check-vals"><span>{exp_str}</span><span>{act_str}</span><span>{diff_str}</span></span>
  <span class="badge {badge_class}">{badge_label}</span>
</div>
<div class="dd-inline" id="{dd_id}">{_render_drilldown(result, report)}</div>"""

    check_section = (
        f'<div class="check-summary"><div class="check-summary-head">검증 결과</div>{check_rows}</div>'
        if results else ""
    )

    return f"""<div class="panel" id="{_esc(panel_id)}">
  <div class="panel-title">{"" if not section.note_no else _esc(section.note_no) + ". "}{_esc(section.title)}</div>
  {table_html}
  {check_section}
</div>"""


# ── Parse Uncertain Panel ─────────────────────────────────────────────────────

def _render_parse_uncertain_panel(results: list[CheckResult]) -> str:
    cards = ""
    for result in results:
        reason_code = result.parse_uncertain_reason or "UNKNOWN"
        reason_text = _uncertain_reason_text(reason_code)
        candidates_text = ""
        for ev in result.evidence:
            if ev.source:
                candidates_text += f"<li>항목: {_esc(ev.label)} — 출처: {_esc(ev.source)}</li>"
        cards += f"""<div class="diag-card">
  <div class="diag-title">{_esc(result.title)}</div>
  <div class="diag-reason"><span class="badge badge-unc">{_esc(reason_code)}</span> {_esc(reason_text)}</div>
  <ul class="diag-candidates">{candidates_text}</ul>
  <div class="diag-guide">이 항목이 공시에 포함된 경우 issue를 제보하세요.</div>
</div>"""

    return f"""<div class="panel" id="panel-parse-diag">
  <div class="panel-title">파싱 진단</div>
  <div class="panel-sub">자동 해석에 실패한 항목입니다.</div>
  {cards}
</div>"""


def _uncertain_reason_text(code: str) -> str:
    return {
        "LABEL_NOT_FOUND": "공시에서 해당 계정과목을 찾지 못했습니다.",
        "LOW_CONFIDENCE_MATCH": "유사한 항목을 찾았으나 신뢰도가 낮습니다.",
        "AMBIGUOUS_MULTIPLE": "동일한 신뢰도의 후보가 여러 개입니다.",
        "COLUMN_NOT_DETECTED": "당기/전기 컬럼을 구별하지 못했습니다.",
        "TABLE_NOT_FOUND": "해당 재무제표/주석 섹션이 공시에 없습니다.",
        "AMOUNT_PARSE_FAILED": "행은 찾았으나 숫자 추출에 실패했습니다.",
    }.get(code, "알 수 없는 파싱 오류입니다.")


# ── CSS ───────────────────────────────────────────────────────────────────────

def _inline_css() -> str:
    return """<style>
:root {
  --bg:#fff; --surface:#f8fafc; --surface-2:#f1f5f9;
  --border:#e2e8f0; --text:#0f172a; --muted:#64748b;
  --accent:#3b82f6; --accent-dim:rgba(59,130,246,.12);
  --warn:#f59e0b; --warn-dim:#fef3c7;
  --ok:#16a34a; --ok-dim:#dcfce7;
  --down:#dc2626; --down-dim:#fee2e2;
  --sidebar-bg:#0f172a; --sidebar-text:#94a3b8;
  --sidebar-active:#f1f5f9; --sidebar-accent:#3b82f6;
  --font:Pretendard,ui-sans-serif,system-ui,-apple-system,sans-serif;
}
*{box-sizing:border-box;margin:0;padding:0;}
body{font-family:var(--font);background:var(--bg);color:var(--text);font-size:13px;line-height:1.6;letter-spacing:0;}
.shell{display:grid;grid-template-columns:220px minmax(0,1fr);min-height:100vh;}
aside{background:var(--sidebar-bg);border-right:1px solid rgba(255,255,255,.06);padding:20px 0;position:sticky;top:0;height:100vh;overflow-y:auto;}
.sidebar-brand{padding:0 16px 14px;border-bottom:1px solid rgba(255,255,255,.08);margin-bottom:8px;}
.sidebar-brand-name{font-size:12px;font-weight:700;color:var(--sidebar-active);}
.sidebar-brand-sub{font-size:11px;color:#475569;margin-top:2px;}
.sidebar-section{padding:10px 16px 4px;font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:.06em;}
.nav-item{display:flex;align-items:center;gap:8px;padding:7px 16px;font-size:12px;font-weight:500;color:var(--sidebar-text);cursor:pointer;border-left:3px solid transparent;}
.nav-item:hover,.nav-item.active{background:rgba(255,255,255,.05);color:var(--sidebar-active);}
.nav-item.active{background:rgba(59,130,246,.18);border-left-color:var(--sidebar-accent);font-weight:700;}
.nav-badge{margin-left:auto;font-size:10px;padding:1px 5px;border-radius:3px;font-weight:700;}
.nb-ok{background:rgba(22,163,74,.2);color:#4ade80;}
.nb-warn{background:rgba(249,115,22,.2);color:#fb923c;}
.nb-unc{background:rgba(100,116,139,.2);color:#94a3b8;}
.sidebar-divider{border:none;border-top:1px solid rgba(255,255,255,.06);margin:8px 0;}
main{padding:24px 28px;}
.panel{margin-bottom:32px;}
.panel.hidden{display:none;}
.panel-title{font-size:14px;font-weight:800;margin-bottom:2px;}
.panel-sub{font-size:12px;color:var(--muted);margin-bottom:16px;}
.empty-state{color:var(--muted);font-size:12px;padding:12px 0;}
.verdict-banner{padding:16px 20px;border-radius:10px;border:1px solid var(--border);margin-bottom:24px;}
.verdict-banner.verdict-ok{border-color:#bbf7d0;background:var(--ok-dim);}
.verdict-banner.verdict-warn{border-color:#fde68a;background:var(--warn-dim);}
.verdict-banner.verdict-unc{border-color:var(--border);background:var(--surface);}
.verdict-label{font-size:16px;font-weight:800;margin-bottom:12px;}
.kpi-strip{display:flex;gap:12px;flex-wrap:wrap;}
.kpi-tile{background:#fff;border:1px solid var(--border);border-radius:7px;padding:10px 16px;min-width:100px;}
.kpi-val{font-size:22px;font-weight:800;}
.kpi-name{font-size:11px;color:var(--muted);}
.kpi-tile.kpi-ok .kpi-val{color:var(--ok);}
.kpi-tile.kpi-exp .kpi-val{color:var(--accent,#1f6feb);}
.kpi-tile.kpi-warn .kpi-val{color:var(--warn);}
.kpi-tile.kpi-unc .kpi-val{color:var(--muted);}
.kpi-tile.kpi-nt .kpi-val{color:#b7791f;}
.statement-wrap{border:1px solid var(--border);border-radius:8px;overflow:hidden;margin-bottom:16px;}
.statement-caption{padding:9px 16px;background:var(--surface-2);border-bottom:1px solid var(--border);font-size:12px;font-weight:700;color:var(--muted);}
.fs-table{width:100%;border-collapse:collapse;font-size:12px;}
.fs-table th{padding:7px 12px;background:var(--surface-2);border-bottom:1px solid var(--border);font-size:11px;font-weight:700;color:var(--muted);text-align:right;}
.fs-table th:first-child{text-align:left;}
.fs-table td{padding:7px 12px;border-bottom:1px solid var(--border);text-align:right;font-variant-numeric:tabular-nums;}
.fs-table td:first-child{text-align:left;}
.fs-table tr:last-child td{border-bottom:none;}
.verified-ok td:first-child::after{content:"✓";display:inline-flex;align-items:center;justify-content:center;margin-left:8px;width:16px;height:16px;background:var(--ok-dim);color:var(--ok);border-radius:3px;font-size:10px;font-weight:800;vertical-align:middle;}
.verified-warn td:first-child::after{content:"⚠";display:inline-flex;align-items:center;justify-content:center;margin-left:8px;width:16px;height:16px;background:var(--warn-dim);color:var(--warn);border-radius:3px;font-size:10px;font-weight:800;vertical-align:middle;}
.verified-uncertain td:first-child::after{content:"?";display:inline-flex;align-items:center;justify-content:center;margin-left:8px;width:16px;height:16px;background:var(--surface-2);color:var(--muted);border-radius:3px;font-size:10px;font-weight:800;vertical-align:middle;}
.verified-ok{cursor:pointer;} .verified-ok:hover td{background:#f0fdf4;}
.verified-warn{cursor:pointer;} .verified-warn:hover td{background:#fffbeb;}
.verified-uncertain{cursor:pointer;} .verified-uncertain:hover td{background:var(--surface);}
.dd-cell{padding:0!important;}
.dd-inner,.dd-inline{display:none;padding:12px 16px;background:var(--surface);border-top:2px solid var(--border);}
.dd-inner.open,.dd-inline.open{display:block;}
.dd-title{font-size:12px;font-weight:700;margin-bottom:8px;}
.src-tbl{width:100%;border-collapse:collapse;font-size:11px;margin-bottom:8px;}
.src-tbl th{background:var(--surface-2);padding:4px 8px;border:1px solid var(--border);font-size:10px;color:var(--muted);}
.src-tbl td{padding:5px 8px;border:1px solid var(--border);}
.src-ref{color:var(--muted);font-size:10px;}
.callout{margin-top:8px;padding:7px 10px;border-radius:5px;font-size:11px;}
.callout.ok{background:var(--ok-dim);border:1px solid #bbf7d0;color:#166534;}
.callout.warn{background:var(--warn-dim);border:1px solid #fde68a;color:#92400e;}
.callout.unc{background:var(--surface-2);border:1px solid var(--border);color:var(--muted);}
.check-summary{border:1px solid var(--border);border-radius:8px;overflow:hidden;margin-top:8px;}
.check-summary-head{padding:9px 14px;background:var(--surface-2);border-bottom:1px solid var(--border);font-size:11px;font-weight:700;color:var(--muted);}
.check-row{display:flex;align-items:center;gap:10px;padding:8px 14px;border-bottom:1px solid var(--border);font-size:12px;cursor:pointer;}
.check-row:last-child{border-bottom:none;}
.check-row:hover{background:var(--surface);}
.check-name{flex:1;}
.check-vals{display:flex;gap:14px;font-variant-numeric:tabular-nums;color:var(--muted);font-size:11px;}
.badge{display:inline-flex;align-items:center;padding:2px 7px;border-radius:4px;font-size:11px;font-weight:700;}
.badge-ok{background:var(--ok-dim);color:#166534;}
.badge-warn{background:var(--warn-dim);color:#92400e;}
.badge-unc{background:var(--surface-2);color:var(--muted);}
.expand-tri{font-size:9px;color:var(--muted);transition:transform .15s;display:inline-block;}
.diag-card{border:1px solid var(--border);border-radius:7px;padding:14px;margin-bottom:12px;}
.diag-title{font-size:13px;font-weight:700;margin-bottom:6px;}
.diag-reason{margin-bottom:8px;font-size:12px;}
.diag-candidates{margin-left:16px;font-size:11px;color:var(--muted);}
.diag-guide{margin-top:8px;font-size:11px;color:var(--muted);}
.acct-state{font-size:10px;font-weight:700;padding:1px 6px;border-radius:3px;border:1px solid var(--border);white-space:nowrap;}
.as-ok{color:var(--ok);} .as-warn{color:var(--warn);} .as-unc{color:var(--muted);} .as-nt{color:#94a3b8;}
.state-col{width:64px;text-align:center;}
.tech-detail{margin-top:8px;font-size:11px;color:var(--muted);} .tech-detail code{font-size:10px;}
</style>"""


# ── JS micro-runtime ───────────────────────────────────────────────────────────

def _inline_js() -> str:
    return """<script>
(function(){
  var navItems = document.querySelectorAll('.nav-item[data-target]');
  var panels = document.querySelectorAll('.panel');
  navItems.forEach(function(item){
    item.addEventListener('click', function(){
      var target = item.getAttribute('data-target');
      navItems.forEach(function(n){ n.classList.remove('active'); });
      item.classList.add('active');
      panels.forEach(function(p){
        p.classList.toggle('hidden', p.id !== target);
      });
      var tp = document.getElementById(target);
      if(tp){ tp.scrollIntoView({behavior:'smooth',block:'start'}); }
    });
  });
})();

function toggleDD(id){
  var el = document.getElementById(id);
  if(!el) return;
  el.classList.toggle('open');
  var tri = document.getElementById('tri-' + id);
  if(tri){ tri.style.transform = el.classList.contains('open') ? 'rotate(90deg)' : ''; }
}
</script>"""


# ── Helpers ────────────────────────────────────────────────────────────────────

def _esc(text: str | None) -> str:
    if not text:
        return ""
    return (str(text)
            .replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _esc_js_str(text: str | None) -> str:
    if not text:
        return ""
    return str(text).replace("\\", "\\\\").replace("'", "\\'")


def _safe_id(text: str) -> str:
    """Make a string safe for use as an HTML id attribute and JS string literal.

    Replaces any character that is not alphanumeric, hyphen, or underscore with
    a hyphen, so the result is safe in both ``id="..."`` HTML attributes and
    ``onclick="toggleDD('...')"`` JS single-quoted string contexts.
    """
    return re.sub(r"[^a-zA-Z0-9_-]", "-", str(text))


def _find_section(sections: list[ReportSection], title_frag: str) -> ReportSection | None:
    for s in sections:
        if title_frag in s.title:
            return s
    return None


def _first_table(section: ReportSection) -> ReportTable | None:
    for block in section.blocks:
        if block.table is not None:
            return block.table
    return None


def _status_to_badge_class(status: str) -> str:
    if status == MATCHED:
        return "badge-ok"
    if status == UNEXPLAINED_GAP:
        return "badge-warn"
    return "badge-unc"


def _status_to_badge_label(status: str) -> str:
    if status == MATCHED:
        return "✓ 일치"
    if status == UNEXPLAINED_GAP:
        return "⚠ 차이"
    return "? 불확실"


def _account_state_badge(status: str | None) -> str:
    """Per-account verification-state badge for statement line rows.
    status None => 미검증 (no covering check). Render-derived; never a CheckResult."""
    if status == MATCHED:
        return '<span class="acct-state as-ok">검증완료</span>'
    if status == UNEXPLAINED_GAP:
        return '<span class="acct-state as-warn">검토필요</span>'
    if status == PARSE_UNCERTAIN:
        return '<span class="acct-state as-unc">파싱불확실</span>'
    return '<span class="acct-state as-nt">미검증</span>'
