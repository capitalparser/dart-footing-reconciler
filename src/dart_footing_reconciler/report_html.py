"""Evidence-cockpit HTML renderer for DART audit reconciliation reports.

Public API (backward compatible):
    export_audit_reconciliation_html(report, checks, output_path) -> Path
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from bs4 import BeautifulSoup

from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.checks import (
    CheckEvidence,
    CheckResult,
    MATCHED,
    EXPLAINABLE_GAP,
    UNEXPLAINED_GAP,
    PARSE_UNCERTAIN,
    NOT_TESTED,
)
from dart_footing_reconciler.document import FullReport, ReportSection, ReportTable
from dart_footing_reconciler.label_resolver import _compact
from dart_footing_reconciler.report_qa import (
    QA_FAIL,
    QA_PASS,
    QA_WARN,
    ValidationQAItem,
    ValidationQAReport,
    build_validation_qa_report,
)
from dart_footing_reconciler.review_backlog import ReviewBacklog, ReviewBacklogItem, build_review_backlog
from dart_footing_reconciler.taxonomy import (
    TaxonomyEntry,
    _entry_for_statement_label,
    _matches_any,
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
    prior_report: FullReport | None = None,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    meta = _ReportMeta(
        company=company_name or report.company or "회사",
        period=period_label,
    )
    output.write_text(_build_html(report, checks, meta, prior_report=prior_report), encoding="utf-8")
    return output


class _ReportMeta(NamedTuple):
    company: str
    period: str


class _StatementPanelEntry(NamedTuple):
    section: ReportSection
    kind: str
    label: str
    panel_id: str


class _DisclosureNoteCandidate(NamedTuple):
    section: ReportSection
    evidence: str


class _ReportScopeView(NamedTuple):
    scope: str
    short: str
    label: str
    report: FullReport
    results: list[CheckResult]
    tied: dict[str, list[CheckResult]]
    review_backlog: ReviewBacklog
    validation_qa: ValidationQAReport
    panel_ids: dict[str, str]
    active: bool


class _TotalMark(NamedTuple):
    status: str
    result: CheckResult


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


def _split_source_context(source: str) -> tuple[str, str]:
    if (source or "").startswith("prior:"):
        return "prior", source[len("prior:"):]
    return "current", source or ""


def _is_prior_source(source: str) -> bool:
    return _split_source_context(source)[0] == "prior"


def _parse_section_source(source: str) -> tuple[str, str, int | None] | None:
    """Return (scope, name, block_idx) for section and note-body sources."""
    m = re.match(r"^(statement|note):([^/:]+)(?::block(\d+)|/block:(\d+))?$", source or "")
    if not m:
        return None
    scope, name, block_a, block_b = m.groups()
    block = block_a or block_b
    return (scope, name, int(block) if block is not None else None)


def _parse_period_source(source: str) -> tuple[str, str, str] | None:
    """Return (scope, name, period_tag) for current/comparative note sources."""
    m = re.match(r"^(statement|note):([^/]+)/([A-Za-z_]+)$", source or "")
    if not m:
        return None
    scope, name, period_tag = m.groups()
    if period_tag not in {"current", "comparative", "prior", "beginning", "ending"}:
        return None
    return scope, name, period_tag


def _parse_table_period_source(source: str) -> tuple[str, str, int, str] | None:
    m = re.match(
        r"^(statement|note):([^/]+)/table:(\d+)/(beginning|ending|current|comparative|prior)$",
        source or "",
    )
    if not m:
        return None
    scope, name, table_idx, period_tag = m.groups()
    return scope, name, int(table_idx), period_tag


_SOURCE_PERIOD_LABELS = {
    "current": "당기",
    "comparative": "비교기간",
    "prior": "전기",
    "beginning": "기초",
    "ending": "기말",
}


def _source_table(report: FullReport, scope: str, name: str, t_idx: int) -> ReportTable | None:
    sections = report.statements if scope == "statement" else report.notes
    for s in sections:
        sid_tail = s.section_id.split(":")[-1]
        if (
            name in (sid_tail, s.note_no, s.title)
            or name in s.section_id
            or (scope == "statement" and _statement_kind(s) == _STMT_KEY_ALIASES.get(name, name))
        ):
            for b in s.blocks:
                if b.table is not None and b.table.index == t_idx:
                    return b.table
    return None


def _humanize_source(report: FullReport, source: str) -> str:
    context, source_body = _split_source_context(source)
    table_period_source = _parse_table_period_source(source_body)
    if table_period_source is not None:
        scope, name, _, period_tag = table_period_source
        head = (f"주석{name}" if scope == "note" else _STMT_KEY_LABELS.get(name, name))
        if context == "prior":
            head = f"전기 보고서 {head}"
        return f"{head} · {_SOURCE_PERIOD_LABELS[period_tag]}"
    parsed = _parse_source(source_body)
    if parsed is None:
        section_source = _parse_section_source(source_body)
        period_source = (
            _parse_period_source(source_body)
            if section_source is None
            else None
        )
        if section_source is None and period_source is None:
            return source or "—"
        if section_source is not None:
            scope, name, block_idx = section_source
        else:
            scope, name, period_tag = period_source
            block_idx = None
        head = (f"주석{name}" if scope == "note" else _STMT_KEY_LABELS.get(name, name))
        if context == "prior":
            head = f"전기 보고서 {head}"
        if section_source is None:
            return f"{head} · {_SOURCE_PERIOD_LABELS[period_tag]}"
        if block_idx is None:
            return head
        return f"{head} · 본문 문단 {block_idx + 1}"
    scope, name, t_idx, row, col = parsed
    table = _source_table(report, scope, name, t_idx) if context == "current" else None
    head = (f"주석{name}" if scope == "note" else _STMT_KEY_LABELS.get(name, name))
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


def _source_panel_id(
    scope: str,
    name: str,
    table_idx: int | None = None,
    report: FullReport | None = None,
) -> str:
    if scope == "note":
        if report is not None and table_idx is not None:
            for section in report.notes:
                if not _note_no_matches_ref(section.note_no, name):
                    continue
                for block in section.blocks:
                    if block.table is not None and block.table.index == table_idx:
                        return _note_panel_id(section, report)
        if report is not None:
            matches = [
                section for section in report.notes
                if _note_no_matches_ref(section.note_no, name)
            ]
            if len(matches) == 1:
                return _note_panel_id(matches[0], report)
        return f"panel-note-{name}"
    kind = _STMT_KEY_ALIASES.get(name, name)
    if table_idx is not None and report is not None:
        for entry in _statement_panel_entries(report):
            table = _first_table(entry.section)
            if entry.kind == kind and table is not None and table.index == table_idx:
                return entry.panel_id
    return f"panel-{kind}"


def _report_scope_views(
    report: FullReport,
    results: list[CheckResult],
    *,
    prior_report: FullReport | None = None,
) -> list[_ReportScopeView]:
    scopes = [
        scope for scope in ("consolidated", "separate")
        if _report_has_scope(report, scope)
    ]
    if len(scopes) < 2:
        return []
    views: list[_ReportScopeView] = []
    for idx, scope in enumerate(scopes):
        scoped_report = _report_for_scope(report, scope)
        scoped_results = _filter_results_for_scope(results, report, scope)
        views.append(
            _ReportScopeView(
                scope=scope,
                short=_report_scope_short(scope),
                label=_report_scope_label(scope),
                report=scoped_report,
                results=scoped_results,
                tied=_tie_results(scoped_results),
                review_backlog=build_review_backlog(scoped_report, scoped_results),
                validation_qa=build_validation_qa_report(
                    scoped_report,
                    scoped_results,
                    prior_report=prior_report,
                ),
                panel_ids=_scope_panel_ids(scope),
                active=idx == 0,
            )
        )
    return views


def _report_has_scope(report: FullReport, scope: str) -> bool:
    return any(section.scope == scope for section in report.statements + report.notes)


def _report_for_scope(report: FullReport, scope: str) -> FullReport:
    return FullReport(
        report.source,
        report.company,
        [section for section in report.statements if section.scope == scope],
        [section for section in report.notes if section.scope == scope],
    )


def _report_scope_short(scope: str) -> str:
    return {"consolidated": "con", "separate": "sep"}.get(scope, _safe_id(scope))


def _report_scope_label(scope: str) -> str:
    return {"consolidated": "연결보고서", "separate": "별도보고서"}.get(scope, scope)


def _scope_panel_ids(scope: str) -> dict[str, str]:
    short = _report_scope_short(scope)
    return {
        "summary": f"panel-summary-{short}",
        "progress": f"panel-progress-{short}",
        "attention": f"panel-attention-{short}",
        "next": f"panel-next-{short}",
        "review_backlog": f"panel-review-backlog-{short}",
        "validation_qa": f"panel-validation-qa-{short}",
        "parse_diag": f"panel-parse-diag-{short}",
    }


def _filter_results_for_scope(
    results: list[CheckResult],
    report: FullReport,
    scope: str,
) -> list[CheckResult]:
    return [result for result in results if _result_matches_report_scope(result, report, scope)]


def _result_matches_report_scope(result: CheckResult, report: FullReport, scope: str) -> bool:
    result_scopes: set[str] = set()
    for ev in result.evidence:
        for parsed in _parse_source_refs(ev.source):
            source_scope, _, table_idx, _, _ = parsed
            section = _section_for_source_table(report, source_scope, table_idx)
            if section is not None and section.scope:
                result_scopes.add(section.scope)
    if result_scopes:
        return scope in result_scopes
    return True


def _section_for_source_table(report: FullReport, source_scope: str, table_idx: int) -> ReportSection | None:
    sections = report.statements if source_scope == "statement" else report.notes
    for section in sections:
        for block in section.blocks:
            if block.table is not None and block.table.index == table_idx:
                return section
    return None


_TOTAL_SURFACE_CHECK_TYPES = {
    "total_check",
    "statement_subtotal",
    "note_layout_formula_check",
    "appropriation_formula_check",
}


def _is_total_surface_check(result: CheckResult) -> bool:
    return result.check_type in _TOTAL_SURFACE_CHECK_TYPES or "rollforward" in result.check_type


def _total_status_class(status: str) -> str:
    if status == MATCHED:
        return "total-ok"
    if status == UNEXPLAINED_GAP:
        return "total-warn"
    return "total-unc"


def _total_status_label(status: str) -> str:
    if status == MATCHED:
        return "합계검증 적정"
    if status == UNEXPLAINED_GAP:
        return "합계검증 이상"
    return "합계검증 확인 필요"


def _is_total_mark_target(ev, table: ReportTable, row_idx: int) -> bool:
    if ev.role == "total":
        return True
    if ev.role:
        return False
    if row_idx < 0 or row_idx >= len(table.rows):
        return False
    row = table.rows[row_idx]
    label = " ".join(cell for cell in row[:2] if parse_amount(cell) is None)
    compact = _compact(label)
    if compact in {"계", "합계", "소계", "총계"}:
        return True
    return compact.endswith(("합계", "소계", "총계"))


def _is_total_column_target(table: ReportTable, col_idx: int | None) -> bool:
    if col_idx is None:
        return False
    header_rows = table.rows[: min(4, len(table.rows))]
    for row in header_rows:
        if col_idx >= len(row):
            continue
        cell = row[col_idx]
        if parse_amount(cell) is not None:
            continue
        compact = _compact(cell)
        if compact in {"계", "합계", "소계", "총계"}:
            return True
        if compact.endswith(("합계", "소계", "총계")):
            return True
    return False


def _total_marks_for_table(
    results: list[CheckResult],
    table: ReportTable,
) -> dict[tuple[int, int | None], str]:
    return {
        key: mark.status
        for key, mark in _total_mark_details_for_table(results, table).items()
    }


def _total_mark_details_for_table(
    results: list[CheckResult],
    table: ReportTable,
) -> dict[tuple[int, int | None], _TotalMark]:
    marks: dict[tuple[int, int | None], _TotalMark] = {}
    for result in results:
        if not _is_total_surface_check(result):
            continue
        for ev_idx, ev in enumerate(result.evidence):
            if ev.role == "component":
                continue
            for parsed in _parse_source_refs(ev.source):
                _, _, table_idx, row_idx, col_idx = parsed
                if table_idx != table.index or row_idx is None:
                    continue
                is_total_row = _is_total_mark_target(ev, table, row_idx)
                is_result_target = (
                    _is_total_result_target(result, ev, ev_idx, len(result.evidence))
                    or (
                        ev_idx == 0
                        and result.check_type == "total_check"
                        and _is_total_column_target(table, col_idx)
                    )
                )
                if not (is_total_row or is_result_target):
                    continue
                _set_total_mark(marks, (row_idx, col_idx), result)
                if is_total_row:
                    _set_total_mark(marks, (row_idx, None), result)
    return marks


def _is_total_result_target(
    result: CheckResult,
    ev: CheckEvidence,
    ev_idx: int,
    evidence_count: int,
) -> bool:
    if ev.role == "total":
        return True
    if result.check_type == "note_rollforward_check" and ev.role == "ending":
        return True
    if result.check_type == "prior_column_rollforward":
        return True
    if result.check_type == "appropriation_formula_check" and ev_idx == evidence_count - 1:
        return True
    return (
        result.check_type == "note_layout_formula_check"
        and not ev.role
        and ev_idx == evidence_count - 1
    )


def _set_total_mark(
    marks: dict[tuple[int, int | None], _TotalMark],
    key: tuple[int, int | None],
    result: CheckResult,
) -> None:
    existing = marks.get(key)
    if (
        existing is None
        or _TOTAL_STATUS_SEVERITY.get(result.status, 2)
        > _TOTAL_STATUS_SEVERITY.get(existing.status, 2)
    ):
        marks[key] = _TotalMark(result.status, result)


_TOTAL_STATUS_SEVERITY = {
    MATCHED: 1,
    EXPLAINABLE_GAP: 2,
    NOT_TESTED: 2,
    PARSE_UNCERTAIN: 2,
    UNEXPLAINED_GAP: 3,
}


# ── Build HTML ────────────────────────────────────────────────────────────────

def _build_html(
    report: FullReport,
    results: list[CheckResult],
    meta: _ReportMeta,
    *,
    prior_report: FullReport | None = None,
) -> str:
    scope_views = _report_scope_views(report, results, prior_report=prior_report)
    if scope_views:
        return _build_scope_split_html(report, results, scope_views, meta)

    tied = _tie_results(results)
    uncertain_results = [r for r in results if r.status == PARSE_UNCERTAIN]
    review_backlog = build_review_backlog(report, results)
    validation_qa = build_validation_qa_report(report, results, prior_report=prior_report)

    sidebar_html = _render_sidebar(report, results, tied, review_backlog, validation_qa)
    masthead_html = _render_report_masthead(report, results, meta)
    banner_html = _render_verdict_banner(report, results)

    panels: list[str] = []

    # Cockpit overview views (대시보드 is the banner; these are 진행상황/확인 필요/다음 작업).
    panels.append(_render_progress_panel(report, results, tied))
    panels.append(_render_attention_panel(results, report))
    panels.append(_render_next_actions_panel(results))
    panels.append(_render_review_backlog_panel(review_backlog))
    panels.append(_render_validation_qa_panel(validation_qa))

    for entry in _statement_panel_entries(report):
        panels.append(_render_statement_panel(
            entry.section,
            tied.get(entry.kind, []),
            panel_id=entry.panel_id,
            label=entry.label,
            report=report,
            all_results=results,
        ))

    for section in report.notes:
        note_no = section.note_no or section.section_id
        panels.append(_render_note_panel(
            section, tied.get(f"note:{note_no}", []), panel_id=_note_panel_id(section, report), report=report,
        ))

    if uncertain_results:
        panels.append(_render_parse_uncertain_panel(uncertain_results))

    content = "\n".join(panels)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" href="data:,">
<title>DART 수치검증 — {_esc(meta.company)}</title>
{_inline_css()}
</head>
<body data-cockpit-profile="evidence_cockpit" data-cockpit-shell="side-app">
<div class="shell">
{sidebar_html}
<main id="main-content">
{_render_workpaper_topbar(report, results, meta)}
{_render_workpaper_status_strip(results)}
{masthead_html}
{banner_html}
{content}
</main>
{_render_review_rail()}
</div>
{_inline_js()}
</body>
</html>"""


def _build_scope_split_html(
    report: FullReport,
    results: list[CheckResult],
    scope_views: list[_ReportScopeView],
    meta: _ReportMeta,
) -> str:
    sidebar_html = _render_scope_split_sidebar(report, scope_views)
    content = "\n".join(_render_report_scope_shell(view, meta, report) for view in scope_views)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" href="data:,">
<title>DART 수치검증 — {_esc(meta.company)}</title>
{_inline_css()}
</head>
<body data-cockpit-profile="evidence_cockpit" data-cockpit-shell="side-app" data-active-report-scope="{_esc(scope_views[0].scope)}">
<div class="shell">
{sidebar_html}
<main id="main-content">
{_render_workpaper_topbar(report, results, meta, scope_views)}
{_render_workpaper_status_strip(results)}
{content}
</main>
{_render_review_rail()}
</div>
{_inline_js()}
</body>
</html>"""


def _render_report_scope_shell(
    view: _ReportScopeView,
    meta: _ReportMeta,
    root_report: FullReport,
) -> str:
    panels: list[str] = []
    panel_ids = view.panel_ids
    uncertain_results = [r for r in view.results if r.status == PARSE_UNCERTAIN]
    statement_entries = _statement_panel_entries_for_scope(root_report, view.scope)
    first_statement_target = statement_entries[0].panel_id if statement_entries else None
    first_note_target = (
        _note_panel_id(view.report.notes[0], root_report) if view.report.notes else None
    )

    panels.append(_render_progress_panel(
        view.report,
        view.results,
        view.tied,
        panel_id=panel_ids["progress"],
    ))
    panels.append(_render_attention_panel(
        view.results,
        view.report,
        panel_id=panel_ids["attention"],
    ))
    panels.append(_render_next_actions_panel(view.results, panel_id=panel_ids["next"]))
    panels.append(_render_review_backlog_panel(
        view.review_backlog,
        panel_id=panel_ids["review_backlog"],
    ))
    panels.append(_render_validation_qa_panel(
        view.validation_qa,
        panel_id=panel_ids["validation_qa"],
    ))

    for entry in statement_entries:
        panels.append(_render_statement_panel(
            entry.section,
            view.tied.get(entry.kind, []),
            panel_id=entry.panel_id,
            label=entry.label,
            report=root_report,
            all_results=view.results,
        ))

    for section in view.report.notes:
        note_no = section.note_no or section.section_id
        panels.append(_render_note_panel(
            section,
            view.tied.get(f"note:{note_no}", []),
            panel_id=_note_panel_id(section, root_report),
            report=root_report,
        ))

    if uncertain_results:
        panels.append(_render_parse_uncertain_panel(
            uncertain_results,
            panel_id=panel_ids["parse_diag"],
        ))

    hidden = "" if view.active else " hidden"
    banner_html = _render_verdict_banner(
        view.report,
        view.results,
        panel_id=panel_ids["summary"],
        attention_panel_id=panel_ids["attention"],
        statement_target_id=first_statement_target,
        note_target_id=first_note_target,
    )
    return f"""<section class="report-scope-shell{hidden}" data-report-scope="{_esc(view.scope)}" aria-label="{_esc(view.label)}">
  <div class="scope-shell-kicker">{_esc(view.label)}</div>
  {_render_report_masthead(view.report, view.results, meta)}
  {banner_html}
  {"".join(panels)}
</section>"""


def _render_review_rail() -> str:
    return """<section class="review-rail" id="review-rail" aria-label="검증 상세">
  <div class="review-rail-head">
    <div>
      <div class="review-rail-kicker">검증 상세</div>
      <div class="review-rail-title">선택 항목 대사</div>
    </div>
    <button type="button" class="review-rail-close" onclick="clearReviewRail()">닫기</button>
  </div>
  <div class="review-rail-tabs" aria-label="검증 유형">
    <span>본문대사</span>
    <span>주석대사</span>
    <span>주석간대사</span>
  </div>
  <div class="review-rail-body" id="review-rail-body">
    <div class="review-empty">재무제표 본문이나 주석 검증 항목을 선택하세요.</div>
  </div>
</section>"""


def _render_workpaper_topbar(
    report: FullReport,
    results: list[CheckResult],
    meta: _ReportMeta,
    scope_views: list[_ReportScopeView] | None = None,
) -> str:
    c = _status_counts(results)
    source = Path(report.source).name if report.source else "원문"
    period = meta.period or "보고기간 미상"
    attention = c["gaps"] + c["uncertain"]
    scope_bits = ""
    if scope_views:
        scope_bits = "".join(
            f'<span class="topbar-chip">{_esc(view.label)} {len(view.results)}</span>'
            for view in scope_views
        )
    return f"""<section class="workpaper-topbar" aria-label="작업 보고서">
  <div class="workpaper-title">
    <span class="topbar-kicker">WORKPAPER</span>
    <strong>{_esc(source)}</strong>
    <span>{_esc(period)}</span>
  </div>
  <div class="workpaper-context">
    <span class="topbar-chip">회사: {_esc(meta.company or report.company or "회사")}</span>
    <span class="topbar-chip">전체 {c["total"]}</span>
    <span class="topbar-chip topbar-chip-attn">우선 검토 {attention}</span>
    {scope_bits}
  </div>
  <div class="workpaper-actions" aria-label="작업 도구">
    <button type="button" onclick="jumpToActiveUtilityPanel('attention')">확인 필요</button>
    <button type="button" onclick="jumpToActiveUtilityPanel('progress')">진행상황</button>
    <button type="button" onclick="window.print()">내보내기</button>
  </div>
