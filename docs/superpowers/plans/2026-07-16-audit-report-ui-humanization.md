# 검증보고서 UI 업무용 문구 정리 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 검증보고서 HTML/DOM과 감사용 Excel에서 내부 코드·영문 기술 문구를 제거하고 감사자용 한국어와 정돈된 UI만 표시한다.

**Architecture:** 엔진의 `CheckResult` 값은 그대로 두고 `report_frame.py`에 표면 공통 표시명·상태·사유 변환을 둔다. HTML과 Excel은 이 표시 계층만 사용하며, HTML 상호작용 ID는 검증 ID 대신 렌더링 순서로 생성한다. verify-app은 기존 `_build_html(...)` 경로를 그대로 재사용한다.

**Tech Stack:** Python 3.12, pytest, BeautifulSoup, openpyxl, HTML/CSS, Playwright CLI

## Global Constraints

- `CheckResult`의 상태, 금액, ID, 순서와 검증 엔진 출력은 변경하지 않는다.
- Footing과 현금흐름 대사 검증을 결합하지 않는다.
- 원문 이동에 필요한 내부 근거 값은 계산에만 사용하고 최종 HTML/DOM에는 삽입하지 않는다.
- HTML, verify-app, Excel 사이에 별도 검증 문구 사전을 만들지 않는다.
- 새 의존성을 추가하지 않는다.
- 각 동작은 실패 테스트를 먼저 확인한 뒤 최소 구현으로 통과시킨다.
- git 명령은 실행하지 않는다.

---

### Task 1: 공통 감사자용 표시 문구

**Files:**
- Modify: `src/dart_footing_reconciler/report_frame.py`
- Modify: `src/dart_footing_reconciler/audit_workbook.py`
- Test: `tests/test_report_frame.py`
- Test: `tests/test_audit_workbook.py`

**Interfaces:**
- Consumes: `CheckResult.check_type`, `.title`, `.reason`, `.status`
- Produces: `check_display_title(check: CheckResult) -> str`, `check_display_reason(check: CheckResult) -> str`, `check_status_label(status: str) -> str`, `CHECK_DISPLAY_NAMES`

- [ ] **Step 1: 공통 표시 함수의 실패 테스트 작성**

`tests/test_report_frame.py`에 다음 테스트를 추가한다.

```python
def test_check_display_copy_hides_internal_english_terms():
    from dart_footing_reconciler.checks import CheckResult, MATCHED, PARSE_UNCERTAIN
    from dart_footing_reconciler.report_frame import (
        check_display_reason,
        check_display_title,
        check_status_label,
    )

    matched = CheckResult(
        "private:id",
        "fs_note_match",
        MATCHED,
        "report",
        "11",
        "리스부채 FS to note match (current)",
        100,
        100,
        0,
        1,
        "financial statement amount agrees to note amount",
        [],
    )
    uncertain = CheckResult(
        "private:uncertain",
        "note_note_match",
        PARSE_UNCERTAIN,
        "note",
        "11",
        "ppe note to note match",
        None,
        None,
        None,
        1,
        "multiple candidate note amounts found",
        [],
        parse_uncertain_reason="AMBIGUOUS_MULTIPLE",
    )

    assert check_display_title(matched) == "재무제표-주석 대사"
    assert check_display_reason(matched) == "재무제표 금액과 주석 금액이 일치함"
    assert check_display_title(uncertain) == "주석 간 금액 대사"
    assert check_display_reason(uncertain) == "비교할 후보가 여러 개여서 자동으로 확정하지 못했습니다."
    assert check_status_label(PARSE_UNCERTAIN) == "자동 해석 확인"
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_report_frame.py::test_check_display_copy_hides_internal_english_terms -q`

Expected: FAIL because the three display functions do not exist.

- [ ] **Step 3: 공통 표시 레지스트리와 함수 구현**

`report_frame.py`에서 `CHECK_METHOD_DESCRIPTIONS` 다음에 `CHECK_DISPLAY_NAMES`를 추가한다. 키는 `CHECK_GROUPS`와 정확히 일치시키고 각 값은 아래 문구를 사용한다.

