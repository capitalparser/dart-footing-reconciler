# 데스크톱 검증 워크벤치 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** DART 원문 표의 병합 구조를 보존하고, 표 내부 산식은 대상 셀 테두리로, 표 사이 대사는 우측 드로워로 보여주는 데스크톱 검증 웹앱을 구현한다.

**Architecture:** 계산 엔진이 사용하는 `ReportTable.rows`는 그대로 유지하고 파서가 선택적 원본 셀 레이아웃을 함께 보존한다. `report_frame.py`가 엔진 결과를 `CellAnnotation`과 `DrawerItem`으로 변환하며, 공통 HTML 렌더러가 왼쪽 원문 탐색·중앙 표·오른쪽 대사 드로워를 생성한다. verify-app은 계속 같은 `_build_html(...)` 결과를 삽입하고 업로드 상태만 사용자 문구로 표시한다.

**Tech Stack:** Python 3.11+, BeautifulSoup4/lxml, pytest, HTML/CSS, vanilla JavaScript, Vitest, Playwright

## Global Constraints

- Footing과 현금흐름 대사는 별도 검증으로 유지한다.
- `ReportTable.rows`, `row_acodes`, 단위 정보와 기존 계산 입력을 변경하지 않는다.
- `CheckResult`의 `status`, `expected`, `actual`, `difference`, `check_id`, 결과 순서를 변경하지 않는다.
- 모든 material amount의 원문 위치를 유지한다.
- 라벨 매핑 불확실성은 기존 confidence/evidence 계약을 유지한다.
- 검증 코어는 MCP 없이 실행되어야 한다.
- 표 내부 셀 테두리는 `total_check`, `note_rollforward_check`, `note_layout_formula_check`, `appropriation_formula_check`에만 적용한다.
- 표 사이 대사는 우측 드로워에 표시하고 화면 코드에서 검증 유형을 다시 분기하지 않는다.
- 사용자 HTML/DOM에 내부 검증 ID, raw source path, Python/JavaScript 스택, `LOCAL VERIFY`, `PyOdide`를 노출하지 않는다.
- React, Next.js, 별도 프론트엔드 빌드 도구와 새 런타임 의존성을 추가하지 않는다.
- 데스크톱 1440x900과 1600x1000만 완료 기준으로 삼고 모바일 최적화는 하지 않는다.
- 각 동작은 실패 테스트를 먼저 확인한 뒤 최소 구현으로 통과시킨다.
- git 명령은 실행하지 않는다.

---

### Task 1: 계산 행렬과 분리된 원본 셀 레이아웃 보존

**Files:**
- Modify: `src/dart_footing_reconciler/html_tables.py`
- Modify: `src/dart_footing_reconciler/document.py`
- Test: `tests/test_html_tables.py`
- Test: `tests/test_document.py`

**Interfaces:**
- Consumes: BeautifulSoup `Tag`, 기존 `_extract_rows(table: Tag) -> list[TableRow]`
- Produces: `TableCellLayout`, `ExtractedTable`, `_extract_table(table: Tag) -> ExtractedTable`, `ReportTable.display_cells`

- [ ] **Step 1: 병합 구조와 정규화 행렬 동시 보존 실패 테스트 작성**

`tests/test_html_tables.py`에 다음 테스트를 추가한다.

```python
def test_extract_table_preserves_original_cell_geometry_without_changing_grid() -> None:
    from bs4 import BeautifulSoup
    from dart_footing_reconciler.html_tables import _extract_table

    soup = BeautifulSoup(
        """
        <table>
          <tr><th rowspan="2">구분</th><th colspan="2">당기</th></tr>
          <tr><th>기계장치</th><th>합계</th></tr>
          <tr><td>기말</td><td acode="asset">100</td><td>100</td></tr>
        </table>
        """,
        "lxml",
    )

    extracted = _extract_table(soup.table)

    assert [row.cells for row in extracted.rows] == [
        ["구분", "당기", "당기"],
        ["구분", "기계장치", "합계"],
        ["기말", "100", "100"],
    ]
    assert [(cell.row_index, cell.column_index, cell.rowspan, cell.colspan, cell.tag) for cell in extracted.display_cells] == [
        (0, 0, 2, 1, "th"),
        (0, 1, 1, 2, "th"),
        (1, 1, 1, 1, "th"),
        (1, 2, 1, 1, "th"),
        (2, 0, 1, 1, "td"),
        (2, 1, 1, 1, "td"),
        (2, 2, 1, 1, "td"),
    ]
    assert extracted.display_cells[5].acode == "asset"
```

- [ ] **Step 2: 파서 테스트가 실패하는지 확인**

Run: `uv run pytest tests/test_html_tables.py::test_extract_table_preserves_original_cell_geometry_without_changing_grid -q`

Expected: FAIL because `_extract_table` and `TableCellLayout` do not exist.

- [ ] **Step 3: 원본 셀 레이아웃 추출 구현**

`html_tables.py`에 다음 타입을 추가하고 기존 `_extract_rows`의 반복문을 `_extract_table`로 옮긴다. 기존 호출 호환성을 위해 `_extract_rows`는 wrapper로 남긴다.

