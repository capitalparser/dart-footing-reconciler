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
from dart_footing_reconciler.document import (
    FullReport,
    ReportSection,
    ReportTable,
    SourceLocation,
)
from dart_footing_reconciler.html_tables import TableCellLayout
from dart_footing_reconciler.formula_templates import is_subtotal_row_label
from dart_footing_reconciler.narrative_evidence import (
    NarrativeEvidenceDataset,
    NarrativeNoteReference,
    build_narrative_evidence,
)
from dart_footing_reconciler.report_frame import (
    CellAnnotation,
    CHECK_DISPLAY_NAMES,
    CHECK_GROUP_ORDER,
    CHECK_GROUPS,
    CHECK_METHOD_DESCRIPTIONS,
    DrawerItem,
    TABLE_UNIT_TOLERANCE_CHECK_TYPES,
    check_display_reason,
    check_display_title,
    check_status_compact_label,
    build_workbench_annotations,
    evidence_display_label,
    source_cell_ref,
    statement_kind_from_source,
    statement_kind_from_title,
)


# ── Severity helpers ─────────────────────────────────────────────────────────

_STATUS_SEVERITY = {UNEXPLAINED_GAP: 3, PARSE_UNCERTAIN: 2, MATCHED: 1}


def _worse(a: CheckResult, b: CheckResult) -> CheckResult:
    """Return the check result with the higher severity status."""
    return a if _STATUS_SEVERITY.get(a.status, 0) >= _STATUS_SEVERITY.get(b.status, 0) else b


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


class _RenderedTable(NamedTuple):
    section: ReportSection
    table: ReportTable
    panel_id: str
    panel_key: str


class _ReportRenderMap(NamedTuple):
    tables_by_index: dict[int, tuple[_RenderedTable, ...]]
    statement_panel_ids: dict[int, str]
    unique_statement_panel_keys: dict[str, str]
    note_panel_ids: dict[int, str]
    unique_note_panel_keys: dict[str, str]


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
    "이익잉여금처분계산서": "appropriation", "결손금처리계산서": "appropriation",
    "balance_sheet": "bs", "financial_position": "bs",
    "income_statement": "is", "comprehensive_income": "oci",
    "changes_in_equity": "sce", "cash_flows": "cf", "cashflow_statement": "cf",
}

_STMT_KEY_LABELS = {
    "bs": "재무상태표", "재무상태표": "재무상태표", "is": "손익계산서", "손익계산서": "손익계산서",
    "oci": "포괄손익계산서", "포괄손익계산서": "포괄손익계산서", "sce": "자본변동표",
    "자본변동표": "자본변동표", "cf": "현금흐름표", "현금흐름표": "현금흐름표",
    "appropriation": "이익잉여금처분계산서", "이익잉여금처분계산서": "이익잉여금처분계산서",
    "결손금처리계산서": "결손금처리계산서",
}

_STMT_KINDS = [
    ("재무상태표", "bs", "재무상태표"),
    ("손익계산서", "is", "손익계산서"),
    ("포괄손익계산서", "oci", "포괄손익계산서"),
    ("자본변동표", "sce", "자본변동표"),
    ("현금흐름표", "cf", "현금흐름표"),
    ("이익잉여금처분계산서", "appropriation", "이익잉여금처분계산서"),
    ("결손금처리계산서", "appropriation", "결손금처리계산서"),
]

_FRAME_KIND_TO_PANEL_KEY = {
    "financial_position": "bs",
    "income_statement": "is",
    "changes_in_equity": "sce",
    "cash_flows": "cf",
    "appropriation": "appropriation",
}

_STATEMENT_KIND_LABELS = {kind: label for _fragment, kind, label in _STMT_KINDS}
_STATEMENT_KIND_ORDER = {kind: index for index, (_fragment, kind, _label) in enumerate(_STMT_KINDS)}


def _section_key(result: CheckResult) -> str:
    if result.evidence:
        src = result.evidence[0].source
        m = re.match(r"statement:([^/]+)", src)
        if m:
            return _statement_panel_key(m.group(1))
        m = re.match(r"note:([^/]+)", src)
        if m:
            return f"note:{m.group(1)}"
    if result.note_no and result.note_no not in ("", "bs", "cf", "sce", "cross_statement"):
        return f"note:{result.note_no}"
    return "other"


def _statement_panel_key(name: str) -> str:
    alias = _STMT_KEY_ALIASES.get(name)
    if alias is not None:
        return alias
    kind = statement_kind_from_title(name) or statement_kind_from_source(f"statement:{name}")
    return _FRAME_KIND_TO_PANEL_KEY.get(kind, name)


def _statement_kind_for_section(section: ReportSection) -> str:
    text = f"{section.section_id} {section.title}"
    compact = "".join(text.split()).lower()
    if "처분계산서" in compact or "처리계산서" in compact:
        return "appropriation"
    if "재무상태표" in compact or "statement:bs" in compact or "statement:balance_sheet" in compact:
        return "bs"
    if "포괄손익계산서" in compact or "statement:oci" in compact:
        return "oci"
    if "손익계산서" in compact or "statement:is" in compact or "statement:pl" in compact:
        return "is"
    if "자본변동표" in compact or "statement:sce" in compact or "statement:equity" in compact:
        return "sce"
    if "현금흐름표" in compact or "statement:cf" in compact or "statement:cfs" in compact:
        return "cf"
    return ""


def _statement_label(kind: str, section: ReportSection) -> str:
    return _STATEMENT_KIND_LABELS.get(kind, section.title or kind)


def _parse_source(source: str):
    """Return (scope, name, table_idx, row, col) or None. row/col may be None."""
    m = re.match(r"(statement|note):([^/]+)/table:(\d+)(?:/row:(\d+))?(?:/col:(\d+))?", source or "")
    if not m:
        return None
    scope, name, t_idx, row, col = m.groups()
    return (scope, name, int(t_idx), int(row) if row else None, int(col) if col else None)


class _NarrativeSourceRef(NamedTuple):
    kind: str
    name: str
    scope: str
    block_index: int
    segment_index: int | None


def _parse_narrative_source(source: str) -> _NarrativeSourceRef | None:
    match = re.match(
        r"^(statement|note):([^@/]+)@([^/]+)/block:(\d+)(?:/segment:(\d+))?$",
        source or "",
    )
    if match is None:
        return None
    kind, name, scope, block_index, segment_index = match.groups()
    return _NarrativeSourceRef(
        kind,
        name,
        scope,
        int(block_index),
        int(segment_index) if segment_index is not None else None,
    )


def _section_for_narrative_source(
    report: FullReport, source: _NarrativeSourceRef
) -> ReportSection | None:
    sections = report.statements if source.kind == "statement" else report.notes
    section_id = f"{source.kind}:{source.name}"
    matches = [
        section
        for section in sections
        if section.section_id == section_id
        and (section.scope or "unknown") == source.scope
        and any(
            block.location.block_index == source.block_index
            for block in section.blocks
        )
    ]
    return matches[0] if len(matches) == 1 else None


def _narrative_panel_id(
    report: FullReport,
    source: _NarrativeSourceRef,
    render_map: _ReportRenderMap,
) -> str:
    section = _section_for_narrative_source(report, source)
    if section is None:
        return ""
    if source.kind == "statement":
        return _statement_panel_id(render_map, section)
    return _note_panel_id(render_map, section)


def _split_source_context(source: str) -> tuple[str, str]:
    if (source or "").startswith("prior:"):
        return "prior", source[len("prior:"):]
    return "current", source or ""


def _parse_period_source(source: str) -> tuple[str, str, str] | None:
    match = re.match(r"^(statement|note):([^/]+)/([A-Za-z_]+)$", source or "")
    if match is None:
        return None
    scope, name, period_tag = match.groups()
    if period_tag not in {"current", "comparative", "prior", "beginning", "ending"}:
        return None
    return scope, name, period_tag


def _parse_table_period_source(source: str) -> tuple[str, str, int, str] | None:
    match = re.match(
        r"^(statement|note):([^/]+)/table:(\d+)/(beginning|ending|current|comparative|prior)$",
        source or "",
    )
    if match is None:
        return None
    scope, name, table_idx, period_tag = match.groups()
    return scope, name, int(table_idx), period_tag


_SOURCE_PERIOD_LABELS = {
    "current": "당기",
    "comparative": "비교기간",
    "prior": "전기",
    "beginning": "기초",
    "ending": "기말",
}


def _row_key(table_idx: int, row_idx: int) -> str:
    return f"t{table_idx}r{row_idx}"


def _cell_key(table_idx: int, row_idx: int, col_idx: int | None) -> str:
    row_key = _row_key(table_idx, row_idx)
    if col_idx is None:
        return row_key
    return f"{row_key}c{col_idx}"


def _source_table(report: FullReport, scope: str, name: str, t_idx: int) -> ReportTable | None:
    sections = report.statements if scope == "statement" else report.notes
    for s in sections:
        if _section_matches_source(s, scope, name):
            for b in s.blocks:
                if b.table is not None and b.table.index == t_idx:
                    return b.table
    return None


def _rendered_table_for_source(parsed_source, render_map: _ReportRenderMap) -> _RenderedTable | None:
    scope, name, table_idx, _row_idx, _col_idx = parsed_source
    candidates = render_map.tables_by_index.get(table_idx, ())
    matched = [
        candidate
        for candidate in candidates
        if _section_matches_source(candidate.section, scope, name)
    ]
    if len(matched) == 1:
        return matched[0]
    if len(candidates) == 1:
        return candidates[0]
    return None


def _section_matches_source(section: ReportSection, scope: str, name: str) -> bool:
    sid_tail = section.section_id.split(":")[-1]
    if scope == "statement":
        target_key = _statement_panel_key(name)
        section_keys = {
            _statement_panel_key(value)
            for value in (sid_tail, section.title, section.section_id)
            if value
        }
        return target_key in section_keys or name in section.section_id
    section_names = {sid_tail, section.note_no, section.title}
    return name in section_names or name in section.section_id


def _source_page_label(location: SourceLocation | None) -> str:
    if (
        location is None
        or location.input_format != "pdf"
        or location.page_number is None
    ):
        return ""
    return f"PDF {location.page_number}쪽"


def _humanize_source(report: FullReport, source: str) -> str:
    context, source_body = _split_source_context(source)
    table_period_source = _parse_table_period_source(source_body)
    if table_period_source is not None:
        scope, name, _table_idx, period_tag = table_period_source
        head = _source_head(scope, name)
        if context == "prior":
            head = f"전기 보고서 {head}"
        return f"{head} · {_SOURCE_PERIOD_LABELS[period_tag]}"
    period_source = _parse_period_source(source_body)
    if period_source is not None:
        scope, name, period_tag = period_source
        head = _source_head(scope, name)
        if context == "prior":
            head = f"전기 보고서 {head}"
        return f"{head} · {_SOURCE_PERIOD_LABELS[period_tag]}"
    parsed = _parse_source(source_body)
    if parsed is None:
        return "근거 위치 확인 필요"
    scope, name, t_idx, row, col = parsed
    table = _source_table(report, scope, name, t_idx) if context == "current" else None
    head = _source_head(scope, name)
    if context == "prior":
        head = f"전기 보고서 {head}"
    if table is None or row is None or row >= len(table.rows):
        return head
    row_label = (table.rows[row][0] if table.rows[row] else "").strip()
    col_head = ""
    if col is not None and table.rows and col < len(table.rows[0]):
        col_head = table.rows[0][col].strip()
    parts = [head, f"'{row_label}'" if row_label else "", col_head]
    return " · ".join(p for p in parts if p)


def _source_head(scope: str, name: str) -> str:
    if scope == "note":
        return f"주석{name}"
    panel_key = _statement_panel_key(name)
    return _STMT_KEY_LABELS.get(
        panel_key,
        "재무제표" if re.search(r"[A-Za-z_]", name) else name,
    )


def _source_panel_id(scope: str, name: str) -> str:
    if scope == "note":
        return f"panel-note-{name}"
    return f"panel-{_statement_panel_key(name)}"


def _source_panel_id_for_parsed(parsed_source, render_map: _ReportRenderMap | None) -> str:
    if render_map is None:
        return ""
    rendered = _rendered_table_for_source(parsed_source, render_map)
    return rendered.panel_id if rendered is not None else ""


# ── Build HTML ────────────────────────────────────────────────────────────────

def _build_html(report: FullReport, results: list[CheckResult], meta: _ReportMeta) -> str:
    render_map = _build_render_map(report)
    available_scopes = _available_report_scopes(report)
    active_scope = _default_report_scope(available_scopes)
    annotations = build_workbench_annotations(report, results)
    sidebar_html, first_panel_id = _render_workbench_sidebar(
        report,
        results,
        render_map,
    )
    source_panels_html = _render_workbench_source_panels(
        report,
        annotations.cells,
        annotations.drawers,
        render_map,
        first_panel_id=first_panel_id,
    )
    drawer_html = _render_workbench_drawer(report, annotations.drawers, render_map)
    masthead_html = _render_workbench_header(
        report,
        annotations.drawers,
        meta,
        render_map,
        available_scopes,
        active_scope,
    )

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DART 수치검증 — {_esc(meta.company)}</title>
{_workbench_css()}
</head>
<body data-report-profile="audit-workbench" data-active-report-scope="{_esc(active_scope)}">
<a class="skip-link" href="#main-content">본문으로 건너뛰기</a>
<div id="workbench-status" class="sr-only" aria-live="polite" aria-atomic="true"></div>
{masthead_html}
<div class="audit-workbench">
<aside class="source-nav" aria-label="원문 탐색">
{sidebar_html}
</aside>
<main class="source-stage" id="main-content" tabindex="-1">
{source_panels_html}
</main>
<aside class="reconciliation-drawer" id="reconciliation-drawer" aria-labelledby="drawer-title">
{drawer_html}
</aside>
</div>
{_workbench_js()}
</body>
</html>"""


def _render_workbench_header(
    report: FullReport,
    drawer_items: tuple[DrawerItem, ...],
    meta: _ReportMeta,
    render_map: _ReportRenderMap,
    available_scopes: tuple[str, ...],
    active_scope: str,
) -> str:
    source_name = Path(report.source).name if report.source else "DART 원문"
    period = f'<span class="header-period">{_esc(meta.period)}</span>' if meta.period else ""
    scope_switch = ""
    if len(available_scopes) > 1:
        buttons = "".join(
            f'<button type="button" data-report-scope="{scope}" '
            f'aria-pressed="{str(scope == active_scope).lower()}">{_scope_label(scope)}</button>'
            for scope in available_scopes
        )
        scope_switch = (
            '<div class="report-scope-switch" aria-label="보고서 범위 선택">'
            f'{buttons}</div>'
        )

    scope_counts: list[str] = []
    count_scopes = available_scopes or (active_scope,)
    for scope in count_scopes:
        scoped_items = [
            item
            for item in drawer_items
            if _result_scope_slug(report, item.check, render_map, available_scopes) == scope
        ]
        counts = {
            "all": len(scoped_items),
            "matched": sum(
                _drawer_category_for_status(item.check.status) == "matched"
                for item in scoped_items
            ),
            "attention": sum(
                _drawer_category_for_status(item.check.status) == "attention"
                for item in scoped_items
            ),
            "source_review": sum(
                _drawer_category_for_status(item.check.status) == "source_review"
                for item in scoped_items
            ),
        }
        summary_buttons = "".join(
            f'<button class="status-summary status-{category}" type="button" '
            f'data-result-filter="{category}" '
            f'aria-pressed="{str(category == "all").lower()}">'
            f'{label} <strong>{counts[category]}</strong></button>'
            for category, label in (
                ("all", "전체"),
                ("matched", "일치"),
                ("attention", "확인 필요"),
                ("source_review", "원문 확인 필요"),
            )
        )
        hidden = "" if scope == active_scope else " hidden"
        scope_counts.append(
            f'<span class="scope-status-counts" data-scope-view="{_esc(scope)}" '
            f'data-scope-count="{_esc(scope)}"{hidden}>'
            f'{summary_buttons}'
            '</span>'
        )
    return f"""<header class="workbench-header">
  <div class="report-identity">
    <div class="report-identity-top"><div class="report-kicker">DART 검증보고서</div>{scope_switch}</div>
    <div class="report-title-row">
      <h1>{_esc(meta.company)}</h1>
      {period}
    </div>
    <div class="report-source">{_esc(source_name)}</div>
  </div>
  <div class="report-actions" aria-label="검토 현황">
    {''.join(scope_counts)}
    <button class="export-button" type="button" data-print-report>보고서 내보내기</button>
  </div>
</header>"""


def _render_workbench_sidebar(
    report: FullReport,
    results: list[CheckResult],
    render_map: _ReportRenderMap,
) -> tuple[str, str]:
    available_scopes = _available_report_scopes(report)
    active_scope = _default_report_scope(available_scopes)
    statuses: dict[str, list[str]] = {}
    for result in results:
        attached: set[str] = set()
        for evidence in result.evidence:
            parsed = _parse_source(evidence.source)
            if parsed is None:
                continue
            panel_id = _source_panel_id_for_parsed(parsed, render_map)
            if panel_id and panel_id not in attached:
                statuses.setdefault(panel_id, []).append(result.status)
                attached.add(panel_id)

    panel_ids: list[str] = []

    def item(panel_id: str, label: str, scope: str) -> str:
        panel_ids.append(panel_id)
        normalized_scope = _scope_slug(scope) or active_scope
        active = not any(
            entry_scope == active_scope
            for _entry_panel, entry_scope in rendered_items
        ) and normalized_scope == active_scope
        rendered_items.append((panel_id, normalized_scope))
        active_class = " active" if active else ""
        current = ' aria-current="page"' if active else ""
        hidden = "" if normalized_scope == active_scope else " hidden"
        return (
            f'<button class="source-nav-item{active_class}" type="button" '
            f'title="{_esc(label)}" aria-label="{_esc(label)}" '
            f'data-source-panel="{_esc(panel_id)}" data-scope-view="{_esc(normalized_scope)}"'
            f'{current}{hidden}>'
            f'<span>{_esc(label)}</span>{_workbench_nav_badge(statuses.get(panel_id, []))}'
            f'</button>'
        )

    rendered_items: list[tuple[str, str]] = []
    statement_items = "".join(
        item(
            _statement_panel_id(render_map, section),
            _statement_nav_label(section, kind, label, render_map),
            section.scope,
        )
        for section, kind, label in _rendered_statement_sections(report)
    )
    note_items = "".join(
        item(
            _note_panel_id(render_map, section),
            _note_nav_label(section, render_map),
            section.scope,
        )
        for section in report.notes
    )
    empty_statements = (
        "" if statement_items else '<div class="source-nav-empty">표시할 재무제표가 없습니다.</div>'
    )
    empty_notes = "" if note_items else '<div class="source-nav-empty">표시할 주석이 없습니다.</div>'
    return (
        f"""<div class="source-nav-brand">원문 검토</div>
