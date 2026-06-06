# Layout-Aware Target Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** For a single company report, derive verifiable target values and reconciliation formulas from all note tables even when companies vary row/column orientation, header wording, period columns, and display units.

**Architecture:** Extend the full-note inventory foundation into a layout-aware extraction layer. The layer first detects table orientation and unit scope, then emits normalized verification candidates with source locations, selected row/column coordinates, layout evidence, and formula roles. Existing footing and reconciliation engines should consume these candidates rather than re-discovering table semantics ad hoc.

**Tech Stack:** Python dataclasses, existing `FullReport` document model, `note_inventory.py`, `layout_variants.py`, `table_semantics.py`, `reconciliation_inputs.py`, pytest.

---

## Problem Statement

The engine cannot assume that a company presents a verification target in one stable table shape. The same business fact may appear as:

- row-oriented: rows are movement roles such as `기초`, `취득`, `처분`, `기말`, while columns are asset classes or `합계`;
- column-oriented: rows are asset classes, while columns are measures such as `취득원가`, `감가상각누계액`, `정부보조금`, `장부금액`, `합계`;
- period-oriented: columns are `당기`, `전기`, `제 56 기`, `제 55 기`;
- measure-oriented: columns or rows are `장부금액`, `순장부금액`, `취득원가`, `상각누계액`, `손상차손누계액`;
- unit-variant: amounts may be in 원, 천원, 백만원, or another display unit declared near the table.

Therefore the next implementation must not add one-off company branches. It must produce normalized, source-backed candidate values that explain:

1. which table layout was detected,
2. which row and column supplied the amount,
3. which display unit multiplier was applied,
4. which formula role the amount plays,
5. whether the evidence is strong enough to enter a `matched` formula.

## Audit-Grade Success Criteria

1. **Orientation detection:** Each note table can be classified as row-oriented, column-oriented, period-oriented, mixed, or unknown. Unknown orientation is preserved and surfaced, not silently ignored.
2. **Unit normalization:** Every extracted amount records raw display amount, unit multiplier, normalized amount, and source of the unit assumption.
3. **Target candidate extraction:** For known layouts, the engine emits `VerificationCandidate` records for balances, movements, totals, and formula adjustments.
4. **Formula target discovery:** For a single report, the engine can derive candidate formulas such as `beginning + additions - depreciation - disposals = ending`, `note balance = statement balance`, or `selected components = displayed total` from candidate roles.
5. **No materiality pass/fail:** A formula is `matched` only when it closes exactly or within display-unit tolerance. Materiality may rank review work later but cannot make a gap pass.
6. **Layout-gated evidence:** Unknown or low-confidence layout candidates cannot be used as matched evidence. They must produce `parse_uncertain` or coverage backlog entries.
7. **Source preservation:** Every candidate and formula term preserves `note_no`, table source, row index, column index, label, raw amount, normalized amount, layout key, and layout evidence.
8. **One-company completeness:** A one-company diagnostic command can show: all tables, detected orientation, extracted candidates, generated formulas, matched formulas, parse-uncertain formulas, and unextractable tables.
9. **Regression safety:** Existing `uv run pytest` remains green. Existing cash-flow reconciliation and footing remain separate checks.

## New Concepts

### `TableOrientation`

Represents how table semantics are organized:

```python
@dataclass(frozen=True)
class TableOrientation:
    key: str  # row_oriented | column_oriented | period_oriented | mixed | unknown
    confidence: float
    evidence: tuple[str, ...]
```

### `VerificationCandidate`

Represents one normalized amount that may participate in a verification formula:

```python
@dataclass(frozen=True)
class VerificationCandidate:
    account_key: str
    role: str
    label: str
    raw_amount: int
    unit_multiplier: int
    amount: int
    note_no: str
    table_source: str
    row_index: int
    column_index: int
    layout_key: str
    orientation_key: str
    confidence: float
    evidence: tuple[str, ...]
```

### `VerificationFormula`

Represents a candidate formula generated from extracted values:

```python
@dataclass(frozen=True)
class VerificationFormula:
    formula_key: str
    target_role: str
    expected: int
    actual: int
    difference: int
    tolerance: int
    status: str
    terms: tuple[VerificationCandidate, ...]
    reason: str
```

## File Structure

- Create `src/dart_footing_reconciler/orientation.py`
  - Detects row/column/period/mixed/unknown orientation from headers and row labels.
- Create `src/dart_footing_reconciler/verification_candidates.py`
  - Emits normalized amount candidates from `NoteTableInventoryItem`, parsed report tables, layout classification, orientation, and unit multiplier.
- Create `src/dart_footing_reconciler/formula_discovery.py`
  - Generates source-backed formulas from candidates.
- Modify `src/dart_footing_reconciler/reconciliation_inputs.py`
  - Start attaching layout/orientation metadata to note balance and movement inputs.
- Modify `src/dart_footing_reconciler/coverage.py`
  - Include orientation counts and candidate extraction counts.
- Modify `src/dart_footing_reconciler/cli.py`
  - Add a diagnostic command, tentatively `candidate-report`, for one company.