```python
@dataclass(frozen=True)
class TableCellLayout:
    text: str
    row_index: int
    column_index: int
    rowspan: int = 1
    colspan: int = 1
    tag: str = "td"
    source_line: int | None = None
    acode: str = ""


@dataclass(frozen=True)
class ExtractedTable:
    rows: list[TableRow]
    display_cells: tuple[TableCellLayout, ...]


def _extract_table(table: Tag) -> ExtractedTable:
    rows: list[TableRow] = []
    display_cells: list[TableCellLayout] = []
    rowspans: dict[int, tuple[str, str, int | None, int]] = {}

    for tr in _direct_table_rows(table):
        normalized_row = len(rows)
        cells: list[str] = []
        acodes: list[str] = []
        cell_source_lines: list[int | None] = []
        col_index = 0

        for cell in tr.find_all(["th", "td"], recursive=False):
            while col_index in rowspans:
                text, acode, source_line, remaining = rowspans[col_index]
                cells.append(text)
                acodes.append(acode)
                cell_source_lines.append(source_line)
                if remaining <= 1:
                    del rowspans[col_index]
                else:
                    rowspans[col_index] = (text, acode, source_line, remaining - 1)
                col_index += 1

            text = _clean_text(cell.get_text(" ", strip=True))
            acode = str(cell.get("acode") or "")
            source_line = _source_line(cell)
            colspan = _int_attr(cell, "colspan", default=1)
            rowspan = _int_attr(cell, "rowspan", default=1)
            display_cells.append(TableCellLayout(
                text=text,
                row_index=normalized_row,
                column_index=col_index,
                rowspan=rowspan,
                colspan=colspan,
                tag=cell.name or "td",
                source_line=source_line,
                acode=acode,
            ))
            for offset in range(colspan):
                cells.append(text)
                acodes.append(acode)
                cell_source_lines.append(source_line)
                if rowspan > 1:
                    rowspans[col_index + offset] = (text, acode, source_line, rowspan - 1)
            col_index += colspan

        while col_index in rowspans:
            text, acode, source_line, remaining = rowspans[col_index]
            cells.append(text)
            acodes.append(acode)
            cell_source_lines.append(source_line)
            if remaining <= 1:
                del rowspans[col_index]
            else:
                rowspans[col_index] = (text, acode, source_line, remaining - 1)
            col_index += 1

        if any(cells):
            rows.append(TableRow(
                cells=cells,
                index=normalized_row,
                acodes=acodes,
                source_line=_source_line(tr),
                cell_source_lines=cell_source_lines,
            ))
        else:
            display_cells = [cell for cell in display_cells if cell.row_index != normalized_row]

    return ExtractedTable(rows=rows, display_cells=tuple(display_cells))


def _extract_rows(table: Tag) -> list[TableRow]:
    return _extract_table(table).rows
```

- [ ] **Step 4: 원본 셀 추출 테스트 통과 확인**

Run: `uv run pytest tests/test_html_tables.py -q`

Expected: PASS and all existing normalized-row assertions remain unchanged.

- [ ] **Step 5: `ReportTable` 표시 필드와 선행 단위 행 좌표 실패 테스트 작성**

`tests/test_document.py`에 다음 테스트를 추가한다.

```python
def test_report_table_keeps_display_geometry_after_leading_unit_row(tmp_path):
    report = _parse_html_string(tmp_path, """
    <p>재무제표 주석</p>
    <p>11. 유형자산</p>
    <table>
      <tr><td colspan="3">(단위: 천원)</td></tr>
      <tr><th rowspan="2">구분</th><th colspan="2">당기</th></tr>
      <tr><th>취득</th><th>합계</th></tr>
      <tr><td>기말</td><td>100</td><td>100</td></tr>
    </table>
    """)

    table = report.notes[0].blocks[-1].table
    assert table.rows == [
        ["구분", "당기", "당기"],
        ["구분", "취득", "합계"],
        ["기말", "100", "100"],
    ]
    assert [(cell.row_index, cell.column_index, cell.rowspan, cell.colspan) for cell in table.display_cells] == [
        (0, 0, 2, 1), (0, 1, 1, 2), (1, 1, 1, 1), (1, 2, 1, 1),
        (2, 0, 1, 1), (2, 1, 1, 1), (2, 2, 1, 1),
    ]
```

- [ ] **Step 6: 문서 파서에 선택적 표시 레이아웃 연결**

`document.py`에서 `_extract_table`과 `TableCellLayout`을 import하고 `ReportTable`의 마지막 필드로 다음을 추가한다.

```python
@dataclass(frozen=True)
class ReportTable:
    index: int
    rows: list[list[str]]
    heading: str
    location: SourceLocation
    row_acodes: list[list[str]] | None = None
    unit_multiplier: int = 1
    unit_declared: bool = False
    display_cells: tuple[TableCellLayout, ...] | None = None
```

선행 행 제거 시 셀 범위를 잘라 좌표를 이동하는 helper를 추가한다.

```python
def _slice_display_cells(
    cells: tuple[TableCellLayout, ...], *, first_row: int
) -> tuple[TableCellLayout, ...]:
    sliced: list[TableCellLayout] = []
    for cell in cells:
        end_row = cell.row_index + cell.rowspan
        if end_row <= first_row:
            continue
        clipped_start = max(cell.row_index, first_row)
        sliced.append(dataclasses.replace(
            cell,
            row_index=clipped_start - first_row,
            rowspan=end_row - clipped_start,
        ))
    return tuple(sliced)
```

