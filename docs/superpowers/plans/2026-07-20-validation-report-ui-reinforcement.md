# 검증보고서 UI 전체 보강 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 검증 결과와 원문 근거를 유지하면서 데스크톱 검증보고서의 탐색 문맥, 상태 필터, 우측 드로워, 합계 표시, 넓은 표와 키보드 접근성을 보강한다.

**Architecture:** `report_html.py`의 서버 렌더링 마크업·CSS·독립 JavaScript를 그대로 사용하고, 표시용 helper와 DOM 상태 계약만 확장한다. 검증 엔진과 파서는 변경하지 않으며 독립 HTML과 verify-app은 계속 같은 렌더러 결과를 사용한다.

**Tech Stack:** Python 3.11+, pytest, BeautifulSoup, 독립 HTML/CSS/JavaScript, Playwright CLI 데스크톱 QA.

## Global Constraints

- git 명령을 실행하지 않는다.
- React, Next.js 또는 새 프런트엔드 런타임을 추가하지 않는다.
- 검토 완료, 보류, 메모 저장과 사용자별 검토 이력은 구현하지 않는다.
- Footing과 현금흐름표 대사는 별도 검증으로 유지한다.
- `CheckResult`의 상태, 금액, 허용오차, ID, 유형, 순서와 `CheckEvidence.source`를 변경하지 않는다.
- 합계 테두리는 기존 명시적 검증 대상 셀에만 적용한다.
- 원문 라벨 정리는 표시용 복사본에만 적용하고 이동 대상과 원문 근거는 보존한다.
- 모바일 레이아웃은 완료 기준에 포함하지 않는다.
- 모든 동작 변경은 실패 테스트를 먼저 확인한 뒤 최소 구현으로 통과시킨다.
- 모든 파일 수정은 `apply_patch`로 수행한다.

---

### Task 1: 페이지 전환 문맥과 키보드 진입점 안정화

**Files:**
- Modify: `tests/test_report_html_new.py:240-326`
- Modify: `src/dart_footing_reconciler/report_html.py:441-464`
- Modify: `src/dart_footing_reconciler/report_html.py:546-563`
- Modify: `src/dart_footing_reconciler/report_html.py:671-729`
- Modify: `src/dart_footing_reconciler/report_html.py:2906-2974`
- Modify: `src/dart_footing_reconciler/report_html.py:3172-3326`

**Interfaces:**
- Consumes: 기존 `data-report-scope`, `data-source-panel`, `data-source-jump`, `data-jump-*` 속성.
- Produces: `activatePanel(panelId, options)`, `announceWorkbench(message)`, `.skip-link`, `#workbench-status`, 제목 포커스 계약.

- [ ] **Step 1: 문맥 초기화와 접근성 마크업 실패 테스트 작성**

`tests/test_report_html_new.py`에 다음 테스트를 추가한다.

```python
def test_workbench_navigation_resets_stale_context_and_exposes_skip_link(tmp_path: Path):
    report = FullReport(
        "test.html",
        "회사",
        [
            replace(_section("statement:bs", "재무상태표", "statement", "", 0), scope="consolidated"),
            replace(_section("statement:cf", "현금흐름표", "statement", "", 1), scope="separate"),
        ],
        [],
    )
    output = tmp_path / "report.html"
    export_audit_reconciliation_html(report, [], output)
    content = output.read_text(encoding="utf-8")

    assert '<a class="skip-link" href="#main-content">본문으로 건너뛰기</a>' in content
    assert '<main class="source-stage" id="main-content" tabindex="-1">' in content
    assert 'id="workbench-status" class="sr-only" aria-live="polite"' in content
    assert '<h2 tabindex="-1">재무상태표' in content
    assert "function activatePanel(panelId, options)" in content
    assert "stage.scrollTop = 0;" in content
    assert "if (!settings.preserveDrawer) closeDrawer(false);" in content
    assert "if (settings.focusHeading && heading) heading.focus();" in content
    assert "activatePanel(panelId, {preserveDrawer:true, resetScroll:false, focusHeading:false});" in content
```

- [ ] **Step 2: 실패 확인**

Run:

```bash
uv run pytest -q tests/test_report_html_new.py::test_workbench_navigation_resets_stale_context_and_exposes_skip_link
```

Expected: FAIL because skip link, live region and option-based `activatePanel` do not exist.

- [ ] **Step 3: 본문·제목 접근성 마크업 구현**

`_build_workbench_html(...)`의 `<body>` 직후와 본문에 다음 마크업을 적용한다.

```python
<body data-report-profile="audit-workbench" data-active-report-scope="{_esc(active_scope)}">
<a class="skip-link" href="#main-content">본문으로 건너뛰기</a>
<div id="workbench-status" class="sr-only" aria-live="polite" aria-atomic="true"></div>
{masthead_html}
...
<main class="source-stage" id="main-content" tabindex="-1">
```

`_render_workbench_source_panel(...)`의 제목은 다음처럼 바꾼다.

```python
<h2 tabindex="-1">{_esc(title)}</h2>
```

