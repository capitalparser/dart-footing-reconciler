# Semantic Report Verification Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 회사별로 서로 다른 DART HTML/DSD 표 구조를 회사명 분기 없이 semantic layer로 정규화하고, `statement_note`와 `note_internal` 검증 후보를 1차 범위에서 함께 생성하며, 실제 회사 보고서 순서를 반영한 검증보고서 배치를 제공한다.

**Architecture:** Keep the existing parser, footing checks, reconciliation checks, and HTML renderer. Add a thin semantic layer that indexes report tables in source/report order, attaches verification signatures, emits table-level semantic amount facts, derives validation candidates for both financial-statement-body-to-note and note-internal checks, and places existing `CheckResult` rows back onto the company report order. This is a migration foundation: existing checks still run, but report validation is no longer organized by company-specific dataset shape or layout-name dispatch.

**Tech Stack:** Python 3.11, pytest, uv, existing `dart_footing_reconciler` package modules.

---

## Current State Snapshot

- `src/dart_footing_reconciler/checks_statement_ties.py` exists and is wired through `check_pipeline.py`.
- `src/dart_footing_reconciler/signatures.py` exists with v0 signature extraction: `rollforward_axis`, `internal_closure`, `statement_core_match`.
- `src/dart_footing_reconciler/essential_notes.py` does not exist yet, although the previous cementing-layer plan expected it.
- `report_frame.py` already attaches checks to statement/note source tables using evidence source prefixes.
- `report_frame.py` currently orders statements canonically and notes by numeric note key; the new requirement is to use the company report order as the primary report shape.
- Working tree contains an untracked prior plan: `docs/superpowers/plans/2026-06-08-cementing-layer-v0.md`. Do not edit or remove it unless explicitly requested.
- Baseline smoke already passed before this plan was written:

```bash
uv run pytest tests/test_signatures.py tests/test_checks_statement_ties.py tests/test_check_pipeline.py tests/test_report_frame.py -q
```

Expected baseline at handoff time: `43 passed`.

## Non-Negotiable Constraints

- Footing and reconciliation remain separate checks. Do not collapse `total_check` / internal footing into cash-flow or note-statement reconciliation.
- Every material amount must preserve source location through `CheckEvidence.source`.
- Label mapping uncertainty must stay explicit through signature confidence, evidence, and `parse_uncertain`.
- The core engine must run without MCP.
- Do not use company names, DART industry codes, or layout keys as verification routing gates.
- Do not use closest-amount matching to manufacture `matched`; semantic correspondence comes from labels, signatures, source section, and arithmetic closure.
- The reviewer-facing validation report must borrow the actual company report sequence: financial statements first in report form order, then notes in parsed report order unless there is no parsed order.
- V1 candidate generation includes both `statement_note` and `note_internal`. Do not defer note-internal candidate generation to a later phase.
- `note_internal` candidates are first-class semantic candidates, not incidental byproducts of rendered `total_check` rows.

## V1 Dataset And Candidate Scope

The first semantic dataset must answer two questions before checks run:

1. What source-backed facts exist in this report?
2. Which validations are eligible to run from those facts and signatures?

V1 includes these validation candidate layers:

| Layer | Candidate IDs | Required semantic basis |
|---|---|---|
| `statement_note` | `note_statement_balance`, `note_cashflow_bridge` | statement/core table signatures, note table signatures, source-backed amount facts |
| `note_internal` | `internal_table_total`, `rollforward_internal_formula` | internal closure signatures, rollforward signatures, table-local amount facts |
| `statement_cross` | `statement_cross_ties` | statement core signatures |

The semantic layer does not need to execute every candidate in V1. It must expose the candidate list with enough metadata for the harness layer to decide which existing check function should consume it.

## Dataset Contract

Semantic table facts are table-level facts. They preserve the parsed source table and attach signatures:

```python
@dataclass(frozen=True)
class SemanticTable:
    company: str
    source: str
    order: int
    section_kind: str
    statement_kind: str
    section_id: str
    section_title: str
    note_no: str
    table_index: int
    heading: str
    row_count: int
    column_count: int
    unit_multiplier: int
    headers: tuple[str, ...]
    row_labels: tuple[str, ...]
    signatures: tuple[SignatureMatch, ...]
```

Semantic amount facts are table-local facts. V1 uses conservative extraction: row label, amount, period, role, and exact source location. Account mapping can be missing, but source location cannot be missing for material extracted amounts:

```python
@dataclass(frozen=True)
class SemanticAmountFact:
    fact_id: str
    table_source: str
    cell_source: str
    label: str
    amount: int
    period: str
    role: str
    account_key: str | None
    confidence: float
```

Validation candidates are proposed work items for harnesses. V1 candidates are produced from signatures and facts, not company names or layout keys:

```python
@dataclass(frozen=True)
class SemanticValidationCandidate:
    candidate_id: str
    layer: str
    attempt_id: str
    check_type: str
    table_source: str
    evidence_sources: tuple[str, ...]
    confidence: float
    block_reason: str | None = None
```

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `src/dart_footing_reconciler/report_order.py` | Build stable table order index from `FullReport` | Create |
| `src/dart_footing_reconciler/essential_notes.py` | Audit Cycle x Core Account x Essential Note registry | Create |
| `src/dart_footing_reconciler/semantic_layer.py` | Convert `FullReport` tables into signature-backed semantic tables and amount facts | Create |
| `src/dart_footing_reconciler/semantic_attempts.py` | Signature/confidence based attempt registry, no company/layout routing | Create |
| `src/dart_footing_reconciler/semantic_validation.py` | Emit semantic validation candidates and place existing `CheckResult` rows onto semantic report order | Create |
| `src/dart_footing_reconciler/report_frame.py` | Use semantic/report order for note sections and table attachment | Modify |
| `tests/test_report_order.py` | Report-order index behavior | Create |
| `tests/test_essential_notes.py` | Essential-note registry behavior | Create |
| `tests/test_semantic_layer.py` | Semantic dataset behavior across company-specific report shapes | Create |
| `tests/test_semantic_attempts.py` | Attempt selection behavior | Create |
| `tests/test_semantic_validation.py` | Check placement behavior in report order | Create |
| `tests/test_report_frame.py` | Add regression for parsed note order | Modify |

---

### Task 1: Baseline Guard And Scope Freeze