`parse_full_report`의 표 처리에서 `extracted = _extract_table(node)`을 한 번 호출하고 `rows = extracted.rows`를 사용한다. `leading_unit_multiplier`로 첫 행을 제거한 경우 `first_display_row = 1`, 아니면 `0`으로 두고 `ReportTable` 생성 시 다음 필드를 전달한다.

```python
display_cells=_slice_display_cells(
    extracted.display_cells,
    first_row=first_display_row,
),
```

`document.py` 상단에 `import dataclasses`를 추가한다.

- [ ] **Step 7: Task 1 회귀 확인**

Run: `uv run pytest tests/test_html_tables.py tests/test_document.py -q`

Expected: PASS; 기존 `ReportTable(...)` 위치 인자 생성 테스트도 변경 없이 통과한다.

---

### Task 2: 표 내부 산식의 목표 셀 역할 명시

**Files:**
- Modify: `src/dart_footing_reconciler/checks_totals.py`
- Modify: `src/dart_footing_reconciler/layout_formula_assertions.py`
- Modify: `src/dart_footing_reconciler/note_internal_harness.py`
- Test: `tests/test_checks_totals.py`
- Test: `tests/test_layout_formula_assertions.py`
- Test: `tests/test_note_internal_harness.py`
- Test: `tests/test_note_assertions.py`

**Interfaces:**
- Consumes: 기존 `CheckResult`, `CheckEvidence`, `VerificationFormula.target_role`
- Produces: 표 내부 산식 target evidence의 `role="target"`; 증감표는 기존 `role="ending"` 유지

- [ ] **Step 1: 네 검증 유형의 목표 역할 실패 테스트 작성**

각 기존 대표 fixture 테스트에 다음 assertion을 추가한다.

```python
assert next(result for result in results if result.check_type == "total_check").evidence[0].role == "target"

layout = next(result for result in results if result.check_type == "note_layout_formula_check")
assert [e.role for e in layout.evidence].count("target") == 1

appropriation = next(result for result in results if result.check_type == "appropriation_formula_check")
assert appropriation.evidence[-1].role == "target"

rollforward = next(result for result in results if result.check_type == "note_rollforward_check")
assert [e.role for e in rollforward.evidence].count("ending") == 1
```

같은 테스트에서 역할을 제외한 불변 스냅샷을 고정한다.

```python
def _result_signature(result):
    return (
        result.status,
        result.expected,
        result.actual,
        result.difference,
        result.check_id,
    )
```

- [ ] **Step 2: 목표 역할 테스트 실패 확인**

Run: `uv run pytest tests/test_checks_totals.py tests/test_layout_formula_assertions.py tests/test_note_internal_harness.py tests/test_note_assertions.py -q`

Expected: FAIL only for missing target roles; numeric/status assertions remain unchanged.

- [ ] **Step 3: 합계·레이아웃 산식·처분 산식 근거 역할 보강**

`checks_totals.py`에서 `_result(...)`에 전달되는 모든 첫 번째 target evidence에 `role="target"`을 추가한다. component evidence는 기존 `role="component"`를 유지한다.

`layout_formula_assertions._formula_check_result`의 evidence 생성은 다음처럼 바꾼다.

```python
evidence=[
    CheckEvidence(
        term.label,
        term.amount,
        f"{term.table_source}/row:{term.row_index}/col:{term.column_index}",
        role="target" if term.role == formula.target_role else "component",
    )
    for term in formula.terms
],
```

`note_internal_harness._appropriation_formula_checks`에서는 opening/addition/movement를 `component`, closing을 `target`으로 지정한다.

```python
CheckEvidence(
    rows[closing_idx][0],
    closing,
    f"{source_base}/row:{closing_idx}/col:{col}",
    role="target",
)
```

`note_assertions.py`의 `ending` 역할은 변경하지 않는다.

- [ ] **Step 4: Task 2 회귀 확인**

Run: `uv run pytest tests/test_checks_totals.py tests/test_checks_totals_structure.py tests/test_layout_formula_assertions.py tests/test_note_internal_harness.py tests/test_note_assertions.py -q`

Expected: PASS with unchanged result signatures and result ordering.

---

### Task 3: `report_frame`의 셀 주석·대사 드로워 표시 모델

**Files:**
- Modify: `src/dart_footing_reconciler/report_frame.py`
- Test: `tests/test_report_frame.py`

**Interfaces:**
- Consumes: `FullReport`, `list[CheckResult]`, `CheckEvidence.source`, `CHECK_LAYERS`
- Produces: `SourceCellRef`, `CellAnnotation`, `DrawerItem`, `WorkbenchAnnotations`, `build_workbench_annotations(report, checks)`

- [ ] **Step 1: 표시 분기와 좌표 모델 실패 테스트 작성**

`tests/test_report_frame.py`에 내부 합계와 표 사이 대사를 함께 구성하는 테스트를 추가한다.