```python
CHECK_DISPLAY_NAMES: dict[str, str] = {
    "statement_bs_equation": "재무상태표 등식 검증",
    "statement_cash_tie": "현금및현금성자산 대사",
    "statement_equity_tie": "자본총계 대사",
    "total_check": "표 합계 검증",
    "prior_year_beginning_balance_match": "전기말-당기초 대사",
    "prior_column_fs_note": "전기 재무제표-주석 대사",
    "prior_column_rollforward": "전기 기초잔액 대사",
    "prior_year_amount_match": "전기 공시 금액 대사",
    "prior_year_structure_change": "전기 주석 구조 확인",
    "cfs_note_match": "현금흐름표-주석 대사",
    "primary_balance_reconciliation": "재무상태표-주석 잔액 대사",
    "cashflow_reconciliation": "현금흐름 금액 대사",
    "fs_note_match": "재무제표-주석 대사",
    "asset_note_bridge_check": "자산 취득·처분 대사",
    "expense_allocation": "비용 배분 대사",
    "note_reference_check": "주석 참조 확인",
    "note_note_match": "주석 간 금액 대사",
    "note_note_reconciliation": "주석 간 잔액 대사",
    "note_rollforward_check": "주석 증감표 검산",
    "note_balance_bridge_check": "주석 잔액 합계 검증",
    "note_internal_consistency_check": "주석 내부 일관성 검증",
    "note_layout_formula_check": "주석 표 산식 검증",
    "appropriation_formula_check": "이익잉여금 처분 산식 검증",
}
```

같은 파일에 정확 일치 사유 사전과 안전한 상태별 대체 문구를 둔다. `audit_workbook._reason_text`의 기존 사유 사전 전체를 이곳으로 이동하고 아래 항목을 추가한다.

```python
_DISPLAY_REASON_TEXTS = {
    "row total agrees": "행 구성항목 합계가 표시 금액과 일치함",
    "column total agrees": "열 구성항목 합계가 표시 금액과 일치함",
    "row total does not agree": "행 구성항목 합계와 표시 금액 간 차이가 있음",
    "column total does not agree": "열 구성항목 합계와 표시 금액 간 차이가 있음",
    "no reliable total label found": "합계/소계 표시를 신뢰성 있게 식별하지 못함",
    "financial statement amount agrees to note amount": "재무제표 금액과 주석 금액이 일치함",
    "financial statement amount agrees within display-unit rounding": (
        "재무제표 금액과 주석 금액의 차이가 표시단위 절사 허용범위 내에 있음"
    ),
    "financial statement amount does not agree to note amount": "재무제표 금액과 주석 금액 간 차이가 있음",
    "financial statement line agrees to note ending balance": "재무제표 계정과 주석 기말 장부금액이 일치함",
    "financial statement line does not agree to note ending balance": (
        "재무제표 계정과 주석 기말 장부금액 간 차이가 있음"
    ),
    "cash flow statement amount agrees to note movement": "현금흐름표 항목과 관련 주석 변동금액이 일치함",
    "cash flow statement amount does not agree to note movement": (
        "현금흐름표 항목과 관련 주석 변동금액 간 차이가 있음"
    ),
    "cash flow statement line agrees to note cash movement": "현금흐름표 금액 크기와 주석 현금성 변동금액이 일치함",
    "cash flow statement line does not agree to note cash movement": (
        "현금흐름표 금액 크기와 주석 현금성 변동금액 간 차이가 있음"
    ),
    "current comparative amount agrees to prior current amount": "당기 비교표시 전기금액과 전기 공시 당기금액이 일치함",
    "current comparative amount does not agree to prior current amount": (
        "당기 비교표시 전기금액과 전기 공시 당기금액 간 차이가 있음"
    ),
    "prior-year ending balance agrees to current-year beginning balance": "전기말 주석 금액과 당기초 주석 금액이 일치함",
    "prior-year ending balance does not agree to current-year beginning balance": (
        "전기말 주석 금액과 당기초 주석 금액 간 차이가 있음"
    ),
    "related note amounts agree": "관련 주석에 반복 공시된 금액이 일치함",
    "multiple candidate note amounts found": "비교할 후보가 여러 개여서 자동으로 확정하지 못했습니다.",
    "candidate difference exceeds statement amount; note balance match is parse uncertain": (
        "후보 금액 차이가 재무제표 금액보다 커서 자동으로 확정하지 못했습니다."
    ),
}

_STATUS_LABELS = {
    "matched": "일치",
    "explainable_gap": "차이 설명 가능",
    "unexplained_gap": "미해소 차이",
    "parse_uncertain": "자동 해석 확인",
    "not_tested": "검증 미수행",
}

_GENERIC_REASON_BY_STATUS = {
    "matched": "비교 금액이 허용오차 안에서 일치합니다.",
    "explainable_gap": "차이가 확인되었으며 공시 근거로 설명됩니다.",
    "unexplained_gap": "비교 금액의 차이 원인을 확인해야 합니다.",
    "parse_uncertain": "원문 구조를 자동으로 확정하지 못했습니다.",
    "not_tested": "적용 가능한 검증 근거를 확정하지 못했습니다.",
}
```