<div class="source-nav-group">
  <div class="source-nav-heading">재무제표 본문</div>
  {statement_items}{empty_statements}
</div>
<div class="source-nav-group">
  <div class="source-nav-heading">각 주석</div>
  {note_items}{empty_notes}
</div>""",
        next(
            (panel_id for panel_id, scope in rendered_items if scope == active_scope),
            panel_ids[0] if panel_ids else "",
        ),
    )


def _workbench_nav_badge(statuses: list[str]) -> str:
    gaps = statuses.count(UNEXPLAINED_GAP)
    uncertain = statuses.count(PARSE_UNCERTAIN)
    explained = statuses.count(EXPLAINABLE_GAP)
    if gaps:
        return f'<span class="nav-state nav-state-gap">확인 {gaps}</span>'
    if uncertain:
        return f'<span class="nav-state nav-state-uncertain">원문 {uncertain}</span>'
    if explained:
        return '<span class="nav-state nav-state-explained">설명됨</span>'
    if statuses and all(status == MATCHED for status in statuses):
        return '<span class="nav-state nav-state-matched">완료</span>'
    return ""


def _render_workbench_source_panels(
    report: FullReport,
    cell_annotations: tuple[CellAnnotation, ...],
    drawer_items: tuple[DrawerItem, ...],
    render_map: _ReportRenderMap,
    *,
    first_panel_id: str,
) -> str:
    panels: list[str] = []
    narrative = build_narrative_evidence(report)
    for section, kind, label in _rendered_statement_sections(report):
        panel_id = _statement_panel_id(render_map, section)
        panels.append(
            _render_workbench_source_panel(
                section,
                panel_id,
                _statement_nav_label(section, kind, label, render_map),
                cell_annotations,
                drawer_items,
                hidden=panel_id != first_panel_id,
                scope=_scope_slug(section.scope) or _default_report_scope(_available_report_scopes(report)),
                is_statement=True,
                narrative=narrative,
                report=report,
                render_map=render_map,
            )
        )
    for section in report.notes:
        panel_id = _note_panel_id(render_map, section)
        title = f"{section.note_no}. {section.title}" if section.note_no else section.title
        panels.append(
            _render_workbench_source_panel(
                section,
                panel_id,
                title,
                cell_annotations,
                drawer_items,
                hidden=panel_id != first_panel_id,
                scope=_scope_slug(section.scope) or _default_report_scope(_available_report_scopes(report)),
                is_statement=False,
                narrative=narrative,
                report=report,
                render_map=render_map,
            )
        )
    if panels:
        return "\n".join(panels)
    return (
        '<section class="source-panel source-panel-empty">'
        '<h2>DART 원문</h2><p>표시할 재무제표 또는 주석을 찾지 못했습니다.</p></section>'
    )


def _render_workbench_source_panel(
    section: ReportSection,
    panel_id: str,
    title: str,
    cell_annotations: tuple[CellAnnotation, ...],
    drawer_items: tuple[DrawerItem, ...],
    *,
    hidden: bool,
    scope: str,
    is_statement: bool,
    narrative: NarrativeEvidenceDataset,
    report: FullReport,
    render_map: _ReportRenderMap,
) -> str:
    hidden_attr = " hidden" if hidden else ""
    blocks: list[str] = []
    for block_index, block in enumerate(section.blocks):
        block_source = _narrative_block_source_key(section, block_index)
        if block.table is not None:
            caption = block.table.heading or title
            page_label = _source_page_label(block.table.location)
            page_html = (
                f' · <span class="source-page-label">{_esc(page_label)}</span>'
                if page_label
                else ""
            )
            blocks.append(
                f'<section class="source-table-block" data-table="{block.table.index}" '
                f'data-source-block="{_esc(block_source)}">'
                f'<div class="source-table-caption">{_esc(caption)}{page_html}'
                f'{_table_level_drawer_badge(block.table, drawer_items)}</div>'
                f'{_render_source_table(block.table, cell_annotations, drawer_items, is_statement=is_statement)}'
                f'</section>'
            )
        elif block.text.strip():
            blocks.extend(
                _render_narrative_block(
                    section,
                    block_index,
                    block,
                    narrative,
                    report,
                    render_map,
                )
            )
    content = "".join(blocks) or '<p class="source-empty">표시할 원문 내용이 없습니다.</p>'
    validation_summary = _section_validation_summary(
        section,
        cell_annotations,
        drawer_items,
    )
    return f"""<section class="source-panel" id="{_esc(panel_id)}" data-scope-view="{_esc(scope)}"{hidden_attr}>
  <div class="source-panel-heading">
    <div class="source-panel-kicker">원문</div>
    <h2 tabindex="-1">{_esc(title)}</h2>
    {validation_summary}
  </div>
  {content}
</section>"""


def _narrative_block_source_key(section: ReportSection, block_index: int) -> str:
    scope = section.scope or "unknown"
    actual_index = section.blocks[block_index].location.block_index
    return f"{section.section_id}@{scope}/block:{actual_index}"


def _render_narrative_block(
    section: ReportSection,
    block_index: int,
    block,
    narrative: NarrativeEvidenceDataset,
    report: FullReport,
    render_map: _ReportRenderMap,
) -> list[str]:
    scope = section.scope or "unknown"
    actual_index = block.location.block_index
    page_label = _source_page_label(block.location)
    page_html = (
        f'<span class="source-page-label">{_esc(page_label)}</span>'
        if page_label
        else ""
    )
    segment_items = [
        segment
        for segment in narrative.segments
        if segment.source.section_id == section.section_id
        and segment.source.scope == scope
        and segment.source.block_index == actual_index
    ]
    if not segment_items:
        source_key = _narrative_block_source_key(section, block_index)
        return [
            f'<p class="source-text" data-source-block="{_esc(source_key)}">'
            f'{_esc(block.text)}</p>'
        ]
    attachment_sources = {
        attachment.segment_source for attachment in narrative.attachments
    }
    references_by_source: dict[str, list[NarrativeNoteReference]] = {}
    for reference in narrative.note_references:
        references_by_source.setdefault(reference.source.source_key, []).append(reference)
    rendered: list[str] = []
    for segment in segment_items:
        references = references_by_source.get(segment.source.source_key, [])
        if segment.source.source_key not in attachment_sources and not references:
            rendered.append(
                f'<p class="source-text" data-source-block="{_esc(segment.source.source_key)}">'
                f'{_esc(segment.text)}</p>'
            )
            continue
        marker = (
            f'<span class="source-narrative-marker">{_esc(segment.marker)}</span>'
            if segment.marker
            else ""
        )
        reference_buttons = "".join(
            _render_narrative_reference_button(report, reference, render_map)
            for reference in references
        )
        actions = (
            f'<div class="source-narrative-actions">{reference_buttons}</div>'
            if reference_buttons
            else ""
        )
        rendered.append(
            f'<aside class="source-narrative" '
            f'data-source-block="{_esc(segment.source.source_key)}">'
            '<div class="source-narrative-head">'
            f'{marker}<span>표 설명·말 주기</span>{page_html}</div>'
            f'<p>{_esc(segment.text)}</p>{actions}</aside>'
        )
    return rendered


def _render_narrative_reference_button(
    report: FullReport,
    reference: NarrativeNoteReference,
    render_map: _ReportRenderMap,
) -> str:
    primary = reference.note_no.split("-", 1)[0].split(".", 1)[0]
    targets = [
        note
        for note in report.notes
        if note.note_no.split("-", 1)[0].split(".", 1)[0] == primary
        and (note.scope or "unknown") == reference.source.scope
    ]
    if not targets or not targets[0].blocks:
        return ""
    target = targets[0]
    panel_id = _note_panel_id(render_map, target)
    block_index = target.blocks[0].location.block_index
    block_source = (
        f"{target.section_id}@{target.scope or 'unknown'}/block:{block_index}"
    )
    return (
        '<button class="source-narrative-reference" type="button" '
        'data-source-jump="narrative-reference" '
        f'data-jump-panel="{_esc(panel_id)}" data-jump-block="{_esc(block_source)}" '
        'data-jump-cell="" data-jump-row="">'
        f'참조 주석 { _esc(reference.note_no) }</button>'
    )


def _section_validation_summary(
    section: ReportSection,
    cell_annotations: tuple[CellAnnotation, ...],
    drawer_items: tuple[DrawerItem, ...],
) -> str:
    table_indexes = {
        block.table.index for block in section.blocks if block.table is not None
    }
    checks: dict[str, CheckResult] = {}
    cell_check_ids: set[str] = set()
    for annotation in cell_annotations:
        if annotation.target.table_index not in table_indexes:
            continue
        for check in annotation.checks:
            checks.setdefault(check.check_id, check)
            cell_check_ids.add(check.check_id)
    for item in drawer_items:
        if any(anchor.table_index in table_indexes for anchor in item.anchors):
            checks.setdefault(item.check.check_id, item.check)
    if not checks:
        return ""

    counts: dict[str, int] = {}
    for check_id, check in checks.items():
        group = (
            "합계 검증"
            if check_id in cell_check_ids
            else CHECK_GROUPS.get(check.check_type, "기타 검증")
        )
        counts[group] = counts.get(group, 0) + 1
    ordered_groups = [
        group for group in CHECK_GROUP_ORDER if group in counts
    ] + sorted(group for group in counts if group not in CHECK_GROUP_ORDER)
    chips = "".join(
        f'<span class="validation-summary-chip" data-validation-group="{_esc(group)}">'
        f'{_esc(group)} <strong>{counts[group]}</strong></span>'
        for group in ordered_groups
    )
    return f'<div class="validation-summary" aria-label="이 원문의 검증 내용">{chips}</div>'


def _table_level_drawer_badge(
    table: ReportTable,
    drawer_items: tuple[DrawerItem, ...],
) -> str:
    indexes = [
        index
        for index, item in enumerate(drawer_items)
        if any(
            anchor.table_index == table.index and not anchor.is_exact_cell
            for anchor in item.anchors
        )
    ]
    if not indexes:
        return ""
    return (
        f'<button class="table-drawer-badge" type="button" '
        f'data-open-drawer="{indexes[0]}">검증 결과 {len(indexes)}</button>'
    )


def _drawer_category_for_status(status: str) -> str:
    if status == MATCHED:
        return "matched"
    if status in {PARSE_UNCERTAIN, NOT_TESTED}:
        return "source_review"
    return "attention"


_CASHFLOW_DRAWER_TYPES = {
    "cashflow_reconciliation",
    "cfs_note_match",
    "asset_note_bridge_check",
}


def _drawer_subject_label(check: CheckResult) -> str:
    preferred_roles = ("statement_amount", "cashflow_amount")
    for role in preferred_roles:
        evidence = _first_evidence_for_role(check, role)
        if evidence is not None and evidence.label.strip():
            display = evidence_display_label(evidence.label).strip()
            return re.sub(r"\s+(?:주석 금액 )?대사$", "", display)
    title = check_display_title(check)
    return re.sub(r"\s+(?:주석 금액 )?대사$", "", title).strip() or "검증 결과"


def _drawer_note_number(check: CheckResult) -> str:
    for evidence in check.evidence:
        _context, source_body = _split_source_context(evidence.source)
        parsed = source_cell_ref(source_body)
        if parsed is not None and parsed.scope == "note":
            return parsed.name
    return check.note_no


def _drawer_amount_labels(check: CheckResult) -> tuple[str, str]:
    note_no = _drawer_note_number(check)
    note_label = f"주석 {note_no}" if note_no else "주석"
    if check.check_type in _CASHFLOW_DRAWER_TYPES:
        return "현금흐름표 금액", f"{note_label} 변동금액"
    source_bodies = [
        _split_source_context(source)[1]
        for source in _drawer_evidence_sources(check)
    ]
    if any(source.startswith("statement:") for source in source_bodies) and any(
        source.startswith("note:") for source in source_bodies
    ):
        return "재무제표 금액", f"{note_label} 금액"
    return "기준 금액", "비교 금액"


def _clean_display_location(value: str) -> str:
    parts = [
        re.sub(r"\s+", " ", part).strip(" ·|")
        for part in value.split("·")
    ]
    return " · ".join(dict.fromkeys(part for part in parts if part and part != "0"))


def _drawer_note_sources(check: CheckResult) -> tuple[str, ...]:
    sources: list[str] = []
    for source in _drawer_evidence_sources(check):
        _context, source_body = _split_source_context(source)
        if source_body.startswith("note:") or _parse_narrative_source(source_body) is not None:
            sources.append(source)
    return tuple(sources)


def _render_workbench_drawer(
    report: FullReport,
    drawer_items: tuple[DrawerItem, ...],
    render_map: _ReportRenderMap,
) -> str:
    cards = "".join(
        _render_workbench_drawer_item(report, item, index, render_map)
        for index, item in enumerate(drawer_items)
    )
    empty = (
        '<div class="drawer-empty" data-drawer-empty>'
        '<strong>대사 결과</strong><p>중앙 표의 대사 표시를 선택하면 비교 결과가 여기에 나타납니다.</p>'
        '</div>'
    )
    if not drawer_items:
        empty = (
            '<div class="drawer-empty" data-drawer-empty>'
            '<strong>대사 결과 없음</strong><p>이 보고서에서 표 사이 대사 결과가 생성되지 않았습니다.</p>'
            '</div>'
        )
    return f"""<div class="drawer-header">
  <div>
    <div class="drawer-kicker">비교 검토</div>
    <h2 id="drawer-title" tabindex="-1">대사 결과</h2>
  </div>
  <button class="drawer-close" type="button" data-close-drawer>닫기</button>
</div>
<div class="drawer-filters" aria-label="대사 결과 필터">
  <button type="button" data-result-filter="all" aria-pressed="true">전체</button>
  <button type="button" data-result-filter="matched" aria-pressed="false">일치</button>
  <button type="button" data-result-filter="attention" aria-pressed="false">확인 필요</button>
  <button type="button" data-result-filter="source_review" aria-pressed="false">원문 확인 필요</button>
</div>
<div class="drawer-navigation" aria-label="검증 결과 이동">
  <button type="button" data-drawer-prev aria-label="이전 검증 결과">이전</button>
  <span data-drawer-position aria-live="polite">결과를 선택하세요</span>
  <button type="button" data-drawer-next aria-label="다음 검증 결과">다음</button>
</div>
{empty}{cards}"""


def _render_workbench_drawer_item(
    report: FullReport,
    item: DrawerItem,
    drawer_index: int,
    render_map: _ReportRenderMap,
) -> str:
    check = item.check
    if check.check_type == "statement_note_row_reconciliation":
        return _render_statement_note_drawer_item(
            report,
            check,
            drawer_index,
            render_map,
        )
    if check.check_type == "note_reference_check" and _first_evidence_for_role(
        check, "narrative_reference"
    ) is not None:
        return _render_note_reference_drawer_item(
            report,
            check,
            drawer_index,
            render_map,
        )
    category = _drawer_category_for_status(check.status)
    scope = _result_scope_slug(
        report,
        check,
        render_map,
        _available_report_scopes(report),
    )
    subject = _drawer_subject_label(check)
    expected_label, actual_label = _drawer_amount_labels(check)
    note_sources = _drawer_note_sources(check)
    location_sources = note_sources or _drawer_evidence_sources(check)
    location_heading = (
        "주석 위치"
        if note_sources or re.search(r"\d", check.note_no or "")
        else "확인 위치"
    )
    display_locations = [
        _clean_display_location(_humanize_source(report, source)) or "주석 위치"
        for source in location_sources
    ]
    duplicate_counts = {
        label: display_locations.count(label) for label in display_locations
    }
    duplicate_positions: dict[str, int] = {}
    rendered_locations: list[str] = []
    for source_index, (source, display_location) in enumerate(
        zip(location_sources, display_locations, strict=True)
    ):
        label_override = None
        if duplicate_counts[display_location] > 1:
            position = duplicate_positions.get(display_location, 0) + 1
            duplicate_positions[display_location] = position
            ordinal = {1: "첫 번째 표", 2: "두 번째 표"}.get(
                position, f"{position}번째 표"
            )
            label_override = f"{display_location} ({ordinal})"
        rendered_locations.append(
            _render_drawer_evidence_location(
                report,
                check,
                source,
                source_index,
                render_map,
                label_override=label_override,
            )
        )
    locations = "".join(rendered_locations)
    if not locations:
        locations = (
            '<span class="drawer-source-unavailable">주석 위치 확인 필요</span>'
            if location_heading == "주석 위치"
            else '<span class="drawer-source-unavailable">확인 위치를 자동으로 찾지 못했습니다.</span>'
        )
    return f"""<article class="drawer-item" data-drawer-item="{drawer_index}" data-drawer-category="{category}" data-drawer-status="{_esc(check.status)}" data-scope-view="{_esc(scope)}" hidden>
  <div class="drawer-group">{_esc(CHECK_GROUPS.get(check.check_type, "검증 결과"))}</div>
  <div class="drawer-result-head">
    <h3>{_esc(subject)}</h3>
    <span class="drawer-status status-{_esc(check.status)}">{_esc(check_status_compact_label(check.status))}</span>
  </div>
  <section class="drawer-section drawer-result-copy"><h4>결과</h4><p>{_esc(check_display_reason(check))}</p></section>
  <dl class="drawer-amounts">
    <div><dt>{_esc(expected_label)}</dt><dd>{_amount_text(check.expected)}</dd></div>
    <div><dt>{_esc(actual_label)}</dt><dd>{_amount_text(check.actual)}</dd></div>
    <div><dt>차이</dt><dd>{_amount_text(check.difference)}</dd></div>
  </dl>
  <section class="drawer-section"><h4>{_esc(location_heading)}</h4><div class="drawer-sources">{locations}</div></section>
  <section class="drawer-section drawer-next"><h4>필요한 행동</h4><p>{_esc(_next_action_text(check))}</p></section>
