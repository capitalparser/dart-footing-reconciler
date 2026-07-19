# Narrative Note Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve table-adjacent narrative provenance and turn explicit footnote and cross-note statements into source-backed reconciliation evidence without inventing arithmetic.

**Architecture:** Extend `ReportBlock` with optional raw provenance, derive immutable narrative facts in a focused `narrative_evidence` module, and feed those facts into note-reference checks and HTML source routing. Keep deterministic parsing in the core package; Luna's multi-company investigation supplies fixtures and rules but no runtime agent dependency.

**Tech Stack:** Python 3.11, BeautifulSoup/lxml, dataclasses, regular expressions, pytest, standalone HTML/CSS/JavaScript.

## Global Constraints

- Do not run git commands.
- The core reconciliation engine must run without MCP or an agent.
- Parser changes require fixture coverage for source location and uncertainty.
- Preserve report block order and existing table source strings.
- Include connection scope in narrative source keys.
- Do not interpret limits, collateral, included amounts, dates, standard numbers, ratios, or note numbers as statement balances.
- Use TDD for every task.

---

### Task 1: Preserve narrative block provenance

**Files:**
- Modify: `src/dart_footing_reconciler/document.py:30-45`
- Modify: `src/dart_footing_reconciler/document.py:100-275`
- Modify: `src/dart_footing_reconciler/document.py:388-392`
- Test: `tests/test_document.py`

**Interfaces:**
- Produces: optional `ReportBlock.raw_text`, `text_segments`, `html_line`, `raw_tag`, and `wrapper_class` fields with backward-compatible defaults.

- [ ] **Step 1: Add failing parser tests**

Create a synthetic DART fragment with a data table followed by `<table class="nb"><tr><td><p>(*1) 포함 금액</p><p>(*2) 제외 금액<br>1-3 다음 제목</p></td></tr></table>`. Assert:

```python
text_blocks = [block for block in report.notes[0].blocks if block.kind == "text"]
assert text_blocks[0].raw_text == "(*1) 포함 금액"
assert text_blocks[0].raw_tag == "p"
assert text_blocks[0].wrapper_class == "nb"
assert text_blocks[1].text_segments == ("(*2) 제외 금액", "1-3 다음 제목")
assert text_blocks[0].location.block_index > report.notes[0].blocks[0].location.block_index
```

- [ ] **Step 2: Run the parser test and confirm RED**

Expected: FAIL because `ReportBlock` has no provenance fields.

- [ ] **Step 3: Add backward-compatible fields and node-aware append**

Use:

```python
@dataclass(frozen=True)
class ReportBlock:
    kind: str
    text: str
    table: ReportTable | None
    location: SourceLocation
    raw_text: str = ""
    text_segments: tuple[str, ...] = ()
    html_line: int | None = None
    raw_tag: str = ""
    wrapper_class: str = ""
```

Change `_append_text` to accept `node: Tag | None = None`, compute newline-separated segments with `node.get_text("\n", strip=True)`, and find the nearest parent table class. Existing synthetic constructors remain valid because every new field has a default.

- [ ] **Step 4: Verify parser and existing document tests**

Run `uv run pytest -q tests/test_document.py tests/test_local_report.py`. Expected: PASS.

### Task 2: Build deterministic narrative facts and attachments

**Files:**
- Create: `src/dart_footing_reconciler/narrative_evidence.py`
- Create: `tests/test_narrative_evidence.py`

**Interfaces:**
- Produces: `NarrativeSource`, `NarrativeSegment`, `NarrativeAttachment`, `NarrativeNoteReference`, `NarrativeAmountMention`, `NarrativeEvidenceDataset`, and `build_narrative_evidence(report)`.

- [ ] **Step 1: Write failing fact extraction tests**

Cover exact marker matching, markerless `상기` weak attachment, heading split, forward unit text, approval disclaimer exclusion, explicit cross-note reference, and safe amount roles. Required assertions include:

```python
dataset = build_narrative_evidence(report)
assert dataset.segments[0].source.source_key == "note:15@consolidated/block:1/segment:0"
assert dataset.attachments[0].table_source == "note:15/table:109"
assert dataset.attachments[0].confidence == 1.0
assert dataset.note_references[0].note_no == "46"
assert dataset.amount_mentions[0].role == "borrowing_transferred_by_merger"
assert dataset.amount_mentions[0].amount == 18_000_000_000
assert dataset.reconciliation_candidates_for(disclaimer_source) == ()
```

- [ ] **Step 2: Confirm the module import fails**

Run `uv run pytest -q tests/test_narrative_evidence.py`. Expected: collection ERROR for missing module, proving the new contract is active.

- [ ] **Step 3: Implement source and segment splitting**

Define immutable dataclasses. Create scope-aware source keys, split `text_segments` again at `1-3`, `(2)`, `가.`, and `나.` headings, and retain character spans relative to normalized segment text.

- [ ] **Step 4: Implement attachment rules**

Walk each section's blocks in order. Exact normalized marker equality creates confidence `1.0`; markerless backward words plus a shared substantive noun create confidence `0.7`; approval disclaimers create no reconciliation attachment. Stop at a new table or section boundary.

- [ ] **Step 5: Implement safe references and amounts**

Reuse `extract_note_ref_tokens` only in explicit reference context. Require an amount unit and a role token in the same segment. Map role tokens to typed roles such as `borrowing_limit`, `collateral_amount`, `included_amount`, `internal_transactions_not_eliminated`, `transferred_amount`, and `replacement_amount`. Reject dates, percentages, standards, and note markers.