함수는 내부 영문이 남으면 검증 유형/상태별 안전 문구로 대체한다.

```python
def check_display_title(check: CheckResult) -> str:
    title = check.title.strip()
    replacements = (
        ("FS to note match", "재무제표-주석 대사"),
        ("CFS to note match", "현금흐름표-주석 대사"),
        ("note to note match", "주석 간 금액 대사"),
        ("BS equation", "재무상태표 등식"),
        ("total check", "합계 검증"),
        ("column total", "열 합계 검증"),
    )
    for source, target in replacements:
        title = title.replace(source, target)
    if re.search(r"[A-Za-z_]", title):
        return CHECK_DISPLAY_NAMES.get(check.check_type, "기타 검증")
    return title or CHECK_DISPLAY_NAMES.get(check.check_type, "기타 검증")


def check_display_reason(check: CheckResult) -> str:
    if check.parse_uncertain_reason == "AMBIGUOUS_MULTIPLE":
        return _DISPLAY_REASON_TEXTS["multiple candidate note amounts found"]
    reason = _DISPLAY_REASON_TEXTS.get(check.reason, check.reason).strip()
    reason = reason.replace("BS", "재무상태표").replace("SCE", "자본변동표")
    if re.search(r"[A-Za-z_]", reason):
        return _GENERIC_REASON_BY_STATUS.get(check.status, "검증 결과를 확인해야 합니다.")
    return reason or _GENERIC_REASON_BY_STATUS.get(check.status, "검증 결과를 확인해야 합니다.")


def check_status_label(status: str) -> str:
    return _STATUS_LABELS.get(status, "확인 필요")
```

`report_frame.py` 상단에 `import re`가 이미 있으므로 재사용한다. `tests/test_report_frame.py::test_check_method_descriptions_match_registered_check_types`에 `assert CHECK_DISPLAY_NAMES.keys() == CHECK_GROUPS.keys()`를 추가한다.

- [ ] **Step 4: 공통 표시 함수 테스트 통과 확인**

Run: `uv run pytest tests/test_report_frame.py -q`

Expected: PASS.

- [ ] **Step 5: Excel 표면의 실패 테스트 작성**

`tests/test_audit_workbook.py::test_export_audit_workbook_uses_business_labels_for_matching_checks`에 다음 기대값을 추가한다.

```python
assert ws["B7"].value == "재무제표-주석 대사"
assert ws["H7"].value == "재무제표 금액과 주석 금액이 일치함"
assert "FS to note match" not in ws["B7"].value
```

Run: `uv run pytest tests/test_audit_workbook.py::test_export_audit_workbook_uses_business_labels_for_matching_checks -q`

Expected: FAIL because B7 still contains the raw title.

- [ ] **Step 6: Excel이 공통 표시 함수를 사용하도록 변경**

`audit_workbook.py`의 `report_frame` import에 `check_display_title`, `check_display_reason`, `check_status_label`을 추가한다. `_write_check_row`의 값 세 곳을 다음처럼 바꾼다.

```python
values = [
    check_group(check),
    check_display_title(check),
    _trace_text(check, source_map),
    formula_values[0],
    formula_values[1],
    formula_values[2],
    check_status_label(check.status),
    check_display_reason(check),
    _evidence_text(check, source_map),
    CHECK_METHOD_DESCRIPTIONS.get(check.check_type, "-"),
]
```

기존 `_reason_text`와 `_status_label` 함수는 삭제해 표면별 사전 중복을 없앤다.

- [ ] **Step 7: Task 1 회귀 테스트**

Run: `uv run pytest tests/test_report_frame.py tests/test_audit_workbook.py tests/test_surface_parity.py -q`

