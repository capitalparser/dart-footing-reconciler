# Real Disclosure PDF Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Korean native-text business-report PDFs produce trustworthy statement sections and scope, while unsupported or semantically empty PDFs fail closed instead of generating a misleading workbench.

**Architecture:** Preserve PDF extraction and report parsing as separate stages. Add a PDF-only semantic success gate, then teach the existing document state machine to recognize exact PDF-native area boundaries without treating TOC tables or reference sentences as state transitions. Harden note headings contextually, and address mixed line/text table geometry independently after section semantics are stable.

**Tech Stack:** Python 3.11+, BeautifulSoup/lxml, pdfplumber, pytest, ReportLab fixtures.

## Global Constraints

- Korean DART filings are the supported semantic scope; unsupported English PDFs must fail closed.
- Footing and cash-flow reconciliation remain separate checks.
- Every retained PDF amount preserves page number and table bbox.
- No company-name, fixed-page, or filing-specific routing.
- Structure and scope uncertainty must be explicit.
- Existing HTML/DSD/XML parsing behavior, result IDs, ordering, amounts, and statuses remain unchanged.
- OCR remains out of scope.
- Do not run git commands.
- Follow RED-GREEN-REFACTOR; every production change starts with a failing behavior test.

---

### Task 1: PDF Semantic Success Gate

**Files:**
- Modify: `src/dart_footing_reconciler/attachment_ingestion.py`
- Test: `tests/test_attachment_ingestion.py`
- Test: `tests/test_pdf_ingestion.py`

**Interfaces:**
- Consumes: `parse_full_report_text()` and `is_usable_report_table()`.
- Produces: `_has_usable_report_structure(report: FullReport, *, input_format: str) -> bool`.
- Preserves: note-only structured HTML/DSD/XML compatibility.

- [ ] **Step 1: Add failing PDF fail-closed tests**

Add a native PDF fixture containing only `1. 일반사항` plus an amount-bearing table, and another containing an unsupported English statement title plus numeric table. Assert both public calls raise:

```python
with pytest.raises(AttachmentIngestionError) as exc:
    parse_report_attachment(path)
assert exc.value.code == "REPORT_STRUCTURE_NOT_FOUND"
```

Add a valid Korean statement plus note PDF and assert it still succeeds with one statement.

- [ ] **Step 2: Verify RED**

Run:

```text
uv run pytest -q tests/test_pdf_ingestion.py -k "semantic_gate or unsupported_english"
```

Expected: the note-only and English PDFs incorrectly return `ParsedAttachment`.

- [ ] **Step 3: Require an amount-bearing statement for PDF only**

Change the call and predicate to:

```python
if not _has_usable_report_structure(report, input_format=input_format):
    raise AttachmentIngestionError(
        "REPORT_STRUCTURE_NOT_FOUND",
        "재무제표 본문과 검증 가능한 금액 표를 찾지 못했습니다.",
    )


def _has_usable_report_structure(report: FullReport, *, input_format: str) -> bool:
    sections = report.statements if input_format == "pdf" else [*report.statements, *report.notes]
    return any(
        block.table is not None and is_usable_report_table(block.table)
        for section in sections
        for block in section.blocks
    )
```

- [ ] **Step 4: Verify GREEN and structured compatibility**

Run:

```text
uv run pytest -q tests/test_pdf_ingestion.py tests/test_attachment_ingestion.py
```

Expected: all tests pass; non-PDF note-only compatibility remains unchanged.

---

### Task 2: PDF-Native Body Boundaries and Consolidated/Separate Scope

**Files:**
- Modify: `src/dart_footing_reconciler/document.py`
- Test: `tests/test_document.py`

**Interfaces:**
- Produces: `_pdf_area_transition(text: str) -> tuple[str, str] | None`.
- Consumes: existing `_toc_area_transition()` and statement/note state variables.
- Preserves: HTML `section-N` transition behavior.

- [ ] **Step 1: Add an SK-like failing lifecycle fixture**

Create in-memory PDF markup with page attributes in this order:

```python
markup = """
<table data-pdf-page="1"><tr><td>2. 연결재무제표</td><td>3. 연결재무제표 주석</td></tr>
<tr><td>4. 재무제표</td><td>5. 재무제표 주석</td></tr></table>
<p data-pdf-page="34">5. 재무제표 주석을 참조하십시오.</p>
<p data-pdf-page="34">2. 연결재무제표</p>
<p data-pdf-page="34">2-1. 연결 재무상태표</p>
<table data-pdf-page="34" data-pdf-bbox="10,100,500,700">
<tr><td>구분</td><td>당기</td></tr><tr><td>자산총계</td><td>1,000</td></tr>
</table>
<p data-pdf-page="40">3. 연결재무제표 주석</p>
<p data-pdf-page="40">1. 일반사항</p>
<table data-pdf-page="40" data-pdf-bbox="10,100,500,300">
<tr><td>구분</td><td>금액</td></tr><tr><td>합계</td><td>100</td></tr>
</table>
"""
```

Assert one consolidated balance-sheet section, no note `2-1`, and note `1` scoped consolidated. Add separate assertions that the compound TOC table and reference sentence do not mutate state.

- [ ] **Step 2: Add an LG-like failing scope fixture**

After consolidated statements/notes, add standalone `4. 재무제표`, an unqualified `재무상태표` with amount table, then `5. 재무제표 주석`. Assert the second statement and following note have `scope == "separate"`.

- [ ] **Step 3: Verify RED**

Run:

```text
uv run pytest -q tests/test_document.py -k "pdf_body_boundary or pdf_scope_reset"
```

Expected: SK-like statement is missing or becomes note `2-1`; LG-like statement inherits consolidated scope.

- [ ] **Step 4: Implement exact PDF transitions**

Add:

```python
def _pdf_area_transition(text: str) -> tuple[str, str] | None:
    compact = _normalize(text)
    compact = re.sub(r"^\d+\.\s*", "", compact)
    exact = {
        "연결재무제표": ("statements", "consolidated"),
        "연결재무제표주석": ("notes", "consolidated"),
        "재무제표": ("statements", "separate"),
        "재무제표주석": ("notes", "separate"),
    }
    if compact in exact:
        return exact[compact]
    if "요약재무" in compact and len(compact) <= 20:
        return ("summary", "")
    return None
```

For `input_format == "pdf"`:

```python
in_note_area = False
```

Before broad marker checks for both paragraph and table nodes, accept only `_pdf_area_transition(text)` or `_pdf_area_transition(table_text)`. Apply the same reset performed by the HTML `section-N` branch: clear `current`, reset unit state, set `toc_area`, `in_note_area`, and `area_scope`. For PDF nodes without an exact transition, skip the substring-based `_note_area_marker`/`_non_note_area_marker` state mutation. Do not change the HTML branches.

- [ ] **Step 5: Verify GREEN and HTML parity**

Run:

```text
uv run pytest -q tests/test_document.py
```

Expected: PDF boundary tests pass and all existing document tests remain green.

---

### Task 3: Contextual PDF Note-Heading Sanity

**Files:**
- Modify: `src/dart_footing_reconciler/document.py`
- Test: `tests/test_document.py`

**Interfaces:**
- Changes: `_note_heading(text: str, *, input_format: str = "html")`.
- Preserves: legitimate Korean `1.`, `5-1.`, and nested `1.1` behavior.

- [ ] **Step 1: Add failing wrapped-decimal and valid-note tests**

Assert PDF input does not create notes for:

```text
92.4072 trillion in total assets
65.00 percent ownership
26.2 billion for intangible assets
1. Company overview
```

Assert a real PDF note area still recognizes `1. 일반사항`, keeps `1.1 세부사항` inside note 1, and recognizes `5-1. 금융상품` when it is a valid subsequent heading.

- [ ] **Step 2: Verify RED**

Run:

```text
uv run pytest -q tests/test_document.py -k "pdf_note_heading_sanity"
```

Expected: at least one decimal or English business heading becomes a note.

- [ ] **Step 3: Implement PDF-only conservative grammar**

Use:

```python
def _valid_note_no(value: str) -> bool:
    parts = re.split(r"[-.]", value)
    if not 1 <= len(parts) <= 3:
        return False
    if any(not part.isdigit() or not 1 <= int(part) <= 99 for part in parts):
        return False
    return True


def _note_heading(text: str, *, input_format: str = "html") -> tuple[str, str] | None:
    note_no_pattern = r"\d+(?:(?:-|\.)\d+)*"
    match = re.match(rf"^(?:주석?\s*)?({note_no_pattern})\.?\s+(.+)$", text)
    if match is None or not _valid_note_no(match.group(1)):
        return None
    title = _strip_heading_tail(match.group(2))
    if input_format == "pdf" and re.search(r"[가-힣]", title) is None:
        return None
    if _non_note_heading_title(title):
        return None
    return match.group(1), title
```

