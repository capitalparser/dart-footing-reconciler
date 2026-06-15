# Evidence-traceability Drilldown Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make verification findings traceable in the evidence_cockpit report — fix orphaned statement-account checks, show per-account verification state (incl. 미검증), humanize source locations with jump+highlight, and show the component-sum math.

**Architecture:** All UI lands in the single renderer `src/dart_footing_reconciler/report_html.py` (the PyOdide offline app reuses `_build_html`, so it inherits everything). Phase 2 adds an optional `role` field to `CheckEvidence` and attaches already-computed components as additive evidence in `checks_totals.py` / `note_assertions.py`. Inline micro-runtime only (no CDN).

**Tech Stack:** Python 3.12 / pytest (`uv run pytest`), ruff, inline HTML+CSS+JS string templates, Playwright (existing E2E), `dart-footing workpaper-corpus` for the regression gate.

**Hard invariant (every task):** verification `status`, `expected`, `actual`, `difference`, per-status counts, and the corpus 5-status histogram are UNCHANGED. Phases 0–1 are render-only; Phase 2 evidence is purely additive. Verify with the status-invariance test (Task 9) + corpus gate.

**Spec:** `docs/superpowers/specs/2026-06-15-evidence-traceability-drilldown-design.md`
**Branch:** `feat/evidence-traceability-drilldown`

---

## File Structure

- `src/dart_footing_reconciler/report_html.py` — renderer. Phase 0 (`_section_key`, `_render_table_rows`, `_render_statement_panel`, `_render_note_panel`), Phase 1 (`_render_drilldown`, `_render_table_rows` cell ids, `_inline_js`), Phase 2 UI (`_render_drilldown` breakdown).
- `src/dart_footing_reconciler/checks.py` — Phase 2: add `CheckEvidence.role: str = ""`.
- `src/dart_footing_reconciler/checks_totals.py` — Phase 2: attach `role="component"` evidence in `_row_total_results`/`_column_total_results`/`_subtotal_results`.
- `src/dart_footing_reconciler/note_assertions.py` — Phase 2: attach beginning/movement/ending component evidence in `_asset_rollforward_results`.
- `tests/test_report_html_new.py` — extend (reuse helpers `_table`, `_stmt_section`, `_note_section`, `_result`).
- `tests/test_report_html_evidence.py` — new (Phase 0.3 + Phase 1/2 render assertions + status-invariance).

Reference helpers already in report_html.py: `_esc`, `_safe_id`, `_find_section`, `_first_table`, `_status_to_badge_class`, `_status_to_badge_label`, `_status_to_row_class`, `_render_drilldown`, `_inline_js`, `_inline_css`.

---

## Phase 0 — Panel correctness & coverage

### Task 1: Normalize statement section key (fix orphaned account checks)

**Files:**
- Modify: `src/dart_footing_reconciler/report_html.py` (`_section_key`, ~line 57)
- Test: `tests/test_report_html_new.py`

- [ ] **Step 1: Write the failing test**

```python
def test_section_key_normalizes_korean_statement_id():
    from dart_footing_reconciler.report_html import _section_key
    r = _result("fsn", MATCHED, "statement:재무상태표/table:0/row:10/col:1")
    assert _section_key(r) == "bs"
    r2 = _result("t", MATCHED, "statement:손익계산서/table:1/row:1/col:1")
    assert _section_key(r2) == "is"
    r3 = _result("t", MATCHED, "statement:bs/table:0/row:1")  # short code still works
    assert _section_key(r3) == "bs"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_report_html_new.py::test_section_key_normalizes_korean_statement_id -q`
Expected: FAIL (`_section_key` returns `"재무상태표"`, not `"bs"`).

- [ ] **Step 3: Implement**

Add the alias map above `_section_key` and apply it:

```python
_STMT_KEY_ALIASES = {
    "재무상태표": "bs", "손익계산서": "is", "포괄손익계산서": "oci",
    "자본변동표": "sce", "현금흐름표": "cf",
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_report_html_new.py::test_section_key_normalizes_korean_statement_id -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/report_html.py tests/test_report_html_new.py
git commit -m "fix(report-html): normalize statement section key so account checks reach the panel"
```