Expected: PASS.

---

### Task 2: HTML/DOM 내부 값 제거

**Files:**
- Modify: `src/dart_footing_reconciler/report_html.py`
- Test: `tests/test_report_html_evidence.py`
- Test: `tests/test_report_html_new.py`

**Interfaces:**
- Consumes: Task 1의 `check_display_title`, `check_display_reason`, `CHECK_DISPLAY_NAMES`
- Produces: 원시 검증 ID·유형·근거·영문 사유 코드가 없는 HTML

- [ ] **Step 1: 범례·드릴다운·DOM 비노출 실패 테스트 작성**

`tests/test_report_html_evidence.py`에 다음 테스트를 추가한다.

```python
def test_report_html_excludes_internal_check_metadata(tmp_path):
    from dart_footing_reconciler.report_html import export_audit_reconciliation_html

    report = _report_with_note()
    check = CheckResult(
        "private_total_check_identifier",
        "total_check",
        MATCHED,
        "note",
        "8",
        "내부 합계 검증",
        300,
        300,
        0,
        1,
        "row total agrees",
        [CheckEvidence("합계", 300, "note:8/table:28/row:1/col:1", role="total")],
    )
    out = tmp_path / "report.html"

    export_audit_reconciliation_html(report, [check], out)
    content = out.read_text(encoding="utf-8")

    assert "private_total_check_identifier" not in content
    assert "total_check" not in content
    assert "note:8/table:28/row:1/col:1" not in content
    assert "기술 세부정보" not in content
    assert "표 안의 구성요소 합계 = 표시된 합계" in content
    assert "주석8" in content
```

`tests/test_report_html_new.py::test_parse_uncertain_panel_present`의 기대값을 다음처럼 변경한다.

```python
assert "panel-parse-diag" in content
assert "LABEL_NOT_FOUND" not in content
assert "statement:bs/table:0/row:1" not in content
assert "자동 해석 확인" in content
assert "공시에서 해당 계정과목을 찾지 못했습니다." in content
assert "원문에 해당 항목이 있다면 검토를 요청하세요." in content
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_report_html_evidence.py::test_report_html_excludes_internal_check_metadata tests/test_report_html_new.py::test_parse_uncertain_panel_present -q`

Expected: FAIL on raw check ID/type/source and old diagnostic copy.

- [ ] **Step 3: HTML 렌더러가 공통 표시 함수를 사용하도록 변경**

`report_html.py`에서 Task 1의 함수들을 import한다.

```python
from dart_footing_reconciler.report_frame import (
    CHECK_DISPLAY_NAMES,
    CHECK_GROUP_ORDER,
    CHECK_GROUPS,
    CHECK_METHOD_DESCRIPTIONS,
    TABLE_UNIT_TOLERANCE_CHECK_TYPES,
    check_display_reason,
    check_display_title,
)
```

다음 모든 표시 위치에서 `result.title` 대신 `check_display_title(result)`, `result.reason` 대신 `check_display_reason(result)`을 사용한다.

- `_render_attention_panel`
- `_render_drilldown`
- `_render_check_summary`
- `_render_expandable_check_summary`
- `_render_parse_uncertain_panel`

주석 패널 제목 정리는 `def _display_check_title(result: CheckResult, section: ReportSection) -> str`로 바꾸고 첫 줄을 `out = check_display_title(result)`로 한다. 호출 람다도 `lambda result: _display_check_title(result, section)`을 유지한다.

- [ ] **Step 4: 검증 ID 대신 화면 전용 순번 ID 사용**

`_render_attention_panel`은 `for index, result in enumerate(flagged):`로 순회하고 `dd_id = f"dd-attn-{index}"`를 사용한다. `_render_expandable_check_summary`도 `enumerate(results)`와 `dd_id = f"{id_prefix}-{index}"`를 사용한다. `_render_note_panel`은 패널 간 충돌 방지를 위해 다음 prefix를 넘긴다.

```python
id_prefix=f"{_safe_id(panel_id)}-check"
```

이 변경은 `CheckResult` 순서를 바꾸지 않는다.

- [ ] **Step 5: 원시 근거와 영문 진단 코드를 마크업에서 제거**

`_humanize_source`의 파싱 불가 fallback을 원시 문자열 대신 다음처럼 바꾼다.