</article>"""


def _render_note_reference_drawer_item(
    report: FullReport,
    check: CheckResult,
    drawer_index: int,
    render_map: _ReportRenderMap,
) -> str:
    category = _drawer_category_for_status(check.status)
    scope = _result_scope_slug(
        report,
        check,
        render_map,
        _available_report_scopes(report),
    )
    reference = _first_evidence_for_role(check, "narrative_reference")
    sentence = reference.label if reference is not None else check_display_reason(check)
    location_items = [
        evidence
        for evidence in check.evidence
        if evidence.role in {"narrative_reference", "referenced_note"}
    ]
    locations = "".join(
        _render_drawer_evidence_location(
            report,
            check,
            evidence.source,
            source_index,
            render_map,
        )
        for source_index, evidence in enumerate(location_items)
    )
    if not locations:
        locations = '<span class="drawer-source-unavailable">주석 위치 확인 필요</span>'
    next_action = ""
    if check.status != MATCHED:
        if "내용 비어" in check.reason:
            action = f"참조된 주석 {check.note_no}에 실제 공시 내용이 있는지 확인하세요."
        else:
            action = (
                f"참조된 주석 {check.note_no}가 보고서에 존재하는지 확인하고, "
                "번호가 잘못되었다면 말 주기 문장을 수정하세요."
            )
        next_action = (
            '<section class="drawer-section drawer-next"><h4>후속작업</h4>'
            f'<p>{_esc(action)}</p></section>'
        )
    return f"""<article class="drawer-item drawer-item-note-reference" data-drawer-item="{drawer_index}" data-drawer-category="{category}" data-drawer-status="{_esc(check.status)}" data-scope-view="{_esc(scope)}" hidden>
  <div class="drawer-group">주석 간 대사</div>
  <div class="drawer-result-head">
    <h3>주석 {_esc(check.note_no)} 참조</h3>
    <span class="drawer-status status-{_esc(check.status)}">{_esc(check_status_compact_label(check.status))}</span>
  </div>
  <section class="drawer-section drawer-reference-sentence"><h4>참조 문장</h4><p>{_esc(sentence)}</p></section>
  {next_action}
  <section class="drawer-section"><h4>주석 위치</h4><div class="drawer-sources">{locations}</div></section>
</article>"""


def _render_statement_note_drawer_item(
    report: FullReport,
    check: CheckResult,
    drawer_index: int,
    render_map: _ReportRenderMap,
) -> str:
    category = _drawer_category_for_status(check.status)
    scope = _result_scope_slug(
        report,
        check,
        render_map,
        _available_report_scopes(report),
    )
    statement = _first_evidence_for_role(check, "statement_amount")
    note_amounts = _evidence_for_roles(check, {"note_amount", "candidate_note_amount"})
    displayed_refs = _evidence_for_roles(check, {"displayed_note_reference"})
    missing_refs = _evidence_for_roles(check, {"missing_note_reference"})
    statement_label = statement.label if statement is not None else check_display_title(check)
    note_locations = _render_statement_note_locations(
        report,
        check,
        note_amounts,
        missing_refs,
        render_map,
    )
    displayed = ", ".join(
        _note_number_label(evidence.label) for evidence in displayed_refs
    ) or "표시 주석 확인 필요"
    reconciled = ", ".join(
        _note_number_label(evidence.label) for evidence in note_amounts
    ) or "금액 확인 필요"
    missing = ", ".join(
        _note_number_label(evidence.label) for evidence in missing_refs
    ) or "없음"
    references_complete = bool(displayed_refs) and not missing_refs
    completeness = "완전" if references_complete else "확인 필요"
    completeness_class = "" if references_complete else " drawer-note-role-attention"
    scope_label = {"consolidated": "연결", "separate": "별도"}.get(
        check.consolidation_basis,
        "",
    )
    period_label = "당기" if check.report_period == "current" else ""
    meta = " · ".join(value for value in (scope_label, period_label, displayed) if value)
    actual_text = _statement_note_actual_text(check)
    difference_text = _amount_text(check.difference) if check.difference is not None else "비교 후 산정"
    result_label = _statement_note_result_label(check, missing_refs)
    note_amount_label = (
        f"{_note_number_label(note_amounts[0].label)} 금액"
        if note_amounts
        else "주석 금액"
    )
    next_action_text = (
        "추가로 확인할 사항이 없습니다."
        if check.status == MATCHED and not missing_refs
        else _statement_note_next_action_text(check)
    )
    next_action = (
        '<section class="drawer-section drawer-next"><h4>후속작업</h4>'
        f'<p>{_esc(next_action_text)}</p></section>'
    )
    return f"""<article class="drawer-item drawer-item-statement-note" data-drawer-item="{drawer_index}" data-drawer-category="{category}" data-drawer-status="{_esc(check.status)}" data-scope-view="{_esc(scope)}" hidden>
  <div class="drawer-group">재무제표-주석 대사</div>
  <div class="drawer-result-head">
    <div><h3>{_esc(statement_label)}</h3><p class="drawer-result-meta">{_esc(meta)}</p></div>
    <span class="drawer-status status-{_esc(check.status)}">{_esc(result_label)}</span>
  </div>
  <dl class="drawer-amounts">
    <div><dt>재무제표 금액</dt><dd>{_amount_text(check.expected)}</dd></div>
    <div><dt>{_esc(note_amount_label)}</dt><dd>{_esc(actual_text)}</dd></div>
    <div><dt>차이</dt><dd>{_esc(difference_text)}</dd></div>
  </dl>
  <section class="drawer-section"><div class="drawer-completeness-head"><h4>주석번호 완전성</h4><strong>{_esc(completeness)}</strong></div>
    <div class="drawer-note-roles">
      <div class="drawer-note-role"><span>표시됨</span><strong>{_esc(displayed)}</strong></div>
      <div class="drawer-note-role"><span>금액 대사</span><strong>{_esc(reconciled)}</strong></div>
      <div class="drawer-note-role{completeness_class}"><span>누락</span><strong>{_esc(missing)}</strong></div>
    </div>
  </section>
  {next_action}
  {note_locations}
</article>"""


def _note_number_label(label: str) -> str:
    match = re.search(r"주석\s+([0-9]+(?:[-.][0-9]+)*)", label or "")
    return f"주석 {match.group(1)}" if match is not None else label


def _first_evidence_for_role(check: CheckResult, role: str):
    return next((evidence for evidence in check.evidence if evidence.role == role), None)


def _evidence_for_roles(check: CheckResult, roles: set[str]):
    return [evidence for evidence in check.evidence if evidence.role in roles]


def _render_statement_note_locations(
    report: FullReport,
    check: CheckResult,
    note_amounts: list,
    missing_refs: list,
    render_map: _ReportRenderMap,
) -> str:
    locations: list[str] = []
    seen: set[tuple[str, str]] = set()
    for role_label, css_class, evidence_items in (
        ("실재성", "drawer-note-location-existence", note_amounts),
        ("완전성 누락", "drawer-note-location-completeness", missing_refs),
    ):
        for evidence in evidence_items:
            key = (role_label, evidence.source)
            if key in seen:
                continue
            seen.add(key)
            locations.append(
                _render_named_evidence_source(
                    report,
                    check,
                    evidence,
                    len(locations),
                    render_map,
                    label=f"{role_label} · {_note_number_label(evidence.label)}",
                    css_class=css_class,
                )
            )
    if not locations:
        return ""
    return (
        '<section class="drawer-section drawer-note-locations">'
        '<h4>주석 위치</h4><div class="drawer-sources">'
        + "".join(locations)
        + "</div></section>"
    )


def _render_named_evidence_source(
    report: FullReport,
    check: CheckResult,
    evidence,
    source_index: int,
    render_map: _ReportRenderMap,
    *,
    label: str,
    css_class: str = "",
) -> str:
    if evidence is None:
        return ""
    parsed = source_cell_ref(evidence.source)
    if parsed is None:
        return f'<span class="drawer-source-context">{_esc(label)} · 주석 위치 확인 필요</span>'
    return _render_drawer_source_button(
        report,
        parsed,
        source_index,
        render_map,
        label=label,
        css_class=css_class,
    )


def _statement_note_actual_text(check: CheckResult) -> str:
    if check.actual is not None:
        return _amount_text(check.actual)
    if check.parse_uncertain_reason == "AMBIGUOUS_MULTIPLE":
        return "금액 후보 확인 필요"
    if check.parse_uncertain_reason == "TABLE_NOT_FOUND":
        return "주석 원문 확인 필요"
    return "주석 금액 확인 필요"


def _statement_note_result_label(check: CheckResult, missing_refs: list) -> str:
    if check.actual is None or check.difference is None:
        amount_label = "금액 확인 필요"
    elif abs(check.difference) <= check.tolerance:
        amount_label = "금액 일치"
    else:
        amount_label = "금액 차이 확인 필요"
    reference_label = "주석번호 확인 필요" if missing_refs else "주석번호 확인 완료"
    return f"{amount_label} · {reference_label}"


def _statement_note_next_action_text(check: CheckResult) -> str:
    if check.parse_uncertain_reason == "MISSING_DISPLAYED_NOTE_REFERENCE":
        return "누락 후보 주석번호를 재무제표 계정 옆에 추가해야 하는지 확인하세요."
    if check.status == MATCHED:
        return "추가 조치가 필요하지 않습니다."
    if check.parse_uncertain_reason == "AMBIGUOUS_MULTIPLE":
        return "표시된 후보 금액의 기간과 행 의미를 확인해 대사 대상을 확정하세요."
    if check.parse_uncertain_reason == "TABLE_NOT_FOUND":
        return "재무제표 본문의 주석번호와 실제 주석번호가 같은지 확인하세요."
    if check.parse_uncertain_reason == "LABEL_NOT_FOUND":
        return "지정된 주석에서 해당 계정의 합계 또는 기말금액을 확인하세요."
    if check.status == UNEXPLAINED_GAP:
        return "재무제표와 주석의 금액·기간·공시 범위를 확인하고 차이 원인을 기록하세요."
    return "표시된 주석의 원문을 확인해 비교 대상을 확정하세요."


def _drawer_evidence_sources(check: CheckResult) -> tuple[str, ...]:
    sources: list[str] = []
    for evidence in check.evidence:
        for source in evidence.source.split(";"):
            normalized = source.strip()
            if normalized and normalized not in sources:
                sources.append(normalized)
    return tuple(sources)


def _render_drawer_evidence_location(
    report: FullReport,
    check: CheckResult,
    source: str,
    source_index: int,
    render_map: _ReportRenderMap,
    *,
    label_override: str | None = None,
) -> str:
    context, source_body = _split_source_context(source)
    narrative_source = _parse_narrative_source(source_body)
    if narrative_source is not None:
        return _render_drawer_narrative_source_button(
            report,
            narrative_source,
            source_body,
            source_index,
            render_map,
        )
    human = (
        label_override
        or _clean_display_location(_humanize_source(report, source))
        or "주석 위치"
    )
    if context == "prior":
        return f'<span class="drawer-source-prior">{_esc(human)}</span>'
    if check.report_period == "prior":
        human = f"당기 보고서 {human}"
    parsed = source_cell_ref(source_body)
    if parsed is not None:
        return _render_drawer_source_button(
            report,
            parsed,
            source_index,
            render_map,
            label=human,
        )
    return f'<span class="drawer-source-context">{_esc(human)}</span>'


def _render_drawer_narrative_source_button(
    report: FullReport,
    source: _NarrativeSourceRef,
    source_key: str,
    source_index: int,
    render_map: _ReportRenderMap,
) -> str:
    panel_id = _narrative_panel_id(report, source, render_map)
    if not panel_id:
        return '<span class="drawer-source-unavailable">주석 위치 확인 필요</span>'
    label = (
        "말 주기 문장"
        if source.segment_index is not None
        else f"참조 주석 {source.name}"
    )
    section = _section_for_narrative_source(report, source)
    location = (
        next(
            (
                block.location
                for block in section.blocks
                if block.location.block_index == source.block_index
            ),
            None,
        )
        if section is not None
        else None
    )
    page_label = _source_page_label(location)
    if page_label:
        label = f"{label} · {page_label}"
    return (
        f'<button class="drawer-source" type="button" data-source-jump="{source_index}" '
        f'data-jump-panel="{_esc(panel_id)}" data-jump-block="{_esc(source_key)}" '
        f'data-jump-cell="" data-jump-row="">{_esc(label)}</button>'
    )


def _render_drawer_source_button(
    report: FullReport,
    anchor,
    anchor_index: int,
    render_map: _ReportRenderMap,
    *,
    label: str | None = None,
    css_class: str = "",
) -> str:
    parsed = (
        anchor.scope,
        anchor.name,
        anchor.table_index,
        anchor.row_index,
        anchor.column_index,
    )
    panel_id = _source_panel_id_for_parsed(parsed, render_map)
    source = f"{anchor.scope}:{anchor.name}/table:{anchor.table_index}"
    if anchor.row_index is not None:
        source += f"/row:{anchor.row_index}"
    if anchor.column_index is not None:
        source += f"/col:{anchor.column_index}"
    human = _clean_display_location(label or _humanize_source(report, source)) or "주석 위치"
    table = _source_table(report, anchor.scope, anchor.name, anchor.table_index)
    page_label = _source_page_label(table.location if table is not None else None)
    if page_label:
        human = f"{human} · {page_label}"
    if not panel_id or not _drawer_anchor_is_renderable(report, anchor):
        return (
            '<span class="drawer-source-unavailable">'
            f'위치 확인 필요 · {_esc(human)}</span>'
        )
    cell_key = (
        f"t{anchor.table_index}r{anchor.row_index}c{anchor.column_index}"
        if anchor.is_exact_cell
        else ""
    )
    row_key = (
        f"t{anchor.table_index}r{anchor.row_index}"
        if anchor.row_index is not None
        else ""
    )
    return (
        f'<button class="drawer-source{(" " + _esc(css_class)) if css_class else ""}" '
        f'type="button" data-source-jump="{anchor_index}" '
        f'data-jump-panel="{_esc(panel_id)}" data-jump-cell="{_esc(cell_key)}" '
        f'data-jump-row="{_esc(row_key)}">{_esc(human)}</button>'
    )


def _drawer_anchor_is_renderable(report: FullReport, anchor) -> bool:
    table = _source_table(report, anchor.scope, anchor.name, anchor.table_index)
    if table is None:
        return False
    if anchor.row_index is None:
        return True
    if anchor.row_index < 0 or anchor.row_index >= len(table.rows):
        return False
    if anchor.column_index is None:
        return True
    return 0 <= anchor.column_index < len(table.rows[anchor.row_index])


def _next_action_text(check: CheckResult) -> str:
    if check.status == UNEXPLAINED_GAP:
        return "양쪽 원문 금액과 공시 범위를 확인하고 차이 원인을 기록하세요."
    if check.status == PARSE_UNCERTAIN:
        return "원문 표의 머리글과 병합 구조를 확인해 비교 대상을 확정하세요."
    if check.status == EXPLAINABLE_GAP:
        return "표시된 설명 근거가 현재 보고기간에도 유효한지 확인하세요."
    return "추가로 확인할 사항이 없습니다."


def _build_render_map(report: FullReport) -> _ReportRenderMap:
    tables_by_index: dict[int, list[_RenderedTable]] = {}
    statement_entries = _rendered_statement_sections(report)
    statement_panel_ids = _build_statement_panel_ids(statement_entries)
    unique_statement_panel_keys = _unique_statement_panel_keys(statement_entries, statement_panel_ids)
    note_panel_ids = _build_note_panel_ids(report.notes)
    unique_note_panel_keys = _unique_note_panel_keys(report.notes, note_panel_ids)

    for section, kind, _label in statement_entries:
        panel_id = statement_panel_ids[id(section)]
        for table in _section_tables(section):
            entry = _RenderedTable(section, table, panel_id, panel_id)
            tables_by_index.setdefault(table.index, []).append(entry)

    for section in report.notes:
        panel_id = note_panel_ids[id(section)]
        for table in _section_tables(section):
            entry = _RenderedTable(section, table, panel_id, panel_id)
            tables_by_index.setdefault(table.index, []).append(entry)

    return _ReportRenderMap(
        tables_by_index={idx: tuple(entries) for idx, entries in tables_by_index.items()},
        statement_panel_ids=statement_panel_ids,
        unique_statement_panel_keys=unique_statement_panel_keys,
        note_panel_ids=note_panel_ids,
        unique_note_panel_keys=unique_note_panel_keys,
    )


def _rendered_statement_sections(report: FullReport) -> list[tuple[ReportSection, str, str]]:
    entries: list[tuple[int, int, ReportSection, str, str]] = []
    for original_index, section in enumerate(report.statements):
        kind = _statement_kind_for_section(section)
        if not kind:
            continue
        order = _STATEMENT_KIND_ORDER.get(kind, len(_STATEMENT_KIND_ORDER))
        entries.append((order, original_index, section, kind, _statement_label(kind, section)))
    return [
        (section, kind, label)
        for _order, _original_index, section, kind, label in sorted(entries, key=lambda item: (item[0], item[1]))
    ]


def _build_statement_panel_ids(
    statement_entries: list[tuple[ReportSection, str, str]],
) -> dict[int, str]:
    counts: dict[str, int] = {}
    occurrences: dict[str, int] = {}
    used: set[str] = set()
    for _section, kind, _label in statement_entries:
        counts[kind] = counts.get(kind, 0) + 1

    panel_ids: dict[int, str] = {}
    for section, kind, _label in statement_entries:
        occurrences[kind] = occurrences.get(kind, 0) + 1
        occurrence = occurrences[kind]
        base = f"panel-{kind}"
        if counts[kind] == 1:
            candidate = base
        else:
            scope_slug = _scope_slug(section.scope)
            candidate = f"{base}-{scope_slug}" if scope_slug else (
                base if occurrence == 1 else f"{base}-{occurrence}"
            )
        if candidate in used:
            suffix_base = candidate
            candidate = f"{suffix_base}-{occurrence}"
            while candidate in used:
                occurrence += 1
                candidate = f"{suffix_base}-{occurrence}"
        used.add(candidate)
        panel_ids[id(section)] = candidate
    return panel_ids


def _unique_statement_panel_keys(
    statement_entries: list[tuple[ReportSection, str, str]],
    panel_ids: dict[int, str],
) -> dict[str, str]:
    counts: dict[str, int] = {}
    for _section, kind, _label in statement_entries:
        counts[kind] = counts.get(kind, 0) + 1
    return {
        kind: panel_ids[id(section)]
        for section, kind, _label in statement_entries
        if counts[kind] == 1
    }


def _statement_panel_id(render_map: _ReportRenderMap, section: ReportSection) -> str:
    return render_map.statement_panel_ids[id(section)]


def _statement_nav_label(
    section: ReportSection,
    kind: str,
    label: str,
    render_map: _ReportRenderMap,
) -> str:
    duplicated = kind not in render_map.unique_statement_panel_keys
    if duplicated:
        scope_label = _scope_label(section.scope)
        suffix = f" ({scope_label})" if scope_label else ""
        return f"{label}{suffix}"
    return label


def _build_note_panel_ids(sections: list[ReportSection]) -> dict[int, str]:
    counts: dict[str, int] = {}
    occurrences: dict[str, int] = {}
    used: set[str] = set()
    for section in sections:
        counts[_note_identity(section)] = counts.get(_note_identity(section), 0) + 1

    panel_ids: dict[int, str] = {}
    for section in sections:
        note_key = _note_identity(section)
        occurrences[note_key] = occurrences.get(note_key, 0) + 1
        occurrence = occurrences[note_key]
        base = f"panel-note-{_safe_id(note_key)}"
        if counts[note_key] == 1:
            candidate = base
        else:
            scope_slug = _scope_slug(section.scope)
            candidate = f"{base}-{scope_slug}" if scope_slug else (
                base if occurrence == 1 else f"{base}-{occurrence}"
            )
        if candidate in used:
            suffix_base = candidate
            candidate = f"{suffix_base}-{occurrence}"
            while candidate in used:
                occurrence += 1
                candidate = f"{suffix_base}-{occurrence}"
        used.add(candidate)
        panel_ids[id(section)] = candidate
    return panel_ids


def _unique_note_panel_keys(
    sections: list[ReportSection],
    panel_ids: dict[int, str],
) -> dict[str, str]:
    counts: dict[str, int] = {}
    for section in sections:
        counts[_note_identity(section)] = counts.get(_note_identity(section), 0) + 1
    return {
        f"note:{_note_identity(section)}": panel_ids[id(section)]
        for section in sections
        if counts[_note_identity(section)] == 1
    }


def _note_identity(section: ReportSection) -> str:
    return section.note_no or section.section_id


def _note_panel_id(render_map: _ReportRenderMap, section: ReportSection) -> str:
    return render_map.note_panel_ids[id(section)]


def _scope_slug(scope: str) -> str:
    normalized = (scope or "").strip().lower()
    if normalized in {"consolidated", "연결"}:
        return "consolidated"
    if normalized in {"separate", "별도"}:
        return "separate"
    return _safe_id(normalized) if normalized else ""


def _scope_label(scope: str) -> str:
    slug = _scope_slug(scope)
    if slug == "consolidated":
        return "연결"
    if slug == "separate":
        return "별도"
    return scope.strip()


def _available_report_scopes(report: FullReport) -> tuple[str, ...]:
    found = {
        _scope_slug(section.scope)
        for section in [*report.statements, *report.notes]
    }
    return tuple(
        scope for scope in ("consolidated", "separate") if scope in found
    )


def _default_report_scope(available_scopes: tuple[str, ...]) -> str:
    if "consolidated" in available_scopes:
        return "consolidated"
    if available_scopes:
        return available_scopes[0]
    return "all"


def _result_scope_slug(
    report: FullReport,
    result: CheckResult,
    render_map: _ReportRenderMap,
    available_scopes: tuple[str, ...] | None = None,
) -> str:
    explicit = _result_consolidation_scope_slug(result)
    if explicit in {"consolidated", "separate"}:
        return explicit

    inferred: list[str] = []
    for evidence in result.evidence:
        for source in evidence.source.split(";"):
            _context, source_body = _split_source_context(source.strip())
            parsed = _parse_source(source_body)
            if parsed is None:
                continue
            rendered = _rendered_table_for_source(parsed, render_map)
            if rendered is None:
                continue
            scope = _scope_slug(rendered.section.scope)
            if scope in {"consolidated", "separate"} and scope not in inferred:
                inferred.append(scope)
    if len(inferred) == 1:
        return inferred[0]

    scopes = available_scopes if available_scopes is not None else _available_report_scopes(report)
    if len(scopes) == 1:
        return scopes[0]
    return "all"


def _note_nav_label(section: ReportSection, render_map: _ReportRenderMap) -> str:
    note_key = _note_identity(section)
    duplicated = f"note:{note_key}" not in render_map.unique_note_panel_keys
    if duplicated:
        scope_label = _scope_label(section.scope)
        suffix = f" ({scope_label})" if scope_label else ""
        title = _without_scope_suffix(section.title, scope_label)
        return f"주석 {note_key}{suffix} {title}".strip()
    if section.note_no:
        return f"{section.note_no}. {section.title}"
    return section.title


def _without_scope_suffix(title: str, scope_label: str) -> str:
    if not scope_label:
        return title
    return re.sub(rf"\s*\({re.escape(scope_label)}\)\s*$", "", title).strip()


def _place_results(
    report: FullReport,
    results: list[CheckResult],
    render_map: _ReportRenderMap,
) -> dict[str, list[CheckResult]]:
    renderable_keys = _renderable_panel_keys(report, render_map)
    grouped: dict[str, list[CheckResult]] = {}
    for result in results:
        key = _result_panel_key(report, result, render_map)
        if key not in renderable_keys:
            key = "other"
        grouped.setdefault(key, []).append(result)
    return grouped


def _result_panel_key(
    report: FullReport,
    result: CheckResult,
    render_map: _ReportRenderMap,
) -> str:
    if result.evidence:
        narrative_source = _parse_narrative_source(result.evidence[0].source)
        if narrative_source is not None:
            panel_id = _narrative_panel_id(report, narrative_source, render_map)
            if panel_id:
                return panel_id
        parsed = _parse_source(result.evidence[0].source)
        if parsed is not None:
            rendered = _rendered_table_for_source(parsed, render_map)
            if rendered is not None:
                return rendered.panel_key
    hinted_panel = _panel_key_from_check_id_table_hint(result, render_map)
    if hinted_panel:
        return hinted_panel
    note_ref_panel = _note_reference_panel_key(report, result, render_map)
    if note_ref_panel:
        return note_ref_panel
    legacy_key = _section_key(result)
    return render_map.unique_statement_panel_keys.get(
        legacy_key,
        render_map.unique_note_panel_keys.get(legacy_key, legacy_key),
    )


def _panel_key_from_check_id_table_hint(
    result: CheckResult,
    render_map: _ReportRenderMap,
) -> str:
    match = re.search(r"(?:^|:)table(\d+)(?::|$)", result.check_id or "")
    if match is None:
        return ""
    candidates = render_map.tables_by_index.get(int(match.group(1)), ())
    if result.note_no:
        note_matches = [
            candidate
            for candidate in candidates
            if candidate.section.kind == "note"
            and _note_identity(candidate.section) == result.note_no
        ]
        if len(note_matches) == 1:
            return note_matches[0].panel_key
    if len(candidates) == 1:
        return candidates[0].panel_key
    return ""


def _note_reference_panel_key(
    report: FullReport,
    result: CheckResult,
    render_map: _ReportRenderMap,
) -> str:
    if result.check_type != "note_reference_check" or not result.note_no:
        return ""

    scope_slug = _result_consolidation_scope_slug(result)
    if not scope_slug:
        source = _note_reference_source_from_check_id(result.check_id)
        section = _section_for_note_reference_source(report, source)
        scope_slug = _scope_slug(section.scope) if section is not None else ""
    if not scope_slug:
        return ""

    matches = _note_reference_note_matches(report, result.note_no, scope_slug)
    if len(matches) != 1:
        return ""
    return _note_panel_id(render_map, matches[0])


def _note_reference_note_matches(
    report: FullReport, note_no: str, scope_slug: str
) -> list[ReportSection]:
    exact = [
        section
        for section in report.notes
        if _note_identity(section) == note_no
        and _scope_slug(section.scope) == scope_slug
    ]
    if exact:
        return exact[:1] if len(exact) == 1 else []

    primary = _primary_note_number(note_no)
    if not primary:
        return []
    primary_matches = [
        section
        for section in report.notes
        if _primary_note_number(_note_identity(section)) == primary
        and _scope_slug(section.scope) == scope_slug
    ]
    return primary_matches[:1]


def _primary_note_number(note_no: str) -> str:
    match = re.match(r"\d+", note_no or "")
    return match.group(0) if match is not None else ""


def _result_consolidation_scope_slug(result: CheckResult) -> str:
    basis = (result.consolidation_basis or "").strip().lower()
    if basis in {"", "unknown"}:
        return ""
    return _scope_slug(result.consolidation_basis)


def _note_reference_source_from_check_id(check_id: str) -> str:
    match = re.match(r"^note_ref:(.+):note\d+$", check_id or "")
    return match.group(1) if match is not None else ""


def _section_for_note_reference_source(
    report: FullReport, source: str
) -> ReportSection | None:
    match = re.match(r"^(.*):block(\d+)$", source or "")
    if match is None:
        return None
    section_id, block_idx_text = match.groups()
    block_idx = int(block_idx_text)
    candidates = [
        section
        for section in [*report.statements, *report.notes]
        if section.section_id == section_id and block_idx < len(section.blocks)
    ]
    return candidates[0] if len(candidates) == 1 else None


def _renderable_panel_keys(report: FullReport, render_map: _ReportRenderMap) -> set[str]:
    keys: set[str] = set()
    for section, _kind, _label in _rendered_statement_sections(report):
        keys.add(_statement_panel_id(render_map, section))
    for section in report.notes:
        keys.add(_note_panel_id(render_map, section))
    return keys


def _rendered_panel_keys(
    report: FullReport,
    tied: dict[str, list[CheckResult]],
    render_map: _ReportRenderMap,
) -> set[str]:
    keys = _renderable_panel_keys(report, render_map)
    if tied.get("other"):
        keys.add("other")
    return keys


def _unplaced_result_count(
    results: list[CheckResult],
    tied: dict[str, list[CheckResult]],
    rendered_keys: set[str],
) -> int:
    return len(tied.get("other", []))


def _broken_evidence_anchor_count(
    report: FullReport,
    results: list[CheckResult],
    render_map: _ReportRenderMap | None = None,
) -> int:
    if render_map is None:
        render_map = _build_render_map(report)
    broken = 0
    for result in results:
        for evidence in result.evidence:
            if not evidence.source:
                continue
            parsed = _parse_source(evidence.source)
            if parsed is None:
                continue
            _scope, _name, _table_idx, row_idx, col_idx = parsed
            if row_idx is None:
                continue
            rendered = _rendered_table_for_source(parsed, render_map)
            if rendered is None or row_idx <= 0 or row_idx >= len(rendered.table.rows):
                broken += 1
                continue
            if col_idx is not None and (
                col_idx < 0 or col_idx >= len(rendered.table.rows[row_idx])
            ):
                broken += 1
    return broken


def _render_report_masthead(
    report: FullReport,
    results: list[CheckResult],
    meta: _ReportMeta,
) -> str:
    c = _status_counts(results)
    open_items = c["gaps"] + c["uncertain"]
    source = Path(report.source).name if report.source else "원문"
    period = f'<span>{_esc(meta.period)}</span>' if meta.period else ""
    return f"""<section class="report-masthead" aria-label="보고서 개요">
  <div class="report-id">
    <div class="report-kicker">DART 검증보고서</div>
    <h1>{_esc(meta.company)}</h1>
    <div class="report-meta">
      <span>{_esc(source)}</span>
      {period}
      <span>재무제표 {len(report.statements)}</span>
      <span>주석 {len(report.notes)}</span>
    </div>
  </div>
  <div class="report-focus">
    <div class="focus-number">{open_items}</div>
    <div>
      <div class="focus-label">우선 검토</div>
      <div class="focus-sub">검토 필요 + 자동 해석 확인</div>
    </div>
  </div>