사이드바 항목의 보이는 말줄임과 전체 이름이 같도록 버튼에 `title`을 추가한다.

```python
f'title="{_esc(label)}" aria-label="{_esc(label)}" '
```

- [ ] **Step 4: 옵션 기반 패널 전환 구현**

기존 `activatePanel`을 다음 계약으로 교체한다.

```javascript
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
  if (!settings.preserveDrawer) closeDrawer(false);
  var stage = document.querySelector('.source-stage');
  if (settings.resetScroll && stage) stage.scrollTop = 0;
  var heading = activePanel && activePanel.querySelector('.source-panel-heading h2');
  if (settings.focusHeading && heading) heading.focus();
  if (heading) announceWorkbench(heading.textContent + ' 원문을 열었습니다.');
}
```

범위 전환은 초기 실행 여부를 받아 최초 로드에서만 제목 포커스를 생략한다.

```javascript
function activateReportScope(scope, options) {
  var settings = Object.assign({initial:false}, options || {});
  document.body.setAttribute('data-active-report-scope', scope);
  document.querySelectorAll('[data-report-scope]').forEach(function(button) {
    button.setAttribute('aria-pressed', button.getAttribute('data-report-scope') === scope ? 'true' : 'false');
  });
  document.querySelectorAll('[data-scope-view]:not([data-drawer-item])').forEach(function(item) {
    item.hidden = item.getAttribute('data-scope-view') !== scope;
  });
  var first = document.querySelector('[data-source-panel][data-scope-view="' + scope + '"]');
  if (first) activatePanel(first.getAttribute('data-source-panel'), {focusHeading:!settings.initial});
  announceWorkbench((scope === 'consolidated' ? '연결' : '별도') + ' 보고서 범위를 선택했습니다.');
}
```

직접 목차 이동은 기본 옵션을 사용하고, 근거 버튼 이동만 다음 옵션을 사용한다.

```javascript
activatePanel(panelId, {preserveDrawer:true, resetScroll:false, focusHeading:false});
```

초기 호출은 다음처럼 바꾼다.

```javascript
activateReportScope(activeReportScope(), {initial:true});
```

- [ ] **Step 5: skip link와 키보드 포커스 스타일 구현**

`_workbench_css()`에 다음 규칙을 추가한다.

```css
.sr-only{position:absolute!important;width:1px!important;height:1px!important;padding:0!important;margin:-1px!important;overflow:hidden!important;clip:rect(0,0,0,0)!important;white-space:nowrap!important;border:0!important;}
.skip-link{position:fixed;left:16px;top:8px;z-index:1000;transform:translateY(-150%);padding:8px 12px;border-radius:5px;background:#fff;color:var(--accent);font-weight:900;box-shadow:0 4px 16px rgba(15,23,42,.2);}
.skip-link:focus{transform:translateY(0);}
button:focus-visible,[tabindex]:focus-visible,a:focus-visible{outline:3px solid #2563eb;outline-offset:2px;}
.source-panel-heading h2:focus{outline:none;}
```

- [ ] **Step 6: Task 1 통과 확인**

Run:

```bash
uv run pytest -q tests/test_report_html_new.py::test_workbench_navigation_resets_stale_context_and_exposes_skip_link tests/test_report_html_new.py::test_mixed_scope_report_renders_one_scope_switch_for_all_workbench_regions
```

Expected: `2 passed`.

---

### Task 2: 상단 현황과 드로워 탐색을 하나의 실제 필터로 통합

**Files:**
- Modify: `tests/test_report_html_cockpit.py:114-134`
- Modify: `tests/test_report_html_new.py:327-350`
- Modify: `tests/test_report_html_new.py:808-833`
- Modify: `src/dart_footing_reconciler/report_html.py:432-438`
- Modify: `src/dart_footing_reconciler/report_html.py:467-522`
- Modify: `src/dart_footing_reconciler/report_html.py:896-991`
- Modify: `src/dart_footing_reconciler/report_html.py:994-1124`
- Modify: `src/dart_footing_reconciler/report_html.py:3172-3326`

**Interfaces:**
- Consumes: `annotations.drawers: tuple[DrawerItem, ...]`, `CheckResult.status`, 활성 보고서 범위.
- Produces: `_drawer_category_for_status(status: str) -> str`, `activeDrawerCategory`, `setDrawerCategory(category, trigger)`, 필터된 `drawerItems()`.

- [ ] **Step 1: 동일 모집단 현황과 세 범주 실패 테스트 작성**

`tests/test_report_html_cockpit.py`의 기존 상단 현황 테스트를 다음 계약으로 교체한다.