```python
if parsed is None:
    return "근거 위치 확인 필요"
```

`_render_drilldown`에서 `raw_rows` 생성과 `<details class="tech-detail">...</details>`를 삭제한다. 자동 해석 사유는 다음처럼 표시한다.

```python
uncertain_note = ""
if result.parse_uncertain_reason:
    uncertain_note = (
        f'<div class="callout unc">자동 해석 확인: '
        f'{_esc(_uncertain_reason_text(result.parse_uncertain_reason))}</div>'
    )
```

`_render_parse_uncertain_panel` 시그니처를 `def _render_parse_uncertain_panel(results: list[CheckResult], report: FullReport) -> str`로 바꾸고 `_build_html`에서 `report`를 전달한다. 카드의 근거 목록은 다음처럼 만든다.

```python
candidates_text = "".join(
    f"<li><strong>확인 대상</strong><span>{_esc(ev.label)} · "
    f"{_esc(_humanize_source(report, ev.source))}</span></li>"
    for ev in result.evidence
    if ev.source
)
```

사유 배지는 없애고 한국어 설명만 표시한다. 패널 카피는 설계 문서의 `자동 해석 확인` 문구를 그대로 사용한다. `_uncertain_reason_text`의 fallback은 `원문 구조를 자동으로 확정하지 못했습니다.`로 바꾼다.

- [ ] **Step 6: Task 2 테스트 통과 확인**

Run: `uv run pytest tests/test_report_html_evidence.py tests/test_report_html_new.py -q`

Expected: PASS after old raw-string expectations are repinned to the approved Korean copy.

---

### Task 3: 공통 상태 문구와 UI 서식 정돈

**Files:**
- Modify: `src/dart_footing_reconciler/report_html.py`
- Test: `tests/test_report_html_cockpit.py`
- Test: `tests/test_verify_app.py`

**Interfaces:**
- Consumes: 기존 상태 집계와 Task 2의 안전한 HTML
- Produces: 구현 관점 진단 용어가 없는 데스크톱·모바일 UI

- [ ] **Step 1: 상태·진행 문구 실패 테스트 작성**

`tests/test_report_html_cockpit.py`의 기존 KPI 기대값을 `자동 해석 확인`으로 바꾸고 다음 테스트를 추가한다.

```python
def test_report_chrome_uses_auditor_facing_language(tmp_path: Path):
    content = _mixed_report(tmp_path)

    assert "자동 해석 확인" in content
    assert "보고서 표시 확인 필요 0건" in content
    assert "원문 위치 확인 필요 0건" in content
    assert "파싱 불확실" not in content
    assert "파싱불확실" not in content
    assert "배치되지 않은 검증" not in content
    assert "근거 연결 실패" not in content
```