**Files:**
- Read: `AGENTS.md`
- Read: `CONTEXT.md`
- Read: `docs/adr/0003-signature-driven-verification-not-category-dispatch.md`
- Read: `docs/adr/0004-note-tab-verification-surfacing.md`
- Read: `docs/superpowers/plans/2026-06-08-cementing-layer-v0.md`

- [ ] **Step 1: Confirm current code state**

Run:

```bash
git status --short
rg --files src/dart_footing_reconciler tests | sort
```

Expected at handoff time if neither plan has been committed:

```text
?? docs/superpowers/plans/2026-06-08-cementing-layer-v0.md
?? docs/superpowers/plans/2026-06-10-semantic-report-verification-layer.md
```

Additional untracked files may exist if another agent continued after this plan. Inspect them before editing and do not revert user/agent work.

- [ ] **Step 2: Run focused baseline tests**

Run:

```bash
uv run pytest tests/test_signatures.py tests/test_checks_statement_ties.py tests/test_check_pipeline.py tests/test_report_frame.py -q
```

Expected:

```text
43 passed
```

If the exact count changed because new tests were added, accept only a clean PASS. If failures appear, stop and diagnose before implementing this plan.

- [ ] **Step 3: Record baseline note**

Append one bullet to `HANDOFF.md` under the latest implementation slice after the whole plan is implemented, not now. Use this exact content template:

```markdown
- Latest implementation slice: semantic report verification layer now indexes company reports in statement/note order, attaches signature-backed semantic table metadata and amount facts, emits `statement_note` and `note_internal` candidates without company/layout routing, and places existing CheckResult rows back onto the source report sequence. Verification passed with focused semantic tests and full `uv run pytest`.
```

---

### Task 2: Report Order Index

**Files:**
- Create: `src/dart_footing_reconciler/report_order.py`
- Create: `tests/test_report_order.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_report_order.py`:

```python
from dart_footing_reconciler.document import (
    FullReport,
    ReportBlock,
    ReportSection,
    ReportTable,
    SourceLocation,
)
from dart_footing_reconciler.report_order import build_report_order_index


def _section(section_id: str, title: str, kind: str, note_no: str, table: ReportTable) -> ReportSection:
    return ReportSection(
        section_id,
        title,
        kind,
        note_no,
        [ReportBlock("table", "", table, table.location)],
    )


def _table(section_id: str, index: int, heading: str) -> ReportTable:
    return ReportTable(
        index,
        [["구분", "당기"], ["합계", "100"]],
        heading,
        SourceLocation(section_id, 0, index),
    )


def test_report_order_uses_statement_form_order_then_parsed_note_order():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section("statement:cf", "현금흐름표", "statement", "", _table("statement:cf", 0, "현금흐름표")),
            _section("statement:bs", "재무상태표", "statement", "", _table("statement:bs", 1, "재무상태표")),
            _section("statement:pl", "손익계산서", "statement", "", _table("statement:pl", 2, "손익계산서")),
        ],
        [
            _section("note:12", "유형자산", "note", "12", _table("note:12", 3, "12. 유형자산")),
            _section("note:3", "매출", "note", "3", _table("note:3", 4, "3. 매출")),
        ],
    )

    index = build_report_order_index(report)

    assert [entry.source for entry in index.entries] == [
        "statement:bs/table:1",
        "statement:pl/table:2",
        "statement:cf/table:0",
        "note:12/table:3",
        "note:3/table:4",
    ]
    assert index.order_for_source("note:12/table:3") < index.order_for_source("note:3/table:4")


def test_report_order_resolves_evidence_cell_source_to_table_order():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section("note:7", "차입금", "note", "7", _table("note:7", 0, "7. 차입금")),
        ],
    )
    index = build_report_order_index(report)

    assert index.order_for_source("note:7/table:0/row:1/col:1") == 10_000
    assert index.table_source_for("note:7/table:0/row:1/col:1") == "note:7/table:0"
    assert index.order_for_source("unplaced") is None
```

- [ ] **Step 2: Run RED**

Run:

```bash
uv run pytest tests/test_report_order.py -q
```

Expected: import failure for `dart_footing_reconciler.report_order`.

- [ ] **Step 3: Implement `report_order.py`**

Create `src/dart_footing_reconciler/report_order.py`:

```python
"""Company report-order index for semantic validation output."""

from __future__ import annotations

from dataclasses import dataclass

from dart_footing_reconciler.document import FullReport, ReportSection, ReportTable


CANONICAL_STATEMENT_ORDER = (
    "financial_position",
    "income_statement",
    "changes_in_equity",
    "cash_flows",
)


@dataclass(frozen=True)
class ReportOrderEntry:
    source: str
    order: int
    section_kind: str
    statement_kind: str
    section_id: str
    section_title: str
    note_no: str
    table_index: int


@dataclass(frozen=True)
class ReportOrderIndex:
    entries: tuple[ReportOrderEntry, ...]
    _order_by_source: dict[str, int]

    def order_for_source(self, source: str) -> int | None:
        table_source = self.table_source_for(source)
        if not table_source:
            return None
        return self._order_by_source.get(table_source)

    def table_source_for(self, source: str) -> str:
        if "/table:" not in source:
            return ""
        prefix, tail = source.split("/table:", 1)
        table_index = tail.split("/", 1)[0]
        return f"{prefix}/table:{table_index}"


def build_report_order_index(report: FullReport) -> ReportOrderIndex:
    entries: list[ReportOrderEntry] = []
    order = 0

    statement_items: list[tuple[int, int, ReportSection, ReportTable, str]] = []
    for source_index, section in enumerate(report.statements):
        statement_kind = statement_kind_from_title(section.title) or statement_kind_from_source(section.section_id)
        if statement_kind not in CANONICAL_STATEMENT_ORDER:
            continue
        for table in _section_tables(section):
            statement_items.append(
                (
                    CANONICAL_STATEMENT_ORDER.index(statement_kind),
                    source_index,
                    section,
                    table,
                    statement_kind,
                )
            )

    for _kind_order, _source_index, section, table, statement_kind in sorted(
        statement_items,
        key=lambda item: (item[0], item[1], item[3].index),
    ):
        entries.append(
            _entry(order, section, table, section_kind="statement", statement_kind=statement_kind)
        )
        order += 1

    note_base = 10_000
    for note_source_index, section in enumerate(report.notes):
        for table in _section_tables(section):
            entries.append(
                _entry(
                    note_base + note_source_index * 100 + table.index,
                    section,
                    table,
                    section_kind="note",
                    statement_kind="",
                )
            )

    return ReportOrderIndex(
        entries=tuple(entries),
        _order_by_source={entry.source: entry.order for entry in entries},
    )


def statement_kind_from_title(title: str) -> str:
    normalized = _compact(title)
    if "재무상태표" in normalized:
        return "financial_position"
    if "자본변동표" in normalized:
        return "changes_in_equity"
    if "현금흐름표" in normalized:
        return "cash_flows"
    if "손익계산서" in normalized or "포괄손익계산서" in normalized:
        return "income_statement"
    return ""


def statement_kind_from_source(source: str) -> str:
    if not source.startswith("statement:"):
        return ""
    normalized = _compact(source.split("/", 1)[0].split(":", 1)[1])
    aliases = {
        "financial_position": ("bs", "balance_sheet", "financial_position", "재무상태표"),
        "income_statement": ("is", "pl", "income_statement", "손익계산서", "포괄손익계산서"),
        "changes_in_equity": ("sce", "ce", "equity", "changes_in_equity", "자본변동표"),
        "cash_flows": ("cf", "cfs", "cashflow", "cash_flows", "현금흐름표"),
    }
    for kind, values in aliases.items():
        if normalized in {_compact(value) for value in values}:
            return kind
    return ""


def _entry(
    order: int,
    section: ReportSection,
    table: ReportTable,
    *,
    section_kind: str,
    statement_kind: str,
) -> ReportOrderEntry:
    return ReportOrderEntry(
        source=f"{section.section_id}/table:{table.index}",
        order=order,
        section_kind=section_kind,
        statement_kind=statement_kind,
        section_id=section.section_id,
        section_title=section.title,
        note_no=section.note_no,
        table_index=table.index,
    )


def _section_tables(section: ReportSection) -> list[ReportTable]:
    return [
        block.table
        for block in section.blocks
        if block.table is not None and getattr(block.table, "rows", None)
    ]


def _compact(value: str) -> str:
    return "".join(value.split()).lower()
```

- [ ] **Step 4: Run GREEN**

Run:

```bash
uv run pytest tests/test_report_order.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/dart_footing_reconciler/report_order.py tests/test_report_order.py
git commit -m "feat: add company report order index"
```

---

### Task 3: Essential Note Registry

**Files:**
- Create: `src/dart_footing_reconciler/essential_notes.py`
- Create: `tests/test_essential_notes.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_essential_notes.py`:

```python
from dart_footing_reconciler.essential_notes import (
    AUDIT_CYCLES,
    EssentialNote,
    all_essential_notes,
    essential_notes_for,
)


def test_all_six_audit_cycles_are_registered():
    assert AUDIT_CYCLES == ("operating", "investing", "financing", "tax", "employee", "other")


def test_investing_cycle_includes_asset_cashflow_and_balance_axes():
    notes = essential_notes_for("investing")
    ppe = [note for note in notes if note.account_key == "property_plant_equipment"]

    assert ppe
    assert "note_to_bs" in ppe[0].reconciliation_axes
    assert "note_to_cf" in ppe[0].reconciliation_axes
    assert "rollforward_axis" in ppe[0].required_signatures


def test_registry_entries_are_plain_semantic_contracts_not_company_branches():
    for note in all_essential_notes():
        assert isinstance(note, EssentialNote)
        assert not hasattr(note, "company")
        assert not hasattr(note, "layout_key")
        assert note.required_signatures
        assert note.reconciliation_axes


def test_unknown_cycle_returns_empty_tuple():
    assert essential_notes_for("unknown") == ()
```

- [ ] **Step 2: Run RED**

Run:

```bash
uv run pytest tests/test_essential_notes.py -q
```

Expected: import failure for `dart_footing_reconciler.essential_notes`.

- [ ] **Step 3: Implement `essential_notes.py`**

Create `src/dart_footing_reconciler/essential_notes.py`:

```python
"""Audit Cycle x Core Account x Essential Note semantic registry."""

from __future__ import annotations

from dataclasses import dataclass


AUDIT_CYCLES = ("operating", "investing", "financing", "tax", "employee", "other")


@dataclass(frozen=True)
class EssentialNote:
    cycle: str
    account_key: str
    display_name: str
    required_signatures: tuple[str, ...]
    reconciliation_axes: tuple[str, ...]
    source_priority: tuple[str, ...] = ("statement", "note", "cross_note")
    rationale: str = ""


_REGISTRY: dict[str, tuple[EssentialNote, ...]] = {
    "operating": (
        EssentialNote(
            cycle="operating",
            account_key="revenue",
            display_name="매출액",
            required_signatures=("statement_core_match",),
            reconciliation_axes=("note_to_pl",),
            rationale="PL core account to revenue disclosure.",
        ),
        EssentialNote(
            cycle="operating",
            account_key="cost_of_sales",
            display_name="매출원가",
            required_signatures=("statement_core_match",),
            reconciliation_axes=("note_to_pl",),
            rationale="PL core account to cost disclosure.",
        ),
    ),
    "investing": (
        EssentialNote(
            cycle="investing",
            account_key="property_plant_equipment",
            display_name="유형자산",
            required_signatures=("statement_core_match", "rollforward_axis"),
            reconciliation_axes=("note_to_bs", "note_to_cf", "note_to_note", "internal"),
            rationale="PPE balance, roll-forward, and cash acquisition/disposal bridge.",
        ),
        EssentialNote(
            cycle="investing",
            account_key="intangible_assets",
            display_name="무형자산",
            required_signatures=("statement_core_match", "rollforward_axis"),
            reconciliation_axes=("note_to_bs", "note_to_cf", "note_to_note", "internal"),
            rationale="Intangible balance, roll-forward, and cash acquisition/disposal bridge.",
        ),
        EssentialNote(
            cycle="investing",
            account_key="investment_property",
            display_name="투자부동산",
            required_signatures=("statement_core_match", "rollforward_axis"),
            reconciliation_axes=("note_to_bs", "note_to_cf", "internal"),
            rationale="Investment-property balance and movement bridge.",
        ),
    ),
    "financing": (
        EssentialNote(
            cycle="financing",
            account_key="borrowings",
            display_name="차입금",
            required_signatures=("statement_core_match",),
            reconciliation_axes=("note_to_bs", "note_to_cf", "internal"),
            rationale="Borrowing balance and financing cash-flow bridge.",
        ),
        EssentialNote(
            cycle="financing",
            account_key="bonds",
            display_name="사채",
            required_signatures=("statement_core_match",),
            reconciliation_axes=("note_to_bs", "note_to_cf", "internal"),
            rationale="Bond balance and financing cash-flow bridge.",
        ),
        EssentialNote(
            cycle="financing",
            account_key="lease_liabilities",
            display_name="리스부채",
            required_signatures=("statement_core_match",),
            reconciliation_axes=("note_to_bs", "note_to_cf", "internal"),
            rationale="Lease liability current/non-current and financing payment bridge.",
        ),
    ),
    "tax": (
        EssentialNote(
            cycle="tax",
            account_key="income_tax_expense_benefit",
            display_name="법인세비용",
            required_signatures=("statement_core_match", "component_total_pair"),
            reconciliation_axes=("note_to_pl", "internal"),
            rationale="Tax expense composition to PL tax expense.",
        ),
    ),
    "employee": (
        EssentialNote(
            cycle="employee",
            account_key="defined_benefit_obligation",
            display_name="확정급여채무",
            required_signatures=("rollforward_axis", "statement_core_match"),
            reconciliation_axes=("note_to_bs", "note_to_pl", "internal"),
            rationale="Employee benefit obligation and expense allocation.",
        ),
    ),
    "other": (
        EssentialNote(
            cycle="other",
            account_key="cash_and_cash_equivalents",
            display_name="현금및현금성자산",
            required_signatures=("statement_core_match",),
            reconciliation_axes=("statement_to_statement",),
            rationale="BS ending cash to CF ending cash tie.",
        ),
        EssentialNote(
            cycle="other",
            account_key="equity_total",
            display_name="자본총계",
            required_signatures=("statement_core_match",),
            reconciliation_axes=("statement_to_statement", "note_to_sce"),
            rationale="BS equity to statement of changes in equity.",
        ),
    ),
}


def essential_notes_for(cycle: str) -> tuple[EssentialNote, ...]:
    return _REGISTRY.get(cycle, ())


def all_essential_notes() -> tuple[EssentialNote, ...]:
    return tuple(note for cycle in AUDIT_CYCLES for note in _REGISTRY.get(cycle, ()))
```

- [ ] **Step 4: Run GREEN**

Run:

```bash
uv run pytest tests/test_essential_notes.py -q
```

Expected: `4 passed`.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/dart_footing_reconciler/essential_notes.py tests/test_essential_notes.py
git commit -m "feat: add essential note semantic registry"
```

---

### Task 4: Semantic Dataset Layer

**Files:**
- Create: `src/dart_footing_reconciler/semantic_layer.py`
- Create: `tests/test_semantic_layer.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_semantic_layer.py`:

```python
from dart_footing_reconciler.document import (
    FullReport,
    ReportBlock,
    ReportSection,
    ReportTable,
    SourceLocation,
)
from dart_footing_reconciler.semantic_layer import build_semantic_dataset


def _section(section_id: str, title: str, kind: str, note_no: str, table: ReportTable) -> ReportSection:
    return ReportSection(
        section_id,
        title,
        kind,
        note_no,
        [ReportBlock("table", "", table, table.location)],
    )


def _table(section_id: str, index: int, rows: list[list[str]], heading: str) -> ReportTable:
    return ReportTable(index, rows, heading, SourceLocation(section_id, 0, index))


def test_semantic_dataset_attaches_signatures_to_company_specific_tables():
    rows = [
        ["구분", "금액"],
        ["기초장부금액", "1,000"],
        ["취득", "200"],
        ["기말장부금액", "1,200"],
    ]
    report_a = FullReport(
        "a.html",
        "A사",
        [],
        [_section("note:11", "유형자산", "note", "11", _table("note:11", 0, rows, "11. 유형자산"))],
    )
    report_b = FullReport(
        "b.html",
        "B사",
        [],
        [_section("note:44", "유형자산", "note", "44", _table("note:44", 3, rows, "44. 유형자산"))],
    )

    dataset_a = build_semantic_dataset(report_a)
    dataset_b = build_semantic_dataset(report_b)

    assert dataset_a.company == "A사"
    assert dataset_b.company == "B사"
    assert dataset_a.tables[0].source == "note:11/table:0"
    assert dataset_b.tables[0].source == "note:44/table:3"
    assert {match.signature for match in dataset_a.tables[0].signatures} == {
        match.signature for match in dataset_b.tables[0].signatures
    }
    assert "rollforward_axis" in {match.signature for match in dataset_a.tables[0].signatures}
    assert [fact.label for fact in dataset_a.amount_facts] == ["기초장부금액", "취득", "기말장부금액"]
    assert dataset_a.amount_facts[0].cell_source == "note:11/table:0/row:1/col:1"


def test_semantic_dataset_exposes_report_order_lookup():
    report = FullReport(
        "sample.html",
        "Sample",
        [],
        [
            _section("note:20", "후순위 주석", "note", "20", _table("note:20", 0, [["구분", "당기"], ["합계", "1"]], "20")),
            _section("note:3", "선행 후순위 번호", "note", "3", _table("note:3", 1, [["구분", "당기"], ["합계", "1"]], "3")),
        ],
    )

    dataset = build_semantic_dataset(report)

    assert [table.source for table in dataset.tables] == ["note:20/table:0", "note:3/table:1"]
    assert dataset.table_for_source("note:3/table:1/row:1/col:1").note_no == "3"
    assert dataset.amount_facts_for_table("note:3/table:1")
    assert dataset.table_for_source("missing") is None
```

- [ ] **Step 2: Run RED**

Run:

```bash
uv run pytest tests/test_semantic_layer.py -q
```

Expected: import failure for `dart_footing_reconciler.semantic_layer`.

- [ ] **Step 3: Implement `semantic_layer.py`**

Create `src/dart_footing_reconciler/semantic_layer.py`:

```python
"""Semantic dataset layer over parsed DART report tables."""

from __future__ import annotations

from dataclasses import dataclass