</section>"""


def _render_workpaper_status_strip(results: list[CheckResult]) -> str:
    c = _status_counts(results)
    attention = c["gaps"] + c["uncertain"]
    tabs = (
        _workpaper_status_tab("progress", "전체", c["total"], active=False)
        + _workpaper_status_tab("attention", "우선 검토", attention, active=attention > 0)
        + _workpaper_status_tab("progress", "검증완료", c["matched"], active=attention == 0)
        + _workpaper_status_tab("attention", "확인필요", attention, active=False)
        + _workpaper_status_tab("progress", "미검증", c["not_tested"], active=False)
    )
    return f"""<section class="workpaper-status-strip" aria-label="상태별 작업 필터">
  <div class="workpaper-status-tabs" role="tablist" aria-label="검증 상태">
    {tabs}
  </div>
  <div class="workpaper-filterbar">
    <label class="workpaper-search">
      <span>검색</span>
      <input type="search" data-workpaper-search placeholder="항목명, 주석, 근거 검색">
    </label>
    <button type="button" class="workpaper-filter-button" onclick="focusWorkbenchSearch()">필터</button>
  </div>
</section>"""


def _workpaper_status_tab(target_key: str, label: str, count: int, active: bool) -> str:
    pressed = "true" if active else "false"
    return f"""<button type="button" class="workpaper-status-tab" aria-pressed="{pressed}" onclick="jumpToActiveUtilityPanel('{_esc(target_key)}')">
      <span>{_esc(label)}</span>
      <strong>{count}</strong>
    </button>"""


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
    <div class="report-kicker">DART VALIDATION</div>
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
      <div class="focus-sub">확인필요 + 파싱 불확실</div>
    </div>
  </div>
</section>"""


# ── Sidebar ───────────────────────────────────────────────────────────────────

def _render_scope_split_sidebar(report: FullReport, scope_views: list[_ReportScopeView]) -> str:
    buttons = "".join(
        f'<button type="button" class="report-scope-button{" active" if view.active else ""}" '
        f'data-report-scope="{_esc(view.scope)}" aria-pressed="{str(view.active).lower()}">'
        f'{_esc(view.label)}</button>'
        for view in scope_views
    )
    navs = "".join(_render_scope_sidebar_nav(view, report) for view in scope_views)
    return f"""<aside>
  <div class="sidebar-brand">
    <div class="sidebar-brand-name">DART 수치 검증</div>
    <div class="sidebar-brand-sub">{_esc(report.company)}</div>
  </div>
  <div class="report-scope-switch" aria-label="보고서 구분">
    {buttons}
  </div>
  {navs}
</aside>"""


def _render_scope_sidebar_nav(view: _ReportScopeView, root_report: FullReport) -> str:
    panel_ids = view.panel_ids
    statement_entries = _statement_panel_entries_for_scope(root_report, view.scope)
    initial_panel_id = statement_entries[0].panel_id if statement_entries else panel_ids["summary"]
    stmt_items = ""
    for entry in statement_entries:
        b = _statement_entry_badge(entry, view.tied.get(entry.kind, []))
        active = entry.panel_id == initial_panel_id
        active_class = " active" if active else ""
        active_aria = ' aria-current="page"' if active else ""
        stmt_items += (
            f'<div class="nav-item{active_class}" data-target="{_esc(entry.panel_id)}"{active_aria}>'
            f'{_esc(entry.label)} {b}</div>\n'
        )

    note_items = ""
    for section in view.report.notes:
        note_no = section.note_no or section.section_id
        b = _note_entry_badge(section, view.tied.get(f"note:{note_no}", []), view.results)
        note_items += (
            f'<div class="nav-item" data-target="{_esc(_note_panel_id(section, root_report))}">'
            f'{_esc(_note_nav_label(section))} {b}'
            f'</div>\n'
        )

    uncertain_count = sum(1 for r in view.results if r.status == PARSE_UNCERTAIN)
    gap_count = sum(1 for r in view.results if r.status == UNEXPLAINED_GAP)
    if gap_count:
        attn_badge = f'<span class="nav-badge nb-warn">⚠ {gap_count}</span>'
    elif uncertain_count:
        attn_badge = f'<span class="nav-badge nb-unc">? {uncertain_count}</span>'
    else:
        attn_badge = '<span class="nav-badge nb-ok">✓</span>'
    backlog_badge = ""
    if view.review_backlog.items:
        backlog_badge = f'<span class="nav-badge nb-unc">{len(view.review_backlog.items)}</span>'
    qa_badge = _validation_qa_nav_badge(view.validation_qa)
    diag_item = ""
    if uncertain_count:
        diag_item = (
            f'<div class="nav-item" data-target="{_esc(panel_ids["parse_diag"])}">'
            f'파싱 진단 <span class="nav-badge nb-unc">? {uncertain_count}</span>'
            f'</div>'
        )
    hidden = "" if view.active else " hidden"
    dashboard_active = initial_panel_id == panel_ids["summary"]
    dashboard_class = " active" if dashboard_active else ""
    dashboard_aria = ' aria-current="page"' if dashboard_active else ""
    return f"""<nav class="side-nav scope-nav{hidden}" data-report-scope="{_esc(view.scope)}" aria-label="{_esc(view.label)}">
  <div class="sidebar-section">재무제표 · {_esc(view.label)}</div>
  {stmt_items}
  <hr class="sidebar-divider">
  <div class="sidebar-section">검증 요약</div>
  <div class="nav-item{dashboard_class}" data-target="{_esc(panel_ids["summary"])}"{dashboard_aria}>대시보드</div>
  <div class="nav-item" data-target="{_esc(panel_ids["progress"])}">진행상황</div>
  <div class="nav-item" data-target="{_esc(panel_ids["attention"])}">확인 필요 {attn_badge}</div>
  <div class="nav-item" data-target="{_esc(panel_ids["next"])}">다음 작업</div>
  <div class="nav-item" data-target="{_esc(panel_ids["review_backlog"])}">검증 고도화 {backlog_badge}</div>
  <div class="nav-item" data-target="{_esc(panel_ids["validation_qa"])}">검증 QA {qa_badge}</div>
  <hr class="sidebar-divider">
  <div class="sidebar-section">근거 · 주석</div>
  {note_items}
  {diag_item}
</nav>"""


def _note_entry_badge(
    section: ReportSection,
    items: list[CheckResult],
    all_results: list[CheckResult],
) -> str:
    section_results = [
        result for result in all_results
        if _result_mentions_any_section_tables(result, [section])
    ]
    merged: list[CheckResult] = []
    seen_ids: set[int] = set()
    for result in items + section_results:
        result_id = id(result)
        if result_id in seen_ids:
            continue
        seen_ids.add(result_id)
        merged.append(result)
    return _scope_note_badge(merged)


def _scope_note_badge(items: list[CheckResult]) -> str:
    if not items:
        return ""
    warn = sum(1 for r in items if r.status == UNEXPLAINED_GAP)
    unc = sum(1 for r in items if r.status == PARSE_UNCERTAIN)
    if warn:
        return f'<span class="nav-badge nb-warn">⚠ {warn}</span>'
    if unc:
        return f'<span class="nav-badge nb-unc">? {unc}</span>'
    return '<span class="nav-badge nb-ok">✓</span>'


