"""Self-contained HTML report export for audit reconciliation results."""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.checks import CheckResult
from dart_footing_reconciler.document import FullReport, ReportSection
from dart_footing_reconciler.table_semantics import (
    amount_from_current_period as semantic_amount_from_current_period,
    amount_from_prior_period as semantic_amount_from_prior_period,
    current_period_columns as semantic_current_period_columns,
    fiscal_period_columns as semantic_fiscal_period_columns,
    prior_period_columns as semantic_prior_period_columns,
)
from dart_footing_reconciler.taxonomy import ClassifiedReport, classify_report


PRIMARY_CHECK_TYPES = {
    "primary_balance_reconciliation",
    "cashflow_reconciliation",
    "expense_allocation",
    "prior_year_beginning_balance_match",
}

NOTE_ASSERTION_CHECK_TYPES = {
    "note_rollforward_check",
    "note_balance_bridge_check",
    "note_internal_consistency_check",
}

NOTE_BRIDGE_CHECK_TYPES = {
    "asset_note_bridge_check",
}


def export_audit_reconciliation_html(
    report: FullReport, checks: list[CheckResult], output_path: str | Path
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_audit_reconciliation_html(report, checks), encoding="utf-8")
    return output


def render_audit_reconciliation_html(report: FullReport, checks: list[CheckResult]) -> str:
    generated_at = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M")
    verdict = _overall_verdict(checks)
    classified = classify_report(report)
    scope_context = _scope_context(report, checks)
    account_coverage = _account_coverage_rows(report, classified, checks, scope_context)
    primary_checks = [check for check in checks if check.check_type in PRIMARY_CHECK_TYPES]
    supporting_checks = [check for check in checks if check.check_type not in PRIMARY_CHECK_TYPES]
    total_checks = [check for check in supporting_checks if check.check_type == "total_check"]
    note_assertion_checks = [check for check in supporting_checks if check.check_type in NOTE_ASSERTION_CHECK_TYPES]
    note_bridge_checks = [check for check in supporting_checks if check.check_type in NOTE_BRIDGE_CHECK_TYPES]
    other_supporting_checks = [
        check
        for check in supporting_checks
        if check.check_type != "total_check"
        and check.check_type not in NOTE_ASSERTION_CHECK_TYPES
        and check.check_type not in NOTE_BRIDGE_CHECK_TYPES
    ]
    review_checks = [
        check
        for check in checks
        if _check_audit_status_label(check)
        in {"차이내역 확인 필요", "합계 차이 확인 필요", "원천 근거 부족", "실질 차이 확인 필요", "표 구조 해석 필요"}
    ]
    primary_review_checks = [check for check in review_checks if check.check_type in PRIMARY_CHECK_TYPES]
    note_tables_by_source_global = _note_tables_by_source(report)
    note_self_verification_by_no_global = _note_self_verification_by_no(checks)

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(report.company)} 감사 대사 결과 보고서</title>
  <style>
{_css()}
  </style>
</head>
<body>
  <div class="report-shell">
    <aside class="report-sidebar">
      <div class="sidebar-title">감사 대사</div>
      <nav class="report-nav" aria-label="조서 이동">
        <a href="#summary">요약</a>
        <a href="#statement-match">재무제표-주석 공식 계정 대사</a>
        <a href="#cashflow-map">현금흐름표-주석 현금 변동 대사</a>
        <a href="#prior">전기말-당기초 대사</a>
        <a href="#supporting">보조 검증</a>
        <a href="#gaps">검증 제외 및 한계</a>
        <a href="#note-totals">원천 근거</a>
        <a href="#asset-note-bridges">자산 주석 연결</a>
        <a href="#note-assertions">주석별 내부 검증</a>
        <a href="#expense-allocation">상각비 배부</a>
      </nav>
    </aside>
    <main class="report-main">
      {_worksheet_cover(report, generated_at, verdict)}
      {_view_tabs()}
      {_scope_switcher(scope_context)}
      {_scope_kpi_strips(checks, account_coverage, scope_context)}

      <div class="view-panel" data-view-panel="working">
      {_statement_match_section(report, classified, checks, scope_context)}
      {_cashflow_relation_map_section(report, primary_checks, scope_context, note_tables_by_source_global, note_self_verification_by_no_global)}
      {_section(
          "asset-note-bridges",
          "자산 주석 연결 대사",
          "자산 주석 연결 대사: 자산 증감표, 비현금거래, 처분손익 등 관련 주석 금액이 현금흐름표 산식으로 연결되는지 확인합니다.",
          note_bridge_checks,
          ("연결 항목", "현금흐름표 금액", "주석 산식 금액"),
          scope_context,
          note_tables_by_source_global,
          note_self_verification_by_no_global,
      )}
      {_section(
          "note-assertions",
          "주석별 내부 검증",
          "주석별 내부 검증: 주석 표 내부의 증감표, 합계, 관련 주석 간 대사가 재현 가능한지 확인합니다.",
          note_assertion_checks,
          ("검증 항목", "계산 금액", "원문 금액"),
          scope_context,
          note_tables_by_source_global,
          note_self_verification_by_no_global,
      )}
      {_note_total_section(report, [*total_checks, *note_assertion_checks], scope_context)}
      {_section(
          "expense-allocation",
          "성격별 비용-자산 주석 상각비 대사",
          "상각비 배부 대사: 성격별 비용 주석의 감가상각비·무형자산상각비가 자산 주석의 매출원가, 판매비와관리비 등 기능별 배부 합계와 일치하는지 확인합니다.",
          [check for check in primary_checks if check.check_type == "expense_allocation"],
          ("대상 비용", "성격별 비용 금액", "자산 주석 배부금액"),
          scope_context,
          note_tables_by_source_global,
          note_self_verification_by_no_global,
      )}
      {_section(
          "prior",
          "전기말-당기초 대사",
          "전기말-당기초 대사: 전기 주석의 기말 장부금액이 당기 주석의 기초 장부금액으로 이어지는지 확인합니다.",
          [check for check in primary_checks if check.check_type == "prior_year_beginning_balance_match"],
          ("주석", "전기 기말금액", "당기 기초금액"),
          scope_context,
          note_tables_by_source_global,
          note_self_verification_by_no_global,
      )}
      {_section(
          "supporting",
          "보조 검증",
          "보조 검증: 주석 간 대사, 전기 비교표처럼 주요 대사를 뒷받침하는 검증입니다.",
          other_supporting_checks,
          ("검증 항목", "기준 금액", "확인 금액"),
          scope_context,
          note_tables_by_source_global,
          note_self_verification_by_no_global,
      )}
      <section class="report-section" id="gaps">
        <div class="section-head">
          <h2>검증 제외 및 한계</h2>
          <p>자동 대사는 원천 표에서 필요한 계정, 주석, 현금 변동 행을 찾은 경우에만 수행합니다.</p>
        </div>
        <div class="gap-grid">
          <article>
            <strong>필수 확인</strong>
            <p>후속 확인 항목은 차이내역 확인 필요와 실질 차이 확인 필요를 구분해 원천 근거를 확인합니다.</p>
          </article>
          <article>
            <strong>추정 금지</strong>
            <p>필요한 원천 행이 없으면 자동으로 맞다고 판단하지 않습니다. 누락 항목은 후속 버전에서 별도 표시할 예정입니다.</p>
          </article>
        </div>
      </section>
      </div>

      <div class="view-panel" data-view-panel="review" hidden>
      {_review_queue_section(primary_checks, scope_context)}
      {_reviewer_lens_section(report)}
      {_coverage_section(account_coverage)}
      </div>

      <footer class="report-footer">이 보고서는 DART 공시 파싱 결과를 기준으로 생성되었습니다. 원천 표 위치는 각 행의 근거 위치에서 확인합니다.</footer>
    </main>
    <aside class="note-drawer" aria-label="선택 계정 주석 상세" aria-hidden="true">
      <div class="note-drawer-head">
        <div>
          <p class="eyebrow">선택 계정 주석</p>
          <h2>계정을 선택하세요</h2>
        </div>
        <button type="button" class="note-drawer-close" aria-label="주석 상세 닫기">닫기</button>
      </div>
      <div class="note-drawer-body">
        <p class="empty">재무제표 원문 표에서 계정명을 누르면 FSC, 매칭 주석, 원문 주석 표가 이곳에 표시됩니다.</p>
      </div>
    </aside>
  </div>
  <script>
{_js()}
  </script>
</body>
</html>
"""


def _scope_context(report: FullReport, checks: list[CheckResult]) -> dict[str, object]:
    statement_table_scopes = _statement_table_scopes(report)
    note_table_scopes = _note_table_scopes(report)
    scopes = {
        scope
        for scope in statement_table_scopes.values()
        if scope in {"consolidated", "separate"}
    }
    if not scopes:
        scopes.update(
            scope for scope in (_check_scope_raw(check, statement_table_scopes, note_table_scopes) for check in checks)
            if scope in {"consolidated", "separate"}
        )
    ordered = [scope for scope in ("consolidated", "separate") if scope in scopes]
    if not ordered:
        ordered = ["unknown"]
    default_scope = "consolidated" if "consolidated" in ordered else ordered[0]
    return {
        "statement_table_scopes": statement_table_scopes,
        "note_table_scopes": note_table_scopes,
        "scopes": ordered,
        "default_scope": default_scope,
    }


def _statement_table_scopes(report: FullReport) -> dict[str, str]:
    table_items: list[tuple[str, ReportSection, object]] = []
    explicit: dict[str, str] = {}
    for section in report.statements:
        for block in section.blocks:
            table = block.table
            if table is None:
                continue
            source = f"{section.section_id}/table:{table.index}"
            table_items.append((source, section, table))
            explicit_scope = _explicit_statement_table_scope(section, table)
            if explicit_scope:
                explicit[source] = explicit_scope

    inferred = _infer_statement_table_scopes_from_sequence(table_items)
    scopes: dict[str, str] = {}
    for source, _section, _table in table_items:
        scopes[source] = explicit.get(source) or inferred.get(source) or "unknown"
    return scopes


def _explicit_statement_table_scope(section: ReportSection, table) -> str:
    text = f"{section.title} {getattr(table, 'heading', '')}"
    if "(연결)" in text or "연결재무제표" in text:
        return "consolidated"
    if "(별도)" in text or "별도재무제표" in text:
        return "separate"
    acode_scope = _scope_from_table_acodes(table)
    return acode_scope


def _scope_from_table_acodes(table) -> str:
    scopes = {
        _scope_from_acodes(row_acodes)
        for row_acodes in getattr(table, "row_acodes", []) or []
    }
    scopes.discard("")
    if len(scopes) == 1:
        return scopes.pop()
    return ""


def _infer_statement_table_scopes_from_sequence(
    table_items: list[tuple[str, ReportSection, object]]
) -> dict[str, str]:
    first_seen: set[str] = set()
    second_cycle_start: int | None = None
    for idx, (_source, section, _table) in enumerate(table_items):
        key = _statement_scope_sequence_key(section.title)
        if key in first_seen:
            second_cycle_start = idx
            break
        first_seen.add(key)
    if second_cycle_start is None or second_cycle_start == 0:
        return {}
    return {
        source: "consolidated" if idx < second_cycle_start else "separate"
        for idx, (source, _section, _table) in enumerate(table_items)
    }


def _statement_scope_sequence_key(title: str) -> str:
    normalized = _compact(title)
    if "재무상태표" in normalized:
        return "financial_position"
    if "현금흐름표" in normalized:
        return "cash_flows"
    if "자본변동표" in normalized:
        return "changes_in_equity"
    if "손익계산서" in normalized or "포괄손익계산서" in normalized:
        return normalized
    return normalized


def _note_table_scopes(report: FullReport) -> dict[str, str]:
    return {
        f"{section.section_id}/table:{block.table.index}": _note_table_scope(block.table)
        for section in report.notes
        for block in section.blocks
        if block.table is not None
    }


def _scope_switcher(scope_context: dict[str, object]) -> str:
    scopes = list(scope_context["scopes"])
    if len(scopes) <= 1:
        return ""
    buttons = "\n".join(
        f'<button type="button" class="scope-tab" data-scope-tab="{escape(scope)}">{escape(_scope_label(scope))}</button>'
        for scope in scopes
    )
    return f"""
      <section class="scope-switcher" aria-label="보고 범위 선택">
        <div>
          <p class="eyebrow">보고 범위</p>
          <h2>연결/별도 검증 결과 구분</h2>
        </div>
        <div class="scope-tabs" role="tablist">{buttons}</div>
      </section>
"""


def _scope_kpi_strips(
    checks: list[CheckResult],
    account_coverage: list[dict[str, str | int | None]],
    scope_context: dict[str, object],
) -> str:
    strips: list[str] = []
    for scope in scope_context["scopes"]:
        scoped_checks = [check for check in checks if _check_scope(check, scope_context) == scope]
        scoped_coverage = [row for row in account_coverage if row.get("scope") == scope]
        status_counts = _audit_status_counts(scoped_checks)
        follow_up_count = sum(
            status_counts[label]
            for label in ("차이내역 확인 필요", "합계 차이 확인 필요", "자동화 보완 필요", "원천 근거 부족", "실질 차이 확인 필요", "표 구조 해석 필요")
        )
        strips.append(
            f"""
      <section class="kpi-strip" aria-label="{escape(_scope_label(scope))} 핵심 지표" data-report-scope="{escape(scope)}">
        {_kpi("전체 대사 항목", len(scoped_checks), f"{_scope_label(scope)} 자동 수행")}
        {_kpi("일치", status_counts["대사 완료"], "허용 차이 이내")}
        {_kpi("미해소 차이", follow_up_count, "조서 검토 필요")}
        {_kpi("검증 제외", status_counts["자동 검증 제외"], "원천 근거 부족")}
        {_kpi("재무제표 계정", len(scoped_coverage), "본문 계정 기준")}
      </section>
"""
        )
    return "\n".join(strips)


def _table_scope_for_source(scope_context: dict[str, object], table_source: str) -> str:
    statement_table_scopes = scope_context.get("statement_table_scopes", {})
    if isinstance(statement_table_scopes, dict):
        return str(statement_table_scopes.get(table_source, "unknown"))
    return "unknown"


def _check_scope(check: CheckResult, scope_context: dict[str, object]) -> str:
    statement_table_scopes = scope_context.get("statement_table_scopes", {})
    note_table_scopes = scope_context.get("note_table_scopes", {})
    if not isinstance(statement_table_scopes, dict) or not isinstance(note_table_scopes, dict):
        return "unknown"
    return _check_scope_raw(check, statement_table_scopes, note_table_scopes)


def _check_scope_raw(
    check: CheckResult,
    statement_table_scopes: dict[str, str],
    note_table_scopes: dict[str, str],
) -> str:
    for evidence in check.evidence:
        table_source = _source_table_prefix(evidence.source)
        if table_source in statement_table_scopes:
            return statement_table_scopes[table_source]
    for evidence in check.evidence:
        table_source = _source_table_prefix(evidence.source)
        if table_source in note_table_scopes:
            return note_table_scopes[table_source]
    return "unknown"


def _scope_label(scope: str) -> str:
    return {
        "consolidated": "연결",
        "separate": "별도",
        "unknown": "범위 미확정",
    }.get(scope, scope)


def _scoped_statement_title(title: str, scope: str) -> str:
    if scope in {"consolidated", "separate"} and _scope_label(scope) not in title:
        return f"{_scope_label(scope)} · {title}"
    return title


def _statement_match_section(
    report: FullReport,
    classified: ClassifiedReport,
    checks: list[CheckResult],
    scope_context: dict[str, object],
) -> str:
    statement_sections = "\n".join(
        _statement_match_block(report, section, classified, checks, scope_context)
        for section in report.statements
    )
    if not statement_sections:
        statement_sections = '<p class="empty">재무제표 원문 표를 찾지 못했습니다.</p>'
    return f"""
      <section class="report-section statement-match-section" id="statement-match">
        <div class="section-head">
          <h2>재무제표-주석 공식 계정 대사</h2>
          <p class="term-note"><strong>공식 계정 대사</strong>: 재무상태표 또는 손익계산서의 계정 금액이 관련 주석의 기말금액 또는 표시금액과 맞는지 확인하는 절차입니다.</p>
          <div class="self-verify-advisory">
            <strong>관련 주석의 자체 검증 한계</strong>
            <p>주석 내부 합계·증감표·교차 참조 등 자체 정합성은 현 단계에서 자산 증감표 검산에 한정되며, 그 외 주석 내부 검산은 별도 자동 확인되지 않습니다. 각 관련 주석 셀에 다음 배지를 표시합니다.</p>
            <ul>
              <li><span class="self-verify-badge ok">증감표 검산</span> 해당 주석의 기초 + 변동 = 기말 정합이 확인된 경우.</li>
              <li><span class="self-verify-badge warn">증감표 검산 차이</span> 증감표 검산에서 차이가 확인된 경우.</li>
              <li><span class="self-verify-badge none">자체 검산 미확인</span> 자체 검산 결과가 없거나 자동 검증이 적용되지 않은 경우.</li>
            </ul>
          </div>
        </div>
        {statement_sections}
      </section>
"""


def _statement_match_block(
    report: FullReport,
    section: ReportSection,
    classified: ClassifiedReport,
    checks: list[CheckResult],
    scope_context: dict[str, object],
) -> str:
    tables = [block.table for block in section.blocks if block.table is not None]
    if not tables:
        return ""
    classified_by_source = {line.source: line for line in classified.statement_lines}
    checks_by_source = _checks_by_first_evidence_source(checks)
    note_topics_by_key = _best_note_topics_by_key(classified)
    note_tables_by_source = _note_tables_by_source(report)
    statement_scopes_by_source = _statement_scopes_by_source(report)
    note_table_sources_by_key = _note_table_sources_by_key(classified, note_tables_by_source)
    note_match_rows_by_source = _note_match_rows_by_statement_source(
        classified, note_tables_by_source, statement_scopes_by_source, note_table_sources_by_key
    )
    note_details_by_key: dict[str, list[str]] = {}
    for amount in classified.note_amounts:
        note_details_by_key.setdefault(amount.account_key, [])
        if amount.label not in note_details_by_key[amount.account_key]:
            note_details_by_key[amount.account_key].append(amount.label)
    note_self_verification_by_no = _note_self_verification_by_no(checks)

    blocks: list[str] = []
    for table in tables:
        table_source = f"{section.section_id}/table:{table.index}"
        scope = _table_scope_for_source(scope_context, table_source)
        display_rows, row_index_map = _display_statement_rows(section, table.rows)
        row_notes = _statement_row_hover_notes(
            section,
            table.index,
            row_index_map,
            classified_by_source,
            checks_by_source,
            note_topics_by_key,
            note_details_by_key,
            note_tables_by_source,
            note_table_sources_by_key,
            note_match_rows_by_source,
        )
        source_rows = _source_table_html(display_rows, row_notes)
        leadsheet = _statement_leadsheet(
            section,
            table,
            note_match_rows_by_source,
            checks_by_source,
            note_tables_by_source,
            note_self_verification_by_no,
        )
        blocks.append(
            f"""
        <article class="statement-block" data-report-scope="{escape(scope)}">
          <h3>{escape(_scoped_statement_title(section.title, scope))}</h3>
          {leadsheet}
          <details class="source-table-details">
            <summary>재무제표 원문 표 보기 — 계정명을 누르면 연결 주석 상세가 열립니다</summary>
            <div class="source-table-panel">
              <div class="panel-label">재무제표 원문</div>
              <div class="source-table-wrap">{source_rows}</div>
            </div>
          </details>
        </article>