from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.document import FullReport, ReportSection, ReportTable
from dart_footing_reconciler.report_order import build_report_order_index
from dart_footing_reconciler.signatures import SignatureMatch, emit_signatures
from dart_footing_reconciler.table_semantics import compact


@dataclass(frozen=True)
class SemanticTable:
    company: str
    source: str
    order: int
    section_kind: str
    statement_kind: str
    section_id: str
    section_title: str
    note_no: str
    table_index: int
    heading: str
    row_count: int
    column_count: int
    unit_multiplier: int
    headers: tuple[str, ...]
    row_labels: tuple[str, ...]
    signatures: tuple[SignatureMatch, ...]


@dataclass(frozen=True)
class SemanticAmountFact:
    fact_id: str
    table_source: str
    cell_source: str
    label: str
    amount: int
    period: str
    role: str
    account_key: str | None
    confidence: float


@dataclass(frozen=True)
class SemanticDataset:
    company: str
    tables: tuple[SemanticTable, ...]
    amount_facts: tuple[SemanticAmountFact, ...]
    _tables_by_source: dict[str, SemanticTable]
    _amount_facts_by_table: dict[str, tuple[SemanticAmountFact, ...]]

    def table_for_source(self, source: str) -> SemanticTable | None:
        table_source = _table_source_for(source)
        if not table_source:
            return None
        return self._tables_by_source.get(table_source)

    def amount_facts_for_table(self, source: str) -> tuple[SemanticAmountFact, ...]:
        table_source = _table_source_for(source) or source
        return self._amount_facts_by_table.get(table_source, ())


def build_semantic_dataset(report: FullReport) -> SemanticDataset:
    order_index = build_report_order_index(report)
    raw_tables = _raw_tables_by_source(report)
    semantic_tables: list[SemanticTable] = []
    amount_facts: list[SemanticAmountFact] = []

    for entry in order_index.entries:
        table = raw_tables.get(entry.source)
        if table is None:
            continue
        semantic_tables.append(
            SemanticTable(
                company=report.company,
                source=entry.source,
                order=entry.order,
                section_kind=entry.section_kind,
                statement_kind=entry.statement_kind,
                section_id=entry.section_id,
                section_title=entry.section_title,
                note_no=entry.note_no,
                table_index=entry.table_index,
                heading=table.heading,
                row_count=len(table.rows),
                column_count=max((len(row) for row in table.rows), default=0),
                unit_multiplier=table.unit_multiplier,
                headers=tuple(table.rows[0]) if table.rows else (),
                row_labels=tuple(row[0] for row in table.rows[1:] if row),
                signatures=tuple(emit_signatures(table)),
            )
        )
        amount_facts.extend(_amount_facts_for_table(entry.source, table))

    return SemanticDataset(
        company=report.company,
        tables=tuple(semantic_tables),
        amount_facts=tuple(amount_facts),
        _tables_by_source={table.source: table for table in semantic_tables},
        _amount_facts_by_table=_group_amount_facts_by_table(amount_facts),
    )


def _raw_tables_by_source(report: FullReport) -> dict[str, ReportTable]:
    tables: dict[str, ReportTable] = {}
    for section in [*report.statements, *report.notes]:
        for table in _section_tables(section):
            tables[f"{section.section_id}/table:{table.index}"] = table
    return tables


def _section_tables(section: ReportSection) -> list[ReportTable]:
    return [
        block.table
        for block in section.blocks
        if block.table is not None and getattr(block.table, "rows", None)
    ]


def _table_source_for(source: str) -> str:
    if "/table:" not in source:
        return ""
    prefix, tail = source.split("/table:", 1)
    table_index = tail.split("/", 1)[0]
    return f"{prefix}/table:{table_index}"


def _amount_facts_for_table(table_source: str, table: ReportTable) -> list[SemanticAmountFact]:
    if not table.rows:
        return []
    headers = table.rows[0]
    facts: list[SemanticAmountFact] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if not row:
            continue
        label = row[0]
        for col_idx in range(1, len(row)):
            amount = parse_amount(row[col_idx])
            if amount is None:
                continue
            cell_source = f"{table_source}/row:{row_idx}/col:{col_idx}"
            facts.append(
                SemanticAmountFact(
                    fact_id=f"{table_source}:r{row_idx}:c{col_idx}",
                    table_source=table_source,
                    cell_source=cell_source,
                    label=label,
                    amount=amount,
                    period=_period_for_column(headers, col_idx),
                    role=_role_for_label(label),
                    account_key=None,
                    confidence=0.80,
                )
            )
    return facts


def _period_for_column(headers: list[str], col_idx: int) -> str:
    if col_idx >= len(headers):
        return "unknown"
    normalized = compact(headers[col_idx])
    if normalized in {"당기", "당기말", "당년도", "당기말현재"}:
        return "current"
    if normalized in {"전기", "전기말", "전년도", "전기말현재"}:
        return "prior"
    if "당기" in normalized:
        return "current"
    if "전기" in normalized:
        return "prior"
    return "unknown"


def _role_for_label(label: str) -> str:
    normalized = compact(label)
    if normalized.startswith("기초") or normalized in {"전기말", "전기말잔액"}:
        return "beginning"
    if normalized.startswith("기말") or normalized in {"당기말", "당기말잔액"}:
        return "ending"
    if normalized in {"합계", "소계", "총계", "계"}:
        return "total"
    return "movement"


def _group_amount_facts_by_table(
    facts: list[SemanticAmountFact],
) -> dict[str, tuple[SemanticAmountFact, ...]]:
    grouped: dict[str, list[SemanticAmountFact]] = {}
    for fact in facts:
        grouped.setdefault(fact.table_source, []).append(fact)
    return {source: tuple(items) for source, items in grouped.items()}
```

- [ ] **Step 4: Run GREEN**

Run:

```bash
uv run pytest tests/test_semantic_layer.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/dart_footing_reconciler/semantic_layer.py tests/test_semantic_layer.py
git commit -m "feat: build signature-backed semantic dataset"
```

---

### Task 5: Semantic Attempt Registry

**Files:**
- Create: `src/dart_footing_reconciler/semantic_attempts.py`
- Create: `tests/test_semantic_attempts.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_semantic_attempts.py`:

```python
from dart_footing_reconciler.semantic_attempts import (
    SEMANTIC_ATTEMPTS,
    attempts_for_signatures,
)
from dart_footing_reconciler.signatures import SignatureMatch