```python
def test_workbench_annotations_split_internal_cells_from_cross_table_drawer():
    from dart_footing_reconciler.report_frame import build_workbench_annotations

    report = FullReport(
        "sample.html",
        "Sample Co",
        [_section("statement:bs", "재무상태표", "statement", "", _table("statement:bs", 0, "재무상태표"))],
        [_section("note:11", "유형자산", "note", "11", _table("note:11", 1, "유형자산"))],
    )
    internal = CheckResult(
        "total:11:table1:row1:col1", "total_check", "matched", "note", "11",
        "표 합계", 100, 100, 0, 1, "row total agrees",
        [CheckEvidence("합계", 100, "note:11/table:1/row:1/col:1", role="target")],
    )
    cross = CheckResult(
        "fs-note", "fs_note_match", "unexplained_gap", "report", "11",
        "재무제표-주석 대사", 100, 90, -10, 1, "gap",
        [
            CheckEvidence("재무제표", 100, "statement:bs/table:0/row:1/col:1"),
            CheckEvidence("주석", 90, "note:11/table:1/row:1/col:1"),
        ],
    )

    model = build_workbench_annotations(report, [internal, cross])

    assert [(item.target.table_index, item.target.row_index, item.target.column_index) for item in model.cells] == [(1, 1, 1)]
    assert [item.check for item in model.drawers] == [cross]
    assert [(ref.table_index, ref.row_index, ref.column_index) for ref in model.drawers[0].anchors] == [(0, 1, 1), (1, 1, 1)]
```

한 셀에 여러 검증이 연결되는 우선순위 테스트도 추가한다.

```python
def test_cell_annotations_keep_all_checks_and_choose_worst_status():
    model = build_workbench_annotations(report, [matched_check, uncertain_check, gap_check])
    annotation = model.cells[0]
    assert annotation.status == "unexplained_gap"
    assert annotation.count == 3
    assert annotation.checks == (matched_check, uncertain_check, gap_check)
```

- [ ] **Step 2: 표시 모델 테스트 실패 확인**

Run: `uv run pytest tests/test_report_frame.py -q`

Expected: FAIL because workbench annotation types and builder do not exist.

- [ ] **Step 3: 단일 레지스트리와 표시 모델 구현**

`report_frame.py`에 모든 엔진 check type을 포함하는 표시 레지스트리를 추가한다. 내부 네 유형만 `cell`, 나머지는 `drawer`; `not_tested` 또는 좌표 없는 항목은 어느 셀에도 붙이지 않는다.

```python
CHECK_PRESENTATIONS: dict[str, str] = {
    check_type: (
        "cell"
        if check_type in {
            "total_check",
            "note_rollforward_check",
            "note_layout_formula_check",
            "appropriation_formula_check",
        }
        else "drawer"
    )
    for check_type in CHECK_GROUPS
}

TARGET_EVIDENCE_ROLES: dict[str, tuple[str, ...]] = {
    "total_check": ("target",),
    "note_rollforward_check": ("ending",),
    "note_layout_formula_check": ("target",),
    "appropriation_formula_check": ("target",),
}

@dataclass(frozen=True)
class SourceCellRef:
    scope: str
    name: str
    table_index: int
    row_index: int | None
    column_index: int | None

    @property
    def is_exact_cell(self) -> bool:
        return self.row_index is not None and self.column_index is not None


@dataclass(frozen=True)
class CellAnnotation:
    target: SourceCellRef
    status: str
    checks: tuple[CheckResult, ...]

    @property
    def count(self) -> int:
        return len(self.checks)


@dataclass(frozen=True)
class DrawerItem:
    check: CheckResult
    anchors: tuple[SourceCellRef, ...]


@dataclass(frozen=True)
class WorkbenchAnnotations:
    cells: tuple[CellAnnotation, ...]
    drawers: tuple[DrawerItem, ...]
```

source parser는 화면 raw 문자열을 만들지 않고 좌표 객체로만 반환한다.

```python
_CELL_SOURCE_RE = re.compile(
    r"^(statement|note):([^/]+)/table:(\d+)"
    r"(?:/row:(\d+))?(?:/col:(\d+))?$"
)

def source_cell_ref(source: str) -> SourceCellRef | None:
    match = _CELL_SOURCE_RE.match(source)
    if match is None:
        return None
    return SourceCellRef(
        scope=match.group(1),
        name=match.group(2),
        table_index=int(match.group(3)),
        row_index=int(match.group(4)) if match.group(4) is not None else None,
        column_index=int(match.group(5)) if match.group(5) is not None else None,
    )
```

`build_workbench_annotations`는 입력 순서를 유지하고 셀별 severity만 계산한다.

```python
_DISPLAY_SEVERITY = {
    "matched": 1,
    "explainable_gap": 2,
    "parse_uncertain": 3,
    "unexplained_gap": 4,
}

def build_workbench_annotations(
    report: FullReport,
    checks: list[CheckResult],
) -> WorkbenchAnnotations:
    valid_table_indexes = {
        block.table.index
        for section in (*report.statements, *report.notes)
        for block in section.blocks
        if block.table is not None
    }
    grouped: dict[SourceCellRef, list[CheckResult]] = {}
    drawers: list[DrawerItem] = []
    for check in checks:
        presentation = CHECK_PRESENTATIONS.get(check.check_type, "drawer")
        refs = tuple(
            ref
            for evidence in check.evidence
            if (ref := source_cell_ref(evidence.source))
            and ref.table_index in valid_table_indexes
        )
        if presentation == "drawer":
            if refs and check.status != "not_tested":
                drawers.append(DrawerItem(check=check, anchors=refs))
            continue
        roles = TARGET_EVIDENCE_ROLES[check.check_type]
        target = next(
            (
                source_cell_ref(evidence.source)
                for evidence in check.evidence
                if evidence.role in roles
            ),
            None,
        )
        if (
            target is not None
            and target.is_exact_cell
            and target.table_index in valid_table_indexes
            and check.status != "not_tested"
        ):
            grouped.setdefault(target, []).append(check)
    cells = tuple(
        CellAnnotation(
            target=target,
            status=max(items, key=lambda item: _DISPLAY_SEVERITY.get(item.status, 0)).status,
            checks=tuple(items),
        )
        for target, items in grouped.items()
    )
    return WorkbenchAnnotations(cells=cells, drawers=tuple(drawers))
```

