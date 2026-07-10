# Scope Split Report Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the generated workpaper HTML into independently browsable consolidated and separate report shells.

**Architecture:** Reuse `ReportSection.scope` and render one scope shell per report scope. Common overview panel ids get scope suffixes; statement and note panels keep their existing scope-aware ids. JavaScript switches active scope shells and routes source jumps to the target shell.

**Tech Stack:** Python renderer in `src/dart_footing_reconciler/report_html.py`, pytest tests in `tests/test_report_html_new.py`, browser verification with Playwright CLI.

## Global Constraints

- Keep one generated HTML file.
- Add a top-left report scope switch: `연결보고서`, `별도보고서`.
- Render independent sidebar sections and main panels per scope.
- Preserve source HTML fidelity, total highlights, review rail, and source jumps.
- Do not change parser section scope semantics or deterministic validation status rules.

---

### Task 1: Scope Helpers And Failing Tests

**Files:**
- Modify: `tests/test_report_html_new.py`
- Modify: `src/dart_footing_reconciler/report_html.py`

**Interfaces:**
- Produces: `_report_scope_views(report: FullReport) -> list[_ReportScopeView]`
- Produces: `_filter_results_for_scope(results: list[CheckResult], report: FullReport, scope: str) -> list[CheckResult]`

- [ ] **Step 1: Write failing tests**

Add tests that export a report with consolidated and separate statements/notes, then assert:

```python
assert 'data-report-scope="consolidated"' in content
assert 'data-report-scope="separate"' in content
assert "연결보고서" in content
assert "별도보고서" in content
assert "재무상태표 (연결)" in content
assert "재무상태표 (별도)" in content
```

- [ ] **Step 2: Run the failing tests**

Run: `uv run pytest tests/test_report_html_new.py::test_scope_split_report_shell_renders_consolidated_and_separate_views -q`

Expected: fail because scope shells and switch do not exist.

- [ ] **Step 3: Add helpers**

Add `_ReportScopeView` and helpers in `report_html.py`. Result filtering should infer scope from evidence table sources by looking up the section containing the referenced table.

- [ ] **Step 4: Run helper tests**

Run: `uv run pytest tests/test_report_html_new.py::test_scope_split_report_shell_renders_consolidated_and_separate_views -q`

Expected: progress to render assertions.

### Task 2: Render Independent Scope Shells

**Files:**
- Modify: `src/dart_footing_reconciler/report_html.py`
- Modify: `tests/test_report_html_new.py`

**Interfaces:**
- Consumes: `_report_scope_views`
- Produces: `_render_report_scope_shell(view, meta) -> str`
- Produces: `_render_sidebar_scope_nav(view) -> str`

- [ ] **Step 1: Write failing tests**

Assert common overview panel ids are unique:

```python
ids = re.findall(r'id="([^"]+)"', content)
assert len(ids) == len(set(ids))
assert 'id="panel-summary-con"' in content
assert 'id="panel-summary-sep"' in content
```

- [ ] **Step 2: Implement scoped render**

For reports with both consolidated and separate scopes, render:

```html
<button data-report-scope="consolidated">연결보고서</button>
<button data-report-scope="separate">별도보고서</button>
<nav class="scope-nav" data-report-scope="consolidated">...</nav>
<nav class="scope-nav hidden" data-report-scope="separate">...</nav>
<section class="report-scope-shell" data-report-scope="consolidated">...</section>
<section class="report-scope-shell hidden" data-report-scope="separate">...</section>
```

Keep legacy single-shell rendering when there is only one or no scoped report.

- [ ] **Step 3: Run render tests**

Run: `uv run pytest tests/test_report_html_new.py tests/test_report_html_evidence.py -q`

Expected: pass.

### Task 3: Scope Switching JavaScript And Browser Verification

**Files:**
- Modify: `src/dart_footing_reconciler/report_html.py`
- Modify: `tests/test_report_html_new.py`
- Regenerate: `output/playwright/sk_eternix_reference_check_smoke.html`

**Interfaces:**
- Consumes: `.report-scope-shell[data-report-scope]`
- Produces: `setReportScope(scope, targetPanelId)`

- [ ] **Step 1: Add JS tests**

Assert `_inline_js()` contains:

```python
assert "setReportScope" in js
assert "data-report-scope" in js
assert "closest('.report-scope-shell')" in js
```

- [ ] **Step 2: Implement JS**

Switch active scope buttons, sidebar navs, and main shells. Update `jumpToPanel(panelId)` to activate the target panel's scope before scrolling.

- [ ] **Step 3: Regenerate SK Eternix HTML**

Run:

```bash
uv run dart-footing workpaper-html out/sk_eternix/2025_annual_financial.html output/playwright/sk_eternix_reference_check_smoke.html --company SK이터닉스 --tolerance 1
```

- [ ] **Step 4: Browser verify**

Run Playwright against a local HTTP server and assert:

```js
{
  consolidatedVisible: true,
  separateVisibleAfterClick: true,
  consolidatedLabelsHiddenInSeparate: true,
  duplicateIdCount: 0
}
```

### Task 4: Full Verification

**Files:**
- Modify: none

- [ ] **Step 1: Run lint**

Run: `uv run ruff check .`

Expected: `All checks passed!`

- [ ] **Step 2: Run all tests**

Run: `uv run pytest -q`

Expected: all tests pass with one skipped test allowed.