---

### Task 2: Per-account verification state in statement panels (incl. 미검증)

**Files:**
- Modify: `src/dart_footing_reconciler/report_html.py` (`_render_table_rows`, ~line 277; add `_account_state_badge`)
- Test: `tests/test_report_html_evidence.py` (new)

- [ ] **Step 1: Write the failing test**

```python
from dart_footing_reconciler.checks import CheckEvidence, CheckResult, MATCHED, UNEXPLAINED_GAP
from dart_footing_reconciler.document import ReportTable, SourceLocation
from dart_footing_reconciler.report_html import _render_table_rows


def _t(rows):
    return ReportTable(0, rows, "재무상태표", SourceLocation("statement:bs", 0, 0))


def _chk(status):
    return CheckResult("c", "t", status, "report", "", "t", 100, 100, 0, 1, "ok",
                       [CheckEvidence("유형자산", 100, "statement:bs/table:0/row:1/col:1")])


def test_table_rows_show_per_account_state_and_mich_for_uncovered():
    table = _t([["구분", "당기"], ["유형자산", "100"], ["재고자산", "50"], ["자산", ""]])
    html = _render_table_rows(table, {1: _chk(MATCHED)})
    assert "검증완료" in html          # row 1 has a matched check
    assert "미검증" in html            # row 2 (재고자산) has an amount but no check
    # row 3 (자산, group header, no amount) gets no state badge
    assert html.count("acct-state") == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_report_html_evidence.py::test_table_rows_show_per_account_state_and_mich_for_uncovered -q`
Expected: FAIL (no `acct-state` / `미검증` markup yet).

- [ ] **Step 3: Implement**

Add the import at the top of report_html.py (with the other imports):

```python
from dart_footing_reconciler.amounts import parse_amount
```

Add a state-badge helper near `_status_to_badge_label`:

```python
def _account_state_badge(status: str | None) -> str:
    """Per-account verification-state badge for statement line rows.

    status None => 미검증 (no covering check). Render-derived; never a CheckResult.
    """
    if status == MATCHED:
        return '<span class="acct-state as-ok">검증완료</span>'
    if status == UNEXPLAINED_GAP:
        return '<span class="acct-state as-warn">검토필요</span>'
    if status == PARSE_UNCERTAIN:
        return '<span class="acct-state as-unc">파싱불확실</span>'
    return '<span class="acct-state as-nt">미검증</span>'
```

Rewrite `_render_table_rows` to add a leading `검증` column with the state badge (only on rows that have an amount or a check; group/blank rows get an empty state cell):

```python
def _render_table_rows(table: ReportTable, row_map: dict[int, CheckResult], *, id_prefix: str = "dd") -> str:
    html_parts: list[str] = []
    if not table.rows:
        return ""
    header = table.rows[0]
    header_cells = "<th>검증</th>" + "".join(f"<th>{_esc(c)}</th>" for c in header)
    html_parts.append(f"<thead><tr>{header_cells}</tr></thead><tbody>")

    for i, row in enumerate(table.rows[1:], start=1):
        result = row_map.get(i)
        has_amount = any(parse_amount(c) is not None for c in row[1:])
        if result is not None:
            state_cell = f"<td class='state-col'>{_account_state_badge(result.status)}</td>"
        elif has_amount:
            state_cell = f"<td class='state-col'>{_account_state_badge(None)}</td>"
        else:
            state_cell = "<td class='state-col'></td>"
        cells = "".join(f"<td>{_esc(c)}</td>" for c in row)
        if result is None:
            html_parts.append(f"<tr>{state_cell}{cells}</tr>")
        else:
            css_class = _status_to_row_class(result.status)
            dd_id = f"{id_prefix}-{i}"
            html_parts.append(
                f'<tr class="{css_class}" data-check-row="{i}" '
                f'onclick="toggleDD(\'{dd_id}\')">{state_cell}{cells}</tr>'
            )
            html_parts.append(
                f'<tr class="dd-row"><td colspan="{len(row) + 1}" class="dd-cell">'
                f'<div class="dd-inner" id="{dd_id}">{_render_drilldown(result)}</div>'
                f'</td></tr>'
            )
    html_parts.append("</tbody>")
    return "\n".join(html_parts)
```

