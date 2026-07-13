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
from dart_footing_reconciler.report_frame import (
    CHECK_GROUP_ORDER,
    CHECK_GROUPS,
    CHECK_METHOD_DESCRIPTIONS,
    TABLE_UNIT_TOLERANCE_CHECK_TYPES,
    statement_kind_from_source,
    statement_kind_from_title,
)


# ── Severity helpers ─────────────────────────────────────────────────────────

_STATUS_SEVERITY = {
    UNEXPLAINED_GAP: 4,
    PARSE_UNCERTAIN: 3,
    EXPLAINABLE_GAP: 2,
    MATCHED: 1,
    NOT_TESTED: 0,
}


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
    tied = _place_results(report, results, render_map)
    rendered_keys = _rendered_panel_keys(report, tied, render_map)
    unplaced_count = _unplaced_result_count(results, tied, rendered_keys)
    broken_anchor_count = _broken_evidence_anchor_count(report, results, render_map)
    uncertain_results = [r for r in results if r.status == PARSE_UNCERTAIN]

    sidebar_html = _render_sidebar(report, results, tied, render_map)
    masthead_html = _render_report_masthead(report, results, meta)
    banner_html = _render_verdict_banner(report, results, render_map)

    panels: list[str] = []

    # Cockpit overview views (대시보드 is the banner; these are 진행상황/확인 필요/다음 작업).
    panels.append(_render_progress_panel(
        report,
        results,
        tied,
        render_map,
        unplaced_count=unplaced_count,
        broken_anchor_count=broken_anchor_count,
    ))
    panels.append(_render_attention_panel(results, report, render_map))
    panels.append(_render_next_actions_panel(results))
    panels.append(_render_legend_panel(results))

    for section, kind, label in _rendered_statement_sections(report):
        panel_id = _statement_panel_id(render_map, section)
        display_label = _statement_nav_label(section, kind, label, render_map)
        panels.append(_render_statement_panel(
            section,
            tied.get(panel_id, []),
            panel_id=panel_id,
            label=display_label,
            report=report,
            render_map=render_map,
        ))

    for section in report.notes:
        panel_id = _note_panel_id(render_map, section)
        panels.append(_render_note_panel(
            section,
            tied.get(panel_id, []),
            panel_id=panel_id,
            report=report,
            render_map=render_map,
        ))

    if tied.get("other"):
        panels.append(_render_other_panel(tied["other"], report=report, render_map=render_map))

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
{masthead_html}
{banner_html}
{content}
</main>
</div>
{_inline_js()}
</body>
</html>"""


def _build_render_map(report: FullReport) -> _ReportRenderMap:
    tables_by_index: dict[int, list[_RenderedTable]] = {}
    statement_entries = _rendered_statement_sections(report)
    statement_panel_ids = _build_statement_panel_ids(statement_entries)
    unique_statement_panel_keys = _unique_statement_panel_keys(statement_entries, statement_panel_ids)
    note_panel_ids = _build_note_panel_ids(report.notes)
    unique_note_panel_keys = _unique_note_panel_keys(report.notes, note_panel_ids)

    for section, kind, _label in statement_entries:
        panel_id = statement_panel_ids[id(section)]
        table = _first_table(section)
        if table is not None:
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


def _note_nav_label(section: ReportSection, render_map: _ReportRenderMap) -> str:
    note_key = _note_identity(section)
    duplicated = f"note:{note_key}" not in render_map.unique_note_panel_keys
    if duplicated:
        scope_label = _scope_label(section.scope)
        suffix = f" ({scope_label})" if scope_label else ""
        return f"주석 {note_key}{suffix} {section.title}".strip()
    if section.note_no:
        return f"{section.note_no}. {section.title}"
    return section.title


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
      <div class="focus-sub">검토 필요 + 파싱 불확실</div>
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
        exp = sum(1 for r in items if r.status == EXPLAINABLE_GAP)
        if warn:
            return f'<span class="nav-badge nb-warn">⚠ {warn}</span>'
        if unc:
            return f'<span class="nav-badge nb-unc">? {unc}</span>'
        if exp:
            return f'<span class="nav-badge nb-exp">△ {exp}</span>'
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
        return "불확실 항목 우선 확인"
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
    <span class="pc-copy">차이 {c['gaps']} · 불확실 {c['uncertain']}</span>
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
    <div class="kpi-tile kpi-unc"><div class="kpi-val">{c['uncertain']}</div><div class="kpi-name">파싱 불확실</div></div>
    <div class="kpi-tile kpi-nt"><div class="kpi-val">{c['not_tested']}</div><div class="kpi-name">미검증</div></div>
    <div class="kpi-tile"><div class="kpi-val">{c['total']}</div><div class="kpi-name">전체</div></div>
  </div>"""