- [ ] **Step 4: 레지스트리 완전성·표시 모델 회귀 확인**

`test_check_type_registries_are_self_consistent_for_known_check_types`에 다음을 추가한다.

```python
assert set(CHECK_PRESENTATIONS) == ENGINE_CHECK_TYPES
```

Run: `uv run pytest tests/test_report_frame.py -q`

Expected: PASS.

---

### Task 4: 병합 표 렌더링과 정확한 셀 테두리

**Files:**
- Modify: `src/dart_footing_reconciler/report_html.py`
- Test: `tests/test_report_html_evidence.py`

**Interfaces:**
- Consumes: `ReportTable.display_cells`, `CellAnnotation`, `TableCellLayout`
- Produces: `_render_source_table(table: ReportTable, cell_annotations: tuple[CellAnnotation, ...], drawer_items: tuple[DrawerItem, ...]) -> str`

- [ ] **Step 1: 병합 마크업·대상 셀 테두리 실패 테스트 작성**

`tests/test_report_html_evidence.py`에 `display_cells`가 있는 표와 target check를 구성해 다음을 검증한다.

```python
def test_source_table_renders_original_merges_and_internal_check_on_target_cell():
    from dart_footing_reconciler.html_tables import TableCellLayout
    from dart_footing_reconciler.report_frame import build_workbench_annotations
    from dart_footing_reconciler.report_html import _display_cell_for_coordinate, _render_source_table

    table = ReportTable(
        28,
        [["구분", "당기", "당기"], ["구분", "취득", "합계"], ["기말", "100", "100"]],
        "유형자산",
        SourceLocation("note:8", 0, 28),
        display_cells=(
            TableCellLayout("구분", 0, 0, 2, 1, "th"),
            TableCellLayout("당기", 0, 1, 1, 2, "th"),
            TableCellLayout("취득", 1, 1, 1, 1, "th"),
            TableCellLayout("합계", 1, 2, 1, 1, "th"),
            TableCellLayout("기말", 2, 0),
            TableCellLayout("100", 2, 1),
            TableCellLayout("100", 2, 2),
        ),
    )
    check = CheckResult(
        "total", "total_check", MATCHED, "note", "8", "합계", 100, 100, 0, 1,
        "row total agrees",
        [CheckEvidence("합계", 100, "note:8/table:28/row:2/col:2", role="target")],
    )
    note = ReportSection(
        "note:8",
        "유형자산",
        "note",
        "8",
        [ReportBlock("table", "", table, table.location)],
    )
    report = FullReport("sample.html", "Sample Co", [], [note])
    model = build_workbench_annotations(report, [check])

    html = _render_source_table(table, model.cells, model.drawers)

    assert '<th rowspan="2"' in html
    assert '<th colspan="2"' in html
    assert 'data-cell="t28r2c2"' in html
    assert 'cell-check cell-matched' in html
    assert 'aria-label="합계 일치"' in html
    assert _display_cell_for_coordinate(table, 1, 0).rowspan == 2
```

- [ ] **Step 2: 렌더링 테스트 실패 확인**

Run: `uv run pytest tests/test_report_html_evidence.py -q`

Expected: FAIL because `_render_source_table` and merged-cell mapping do not exist.

- [ ] **Step 3: 원본 셀 범위 매핑과 fallback renderer 구현**

`report_html.py`에 다음 helper를 추가한다.

```python
def _display_cell_for_coordinate(
    table: ReportTable, row_index: int, column_index: int
):
    for cell in table.display_cells or ():
        if (
            cell.row_index <= row_index < cell.row_index + cell.rowspan
            and cell.column_index <= column_index < cell.column_index + cell.colspan
        ):
            return cell
    return None


def _annotation_key(table_index: int, row_index: int, column_index: int) -> str:
    return f"t{table_index}r{row_index}c{column_index}"
```

`_render_source_table`은 `display_cells`가 있으면 원본 cell만 렌더링하고, 없으면 기존 정규화 grid를 렌더링한다. annotation 좌표가 병합 범위 안이면 원본 cell 시작 좌표에 합친다.

```python
status_class = {
    MATCHED: "cell-matched",
    EXPLAINABLE_GAP: "cell-explained",
    UNEXPLAINED_GAP: "cell-gap",
    PARSE_UNCERTAIN: "cell-uncertain",
}
status_label = {
    MATCHED: "일치",
    EXPLAINABLE_GAP: "차이 원인 설명됨",
    UNEXPLAINED_GAP: "확인 필요",
    PARSE_UNCERTAIN: "원문 확인",
}
```

각 검증 셀에는 raw source나 check ID 대신 렌더링 순번으로 만든 `data-annotation`만 넣고 `tabindex="0"`, `aria-label`, 검증 건수 badge를 추가한다. `not_tested`는 class를 만들지 않는다. drawer anchor가 정확한 셀 좌표를 가지면 같은 셀에 `data-open-drawer="{render_index}"`를 추가하고, 행 또는 표까지만 식별된 anchor는 해당 표 caption의 `대사 결과` badge로 연결한다.

- [ ] **Step 4: 셀 테두리 CSS와 키보드 툴팁 구현**