```python
def test_report_header_and_drawer_share_one_result_filter_population(tmp_path: Path):
    uncertain = CheckResult(
        "uncertain", "note_reference_check", PARSE_UNCERTAIN, "report", "11",
        "주석 참조 확인", None, None, None, 0, "원문 확인 필요", [],
    )
    content = _render(tmp_path, [_cross_check(), uncertain, _cross_check(MATCHED)])

    assert 'data-result-filter="all">전체 <strong>3</strong>' in content
    assert 'data-result-filter="matched">일치 <strong>1</strong>' in content
    assert 'data-result-filter="attention">확인 필요 <strong>1</strong>' in content
    assert 'data-result-filter="source_review">원문 확인 필요 <strong>1</strong>' in content
    assert 'data-drawer-category="attention"' in content
    assert 'data-drawer-category="source_review"' in content
    assert 'data-drawer-category="matched"' in content
    assert 'data-open-status=' not in content
```

`tests/test_report_html_new.py`에 필터 탐색 계약을 추가한다.

```python
def test_drawer_navigation_uses_active_scope_and_result_filter(tmp_path: Path):
    report = FullReport(
        "test.html", "회사",
        [_section("statement:bs", "재무상태표", "statement", "", 0)], [],
    )
    checks = [
        _result("matched", MATCHED, "statement:bs/table:0/row:1/col:1"),
        _result("gap", UNEXPLAINED_GAP, "statement:bs/table:0/row:1/col:1"),
        _result("uncertain", PARSE_UNCERTAIN, "statement:bs/table:0/row:1/col:1"),
    ]
    output = tmp_path / "report.html"
    export_audit_reconciliation_html(report, checks, output)
    content = output.read_text(encoding="utf-8")

    assert "var activeDrawerCategory = 'all';" in content
    assert "function setDrawerCategory(category, trigger)" in content
    assert "if (activeDrawerCategory === 'all') return true;" in content
    assert "item.getAttribute('data-drawer-category') === activeDrawerCategory" in content
    assert "var items = drawerItems();" in content
    assert "document.querySelectorAll('[data-result-filter]')" in content
```

- [ ] **Step 2: 실패 확인**

Run:

```bash
uv run pytest -q tests/test_report_html_cockpit.py::test_report_header_and_drawer_share_one_result_filter_population tests/test_report_html_new.py::test_drawer_navigation_uses_active_scope_and_result_filter
```

Expected: FAIL because header totals, `source_review`, shared filter and filtered navigation do not exist.

- [ ] **Step 3: 결과 범주 helper와 드로워 데이터 속성 구현**

`report_html.py`에 다음 helper를 추가하고 세 드로워 렌더러에서 사용한다.

```python
def _drawer_category_for_status(status: str) -> str:
    if status == MATCHED:
        return "matched"
    if status in {PARSE_UNCERTAIN, NOT_TESTED}:
        return "source_review"
    return "attention"
```

기존 `"matched" if ... else "attention"`을 모두 다음으로 교체한다.

```python
category = _drawer_category_for_status(check.status)
```

- [ ] **Step 4: 상단 현황을 drawer 모집단 기준으로 렌더링**

`_build_workbench_html(...)`은 `_render_workbench_header`에 `annotations.drawers`를 넘긴다.

```python
masthead_html = _render_workbench_header(
    report, annotations.drawers, meta, render_map,
    available_scopes, active_scope,
)
```

헤더 시그니처와 범위별 집계를 다음 계약으로 변경한다.

```python
def _render_workbench_header(
    report: FullReport,
    drawer_items: tuple[DrawerItem, ...],
    meta: _ReportMeta,
    render_map: _ReportRenderMap,
    available_scopes: tuple[str, ...],
    active_scope: str,
) -> str:
```

```python
scoped_items = [
    item for item in drawer_items
    if _result_scope_slug(report, item.check, render_map, available_scopes) == scope
]
counts = {
    "all": len(scoped_items),
    "matched": sum(_drawer_category_for_status(item.check.status) == "matched" for item in scoped_items),
    "attention": sum(_drawer_category_for_status(item.check.status) == "attention" for item in scoped_items),
    "source_review": sum(_drawer_category_for_status(item.check.status) == "source_review" for item in scoped_items),
}
summary_buttons = "".join(
    f'<button class="status-summary status-{category}" type="button" '
    f'data-result-filter="{category}" aria-pressed="{str(category == "all").lower()}">'
    f'{label} <strong>{counts[category]}</strong></button>'
    for category, label in (
        ("all", "전체"),
        ("matched", "일치"),
        ("attention", "확인 필요"),
        ("source_review", "원문 확인 필요"),
    )
)
```

드로워 필터도 같은 네 개의 `data-result-filter` 버튼을 사용하고 기본값은 `전체`다.

- [ ] **Step 5: 실제 필터 상태와 범주 안 이전/다음 구현**

기존 `syncDrawerFilter`, `drawerItems`, `data-open-status`, `data-drawer-filter` 처리부를 다음 계약으로 교체한다.