def _next_action_lines(c: dict[str, int]) -> list[str]:
    lines: list[str] = []
    if c["gaps"]:
        lines.append(f"‘확인 필요’ 화면에서 검토 필요 {c['gaps']}건의 차이 원인(재분류·반올림·범위)을 공시 원문과 대조")
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
            f'<th>검토필요</th><th>파싱불확실</th><th>미검증</th><th>전체</th>'
            f'</tr></thead><tbody>{rows}</tbody>'
            f'</table></div>') if rows else '<div class="empty-state">검증 항목이 없습니다.</div>'

    if unplaced_count:
        placement = (
            f'<button class="progress-diag warn" type="button" data-target-inline="panel-other">'
            f'배치되지 않은 검증 {unplaced_count}건 · 기타 검증 패널에서 확인</button>'
        )
    else:
        placement = '<span class="progress-diag">배치되지 않은 검증 0건</span>'
    anchor_class = "progress-diag warn" if broken_anchor_count else "progress-diag"
    anchors = f'<span class="{anchor_class}">근거 연결 실패 {broken_anchor_count}건</span>'

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
        for r in flagged:
            tag = "warn" if r.status == UNEXPLAINED_GAP else "unc"
            badge_class = _status_to_badge_class(r.status)
            badge_label = _status_to_badge_label(r.status)
            exp_str = f"{r.expected:,}" if r.expected is not None else "—"
            act_str = f"{r.actual:,}" if r.actual is not None else "—"
            diff_str = f"차이 {r.difference:,}" if r.difference is not None else ""
            dd_id = f"dd-attn-{_safe_id(r.check_id)}"
            rows += f"""<div class="check-row attn-row" data-tags="{tag}" onclick="toggleDD('{dd_id}')">
  <span class="expand-tri" id="tri-{dd_id}">▶</span>
  <span class="check-name">{_esc(r.title)}</span>
  <span class="check-vals"><span>{exp_str}</span><span>{act_str}</span><span>{diff_str}</span></span>
  <span class="badge {badge_class}">{badge_label}</span>
</div>
<div class="dd-inline" id="{dd_id}">{_render_drilldown(r, report, render_map)}</div>"""
        body = f'<div class="check-summary">{rows}</div>'

    return f"""<div class="panel hidden" id="panel-attention">
  <div class="panel-title">확인 필요</div>
  <div class="panel-sub">검토 필요·파싱 불확실 항목을 한 곳에 모았습니다.</div>
  <div class="filter-pills" data-filter-control="#panel-attention">
    <button data-filter="all" aria-pressed="true">전체</button>
    <button data-filter="warn" aria-pressed="false">검토 필요</button>
    <button data-filter="unc" aria-pressed="false">파싱 불확실</button>
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
    results_by_group: dict[str, list[CheckResult]] = {group: [] for group in CHECK_GROUP_ORDER}
    methods_by_group: dict[str, list[tuple[str, str]]] = {group: [] for group in CHECK_GROUP_ORDER}
    for check_type, group in CHECK_GROUPS.items():
        methods_by_group.setdefault(group, []).append((
            check_type,
            CHECK_METHOD_DESCRIPTIONS.get(check_type, "등록되지 않은 검증 유형"),
        ))
    for result in results:
        group = CHECK_GROUPS.get(result.check_type, "기타")
        results_by_group.setdefault(group, []).append(result)

    cards = ""
    ordered_groups = list(CHECK_GROUP_ORDER)
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
            f"검증완료 {counts['matched']} · 설명차이 {counts['explained']} · "
            f"검토필요 {counts['gaps']} · 파싱불확실 {counts['uncertain']} · "
            f"미검증 {counts['not_tested']}"
        )
        method_items = "".join(
            f'<li><code>{_esc(check_type)}</code><span>{_esc(description)}</span></li>'
            for check_type, description in sorted(methods)
        )
        if not method_items:
            method_items = '<li><code>unknown</code><span>등록되지 않은 검증 유형</span></li>'
        cards += f"""<div class="legend-group">
  <div class="legend-head">
    <div class="legend-title">{_esc(group)}</div>
    <div class="legend-counts">{_esc(status_line)}</div>
  </div>
  <ul class="legend-methods">{method_items}</ul>