def test_attempt_registry_has_no_company_or_layout_routing_fields():
    for attempt in SEMANTIC_ATTEMPTS:
        assert not hasattr(attempt, "company")
        assert not hasattr(attempt, "layout_key")
        assert attempt.required_signatures
        assert attempt.layer in {"statement_note", "note_internal", "statement_cross"}
        assert attempt.axis in {
            "internal",
            "note_to_note",
            "note_to_bs",
            "note_to_pl",
            "note_to_sce",
            "note_to_cf",
            "statement_to_statement",
        }


def test_attempts_are_selected_by_signature_confidence():
    attempts = attempts_for_signatures(
        (
            SignatureMatch("internal_closure", 0.85, {"axis": "row"}),
            SignatureMatch("rollforward_axis", 0.75, {"degree": "minimal"}),
        )
    )

    ids = {attempt.attempt_id for attempt in attempts}
    assert "internal_table_total" in ids
    assert "rollforward_internal_formula" in ids
    internal_attempts = [
        attempt
        for attempt in attempts
        if attempt.attempt_id in {"internal_table_total", "rollforward_internal_formula"}
    ]
    assert {attempt.layer for attempt in internal_attempts} == {"note_internal"}


def test_low_confidence_signature_does_not_trigger_attempt():
    attempts = attempts_for_signatures(
        (
            SignatureMatch("internal_closure", 0.2, {}),
            SignatureMatch("rollforward_axis", 0.2, {}),
        )
    )

    assert attempts == ()
```

- [ ] **Step 2: Run RED**

Run:

```bash
uv run pytest tests/test_semantic_attempts.py -q
```

Expected: import failure for `dart_footing_reconciler.semantic_attempts`.

- [ ] **Step 3: Implement `semantic_attempts.py`**

Create `src/dart_footing_reconciler/semantic_attempts.py`:

```python
"""Semantic verification attempt registry selected from signatures."""

from __future__ import annotations

from dataclasses import dataclass

from dart_footing_reconciler.signatures import SignatureMatch


@dataclass(frozen=True)
class SemanticAttemptSpec:
    attempt_id: str
    layer: str
    check_type: str
    axis: str
    handler_key: str
    required_signatures: tuple[str, ...]
    check_group: str
    attempt_minimum: float = 0.40
    matched_minimum: float = 0.70


SEMANTIC_ATTEMPTS: tuple[SemanticAttemptSpec, ...] = (
    SemanticAttemptSpec(
        attempt_id="statement_cross_ties",
        layer="statement_cross",
        check_type="statement_bs_equation",
        axis="statement_to_statement",
        handler_key="check_statement_ties",
        required_signatures=("statement_core_match",),
        check_group="재무제표 교차 검증",
        matched_minimum=0.90,
    ),
    SemanticAttemptSpec(
        attempt_id="internal_table_total",
        layer="note_internal",
        check_type="total_check",
        axis="internal",
        handler_key="check_table_totals",
        required_signatures=("internal_closure",),
        check_group="합계 검증",
    ),
    SemanticAttemptSpec(
        attempt_id="rollforward_internal_formula",
        layer="note_internal",
        check_type="note_layout_formula_check",
        axis="internal",
        handler_key="check_layout_formula_assertions",
        required_signatures=("rollforward_axis",),
        check_group="주석 내부/공식 검증",
    ),
    SemanticAttemptSpec(
        attempt_id="note_statement_balance",
        layer="statement_note",
        check_type="fs_note_match",
        axis="note_to_bs",
        handler_key="check_fs_note_matches",
        required_signatures=("statement_core_match",),
        check_group="재무제표-주석 대사",
    ),
    SemanticAttemptSpec(
        attempt_id="note_cashflow_bridge",
        layer="statement_note",
        check_type="cfs_note_match",
        axis="note_to_cf",
        handler_key="check_cfs_note_matches",
        required_signatures=("rollforward_axis", "statement_core_match"),
        check_group="현금흐름표-주석 대사",
        attempt_minimum=0.35,
    ),
)


def attempts_for_signatures(signatures: tuple[SignatureMatch, ...]) -> tuple[SemanticAttemptSpec, ...]:
    confidence_by_signature: dict[str, float] = {}
    for signature in signatures:
        confidence_by_signature[signature.signature] = max(
            confidence_by_signature.get(signature.signature, 0.0),
            signature.confidence,
        )

    selected: list[SemanticAttemptSpec] = []
    for attempt in SEMANTIC_ATTEMPTS:
        confidences = [
            confidence_by_signature.get(signature_name, 0.0)
            for signature_name in attempt.required_signatures
        ]
        if not confidences:
            continue
        if min(confidences) >= attempt.attempt_minimum:
            selected.append(attempt)
    return tuple(selected)
```

- [ ] **Step 4: Run GREEN**

Run:

```bash
uv run pytest tests/test_semantic_attempts.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/dart_footing_reconciler/semantic_attempts.py tests/test_semantic_attempts.py
git commit -m "feat: add signature-driven attempt registry"
```

---

### Task 6: Semantic Validation Placement

**Files:**
- Create: `src/dart_footing_reconciler/semantic_validation.py`
- Create: `tests/test_semantic_validation.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_semantic_validation.py`:

```python
from dart_footing_reconciler.checks import CheckEvidence, CheckResult
from dart_footing_reconciler.document import (
    FullReport,
    ReportBlock,
    ReportSection,
    ReportTable,
    SourceLocation,
)
from dart_footing_reconciler.semantic_validation import build_semantic_validation_report


def _section(section_id: str, title: str, kind: str, note_no: str, table: ReportTable) -> ReportSection:
    return ReportSection(section_id, title, kind, note_no, [ReportBlock("table", "", table, table.location)])


def _table(section_id: str, index: int) -> ReportTable:
    return ReportTable(index, [["구분", "당기"], ["합계", "100"]], section_id, SourceLocation(section_id, 0, index))


def _check(check_id: str, source: str) -> CheckResult:
    return CheckResult(
        check_id=check_id,
        check_type="total_check",
        status="matched",
        scope="report",
        note_no="",
        title=check_id,
        expected=100,
        actual=100,
        difference=0,
        tolerance=0,
        reason="matched",
        evidence=[CheckEvidence("합계", 100, source)],
    )