</section>"""


# ── Sidebar ───────────────────────────────────────────────────────────────────

def _render_sidebar(
    report: FullReport,
    results: list[CheckResult],
    tied: dict[str, list[CheckResult]],
    render_map: _ReportRenderMap,
) -> str:

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
    for section, kind, label in _rendered_statement_sections(report):
        panel_id = _statement_panel_id(render_map, section)
        b = _badge(panel_id)
        stmt_items += (
            f'<div class="nav-item" data-target="{_esc(panel_id)}">'
            f'{_esc(_statement_nav_label(section, kind, label, render_map))} {b}</div>\n'
        )

    note_items = ""
    for section in report.notes:
        panel_id = _note_panel_id(render_map, section)
        b = _badge(panel_id)
        note_items += (
            f'<div class="nav-item" data-target="{_esc(panel_id)}">'
            f'{_esc(_note_nav_label(section, render_map))} {b}'
            f'</div>\n'
        )

    other_item = ""
    if tied.get("other"):
        other_item = (
            f'<div class="nav-item" data-target="panel-other">'
            f'기타 검증 {_badge("other")}'
            f'</div>'
        )

    uncertain_count = sum(1 for r in results if r.status == PARSE_UNCERTAIN)
    diag_item = ""
    if uncertain_count:
        diag_item = (
            f'<div class="nav-item" data-target="panel-parse-diag">'
            f'자동 해석 확인 <span class="nav-badge nb-unc">? {uncertain_count}</span>'
            f'</div>'
        )

    gap_count = sum(1 for r in results if r.status == UNEXPLAINED_GAP)
    if gap_count:
        attn_badge = f'<span class="nav-badge nb-warn">⚠ {gap_count}</span>'
    elif uncertain_count:
        attn_badge = f'<span class="nav-badge nb-unc">? {uncertain_count}</span>'
    else:
        attn_badge = '<span class="nav-badge nb-ok">✓</span>'

    return f"""<aside>
  <div class="sidebar-brand">
    <div class="sidebar-brand-name">DART 수치 검증</div>
    <div class="sidebar-brand-sub">{_esc(report.company)}</div>
  </div>
  <nav class="side-nav" aria-label="검토 뷰">
  <div class="sidebar-section">검토 뷰</div>
  <div class="nav-item active" data-target="panel-summary" aria-current="page">대시보드</div>
  <div class="nav-item" data-target="panel-progress">진행상황</div>
  <div class="nav-item" data-target="panel-attention">확인 필요 {attn_badge}</div>
  <div class="nav-item" data-target="panel-next">다음 작업</div>
  <div class="nav-item" data-target="panel-legend">검증 범례</div>
  </nav>
  <hr class="sidebar-divider">
  <div class="sidebar-section">근거 · 재무제표 본문</div>
  {stmt_items}
  <hr class="sidebar-divider">
  <div class="sidebar-section">근거 · 주석</div>
  {note_items}
  {other_item}
  {diag_item}
</aside>"""


# ── Verdict Banner ────────────────────────────────────────────────────────────

def _render_verdict_banner(
    report: FullReport,
    results: list[CheckResult],
    render_map: _ReportRenderMap,
) -> str:
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

    c = {
        "matched": matched,
        "explained": explained,
        "gaps": gaps,
        "uncertain": uncertain,
        "not_tested": not_tested,
        "total": total,
    }
    # All five statuses are surfaced so explainable gaps and — critically —
    # not-tested coverage are never hidden behind a clean-looking verdict.
    return f"""<div class="verdict-banner {verdict_class}" id="panel-summary">
  <div class="verdict-head">
    <div>
      <div class="verdict-label">{verdict_label}</div>
      <div class="verdict-sub">{_esc(_verdict_subtitle(c))}</div>
    </div>
    <button class="summary-action" type="button" data-target-inline="panel-attention">확인 필요 보기</button>
  </div>
  {_render_dashboard_cards(report, c, render_map)}
  {_render_status_tiles(c)}
  {_render_reader_brief(results)}
</div>"""


# ── Reader-orientation brief + cockpit overview views ─────────────────────────

def _status_counts(results: list[CheckResult]) -> dict[str, int]:
    return {
        "matched": sum(1 for r in results if r.status == MATCHED),
        "explained": sum(1 for r in results if r.status == EXPLAINABLE_GAP),
        "gaps": sum(1 for r in results if r.status == UNEXPLAINED_GAP),
        "uncertain": sum(1 for r in results if r.status == PARSE_UNCERTAIN),
        "not_tested": sum(1 for r in results if r.status == NOT_TESTED),
        "total": len(results),
    }


def _verdict_subtitle(c: dict[str, int]) -> str:
    if c["gaps"]:
        return "차이 항목 우선 확인"
    if c["uncertain"]:
        return "자동 해석 항목 우선 확인"
    if c["not_tested"]:
        return "미검증 범위 확인"
    return "열린 항목 없음"


def _first_statement_target(report: FullReport, render_map: _ReportRenderMap) -> str:
    statements = _rendered_statement_sections(report)
    if statements:
        section, _kind, _label = statements[0]
        return _statement_panel_id(render_map, section)
    return "panel-progress"


def _first_note_target(report: FullReport, render_map: _ReportRenderMap) -> str:
    if not report.notes:
        return "panel-progress"
    return _note_panel_id(render_map, report.notes[0])


def _render_dashboard_cards(
    report: FullReport,
    c: dict[str, int],
    render_map: _ReportRenderMap,
) -> str:
    attention = c["gaps"] + c["uncertain"]
    return f"""<div class="dashboard-card-grid" aria-label="총괄 대시보드">
  <button class="dash-card dc-attention" type="button" data-target-inline="panel-attention">
    <span class="pc-value">{attention}</span>
    <span class="pc-label">확인 필요</span>
    <span class="pc-copy">차이 {c['gaps']} · 해석 확인 {c['uncertain']}</span>
  </button>
  <button class="dash-card dc-progress" type="button" data-target-inline="panel-progress">
    <span class="pc-value">{c['matched']}</span>
    <span class="pc-label">진행상황</span>
    <span class="pc-copy">전체 {c['total']}</span>
  </button>
  <button class="dash-card dc-source" type="button" data-target-inline="{_first_statement_target(report, render_map)}">
    <span class="pc-value">{len(report.statements)}</span>
    <span class="pc-label">재무제표</span>
    <span class="pc-copy">원문 매칭</span>
  </button>
  <button class="dash-card dc-note" type="button" data-target-inline="{_first_note_target(report, render_map)}">
    <span class="pc-value">{len(report.notes)}</span>
    <span class="pc-label">주석</span>
    <span class="pc-copy">근거 표</span>
  </button>
  <button class="dash-card dc-next" type="button" data-target-inline="panel-next">
    <span class="pc-value">{c['not_tested']}</span>
    <span class="pc-label">다음 작업</span>
    <span class="pc-copy">처리 순서</span>
  </button>
</div>"""


def _render_status_tiles(c: dict[str, int]) -> str:
    return f"""<div class="kpi-strip" aria-label="상태별 검증 건수">
    <div class="kpi-tile kpi-ok"><div class="kpi-val">{c['matched']}</div><div class="kpi-name">검증 완료</div></div>
    <div class="kpi-tile kpi-exp"><div class="kpi-val">{c['explained']}</div><div class="kpi-name">설명된 차이</div></div>
    <div class="kpi-tile kpi-warn"><div class="kpi-val">{c['gaps']}</div><div class="kpi-name">검토 필요</div></div>
    <div class="kpi-tile kpi-unc"><div class="kpi-val">{c['uncertain']}</div><div class="kpi-name">자동 해석 확인</div></div>
    <div class="kpi-tile kpi-nt"><div class="kpi-val">{c['not_tested']}</div><div class="kpi-name">미검증</div></div>
    <div class="kpi-tile"><div class="kpi-val">{c['total']}</div><div class="kpi-name">전체</div></div>
  </div>"""


def _next_action_lines(c: dict[str, int]) -> list[str]:
    lines: list[str] = []
    if c["gaps"]:
        lines.append(f"‘확인 필요’ 화면에서 검토 필요 {c['gaps']}건의 차이 원인(재분류·반올림·범위)을 공시 원문과 대조")
    if c["uncertain"]:
        lines.append(f"자동 해석 확인 {c['uncertain']}건은 근거 위치를 직접 열어 수치를 확인")
    if not lines:
        lines.append("표본 내 추가 조치 없음 — 미검증 범위 확대 검토")
    return lines


def _render_reader_brief(results: list[CheckResult]) -> str:
    """Section Brief: 현재 상태 / 왜 중요한가 / 다음 작업, always visible in the
    first viewport so a clean verdict never hides coverage or open items."""
    c = _status_counts(results)
    state = f"완료 {c['matched']} · 열림 {c['gaps'] + c['uncertain']} · 미검증 {c['not_tested']}"
    why = "원문 수치와 주석 근거를 같은 화면에서 대조"
    do = "확인 필요 → 근거 위치 → 후속 처리"
    return f"""<div class="reader-brief">
  <div class="rb-item"><div class="rb-k">현재 상태</div><div class="rb-v">{_esc(state)}</div></div>
  <div class="rb-item"><div class="rb-k">왜 중요한가</div><div class="rb-v">{_esc(why)}</div></div>
  <div class="rb-item"><div class="rb-k">다음 작업</div><div class="rb-v">{_esc(do)}</div></div>