`_inline_css()`에 다음 상태를 추가한다.

```css
.source-cell{position:relative}
.cell-check{outline-offset:-3px;cursor:help}
.cell-matched{outline:3px solid #16825d}
.cell-explained{outline:3px solid #0f766e}
.cell-gap{outline:3px solid #c26a16}
.cell-uncertain{outline:2px dashed #64748b;outline-offset:-2px}
.cell-check-count{position:absolute;top:3px;right:3px;min-width:18px;height:18px;border-radius:9px;background:#163a34;color:#fff;font-size:10px;display:grid;place-items:center}
.cell-tooltip{position:absolute;z-index:20;display:none;max-width:320px;padding:10px 12px;border:1px solid var(--border);background:#fff;box-shadow:0 12px 30px rgba(15,23,42,.16)}
.cell-check:hover .cell-tooltip,.cell-check:focus .cell-tooltip{display:block}
```

툴팁에는 `check_display_title`, `CHECK_METHOD_DESCRIPTIONS`, expected, actual, difference만 넣고 raw engine field를 넣지 않는다.

- [ ] **Step 5: Task 4 회귀 확인**

Run: `uv run pytest tests/test_report_html_evidence.py tests/test_report_html_new.py -q`

Expected: PASS; HTML에는 실제 `rowspan`/`colspan`과 target cell class가 존재한다.

---

### Task 5: 데스크톱 3열 워크벤치와 우측 대사 드로워

**Files:**
- Modify: `src/dart_footing_reconciler/report_html.py`
- Modify: `tests/test_report_html_cockpit.py`
- Modify: `tests/test_report_html_new.py`
- Modify: `tests/test_report_html_evidence.py`
- Modify: `tests/test_verify_app.py`

**Interfaces:**
- Consumes: Task 3 `WorkbenchAnnotations`, Task 4 `_render_source_table`
- Produces: `_render_workbench_drawer`, 데스크톱 `audit-workbench` HTML/JS

- [ ] **Step 1: 새로운 화면 계약 실패 테스트 작성**

기존 대시보드 탭 기대 테스트를 데스크톱 원문 탐색 계약으로 교체한다.

```python
def test_report_html_uses_source_workbench_navigation_and_drawer(tmp_path):
    content = _mixed_report(tmp_path)

    assert 'class="audit-workbench"' in content
    assert 'class="source-nav"' in content
    assert 'class="source-stage"' in content
    assert 'id="reconciliation-drawer"' in content
    assert "재무제표 본문" in content
    assert "각 주석" in content
    assert "대사 결과" in content
    assert "다음에 확인할 내용" in content
    assert "대시보드" not in content
    assert "진행상황" not in content
    assert "검증 범례" not in content
```

drawer 금액과 양쪽 원문 이동 계약을 추가한다.

```python
assert 'data-drawer-item="0"' in content
assert 'data-open-drawer="0"' in content
assert "기준 금액" in content
assert "비교 금액" in content
assert "차이" in content
assert 'data-source-jump="0"' in content
assert 'data-source-jump="1"' in content
assert "fs_note_match" not in content
assert "statement:bs/table" not in content
```

- [ ] **Step 2: 화면 계약 테스트 실패 확인**

Run: `uv run pytest tests/test_report_html_cockpit.py tests/test_report_html_new.py tests/test_verify_app.py -q`

Expected: FAIL because the current dashboard/progress/legend panels are still rendered.

- [ ] **Step 3: `_build_html`을 3열 workbench 조립으로 변경**

`_build_html`은 `build_workbench_annotations(report, results)`를 한 번 호출한다. 기존 dashboard/progress/attention/next/legend panel 조립을 제거하고 다음 구조만 반환한다.

```html
<header class="workbench-header">
  <div class="report-identity">{masthead_html}</div>
  <div class="report-counts">{status_counts_html}</div>
</header>
<div class="audit-workbench">
  <aside class="source-nav">{sidebar_html}</aside>
  <main class="source-stage" id="main-content">{source_panels_html}</main>
  <aside class="reconciliation-drawer" id="reconciliation-drawer" aria-labelledby="drawer-title">{drawer_html}</aside>
</div>
```

상단 바에는 회사명·기간, `검토 필요`, `원문 확인 필요`, 기존 export entry가 있을 때만 내보내기 버튼을 둔다. sidebar는 `재무제표 본문`, `각 주석` 두 그룹만 렌더링한다. 첫 번째 실제 원문 panel을 active로 둔다.

- [ ] **Step 4: 우측 drawer 결과와 사용자 행동 구현**

`_render_workbench_drawer`는 각 `DrawerItem`을 렌더링 순번으로 식별하고 다음 순서를 고정한다.

```python
def _next_action_text(check: CheckResult) -> str:
    if check.status == UNEXPLAINED_GAP:
        return "양쪽 원문 금액과 공시 범위를 확인하고 차이 원인을 기록하세요."
    if check.status == PARSE_UNCERTAIN:
        return "원문 표의 머리글과 병합 구조를 확인해 비교 대상을 확정하세요."
    if check.status == EXPLAINABLE_GAP:
        return "표시된 설명 근거가 현재 보고기간에도 유효한지 확인하세요."
    return "추가 조치가 필요하지 않습니다."
```

drawer item에는 표시명, 상태, expected, actual, difference, `check_display_reason`, `_next_action_text`, humanized source buttons를 넣는다. 동일 셀에 여러 대사가 연결되면 status severity와 원래 결과 순서로 정렬하며 `확인 필요`/`일치` filter button을 제공한다.