def _render_sidebar(
    report: FullReport,
    results: list[CheckResult],
    tied: dict[str, list[CheckResult]],
    review_backlog: ReviewBacklog,
    validation_qa: ValidationQAReport | None = None,
) -> str:
    if validation_qa is None:
        validation_qa = build_validation_qa_report(report, results)
    statement_entries = _statement_panel_entries(report)
    initial_panel_id = statement_entries[0].panel_id if statement_entries else "panel-summary"
    stmt_items = ""
    for entry in statement_entries:
        b = _statement_entry_badge(entry, tied.get(entry.kind, []))
        active = entry.panel_id == initial_panel_id
        active_class = " active" if active else ""
        active_aria = ' aria-current="page"' if active else ""
        stmt_items += (
            f'<div class="nav-item{active_class}" data-target="{_esc(entry.panel_id)}"{active_aria}>'
            f'{_esc(entry.label)} {b}</div>\n'
        )

    note_items = ""
    for section in report.notes:
        note_no = section.note_no or section.section_id
        b = _note_entry_badge(section, tied.get(f"note:{note_no}", []), results)
        note_items += (
            f'<div class="nav-item" data-target="{_esc(_note_panel_id(section, report))}">'
            f'{_esc(_note_nav_label(section))} {b}'
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

    gap_count = sum(1 for r in results if r.status == UNEXPLAINED_GAP)
    if gap_count:
        attn_badge = f'<span class="nav-badge nb-warn">⚠ {gap_count}</span>'
    elif uncertain_count:
        attn_badge = f'<span class="nav-badge nb-unc">? {uncertain_count}</span>'
    else:
        attn_badge = '<span class="nav-badge nb-ok">✓</span>'
    backlog_badge = ""
    if review_backlog.items:
        backlog_badge = f'<span class="nav-badge nb-unc">{len(review_backlog.items)}</span>'
    qa_badge = _validation_qa_nav_badge(validation_qa)
    dashboard_active = initial_panel_id == "panel-summary"
    dashboard_class = " active" if dashboard_active else ""
    dashboard_aria = ' aria-current="page"' if dashboard_active else ""

    return f"""<aside>
  <div class="sidebar-brand">
    <div class="sidebar-brand-name">DART 수치 검증</div>
    <div class="sidebar-brand-sub">{_esc(report.company)}</div>
  </div>
  <nav class="side-nav" aria-label="검토 뷰">
  <div class="sidebar-section">재무제표</div>
  {stmt_items}
  <hr class="sidebar-divider">
  <div class="sidebar-section">검증 요약</div>
  <div class="nav-item{dashboard_class}" data-target="panel-summary"{dashboard_aria}>대시보드</div>
  <div class="nav-item" data-target="panel-progress">진행상황</div>
  <div class="nav-item" data-target="panel-attention">확인 필요 {attn_badge}</div>
  <div class="nav-item" data-target="panel-next">다음 작업</div>
  <div class="nav-item" data-target="panel-review-backlog">검증 고도화 {backlog_badge}</div>
  <div class="nav-item" data-target="panel-validation-qa">검증 QA {qa_badge}</div>
  </nav>
  <hr class="sidebar-divider">
  <div class="sidebar-section">근거 · 주석</div>
  {note_items}
  {diag_item}
</aside>"""


def _statement_panel_entries(report: FullReport) -> list[_StatementPanelEntry]:
    seen: dict[str, int] = {}
    entries: list[_StatementPanelEntry] = []
    for section in report.statements:
        kind = _statement_kind(section)
        if kind is None:
            continue
        table = _first_table(section)
        count = seen.get(kind, 0)
        seen[kind] = count + 1
        panel_id = f"panel-{kind}" if count == 0 else f"panel-{kind}-t{table.index if table else count}"
        entries.append(
            _StatementPanelEntry(
                section=section,
                kind=kind,
                label=_statement_display_label(section, kind),
                panel_id=panel_id,
            )
        )
    return entries


def _statement_panel_entries_for_scope(
    report: FullReport,
    scope: str,
) -> list[_StatementPanelEntry]:
    return [
        entry for entry in _statement_panel_entries(report)
        if entry.section.scope == scope
    ]


def _statement_kind(section: ReportSection) -> str | None:
    for title, kind in (
        ("재무상태표", "bs"),
        ("포괄손익계산서", "oci"),
        ("손익계산서", "is"),
        ("자본변동표", "sce"),
        ("현금흐름표", "cf"),
    ):
        if title in section.title:
            return kind
    return None


def _statement_display_label(section: ReportSection, kind: str) -> str:
    label = _STMT_KEY_LABELS.get(kind, section.title)
    if section.scope == "consolidated":
        return f"{label} (연결)"
    if section.scope == "separate":
        return f"{label} (별도)"
    return label


def _statement_entry_badge(entry: _StatementPanelEntry, results: list[CheckResult]) -> str:
    table = _first_table(entry.section)
    if table is None:
        return ""
    items = [result for result in results if _result_mentions_table(result, table)]
    if not items:
        return ""
    warn = sum(1 for r in items if r.status == UNEXPLAINED_GAP)
    unc = sum(1 for r in items if r.status == PARSE_UNCERTAIN)
    if warn:
        return f'<span class="nav-badge nb-warn">⚠ {warn}</span>'
    if unc:
        return f'<span class="nav-badge nb-unc">? {unc}</span>'
    return '<span class="nav-badge nb-ok">✓</span>'


def _result_mentions_table(result: CheckResult, table: ReportTable) -> bool:
    for ev in result.evidence:
        parsed = _parse_source(ev.source)
        if parsed is not None and parsed[2] == table.index:
            return True
    return False


# ── Verdict Banner ────────────────────────────────────────────────────────────

def _render_verdict_banner(
    report: FullReport,
    results: list[CheckResult],
    *,
    panel_id: str = "panel-summary",
    attention_panel_id: str = "panel-attention",
    statement_target_id: str | None = None,
    note_target_id: str | None = None,
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
        verdict_label = "확인 필요"
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
    status_overview = _render_status_overview(results, report)
    return f"""<section class="panel summary-panel verdict-banner {verdict_class}" id="{_esc(panel_id)}">
  <div class="verdict-head">
    <div>
      <div class="verdict-label">{verdict_label}</div>
      <div class="verdict-sub">{_esc(_verdict_subtitle(c))}</div>
    </div>
    <button class="summary-action" type="button" data-target-inline="{_esc(attention_panel_id)}">확인 필요 보기</button>
  </div>
  {status_overview}
</section>"""


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
        return "불확실 항목 우선 확인"
    if c["not_tested"]:
        return "미검증 범위 확인"
    return "열린 항목 없음"


def _first_statement_target(report: FullReport) -> str:
    entries = _statement_panel_entries(report)
    if entries:
        return entries[0].panel_id
    return "panel-progress"


def _first_note_target(report: FullReport) -> str:
    if not report.notes:
        return "panel-progress"
    return _note_panel_id(report.notes[0], report)


def _note_panel_base_id(section: ReportSection) -> str:
    note_no = section.note_no or section.section_id
    scope_suffix = {"consolidated": "con", "separate": "sep"}.get(section.scope)
    if scope_suffix:
        return f"panel-note-{note_no}-{scope_suffix}"
    return f"panel-note-{note_no}"


def _note_panel_id(section: ReportSection, report: FullReport | None = None) -> str:
    base_id = _note_panel_base_id(section)
    if report is None:
        return base_id
    matches = [
        candidate
        for candidate in report.notes
        if _note_panel_base_id(candidate) == base_id
    ]
    if len(matches) <= 1:
        return base_id
    for idx, candidate in enumerate(matches):
        if candidate is section:
            return base_id if idx == 0 else f"{base_id}-n{idx + 1}"
    for idx, candidate in enumerate(matches):
        if candidate == section:
            return base_id if idx == 0 else f"{base_id}-n{idx + 1}"
    return base_id


def _note_nav_label(section: ReportSection) -> str:
    note_no = section.note_no or section.section_id
    label = f"{note_no}. {section.title}"
    compact_title = _compact(section.title)
    if section.scope == "consolidated" and "연결" not in compact_title:
        return f"{label} (연결)"
    if section.scope == "separate" and "별도" not in compact_title:
        return f"{label} (별도)"
    return label


def _render_status_overview(results: list[CheckResult], report: FullReport) -> str:
    c = _status_counts(results)
    attention = c["gaps"] + c["uncertain"]
    cards = (
        _status_filter_card("matched", "검증완료", c["matched"], attention == 0)
        + _status_filter_card("explained", "설명차이", c["explained"], False)
        + _status_filter_card("attention", "확인필요", attention, attention > 0)
        + _status_filter_card("not_tested", "미검증", c["not_tested"], False)
    )
    default_key = "attention" if attention else "matched"
    rows = "".join(
        _render_status_list_row(result, report, default_key)
        for result in results
    )
    if not rows:
        rows = '<div class="status-list-empty">표시할 검증 항목이 없습니다.</div>'
    return f"""<div class="status-overview" aria-label="현재 상태">
  <div class="status-toolbar">
    <div class="status-card-grid" role="tablist" aria-label="검증 상태">{cards}</div>
    <label class="status-search">
      <span>검색</span>
      <input type="search" data-status-search placeholder="항목명, 주석, 근거 검색">
    </label>
  </div>
  <div class="status-list" aria-label="상태별 검증 항목">
    {rows}
  </div>
</div>"""


def _status_filter_card(key: str, label: str, count: int, active: bool) -> str:
    pressed = "true" if active else "false"
    return f"""<button class="status-card status-{_esc(key)}" type="button" data-status-filter="{_esc(key)}" aria-pressed="{pressed}">
  <span class="status-value">{count}</span>
  <span class="status-label">{_esc(label)}</span>
</button>"""


def _render_status_list_row(
    result: CheckResult,
    report: FullReport,
    default_key: str,
) -> str:
    key = _status_item_key(result.status)
    hidden = "" if key == default_key else " hidden"
    attrs = _jump_attrs_for_result(result, report)
    badge_class = _status_to_badge_class(result.status)
    badge_label = _status_to_badge_label(result.status)
    source = _humanize_source(report, result.evidence[0].source) if result.evidence else "근거 없음"
    diff = f" · 차이 {result.difference:,}" if result.difference is not None else ""
    return f"""<button type="button" class="status-list-row" data-status-item="{_esc(key)}"{hidden} {attrs} onclick="jumpToCheckSource(this)">
  <span class="status-row-main">{_esc(result.title)}</span>
  <span class="status-row-source">{_esc(source)}</span>
  <span class="status-row-diff">{_esc(diff)}</span>
  <span class="badge {badge_class}">{badge_label}</span>
</button>"""


def _status_item_key(status: str) -> str:
    if status == MATCHED:
        return "matched"
    if status == EXPLAINABLE_GAP:
        return "explained"
    if status == NOT_TESTED:
        return "not_tested"
    return "attention"


def _jump_attrs_for_result(result: CheckResult, report: FullReport) -> str:
    for evidence in result.evidence:
        parsed = _parse_source(evidence.source)
        if parsed is None:
            continue
        scope, name, table_idx, row, col = parsed
        panel = _source_panel_id(scope, name, table_idx, report)
        attrs = [
            f'data-jump="{_esc(panel)}"',
            f'data-jump-table="{table_idx}"',
        ]
        if row is not None:
            attrs.append(f'data-jump-cell="r{row}c{col}"' if col is not None else f'data-jump-cell="r{row}"')
        return " ".join(attrs)
    return ""


def _next_action_lines(c: dict[str, int]) -> list[str]:
    lines: list[str] = []
    if c["gaps"]:
        lines.append(f"‘확인 필요’ 화면에서 확인필요 {c['gaps']}건의 차이 원인(재분류·반올림·범위)을 공시 원문과 대조")
    if c["uncertain"]:
        lines.append(f"파싱 불확실 {c['uncertain']}건은 근거 위치를 직접 열어 수치를 확인")
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
    *,
    panel_id: str = "panel-progress",
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
    for label, kind in (("재무상태표", "bs"), ("손익계산서", "is"),
                        ("포괄손익계산서", "oci"), ("자본변동표", "sce"),
                        ("현금흐름표", "cf")):
        rows += _row(label, tied.get(kind, []))
    for section in report.notes:
        note_no = section.note_no or section.section_id
        rows += _row(f"{section.note_no}. {section.title}", tied.get(f"note:{note_no}", []))

    body = (f'<div class="statement-wrap"><table class="fs-table">'
            f'<thead><tr><th>구분</th><th>검증완료</th><th>설명차이</th>'
            f'<th>확인필요</th><th>파싱불확실</th><th>미검증</th><th>전체</th>'
            f'</tr></thead><tbody>{rows}</tbody>'
            f'</table></div>') if rows else '<div class="empty-state">검증 항목이 없습니다.</div>'

    return f"""<div class="panel hidden" id="{_esc(panel_id)}">
  <div class="panel-title">진행상황</div>
  <div class="panel-sub">검증 완료율 {rate} · 미검증 {c['not_tested']}건은 적용 가능한 검증이 없었던 항목입니다.</div>
  {body}
</div>"""


def _render_attention_panel(
    results: list[CheckResult],
    report: FullReport | None = None,
    *,
    panel_id: str = "panel-attention",
) -> str:
    """확인 필요: every unexplained gap and parse-uncertain item consolidated into
    one filterable list, so the auditor does not have to walk every note panel."""
    flagged = [
        r for r in results
        if r.status in (UNEXPLAINED_GAP, PARSE_UNCERTAIN)
        and not _is_total_surface_check(r)
    ]
    if not flagged:
        body = '<div class="empty-state">검토가 필요한 항목이 없습니다.</div>'
    else:
        rows = ""
        detail_prefix = _safe_id(panel_id)
        for idx, r in enumerate(flagged):
            tag = "warn" if r.status == UNEXPLAINED_GAP else "unc"
            badge_class = _status_to_badge_class(r.status)
            badge_label = _status_to_badge_label(r.status)
            dd_id = f"dd-{detail_prefix}-{idx}-{_safe_id(r.check_id)}"
            method_label = _comparison_labels(r)[2]
            value_summary = _render_attention_value_summary(r)
            rows += f"""<div class="check-row attn-row" data-tags="{tag}" onclick="showReview('{dd_id}', this)">
  <span class="expand-tri" id="tri-{dd_id}">▶</span>
  <span class="check-name"><span class="check-kind">{_esc(method_label)}</span><span class="check-title">{_esc(r.title)}</span></span>
  {value_summary}
  <span class="badge {badge_class}">{badge_label}</span>
</div>
<div class="dd-inline" id="{dd_id}">{_render_drilldown(r, report)}</div>"""
        body = f'<div class="check-summary">{rows}</div>'

    return f"""<div class="panel hidden" id="{_esc(panel_id)}">
  <div class="panel-title">확인 필요</div>
  <div class="panel-sub">확인필요·파싱 불확실 항목을 한 곳에 모았습니다.</div>
  <div class="filter-pills" data-filter-control="#{_esc(panel_id)}">
    <button data-filter="all" aria-pressed="true">전체</button>
    <button data-filter="warn" aria-pressed="false">확인필요</button>
    <button data-filter="unc" aria-pressed="false">파싱 불확실</button>
  </div>
  {body}
</div>"""


def _render_attention_value_summary(result: CheckResult) -> str:
    if result.expected is None and result.actual is None and result.difference is None:
        return '<span class="check-vals"><span>금액 대사 아님</span></span>'
    exp_str = f"{result.expected:,}" if result.expected is not None else "—"
    act_str = f"{result.actual:,}" if result.actual is not None else "—"
    diff_str = f"차이 {result.difference:,}" if result.difference is not None else "차이 —"
    return (
        f'<span class="check-vals"><span>기준 {exp_str}</span>'
        f'<span>대사 {act_str}</span><span>{diff_str}</span></span>'
    )


def _render_next_actions_panel(results: list[CheckResult], *, panel_id: str = "panel-next") -> str:
    """다음 작업: derived checklist so the report ends on action, not just status."""
    c = _status_counts(results)
    lis = "".join(f"<li>{_esc(line)}</li>" for line in _next_action_lines(c))
    return f"""<div class="panel hidden" id="{_esc(panel_id)}">
  <div class="panel-title">다음 작업</div>
  <div class="panel-sub">확인 필요 항목을 처리하기 위한 후속 작업입니다.</div>
  <ol class="next-actions">{lis}</ol>
</div>"""


def _validation_qa_nav_badge(qa: ValidationQAReport) -> str:
    counts = qa.status_counts()
    if counts[QA_FAIL]:
        return f'<span class="nav-badge nb-warn">QA {counts[QA_FAIL]}</span>'
    if counts[QA_WARN]:
        return f'<span class="nav-badge nb-unc">QA {counts[QA_WARN]}</span>'
    return '<span class="nav-badge nb-ok">✓</span>'


def _render_validation_qa_panel(
    qa: ValidationQAReport,
    *,
    panel_id: str = "panel-validation-qa",
) -> str:
    counts = qa.status_counts()
    summary = f"""<div class="qa-summary">
  <span class="qa-status qa-status-{_esc(qa.status)}">{_esc(_qa_status_label(qa.status))}</span>
  <span>실패 {counts[QA_FAIL]}건</span>
  <span>주의 {counts[QA_WARN]}건</span>
  <span>통과 {counts[QA_PASS]}건</span>
</div>"""
    visible_categories = [
        (category, items)
        for category, items in qa.by_category().items()
        if any(item.status != QA_PASS for item in items) or category in _ALWAYS_VISIBLE_QA_CATEGORIES
    ]
    if not visible_categories:
        body = '<div class="empty-state">검증 커버리지 QA에 걸린 항목이 없습니다.</div>'
    else:
        body = "".join(
            _render_validation_qa_category(category, items)
            for category, items in visible_categories
        )
    return f"""<div class="panel hidden" id="{_esc(panel_id)}">
  <div class="panel-title">검증 커버리지 QA</div>
  <div class="panel-sub">핵심 검증군 수행 여부와 근거 source 연결 상태를 확인합니다.</div>
  {summary}
  {body}
</div>"""


_ALWAYS_VISIBLE_QA_CATEGORIES = {"frontend_contract", "completion_readiness"}


def _render_validation_qa_category(category: str, items: tuple[ValidationQAItem, ...]) -> str:
    visible_items = (
        list(items)
        if category in _ALWAYS_VISIBLE_QA_CATEGORIES
        else [item for item in items if item.status != QA_PASS]
    )
    cards = "".join(_render_validation_qa_item(item) for item in visible_items[:12])
    more = ""
    if len(visible_items) > 12:
        more = f'<div class="backlog-more">외 {len(visible_items) - 12}건</div>'
    return f"""<section class="backlog-category">
  <div class="backlog-category-head">
    <span>{_esc(_qa_category_label(category))}</span>
    <span class="backlog-count">{len(visible_items)}건</span>
  </div>
  <div class="backlog-card-list">{cards}</div>
  {more}
</section>"""


def _render_validation_qa_item(item: ValidationQAItem) -> str:
    evidence = " · ".join(item.evidence_sources[:3]) or "근거 위치 없음"
    check_types = " · ".join(item.check_types[:5]) or "검증 결과 없음"
    check_ids = " · ".join(item.check_ids[:3]) or "검증 ID 없음"
    return f"""<article class="backlog-card">
  <div class="backlog-card-head">
    <span class="backlog-rule">{_esc(item.expected_family)}</span>
    <span class="backlog-status">{_esc(_qa_status_label(item.status))}</span>
  </div>
  <div class="backlog-title">{_esc(item.target)}</div>
  <dl class="backlog-grid">
    <dt>QA 사유</dt><dd>{_esc(item.reason)}</dd>
    <dt>검증군</dt><dd>{_esc(_qa_category_label(item.category))}</dd>
    <dt>검증 유형</dt><dd><code>{_esc(check_types)}</code></dd>
    <dt>검증 ID</dt><dd><code>{_esc(check_ids)}</code></dd>
    <dt>근거 위치</dt><dd><code>{_esc(evidence)}</code></dd>
  </dl>
</article>"""


def _qa_status_label(status: str) -> str:
    if status == QA_FAIL:
        return "QA 실패"
    if status == QA_WARN:
        return "QA 주의"
    return "QA 통과"


def _qa_category_label(category: str) -> str:
    labels = {
        "statement_body_coverage": "재무제표 본문 검증",
        "total_coverage": "합계검증",
        "fs_note_coverage": "재무제표 본문-주석 대사",
        "note_note_coverage": "주석간 대사",
        "cashflow_coverage": "현금흐름표 대사",
        "prior_period_coverage": "전기 숫자 검증",
        "evidence_integrity": "근거 위치 무결성",
        "frontend_contract": "백엔드-프론트 표시 계약",
        "completion_readiness": "작업 완료 기준",
    }
    return labels.get(category, category.replace("_", " "))


def _render_review_backlog_panel(
    backlog: ReviewBacklog,
    *,
    panel_id: str = "panel-review-backlog",
) -> str:
    if not backlog.items:
        body = '<div class="empty-state">검증 고도화 큐에 쌓인 항목이 없습니다.</div>'
    else:
        body = "".join(
            _render_backlog_category(category, items)
            for category, items in backlog.by_category().items()
        )
    return f"""<div class="panel hidden" id="{_esc(panel_id)}">
  <div class="panel-title">검증 고도화 큐</div>
  <div class="panel-sub">불확실·확인필요 항목을 백엔드 개선 유형으로 분류한 데이터입니다.</div>
  {body}
</div>"""


def _render_backlog_category(category: str, items: tuple[ReviewBacklogItem, ...]) -> str:
    cards = "".join(_render_backlog_item(item) for item in items[:12])
    more = ""
    if len(items) > 12:
        more = f'<div class="backlog-more">외 {len(items) - 12}건</div>'
    return f"""<section class="backlog-category">
  <div class="backlog-category-head">
    <span>{_esc(category)}</span>
    <span class="backlog-count">{len(items)}건</span>
  </div>
  <div class="backlog-card-list">{cards}</div>
  {more}
</section>"""


def _render_backlog_item(item: ReviewBacklogItem) -> str:
    evidence = " · ".join(item.evidence_sources[:3]) or "근거 위치 없음"
    semantic_sources = " · ".join(item.semantic_table_sources[:3]) or "의미 표 없음"
    flags = " · ".join(_backlog_semantic_flag_label(flag) for flag in item.semantic_flags)
    if not flags:
        flags = "구조 특이사항 없음"
    account_label = _backlog_account_label(item.account_key)
    title = _backlog_title_label(item.title)
    return f"""<article class="backlog-card">
  <div class="backlog-card-head">
    <span class="backlog-rule">{_esc(item.category)}</span>
    <span class="backlog-status">{_esc(_backlog_status_label(item.status))}</span>
  </div>
  <div class="backlog-title">{_esc(title)}</div>
  <dl class="backlog-grid">
    <dt>검토 질문</dt><dd>{_esc(item.reviewer_question)}</dd>
    <dt>개선 방향</dt><dd>{_esc(item.backend_action)}</dd>
    <dt>관련 계정</dt><dd>{_esc(account_label)}</dd>
    <dt>근거 위치</dt><dd><code>{_esc(evidence)}</code></dd>
    <dt>의미 표</dt><dd><code>{_esc(semantic_sources)}</code></dd>
    <dt>해석 이슈</dt><dd>{_esc(flags)}</dd>
  </dl>
</article>"""


def _backlog_title_label(title: str) -> str:
    replacements = {
        "CFS to note match": "현금흐름표-주석 대사",
        "FS to note match": "재무제표 본문-주석 대사",
        "note to note match": "주석간 대사",
        "primary balance reconciliation": "기말 잔액 대사",
        "defined_benefit_obligation": "확정급여채무",
        "plan_assets": "사외적립자산",
        "amortization_expense": "감가상각/상각비",
        "property_plant_equipment": "유형자산",
        "intangible_assets": "무형자산",
        "investment_property": "투자부동산",
        "right_of_use_assets": "사용권자산",
        "earnings_per_share": "주당손익",
        "cash_and_cash_equivalents": "현금및현금성자산",
    }
    label = title
    for old, new in replacements.items():
        label = label.replace(old, new)
    return label.replace("_", " ")


def _backlog_status_label(status: str) -> str:
    if status == UNEXPLAINED_GAP:
        return "차이 원인 확인 필요"
    if status == PARSE_UNCERTAIN:
        return "원문 해석 확인 필요"
    if status == EXPLAINABLE_GAP:
        return "설명 가능한 차이"
    if status == MATCHED:
        return "특이사항 없음"
    return "검증 범위 밖"


def _backlog_account_label(account_key: str) -> str:
    labels = {
        "property_plant_equipment": "유형자산",
        "intangible_assets": "무형자산",
        "investment_property": "투자부동산",
        "right_of_use_assets": "사용권자산",
        "lease_liabilities": "리스부채",
        "borrowings": "차입금",
        "bonds": "사채",
        "trade_receivables": "매출채권",
        "cash_and_cash_equivalents": "현금및현금성자산",
        "earnings_per_share": "주당손익",
        "income_tax_expense_benefit": "법인세",
        "unknown": "계정 분류 미확정",
    }
    if account_key.startswith("fsc:"):
        return f"재무제표 계정 후보({account_key.removeprefix('fsc:')})"
    return labels.get(account_key, account_key.replace("_", " "))


def _backlog_semantic_flag_label(flag: str) -> str:
    labels = {
        "multi_header_unresolved": "표 머리글이 여러 줄이라 열 의미 확인 필요",
        "orientation_unknown": "표 방향 확인 필요",
        "low_orientation_confidence": "표 방향 판단 신뢰도 낮음",
        "unknown_layout": "표 구조 유형 미확정",
        "low_layout_confidence": "표 구조 판단 신뢰도 낮음",
        "maturity_total_missing": "만기분석 합계 행 확인 필요",
    }
    return labels.get(flag, flag.replace("_", " "))


# ── Statement Panel ───────────────────────────────────────────────────────────

def _render_statement_panel(
    section: ReportSection,
    results: list[CheckResult],
    panel_id: str,
    label: str,
    report: FullReport | None = None,
    all_results: list[CheckResult] | None = None,
) -> str:
    table = _first_table(section)
    if table is None:
        return (
            f'<div class="panel" id="{_esc(panel_id)}">'
            f'<div class="panel-title">{_esc(label)}</div>'
            f'<p class="empty-state">공시에서 찾을 수 없음</p></div>'
        )

    row_map = _row_result_map_for_table(results, table)

    rows_html = _render_table_rows(
        table,
        row_map,
        id_prefix=panel_id,
        show_state=True,
        report=report,
        all_results=all_results,
        statement_scope=section.scope,
        statement_kind=_statement_kind(section) or "",
        total_results=results,
    )
    check_summary = _render_check_summary(results) if results else ""

    return f"""<div class="panel" id="{_esc(panel_id)}">
  <div class="panel-title">{_esc(label)}</div>
  <div class="panel-sub">원문 보고서 형태 · 검증 행 클릭 시 근거 확인</div>
  <div class="statement-toolbar" aria-label="재무제표 섹션">
    <div class="statement-path">
      <span>재무제표</span>
      <strong>{_esc(label)}</strong>
    </div>
    <div class="statement-toolbar-meta">
      <span>원문 테이블 유지</span>
      <span>행 {max(len(table.rows) - 1, 0)}</span>
    </div>
  </div>
  <div class="statement-wrap">
    <div class="statement-caption"><span>{_esc(label)}</span></div>
    <table class="fs-table">
      {rows_html}
    </table>
  </div>
  {check_summary}
</div>"""


def _row_result_map_for_table(
    results: list[CheckResult],
    table: ReportTable,
) -> dict[int, CheckResult]:
    row_map: dict[int, CheckResult] = {}
    for result in results:
        if _is_total_surface_check(result):
            continue
        for ev in result.evidence:
            for parsed in _parse_source_refs(ev.source):
                _, _, table_idx, row_idx, _ = parsed
                if table_idx != table.index or row_idx is None:
                    continue
                row_map[row_idx] = _preferred_statement_row_result(row_map.get(row_idx), result)
    return row_map


def _parse_source_refs(source: str) -> list[tuple[str, str, int, int | None, int | None]]:
    refs: list[tuple[str, str, int, int | None, int | None]] = []
    for part in (source or "").split(";"):
        parsed = _parse_source(part.strip())
        if parsed is not None:
            refs.append(parsed)
    return refs


_STATEMENT_ROW_CHECK_PRIORITY = {
    "fs_note_ref_amount_match": -1,
    "primary_balance_reconciliation": 0,
    "fs_note_match": 0,
    "cfs_note_match": 0,
    "cashflow_reconciliation": 1,
    "asset_note_bridge_check": 1,
    "statement_cash_tie": 2,
    "statement_equity_tie": 2,
    "statement_bs_equation": 2,
    "statement_subtotal": 4,
}


def _preferred_statement_row_result(
    current: CheckResult | None,
    candidate: CheckResult,
) -> CheckResult:
    if current is None:
        return candidate
    current_rank = _STATEMENT_ROW_CHECK_PRIORITY.get(current.check_type, 3)
    candidate_rank = _STATEMENT_ROW_CHECK_PRIORITY.get(candidate.check_type, 3)
    if candidate_rank < current_rank:
        return candidate
    if candidate_rank > current_rank:
        return current
    return _worse(current, candidate)


def _render_table_rows(
    table: ReportTable,
    row_map: dict[int, CheckResult],
    *,
    id_prefix: str = "dd",
    show_state: bool = False,
    report: FullReport | None = None,
    all_results: list[CheckResult] | None = None,
    statement_scope: str = "",
    statement_kind: str = "",
    total_results: list[CheckResult] | None = None,
) -> str:
    html_parts: list[str] = []
    if not table.rows:
        return ""

    total_marks = _total_mark_details_for_table(total_results or [], table)
    header = table.rows[0]
    if show_state:
        header_cells = '<th class="state-col">검증</th>' + "".join(f"<th>{_esc(c)}</th>" for c in header)
    else:
        header_cells = "".join(f"<th>{_esc(c)}</th>" for c in header)
    html_parts.append(f"<thead><tr>{header_cells}</tr></thead><tbody>")

    for i, row in enumerate(table.rows[1:], start=1):
        result = row_map.get(i)
        row_total_mark = total_marks.get((i, None))
        row_total_status = row_total_mark.status if row_total_mark else None
        row_total_class = f" total-mark {_total_status_class(row_total_status)}" if row_total_status else ""
        # Determine whether this row has any amount value (non-blank, non-None)
        has_amount = any(parse_amount(c) is not None for c in row)
        cell_parts = []
        for ci, c in enumerate(row):
            cell_mark = total_marks.get((i, ci))
            cell_status = cell_mark.status if cell_mark else None
            cell_class = (
                f' class="total-cell {_total_status_class(cell_status)}"'
                if cell_status else ""
            )
            cell_title = (
                f' title="{_esc(_total_status_label(cell_status))}"'
                if cell_status else ""
            )
            formula = _render_total_formula_popover(cell_mark.result) if cell_mark else ""
            formula_attr = (
                f' data-total-formula="{_esc(_total_formula_text(cell_mark.result))}" tabindex="0"'
                if cell_mark else ""
            )
            cell_parts.append(
                f'<td data-cell="r{i}c{ci}"{cell_class}{cell_title}{formula_attr}>{_esc(c)}{formula}</td>'
            )
        cells = "".join(cell_parts)
        if result is not None:
            css_class = _status_to_row_class(result.status)
            dd_id = f"{id_prefix}-{i}"
            if show_state:
                state_cell = f'<td class="state-col">{_account_state_badge(result.status)}</td>'
                dd_colspan = len(row) + 1
                html_parts.append(
                    f'<tr class="{css_class}{row_total_class}" data-check-row="{i}" '
                    f'onclick="showReview(\'{dd_id}\', this)">{state_cell}{cells}</tr>'
                )
            else:
                dd_colspan = len(row)
                html_parts.append(
                    f'<tr class="{css_class}{row_total_class}" data-check-row="{i}" '
                    f'onclick="showReview(\'{dd_id}\', this)">{cells}</tr>'
                )
            drilldown = _render_drilldown(
                result,
                report,
                statement_label=row[0] if row else "",
                statement_scope=statement_scope,
                statement_kind=statement_kind,
            )
            html_parts.append(
                f'<tr class="dd-row">'
                f'<td colspan="{dd_colspan}" class="dd-cell">'
                f'<div class="dd-inner" id="{dd_id}">'
                f'{drilldown}'
                f'</div></td></tr>'
            )
        elif has_amount:
            if row_total_status is not None:
                if show_state:
                    state_cell = (
                        '<td class="state-col">'
                        f'{_account_state_badge(row_total_status)}'
                        '</td>'
                    )
                    html_parts.append(
                        f'<tr class="total-only-row{row_total_class}" '
                        f'data-check-row="{i}">{state_cell}{cells}</tr>'
                    )
                else:
                    html_parts.append(
                        f'<tr class="total-only-row{row_total_class}" data-check-row="{i}">{cells}</tr>'
                )
                continue
            if show_state:
                fallback_badge = _statement_row_fallback_badge(
                    row, report, all_results, statement_scope, statement_kind
                )
                state_cell = (
                    '<td class="state-col">'
                    f'{fallback_badge}'
                    '</td>'
                )
                if not fallback_badge:
                    html_parts.append(f"<tr>{state_cell}{cells}</tr>")
                    continue
                dd_id = f"{id_prefix}-unverified-{i}"
                html_parts.append(
                    f'<tr class="unverified-row" data-check-row="{i}" '
                    f'onclick="showReview(\'{dd_id}\', this)">{state_cell}{cells}</tr>'
                )
                html_parts.append(
                    f'<tr class="dd-row">'
                    f'<td colspan="{len(row) + 1}" class="dd-cell">'
                    f'<div class="dd-inner" id="{dd_id}">'
                    f'{_render_unverified_statement_drilldown(row, report, all_results, statement_scope, statement_kind)}'
                    f'</div></td></tr>'
                )
            else:
                html_parts.append(f"<tr>{cells}</tr>")
        else:
            if show_state:
                state_cell = '<td class="state-col"></td>'
                html_parts.append(f"<tr>{state_cell}{cells}</tr>")
            else:
                html_parts.append(f"<tr>{cells}</tr>")

    html_parts.append("</tbody>")
    return "\n".join(html_parts)


def _render_unverified_statement_drilldown(
    row: list[str],
    report: FullReport | None = None,
    all_results: list[CheckResult] | None = None,
    statement_scope: str = "",
    statement_kind: str = "",
) -> str:
    label = row[0].strip() if row else ""
    amount = next((parse_amount(cell) for cell in row[1:] if parse_amount(cell) is not None), None)
    amount_text = f"{amount:,}" if amount is not None else "—"
    note_refs = _note_refs_from_label(label)
    is_structure = not note_refs and _is_statement_structure_label(label, statement_kind)
    if is_structure:
        state_text = ""
        callout_text = "개별 주석대사 대상이 아닌 재무제표 본문 구조 항목입니다."
    else:
        state_text, callout_text = _statement_note_review_state(
            note_refs, report, all_results, statement_scope, label
        )
    note_text = _render_statement_note_reference_hint(note_refs, report, all_results, statement_scope, label)
    return f"""<div class="dd-title">{_esc(label or "미검증 행")}</div>
<table class="src-tbl">
  <thead><tr><th>항목</th><th>금액</th><th>상태</th></tr></thead>
  <tbody><tr><td>{_esc(label)}</td><td>{amount_text}</td><td>{_esc(state_text)}</td></tr></tbody>
</table>
<div class="callout unc">{_esc(callout_text)}</div>
{note_text}"""


def _statement_note_review_state(
    note_refs: list[str],
    report: FullReport | None,
    all_results: list[CheckResult] | None,
    statement_scope: str = "",
    statement_label: str = "",
) -> tuple[str, str]:
    if not note_refs:
        return "미검증", "이 본문 행에 대한 직접 금액대사는 아직 연결되지 않았습니다."
    if report is None:
        return "미검증", "관련 주석번호는 있으나 주석 원문과 검증 결과를 함께 확인하지 못했습니다."
    has_note_section = False
    statuses: list[str] = []
    for ref in note_refs:
        sections = _matching_note_sections(report, ref, statement_scope, statement_label)
        has_note_section = has_note_section or bool(sections)
        statuses.extend(
            result.status for result in (all_results or [])
            if result.note_no
            and _note_no_matches_ref(result.note_no, ref)
            and (not sections or _result_mentions_any_section_tables(result, sections))
        )
    status = _worse_status(statuses)
    if status == UNEXPLAINED_GAP:
        return "확인필요", "직접 금액대사는 아직 없고, 참조 주석에 확인할 검토 항목이 있습니다."
    if status == PARSE_UNCERTAIN:
        return "확인필요", "직접 금액대사는 아직 없고, 참조 주석 해석에 확인이 필요한 항목이 있습니다."
    if status == EXPLAINABLE_GAP:
        return "설명차이", "직접 금액대사는 아직 없고, 참조 주석에 설명 가능한 차이 항목이 있습니다."
    if status == MATCHED:
        return "주석 검증완료", "직접 금액대사는 아직 없지만, 참조 주석의 검증 결과는 특이사항 없음으로 확인되었습니다."
    if has_note_section:
        return "주석 원문확인", "직접 금액대사는 아직 없지만, 관련 주석 원문은 확인되었습니다."
    return "미검증", "이 본문 행에 대한 직접 금액대사는 아직 연결되지 않았습니다."


def _render_statement_note_reference_hint(
    note_refs: list[str],
    report: FullReport | None,
    all_results: list[CheckResult] | None,
    statement_scope: str = "",
    statement_label: str = "",
) -> str:
    if not note_refs:
        return '<div class="callout unc">관련 주석 번호가 행 라벨에 직접 표시되지 않았습니다.</div>'
    if report is None:
        return f'<div class="callout unc">관련 주석 후보: {", ".join(note_refs)}</div>'

    cards = ""
    for ref in note_refs:
        sections = _matching_note_sections(report, ref, statement_scope, statement_label)
        note_results = [
            r for r in (all_results or [])
            if r.note_no
            and _note_no_matches_ref(r.note_no, ref)
            and (not sections or _result_mentions_any_section_tables(r, sections))
        ]
        status = _worse_status([r.status for r in note_results])
        badge = _account_state_badge(status)
        state_label = _note_reference_state_label(status, bool(sections))
        review_summary = _render_note_reference_review_summary(note_results)
        section_links = ""
        seen_panel_ids: set[str] = set()
        for section in sections:
            note_no = section.note_no or section.section_id
            panel_id = _note_panel_id(section, report)
            if panel_id in seen_panel_ids:
                continue
            seen_panel_ids.add(panel_id)
            section_links += (
                f'<button type="button" class="mini-jump" onclick="jumpToPanel(\'{_esc_js_str(panel_id)}\')">'
                f'주석 { _esc(note_no) } 열기</button>'
            )
        if not section_links:
            section_links = '<span class="note-ref-missing">주석 원문 미발견</span>'
        cards += f"""<div class="note-ref-card">
  <div class="note-ref-title">주석번호 확인: 주{_esc(ref)}</div>
  <div class="note-ref-body">{section_links}<span>주석 내 검증 {len(note_results)}건</span>{badge}</div>
  <div class="note-ref-state">{_esc(state_label)}</div>
  {review_summary}
</div>"""
    return f'<div class="note-ref-list">{cards}</div>'


def _note_reference_state_label(status: str | None, has_note_section: bool) -> str:
    if status == UNEXPLAINED_GAP:
        return "확인필요 · 참조 주석에 확인필요 항목이 있습니다."
    if status == PARSE_UNCERTAIN:
        return "확인필요 · 참조 주석 원문 해석 확인이 필요합니다."
    if status == EXPLAINABLE_GAP:
        return "설명차이 · 설명 가능한 차이를 확인했습니다."
    if status == MATCHED:
        return "주석 검증완료 · 참조 주석 검증 특이사항 없음."
    if has_note_section:
        return "주석 원문확인 · 원문 위치를 확인했습니다."
    return "미검증 · 주석 원문을 찾지 못했습니다."


def _render_note_reference_review_summary(results: list[CheckResult]) -> str:
    if not results:
        return ""
    detail_results = [result for result in results if not _is_total_surface_check(result)]
    total_count = len(results) - len(detail_results)
    counts: list[str] = []
    for status, label in (
        (UNEXPLAINED_GAP, "확인필요"),
        (PARSE_UNCERTAIN, "파싱불확실"),
        (EXPLAINABLE_GAP, "설명차이"),
        (MATCHED, "검증완료"),
    ):
        count = sum(1 for result in results if result.status == status)
        if count:
            counts.append(f"{label} {count}")
    count_text = " · ".join(counts)
    body = f'<div class="note-ref-counts">{_esc(count_text)}</div>' if count_text else ""
    for result in sorted(detail_results, key=lambda item: _NOTE_REF_STATUS_RANK.get(item.status, 9))[:4]:
        badge_class = _status_to_badge_class(result.status)
        badge_label = _status_to_badge_label(result.status)
        diff = f" · 차이 {result.difference:,}" if result.difference is not None else ""
        reason = f'<div class="note-ref-reason">{_esc(result.reason)}</div>' if result.reason else ""
        body += f"""<div class="note-ref-check">
  <span class="note-ref-check-title">{_esc(result.title)}</span>
  <span class="badge {badge_class}">{badge_label}</span>
  <span class="note-ref-diff">{_esc(diff)}</span>
  {reason}
</div>"""
    if total_count:
        total_summary = _status_count_text(
            result.status for result in results
            if _is_total_surface_check(result)
        )
        total_suffix = f"({total_summary})" if total_summary else ""
        body += (
            '<div class="note-ref-total-hint">'
            f'합계검증 {total_count}건{_esc(total_suffix)}은 주석 원문 표의 색상 테두리에서 확인합니다.'
            '</div>'
        )
    return f'<div class="note-ref-review">{body}</div>' if body else ""


def _status_count_text(statuses) -> str:
    counts: list[str] = []
    status_list = list(statuses)
    for status, label in (
        (UNEXPLAINED_GAP, "확인필요"),
        (PARSE_UNCERTAIN, "파싱불확실"),
        (EXPLAINABLE_GAP, "설명차이"),
        (MATCHED, "검증완료"),
    ):
        count = sum(1 for item in status_list if item == status)
        if count:
            counts.append(f"{label} {count}")
    return " · ".join(counts)


_NOTE_REF_STATUS_RANK = {
    UNEXPLAINED_GAP: 0,
    PARSE_UNCERTAIN: 1,
    EXPLAINABLE_GAP: 2,
    NOT_TESTED: 3,
    MATCHED: 4,
}


def _statement_row_fallback_badge(
    row: list[str],
    report: FullReport | None,
    all_results: list[CheckResult] | None,
    statement_scope: str,
    statement_kind: str = "",
) -> str:
    label = row[0].strip() if row else ""
    refs = _note_refs_from_label(label)
    if not refs or report is None:
        return ""
    state_text, _ = _statement_note_review_state(refs, report, all_results, statement_scope, label)
    if state_text == "확인필요":
        return '<span class="acct-state as-warn">확인필요</span>'
    if state_text == "설명차이":
        return '<span class="acct-state as-exp">설명차이</span>'
    if state_text in {"주석 검증완료", "주석 원문확인"}:
        return f'<span class="acct-state as-note">{_esc(state_text)}</span>'
    return _account_state_badge(None)


def _render_statement_disclosure_review(
    statement_label: str,
    report: FullReport | None,
    statement_scope: str = "",
    statement_kind: str = "",
) -> str:
    label = statement_label.strip()
    if report is None or not label:
        return ""
    entry = _statement_account_entry(label, statement_kind)
    if entry is None:
        return ""

    refs = _note_refs_from_label(label)
    candidates = _note_candidates_for_statement_account(report, entry, statement_scope)
    accuracy_html = _render_statement_disclosure_accuracy(entry, refs, candidates, report)
    completeness_html = _render_statement_disclosure_completeness(entry, refs, candidates, report)
    return f"""<section class="statement-disclosure-review" aria-label="공시계정 주석번호 검토">
  <div class="note-source-head">공시계정 주석번호 검토</div>
  {accuracy_html}
  {completeness_html}
</section>"""


def _statement_account_entry(statement_label: str, statement_kind: str = "") -> TaxonomyEntry | None:
    title = _STMT_KEY_LABELS.get(statement_kind, statement_kind)
    label = re.sub(r"\([^)]*\)", "", statement_label)
    compact_label = _compact(label)
    if title in {"손익계산서", "포괄손익계산서"}:
        if "법인세비용차감전" in compact_label:
            return _entry_for_statement_label(title, "법인세비용(수익)")
        if compact_label in {"법인세비용", "법인세비용수익", "법인세수익"}:
            return None
    return _entry_for_statement_label(title, label)


def _note_candidates_for_statement_account(
    report: FullReport,
    entry: TaxonomyEntry,
    statement_scope: str = "",
) -> list[_DisclosureNoteCandidate]:
    candidates: list[_DisclosureNoteCandidate] = []
    seen: set[tuple[str, str]] = set()
    for section in report.notes:
        if statement_scope and section.scope and section.scope != statement_scope:
            continue
        evidence = _note_account_evidence(section, entry)
        if evidence is None:
            continue
        key = (section.note_no or section.section_id, section.title)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(_DisclosureNoteCandidate(section, evidence))
    return candidates


def _note_account_evidence(section: ReportSection, entry: TaxonomyEntry) -> str | None:
    topic_aliases = _statement_disclosure_topic_aliases(entry)
    if _matches_any(section.title, topic_aliases):
        return "주석 제목"
    for block in section.blocks:
        if block.text and _matches_any(block.text, topic_aliases):
            return "주석 문단"
        table = block.table
        if table is None:
            continue
        if table.heading and _matches_any(table.heading, topic_aliases):
            return "표 제목"
        for row in table.rows[1:]:
            label = " ".join(cell for cell in row[:2] if parse_amount(cell) is None)
            if label and _matches_any(label, topic_aliases):
                return "표 행"
    return None


def _statement_disclosure_topic_aliases(entry: TaxonomyEntry) -> tuple[str, ...]:
    aliases = [
        entry.display_name,
        *entry.statement_aliases,
        *entry.note_title_aliases,
    ]
    return tuple(dict.fromkeys(alias for alias in aliases if alias))


def _render_statement_disclosure_accuracy(
    entry: TaxonomyEntry,
    refs: list[str],
    candidates: list[_DisclosureNoteCandidate],
    report: FullReport,
) -> str:
    ref_text = _statement_disclosure_ref_text(refs)
    matched = [candidate for candidate in candidates if _candidate_matches_any_ref(candidate, refs)]
    if not refs:
        callout = (
            f'<div class="callout warn">⚠ 본문 행에 주석번호가 없습니다. '
            f'{_esc(entry.display_name)}을 다루는 주석 후보를 확인하세요.</div>'
        )
    elif matched:
        callout = (
            f'<div class="callout ok">✓ 본문 주석번호 {ref_text}가 '
            f'{_esc(entry.display_name)}을 다루는 주석과 일치합니다.</div>'
        )
    else:
        callout = (
            f'<div class="callout warn">⚠ 본문 주석번호 {ref_text} 안에서 '
            f'{_esc(entry.display_name)} 공시계정 내용을 확인하지 못했습니다.</div>'
        )
    cards = _render_disclosure_candidate_cards(matched, report)
    return f"""<div class="statement-disclosure-card">
  <div class="statement-disclosure-title">공시계정 주석번호 정확성</div>
  {callout}
  {cards}
</div>"""


def _render_statement_disclosure_completeness(
    entry: TaxonomyEntry,
    refs: list[str],
    candidates: list[_DisclosureNoteCandidate],
    report: FullReport,
) -> str:
    missing = [
        candidate for candidate in candidates
        if not _candidate_matches_any_ref(candidate, refs)
    ]
    if missing:
        callout = (
            f'<div class="callout warn">⚠ 주석 내용은 있는데 본문 번호에 포함되지 않은 '
            f'{_esc(entry.display_name)} 후보 {len(missing)}건입니다.</div>'
        )
    else:
        callout = (
            f'<div class="callout ok">✓ 주석 전체에서 본문 주석번호 밖의 '
            f'{_esc(entry.display_name)} 후보를 찾지 못했습니다.</div>'
        )
    cards = _render_disclosure_candidate_cards(missing, report, prefix="본문 번호 미기재 후보")
    return f"""<div class="statement-disclosure-card">
  <div class="statement-disclosure-title">공시계정 주석번호 완전성</div>
  {callout}
  {cards}
</div>"""


def _render_disclosure_candidate_cards(
    candidates: list[_DisclosureNoteCandidate],
    report: FullReport,
    *,
    prefix: str = "",
) -> str:
    if not candidates:
        return ""
    cards = ""
    for candidate in candidates[:6]:
        section = candidate.section
        note_no = section.note_no or section.section_id
        panel_id = _note_panel_id(section, report)
        title = f"주석 {note_no} {section.title}".strip()
        if prefix:
            title = f"{prefix}: {title}"
        cards += f"""<div class="note-ref-card">
  <div class="note-ref-title">{_esc(title)}</div>
  <div class="note-ref-body">
    <button type="button" class="mini-jump" onclick="jumpToPanel('{_esc_js_str(panel_id)}')">주석 { _esc(note_no) } 열기</button>
    <span>{_esc(candidate.evidence)}</span>
  </div>
  <div class="note-ref-state">{_esc(_note_nav_label(section))}</div>
</div>"""
    if len(candidates) > 6:
        cards += f'<div class="completeness-more">외 {len(candidates) - 6}건</div>'
    return f'<div class="note-ref-list">{cards}</div>'


def _candidate_matches_any_ref(candidate: _DisclosureNoteCandidate, refs: list[str]) -> bool:
    note_no = candidate.section.note_no or candidate.section.section_id
    return any(_note_no_matches_ref(note_no, ref) for ref in refs)


def _statement_disclosure_ref_text(refs: list[str]) -> str:
    return ", ".join(f"주{ref}" for ref in refs) if refs else "없음"


def _is_statement_structure_label(label: str, statement_kind: str = "") -> bool:
    compact = _compact(label)
    if not compact:
        return False
    if statement_kind in {"cf", "sce"}:
        return True
    if re.match(r"^\d{4}\.\d{2}\.\d{2}", compact):
        return True
    return any(
        key in compact for key in (
            "총계",
            "총이익",
            "영업이익",
            "법인세비용차감전",
            "당기순이익",
            "기타포괄손익",
            "총포괄손익",
            "재분류되는항목",
            "재분류되지않는항목",
            "소유주에게귀속",
            "비지배지분",
            "지배기업소유주지분",
            "기초자본",
            "기말자본",
            "기초의현금및현금성자산",
            "현금및현금성자산의증가",
            "현금및현금성자산의순증가",
            "기말의현금및현금성자산",
        )
    )


def _matching_note_sections(
    report: FullReport,
    ref: str,
    statement_scope: str = "",
    statement_label: str = "",
) -> list[ReportSection]:
    sections = [
        section for section in report.notes
        if section.note_no and _note_no_matches_ref(section.note_no, ref)
        and (not statement_scope or section.scope == statement_scope)
    ]
    label_key = _compact_note_ref_label(statement_label)
    if not label_key:
        return sections
    title_matches = [
        section for section in sections
        if _note_title_matches_statement_label(section.title, label_key)
    ]
    return title_matches or sections


def _compact_note_ref_label(label: str) -> str:
    label = re.sub(r"\([^)]*\)", "", label)
    return re.sub(r"^(유동|비유동|장기|단기)", "", _compact(label))


def _note_title_matches_statement_label(note_title: str, label_key: str) -> bool:
    title_key = re.sub(r"^(유동|비유동|장기|단기)", "", _compact(note_title))
    return bool(label_key and (label_key in title_key or title_key in label_key))


def _result_mentions_any_section_tables(result: CheckResult, sections: list[ReportSection]) -> bool:
    table_indexes = {
        block.table.index
        for section in sections
        for block in section.blocks
        if block.table is not None
    }
    if not table_indexes:
        return False
    for ev in result.evidence:
        for parsed in _parse_source_refs(ev.source):
            scope, _, table_idx, _, _ = parsed
            if scope == "note" and table_idx in table_indexes:
                return True
    return False


def _note_no_matches_ref(note_no: str, ref: str) -> bool:
    return note_no == ref or note_no.startswith(f"{ref}-")


def _worse_status(statuses: list[str]) -> str | None:
    if not statuses:
        return None
    rank = {
        UNEXPLAINED_GAP: 0,
        PARSE_UNCERTAIN: 1,
        EXPLAINABLE_GAP: 2,
        NOT_TESTED: 3,
        MATCHED: 4,
    }
    return min(statuses, key=lambda status: rank.get(status, 5))


def _note_refs_from_label(label: str) -> list[str]:
    refs: list[str] = []
    for group in re.findall(r"주\s*([0-9,\-~ㆍ· ]+)", label):
        refs.extend(re.findall(r"\d+", group))
    return list(dict.fromkeys(refs))


def _status_to_row_class(status: str) -> str:
    if status == MATCHED:
        return "verified-ok"
    if status == UNEXPLAINED_GAP:
        return "verified-warn"
    return "verified-uncertain"


def _render_drilldown(
    result: CheckResult,
    report: FullReport | None = None,
    *,
    statement_label: str = "",
    statement_scope: str = "",
    statement_kind: str = "",
) -> str:
    callout_class = "ok" if result.status == MATCHED else "warn"
    callout_icon = "✓" if result.status == MATCHED else "⚠"
    ev_rows = ""
    raw_rows = ""
    visible_evidence = [
        (idx, ev)
        for idx, ev in enumerate(result.evidence)
        if not _is_target_evidence(result, ev, idx)
    ]
    for idx, ev in visible_evidence:
        amount_str = f"{ev.amount:,}" if ev.amount is not None else "—"
        role = _evidence_role_label(result, ev, idx)
        src_cell = _render_source_jump_cell(ev.source, report)
        ev_rows += (
            f"<tr><td>{_esc(role)}</td><td>{_esc(ev.label)}</td>"
            f"<td>{amount_str}</td>{src_cell}</tr>"
        )
        raw_rows += f"<div>{_esc(ev.label)}: <code>{_esc(ev.source)}</code></div>"
    if not visible_evidence:
        ev_rows = '<tr><td colspan="4">표시할 상대 근거가 없습니다.</td></tr>'
    components = [e for e in result.evidence if e.role == "component"]
    breakdown = ""
    if components:
        comp_rows = "".join(
            f"<tr><td>{_esc(e.label)}</td><td>{(e.amount if e.amount is not None else 0):,}</td></tr>"
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
        uncertain_note = f'<div class="callout unc">파싱 사유: {_esc(result.parse_uncertain_reason)}</div>'
    note_ref_note = _render_note_reference_check(result)
    status_note = _render_review_status_note(result)
    comparison_summary = _render_comparison_summary(result, report)
    return f"""<div class="dd-title">{_esc(result.title)}</div>
{comparison_summary}
{status_note}
<table class="src-tbl">
  <thead><tr><th>역할</th><th>항목</th><th>금액</th><th>위치</th></tr></thead>
  <tbody>{ev_rows}</tbody>
</table>
{note_ref_note}
{breakdown}<div class="callout {callout_class}">{callout_icon} {_esc(result.reason)}</div>
{uncertain_note}
<details class="tech-detail"><summary>기술 세부정보</summary>{raw_rows}</details>"""


def _render_comparison_summary(result: CheckResult, report: FullReport | None) -> str:
    left_label, right_label, method_label = _comparison_labels(result)
    left_items, right_items = _comparison_evidence_groups(result)
    left_body = _render_comparison_items(result, left_items, report)
    right_body = _render_comparison_items(result, right_items, report)
    math_line = _render_comparison_math(result)
    return f"""<section class="comparison-summary" aria-label="비교한 내용">
  <div class="comparison-head">
    <span>비교한 내용</span>
    <strong>{_esc(method_label)}</strong>
  </div>
  <div class="comparison-grid">
    <div class="comparison-side">
      <div class="comparison-side-label">{_esc(left_label)}</div>
      {left_body}
    </div>
    <div class="comparison-arrow" aria-hidden="true">&harr;</div>
    <div class="comparison-side">
      <div class="comparison-side-label">{_esc(right_label)}</div>
      {right_body}
    </div>
  </div>
  {math_line}
</section>"""


def _comparison_labels(result: CheckResult) -> tuple[str, str, str]:
    if result.check_type in {"total_check", "note_layout_formula_check", "statement_subtotal"}:
        return ("구성요소 합산액", "표시 합계", "합계 산식 대사")
    if result.check_type == "statement_bs_equation":
        return ("부채총계 + 자본총계", "자산총계", "재무상태표 등식 대사")
    if result.check_type in _BODY_MATCH_CHECK_TYPES:
        return ("재무제표 본문 금액", "주석 공시 금액", "본문-주석 금액 대사")
    if result.check_type in {"cfs_note_match", "cashflow_reconciliation", "asset_note_bridge_check"}:
        return ("현금흐름표 금액", "주석 증감/보조 금액", "현금흐름표-주석 대사")
    if result.check_type in {"note_note_match", "note_note_reconciliation"}:
        return ("첫 번째 주석 금액", "관련 주석 금액", "주석 간 금액 대사")
    if result.check_type == "prior_year_amount_match":
        return ("전기 보고서 당기 금액(기준)", "당기 보고서 비교기간 금액(대사)", "전기 숫자 대사")
    if result.check_type == "prior_year_beginning_balance_match":
        return ("전기 보고서 기말 금액(기준)", "당기 보고서 기초 금액(대사)", "전기 이월 금액 대사")
    if result.check_type == "prior_column_rollforward":
        return ("재무제표 전기 열 금액(기준)", "주석 기초/전기 금액(대사)", "전기 열-주석 대사")
    if result.check_type == "prior_column_fs_note":
        return ("재무제표 전기 열 금액(기준)", "주석 전기 열 금액(대사)", "전기 열 본문-주석 대사")
    if result.check_type in {
        "prior_year_structure_change",
    }:
        return ("당기 주석 구조", "전기 주석 구조", "전기 구조 비교")
    if result.check_type in {
        "note_reference_check",
        "statement_note_reference_accuracy",
        "statement_note_reference_completeness",
    }:
        return ("표시된 주석 참조", "실제 주석/원문 위치", "주석 참조 대사")
    return ("검증 기준", "대사 대상", "검증 대사")


def _comparison_evidence_groups(
    result: CheckResult,
) -> tuple[list[tuple[int, CheckEvidence]], list[tuple[int, CheckEvidence]]]:
    indexed = list(enumerate(result.evidence))
    if not indexed:
        return ([], [])
    if result.check_type in {"total_check", "note_layout_formula_check", "statement_subtotal"}:
        targets = [(idx, ev) for idx, ev in indexed if _is_target_evidence(result, ev, idx)]
        components = [(idx, ev) for idx, ev in indexed if not _is_target_evidence(result, ev, idx)]
        return (components, targets)
    if result.check_type == "statement_bs_equation":
        targets = indexed[:1]
        components = indexed[1:]
        return (components, targets)
    if result.check_type in _BODY_MATCH_CHECK_TYPES:
        statement_items = [(idx, ev) for idx, ev in indexed if (ev.source or "").startswith("statement:")]
        note_items = [(idx, ev) for idx, ev in indexed if (ev.source or "").startswith("note:")]
        if statement_items or note_items:
            return (statement_items, note_items)
    if result.check_type in _CROSS_STATEMENT_CHECK_TYPES:
        return (indexed[:1], indexed[1:])
    if result.check_type in {"prior_year_amount_match", "prior_year_beginning_balance_match"}:
        prior_items = [(idx, ev) for idx, ev in indexed if _is_prior_source(ev.source)]
        current_items = [(idx, ev) for idx, ev in indexed if not _is_prior_source(ev.source)]
        if prior_items or current_items:
            return (prior_items, current_items)
    if len(indexed) == 1:
        return (indexed, [])
    return (indexed[:1], indexed[1:])


def _render_comparison_items(
    result: CheckResult,
    items: list[tuple[int, CheckEvidence]],
    report: FullReport | None,
) -> str:
    if not items:
        return '<div class="comparison-empty">해당 방향의 원문 근거가 없습니다.</div>'
    rendered: list[str] = []
    for idx, ev in items[:4]:
        amount = f"{ev.amount:,}" if ev.amount is not None else "금액 없음"
        source = _humanize_source(report, ev.source) if report is not None else (ev.source or "—")
        label = _compact(" ".join((ev.label or "").split()))
        rendered.append(
            f"""<div class="comparison-item">
  <div class="comparison-item-main">{_esc(label or _evidence_role_label(result, ev, idx))}</div>
  <div class="comparison-item-meta"><span>{_esc(amount)}</span><span>{_esc(source)}</span></div>
</div>"""
        )
    if len(items) > 4:
        rendered.append(f'<div class="comparison-more">외 {len(items) - 4}개 근거</div>')
    return "".join(rendered)


def _render_comparison_math(result: CheckResult) -> str:
    if result.expected is None and result.actual is None and result.difference is None:
        return f'<div class="comparison-math">판정 기준: {_esc(result.reason)}</div>'
    expected = f"{result.expected:,}" if result.expected is not None else "—"
    actual = f"{result.actual:,}" if result.actual is not None else "—"
    difference = f"{result.difference:,}" if result.difference is not None else "—"
    return (
        f'<div class="comparison-math">엔진 판정: 기준값 {expected} · '
        f'대사값 {actual} · 차이 {difference} · 허용오차 {result.tolerance:,}</div>'
    )


def _render_review_status_note(result: CheckResult) -> str:
    if result.status == MATCHED:
        return '<div class="callout ok">특이사항 없음</div>'
    if result.status == UNEXPLAINED_GAP:
        return '<div class="callout warn">확인 필요</div>'
    return '<div class="callout unc">확인 필요</div>'


def _is_target_evidence(result: CheckResult, evidence, index: int) -> bool:
    if evidence.role == "total":
        return True
    if result.check_type == "statement_bs_equation":
        return index == 0
    if result.check_type == "statement_subtotal":
        return index == 0
    if result.check_type in _BODY_MATCH_CHECK_TYPES and (evidence.source or "").startswith("statement:"):
        return True
    if result.check_type in _CROSS_STATEMENT_CHECK_TYPES:
        return index == 0
    return False


def _render_source_jump_cell(source: str, report: FullReport | None = None) -> str:
    human = _humanize_source(report, source) if report is not None else (source or "—")
    if _is_prior_source(source):
        return f"<td class='src-ref src-ref-prior'>{_esc(human)}</td>"
    parsed = _parse_source(source)
    if parsed and parsed[3] is not None:
        scope, name, table_idx, rr, cc = parsed
        cell_key = f"r{rr}c{cc}" if cc is not None else f"r{rr}"
        panel = _source_panel_id(scope, name, table_idx, report)
        return (
            f'<td class="src-ref"><span class="src-jump" '
            f'data-jump="{_esc(panel)}" data-jump-cell="{cell_key}" '
            f'data-jump-table="{table_idx}" '
            f'onclick="jumpToCell(this)">{_esc(human)}</span></td>'
        )
    section_source = _parse_section_source(source)
    if section_source and report is not None:
        scope, name, _ = section_source
        panel = _source_panel_id(scope, name, None, report)
        return (
            f'<td class="src-ref"><span class="src-jump" '
            f'data-jump="{_esc(panel)}" onclick="jumpToCheckSource(this)">'
            f'{_esc(human)}</span></td>'
        )
    period_source = _parse_period_source(source)
    if period_source and report is not None:
        scope, name, _ = period_source
        panel = _source_panel_id(scope, name, None, report)
        return (
            f'<td class="src-ref"><span class="src-jump" '
            f'data-jump="{_esc(panel)}" onclick="jumpToCheckSource(this)">'
            f'{_esc(human)}</span></td>'
        )
    return f"<td class='src-ref'>{_esc(human)}</td>"


_BODY_MATCH_CHECK_TYPES = {
    "fs_note_ref_amount_match",
    "fs_note_match",
    "primary_balance_reconciliation",
}
_CROSS_STATEMENT_CHECK_TYPES = {
    "statement_cash_tie",
    "statement_equity_tie",
    "cfs_note_match",
    "cashflow_reconciliation",
    "asset_note_bridge_check",
}


def _evidence_role_label(result: CheckResult, evidence, index: int) -> str:
    source = evidence.source or ""
    if evidence.role == "component":
        return "합산 근거"
    if evidence.role == "total":
        return "검증 대상"
    if result.check_type in {"prior_year_amount_match", "prior_year_beginning_balance_match"}:
        if _is_prior_source(source):
            return "기준 근거(전기 보고서)"
        return "대사 근거(당기 보고서)"
    if result.check_type == "statement_bs_equation":
        return "검증 대상" if index == 0 else "산식 근거"
    if result.check_type == "statement_subtotal":
        return "검증 대상" if index == 0 else "합산 근거"
    if result.check_type in _BODY_MATCH_CHECK_TYPES:
        if source.startswith("statement:"):
            return "검증 대상(본문)"
        if source.startswith("note:"):
            return "대사 근거(주석)"
    if result.check_type in _CROSS_STATEMENT_CHECK_TYPES:
        return "검증 대상" if index == 0 else "대사 근거"
    if source.startswith("statement:"):
        return "본문 위치"
    if source.startswith("note:"):
        return "주석 근거"
    return "근거"


def _render_note_reference_check(result: CheckResult) -> str:
    if not result.note_no or result.note_no in {"bs", "cf", "sce", "cross_statement"}:
        return ""
    refs: list[str] = []
    for ev in result.evidence:
        if not (ev.source or "").startswith("statement:"):
            continue
        refs.extend(_note_refs_from_label(ev.label))
    refs = list(dict.fromkeys(refs))
    if not refs:
        return ""
    ok = any(_note_no_matches_ref(result.note_no, ref) for ref in refs)
    ref_text = ", ".join(f"주{ref}" for ref in refs)
    if ok:
        return (
            f'<div class="callout ok">✓ 본문 행의 주석번호({ _esc(ref_text) })와 '
            f'현재 대사 주석 { _esc(result.note_no) }가 일치합니다.</div>'
        )
    return (
        f'<div class="callout warn">⚠ 본문 행의 주석번호({ _esc(ref_text) })와 '
        f'현재 대사 주석 { _esc(result.note_no) }가 다릅니다.</div>'
    )


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
    source_html = _render_note_source_blocks(section, panel_id, report, results)
    check_section = _render_note_check_groups(section, results, panel_id, report)

    return f"""<div class="panel" id="{_esc(panel_id)}">
  <div class="panel-title">{"" if not section.note_no else _esc(section.note_no) + ". "}{_esc(section.title)}</div>
  {check_section}
  {source_html}
</div>"""


def _render_note_source_blocks(
    section: ReportSection,
    panel_id: str,
    report: FullReport | None,
    results: list[CheckResult] | None = None,
) -> str:
    blocks: list[str] = []
    for idx, block in enumerate(section.blocks):
        if block.text:
            if block.raw_html:
                blocks.append(
                    f'<div class="note-text-original">{block.raw_html}</div>'
                )
            else:
                blocks.append(f'<pre class="note-text-block">{_esc(block.text)}</pre>')
            continue
        if block.table is None:
            continue
        table = block.table
        if block.raw_html:
            raw_html = _strip_xbrl_disclosure_caption_rows(block.raw_html)
            raw_html = _annotate_raw_total_marks(raw_html, results or [], table)
            raw_html = _normalize_xbrl_reader_tables(raw_html)
            blocks.append(
                f"""<div class="note-source-original" data-source-table="{table.index}">
  {raw_html}
</div>"""
            )
        else:
            rows_html = _render_table_rows(
                table,
                {},
                id_prefix=f"{panel_id}-table-{table.index}",
                report=report,
                total_results=results,
            )
            caption = table.heading or f"표 {table.index}"
            blocks.append(
                f"""<div class="statement-wrap note-source-table">
  <div class="statement-caption"><span>{_esc(caption)}</span></div>
  <table class="fs-table">{rows_html}</table>
</div>"""
            )
    if not blocks:
        return '<p class="empty-state">주석 원문 표를 찾을 수 없음</p>'
    return f"""<section class="note-source" aria-label="주석 원문">
  <div class="note-source-head">주석 원문</div>
  {"".join(blocks)}
</section>"""


def _annotate_raw_total_marks(
    raw_html: str,
    results: list[CheckResult],
    table: ReportTable,
) -> str:
    total_marks = _total_mark_details_for_table(results, table)
    if not raw_html or not total_marks:
        return raw_html
    soup = BeautifulSoup(raw_html, "html.parser")
    ordered_marks = sorted(
        total_marks.items(),
        key=lambda item: (
            item[0][0],
            item[0][1] is not None,
            item[0][1] if item[0][1] is not None else -1,
        ),
    )
    for (row_idx, col_idx), mark in ordered_marks:
        class_name = _total_status_class(mark.status)
        label = _total_status_label(mark.status)
        if col_idx is None:
            key_prefix = f"r{row_idx}c"
            cells = [
                cell for cell in soup.find_all(["td", "th"])
                if any(key.startswith(key_prefix) for key in _cell_keys(cell))
            ]
        else:
            key = f"r{row_idx}c{col_idx}"
            cells = [
                cell for cell in soup.find_all(["td", "th"])
                if key in _cell_keys(cell)
            ]
        for cell in cells:
            classes = list(cell.get("class") or [])
            for item in ("total-cell", class_name):
                if item not in classes:
                    classes.append(item)
            cell["class"] = classes
            cell["title"] = label
            formula_text = _total_formula_text(mark.result)
            if formula_text:
                cell["data-total-formula"] = formula_text
                cell["tabindex"] = "0"
                _append_total_formula_popover(soup, cell, mark.result)
    return str(soup)


def _total_formula_text(result: CheckResult) -> str:
    components = [ev for ev in result.evidence if ev.role == "component"]
    if components:
        expression = " + ".join(
            f"{_formula_label(ev.label)}({_formula_amount(ev.amount)})"
            for ev in components
        )
        expected = (
            result.expected
            if result.expected is not None
            else sum(ev.amount or 0 for ev in components)
        )
        lines = [f"{expression} = {_formula_amount(expected)}"]
    elif result.expected is not None:
        lines = [f"기대금액 = {_formula_amount(result.expected)}"]
    else:
        lines = []
    if result.actual is not None:
        lines.append(f"표시금액 = {_formula_amount(result.actual)}")
    if result.difference is not None:
        lines.append(f"차이 = {_formula_amount(result.difference)}")
    return "\n".join(lines)


def _formula_label(value: str) -> str:
    return _compact_text(value).replace("(", "[").replace(")", "]") or "항목"


def _formula_amount(value: int | None) -> str:
    return "—" if value is None else f"{value:,}"


def _render_total_formula_popover(result: CheckResult) -> str:
    formula_text = _total_formula_text(result)
    if not formula_text:
        return ""
    table_rows = "".join(
        f"<tr><td>{_esc(role)}</td><td>{_esc(label)}</td><td>{_esc(amount)}</td></tr>"
        for role, label, amount in _total_formula_rows(result)
    )
    copy_text = _total_formula_tsv(result)
    return (
        '<span class="total-formula-popover" role="tooltip">'
        f'<div class="total-formula-summary">{_esc(formula_text)}</div>'
        '<table class="total-formula-table"><thead><tr>'
        '<th>역할</th><th>항목</th><th>금액</th>'
        f'</tr></thead><tbody>{table_rows}</tbody></table>'
        f'<button type="button" class="formula-copy" data-copy-text="{_esc(copy_text)}" '
        'onclick="copyFormula(this,event)">표 복사</button>'
        '</span>'
    )


def _total_formula_rows(result: CheckResult) -> list[tuple[str, str, str]]:
    rows = [
        ("구성요소", _formula_label(ev.label), _formula_amount(ev.amount))
        for ev in result.evidence
        if ev.role == "component"
    ]
    if result.expected is not None:
        rows.append(("계산합계", "", _formula_amount(result.expected)))
    if result.actual is not None:
        rows.append(("표시금액", "", _formula_amount(result.actual)))
    if result.difference is not None:
        rows.append(("차이", "", _formula_amount(result.difference)))
    return rows


def _total_formula_tsv(result: CheckResult) -> str:
    rows = [("역할", "항목", "금액"), *_total_formula_rows(result)]
    return "\n".join("\t".join(row) for row in rows)


def _append_total_formula_popover(soup: BeautifulSoup, cell, result: CheckResult) -> None:
    for existing in cell.find_all(class_="total-formula-popover"):
        existing.decompose()
    fragment = BeautifulSoup(_render_total_formula_popover(result), "html.parser")
    for node in list(fragment.contents):
        cell.append(node)


def _normalize_xbrl_reader_tables(raw_html: str) -> str:
    if not raw_html:
        return raw_html
    soup = BeautifulSoup(raw_html, "html.parser")
    changed = False
    for table in list(soup.find_all("table")):
        if _is_nb_table(table):
            continue
        changed = _suppress_repeated_group_leading_cells(table) or changed
        reader_table = _reader_table_for_single_row_xbrl_detail(soup, table)
        if reader_table is not None:
            table.replace_with(reader_table)
            changed = True
    return str(soup) if changed else raw_html


def _is_nb_table(table) -> bool:
    classes = table.get("class") or []
    if isinstance(classes, str):
        classes = classes.split()
    return "nb" in classes


def _suppress_repeated_group_leading_cells(table) -> bool:
    body = table.find("tbody")
    if body is None:
        return False
    changed = False
    active_group = ""
    for row in body.find_all("tr", recursive=False):
        cells = row.find_all(["td", "th"], recursive=False)
        if not cells:
            continue
        first = cells[0]
        first_text = _compact_text(first.get_text(" ", strip=True))
        colspan = _int_html_attr(first.get("colspan"), default=1)
        if colspan >= 2 and first_text:
            active_group = first_text
            continue
        if (
            active_group
            and len(cells) >= 2
            and not first.get("colspan")
            and not first.get("rowspan")
            and first_text == active_group
        ):
            original = first.get_text(" ", strip=True)
            first.clear()
            classes = list(first.get("class") or [])
            if "xbrl-repeated-group-cell" not in classes:
                classes.append("xbrl-repeated-group-cell")
            first["class"] = classes
            first["aria-label"] = original
            changed = True
    return changed


def _reader_table_for_single_row_xbrl_detail(soup: BeautifulSoup, table):
    header = table.find("thead")
    body = table.find("tbody")
    if header is None or body is None:
        return None
    header_rows = header.find_all("tr", recursive=False)
    body_rows = body.find_all("tr", recursive=False)
    if len(header_rows) < 3 or len(body_rows) != 1:
        return None
    data_cells = body_rows[0].find_all(["td", "th"], recursive=False)
    if len(data_cells) < 7:
        return None
    header_grid = _expanded_header_grid(header_rows)
    if not header_grid:
        return None
    max_cols = max(len(row) for row in header_grid)
    if len(data_cells) < max_cols:
        return None
    groups_by_name: dict[str, list[tuple[str, int]]] = {}
    group_order: list[str] = []
    total_columns: list[int] = []
    for col_idx in range(1, min(len(data_cells), max_cols)):
        path = _header_path(header_grid, col_idx)
        group = _xbrl_detail_group(path)
        metric = _xbrl_detail_metric(path)
        if group and metric:
            if group not in groups_by_name:
                groups_by_name[group] = []
                group_order.append(group)
            groups_by_name[group].append((metric, col_idx))
        elif _xbrl_total_header(path):
            total_columns.append(col_idx)
    metric_order = _xbrl_metric_order(groups_by_name)
    if len(group_order) < 2 or len(metric_order) < 2:
        return None

    new_table = soup.new_tag("table")
    new_table["class"] = ["xbrl-reader-table"]
    new_table["data-xbrl-reader"] = "single-row-detail"

    new_thead = soup.new_tag("thead")
    head_row = soup.new_tag("tr")
    first_head = soup.new_tag("th")
    first_head.string = "구분"
    head_row.append(first_head)
    for metric in metric_order:
        th = soup.new_tag("th")
        th.string = metric
        head_row.append(th)
    new_thead.append(head_row)
    new_table.append(new_thead)

    new_tbody = soup.new_tag("tbody")
    for group in group_order:
        row = soup.new_tag("tr")
        label_cell = soup.new_tag("td")
        label_cell.string = group
        row.append(label_cell)
        by_metric = {metric: col for metric, col in groups_by_name[group]}
        for metric in metric_order:
            cell = (
                _copy_data_cell_for_reader(soup, data_cells[by_metric[metric]])
                if metric in by_metric
                else soup.new_tag("td")
            )
            row.append(cell)
        new_tbody.append(row)
    for col_idx in total_columns:
        label = _xbrl_total_header(_header_path(header_grid, col_idx))
        if not label:
            continue
        row = soup.new_tag("tr")
        label_cell = soup.new_tag("td")
        label_cell.string = label
        row.append(label_cell)
        value_cell = _copy_data_cell_for_reader(soup, data_cells[col_idx])
        for metric in metric_order:
            if metric == metric_order[-1]:
                row.append(value_cell)
            else:
                row.append(soup.new_tag("td"))
        new_tbody.append(row)
    new_table.append(new_tbody)
    return new_table


def _expanded_header_grid(header_rows) -> list[list[object]]:
    grid: list[list[object]] = []
    rowspans: dict[int, tuple[object, int]] = {}
    for row in header_rows:
        out: list[object] = []
        col_idx = 0
        cells = row.find_all(["td", "th"], recursive=False)
        for cell in cells:
            while col_idx in rowspans:
                span_cell, remaining = rowspans[col_idx]
                out.append(span_cell)
                if remaining <= 1:
                    del rowspans[col_idx]
                else:
                    rowspans[col_idx] = (span_cell, remaining - 1)
                col_idx += 1
            colspan = _int_html_attr(cell.get("colspan"), default=1)
            rowspan = _int_html_attr(cell.get("rowspan"), default=1)
            for offset in range(colspan):
                out.append(cell)
                if rowspan > 1:
                    rowspans[col_idx + offset] = (cell, rowspan - 1)
            col_idx += colspan
        while col_idx in rowspans:
            span_cell, remaining = rowspans[col_idx]
            out.append(span_cell)
            if remaining <= 1:
                del rowspans[col_idx]
            else:
                rowspans[col_idx] = (span_cell, remaining - 1)
            col_idx += 1
        grid.append(out)
    return grid


def _header_path(header_grid: list[list[object]], col_idx: int) -> list[str]:
    values: list[str] = []
    for row in header_grid:
        if col_idx >= len(row):
            continue
        text = _clean_header_text(row[col_idx].get_text(" ", strip=True))
        if text and (not values or values[-1] != text):
            values.append(text)
    return values


def _xbrl_detail_group(path: list[str]) -> str:
    if len(path) < 3:
        return ""
    candidates = [
        item for item in path[:-1]
        if item and item not in {"장부금액", "공시금액"}
    ]
    if len(candidates) < 2:
        return ""
    return candidates[-1]


def _xbrl_detail_metric(path: list[str]) -> str:
    if not path:
        return ""
    metric = path[-1]
    if metric in {"장부금액", "공시금액"}:
        return ""
    return metric


def _xbrl_total_header(path: list[str]) -> str:
    if not path:
        return ""
    label = path[-1]
    return label if _compact_text(label).endswith("합계") else ""


def _xbrl_metric_order(groups_by_name: dict[str, list[tuple[str, int]]]) -> list[str]:
    order: list[str] = []
    for columns in groups_by_name.values():
        for metric, _ in columns:
            if metric not in order:
                order.append(metric)
    return order


def _copy_data_cell_for_reader(soup: BeautifulSoup, source_cell):
    copied = BeautifulSoup(str(source_cell), "html.parser").find(["td", "th"])
    if copied is None:
        return soup.new_tag("td")
    copied.name = "td"
    for attr in ("colspan", "rowspan", "width", "height"):
        if copied.has_attr(attr):
            del copied[attr]
    return copied


def _clean_header_text(value: str) -> str:
    return " ".join((value or "").replace("\xa0", " ").split())


def _int_html_attr(value: object, *, default: int) -> int:
    try:
        return max(1, int(str(value)))
    except (TypeError, ValueError):
        return default


def _strip_xbrl_disclosure_caption_rows(raw_html: str) -> str:
    if not raw_html:
        return raw_html
    soup = BeautifulSoup(raw_html, "html.parser")
    changed = False
    for table in soup.find_all("table"):
        classes = table.get("class") or []
        if isinstance(classes, str):
            classes = classes.split()
        if "nb" not in classes:
            for row in list(table.find_all("tr")):
                if _is_xbrl_top_aggregate_row(row):
                    row.decompose()
                    changed = True
            continue
        for row in list(table.find_all("tr")):
            if _is_xbrl_disclosure_caption_row(row):
                row.decompose()
                changed = True
        if not any(_text_content(row) for row in table.find_all("tr")):
            table.decompose()
            changed = True
    return str(soup) if changed else raw_html


def _is_xbrl_disclosure_caption_row(row) -> bool:
    cells = row.find_all(["td", "th"], recursive=False)
    raw_texts = [cell.get_text(" ", strip=True) for cell in cells]
    texts = [_compact_text(text) for text in raw_texts]
    texts = [text for text in texts if text]
    if texts and all(_is_period_or_unit_marker_text(text) for text in texts):
        return True
    if len(texts) != 1:
        return False
    text = texts[0]
    if _is_period_or_unit_marker_text(text) or _is_explanatory_nb_text(text):
        return False
    if "공시" in text:
        return len(text) <= 80
    if any(token in text for token in ("세부내역", "세부정보")):
        return True
    if len(text) <= 30 and not _looks_like_sentence_text(text):
        return True
    return False


def _is_xbrl_top_aggregate_row(row) -> bool:
    cells = row.find_all(["td", "th"], recursive=False)
    if len(cells) < 2:
        return False
    first = cells[0]
    if first.get("rowspan"):
        return False
    try:
        colspan = int(first.get("colspan") or "1")
    except ValueError:
        colspan = 1
    if colspan < 2:
        return False
    label = _compact_text(first.get_text(" ", strip=True))
    if label not in {"금융자산", "금융부채", "총금융자산", "총금융부채"}:
        return False
    values = [_compact_text(cell.get_text(" ", strip=True)) for cell in cells[1:]]
    values = [value for value in values if value]
    return bool(values) and all(parse_amount(value) is not None for value in values)


def _is_period_or_unit_marker_text(text: str) -> bool:
    normalized = text.strip("[]<>()")
    if "단위" in text:
        return True
    return normalized in {"당기", "전기", "당기말", "전기말"}


def _is_explanatory_nb_text(text: str) -> bool:
    if text.startswith("(주") or text.startswith("주석"):
        return True
    return len(text) > 80 or _looks_like_sentence_text(text)


def _looks_like_sentence_text(text: str) -> bool:
    return any(marker in text for marker in ("습니다", "합니다", "되었습니다", "입니다", "없습니다"))


def _text_content(node) -> str:
    return _compact_text(node.get_text(" ", strip=True))


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def _cell_keys(cell) -> list[str]:
    return str(cell.get("data-cell-keys") or "").split()


def _render_note_statement_completeness(
    section: ReportSection,
    report: FullReport | None,
    results: list[CheckResult],
) -> str:
    if report is None or not section.note_no:
        return ""
    linked_rows = _statement_rows_referencing_note(report, section)
    if not linked_rows and not results:
        return ""
    if linked_rows:
        body_rows = "".join(
            f"<tr><td>{_esc(item['label'])}</td><td>{_esc(item['amount'])}</td>"
            f"{_render_source_jump_cell(item['source'], report)}</tr>"
            for item in linked_rows[:8]
        )
        more = ""
        if len(linked_rows) > 8:
            more = f'<div class="completeness-more">외 {len(linked_rows) - 8}건</div>'
        return f"""<section class="note-completeness note-completeness-ok" aria-label="본문 공시계정 연결">
  <div class="note-source-head">본문 공시계정 연결</div>
  <div class="callout ok">특이사항 없음 · 본문에서 이 주석번호를 참조한 공시계정 {len(linked_rows)}건을 확인했습니다.</div>
  <table class="src-tbl completeness-table">
    <thead><tr><th>공시계정</th><th>금액</th><th>본문 위치</th></tr></thead>
    <tbody>{body_rows}</tbody>
  </table>
  {more}
</section>"""
    return """<section class="note-completeness note-completeness-warn" aria-label="본문 공시계정 연결">
  <div class="note-source-head">본문 공시계정 연결</div>
  <div class="callout unc">확인 필요 · 이 주석번호를 참조한 재무제표 본문 공시계정을 찾지 못했습니다.</div>
</section>"""


def _statement_rows_referencing_note(report: FullReport, note: ReportSection) -> list[dict[str, str]]:
    linked: list[dict[str, str]] = []
    for section in report.statements:
        if note.scope and section.scope and section.scope != note.scope:
            continue
        statement_kind = _statement_kind(section)
        if not statement_kind:
            continue
        for block in section.blocks:
            table = block.table
            if table is None or not table.rows:
                continue
            headers = table.rows[0]
            for row_idx, row in enumerate(table.rows[1:], start=1):
                if not row:
                    continue
                label = row[0].strip()
                refs = _note_refs_from_label(label)
                if not any(_note_no_matches_ref(note.note_no, ref) for ref in refs):
                    continue
                amount, col_idx = _first_amount_with_column(row)
                amount_text = f"{amount * table.unit_multiplier:,}" if amount is not None else "—"
                source = f"statement:{statement_kind}/table:{table.index}/row:{row_idx}"
                if col_idx is not None:
                    source += f"/col:{col_idx}"
                period = headers[col_idx] if col_idx is not None and col_idx < len(headers) else ""
                linked.append({
                    "label": label,
                    "amount": amount_text,
                    "source": source,
                    "period": period,
                })
    return linked


def _first_amount_with_column(row: list[str]) -> tuple[int | None, int | None]:
    for col_idx, cell in enumerate(row[1:], start=1):
        amount = parse_amount(cell)
        if amount is not None:
            return amount, col_idx
    return None, None


_NOTE_CHECK_ORDER = ("total", "body", "cashflow", "note_ref", "note", "prior", "other")
_NOTE_CHECK_LABELS = {
    "total": "합계검증",
    "body": "본문대사",
    "cashflow": "현금흐름대사",
    "note_ref": "말주기 참조",
    "note": "주석간대사",
    "prior": "전기대사",
    "other": "기타검증",
}


def _note_check_group_key(result: CheckResult) -> str:
    check_type = result.check_type
    if check_type in {"total_check", "note_layout_formula_check"} or "rollforward" in check_type:
        return "total"
    if check_type in {"cashflow_reconciliation", "cfs_note_match", "asset_note_bridge_check"}:
        return "cashflow"
    if check_type in {"fs_note_ref_amount_match", "fs_note_match", "primary_balance_reconciliation"}:
        return "body"
    if check_type == "note_reference_check":
        return "note_ref"
    if check_type == "note_note_match":
        return "note"
    if check_type.startswith("prior_"):
        return "prior"
    return "other"


def _render_note_check_groups(
    section: ReportSection,
    results: list[CheckResult],
    panel_id: str,
    report: FullReport | None,
) -> str:
    if not results:
        return ""
    grouped: dict[str, list[CheckResult]] = {}
    for result in results:
        key = _note_check_group_key(result)
        if key == "total":
            continue
        grouped.setdefault(key, []).append(result)
    group_keys = [key for key in _NOTE_CHECK_ORDER if grouped.get(key)]
    if not group_keys:
        return ""
    tabs = "".join(
        f'<button type="button" class="note-check-tab" data-note-filter="{_esc(key)}">'
        f'{_esc(_NOTE_CHECK_LABELS[key])} {len(grouped[key])}</button>'
        for key in group_keys
    )
    rows = ""
    for key in group_keys:
        group_results = grouped[key]
        representative = group_results[0]
        for result in group_results[1:]:
            representative = _worse(representative, result)
        dd_id = f"dd-note-group-{_safe_id(panel_id)}-{key}"
        badge_class = _status_to_badge_class(representative.status)
        badge_label = _status_to_badge_label(representative.status)
        rows += f"""<div class="note-check-group" data-note-group="{_esc(key)}" onclick="showReview('{dd_id}', this)">
  <span class="expand-tri" id="tri-{dd_id}">▶</span>
  <span class="check-name">{_esc(_NOTE_CHECK_LABELS[key])}</span>
  <span class="check-vals"><span>{len(group_results)}건</span></span>
  <span class="badge {badge_class}">{badge_label}</span>
</div>
<div class="dd-inline note-group-detail" id="{dd_id}">
  {_render_note_group_detail(section, group_results, report)}
</div>"""
    return f"""<section class="note-review" aria-label="주석 검증">
  <div class="check-summary-head">검증 결과</div>
  <div class="note-check-tabs" data-note-tabs="#{_esc(panel_id)}">
    <button type="button" class="note-check-tab" data-note-filter="all" aria-pressed="true">전체 {sum(len(grouped[key]) for key in group_keys)}</button>
    {tabs}
  </div>
  <div class="note-review-groups">{rows}</div>
</section>"""


def _render_note_group_detail(
    section: ReportSection,
    results: list[CheckResult],
    report: FullReport | None,
) -> str:
    cards = ""
    for result in results:
        badge_class = _status_to_badge_class(result.status)
        badge_label = _status_to_badge_label(result.status)
        exp_str = f"{result.expected:,}" if result.expected is not None else "—"
        act_str = f"{result.actual:,}" if result.actual is not None else "—"
        diff_str = f"차이 {result.difference:,}" if result.difference is not None else ""
        title_disp = _display_check_title(result.title, section)
        cards += f"""<article class="note-check-card">
  <div class="note-check-card-head">
    <span class="check-name">{_esc(title_disp)}</span>
    <span class="check-vals"><span>{exp_str}</span><span>{act_str}</span><span>{diff_str}</span></span>
    <span class="badge {badge_class}">{badge_label}</span>
  </div>
  {_render_drilldown(result, report)}
</article>"""
    return cards


# ── Parse Uncertain Panel ─────────────────────────────────────────────────────

def _render_parse_uncertain_panel(
    results: list[CheckResult],
    *,
    panel_id: str = "panel-parse-diag",
) -> str:
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

    return f"""<div class="panel" id="{_esc(panel_id)}">
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
  --bg:#f5f7f6; --surface:#ffffff; --surface-2:#eef3f2; --surface-3:#f8faf9;
  --border:#d7e0df; --text:#12201f; --muted:#657574;
  --accent:#0f766e; --accent-dim:#dff3ef;
  --review:#1d4ed8; --review-dim:#eaf2ff; --review-border:#9bbcf3;
  --paper:#ffffff; --paper-border:#cfd8dc;
  --warn:#b7791f; --warn-dim:#fff4ce;
  --ok:#12805c; --ok-dim:#dff6ec;
  --down:#b42318; --down-dim:#fdecea;
  --sidebar-bg:#143431; --sidebar-text:#b7c8c5;
  --sidebar-active:#ffffff; --sidebar-accent:#35c1a7;
  --font:Pretendard,ui-sans-serif,system-ui,-apple-system,sans-serif;
  --review-rail-width:min(560px,calc(100vw - 280px));
}
*{box-sizing:border-box;margin:0;padding:0;}
body{font-family:var(--font);background:var(--bg);color:var(--text);font-size:14px;line-height:1.62;letter-spacing:0;}
.shell{display:grid;grid-template-columns:258px minmax(760px,1fr);min-height:100vh;align-items:start;}
aside{background:var(--sidebar-bg);border-right:1px solid rgba(255,255,255,.08);padding:18px 0;position:sticky;top:0;height:100vh;overflow-y:auto;}
.sidebar-brand{padding:0 16px 14px;border-bottom:1px solid rgba(255,255,255,.08);margin-bottom:8px;}
.sidebar-brand-name{font-size:13px;font-weight:800;color:var(--sidebar-active);}
.sidebar-brand-sub{font-size:11px;color:#7fa09b;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.report-scope-switch{display:grid;grid-template-columns:1fr 1fr;gap:6px;padding:0 12px 14px;}
.report-scope-button{appearance:none;border:1px solid rgba(255,255,255,.16);background:rgba(255,255,255,.05);color:#c7dcd8;border-radius:6px;padding:7px 6px;font-size:12px;font-weight:900;cursor:pointer;}
.report-scope-button:hover,.report-scope-button.active{background:rgba(53,193,167,.18);border-color:rgba(53,193,167,.55);color:#fff;}
.scope-nav.hidden,.report-scope-shell.hidden{display:none;}
.scope-shell-kicker{font-size:12px;font-weight:900;color:var(--accent);margin:0 0 8px;}
.sidebar-section{padding:10px 16px 4px;font-size:10px;font-weight:800;color:#7fa09b;text-transform:uppercase;letter-spacing:.06em;}
.nav-item{display:flex;align-items:center;gap:8px;padding:8px 16px;font-size:13px;font-weight:500;color:var(--sidebar-text);cursor:pointer;border-left:3px solid transparent;}
.nav-item:hover,.nav-item.active{background:rgba(255,255,255,.05);color:var(--sidebar-active);}
.nav-item.active{background:rgba(53,193,167,.16);border-left-color:var(--sidebar-accent);font-weight:800;}
.nav-badge{margin-left:auto;font-size:10px;padding:1px 5px;border-radius:3px;font-weight:700;}
.nb-ok{background:rgba(18,128,92,.22);color:#8be1c0;}
.nb-warn{background:rgba(183,121,31,.24);color:#ffd37a;}
.nb-unc{background:rgba(183,200,197,.16);color:#c5d2d0;}
.sidebar-divider{border:none;border-top:1px solid rgba(255,255,255,.06);margin:8px 0;}
main{padding:24px 30px;min-width:0;background:var(--bg);}
body.review-open main{padding-right:calc(30px + var(--review-rail-width));}
.review-rail{position:fixed;top:0;right:0;z-index:30;width:var(--review-rail-width);height:100vh;overflow-y:auto;border-left:1px solid var(--review-border);background:#f8fbff;padding:18px 18px 22px;box-shadow:-12px 0 28px rgba(15,23,42,.14);transform:translateX(104%);opacity:0;pointer-events:none;transition:transform .18s ease,opacity .18s ease;}
body.review-open .review-rail{transform:translateX(0);opacity:1;pointer-events:auto;}
.review-rail-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding-bottom:12px;border-bottom:1px solid var(--review-border);margin-bottom:10px;}
.review-rail-kicker{font-size:10px;font-weight:900;color:var(--review);letter-spacing:.08em;}
.review-rail-title{font-size:15px;font-weight:900;color:#0f172a;margin-top:2px;}
.review-rail-close{font:inherit;font-size:11px;font-weight:800;border:1px solid var(--review-border);background:#fff;color:#1d4ed8;border-radius:6px;padding:5px 8px;cursor:pointer;}
.review-rail-close:hover{background:#eff6ff;}
.review-rail-tabs{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0 14px;}
.review-rail-tabs span{font-size:11px;font-weight:800;color:#1e3a8a;border:1px solid #bfdbfe;background:#fff;border-radius:999px;padding:3px 8px;}
.review-rail-body{font-size:13px;color:#172554;overflow-x:hidden;}
.review-empty{border:1px dashed var(--review-border);border-radius:8px;background:#fff;padding:16px;color:#64748b;font-size:12px;line-height:1.6;}
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
.panel-title{font-size:18px;font-weight:900;margin-bottom:3px;}
.panel-sub{font-size:13px;color:var(--muted);margin-bottom:16px;}
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
.status-overview{display:grid;grid-template-columns:minmax(240px,340px) minmax(0,1fr);gap:14px;align-items:start;margin-top:10px;}
.status-card-grid{display:grid;grid-template-columns:1fr;gap:8px;}
.status-card{font:inherit;text-align:left;display:grid;grid-template-columns:auto 1fr;gap:0 10px;align-items:center;border:1px solid var(--border);border-radius:7px;background:#fff;padding:10px 12px;cursor:pointer;min-height:58px;}
.status-card:hover,.status-card[aria-pressed="true"]{border-color:#9fd3ca;background:#fbfefd;box-shadow:inset 3px 0 0 var(--accent);}
.status-value{grid-row:span 2;min-width:42px;font-size:24px;font-weight:900;font-variant-numeric:tabular-nums;}
.status-label{font-size:12px;font-weight:900;}
.status-attention .status-value,.status-not_tested .status-value{color:var(--warn);}
.status-matched .status-value{color:var(--ok);}
.status-explained .status-value{color:var(--accent);}
.status-list{border:1px solid var(--border);border-radius:7px;background:#fff;overflow:hidden;max-height:340px;overflow-y:auto;}
.status-list-row{font:inherit;width:100%;display:grid;grid-template-columns:minmax(0,1fr) minmax(120px,220px) auto auto;gap:8px;align-items:center;border:0;border-bottom:1px solid #e2e8eb;background:#fff;padding:9px 11px;text-align:left;cursor:pointer;}
.status-list-row:hover{background:#f8fbff;}
.status-list-row:last-child{border-bottom:0;}
.status-row-main{font-size:12px;font-weight:800;min-width:0;color:#0f172a;}
.status-row-source{font-size:11px;color:#64748b;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.status-row-diff{font-size:11px;color:#64748b;font-variant-numeric:tabular-nums;white-space:nowrap;}
.status-list-empty{padding:12px;color:var(--muted);font-size:12px;}
.statement-wrap{border:0;border-radius:0;overflow:auto;margin-bottom:18px;background:transparent;}
.statement-caption{padding:4px 0 8px;background:transparent;border-bottom:0;font-size:13px;font-weight:800;color:#314241;}
.fs-table{width:100%;min-width:760px;border-collapse:collapse;font-size:13px;}
.fs-table th{padding:9px 14px;background:#fff;border-bottom:1px solid var(--paper-border);font-size:12px;font-weight:800;color:#2e3b3a;text-align:right;}
.fs-table th:first-child{text-align:left;}
.fs-table td{padding:9px 14px;border-bottom:1px solid #e2e8eb;text-align:right;font-variant-numeric:tabular-nums;color:#172120;}
.fs-table td:first-child{text-align:left;}
.fs-table th,.fs-table td{white-space:nowrap;}
.fs-table tr:last-child td{border-bottom:none;}
.verified-ok td:first-child::after{content:"✓";display:inline-flex;align-items:center;justify-content:center;margin-left:8px;width:16px;height:16px;background:var(--ok-dim);color:var(--ok);border-radius:3px;font-size:10px;font-weight:800;vertical-align:middle;}
.verified-warn td:first-child::after{content:"⚠";display:inline-flex;align-items:center;justify-content:center;margin-left:8px;width:16px;height:16px;background:var(--warn-dim);color:var(--warn);border-radius:3px;font-size:10px;font-weight:800;vertical-align:middle;}
.verified-uncertain td:first-child::after{content:"?";display:inline-flex;align-items:center;justify-content:center;margin-left:8px;width:16px;height:16px;background:var(--surface-2);color:var(--muted);border-radius:3px;font-size:10px;font-weight:800;vertical-align:middle;}
.verified-ok{cursor:pointer;} .verified-ok:hover td{background:#f0fdf4;}
.verified-warn{cursor:pointer;} .verified-warn:hover td{background:#fffbeb;}
.verified-uncertain{cursor:pointer;} .verified-uncertain:hover td{background:var(--surface);}
.dd-row{display:none;}
.dd-cell{padding:0!important;}
.dd-inner,.dd-inline{display:none;padding:14px 18px;background:var(--review-dim);border-top:2px solid var(--review-border);border-left:4px solid var(--review);}
.dd-inner.open,.dd-inline.open{display:none;}
.dd-title{font-size:14px;font-weight:900;margin-bottom:10px;color:#173b86;}
.comparison-summary{border:1px solid var(--review-border);border-radius:8px;background:#fff;margin:0 0 10px;overflow:hidden;}
.comparison-head{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:8px 10px;border-bottom:1px solid var(--review-border);background:#eef5ff;font-size:11px;}
.comparison-head span{font-weight:900;color:#1e3a8a;}
.comparison-head strong{font-size:11px;color:#475569;}
.comparison-grid{display:grid;grid-template-columns:minmax(0,1fr) 24px minmax(0,1fr);gap:8px;align-items:stretch;padding:10px;}
.comparison-side{min-width:0;border:1px solid #e2e8f0;border-radius:6px;background:#fbfdff;padding:8px;}
.comparison-side-label{font-size:11px;font-weight:900;color:#334155;margin-bottom:6px;}
.comparison-item{display:grid;gap:3px;padding:6px 0;border-top:1px solid #e6edf7;}
.comparison-item:first-of-type{border-top:0;padding-top:0;}
.comparison-item-main{font-size:12px;font-weight:800;color:#0f172a;overflow-wrap:anywhere;}
.comparison-item-meta{display:grid;gap:2px;font-size:10px;color:#64748b;font-variant-numeric:tabular-nums;}
.comparison-arrow{display:flex;align-items:center;justify-content:center;color:#64748b;font-weight:900;}
.comparison-empty,.comparison-more{font-size:11px;color:#64748b;}
.comparison-math{padding:8px 10px;border-top:1px solid var(--review-border);background:#fffefa;font-size:11px;color:#334155;font-variant-numeric:tabular-nums;}
.src-tbl{width:100%;border-collapse:collapse;font-size:12px;margin-bottom:8px;}
.src-tbl th{background:#dbeafe;padding:6px 9px;border:1px solid var(--review-border);font-size:11px;color:#1e3a8a;}
.src-tbl td{padding:7px 9px;border:1px solid var(--review-border);background:#fff;color:#172554;}
.review-rail .src-tbl{width:100%;min-width:100%;table-layout:auto;}
.review-rail .src-tbl th,.review-rail .src-tbl td{white-space:normal;overflow-wrap:anywhere;}
.src-ref{color:var(--muted);font-size:10px;}
.callout{margin-top:8px;padding:7px 10px;border-radius:5px;font-size:11px;}
.callout.ok{background:var(--ok-dim);border:1px solid #bbf7d0;color:#166534;}
.callout.warn{background:var(--warn-dim);border:1px solid #fde68a;color:#92400e;}
.callout.unc{background:var(--surface-2);border:1px solid var(--border);color:var(--muted);}
.check-summary{border:1px solid var(--review-border);border-radius:8px;overflow:hidden;margin-top:8px;background:var(--review-dim);}
.check-summary-head{padding:9px 14px;background:#dbeafe;border-bottom:1px solid var(--review-border);font-size:11px;font-weight:800;color:#1e3a8a;}
.check-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:10px 14px;border-bottom:1px solid var(--border);font-size:13px;cursor:pointer;}
.check-row:last-child{border-bottom:none;}
.check-row:hover{background:var(--surface);}
.check-name{flex:1 1 220px;min-width:0;}
.check-kind{display:block;margin-bottom:2px;font-size:10px;font-weight:900;color:#64748b;}
.check-title{display:block;}
.check-vals{display:flex;gap:14px;flex:0 1 auto;flex-wrap:wrap;font-variant-numeric:tabular-nums;color:var(--muted);font-size:11px;}
.badge{display:inline-flex;align-items:center;padding:2px 7px;border-radius:4px;font-size:11px;font-weight:700;}
.badge-ok{background:var(--ok-dim);color:#166534;}
.badge-exp{background:var(--review-dim);color:#1e3a8a;}
.badge-warn{background:var(--warn-dim);color:#92400e;}
.badge-unc{background:var(--surface-2);color:var(--muted);}
.expand-tri{font-size:9px;color:var(--muted);transition:transform .15s;display:inline-block;}
.diag-card{border:1px solid var(--border);border-radius:7px;padding:14px;margin-bottom:12px;}
.diag-title{font-size:13px;font-weight:700;margin-bottom:6px;}
.diag-reason{margin-bottom:8px;font-size:12px;}
.diag-candidates{margin-left:16px;font-size:11px;color:var(--muted);}
.diag-guide{margin-top:8px;font-size:11px;color:var(--muted);}
.acct-state{font-size:11px;font-weight:700;padding:2px 7px;border-radius:3px;border:1px solid var(--border);white-space:nowrap;}
.as-ok{color:var(--ok);} .as-note{color:var(--review);} .as-struct{color:#475569;} .as-exp{color:var(--review);} .as-warn{color:var(--warn);} .as-unc{color:var(--muted);} .as-nt{color:#94a3b8;}
.state-col{width:64px;text-align:center;}
.tech-detail{margin-top:8px;font-size:11px;color:var(--muted);} .tech-detail code{font-size:10px;}
.src-jump{color:var(--accent);cursor:pointer;text-decoration:underline dotted;}
.total-cell{position:relative;cursor:help;}
.total-cell.total-ok{box-shadow:inset 0 0 0 2px #16a34a;background:#f0fdf4!important;}
.total-cell.total-warn{box-shadow:inset 0 0 0 2px #dc2626;background:#fef2f2!important;}
.total-cell.total-unc{box-shadow:inset 0 0 0 2px #f59e0b;background:#fffbeb!important;}
.total-formula-popover{display:none;position:absolute;right:8px;top:calc(100% + 6px);z-index:25;min-width:360px;max-width:560px;text-align:left;white-space:normal;background:#0f172a;color:#f8fafc;border:1px solid #334155;border-radius:7px;box-shadow:0 14px 32px rgba(15,23,42,.24);padding:10px;font-variant-numeric:tabular-nums;}
.total-formula-summary{white-space:pre-wrap;font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;color:#f8fafc;margin-bottom:8px;}
.total-formula-table{width:100%;border-collapse:collapse;margin:0 0 8px;background:#0f172a;color:#f8fafc;}
.total-formula-table th,.total-formula-table td{border:1px solid #475569;padding:4px 6px;font-size:11px;line-height:1.35;white-space:nowrap;}
.total-formula-table th{background:#1e293b;color:#dbeafe;font-weight:800;text-align:left;}
.total-formula-table td:last-child{text-align:right;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;}
.total-cell:hover .total-formula-popover,.total-cell:focus .total-formula-popover,.total-cell:focus-within .total-formula-popover{display:block;}
.formula-copy{font:inherit;font-size:11px;font-weight:800;border:1px solid #93c5fd;background:#eff6ff;color:#1d4ed8;border-radius:5px;padding:3px 8px;cursor:pointer;}
.total-mark.total-ok td{border-top:2px solid #16a34a!important;border-bottom:2px solid #16a34a!important;}
.total-mark.total-ok td:first-child{border-left:2px solid #16a34a!important;}
.total-mark.total-ok td:last-child{border-right:2px solid #16a34a!important;}
.total-mark.total-warn td{border-top:2px solid #dc2626!important;border-bottom:2px solid #dc2626!important;}
.total-mark.total-warn td:first-child{border-left:2px solid #dc2626!important;}
.total-mark.total-warn td:last-child{border-right:2px solid #dc2626!important;}
.total-mark.total-unc td{border-top:2px solid #f59e0b!important;border-bottom:2px solid #f59e0b!important;}
.total-mark.total-unc td:first-child{border-left:2px solid #f59e0b!important;}
.total-mark.total-unc td:last-child{border-right:2px solid #f59e0b!important;}
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
.qa-summary{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:2px 0 14px;font-size:12px;color:var(--muted);}
.qa-summary span{display:inline-flex;align-items:center;min-height:24px;border:1px solid var(--border);background:#fff;border-radius:5px;padding:2px 8px;}
.qa-status{font-weight:900;}
.qa-status-pass{color:var(--ok);background:var(--ok-dim)!important;border-color:#bbf7d0!important;}
.qa-status-warn{color:var(--warn);background:var(--warn-dim)!important;border-color:#fde68a!important;}
.qa-status-fail{color:#991b1b;background:#fee2e2!important;border-color:#fecaca!important;}
.backlog-category{margin:0 0 16px;}
.backlog-category-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:8px 0;font-size:13px;font-weight:900;color:#0f172a;}
.backlog-count{font-size:11px;color:#475569;background:#f1f5f9;border:1px solid #d7e2e8;border-radius:999px;padding:2px 8px;}
.backlog-card-list{display:grid;gap:10px;}
.backlog-card{background:#fff;border:1px solid #d7e2e8;border-radius:7px;padding:11px 12px;}
.backlog-card-head{display:flex;align-items:center;gap:8px;justify-content:space-between;margin-bottom:6px;}
.backlog-rule{font-size:10px;font-weight:900;color:#1d4ed8;background:#eff6ff;border:1px solid #bfdbfe;border-radius:999px;padding:2px 7px;}
.backlog-status{font-size:10px;font-weight:800;color:#92400e;background:#fffbeb;border:1px solid #fde68a;border-radius:999px;padding:2px 7px;}
.backlog-title{font-size:13px;font-weight:900;margin-bottom:8px;color:#111827;}
.backlog-grid{display:grid;grid-template-columns:88px minmax(0,1fr);gap:5px 10px;font-size:12px;line-height:1.5;}
.backlog-grid dt{color:#64748b;font-weight:800;}
.backlog-grid dd{min-width:0;color:#1f2937;}
.backlog-grid code{font-size:11px;color:#334155;white-space:normal;word-break:break-all;}
.backlog-more{font-size:11px;color:#64748b;margin-top:6px;}
.check-row[hidden]{display:none;}
.review-source-active td{background:#eaf2ff!important;}
.review-source-active td:first-child{box-shadow:inset 4px 0 0 var(--review);}
.check-row.review-source-active,.note-check-group.review-source-active{background:#eaf2ff!important;box-shadow:inset 4px 0 0 var(--review);}
.note-source{margin-bottom:22px;max-width:100%;}
.note-source-head{font-size:11px;font-weight:800;color:var(--muted);margin:8px 0 10px;}
.note-text-block{white-space:pre-wrap;font:inherit;font-size:13px;line-height:1.68;background:transparent;border:0;border-radius:0;padding:4px 0;margin-bottom:10px;color:#151f1f;}
.note-text-original{font-size:13px;line-height:1.7;margin:0 0 12px;color:#151f1f;}
.note-text-original p,.note-text-original div{margin:0 0 7px;}
.note-text-original table{border-collapse:collapse;}
.note-source-original{overflow:auto;margin:0 0 18px;background:#fff;border:1px solid #d8e3e6;border-radius:6px;padding:10px 12px;box-shadow:0 1px 2px rgba(15,23,42,.04);}
.note-source-original table{border-collapse:collapse;width:max-content;min-width:100%;max-width:none;margin:0 0 10px;color:#111827;}
.note-source-original table.nb{width:100%;min-width:0;margin:0 0 8px;}
.note-source-original th,.note-source-original td{font-size:13px;line-height:1.45;vertical-align:middle;padding:7px 10px;border:1px solid #d7e0e3;background:#fff;white-space:nowrap;font-variant-numeric:tabular-nums;}
.note-source-original table.nb th,.note-source-original table.nb td{border:0;background:transparent;padding:2px 0;font-weight:700;color:#263534;}
.note-source-original table:not(.nb) thead tr:first-child > th,.note-source-original table:not(.nb) thead tr:first-child > td{background:#f5f8fa;font-weight:800;text-align:center;color:#20302f;}
.note-source-original table:not(.nb) tr > :first-child{text-align:left;white-space:nowrap;min-width:220px;}
.note-source-original table:not(.nb) thead tr:first-child > :first-child{background:#f5f8fa;}
.note-source-original .xbrl-repeated-group-cell{background:#fbfcfd;color:transparent;}
.note-source-original .xbrl-reader-table{width:max-content;min-width:720px;border-collapse:collapse;margin:0 0 10px;color:#111827;}
.note-source-original .xbrl-reader-table th,.note-source-original .xbrl-reader-table td{font-size:13px;line-height:1.45;padding:7px 10px;border:1px solid #d7e0e3;background:#fff;white-space:nowrap;font-variant-numeric:tabular-nums;}
.note-source-original .xbrl-reader-table th{background:#f5f8fa;text-align:center;font-weight:800;color:#20302f;}
.note-source-original .xbrl-reader-table td:first-child{text-align:left;font-weight:800;color:#20302f;}
.note-source-original td[align="center"],.note-source-original th[align="center"]{text-align:center;}
.note-source-original td[align="right"],.note-source-original th[align="right"]{text-align:right;}
.note-source-original td[align="left"],.note-source-original th[align="left"]{text-align:left;}
.note-source-original [data-cell-keys]{scroll-margin:120px;}
.note-source-original .total-formula-table{width:100%;min-width:0;margin:0 0 8px;background:#0f172a;color:#f8fafc;}
.note-source-original .total-formula-table th,.note-source-original .total-formula-table td{border:1px solid #475569;background:#0f172a;color:#f8fafc;padding:4px 6px;font-size:11px;line-height:1.35;white-space:nowrap;min-width:0;}
.note-source-original .total-formula-table th{background:#1e293b;color:#dbeafe;text-align:left;font-weight:800;}
.note-source-original .total-formula-table td:first-child{text-align:left;font-weight:400;color:#f8fafc;min-width:0;}
.note-source-original .total-formula-table td:last-child{text-align:right;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;}
.note-source-table{margin-bottom:10px;}
.note-completeness{margin:0 0 18px;}
.completeness-table{margin-top:8px;}
.completeness-more{font-size:11px;color:var(--muted);margin-top:6px;}
.note-review{border:1px solid var(--review-border);border-radius:8px;overflow:hidden;margin-top:12px;background:var(--review-dim);}
.note-check-tabs{display:flex;gap:8px;flex-wrap:wrap;padding:10px 14px;border-bottom:1px solid var(--review-border);background:#dbeafe;}
.note-check-tab{font:inherit;font-size:12px;padding:5px 11px;border:1px solid var(--review-border);background:#fff;color:#1e3a8a;border-radius:999px;cursor:pointer;}
.note-check-tab[aria-pressed="true"]{border-color:var(--review);color:#fff;font-weight:800;background:var(--review);}
.note-check-group{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:10px 14px;border-bottom:1px solid var(--border);font-size:13px;cursor:pointer;}
.note-check-group:hover{background:#f8fbff;}
.note-check-group[hidden]{display:none;}
.note-group-detail{border-top:0;}
.note-check-card{border:1px solid var(--review-border);border-radius:7px;margin-bottom:10px;overflow:hidden;background:#fff;}
.note-check-card:last-child{margin-bottom:0;}
.note-check-card-head{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:8px 10px;border-bottom:1px solid var(--review-border);background:#eff6ff;font-size:12px;}
.note-ref-list{display:grid;gap:8px;margin-top:8px;}
.note-ref-card{border:1px solid var(--review-border);border-radius:6px;background:#fff;padding:8px 10px;}
.note-ref-title{font-size:11px;font-weight:800;color:#1e3a8a;margin-bottom:4px;}
.note-ref-body{display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:11px;color:#334155;}
.note-ref-state{margin-top:6px;font-size:12px;font-weight:800;color:#0f172a;}
.note-ref-review{margin-top:7px;border-top:1px solid #dbeafe;padding-top:7px;}
.note-ref-counts{font-size:11px;color:#475569;margin-bottom:5px;}
.note-ref-check{display:grid;grid-template-columns:1fr auto auto;gap:5px 7px;align-items:center;padding:5px 0;border-top:1px solid #edf3ff;font-size:11px;}
.note-ref-check:first-of-type{border-top:0;}
.note-ref-check-title{font-weight:700;color:#1e293b;min-width:0;}
.note-ref-diff{color:#64748b;font-variant-numeric:tabular-nums;white-space:nowrap;}
.note-ref-reason{grid-column:1 / -1;color:#475569;line-height:1.45;}
.note-ref-total-hint{margin-top:5px;font-size:11px;color:#475569;background:#f8fafc;border:1px solid #e2e8f0;border-radius:5px;padding:5px 7px;}
.mini-jump{font:inherit;font-size:11px;font-weight:800;border:1px solid var(--review-border);background:#eff6ff;color:#1d4ed8;border-radius:5px;padding:3px 8px;cursor:pointer;}
.note-ref-missing{color:#92400e;font-weight:700;}
/* Re-imagined workpaper cockpit layer. */
:root{
  --bg:#f3f1ea;
  --surface:#fffefa;
  --surface-2:#ece7dc;
  --surface-3:#faf8f2;
  --border:#d7d0c2;
  --text:#171b1f;
  --muted:#66706f;
  --accent:#0b7a75;
  --accent-dim:#d9f0eb;
  --review:#1f5fbf;
  --review-dim:#eef5ff;
  --review-border:#b7c9e8;
  --paper:#fffefa;
  --paper-border:#d8d2c7;
  --warn:#b26b00;
  --warn-dim:#fff1cf;
  --ok:#08745b;
  --ok-dim:#ddf5ec;
  --down:#b42318;
  --down-dim:#fdecea;
  --sidebar-bg:#121a22;
  --sidebar-text:#b9c5c8;
  --sidebar-active:#ffffff;
  --sidebar-accent:#38b7a6;
  --review-rail-width:min(360px,calc(100vw - 292px));
}
body{background:var(--bg);color:var(--text);}
.shell{grid-template-columns:274px minmax(780px,1fr);}
aside{background:linear-gradient(180deg,#111a22 0%,#142226 100%);border-right:1px solid rgba(255,255,255,.08);padding:16px 0;}
.sidebar-brand{padding:2px 18px 16px;margin-bottom:6px;}
.sidebar-brand-name{font-size:15px;letter-spacing:0;}
.sidebar-brand-sub{color:#91a3a5;}
.sidebar-section{padding:14px 18px 6px;color:#84979a;letter-spacing:.04em;}
.nav-item{margin:0 8px;padding:9px 10px 9px 14px;border-left:0;border-radius:6px;font-weight:760;color:var(--sidebar-text);}
.nav-item:hover{background:rgba(255,255,255,.06);}
.nav-item.active{background:linear-gradient(90deg,rgba(56,183,166,.26),rgba(56,183,166,.10));box-shadow:inset 3px 0 0 var(--sidebar-accent);color:#fff;}
.nav-badge{border-radius:999px;padding:1px 7px;font-weight:850;}
.nb-ok{background:rgba(8,116,91,.34);color:#a8f0dc;}
.nb-warn{background:rgba(178,107,0,.34);color:#ffd68a;}
.nb-unc{background:rgba(255,255,255,.14);color:#d6e0e3;}
.sidebar-divider{margin:10px 18px;}
main{padding:0 30px 36px;background:var(--bg);}
body.review-open main{padding-right:calc(30px + var(--review-rail-width));}
.workpaper-topbar{position:sticky;top:0;z-index:20;display:flex;align-items:center;justify-content:space-between;gap:10px 18px;flex-wrap:wrap;margin:0 -30px 18px;padding:12px 30px;border-bottom:1px solid var(--border);background:rgba(255,254,250,.95);backdrop-filter:saturate(120%) blur(8px);box-shadow:0 1px 0 rgba(15,23,42,.02);}
.workpaper-title{display:flex;align-items:baseline;gap:10px;flex:1 1 280px;min-width:0;color:#253033;}
.workpaper-title strong{font-size:16px;line-height:1.3;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.topbar-kicker{font-size:10px;font-weight:900;color:var(--accent);letter-spacing:.08em;}
.workpaper-title span:last-child{font-size:12px;color:var(--muted);white-space:nowrap;}
.workpaper-context{display:flex;align-items:center;justify-content:flex-end;gap:7px;flex:1 1 360px;flex-wrap:wrap;min-width:0;}
.topbar-chip{display:inline-flex;align-items:center;min-height:25px;border:1px solid var(--border);border-radius:5px;background:#fff;padding:2px 8px;font-size:12px;font-weight:760;color:#394445;white-space:nowrap;}
.topbar-chip-attn{border-color:#e5ba6f;background:#fff8e8;color:#8a5100;}
.workpaper-actions{display:flex;align-items:center;justify-content:flex-end;gap:7px;flex-wrap:wrap;}
.workpaper-actions button{font:inherit;font-size:12px;font-weight:800;min-height:29px;border:1px solid var(--border);border-radius:5px;background:#fff;color:#263232;padding:4px 9px;cursor:pointer;white-space:nowrap;}
.workpaper-actions button:hover{border-color:#9fcfc8;color:var(--accent);background:#f7fffd;}
.workpaper-status-strip{position:sticky;top:54px;z-index:18;display:grid;grid-template-columns:minmax(0,1fr) minmax(310px,420px);gap:10px;align-items:stretch;margin:0 -30px 14px;padding:0 30px 10px;border-bottom:1px solid var(--border);background:rgba(255,254,250,.94);backdrop-filter:saturate(120%) blur(8px);}
.workpaper-status-tabs{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));border:1px solid var(--border);border-radius:0 0 7px 7px;overflow:hidden;background:#fff;}
.workpaper-status-tab{font:inherit;display:flex;align-items:center;justify-content:center;gap:7px;min-height:44px;border:0;border-right:1px solid var(--border);background:#fff;color:#2d3739;font-size:12px;font-weight:850;cursor:pointer;white-space:nowrap;}
.workpaper-status-tab:last-child{border-right:0;}
.workpaper-status-tab:hover,.workpaper-status-tab[aria-pressed="true"]{background:#f8fbff;box-shadow:inset 0 -3px 0 #2263c6;color:#174ea6;}
.workpaper-status-tab strong{font-size:13px;color:inherit;}
.workpaper-filterbar{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;align-items:center;}
.workpaper-search{display:grid;grid-template-columns:auto minmax(0,1fr);align-items:center;gap:8px;min-height:44px;border:1px solid var(--border);border-radius:5px;background:#fff;padding:0 10px;}
.workpaper-search span{font-size:11px;font-weight:900;color:var(--muted);}
.workpaper-search input{min-width:0;width:100%;border:0;outline:0;background:transparent;color:var(--text);font:inherit;font-size:13px;}
.workpaper-filter-button{font:inherit;min-height:44px;border:1px solid var(--border);border-radius:5px;background:#fff;color:#263232;padding:0 12px;font-size:12px;font-weight:850;cursor:pointer;}
.workpaper-filter-button:hover{border-color:#9fcfc8;color:var(--accent);}
.report-masthead{align-items:flex-start;margin:0 0 12px;padding:0;}
.report-kicker{font-size:10px;color:var(--accent);}
.report-id h1{font-size:25px;letter-spacing:0;}
.report-meta{gap:6px;margin-top:7px;}
.report-meta span{min-height:23px;background:#fff;border-color:var(--border);border-radius:5px;color:#495555;font-weight:700;}
.report-focus{align-items:center;min-width:190px;border-color:#d2c7b7;background:#fffefa;border-radius:7px;box-shadow:0 1px 1px rgba(15,23,42,.04);}
.focus-number{color:var(--warn);}
.focus-label{font-size:13px;}
.verdict-banner{margin:0 -30px 22px;padding:16px 30px 18px;border-width:1px 0;background:#fff8df;}
.verdict-banner.verdict-ok{background:#eaf8f1;border-color:#b9e7d1;}
.verdict-banner.verdict-warn{background:#fff1cf;border-color:#e7c269;}
.verdict-banner.verdict-unc{background:#f8f4ec;border-color:#dacfbf;}
.verdict-head{align-items:center;margin-bottom:12px;}
.verdict-label{font-size:20px;}
.summary-action{border-color:#b7d4cf;background:#fff;color:var(--accent);border-radius:5px;}
.status-overview{grid-template-columns:1fr;gap:10px;margin-top:4px;}
.status-toolbar{display:grid;grid-template-columns:minmax(0,1fr) minmax(250px,340px);gap:10px;align-items:stretch;}
.status-card-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:0;border:1px solid var(--border);border-radius:7px;overflow:hidden;background:#fff;}
.status-card{border:0;border-right:1px solid var(--border);border-radius:0;background:#fff;display:grid;grid-template-columns:minmax(0,1fr);gap:2px;align-content:center;min-height:62px;padding:10px 14px;}
.status-card:last-child{border-right:0;}
.status-card:hover,.status-card[aria-pressed="true"]{background:#fbf8ef;box-shadow:inset 0 -3px 0 var(--review);border-color:transparent;}
.status-card[aria-pressed="true"] .status-label{color:#14212a;}
.status-value{grid-row:auto;grid-column:1;min-width:0;font-size:24px;text-align:left;}
.status-label{grid-column:1;grid-row:auto;align-self:center;font-size:13px;line-height:1.25;}
.status-search{display:grid;grid-template-columns:auto minmax(0,1fr);gap:8px;align-items:center;border:1px solid var(--border);border-radius:7px;background:#fff;padding:0 10px;min-height:62px;}
.status-search span{font-size:11px;font-weight:900;color:var(--muted);}
.status-search input{width:100%;min-width:0;border:0;outline:0;background:transparent;color:var(--text);font:inherit;font-size:13px;}
.status-search:focus-within{border-color:#9fcfc8;box-shadow:inset 0 -3px 0 var(--accent);}
.status-list{max-height:285px;border-color:var(--border);border-radius:7px;box-shadow:0 1px 1px rgba(15,23,42,.03);}
.status-list-row{grid-template-columns:minmax(180px,1.4fr) minmax(180px,1fr) minmax(84px,auto) auto;gap:10px;padding:10px 12px;border-bottom-color:#e6ded0;background:#fff;}
.status-list-row:hover{background:#fffaf0;}
.status-row-main{font-size:13px;}
.status-row-source,.status-row-diff{color:#66706f;}
.panel{margin-bottom:26px;}
.panel-title{font-size:20px;line-height:1.25;}
.panel-sub{margin-bottom:12px;color:#626d6d;}
.statement-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:0 0 8px;border:1px solid var(--border);border-radius:7px;background:#fffefa;padding:10px 13px;}
.statement-path{display:flex;align-items:baseline;gap:8px;min-width:0;}
.statement-path span{font-size:11px;font-weight:900;color:var(--accent);letter-spacing:.04em;}
.statement-path strong{font-size:14px;line-height:1.35;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.statement-toolbar-meta{display:flex;align-items:center;justify-content:flex-end;gap:7px;flex-wrap:wrap;flex:0 0 auto;}
.statement-toolbar-meta span{display:inline-flex;align-items:center;min-height:24px;border:1px solid var(--border);border-radius:5px;background:#fff;padding:2px 8px;font-size:11px;font-weight:800;color:#4a5556;white-space:nowrap;}
.statement-wrap{border:1px solid var(--border);border-radius:7px;background:#fff;box-shadow:0 1px 2px rgba(15,23,42,.04);}
.statement-caption{padding:9px 14px;border-bottom:1px solid var(--border);background:#faf8f2;color:#263232;}
.fs-table{font-size:13px;min-width:820px;background:#fff;}
.fs-table th{position:sticky;top:45px;z-index:4;padding:10px 13px;background:#f5f1e8;border-bottom:1px solid var(--paper-border);color:#364041;}
.fs-table td{padding:9px 13px;border-bottom:1px solid #e5dfd4;color:#1c2528;}
.fs-table tbody tr:hover td{background:#fffaf0;}
.state-col{width:76px;text-align:center;}
.acct-state{border-radius:999px;padding:2px 8px;font-size:11px;font-weight:850;background:#fff;}
.as-ok{background:var(--ok-dim);border-color:#b9e7d1;color:#056249;}
.as-note,.as-exp{background:#eef5ff;border-color:#bfd2ef;color:#1f5fbf;}
.as-warn{background:#fff1cf;border-color:#e7c269;color:#8a5100;}
.as-unc,.as-nt{background:#f1f3f4;border-color:#d8dee2;color:#64727a;}
.verified-ok td:first-child::after,.verified-warn td:first-child::after,.verified-uncertain td:first-child::after{border-radius:999px;}
.review-rail{width:var(--review-rail-width);background:#fffefa;border-left:1px solid #cfc6b8;padding:0;box-shadow:-18px 0 34px rgba(17,24,39,.18);}
@media (min-width:981px){
  main{padding-right:calc(30px + var(--review-rail-width));}
  .review-rail{transform:translateX(0);opacity:1;pointer-events:auto;}
}
.review-rail-head{position:sticky;top:0;z-index:2;margin:0;padding:18px 18px 13px;background:#fffefa;border-bottom:1px solid var(--border);}
.review-rail-kicker{color:var(--review);letter-spacing:.06em;}
.review-rail-title{font-size:17px;color:#17212b;}
.review-rail-close{border-color:var(--border);color:#334155;border-radius:5px;padding:5px 9px;}
.review-rail-tabs{position:sticky;top:65px;z-index:2;margin:0;padding:9px 18px 10px;border-bottom:1px solid var(--border);background:#faf8f2;}
.review-rail-tabs span{border-color:#d7d0c2;background:#fff;color:#344148;border-radius:5px;}
.review-rail-body{padding:14px 18px 22px;overflow-x:auto;color:#17212b;}
.comparison-summary{border-color:#d7d0c2;border-radius:7px;}
.comparison-head{background:#faf8f2;border-bottom-color:#d7d0c2;}
.comparison-grid{grid-template-columns:minmax(0,1fr);}
.comparison-arrow{min-height:18px;}
.comparison-side{background:#fff;border-color:#e3dccf;}
.comparison-math{border-top-color:#d7d0c2;background:#fffaf0;}
.review-empty{border-color:#d7d0c2;background:#fff;border-radius:7px;}
.check-summary{border-color:var(--review-border);border-radius:7px;background:#fff;overflow:hidden;}
.check-summary-head{background:#eef5ff;border-bottom-color:var(--review-border);}
.check-row{padding:10px 12px;background:#fff;border-bottom-color:#e3dccf;}
.check-row:hover{background:#fffaf0;}
.check-row[data-tags]{display:grid;grid-template-columns:auto minmax(0,1fr) auto auto;align-items:center;}
.src-tbl th{background:#eef5ff;color:#183c76;}
.src-tbl td{background:#fff;}
.review-rail .src-tbl{min-width:480px;}
.review-rail .src-tbl th,.review-rail .src-tbl td{white-space:nowrap;overflow-wrap:normal;}
.note-source-original{border-color:var(--border);border-radius:7px;background:#fffefa;}
.note-source-original th,.note-source-original td{border-color:#d9d1c6;}
@media (max-width: 1280px){
  :root{--review-rail-width:min(360px,calc(100vw - 258px));}
  .shell{grid-template-columns:258px minmax(620px,1fr);}
}
@media (max-width: 980px){
  :root{--review-rail-width:100vw;}
  .shell{grid-template-columns:1fr;}
  aside{position:relative;height:auto;max-height:30vh;border-right:none;border-bottom:1px solid rgba(255,255,255,.08);}
  body.review-open main{padding-right:16px;}
  main{padding:18px 16px;}
  .workpaper-topbar{position:relative;top:auto;flex-direction:column;align-items:flex-start;gap:8px;margin:0 -16px 14px;padding:12px 16px;}
  .workpaper-title,.workpaper-context{flex:0 1 auto;}
  .workpaper-title{flex-wrap:wrap;}
  .workpaper-title strong{white-space:normal;overflow-wrap:anywhere;}
  .workpaper-title span:last-child{white-space:normal;}
  .workpaper-context{justify-content:flex-start;min-width:0;width:100%;}
  .workpaper-actions{justify-content:flex-start;width:100%;}
  .workpaper-status-strip{position:relative;top:auto;grid-template-columns:1fr;margin:0 -16px 14px;padding:0 16px 10px;}
  .workpaper-status-tabs{grid-template-columns:repeat(2,minmax(0,1fr));border-radius:7px;}
  .workpaper-status-tab{justify-content:space-between;padding:0 11px;}
  .workpaper-filterbar{grid-template-columns:1fr;}
  .workpaper-filter-button{display:none;}
  .side-nav{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));}
  .report-masthead,.verdict-head{align-items:stretch;flex-direction:column;}
  .report-focus{align-self:flex-start;}
  .status-overview{grid-template-columns:1fr;}
  .status-toolbar{grid-template-columns:1fr;}
  .status-card-grid{grid-template-columns:repeat(2,minmax(0,1fr));}
  .status-card{min-height:70px;}
  .status-label{word-break:keep-all;overflow-wrap:normal;}
  .status-list-row{grid-template-columns:1fr;align-items:start;}
  .reader-brief{grid-template-columns:1fr;}
  .check-row{align-items:flex-start;}
  .statement-toolbar{align-items:flex-start;flex-direction:column;}
  .statement-toolbar-meta{justify-content:flex-start;}
  .statement-wrap{overflow:auto;}
  .review-rail{display:none!important;}
}
@media print{
  .shell{display:block;}
  aside,.filter-pills,.expand-tri{display:none;}
  main{padding:0;}
  .panel.hidden{display:block!important;}
  .review-rail{display:none!important;}
  .dd-inline,.dd-inner{display:block!important;}
  thead{display:table-header-group;}
  tr,figure,.statement-wrap,.check-summary,.panel{break-inside:avoid;}
  .reader-brief{grid-template-columns:1fr;}
}
</style>"""


# ── JS micro-runtime ───────────────────────────────────────────────────────────

def _inline_js() -> str:
    return """<script>
(function(){
  var navItems = document.querySelectorAll('.nav-item[data-target]');
  var panels = document.querySelectorAll('.panel');
  var scopeButtons = document.querySelectorAll('.report-scope-button[data-report-scope]');
  navItems.forEach(function(item){
    item.addEventListener('click', function(){
      var target = item.getAttribute('data-target');
      activatePanel(target, true);
    });
  });
  scopeButtons.forEach(function(btn){
    btn.addEventListener('click', function(){
      setReportScope(btn.getAttribute('data-report-scope'), null, true);
    });
  });
  if(scopeButtons.length){
    setReportScope(document.body.getAttribute('data-active-report-scope') || scopeButtons[0].getAttribute('data-report-scope'), null, false);
  } else {
    var initialNav = document.querySelector('.nav-item[data-target].active') || document.querySelector('.nav-item[data-target]');
    if(initialNav){ selectPanel(initialNav.getAttribute('data-target'), false); }
  }
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
  document.querySelectorAll('[data-note-tabs]').forEach(function(ctrl){
    ctrl.addEventListener('click', function(e){
      var btn = e.target.closest('[data-note-filter]');
      if(!btn) return;
      var key = btn.getAttribute('data-note-filter');
      ctrl.querySelectorAll('[data-note-filter]').forEach(function(b){ b.setAttribute('aria-pressed','false'); });
      btn.setAttribute('aria-pressed','true');
      var panel = document.querySelector(ctrl.getAttribute('data-note-tabs'));
      if(!panel) return;
      closeOpenDrilldowns();
      panel.querySelectorAll('[data-note-group]').forEach(function(row){
        row.hidden = key !== 'all' && row.getAttribute('data-note-group') !== key;
      });
      openNoteGroupForFilter(panel, key);
    });
  });
  document.querySelectorAll('[data-target-inline]').forEach(function(btn){
    btn.addEventListener('click', function(){
      var target = btn.getAttribute('data-target-inline');
      activatePanel(target, true);
    });
  });
  document.querySelectorAll('.status-overview').forEach(function(view){
    var active = view.querySelector('[data-status-filter][aria-pressed="true"]');
    view.setAttribute('data-active-status', active ? active.getAttribute('data-status-filter') : 'attention');
    view.addEventListener('click', function(e){
      var btn = e.target.closest('[data-status-filter]');
      if(!btn) return;
      var key = btn.getAttribute('data-status-filter');
      view.querySelectorAll('[data-status-filter]').forEach(function(item){
        item.setAttribute('aria-pressed', 'false');
      });
      btn.setAttribute('aria-pressed', 'true');
      view.setAttribute('data-active-status', key);
      applyStatusOverviewFilters(view);
    });
    var search = view.querySelector('[data-status-search]');
    if(search){
      search.addEventListener('input', function(){ applyStatusOverviewFilters(view); });
    }
    applyStatusOverviewFilters(view);
  });
  document.querySelectorAll('[data-workpaper-search]').forEach(function(input){
    input.addEventListener('input', applyWorkbenchSearch);
  });
})();

function applyStatusOverviewFilters(view){
  var key = view.getAttribute('data-active-status') || 'attention';
  var search = view.querySelector('[data-status-search]');
  var query = search ? search.value.trim().toLowerCase() : '';
  view.querySelectorAll('[data-status-item]').forEach(function(row){
    var statusMatch = row.getAttribute('data-status-item') === key;
    var textMatch = !query || row.textContent.toLowerCase().indexOf(query) >= 0;
    row.hidden = !(statusMatch && textMatch);
  });
}

function setReportScope(scope, targetPanelId, shouldScroll){
  if(!scope) return;
  document.body.setAttribute('data-active-report-scope', scope);
  document.querySelectorAll('.report-scope-button[data-report-scope]').forEach(function(btn){
    var active = btn.getAttribute('data-report-scope') === scope;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-pressed', active ? 'true' : 'false');
  });
  document.querySelectorAll('.scope-nav[data-report-scope]').forEach(function(nav){
    nav.classList.toggle('hidden', nav.getAttribute('data-report-scope') !== scope);
  });
  document.querySelectorAll('.report-scope-shell[data-report-scope]').forEach(function(shell){
    shell.classList.toggle('hidden', shell.getAttribute('data-report-scope') !== scope);
  });
  var target = targetPanelId;
  if(!target){
    var activeNav = document.querySelector('.scope-nav[data-report-scope="' + scope + '"]');
    var defaultNav = activeNav ? activeNav.querySelector('.nav-item[data-target].active') : null;
    var firstNav = activeNav ? activeNav.querySelector('.nav-item[data-target]') : null;
    target = (defaultNav || firstNav) ? (defaultNav || firstNav).getAttribute('data-target') : null;
  }
  if(target){ selectPanel(target, shouldScroll); }
}

function activatePanel(target, shouldScroll){
  var panel = document.getElementById(target);
  if(!panel) return;
  var shell = panel.closest('.report-scope-shell');
  if(shell){
    var scope = shell.getAttribute('data-report-scope');
    if(document.body.getAttribute('data-active-report-scope') !== scope){
      setReportScope(scope, target, shouldScroll);
      return;
    }
  }
  selectPanel(target, shouldScroll);
}

function selectPanel(target, shouldScroll){
  var panel = document.getElementById(target);
  if(!panel) return;
  document.querySelectorAll('.nav-item[data-target]').forEach(function(n){
    var active = n.getAttribute('data-target') === target;
    n.classList.toggle('active', active);
    if(active){ n.setAttribute('aria-current', 'page'); }
    else{ n.removeAttribute('aria-current'); }
  });
  document.querySelectorAll('.panel').forEach(function(p){
    p.classList.toggle('hidden', p.id !== target);
  });
  if(shouldScroll){ panel.scrollIntoView({behavior:'smooth',block:'start'}); }
}

function jumpToActiveUtilityPanel(key){
  var target = 'panel-' + key;
  var scope = document.body.getAttribute('data-active-report-scope');
  if(scope === 'consolidated') target += '-con';
  else if(scope === 'separate') target += '-sep';
  activatePanel(target, true);
}

function focusWorkbenchSearch(){
  var input = document.querySelector('[data-workpaper-search]');
  if(input){ input.focus(); }
}

function applyWorkbenchSearch(){
  var input = document.querySelector('[data-workpaper-search]');
  var query = input ? input.value.trim().toLowerCase() : '';
  var panel = Array.prototype.find.call(document.querySelectorAll('.panel'), function(item){
    return !item.classList.contains('hidden');
  });
  document.querySelectorAll('.fs-table tbody tr').forEach(function(row){
    row.hidden = false;
  });
  if(!panel || !query) return;
  panel.querySelectorAll('.fs-table tbody tr').forEach(function(row){
    row.hidden = row.textContent.toLowerCase().indexOf(query) < 0;
  });
}

function closeOpenDrilldowns(exceptId){
  document.querySelectorAll('.dd-inner.open, .dd-inline.open').forEach(function(item){
    if(exceptId && item.id === exceptId) return;
    item.classList.remove('open');
  });
  clearReviewSource();
  resetReviewTriangles(exceptId || null);
  if(!exceptId){
    resetReviewRailBody();
    document.body.classList.remove('review-open');
  }
}

function resetReviewRailBody(){
  var body = document.getElementById('review-rail-body');
  if(!body) return;
  body.innerHTML = '<div class="review-empty">재무제표 본문이나 주석 검증 항목을 선택하세요.</div>';
}

function clearReviewSource(){
  document.querySelectorAll('.review-source-active').forEach(function(item){
    item.classList.remove('review-source-active');
    item.removeAttribute('data-review-active');
  });
}

function resetReviewTriangles(activeId){
  document.querySelectorAll('.expand-tri').forEach(function(tri){ tri.style.transform = ''; });
  if(!activeId) return;
  var activeTri = document.getElementById('tri-' + activeId);
  if(activeTri){ activeTri.style.transform = 'rotate(90deg)'; }
}

function showReview(id, sourceEl){
  var template = document.getElementById(id);
  var body = document.getElementById('review-rail-body');
  if(!template || !body) return;
  document.querySelectorAll('.dd-inner.open, .dd-inline.open').forEach(function(item){
    item.classList.remove('open');
  });
  clearReviewSource();
  if(sourceEl){
    sourceEl.classList.add('review-source-active');
    sourceEl.setAttribute('data-review-active', 'true');
  }
  document.body.classList.add('review-open');
  body.innerHTML = template.innerHTML;
  resetReviewTriangles(id);
  var rail = document.getElementById('review-rail');
  if(rail){ rail.scrollTop = 0; }
}

function clearReviewRail(){
  clearReviewSource();
  resetReviewTriangles(null);
  resetReviewRailBody();
  document.body.classList.remove('review-open');
}

function toggleDD(id){
  showReview(id, null);
}

function openNoteGroupForFilter(panel, key){
  if(key === 'all') return;
  var row = panel.querySelector('[data-note-group="' + key + '"]');
  if(!row) return;
  var detail = row.nextElementSibling;
  if(detail && detail.id){ showReview(detail.id, row); }
}

function jumpToPanel(panelId){
  activatePanel(panelId, true);
}

function jumpToCheckSource(el){
  var panelId = el.getAttribute('data-jump');
  if(!panelId) return;
  if(el.getAttribute('data-jump-cell')){
    jumpToCell(el);
    return;
  }
  jumpToPanel(panelId);
}

function jumpToCell(el){
  var panelId = el.getAttribute('data-jump');
  var cellKey = el.getAttribute('data-jump-cell');
  var tableKey = el.getAttribute('data-jump-table');
  jumpToPanel(panelId);
  var panel = document.getElementById(panelId);
  if(!panel) return;
  if(!cellKey) return;
  var cell = null;
  if(tableKey){
    cell = panel.querySelector('[data-source-table="' + tableKey + '"] [data-cell="' + cellKey + '"]')
        || panel.querySelector('[data-source-table="' + tableKey + '"] [data-cell-keys~="' + cellKey + '"]');
  }
  cell = cell || panel.querySelector('[data-cell="' + cellKey + '"]')
          || panel.querySelector('[data-cell-keys~="' + cellKey + '"]')
          || panel.querySelector('[data-check-row="' + cellKey.replace(/c.*/, '').slice(1) + '"]');
  if(cell){
    cell.scrollIntoView({behavior:'smooth', block:'center'});
    cell.classList.add('cell-flash');
    setTimeout(function(){ cell.classList.remove('cell-flash'); }, 1200);
  }
}

function copyFormula(btn, event){
  if(event){ event.preventDefault(); event.stopPropagation(); }
  var text = btn.getAttribute('data-copy-text') || '';
  function done(){
    var old = btn.textContent;
    btn.textContent = '복사됨';
    setTimeout(function(){ btn.textContent = old; }, 900);
  }
  if(navigator.clipboard && navigator.clipboard.writeText){
    navigator.clipboard.writeText(text).then(done).catch(function(){ fallbackCopy(text); done(); });
    return;
  }
  fallbackCopy(text);
  done();
}

function fallbackCopy(text){
  var area = document.createElement('textarea');
  area.value = text;
  area.setAttribute('readonly', 'readonly');
  area.style.position = 'fixed';
  area.style.left = '-9999px';
  document.body.appendChild(area);
  area.select();
  try{ document.execCommand('copy'); }catch(e){}
  document.body.removeChild(area);
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
    if status == EXPLAINABLE_GAP:
        return "badge-exp"
    if status == UNEXPLAINED_GAP:
        return "badge-warn"
    return "badge-unc"


def _status_to_badge_label(status: str) -> str:
    if status == MATCHED:
        return "✓ 일치"
    if status == EXPLAINABLE_GAP:
        return "설명차이"
    if status == UNEXPLAINED_GAP:
        return "확인필요"
    if status == PARSE_UNCERTAIN:
        return "파싱불확실"
    if status == NOT_TESTED:
        return "미검증"
    return "확인필요"


def _account_state_badge(status: str | None) -> str:
    """Per-account verification-state badge for statement line rows.
    status None => 미검증 (no covering check). Render-derived; never a CheckResult."""
    if status == MATCHED:
        return '<span class="acct-state as-ok">검증완료</span>'
    if status == EXPLAINABLE_GAP:
        return '<span class="acct-state as-exp">설명차이</span>'
    if status == UNEXPLAINED_GAP:
        return '<span class="acct-state as-warn">확인필요</span>'
    if status == PARSE_UNCERTAIN:
        return '<span class="acct-state as-unc">파싱불확실</span>'
    return '<span class="acct-state as-nt">미검증</span>'