```javascript
var activeDrawerCategory = 'all';
function syncResultFilterButtons() {
  document.querySelectorAll('[data-result-filter]').forEach(function(button) {
    button.setAttribute(
      'aria-pressed',
      button.getAttribute('data-result-filter') === activeDrawerCategory ? 'true' : 'false'
    );
  });
}
function drawerItems() {
  return Array.prototype.slice.call(
    document.querySelectorAll('[data-drawer-item][data-scope-view="' + activeReportScope() + '"]')
  ).filter(function(item) {
    if (activeDrawerCategory === 'all') return true;
    return item.getAttribute('data-drawer-category') === activeDrawerCategory;
  });
}
function setDrawerCategory(category, trigger) {
  activeDrawerCategory = category || 'all';
  syncResultFilterButtons();
  var items = drawerItems();
  if (!items.length) {
    closeDrawer(false);
    announceWorkbench('해당 결과가 없습니다.');
    return;
  }
  openDrawer(items[0].getAttribute('data-drawer-item'), trigger);
}
document.querySelectorAll('[data-result-filter]').forEach(function(button) {
  button.addEventListener('click', function() {
    setDrawerCategory(button.getAttribute('data-result-filter'), button);
  });
});
```

직접 행·셀을 눌러 결과를 연 경우 해당 결과의 범주를 활성화한 뒤 `openDrawer`를 실행한다.

```javascript
function syncDrawerCategory(target) {
  activeDrawerCategory = target.getAttribute('data-drawer-category') || 'all';
  syncResultFilterButtons();
}
```

범위 전환에서는 `activeDrawerCategory = 'all'`과 `syncResultFilterButtons()`를 호출한다.

- [ ] **Step 6: Task 2 통과 및 기존 드로워 회귀 확인**

Run:

```bash
uv run pytest -q tests/test_report_html_cockpit.py tests/test_report_html_new.py -k 'header or drawer or scope'
```

Expected: selected tests pass with no old `data-open-status` or `data-drawer-filter` expectation remaining.

---

### Task 3: 드로워를 대상·결과·금액·주석 위치·행동 중심으로 축약

**Files:**
- Modify: `tests/test_report_html_cockpit.py:83-103`
- Modify: `tests/test_report_html_cockpit.py:159-180`
- Modify: `tests/test_report_html_new.py:552-710`
- Modify: `tests/test_report_html_evidence.py:584-623`
- Modify: `src/dart_footing_reconciler/report_html.py:935-1372`
- Modify: `src/dart_footing_reconciler/report_html.py:2962-2971`

**Interfaces:**
- Consumes: `CheckResult`, evidence 역할, `source_cell_ref`, 기존 원문 이동 계약.
- Produces: `_drawer_subject_label(check)`, `_drawer_amount_labels(check)`, `_drawer_note_sources(check)`, `_clean_display_location(value)`, `_statement_note_result_label(check, missing_refs)`.

- [ ] **Step 1: 대상명·출처명·복합결론 실패 테스트 작성**

`tests/test_report_html_new.py::test_cashflow_row_and_drawer_name_the_cashflow_note_validation`에 다음을 추가한다.

```python
assert '<h3>유형자산 취득</h3>' in content
assert '<dt>현금흐름표 금액</dt>' in content
assert '<dt>주석 11 변동금액</dt>' in content
assert '<h4>주석 위치</h4>' in content
assert '<h4>원문 위치</h4>' not in content
assert '>현금흐름표<' not in content.split('<h4>주석 위치</h4>', 1)[1]
```

`tests/test_report_html_new.py::test_statement_note_drawer_explains_comparison_note_roles_and_actions`에 다음을 추가한다.

```python
assert '금액 일치 · 주석번호 확인 필요' in content
assert '<dt>주석 10 금액</dt>' in content
assert '<h4>후속작업</h4>' in content
assert '<h4>원문 위치</h4>' not in content
```

새 일치 테스트를 추가한다.

```python
def test_statement_note_drawer_separates_amount_and_reference_completion(tmp_path: Path):
    report = FullReport(
        "test.html", "회사",
        [_section("statement:bs", "재무상태표", "statement", "", 0)],
        [_section("note:10", "유형자산", "note", "10", 10)],
    )
    check = CheckResult(
        "statement-note-row", "statement_note_row_reconciliation", MATCHED,
        "report", "10", "유형자산 주석 금액 대사", 100, 100, 0, 1,
        "일치",
        [
            CheckEvidence("유형자산", 100, "statement:bs/table:0/row:1/col:1", role="statement_amount"),
            CheckEvidence("본문 표시 주석 10", None, "statement:bs/table:0/row:1/col:0", role="displayed_note_reference"),
            CheckEvidence("주석 10 기말 장부금액", 100, "note:10/table:10/row:1/col:1", role="note_amount"),
        ],
    )
    output = tmp_path / "report.html"
    export_audit_reconciliation_html(report, [check], output)
    content = output.read_text(encoding="utf-8")

    assert '금액 일치 · 주석번호 확인 완료' in content
    assert '추가로 확인할 사항이 없습니다.' in content
```

- [ ] **Step 2: 실패 확인**

Run:

```bash
uv run pytest -q tests/test_report_html_new.py::test_cashflow_row_and_drawer_name_the_cashflow_note_validation tests/test_report_html_new.py::test_statement_note_drawer_explains_comparison_note_roles_and_actions tests/test_report_html_new.py::test_statement_note_drawer_separates_amount_and_reference_completion
```

