# Multi-Company Corpus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the footing/reconciliation report against at least five public DART companies and turn observed failures into reusable, company-agnostic logic.

**Architecture:** Add a corpus layer that fetches the DART financial section from each filing, runs the existing workpaper checks, exports one HTML report per company, and writes a combined diagnostic Markdown report. Keep company-specific data in a manifest; keep matching logic in semantic helpers and reconciliation modules.

**Tech Stack:** Python 3.11, Typer CLI, urllib, BeautifulSoup/lxml through the existing parser, pytest, self-contained HTML report export.

---

### Task 1: DART Financial Section Fetcher

**Files:**
- Create: `src/dart_footing_reconciler/dart_fetch.py`
- Test: `tests/test_dart_fetch.py`

- [x] Parse `III. 재무에 관한 사항` node metadata from a DART main page.
- [x] Build `report/viewer.do` URL from `rcpNo`, `dcmNo`, `eleId`, `offset`, `length`, and `dtd`.
- [x] Download main and viewer HTML with a browser-like user agent.

### Task 2: Multi-Company Corpus Runner

**Files:**
- Create: `src/dart_footing_reconciler/corpus.py`
- Modify: `src/dart_footing_reconciler/cli.py`
- Test: `tests/test_corpus.py`

- [x] Load sample manifest JSON.
- [x] For each sample, fetch or reuse local raw HTML.
- [x] Parse report, run workpaper checks, export per-company HTML.
- [x] Summarize counts by check status and check type.
- [x] Write a combined Markdown diagnostic report.

### Task 3: Company-Agnostic Matching Improvements

**Files:**
- Modify: `src/dart_footing_reconciler/table_semantics.py`
- Modify: `src/dart_footing_reconciler/report_html.py`
- Modify: `src/dart_footing_reconciler/reconciliation_inputs.py`

- [x] Centralize current/prior period inference.
- [x] Remove fixed fiscal-period and fixed note-number assumptions from report-layer cashflow map.
- [x] Apply current-period preference to reconciliation input extraction.

### Task 4: Public 5-Company Run

**Files:**
- Create: `out/corpus/manifest_2026-05-25.json`
- Create: `docs/validation/2026-05-25-multi-company-workpaper.md`

- [x] Run AP시스템, CJ제일제당, DB하이텍, DS단석, GST.
- [x] Generate one report per company.
- [x] Record observed failure categories and next implementation priorities.
