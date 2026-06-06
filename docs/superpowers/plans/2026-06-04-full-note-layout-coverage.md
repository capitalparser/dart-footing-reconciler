# Full Note Layout Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a full-note inventory and layout coverage foundation so every company report scans all notes/tables, classifies known versus unknown table layouts, and reports what was verified, unverified, or parse-uncertain across the entire disclosure.

**Architecture:** Add a source-preserving note inventory layer above the existing document parser, then classify each table with a small layout registry that records confidence and evidence. Keep existing footing and reconciliation checks separate; coverage reporting observes all notes/tables and links existing check results back to table sources without making materiality a pass/fail criterion.

**Tech Stack:** Python dataclasses, existing DART HTML parser/document model, Typer CLI, pytest, existing corpus/workpaper flows.

---

## Audit-Grade Success Criteria

1. **All-note scope:** For a parsed company report, every note section and every table under every note appears in the inventory, including tables with unknown or unsupported layouts.
2. **Source preservation:** Every inventory table preserves `note_no`, `section_id`, title, table index, unit multiplier, heading, row count, column count, and a deterministic source string such as `note:11/table:0`.
3. **Layout classification with evidence:** Every inventory table receives one layout classification: a known layout key or `unknown_layout`. Known classifications include confidence and evidence strings based on observed labels/headers, not company names.
4. **No materiality pass/fail:** `matched` remains exact or display-unit-bounded. Materiality is not used to turn a gap into a pass.
5. **Coverage accounting:** A company-level report counts total notes, total note tables, known layout tables, unknown layout tables, tables with at least one validation/check result, tables with only parse uncertainty, and tables with no attempted validation.
6. **Regression safety:** Existing default tests pass with `uv run pytest`. Focused tests for inventory, layout classification, and coverage pass before any corpus run.
7. **Corpus readiness:** The new coverage report can be generated for a multi-company corpus without external fetches when cached manifests are available, and unknown layouts are surfaced as backlog instead of being silently ignored.

## File Structure

- Create `src/dart_footing_reconciler/note_inventory.py`
  - Owns full-note inventory dataclasses and extraction from `FullReport`.
  - Does not perform reconciliation arithmetic.
- Create `src/dart_footing_reconciler/layout_variants.py`
  - Owns deterministic table layout classification.
  - Uses table headers, row labels, titles, and note metadata; never company names.
- Create `src/dart_footing_reconciler/coverage.py`
  - Owns company-level coverage aggregation by joining inventory tables with existing `CheckResult` evidence sources.
- Modify `src/dart_footing_reconciler/cli.py`
  - Add a `coverage-report` command for one local HTML file.
- Modify `src/dart_footing_reconciler/__init__.py`
  - Export the new public package helpers only if current package style already exports similar helpers.
- Create `tests/test_note_inventory.py`
- Create `tests/test_layout_variants.py`
- Create `tests/test_coverage.py`
- Modify `tests/test_cli.py`

## Task 1: Full Note Inventory

**Files:**
- Create: `src/dart_footing_reconciler/note_inventory.py`
- Test: `tests/test_note_inventory.py`

- [ ] **Step 1: Write the failing inventory test**

```python
from dart_footing_reconciler.document import parse_full_report
from dart_footing_reconciler.note_inventory import build_note_inventory


def test_build_note_inventory_includes_every_note_table(tmp_path):
    html = """
    <html><body>
      <p>1. 일반사항</p>
      <table><tr><th>구분</th><th>내용</th></tr><tr><td>회사</td><td>샘플</td></tr></table>
      <p>11. 유형자산</p>
      <table><tr><th>구분</th><th>합계</th></tr><tr><td>기말</td><td>1,000</td></tr></table>
      <p>31. 비용의 성격별 분류</p>
      <table><tr><th>구분</th><th>금액</th></tr><tr><td>감가상각비</td><td>100</td></tr></table>
    </body></html>
    """
    source = tmp_path / "sample.html"
    source.write_text(html, encoding="utf-8")

    report = parse_full_report(source, company="Sample Co")
    inventory = build_note_inventory(report)

    assert inventory.company == "Sample Co"
    assert inventory.note_count == 3
    assert len(inventory.tables) == 3
    assert [table.note_no for table in inventory.tables] == ["1", "11", "31"]
    assert inventory.tables[1].source == "note:11/table:1"
    assert inventory.tables[1].row_count == 2
    assert inventory.tables[1].column_count == 2
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_note_inventory.py::test_build_note_inventory_includes_every_note_table -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'dart_footing_reconciler.note_inventory'`.