"""
        )
    return "\n".join(blocks)


def _leadsheet_tickmark(check: CheckResult) -> tuple[str, str]:
    if check.status == "matched":
        if check.check_type in {"cashflow_reconciliation", "asset_note_bridge_check"}:
            return "C", "status-ok"
        if check.check_type == "total_check":
            return "F", "status-ok"
        return "R", "status-ok"
    if check.status in {"unexplained_gap", "explainable_gap"}:
        return "Φ", _check_audit_status_class(check)
    return "N/T", "status-muted"


def _statement_leadsheet(
    section: ReportSection,
    table,
    note_match_rows_by_source: dict[str, list[dict[str, str]]],
    checks_by_source: dict[str, CheckResult],
    note_tables_by_source: dict[str, object],
    note_self_verification_by_no: dict[str, str],
) -> str:
    prefix = f"{section.section_id}/table:{table.index}/"
    body_rows: list[str] = []
    for row_source, label, amount in _statement_rows(section):
        if not row_source.startswith(prefix):
            continue
        note_rows = note_match_rows_by_source.get(row_source)
        check = checks_by_source.get(row_source)
        if not note_rows and check is None:
            continue
        note_amount = note_rows[0]["current"] if note_rows else "-"
        topic_only = bool(note_rows) and all("· 표 전체" in row["all"] for row in note_rows)
        if check is not None:
            mark, mark_class = _leadsheet_tickmark(check)
            diff = _amount(check.difference)
        elif note_rows and not topic_only:
            mark, mark_class, diff = "R", "status-ok", "-"
        else:
            mark, mark_class, diff = "·", "status-muted", "-"
        related_cell = _leadsheet_related_note_cell(
            note_rows or [],
            check,
            note_tables_by_source,
            note_self_verification_by_no,
        )
        body_rows.append(
            f"""
              <tr>
                <td>{escape(label)}</td>
                <td class="num">{_amount(amount)}</td>
                <td class="num">{escape(note_amount)}</td>
                <td class="num">{diff}</td>
                <td class="tick"><span class="tick-mark {mark_class}">{escape(mark)}</span></td>
                <td class="note related-note-cell">{related_cell}</td>
              </tr>"""
        )
    if not body_rows:
        return ""
    return f"""
          <div class="leadsheet-wrap">
            <table class="leadsheet">
              <thead><tr><th>계정</th><th>재무제표 금액</th><th>주석 금액</th><th>차이</th><th>표기</th><th>관련 주석</th></tr></thead>
              <tbody>{''.join(body_rows)}</tbody>
            </table>
          </div>"""


def _leadsheet_note_label(label: str, limit: int = 44) -> str:
    compact = " ".join(label.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _parse_note_no_from_source(source: str) -> str:
    if not source.startswith("note:"):
        return ""
    rest = source.split("note:", 1)[1]
    return rest.split("/", 1)[0]


def _related_note_display_label(
    note_rows: list[dict[str, str]],
    check: "CheckResult | None",
    note_tables_by_source: dict[str, object],
    limit: int = 44,
) -> tuple[str, str, str]:
    """Return (display_label, full_label, note_no) for a 관련 주석 reference.

    Format: ``주석 NN. 주제명``. Falls back to topic-only or check-derived label.
    """
    note_no = ""
    title = ""
    if note_rows:
        source = note_rows[0].get("source", "")
        note_no = _parse_note_no_from_source(source)
        table_source = _source_table_prefix(source)
        table = note_tables_by_source.get(table_source) if table_source else None
        if table is not None:
            title = _display_note_title(getattr(table, "heading", ""))
        if not title:
            raw = note_rows[0].get("all", "")
            title = raw.split(" · ", 1)[0].strip()
    if not note_no and check is not None and getattr(check, "note_no", None):
        note_no = str(check.note_no)
        if not title and len(check.evidence) > 1:
            evidence_source = check.evidence[1].source
            table_source = _source_table_prefix(evidence_source)
            table = note_tables_by_source.get(table_source) if table_source else None
            if table is not None:
                title = _display_note_title(getattr(table, "heading", ""))
    if note_no and title:
        full = f"주석 {note_no}. {title}"
    elif note_no:
        full = f"주석 {note_no}"
    elif title:
        full = title
    else:
        full = "-"
    display = full if len(full) <= limit else full[: limit - 1].rstrip() + "…"
    return display, full, note_no


def _note_self_verification_by_no(checks: list[CheckResult]) -> dict[str, str]:
    """Map note_no → self-verification status from note_rollforward_check results.

    Status values: ``"verified"`` (matched rollforward exists),
    ``"unverified"`` (rollforward exists but mismatched/uncertain),
    absent key implies no self-verification was attempted for that note.
    """
    status: dict[str, str] = {}
    for check in checks:
        if check.check_type != "note_rollforward_check":
            continue
        note_no = str(getattr(check, "note_no", "") or "")
        if not note_no:
            continue
        existing = status.get(note_no)
        if check.status == "matched":
            if existing != "verified":
                status[note_no] = "verified"
        else:
            if existing is None:
                status[note_no] = "unverified"
    return status


def _self_verification_badge_html(note_no: str, status_by_no: dict[str, str]) -> str:
    status = status_by_no.get(note_no, "")
    if status == "verified":
        return '<span class="self-verify-badge ok" title="해당 주석의 자산 증감표 검산이 통과됨">증감표 검산</span>'
    if status == "unverified":
        return '<span class="self-verify-badge warn" title="증감표 검산에서 차이가 확인됨">증감표 검산 차이</span>'
    return '<span class="self-verify-badge none" title="자체 검산 결과 없음 또는 자동 검증 미적용">자체 검산 미확인</span>'


def _leadsheet_related_note_hover(
    full_label: str,
    note_rows: list[dict[str, str]],
    check: "CheckResult | None",
    note_tables_by_source: dict[str, object],
    self_verification_html: str,
) -> str:
    status_label = "관련 주석"
    status_class = "status-muted"
    judgment_html = ""
    if check is not None:
        status_label = _check_audit_status_label(check)
        status_class = _check_audit_status_class(check)
        judgment_html = _judgment_html(check, _reason_label(check.reason))
    elif note_rows:
        status_label = "주석 연결"
        status_class = "status-warning"
    note_match_table = _note_match_summary_html(note_rows) if note_rows else ""
    if check is not None:
        raw_note_table = _raw_note_table_from_check(check, note_tables_by_source)
    elif note_rows:
        raw_note_table = _raw_note_table_for_match_rows(note_rows, note_tables_by_source)
    else:
        raw_note_table = ""
    return f"""
      <span class="hover-note" role="tooltip">
        <span class="hover-note-head">
          <strong>{escape(full_label)}</strong>
          <span class="status {status_class}">{escape(status_label)}</span>
        </span>
        <span class="self-verify-line">{self_verification_html}</span>
        {note_match_table}
        {judgment_html}
        {raw_note_table}
      </span>
"""


def _leadsheet_related_note_cell(
    note_rows: list[dict[str, str]],
    check: "CheckResult | None",
    note_tables_by_source: dict[str, object],
    note_self_verification_by_no: dict[str, str],
) -> str:
    if not note_rows and check is None:
        return escape("-")
    display, full, note_no = _related_note_display_label(
        note_rows, check, note_tables_by_source
    )
    badge_html = _self_verification_badge_html(note_no, note_self_verification_by_no) if note_no else ""
    hover = _leadsheet_related_note_hover(
        full,
        note_rows,
        check,
        note_tables_by_source,
        badge_html,
    )
    badge_inline = badge_html if note_no else ""
    return (
        '<button type="button" class="row-match-trigger leadsheet-note-trigger" aria-haspopup="dialog">'
        f'<span class="leadsheet-note-display">{escape(display)}</span>'
        '<span class="leadsheet-note-meta">'
        f'{badge_inline}'
        '<span class="match-dot">상세</span>'
        '</span>'
        f'{hover}'
        '</button>'
    )


def _statement_row_hover_notes(
    section: ReportSection,
    table_index: int,
    row_index_map: dict[int, int],
    classified_by_source: dict[str, object],
    checks_by_source: dict[str, CheckResult],
    note_topics_by_key: dict[str, str],
    note_details_by_key: dict[str, list[str]],
    note_tables_by_source: dict[str, object],
    note_table_sources_by_key: dict[str, list[str]],
    note_match_rows_by_source: dict[str, list[dict[str, str]]],
) -> dict[int, str]:
    notes: dict[int, str] = {}
    for row_source, label, amount in _statement_rows(section):
        if not row_source.startswith(f"{section.section_id}/table:{table_index}/"):
            continue
        row_idx = _source_row_index(row_source)
        if row_idx is None:
            continue
        display_row_idx = row_index_map.get(row_idx)
        if display_row_idx is None:
            continue
        notes[display_row_idx] = _hover_note_html(
            label,
            amount,
            classified_by_source.get(row_source),
            checks_by_source.get(row_source),
            note_topics_by_key,
            note_details_by_key,
            note_tables_by_source,
            note_table_sources_by_key,
            note_match_rows_by_source,
        )
    return notes


def _display_statement_rows(section: ReportSection, rows: list[list[str]]) -> tuple[list[list[str]], dict[int, int]]:
    if _statement_scope_sequence_key(section.title) == "changes_in_equity":
        return _display_equity_statement_rows(rows)
    if _is_income_statement_section(section.title):
        return _display_income_statement_rows(rows)
    return rows, {idx: idx for idx in range(len(rows))}


def _is_income_statement_section(title: str) -> bool:
    normalized = _compact(title)
    return "손익계산서" in normalized or "포괄손익계산서" in normalized


def _display_income_statement_rows(rows: list[list[str]]) -> tuple[list[list[str]], dict[int, int]]:
    if not rows:
        return rows, {}
    revenue_idx = next((idx for idx, row in enumerate(rows[1:], start=1) if row and _is_revenue_row_label(row[0])), None)
    cost_idx = next((idx for idx, row in enumerate(rows[1:], start=1) if row and _is_cost_of_sales_row_label(row[0])), None)
    if revenue_idx is None:
        return rows, {idx: idx for idx in range(len(rows))}

    ordered_indices: list[int] = [0, revenue_idx]
    if cost_idx is not None and cost_idx != revenue_idx:
        ordered_indices.append(cost_idx)
    for idx in range(revenue_idx + 1, len(rows)):
        if idx not in ordered_indices:
            ordered_indices.append(idx)
    display_rows = [rows[idx] for idx in ordered_indices]
    return display_rows, {original_idx: display_idx for display_idx, original_idx in enumerate(ordered_indices)}


def _display_equity_statement_rows(rows: list[list[str]]) -> tuple[list[list[str]], dict[int, int]]:
    if len(rows) < 2:
        return rows, {idx: idx for idx in range(len(rows))}
    parent = rows[0]
    child = rows[1]
    parent_labels = {_compact(cell) for cell in parent[1:] if cell.strip()}
    child_labels = {_compact(cell) for cell in child[1:] if cell.strip()}
    if parent_labels == {"자본"} and child_labels - {"자본", "구분"}:
        width = max(len(parent), len(child))
        header = []
        for idx in range(width):
            child_cell = child[idx] if idx < len(child) else ""
            parent_cell = parent[idx] if idx < len(parent) else ""
            header.append(child_cell if child_cell.strip() else parent_cell)
        display_rows = [header] + rows[2:]
        return display_rows, {0: 0, **{original_idx: original_idx - 1 for original_idx in range(2, len(rows))}}
    return rows, {idx: idx for idx in range(len(rows))}


def _is_revenue_row_label(label: str) -> bool:
    normalized = _compact(label)
    return normalized in {
        "매출",
        "매출액",
        "영업수익",
        "수익",
        "수익(매출액)",
        "고객과의계약에서생기는수익",
    }


def _is_cost_of_sales_row_label(label: str) -> bool:
    normalized = _compact(label)
    return normalized in {
        "매출원가",
        "영업비용",
        "수익원가",
        "용역원가",
        "상품매출원가",
        "제품매출원가",
    }


def _source_row_index(source: str) -> int | None:
    marker = "/row:"
    if marker not in source:
        return None
    tail = source.split(marker, 1)[1]
    try:
        return int(tail.split("/", 1)[0])
    except ValueError:
        return None


def _source_column_index(source: str) -> int | None:
    marker = "/col:"
    if marker not in source:
        return None
    try:
        return int(source.split(marker, 1)[1].split("/", 1)[0])
    except ValueError:
        return None


def _source_table_html(rows: list[list[str]], row_notes: dict[int, str]) -> str:
    body: list[str] = ['<table class="source-table">']
    for row_idx, row in enumerate(rows):
        tag = "th" if row_idx == 0 else "td"
        cells: list[str] = []
        for col_idx, cell in enumerate(row):
            content = escape(cell)
            if row_idx in row_notes and col_idx == 0 and tag == "td":
                content = (
                    '<button type="button" class="row-match-trigger" aria-haspopup="dialog">'
                    f"{content}<span class=\"match-dot\">매칭</span>{row_notes[row_idx]}"
                    "</button>"
                )
            cells.append(f"<{tag}>{content}</{tag}>")
        row_class = ' class="has-hover-note"' if row_idx in row_notes else ""
        body.append(f"<tr{row_class}>{''.join(cells)}</tr>")
    body.append("</table>")
    return "\n".join(body)


def _hover_note_html(
    label: str,
    amount: int | None,
    classified_line,
    check: CheckResult | None,
    note_topics_by_key: dict[str, str],
    note_details_by_key: dict[str, list[str]],
    note_tables_by_source: dict[str, object],
    note_table_sources_by_key: dict[str, list[str]],
    note_match_rows_by_source: dict[str, list[dict[str, str]]],
) -> str:
    if check is not None:
        status = _check_audit_status_label(check)
        status_class = _check_audit_status_class(check)
        note = _display_evidence_label(check.evidence[1].label) if len(check.evidence) > 1 else "연결 근거 확인 필요"
        reason = _reason_label(check.reason)
        detail = f"차이 {_amount(check.difference)}"
        raw_note_table = _raw_note_table_from_check(check, note_tables_by_source)
        note_match_table = ""
        judgment_html = _judgment_html(check, reason)
    elif classified_line is not None:
        matched_note_rows = note_match_rows_by_source.get(classified_line.source, [])
        if matched_note_rows:
            note = matched_note_rows[0]["all"]
            details = ", ".join(row["all"] for row in matched_note_rows[:3])
        else:
            note = None
            details = ""
        if note is None and _is_structural_statement_label(label):
            status = "구조/소계"
            status_class = "status-muted"
            note = "별도 주석 대상 아님"
            detail = "재무제표 표시 구조 또는 소계 행"
            reason = "본문 표시 구조를 구성하는 행으로 별도 세부 주석 대사 대상에서 제외함"
        elif note is None:
            status = "공식 계정 확인"
            status_class = "status-muted"
            note = "금액 확인 주석 후보 없음"
            detail = "재무제표 계정명 기준 공식 계정단 확인됨"
            reason = "공식 계정단은 확인됐지만 재무제표 본문 금액과 일치하는 숫자 주석 표는 아직 연결되지 않음"
        else:
            status = "주석 연결"
            status_class = "status-warning"
            detail = details or "하위 세부 근거 확인 필요"
            reason = "공식 계정단으로 분류됐지만 대사 기준 금액 확정이 필요함"
        raw_note_table = _raw_note_table_for_match_rows(matched_note_rows, note_tables_by_source)
        note_match_table = _note_match_summary_html(matched_note_rows)
        judgment_html = f"<span><b>판단</b>{escape(reason)}</span>"
    else:
        status = "매핑 필요"
        status_class = "status-risk"
        note = "미연결"
        detail = "FSC 계정 alias 및 주석 후보 추가 필요"
        reason = "재무제표 본문 계정을 공식 계정단으로 분류하지 못함"
        raw_note_table = ""
        note_match_table = ""
        judgment_html = f"<span><b>판단</b>{escape(reason)}</span>"
    canonical = classified_line.display_name if classified_line is not None else "분류 필요"
    return f"""
      <span class="hover-note" role="tooltip">
        <span class="hover-note-head">
          <strong>{escape(label)}</strong>
          <span class="status {status_class}">{escape(status)}</span>
        </span>
        <span><b>본문 금액</b>{_amount(amount)}</span>
        <span><b>공식 계정단</b>{escape(canonical)}</span>
        <span><b>연결 주석</b>{escape(note)}</span>
        {note_match_table}
        <span><b>하위 세부 근거</b>{escape(detail)}</span>
        {judgment_html}
        {raw_note_table}
      </span>
"""


def _judgment_html(check: CheckResult, reason: str) -> str:
    if check.check_type == "cashflow_reconciliation" and ";" in reason:
        return f'<span class="judgment-block"><b>판단</b>{_cashflow_formula_html(reason)}</span>'
    return f"<span><b>판단</b>{escape(reason)}</span>"


def _note_tables_by_source(report: FullReport) -> dict[str, object]:
    tables: dict[str, object] = {}
    for section in report.notes:
        for block in section.blocks:
            table = block.table
            if table is None:
                continue
            tables[f"{section.section_id}/table:{table.index}"] = table
    return tables


def _statement_scopes_by_source(report: FullReport) -> dict[str, str]:
    scopes: dict[str, str] = {}
    table_scopes = _statement_table_scopes(report)
    for section in report.statements:
        for block in section.blocks:
            table = block.table
            if table is None or not table.rows:
                continue
            table_source = f"{section.section_id}/table:{table.index}"
            table_scope = table_scopes.get(table_source, "unknown")
            headers = table.rows[0]
            for row_idx, row in enumerate(table.rows[1:], start=1):
                amount, col_idx = _row_amount(row, headers)
                if col_idx is None:
                    continue
                row_acodes = _row_acodes(table, row_idx)
                row_scope = _scope_from_acodes(row_acodes)
                scopes[f"{table_source}/row:{row_idx}/col:{col_idx}"] = row_scope or table_scope
    return scopes


def _row_acodes(table, row_idx: int) -> list[str]:
    row_acodes = getattr(table, "row_acodes", None)
    if not row_acodes or row_idx >= len(row_acodes):
        return []
    return row_acodes[row_idx]


def _scope_from_acodes(acodes: list[str]) -> str:
    normalized = " ".join(acode.lower() for acode in acodes)
    if "consolidatedmember" in normalized:
        return "consolidated"
    if "separatemember" in normalized:
        return "separate"
    return ""


def _note_table_scope(table) -> str:
    heading = getattr(table, "heading", "")
    if "(연결)" in heading or "연결)" in heading:
        return "consolidated"
    if "(별도)" in heading or "별도)" in heading:
        return "separate"
    return "unknown"


def _scope_compatible(statement_scope: str, note_scope: str) -> bool:
    if note_scope == "unknown":
        return True
    if statement_scope == "consolidated":
        return note_scope == "consolidated"
    if statement_scope == "separate":
        return note_scope != "consolidated"
    return True


def _best_note_topics_by_key(classified: ClassifiedReport) -> dict[str, str]:
    best: dict[str, tuple[tuple[int, int, int], str]] = {}
    display_names = {line.account_key: line.display_name for line in classified.statement_lines}
    display_names.update({topic.topic_key: topic.display_name for topic in classified.note_topics})
    for topic in classified.note_topics:
        display_name = display_names.get(topic.topic_key, topic.display_name)
        compact_title = _compact(topic.title)
        compact_display = _compact(display_name)
        score = (
            0 if compact_display and compact_display in compact_title else 1,
            0 if "공시" in topic.title else 1,
            len(topic.title),
        )
        label = f"주석 {topic.note_no} {_display_note_title(topic.title)}"
        if topic.topic_key not in best or score < best[topic.topic_key][0]:
            best[topic.topic_key] = (score, label)
    return {key: value for key, (_, value) in best.items()}


def _note_match_rows_by_key(
    classified: ClassifiedReport, note_tables_by_source: dict[str, object]
) -> dict[str, list[dict[str, str]]]:
    grouped: dict[tuple[str, str, str], list[object]] = {}
    for amount in classified.note_amounts:
        table_source = _source_table_prefix(amount.source)
        table = note_tables_by_source.get(table_source)
        if table is None or not _is_displayable_note_table(getattr(table, "heading", "")):
            continue
        title = _display_note_title(getattr(table, "heading", amount.note_title))
        group_key = (amount.account_key, _compact(title), _compact(amount.label))
        grouped.setdefault(group_key, []).append(amount)

    rows_by_key: dict[str, list[dict[str, str]]] = {}
    for (account_key, _title_key, _label_key), amounts in sorted(
        grouped.items(), key=lambda item: _note_amount_sort_key(item[1][0], note_tables_by_source)
    ):
        ordered = sorted(amounts, key=lambda amount: _note_amount_sort_key(amount, note_tables_by_source))
        current = ordered[0]
        current_table_source = _source_table_prefix(current.source)
        current_table = note_tables_by_source.get(current_table_source)
        title = _display_note_title(getattr(current_table, "heading", current.note_title))
        prior = _prior_amount_for_note_amount(current.source, current_table)
        if prior == "-":
            prior = _prior_amount_from_sibling_note_table(current, current_table, note_tables_by_source)
        if prior == "-" and len(ordered) > 1:
            prior_table = note_tables_by_source.get(_source_table_prefix(ordered[1].source))
            prior = _note_amount_display(ordered[1].amount, prior_table)
        label = current.label.strip()
        all_label = _note_match_all_label(title, label)
        rows_by_key.setdefault(account_key, []).append(
            {
                "all": all_label,
                "current": _note_amount_display(current.amount, current_table),
                "prior": prior,
                "source": current.source,
            }
        )
    for rows in rows_by_key.values():
        rows.sort(key=_note_match_row_sort_key)
    return rows_by_key


def _note_match_rows_by_statement_source(
    classified: ClassifiedReport,
    note_tables_by_source: dict[str, object],
    statement_scopes_by_source: dict[str, str],
    note_table_sources_by_key: dict[str, list[str]],
) -> dict[str, list[dict[str, str]]]:
    rows_by_source: dict[str, list[dict[str, str]]] = {}
    amounts_by_key: dict[str, list[object]] = {}
    for amount in classified.note_amounts:
        table_source = _source_table_prefix(amount.source)
        table = note_tables_by_source.get(table_source)
        if table is None or not _is_displayable_note_table(getattr(table, "heading", "")):
            continue
        amounts_by_key.setdefault(amount.account_key, []).append(amount)

    for line in classified.statement_lines:
        candidates = []
        statement_scope = statement_scopes_by_source.get(line.source, "")
        if line.account_key in {"cost_of_sales", "selling_general_admin"}:
            topic_rows = _note_topic_rows_for_line(
                line.account_key,
                line.label,
                statement_scope,
                note_table_sources_by_key,
                note_tables_by_source,
            )
            if topic_rows:
                rows_by_source[line.source] = topic_rows
                continue
        for amount in amounts_by_key.get(line.account_key, []):
            table = note_tables_by_source.get(_source_table_prefix(amount.source))
            if table is None:
                continue
            if not _scope_compatible(statement_scope, _note_table_scope(table)):
                continue
            if not _statement_note_amount_matches(
                line.account_key,
                line.amount,
                amount.amount,
                getattr(table, "unit_multiplier", 1),
            ):
                continue
            candidates.append(amount)
        if candidates:
            rows_by_source[line.source] = _note_match_rows_from_amounts(candidates, note_tables_by_source)
            continue
        topic_rows = _note_topic_rows_for_line(
            line.account_key,
            line.label,
            statement_scope,
            note_table_sources_by_key,
            note_tables_by_source,
        )
        if topic_rows:
            rows_by_source[line.source] = topic_rows
    return rows_by_source


def _note_topic_rows_for_line(
    account_key: str,
    line_label: str,
    statement_scope: str,
    note_table_sources_by_key: dict[str, list[str]],
    note_tables_by_source: dict[str, object],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    sources = sorted(
        note_table_sources_by_key.get(account_key, []),
        key=lambda source: _topic_source_preference(account_key, source, note_tables_by_source),
    )
    for source in sources[:4]:
        table = note_tables_by_source.get(source)
        if table is None or not _scope_compatible(statement_scope, _note_table_scope(table)):
            continue
        title = _display_note_title(getattr(table, "heading", ""))
        if any(_compact(title) == _compact(row["all"].replace(" · 표 전체", "")) for row in rows):
            continue
        current, prior = _topic_table_amounts_for_line(line_label, table)
        rows.append({"all": f"{title} · 표 전체", "current": current, "prior": prior, "source": source})
    return rows


def _topic_table_amounts_for_line(line_label: str, table) -> tuple[str, str]:
    if table is None or not getattr(table, "rows", None):
        return "-", "-"
    headers = table.rows[0]
    variants = _label_match_variants(line_label)
    target_row = None
    for row in table.rows[1:]:
        row_label = _compact(_note_row_label(row))
        if variants and any(variant == row_label or variant in row_label for variant in variants):
            target_row = row
            break
    if target_row is None:
        target_row = next((row for row in table.rows[1:] if _row_amount(row, headers)[0] is not None), None)
    if target_row is None:
        return "-", "-"
    current = _period_amount_display(target_row, headers, table, "current")
    prior = _period_amount_display(target_row, headers, table, "prior")
    return current, prior


def _label_match_variants(label: str) -> set[str]:
    normalized = _compact(label)
    variants = {normalized} if normalized else set()
    replacements = (
        ("기타유동금융자산", "기타금융자산"),
        ("기타비유동금융자산", "기타금융자산"),
        ("영업외수익", "기타수익"),
        ("영업외비용", "기타비용"),
        ("금융수익", "금융수익"),
        ("금융비용", "금융비용"),
    )
    for source, target in replacements:
        if source in normalized:
            variants.add(_compact(target))
    return {variant for variant in variants if variant}


def _period_amount_display(row: list[str], headers: list[str], table, period: str) -> str:
    amount, col_idx = (
        _amount_from_current_period(row, headers)
        if period == "current"
        else _amount_from_prior_period(row, headers)
    )
    if amount is None or col_idx is None:
        return "-"
    return _note_amount_display(amount * getattr(table, "unit_multiplier", 1), table)


def _statement_note_amount_matches(
    account_key: str, statement_amount: int, note_amount: int, unit_multiplier: int = 1
) -> bool:
    if _amounts_close_with_unit(statement_amount, note_amount, unit_multiplier):
        return True
    if account_key in {"selling_general_admin", "income_tax_expense_benefit"}:
        return _amounts_close_with_unit(abs(statement_amount), abs(note_amount), unit_multiplier)
    return False


def _topic_source_preference(
    account_key: str, source: str, note_tables_by_source: dict[str, object]
) -> tuple[int, tuple[int, ...]]:
    table = note_tables_by_source.get(source)
    heading = _compact(getattr(table, "heading", "")) if table is not None else ""
    if account_key in {"cost_of_sales", "selling_general_admin"} and "비용의성격별분류" in heading:
        return (0, _source_sort_key(source))
    return (1, _source_sort_key(source))


def _note_match_rows_from_amounts(
    amounts: list[object], note_tables_by_source: dict[str, object]
) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str], list[object]] = {}
    for amount in amounts:
        table = note_tables_by_source.get(_source_table_prefix(amount.source))
        if table is None:
            continue
        title = _display_note_title(getattr(table, "heading", amount.note_title))
        group_key = (_compact(title), _compact(amount.label))
        grouped.setdefault(group_key, []).append(amount)

    rows: list[dict[str, str]] = []
    for (_title_key, _label_key), grouped_amounts in sorted(
        grouped.items(), key=lambda item: _note_amount_sort_key(item[1][0], note_tables_by_source)
    ):
        ordered = sorted(grouped_amounts, key=lambda amount: _note_amount_sort_key(amount, note_tables_by_source))
        current = ordered[0]
        current_table = note_tables_by_source.get(_source_table_prefix(current.source))
        title = _display_note_title(getattr(current_table, "heading", current.note_title))
        prior = _prior_amount_for_note_amount(current.source, current_table)
        if prior == "-":
            prior = _prior_amount_from_sibling_note_table(current, current_table, note_tables_by_source)
        label = current.label.strip()
        all_label = _note_match_all_label(title, label)
        rows.append(
            {
                "all": all_label,
                "current": _note_amount_display(current.amount, current_table),
                "prior": prior,
                "source": current.source,
            }
        )
    rows.sort(key=_note_match_row_sort_key)
    return rows


def _note_match_all_label(title: str, label: str) -> str:
    compact_label = _compact(label)
    if not compact_label:
        return title
    compact_title = _compact(title)
    if _is_multi_line_note_title(compact_title):
        return f"{title} · {label}"
    return title if compact_label in compact_title else f"{title} · {label}"


def _is_multi_line_note_title(compact_title: str) -> bool:
    return any(
        token in compact_title
        for token in (
            "영업외수익및영업외비용",
            "기타수익및기타비용",
            "금융수익및금융비용",
            "금융수익및금융원가",
        )
    )


def _prior_amount_for_note_amount(source: str, table) -> str:
    if table is None or not getattr(table, "rows", None):
        return "-"
    row_idx = _source_row_index(source)
    col_idx = _source_column_index(source)
    if row_idx is None or col_idx is None or row_idx >= len(table.rows):
        return "-"
    headers = table.rows[0]
    row = table.rows[row_idx]
    for idx in _prior_period_columns(headers):
        if idx == col_idx or idx >= len(row):
            continue
        amount = parse_amount(row[idx])
        if amount is not None:
            unit_multiplier = getattr(table, "unit_multiplier", 1)
            return _note_amount_display(amount * unit_multiplier, table)
    return "-"


def _prior_amount_from_sibling_note_table(
    amount, table, note_tables_by_source: dict[str, object]
) -> str:
    if table is None or not getattr(table, "rows", None):
        return "-"
    current_source = _source_table_prefix(amount.source)
    current_title = _compact(_display_note_title(getattr(table, "heading", amount.note_title)))
    target_label = _compact(amount.label)
    for source, candidate in sorted(note_tables_by_source.items(), key=lambda item: _source_sort_key(item[0])):
        if source == current_source or not getattr(candidate, "rows", None):
            continue
        if _compact(_display_note_title(getattr(candidate, "heading", ""))) != current_title:
            continue
        headers = candidate.rows[0]
        prior_columns = _prior_period_columns(headers)
        if prior_columns:
            for row in candidate.rows[1:]:
                row_label = _compact(row[0]) if row else ""
                if target_label and target_label != row_label and target_label not in row_label:
                    continue
                for col_idx in prior_columns:
                    if col_idx >= len(row):
                        continue
                    prior_amount = parse_amount(row[col_idx])
                    if prior_amount is not None:
                        unit_multiplier = getattr(candidate, "unit_multiplier", 1)
                        return _note_amount_display(prior_amount * unit_multiplier, candidate)
            continue
        row_idx = _source_row_index(amount.source)
        col_idx = _source_column_index(amount.source)
        if (
            row_idx is not None
            and col_idx is not None
            and row_idx < len(candidate.rows)
            and col_idx < len(candidate.rows[row_idx])
        ):
            prior_amount = parse_amount(candidate.rows[row_idx][col_idx])
            if prior_amount is not None:
                unit_multiplier = getattr(candidate, "unit_multiplier", 1)
                return _note_amount_display(prior_amount * unit_multiplier, candidate)
    return "-"


def _note_amount_display(value: int | None, table) -> str:
    if value is None:
        return "-"
    unit_multiplier = getattr(table, "unit_multiplier", 1) if table is not None else 1
    if unit_multiplier > 1 and abs(value) % unit_multiplier == 0:
        return _amount(value // unit_multiplier)
    return _amount(value)


def _note_match_summary_html(rows: list[dict[str, str]]) -> str:
    if not rows:
        return ""
    rendered = "\n".join(
        f"<span class=\"note-match-cell note-match-label\">{escape(row['all'])}</span>"
        f"<span class=\"note-match-cell note-match-num\">{escape(row['current'])}</span>"
        f"<span class=\"note-match-cell note-match-num\">{escape(row['prior'])}</span>"
        for row in rows[:5]
    )
    return f"""
        <span class="note-match-schema">
          <b>매칭 주석</b>
          <span class="note-match-table-wrap"><span class="note-match-table" role="table" aria-label="매칭 주석 금액">
            <span class="note-match-head">all</span><span class="note-match-head note-match-num">당기</span><span class="note-match-head note-match-num">전기</span>
            {rendered}
          </span></span>
        </span>