- [ ] **Step 6: Verify the focused fact suite**

Run `uv run pytest -q tests/test_narrative_evidence.py`. Expected: PASS.

### Task 3: Add narrative evidence to note-reference checks

**Files:**
- Modify: `src/dart_footing_reconciler/checks_note_references.py`
- Modify: `src/dart_footing_reconciler/note_reference_validator.py`
- Modify: `tests/test_note_reference_validator.py`

**Interfaces:**
- Consumes: `NarrativeNoteReference` facts.
- Produces: `CheckEvidence` roles `narrative_reference` and `referenced_note`, scope-aware `consolidation_basis`, and preserved source text.

- [ ] **Step 1: Write failing evidence tests**

Assert one valid reference result contains:

```python
assert check.consolidation_basis == "consolidated"
assert [(e.role, e.source) for e in check.evidence] == [
    ("narrative_reference", "note:12@consolidated/block:7/segment:0"),
    ("referenced_note", "note:46@consolidated/block:0"),
]
assert check.evidence[0].label == original_sentence
```

Add duplicate note-number fixtures in connected and separate scopes and assert targets never cross scopes.

- [ ] **Step 2: Confirm existing evidence is empty**

Run the new node IDs. Expected: FAIL because current checks emit `evidence=[]` and unknown scope.

- [ ] **Step 3: Integrate facts and exact target resolution**

Build narrative evidence once in `check_note_references`, resolve the referenced note within the referring source's scope, use the first meaningful target block as `referenced_note`, and keep the existing status mapping for valid, missing, and empty notes.

- [ ] **Step 4: Verify note-reference and harness tests**

Run `uv run pytest -q tests/test_note_reference_validator.py tests/test_statement_note_harness.py tests/test_check_pipeline.py -k 'not corpus_and_workpaper_checks_are_identical and not assemble_'`.

### Task 4: Render narrative cards and exact block jumps

**Files:**
- Modify: `src/dart_footing_reconciler/report_html.py:580-625`
- Modify: `src/dart_footing_reconciler/report_html.py:1290-1435`
- Modify: `src/dart_footing_reconciler/report_html.py:2590-2650`
- Modify: `src/dart_footing_reconciler/report_html.py:2860-2920`
- Test: `tests/test_report_html_evidence.py`

**Interfaces:**
- Consumes: scope-aware narrative source keys and `CheckEvidence` roles.
- Produces: `source-narrative` cards, `data-source-block` anchors, and drawer/block jump buttons.

- [ ] **Step 1: Write failing HTML contracts**

Assert generated HTML includes:

```python
assert 'class="source-narrative"' in content
assert 'data-source-block="note:12@consolidated/block:7/segment:0"' in content
assert '<span class="source-narrative-marker">(*1)</span>' in content
assert 'data-jump-block="note:12@consolidated/block:7/segment:0"' in content
assert '>참조 주석 46<' in content
assert "원문 위치 확인 필요" not in content
```

- [ ] **Step 2: Confirm the HTML tests fail**

Expected: FAIL because text blocks are plain paragraphs and source parsing handles cells only.

- [ ] **Step 3: Route block sources**

Add `_parse_narrative_source`, route block evidence to the owning scope-aware panel, and extend source-jump JavaScript to locate `[data-source-block="..."]`, scroll it into view, and apply the existing flash class.

- [ ] **Step 4: Render narrative cards**

Replace plain post-table paragraphs with semantic cards only when facts attach them to a table. Render unattached prose as the existing neutral paragraph. Include marker, full sentence, relation label, and explicit referenced-note buttons. Do not label ordinary prose as verified.

- [ ] **Step 5: Verify HTML and browser behavior**

Run `uv run pytest -q tests/test_report_html_evidence.py tests/test_report_html_new.py`, then use Playwright CLI on synthetic and SK이터닉스 reports to check text and target jumps.

### Task 5: Multi-company regression and final QA

**Files:**
- Create or modify: `tests/test_narrative_evidence_real_fixtures.py`
- Regenerate: `output/sk_eternix/sk_eternix_2026_q1_audit_workbench.html`

**Interfaces:**
- Consumes: Luna's P0/P1/P2 fixture paths when present.
- Produces: generalized regression evidence without making external fixture availability a default-test requirement.

- [ ] **Step 1: Add P0/P1/P2 fixture cases**

Use `pytest.mark.skipif(not path.exists(), reason="external DART fixture unavailable")`. Pin section, block, table index, marker, attachment direction, scope, reference target, amount role, and reconciliation-candidate count for each accessible file.

- [ ] **Step 2: Run real-fixture tests where available**

Expected: SK이터닉스, 삼성SDI, 한국전력공사, CJ제일제당, 더존비즈온, 현대자동차, 대한항공, 한일시멘트, 아모레퍼시픽, and POSCO홀딩스 cases either PASS or explicitly SKIP for a missing file; no raw-file `FileNotFoundError` is allowed.

- [ ] **Step 3: Regenerate SK이터닉스 and inspect narrative cards**

Use the same `workpaper-html` command from the UI plan. Verify the note 1 table 6 sentence splits before `1-3`, retains the basis text, and does not create an arithmetic adjustment.

- [ ] **Step 4: Run final quality gates**

Run:

```bash
uv run ruff check src tests
uv run pytest -q
```

Report exact totals, any fixture skips, and any pre-existing missing external fixture failures separately.