- [ ] **Step 3: Implement the inventory dataclasses and builder**

```python
from __future__ import annotations

from dataclasses import dataclass

from dart_footing_reconciler.document import FullReport


@dataclass(frozen=True)
class NoteTableInventoryItem:
    company: str
    section_id: str
    note_no: str
    title: str
    table_index: int
    source: str
    heading: str
    unit_multiplier: int
    row_count: int
    column_count: int
    headers: tuple[str, ...]
    row_labels: tuple[str, ...]


@dataclass(frozen=True)
class NoteInventory:
    company: str
    note_count: int
    tables: tuple[NoteTableInventoryItem, ...]


def build_note_inventory(report: FullReport) -> NoteInventory:
    tables: list[NoteTableInventoryItem] = []
    for section in report.notes:
        for block in section.blocks:
            table = block.table
            if table is None:
                continue
            rows = table.rows
            headers = tuple(rows[0]) if rows else ()
            row_labels = tuple(row[0] for row in rows[1:] if row)
            column_count = max((len(row) for row in rows), default=0)
            tables.append(
                NoteTableInventoryItem(
                    company=report.company,
                    section_id=section.section_id,
                    note_no=section.note_no,
                    title=section.title,
                    table_index=table.index,
                    source=f"note:{section.note_no}/table:{table.index}",
                    heading=table.heading,
                    unit_multiplier=table.unit_multiplier,
                    row_count=len(rows),
                    column_count=column_count,
                    headers=headers,
                    row_labels=row_labels,
                )
            )
    return NoteInventory(
        company=report.company,
        note_count=len(report.notes),
        tables=tuple(tables),
    )
```

- [ ] **Step 4: Run the inventory test**

Run: `uv run pytest tests/test_note_inventory.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/note_inventory.py tests/test_note_inventory.py
git commit -m "feat: add full note inventory"
```

## Task 2: Layout Variant Classification

**Files:**
- Create: `src/dart_footing_reconciler/layout_variants.py`
- Test: `tests/test_layout_variants.py`

- [ ] **Step 1: Write failing layout classification tests**

```python
from dart_footing_reconciler.layout_variants import classify_layout
from dart_footing_reconciler.note_inventory import NoteTableInventoryItem


def _item(title, headers, rows):
    return NoteTableInventoryItem(
        company="Sample Co",
        section_id="note:11",
        note_no="11",
        title=title,
        table_index=0,
        source="note:11/table:0",
        heading=title,
        unit_multiplier=1000,
        row_count=1 + len(rows),
        column_count=len(headers),
        headers=tuple(headers),
        row_labels=tuple(rows),
    )


def test_classify_ppe_cost_accumulated_grant_total_layout():
    item = _item(
        "유형자산",
        ["구분", "취득원가", "감가상각누계액", "정부보조금", "합계"],
        ["토지", "건물", "합계"],
    )

    result = classify_layout(item)

    assert result.key == "asset_cost_accumulated_grant_total"
    assert result.confidence >= 0.8
    assert "정부보조금" in " ".join(result.evidence)
    assert result.source == "note:11/table:0"


def test_unknown_layout_is_preserved():
    item = _item("일반사항", ["구분", "내용"], ["회사", "주소"])

    result = classify_layout(item)

    assert result.key == "unknown_layout"
    assert result.confidence == 0.0
    assert result.evidence == ()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_layout_variants.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'dart_footing_reconciler.layout_variants'`.

- [ ] **Step 3: Implement layout classification**