"""


def _display_note_title(value: str) -> str:
    title = re.sub(r"^\s*\d+(?:\.\d+)*\.?\s*중요한\s*회계정책\s*", "", value).strip()
    title = re.sub(r"^\s*\d+(?:\.\d+)*\.?\s*", "", title).strip()
    return title or value


def _compact(value: str) -> str:
    return "".join(value.split()).lower()


def _note_table_sources_by_key(
    classified: ClassifiedReport, note_tables_by_source: dict[str, object]
) -> dict[str, list[str]]:
    sources: dict[str, list[str]] = {}
    amount_sources: dict[str, list[str]] = {}
    for amount in sorted(
        classified.note_amounts, key=lambda value: _note_amount_sort_key(value, note_tables_by_source)
    ):
        table_source = _source_table_prefix(amount.source)
        table = note_tables_by_source.get(table_source)
        if not table_source or table is None or not _is_displayable_note_table(getattr(table, "heading", "")):
            continue
        amount_sources.setdefault(amount.account_key, [])
        if table_source not in amount_sources[amount.account_key]:
            amount_sources[amount.account_key].append(table_source)
    sources.update(amount_sources)
    for topic in classified.note_topics:
        topic_sources = [topic.source] if "/table:" in topic.source else [
            source for source in note_tables_by_source if source.startswith(f"{topic.source}/table:")
        ]
        for topic_source in topic_sources:
            table = note_tables_by_source.get(topic_source)
            if table is None or not _is_displayable_note_table(getattr(table, "heading", "")):
                continue
            sources.setdefault(topic.topic_key, [])
            if topic_source not in sources[topic.topic_key]:
                sources[topic.topic_key].append(topic_source)
    return sources


def _raw_note_table_from_check(
    check: CheckResult, note_tables_by_source: dict[str, object]
) -> str:
    if len(check.evidence) < 2:
        return ""
    table_source = _source_table_prefix(check.evidence[1].source)
    if not table_source:
        return ""
    table = note_tables_by_source.get(table_source)
    if table is None or not _is_displayable_note_table(getattr(table, "heading", "")):
        return ""
    return _raw_note_table_html(table)


def _raw_note_table_for_account(
    account_key: str,
    note_tables_by_source: dict[str, object],
    note_table_sources_by_key: dict[str, list[str]],
) -> str:
    for source in note_table_sources_by_key.get(account_key, []):
        table = note_tables_by_source.get(source)
        if table is not None:
            return _raw_note_table_html(table)
    return ""


def _raw_note_table_for_match_rows(
    matched_note_rows: list[dict[str, str]], note_tables_by_source: dict[str, object]
) -> str:
    if not matched_note_rows:
        return ""
    table_source = _source_table_prefix(matched_note_rows[0].get("source", ""))
    table = note_tables_by_source.get(table_source)
    if table is None:
        return ""
    return _raw_note_table_html(table)


def _is_displayable_note_table(heading: str) -> bool:
    normalized = _compact(heading)
    business_disclosure_keywords = (
        "장기체화재고",
        "수주상황",
        "원재료",
        "생산설비",
        "사업의내용",
        "배당에관한사항",
    )
    if any(keyword in normalized for keyword in business_disclosure_keywords):
        return False
    risk_keywords = ("신용위험", "시장위험", "유동성위험", "자본위험")
    disclosure_keywords = ("장부금액", "변동", "내역", "범주별", "구성내역", "세부내역")
    return not any(keyword in normalized for keyword in risk_keywords) or any(
        keyword in normalized for keyword in disclosure_keywords
    )


def _source_sort_key(source: str) -> tuple[int, ...]:
    numbers = tuple(int(value) for value in re.findall(r"\d+", source))
    return numbers or (0,)


def _note_amount_sort_key(amount, note_tables_by_source: dict[str, object]) -> tuple[int, tuple[int, ...]]:
    table = note_tables_by_source.get(_source_table_prefix(amount.source))
    return (_note_table_rank(table), _source_sort_key(amount.source))


def _note_table_rank(table) -> int:
    heading = _compact(getattr(table, "heading", ""))
    if any(keyword in heading for keyword in ("장부금액", "범주별", "구성내역", "세부내역")):
        return 0
    if "내역" in heading:
        return 1
    if any(keyword in heading for keyword in ("가치평가기법", "서열체계", "공정가치")):
        return 2
    return 1


def _note_match_row_sort_key(row: dict[str, str]) -> tuple[int, int, str]:
    prior = parse_amount(row["prior"])
    has_prior = 0 if prior not in (None, 0) else 1
    return (has_prior, _note_title_rank(row["all"]), row["all"])


def _note_title_rank(title: str) -> int:
    compact = _compact(title)
    if any(keyword in compact for keyword in ("장부금액", "범주별", "구성내역", "세부내역")):
        return 0
    if "내역" in compact:
        return 1
    if any(keyword in compact for keyword in ("가치평가기법", "서열체계", "공정가치")):
        return 2
    return 1


def _amounts_close(left: int, right: int) -> bool:
    if min(abs(left), abs(right)) >= 1_000_000:
        return abs(left - right) <= 999
    return left == right


def _amounts_close_with_unit(left: int, right: int, unit_multiplier: int) -> bool:
    if _amounts_close(left, right):
        return True
    return abs(left - right) <= max(unit_multiplier - 1, 0)


def _source_table_prefix(source: str) -> str:
    if "/table:" not in source:
        return ""
    prefix, tail = source.split("/table:", 1)
    table_index = tail.split("/", 1)[0]
    return f"{prefix}/table:{table_index}"


def _raw_note_table_html(table, cell_issues: dict[tuple[int, int], str] | None = None) -> str:
    rows = getattr(table, "rows", None)
    if not rows:
        return ""
    cell_issues = cell_issues or {}
    rendered_rows = "\n".join(
        "<tr>"
        + "".join(
            _raw_note_table_cell_html(row_idx, col_idx, cell, cell_issues)
            for col_idx, cell in enumerate(row)
        )
        + "</tr>"
        for row_idx, row in enumerate(rows)
    )
    return f"""
        <span class="raw-note-block">
          <b>주석 원문 표</b>
          <span class="raw-note-heading">{escape(getattr(table, "heading", ""))}</span>
          <span class="raw-note-table-wrap"><table class="raw-note-table">{rendered_rows}</table></span>
        </span>
"""


def _raw_note_table_cell_html(
    row_idx: int, col_idx: int, cell: str, cell_issues: dict[tuple[int, int], str]
) -> str:
    tag = "th" if row_idx == 0 else "td"
    display_cell = _raw_note_cell_display(cell, is_header=row_idx == 0)
    issue = cell_issues.get((row_idx, col_idx))
    if not issue:
        return f"<{tag}>{escape(display_cell)}</{tag}>"
    return (
        f'<{tag} class="total-issue-cell">{escape(display_cell)}'
        f'<span class="total-issue-tip">{escape(issue)}</span></{tag}>'
    )


def _raw_note_cell_display(cell: str, *, is_header: bool) -> str:
    if is_header:
        return cell
    if not cell.strip():
        return "-"
    amount = parse_amount(cell)
    if amount == 0:
        return "-"
    return cell


def _checks_by_first_evidence_source(checks: list[CheckResult]) -> dict[str, CheckResult]:
    indexed: dict[str, CheckResult] = {}
    for check in checks:
        if not check.evidence:
            continue
        indexed.setdefault(check.evidence[0].source, check)
    return indexed


def _coverage_section(rows: list[dict[str, str | int | None]]) -> str:
    rendered_rows = "\n".join(_coverage_row(row) for row in rows)
    if not rendered_rows:
        rendered_rows = (
            '<tr><td colspan="8" class="empty">재무제표 본문 계정을 찾지 못했습니다. '
            "원천 HTML의 재무제표 표 구조를 확인하세요.</td></tr>"
        )
    return f"""
      <section class="report-section" id="coverage">
        <div class="section-head">
          <h2>전체 재무제표 계정 커버리지</h2>
          <p class="term-note"><strong>계정 커버리지</strong>: 재무제표 본문에 표시된 계정이 공식 계정단으로 분류되고, 관련 주석 및 하위 세부 금액 근거까지 연결되는지 보여줍니다.</p>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>재무제표</th>
                <th>본문 계정</th>
                <th>금액</th>
                <th>공식 계정단</th>
                <th>연결 주석</th>
                <th>하위 세부 근거</th>
                <th>상태</th>
                <th>필요 조치</th>
              </tr>
            </thead>
            <tbody>
              {rendered_rows}
            </tbody>
          </table>
        </div>
      </section>
"""


def _coverage_row(row: dict[str, str | int | None]) -> str:
    status = str(row["status"])
    return f"""
      <tr data-report-scope="{escape(str(row.get("scope", "unknown")))}">
        <td>{escape(str(row["statement"]))}</td>
        <td>{escape(str(row["label"]))}</td>
        <td class="num">{_amount(row["amount"] if isinstance(row["amount"], int) else None)}</td>
        <td>{escape(str(row["canonical"]))}</td>
        <td>{escape(str(row["note"]))}</td>
        <td>{escape(str(row["detail"]))}</td>
        <td><span class="status {_coverage_status_class(status)}">{escape(status)}</span></td>
        <td>{escape(str(row["action"]))}</td>
      </tr>
"""


def _account_coverage_rows(
    report: FullReport,
    classified: ClassifiedReport,
    checks: list[CheckResult],
    scope_context: dict[str, object],
) -> list[dict[str, str | int | None]]:
    classified_by_source = {line.source: line for line in classified.statement_lines}
    note_topics_by_key = _best_note_topics_by_key(classified)
    note_details_by_key: dict[str, list[str]] = {}
    for amount in classified.note_amounts:
        note_details_by_key.setdefault(amount.account_key, [])
        if amount.label not in note_details_by_key[amount.account_key]:
            note_details_by_key[amount.account_key].append(amount.label)
    reconciled_keys = _reconciled_account_keys(checks)

    rows: list[dict[str, str | int | None]] = []
    for section in report.statements:
        if section.title == "현금흐름표":
            continue
        for source, label, amount in _statement_rows(section):
            scope = _table_scope_for_source(scope_context, _source_table_prefix(source))
            classified_line = classified_by_source.get(source)
            if classified_line is None:
                rows.append(
                    {
                        "scope": scope,
                        "statement": section.title,
                        "label": label,
                        "amount": amount,
                        "canonical": "분류 필요",
                        "note": "미연결",
                        "detail": "-",
                        "status": "공식 계정 매핑 필요",
                        "action": "FSC 계정 alias와 주석 제목 후보 미구성.",
                    }
                )
                continue
            note = note_topics_by_key.get(classified_line.account_key)
            details = ", ".join(note_details_by_key.get(classified_line.account_key, [])[:3])
            if classified_line.account_key in reconciled_keys:
                status = "대사 수행"
                action = "대사 결과와 근거 위치가 자동 산출됨."
            elif note:
                status = "주석 연결"
                action = "하위 세부 금액 중 대사 기준 금액 확정 필요."
            elif _is_structural_statement_label(label):
                status = "구조/소계"
                action = "재무제표 표시 구조 또는 소계 행으로 별도 주석 후보 연결 대상에서 제외했습니다."
            else:
                status = "공식 계정 확인"
                action = "공식 계정단 확인 완료. 관련 주석 제목 또는 하위 표 연결 필요."
            rows.append(
                {
                    "scope": scope,
                    "statement": section.title,
                    "label": label,
                    "amount": amount,
                    "canonical": classified_line.display_name,
                    "note": note or "미연결",
                    "detail": details or "-",
                    "status": status,
                    "action": action,
                }
            )
    return rows


def _statement_rows(section: ReportSection) -> list[tuple[str, str, int | None]]:
    rows: list[tuple[str, str, int | None]] = []
    for block in section.blocks:
        table = block.table
        if table is None or not table.rows:
            continue
        headers = table.rows[0]
        for row_idx, row in enumerate(table.rows[1:], start=1):
            if not row:
                continue
            amount, col_idx = _row_amount(row, headers)
            if col_idx is None:
                continue
            rows.append(
                (
                    f"{section.section_id}/table:{table.index}/row:{row_idx}/col:{col_idx}",
                    row[0],
                    amount,
                )
            )
    return rows


def _row_amount(row: list[str], headers: list[str]) -> tuple[int | None, int | None]:
    amount, col_idx = _amount_from_current_period(row, headers)
    if amount is not None and col_idx is not None:
        return amount, col_idx
    for col_idx in range(len(row) - 1, 0, -1):
        amount = parse_amount(row[col_idx])
        if amount is not None:
            return amount, col_idx
    return None, None


def _amount_from_current_period(row: list[str], headers: list[str]) -> tuple[int | None, int | None]:
    return semantic_amount_from_current_period(row, headers)


def _amount_from_prior_period(row: list[str], headers: list[str]) -> tuple[int | None, int | None]:
    return semantic_amount_from_prior_period(row, headers)


def _current_period_columns(headers: list[str]) -> list[int]:
    return semantic_current_period_columns(headers)


def _prior_period_columns(headers: list[str]) -> list[int]:
    return semantic_prior_period_columns(headers)


def _fiscal_period_columns(headers: list[str]) -> list[tuple[int, int]]:
    return semantic_fiscal_period_columns(headers)


def _is_prior_period_header(value: str) -> bool:
    return _compact(value) in {"전기", "전기말", "전년도", "전기말현재"}


def _reconciled_account_keys(checks: list[CheckResult]) -> set[str]:
    keys: set[str] = set()
    for check in checks:
        if check.check_type not in PRIMARY_CHECK_TYPES:
            continue
        if "." in check.title:
            keys.add(check.title.split(".", 1)[0])
    return keys


def _section(
    section_id: str,
    title: str,
    term_note: str,
    checks: list[CheckResult],
    amount_headers: tuple[str, str, str],
    scope_context: dict[str, object],
    note_tables_by_source: dict[str, object] | None = None,
    note_self_verification_by_no: dict[str, str] | None = None,
) -> str:
    row_renderer = _cashflow_check_row if section_id == "cashflow" else _check_row
    tables_ctx = note_tables_by_source or {}
    verify_ctx = note_self_verification_by_no or {}
    rows = "\n".join(
        row_renderer(check, amount_headers[0], scope_context, tables_ctx, verify_ctx)
        for check in checks
    )
    if not rows:
        rows = (
            f'<tr><td colspan="8" class="empty">{_section_empty_message(section_id)}</td></tr>'
        )
    return f"""
      <section class="report-section" id="{escape(section_id)}">
        <div class="section-head">
          <h2>{escape(title)}</h2>
          <p class="term-note"><strong>{escape(term_note.split(':', 1)[0])}</strong>: {escape(term_note.split(':', 1)[1].strip())}</p>
        </div>
        {_section_review_summary(checks, section_id)}
        <div class="table-wrap">
          <table class="{escape(section_id)}-checks-table">
            {_section_table_head(section_id, amount_headers)}
            <tbody>
              {rows}
            </tbody>
          </table>
        </div>
      </section>
"""


def _section_table_head(section_id: str, amount_headers: tuple[str, str, str]) -> str:
    if section_id == "cashflow":
        headers = (
            amount_headers[0],
            amount_headers[1],
            amount_headers[2],
            "대사 산식",
            "차이",
            "결과",
            "대사 결과",
            "근거 위치",
        )
    else:
        headers = (
            amount_headers[0],
            amount_headers[1],
            amount_headers[2],
            "차이",
            "결과",
            "대사 결과",
            "판단 근거",
            "근거 위치",
        )
    cells = "".join(f"<th>{escape(header)}</th>" for header in headers)
    return f"<thead><tr>{cells}</tr></thead>"


def _check_row(
    check: CheckResult,
    first_col_label: str,
    scope_context: dict[str, object],
    note_tables_by_source: dict[str, object] | None = None,
    note_self_verification_by_no: dict[str, str] | None = None,
) -> str:
    source = _source_cell(check)
    scope = _check_scope(check, scope_context)
    status = _check_audit_status_label(check)
    status_class = _check_audit_status_class(check)
    title_cell = _check_title_cell(
        check,
        first_col_label,
        note_tables_by_source or {},
        note_self_verification_by_no or {},
    )
    return f"""
      <tr class="check-row {status_class}-row" data-report-scope="{escape(scope)}">
        <td class="related-note-cell">{title_cell}</td>
        <td class="num">{_amount(check.expected)}</td>
        <td class="num">{_amount(check.actual)}</td>
        <td class="num">{_amount(check.difference)}</td>
        <td><span class="status {status_class}">{escape(status)}</span></td>
        <td class="review-action">{_review_action_cell(check)}</td>
        <td>{_reason_cell(check)}</td>
        <td class="source">{source}</td>
      </tr>