Add CSS (inside `_inline_css`, append before the closing `</style>`):

```python
.acct-state{font-size:10px;font-weight:700;padding:1px 6px;border-radius:3px;border:1px solid var(--border);white-space:nowrap;}
.as-ok{color:var(--ok);} .as-warn{color:var(--warn);} .as-unc{color:var(--muted);} .as-nt{color:#94a3b8;}
.state-col{width:64px;text-align:center;}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_report_html_evidence.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/report_html.py tests/test_report_html_evidence.py
git commit -m "feat(report-html): per-account verification state (검증완료/검토필요/미검증) in statement panels"
```

---

### Task 3: Strip redundant note-title prefix + Koreanize check titles

**Files:**
- Modify: `src/dart_footing_reconciler/report_html.py` (`_render_note_panel`, ~line 363; add `_display_check_title`)
- Test: `tests/test_report_html_evidence.py`

- [ ] **Step 1: Write the failing test**

```python
from dart_footing_reconciler.report_html import _display_check_title
from dart_footing_reconciler.document import ReportSection


def test_display_check_title_strips_note_prefix_and_koreanizes():
    sec = ReportSection("note:4", "영업부문 (연결)", "note", "4", [])
    title = "4. 영업부문 (연결) 보고부문에 대한 공시 당기 (단위 : 백만원) total check"
    out = _display_check_title(title, sec)
    assert out.startswith("보고부문에 대한 공시")
    assert "4. 영업부문" not in out
    assert "total check" not in out
    assert "합계검증" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_report_html_evidence.py::test_display_check_title_strips_note_prefix_and_koreanizes -q`
Expected: FAIL (`_display_check_title` undefined).

- [ ] **Step 3: Implement**

Add the helper near `_render_note_panel`:

```python
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
```

Use it in `_render_note_panel` (replace `{_esc(result.title)}` in the check-name span):

```python
        title_disp = _display_check_title(result.title, section)
        check_rows += f"""<div class="check-row" onclick="toggleDD('{dd_id}')">
  <span class="expand-tri" id="tri-{dd_id}">▶</span>
  <span class="check-name">{_esc(title_disp)}</span>
  <span class="check-vals"><span>{exp_str}</span><span>{act_str}</span><span>{diff_str}</span></span>
  <span class="badge {badge_class}">{badge_label}</span>
</div>
<div class="dd-inline" id="{dd_id}">{_render_drilldown(result)}</div>"""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_report_html_evidence.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/report_html.py tests/test_report_html_evidence.py
git commit -m "fix(report-html): drop redundant note prefix + Koreanize check titles in note panels"
```

---

## Phase 1 — Humanized source + jump/highlight

### Task 4: Humanize evidence source; move raw string to 기술 세부정보

**Files:**
- Modify: `src/dart_footing_reconciler/report_html.py` (add `_parse_source`, `_humanize_source`; thread `report` into `_render_drilldown`)
- Test: `tests/test_report_html_evidence.py`

- [ ] **Step 1: Write the failing test**

```python
from dart_footing_reconciler.report_html import _humanize_source
from dart_footing_reconciler.document import FullReport, ReportBlock, ReportSection, ReportTable, SourceLocation


def _report_with_note():
    t = ReportTable(28, [["구분", "총장부금액"], ["매출채권 합계", "100"]], "8. 매출채권", SourceLocation("note:8", 0, 28))
    note = ReportSection("note:8", "매출채권 및 기타채권", "note", "8", [ReportBlock("table", "", t, t.location)])
    return FullReport("s.html", "Co", [], [note])


def test_humanize_source_resolves_note_row_and_column():
    report = _report_with_note()
    out = _humanize_source(report, "note:8/table:28/row:1/col:1")
    assert "주석8" in out and "매출채권 합계" in out and "총장부금액" in out
    assert "table:28" not in out  # raw coords not in the human label


def test_humanize_source_falls_back_without_crash():
    report = _report_with_note()
    out = _humanize_source(report, "note:99/table:5/row:3/col:2")
    assert isinstance(out, str) and out  # graceful fallback, no exception
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_report_html_evidence.py -k humanize -q`
Expected: FAIL (`_humanize_source` undefined).