```python
from __future__ import annotations

import re
from dataclasses import dataclass

from dart_footing_reconciler.note_inventory import NoteTableInventoryItem


@dataclass(frozen=True)
class LayoutClassification:
    key: str
    confidence: float
    evidence: tuple[str, ...]
    source: str


def classify_layout(item: NoteTableInventoryItem) -> LayoutClassification:
    headers = tuple(_compact(header) for header in item.headers)
    row_labels = tuple(_compact(label) for label in item.row_labels)
    title = _compact(item.title + " " + item.heading)

    if _is_asset_cost_accumulated_grant_total(title, headers, row_labels):
        return LayoutClassification(
            key="asset_cost_accumulated_grant_total",
            confidence=0.9,
            evidence=(
                "title contains asset topic",
                "headers include 취득원가",
                "headers include 감가상각누계액",
                "headers include 정부보조금",
                "headers include 합계",
            ),
            source=item.source,
        )

    if _is_asset_carrying_amount_total(title, headers, row_labels):
        return LayoutClassification(
            key="asset_carrying_amount_total",
            confidence=0.8,
            evidence=(
                "title contains asset topic",
                "headers include carrying amount or total",
                "rows include 기말 or 합계",
            ),
            source=item.source,
        )

    if _is_functional_expense_allocation(title, headers, row_labels):
        return LayoutClassification(
            key="functional_expense_allocation",
            confidence=0.8,
            evidence=("title or rows indicate expense allocation",),
            source=item.source,
        )

    return LayoutClassification(
        key="unknown_layout",
        confidence=0.0,
        evidence=(),
        source=item.source,
    )


def _is_asset_cost_accumulated_grant_total(
    title: tuple[str, ...] | str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    joined_title = "".join(title) if isinstance(title, tuple) else title
    return (
        any(topic in joined_title for topic in ("유형자산", "무형자산", "투자부동산"))
        and any("취득원가" in header for header in headers)
        and any("감가상각누계액" in header or "상각누계액" in header for header in headers)
        and any("정부보조금" in header for header in headers)
        and any(header in {"합계", "총계"} for header in headers)
    )


def _is_asset_carrying_amount_total(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    return (
        any(topic in title for topic in ("유형자산", "무형자산", "투자부동산"))
        and any(any(alias in header for alias in ("장부금액", "장부가액", "합계")) for header in headers)
        and any(any(alias in row for alias in ("기말", "합계", "총계")) for row in row_labels)
    )


def _is_functional_expense_allocation(
    title: str,
    headers: tuple[str, ...],
    row_labels: tuple[str, ...],
) -> bool:
    joined_rows = " ".join(row_labels)
    return "비용" in title and any(alias in joined_rows for alias in ("매출원가", "판매비와관리비", "연구", "개발"))


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", value or "")
```

- [ ] **Step 4: Run layout tests**

Run: `uv run pytest tests/test_layout_variants.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/layout_variants.py tests/test_layout_variants.py
git commit -m "feat: classify note table layout variants"
```

## Task 3: Company Coverage Aggregation

**Files:**
- Create: `src/dart_footing_reconciler/coverage.py`
- Test: `tests/test_coverage.py`

- [ ] **Step 1: Write failing coverage tests**

```python
from dart_footing_reconciler.checks import CheckEvidence, CheckResult
from dart_footing_reconciler.coverage import build_coverage_report
from dart_footing_reconciler.layout_variants import LayoutClassification
from dart_footing_reconciler.note_inventory import NoteInventory, NoteTableInventoryItem


def _table(note_no, table_index, title):
    return NoteTableInventoryItem(
        company="Sample Co",
        section_id=f"note:{note_no}",
        note_no=str(note_no),
        title=title,
        table_index=table_index,
        source=f"note:{note_no}/table:{table_index}",
        heading=title,
        unit_multiplier=1,
        row_count=2,
        column_count=2,
        headers=("구분", "합계"),
        row_labels=("기말",),
    )


def test_coverage_counts_known_unknown_and_validated_tables():
    inventory = NoteInventory(
        company="Sample Co",
        note_count=2,
        tables=(_table(11, 0, "유형자산"), _table(31, 1, "기타")),
    )
    layouts = {
        "note:11/table:0": LayoutClassification("asset_carrying_amount_total", 0.8, ("evidence",), "note:11/table:0"),
        "note:31/table:1": LayoutClassification("unknown_layout", 0.0, (), "note:31/table:1"),
    }
    checks = [
        CheckResult(
            check_id="reconciliation:property_plant_equipment.balance",
            check_type="primary_balance_reconciliation",
            title="유형자산 balance",
            status="matched",
            expected=100,
            actual=100,
            difference=0,
            tolerance=0,
            evidence=[CheckEvidence("note", 100, "note:11/table:0/row:1/col:1")],
            reason="matched",
        )
    ]

    report = build_coverage_report(inventory, layouts, checks)

    assert report.company == "Sample Co"
    assert report.total_notes == 2
    assert report.total_tables == 2
    assert report.known_layout_tables == 1
    assert report.unknown_layout_tables == 1
    assert report.validated_tables == 1
    assert report.unvalidated_tables == 1
```