"""


def _cashflow_check_row(
    check: CheckResult,
    first_col_label: str,
    scope_context: dict[str, object],
    note_tables_by_source: dict[str, object] | None = None,
    note_self_verification_by_no: dict[str, str] | None = None,
) -> str:
    source = _source_cell(check)
    scope = _check_scope(check, scope_context)
    status = _check_audit_status_label(check)
    status_class = _check_audit_status_class(check)
    title_cell = _check_title_cell(
        check,
        first_col_label,
        note_tables_by_source or {},
        note_self_verification_by_no or {},
    )
    return f"""
      <tr class="check-row {status_class}-row" data-report-scope="{escape(scope)}">
        <td class="related-note-cell">{title_cell}</td>
        <td class="num">{_amount(check.expected)}</td>
        <td class="num">{_amount(check.actual)}</td>
        <td>{_reason_cell(check)}</td>
        <td class="num">{_amount(check.difference)}</td>
        <td><span class="status {status_class}">{escape(status)}</span></td>
        <td class="review-action">{_review_action_cell(check)}</td>
        <td class="source">{source}</td>
      </tr>
"""


def _check_title_cell(
    check: CheckResult,
    first_col_label: str,
    note_tables_by_source: dict[str, object],
    note_self_verification_by_no: dict[str, str],
) -> str:
    title = _display_title(check, first_col_label)
    raw_note_table = _raw_note_table_from_check(check, note_tables_by_source)
    has_note = bool(getattr(check, "note_no", "")) and bool(raw_note_table)
    if not has_note:
        return escape(title)
    note_no = str(check.note_no)
    badge_html = _self_verification_badge_html(note_no, note_self_verification_by_no)
    status_label = _check_audit_status_label(check)
    status_class = _check_audit_status_class(check)
    judgment_html = _judgment_html(check, _reason_label(check.reason))
    hover = f"""
      <span class="hover-note" role="tooltip">
        <span class="hover-note-head">
          <strong>{escape(title)}</strong>
          <span class="status {status_class}">{escape(status_label)}</span>
        </span>
        <span class="self-verify-line">{badge_html}</span>
        {judgment_html}
        {raw_note_table}
      </span>
"""
    return (
        '<button type="button" class="row-match-trigger leadsheet-note-trigger" aria-haspopup="dialog">'
        f'<span class="leadsheet-note-display">{escape(title)}</span>'
        '<span class="leadsheet-note-meta">'
        f'{badge_html}'
        '<span class="match-dot">상세</span>'
        '</span>'
        f'{hover}'
        '</button>'
    )


def _note_total_section(
    report: FullReport, checks: list[CheckResult], scope_context: dict[str, object]
) -> str:
    material_checks = [
        check for check in checks if check.status != "not_tested" or check.expected is not None or check.actual is not None
    ]
    material_checks.sort(
        key=lambda check: (
            _total_check_sort_rank(check),
            _source_sort_key(check.evidence[0].source if check.evidence else check.check_id),
        )
    )
    note_tables = _note_total_table_blocks(report, material_checks, scope_context)
    if not note_tables:
        note_tables = '<p class="empty">주석 표에서 검증 가능한 소계 또는 합계 행을 찾지 못했습니다.</p>'
    return f"""
      <section class="report-section" id="note-totals">
        <div class="section-head">
          <h2>원천 근거</h2>
          <p class="term-note"><strong>원천 근거</strong>: 주석 1번부터 마지막 주석까지 원문 표를 유지하면서 소계·합계 차이와 증감표 기초-변동-기말 검산 결과를 표시합니다.</p>
        </div>
        {_note_total_summary(material_checks)}
        <div class="note-total-source-list">{note_tables}</div>
      </section>
"""


def _note_total_summary(checks: list[CheckResult]) -> str:
    if not checks:
        return ""
    matched = sum(1 for check in checks if check.status == "matched")
    mismatched = sum(1 for check in checks if check.status == "unexplained_gap")
    uncertain = sum(1 for check in checks if check.status == "parse_uncertain")
    row_class = "status-risk-row" if mismatched else "status-info-row" if uncertain else "status-ok-row"
    return f"""
        <div class="section-review-summary {row_class}">
          <strong>주석 검증 범위</strong>
          <span>검증 가능 항목 {len(checks)}개 중 일치 {matched}개, 차이 {mismatched}개, 구조 확인 {uncertain}개입니다.</span>
        </div>
"""


def _note_total_table_blocks(
    report: FullReport, checks: list[CheckResult], scope_context: dict[str, object]
) -> str:
    by_table: dict[str, list[CheckResult]] = {}
    for check in checks:
        table_source = _total_check_table_source(check)
        if table_source:
            by_table.setdefault(table_source, []).append(check)
    blocks: list[str] = []
    for section in report.notes:
        note_blocks: list[str] = []
        for block in section.blocks:
            table = block.table
            if table is None or not getattr(table, "rows", None):
                continue
            table_source = f"{section.section_id}/table:{table.index}"
            table_checks = by_table.get(table_source, [])
            if not table_checks and not _is_displayable_note_table(getattr(table, "heading", section.title)):
                continue
            scope = _table_scope_for_source(scope_context, table_source)
            note_blocks.append(_note_total_table_card(table, table_source, table_checks, scope))
        if note_blocks:
            blocks.append(
                f"""
        <article class="note-total-note-block">
          <h3>{escape(_note_section_title(section))}</h3>
          <div class="note-total-table-list">{"".join(note_blocks)}</div>
        </article>
"""
            )
    return "\n".join(blocks)


def _note_total_table_card(table, table_source: str, checks: list[CheckResult], scope: str) -> str:
    status = _note_total_table_status(checks)
    status_class = _audit_status_class(status)
    issue_count = sum(1 for check in checks if check.status == "unexplained_gap")
    structure_count = sum(1 for check in checks if check.status == "parse_uncertain")
    matched_count = sum(1 for check in checks if check.status == "matched")
    meta = f"일치 {matched_count} · 차이 {issue_count} · 구조 확인 {structure_count}"
    return f"""
          <details class="note-total-table-card {status_class}-row" data-report-scope="{escape(scope)}" {"open" if issue_count else ""}>
            <summary>
              <span>{escape(_display_note_title(getattr(table, "heading", "")))}</span>
              <span class="status {status_class}">{escape(status)}</span>
              <small>{escape(meta)}</small>
            </summary>
            {_raw_note_table_html(table, _note_total_cell_issues(checks))}
          </details>
"""


def _note_section_title(section: ReportSection) -> str:
    prefix = f"주석 {section.note_no}" if section.note_no else "주석"
    title = _display_note_title(section.title)
    return f"{prefix}. {title}" if title and not title.startswith(prefix) else title or prefix


def _note_total_table_status(checks: list[CheckResult]) -> str:
    if any(check.status == "unexplained_gap" for check in checks):
        if any(check.check_type == "note_rollforward_check" for check in checks):
            return "주석 검산 차이 확인 필요"
        return "합계 차이 확인 필요"
    if any(check.status == "parse_uncertain" for check in checks):
        return "합계 구조 확인 필요"
    if any(check.status == "matched" for check in checks):
        if any(check.check_type == "note_rollforward_check" for check in checks):
            return "주석 검증 일치"
        return "합계 일치"
    return "주석 검증 대상 없음"


def _total_check_table_source(check: CheckResult) -> str:
    if check.evidence:
        return _source_table_prefix(check.evidence[0].source)
    match = re.search(r":table(\d+)", check.check_id)
    if not match:
        return ""
    return f"note:{check.note_no}/table:{match.group(1)}"


def _note_total_cell_issues(checks: list[CheckResult]) -> dict[tuple[int, int], str]:
    issues: dict[tuple[int, int], str] = {}
    for check in checks:
        if check.status != "unexplained_gap" or not check.evidence:
            continue
        marker_evidence = check.evidence[-1] if check.check_type == "note_rollforward_check" else check.evidence[0]
        row_idx = _source_row_index(marker_evidence.source)
        col_idx = _source_column_index(marker_evidence.source)
        if row_idx is None or col_idx is None:
            continue
        if check.check_type == "note_rollforward_check":
            issues[(row_idx, col_idx)] = (
                f"증감표 검산 · 계산 기말 {_amount(check.expected)} · "
                f"원문 기말 {_amount(check.actual)} · 차이 {_amount(check.difference)}"
            )
        else:
            issues[(row_idx, col_idx)] = (
                f"{_total_check_kind(check)} · 구성항목 합계 {_amount(check.expected)} · "
                f"표시 소계/합계 {_amount(check.actual)} · 차이 {_amount(check.difference)}"
            )
    return issues


def _note_label(check: CheckResult) -> str:
    return f"주석 {check.note_no}" if check.note_no else "주석"


def _total_check_target_label(check: CheckResult) -> str:
    title = check.title
    for suffix in (" row total", " column total", " total check"):
        if title.endswith(suffix):
            return title[: -len(suffix)].strip() or "합계"
    return _human_check_title(title)


def _total_check_kind(check: CheckResult) -> str:
    if check.title.endswith(" row total"):
        return "행 소계/합계"
    if check.title.endswith(" column total"):
        return "열 소계/합계"
    return "합계 구조 확인"


def _total_check_status_label(check: CheckResult) -> str:
    if check.status == "matched":
        return "합계 일치"
    if check.status == "unexplained_gap":
        return "합계 차이 확인 필요"
    if check.status == "parse_uncertain":
        return "합계 구조 확인 필요"
    return "자동 검증 제외"


def _total_check_sort_rank(check: CheckResult) -> int:
    return {
        "unexplained_gap": 0,
        "parse_uncertain": 1,
        "matched": 2,
        "not_tested": 3,
    }.get(check.status, 4)


def _kpi(label: str, value: int, qualifier: str) -> str:
    return f"""<article class="kpi"><span>{escape(label)}</span><strong>{value}</strong><small>{escape(qualifier)}</small></article>"""


def _review_queue_section(checks: list[CheckResult], scope_context: dict[str, object]) -> str:
    review_targets = [
        check
        for check in checks
        if _check_audit_status_label(check)
        in {"차이내역 확인 필요", "원천 근거 부족", "실질 차이 확인 필요", "표 구조 해석 필요"}
    ]
    review_targets.sort(
        key=lambda check: (
            _review_priority(_check_audit_status_label(check)),
            -abs(check.difference or 0),
        )
    )
    if not review_targets:
        body = '<p class="empty">리뷰어가 우선 확인해야 할 후속 확인 항목이 없습니다. 일치 항목의 근거 위치만 표본 조서에 첨부하세요.</p>'
    else:
        cards = "\n".join(_review_queue_card(check, scope_context) for check in review_targets[:6])
        body = f'<div class="review-queue-grid">{cards}</div>'
    return f"""
      <section class="report-section review-queue" id="review-queue">
        <div class="section-head">
          <h2>리뷰 큐</h2>
          <p class="term-note"><strong>리뷰 큐</strong>: 감사팀 또는 리뷰어가 결론 전에 먼저 확인해야 할 항목입니다. 차이내역 확인 필요와 실질 차이 확인 필요를 분리해 표시합니다.</p>
        </div>
        {body}
      </section>
"""


def _review_queue_card(check: CheckResult, scope_context: dict[str, object]) -> str:
    scope = _check_scope(check, scope_context)
    status = _check_audit_status_label(check)
    status_class = _check_audit_status_class(check)
    action = _review_action(check)
    action_html = _review_action_cell_from_action(check, action)
    action_class = ' class="review-action-formula"' if _review_action_uses_formula(check, action) else ""
    return f"""
          <article class="review-card" data-report-scope="{escape(scope)}">
            <div class="review-card-head">
              <strong>{escape(_target_label(check.title))}</strong>
              <span class="status {status_class}">{escape(status)}</span>
            </div>
            <dl>
              <div><dt>차이</dt><dd>{_amount(check.difference)}</dd></div>
              <div{action_class}><dt>대사 결과</dt><dd>{action_html}</dd></div>
            </dl>
          </article>
"""


def _reviewer_lens_section(report: FullReport) -> str:
    lens = _build_reviewer_lens(report)
    movement_rows = "\n".join(
        f"""
              <tr>
                <td>{escape(row['label'])}</td>
                <td class="num">{_amount(row['current'])}</td>
                <td class="num">{_amount(row['prior'])}</td>
                <td class="num">{row['change_html']}</td>
                <td>{escape(row['meaning'])}</td>
              </tr>
"""
        for row in lens["movements"]
    )
    signals = "".join(f"<li>{signal}</li>" for signal in lens["signals"])
    hypotheses = "".join(f"<li>{item}</li>" for item in lens["hypotheses"])
    questions = "".join(f"<li>{escape(item)}</li>" for item in lens["questions"])
    requests = "".join(f"<li>{escape(item)}</li>" for item in lens["requests"])
    summary = "".join(f"<li>{escape(item)}</li>" for item in lens["business_summary"])
    return f"""
      <section class="report-section reviewer-lens-preview" id="reviewer-lens">
        <div class="section-head">
          <h2>리뷰어 렌즈</h2>
          <p class="term-note"><strong>리뷰어 렌즈</strong>: 푸팅 결과와 재무제표 수치를 근거로 리뷰어가 물어야 할 질문을 정리합니다. 아래 내용은 감사위험 단정이 아니라 후속 확인 가설입니다.</p>
        </div>
        <div class="lens-verdict">
          <strong>{escape(lens['verdict'])}</strong>
          <span>{escape(lens['why'])}</span>
        </div>
        <div class="lens-contract lens-two-column">
          <article>
            <strong>사업모델 요약</strong>
            <ul>{summary}</ul>
          </article>
          <article>
            <strong>이상 신호</strong>
            <ul>{signals}</ul>
          </article>
        </div>
        <div class="table-wrap lens-movement-table">
          <table>
            <thead>
              <tr>
                <th>주요 계정</th>
                <th>당기</th>
                <th>전기</th>
                <th>증감</th>
                <th>리뷰 의미</th>
              </tr>
            </thead>
            <tbody>{movement_rows}</tbody>
          </table>
        </div>
        <div class="lens-contract">
          <article>
            <strong>위험 가설</strong>
            <ul>{hypotheses}</ul>
          </article>
          <article>
            <strong>리뷰어 질문</strong>
            <ul>{questions}</ul>
          </article>
        </div>
        <div class="lens-contract">
          <article>
            <strong>요청자료 리스트</strong>
            <ul>{requests}</ul>
          </article>
          <article>
            <strong>주의</strong>
            <p>자동 위험평가는 결론이 아니라 후속 확인 가설입니다. 질문과 요청자료는 감사팀 확인을 위한 출발점으로 사용하세요.</p>
          </article>
        </div>
      </section>
"""


def _section_review_summary(checks: list[CheckResult], section_id: str) -> str:
    if not checks:
        return f"""
        <div class="section-review-summary status-muted-row">
          <strong>검토 상태</strong>
          <span>{escape(_section_empty_message(section_id))}</span>
        </div>
"""
    counts = _audit_status_counts(checks)
    follow_up_count = sum(
        counts[label]
        for label in ("차이내역 확인 필요", "합계 차이 확인 필요", "자동화 보완 필요", "원천 근거 부족", "실질 차이 확인 필요", "표 구조 해석 필요")
    )
    if counts["실질 차이 확인 필요"]:
        summary = f"실질 차이 확인 필요 {counts['실질 차이 확인 필요']}건이 있습니다. 원천 금액 차이가 보고서 표시 차이인지 먼저 확인하세요."
        row_class = "status-risk-row"
    elif follow_up_count:
        summary = f"차이내역 또는 원천 근거 확인 항목 {follow_up_count}건이 있습니다. 회사별 표 구조와 대응 주석을 보완해야 합니다."
        row_class = "status-info-row"
    elif counts["차이내역 확인 필요"]:
        summary = f"차이내역 확인 필요 {counts['차이내역 확인 필요']}건이 있습니다. 표시된 산식과 원천 금액으로 잔여 차이를 확인하세요."
        row_class = "status-warning-row"
    else:
        summary = "표시된 자동 대사 항목은 허용 차이 이내입니다. 근거 위치를 조서에 첨부하면 됩니다."
        row_class = "status-ok-row"
    return f"""
        <div class="section-review-summary {row_class}">
          <strong>섹션 판정</strong>
          <span>{escape(summary)}</span>
        </div>
"""


def _cashflow_relation_map_section(
    report: FullReport,
    checks: list[CheckResult],
    scope_context: dict[str, object],
    note_tables_by_source: dict[str, object] | None = None,
    note_self_verification_by_no: dict[str, str] | None = None,
) -> str:
    tables_ctx = note_tables_by_source or {}
    verify_ctx = note_self_verification_by_no or {}
    activity_rows = _cashflow_material_rows(report, checks, scope_context)
    if not activity_rows:
        activity_rows = _cashflow_rows_from_checks(checks, scope_context)
    operating_rows = _cashflow_operating_adjustment_rows(report)
    if not activity_rows and not operating_rows:
        return ""
    activity_html = "\n".join(
        f"""
          <tr data-report-scope="{escape(str(row.get('scope', 'unknown')))}">
            <td>{escape(row['section'])}</td>
            <td>{escape(row['label'])}</td>
            <td class="num">{_amount(row['amount'])}</td>
            <td>{escape(_cashflow_reference_path(str(row['label'])))}</td>
            <td class="related-note-cell">{_cashflow_related_note_cell(row, checks, tables_ctx, verify_ctx)}</td>
            <td>{_cashflow_relation_formula_html(row, checks)}</td>
            <td><span class="status {_coverage_status_class(row['status'])}">{escape(row['status'])}</span></td>
          </tr>
"""
        for row in activity_rows
    )
    operating_html = "\n".join(
        f"""
          <tr>
            <td>{escape(row['label'])}</td>
            <td class="num">{_amount(row['amount'])}</td>
            <td>{escape(row['reference'])}</td>
            <td>{escape(row['formula'])}</td>
          </tr>
"""
        for row in operating_rows
    )
    return f"""
      <section class="report-section" id="cashflow-map">
        <div class="section-head">
          <h2>현금흐름표-주석 현금 변동 대사</h2>
          <p class="term-note"><strong>현금 변동 대사</strong>: 현금흐름표의 취득, 처분, 차입, 상환 금액이 주석의 현금성 변동 내역과 맞는지 확인하는 절차입니다.</p>
        </div>
        {_cashflow_unified_summary(activity_rows)}
        <div class="cashflow-map-grid">
          <article>
            <h3>투자·재무활동 본문 대사</h3>
            <p class="hover-help">10억원 이상 현금 유입·유출을 기준으로 주석 단일 금액, 산식 대사 근거, 미확인 항목을 분리해 표시합니다.</p>
            <div class="table-wrap">
              <table class="cashflow-map-table">
                <thead>
                  <tr>
                    <th>구분</th>
                    <th>현금흐름표 항목</th>
                    <th>당기 금액</th>
                    <th>참조 경로</th>
                    <th>주석에서 확인된 금액</th>
                    <th>산식/매칭 방식</th>
                    <th>상태</th>
                  </tr>
                </thead>
                <tbody>{activity_html}</tbody>
              </table>
            </div>
          </article>
          <article>
            <h3>영업현금흐름 주석 조정</h3>
            <p class="hover-help">영업현금흐름 주석의 비현금 조정 항목이 어느 손익계산서·비용 주석과 대사되어야 하는지 표시합니다.</p>
            <div class="table-wrap">
              <table class="cashflow-operating-map-table">
                <thead>
                  <tr>
                    <th>현금흐름 주석 조정</th>
                    <th>주석 금액</th>
                    <th>대응 손익/주석</th>
                    <th>산식/검토 방식</th>
                  </tr>
                </thead>
                <tbody>{operating_html}</tbody>
              </table>
            </div>
          </article>
        </div>
      </section>
"""


def _cashflow_rows_from_checks(
    checks: list[CheckResult], scope_context: dict[str, object]
) -> list[dict[str, str | int]]:
    rows: list[dict[str, str | int]] = []
    for check in checks:
        if check.check_type != "cashflow_reconciliation":
            continue
        statement_evidence = next(
            (evidence for evidence in check.evidence if evidence.source.startswith("statement:")),
            None,
        )
        if statement_evidence is None:
            continue
        label = re.sub(r"^\s*cfs\s+", "", statement_evidence.label).strip() or _target_label(check.title)
        table_source = _source_table_prefix(statement_evidence.source)
        rows.append(
            {
                "section": "현금흐름",
                "label": label,
                "amount": statement_evidence.amount or check.expected or 0,
                "status": _cashflow_check_status_label(check, "no_related"),
                "note_candidate": _cashflow_note_candidate(label),
                "next_action": _cashflow_review_result(check, _cashflow_check_status_label(check, "no_related")),
                "source": statement_evidence.source,
                "scope": _table_scope_for_source(scope_context, table_source),
                "note_match": "",
            }
        )
    return rows


def _cashflow_unified_summary(rows: list[dict[str, str | int]]) -> str:
    if not rows:
        return ""
    counts = Counter(str(row.get("status", "")) for row in rows)
    checked = counts["대사 완료"] + counts["주석 금액 확인"]
    difference_review = (
        counts["실질 차이 확인 필요"] + counts["차이내역 확인 필요"]
    )
    disclosure_review = counts["대응 주석 확인 필요"] + counts["표 구조 해석 필요"] + counts["원천 근거 부족"]
    return f"""
        <div class="section-review-summary status-info-row">
          <strong>현금흐름 대사 범위</strong>
          <span>주요 투자·재무활동 {len(rows)}개 중 산식/주석 금액 확인 {checked}개, 차이내역 확인 필요 {difference_review}개, 대응 주석 확인 필요 {disclosure_review}개입니다. 관련 주석을 전수 확인한 뒤 동일 금액 여부와 차이 검토 필요 항목을 분리합니다.</span>
        </div>
"""


def _cashflow_coverage_gap_section(
    report: FullReport, checks: list[CheckResult], scope_context: dict[str, object]
) -> str:
    rows = _cashflow_material_rows(report, checks, scope_context)
    if not rows:
        return ""
    rendered = "\n".join(
        f"""
          <tr data-report-scope="{escape(str(row.get('scope', 'unknown')))}">
            <td>{escape(row['section'])}</td>
            <td>{escape(row['label'])}</td>
            <td class="num">{_amount(row['amount'])}</td>
            <td><span class="status {_coverage_status_class(row['status'])}">{escape(row['status'])}</span></td>
            <td>{escape(row['note_candidate'])}</td>
            <td>{escape(row['next_action'])}</td>
          </tr>