Pass `input_format` from every parser call site. Keep `_should_start_note()` so nested headings remain within their parent.

- [ ] **Step 4: Verify GREEN**

Run:

```text
uv run pytest -q tests/test_document.py tests/test_attachment_ingestion.py
```

---

### Task 4: Mixed Line/Text Table Candidate Selection

**Files:**
- Modify: `src/dart_footing_reconciler/pdf_ingestion.py`
- Test: `tests/test_pdf_ingestion.py`

**Interfaces:**
- Produces: `_select_table_candidates(line_tables, text_tables) -> tuple[list[tuple[bbox, rows]], bool]`.
- Produces diagnostic: `PDF_TABLE_FRAGMENT_RECOVERED` on pages where a text candidate replaces incomplete ruled fragments.
- Consumes: `parse_amount` imported from `dart_footing_reconciler.amounts`.

- [ ] **Step 1: Add a failing mixed-geometry PDF fixture**

Generate a page with left-side row labels outside a ruled right-side numeric grid. Assert extraction returns one retained table containing both labels and amounts, or returns a structural diagnostic rather than silently emitting numeric-only fragments.

- [ ] **Step 2: Verify RED**

Run:

```text
uv run pytest -q tests/test_pdf_ingestion.py -k mixed_geometry
```

Expected: line candidates suppress label recovery.

- [ ] **Step 3: Add conservative candidate scoring**

Represent candidates as `(bbox, rows, source)`. Always compute line candidates. When a line candidate has amount cells but no nonnumeric label in its first two columns, compute text candidates and compare overlapping groups. Prefer the text candidate only when it contains at least the same count of parseable amounts and strictly more nonnumeric labels; otherwise retain line candidates. Add `PDF_TABLE_FRAGMENT_RECOVERED` for every replacement page. Non-overlapping text candidates remain eligible.

The scoring helpers are:

```python
def _amount_count(rows):
    return sum(parse_amount(cell or "") is not None for row in rows for cell in row)


def _label_count(rows):
    return sum(
        bool((cell or "").strip()) and parse_amount(cell or "") is None
        for row in rows
        for cell in row[:2]
    )
```

Use bbox intersection over the smaller candidate area to group overlaps; do not merge cell arrays manually.

- [ ] **Step 4: Verify GREEN and PDF regression**

Run:

```text
uv run pytest -q tests/test_pdf_ingestion.py tests/test_attachment_ingestion.py tests/test_document.py
```

---

### Task 5: Repeat Actual Four-Company QA

**Files:**
- Input: `output/pdf/real-disclosure-qa/sources/*.pdf`
- Create: `.superpowers/sdd/real-disclosure-pdf-qa-after-hardening.md`
- Generated report artifacts: `output/pdf/real-disclosure-qa/results/`

**Interfaces:**
- Verifies: public `parse_report_attachment()` and later `verify_attachment()`.

- [ ] **Step 1: Re-run package parsing with a 180-second per-file ceiling**

Required outcomes:

- SK이터닉스: at least one plausible consolidated statement family; no statement heading such as `2-1` stored as a note.
- LG화학: consolidated and separate statement families both present with correct scope.
- Samsung/Hyundai English: explicit `REPORT_STRUCTURE_NOT_FOUND`, not success and not a third-party exception.
- All retained amount tables: page and bbox coverage 100%.

- [ ] **Step 2: Re-render the same twelve representative pages**

Run `pdftoppm` into `tmp/pdfs/real-disclosure-qa-after/`, inspect statement/note/mixed-table pages, and compare with extracted rows. Delete temporary PNGs after inspection.

- [ ] **Step 3: Run focused and full verification**

Run:

```text
uv run ruff check src tests
uv run pytest -q tests/test_document.py tests/test_attachment_ingestion.py tests/test_pdf_ingestion.py
uv run pytest -q
```

Record exact totals. Separate the known external `out/corpus` fixture `FileNotFoundError` failures from new regressions.

---

## Plan Self-Review

- Slice order matches the root-cause report: fail closed, boundary lifecycle, scope, note sanity, mixed geometry.
- Korean DART success and unsupported English fail-closed outcomes are explicit.
- PDF-only behavior is isolated so HTML/DSD/XML compatibility remains testable.
- No company-name, fixed-page, OCR, or LLM routing is introduced.
- Source page/bbox requirements remain unchanged.
- No git command is included.