def test_semantic_validation_places_checks_in_company_report_order():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section("note:20", "먼저 나온 주석", "note", "20", _table("note:20", 0)),
            _section("note:3", "나중에 나온 주석", "note", "3", _table("note:3", 1)),
        ],
    )
    checks = [
        _check("second", "note:3/table:1/row:1/col:1"),
        _check("first", "note:20/table:0/row:1/col:1"),
    ]

    validation = build_semantic_validation_report(report, checks)

    assert [placement.check.check_id for placement in validation.placements] == ["first", "second"]
    assert validation.placements[0].table.source == "note:20/table:0"
    assert validation.placements[1].table.source == "note:3/table:1"


def test_semantic_validation_keeps_unplaced_checks_last():
    report = FullReport("sample.html", "Sample Co", [], [])
    validation = build_semantic_validation_report(report, [_check("orphan", "generated:no-source")])

    assert validation.placements[0].check.check_id == "orphan"
    assert validation.placements[0].table is None
    assert validation.placements[0].order is None


def test_semantic_validation_emits_note_internal_candidates():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [_section("note:9", "합계 주석", "note", "9", _table("note:9", 0))],
    )

    validation = build_semantic_validation_report(report, [])

    internal_candidates = [
        candidate
        for candidate in validation.candidates
        if candidate.layer == "note_internal"
    ]
    assert [candidate.attempt_id for candidate in internal_candidates] == ["internal_table_total"]
    assert internal_candidates[0].table_source == "note:9/table:0"
    assert internal_candidates[0].evidence_sources == ("note:9/table:0/row:1/col:1",)
```

- [ ] **Step 2: Run RED**

Run:

```bash
uv run pytest tests/test_semantic_validation.py -q
```

Expected: import failure for `dart_footing_reconciler.semantic_validation`.

- [ ] **Step 3: Implement `semantic_validation.py`**

Create `src/dart_footing_reconciler/semantic_validation.py`:

```python
"""Semantic validation report placement over existing CheckResult rows."""

from __future__ import annotations

from dataclasses import dataclass

from dart_footing_reconciler.checks import CheckResult
from dart_footing_reconciler.check_pipeline import assemble_report_checks
from dart_footing_reconciler.document import FullReport
from dart_footing_reconciler.semantic_attempts import SemanticAttemptSpec, attempts_for_signatures
from dart_footing_reconciler.semantic_layer import SemanticDataset, SemanticTable, build_semantic_dataset


@dataclass(frozen=True)
class SemanticCheckPlacement:
    check: CheckResult
    table: SemanticTable | None
    order: int | None


@dataclass(frozen=True)
class SemanticValidationCandidate:
    candidate_id: str
    layer: str
    attempt_id: str
    check_type: str
    table_source: str
    evidence_sources: tuple[str, ...]
    confidence: float
    block_reason: str | None = None


@dataclass(frozen=True)
class SemanticValidationReport:
    dataset: SemanticDataset
    candidates: tuple[SemanticValidationCandidate, ...]
    placements: tuple[SemanticCheckPlacement, ...]
    attempts_by_source: dict[str, tuple[SemanticAttemptSpec, ...]]


def run_semantic_validation(
    report: FullReport,
    prior_report: FullReport | None,
    *,
    tolerance: int,
) -> SemanticValidationReport:
    checks = assemble_report_checks(report, prior_report, tolerance=tolerance)
    return build_semantic_validation_report(report, checks)


def build_semantic_validation_report(
    report: FullReport,
    checks: list[CheckResult],
) -> SemanticValidationReport:
    dataset = build_semantic_dataset(report)
    attempts_by_source = {
        table.source: attempts_for_signatures(table.signatures)
        for table in dataset.tables
    }
    candidates = tuple(
        candidate
        for table in dataset.tables
        for candidate in _candidates_for_table(
            dataset,
            table,
            attempts_by_source.get(table.source, ()),
        )
    )
    placements = tuple(sorted(
        (_placement(dataset, check) for check in checks),
        key=_placement_sort_key,
    ))
    return SemanticValidationReport(
        dataset=dataset,
        candidates=candidates,
        placements=placements,
        attempts_by_source=attempts_by_source,
    )


def _candidates_for_table(
    dataset: SemanticDataset,
    table: SemanticTable,
    attempts: tuple[SemanticAttemptSpec, ...],
) -> tuple[SemanticValidationCandidate, ...]:
    facts = dataset.amount_facts_for_table(table.source)
    evidence_sources = tuple(fact.cell_source for fact in facts)
    candidates: list[SemanticValidationCandidate] = []
    for attempt in attempts:
        confidences = [
            signature.confidence
            for signature in table.signatures
            if signature.signature in attempt.required_signatures
        ]
        confidence = min(confidences) if confidences else 0.0
        candidates.append(
            SemanticValidationCandidate(
                candidate_id=f"{table.source}:{attempt.attempt_id}",
                layer=attempt.layer,
                attempt_id=attempt.attempt_id,
                check_type=attempt.check_type,
                table_source=table.source,
                evidence_sources=evidence_sources,
                confidence=confidence,
                block_reason=None if evidence_sources else "no amount facts",
            )
        )
    return tuple(candidates)


def _placement(dataset: SemanticDataset, check: CheckResult) -> SemanticCheckPlacement:
    for evidence in check.evidence:
        table = dataset.table_for_source(evidence.source)
        if table is not None:
            return SemanticCheckPlacement(check=check, table=table, order=table.order)
    return SemanticCheckPlacement(check=check, table=None, order=None)


def _placement_sort_key(placement: SemanticCheckPlacement) -> tuple[int, int, str]:
    if placement.order is None:
        return (1, 999_999_999, placement.check.check_id)
    return (0, placement.order, placement.check.check_id)
```

- [ ] **Step 4: Run GREEN**

Run:

```bash
uv run pytest tests/test_semantic_validation.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/dart_footing_reconciler/semantic_validation.py tests/test_semantic_validation.py
git commit -m "feat: place validation checks by semantic report order"
```

---

### Task 7: Wire Report Frame To Report Order

**Files:**
- Modify: `src/dart_footing_reconciler/report_frame.py`
- Modify: `tests/test_report_frame.py`

- [ ] **Step 1: Add failing report-frame test**

Append to `tests/test_report_frame.py`:

```python
def test_report_frame_preserves_parsed_note_order_not_numeric_sort():
    first_note = _section(
        "note:20",
        "먼저 나온 주석",
        "note",
        "20",
        _table("note:20", 0, "20. 먼저 나온 주석"),
    )
    second_note = _section(
        "note:3",
        "나중에 나온 주석",
        "note",
        "3",
        _table("note:3", 1, "3. 나중에 나온 주석"),
    )

    frame = build_report_frame(
        FullReport("sample.html", "Sample Co", [], [first_note, second_note]),
        [],
    )

    assert [note.note_no for note in frame.notes] == ["20", "3"]