"""
        for row in rows
    )
    return f"""
        <div class="cashflow-gap-panel">
          <h3>현금흐름 주요 유입·유출 커버리지</h3>
          <p class="hover-help">투자활동·재무활동의 10억원 이상 현금흐름 중 현재 자동 대사 타깃에 포함됐는지 확인합니다.</p>
          <div class="table-wrap">
            <table class="cashflow-gap-table">
              <thead>
                <tr>
                  <th>구분</th>
                  <th>현금흐름표 항목</th>
                  <th>당기 금액</th>
                  <th>상태</th>
                  <th>주석 후보</th>
                  <th>필요 조치</th>
                </tr>
              </thead>
              <tbody>{rendered}</tbody>
            </table>
          </div>
        </div>
"""


def _cashflow_material_rows(
    report: FullReport, checks: list[CheckResult], scope_context: dict[str, object] | None = None
) -> list[dict[str, str | int]]:
    checked_sources = _cashflow_checked_statement_sources(checks)
    checks_by_source = _cashflow_check_by_statement_source(checks)
    rows: list[dict[str, str | int]] = []
    for section in report.statements:
        if "현금흐름" not in _compact(section.title):
            continue
        for block in section.blocks:
            table = block.table
            if table is None or not table.rows:
                continue
            current_section = ""
            for row_idx, row in enumerate(table.rows[1:], start=1):
                if not row:
                    continue
                label = row[0].strip()
                normalized = _compact(label)
                if "투자활동" in normalized and "현금흐름" in normalized:
                    current_section = "투자활동"
                    continue
                if "재무활동" in normalized and "현금흐름" in normalized:
                    current_section = "재무활동"
                    continue
                if current_section not in {"투자활동", "재무활동"} or _is_cashflow_summary_line(label):
                    continue
                amount, col_idx = _cashflow_current_amount(row, table.rows[0])
                if amount is None or col_idx is None:
                    continue
                amount *= getattr(table, "unit_multiplier", 1)
                source = f"{section.section_id}/table:{table.index}/row:{row_idx}/col:{col_idx}"
                if abs(amount) < 1_000_000_000 and source not in checked_sources:
                    continue
                table_source = f"{section.section_id}/table:{table.index}"
                note_candidate = _cashflow_note_candidate(label)
                statement_scope = _table_scope_for_source(scope_context, table_source) if scope_context else "unknown"
                note_review = _cashflow_note_review(report, label, amount, statement_scope)
                check = checks_by_source.get(source)
                status = (
                    _cashflow_check_status_label(check, str(note_review["kind"]))
                    if check is not None
                    else _cashflow_map_status(note_candidate, str(note_review["kind"]))
                )
                rows.append(
                    {
                        "section": current_section,
                        "label": label,
                        "amount": amount,
                        "status": status,
                        "note_candidate": note_candidate,
                        "next_action": _cashflow_gap_action(status, note_candidate),
                        "source": source,
                        "scope": statement_scope,
                        "note_match": note_review["exact"],
                        "note_review_kind": note_review["kind"],
                        "note_review_summary": note_review["related"],
                    }
                )
    rows.sort(key=lambda row: (_cashflow_map_sort_rank(str(row["status"])), -abs(int(row["amount"]))))
    return rows


def _cashflow_relation_formula_html(row: dict[str, str | int], checks: list[CheckResult]) -> str:
    check = _cashflow_check_by_statement_source(checks).get(str(row.get("source", "")))
    if check is not None:
        return _reason_cell(check)
    label = str(row["label"])
    normalized = _compact(label)
    if "금융자산" in normalized:
        formula = "기초 금융자산 + 취득 - 처분 ± 평가/환율/대체 = 기말 금융자산"
        target = "현금흐름표 취득·처분 금액을 기타금융자산/범주별 금융상품 변동표의 현금성 변동과 대사"
    elif "매각예정자산" in normalized:
        formula = "처분 현금 = 처분대가 - 미수금 변동 또는 선수금 정산"
        target = "매각예정자산 장부금액, 처분손익, 미수·선수금 변동을 주석과 손익 주석에서 확인"
    elif "관계기업" in normalized or "종속기업" in normalized:
        formula = "투자주식 기초 + 취득 - 처분 ± 지분법/손상/환율/대체 = 기말"
        target = "관계기업·종속기업 투자 변동표의 취득/처분 행과 현금흐름표 금액 대사"
    elif "배당" in normalized or "비지배지분" in normalized or "신종자본증권" in normalized:
        formula = "자본변동표 현금성 거래 = 현금흐름표 재무활동 유출입"
        target = "자본변동표, 이익잉여금/비지배지분/신종자본증권 주석 금액과 직접 연결"
    elif "금융부채" in normalized:
        formula = "재무활동부채 기초 + 재무활동현금흐름 ± 비현금흐름 = 기말"
        target = "현금흐름 주석의 재무활동부채 조정표와 현금흐름표 금액 대사"
    else:
        formula = "현금흐름표 금액 ↔ 관련 주석의 현금성 변동"
        target = "대응 주석 후보를 확정한 뒤 변동표 산식을 구성"
    return f"""
      <div class="formula-box">
        <div class="formula-row"><b>산식</b><span>{escape(formula)}</span></div>
        <div class="formula-row"><b>대상</b><span>{escape(target)}</span></div>
      </div>
"""


def _cashflow_related_note_cell(
    row: dict[str, str | int],
    checks: list[CheckResult],
    note_tables_by_source: dict[str, object],
    note_self_verification_by_no: dict[str, str],
) -> str:
    base_html = _cashflow_note_match_html(row, checks)
    check = _cashflow_check_by_statement_source(checks).get(str(row.get("source", "")))
    if check is None or not getattr(check, "note_no", ""):
        return base_html
    raw_note_table = _raw_note_table_from_check(check, note_tables_by_source)
    if not raw_note_table:
        return base_html
    note_no = str(check.note_no)
    title = ""
    if len(check.evidence) > 1:
        table_source = _source_table_prefix(check.evidence[1].source)
        table = note_tables_by_source.get(table_source) if table_source else None
        if table is not None:
            title = _display_note_title(getattr(table, "heading", ""))
    if not title:
        title = str(row.get("label", "")).strip()
    full_label = f"주석 {note_no}. {title}" if title else f"주석 {note_no}"
    badge_html = _self_verification_badge_html(note_no, note_self_verification_by_no)
    status_label = _check_audit_status_label(check)
    status_class = _check_audit_status_class(check)
    judgment_html = _judgment_html(check, _reason_label(check.reason))
    hover = f"""
      <span class="hover-note" role="tooltip">
        <span class="hover-note-head">
          <strong>{escape(full_label)}</strong>
          <span class="status {status_class}">{escape(status_label)}</span>
        </span>
        <span class="self-verify-line">{badge_html}</span>
        {judgment_html}
        {raw_note_table}
      </span>