</div>"""


def _render_progress_panel(
    report: FullReport,
    results: list[CheckResult],
    tied: dict[str, list[CheckResult]],
    render_map: _ReportRenderMap,
    *,
    unplaced_count: int = 0,
    broken_anchor_count: int = 0,
) -> str:
    """진행상황: per-section coverage so the auditor sees what was tested, what is
    open, and what was never reached — in one place instead of per-statement."""
    c = _status_counts(results)
    tested = c["matched"] + c["explained"] + c["gaps"] + c["uncertain"]
    rate = f"{(c['matched'] / tested * 100):.0f}%" if tested else "—"

    def _row(label: str, items: list[CheckResult]) -> str:
        if not items:
            return ""
        m = sum(1 for r in items if r.status == MATCHED)
        e = sum(1 for r in items if r.status == EXPLAINABLE_GAP)
        g = sum(1 for r in items if r.status == UNEXPLAINED_GAP)
        u = sum(1 for r in items if r.status == PARSE_UNCERTAIN)
        n = sum(1 for r in items if r.status == NOT_TESTED)
        return (f"<tr><td>{_esc(label)}</td><td>{m}</td><td>{e}</td><td>{g}</td>"
                f"<td>{u}</td><td>{n}</td><td>{len(items)}</td></tr>")

    rows = ""
    for section, kind, label in _rendered_statement_sections(report):
        panel_id = _statement_panel_id(render_map, section)
        rows += _row(_statement_nav_label(section, kind, label, render_map), tied.get(panel_id, []))
    for section in report.notes:
        panel_id = _note_panel_id(render_map, section)
        rows += _row(_note_nav_label(section, render_map), tied.get(panel_id, []))
    rows += _row("기타 검증", tied.get("other", []))

    body = (f'<div class="statement-wrap"><table class="fs-table">'
            f'<thead><tr><th>구분</th><th>검증완료</th><th>설명차이</th>'
            f'<th>검토필요</th><th>해석확인필요</th><th>미검증</th><th>전체</th>'
            f'</tr></thead><tbody>{rows}</tbody>'
            f'</table></div>') if rows else '<div class="empty-state">검증 항목이 없습니다.</div>'

    if unplaced_count:
        placement = (
            f'<button class="progress-diag warn" type="button" data-target-inline="panel-other">'
            f'보고서 표시 확인 필요 {unplaced_count}건 · 기타 검증 패널에서 확인</button>'
        )
    else:
        placement = '<span class="progress-diag">보고서 표시 확인 필요 0건</span>'
    anchor_class = "progress-diag warn" if broken_anchor_count else "progress-diag"
    anchors = f'<span class="{anchor_class}">원문 위치 확인 필요 {broken_anchor_count}건</span>'

    return f"""<div class="panel hidden" id="panel-progress">
  <div class="panel-title">진행상황</div>
  <div class="panel-sub">검증 완료율 {rate} · 미검증 {c['not_tested']}건은 적용 가능한 검증이 없었던 항목입니다. · {placement} · {anchors}</div>
  {body}
</div>"""


def _render_attention_panel(
    results: list[CheckResult],
    report: FullReport | None = None,
    render_map: _ReportRenderMap | None = None,
) -> str:
    """확인 필요: every unexplained gap and parse-uncertain item consolidated into
    one filterable list, so the auditor does not have to walk every note panel."""
    flagged = [r for r in results if r.status in (UNEXPLAINED_GAP, PARSE_UNCERTAIN)]
    if not flagged:
        body = '<div class="empty-state">검토가 필요한 항목이 없습니다.</div>'
    else:
        rows = ""
        for index, r in enumerate(flagged):
            tag = "warn" if r.status == UNEXPLAINED_GAP else "unc"
            badge_class = _status_to_badge_class(r.status)
            badge_label = _status_to_badge_label(r.status)
            exp_str = f"{r.expected:,}" if r.expected is not None else "—"
            act_str = f"{r.actual:,}" if r.actual is not None else "—"
            diff_str = f"차이 {r.difference:,}" if r.difference is not None else ""
            dd_id = f"dd-attn-{index}"
            rows += f"""<div class="check-row attn-row" data-tags="{tag}" onclick="toggleDD('{dd_id}')">
  <span class="expand-tri" id="tri-{dd_id}">▶</span>
  <span class="check-name">{_esc(check_display_title(r))}</span>
  <span class="check-vals"><span>{exp_str}</span><span>{act_str}</span><span>{diff_str}</span></span>
  <span class="badge {badge_class}">{badge_label}</span>
</div>
<div class="dd-inline" id="{dd_id}">{_render_drilldown(r, report, render_map)}</div>"""
        body = f'<div class="check-summary">{rows}</div>'

    return f"""<div class="panel hidden" id="panel-attention">
  <div class="panel-title">확인 필요</div>
  <div class="panel-sub">검토 필요·자동 해석 확인 항목을 한 곳에 모았습니다.</div>
  <div class="filter-pills" data-filter-control="#panel-attention">
    <button data-filter="all" aria-pressed="true">전체</button>
    <button data-filter="warn" aria-pressed="false">검토 필요</button>
    <button data-filter="unc" aria-pressed="false">자동 해석 확인</button>
  </div>
  {body}
</div>"""


def _render_next_actions_panel(results: list[CheckResult]) -> str:
    """다음 작업: derived checklist so the report ends on action, not just status."""
    c = _status_counts(results)
    lis = "".join(f"<li>{_esc(line)}</li>" for line in _next_action_lines(c))
    return f"""<div class="panel hidden" id="panel-next">
  <div class="panel-title">다음 작업</div>
  <div class="panel-sub">확인 필요 항목을 처리하기 위한 후속 작업입니다.</div>
  <ol class="next-actions">{lis}</ol>
</div>"""


def _render_legend_panel(results: list[CheckResult]) -> str:
    results_by_group: dict[str, list[CheckResult]] = {}
    methods_by_group: dict[str, list[tuple[str, str]]] = {}
    seen_check_types: set[str] = set()
    for result in results:
        group = CHECK_GROUPS.get(result.check_type, "기타")
        results_by_group.setdefault(group, []).append(result)
        if result.check_type in CHECK_GROUPS and result.check_type not in seen_check_types:
            methods_by_group.setdefault(group, []).append((
                CHECK_DISPLAY_NAMES[result.check_type],
                CHECK_METHOD_DESCRIPTIONS[result.check_type],
            ))
            seen_check_types.add(result.check_type)

    cards = ""
    ordered_groups = [group for group in CHECK_GROUP_ORDER if group in results_by_group]
    for group in results_by_group:
        if group not in ordered_groups:
            ordered_groups.append(group)
    for group in ordered_groups:
        methods = methods_by_group.get(group, [])
        group_results = results_by_group.get(group, [])
        if not methods and not group_results:
            continue
        counts = _status_counts(group_results)
        status_line = (
            f"검증 완료 {counts['matched']} · 설명된 차이 {counts['explained']} · "
            f"검토 필요 {counts['gaps']} · 해석 확인 필요 {counts['uncertain']} · "
            f"미검증 {counts['not_tested']}"
        )
        method_items = "".join(
            f'<li><strong>{_esc(display_name)}</strong><span>{_esc(description)}</span></li>'
            for display_name, description in sorted(methods)
        )
        if not method_items:
            method_items = '<li><strong>기타 검증</strong><span>등록되지 않은 검증 유형</span></li>'
        cards += f"""<div class="legend-group">
  <div class="legend-head">
    <div class="legend-title">{_esc(group)}</div>
    <div class="legend-counts">{_esc(status_line)}</div>
  </div>
  <ul class="legend-methods">{method_items}</ul>
</div>"""

    return f"""<div class="panel hidden" id="panel-legend">
  <div class="panel-title">검증 범례</div>
  <div class="panel-sub">이 보고서에서 수행한 검증의 비교 방식과 상태별 건수입니다.</div>
  {cards}
</div>"""


# ── Statement Panel ───────────────────────────────────────────────────────────

def _render_statement_panel(
    section: ReportSection,
    results: list[CheckResult],
    panel_id: str,
    label: str,
    report: FullReport | None = None,
    render_map: _ReportRenderMap | None = None,
) -> str:
    table = _first_table(section)
    if table is None:
        check_summary = _render_expandable_check_summary(
            results,
            report=report,
            render_map=render_map,
            id_prefix=f"dd-stmt-{_safe_id(panel_id)}",
        )
        return (
            f'<div class="panel" id="{_esc(panel_id)}">'
            f'<div class="panel-title">{_esc(label)}</div>'
            f'<p class="empty-state">공시에서 찾을 수 없음</p>'
            f'{check_summary}</div>'
        )

    row_map: dict[int, CheckResult] = {}
    for result in results:
        for ev in result.evidence:
            parsed = _parse_source(ev.source)
            if parsed and parsed[2] == table.index and parsed[3] is not None:
                idx = parsed[3]
                if idx not in row_map:
                    row_map[idx] = result
                else:
                    row_map[idx] = _worse(row_map[idx], result)

    rows_html = _render_table_rows(
        table,
        row_map,
        id_prefix=panel_id,
        show_state=True,
        report=report,
        render_map=render_map,
    )
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
    render_map: _ReportRenderMap | None = None,
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
        row_key = _row_key(table.index, i)
        cells = "".join(
            f'<td data-cell="{_cell_key(table.index, i, ci)}">{_esc(c)}</td>'
            for ci, c in enumerate(row)
        )
        if result is not None:
            css_class = _status_to_row_class(result.status)
            dd_id = f"{id_prefix}-{i}"
            if show_state:
                state_cell = f'<td class="state-col">{_account_state_badge(result.status)}</td>'
                dd_colspan = len(row) + 1
                html_parts.append(
                    f'<tr class="{css_class}" data-row="{row_key}" data-check-row="{i}" '
                    f'onclick="toggleDD(\'{dd_id}\')">{state_cell}{cells}</tr>'
                )
            else:
                dd_colspan = len(row)
                html_parts.append(
                    f'<tr class="{css_class}" data-row="{row_key}" data-check-row="{i}" '
                    f'onclick="toggleDD(\'{dd_id}\')">{cells}</tr>'
                )
            html_parts.append(
                f'<tr class="dd-row">'
                f'<td colspan="{dd_colspan}" class="dd-cell">'
                f'<div class="dd-inner" id="{dd_id}">'
                f'{_render_drilldown(result, report, render_map)}'
                f'</div></td></tr>'
            )
        elif has_amount:
            if show_state:
                state_cell = f'<td class="state-col">{_account_state_badge(None)}</td>'
                html_parts.append(f'<tr data-row="{row_key}">{state_cell}{cells}</tr>')
            else:
                html_parts.append(f'<tr data-row="{row_key}">{cells}</tr>')
        else:
            if show_state:
                state_cell = '<td class="state-col"></td>'
                html_parts.append(f'<tr data-row="{row_key}">{state_cell}{cells}</tr>')
            else:
                html_parts.append(f'<tr data-row="{row_key}">{cells}</tr>')

    html_parts.append("</tbody>")
    return "\n".join(html_parts)


def _display_cell_for_coordinate(
    table: ReportTable,
    row_index: int,
    column_index: int,
) -> TableCellLayout | None:
    for cell in table.display_cells or ():
        if (
            cell.row_index <= row_index < cell.row_index + cell.rowspan
            and cell.column_index <= column_index < cell.column_index + cell.colspan
        ):
            return cell
    return None


def _render_source_table(
    table: ReportTable,
    cell_annotations: tuple[CellAnnotation, ...],
    drawer_items: tuple[DrawerItem, ...],
    *,
    is_statement: bool = False,
) -> str:
    display_cells = table.display_cells or tuple(
        TableCellLayout(
            text=value,
            row_index=row_index,
            column_index=column_index,
            tag="th" if row_index == 0 else "td",
        )
        for row_index, row in enumerate(table.rows)
        for column_index, value in enumerate(row)
    )
    if not display_cells:
        return '<div class="empty-state">표시할 원문 표가 없습니다.</div>'

    annotations_by_origin: dict[tuple[int, int], list[CellAnnotation]] = {}
    for annotation in cell_annotations:
        if annotation.target.table_index != table.index or not annotation.target.is_exact_cell:
            continue
        original = _display_cell_for_coordinate(
            table,
            annotation.target.row_index,
            annotation.target.column_index,
        )
        origin = (
            (original.row_index, original.column_index)
            if original is not None
            else (annotation.target.row_index, annotation.target.column_index)
        )
        annotations_by_origin.setdefault(origin, []).append(annotation)

    drawers_by_origin: dict[tuple[int, int], list[int]] = {}
    for drawer_index, item in enumerate(drawer_items):
        for anchor in item.anchors:
            if anchor.table_index != table.index or not anchor.is_exact_cell:
                continue
            original = _display_cell_for_coordinate(
                table,
                anchor.row_index,
                anchor.column_index,
            )
            origin = (
                (original.row_index, original.column_index)
                if original is not None
                else (anchor.row_index, anchor.column_index)
            )
            drawers_by_origin.setdefault(origin, []).append(drawer_index)

    cells_by_row: dict[int, list[TableCellLayout]] = {}
    for cell in display_cells:
        cells_by_row.setdefault(cell.row_index, []).append(cell)
    for cells in cells_by_row.values():
        cells.sort(key=lambda cell: cell.column_index)

    header_rows: set[int] = set()
    for row_index in sorted(cells_by_row):
        if all(cell.tag == "th" for cell in cells_by_row[row_index]):
            header_rows.add(row_index)
            continue
        break

    def render_row(row_index: int) -> str:
        rendered: list[str] = []
        row_drawer_indexes = list(
            dict.fromkeys(
                drawer_index
                for (origin_row, _origin_col), indexes in drawers_by_origin.items()
                if origin_row == row_index
                for drawer_index in indexes
            )
        )
        row_drawer_indexes.sort(
            key=lambda index: (
                drawer_items[index].check.check_type
                != "statement_note_row_reconciliation"
            )
        )
        row_cells = cells_by_row[row_index]
        row_annotations = [
            annotation
            for (origin_row, _origin_col), items in annotations_by_origin.items()
            if origin_row == row_index
            for annotation in items
        ]
        is_total_row = bool(row_cells) and is_subtotal_row_label(row_cells[0].text)
        is_unchecked_total = (
            is_total_row and not row_annotations and row_index not in header_rows
        )
        row_result_text = _statement_row_result_text(
            [drawer_items[index].check for index in row_drawer_indexes]
        )
        for cell_index, cell in enumerate(row_cells):
            origin = (cell.row_index, cell.column_index)
            annotations = annotations_by_origin.get(origin, [])
            drawer_indexes = drawers_by_origin.get(origin, [])
            classes = ["source-cell"]
            attributes = [f'data-cell="t{table.index}r{cell.row_index}c{cell.column_index}"']
            coverage = " ".join(
                f"t{table.index}r{row}c{column}"
                for row in range(cell.row_index, cell.row_index + cell.rowspan)
                for column in range(cell.column_index, cell.column_index + cell.colspan)
            )
            attributes.append(f'data-cell-coverage="{coverage}"')
            if cell.rowspan > 1:
                attributes.insert(0, f'rowspan="{cell.rowspan}"')
            if cell.colspan > 1:
                attributes.insert(0, f'colspan="{cell.colspan}"')

            inner = _esc(cell.text)
            if annotations:
                severity = {
                    MATCHED: 1,
                    EXPLAINABLE_GAP: 2,
                    PARSE_UNCERTAIN: 3,
                    UNEXPLAINED_GAP: 4,
                }
                worst = max(
                    annotations,
                    key=lambda item: severity.get(item.status, 0),
                )
                status_class = {
                    MATCHED: "cell-matched",
                    EXPLAINABLE_GAP: "cell-explained",
                    UNEXPLAINED_GAP: "cell-gap",
                    PARSE_UNCERTAIN: "cell-uncertain",
                }.get(worst.status, "")
                status_label = {
                    MATCHED: "일치",
                    EXPLAINABLE_GAP: "차이 원인 설명됨",
                    UNEXPLAINED_GAP: "확인 필요",
                    PARSE_UNCERTAIN: "원문 확인",
                }.get(worst.status, "확인 필요")
                checks = tuple(
                    check
                    for annotation in annotations
                    for check in annotation.checks
                )
                classes.extend(["cell-check", status_class])
                attributes.extend(
                    [
                        'tabindex="0"',
                        f'aria-label="{_esc(check_display_title(checks[0]))} {status_label}"',
                        f'data-validation-label="합계 검증 {status_label}"',
                    ]
                )
                tooltip_rows = "".join(
                    f'<div class="cell-tooltip-item"><strong>{_esc(check_display_title(check))}</strong>'
                    f'<span>{_esc(CHECK_METHOD_DESCRIPTIONS.get(check.check_type, "검증 결과 확인"))}</span>'
                    f'<span>기준 {_amount_text(check.expected)} · 표시 {_amount_text(check.actual)} · '
                    f'차이 {_amount_text(check.difference)}</span></div>'
                    for check in checks
                )
                count_badge = (
                    '<span class="cell-check-count" '
                    f'aria-label="합계 검증 {len(checks)}건">'
                    f'합계 검증 {len(checks)}건</span>'
                    if len(checks) > 1
                    else ""
                )
                inner = f'{inner}{count_badge}<span class="cell-tooltip">{tooltip_rows}</span>'
            if drawer_indexes:
                drawer_indexes = list(dict.fromkeys(drawer_indexes))
                classes.append("cell-reconciliation")
                attributes.append(f'data-open-drawer="{drawer_indexes[0]}"')
                attributes.append(
                    f'data-drawer-indexes="{",".join(str(index) for index in drawer_indexes)}"'
                )
                attributes.append('role="button"')
                if not annotations:
                    attributes.append('tabindex="0"')
                if len(drawer_indexes) > 1 and not (
                    is_statement and row_drawer_indexes
                ):
                    inner += (
                        '<span class="cell-reconciliation-count" '
                        f'aria-label="대사 {len(drawer_indexes)}건">'
                        f'대사 {len(drawer_indexes)}건</span>'
                    )
            if is_statement and row_drawer_indexes and cell_index == 0:
                inner += (
                    f'<span class="row-result-count">{_esc(row_result_text)}</span>'
                )
            if is_unchecked_total and cell_index == 0:
                inner += (
                    '<span class="total-result-missing">합계 검증 결과 없음</span>'
                )

            tag = "th" if cell.tag == "th" else "td"
            attrs = " ".join(attributes)
            rendered.append(
                f'<{tag} {attrs} class="{" ".join(value for value in classes if value)}">'
                f'{inner}</{tag}>'
            )
        row_attributes = [f'data-row="t{table.index}r{row_index}"']
        row_classes = ["source-row"]
        if is_unchecked_total:
            row_classes.append("source-row-total-unchecked")
        if is_statement and row_drawer_indexes and row_index not in header_rows:
            row_classes.append("source-row-reconciliation")
            row_attributes.extend(
                [
                    f'data-open-drawer="{row_drawer_indexes[0]}"',
                    'tabindex="0"',
                    'role="button"',
                    f'aria-label="{_esc(row_cells[0].text)} 행 검증 결과 '
                    f'{len(row_drawer_indexes)}건"',
                ]
            )
        return (
            f'<tr class="{" ".join(row_classes)}" {" ".join(row_attributes)}>'
            f'{"".join(rendered)}</tr>'
        )

    head = "".join(render_row(row) for row in sorted(header_rows))
    body = "".join(
        render_row(row)
        for row in sorted(cells_by_row)
        if row not in header_rows
    )
    sticky_total = any(
        annotation.target.table_index == table.index
        and annotation.target.is_exact_cell
        and annotation.target.row_index < len(table.rows)
        and annotation.target.column_index == len(table.rows[annotation.target.row_index]) - 1
        for annotation in cell_annotations
    )
    table_class = (
        "source-table source-table-sticky-total"
        if sticky_total
        else "source-table"
    )
    return (
        '<div class="source-table-scroll" data-horizontal-scroll>'
        '<span class="source-table-scroll-hint">가로로 이동하여 전체 금액 확인</span>'
        f'<table class="{table_class}">'
        f'<thead>{head}</thead><tbody>{body}</tbody>'
        '</table></div>'
    )


def _statement_row_result_text(checks: list[CheckResult]) -> str:
    if not checks:
        return ""
    severity = {
        MATCHED: 1,
        EXPLAINABLE_GAP: 2,
        PARSE_UNCERTAIN: 3,
        UNEXPLAINED_GAP: 4,
    }
    status = max(checks, key=lambda check: severity.get(check.status, 0)).status
    cashflow = any(
        CHECK_GROUPS.get(check.check_type) == "현금흐름표-주석 대사"
        for check in checks
    )
    statement_cross = any(
        CHECK_GROUPS.get(check.check_type) == "재무제표 교차 검증"
        for check in checks
    )
    statement_note = any(
        check.check_type == "statement_note_row_reconciliation" for check in checks
    )
    if statement_note:
        label = "주석 대사 완료" if status == MATCHED else "주석 대사 확인 필요"
    elif cashflow:
        label = {
            MATCHED: "주석과 일치",
            EXPLAINABLE_GAP: "차이 설명됨",
            PARSE_UNCERTAIN: "원문 확인 필요",
            UNEXPLAINED_GAP: "확인 필요",
        }.get(status, "검증 결과")
    elif statement_cross:
        label = {
            MATCHED: "재무제표 등식 일치",
            EXPLAINABLE_GAP: "등식 차이 설명됨",
            PARSE_UNCERTAIN: "등식 원문 확인 필요",
            UNEXPLAINED_GAP: "등식 확인 필요",
        }.get(status, "재무제표 등식 결과")
    else:
        label = {
            MATCHED: "검증 완료",
            EXPLAINABLE_GAP: "차이 설명됨",
            PARSE_UNCERTAIN: "원문 확인 필요",
            UNEXPLAINED_GAP: "검토 필요",
        }.get(status, "검증 결과")
    return f"{label} · {len(checks)}건" if len(checks) > 1 else label


def _amount_text(value: int | None) -> str:
    return "—" if value is None else f"{value:,}"


def _status_to_row_class(status: str) -> str:
    if status == MATCHED:
        return "verified-ok"
    if status == UNEXPLAINED_GAP:
        return "verified-warn"
    return "verified-uncertain"


def _tolerance_text(result: CheckResult) -> str:
    if result.check_type in TABLE_UNIT_TOLERANCE_CHECK_TYPES:
        return f"허용오차 ±{result.tolerance:,} (표시 단위)"
    return f"허용오차 ±{result.tolerance:,}원"


def _render_drilldown(
    result: CheckResult,
    report: FullReport | None = None,
    render_map: _ReportRenderMap | None = None,
) -> str:
    if render_map is None and report is not None:
        render_map = _build_render_map(report)
    callout_class = "ok" if result.status == MATCHED else "warn"
    callout_icon = "✓" if result.status == MATCHED else "⚠"
    ev_rows = ""
    for ev in [e for e in result.evidence if e.role != "component"]:
        amount_str = f"{ev.amount:,}" if ev.amount is not None else "—"
        human = _humanize_source(report, ev.source) if report is not None else (ev.source or "—")
        parsed = _parse_source(ev.source)
        if parsed and parsed[3] is not None:
            scope, name, table_idx, rr, cc = parsed
            cell_key = _cell_key(table_idx, rr, cc)
            panel = _source_panel_id_for_parsed(parsed, render_map) or _source_panel_id(scope, name)
            src_cell = (f'<td class="src-ref"><span class="src-jump" '
                        f'data-jump="{_esc(panel)}" data-jump-cell="{cell_key}" '
                        f'onclick="jumpToCell(this)">{_esc(human)}</span></td>')
        else:
            src_cell = f"<td class='src-ref'>{_esc(human)}</td>"
        ev_rows += f"<tr><td>{_esc(evidence_display_label(ev.label))}</td><td>{amount_str}</td>{src_cell}</tr>"
    components = [e for e in result.evidence if e.role == "component"]
    breakdown = ""
    if components:
        comp_rows = "".join(
            f"<tr><td>{_esc(evidence_display_label(e.label))}</td><td>{(e.amount if e.amount is not None else 0):,}</td></tr>"
            for e in components
        )
        comp_sum = sum(e.amount or 0 for e in components)
        exp_str = f"{result.expected:,}" if result.expected is not None else f"{comp_sum:,}"
        act_str = f"{result.actual:,}" if result.actual is not None else "—"
        diff_val = result.difference if result.difference is not None else 0
        breakdown = (
            f'<div class="dd-breakdown"><div class="dd-bd-head">구성요소 합산</div>'
            f'<table class="src-tbl"><tbody>{comp_rows}</tbody></table>'
            f'<div class="dd-bd-sum">기대 = Σ구성요소 {exp_str} · 실제 {act_str} · 차이 {diff_val:,}</div></div>'
        )
    uncertain_note = ""
    if result.parse_uncertain_reason:
        uncertain_note = (
            f'<div class="callout unc">자동 해석 확인: '
            f'{_esc(_uncertain_reason_text(result.parse_uncertain_reason))}</div>'
        )
    method = CHECK_METHOD_DESCRIPTIONS.get(result.check_type, "등록되지 않은 검증 유형")
    method_line = (
        f'<div class="method-line">검증 방법: {_esc(method)} · '
        f'{_esc(_tolerance_text(result))}</div>'
    )
    return f"""<div class="dd-title">{_esc(check_display_title(result))}</div>