```

- [ ] **Step 2: Run RED**

Run:

```bash
uv run pytest tests/test_report_frame.py::test_report_frame_preserves_parsed_note_order_not_numeric_sort -q
```

Expected: failure because current `build_report_frame` sorts notes by `_note_section_sort_key`, which returns `["3", "20"]`.

- [ ] **Step 3: Modify `report_frame.py` note iteration**

In `src/dart_footing_reconciler/report_frame.py`, replace this loop:

```python
    for section in sorted(report.notes, key=_note_section_sort_key):
```

with:

```python
    for section in report.notes:
```

Keep `_note_section_sort_key` for compatibility if any other local function still uses it. Remove it only after `rg "_note_section_sort_key"` shows no references and tests pass.

- [ ] **Step 4: Run GREEN**

Run:

```bash
uv run pytest tests/test_report_frame.py::test_report_frame_preserves_parsed_note_order_not_numeric_sort -q
uv run pytest tests/test_report_frame.py -q
```

Expected: the new test passes and existing report-frame tests stay green.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/dart_footing_reconciler/report_frame.py tests/test_report_frame.py
git commit -m "fix: preserve parsed note order in report frame"
```

---

### Task 8: Full Verification And Corpus Smoke

**Files:**
- Modify: `HANDOFF.md`

- [ ] **Step 1: Run focused semantic tests**

Run:

```bash
uv run pytest \
  tests/test_report_order.py \
  tests/test_essential_notes.py \
  tests/test_semantic_layer.py \
  tests/test_semantic_attempts.py \
  tests/test_semantic_validation.py \
  tests/test_report_frame.py \
  -q
```

Expected: all listed tests pass.

- [ ] **Step 2: Run full test suite**

Run:

```bash
uv run pytest -q
```

Expected: full suite passes. At handoff time the focused baseline was 43 tests; the full count may differ as agents add tests.

- [ ] **Step 3: Run one-company corpus smoke**

Run:

```bash
uv run dart-footing workpaper-corpus \
  out/corpus/manifest_2026-06-06-inveni-one.json \
  out/corpus/run_2026-06-10-semantic-report-verification-smoke \
  --no-fetch
```

Expected command output includes:

```text
Generated reports: 1/1
```

Open generated files:

```bash
sed -n '1,120p' out/corpus/run_2026-06-10-semantic-report-verification-smoke/corpus_report.md
test -f out/corpus/run_2026-06-10-semantic-report-verification-smoke/reports/inveni_2024.html
```

Expected:

- `corpus_report.md` exists.
- HTML report exists.
- Report sections still render in statement/note order.
- No new `failed_samples`.
- `corpus_report.md` records failed samples as `0`.

- [ ] **Step 4: Run 100-company no-fetch corpus gate when cache is available**

Run:

```bash
uv run dart-footing workpaper-corpus \
  out/corpus/manifest_2026-05-31-cached-from-accuracy-v1.json \
  out/corpus/run_2026-06-10-semantic-report-verification-100 \
  --no-fetch
```

Expected:

- Generated reports: `100/100`
- Failed samples: `0`
- Primary no-difference rate does not decrease because this plan is ordering/semantic plumbing, not arithmetic matching expansion.
- Newly unresolved primary IDs: `0`

- [ ] **Step 5: Append HANDOFF implementation note**

Append under the latest implementation slice in `HANDOFF.md`:

```markdown
- Latest implementation slice: semantic report verification layer now indexes company reports in statement/note order, attaches signature-backed semantic table metadata and amount facts, emits `statement_note` and `note_internal` candidates without company/layout routing, and places existing CheckResult rows back onto the source report sequence. Verification passed with focused semantic tests and full `uv run pytest`. One-company INVENI corpus smoke generated 1/1 reports with 0 failed samples.
```

- [ ] **Step 6: Commit**

Run:

```bash
git add HANDOFF.md
git commit -m "docs: record semantic verification layer handoff"
```

---

## Acceptance Criteria

- New semantic layer can represent two different companies with different note numbers/table indexes and still emit the same signature-backed verification semantics.
- Semantic dataset exposes table-local `SemanticAmountFact` rows with exact cell source locations for material parsed amounts.
- Attempt selection is driven only by signatures and confidence thresholds, not company name, industry code, or layout key.
- V1 semantic validation emits `statement_note` and `note_internal` candidates. `internal_table_total` and `rollforward_internal_formula` are first-class `note_internal` candidates.
- Existing `assemble_report_checks` behavior remains available and full tests pass.
- `build_semantic_validation_report` orders checks by source report sequence and keeps unplaced/generated checks visible at the end.
- `build_semantic_validation_report` exposes `candidates` so harnesses can consume semantic candidates without re-deriving table signatures.
- `report_frame.build_report_frame` preserves parsed note order so the reviewer sees validation results in the company report sequence.
- No closest-value matching is introduced.
- `uv run pytest -q` passes before handoff.

## Self-Review

- Spec coverage: company-specific datasets are handled by `SemanticDataset`; source-backed amount facts are handled by `SemanticAmountFact`; generic semantic dispatch is handled by `semantic_attempts.py`; candidate emission and report-sequence output are handled by `semantic_validation.py`; rendered order is handled by `report_order.py` and `report_frame.py`.
- Placeholder scan: no `TBD`, no unbounded "handle edge cases", no company-specific branch instructions.
- Type consistency: `SemanticTable.source`, `SemanticAmountFact.table_source`, and `SemanticValidationCandidate.table_source` use the existing `section_id/table:index` source contract; `SemanticCheckPlacement.table` is nullable only for generated/unplaced checks; `SemanticAttemptSpec` has no company/layout routing fields and now carries an explicit `layer`.
- Risk: `report_frame.py` note ordering change is user-visible. The new test intentionally encodes the requirement that validation report order borrows the parsed company report order.