- [ ] **Step 5: 데스크톱 고정 레이아웃과 넓은 표 스크롤 구현**

기존 모바일 media query를 제거하고 CSS를 다음 구조로 교체한다.

```css
.audit-workbench{display:grid;grid-template-columns:260px minmax(620px,1fr) 400px;height:calc(100vh - 72px);min-width:1280px;background:var(--bg)}
.source-nav{position:sticky;top:72px;height:calc(100vh - 72px);overflow:auto;border-right:1px solid var(--border)}
.source-stage{min-width:0;overflow:auto;padding:20px 24px}
.source-table-scroll{overflow-x:auto;overflow-y:visible;border:1px solid var(--border);background:#fff}
.reconciliation-drawer{position:sticky;top:72px;height:calc(100vh - 72px);overflow:auto;border-left:1px solid var(--border);background:#fff}
.source-panel[hidden]{display:none}
```

1440px에서 중앙 표가 줄어들어도 좌측 navigation과 drawer는 겹치지 않으며, 화면이 1280px보다 좁으면 페이지 전체 가로 스크롤을 허용한다. 별도 모바일 카드 레이아웃은 만들지 않는다.

- [ ] **Step 6: navigation·drawer·원문 이동 JavaScript 구현**

`_inline_js()`는 inline raw source 없이 렌더링 순번을 사용한다.

```javascript
document.querySelectorAll('[data-source-panel]').forEach(function(button) {
  button.addEventListener('click', function() {
    var panelId = button.getAttribute('data-source-panel');
    document.querySelectorAll('.source-panel').forEach(function(panel) {
      panel.hidden = panel.id !== panelId;
    });
    document.querySelectorAll('[data-source-panel]').forEach(function(item) {
      item.classList.toggle('active', item === button);
      if (item === button) item.setAttribute('aria-current', 'page');
      else item.removeAttribute('aria-current');
    });
  });
});

document.querySelectorAll('[data-open-drawer]').forEach(function(trigger) {
  trigger.addEventListener('click', function() {
    openDrawerItem(Number(trigger.getAttribute('data-open-drawer')), trigger);
  });
});
```

drawer가 열리면 `#drawer-title`로 초점을 이동하고 닫으면 이전 trigger로 복귀한다. source jump는 등록된 렌더 순번으로 target panel을 열고 `data-cell`을 2초간 강조한다. anchor가 행까지만 식별되면 해당 행을 강조하고, 표까지만 식별되면 해당 표 caption으로 이동한다.

- [ ] **Step 7: Task 5 HTML 회귀 확인**

Run: `uv run pytest tests/test_report_html_cockpit.py tests/test_report_html_new.py tests/test_report_html_evidence.py tests/test_verify_app.py tests/test_surface_parity.py -q`

Expected: PASS; verify-app과 standalone HTML 모두 `audit-workbench`를 포함하고 old cockpit panels는 포함하지 않는다.

---

### Task 6: verify-app의 사용자 문구와 오류 표면 정리

**Files:**
- Modify: `static/dart-verify/index.html`
- Modify: `static/dart-verify/app.js`
- Modify: `tests/js/dart_verify_app.test.js`
- Test: `tests/test_build_verify_app.py`

**Interfaces:**
- Consumes: 기존 `verify_html_report` 반환 HTML
- Produces: `DART 원문 선택`, `검증 준비 중`, `검증 중`, `검증 완료`, `파일 확인 필요` 상태

- [ ] **Step 1: 시스템 용어·스택 비노출 실패 테스트 작성**

`tests/js/dart_verify_app.test.js`에 다음 테스트를 추가한다.

```javascript
import { readFile } from "node:fs/promises";

test("shows actionable copy without runtime names or stack traces", async () => {
  const { initDartVerifyApp } = await import("../../static/dart-verify/app.js");
  const indexHtml = await readFile("static/dart-verify/index.html", "utf8");
  expect(indexHtml).not.toContain("LOCAL VERIFY");
  expect(indexHtml).not.toContain("PyOdide");
  expect(indexHtml).not.toContain("파싱 불확실");
  expect(indexHtml).toContain("DART 원문 선택");

  const controller = initDartVerifyApp({ autoBoot: false, loadPyodideFn: vi.fn() });
  controller.showError(Object.assign(new Error("private runtime failure"), { stack: "SECRET_STACK" }));
  expect(document.getElementById("status").textContent).toBe("파일 확인 필요");
  expect(document.getElementById("details").textContent).not.toContain("SECRET_STACK");
});
```

- [ ] **Step 2: JS 테스트 실패 확인**

Run: `npx vitest run tests/js/dart_verify_app.test.js`

Expected: FAIL because current shell contains runtime copy and writes `error.stack` into `<pre>`.

- [ ] **Step 3: 업로드 shell을 데스크톱 결과 우선 화면으로 단순화**

`index.html`에서 `LOCAL VERIFY`, engine steps, dashboard 안내 tiles, 기술 footer를 제거한다. 입력 panel title은 `DART 원문 선택`, 설명은 `HTML 또는 DSD 추출 HTML을 선택하세요.`로 고정한다. 결과 전에는 간단한 안내만 보이고 `body.has-result`에서는 input panel을 280px로 축소하고 result panel이 나머지 너비를 사용한다.