- [ ] **Step 2: Run coverage test to verify it fails**

Run: `uv run pytest tests/test_coverage.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'dart_footing_reconciler.coverage'`.

- [ ] **Step 3: Implement coverage aggregation**

```python
from __future__ import annotations

from dataclasses import dataclass

from dart_footing_reconciler.checks import CheckResult
from dart_footing_reconciler.layout_variants import LayoutClassification
from dart_footing_reconciler.note_inventory import NoteInventory


@dataclass(frozen=True)
class CoverageReport:
    company: str
    total_notes: int
    total_tables: int
    known_layout_tables: int
    unknown_layout_tables: int
    validated_tables: int
    parse_uncertain_tables: int
    unvalidated_tables: int


def build_coverage_report(
    inventory: NoteInventory,
    layouts: dict[str, LayoutClassification],
    checks: list[CheckResult],
) -> CoverageReport:
    table_sources = {table.source for table in inventory.tables}
    known_layout_tables = sum(
        1 for table in inventory.tables if layouts.get(table.source) and layouts[table.source].key != "unknown_layout"
    )
    unknown_layout_tables = len(inventory.tables) - known_layout_tables
    validated_sources: set[str] = set()
    parse_uncertain_sources: set[str] = set()
    for check in checks:
        touched = {
            source
            for evidence in check.evidence
            for source in table_sources
            if evidence.source.startswith(source + "/")
        }
        if check.status == "parse_uncertain":
            parse_uncertain_sources.update(touched)
        else:
            validated_sources.update(touched)
    validated_tables = len(validated_sources)
    parse_uncertain_tables = len(parse_uncertain_sources - validated_sources)
    unvalidated_tables = len(table_sources - validated_sources - parse_uncertain_sources)
    return CoverageReport(
        company=inventory.company,
        total_notes=inventory.note_count,
        total_tables=len(inventory.tables),
        known_layout_tables=known_layout_tables,
        unknown_layout_tables=unknown_layout_tables,
        validated_tables=validated_tables,
        parse_uncertain_tables=parse_uncertain_tables,
        unvalidated_tables=unvalidated_tables,
    )
```

- [ ] **Step 4: Run coverage tests**

Run: `uv run pytest tests/test_coverage.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/coverage.py tests/test_coverage.py
git commit -m "feat: report note table coverage"
```

## Task 4: CLI Coverage Report