"""
    return (
        '<button type="button" class="row-match-trigger leadsheet-note-trigger" aria-haspopup="dialog">'
        f'<span class="leadsheet-note-display">{escape(full_label)}</span>'
        '<span class="leadsheet-note-meta">'
        f'{badge_html}'
        '<span class="match-dot">상세</span>'
        '</span>'
        f'{hover}'
        f'</button>'
        f'<div class="cashflow-note-evidence">{base_html}</div>'
    )


def _cashflow_note_match_html(row: dict[str, str | int], checks: list[CheckResult]) -> str:
    value = str(row.get("note_match", ""))
    if value:
        items = "".join(f"<li>{escape(item.strip())}</li>" for item in value.split("||") if item.strip())
        if items:
            return f'<ul class="cashflow-note-match-list">{items}</ul>'
    check = _cashflow_check_by_statement_source(checks).get(str(row.get("source", "")))
    if check is not None:
        note_items = "".join(
            f"<li>{escape(_display_evidence_label(evidence.label))} · {_amount(evidence.amount)}</li>"
            for evidence in check.evidence
            if evidence.source.startswith("note:")
        )
        if note_items:
            return f'<b class="mini-label">산식 대사 근거</b><ul class="cashflow-note-match-list">{note_items}</ul>'
    related = str(row.get("note_review_summary", ""))
    if related:
        items = "".join(f"<li>{escape(item.strip())}</li>" for item in related.split("||") if item.strip())
        return (
            '<b class="mini-label">관련 주석 확인됨 · 동일 금액 없음</b>'
            f'<ul class="cashflow-note-match-list">{items}</ul>'
        )
    return '<span class="muted">주석 전수 확인 결과 동일/관련 금액 미확인</span>'


def _cashflow_note_match_summary(report: FullReport, label: str, amount: int, statement_scope: str = "unknown") -> str:
    matches = _cashflow_note_match_candidates(report, label, amount, statement_scope)
    return "||".join(matches[:3])


def _cashflow_note_review(
    report: FullReport, label: str, amount: int, statement_scope: str = "unknown"
) -> dict[str, str]:
    exact = _cashflow_note_match_candidates(report, label, amount, statement_scope)
    if exact:
        return {"kind": "exact", "exact": "||".join(exact[:3]), "related": ""}
    related = _cashflow_related_note_candidates(report, label, statement_scope)
    if related:
        return {"kind": "related_no_exact", "exact": "", "related": "||".join(related[:3])}
    return {"kind": "no_related", "exact": "", "related": ""}


def _cashflow_note_match_candidates(report: FullReport, label: str, amount: int, statement_scope: str = "unknown") -> list[str]:
    if amount == 0:
        return []
    family_keywords = _cashflow_note_family_keywords(label)
    if not family_keywords:
        return []
    action_keywords = _cashflow_action_keywords(label)
    candidates: list[tuple[tuple[int, int, tuple[int, ...], int, int], str]] = []
    target = abs(amount)
    for section in report.notes:
        for block in section.blocks:
            table = block.table
            if table is None or not getattr(table, "rows", None):
                continue
            if not _scope_compatible(statement_scope, _note_table_scope(table)):
                continue
            heading = _display_note_title(getattr(table, "heading", section.title))
            if not _is_displayable_note_table(heading):
                continue
            heading_compact = _compact(heading)
            if not _is_cashflow_reconciliation_note_heading(heading_compact):
                continue
            if "전기" in heading_compact and "당기" not in heading_compact:
                continue
            unit_multiplier = getattr(table, "unit_multiplier", 1)
            current_columns = set(_current_period_columns(table.rows[0]))
            for row_idx, row in enumerate(table.rows[1:], start=1):
                row_label = _note_row_label(row)
                context = heading_compact + _compact(row_label)
                if not any(keyword in context for keyword in family_keywords):
                    continue
                for col_idx, cell in enumerate(row[1:], start=1):
                    if current_columns and col_idx not in current_columns:
                        continue
                    raw_amount = parse_amount(cell)
                    if raw_amount is None:
                        continue
                    scaled = raw_amount * unit_multiplier
                    if not _amounts_close_with_unit(target, abs(scaled), unit_multiplier):
                        continue
                    action_rank = 0 if any(keyword in _compact(row_label) for keyword in action_keywords) else 1
                    heading_rank = 0 if any(keyword in heading_compact for keyword in family_keywords) else 1
                    score = (
                        action_rank,
                        heading_rank,
                        _source_sort_key(f"{section.section_id}/table:{table.index}"),
                        row_idx,
                        col_idx,
                    )
                    amount_text = _note_amount_display(scaled, table)
                    candidates.append((score, f"{heading} · {row_label} · {amount_text}"))
    seen: set[str] = set()
    result: list[str] = []
    for _score, text in sorted(candidates):
        if text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _cashflow_related_note_candidates(report: FullReport, label: str, statement_scope: str = "unknown") -> list[str]:
    family_keywords = _cashflow_note_family_keywords(label)
    if not family_keywords:
        return []
    action_keywords = _cashflow_action_keywords(label)
    candidates: list[tuple[tuple[int, int, tuple[int, ...], int, int], str]] = []
    for section in report.notes:
        for block in section.blocks:
            table = block.table
            if table is None or not getattr(table, "rows", None):
                continue
            if not _scope_compatible(statement_scope, _note_table_scope(table)):
                continue
            heading = _display_note_title(getattr(table, "heading", section.title))
            if not _is_displayable_note_table(heading):
                continue
            heading_compact = _compact(heading)
            if not _is_cashflow_reconciliation_note_heading(heading_compact):
                continue
            if "전기" in heading_compact and "당기" not in heading_compact:
                continue
            heading_has_family = any(keyword in heading_compact for keyword in family_keywords)
            current_columns = set(_current_period_columns(table.rows[0]))
            unit_multiplier = getattr(table, "unit_multiplier", 1)
            for row_idx, row in enumerate(table.rows[1:], start=1):
                row_label = _note_row_label(row)
                row_compact = _compact(row_label)
                context = heading_compact + row_compact
                if not any(keyword in context for keyword in family_keywords):
                    continue
                amount_text = ""
                amount_rank = 1
                for col_idx, cell in enumerate(row[1:], start=1):
                    if current_columns and col_idx not in current_columns:
                        continue
                    raw_amount = parse_amount(cell)
                    if raw_amount is None:
                        continue
                    amount_text = f" · {_note_amount_display(raw_amount * unit_multiplier, table)}"
                    amount_rank = 0
                    break
                action_rank = 0 if any(keyword in row_compact for keyword in action_keywords) else 1
                heading_rank = 0 if heading_has_family else 1
                score = (
                    action_rank,
                    heading_rank,
                    _source_sort_key(f"{section.section_id}/table:{table.index}"),
                    amount_rank,
                    row_idx,
                )
                candidates.append((score, f"{heading} · {row_label}{amount_text}"))
    seen: set[str] = set()
    result: list[str] = []
    for _score, text in sorted(candidates):
        if text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _is_cashflow_reconciliation_note_heading(heading_compact: str) -> bool:
    excluded = (
        "회계정책",
        "재무위험관리",
        "신용위험",
        "시장위험",
        "환위험",
        "유동성위험",
        "자본위험",
        "회사의개요",
        "주주현황",
        "사업의내용",
    )
    return not any(keyword in heading_compact for keyword in excluded)


def _note_row_label(row: list[str]) -> str:
    label_cells = [cell.strip() for cell in row if cell.strip() and parse_amount(cell) is None]
    return " ".join(label_cells) or (row[0].strip() if row else "")


def _cashflow_note_family_keywords(label: str) -> tuple[str, ...]:
    normalized = _compact(label)
    keyword_sets = (
        (("사용권자산",), ("사용권자산", "리스")),
        (("유형자산",), ("유형자산",)),
        (("무형자산",), ("무형자산",)),
        (("정부보조금",), ("정부보조금", "유형자산", "무형자산", "현금흐름")),
        (("투자부동산",), ("투자부동산",)),
        (("투자자산",), ("투자자산", "금융자산", "금융상품")),
        (("매각예정자산",), ("매각예정자산",)),
        (("관계기업",), ("관계기업", "공동기업", "관계기업투자")),
        (("관계기업주식",), ("관계기업", "관계기업투자", "관계기업주식")),
        (("종속기업",), ("종속기업", "종속기업투자")),
        (("단기금융상품",), ("단기금융상품", "금융상품", "금융자산")),
        (("금융상품",), ("금융상품", "금융자산")),
        (("금융자산",), ("금융자산", "금융상품")),
        (("파생상품",), ("파생상품", "통화선도", "금융상품", "금융수익", "금융비용")),
        (("통화선도",), ("통화선도", "파생상품", "금융상품", "금융수익", "금융비용")),
        (("대여금",), ("대여금", "수취채권", "기타채권", "매출채권및기타채권")),
        (("수취채권",), ("수취채권", "기타채권", "매출채권및기타채권", "대여금")),
        (("보증금",), ("보증금", "기타채권", "매출채권및기타채권")),
        (("차입금",), ("차입금", "재무활동부채")),
        (("장기부채",), ("차입금", "장기부채", "재무활동부채")),
        (("공급자금융약정",), ("공급자금융약정", "차입금", "금융부채", "재무활동부채")),
        (("사채",), ("사채", "재무활동부채")),
        (("리스부채",), ("리스부채", "재무활동부채")),
        (("금융부채",), ("금융부채", "재무활동부채")),
        (("이자",), ("이자", "금융수익", "금융비용", "차입금", "사채", "리스부채")),
        (("배당",), ("배당", "이익잉여금", "자본변동")),
        (("자기주식",), ("자기주식", "기타자본구성요소", "자본변동")),
        (("유상증자",), ("유상증자", "자본금", "주식발행초과금", "자본변동")),
        (("주식선택권",), ("주식선택권", "기타자본구성요소", "자본변동")),
        (("비지배지분",), ("비지배지분",)),
        (("신종자본증권",), ("신종자본증권",)),
    )
    for triggers, keywords in keyword_sets:
        if any(trigger in normalized for trigger in triggers):
            return keywords
    return ()


def _cashflow_action_keywords(label: str) -> tuple[str, ...]:
    normalized = _compact(label)
    actions = []
    for keyword in ("취득", "처분", "차입", "상환", "발행", "배당", "회수", "증가", "감소", "납입", "지급"):
        if keyword in normalized:
            actions.append(keyword)
    if "취득" in actions:
        actions.extend(["증가", "매입"])
    if "처분" in actions:
        actions.extend(["감소", "매각"])
    return tuple(actions)


def _cashflow_check_by_statement_source(checks: list[CheckResult]) -> dict[str, CheckResult]:
    by_source: dict[str, CheckResult] = {}
    for check in checks:
        if check.check_type != "cashflow_reconciliation":
            continue
        for evidence in check.evidence:
            if evidence.source.startswith("statement:"):
                by_source[evidence.source] = check
    return by_source


def _cashflow_reference_path(label: str) -> str:
    normalized = _compact(label)
    if "유형자산" in normalized:
        return "유형자산 주석 + 처분손익 주석 + 현금흐름 주석"
    if "무형자산" in normalized:
        return "무형자산 주석 + 처분손익 주석 + 현금흐름 주석"
    if "차입금" in normalized or "사채" in normalized or "리스부채" in normalized:
        return "현금흐름 주석 재무활동부채 조정표"
    if "단기금융상품" in normalized or "금융상품" in normalized or "금융자산" in normalized:
        return _cashflow_note_candidate(label)
    if "파생상품" in normalized or "통화선도" in normalized:
        return "파생상품/범주별 금융상품 주석 + 금융수익 및 금융비용 주석"
    if "대여금" in normalized or "수취채권" in normalized or "보증금" in normalized:
        return "매출채권 및 기타채권 주석 + 특수관계자 자금거래 주석"
    if "매각예정자산" in normalized:
        return "매각예정자산 주석 + 기타수익/비용 주석"
    if "관계기업" in normalized:
        return "관계기업 및 공동기업 투자 주석"
    if "종속기업" in normalized:
        return "종속기업투자/일반사항 주석"
    if (
        "배당" in normalized
        or "비지배지분" in normalized
        or "신종자본증권" in normalized
        or "자기주식" in normalized
        or "유상증자" in normalized
        or "주식선택권" in normalized
    ):
        return "자본변동표 + 자본/배당 주석"
    if "금융부채" in normalized:
        return "기타금융부채 주석 + 재무활동부채 조정표"
    return _cashflow_note_candidate(label)


def _cashflow_operating_adjustment_rows(report: FullReport) -> list[dict[str, str | int]]:
    rows: list[dict[str, str | int]] = []
    for section in report.notes:
        if "현금흐름" not in _compact(section.title):
            continue
        for block in section.blocks:
            table = block.table
            if table is None or not table.rows:
                continue
            heading = _compact(table.heading)
            if not (
                "영업에서창출된현금흐름" in heading
                or "영업활동에서창출된현금흐름" in heading
                or "영업으로부터창출된현금흐름" in heading
                or "영업활동으로부터창출된현금흐름" in heading
            ):
                continue
            for row_idx, row in enumerate(table.rows[1:], start=1):
                if len(row) < 2 or "비현금항목" not in "".join(row):
                    continue
                label = _cashflow_adjustment_label(row)
                if not label or label == "비현금항목의 조정":
                    continue
                amount, col_idx = _cashflow_current_amount(row, table.rows[0])
                if amount is None or col_idx is None:
                    amount, col_idx = _row_amount(row, table.rows[0])
                if amount is None or abs(amount * getattr(table, "unit_multiplier", 1)) < 1_000_000_000:
                    continue
                rows.append(
                    {
                        "label": label,
                        "amount": amount * getattr(table, "unit_multiplier", 1),
                        "reference": _cashflow_adjustment_reference(label),
                        "formula": "당기순이익 + 비현금 조정 ± 운전자본 변동 = 영업에서 창출된 현금흐름",
                    }
                )
            break
        break
    rows.sort(key=lambda row: -abs(int(row["amount"])))
    return rows[:16]


def _cashflow_adjustment_label(row: list[str]) -> str:
    for cell in reversed(row[:-1]):
        if parse_amount(cell) is not None:
            continue
        if cell.strip() and "비현금항목" not in cell and "영업에서창출된현금흐름" not in _compact(cell):
            return cell.strip()
        if cell.strip() and "비현금항목" in cell:
            return cell.replace("비현금항목의 조정", "").strip()
    return ""


def _cashflow_adjustment_reference(label: str) -> str:
    normalized = _compact(label)
    if "법인세" in normalized:
        return "손익계산서 법인세비용 + 법인세비용 주석"
    if "사용권자산" in normalized:
        return "성격별 비용 주석 + 리스/사용권자산 주석"
    if "감가상각비" in normalized:
        return "성격별 비용 주석 + 유형자산 주석"
    if "무형자산상각" in normalized:
        return "성격별 비용 주석 + 무형자산 주석"
    if "이자비용" in normalized or "이자수익" in normalized or "배당금수익" in normalized:
        return "금융수익 및 금융원가 주석"
    if "대손" in normalized:
        return "매출채권/기타채권 손상 주석 + 판매비와관리비"
    if "처분" in normalized or "손상" in normalized:
        return "기타수익 및 기타비용 주석 + 관련 자산/투자 주석"
    if "파생상품" in normalized:
        return "파생상품/금융상품 주석 + 금융수익 및 금융원가 주석"
    if "지분법" in normalized:
        return "관계기업 및 공동기업 투자 주석 + 손익계산서 지분법손익"
    if "퇴직급여" in normalized:
        return "종업원급여/퇴직급여 주석 + 성격별 비용 주석"
    if "외화" in normalized or "환산" in normalized:
        return "금융손익 또는 기타손익 주석"
    return "손익계산서 또는 관련 손익 주석"


def _cashflow_current_amount(row: list[str], headers: list[str]) -> tuple[int | None, int | None]:
    return _amount_from_current_period(row, headers)


def _cashflow_checked_statement_sources(checks: list[CheckResult]) -> set[str]:
    sources: set[str] = set()
    for check in checks:
        if check.check_type != "cashflow_reconciliation":
            continue
        for evidence in check.evidence:
            if evidence.source.startswith("statement:"):
                sources.add(evidence.source)
    return sources


def _is_cashflow_summary_line(label: str) -> bool:
    normalized = _compact(label)
    return (
        "현금흐름" in normalized
        or "현금및현금성자산" in normalized
        or "환율변동효과" in normalized
        or "기초" in normalized
        or "기말" in normalized
        or normalized in {
            "투자활동으로부터의현금유입",
            "투자활동으로부터의현금유출",
            "투자활동으로인한현금유입액",
            "투자활동으로인한현금유출액",
            "재무활동으로부터의현금유입",
            "재무활동으로부터의현금유출",
            "재무활동으로인한현금유입액",
            "재무활동으로인한현금유출액",
        }
    )


def _cashflow_note_candidate(label: str) -> str:
    normalized = _compact(label)
    candidates = (
        (("매각예정자산",), "매각예정자산 주석"),
        (("당기손익", "공정가치", "금융자산"), "범주별 금융상품/공정가치/금융자산 주석"),
        (("정부보조금",), "유형자산/무형자산/현금흐름 관련 정보 주석"),
        (("단기금융상품",), "범주별 금융상품/금융자산 주석"),
        (("금융상품",), "범주별 금융상품 주석"),
        (("기타금융자산",), "기타금융자산/범주별 금융상품 주석"),
        (("기타장기금융자산",), "기타금융자산/범주별 금융상품 주석"),
        (("기타유동금융자산",), "기타금융자산 주석"),
        (("기타비유동금융자산",), "기타금융자산 주석"),
        (("파생상품",), "파생상품/범주별 금융상품 주석"),
        (("통화선도",), "파생상품/금융상품/금융수익비용 주석"),
        (("대여금",), "매출채권 및 기타채권/특수관계자 자금거래 주석"),
        (("수취채권",), "매출채권 및 기타채권 주석"),
        (("보증금",), "매출채권 및 기타채권/기타채권 주석"),
        (("관계기업",), "관계기업 및 공동기업 투자 주석"),
        (("종속기업",), "종속기업투자/일반사항 주석"),
        (("배당",), "자본변동표/이익잉여금/배당 주석"),
        (("자기주식",), "자본변동표/기타자본구성요소 주석"),
        (("유상증자",), "자본변동표/자본금과 주식발행초과금 주석"),
        (("주식선택권",), "자본변동표/기타자본구성요소 주석"),
        (("비지배지분",), "비지배지분 주석"),
        (("신종자본증권",), "신종자본증권 주석"),
        (("기타비유동금융부채",), "기타금융부채/재무활동부채 조정 주석"),
        (("유형자산",), "유형자산 주석"),
        (("무형자산",), "무형자산 주석"),
        (("공급자금융약정",), "공급자금융약정/차입금/금융부채 주석"),
        (("유동성장기부채",), "차입금/재무활동부채 조정 주석"),
        (("차입금",), "재무활동부채 조정 주석"),
        (("사채",), "재무활동부채 조정 주석"),
        (("리스부채",), "재무활동부채 조정 주석"),
        (("이자",), "금융수익 및 금융비용/차입금 주석"),
    )
    for keywords, candidate in candidates:
        if all(keyword in normalized for keyword in keywords):
            return candidate
    return "주석 후보 룰 추가 필요"


def _cashflow_map_status(note_candidate: str, note_review_kind: str) -> str:
    if note_review_kind == "exact":
        return "주석 금액 확인"
    if note_review_kind == "related_no_exact":
        return "차이내역 확인 필요"
    if note_candidate == "주석 후보 룰 추가 필요":
        return "대응 주석 확인 필요"
    return "대응 주석 확인 필요"


def _cashflow_check_status_label(check: CheckResult, note_review_kind: str) -> str:
    audit_status = _check_audit_status_label(check)
    if audit_status == "자동화 보완 필요":
        if note_review_kind in {"exact", "related_no_exact"}:
            return "차이내역 확인 필요"
        return "대응 주석 확인 필요"
    return audit_status


def _cashflow_map_sort_rank(status: str) -> int:
    ranks = {
        "실질 차이 확인 필요": 0,
        "대사 완료": 1,
        "주석 금액 확인": 2,
        "차이내역 확인 필요": 3,
        "대응 주석 확인 필요": 5,
        "자동화 보완 필요": 6,
        "원천 근거 부족": 7,
    }
    return ranks.get(status, 8)


def _cashflow_gap_action(status: str, note_candidate: str) -> str:
    if status == "대사 완료":
        return "현재 현금 변동 대사 섹션에서 검증됩니다."
    if status == "원천 근거 부족":
        return "보고서 원문에서 대응 주석 또는 자본변동표 금액이 충분히 공시됐는지 확인하세요."
    if status == "차이내역 확인 필요":
        return "관련 주석은 확인됐으나 현금흐름표 금액과 직접 일치하지 않습니다. 미수·미지급, 비현금거래, 연결범위 변동 등 차이내역을 확인해야 합니다."
    if status == "대응 주석 확인 필요":
        return "주석 전수 확인 결과 대응 주석 금액이 확인되지 않았습니다. 회사별 표시명 또는 원문 공시 누락 여부를 확인해야 합니다."
    if note_candidate == "주석 후보 룰 추가 필요":
        return "회사별 현금흐름표 표시명을 케이스 라이브러리에 추가하고 대응 주석 family를 정해야 합니다."
    return "후보 주석의 표 제목·행·금액 방향을 수집해 대사 산식 규칙으로 승격해야 합니다."


def _build_reviewer_lens(report: FullReport) -> dict[str, object]:
    metrics = _reviewer_lens_metrics(report)
    movements = _reviewer_lens_movements(metrics)
    signals = _reviewer_lens_signals(metrics)
    hypotheses = _reviewer_lens_hypotheses(metrics)
    questions = _reviewer_lens_questions(signals)
    requests = _reviewer_lens_requests(signals)
    return {
        "verdict": "conditional - 주요 계정 변화 확인 필요" if signals else "normal-with-watchpoints - 자동 신호 제한적",
        "why": _reviewer_lens_why(signals),
        "business_summary": _reviewer_lens_business_summary(report, metrics),
        "movements": movements,
        "signals": signals or ["현재 추출된 주요 계정 기준으로 즉시 강조할 이상 신호는 제한적입니다."],
        "hypotheses": hypotheses,
        "questions": questions,
        "requests": requests,
    }


def _reviewer_lens_why(signals: list[str]) -> str:
    if signals:
        return "주요 계정 변화와 현금흐름 대사 항목에서 후속 확인이 필요한 신호가 추출되었습니다."
    return "현재 추출된 수치만으로는 강한 이상 신호가 제한적이나, 주요 계정별 표준 확인 질문은 유지합니다."


def _reviewer_lens_metrics(report: FullReport) -> dict[str, dict[str, int | None]]:
    labels = {
        "revenue": ("매출액", "영업수익", "수익"),
        "cost_of_sales": ("매출원가",),
        "gross_profit": ("매출총이익", "매출총손익"),
        "sga": ("판매비와관리비", "판매 및 일반관리비"),
        "operating_profit": ("영업이익", "영업손익"),
        "profit_before_tax": ("법인세비용차감전순이익",),
        "profit": ("당기순이익", "당기순손익"),
        "trade_receivables": ("매출채권", "매출채권및기타채권"),
        "inventory": ("재고자산",),
        "ppe": ("유형자산",),
        "operating_cash_flow": ("영업활동현금흐름", "영업활동으로인한현금흐름", "영업활동으로부터의현금흐름"),
    }
    metrics: dict[str, dict[str, int | None]] = {}
    for key, aliases in labels.items():
        metrics[key] = _first_statement_metric(report, aliases)
    return metrics


def _first_statement_metric(report: FullReport, aliases: tuple[str, ...]) -> dict[str, int | None]:
    for section in report.statements:
        for block in section.blocks:
            table = block.table
            if table is None or not table.rows:
                continue
            headers = table.rows[0]
            for row in table.rows[1:]:
                if not row:
                    continue
                normalized = _compact(row[0])
                if not any(_compact(alias) == normalized or _compact(alias) in normalized for alias in aliases):
                    continue
                current = _amount_from_period(row, headers, "current")
                prior = _amount_from_period(row, headers, "prior")
                if current is not None:
                    current *= getattr(table, "unit_multiplier", 1)
                if prior is not None:
                    prior *= getattr(table, "unit_multiplier", 1)
                return {"current": current, "prior": prior}
    return {"current": None, "prior": None}


def _amount_from_period(row: list[str], headers: list[str], period: str) -> int | None:
    if period == "current":
        amount, _ = _amount_from_current_period(row, headers)
    else:
        amount, _ = _amount_from_prior_period(row, headers)
    return amount


def _reviewer_lens_movements(metrics: dict[str, dict[str, int | None]]) -> list[dict[str, object]]:
    labels = [
        ("매출", "revenue"),
        ("매출원가", "cost_of_sales"),
        ("매출총이익", "gross_profit"),
        ("판매비와관리비", "sga"),
        ("매출채권", "trade_receivables"),
        ("재고자산", "inventory"),
        ("유형자산", "ppe"),
        ("영업현금흐름", "operating_cash_flow"),
    ]
    rows: list[dict[str, object]] = []
    for label, key in labels:
        current = metrics.get(key, {}).get("current")
        prior = metrics.get(key, {}).get("prior")
        if current is None and prior is None:
            continue
        rows.append(
            {
                "label": label,
                "current": current,
                "prior": prior,
                "change_html": _change_html(current, prior),
                "meaning": _movement_meaning(label, current, prior),
            }
        )
    return rows


def _change_html(current: int | None, prior: int | None) -> str:
    if current is None or prior in {None, 0}:
        return "-"
    diff = current - prior
    rate = diff / abs(prior) * 100
    return f"{escape(_amount(diff))} {_format_rate_html(rate)}"


def _format_rate_html(rate: float) -> str:
    if rate < 0:
        return f'<span class="negative-rate">({abs(rate):.1f}%)</span>'
    return f"{rate:+.1f}%"


def _movement_meaning(label: str, current: int | None, prior: int | None) -> str:
    if current is None or prior in {None, 0}:
        return "전기 비교 금액이 제한적이어서 추세 판단은 보류합니다."
    rate = (current - prior) / abs(prior) * 100
    if label == "매출채권" and rate > 10:
        return "매출채권 회수조건, 기말 매출 및 후속 입금 확인이 필요합니다."
    if label == "재고자산" and rate > 10:
        return "재고 구성, 장기체화, 순실현가능가치 평가를 확인할 필요가 있습니다."
    if label == "매출총이익" and rate < -10:
        return "마진 하락 원인과 원가 상승분의 판가 전가 여부를 확인할 필요가 있습니다."
    if label == "영업현금흐름" and current < prior:
        return "이익과 현금흐름의 괴리를 운전자본 변동으로 설명할 수 있는지 확인합니다."
    return "전기 대비 변화가 있으므로 관련 주석과 사업 설명의 정합성을 확인합니다."


def _reviewer_lens_signals(metrics: dict[str, dict[str, int | None]]) -> list[str]:
    signals: list[str] = []
    revenue = metrics["revenue"]
    receivables = metrics["trade_receivables"]
    inventory = metrics["inventory"]
    gross_profit = metrics["gross_profit"]
    cfo = metrics["operating_cash_flow"]
    profit = metrics["profit"]
    revenue_growth = _growth(revenue)
    receivable_growth = _growth(receivables)
    inventory_growth = _growth(inventory)
    gross_profit_growth = _growth(gross_profit)
    if revenue_growth is not None and receivable_growth is not None and receivable_growth > revenue_growth + 10:
        signals.append(
            f"매출채권 증가율({_format_rate_html(receivable_growth)})이 매출 증가율({_format_rate_html(revenue_growth)})을 상회합니다."
        )
    if inventory_growth is not None and inventory_growth > 10:
        signals.append(f"재고자산이 전기 대비 {_format_rate_html(inventory_growth)} 변동했습니다.")
    if gross_profit_growth is not None and revenue_growth is not None and gross_profit_growth < revenue_growth - 10:
        signals.append(
            f"매출총이익 증가율({_format_rate_html(gross_profit_growth)})이 매출 증가율({_format_rate_html(revenue_growth)})보다 낮습니다."
        )
    if cfo["current"] is not None and profit["current"] is not None and cfo["current"] < profit["current"] * 0.5:
        signals.append("영업현금흐름이 당기순이익 대비 낮아 운전자본 변동 설명이 필요합니다.")
    if metrics["ppe"]["current"] is not None:
        signals.append("유형자산 규모가 크므로 취득·처분·감가상각비 대사와 손상징후 검토가 중요합니다.")
    return signals[:5]


def _growth(metric: dict[str, int | None]) -> float | None:
    current = metric.get("current")
    prior = metric.get("prior")
    if current is None or prior in {None, 0}:
        return None
    return (current - prior) / abs(prior) * 100


def _reviewer_lens_hypotheses(metrics: dict[str, dict[str, int | None]]) -> list[str]:
    hypotheses: list[str] = []
    revenue_growth = _growth(metrics["revenue"])
    receivable_growth = _growth(metrics["trade_receivables"])
    inventory_growth = _growth(metrics["inventory"])
    gross_profit_growth = _growth(metrics["gross_profit"])
    cfo_growth = _growth(metrics["operating_cash_flow"])
    profit_growth = _growth(metrics["profit"])
    ppe_growth = _growth(metrics["ppe"])

    if revenue_growth is not None and receivable_growth is not None:
        spread = receivable_growth - revenue_growth
        if spread > 5:
            hypotheses.append(
                f"매출은 {_format_rate_html(revenue_growth)} 변동한 반면 매출채권은 {_format_rate_html(receivable_growth)} 변동하여, 회수조건 완화·장기 미회수·기말 매출 후속입금 지연 여부를 질문해야 합니다."
            )
        elif receivable_growth > 0:
            hypotheses.append(
                f"매출채권이 {_format_rate_html(receivable_growth)} 변동했으므로, 증가분이 특정 거래처나 기말 매출에 집중됐는지 확인해야 합니다."
            )
    if inventory_growth is not None:
        if inventory_growth > 0:
            hypotheses.append(
                f"재고자산이 {_format_rate_html(inventory_growth)} 증가했으므로, 원재료·재공품·제품 중 증가 위치와 장기체화/순실현가능가치 평가 근거를 확인해야 합니다."
            )
        elif inventory_growth < -10:
            hypotheses.append(
                f"재고자산이 {_format_rate_html(inventory_growth)} 감소했으므로, 매출 감소와 재고 축소가 물량 감소·재고 처분·평가손 반영 중 무엇으로 설명되는지 확인해야 합니다."
            )
    if gross_profit_growth is not None and revenue_growth is not None:
        spread = gross_profit_growth - revenue_growth
        if spread < -5:
            hypotheses.append(
                f"매출총이익 변동률({_format_rate_html(gross_profit_growth)})이 매출 변동률({_format_rate_html(revenue_growth)})보다 낮아, 원가 상승·운송비/인건비 상승·판가 전가 실패 가능성을 확인해야 합니다."
            )
        elif spread > 5:
            hypotheses.append(
                f"매출총이익 변동률({_format_rate_html(gross_profit_growth)})이 매출 변동률({_format_rate_html(revenue_growth)})보다 높아, 원가 절감·사업믹스 변화·일회성 원가 조정 여부를 확인해야 합니다."
            )
    if cfo_growth is not None:
        hypotheses.append(
            f"영업현금흐름이 {_format_rate_html(cfo_growth)} 변동했으므로, 당기순이익 변화와 운전자본 증감이 같은 방향으로 설명되는지 확인해야 합니다."
        )
    elif metrics["operating_cash_flow"]["current"] is not None and metrics["profit"]["current"] is not None:
        cfo = metrics["operating_cash_flow"]["current"] or 0
        profit = metrics["profit"]["current"] or 0
        if profit and cfo < profit:
            hypotheses.append(
                "영업현금흐름이 당기순이익보다 낮게 표시되어, 매출채권·재고·미지급금 등 운전자본 변동이 손익과 일관되는지 확인해야 합니다."
            )
    if ppe_growth is not None or metrics["ppe"]["current"] is not None:
        movement_text = (
            f"{_format_rate_html(ppe_growth)} 변동했고" if ppe_growth is not None else "중요 계정으로 표시되어"
        )
        hypotheses.append(
            f"유형자산이 {movement_text}, 취득·처분 현금흐름, 감가상각비 기능별 배부, 손상징후 검토의 원천 근거를 확인해야 합니다."
        )
    if profit_growth is not None and profit_growth < -10:
        hypotheses.append(
            f"당기순이익이 {_format_rate_html(profit_growth)} 변동했으므로, 영업손익·금융손익·법인세효과 중 어느 항목이 변동을 주도했는지 확인해야 합니다."
        )
    return hypotheses[:5] or [
        "추출된 주요 계정의 전기 비교 수치가 제한적이므로, 매출·운전자본·유형자산·현금흐름의 원천 표를 우선 확인해야 합니다."
    ]


def _reviewer_lens_questions(signals: list[str]) -> list[str]:
    return [
        "기말 전후 주요 거래처 매출과 후속 입금은 확인했는가?",
        "재고 증가가 원재료, 재공품, 제품 중 어디에서 발생했는가?",
        "원가율 또는 매출총이익 변동의 주요 원인이 가격, 물량, 원재료/운송비 중 무엇인가?",
        "가동률 또는 물류 처리량 하락이 있었고 유휴원가는 손익 처리됐는가?",
        "유형자산 취득·처분 현금흐름 차이에 대한 미지급금, 미수금, 비현금거래 조정 근거가 있는가?",
    ]


def _reviewer_lens_requests(signals: list[str]) -> list[str]:
    return [
        "기말 전후 매출 cut-off 표본 및 후속 입금 내역",
        "매출채권 연령분석, 대손충당금 산정표, 주요 장기 미회수 채권 사유",
        "재고자산 구성별 증감표, 장기체화 리스트, 순실현가능가치 테스트",
        "매출원가 및 판매비와관리비 성격별 비용 분석표",
        "유형자산 취득·처분 상세, 미지급/미수 변동, 감가상각비 기능별 배부 근거",
    ]


def _reviewer_lens_business_summary(report: FullReport, metrics: dict[str, dict[str, int | None]]) -> list[str]:
    nature_terms = _top_expense_nature_terms(report)
    summary = [
        f"{report.company}의 당기 매출은 {_amount(metrics['revenue']['current'])}, 전기 매출은 {_amount(metrics['revenue']['prior'])}입니다.",
        f"매출원가는 {_amount(metrics['cost_of_sales']['current'])}, 판매비와관리비는 {_amount(metrics['sga']['current'])}입니다.",
        f"매출채권은 {_amount(metrics['trade_receivables']['current'])}, 재고자산은 {_amount(metrics['inventory']['current'])}입니다.",
        f"유형자산은 {_amount(metrics['ppe']['current'])}로 취득·처분·감가상각비 검토가 필요한 계정입니다.",
    ]
    if nature_terms:
        summary.append("성격별 비용 주석에서 큰 비용 항목은 " + ", ".join(nature_terms[:4]) + "입니다.")
    summary.append("아래 질문은 확정 결론이 아니라 engagement team에 대한 후속 확인 포인트입니다.")
    return summary


def _top_expense_nature_terms(report: FullReport) -> list[str]:
    rows: list[tuple[int, str]] = []
    for section in report.notes:
        if "비용의 성격별 분류" not in section.title:
            continue
        for block in section.blocks:
            table = block.table
            if table is None or not table.rows:
                continue
            for row in table.rows[1:]:
                if len(row) < 2:
                    continue
                label = next((cell for cell in reversed(row[:-1]) if cell.strip()), row[0])
                if "합계" in label:
                    continue
                amount = parse_amount(row[-1])
                if amount is None:
                    continue
                rows.append((abs(amount) * getattr(table, "unit_multiplier", 1), label))
            if rows:
                break
        if rows:
            break
    rows.sort(reverse=True)
    return [label for _, label in rows[:5]]


def _section_empty_message(section_id: str) -> str:
    messages = {
        "asset-note-bridges": "자산 주석 연결 대사 결과가 없습니다. 현금흐름표와 자산 주석·비현금거래·처분손익 주석이 함께 식별되는 경우 표시됩니다.",
        "note-assertions": "주석별 증감표 검산 결과가 없습니다. 기초·기말과 변동행을 함께 가진 주석 표가 확인되는 범위에서 표시됩니다.",
        "prior": "전기말-당기초 자동 대사 결과가 없습니다. 전기 주석 기말 장부금액과 당기 주석 기초 장부금액의 원천 행 식별이 필요합니다.",
        "supporting": "보조 검증 항목이 없습니다. 합계 행, 비교표, 주석 간 대사는 원천 표 구조가 확인되는 범위에서 추가됩니다.",
    }
    return messages.get(
        section_id,
        "표시할 자동 대사 결과가 없습니다. 필요한 원천 계정 또는 주석 행을 확인하세요.",
    )


def _source_cell(check: CheckResult) -> str:
    if not check.evidence:
        return "-"
    visible = check.evidence[:2]
    items = "".join(
        f"<li><b>{escape(_display_evidence_label(evidence.label))}</b><span>{escape(_display_source_location(evidence.source))}</span></li>"
        for evidence in visible
    )
    hidden = check.evidence[2:]
    if hidden:
        hidden_items = "".join(
            f"<li><b>{escape(_display_evidence_label(evidence.label))}</b><span>{escape(_display_source_location(evidence.source))}</span></li>"
            for evidence in hidden
        )
        return (
            f'<ul class="source-list">{items}</ul>'
            f'<details class="source-more"><summary>근거 {len(hidden)}개 더 보기</summary>'
            f'<ul class="source-list">{hidden_items}</ul></details>'
        )
    return f'<ul class="source-list">{items}</ul>'


def _reason_cell(check: CheckResult) -> str:
    if check.check_type == "cashflow_reconciliation" and ";" in check.reason:
        return _cashflow_formula_html(check.reason)
    return escape(_reason_label(check.reason))


def _review_action_cell(check: CheckResult) -> str:
    action = _review_action(check)
    return _review_action_cell_from_action(check, action)


def _review_action_cell_from_action(check: CheckResult, action: str) -> str:
    if _review_action_uses_formula(check, action):
        return _cashflow_formula_html(action)
    return escape(action)


def _review_action_uses_formula(check: CheckResult, action: str) -> bool:
    return check.check_type == "cashflow_reconciliation" and ";" in action


def _cashflow_formula_html(reason: str) -> str:
    parts = [part.strip() for part in reason.split(";") if part.strip()]
    if not parts:
        return escape(_reason_label(reason))
    labels = ("산식", "대사 대상", "차이", "판정")
    rows = []
    for idx, part in enumerate(parts[:4]):
        label = labels[idx] if idx < len(labels) else "근거"
        part = _formula_part_display(part)
        rows.append(
            f"<tr><td>{escape(label)}</td><td>{escape(part)}</td></tr>"
        )
    return (
        '<div class="formula-box">'
        '<table class="formula-table">'
        "<thead><tr><th>구분</th><th>내용</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
        "</div>"
    )


def _formula_part_display(part: str) -> str:
    normalized = _compact(part)
    if normalized in {"차이0", "잔여차이0"}:
        return "-"
    return part


def _review_action(check: CheckResult) -> str:
    audit_status = _check_audit_status_label(check)
    if check.check_type == "cashflow_reconciliation":
        return _cashflow_review_result(check, audit_status)
    if check.status == "matched":
        return "원천 금액이 허용 차이 이내로 대사 완료됨."
    if check.status == "explainable_gap":
        return f"확인된 조정항목 반영 후에도 잔여 차이 {_amount(check.difference)}가 남아 차이내역 확인이 필요함."
    if audit_status == "실질 차이 확인 필요":
        return f"자동 대사 대상 금액 간 차이 {_amount(check.difference)}가 남아 실질 차이 확인 대상으로 분류됨."
    if audit_status in {"자동화 보완 필요", "차이내역 확인 필요"}:
        return f"현재 추출된 원천 금액만으로는 대사 산식이 완성되지 않음. 잔여 차이 {_amount(check.difference)}."
    if audit_status == "원천 근거 부족":
        return "필요한 주석 표 또는 금액 행이 자동 추출되지 않아 원천 근거 부족으로 분류됨."
    if audit_status == "표 구조 해석 필요":
        return "합계 행, 비교기간 열, 소계 구조가 안정적으로 확정되지 않아 표 구조 해석 필요로 분류됨."
    return "검토 상태와 원천 근거 보완 필요 여부가 남아 있음."


def _cashflow_review_result(check: CheckResult, audit_status: str) -> str:
    parts = [part.strip() for part in check.reason.split(";") if part.strip()]
    formula = parts[0] if parts else ""
    cfs_target = parts[1] if len(parts) > 1 else ""
    difference = _amount(check.difference)
    if check.status == "matched":
        if formula and cfs_target:
            return f"{formula}; {cfs_target}; 차이 {difference}. 현금흐름표와 주석 금액이 대사 완료됨."
        return "현금흐름표와 주석 금액이 대사 완료됨."
    if check.status == "explainable_gap":
        if formula and cfs_target:
            return f"{formula}; {cfs_target}; 잔여 차이 {difference}. 확인된 조정항목 반영 후에도 차이가 남아 차이내역 확인이 필요함."
        return f"확인된 조정항목 반영 후에도 잔여 차이 {difference}가 남아 차이내역 확인이 필요함."
    if audit_status in {"자동화 보완 필요", "차이내역 확인 필요"}:
        if formula and cfs_target:
            return f"{formula}; {cfs_target}; 잔여 차이 {difference}. 현재 추출된 원천 금액만으로는 대사 산식이 완성되지 않음."
        return f"현재 추출된 원천 금액만으로는 대사 산식이 완성되지 않음. 잔여 차이 {difference}."
    return f"현금흐름표-주석 현금 변동 대사 결과: {audit_status}. 잔여 차이 {difference}."


def _overall_verdict(checks: list[CheckResult]) -> tuple[str, str]:
    labels = {_check_audit_status_label(check) for check in checks}
    if "실질 차이 확인 필요" in labels:
        return "실질 차이 확인 필요", "status-risk"
    if labels & {"차이내역 확인 필요", "합계 차이 확인 필요", "자동화 보완 필요", "원천 근거 부족", "표 구조 해석 필요"}:
        return "후속 검토 필요", "status-warning"
    if checks:
        return "대사 완료", "status-ok"
    return "검증 결과 없음", "status-muted"


def _worksheet_cover(
    report: FullReport,
    generated_at: str,
    verdict: tuple[str, str],
) -> str:
    return f"""
      <header class="report-header worksheet-cover" id="summary">
        <div class="cover-main">
          <p class="eyebrow">DART 공시 기반 감사 대사</p>
          <h1>감사 대사 결과 보고서</h1>
          <p class="context">{escape(report.company)} · 보고기간 자동 추정 · DART 공시 원천 · 생성 {escape(generated_at)}</p>
          <span class="status {verdict[1]}">{escape(verdict[0])}</span>
        </div>
        <dl class="signoff" aria-label="조서 작성·검토 기록">
          <div><dt>작성자</dt><dd></dd></div>
          <div><dt>검토자</dt><dd></dd></div>
          <div><dt>작성일</dt><dd></dd></div>
          <div><dt>검토일</dt><dd></dd></div>
        </dl>
      </header>
      {_tickmark_legend()}