</div>"""

    return f"""<div class="panel hidden" id="panel-legend">
  <div class="panel-title">검증 범례</div>
  <div class="panel-sub">검증 유형별 비교 방식과 이 보고서의 상태별 건수입니다.</div>
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


def _status_to_row_class(status: str) -> str:
    if status == MATCHED:
        return "verified-ok"
    if status == EXPLAINABLE_GAP:
        return "verified-exp"
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
    if result.status == MATCHED:
        callout_class = "ok"
        callout_icon = "✓"
    elif result.status == EXPLAINABLE_GAP:
        callout_class = "exp"
        callout_icon = "△"
    else:
        callout_class = "warn"
        callout_icon = "⚠"
    ev_rows = ""
    raw_rows = ""
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
        ev_rows += f"<tr><td>{_esc(ev.label)}</td><td>{amount_str}</td>{src_cell}</tr>"
        raw_rows += f"<div>{_esc(ev.label)}: <code>{_esc(ev.source)}</code></div>"
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
    method = CHECK_METHOD_DESCRIPTIONS.get(result.check_type, "등록되지 않은 검증 유형")
    method_line = (
        f'<div class="method-line">검증 방법: {_esc(method)} · '
        f'{_esc(_tolerance_text(result))}</div>'
    )
    return f"""<div class="dd-title">{_esc(result.title)}</div>
<table class="src-tbl">
  <thead><tr><th>항목</th><th>금액</th><th>근거 위치</th></tr></thead>
  <tbody>{ev_rows}</tbody>
</table>
{breakdown}{method_line}<div class="callout {callout_class}">{callout_icon} {_esc(result.reason)}</div>
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
    for result in results:
        badge_class = _status_to_badge_class(result.status)
        badge_label = _status_to_badge_label(result.status)
        exp_str = f"{result.expected:,}" if result.expected is not None else "—"
        act_str = f"{result.actual:,}" if result.actual is not None else "—"
        diff_str = f"차이 {result.difference:,}" if result.difference is not None else ""
        dd_id = f"{id_prefix}-{_safe_id(result.check_id)}"
        title = title_for_result(result) if title_for_result else result.title
        check_rows += f"""<div class="check-row" onclick="toggleDD('{dd_id}')">
  <span class="expand-tri" id="tri-{dd_id}">▶</span>
  <span class="check-name">{_esc(title)}</span>
  <span class="check-vals"><span>{exp_str}</span><span>{act_str}</span><span>{diff_str}</span></span>
  <span class="badge {badge_class}">{badge_label}</span>