- [ ] **Step 3: Implement**

Add a source parser + humanizer. Build a table index keyed by `"{statement|note prefix}/table:{idx}"`:

```python
def _parse_source(source: str):
    """Return (kind, table_idx, row, col) or None. col may be None."""
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
```

Add the label map near `_STMT_KEY_ALIASES`:

```python
_STMT_KEY_LABELS = {
    "bs": "재무상태표", "재무상태표": "재무상태표", "is": "손익계산서", "손익계산서": "손익계산서",
    "oci": "포괄손익계산서", "포괄손익계산서": "포괄손익계산서", "sce": "자본변동표",
    "자본변동표": "자본변동표", "cf": "현금흐름표", "현금흐름표": "현금흐름표",
}
```

Update `_render_drilldown(result)` → `_render_drilldown(result, report)` and humanize the source column, moving the raw string into a `<details>`:

```python
def _render_drilldown(result: CheckResult, report: FullReport) -> str:
    callout_class = "ok" if result.status == MATCHED else "warn"
    callout_icon = "✓" if result.status == MATCHED else "⚠"
    ev_rows = ""
    raw_rows = ""
    for ev in result.evidence:
        amount_str = f"{ev.amount:,}" if ev.amount is not None else "—"
        human = _humanize_source(report, ev.source)
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
```

Update the two call sites to pass `report`: in `_render_table_rows` (thread `report` param through `_render_statement_panel`/`_render_note_panel`) and `_render_note_panel`. Add `report: FullReport` to `_render_table_rows`, `_render_statement_panel`, `_render_note_panel` signatures and pass it from `_build_html`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_report_html_evidence.py -q && uv run pytest tests/test_report_html_new.py -q`
Expected: PASS (update any call-site test that constructs `_render_drilldown`/`_render_table_rows` directly to pass a `report`/`FullReport(...)`).

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/report_html.py tests/test_report_html_evidence.py
git commit -m "feat(report-html): humanize evidence source; raw coords to 기술 세부정보"
```

---

### Task 5: Source jump + cell highlight (data attributes + inline JS)

**Files:**
- Modify: `src/dart_footing_reconciler/report_html.py` (`_render_table_rows` cell ids, `_render_drilldown` jump controls, `_inline_js`, `_inline_css`)
- Test: `tests/test_report_html_evidence.py`

- [ ] **Step 1: Write the failing test**

```python
def test_drilldown_source_is_clickable_jump_and_cells_have_addresses():
    report = _report_with_note()
    # cells carry addresses
    html = _render_table_rows(report.notes[0].blocks[0].table, {}, report=report, id_prefix="dd")
    assert 'data-cell="r1c1"' in html
    # drilldown source carries a jump target
    from dart_footing_reconciler.checks import CheckResult, CheckEvidence, MATCHED
    r = CheckResult("c", "t", MATCHED, "report", "8", "t", 100, 100, 0, 1, "ok",
                    [CheckEvidence("매출채권 합계", 100, "note:8/table:28/row:1/col:1")])
    dd = _render_drilldown(r, report)
    assert 'data-jump="panel-note-8"' in dd and 'data-jump-cell="r1c1"' in dd
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_report_html_evidence.py -k jump -q`
Expected: FAIL (no `data-cell`/`data-jump` markup).

- [ ] **Step 3: Implement**