Expected: FAIL because generic titles, amount labels and combined statement-note conclusions are absent.

- [ ] **Step 3: 대상명과 금액 출처 helper 구현**

`report_html.py`에 다음 helper를 추가한다.

```python
_CASHFLOW_DRAWER_TYPES = {
    "cashflow_reconciliation",
    "cfs_note_match",
    "asset_note_bridge_check",
}

def _drawer_subject_label(check: CheckResult) -> str:
    preferred_roles = ("statement_amount", "cashflow_amount", "target")
    for role in preferred_roles:
        evidence = _first_evidence_for_role(check, role)
        if evidence is not None and evidence.label.strip():
            return re.sub(r"\s+(?:주석 금액 )?대사$", "", evidence_display_label(evidence.label).strip())
    title = check_display_title(check)
    return re.sub(r"\s+(?:주석 금액 )?대사$", "", title).strip() or "검증 결과"

def _drawer_note_number(check: CheckResult) -> str:
    for evidence in check.evidence:
        if source_cell_ref(evidence.source) is not None and evidence.source.startswith("note:"):
            parsed = source_cell_ref(evidence.source)
            if parsed is not None:
                return parsed.name
    return check.note_no

def _drawer_amount_labels(check: CheckResult) -> tuple[str, str]:
    note_no = _drawer_note_number(check)
    note_label = f"주석 {note_no}" if note_no else "주석"
    if check.check_type in _CASHFLOW_DRAWER_TYPES:
        return "현금흐름표 금액", f"{note_label} 변동금액"
    sources = _drawer_evidence_sources(check)
    if any(source.startswith("statement:") for source in sources) and any(
        source.startswith("note:") for source in sources
    ):
        return "재무제표 금액", f"{note_label} 금액"
    return "기준 금액", "비교 금액"
```

`evidence_display_label` import를 기존 `report_frame` import 목록에 추가한다.

- [ ] **Step 4: 표시용 위치 정리와 주석 근거만 선택**

다음 helper를 추가한다.

```python
def _clean_display_location(value: str) -> str:
    parts = [re.sub(r"\s+", " ", part).strip(" ·|") for part in value.split("·")]
    parts = [part for part in parts if part and part != "0"]
    return " · ".join(dict.fromkeys(parts))

def _drawer_note_sources(check: CheckResult) -> tuple[str, ...]:
    sources = []
    for source in _drawer_evidence_sources(check):
        _context, source_body = _split_source_context(source)
        if source_body.startswith("note:") or _parse_narrative_source(source_body) is not None:
            sources.append(source)
    return tuple(sources)
```

`_render_drawer_evidence_location`과 `_render_drawer_source_button`에서 최종 보이는
`human`에만 `_clean_display_location(human)`을 적용한다. source와 `data-jump-*`는
변경하지 않는다.

- [ ] **Step 5: 일반·현금흐름 드로워 정보 구조 구현**

`_render_workbench_drawer_item`의 일반 분기를 다음 순서로 바꾼다.

```python
subject = _drawer_subject_label(check)
expected_label, actual_label = _drawer_amount_labels(check)
note_sources = _drawer_note_sources(check)
locations = "".join(
    _render_drawer_evidence_location(report, check, source, index, render_map)
    for index, source in enumerate(note_sources)
)
if not locations:
    locations = '<span class="drawer-source-unavailable">주석 위치 확인 필요</span>'
```

```python
return f"""<article ...>
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
  <section class="drawer-section"><h4>주석 위치</h4><div class="drawer-sources">{locations}</div></section>
  <section class="drawer-section drawer-next"><h4>필요한 행동</h4><p>{_esc(_next_action_text(check))}</p></section>
</article>"""
```

- [ ] **Step 6: 재무제표-주석 복합결론과 금액명 구현**

다음 helper를 추가한다.

```python
def _statement_note_result_label(check: CheckResult, missing_refs: list) -> str:
    if check.actual is None or check.difference is None:
        amount_label = "금액 확인 필요"
    elif abs(check.difference) <= check.tolerance:
        amount_label = "금액 일치"
    else:
        amount_label = "금액 차이 확인 필요"
    reference_label = "주석번호 확인 필요" if missing_refs else "주석번호 확인 완료"
    return f"{amount_label} · {reference_label}"
```

`_render_statement_note_drawer_item`에서 상태 배지, 두 번째 금액명과 후속작업을 다음처럼 바꾼다.

```python
result_label = _statement_note_result_label(check, missing_refs)
note_amount_label = reconciled if reconciled.startswith("주석 ") else "주석"
note_amount_label = f"{note_amount_label.split(',', 1)[0]} 금액"
next_action_text = (
    "추가로 확인할 사항이 없습니다."
    if check.status == MATCHED and not missing_refs
    else _statement_note_next_action_text(check)
)
```