테스트 fixture의 제목과 사유도 결과 데이터 자체가 기술 용어를 강제로 넣지 않도록 `자동 해석 확인 항목`, `자동 해석 확인 필요`로 바꾼다. 기존 `배치되지 않은 검증`, `근거 연결 실패` 기대값은 각각 `보고서 표시 확인 필요`, `원문 위치 확인 필요`로 일괄 갱신한다. `tests/test_verify_app.py`의 KPI 기대도 `자동 해석 확인`으로 바꾼다.

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_report_html_cockpit.py::test_report_chrome_uses_auditor_facing_language -q`

Expected: FAIL because the old chrome copy remains.

- [ ] **Step 3: 모든 사용자 화면 문구 변경**

`report_html.py`에서 아래 문구를 정확히 바꾼다.

```text
파싱 불확실 / 파싱불확실 -> 자동 해석 확인 / 해석확인필요
파싱 진단 -> 자동 해석 확인
파싱 사유 -> 자동 해석 확인
배치되지 않은 검증 -> 보고서 표시 확인 필요
근거 연결 실패 -> 원문 위치 확인 필요
```

대상은 masthead, sidebar, KPI, next actions, progress table·진단, attention 설명·필터, legend counts, account state badge다. 내부 상태 상수와 집계 dictionary key는 변경하지 않는다.

- [ ] **Step 4: 범례·진단·드릴다운 CSS 정돈**

기존 CSS 토큰만 사용해 다음 규칙으로 교체한다.

```css
.method-line{margin:10px 0 2px;padding:8px 10px;border-left:3px solid var(--accent);background:var(--surface-2);font-size:11px;font-weight:700;color:var(--text);}
.diag-card{border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:12px;background:var(--surface);}
.diag-title{font-size:13px;font-weight:800;margin-bottom:8px;}
.diag-reason{margin-bottom:10px;padding:8px 10px;border-left:3px solid var(--warn);background:var(--warn-dim);font-size:12px;}
.diag-candidates{list-style:none;margin:0;font-size:11px;color:var(--muted);}
.diag-candidates li{display:flex;gap:8px;padding:7px 0;border-bottom:1px solid var(--border);}
.diag-candidates li:last-child{border-bottom:0;}
.diag-candidates strong{flex:0 0 auto;color:var(--text);}
.diag-guide{margin-top:10px;padding-top:8px;border-top:1px solid var(--border);font-size:11px;color:var(--muted);}
.legend-methods{list-style:none;}
.legend-methods li{display:block;padding:10px 12px;border-bottom:1px solid var(--border);font-size:11px;line-height:1.55;}
.legend-methods li:last-child{border-bottom:none;}
```

기존 `.tech-detail`, `.legend-methods code`, 2열 grid 규칙은 삭제한다.

- [ ] **Step 5: Task 3 회귀 테스트**

Run: `uv run pytest tests/test_report_html_cockpit.py tests/test_report_html_evidence.py tests/test_report_html_new.py tests/test_verify_app.py tests/test_surface_parity.py -q`

Expected: PASS. `tests/test_verify_app.py`는 로컬 corpus fixture가 없으면 해당 실패를 환경 제약으로 기록하고 fixture 비의존 테스트를 모두 통과시킨다.

---

### Task 4: 전체 검증과 브라우저 QA

**Files:**
- No production changes expected
- Artifacts: `output/playwright/` only if screenshots are retained

**Interfaces:**
- Consumes: Tasks 1–3의 최종 보고서 HTML
- Produces: 테스트·린트·데스크톱·모바일 QA 증거

- [ ] **Step 1: 내부 문자열 정적 스캔**

Run:

```bash
rg -n '기술 세부정보|issue를 제보|<code>|파싱 진단|파싱 불확실|파싱불확실|배치되지 않은 검증|근거 연결 실패' src/dart_footing_reconciler/report_html.py
```

Expected: no matches in user-facing renderer literals.

- [ ] **Step 2: 전체 Python 테스트**

Run: `uv run pytest -q`

Expected: zero failures. Local-only corpus fixture absence is not a product regression; if it is the sole failure source, run and report the complete fixture-independent suite separately rather than claiming the full suite passed.

- [ ] **Step 3: 린트**

Run: `uv run ruff check`

Expected: `All checks passed!`

- [ ] **Step 4: 대표 HTML 생성**

테스트 fixture와 같은 최소 `FullReport`를 사용해 매칭·차이·자동 해석 확인 결과가 모두 있는 HTML을 임시 경로에 생성한다. 저장소 산출물을 남길 경우에만 `output/playwright/audit-report-ui.html`을 사용한다.

- [ ] **Step 5: Playwright 데스크톱 QA**

Run:

```bash
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
export PWCLI="$CODEX_HOME/skills/playwright/scripts/playwright_cli.sh"
"$PWCLI" open "file:///absolute/path/to/audit-report-ui.html" --headed
"$PWCLI" snapshot
"$PWCLI" screenshot --filename output/playwright/audit-report-ui-desktop.png
```

검증 범례, 검증 상세, 자동 해석 확인 패널을 각각 열어 코드 문자열, 잘림, 과밀, 클릭 동작을 확인한다.

- [ ] **Step 6: Playwright 모바일 QA**

Run:

```bash
"$PWCLI" resize 390 844
"$PWCLI" snapshot
"$PWCLI" screenshot --filename output/playwright/audit-report-ui-mobile.png --full-page
```

범례가 단일 열이고 진단 카드와 근거 표가 가로로 잘리지 않는지 확인한다.

- [ ] **Step 7: 최종 요구사항 대조**

설계 문서의 성공 기준을 한 줄씩 대조하고 변경 파일, 추가/수정 테스트, `pytest`와 `ruff` 결과, 브라우저 QA 결과를 보고한다. 검증 엔진 파일이 수정되지 않았음을 파일 목록으로 확인한다.