**Files:**
- Modify: `src/dart_footing_reconciler/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI test**

```python
def test_cli_coverage_report_outputs_full_note_counts(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>1. 일반사항</p>
          <table><tr><th>구분</th><th>내용</th></tr><tr><td>회사</td><td>샘플</td></tr></table>
          <p>11. 유형자산</p>
          <table><tr><th>구분</th><th>합계</th></tr><tr><td>기말</td><td>1,000</td></tr></table>
        </body></html>
        """,
        encoding="utf-8",
    )

    result = runner.invoke(app, ["coverage-report", str(source), "--company", "Sample Co"])

    assert result.exit_code == 0
    assert "company: Sample Co" in result.output
    assert "total_notes: 2" in result.output
    assert "total_tables: 2" in result.output
    assert "unknown_layout_tables:" in result.output
```

- [ ] **Step 2: Run CLI test to verify it fails**

Run: `uv run pytest tests/test_cli.py::test_cli_coverage_report_outputs_full_note_counts -v`

Expected: FAIL because command `coverage-report` does not exist.

- [ ] **Step 3: Add CLI command**

Add imports:

```python
from dart_footing_reconciler.coverage import build_coverage_report
from dart_footing_reconciler.layout_variants import classify_layout
from dart_footing_reconciler.note_inventory import build_note_inventory
```

Add command:

```python
@app.command("coverage-report")
def coverage_report(
    html: Path,
    company: Annotated[str | None, typer.Option(help="Company name for the report")] = None,
    tolerance: Annotated[int, typer.Option(help="Allowed absolute difference")] = 1,
) -> None:
    report = parse_full_report(html, company=company or html.stem)
    inventory = build_note_inventory(report)
    layouts = {table.source: classify_layout(table) for table in inventory.tables}
    checks = _run_workpaper_checks(report, None, tolerance)
    coverage = build_coverage_report(inventory, layouts, checks)
    typer.echo(f"company: {coverage.company}")
    typer.echo(f"total_notes: {coverage.total_notes}")
    typer.echo(f"total_tables: {coverage.total_tables}")
    typer.echo(f"known_layout_tables: {coverage.known_layout_tables}")
    typer.echo(f"unknown_layout_tables: {coverage.unknown_layout_tables}")
    typer.echo(f"validated_tables: {coverage.validated_tables}")
    typer.echo(f"parse_uncertain_tables: {coverage.parse_uncertain_tables}")
    typer.echo(f"unvalidated_tables: {coverage.unvalidated_tables}")
```

Use the existing `_run_workpaper_checks(report, None, tolerance)` helper in `cli.py`. Do not create a second validation pipeline.

- [ ] **Step 4: Run CLI test**

Run: `uv run pytest tests/test_cli.py::test_cli_coverage_report_outputs_full_note_counts -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/cli.py tests/test_cli.py
git commit -m "feat: add note coverage CLI report"
```

## Task 5: Final Verification And Documentation

**Files:**
- Modify: `HANDOFF.md`
- Modify: `docs/validation/2026-06-03-agent-work-integration-ledger.md`

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/test_note_inventory.py tests/test_layout_variants.py tests/test_coverage.py tests/test_cli.py -q
```

Expected: PASS.

- [ ] **Step 2: Run default test suite**

Run:

```bash
uv run pytest
```

Expected: PASS.

- [ ] **Step 3: Update handoff**

Add a `Latest implementation slice` entry to `HANDOFF.md`:

```markdown
- Latest implementation slice: full-note layout coverage foundation now scans every note table in a company report, classifies known versus unknown table layouts without company-name branching, and reports all-note coverage counts through the CLI. This is a coverage and backlog-management layer only: materiality is not used as a pass/fail criterion, and existing footing and cash-flow reconciliation checks remain separate. Verification passed with full `uv run pytest`.
```

- [ ] **Step 4: Update integration ledger**

Add a canonical feature unit row:

```markdown
| `full-note-layout-coverage` | current follow-up | current uncommitted slice | `src/dart_footing_reconciler/note_inventory.py`, `src/dart_footing_reconciler/layout_variants.py`, `src/dart_footing_reconciler/coverage.py`, `src/dart_footing_reconciler/cli.py` | Scans every note table, classifies known vs unknown layouts, and reports company-level note/table coverage. Future company-format fixes should add layout variants and fixtures here rather than company-name branches. |
```

- [ ] **Step 5: Commit docs**

```bash
git add HANDOFF.md docs/validation/2026-06-03-agent-work-integration-ledger.md
git commit -m "docs: record full note layout coverage foundation"
```

## Self-Review

- **Spec coverage:** The plan covers all-note scope, source preservation, layout evidence, no materiality pass/fail, coverage accounting, regression tests, and corpus readiness.
- **Placeholder scan:** The implementation steps define concrete files, dataclasses, functions, test cases, commands, and expected outcomes. No `TBD` or open-ended implementation steps remain.
- **Type consistency:** `NoteTableInventoryItem`, `NoteInventory`, `LayoutClassification`, and `CoverageReport` signatures are used consistently across tasks.
- **Scope check:** This plan intentionally stops at coverage foundation. It does not migrate every existing reconciliation rule to variant-aware selectors yet; that becomes the next plan once coverage exposes the highest-impact unknown layouts.