<table class="src-tbl">
  <thead><tr><th>항목</th><th>금액</th><th>근거 위치</th></tr></thead>
  <tbody>{ev_rows}</tbody>
</table>
{breakdown}{method_line}<div class="callout {callout_class}">{callout_icon} {_esc(check_display_reason(result))}</div>
{uncertain_note}"""


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
  <span class="check-name">{_esc(check_display_title(result))}</span>
  <span class="check-vals"><span>{exp_str}</span><span>{act_str}</span><span>{diff_str}</span></span>
  <span class="badge {badge_class}">{badge_label}</span>
</div>"""
    return f'<div class="check-summary"><div class="check-summary-head">검증 결과</div>{rows}</div>'


def _render_expandable_check_summary(
    results: list[CheckResult],
    *,
    report: FullReport | None = None,
    render_map: _ReportRenderMap | None = None,
    id_prefix: str,
    title_for_result=None,
) -> str:
    if not results:
        return ""
    check_rows = ""
    for index, result in enumerate(results):
        badge_class = _status_to_badge_class(result.status)
        badge_label = _status_to_badge_label(result.status)
        exp_str = f"{result.expected:,}" if result.expected is not None else "—"
        act_str = f"{result.actual:,}" if result.actual is not None else "—"
        diff_str = f"차이 {result.difference:,}" if result.difference is not None else ""
        dd_id = f"{id_prefix}-{index}"
        title = title_for_result(result) if title_for_result else check_display_title(result)
        check_rows += f"""<div class="check-row" onclick="toggleDD('{dd_id}')">
  <span class="expand-tri" id="tri-{dd_id}">▶</span>
  <span class="check-name">{_esc(title)}</span>
  <span class="check-vals"><span>{exp_str}</span><span>{act_str}</span><span>{diff_str}</span></span>
  <span class="badge {badge_class}">{badge_label}</span>
</div>
<div class="dd-inline" id="{dd_id}">{_render_drilldown(result, report, render_map)}</div>"""
    return f'<div class="check-summary"><div class="check-summary-head">검증 결과</div>{check_rows}</div>'


# ── Note Panel ────────────────────────────────────────────────────────────────

def _display_check_title(result: CheckResult, section: ReportSection) -> str:
    """Drop the redundant note-no/title prefix (the panel already names the note)
    and Koreanize trailing English check phrases."""
    out = check_display_title(result)
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
    return out.strip(" ·-—") or check_display_title(result)


def _render_note_panel(
    section: ReportSection,
    results: list[CheckResult],
    panel_id: str,
    report: FullReport | None = None,
    render_map: _ReportRenderMap | None = None,
) -> str:
    table_html = ""
    for table in _section_tables(section):
        rows_html = _render_table_rows(table, {}, report=report, render_map=render_map)
        caption = _esc(table.heading or section.title)
        table_html += (
            f'<div class="statement-wrap"><div class="statement-caption"><span>{caption}</span></div>'
            f'<table class="fs-table">{rows_html}</table></div>'
        )

    check_section = _render_expandable_check_summary(
        results,
        report=report,
        render_map=render_map,
        id_prefix=f"{_safe_id(panel_id)}-check",
        title_for_result=lambda result: _display_check_title(result, section),
    )

    return f"""<div class="panel" id="{_esc(panel_id)}">
  <div class="panel-title">{"" if not section.note_no else _esc(section.note_no) + ". "}{_esc(section.title)}</div>
  {table_html}
  {check_section}
</div>"""


def _render_other_panel(
    results: list[CheckResult],
    report: FullReport | None = None,
    render_map: _ReportRenderMap | None = None,
) -> str:
    return f"""<div class="panel" id="panel-other">
  <div class="panel-title">기타 검증</div>
  <div class="panel-sub">특정 표에 귀속되지 않는 검증</div>
  {_render_expandable_check_summary(results, report=report, render_map=render_map, id_prefix="dd-other")}
</div>"""


# ── Parse Uncertain Panel ─────────────────────────────────────────────────────

def _render_parse_uncertain_panel(results: list[CheckResult], report: FullReport) -> str:
    cards = ""
    for result in results:
        reason_text = _uncertain_reason_text(result.parse_uncertain_reason or "UNKNOWN")
        candidates_text = "".join(
            f"<li><strong>확인 대상</strong><span>{_esc(evidence_display_label(ev.label))} · "
            f"{_esc(_humanize_source(report, ev.source))}</span></li>"
            for ev in result.evidence
            if ev.source
        )
        cards += f"""<div class="diag-card">
  <div class="diag-title">{_esc(check_display_title(result))}</div>
  <div class="diag-reason">{_esc(reason_text)}</div>
  <ul class="diag-candidates">{candidates_text}</ul>
  <div class="diag-guide">원문에 해당 항목이 있다면 검토를 요청하세요.</div>
</div>"""

    return f"""<div class="panel" id="panel-parse-diag">
  <div class="panel-title">자동 해석 확인</div>
  <div class="panel-sub">원문 구조를 자동으로 확정하지 못한 항목입니다.</div>
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
        "UNIT_MISMATCH_SUSPECTED": "단위(천원/백만원) 스케일 불일치 의심 — 원문 단위 확인 필요",
    }.get(code, "원문 구조를 자동으로 확정하지 못했습니다.")


# ── Desktop workbench assets ─────────────────────────────────────────────────

def _workbench_css() -> str:
    return """<style>
