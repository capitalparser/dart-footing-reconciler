# Note Workspace And Statement Parser Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make INVENI-style reports show all primary statements and expose note text/tables in a selectable note workspace with direct comparison context.

**Architecture:** Keep parsing and report rendering separate. Extend `document.py` so standalone statement headings start a new statement section even after a previous statement has blocks. Extend `report_html.py` working view with a note workspace that renders note text blocks, note tables, and grouped checks while preserving the report-order sections.

**Tech Stack:** Python dataclasses, BeautifulSoup/lxml parser, HTML/CSS/vanilla JS report renderer, pytest.

---

### Task 1: Statement Heading Continuation Parser

**Files:**
- Modify: `src/dart_footing_reconciler/document.py`
- Test: `tests/test_document.py`

- [ ] Add a failing parser test with `재무상태표`, then standalone `포괄손익계산서`, `자본변동표`, `현금흐름표` headings after populated tables.
- [ ] Run `uv run pytest tests/test_document.py::test_parse_full_report_starts_new_statement_after_populated_statement_heading -q`; expect failure with only one parsed statement.
- [ ] Update inline statement heading handling to allow explicit standalone statement headings in the non-note area after an existing statement.
- [ ] Re-run the targeted test and existing document tests.

### Task 2: Note Text Rendering

**Files:**
- Modify: `src/dart_footing_reconciler/report_html.py`
- Test: `tests/test_cli_workpaper.py`

- [ ] Add a failing HTML test where a note has text blocks and a table; assert the note workspace renders both text and table.
- [ ] Run the targeted test and verify it fails because note text is absent.
- [ ] Render note text blocks in the notes section without changing `FullReport` or CLI contracts.
- [ ] Re-run the targeted test.

### Task 3: Selectable Note Workspace

**Files:**
- Modify: `src/dart_footing_reconciler/report_html.py`
- Test: `tests/test_cli_workpaper.py`

- [ ] Add a failing HTML test for a note navigator item, a note workspace panel, and comparison blocks for 재무상태표, 손익계산서, 자본변동표, 현금흐름표, 다른 주석.
- [ ] Run the targeted test and verify it fails.
- [ ] Add a compact note workspace: left note list/search-style buttons and right note detail panels; show note text, raw tables, and grouped checks.
- [ ] Add small JS to switch active note panels.
- [ ] Re-run the targeted test.

### Task 4: INVENI Regression And Visual Verification

**Files:**
- Modify tests only if a regression assertion needs exact wording.
- Generated ignored output: `out/corpus/run_2026-06-06-inveni-one/reports/inveni_2024.html`

- [ ] Run `uv run pytest`.
- [ ] Regenerate INVENI with `uv run dart-footing workpaper-corpus out/corpus/manifest_2026-06-06-inveni-one.json out/corpus/run_2026-06-06-inveni-one --tolerance 1`.
- [ ] Verify parsed statements include 재무상태표, 포괄손익계산서, 자본변동표, 현금흐름표.
- [ ] Use Playwright to screenshot the report order and note workspace.