```python
<span class="drawer-status status-{_esc(check.status)}">{_esc(result_label)}</span>
...
<div><dt>{_esc(note_amount_label)}</dt><dd>{_esc(actual_text)}</dd></div>
...
<section class="drawer-section drawer-next"><h4>후속작업</h4><p>{_esc(next_action_text)}</p></section>
```

`.drawer-status`는 긴 복합 결론이 잘리지 않도록 `max-width`, `white-space:normal`,
`text-align:right`를 적용한다.

- [ ] **Step 7: Task 3 통과 및 시스템 문구 회귀 확인**

Run:

```bash
uv run pytest -q tests/test_report_html_new.py::test_cashflow_row_and_drawer_name_the_cashflow_note_validation tests/test_report_html_new.py::test_statement_note_drawer_explains_comparison_note_roles_and_actions tests/test_report_html_new.py::test_statement_note_drawer_names_unresolved_amount_instead_of_dash tests/test_report_html_new.py::test_statement_note_drawer_separates_amount_and_reference_completion tests/test_report_html_cockpit.py::test_report_hides_internal_metadata_and_runtime_terms
```

Expected: `5 passed`.

---

### Task 4: 합계 미연결 상태와 넓은 표 가독성 보강

**Files:**
- Modify: `tests/test_report_html_new.py:414-503`
- Modify: `tests/test_report_html_cockpit.py:136-157`
- Modify: `src/dart_footing_reconciler/report_html.py:1-40`
- Modify: `src/dart_footing_reconciler/report_html.py:2415-2640`
- Modify: `src/dart_footing_reconciler/report_html.py:2906-2974`
- Modify: `src/dart_footing_reconciler/report_html.py:3172-3326`

**Interfaces:**
- Consumes: `formula_templates.is_subtotal_row_label`, 기존 `CellAnnotation`, 원본 `TableCellLayout`.
- Produces: `_row_has_total_annotation(...)`, `.source-row-total-unchecked`, `.total-result-missing`, `data-horizontal-scroll`, `updateHorizontalScrollCue(container)`.

- [ ] **Step 1: 합계 미연결과 넓은 표 마크업 실패 테스트 작성**

`tests/test_report_html_new.py`에 다음 테스트를 추가한다.

```python
def test_explicit_total_row_distinguishes_missing_validation_from_checked_cell(tmp_path: Path):
    table = ReportTable(
        0,
        [["계정", "당기"], ["현금", "40"], ["자산총계", "40"]],
        "재무상태표",
        SourceLocation("statement:bs", 0, 0),
    )
    statement = ReportSection(
        "statement:bs", "재무상태표", "statement", "",
        [ReportBlock("table", "", table, table.location)],
    )
    report = FullReport("test.html", "회사", [statement], [])
    output = tmp_path / "report.html"
    export_audit_reconciliation_html(report, [], output)
    content = output.read_text(encoding="utf-8")

    assert 'class="source-row source-row-total-unchecked"' in content
    assert '<span class="total-result-missing">검증 결과 없음</span>' in content
    assert 'data-validation-label="합계 검증 일치"' not in content
```

넓은 표 계약 테스트를 추가한다.

```python
def test_wide_source_table_exposes_scroll_cue_and_sticky_description_column(tmp_path: Path):
    table = ReportTable(
        7,
        [["구분", "당기 취득금액", "당기 처분금액", "기말 장부금액 합계"], ["토지", "1", "2", "3"]],
        "유형자산",
        SourceLocation("note:7", 0, 7),
    )
    note = ReportSection("note:7", "유형자산", "note", "7", [ReportBlock("table", "", table, table.location)])
    output = tmp_path / "report.html"
    export_audit_reconciliation_html(FullReport("test.html", "회사", [], [note]), [], output)
    content = output.read_text(encoding="utf-8")

    assert 'class="source-table-scroll" data-horizontal-scroll' in content
    assert '<span class="source-table-scroll-hint">가로로 이동하여 전체 금액 확인</span>' in content
    assert ".source-table th{background:var(--surface-2);font-size:11px;font-weight:800;color:var(--muted);text-align:center;white-space:normal;word-break:keep-all;min-width:96px;}" in content
    assert ".source-table th:first-child,.source-table td:first-child{position:sticky;left:0;" in content
    assert "function updateHorizontalScrollCue(container)" in content
```

- [ ] **Step 2: 실패 확인**

Run:

```bash
uv run pytest -q tests/test_report_html_new.py::test_explicit_total_row_distinguishes_missing_validation_from_checked_cell tests/test_report_html_new.py::test_wide_source_table_exposes_scroll_cue_and_sticky_description_column
```

Expected: FAIL because unchecked total rows and horizontal scroll cues are not rendered.

- [ ] **Step 3: 기존 합계 행 분류를 표시 계층에서 재사용**

상단 import에 다음을 추가한다.

```python
from dart_footing_reconciler.formula_templates import is_subtotal_row_label
```

`_render_source_table.render_row`에서 행 전체에 연결된 셀 검증을 모은 뒤 미연결 합계만 표시한다.