- Create `tests/test_orientation.py`
- Create `tests/test_verification_candidates.py`
- Create `tests/test_formula_discovery.py`
- Extend `tests/test_reconciliation_inputs.py`
- Extend `tests/test_cli.py`

## Task 1: Orientation Detection

**Files:**
- Create: `src/dart_footing_reconciler/orientation.py`
- Test: `tests/test_orientation.py`

- [ ] **Step 1: Write tests for row, column, period, and unknown orientation**

Test examples:

```python
def test_detects_row_oriented_rollforward():
    result = detect_orientation(
        headers=("구분", "토지", "건물", "합계"),
        row_labels=("기초", "취득", "감가상각", "기말"),
    )
    assert result.key == "row_oriented"
    assert result.confidence >= 0.8


def test_detects_column_oriented_asset_measure_table():
    result = detect_orientation(
        headers=("구분", "취득원가", "감가상각누계액", "정부보조금", "합계"),
        row_labels=("토지", "건물", "합계"),
    )
    assert result.key == "column_oriented"
    assert result.confidence >= 0.8


def test_detects_period_oriented_table():
    result = detect_orientation(
        headers=("구분", "당기", "전기"),
        row_labels=("장부금액", "취득"),
    )
    assert result.key == "period_oriented"
    assert result.confidence >= 0.75


def test_unknown_orientation_is_preserved():
    result = detect_orientation(
        headers=("구분", "내용"),
        row_labels=("회사", "주소"),
    )
    assert result.key == "unknown"
    assert result.confidence == 0.0
```

- [ ] **Step 2: Implement deterministic orientation rules**

Rules:

- row-oriented when movement labels appear in rows and amount/category labels appear in columns;
- column-oriented when measure labels appear in columns and entity/account labels appear in rows;
- period-oriented when current/prior period labels appear in columns;
- mixed when both movement labels and measure labels appear on both axes;
- unknown when evidence is insufficient.

- [ ] **Step 3: Verify**

Run:

```bash
uv run pytest tests/test_orientation.py -q
```

Expected: PASS.

## Task 2: Verification Candidate Extraction

**Files:**
- Create: `src/dart_footing_reconciler/verification_candidates.py`
- Test: `tests/test_verification_candidates.py`

- [ ] **Step 1: Write tests for normalized amount candidates**

Required cases:

- row-oriented roll-forward with `합계` column;
- column-oriented table with `정부보조금` and `합계`;
- period-oriented table with `당기` and `전기`;
- unit multiplier `1000` or `1_000_000`;
- unknown orientation returns no matched-eligible candidates and records parse uncertainty.

Example:

```python
def test_extracts_row_oriented_rollforward_candidates_with_unit_multiplier():
    table = ReportTable(
        0,
        [
            ["구분", "토지", "합계"],
            ["기초", "100", "100"],
            ["취득", "50", "50"],
            ["기말", "150", "150"],
        ],
        "11. 유형자산",
        SourceLocation("note:11", 0, 0),
        unit_multiplier=1000,
    )

    candidates = extract_verification_candidates(
        note_no="11",
        title="유형자산",
        table=table,
        layout=LayoutClassification("asset_current_period_carrying_amount", 0.75, ("layout",), "note:11/table:0"),
        orientation=TableOrientation("row_oriented", 0.9, ("movement labels in rows",)),
    )

    ending = next(candidate for candidate in candidates if candidate.role == "ending")
    assert ending.raw_amount == 150
    assert ending.unit_multiplier == 1000
    assert ending.amount == 150_000
    assert ending.table_source == "note:11/table:0"
    assert ending.row_index == 3
    assert ending.column_index == 2
```

- [ ] **Step 2: Implement extraction by orientation**

Extraction rules:

- row-oriented:
  - select total/current amount column using `table_semantics.balance_amount` and known total aliases;
  - classify rows into roles: beginning, additions, disposals, depreciation, amortization, impairment, transfer, ending.
- column-oriented:
  - select measure columns by header roles;
  - classify rows into account/entity labels;
  - for total rows, emit balance candidates from `합계`, `장부금액`, or net measure columns.
- period-oriented:
  - select current-period columns using `current_period_columns`;
  - emit current amount candidates while preserving prior-period availability for later prior-year checks.
- unknown:
  - emit no matched-eligible candidates;
  - return uncertainty metadata for coverage/reporting.

- [ ] **Step 3: Verify**

Run:

```bash
uv run pytest tests/test_verification_candidates.py -q
```

Expected: PASS.

## Task 3: Formula Discovery From Candidates

**Files:**
- Create: `src/dart_footing_reconciler/formula_discovery.py`
- Test: `tests/test_formula_discovery.py`

- [ ] **Step 1: Write tests for internal formula generation**

Required formulas:

- roll-forward footing: `beginning + additions - depreciation - disposals + transfers = ending`;
- displayed total: `component sum = displayed total`;
- note-to-statement: `note ending = statement line`;
- formula blocked by low-confidence/unknown layout.

Example:

```python
def test_discovers_rollforward_formula_from_candidates():
    formula = discover_rollforward_formula(
        [
            candidate("beginning", 100),
            candidate("additions", 50),
            candidate("depreciation", -10),
            candidate("ending", 140),
        ],
        tolerance=0,
    )

    assert formula.status == "matched"
    assert formula.expected == 140
    assert formula.actual == 140
    assert formula.difference == 0
```

- [ ] **Step 2: Implement formula selection**

Rules:

- only use candidates with known layout and sufficient confidence;
- use explicit role signs rather than label string sign guessing;
- when multiple candidate formulas compete, choose the one with exact closure and strongest evidence;
- if no formula closes, return `unexplained_gap`;
- if target or required role is ambiguous due to layout/orientation, return `parse_uncertain`.

- [ ] **Step 3: Verify**

Run:

```bash
uv run pytest tests/test_formula_discovery.py -q
```

Expected: PASS.

## Task 4: Attach Layout Metadata To Existing Reconciliation Inputs

**Files:**
- Modify: `src/dart_footing_reconciler/reconciliation_inputs.py`
- Test: `tests/test_reconciliation_inputs.py`

- [ ] **Step 1: Extend input dataclasses**

Add fields to `NoteBalanceInput` and `NoteMovementInput`:

```python
layout_key: str = ""
layout_confidence: float = 0.0
layout_evidence: tuple[str, ...] = ()
orientation_key: str = ""
orientation_confidence: float = 0.0
orientation_evidence: tuple[str, ...] = ()
```

- [ ] **Step 2: Add tests proving metadata survives extraction**

Test that a sample PPE note table produces a `NoteBalanceInput` with:

- `layout_key`;
- `orientation_key`;
- layout evidence;
- original amount source unchanged.

- [ ] **Step 3: Implement metadata plumbing**

Use `build_note_inventory`, `classify_layout`, and `detect_orientation` to create a lookup by `note:{note_no}/table:{index}`. When existing extraction emits balance/movement inputs, attach the matching metadata.

- [ ] **Step 4: Verify**

Run:

```bash
uv run pytest tests/test_reconciliation_inputs.py -q
```

Expected: PASS.

## Task 5: Diagnostic Candidate Report For One Company

**Files:**
- Modify: `src/dart_footing_reconciler/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Add a failing CLI test**

Command:

```bash
dart-footing candidate-report sample.html --company "Sample Co"
```

Expected output includes:

- company;
- total note tables;
- orientation counts;
- layout counts;
- extracted candidate count;
- generated formula count;
- parse-uncertain table count;
- unknown orientation table count.

- [ ] **Step 2: Implement `candidate-report`**

The command should parse one local HTML report, build note inventory, classify layout and orientation for all note tables, extract verification candidates, discover formulas, and print a compact text summary.

- [ ] **Step 3: Verify**

Run:

```bash
uv run pytest tests/test_cli.py::test_cli_candidate_report_outputs_extraction_summary -v
```

Expected: PASS.

## Task 6: Unknown Layout And Orientation Backlog

**Files:**
- Modify: `src/dart_footing_reconciler/corpus.py`
- Test: `tests/test_corpus.py`

- [ ] **Step 1: Add corpus artifact tests**

Assert that `run_workpaper_corpus` writes:

- `unknown_layout_taxonomy.json`;
- `unknown_layout_taxonomy.md`.

Each item should include:

- company;
- note number;
- title;
- table source;
- headers;
- row labels sample;
- layout key;
- orientation key;
- reason.

- [ ] **Step 2: Implement artifact generation**

Aggregate unknown or low-confidence table classifications from each company report. Keep the artifact source-only; do not invent accounting conclusions.

- [ ] **Step 3: Verify**

Run:

```bash
uv run pytest tests/test_corpus.py -q
```

Expected: PASS.

## Task 7: Final Verification

**Files:**
- Modify: `HANDOFF.md`
- Modify: `docs/validation/2026-06-03-agent-work-integration-ledger.md`

- [ ] **Step 1: Run focused tests**

```bash
uv run pytest \
  tests/test_orientation.py \
  tests/test_layout_variants.py \
  tests/test_verification_candidates.py \
  tests/test_formula_discovery.py \
  tests/test_reconciliation_inputs.py \
  tests/test_cli.py \
  tests/test_corpus.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run full tests**

```bash
uv run pytest
```

Expected: PASS.

- [ ] **Step 3: Update handoff**

Record that layout-aware target extraction now converts table orientation, headers, and units into source-backed verification candidates and formulas. Explicitly state that materiality is not a pass/fail rule.

## Non-Goals

- Do not add company-name-specific extraction branches.
- Do not merge footing and cash-flow reconciliation checks.
- Do not treat materiality as a matching tolerance.
- Do not claim all unknown layouts are solved after this slice.
- Do not use low-confidence or unknown layout evidence to produce `matched`.

## Review Checklist

- Does every extracted amount preserve row, column, unit, note, table, and layout evidence?
- Can row-oriented and column-oriented tables both produce candidates?
- Can period-oriented tables choose current period without losing prior period context?
- Are unknown layouts visible as backlog?
- Are formulas generated from roles rather than raw label string arithmetic?
- Does the diagnostic report show what the engine saw before it claims a validation result?