```css
.workspace{display:grid;grid-template-columns:340px minmax(0,1fr);gap:16px;padding:16px;min-width:1280px}
body.has-result .workspace{grid-template-columns:280px minmax(0,1fr)}
.result-panel{min-width:0;overflow:auto;min-height:calc(100vh - 104px)}
```

- [ ] **Step 4: 실행 상태와 오류 행동 문구 변경**

`app.js`의 상태 문구를 다음처럼 바꾼다.

```javascript
setStatus("검증 준비 중", "loading");
setRunMeta("원문 선택 대기");
setStatus("검증 중", "running");
setStatus("검증 완료", "done");
```

`showError`는 콘솔에 기술 오류를 남기되 DOM에는 사용자 행동만 쓴다.

```javascript
function showError(error) {
  console.error(error);
  setStatus("파일 확인 필요", "error");
  setRunMeta(toKoreanErrorMessage(error));
  if (elements.details) {
    elements.details.hidden = false;
    elements.details.textContent = "DART HTML/DSD 원문을 다시 선택해 주세요.";
  }
}
```

`toKoreanErrorMessage`에서 `PyOdide`, vendor path, exception class 이름이 포함된 응답을 제거한다. PDF는 `PDF 대신 DART HTML/DSD 원문을 선택해 주세요.`, 그 외는 `지원 형식과 파일 내용을 확인해 주세요.`를 반환한다. `technicalDetails` 함수는 삭제한다.

- [ ] **Step 5: Task 6 회귀 확인**

Run: `npx vitest run tests/js/dart_verify_app.test.js && uv run pytest tests/test_build_verify_app.py tests/test_verify_app.py -q`

Expected: PASS; 런타임 이름과 stack은 사용자 DOM에 존재하지 않는다.

---

### Task 7: 전체 불변성·데스크톱 시각 QA

**Files:**
- Modify only if a failing assertion reveals an in-scope defect in Tasks 1-6
- Test: `tests/test_e2e_smoke.py`
- Test: `tests/e2e/dart-verify-parity.spec.js`
- Output: `output/playwright/desktop-audit-workbench-1440x900.png`
- Output: `output/playwright/desktop-audit-workbench-1600x1000.png`

**Interfaces:**
- Consumes: 완성된 parser, check pipeline, report frame, HTML renderer, verify-app
- Produces: 전체 테스트 통과와 두 데스크톱 viewport 시각 증거

- [ ] **Step 1: 엔진 결과 불변성 회귀 실행**

Run: `uv run pytest tests/test_checks_totals.py tests/test_checks_totals_structure.py tests/test_note_assertions.py tests/test_layout_formula_assertions.py tests/test_note_internal_harness.py -q`

Expected: PASS; 상태·금액·차이·ID·순서 회귀 assertion이 모두 유지된다.

- [ ] **Step 2: 전체 Python·JS 테스트 실행**

Run: `uv run pytest -q`

Expected: PASS.

Run: `npx vitest run tests/js/dart_verify_app.test.js`

Expected: PASS.

- [ ] **Step 3: 정적 검사 실행**

Run: `uv run ruff check src tests`

Expected: PASS with no diagnostics.

- [ ] **Step 4: 실제 대표 보고서 생성**

Run:

```bash
uv run python -c "from pathlib import Path; from dart_footing_reconciler.check_pipeline import assemble_report_checks; from dart_footing_reconciler.document import parse_full_report; from dart_footing_reconciler.report_html import export_audit_reconciliation_html; source=Path('out/corpus/run_2026-06-06-inveni-one/raw/inveni_2024_20250310000926.html'); report=parse_full_report(source, company='INVENI'); export_audit_reconciliation_html(report, assemble_report_checks(report, None, tolerance=1), 'output/playwright/desktop-audit-workbench.html', company_name='INVENI')"
```

Expected: `output/playwright/desktop-audit-workbench.html` is created without an exception.

- [ ] **Step 5: Playwright 데스크톱 상호작용·시각 QA**

사용자가 승인한 Playwright 브라우저에서 같은 fixture를 1440x900, 1600x1000으로 연다. 각 viewport에서 다음을 확인한다.

```text
1. 왼쪽에는 재무제표 본문과 각 주석만 있다.
2. 병합 머리글이 중복 셀이 아니라 실제 rowspan/colspan으로 보인다.
3. 합계·소계·총계·증감표·처분 산식 target cell에만 테두리가 있다.
4. 다른 표와의 대사를 선택하면 우측 drawer에 금액·차이·판단·다음 행동이 보인다.
5. drawer 원문 이동 후 정확한 cell이 강조되고 keyboard focus가 복원된다.
6. 넓은 표는 중앙만 가로 스크롤되며 좌우 rail과 겹치지 않는다.
7. LOCAL VERIFY, PyOdide, raw source path, stack trace가 화면에 없다.
```

스크린샷을 다음 경로에 저장한다.

```text
output/playwright/desktop-audit-workbench-1440x900.png
output/playwright/desktop-audit-workbench-1600x1000.png
```

- [ ] **Step 6: 최종 상태보고**

다음을 사용자에게 보고한다.

```text
- 변경 파일
- 추가한 parser/role/presentation/HTML/verify-app 테스트
- `uv run pytest -q` 마지막 결과
- `uv run ruff check src tests` 마지막 결과
- 두 desktop viewport QA 결과
- React/Next.js를 도입하지 않은 근거와 향후 도입 조건
```