"""


def _tickmark_legend() -> str:
    items = [
        ("F", "합계 검증", "표 내부 소계·합계가 구성항목 합계와 일치함"),
        ("R", "재무제표·주석 일치", "본문 계정 금액이 관련 주석 금액과 일치함"),
        ("C", "현금흐름 대사", "현금흐름표 금액이 주석 산식으로 설명됨"),
        ("Φ", "차이 확인 필요", "허용 차이 밖 — 조서 검토 필요"),
        ("N/T", "검증 제외", "원천 근거 부족으로 자동 대사 미수행"),
    ]
    cells = "\n".join(
        f"""<div class="tickmark"><span class="tickmark-mark">{escape(mark)}</span>"""
        f"""<span class="tickmark-label">{escape(label)}</span>"""
        f"""<span class="tickmark-desc">{escape(desc)}</span></div>"""
        for mark, label, desc in items
    )
    return f"""
      <section class="tickmark-legend" aria-label="검산 표기 범례">
        <p class="tickmark-title">검산 표기</p>
        <div class="tickmark-grid">{cells}</div>
      </section>
"""


def _view_tabs() -> str:
    return """
      <div class="view-tabs" role="tablist" aria-label="조서 보기 전환">
        <button type="button" class="view-tab is-active" data-view-tab="working" role="tab" aria-selected="true">감사 대사 결과</button>
        <button type="button" class="view-tab" data-view-tab="review" role="tab" aria-selected="false">리뷰 요약</button>
      </div>
"""


def _section_brief(primary_checks: list[CheckResult], review_checks: list[CheckResult]) -> str:
    total = len(primary_checks)
    matched = sum(1 for check in primary_checks if _check_audit_status_label(check) == "대사 완료")
    review_count = len(review_checks)
    verdict, status_class = _overall_verdict(primary_checks)
    if not total:
        current = "주요 재무제표-주석 대사 항목이 아직 생성되지 않았습니다."
    elif review_count:
        current = f"주요 대사 {total}개 중 {matched}개는 대사 완료, {review_count}개는 후속 확인 대상입니다."
    else:
        current = f"주요 대사 {total}개가 허용 차이 기준 안에서 정리됐습니다."
    why = (
        "대사 완료는 원천 표 위치, 금액 방향, 산식이 함께 확인된 경우에만 표시합니다. "
        "후속 확인 항목은 조서에서 바로 재수행할 수 있도록 원천 근거와 차이를 분리했습니다."
    )
    action = _next_action(review_checks)
    return f"""
      <section class="section-brief" aria-label="검토 브리프">
        <article>
          <h2>현재 상태</h2>
          <span class="status {status_class}">{escape(verdict)}</span>
          <p>{escape(current)}</p>
        </article>
        <article>
          <h2>왜 중요한가</h2>
          <p>{escape(why)}</p>
        </article>
        <article>
          <h2>다음 행동</h2>
          <p>{escape(action)}</p>
        </article>
      </section>
    """


def _next_action(review_checks: list[CheckResult]) -> str:
    labels = Counter(_check_audit_status_label(check) for check in review_checks)
    if labels["실질 차이 확인 필요"]:
        return "실질 차이 확인 필요 항목부터 원천 표를 열어 보고서상 차이인지 확인하세요."
    if labels["차이내역 확인 필요"]:
        return "차이내역 확인 필요 항목은 관련 주석 금액, 비현금거래, 미수·미지급 변동, 연결범위 변동을 순서대로 확인하세요."
    if labels["합계 차이 확인 필요"]:
        return "합계 차이 확인 필요 항목은 주석 표의 소계·합계가 구성항목 합계와 다른지 원문 표에서 확인하세요."
    if labels["자동화 보완 필요"]:
        return "자동화 보완 필요 항목은 회사별 주석 양식과 산식 구성요소를 케이스로 추가하세요."
    if labels["원천 근거 부족"]:
        return "원천 근거 부족 항목은 보고서 내 공시 위치가 있는지 먼저 확인하세요."
    if labels["표 구조 해석 필요"]:
        return "표 구조 해석 필요 항목은 합계 행과 기간 열을 먼저 정리하세요."
    return "모든 자동 대사 항목이 허용 차이 이내입니다. 주요 근거 위치를 조서에 첨부하세요."


def _display_title(check: CheckResult, first_col_label: str) -> str:
    if first_col_label in {"공식 계정", "대상 거래", "대상 비용"}:
        return _target_label(check.title)
    return _human_check_title(check.title)


def _target_label(title: str) -> str:
    labels = {
        "property_plant_equipment.balance": "유형자산",
        "property_plant_equipment.acquisitions_cashflow": "유형자산 취득",
        "property_plant_equipment.disposals_cashflow": "유형자산 처분",
        "intangible_assets.balance": "무형자산",
        "intangible_assets.acquisitions_cashflow": "무형자산 취득",
        "intangible_assets.disposals_cashflow": "무형자산 처분",
        "trade_receivables.balance": "매출채권",
        "property_plant_equipment.depreciation_expense_allocation": "유형자산 감가상각비",
        "intangible_assets.amortization_expense_allocation": "무형자산상각비",
        "lease_liabilities.financing_cashflow": "리스부채 순재무활동현금흐름",
        "borrowings.financing_cashflow": "차입금 순재무활동현금흐름",
        "bonds.financing_cashflow": "사채 순재무활동현금흐름",
    }
    return labels.get(title, _human_check_title(title))


def _human_check_title(title: str) -> str:
    labels = {
        "amortization_expense note to note match": "무형자산상각비 주석 간 대사",
        "tax_temporary_difference note to note match": "이연법인세 일시적 차이 주석 간 대사",
    }
    if title in labels:
        return labels[title]
    if title.endswith(" total check"):
        base = title[: -len(" total check")].strip()
        return f"표 합계 검증: {base}"
    cleaned = title.replace("_", " ").replace(".", " · ")
    cleaned = re.sub(r"\bnote to note match\b", "주석 간 대사", cleaned)
    cleaned = re.sub(r"\btotal check\b", "표 합계 검증", cleaned)
    return cleaned


def _display_evidence_label(label: str) -> str:
    text = label.strip()
    text = re.sub(r"^\s*cfs\s+", "현금흐름표 ", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*bs\s+", "재무상태표 ", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*is\s+", "손익계산서 ", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*note\s+(\d+)", r"주석 \1", text, flags=re.IGNORECASE)
    text = text.replace("_", " ")
    return text


def _display_source_location(source: str) -> str:
    parts = source.split("/")
    if not parts:
        return source
    head = parts[0]
    if head.startswith("statement:"):
        display_parts = [f"재무제표: {head.split(':', 1)[1]}"]
    elif head.startswith("note:"):
        display_parts = [f"주석 {head.split(':', 1)[1]}"]
    else:
        display_parts = [head.replace(":", " ")]
    for part in parts[1:]:
        key, _, value = part.partition(":")
        if key == "table":
            display_parts.append(f"표 {value}")
        elif key == "row":
            display_parts.append(f"행 {value}")
        elif key == "col":
            display_parts.append(f"열 {value}")
        elif part:
            display_parts.append(part.replace(":", " "))
    return " · ".join(display_parts)


def _amount(value: int | None) -> str:
    if value is None:
        return "-"
    if value == 0:
        return "-"
    if value < 0:
        return f"({abs(value):,})"
    return f"{value:,}"


def _audit_status_counts(checks: list[CheckResult]) -> Counter[str]:
    return Counter(_check_audit_status_label(check) for check in checks)


def _check_audit_status_label(check: CheckResult) -> str:
    if check.status == "matched":
        return "대사 완료"
    if check.status == "explainable_gap":
        return "차이내역 확인 필요"
    if check.status == "parse_uncertain":
        return "표 구조 해석 필요"
    if check.status == "not_tested":
        return "자동 검증 제외"
    if check.status == "unexplained_gap":
        if check.check_type == "primary_balance_reconciliation":
            return "실질 차이 확인 필요"
        if check.check_type == "cashflow_reconciliation":
            return "차이내역 확인 필요"
        if check.check_type in {"total_check", "note_note_reconciliation"}:
            return "합계 차이 확인 필요" if check.check_type == "total_check" else "표 구조 해석 필요"
        return "자동화 보완 필요"
    return _status_label(check.status)


def _check_audit_status_class(check: CheckResult) -> str:
    return _audit_status_class(_check_audit_status_label(check))


def _audit_status_class(status: str) -> str:
    classes = {
        "대사 완료": "status-ok",
        "합계 일치": "status-ok",
        "주석 검증 일치": "status-ok",
        "합계 차이 확인 필요": "status-risk",
        "주석 검산 차이 확인 필요": "status-risk",
        "합계 구조 확인 필요": "status-muted",
        "자동화 보완 필요": "status-info",
        "주석 금액 확인": "status-warning",
        "차이내역 확인 필요": "status-warning",
        "대응 주석 확인 필요": "status-risk",
        "원천 근거 부족": "status-muted",
        "실질 차이 확인 필요": "status-risk",
        "표 구조 해석 필요": "status-muted",
        "자동 검증 제외": "status-muted",
        "주석 연결": "status-warning",
        "공식 계정 확인": "status-muted",
        "구조/소계": "status-muted",
        "공식 계정 매핑 필요": "status-risk",
    }
    return classes.get(status, "status-muted")


def _review_priority(status: str) -> int:
    priorities = {
        "실질 차이 확인 필요": 0,
        "차이내역 확인 필요": 1,
        "합계 차이 확인 필요": 1,
        "자동화 보완 필요": 2,
        "원천 근거 부족": 2,
        "표 구조 해석 필요": 3,
        "설명 가능 차이": 4,
    }
    return priorities.get(status, 9)


def _status_label(status: str) -> str:
    labels = {
        "matched": "대사 완료",
        "explainable_gap": "차이내역 확인 필요",
        "unexplained_gap": "자동화 보완 필요",
        "parse_uncertain": "표 구조 해석 필요",
        "not_tested": "자동 검증 제외",
    }
    return labels.get(status, status)


def _status_class(status: str) -> str:
    classes = {
        "matched": "status-ok",
        "explainable_gap": "status-warning",
        "unexplained_gap": "status-info",
        "parse_uncertain": "status-muted",
        "not_tested": "status-muted",
    }
    return classes.get(status, "status-muted")


def _coverage_status_class(status: str) -> str:
    classes = {
        "대사 수행": "status-ok",
        "대사 완료": "status-ok",
        "주석 연결": "status-warning",
        "공식 계정 확인": "status-muted",
        "구조/소계": "status-muted",
        "주석 후보 없음": "status-risk",
        "공식 계정 매핑 필요": "status-risk",
        "자동화 보완 필요": "status-info",
        "차이내역 확인 필요": "status-warning",
        "대응 주석 확인 필요": "status-risk",
        "원천 근거 부족": "status-muted",
        "실질 차이 확인 필요": "status-risk",
        "표 구조 해석 필요": "status-muted",
        "자동 검증 제외": "status-muted",
    }
    return classes.get(status, _audit_status_class(status))


def _is_structural_statement_label(label: str) -> bool:
    normalized = _compact(label)
    structural_labels = {
        "자산",
        "부채",
        "자본",
        "유동자산",
        "비유동자산",
        "자산총계",
        "유동부채",
        "비유동부채",
        "부채총계",
        "자본총계",
        "자본과부채총계",
        "총포괄손익",
        "지배기업소유주지분",
        "지배기업의소유주에게귀속되는자본",
    }
    if normalized in structural_labels:
        return True
    return re.search(r"\d{4}\.\d{2}\.\d{2}.*(?:기초|기말)자본", label) is not None


def _reason_label(reason: str) -> str:
    labels = {
        "financial statement line agrees to note ending balance": "재무제표 계정과 주석 기말 장부금액이 일치함",
        "financial statement line does not agree to note ending balance": "재무제표 계정과 주석 기말 장부금액 간 차이가 있음",
        "cash flow statement line agrees to note cash movement": "현금흐름표 금액 크기와 주석 현금성 변동금액이 일치함",
        "cash flow statement line does not agree to note cash movement": "현금흐름표 금액 크기와 주석 현금성 변동금액 간 차이가 있음",
        "prior-year ending balance agrees to current-year beginning balance": "전기말 주석 금액과 당기초 주석 금액이 일치함",
        "prior-year ending balance does not agree to current-year beginning balance": "전기말 주석 금액과 당기초 주석 금액 간 차이가 있음",
        "financial statement amount agrees to note amount": "재무제표 금액과 주석 금액이 일치함",
        "financial statement amount does not agree to note amount": "재무제표 금액과 주석 금액 간 차이가 있음",
        "cash flow statement amount agrees to note movement": "현금흐름표 항목과 관련 주석 변동금액이 일치함",
        "cash flow statement amount does not agree to note movement": "현금흐름표 항목과 관련 주석 변동금액 간 차이가 있음",
        "current comparative amount agrees to prior current amount": "당기 비교표시 전기금액과 전기 공시 당기금액이 일치함",
        "current comparative amount does not agree to prior current amount": "당기 비교표시 전기금액과 전기 공시 당기금액 간 차이가 있음",
        "no reliable total label found": "합계로 볼 수 있는 행 또는 열 이름을 안정적으로 식별하지 못함",
    }
    return labels.get(reason, reason)


def _js() -> str:
    return """
(() => {
  const scopeTabs = [...document.querySelectorAll("[data-scope-tab]")];
  const scopedItems = [...document.querySelectorAll("[data-report-scope]")];
  const drawer = document.querySelector(".note-drawer");
  const drawerTitle = drawer?.querySelector(".note-drawer-head h2");
  const drawerBody = drawer?.querySelector(".note-drawer-body");
  const closeButton = drawer?.querySelector(".note-drawer-close");
  const triggers = [...document.querySelectorAll(".row-match-trigger")];

  function setScope(scope) {
    if (!scope) return;
    scopeTabs.forEach((tab) => {
      const selected = tab.dataset.scopeTab === scope;
      tab.classList.toggle("is-active", selected);
      tab.setAttribute("aria-selected", selected ? "true" : "false");
    });
    scopedItems.forEach((item) => {
      const itemScope = item.dataset.reportScope || "unknown";
      item.hidden = itemScope !== scope;
    });
    closeDrawer();
  }

  function clearSelection() {
    document.querySelectorAll(".source-table tr.is-selected").forEach((row) => {
      row.classList.remove("is-selected");
    });
  }

  function openDrawer(trigger) {
    if (!drawer || !drawerBody || !drawerTitle) return;
    const note = trigger.querySelector(".hover-note");
    if (!note) return;
    clearSelection();
    trigger.closest("tr")?.classList.add("is-selected");
    const clone = note.cloneNode(true);
    clone.removeAttribute("role");
    drawerBody.replaceChildren(clone);
    const title = clone.querySelector(".hover-note-head strong")?.textContent?.trim();
    drawerTitle.textContent = title || "선택 계정 주석";
    drawer.classList.add("is-open");
    drawer.setAttribute("aria-hidden", "false");
  }

  function closeDrawer() {
    if (!drawer) return;
    drawer.classList.remove("is-open");
    drawer.setAttribute("aria-hidden", "true");
    clearSelection();
  }

  const viewTabs = [...document.querySelectorAll("[data-view-tab]")];
  const viewPanels = [...document.querySelectorAll("[data-view-panel]")];
  function setView(view) {
    if (!view) return;
    viewTabs.forEach((tab) => {
      const selected = tab.dataset.viewTab === view;
      tab.classList.toggle("is-active", selected);
      tab.setAttribute("aria-selected", selected ? "true" : "false");
    });
    viewPanels.forEach((panel) => {
      panel.hidden = panel.dataset.viewPanel !== view;
    });
    closeDrawer();
  }

  triggers.forEach((trigger) => {
    trigger.addEventListener("click", () => openDrawer(trigger));
  });
  scopeTabs.forEach((tab) => {
    tab.addEventListener("click", () => setScope(tab.dataset.scopeTab));
  });
  viewTabs.forEach((tab) => {
    tab.addEventListener("click", () => setView(tab.dataset.viewTab));
  });
  if (viewTabs.length) setView("working");
  if (scopeTabs.length) setScope(scopeTabs[0].dataset.scopeTab);
  closeButton?.addEventListener("click", closeDrawer);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeDrawer();
  });
})();
"""


def _css() -> str:
    return """