```python
row_annotations = [
    annotation
    for (origin_row, _origin_col), items in annotations_by_origin.items()
    if origin_row == row_index
    for annotation in items
]
is_total_row = bool(row_cells) and is_subtotal_row_label(row_cells[0].text)
is_unchecked_total = is_total_row and not row_annotations and row_index not in header_rows
```

첫 셀 렌더링에 다음을 추가한다.

```python
if is_unchecked_total and cell_index == 0:
    inner += '<span class="total-result-missing">검증 결과 없음</span>'
```

행 클래스에 다음을 추가한다.

```python
if is_unchecked_total:
    row_classes.append("source-row-total-unchecked")
```

이 표시는 검증을 새로 수행하지 않으며 기존 합계 라벨 분류만 재사용한다.

- [ ] **Step 4: 가로 스크롤 힌트와 고정 열 구현**

표 wrapper를 다음처럼 바꾼다.

```python
return (
    '<div class="source-table-scroll" data-horizontal-scroll>'
    '<span class="source-table-scroll-hint">가로로 이동하여 전체 금액 확인</span>'
    f'<table class="{table_class}">'
    f'<thead>{head}</thead><tbody>{body}</tbody>'
    '</table></div>'
)
```

CSS를 다음 계약으로 보강한다.

```css
.source-table-scroll{position:relative;overflow-x:auto;overflow-y:visible;...}
.source-table-scroll::after{content:"";position:sticky;right:0;float:right;width:18px;height:100%;pointer-events:none;background:linear-gradient(90deg,transparent,rgba(15,23,42,.14));}
.source-table-scroll.is-scroll-end::after,.source-table-scroll:not(.is-scrollable)::after{display:none;}
.source-table-scroll-hint{position:sticky;left:12px;display:none;width:max-content;margin:6px 0 0 12px;padding:3px 7px;border-radius:999px;background:#eef3f2;color:var(--muted);font-size:10px;font-weight:800;}
.source-table-scroll.is-scrollable .source-table-scroll-hint{display:inline-flex;}
.source-table th{background:var(--surface-2);font-size:11px;font-weight:800;color:var(--muted);text-align:center;white-space:normal;word-break:keep-all;min-width:96px;}
.source-table th:first-child,.source-table td:first-child{position:sticky;left:0;z-index:2;background:#fff;box-shadow:1px 0 0 var(--border);}
.source-table th:first-child{z-index:4;background:var(--surface-2);}
.source-row-total-unchecked td{background:#fafbfb;}
.total-result-missing{display:inline-flex;margin-left:8px;padding:2px 7px;border:1px dashed var(--uncertain);border-radius:999px;color:var(--muted);font-size:9px;font-weight:900;white-space:nowrap;}
```

JavaScript에 다음을 추가한다.

```javascript
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
```

- [ ] **Step 5: 검증된 합계 셀과 미연결 합계의 상호 배타 회귀 확인**

Run:

```bash
uv run pytest -q tests/test_report_html_new.py::test_explicit_total_row_distinguishes_missing_validation_from_checked_cell tests/test_report_html_new.py::test_wide_source_table_exposes_scroll_cue_and_sticky_description_column tests/test_report_html_new.py::test_last_column_row_total_uses_visible_inset_border_and_audit_label tests/test_report_html_new.py::test_multiple_total_checks_name_validation_count tests/test_report_html_cockpit.py::test_not_tested_result_does_not_mark_a_source_cell
```

Expected: `5 passed`.

---

### Task 5: 렌더러 전체 회귀와 실제 SK이터닉스 데스크톱 QA

**Files:**
- Modify if a regression is found: `src/dart_footing_reconciler/report_html.py`
- Modify if a missing contract is found: `tests/test_report_html_new.py`
- Modify if a missing contract is found: `tests/test_report_html_cockpit.py`
- Modify if a missing contract is found: `tests/test_report_html_evidence.py`
- Regenerate: `output/sk_eternix/sk_eternix_2026_q1_audit_workbench.html`
- Create: `output/playwright/ui-reinforcement-2026-07-20/`

**Interfaces:**
- Consumes: unchanged `dart-footing workpaper-html` CLI and actual SK이터닉스 current/prior disclosure inputs.
- Produces: regenerated standalone report, desktop screenshots, exact verification result record.

- [ ] **Step 1: 렌더러 회귀 테스트 실행**

Run:

```bash
uv run pytest -q tests/test_report_html_new.py tests/test_report_html_cockpit.py tests/test_report_html_evidence.py tests/test_verify_app.py
```

Expected: all tests pass. Any pre-existing external fixture failure is recorded separately and is not counted as a new regression.

- [ ] **Step 2: 정적 품질 검사 실행**

Run:

```bash
uv run ruff check src tests
```

Expected: exit code `0`.

- [ ] **Step 3: 전체 기본 테스트 실행**

Run:

```bash
uv run pytest -q
```

Expected: exit code `0`. Output truncation이 발생하면 로그 파일로 재실행하고 종료코드와 총 건수를 별도로 기록한다.

