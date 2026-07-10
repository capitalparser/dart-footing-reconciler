# Validation Coverage QA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an automatic QA gate that verifies whether required validation families ran and carried evidence, without treating ordinary `확인필요` business results as QA failures.

**Architecture:** Add a focused `report_qa.py` layer that consumes `FullReport` and `CheckResult[]` after `assemble_report_checks()`. Render its findings in the HTML report and expose the same QA summary from CLI so “보고서 검증해줘” can check missing validation logic automatically.

**Tech Stack:** Python dataclasses, existing `FullReport`, `CheckResult`, Typer CLI, current HTML renderer.

## Global Constraints

- QA fail means missing or malformed validation coverage, not `unexplained_gap`.
- Core validation families are `합계검증`, `재무제표 본문-주석 대사`, `주석간 대사`, `현금흐름표 대사`.
- Every QA failure must include a category, source/evidence target, reason, and expected check family.
- Keep the core reconciliation engine independent of MCP.
- Use TDD: every new behavior gets a failing test first.

---

### Task 1: Core QA Model And Evaluator

**Files:**
- Create: `src/dart_footing_reconciler/report_qa.py`
- Test: `tests/test_report_qa.py`

**Interfaces:**
- Produces: `build_validation_qa_report(report: FullReport, checks: list[CheckResult]) -> ValidationQAReport`
- Produces: `ValidationQAReport.status`, `.items`, `.summary_by_category()`

- [ ] Write failing tests for missing required check families and evidence integrity.
- [ ] Implement dataclasses and conservative family detection.
- [ ] Verify tests pass.

### Task 2: HTML Report Panel

**Files:**
- Modify: `src/dart_footing_reconciler/report_html.py`
- Test: `tests/test_report_html_new.py`

**Interfaces:**
- Consumes: `build_validation_qa_report(...)`
- Renders: `검증 커버리지 QA` side-nav item and panel.

- [ ] Write failing renderer tests.
- [ ] Add QA panel and badges for global and scope-split reports.
- [ ] Verify renderer tests pass.

### Task 3: CLI Exposure

**Files:**
- Modify: `src/dart_footing_reconciler/cli.py`
- Modify: `src/dart_footing_reconciler/__init__.py`
- Test: `tests/test_cli_workpaper.py`, `tests/test_package.py`

**Interfaces:**
- Produces: `dart-footing qa-report CURRENT_HTML --company ...`
- Extends: `workpaper-html` to print QA summary after writing.

- [ ] Write failing CLI/package tests.
- [ ] Implement command and exports.
- [ ] Verify focused tests and full suite pass.