:root {
  --bg: #f6f7f8;
  --surface: #ffffff;
  --surface-muted: #eef1f4;
  --line: #d8dde3;
  --line-strong: #b9c1ca;
  --text: #17202a;
  --text-muted: #5f6b78;
  --text-soft: #87919d;
  --accent: #0f766e;
  --accent-soft: #d8f3ee;
  --risk: #b42318;
  --risk-soft: #fee4e2;
  --warn: #b54708;
  --warn-soft: #ffead5;
  --info: #175cd3;
  --info-soft: #d1e9ff;
  --ok: #027a48;
  --ok-soft: #dcfae6;
  --radius: 8px;
  --font: Pretendard, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: var(--font);
  font-size: 14px;
  line-height: 1.6;
  letter-spacing: 0;
}
.report-shell { display: grid; grid-template-columns: 260px minmax(0, 1fr); min-height: 100vh; }
.report-sidebar { position: sticky; top: 0; height: 100vh; padding: 24px 18px; background: var(--surface); border-right: 1px solid var(--line); }
.sidebar-title { font-weight: 800; font-size: 18px; margin-bottom: 22px; }
.report-nav { display: grid; gap: 6px; }
.report-nav a { color: var(--text-muted); text-decoration: none; padding: 8px 10px; border-radius: var(--radius); }
.report-nav a:hover { color: var(--text); background: var(--surface-muted); }
.report-main { max-width: 1180px; padding: 28px 32px 56px; }
.report-header { display: flex; justify-content: space-between; gap: 20px; align-items: flex-start; padding: 8px 0 18px; border-bottom: 1px solid var(--line); }
.worksheet-cover .cover-main { display: flex; flex-direction: column; gap: 8px; align-items: flex-start; }
.signoff { display: grid; grid-template-columns: repeat(2, minmax(140px, 1fr)); gap: 0; margin: 0; border: 1px solid var(--line-strong); border-radius: var(--radius); overflow: hidden; min-width: 300px; }
.signoff > div { display: flex; align-items: stretch; border-top: 1px solid var(--line); }
.signoff > div:nth-child(-n+2) { border-top: none; }
.signoff dt { width: 56px; flex: 0 0 auto; padding: 7px 10px; background: var(--surface-muted); color: var(--text-muted); font-size: 12px; font-weight: 700; border-right: 1px solid var(--line); }
.signoff dd { flex: 1; margin: 0; padding: 7px 10px; min-height: 30px; }
.tickmark-legend { margin-top: 14px; padding: 12px 14px; background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); }
.tickmark-title { margin: 0 0 8px; font-size: 12px; font-weight: 800; color: var(--text-muted); letter-spacing: 0.04em; }
.tickmark-grid { display: flex; flex-wrap: wrap; gap: 8px 18px; }
.tickmark { display: flex; align-items: baseline; gap: 7px; font-size: 12px; }
.tickmark-mark { display: inline-flex; align-items: center; justify-content: center; min-width: 22px; height: 20px; padding: 0 5px; border: 1px solid var(--line-strong); border-radius: 4px; background: var(--surface-muted); font-weight: 800; font-variant-numeric: tabular-nums; }
.tickmark-label { font-weight: 700; color: var(--text); }
.tickmark-desc { color: var(--text-soft); }
.view-tabs { display: flex; gap: 6px; margin: 20px 0 6px; border-bottom: 1px solid var(--line); }
.view-tab { appearance: none; border: 1px solid var(--line); border-bottom: none; background: var(--surface-muted); color: var(--text-muted); font-family: inherit; font-size: 13px; font-weight: 700; padding: 9px 18px; border-radius: 8px 8px 0 0; cursor: pointer; margin-bottom: -1px; }
.view-tab:hover { color: var(--text); }
.view-tab.is-active { background: var(--surface); color: var(--accent); border-color: var(--line); border-bottom: 1px solid var(--surface); }
.view-panel[hidden] { display: none; }
.leadsheet-wrap { overflow-x: auto; margin: 8px 0 10px; }
.leadsheet { width: 100%; border-collapse: collapse; font-size: 13px; }
.leadsheet th, .leadsheet td { border: 1px solid var(--line); padding: 6px 10px; text-align: left; vertical-align: top; }
.leadsheet thead th { background: var(--surface-muted); color: var(--text-muted); font-weight: 700; white-space: nowrap; position: sticky; top: 0; }
.leadsheet td.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.leadsheet td.tick { text-align: center; white-space: nowrap; }
.leadsheet td.note { color: var(--text-muted); max-width: 360px; }
.leadsheet th:nth-child(2), .leadsheet th:nth-child(3), .leadsheet th:nth-child(4), .leadsheet th:nth-child(5) { white-space: nowrap; }
.leadsheet td.related-note-cell { white-space: normal; }
.leadsheet-note-trigger { display: flex; flex-direction: column; width: 100%; align-items: stretch; gap: 6px; }
.leadsheet-note-trigger:hover .leadsheet-note-display { text-decoration: underline; }
.leadsheet-note-display { display: block; color: var(--text); font-weight: 600; white-space: normal; word-break: keep-all; overflow-wrap: anywhere; line-height: 1.4; }
.leadsheet-note-meta { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.self-verify-badge { display: inline-flex; align-items: center; gap: 4px; flex: 0 0 auto; border-radius: 4px; padding: 1px 6px; font-size: 11px; font-weight: 700; line-height: 1.4; border: 1px solid transparent; white-space: nowrap; }
.self-verify-badge.ok { background: rgba(22, 132, 102, 0.12); color: var(--ok); border-color: rgba(22, 132, 102, 0.28); }
.self-verify-badge.warn { background: rgba(193, 96, 28, 0.12); color: var(--warn); border-color: rgba(193, 96, 28, 0.28); }
.self-verify-badge.none { background: var(--surface-muted); color: var(--text-muted); border-color: var(--line); }
.self-verify-line { padding: 4px 0; }
.self-verify-advisory { margin: 8px 0 0; padding: 10px 12px; background: var(--surface-muted); border: 1px solid var(--line); border-radius: var(--radius); font-size: 12px; line-height: 1.6; color: var(--text-muted); }
.self-verify-advisory ul { margin: 6px 0 0; padding-left: 18px; }
.self-verify-advisory li { margin: 4px 0; }
.self-verify-advisory .self-verify-badge { margin: 0 2px; vertical-align: baseline; }
.cashflow-note-evidence { margin-top: 6px; }
.tick-mark { display: inline-flex; align-items: center; justify-content: center; min-width: 24px; height: 20px; padding: 0 5px; border: 1px solid var(--line-strong); border-radius: 4px; background: var(--surface); color: var(--text-soft); font-weight: 800; font-size: 12px; font-variant-numeric: tabular-nums; }
.tick-mark.status-ok { color: var(--ok); border-color: var(--ok); }
.tick-mark.status-risk { color: var(--risk); border-color: var(--risk); }
.tick-mark.status-warning { color: var(--warn); border-color: var(--warn); }
.tick-mark.status-info { color: var(--info); border-color: var(--info); }
.source-table-details { margin-top: 4px; }
.source-table-details > summary { cursor: pointer; color: var(--text-muted); font-size: 12px; padding: 6px 0; }
.source-table-details[open] > summary { color: var(--text); font-weight: 700; }
.eyebrow { margin: 0 0 6px; color: var(--accent); font-weight: 700; font-size: 12px; }
h1 { margin: 0; font-size: 28px; line-height: 1.15; }
.context { margin: 8px 0 0; color: var(--text-muted); }
.status { display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; border: 1px solid var(--line); border-radius: 999px; background: var(--surface); padding: 4px 9px; font-size: 12px; font-weight: 700; }
.status::before { content: ""; width: 7px; height: 7px; flex: 0 0 auto; border-radius: 999px; background: var(--text-soft); }
.status-ok { border-color: var(--ok); color: var(--ok); }
.status-ok::before { background: var(--ok); }
.status-risk { border-color: var(--risk); color: var(--risk); }
.status-risk::before { background: var(--risk); }
.status-warning { border-color: var(--warn); color: var(--warn); }
.status-warning::before { background: var(--warn); }
.status-info { border-color: var(--info); color: var(--info); }
.status-info::before { background: var(--info); }
.status-muted { border-color: var(--line-strong); color: var(--text-muted); }
.status-muted::before { background: var(--text-soft); }
.scope-switcher { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin: 18px 0; padding: 0 0 16px; border-bottom: 1px solid var(--line); }
.scope-switcher h2 { margin: 0; font-size: 16px; line-height: 1.3; }
.scope-tabs { display: inline-flex; gap: 6px; padding: 4px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface-muted); }
.scope-tab { appearance: none; border: 0; border-radius: 6px; background: transparent; color: var(--text-muted); padding: 8px 14px; font: inherit; font-weight: 800; cursor: pointer; }
.scope-tab.is-active { background: var(--surface); color: var(--accent); box-shadow: 0 1px 2px rgba(16, 24, 40, 0.12); }
[hidden] { display: none !important; }
.kpi-strip { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; margin: 16px 0; }
.kpi { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); padding: 14px 16px; min-height: 104px; }
.kpi span, .kpi small { display: block; color: var(--text-muted); }
.kpi strong { display: block; font-size: 28px; line-height: 1.2; margin: 8px 0 4px; font-variant-numeric: tabular-nums; }
.section-brief, .report-section { margin-top: 26px; padding-top: 22px; border-top: 1px solid var(--line); }
.section-brief { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.section-brief article { min-width: 0; border-left: 3px solid var(--accent); padding-left: 12px; }
.section-brief h2, .section-head h2 { margin: 0 0 6px; font-size: 18px; line-height: 1.3; }
.section-brief p, .section-head p { margin: 0; color: var(--text-muted); }
.section-brief .status { margin-bottom: 8px; }
.review-queue-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 14px; }
.review-card { border: 1px solid var(--line); border-radius: var(--radius); padding: 14px 16px; background: #fff; }
.review-card-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; margin-bottom: 10px; }
.review-card-head strong { font-size: 14px; line-height: 1.35; }
.review-card dl { display: grid; gap: 8px; margin: 0; }
.review-card dl > div { display: grid; grid-template-columns: 54px minmax(0, 1fr); gap: 10px; }
.review-card dl > div.review-action-formula { grid-template-columns: 1fr; gap: 6px; }
.review-card .formula-box { min-width: 0; }
.review-card dt { color: var(--text-muted); font-size: 12px; font-weight: 700; }
.review-card dd { margin: 0; }
.lens-flow { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-top: 14px; }
.lens-flow article, .lens-contract article { border: 1px solid var(--line); border-radius: var(--radius); background: #fff; padding: 14px 16px; }
.lens-flow strong, .lens-flow span { display: block; }
.lens-flow strong, .lens-contract strong { font-size: 13px; line-height: 1.35; }
.lens-flow span, .lens-contract p { color: var(--text-muted); margin: 6px 0 0; }
.lens-contract { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 12px; }
.lens-verdict { display: grid; grid-template-columns: 190px minmax(0, 1fr); gap: 12px; align-items: start; margin-top: 12px; padding: 12px 14px; border: 1px solid var(--line); border-left: 3px solid var(--accent); border-radius: var(--radius); background: #fff; }
.lens-verdict strong { font-size: 13px; }
.lens-verdict span { color: var(--text-muted); }
.lens-contract ul { margin: 8px 0 0; padding-left: 18px; }
.lens-contract li { margin: 4px 0; }
.lens-movement-table table { min-width: 980px; }
.formula-box { display: block; min-width: 360px; }
.formula-table { width: 100%; min-width: 100%; max-width: 100%; table-layout: fixed; border-collapse: collapse; font-size: 12px; }
.formula-table th, .formula-table td { position: static; padding: 6px 8px; border: 1px solid var(--line); white-space: normal; vertical-align: top; overflow-wrap: anywhere; text-align: left; }
.formula-table th { background: #f6f8f7; color: var(--text-muted); font-weight: 800; }
.formula-table th:first-child, .formula-table td:first-child { width: 82px; white-space: nowrap; word-break: keep-all; overflow-wrap: normal; }
.formula-table td:first-child { color: var(--text-muted); font-weight: 800; }
.formula-table td:nth-child(2) { word-break: keep-all; overflow-wrap: anywhere; }
.negative-rate { color: var(--risk); font-weight: 800; white-space: nowrap; }
.section-review-summary { display: flex; align-items: flex-start; gap: 10px; margin-top: 12px; padding: 10px 12px; border: 1px solid var(--line); border-left-width: 3px; border-radius: var(--radius); background: #fff; }
.section-review-summary strong { flex: 0 0 auto; font-size: 12px; color: var(--text-muted); }
.section-review-summary span { min-width: 0; }
.status-ok-row { border-left-color: var(--ok); }
.status-warning-row { border-left-color: var(--warn); }
.status-info-row { border-left-color: var(--info); }
.status-risk-row { border-left-color: var(--risk); }
.status-muted-row { border-left-color: var(--text-soft); }
.statement-block { margin-top: 18px; padding-top: 18px; border-top: 1px solid var(--line); }
.statement-block h3 { margin: 0 0 10px; font-size: 16px; line-height: 1.35; }
.source-table-panel { min-width: 0; }
.panel-label { font-size: 12px; font-weight: 800; color: var(--text-muted); margin-bottom: 8px; }
.hover-help { margin: 0 0 10px; color: var(--text-muted); font-size: 13px; }
.source-table-wrap { overflow-x: auto; overflow-y: visible; border: 1px solid var(--line); border-radius: var(--radius); background: #fff; padding-bottom: 8px; }
.source-table { min-width: 0; }
.source-table th, .source-table td { white-space: nowrap; }
.source-table td:first-child, .source-table th:first-child { min-width: 160px; white-space: normal; }
.source-table tr.has-hover-note:hover td, .source-table tr.has-hover-note.is-selected td { background: #f7fbfa; }
.row-match-trigger { appearance: none; position: relative; display: inline-flex; align-items: center; gap: 8px; max-width: 100%; padding: 0; border: 0; background: transparent; color: inherit; font: inherit; text-align: left; cursor: pointer; }
.match-dot { flex: 0 0 auto; border-radius: 999px; padding: 2px 6px; background: var(--accent-soft); color: var(--accent); font-size: 11px; font-weight: 800; }
.hover-note { display: none; white-space: normal; color: var(--text); overflow-wrap: anywhere; }
.hover-note::before { display: none; }
.hover-note-head { display: flex; justify-content: space-between; gap: 8px; align-items: flex-start; padding-bottom: 6px; border-bottom: 1px solid var(--line); }
.hover-note > span:not(.status):not(.hover-note-head):not(.note-match-schema):not(.raw-note-block):not(.judgment-block):not(.self-verify-line) { display: grid; grid-template-columns: 110px minmax(0, 1fr); gap: 8px; min-width: 0; }
.hover-note b { color: var(--text-muted); font-size: 12px; }
.hover-note span.raw-note-block { display: grid; grid-template-columns: 1fr; gap: 6px; padding-top: 8px; border-top: 1px solid var(--line); }
.hover-note span.note-match-schema { display: grid; grid-template-columns: 1fr; gap: 6px; padding-top: 8px; border-top: 1px solid var(--line); }
.hover-note span.judgment-block { display: grid; grid-template-columns: 1fr; gap: 6px; min-width: 0; }
.note-match-table-wrap { display: block; width: 100%; overflow: visible; min-width: 0; border: 1px solid var(--line); border-radius: 6px; }
.note-match-table { display: grid; width: 100%; min-width: 0; grid-template-columns: minmax(0, 3fr) minmax(120px, 1fr) minmax(120px, 1fr); font-size: 12px; }
.note-match-head, .note-match-cell { display: block; min-width: 0; padding: 6px 8px; border-bottom: 1px solid var(--line); border-right: 1px solid var(--line); white-space: normal; overflow-wrap: anywhere; text-align: left; }
.note-match-head { background: #f6f8f7; color: var(--text-muted); font-weight: 700; }
.note-match-num { white-space: nowrap; text-align: right; font-variant-numeric: tabular-nums; }
.raw-note-heading { font-size: 12px; color: var(--text-muted); line-height: 1.45; }
.raw-note-table-wrap { overflow: auto; max-height: 280px; border: 1px solid var(--line); border-radius: 6px; }
.raw-note-table { width: max-content; min-width: 100%; border-collapse: collapse; font-size: 12px; }
.raw-note-table th, .raw-note-table td { position: relative; padding: 6px 8px; border-bottom: 1px solid var(--line); border-right: 1px solid var(--line); white-space: nowrap; text-align: left; }
.raw-note-table th { background: #f6f8f7; color: var(--text-muted); font-weight: 700; }
.note-total-source-list { display: grid; gap: 18px; margin-top: 16px; }
.note-total-note-block { display: grid; gap: 10px; padding-top: 14px; border-top: 1px solid var(--line); }
.note-total-note-block h3 { margin: 0; font-size: 16px; line-height: 1.35; }
.note-total-table-list { display: grid; gap: 10px; }
.note-total-table-card { border: 1px solid var(--line); border-left: 3px solid var(--line-strong); border-radius: var(--radius); background: #fff; overflow: hidden; }
.note-total-table-card.status-risk-row { border-left-color: var(--risk); }
.note-total-table-card.status-muted-row { border-left-color: var(--text-soft); }
.note-total-table-card.status-ok-row { border-left-color: var(--ok); }
.note-total-table-card summary { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; align-items: center; gap: 10px; padding: 10px 12px; cursor: pointer; }
.note-total-table-card summary span:first-child { min-width: 0; overflow-wrap: anywhere; font-weight: 800; }
.note-total-table-card summary small { color: var(--text-muted); white-space: nowrap; }
.note-total-table-card .raw-note-block { display: grid; gap: 6px; padding: 0 12px 12px; }
.note-total-table-card .raw-note-table-wrap { max-height: 460px; }
.total-issue-cell { outline: 2px solid var(--risk); outline-offset: -2px; background: var(--risk-soft); color: var(--risk); font-weight: 800; }
.total-issue-tip { display: none; position: absolute; z-index: 20; left: 8px; top: calc(100% + 4px); width: max-content; max-width: 360px; padding: 8px 10px; border: 1px solid var(--risk); border-radius: 6px; background: #fff; color: var(--text); box-shadow: 0 8px 22px rgba(16, 24, 40, 0.18); white-space: normal; line-height: 1.45; font-weight: 700; }
.total-issue-cell:hover .total-issue-tip { display: block; }
.note-drawer { position: fixed; z-index: 30; top: 0; right: 0; width: min(560px, calc(100vw - 28px)); height: 100vh; display: grid; grid-template-rows: auto minmax(0, 1fr); background: var(--surface); border-left: 1px solid var(--line-strong); box-shadow: -16px 0 34px rgba(16, 24, 40, 0.18); transform: translateX(104%); transition: transform 180ms ease; }
.note-drawer.is-open { transform: translateX(0); }
.note-drawer-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; padding: 18px 18px 14px; border-bottom: 1px solid var(--line); }
.note-drawer-head h2 { margin: 0; font-size: 18px; line-height: 1.25; }
.note-drawer-close { appearance: none; border: 1px solid var(--line); border-radius: 6px; background: #fff; color: var(--text-muted); padding: 6px 9px; font: inherit; cursor: pointer; }
.note-drawer-body { min-width: 0; overflow: auto; padding: 16px 18px 24px; }
.note-drawer .hover-note { display: grid; gap: 10px; }
.note-drawer .hover-note > span:not(.status):not(.hover-note-head):not(.note-match-schema):not(.raw-note-block):not(.judgment-block):not(.self-verify-line) { display: grid; grid-template-columns: 112px minmax(0, 1fr); gap: 8px; min-width: 0; }
.note-drawer .raw-note-table-wrap { max-height: none; }
.note-drawer .raw-note-table { min-width: 100%; }
.term-note { padding: 10px 12px; background: var(--accent-soft); border-left: 3px solid var(--accent); border-radius: 6px; }
.table-wrap { overflow-x: auto; margin-top: 14px; }
table { width: 100%; border-collapse: collapse; min-width: 1280px; }
.cashflow-checks-table { min-width: 1680px; }
.cashflow-checks-table th:nth-child(4), .cashflow-checks-table td:nth-child(4) { min-width: 440px; width: 440px; }
.cashflow-checks-table th:nth-child(7), .cashflow-checks-table td:nth-child(7) { min-width: 280px; }
th, td { padding: 9px 10px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }
th { color: var(--text-muted); font-size: 12px; background: var(--surface-muted); position: sticky; top: 0; }
.check-row { border-left: 3px solid var(--line); }
.table-wrap table th:first-child, .table-wrap table td:first-child { min-width: 136px; white-space: normal; word-break: keep-all; overflow-wrap: normal; }
.table-wrap table th:nth-child(5), .table-wrap table td:nth-child(5) { min-width: 88px; }
.table-wrap table th:nth-child(6), .table-wrap table td:nth-child(6) { min-width: 270px; word-break: keep-all; overflow-wrap: anywhere; }
.table-wrap table th:nth-child(7), .table-wrap table td:nth-child(7) { min-width: 220px; word-break: keep-all; overflow-wrap: anywhere; }
.table-wrap table th:nth-child(8), .table-wrap table td:nth-child(8) { min-width: 250px; }
.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.source { color: var(--text-muted); font-size: 12px; }
.source-list { display: grid; gap: 6px; padding: 0; margin: 0; list-style: none; }
.source-list li { display: grid; gap: 2px; }
.source-list b { color: var(--text-muted); font-weight: 700; }
.source-list span { overflow-wrap: anywhere; }
.source-more { margin-top: 6px; }
.source-more summary { cursor: pointer; color: var(--accent); font-weight: 700; }
.review-action { color: var(--text); font-weight: 600; }
.empty { color: var(--text-muted); text-align: center; padding: 24px; }
.gap-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 12px; }
.gap-grid article { border: 1px solid var(--line); border-radius: var(--radius); padding: 14px; background: var(--surface); }
.gap-grid p { margin: 6px 0 0; color: var(--text-muted); }
.cashflow-gap-panel { margin-bottom: 16px; }
.cashflow-gap-panel h3 { margin: 0 0 6px; font-size: 15px; line-height: 1.35; }
.cashflow-gap-table { min-width: 1180px; }
.cashflow-map-grid { display: grid; gap: 16px; }
.cashflow-map-grid article { min-width: 0; }
.cashflow-map-grid h3 { margin: 0 0 6px; font-size: 15px; line-height: 1.35; }
.cashflow-map-table { min-width: 1840px; }
.cashflow-note-match-list { margin: 0; padding-left: 18px; display: grid; gap: 4px; }
.mini-label { display: block; margin-bottom: 4px; color: var(--text-muted); font-size: 12px; }
.cashflow-operating-map-table { min-width: 1180px; }
.report-footer { color: var(--text-soft); font-size: 12px; margin-top: 24px; }
@media (max-width: 860px) {
  .report-shell { display: block; }
  .report-sidebar { position: sticky; height: auto; z-index: 3; padding: 12px; border-right: 0; border-bottom: 1px solid var(--line); }
  .report-nav { display: flex; gap: 4px; overflow-x: auto; }
  .report-nav a { white-space: nowrap; }
  .report-main { padding: 16px; }
  .report-header { display: grid; }
  .section-brief { grid-template-columns: 1fr; }
  .formula-box { min-width: 0; }
  .kpi-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .review-queue-grid { grid-template-columns: 1fr; }
  .lens-flow, .lens-contract { grid-template-columns: 1fr; }
  .lens-verdict { grid-template-columns: 1fr; }
  .source-table { min-width: 620px; }
  .hover-note > span:not(.status):not(.hover-note-head):not(.note-match-schema):not(.raw-note-block):not(.judgment-block):not(.self-verify-line) { grid-template-columns: 92px minmax(0, 1fr); }
  .note-drawer { top: auto; bottom: 0; width: 100%; height: 76vh; border-left: 0; border-top: 1px solid var(--line-strong); transform: translateY(104%); }
  .note-drawer.is-open { transform: translateY(0); }
  .note-drawer .hover-note > span:not(.status):not(.hover-note-head):not(.note-match-schema):not(.raw-note-block):not(.judgment-block):not(.self-verify-line) { grid-template-columns: 92px minmax(0, 1fr); }
  .note-match-table { grid-template-columns: minmax(0, 2fr) minmax(96px, 1fr) minmax(96px, 1fr); }
  .gap-grid { grid-template-columns: 1fr; }
}
@media print {
  body { background: #fff; }
  .report-shell { display: block; }
  .report-sidebar { display: none; }
  .report-main { max-width: none; padding: 0; }
  .report-header, .section-brief, .report-section { box-shadow: none; break-inside: avoid; }
  .report-section { break-before: page; }
  thead { display: table-header-group; }
}
"""