- [ ] **Step 4: 실제 SK이터닉스 보고서 재생성**

Run:

```bash
uv run dart-footing workpaper-html \
  /Users/kjun/vault/01_Projects/09_dart_footing_reconciler/out/sk_eternix/2026_q1_financial.html \
  output/sk_eternix/sk_eternix_2026_q1_audit_workbench.html \
  --company SK이터닉스 \
  --prior-html /Users/kjun/vault/01_Projects/09_dart_footing_reconciler/out/sk_eternix/2025_annual_financial.html \
  --tolerance 1
```

Expected: output path is written without traceback.

- [ ] **Step 5: 생성 HTML의 사용자 문구와 상태 계약 확인**

Run:

```bash
rg -n 'LOCAL VERIFY|PyOdide|statement_note_row_reconciliation|cashflow_reconciliation|<h4>원문 위치</h4>|>0</button>' output/sk_eternix/sk_eternix_2026_q1_audit_workbench.html
```

Expected: no matches.

Run:

```bash
rg -n '본문으로 건너뛰기|금액 일치 · 주석번호 확인 필요|현금흐름표 금액|주석 [0-9.-]+ 변동금액|검증 결과 없음|가로로 이동하여 전체 금액 확인' output/sk_eternix/sk_eternix_2026_q1_audit_workbench.html
```

Expected: each required user-facing contract appears at least once where the SK이터닉스 data contains that state.

- [ ] **Step 6: 1440×1000 브라우저 흐름 QA**

기존에 승인된 Playwright CLI로 생성 보고서를 열고 다음 흐름을 확인한다.

1. 연결 첫 화면에서 재무상태표 제목이 보이고 중앙 스크롤이 0인지 확인한다.
2. 재무제표 계정 행을 열어 제목, 복합 결론, 세 금액, 초록·빨강 주석 위치와 후속작업을 확인한다.
3. 다른 주석으로 직접 이동해 중앙 상단 복귀와 이전 드로워 닫힘을 확인한다.
4. 드로워 주석 위치로 이동하면 드로워가 유지되고 대상 셀이 강조되는지 확인한다.
5. 현금흐름표 행을 열어 `현금흐름표 금액 / 주석 N 변동금액 / 차이`를 확인한다.
6. `확인 필요` 필터에서 이전/다음이 같은 범주만 순환하는지 확인한다.
7. 별도로 전환해 첫 제목, 상단 건수, 드로워 초기화를 확인한다.
8. 넓은 주석 표의 첫 열 고정, 마지막 열 접근, 스크롤 힌트 종료 상태를 확인한다.
9. 키보드만 사용해 skip link, 목차, 드로워 열기·닫기와 결과 이동을 확인한다.

스크린샷은 다음 파일명으로 저장한다.

```text
output/playwright/ui-reinforcement-2026-07-20/01-statement-top.png
output/playwright/ui-reinforcement-2026-07-20/02-statement-drawer.png
output/playwright/ui-reinforcement-2026-07-20/03-note-context-reset.png
output/playwright/ui-reinforcement-2026-07-20/04-cashflow-drawer.png
output/playwright/ui-reinforcement-2026-07-20/05-filtered-results.png
output/playwright/ui-reinforcement-2026-07-20/06-separate-scope.png
output/playwright/ui-reinforcement-2026-07-20/07-wide-note-table.png
```

- [ ] **Step 7: 변경 전·후 동일 상태 비교**

기존 `output/playwright/ui-audit-2026-07-20/` 화면과 새 화면을 같은 뷰포트·같은 상태로 비교한다. 다음 조건을 모두 만족해야 한다.

- 페이지 전환 후 이전 중앙 스크롤과 드로워가 남지 않는다.
- 드로워 제목이 선택 계정 또는 항목을 먼저 말한다.
- 금액 출처와 필요한 행동이 한 번만 표시된다.
- 검증된 합계와 검증 결과가 없는 합계가 시각적으로 구분된다.
- 마지막 금액 열이 잘리지 않고 첫 설명 열이 유지된다.
- 포커스 테두리, 표 테두리, 배지, 여백이 겹치거나 잘리지 않는다.

- [ ] **Step 8: 후속 백엔드 계획이 구현 범위와 분리됐는지 확인**

Run:

```bash
rg -n '검토 완료|보류|메모|사용자별 검토 상태|백엔드' docs/superpowers/specs/2026-07-20-validation-report-ui-reinforcement-design.md
```

Expected: 해당 내용은 `이번 구현에서 제외`와 `후속 개발계획`에만 존재하며 현재 HTML에 저장 버튼이나 API 호출이 추가되지 않는다.

## 완료 보고 형식

- 구현한 사용자 변화
- 생성 보고서 경로와 대표 화면
- targeted pytest, ruff, 전체 pytest의 정확한 결과와 종료코드
- SK이터닉스 브라우저 QA 통과·미통과 항목
- 기존 실패와 신규 회귀의 분리
- 백엔드 저장 기능이 후속 계획으로만 남았다는 확인