</div>
<div class="dd-inline" id="{dd_id}">{_render_drilldown(result, report, render_map)}</div>"""
    return f'<div class="check-summary"><div class="check-summary-head">검증 결과</div>{check_rows}</div>'


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
        id_prefix="dd-note",
        title_for_result=lambda result: _display_check_title(result.title, section),
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
        "UNIT_MISMATCH_SUSPECTED": "단위(천원/백만원) 스케일 불일치 의심 — 원문 단위 확인 필요",
    }.get(code, "알 수 없는 파싱 오류입니다.")


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
.nb-exp{background:rgba(53,193,167,.20);color:#9de9dc;}
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
.verified-ok td:first-child::after{content:"✓";display:inline-flex;align-items:center;justify-content:center;margin-left:8px;width:16px;height:16px;background:var(--ok-dim);color:var(--ok);border-radius:3px;font-size:10px;font-weight:800;vertical-align:middle;}
.verified-exp td:first-child::after{content:"△";display:inline-flex;align-items:center;justify-content:center;margin-left:8px;width:16px;height:16px;background:var(--accent-dim);color:var(--accent);border-radius:3px;font-size:10px;font-weight:800;vertical-align:middle;}
.verified-warn td:first-child::after{content:"⚠";display:inline-flex;align-items:center;justify-content:center;margin-left:8px;width:16px;height:16px;background:var(--warn-dim);color:var(--warn);border-radius:3px;font-size:10px;font-weight:800;vertical-align:middle;}
.verified-uncertain td:first-child::after{content:"?";display:inline-flex;align-items:center;justify-content:center;margin-left:8px;width:16px;height:16px;background:var(--surface-2);color:var(--muted);border-radius:3px;font-size:10px;font-weight:800;vertical-align:middle;}
.verified-ok{cursor:pointer;} .verified-ok:hover td{background:#f0fdf4;}
.verified-exp{cursor:pointer;} .verified-exp:hover td{background:var(--accent-dim);}
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
.callout.exp{background:var(--accent-dim);border:1px solid #9fd3ca;color:#075f58;}
.callout.warn{background:var(--warn-dim);border:1px solid #fde68a;color:#92400e;}
.callout.unc{background:var(--surface-2);border:1px solid var(--border);color:var(--muted);}
.method-line{margin-top:8px;font-size:11px;font-weight:700;color:var(--text);}
.check-summary{border:1px solid var(--border);border-radius:8px;overflow:hidden;margin-top:8px;}
.check-summary-head{padding:9px 14px;background:var(--surface-2);border-bottom:1px solid var(--border);font-size:11px;font-weight:700;color:var(--muted);}
.check-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:8px 14px;border-bottom:1px solid var(--border);font-size:12px;cursor:pointer;}
.check-row:last-child{border-bottom:none;}
.check-row:hover{background:var(--surface);}
.check-name{flex:1 1 220px;min-width:0;}
.check-vals{display:flex;gap:14px;flex:0 1 auto;flex-wrap:wrap;font-variant-numeric:tabular-nums;color:var(--muted);font-size:11px;}
.badge{display:inline-flex;align-items:center;padding:2px 7px;border-radius:4px;font-size:11px;font-weight:700;}
.badge-ok{background:var(--ok-dim);color:#166534;}
.badge-exp{background:var(--accent-dim);color:#075f58;}
.badge-warn{background:var(--warn-dim);color:#92400e;}
.badge-unc{background:var(--surface-2);color:var(--muted);}
.expand-tri{font-size:9px;color:var(--muted);transition:transform .15s;display:inline-block;}
.diag-card{border:1px solid var(--border);border-radius:7px;padding:14px;margin-bottom:12px;}
.diag-title{font-size:13px;font-weight:700;margin-bottom:6px;}
.diag-reason{margin-bottom:8px;font-size:12px;}
.diag-candidates{margin-left:16px;font-size:11px;color:var(--muted);}
.diag-guide{margin-top:8px;font-size:11px;color:var(--muted);}
.acct-state{font-size:10px;font-weight:700;padding:1px 6px;border-radius:3px;border:1px solid var(--border);white-space:nowrap;}
.as-ok{color:var(--ok);} .as-exp{color:var(--accent);} .as-warn{color:var(--warn);} .as-unc{color:var(--muted);} .as-nt{color:#94a3b8;}
.state-col{width:64px;text-align:center;}
.tech-detail{margin-top:8px;font-size:11px;color:var(--muted);} .tech-detail code{font-size:10px;}
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
.legend-methods li{display:grid;grid-template-columns:minmax(180px,240px) 1fr;gap:10px;padding:7px 12px;border-bottom:1px solid var(--border);font-size:11px;}
.legend-methods li:last-child{border-bottom:none;}
.legend-methods code{font-size:10px;color:var(--accent);}
.check-row[hidden]{display:none;}
@media (max-width: 980px){
  .shell{grid-template-columns:1fr;}
  aside{position:relative;height:auto;max-height:30vh;border-right:none;border-bottom:1px solid rgba(255,255,255,.08);}
  main{padding:18px 16px;}
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
    if status == EXPLAINABLE_GAP:
        return "badge-exp"
    if status == UNEXPLAINED_GAP:
        return "badge-warn"
    return "badge-unc"


def _status_to_badge_label(status: str) -> str:
    if status == MATCHED:
        return "✓ 일치"
    if status == EXPLAINABLE_GAP:
        return "△ 설명된 차이"
    if status == UNEXPLAINED_GAP:
        return "⚠ 차이"
    return "? 불확실"


def _account_state_badge(status: str | None) -> str:
    """Per-account verification-state badge for statement line rows.
    status None => 미검증 (no covering check). Render-derived; never a CheckResult."""
    if status == MATCHED:
        return '<span class="acct-state as-ok">검증완료</span>'
    if status == EXPLAINABLE_GAP:
        return '<span class="acct-state as-exp">설명차이</span>'
    if status == UNEXPLAINED_GAP:
        return '<span class="acct-state as-warn">검토필요</span>'
    if status == PARSE_UNCERTAIN:
        return '<span class="acct-state as-unc">파싱불확실</span>'
    return '<span class="acct-state as-nt">미검증</span>'
