# Footing Evidence Source Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add audit evidence coordinates to footing results so each material beginning, movement, and ending amount can be traced to its table cell.

**Architecture:** Keep the existing footing arithmetic engine intact and extend its result model with a small immutable `FootingEvidence` dataclass. Evidence source is represented as deterministic local table coordinates, `table:{table.index} row:{row_idx} col:{col_idx}`, because the HTML table parser currently has table-level context but not file line positions.

**Tech Stack:** Python dataclasses, existing `extract_tables()` parser, existing `uv run pytest` test suite.

---

### Task 1: Add Footing Evidence Coordinates

**Files:**
- Modify: `src/dart_footing_reconciler/footing.py`
- Test: `tests/test_footing.py`

- [x] **Step 1: Write the failing test**

Append this test to `tests/test_footing.py`:

```python
def test_foot_table_preserves_evidence_coordinates_for_material_amounts() -> None:
    html = """
    <p>14. 유형자산</p>
    <table>
      <tr><th>구분</th><th>합계</th></tr>
      <tr><td>기초</td><td>1,000</td></tr>
      <tr><td>취득</td><td>500</td></tr>
      <tr><td>감가상각</td><td>100</td></tr>
      <tr><td>기말</td><td>1,400</td></tr>
    </table>
    """

    result = foot_table(extract_tables(html)[0])
    evidence = result.columns[0].evidence

    assert [(item.role, item.label, item.amount, item.source) for item in evidence] == [
        ("beginning", "기초", 1000, "table:0 row:1 col:1"),
        ("movement", "취득", 500, "table:0 row:2 col:1"),
        ("movement", "감가상각", -100, "table:0 row:3 col:1"),
        ("ending", "기말", 1400, "table:0 row:4 col:1"),
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Note: this worktree was already partially implemented when commit cleanup
started, so the red-state failure was not re-run in this cleanup pass.

Run: `uv run pytest tests/test_footing.py::test_foot_table_preserves_evidence_coordinates_for_material_amounts -v`

Expected: FAIL with `AttributeError: 'FootingColumnResult' object has no attribute 'evidence'`.

- [x] **Step 3: Write minimal implementation**

Modify `src/dart_footing_reconciler/footing.py`:

```python
@dataclass(frozen=True)
class FootingEvidence:
    role: str
    label: str
    amount: int
    source: str
```

Add `evidence: list[FootingEvidence]` to `FootingColumnResult`.

Inside `foot_table()`, create evidence in each comparable column:

```python
evidence: list[FootingEvidence] = [
    FootingEvidence(
        role="beginning",
        label=_cell(table, beginning_idx, label_col),
        amount=beginning,
        source=_cell_source(table, beginning_idx, col),
    )
]
```

For each parsed movement row, compute `movement_amount = _movement_amount(label, amount, column_context)`, add it to `expected`, and append:

```python
FootingEvidence(
    role="movement",
    label=label,
    amount=movement_amount,
    source=_cell_source(table, row_idx, col),
)
```

Before constructing `FootingColumnResult`, append ending evidence:

```python
evidence.append(
    FootingEvidence(
        role="ending",
        label=_cell(table, ending_idx, label_col),
        amount=actual,
        source=_cell_source(table, ending_idx, col),
    )
)
```

Add this helper near `_cell()`:

```python
def _cell_source(table: ParsedTable, row_idx: int, col_idx: int) -> str:
    return f"table:{table.index} row:{row_idx} col:{col_idx}"
```

- [x] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_footing.py::test_foot_table_preserves_evidence_coordinates_for_material_amounts -v`

Expected: PASS.

- [x] **Step 5: Run related tests**

Run: `uv run pytest tests/test_footing.py tests/test_cli.py tests/test_package.py -v`

Expected: all selected tests pass.

- [x] **Step 6: Run full verification**

Run: `uv run pytest`

Expected: all tests pass.