In `_render_table_rows`, give each data `<td>` an address (col index aligns with the original table; the leading state cell is col -1, so data cells start at the row's natural column index):

```python
        cells = "".join(
            f'<td data-cell="r{i}c{ci}">{_esc(c)}</td>' for ci, c in enumerate(row)
        )
```

Add `_source_panel_id(scope, name)` and use it in `_render_drilldown` to render each humanized source as a jump control:

```python
def _source_panel_id(scope: str, name: str) -> str:
    if scope == "note":
        return f"panel-note-{name}"
    return f"panel-{_STMT_KEY_ALIASES.get(name, name)}"
```

In `_render_drilldown`, wrap the humanized source in a clickable span when parseable:

```python
        parsed = _parse_source(ev.source)
        if parsed and parsed[3] is not None:
            scope, name, _t, rr, cc = parsed
            cell_key = f"r{rr}c{cc}" if cc is not None else f"r{rr}"
            panel = _source_panel_id(scope, name)
            src_cell = (f'<td class="src-ref"><span class="src-jump" '
                        f'data-jump="{_esc(panel)}" data-jump-cell="{cell_key}" '
                        f'onclick="jumpToCell(this)">{_esc(human)}</span></td>')
        else:
            src_cell = f"<td class='src-ref'>{_esc(human)}</td>"
        ev_rows += f"<tr><td>{_esc(ev.label)}</td><td>{amount_str}</td>{src_cell}</tr>"
```

Extend `_inline_js` (add inside the `<script>`, after `toggleDD`):

```python
function jumpToCell(el){
  var panelId = el.getAttribute('data-jump');
  var cellKey = el.getAttribute('data-jump-cell');
  var nav = document.querySelector('.nav-item[data-target="' + panelId + '"]');
  if(nav){ nav.click(); }
  var panel = document.getElementById(panelId);
  if(!panel) return;
  var cell = panel.querySelector('[data-cell="' + cellKey + '"]')
          || panel.querySelector('[data-check-row="' + cellKey.replace(/c.*/, '').slice(1) + '"]');
  if(cell){
    cell.scrollIntoView({behavior:'smooth', block:'center'});
    cell.classList.add('cell-flash');
    setTimeout(function(){ cell.classList.remove('cell-flash'); }, 1200);
  }
}
```

Add CSS (in `_inline_css`):

```python
.src-jump{color:var(--accent);cursor:pointer;text-decoration:underline dotted;}
.cell-flash{outline:2px solid var(--accent);background:var(--accent-dim);transition:background .3s,outline .3s;}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_report_html_evidence.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/report_html.py tests/test_report_html_evidence.py
git commit -m "feat(report-html): clickable source jump + cell highlight across panels"
```

---

## Phase 2 — Component breakdown (additive evidence)

### Task 6: Add `role` to CheckEvidence

**Files:**
- Modify: `src/dart_footing_reconciler/checks.py` (`CheckEvidence`)
- Test: `tests/test_report_html_evidence.py`

- [ ] **Step 1: Write the failing test**

```python
def test_check_evidence_role_defaults_empty_and_accepts_value():
    from dart_footing_reconciler.checks import CheckEvidence
    assert CheckEvidence("a", 1, "s").role == ""
    assert CheckEvidence("a", 1, "s", role="component").role == "component"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_report_html_evidence.py::test_check_evidence_role_defaults_empty_and_accepts_value -q`
Expected: FAIL (`role` not a field).

- [ ] **Step 3: Implement**

In `checks.py`, extend the dataclass (append after `source`):

```python
@dataclass(frozen=True)
class CheckEvidence:
    label: str
    amount: int | None
    source: str
    role: str = ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_report_html_evidence.py::test_check_evidence_role_defaults_empty_and_accepts_value -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/checks.py tests/test_report_html_evidence.py
git commit -m "feat(checks): add optional role to CheckEvidence (additive)"
```

---

### Task 7: Attach component evidence in footing + rollforward (additive)

**Files:**
- Modify: `src/dart_footing_reconciler/checks_totals.py` (`_column_total_results`; mirror in `_row_total_results`/`_subtotal_results`)
- Modify: `src/dart_footing_reconciler/note_assertions.py` (`_asset_rollforward_results`)
- Test: `tests/test_checks_totals_structure.py`, `tests/test_note_assertions.py`

- [ ] **Step 1: Write the failing test**

```python
def test_column_total_attaches_component_evidence_without_changing_result():
    from dart_footing_reconciler.checks_totals import check_table_totals
    from dart_footing_reconciler.document import ReportTable, SourceLocation
    table = ReportTable(0, [["구분", "당기"], ["유동", "100"], ["비유동", "200"], ["합계", "300"]],
                        "13. 차입금", SourceLocation("note:13", 0, 0))
    results = [r for r in check_table_totals(table, note_no="13", tolerance=0)
               if r.check_type == "total_check"]
    r = next(r for r in results if r.status == "matched")
    comps = [e for e in r.evidence if e.role == "component"]
    assert {e.amount for e in comps} == {100, 200}      # components attached
    assert r.expected == 300 and r.actual == 300 and r.status == "matched"  # result unchanged
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_checks_totals_structure.py::test_column_total_attaches_component_evidence_without_changing_result -q`
Expected: FAIL (no component evidence).

- [ ] **Step 3: Implement**

In `_column_total_results`, build component evidence from the same rows it already sums and pass them into `_result` via the existing `evidence=[...]`. Append after the `expected = sum(...)` line:

```python
        components = [
            CheckEvidence(
                table.rows[ri][0],
                parse_amount(table.rows[ri][col_idx]),
                f"note:{note_no}/table:{table.index}/row:{ri}/col:{col_idx}",
                role="component",
            )
            for ri in range(1, total_row_idx)
            if col_idx < len(table.rows[ri]) and not _is_total_label(table.rows[ri][0])
            and parse_amount(table.rows[ri][col_idx]) is not None
        ]
```

Then in the `evidence=[...]` list passed to `_result(...)`, append `*components` after the existing total `CheckEvidence(...)`. Apply the same pattern (role="component") to the summed rows in `_row_total_results` and `_subtotal_results`.

For `note_assertions._asset_rollforward_results`, give the existing 기초/기말 evidence roles and add movement components. Where the two `CheckEvidence` are built, set `role="beginning"` / `role="ending"`, and inside the movement loop accumulate:

```python
        movement_ev = []
        for row_idx in range(min(beginning_idx, ending_idx) + 1, max(beginning_idx, ending_idx)):
            movement = _amount_at(table, row_idx, col_idx, blank_as_zero=True)
            if movement is None:
                continue
            signed = _movement_amount(table.rows[row_idx][0], movement)
            expected += signed
            movement_ev.append(CheckEvidence(
                f"{table.rows[row_idx][0]} {column_label}", signed,
                f"note:{section.note_no}/table:{table.index}/row:{row_idx}/col:{col_idx}",
                role="movement",
            ))
```

and append `*movement_ev` to the `evidence=[...]` list. (Add `from dart_footing_reconciler.checks import CheckEvidence` if not already imported.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_checks_totals_structure.py tests/test_note_assertions.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/checks_totals.py src/dart_footing_reconciler/note_assertions.py tests/test_checks_totals_structure.py tests/test_note_assertions.py
git commit -m "feat(checks): attach component/movement evidence (additive) for breakdown"
```

---

### Task 8: Render component-sum breakdown in drilldown

**Files:**
- Modify: `src/dart_footing_reconciler/report_html.py` (`_render_drilldown`)
- Test: `tests/test_report_html_evidence.py`

- [ ] **Step 1: Write the failing test**

```python
def test_drilldown_renders_component_breakdown():
    from dart_footing_reconciler.checks import CheckResult, CheckEvidence, UNEXPLAINED_GAP
    report = _report_with_note()
    r = CheckResult("c", "total_check", UNEXPLAINED_GAP, "note", "8", "합계검증", 300, 290, -10, 1, "차이",
                    [CheckEvidence("합계", 290, "note:8/table:28/row:1/col:1", role="total"),
                     CheckEvidence("유동", 100, "note:8/table:28/row:1/col:1", role="component"),
                     CheckEvidence("비유동", 200, "note:8/table:28/row:1/col:1", role="component")])
    dd = _render_drilldown(r, report)
    assert "구성요소 합산" in dd
    assert "기대" in dd and "300" in dd  # sum-of-components line
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_report_html_evidence.py::test_drilldown_renders_component_breakdown -q`
Expected: FAIL (no breakdown section).

- [ ] **Step 3: Implement**

In `_render_drilldown`, when any evidence has `role == "component"`, render a breakdown block before the callout:

```python
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
        breakdown = (
            f'<div class="dd-breakdown"><div class="dd-bd-head">구성요소 합산</div>'
            f'<table class="src-tbl"><tbody>{comp_rows}</tbody></table>'
            f'<div class="dd-bd-sum">기대 = Σ구성요소 {exp_str} · 실제 {act_str} · 차이 '
            f'{(result.difference if result.difference is not None else 0):,}</div></div>'
        )
```

Insert `{breakdown}` into the returned template before the `<div class="callout ...">`. Components are excluded from the operand evidence table by filtering `result.evidence` to `e.role != "component"` in the `ev_rows` loop.

Add CSS:

```python
.dd-breakdown{margin:8px 0;padding:8px;border:1px solid var(--border);border-radius:6px;}
.dd-bd-head{font-size:11px;font-weight:700;color:var(--muted);margin-bottom:4px;}
.dd-bd-sum{font-size:12px;font-weight:700;margin-top:4px;}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_report_html_evidence.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/report_html.py tests/test_report_html_evidence.py
git commit -m "feat(report-html): component-sum breakdown (기대=Σ구성요소) in drilldown"
```

---

### Task 9: Status-invariance + full suite + corpus gate

**Files:**
- Test: `tests/test_report_html_evidence.py`

- [ ] **Step 1: Write the status-invariance test**

```python
def test_evidence_enrichment_does_not_change_status_counts():
    from collections import Counter
    from pathlib import Path
    from dart_footing_reconciler.document import parse_full_report
    from dart_footing_reconciler.check_pipeline import assemble_report_checks
    fx = Path("out/corpus/run_2026-06-06-inveni-one/raw/inveni_2024_20250310000926.html")
    checks = assemble_report_checks(parse_full_report(fx, company="INVENI"), None, tolerance=1)
    counts = Counter(c.status for c in checks)
    # expected/actual/difference must be internally consistent (additive evidence only)
    for c in checks:
        if c.expected is not None and c.actual is not None and c.difference is not None:
            assert c.actual - c.expected == c.difference
    assert sum(counts.values()) == len(checks)
```

- [ ] **Step 2: Run it**

Run: `uv run pytest tests/test_report_html_evidence.py::test_evidence_enrichment_does_not_change_status_counts -q`
Expected: PASS

- [ ] **Step 3: Full suite + ruff**

Run: `uv run pytest -q && uv run ruff check src/dart_footing_reconciler/report_html.py src/dart_footing_reconciler/checks.py src/dart_footing_reconciler/checks_totals.py src/dart_footing_reconciler/note_assertions.py`
Expected: all pass, ruff clean.

- [ ] **Step 4: Corpus gate (status histogram unchanged vs base)**

Run before (base) and after (this branch):
```bash
uv run dart-footing workpaper-corpus out/corpus/manifest_2026-06-10-nonfinancial-industry-10.json /tmp/c_after
python3 -c "import json,glob;s=json.load(open(glob.glob('/tmp/c_after/**/corpus_result.json',recursive=True)[0]))['summary'];print({k:s[k] for k in ['matched','explainable_gap','unexplained_gap','parse_uncertain','not_tested','total_checks']})"
```
Expected: 5-status counts + total_checks IDENTICAL to base (matched 4708 / explainable_gap 10 / unexplained_gap 517 / parse_uncertain 500 / not_tested 2966). Any change = a bug (evidence must be additive).

- [ ] **Step 5: Visual check + commit**

Regenerate the preview and screenshot the drilldown (humanized source + breakdown + per-account state):
```bash
uv run dart-footing workpaper-html "out/corpus/run_2026-06-08-statement-ties-baseline/raw/현대모비스_2024_20250311001180.html" dashboard-preview.html --company "현대모비스"
git add tests/test_report_html_evidence.py
git commit -m "test(report-html): status-invariance gate for evidence enrichment"
```

---

## Self-Review notes
- Spec coverage: Phase 0.1→Task 1, 0.3→Task 2, 0.2→Task 3, Phase 1→Tasks 4–5, Phase 2→Tasks 6–8, invariant→Task 9. All covered.
- The `report` parameter must be threaded through `_render_statement_panel`, `_render_note_panel`, `_render_table_rows`, `_render_drilldown` (Task 4) — existing direct-call tests in `test_report_html_new.py` that call these must be updated to pass a `FullReport`.
- Column alignment: the leading state cell shifts the displayed table by one column; `colspan` for the drilldown row is `len(row) + 1` (Task 2). `data-cell` uses the row's natural column index (Task 5), independent of the state column.