:root{
  --bg:#f4f7f6;--surface:#ffffff;--surface-2:#f6f9f8;--surface-3:#eef4f2;
  --text:#18302c;--muted:#657b77;--border:#d8e2df;--accent:#167d6d;
  --accent-dim:#e4f4f0;--ok:#16825d;--ok-dim:#e7f6ef;--warn:#b85f12;
  --warn-dim:#fff3e6;--explained:#0f766e;--uncertain:#64748b;
  --sidebar:#16332e;--sidebar-text:#c2d3cf;--sidebar-active:#ffffff;
  --font:Pretendard,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
}
*{box-sizing:border-box;}html,body{margin:0;min-height:100%;}
body{min-width:1280px;background:var(--bg);color:var(--text);font-family:var(--font);font-size:13px;line-height:1.55;}
button{font:inherit;}[hidden]{display:none!important;}
.sr-only{position:absolute!important;width:1px!important;height:1px!important;padding:0!important;margin:-1px!important;overflow:hidden!important;clip:rect(0,0,0,0)!important;white-space:nowrap!important;border:0!important;}
.skip-link{position:fixed;left:16px;top:8px;z-index:1000;transform:translateY(-150%);padding:8px 12px;border-radius:5px;background:#fff;color:var(--accent);font-weight:900;box-shadow:0 4px 16px rgba(15,23,42,.2);}
.skip-link:focus{transform:translateY(0);}button:focus-visible,[tabindex]:focus-visible,a:focus-visible{outline:3px solid #2563eb;outline-offset:2px;}.source-panel-heading h2:focus{outline:none;}
.workbench-header{position:sticky;top:0;z-index:50;height:76px;display:flex;align-items:center;justify-content:space-between;gap:24px;padding:10px 20px;background:#fff;border-bottom:1px solid var(--border);}
.report-identity-top{display:flex;align-items:center;gap:12px;}.report-scope-switch{display:inline-flex;padding:2px;border:1px solid var(--border);border-radius:7px;background:var(--surface-2);}
.report-scope-switch button{min-width:48px;padding:3px 9px;border:0;border-radius:5px;background:transparent;color:var(--muted);font-size:11px;font-weight:800;cursor:pointer;}.report-scope-switch button[aria-pressed="true"]{background:#fff;color:var(--accent);box-shadow:0 1px 3px rgba(15,23,42,.12);}
.report-kicker,.drawer-kicker,.source-panel-kicker{font-size:10px;font-weight:900;letter-spacing:.08em;color:var(--accent);}
.report-title-row{display:flex;align-items:center;gap:10px;}.report-title-row h1{margin:0;font-size:20px;line-height:1.2;}
.header-period{padding:2px 7px;border:1px solid var(--border);border-radius:4px;color:var(--muted);font-size:11px;}
.report-source{margin-top:3px;color:var(--muted);font-size:11px;}.report-actions,.scope-status-counts{display:flex;align-items:center;gap:8px;}
.status-summary{display:inline-flex;align-items:center;gap:6px;padding:6px 9px;border:1px solid var(--border);border-radius:6px;background:var(--surface-2);color:var(--text);font:inherit;font-size:11px;cursor:pointer;}
.status-summary strong{font-size:14px;}.status-gap strong{color:var(--warn);}.status-uncertain strong{color:var(--uncertain);}
.export-button{padding:7px 10px;border:1px solid var(--accent);border-radius:6px;background:#fff;color:var(--accent);font-weight:800;cursor:pointer;}.export-button:hover{background:var(--accent-dim);}
.audit-workbench{display:grid;grid-template-columns:260px minmax(620px,1fr) 400px;height:calc(100vh - 76px);min-width:1280px;}
.source-nav{height:calc(100vh - 76px);overflow:auto;background:var(--sidebar);color:var(--sidebar-text);border-right:1px solid rgba(255,255,255,.08);}
.source-nav-brand{padding:16px 16px 12px;border-bottom:1px solid rgba(255,255,255,.08);font-weight:900;color:#fff;}
.source-nav-group{padding:10px 0;}.source-nav-group+.source-nav-group{border-top:1px solid rgba(255,255,255,.08);}
.source-nav-heading{padding:4px 16px 7px;color:#87a59f;font-size:10px;font-weight:900;letter-spacing:.06em;}
.source-nav-item{width:100%;display:flex;align-items:center;justify-content:space-between;gap:8px;padding:8px 14px;border:0;border-left:3px solid transparent;background:transparent;color:var(--sidebar-text);text-align:left;cursor:pointer;}
.source-nav-item:hover,.source-nav-item.active{background:rgba(255,255,255,.07);color:var(--sidebar-active);}.source-nav-item.active{border-left-color:#45c8ae;font-weight:900;}
.source-nav-item>span:first-child{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}.source-nav-empty{padding:7px 16px;color:#87a59f;font-size:11px;}
.nav-state{flex:0 0 auto;padding:1px 5px;border-radius:4px;font-size:9px;font-weight:900;}.nav-state-gap{background:rgba(240,153,67,.2);color:#ffd19a;}
.nav-state-uncertain{background:rgba(203,213,225,.15);color:#d8e0e8;}.nav-state-explained{background:rgba(45,212,191,.15);color:#99f6e4;}.nav-state-matched{background:rgba(74,222,128,.14);color:#bbf7d0;}
.source-stage{min-width:0;height:calc(100vh - 76px);overflow:auto;padding:20px 24px 40px;}.source-panel{max-width:1500px;margin:0 auto;}
.source-panel-heading{margin-bottom:14px;}.source-panel-heading h2{margin:2px 0 0;font-size:20px;}.validation-summary{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px;}.validation-summary-chip{padding:3px 7px;border:1px solid var(--border);border-radius:999px;background:#fff;color:var(--muted);font-size:10px;}.validation-summary-chip strong{color:var(--accent);}.source-table-block{margin-bottom:22px;}
.source-table-caption{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:9px 12px;border:1px solid var(--border);border-bottom:0;border-radius:8px 8px 0 0;background:var(--surface-2);font-size:11px;font-weight:800;color:var(--muted);}
.source-table-scroll{position:relative;overflow-x:auto;overflow-y:visible;border:1px solid var(--border);border-radius:0 0 8px 8px;background:#fff;}
.source-table-scroll::after{content:"";position:sticky;right:0;float:right;width:18px;height:48px;margin-top:-48px;pointer-events:none;background:linear-gradient(90deg,transparent,rgba(15,23,42,.14));}.source-table-scroll.is-scroll-end::after,.source-table-scroll:not(.is-scrollable)::after{display:none;}
.source-table-scroll-hint{position:sticky;left:12px;display:none;width:max-content;margin:6px 0 0 12px;padding:3px 7px;border-radius:999px;background:#eef3f2;color:var(--muted);font-size:10px;font-weight:800;}.source-table-scroll.is-scrollable .source-table-scroll-hint{display:inline-flex;}
.source-table{width:100%;min-width:max-content;border-collapse:collapse;font-size:12px;}.source-table th,.source-table td{position:relative;padding:8px 12px;border:1px solid var(--border);font-variant-numeric:tabular-nums;white-space:nowrap;}
.audit-workbench .source-table{width:max-content;min-width:100%;}
.source-table th{background:var(--surface-2);font-size:11px;font-weight:800;color:var(--muted);text-align:center;white-space:normal;word-break:keep-all;min-width:96px;}.source-table td{text-align:right;}.source-table td:not(:first-child){min-width:118px;}.source-table td:first-child{text-align:left;}
.source-table th:first-child,.source-table td:first-child{position:sticky;left:0;z-index:2;background:#fff;box-shadow:1px 0 0 var(--border);}.source-table th:first-child{z-index:4;background:var(--surface-2);}
.source-table-sticky-total th:last-child,.source-table-sticky-total td:last-child{position:sticky;right:0;z-index:2;background:#fff;border-left-color:#a9bbb6;}.source-table-sticky-total th:last-child{z-index:3;background:var(--surface-2);}
.source-row-reconciliation:hover td{background-color:var(--accent-dim);}.source-row-reconciliation:focus{outline:2px solid var(--accent);outline-offset:-2px;}.row-result-count{display:inline-flex;align-items:center;margin-left:8px;padding:2px 7px;border-radius:999px;background:var(--accent-dim);color:var(--accent);font-size:9px;font-weight:900;vertical-align:middle;white-space:nowrap;}
.source-row-total-unchecked td{background:#fafbfb;}.total-result-missing{display:inline-flex;margin-left:8px;padding:2px 7px;border:1px dashed var(--uncertain);border-radius:999px;color:var(--muted);font-size:9px;font-weight:900;white-space:nowrap;}
.source-text{padding:12px 14px;border:1px solid var(--border);border-radius:7px;background:#fff;white-space:pre-wrap;}.source-empty,.source-panel-empty{color:var(--muted);}
.source-narrative{margin:-10px 0 18px;padding:11px 13px;border:1px solid #c9d9d4;border-left:4px solid var(--accent);border-radius:7px;background:#f7fbfa;}.source-narrative-head{display:flex;align-items:center;gap:7px;margin-bottom:5px;color:var(--muted);font-size:10px;font-weight:900;}.source-narrative-marker{padding:1px 6px;border-radius:999px;background:var(--accent-dim);color:var(--accent);}.source-narrative p{margin:0;white-space:pre-wrap;}.source-narrative-actions{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px;}.source-narrative-reference{padding:4px 8px;border:1px solid var(--accent);border-radius:999px;background:#fff;color:var(--accent);font-size:10px;font-weight:900;cursor:pointer;}.source-narrative-reference:hover{background:var(--accent-dim);}
.source-cell{position:relative;}.cell-check{cursor:help;}.cell-matched{box-shadow:inset 0 0 0 3px var(--ok);}.cell-explained{box-shadow:inset 0 0 0 3px var(--explained);}
.cell-gap{box-shadow:inset 0 0 0 3px var(--warn);}.cell-uncertain{box-shadow:inset 0 0 0 2px var(--uncertain);}
.cell-check-count,.cell-reconciliation-count{display:inline-flex;align-items:center;margin-left:6px;padding:1px 6px;border-radius:999px;font-size:9px;font-weight:900;white-space:nowrap;vertical-align:middle;}.cell-check-count{background:var(--sidebar);color:#fff;}.cell-reconciliation-count{background:var(--accent);color:#fff;}
.cell-tooltip{position:absolute;left:8px;top:calc(100% - 3px);z-index:30;display:none;width:320px;max-width:40vw;padding:10px 12px;border:1px solid var(--border);border-radius:7px;background:#fff;box-shadow:0 12px 30px rgba(15,23,42,.16);text-align:left;white-space:normal;color:var(--text);}
.cell-tooltip-item{display:grid;gap:3px;padding:5px 0;}.cell-tooltip-item+.cell-tooltip-item{border-top:1px solid var(--border);}.cell-tooltip-item span{font-size:11px;color:var(--muted);}
.cell-check:hover .cell-tooltip,.cell-check:focus .cell-tooltip{display:block;}[data-open-drawer]{cursor:pointer;}.cell-reconciliation:not(.cell-check){background:linear-gradient(to top,var(--accent-dim) 0 4px,transparent 4px);}.cell-reconciliation:not(.cell-check):hover,.cell-reconciliation:not(.cell-check):focus{outline:2px solid var(--accent);outline-offset:-2px;}
.table-drawer-badge{padding:3px 7px;border:1px solid var(--accent);border-radius:5px;background:#fff;color:var(--accent);font-size:10px;font-weight:800;cursor:pointer;}
.reconciliation-drawer{height:calc(100vh - 76px);overflow:auto;border-left:1px solid var(--border);background:#fff;padding-bottom:24px;}
.drawer-header{position:sticky;top:0;z-index:10;display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:16px;border-bottom:1px solid var(--border);background:#fff;}
.drawer-header h2{margin:2px 0 0;font-size:18px;}.drawer-close{padding:5px 8px;border:1px solid var(--border);border-radius:5px;background:#fff;color:var(--muted);cursor:pointer;}
.drawer-filters{display:flex;gap:6px;padding:12px 16px;border-bottom:1px solid var(--border);}.drawer-filters button{padding:5px 9px;border:1px solid var(--border);border-radius:999px;background:#fff;color:var(--muted);font-size:11px;cursor:pointer;}
.drawer-filters button[aria-pressed="true"]{border-color:var(--accent);color:var(--accent);font-weight:900;}.drawer-empty{padding:28px 20px;color:var(--muted);}.drawer-empty strong{display:block;color:var(--text);font-size:15px;}.drawer-empty p{margin:6px 0 0;}
.drawer-navigation{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:8px;padding:8px 16px;border-bottom:1px solid var(--border);}.drawer-navigation button{padding:5px 8px;border:1px solid var(--border);border-radius:5px;background:#fff;color:var(--accent);cursor:pointer;}.drawer-navigation span{text-align:center;color:var(--muted);font-size:11px;font-weight:700;}
.drawer-item{padding:16px;}.drawer-group{margin-bottom:5px;color:var(--accent);font-size:10px;font-weight:900;letter-spacing:.02em;}.drawer-result-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;}.drawer-result-head h3{margin:0;font-size:16px;}
.drawer-result-meta{margin:4px 0 0;color:var(--muted);font-size:11px;}.drawer-completeness-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:8px;}.drawer-completeness-head h4{margin:0;}.drawer-completeness-head strong{font-size:11px;color:var(--text);}.drawer-note-roles{display:grid;gap:7px;}.drawer-note-role{display:grid;grid-template-columns:auto 1fr;align-items:center;gap:8px;padding:8px 9px;border:1px solid var(--border);border-radius:6px;background:var(--surface-2);}.drawer-note-role>span:first-child{padding:2px 6px;border-radius:999px;background:var(--accent-dim);color:var(--accent);font-size:10px;font-weight:900;}.drawer-note-role strong{font-size:12px;}.drawer-note-role-attention>span:first-child{background:var(--warn-dim);color:var(--warn);}
.drawer-status{flex:0 0 auto;max-width:190px;padding:3px 7px;border-radius:4px;background:var(--surface-3);font-size:10px;font-weight:900;line-height:1.4;text-align:right;white-space:normal;}.status-unexplained_gap{background:var(--warn-dim);color:var(--warn);}.status-matched{background:var(--ok-dim);color:var(--ok);}
.drawer-amounts{display:grid;grid-template-columns:1fr;gap:6px;margin:14px 0;}.drawer-amounts div{display:flex;align-items:baseline;justify-content:space-between;gap:12px;padding:9px 11px;border:1px solid var(--border);border-radius:6px;background:var(--surface-2);min-width:0;}
.drawer-amounts dt{color:var(--muted);font-size:11px;}.drawer-amounts dd{margin:0;white-space:nowrap;font-size:14px;font-weight:900;font-variant-numeric:tabular-nums;}
.drawer-section{padding:12px 0;border-top:1px solid var(--border);}.drawer-section h4{margin:0 0 5px;font-size:11px;color:var(--muted);}.drawer-section p{margin:0;}
.drawer-next{margin:0 -8px;padding:12px 8px;border-radius:6px;background:var(--warn-dim);border-top:0;}.drawer-sources{display:grid;gap:6px;}
.drawer-source{padding:7px 8px;border:1px solid var(--border);border-radius:5px;background:#fff;color:var(--accent);text-align:left;cursor:pointer;}.drawer-source:hover{background:var(--accent-dim);}.drawer-source-prior,.drawer-source-context{display:block;padding:7px 8px;border:1px solid var(--border);border-radius:5px;background:var(--surface-2);color:var(--text);font-size:11px;}.drawer-source-prior{border-style:dashed;color:var(--muted);}.drawer-source-unavailable{color:var(--muted);font-size:11px;}
.drawer-note-location-existence{border-color:#86c7a6;background:#edf9f2;color:#17663a;}.drawer-note-location-existence:hover{background:#dff3e8;}
.drawer-note-location-completeness{border-color:#e6a09b;background:#fff0ef;color:#a4312b;}.drawer-note-location-completeness:hover{background:#ffe2df;}
.cell-flash{outline:3px solid #2563eb!important;background:#dbeafe!important;transition:background .2s,outline .2s;}
@media print{body{min-width:0;background:#fff;}.workbench-header{position:static;}.audit-workbench{display:block;height:auto;min-width:0;}.source-nav,.reconciliation-drawer,.export-button{display:none!important;}.source-stage{height:auto;overflow:visible;padding:0;}.source-panel{display:block!important;break-before:page;padding:16px;}.source-panel:first-child{break-before:auto;}.source-table-scroll{overflow:visible;}thead{display:table-header-group;}}
</style>"""


# ── CSS ───────────────────────────────────────────────────────────────────────

def _inline_css() -> str:
    return """<style>
:root {
  --bg:#f5f7f6; --surface:#ffffff; --surface-2:#eef3f2; --surface-3:#f8faf9;
  --border:#d7e0df; --text:#12201f; --muted:#657574;
  --accent:#0f766e; --accent-dim:#dff3ef;
  --warn:#b7791f; --warn-dim:#fff4ce;
  --ok:#12805c; --ok-dim:#dff6ec;
  --down:#b42318; --down-dim:#fdecea;
  --sidebar-bg:#143431; --sidebar-text:#b7c8c5;
  --sidebar-active:#ffffff; --sidebar-accent:#35c1a7;
  --font:Pretendard,ui-sans-serif,system-ui,-apple-system,sans-serif;
}
*{box-sizing:border-box;margin:0;padding:0;}
body{font-family:var(--font);background:var(--bg);color:var(--text);font-size:13px;line-height:1.6;letter-spacing:0;}
.shell{display:grid;grid-template-columns:258px minmax(0,1fr);min-height:100vh;}
aside{background:var(--sidebar-bg);border-right:1px solid rgba(255,255,255,.08);padding:18px 0;position:sticky;top:0;height:100vh;overflow-y:auto;}
.sidebar-brand{padding:0 16px 14px;border-bottom:1px solid rgba(255,255,255,.08);margin-bottom:8px;}
.sidebar-brand-name{font-size:13px;font-weight:800;color:var(--sidebar-active);}
.sidebar-brand-sub{font-size:11px;color:#7fa09b;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.sidebar-section{padding:10px 16px 4px;font-size:10px;font-weight:800;color:#7fa09b;text-transform:uppercase;letter-spacing:.06em;}
.nav-item{display:flex;align-items:center;gap:8px;padding:7px 16px;font-size:12px;font-weight:500;color:var(--sidebar-text);cursor:pointer;border-left:3px solid transparent;}
.nav-item:hover,.nav-item.active{background:rgba(255,255,255,.05);color:var(--sidebar-active);}
.nav-item.active{background:rgba(53,193,167,.16);border-left-color:var(--sidebar-accent);font-weight:800;}
.nav-badge{margin-left:auto;font-size:10px;padding:1px 5px;border-radius:3px;font-weight:700;}
.nb-ok{background:rgba(18,128,92,.22);color:#8be1c0;}
.nb-warn{background:rgba(183,121,31,.24);color:#ffd37a;}
.nb-unc{background:rgba(183,200,197,.16);color:#c5d2d0;}
.sidebar-divider{border:none;border-top:1px solid rgba(255,255,255,.06);margin:8px 0;}
main{padding:24px 30px;min-width:0;}
.report-masthead{display:flex;align-items:flex-end;justify-content:space-between;gap:18px;margin-bottom:16px;}
.report-kicker{font-size:11px;font-weight:900;color:var(--accent);letter-spacing:.08em;}
.report-id h1{font-size:24px;line-height:1.25;margin-top:2px;}
.report-meta{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;color:var(--muted);font-size:12px;}
.report-meta span{display:inline-flex;align-items:center;min-height:22px;padding:1px 8px;border:1px solid var(--border);border-radius:5px;background:var(--surface);}
.report-focus{display:flex;align-items:center;gap:10px;padding:10px 12px;border:1px solid var(--border);border-radius:8px;background:var(--surface);}
.focus-number{font-size:26px;font-weight:900;color:var(--warn);font-variant-numeric:tabular-nums;}
.focus-label{font-size:12px;font-weight:900;}
.focus-sub{font-size:11px;color:var(--muted);white-space:nowrap;}
.panel{margin-bottom:32px;}
.panel.hidden{display:none;}
.panel-title{font-size:16px;font-weight:900;margin-bottom:2px;}
.panel-sub{font-size:12px;color:var(--muted);margin-bottom:16px;}
.progress-diag{font-weight:700;color:var(--muted);}
.progress-diag.warn{color:var(--warn);}
button.progress-diag{font:inherit;border:0;background:transparent;padding:0;cursor:pointer;text-decoration:underline dotted;}
.empty-state{color:var(--muted);font-size:12px;padding:12px 0;}
.verdict-banner{padding:18px 30px;border:1px solid var(--border);border-width:1px 0;margin:0 -30px 24px;background:var(--surface);}
.verdict-banner.verdict-ok{border-color:#bbf7d0;background:var(--ok-dim);}
.verdict-banner.verdict-warn{border-color:#fde68a;background:var(--warn-dim);}
.verdict-banner.verdict-unc{border-color:var(--border);background:var(--surface-3);}
.verdict-head{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;margin-bottom:14px;}
.verdict-label{font-size:18px;font-weight:900;line-height:1.25;}
.verdict-sub{margin-top:4px;color:var(--muted);font-size:12px;}
.summary-action{font:inherit;font-size:12px;font-weight:800;border:1px solid #98cfc7;background:#fff;color:var(--accent);border-radius:6px;padding:7px 10px;cursor:pointer;white-space:nowrap;}
.summary-action:hover{background:var(--accent-dim);}
.kpi-strip{display:grid;grid-template-columns:repeat(6,minmax(92px,1fr));gap:10px;margin-top:10px;}
.kpi-tile{background:#fff;border:1px solid var(--border);border-radius:7px;padding:10px 12px;min-width:0;}
.kpi-val{font-size:22px;font-weight:800;}
.kpi-name{font-size:11px;color:var(--muted);}
.kpi-tile.kpi-ok .kpi-val{color:var(--ok);}
.kpi-tile.kpi-exp .kpi-val{color:var(--accent,#1f6feb);}
.kpi-tile.kpi-warn .kpi-val{color:var(--warn);}
.kpi-tile.kpi-unc .kpi-val{color:var(--muted);}
.kpi-tile.kpi-nt .kpi-val{color:#b7791f;}
.dashboard-card-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin-top:12px;}
.dash-card{font:inherit;text-align:left;display:grid;grid-template-columns:auto 1fr;gap:0 10px;align-items:center;border:1px solid var(--border);border-radius:7px;background:#fff;padding:11px 12px;cursor:pointer;min-height:76px;}
.dash-card:hover{border-color:#9fd3ca;background:#fbfefd;}
.pc-value{grid-row:span 2;font-size:22px;font-weight:900;font-variant-numeric:tabular-nums;}
.pc-label{font-size:12px;font-weight:900;}
.pc-copy{font-size:11px;color:var(--muted);}
.dc-attention .pc-value,.dc-next .pc-value{color:var(--warn);}
.dc-progress .pc-value{color:var(--ok);}
.dc-source .pc-value,.dc-note .pc-value{color:var(--accent);}
.statement-wrap{border:1px solid var(--border);border-radius:8px;overflow:hidden;margin-bottom:16px;}
.statement-caption{padding:9px 16px;background:var(--surface-2);border-bottom:1px solid var(--border);font-size:12px;font-weight:700;color:var(--muted);}
.fs-table{width:100%;border-collapse:collapse;font-size:12px;}
.fs-table th{padding:7px 12px;background:var(--surface-2);border-bottom:1px solid var(--border);font-size:11px;font-weight:800;color:var(--muted);text-align:right;}
.fs-table th:first-child{text-align:left;}
.fs-table td{padding:7px 12px;border-bottom:1px solid var(--border);text-align:right;font-variant-numeric:tabular-nums;}
.fs-table td:first-child{text-align:left;}
.fs-table tr:last-child td{border-bottom:none;}
.source-table-scroll{overflow-x:auto;overflow-y:visible;border:1px solid var(--border);border-radius:8px;background:#fff;margin-bottom:16px;}
.source-table{width:100%;min-width:max-content;border-collapse:collapse;font-size:12px;}
.source-table th,.source-table td{position:relative;padding:8px 12px;border:1px solid var(--border);font-variant-numeric:tabular-nums;white-space:nowrap;}
.source-table th{background:var(--surface-2);font-size:11px;font-weight:800;color:var(--muted);text-align:center;}
.source-table td{text-align:right;}
.source-table td:first-child{text-align:left;}
.source-cell{position:relative;}
.cell-check{outline-offset:-3px;cursor:help;}
.cell-matched{outline:3px solid #16825d;}
.cell-explained{outline:3px solid #0f766e;}
.cell-gap{outline:3px solid #c26a16;}
.cell-uncertain{outline:2px dashed #64748b;outline-offset:-2px;}
.cell-check-count{position:absolute;top:3px;right:3px;min-width:18px;height:18px;border-radius:9px;background:#163a34;color:#fff;font-size:10px;display:grid;place-items:center;}
.cell-tooltip{position:absolute;left:8px;top:calc(100% - 4px);z-index:20;display:none;width:320px;max-width:40vw;padding:10px 12px;border:1px solid var(--border);border-radius:7px;background:#fff;box-shadow:0 12px 30px rgba(15,23,42,.16);text-align:left;white-space:normal;color:var(--text);}
.cell-tooltip-item{display:grid;gap:3px;padding:5px 0;}
.cell-tooltip-item+ .cell-tooltip-item{border-top:1px solid var(--border);}
.cell-tooltip-item span{font-size:11px;color:var(--muted);}
.cell-check:hover .cell-tooltip,.cell-check:focus .cell-tooltip{display:block;}
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
.method-line{margin:10px 0 2px;padding:8px 10px;border-left:3px solid var(--accent);background:var(--surface-2);font-size:11px;font-weight:700;color:var(--text);}
.check-summary{border:1px solid var(--border);border-radius:8px;overflow:hidden;margin-top:8px;}
.check-summary-head{padding:9px 14px;background:var(--surface-2);border-bottom:1px solid var(--border);font-size:11px;font-weight:700;color:var(--muted);}
.check-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:8px 14px;border-bottom:1px solid var(--border);font-size:12px;cursor:pointer;}
.check-row:last-child{border-bottom:none;}
.check-row:hover{background:var(--surface);}
.check-name{flex:1 1 220px;min-width:0;}
.check-vals{display:flex;gap:14px;flex:0 1 auto;flex-wrap:wrap;font-variant-numeric:tabular-nums;color:var(--muted);font-size:11px;}
.badge{display:inline-flex;align-items:center;padding:2px 7px;border-radius:4px;font-size:11px;font-weight:700;}
.badge-ok{background:var(--ok-dim);color:#166534;}
.badge-warn{background:var(--warn-dim);color:#92400e;}
.badge-unc{background:var(--surface-2);color:var(--muted);}
.expand-tri{font-size:9px;color:var(--muted);transition:transform .15s;display:inline-block;}
.diag-card{border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:12px;background:var(--surface);}
.diag-title{font-size:13px;font-weight:800;margin-bottom:8px;}
.diag-reason{margin-bottom:10px;padding:8px 10px;border-left:3px solid var(--warn);background:var(--warn-dim);font-size:12px;}
.diag-candidates{list-style:none;margin:0;font-size:11px;color:var(--muted);}
.diag-candidates li{display:flex;gap:8px;padding:7px 0;border-bottom:1px solid var(--border);}
.diag-candidates li:last-child{border-bottom:0;}
.diag-candidates strong{flex:0 0 auto;color:var(--text);}
.diag-guide{margin-top:10px;padding-top:8px;border-top:1px solid var(--border);font-size:11px;color:var(--muted);}
.acct-state{font-size:10px;font-weight:700;padding:1px 6px;border-radius:3px;border:1px solid var(--border);white-space:nowrap;}
.as-ok{color:var(--ok);} .as-warn{color:var(--warn);} .as-unc{color:var(--muted);} .as-nt{color:#94a3b8;}
.state-col{width:64px;text-align:center;}
.src-jump{color:var(--accent);cursor:pointer;text-decoration:underline dotted;}
.dd-breakdown{margin:8px 0;padding:8px;border:1px solid var(--border);border-radius:6px;}
.dd-bd-head{font-size:11px;font-weight:700;color:var(--muted);margin-bottom:4px;}
.dd-bd-sum{font-size:12px;font-weight:700;margin-top:4px;}
.cell-flash{outline:2px solid var(--accent);background:var(--accent-dim);transition:background .3s,outline .3s;}
.reader-brief{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:14px;}
.rb-item{background:#fff;border:1px solid var(--border);border-radius:7px;padding:10px 12px;}
.rb-k{font-size:10px;font-weight:800;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px;}
.rb-v{font-size:12px;line-height:1.55;}
.side-nav{display:block;}
.filter-pills{display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;}
.filter-pills button{font:inherit;font-size:11px;padding:4px 11px;border:1px solid var(--border);background:#fff;color:var(--muted);border-radius:999px;cursor:pointer;}
.filter-pills button[aria-pressed="true"]{border-color:var(--accent);color:var(--accent);font-weight:700;}
.next-actions{margin:4px 0 0 18px;font-size:12px;line-height:1.7;}
.next-actions li{margin-bottom:6px;}
.legend-group{border:1px solid var(--border);border-radius:8px;background:var(--surface);margin-bottom:12px;overflow:hidden;}
.legend-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;background:var(--surface-2);padding:9px 12px;border-bottom:1px solid var(--border);}
.legend-title{font-size:12px;font-weight:900;}
.legend-counts{font-size:11px;color:var(--muted);text-align:right;}
.legend-methods{list-style:none;}
.legend-methods li{display:block;padding:10px 12px;border-bottom:1px solid var(--border);font-size:11px;line-height:1.55;}
.legend-methods li:last-child{border-bottom:none;}
.legend-methods strong{display:block;margin-bottom:2px;color:var(--text);}
.check-row[hidden]{display:none;}
@media (max-width: 980px){
  .shell{grid-template-columns:1fr;}
  aside{position:relative;height:auto;max-height:30vh;border-right:none;border-bottom:1px solid rgba(255,255,255,.08);}
  main{padding:18px 16px;}
  .verdict-banner{margin:0 -16px 24px;padding:18px 16px;}
  .side-nav{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));}
  .report-masthead,.verdict-head{align-items:stretch;flex-direction:column;}
  .report-focus{align-self:flex-start;}
  .kpi-strip{grid-template-columns:repeat(3,minmax(0,1fr));}
  .dashboard-card-grid{grid-template-columns:repeat(2,minmax(0,1fr));}
  .reader-brief{grid-template-columns:1fr;}
  .check-row{align-items:flex-start;}
  .statement-wrap{overflow:auto;}
}
@media print{
  .shell{display:block;}
  aside,.filter-pills,.expand-tri{display:none;}
  main{padding:0;}
  .panel.hidden{display:block!important;}
  .dd-inline{display:block!important;}
  thead{display:table-header-group;}
  tr,figure,.statement-wrap,.check-summary,.panel{break-inside:avoid;}
  .reader-brief{grid-template-columns:1fr;}
}
</style>"""


def _workbench_js() -> str:
    return """<script>
(function(){
  var lastDrawerTrigger = null;
  var activeDrawerCategory = 'all';
  function activeReportScope() {
    return document.body.getAttribute('data-active-report-scope') || 'all';
  }
  function announceWorkbench(message) {
    var status = document.getElementById('workbench-status');
    if (status) status.textContent = message;
  }
  function activatePanel(panelId, options) {
    var settings = Object.assign({
      preserveDrawer: false,
      resetScroll: true,
      focusHeading: true
    }, options || {});
    var activePanel = null;
    document.querySelectorAll('.source-panel[id]').forEach(function(panel) {
      panel.hidden = panel.id !== panelId;
      if (!panel.hidden) activePanel = panel;
    });
    document.querySelectorAll('[data-source-panel]').forEach(function(button) {
      var active = button.getAttribute('data-source-panel') === panelId;
      button.classList.toggle('active', active);
      if (active) button.setAttribute('aria-current', 'page');
      else button.removeAttribute('aria-current');
    });
    if (!settings.preserveDrawer) {
      activeDrawerCategory = 'all';
      syncResultFilterButtons();
      closeDrawer(false);
    }
    var stage = document.querySelector('.source-stage');
    if (settings.resetScroll && stage) stage.scrollTop = 0;
    var heading = activePanel && activePanel.querySelector('.source-panel-heading h2');
    if (settings.focusHeading && heading) heading.focus();
    if (heading) announceWorkbench(heading.textContent + ' 원문을 열었습니다.');
    if (activePanel) {
      activePanel.querySelectorAll('[data-horizontal-scroll]').forEach(updateHorizontalScrollCue);
    }
  }
  function activateReportScope(scope, options) {
    var settings = Object.assign({initial:false}, options || {});
    document.body.setAttribute('data-active-report-scope', scope);
    document.querySelectorAll('[data-report-scope]').forEach(function(button) {
      button.setAttribute('aria-pressed', button.getAttribute('data-report-scope') === scope ? 'true' : 'false');
    });
    document.querySelectorAll('[data-scope-view]:not([data-drawer-item])').forEach(function(item) {
      item.hidden = item.getAttribute('data-scope-view') !== scope;
    });
    activeDrawerCategory = 'all';
    syncResultFilterButtons();
    var first = document.querySelector('[data-source-panel][data-scope-view="' + scope + '"]');
    if (first) activatePanel(first.getAttribute('data-source-panel'), {focusHeading:!settings.initial});
    announceWorkbench((scope === 'consolidated' ? '연결' : '별도') + ' 보고서 범위를 선택했습니다.');
  }
  document.querySelectorAll('[data-report-scope]').forEach(function(button) {
    button.addEventListener('click', function() {
      activateReportScope(button.getAttribute('data-report-scope'));
    });
  });
  document.querySelectorAll('[data-source-panel]').forEach(function(button) {
    button.addEventListener('click', function() {
      activatePanel(button.getAttribute('data-source-panel'));
    });
  });
  function syncResultFilterButtons() {
    document.querySelectorAll('[data-result-filter]').forEach(function(button) {
      button.setAttribute(
        'aria-pressed',
        button.getAttribute('data-result-filter') === activeDrawerCategory ? 'true' : 'false'
      );
    });
  }
  function syncDrawerCategory(target) {
    activeDrawerCategory = target.getAttribute('data-drawer-category') || 'all';
    syncResultFilterButtons();
  }
  function openDrawer(index, trigger, keepCategory) {
    var target = document.querySelector('[data-drawer-item="' + index + '"]');
    if (!target) return;
    if (target.getAttribute('data-scope-view') !== activeReportScope()) return;
    if (!keepCategory) syncDrawerCategory(target);
    lastDrawerTrigger = trigger || document.activeElement;
    document.querySelectorAll('[data-drawer-item]').forEach(function(item) {
      item.hidden = item !== target;
    });
    var empty = document.querySelector('[data-drawer-empty]');
    if (empty) empty.hidden = true;
    var title = document.getElementById('drawer-title');
    updateDrawerPosition(target);
    if (title) title.focus();
  }
  function drawerItems() {
    return Array.prototype.slice.call(
      document.querySelectorAll('[data-drawer-item][data-scope-view="' + activeReportScope() + '"]')
    ).filter(function(item) {
      if (activeDrawerCategory === 'all') return true;
      return item.getAttribute('data-drawer-category') === activeDrawerCategory;
    });
  }
  function updateDrawerPosition(target) {
    var items = drawerItems();
    var position = document.querySelector('[data-drawer-position]');
    if (!position) return;
    var index = items.indexOf(target);
    position.textContent = index >= 0 ? (index + 1) + ' / ' + items.length : '결과를 선택하세요';
  }
  document.querySelectorAll('[data-open-drawer]').forEach(function(trigger) {
    trigger.addEventListener('click', function(event) {
      event.stopPropagation();
      openDrawer(trigger.getAttribute('data-open-drawer'), trigger);
    });
    trigger.addEventListener('keydown', function(event) {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        openDrawer(trigger.getAttribute('data-open-drawer'), trigger);
      }
    });
  });
  function moveDrawer(direction) {
    var items = drawerItems();
    if (!items.length) return;
    var current = items.findIndex(function(item) { return !item.hidden; });
    var next = current < 0 ? 0 : (current + direction + items.length) % items.length;
    openDrawer(items[next].getAttribute('data-drawer-item'), document.activeElement, true);
  }
  var drawerPrev = document.querySelector('[data-drawer-prev]');
  var drawerNext = document.querySelector('[data-drawer-next]');
  if (drawerPrev) drawerPrev.addEventListener('click', function(){ moveDrawer(-1); });
  if (drawerNext) drawerNext.addEventListener('click', function(){ moveDrawer(1); });
  function closeDrawer(restoreFocus) {
    document.querySelectorAll('[data-drawer-item]').forEach(function(item) { item.hidden = true; });
    var empty = document.querySelector('[data-drawer-empty]');
    if (empty) empty.hidden = false;
    updateDrawerPosition(null);
    if (restoreFocus && lastDrawerTrigger && typeof lastDrawerTrigger.focus === 'function') lastDrawerTrigger.focus();
  }
  var close = document.querySelector('[data-close-drawer]');
  if (close) close.addEventListener('click', function() { closeDrawer(true); });
  function setDrawerCategory(category, trigger) {
    activeDrawerCategory = category || 'all';
    syncResultFilterButtons();
    var items = drawerItems();
    if (!items.length) {
      closeDrawer(false);
      announceWorkbench('해당 결과가 없습니다.');
      return;
    }
    openDrawer(items[0].getAttribute('data-drawer-item'), trigger, true);
  }
  document.querySelectorAll('[data-result-filter]').forEach(function(button) {
    button.addEventListener('click', function() {
      setDrawerCategory(button.getAttribute('data-result-filter'), button);
    });
  });
  document.querySelectorAll('[data-source-jump]').forEach(function(button) {
    button.addEventListener('click', function() {
      var panelId = button.getAttribute('data-jump-panel');
      activatePanel(panelId, {preserveDrawer:true, resetScroll:false, focusHeading:false});
      var panel = document.getElementById(panelId);
      if (!panel) return;
      var cellKey = button.getAttribute('data-jump-cell');
      var rowKey = button.getAttribute('data-jump-row');
      var blockKey = button.getAttribute('data-jump-block');
      var target = null;
      if (blockKey) target = panel.querySelector('[data-source-block="' + blockKey + '"]');
      if (cellKey) {
        target = panel.querySelector('[data-cell="' + cellKey + '"]')
          || panel.querySelector('[data-cell-coverage~="' + cellKey + '"]');
      }
      if (!target && rowKey) target = panel.querySelector('[data-row="' + rowKey + '"]');
      if (!target) target = panel.querySelector('.source-table-caption,.source-panel-heading');
      if (target) {
        target.scrollIntoView({block:'center',inline:'center'});
        target.classList.add('cell-flash');
        setTimeout(function(){ target.classList.remove('cell-flash'); }, 2000);
      }
    });
  });
  function updateHorizontalScrollCue(container) {
    var scrollable = container.scrollWidth > container.clientWidth + 2;
    var atEnd = !scrollable || container.scrollLeft + container.clientWidth >= container.scrollWidth - 2;
    container.classList.toggle('is-scrollable', scrollable);
    container.classList.toggle('is-scroll-end', atEnd);
  }
  document.querySelectorAll('[data-horizontal-scroll]').forEach(function(container) {
    updateHorizontalScrollCue(container);
    container.addEventListener('scroll', function() { updateHorizontalScrollCue(container); });
  });
  window.addEventListener('resize', function() {
    document.querySelectorAll('[data-horizontal-scroll]').forEach(updateHorizontalScrollCue);
  });
  var printButton = document.querySelector('[data-print-report]');
  if (printButton) printButton.addEventListener('click', function(){ window.print(); });
  activateReportScope(activeReportScope(), {initial:true});
})();
</script>"""


# ── JS micro-runtime ───────────────────────────────────────────────────────────

def _inline_js() -> str:
    return """<script>
(function(){
  var navItems = document.querySelectorAll('.nav-item[data-target]');
  var panels = document.querySelectorAll('.panel');
  navItems.forEach(function(item){
    item.addEventListener('click', function(){
      var target = item.getAttribute('data-target');
      navItems.forEach(function(n){ n.classList.remove('active'); n.removeAttribute('aria-current'); });
      item.classList.add('active');
      item.setAttribute('aria-current', 'page');
      panels.forEach(function(p){
        p.classList.toggle('hidden', p.id !== target);
      });
      var tp = document.getElementById(target);
      if(tp){ tp.scrollIntoView({behavior:'smooth',block:'start'}); }
    });
  });
  document.querySelectorAll('[data-filter-control]').forEach(function(ctrl){
    var tgt = document.querySelector(ctrl.getAttribute('data-filter-control'));
    if(!tgt) return;
    ctrl.addEventListener('click', function(e){
      var btn = e.target.closest('[data-filter]');
      if(!btn) return;
      var key = btn.getAttribute('data-filter');
      ctrl.querySelectorAll('[data-filter]').forEach(function(b){ b.setAttribute('aria-pressed','false'); });
      btn.setAttribute('aria-pressed','true');
      tgt.querySelectorAll('[data-tags]').forEach(function(row){
        var tags = ' ' + (row.getAttribute('data-tags') || '') + ' ';
        row.hidden = key !== 'all' && tags.indexOf(' ' + key + ' ') < 0;
      });
    });
  });
  document.querySelectorAll('[data-target-inline]').forEach(function(btn){
    btn.addEventListener('click', function(){
      var target = btn.getAttribute('data-target-inline');
      var nav = document.querySelector('.nav-item[data-target="' + target + '"]');
      if(nav){ nav.click(); return; }
      var panel = document.getElementById(target);
      if(!panel) return;
      panels.forEach(function(p){ p.classList.toggle('hidden', p.id !== target); });
      panel.scrollIntoView({behavior:'smooth',block:'start'});
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

function jumpToCell(el){
  var panelId = el.getAttribute('data-jump');
  var cellKey = el.getAttribute('data-jump-cell');
  var nav = document.querySelector('.nav-item[data-target="' + panelId + '"]');
  if(nav){ nav.click(); }
  var panel = document.getElementById(panelId);
  if(!panel) return;
  var cell = panel.querySelector('[data-cell="' + cellKey + '"]')
          || panel.querySelector('[data-row="' + cellKey.replace(/c.*/, '') + '"]');
  if(cell){
    cell.scrollIntoView({behavior:'smooth', block:'center'});
    cell.classList.add('cell-flash');
    setTimeout(function(){ cell.classList.remove('cell-flash'); }, 1200);
  }
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


def _section_tables(section: ReportSection) -> list[ReportTable]:
    return [block.table for block in section.blocks if block.table is not None]


def _status_to_badge_class(status: str) -> str:
    if status == MATCHED:
        return "badge-ok"
    if status == UNEXPLAINED_GAP:
        return "badge-warn"
    return "badge-unc"


def _status_to_badge_label(status: str) -> str:
    icon = {
        MATCHED: "✓",
        EXPLAINABLE_GAP: "◇",
        UNEXPLAINED_GAP: "⚠",
        PARSE_UNCERTAIN: "?",
        NOT_TESTED: "–",
    }.get(status, "?")
    return f"{icon} {check_status_compact_label(status)}"


def _account_state_badge(status: str | None) -> str:
    """Per-account verification-state badge for statement line rows.
    status None => 미검증 (no covering check). Render-derived; never a CheckResult."""
    if status == MATCHED:
        return '<span class="acct-state as-ok">검증완료</span>'
    if status == UNEXPLAINED_GAP:
        return '<span class="acct-state as-warn">검토필요</span>'
    if status == PARSE_UNCERTAIN:
        return '<span class="acct-state as-unc">해석확인필요</span>'
    return '<span class="acct-state as-nt">미검증</span>'
