# Audit-Grade Reinforcement Roadmap — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 2026-07-09 감사인 관점 전수 점검에서 나온 10개 보강 영역을 6개 Phase(= 6개 이상의 독립 PR 슬라이스)로 나눠, 허위 일치 차단 → 선언 범위 완성 → 본문 footing → 정확도 측정 체계 → 설명 어휘 → 범위 확장 순으로 실행한다.

**Architecture:** 기존 4-harness 파이프라인(`assemble_report_checks`)과 5-status 계약은 그대로 두고, (i) 파싱 층의 단위 결함을 수리하고, (ii) 대사 대상 레지스트리(`RECONCILIATION_TARGETS`)와 harness 배선의 누락을 채우고, (iii) 본문 footing 은 새 `StatementInternalHarness` 로 추가한다. 모든 신규 체크는 abstain-first(v1 은 MATCHED/PARSE_UNCERTAIN 만) → 코퍼스 triage 후 UNEXPLAINED_GAP 승격의 2단 롤아웃을 따른다.

**Tech Stack:** Python 3 / dataclasses, pytest, uv, ruff. 코퍼스: 로컬 10-co + 18-co manifest (HANDOFF.md "Corpus operations").

---

## 프로젝트 불변 규칙 (모든 Phase 공통)

각 Phase = `main` 에서 딴 브랜치 1개 = PR 1개. 각 PR 은 HANDOFF.md "The proven loop" 를 그대로 따른다:

1. TDD: 회귀 핀(regression pin) 테스트 먼저.
2. **코퍼스 하드 게이트** — 변경 전후로 두 manifest(10-co `manifest_2026-06-10-nonfinancial-industry-10.json`, 18-co `manifest_2026-06-22-nonfinancial-expansion.json`) 전체 실행:
   - `matched` ↑ 또는 유지. 신규 matched 는 전건 육안 확인(허위 일치 0).
   - `unexplained_gap` 감소는 제거된 FP 임을 건별 확인.
   - 기존 check_type 의 결과는 fingerprint diff 로 byte-identical (신규 check_type 만 추가분 허용).
   - `uv run python scripts/check_per_company_snapshot.py` HARD 게이트 (두 baseline 모두).
   - **genuine match 파괴 0건.**
3. 신규 check_type 이 baseline 카운트를 바꾸면: 신규분 전건 triage 표를 PR 본문에 첨부한 뒤에만 baseline JSON 갱신.
4. cross-model review (Opus code-reviewer + Codex adversarial) 후 merge. merge 는 사용자 명시 요청 시에만.
5. `uv run pytest -q` ×2 (결정론 확인) + `uv run ruff check` clean.

**도메인 원칙 (위반 시 계획이 아니라 원칙이 이긴다):** 허위 일치 절대 금지 · 추측보다 기권 · 산술은 결정론적 Python · `not_tested` 는 커버리지로 표면화(절대 드롭 금지).

**신규 check_type 의 Definition of Done (Phase R 이 정의하는 표면 완전성 규칙):** 새 check_type 을 추가하는 모든 PR 은 ① `report_frame.CHECK_GROUPS`/`CHECK_LAYERS`/`CHECK_METHOD_DESCRIPTIONS` 등록, ② 드릴다운 렌더 테스트, ③ 근거 앵커 해석 테스트를 포함해야 한다. 화면에 배치되지 않는 체크는 "배치되지 않은 검증 N건" 진단(Task R.1)에 걸리며, N>0 상태로 merge 할 수 없다.

---

# Phase 1 — 단위 파싱 견고화 (허위 일치 원천 차단)

브랜치: `fix/unit-detection-hardening`

### Task 1.1: `_unit_multiplier` 억원 지원

**Files:**
- Modify: `src/dart_footing_reconciler/document.py:388-398`
- Test: `tests/test_document.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_unit_multiplier_recognizes_eokwon():
    from dart_footing_reconciler.document import _unit_multiplier

    assert _unit_multiplier("(단위: 억원)") == 100_000_000
    # 기존 동작 회귀 핀
    assert _unit_multiplier("(단위: 백만원)") == 1_000_000
    assert _unit_multiplier("(단위: 천원)") == 1_000
    assert _unit_multiplier("(단위: 원)") == 1
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_document.py::test_unit_multiplier_recognizes_eokwon -v`
Expected: FAIL — 억원이 `"원" in compact` 분기로 떨어져 `1` 반환.

- [ ] **Step 3: 최소 구현**

```python
def _unit_multiplier(text: str) -> int | None:
    compact = _normalize(text)
    if "단위" not in compact:
        return None
    if "백만원" in compact:
        return 1_000_000
    if "천원" in compact:
        return 1_000
    if "억원" in compact:          # 억원 은 반드시 bare 원 앞에서 검사
        return 100_000_000
    if "원" in compact:
        return 1
    return None
```

- [ ] **Step 4: 통과 확인** — `uv run pytest tests/test_document.py -v` Expected: PASS
- [ ] **Step 5: Commit** — `git commit -m "fix: recognize 억원 unit multiplier in document parser"`

### Task 1.2: '단위' 리터럴 없는 괄호 단위 인식

**Files:**
- Modify: `src/dart_footing_reconciler/document.py` (`_unit_multiplier`, `_is_unit_marker_table`)
- Test: `tests/test_document.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_unit_multiplier_parenthesized_unit_without_danwi_literal():
    from dart_footing_reconciler.document import _unit_multiplier

    assert _unit_multiplier("(백만원)") == 1_000_000
    assert _unit_multiplier("연결재무상태표 (천원)") == 1_000
    assert _unit_multiplier("(억원)") == 100_000_000
    # 오탐 가드: 괄호 안이 단위 토큰 단독이 아니면 발화 금지
    assert _unit_multiplier("1,234백만원") is None
    assert _unit_multiplier("백만원") is None
    assert _unit_multiplier("(주식수: 주, 금액: 원)") is None
```

- [ ] **Step 2: 실패 확인** — Run: `uv run pytest tests/test_document.py -k parenthesized -v` Expected: FAIL

- [ ] **Step 3: 구현** — `_normalize` 는 공백만 제거하므로(document.py `_normalize`) 괄호는 보존된다. 단위-단독 괄호 패턴만 허용하는 fallback 을 추가:

```python
_PAREN_UNIT_RE = re.compile(r"\((억원|백만원|천원|원)\)")

def _unit_multiplier(text: str) -> int | None:
    compact = _normalize(text)
    if "단위" in compact:
        if "백만원" in compact:
            return 1_000_000
        if "천원" in compact:
            return 1_000
        if "억원" in compact:
            return 100_000_000
        if "원" in compact:
            return 1
        return None
    m = _PAREN_UNIT_RE.search(compact)
    if m is None:
        return None
    return {"억원": 100_000_000, "백만원": 1_000_000, "천원": 1_000, "원": 1}[m.group(1)]
```

`_is_unit_marker_table` 의 발화 조건도 동일하게 확장 (기존 재무 키워드 배제 목록은 유지):

```python
    return ("단위" in compact or _PAREN_UNIT_RE.search(compact) is not None) and not any(
        keyword in compact
        for keyword in ("매출", "자산", "부채", "자본", "순이익", "영업이익", "포괄손익")
    )
```

- [ ] **Step 4: 전체 테스트 통과 확인** — `uv run pytest tests/test_document.py -v`
- [ ] **Step 5: 코퍼스 게이트** — 두 manifest 실행. 단위 재인식으로 값이 바뀐 표를 전수 diff 하고, 신규 matched/gap 전건 triage.
- [ ] **Step 6: Commit**

### Task 1.3: 단위 전염(sticky multiplier) 계측 → 영역 경계 리셋

**Files:**
- Create: `scripts/instrument_unit_inheritance.py`
- Modify: `src/dart_footing_reconciler/document.py` (파싱 루프, `ReportTable`)
- Test: `tests/test_document.py`

- [ ] **Step 1: 계측 스크립트 작성 (구현 前 데이터 확인 — 리셋 정책의 근거)**

```python
"""18-co 코퍼스에서 단위 상속 실태 계측.

표별로 (a) 자체 선언 단위 vs (b) 직전 표에서 상속된 단위인지,
(c) 상속이 본문↔주석 영역 경계를 넘는지 집계한다.
"""
import json, sys
from pathlib import Path
from dart_footing_reconciler.document import parse_full_report

manifest = json.loads(Path(sys.argv[1]).read_text())
declared = inherited = cross_area = 0
for entry in manifest["companies"]:
    report = parse_full_report(entry["html_path"], company=entry["name"])
    prev_mult, prev_kind = None, None
    for kind, sections in (("statement", report.statements), ("note", report.notes)):
        for section in sections:
            for block in section.blocks:
                if block.table is None:
                    continue
                t = block.table
                own = t.unit_multiplier != (prev_mult or 1) or prev_mult is None
                if own:
                    declared += 1
                else:
                    inherited += 1
                    if prev_kind is not None and prev_kind != kind:
                        cross_area += 1
                prev_mult, prev_kind = t.unit_multiplier, kind
print(f"declared={declared} inherited={inherited} cross_area={cross_area}")
```

- [ ] **Step 2: 계측 실행 및 기록** — Run: `uv run python scripts/instrument_unit_inheritance.py out/corpus/manifest_2026-06-22-nonfinancial-expansion.json`
  결과 수치를 `docs/accuracy-backlog.md` 에 "unit inheritance 계측 (2026-07)" 절로 기록. cross_area > 0 이면 Step 3 진행, 0 이면 이 태스크는 provenance 필드(Step 3의 `unit_declared`)만 남기고 리셋은 보류.

- [ ] **Step 3: 실패하는 테스트 작성 — 영역 경계에서 단위 리셋 + provenance**

```python
def test_unit_multiplier_resets_at_note_area_boundary():
    """본문(천원 선언) 뒤 주석 영역 첫 표가 단위 미선언이면
    천원을 물려받지 않고 multiplier=1 + unit_declared=False 여야 한다."""
    html = """
    <p>재무상태표</p>
    <table><tr><td>(단위: 천원)</td></tr></table>
    <table><tr><td>자산총계</td><td>100</td></tr></table>
    <p>주석</p>
    <p>1. 일반사항</p>
    <table><tr><td>구분</td><td>금액</td></tr><tr><td>지분율</td><td>50</td></tr></table>
    """
    report = _parse_html_string(html)  # tests/test_document.py 기존 헬퍼 재사용
    note_table = report.notes[0].blocks[-1].table
    assert note_table.unit_multiplier == 1
    assert note_table.unit_declared is False
```

- [ ] **Step 4: 구현** — ① `ReportTable` 에 `unit_declared: bool = False` 필드 추가(heading/leading-row/marker-table 로 단위가 정해진 경우만 True). ② 파싱 루프에서 `_toc_area_transition` · `_note_area_marker` · `_non_note_area_marker` 로 영역이 바뀌는 지점(document.py:97-118, 170-178)에서 `current_unit_multiplier = 1` 로 리셋. 같은 영역 내부의 상속(주석 서두에 한 번 선언 후 이어지는 표들)은 유지.
- [ ] **Step 5: 전체 테스트 + 코퍼스 게이트** — 리셋으로 값이 바뀌는 표 전수 diff. matched 파괴 0 확인. 상속이 정당했던 표가 깨지면 리셋 지점을 TOC 전환으로 한정하는 것으로 후퇴.
- [ ] **Step 6: Commit**

### Task 1.4: 단위 불일치 의심 가드 (×1000 개연성 체크)

**Files:**
- Create: `src/dart_footing_reconciler/` 내 `amount_compare.py` 에 헬퍼 추가
- Modify: `src/dart_footing_reconciler/checks_fs_note.py` (UNEXPLAINED_GAP 판정 직전), `src/dart_footing_reconciler/label_resolver.py` (`PARSE_UNCERTAIN_REASONS`)
- Test: `tests/test_amount_compare.py`, `tests/test_checks_fs_note.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_unit_mismatch_suspected():
    from dart_footing_reconciler.amount_compare import unit_mismatch_suspected

    # 주석이 천원 스케일 누락 → 본문과 정확히 1000배 차이
    assert unit_mismatch_suspected(5_123_456, 5_123_456_000, tolerance=1) is True
    assert unit_mismatch_suspected(5_123_456_000, 5_123_456, tolerance=1) is True
    # 일반 차이는 발화 금지
    assert unit_mismatch_suspected(5_123_456, 5_200_000, tolerance=1) is False
    assert unit_mismatch_suspected(0, 1_000, tolerance=1) is False
```

- [ ] **Step 2: 실패 확인** — `uv run pytest tests/test_amount_compare.py -k mismatch -v`

- [ ] **Step 3: 구현**

```python
def unit_mismatch_suspected(a: int, b: int, tolerance: int) -> bool:
    """두 금액이 정확히 1000배 관계이면 단위 스케일 누락 의심.

    허위 unexplained_gap 대신 parse_uncertain(단위 의심)으로 기권하기 위한 가드.
    """
    if a == 0 or b == 0:
        return False
    return abs(a * 1000 - b) <= tolerance or abs(a - b * 1000) <= tolerance
```

`label_resolver.py` 의 `PARSE_UNCERTAIN_REASONS` 에 `UNIT_MISMATCH_SUSPECTED = "unit_mismatch_suspected"` 추가. `checks_fs_note.py` 의 fs↔note 비교에서 UNEXPLAINED_GAP 이 되기 직전에 이 가드를 통과하면 status 를 PARSE_UNCERTAIN + 해당 reason 으로 강등. `report_html.py` 의 reason 텍스트 맵(716-724 부근)에 `"단위(천원/백만원) 스케일 불일치 의심 — 원문 단위 확인 필요"` 추가.

- [ ] **Step 4: 통과 확인 + 코퍼스 게이트** — 기존 unexplained_gap 436건 중 이 가드로 전환되는 건을 전수 나열, 건별로 실제 단위 문제인지 육안 확인해 PR에 첨부.
- [ ] **Step 5: Commit**

### Task 1.5: 괄호 음수 판정 정밀화 + 인코딩 훼손 감지

**Files:**
- Modify: `src/dart_footing_reconciler/amounts.py:70-74`, `src/dart_footing_reconciler/local_report.py:94-101`
- Test: `tests/test_amounts.py`, `tests/test_document.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_parenthesis_negative_only_when_digits_enclosed():
    from dart_footing_reconciler.amounts import parse_amount

    assert parse_amount("(1,234)") == -1_234          # 진짜 음수 표기
    assert parse_amount("(1,234,567)") == -1_234_567
    # 괄호가 숫자를 감싸지 않으면(말주기 스트립을 통과한 텍스트 주기) 양수 유지
    assert parse_amount("1,234(합계)") == 1_234
    assert parse_amount("1,234 (전기)") == 1_234
```

- [ ] **Step 2: 실패 확인** — `uv run pytest tests/test_amounts.py -k parenthesis -v`
  Expected: 뒤 2건 FAIL — 현행은 `(` 와 `)` 동시 존재만으로 음수 처리.

- [ ] **Step 3: 구현** — 음수 판정을 "괄호가 숫자부를 감싸는 경우"로 한정:

```python
_PAREN_NEGATIVE_RE = re.compile(r"\([\s]*[\d,\.]+[\s]*\)")

    negative = False
    if _PAREN_NEGATIVE_RE.search(text):
        negative = True
    if text.startswith("-"):
        negative = True
```

- [ ] **Step 4: 코퍼스 게이트 (필수 — 동작 변경)** — 부호가 바뀌는 셀 전수 diff. 부호 반전은 Adversarial Set 1순위 항목이므로 바뀐 셀 전건을 원문과 육안 대조해 PR 에 첨부.
- [ ] **Step 5: 인코딩 훼손 감지 추가** — `local_report.py` 의 최종 fallback(`errors="replace"`) 경로에서 대체문자(U+FFFD) 비율이 0.1% 초과 시 `ValueError("인코딩 판별 실패 — 원본 인코딩 확인 필요: {path}")` 로 명시 실패시킨다(조용한 라벨 훼손 → 명시 오류). 테스트: cp949 바이트를 utf-8 로 강제 오판시키는 픽스처.
- [ ] **Step 6: Commit**

---

# Phase 2 — 선언 범위 완성 (초기 스코프의 미가동 항목)

브랜치: `feat/declared-scope-completion`

### Task 2.1: 투자부동산 현금흐름 대사 등록

배경: 브리지 라벨(`checks_note_bridges.py:14-15`)과 산식 틀은 이미 존재. `RECONCILIATION_TARGETS` 에 항목이 없어 한 번도 실행된 적 없음.

**Files:**
- Modify: `src/dart_footing_reconciler/reconciliation_targets.py:17-121`
- Test: `tests/test_reconciliation_targets.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_investment_property_cashflow_targets_registered():
    from dart_footing_reconciler.reconciliation_targets import RECONCILIATION_TARGETS

    keys = {t.key for t in RECONCILIATION_TARGETS}
    assert "investment_property.acquisitions_cashflow" in keys
    assert "investment_property.disposals_cashflow" in keys
    acq = next(t for t in RECONCILIATION_TARGETS
               if t.key == "investment_property.acquisitions_cashflow")
    assert acq.account_key == "investment_property"
    assert acq.assertion_type == "cashflow_acquisition"
```

- [ ] **Step 2: 실패 확인** — `uv run pytest tests/test_reconciliation_targets.py -v`

- [ ] **Step 3: 구현** — `intangible_assets.disposals_cashflow` 항목 뒤에 추가:

```python
    ReconciliationTarget(
        "investment_property.acquisitions_cashflow",
        "investment_property",
        "cashflow_acquisition",
        "statement_cash_flows",
        "note_cash_like_acquisitions",
        ("unpaid_acquisitions", "transfers"),
    ),
    ReconciliationTarget(
        "investment_property.disposals_cashflow",
        "investment_property",
        "cashflow_disposal",
        "statement_cash_flows",
        "note_disposal_proceeds_evidence",
        ("carrying_amount", "disposal_gain_loss"),
    ),
```

- [ ] **Step 4: 통과 확인 + 코퍼스 게이트** — 신규 check 전건 triage(투자부동산 보유 회사에서만 발화해야 정상). PPE 패턴 재사용이므로 허위 일치 위험은 낮으나 신규 matched 전건 육안 확인.
- [ ] **Step 5: (게이트 결과에 따라) `investment_property.balance` 추가 검토** — PPE 와 대칭인 balance 대상도 추가하되, 기존 `fs_note_match` 와 이중 계상 노이즈가 생기면 이 항목만 되돌린다(별도 커밋으로 분리).
- [ ] **Step 6: Commit**

### Task 2.2: 사채 발행/상환 방향 분리

배경: `checks_reconciliation.py` `_cashflow_movement_role` 이 `cashflow_issue_redemption` 에 대해 의도적으로 `None` 을 반환("registry 가 두 방향을 분리할 때까지 보류").

**Files:**
- Modify: `src/dart_footing_reconciler/reconciliation_targets.py`, `src/dart_footing_reconciler/checks_reconciliation.py` (`_cashflow_movement_role` 및 방향별 CF 라인 선택), `src/dart_footing_reconciler/reconciliation_inputs.py` (사채 발행/상환 movement role 어휘 확인)
- Test: `tests/test_checks_reconciliation.py`

- [ ] **Step 1: 현행 어휘 확인** — Run: `grep -n "발행\|상환" src/dart_footing_reconciler/reconciliation_inputs.py | head -30` 으로 사채 노트에서 발행/상환 movement 가 어떤 role 이름으로 추출되는지 확인하고 기록. (이 결과가 Step 3 매핑의 입력.)

- [ ] **Step 2: 실패하는 테스트 작성** — 합성 픽스처: 사채 주석(발행 50,000 / 상환 30,000)과 CF(사채의발행 50,000 / 사채의상환 −30,000). `tests/test_checks_reconciliation.py` 의 기존 FullReport 픽스처 빌더 패턴을 재사용해 작성:

```python
def test_bond_issuance_and_redemption_reconcile_separately():
    report = _bond_fixture(  # 기존 빌더 패턴으로 작성
        note_rows=[["사채의 발행", "50,000"], ["사채의 상환", "(30,000)"]],
        cf_rows=[["사채의 발행", "50,000"], ["사채의 상환", "(30,000)"]],
    )
    checks = check_reconciliations(report, tolerance=1)
    by_id = {c.check_id: c for c in checks}
    assert by_id["bonds.issuance_cashflow"].status == "matched"
    assert by_id["bonds.redemption_cashflow"].status == "matched"
```

- [ ] **Step 3: 구현** — registry 의 `bonds.financing_cashflow`(net) 을 두 방향 대상으로 교체:

```python
    ReconciliationTarget(
        "bonds.issuance_cashflow",
        "bonds",
        "cashflow_issue",
        "statement_cash_flows",
        "note_financing_liability_cashflow",
    ),
    ReconciliationTarget(
        "bonds.redemption_cashflow",
        "bonds",
        "cashflow_redemption",
        "statement_cash_flows",
        "note_financing_liability_cashflow",
    ),
```

`_cashflow_movement_role` 의 roles 딕셔너리에 `"cashflow_issue": "issue"`, `"cashflow_redemption": "redemption"` 추가(실제 role 이름은 Step 1 확인 결과에 맞춤). CF 라인 선택은 `CFS_NOTE_RULES` 방식과 동일하게 발행(+)/상환(−) 부호 규칙 적용.

- [ ] **Step 4: 통과 확인 + 코퍼스 게이트** — 기존 `bonds.financing_cashflow`(net) 의 matched 가 사라지는 회사는 방향 분리 대상으로 재출현하는지 건별 대조(순감소 ≠ 발행−상환 인 회사는 gap 이 정상). genuine 파괴 0.
- [ ] **Step 5: Commit**

### Task 2.3: `note_reference_check` 배선 (구현돼 있으나 미가동)

**Files:**
- Modify: `src/dart_footing_reconciler/statement_note_harness.py:20-32`
- Test: `tests/test_check_pipeline.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_note_reference_check_runs_in_pipeline(sample_report):
    from dart_footing_reconciler.check_pipeline import assemble_report_checks

    checks = assemble_report_checks(sample_report, None, tolerance=1)
    assert any(c.check_type == "note_reference_check" for c in checks)
```

(`sample_report` 는 tests/test_check_pipeline.py 의 기존 픽스처 — 본문 텍스트에 "(주석 4 참조)" 류가 있는 것을 쓰거나 픽스처에 한 줄 추가.)

- [ ] **Step 2: 실패 확인** — `uv run pytest tests/test_check_pipeline.py -k note_reference -v`

- [ ] **Step 3: 구현** — `statement_note_harness.py` 의 `run()` 마지막에:

```python
from dart_footing_reconciler.checks_note_references import check_note_references
...
        results.extend(check_note_references(context.report))
```

- [ ] **Step 4: 통과 확인 + 코퍼스 게이트** — 신규 check_type 이므로 기존 유형은 fingerprint byte-identical 이어야 함. 신규 broken_ref/empty_note 는 전건 나열해 2~3건 원문 육안 대조 후 baseline 갱신. 건수가 과다(회사당 수백 건)하면 valid 결과를 회사당 요약 1건으로 접는 옵션을 검토하되 별도 커밋.
- [ ] **Step 5: Commit**

---

# Phase 3 — 재무제표 본문 footing 확충

브랜치: `feat/statement-internal-footing`

새 모듈 + 새 harness. **v1 롤아웃 규칙:** 라벨 어휘가 검증되기 전에는 `statement_cf_activity_sum` 과 SCE tie 는 MATCHED / PARSE_UNCERTAIN 만 내고(UNEXPLAINED_GAP 금지), 코퍼스 triage 로 라벨 커버리지가 확인된 뒤 후속 커밋에서 승격한다. 3행 등식류(연속성·PL 체인·PL↔CF tie)는 처음부터 UNEXPLAINED_GAP 허용.

> 참고: 아래 태스크의 "결과 미방출" 분기(직접법 CF, 성격별 PL 등)는 Task R.5 merge 후 `NOT_TESTED + '해당 없음' 사유` 방출로 전환한다 — 침묵하는 미발화는 표면 완전성 원칙 위반.

### Task 3.1: `StatementInternalHarness` 골격 + CF 연속성 체크

**Files:**
- Create: `src/dart_footing_reconciler/checks_statement_footing.py`
- Modify: `src/dart_footing_reconciler/supporting_harnesses.py` (harness 추가), `src/dart_footing_reconciler/verification_harness.py` (`LAYER_STATEMENT_INTERNAL` 상수), `src/dart_footing_reconciler/check_pipeline.py:20-26` (`default_report_harnesses`)
- Test: `tests/test_checks_statement_footing.py` (신규)

- [ ] **Step 1: 실패하는 테스트 작성** — 픽스처는 document.py 의 dataclass 를 직접 조립:

```python
from dart_footing_reconciler.document import (
    FullReport, ReportBlock, ReportSection, ReportTable, SourceLocation,
)
from dart_footing_reconciler.checks_statement_footing import check_statement_footing


def _table(rows, index=0):
    return ReportTable(index=index, rows=rows, heading="",
                       location=SourceLocation("s", 0, index))


def _statement(title, rows):
    table = _table(rows)
    return ReportSection(
        section_id=f"statement:{title}", title=title, kind="statement",
        note_no="", blocks=[ReportBlock("table", "", table, table.location)],
    )


def _report(*sections):
    return FullReport(source="t", company="테스트",
                      statements=list(sections), notes=[])


def test_cf_continuity_matched():
    cf = _statement("현금흐름표", [
        ["과목", "당기"],
        ["영업활동현금흐름", "1,000"],
        ["투자활동현금흐름", "(400)"],
        ["재무활동현금흐름", "(100)"],
        ["현금및현금성자산의 순증가(감소)", "500"],
        ["기초 현금및현금성자산", "2,000"],
        ["기말 현금및현금성자산", "2,500"],
    ])
    checks = check_statement_footing(_report(cf), tolerance=1)
    cont = next(c for c in checks if c.check_type == "statement_cf_continuity")
    assert cont.status == "matched"          # 2,000 + 500 = 2,500
    assert cont.expected == 2_500


def test_cf_continuity_gap():
    cf = _statement("현금흐름표", [
        ["과목", "당기"],
        ["현금및현금성자산의 순증가(감소)", "500"],
        ["기초 현금및현금성자산", "2,000"],
        ["기말 현금및현금성자산", "2,600"],
    ])
    checks = check_statement_footing(_report(cf), tolerance=1)
    cont = next(c for c in checks if c.check_type == "statement_cf_continuity")
    assert cont.status == "unexplained_gap"
    assert cont.difference == 100
```

- [ ] **Step 2: 실패 확인** — `uv run pytest tests/test_checks_statement_footing.py -v` Expected: FAIL (module not found)

- [ ] **Step 3: 구현** — `checks_statement_ties.py` 의 헬퍼 스타일(`_find_statement`/`_first_table`/`_current_amount`/`_row_source`/`_tie_result`)을 그대로 따른다. 라벨은 `label_resolver` 의 `AccountRole.CASH_BEGIN`/`CASH_END` 를 재사용하고, 순증감 행만 새 frozenset 으로 잡는다:

```python
"""재무제표 본문 내부 footing (Footing Axis: internal, 본문 대상)."""
from __future__ import annotations

from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.checks import (
    CheckEvidence, CheckResult, MATCHED, PARSE_UNCERTAIN, UNEXPLAINED_GAP,
)
from dart_footing_reconciler.document import FullReport, ReportSection, ReportTable
from dart_footing_reconciler.label_resolver import (
    AccountRole, LabelResolver, LABEL_NOT_FOUND, _compact,
)

_NET_CHANGE_FRAGMENTS = (
    "현금및현금성자산의순증가", "현금및현금성자산의순감소",
    "현금및현금성자산의증가", "현금및현금성자산의감소",
    "현금의증가", "현금의감소", "순현금흐름",
)


def check_statement_footing(report: FullReport, *, tolerance: int = 1) -> list[CheckResult]:
    results: list[CheckResult] = []
    results.extend(_cf_continuity_checks(report, tolerance=tolerance))
    return results


def _find_row_by_fragments(table: ReportTable, fragments: tuple[str, ...]):
    for row in table.rows:
        if not row:
            continue
        label = _compact(row[0])
        if any(frag in label for frag in fragments):
            return row
    return None


def _cf_continuity_checks(report: FullReport, *, tolerance: int) -> list[CheckResult]:
    cf = _find_statement(report, ("현금흐름표",))
    if cf is None:
        return []
    table = _first_table(cf)
    if table is None:
        return []
    begin_m = LabelResolver.find_row(table, AccountRole.CASH_BEGIN)
    end_m = LabelResolver.find_row(table, AccountRole.CASH_END)
    net_row = _find_row_by_fragments(table, _NET_CHANGE_FRAGMENTS)
    if begin_m is None or end_m is None or net_row is None:
        return []  # 직접법 등 행 부재 → not applicable (결과 미방출)
    begin = _current_amount(table, begin_m.row)
    end = _current_amount(table, end_m.row)
    net = _current_amount(table, net_row)
    if begin is None or end is None or net is None:
        return []
    expected = begin + net
    difference = end - expected
    status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP
    return [_tie_result(
        check_id="statement_cf_continuity:current",
        check_type="statement_cf_continuity",
        title="현금흐름표 연속성: 기초 + 순증감 = 기말",
        expected=expected, actual=end, difference=difference,
        tolerance=tolerance, status=status,
        reason="기초+순증감=기말 성립" if status == MATCHED else "기초+순증감≠기말",
        evidence=[
            CheckEvidence(begin_m.row[0], begin, _row_source(table, begin_m.row, "cf")),
            CheckEvidence(net_row[0], net, _row_source(table, net_row, "cf")),
            CheckEvidence(end_m.row[0], end, _row_source(table, end_m.row, "cf")),
        ],
        note_no="cf",
    )]
```

(`_find_statement`/`_first_table`/`_current_amount`/`_row_source`/`_tie_result` 는 `checks_statement_ties.py` 에서 import 하거나, 순환을 피해야 하면 `_match_helpers.py` 로 이동 — HANDOFF 의 M-2 layering debt 해소와 같은 커밋으로 처리.)

harness 등록 (`supporting_harnesses.py`):

```python
class StatementInternalHarness:
    """재무제표 본문 내부 footing harness."""

    harness_id = "statement_internal"
    layer = LAYER_STATEMENT_INTERNAL

    def run(self, context: VerificationContext) -> list[CheckResult]:
        return check_statement_footing(context.report, tolerance=context.tolerance)
```

`check_pipeline.default_report_harnesses()` 목록의 `StatementCrossHarness()` 다음에 삽입.

- [ ] **Step 4: 통과 확인** — `uv run pytest tests/test_checks_statement_footing.py tests/test_check_pipeline.py -v`
- [ ] **Step 5: 코퍼스 게이트 + Commit**

### Task 3.2: CF 활동합계 체크 (v1 abstain-first)

**Files:** Task 3.1 과 동일 모듈/테스트 파일.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_cf_activity_sum_matched():
    cf = _statement("현금흐름표", [
        ["과목", "당기"],
        ["영업활동현금흐름", "1,000"],
        ["투자활동현금흐름", "(400)"],
        ["재무활동현금흐름", "(100)"],
        ["현금및현금성자산에 대한 환율변동효과", "10"],
        ["현금및현금성자산의 순증가(감소)", "510"],
    ])
    checks = check_statement_footing(_report(cf), tolerance=1)
    act = next(c for c in checks if c.check_type == "statement_cf_activity_sum")
    assert act.status == "matched"           # 1,000 - 400 - 100 + 10 = 510


def test_cf_activity_sum_abstains_when_not_closing():
    """v1: 라벨 어휘 미검증 상태 — 닫히지 않으면 gap 이 아니라 기권."""
    cf = _statement("현금흐름표", [
        ["과목", "당기"],
        ["영업활동현금흐름", "1,000"],
        ["투자활동현금흐름", "(400)"],
        ["재무활동현금흐름", "(100)"],
        ["현금및현금성자산의 순증가(감소)", "700"],
    ])
    checks = check_statement_footing(_report(cf), tolerance=1)
    act = next(c for c in checks if c.check_type == "statement_cf_activity_sum")
    assert act.status == "parse_uncertain"
```

- [ ] **Step 2: 실패 확인 → Step 3: 구현** — 활동 3행 frozenset(변형 포함: `영업활동현금흐름`, `영업활동으로인한현금흐름`, `영업활동순현금흐름` / 투자·재무 동형) + 인식된 조정행 frozenset(`환율변동효과`, `외화환산으로인한현금의변동`, `연결범위의변동`, `매각예정` 포함 라벨). expected = 3활동 + Σ인식조정, actual = 순증감 행. 3활동 중 하나라도 미발견 → 결과 미방출. 불일치 → v1 은 `PARSE_UNCERTAIN`(reason: `cf_component_vocabulary_unverified`, LABEL_NOT_FOUND 계열 신규 코드) 로 기권.
- [ ] **Step 4: 코퍼스 triage** — 18-co 에서 이 체크의 parse_uncertain 전건을 나열, 누락 라벨을 frozenset 에 보강. 2회전 후 잔여 기권이 실제 불일치가 아니라 어휘 문제로 확인되면 승격 커밋: 불일치 → UNEXPLAINED_GAP.
- [ ] **Step 5: Commit** (v1 커밋과 승격 커밋 분리)

### Task 3.3: PL 소계 체인 (매출총이익 · 당기순이익)

**Files:** Task 3.1 과 동일 모듈/테스트 파일.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_pl_gross_profit_chain():
    pl = _statement("손익계산서", [
        ["과목", "당기"],
        ["매출액", "10,000"],
        ["매출원가", "6,000"],
        ["매출총이익", "4,000"],
        ["법인세비용차감전순이익", "1,200"],
        ["법인세비용", "200"],
        ["당기순이익", "1,000"],
    ])
    checks = check_statement_footing(_report(pl), tolerance=1)
    types = {c.check_type: c for c in checks}
    assert types["statement_pl_gross_profit"].status == "matched"     # 10,000-6,000
    assert types["statement_pl_net_income"].status == "matched"       # 1,200-200
```

- [ ] **Step 2: 실패 확인 → Step 3: 구현** — 3행 등식 2개. 라벨 frozenset:
  - 매출액(`매출액`, `매출`, `영업수익`) / 매출원가(`매출원가`, `영업비용` 은 **제외** — 성격별 표시 회사는 매출총이익 자체가 없으므로 세 라벨이 모두 있을 때만 발화)
  - 세전이익(`법인세비용차감전순이익`, `법인세차감전순이익`, `법인세비용차감전이익`, `법인세비용차감전순손익`) / 법인세(`법인세비용` — `법인세수익` 라벨이면 **미발화**, 부호 모호) / 당기순이익(`당기순이익`, `당기순이익(손실)`, `연결당기순이익`, `당기순손익`)
  - 세 라벨이 전부 발견될 때만 결과 방출(부분 발견 시 미방출 — PL 표시 형식은 다양하므로 BS equation 식 parse_uncertain 방출은 하지 않음).
- [ ] **Step 4: 코퍼스 게이트** — 발화율과 신규 gap 전건 triage(성격별/기능별 표시, 중단영업 표시 회사 확인).
- [ ] **Step 5: Commit**

### Task 3.4: 당기순이익 삼각 tie (PL ↔ CF 간접법, PL ↔ SCE)

**Files:** Task 3.1 과 동일 모듈/테스트 파일.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_net_income_tie_pl_to_cf():
    pl = _statement("손익계산서", [
        ["과목", "당기"], ["당기순이익", "1,000"],
    ])
    cf = _statement("현금흐름표", [
        ["과목", "당기"], ["당기순이익", "1,000"], ["영업활동현금흐름", "1,500"],
    ])
    checks = check_statement_footing(_report(pl, cf), tolerance=1)
    tie = next(c for c in checks if c.check_type == "statement_net_income_tie")
    assert tie.status == "matched"
```

- [ ] **Step 2: 실패 확인 → Step 3: 구현** —
  - PL↔CF: 양쪽 모두 `LabelResolver.find_row(table, AccountRole.PROFIT_LOSS)`. CF 에 당기순이익 행이 없으면(직접법) 미방출. `checks_statement_ties._cash_tie_checks` 패턴 그대로: 저신뢰 → PARSE_UNCERTAIN, 그 외 matched/unexplained_gap.
  - PL↔SCE(같은 커밋, 별 check_id `statement_net_income_tie_sce`): SCE 에서 `당기순이익` 포함·`총포괄`/`포괄손익` 비포함 행을 찾아 `_rightmost_amount`(자본총계 컬럼) 사용 — `_equity_tie_checks` 의 기말 매트릭스 처리(checks_statement_ties.py:156-162)와 동일 논리. **v1 은 MATCHED / PARSE_UNCERTAIN 만**(매트릭스 컬럼 선택 리스크), 코퍼스 확인 후 승격.
- [ ] **Step 4: 코퍼스 게이트 + Commit**

---

# Phase R — 웹 리포트 검증 표현(UI/UX) 정합

브랜치: `feat/report-surface-integrity`

배경(2026-07-09 코드 확인 결과, 실측 근거):
- `report_html._section_key`(report_html.py:80-91) 는 체크를 **첫 evidence source** 로 패널에 묶는다. 증거가 없거나 주석 번호가 없는 체크는 `"other"` 버킷으로 가는데, **`"other"` 는 문서화만 되어 있고(59행 주석) 어떤 패널도 이를 렌더하지 않는다** — KPI 숫자에는 잡히지만 화면 어디에도 배치되지 않는 검증이 존재할 수 있는 구조.
- `_STMT_KINDS`(report_html.py:153-159) 는 5대 재무제표만 렌더. **이익잉여금처분계산서 패널이 없어** `appropriation_formula_check` 의 근거 앵커가 끊긴다.
- `report_frame.check_group` 은 미등록 check_type 을 휴리스틱으로 `"주석 내부/공식 검증"` 에 **조용히 fallback** 시킨다 — Phase 2·3 의 신규 check_type 이 잘못된 그룹으로 표시될 수 있다.

원칙: **엔진이 계산한 모든 CheckResult 는 (i) KPI 집계, (ii) 패널 배치, (iii) 근거 앵커의 세 표면 모두에 나타나거나, 나타나지 못한 사유가 진단으로 표시되어야 한다.** 이 Phase 는 전부 표시 계층 변경 — 5-status fingerprint byte-identical 게이트로 검증한다.

### Task R.1: 표면 완전성 — "other" 버킷 렌더 + 배치 합계 자기검증

**Files:**
- Modify: `src/dart_footing_reconciler/report_html.py` (`_build_html`, 신규 `_render_other_panel`, 진행현황 패널)
- Test: `tests/test_report_html_cockpit.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_unplaced_checks_render_in_other_panel():
    """증거 없는 체크(예: note_reference_check 류)도 화면에서 사라지면 안 된다."""
    result = _check(check_type="note_reference_check", note_no="", evidence=[])
    html = export_audit_reconciliation_html(_minimal_report(), [result], company="T")
    assert 'id="panel-other"' in html
    assert "note_reference_check" in html or "주석 참조" in html


def test_panel_placement_sums_to_total():
    """패널 배치 합계 = 전체 체크 수 (누락 0) 를 렌더 시점에 자기검증."""
    report, results = _fixture_with_all_check_families()
    html = export_audit_reconciliation_html(report, results, company="T")
    # 진행현황 패널에 배치 진단 카운터가 노출된다
    assert "배치되지 않은 검증 0건" in html
```

- [ ] **Step 2: 실패 확인** — `uv run pytest tests/test_report_html_cockpit.py -k other_panel -v`
- [ ] **Step 3: 구현** — ① `_build_html` 에서 `tied.get("other")` 가 비어있지 않으면 `panel-other`("기타 검증 — 특정 표에 귀속되지 않는 검증") 패널을 렌더하고 사이드바에 항목 추가. ② 렌더 마지막에 `Σ(패널에 배치된 체크) vs len(results)` 를 대조해 진행현황 패널에 "배치되지 않은 검증 N건" 진단 표시(N>0 이면 경고색). 이 카운터가 이후 모든 신규 check_type 의 누락 감시 장치가 된다.
- [ ] **Step 4: 통과 확인 + Commit**

### Task R.2: check_group / check_layer 명시 등록 (조용한 fallback 금지)

**Files:**
- Modify: `src/dart_footing_reconciler/report_frame.py` (`check_group`, `check_layer`)
- Test: `tests/test_report_frame.py` (없으면 신규), `tests/test_report_order.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
KNOWN_CHECK_TYPES = {
    # 현행 (report_frame.check_group 이 명시 매핑하는 전부)
    "total_check", "appropriation_formula_check", "note_rollforward_check",
    "note_layout_formula_check", "note_note_match", "note_note_reconciliation",
    "note_balance_bridge_check", "note_internal_consistency_check",
    "primary_balance_reconciliation", "cashflow_reconciliation", "fs_note_match",
    "cfs_note_match", "asset_note_bridge_check", "expense_allocation",
    "statement_bs_equation", "statement_cash_tie", "statement_equity_tie",
    "prior_year_amount_match", "prior_year_beginning_balance_match",
    "prior_year_structure_change", "prior_column_fs_note", "prior_column_rollforward",
    # Phase 2·3 신규 — 각 Phase merge 시 여기와 CHECK_GROUPS 에 동시 등록
    "note_reference_check",
    "statement_cf_continuity", "statement_cf_activity_sum",
    "statement_pl_gross_profit", "statement_pl_net_income",
    "statement_net_income_tie", "statement_net_income_tie_sce",
}

def test_every_known_check_type_has_explicit_group():
    from dart_footing_reconciler.report_frame import CHECK_GROUPS
    missing = KNOWN_CHECK_TYPES - set(CHECK_GROUPS)
    assert not missing, f"check_group 미등록: {missing}"


def test_pipeline_emits_no_unregistered_check_type(sample_report):
    from dart_footing_reconciler.check_pipeline import assemble_report_checks
    from dart_footing_reconciler.report_frame import CHECK_GROUPS
    emitted = {c.check_type for c in assemble_report_checks(sample_report, None, tolerance=1)}
    assert emitted <= set(CHECK_GROUPS)
```

- [ ] **Step 2: 실패 확인 → Step 3: 구현** — `check_group` 의 if-사다리를 모듈 상수 `CHECK_GROUPS: dict[str, str]` 로 승격하고(`check_layer` 도 동일하게 `CHECK_LAYERS`), 함수는 dict 조회 → 미등록 시에만 기존 evidence-source 휴리스틱 fallback 유지. 신규 check_type 등록 그룹: `note_reference_check` → "재무제표-주석 대사", `statement_cf_*`·`statement_pl_*` → 신설 그룹 **"재무제표 본문 검산"**, `statement_net_income_tie*` → "재무제표 본문 간 대사"(기존 statement_* tie 그룹에 합류).
- [ ] **Step 4: 통과 확인 + Commit**

### Task R.3: 검증 방법(산식) 표시 — 체크 패밀리별 범례

배경: 감사인은 각 결과에 대해 "무엇을 무엇과, 어떤 산식·허용오차로 대사했는지"(tickmark 범례에 해당)를 화면에서 바로 읽을 수 있어야 한다. 현재는 reason 한 줄과 구성요소 표만 있고 **검증 방법 자체의 설명이 없다.**

**Files:**
- Modify: `src/dart_footing_reconciler/report_frame.py` (신규 `CHECK_METHOD_DESCRIPTIONS`), `src/dart_footing_reconciler/report_html.py` (드릴다운 + 신규 "검증 범례" 패널)
- Test: `tests/test_report_html_evidence.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_drilldown_shows_verification_method():
    result = _matched_total_check()
    html = export_audit_reconciliation_html(_minimal_report(), [result], company="T")
    assert "검증 방법" in html
    assert "구성요소 합계 = 표시된 합계" in html


def test_legend_panel_lists_all_groups():
    html = export_audit_reconciliation_html(*_fixture_with_all_check_families(), company="T")
    assert 'id="panel-legend"' in html
    for label in ("합계 검증", "재무제표-주석 대사", "주석끼리 대사", "전기대사"):
        assert label in html
```

- [ ] **Step 2: 실패 확인 → Step 3: 구현** — `CHECK_METHOD_DESCRIPTIONS: dict[str, str]` (check_type → 한 줄 산식 설명, 전 유형 필수 — R.2 의 KNOWN_CHECK_TYPES 와 키 일치 테스트 포함):

```python
CHECK_METHOD_DESCRIPTIONS = {
    "total_check": "표 안의 구성요소 합계 = 표시된 합계 (행·소계·총계·열 방향)",
    "note_rollforward_check": "기초 장부금액 + 증감 합계 = 기말 장부금액",
    "fs_note_match": "재무제표 본문 라인 금액 ↔ 해당 주석의 합계·기말 금액",
    "primary_balance_reconciliation": "재무상태표 라인 ↔ 주석 기말 장부금액 (구성요소 조합 탐색 포함)",
    "cashflow_reconciliation": "현금흐름표 라인 ↔ 주석 증감 중 현금성 항목 (비현금 조정 반영)",
    "cfs_note_match": "현금흐름표 라인 ↔ 주석 키워드 일치 금액 (부호는 크기 비교, 원문 부호는 근거에 보존)",
    "note_note_match": "주석 A 의 금액 ↔ 주석 B 의 동일 개념 금액 (예: 감가상각비 ↔ 비용 성격별)",
    "expense_allocation": "성격별 비용(감가상각·상각) ↔ 기능별 배분(매출원가·판관비·개발비) 합계",
    "statement_bs_equation": "자산총계 = 부채총계 + 자본총계",
    "statement_cash_tie": "재무상태표 현금및현금성자산 ↔ 현금흐름표 기말 현금",
    "statement_equity_tie": "재무상태표 자본총계 ↔ 자본변동표 기말 자본총계",
    "appropriation_formula_check": "차기이월미처분이익잉여금 = 미처분이익잉여금 + 이입액 - 처분액",
    "prior_year_amount_match": "당기 보고서의 전기 비교표시 = 전기 보고서의 당기 금액",
    "prior_year_beginning_balance_match": "전기 기말 = 당기 기초",
    # ... (KNOWN_CHECK_TYPES 전 유형 — Phase 2·3 신규 포함)
}
```

렌더: ① 드릴다운 reason 위에 `검증 방법: {설명} · 허용오차 ±{tolerance}원` 한 줄 고정 표시. ② 사이드바에 "검증 범례" 패널 추가 — 그룹별로 방법 설명과 이 보고서에서의 건수(5-status 분포 미니바)를 나열. 감사조서의 tickmark legend 에 해당하는 화면.

- [ ] **Step 4: 통과 확인 + Commit**

### Task R.4: 근거 앵커 무결성 — 처분계산서 패널 + 끊긴 점프 진단

**Files:**
- Modify: `src/dart_footing_reconciler/report_html.py` (`_STMT_KINDS`, `_STMT_KEY_ALIASES`, `_source_panel_id`, 앵커 검증)
- Test: `tests/test_report_html_evidence.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_appropriation_statement_gets_panel_and_anchor():
    report, results = _fixture_with_appropriation_check()
    html = export_audit_reconciliation_html(report, results, company="T")
    assert 'id="panel-appropriation"' in html
    # 처분계산서 산식 체크의 근거가 점프 가능한 앵커로 렌더된다
    assert "jumpToCell" in html


def test_broken_anchor_counted_not_silent():
    """근거 source 가 렌더된 어떤 셀에도 매핑되지 않으면 진단 카운터에 잡힌다."""
    result = _check_with_source("note:99/table:7/row:3/col:2")   # 존재하지 않는 주석
    html = export_audit_reconciliation_html(_minimal_report(), [result], company="T")
    assert "근거 연결 실패 1건" in html
```

- [ ] **Step 2: 실패 확인 → Step 3: 구현** — ① `_STMT_KINDS` 에 `("이익잉여금처분계산서", "appropriation", "이익잉여금처분계산서")`, `("결손금처리계산서", "appropriation", "결손금처리계산서")` 추가하고 `_STMT_KEY_ALIASES` 에 두 제목 → `appropriation` 매핑 추가(둘 다 있으면 첫 발견 렌더 — 기존 `rendered_kinds` 중복 방지 로직 재사용). ② 렌더 시 각 evidence source 를 `_parse_source`+`_source_table` 로 해석해 실패 건수를 집계, 진행현황 패널에 "근거 연결 실패 N건" 진단 표시(전략 문서의 evidence completeness rate 지표를 화면에 상시화). 실패한 근거는 점프 링크 대신 원문 텍스트로 표시(현행 동작 유지).
- [ ] **Step 4: 통과 확인 + Commit**

### Task R.5: 커버리지 3분할 — '해당 없음' 과 '미커버' 의 분리 (백로그 C1·C2 채택)

배경: 현재 `미검증` 배지는 "적용 가능한 검증이 없었음"과 "검증 로직은 있으나 이 문서에서 발화하지 못함"을 구분하지 못한다. Phase 3 의 "결과 미방출"(직접법 CF 등) 사례도 화면에서는 그냥 사라진다 — 사용자가 지적한 누락 완전성의 핵심.

**Files:**
- Modify: `src/dart_footing_reconciler/checks_statement_footing.py` (미방출 → NOT_TESTED+사유 방출), `src/dart_footing_reconciler/report_html.py` (배지·진행현황 3분할), `src/dart_footing_reconciler/coverage.py`
- Test: `tests/test_checks_statement_footing.py`, `tests/test_coverage.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_direct_method_cf_emits_not_tested_with_reason():
    """직접법 CF(당기순이익 행 없음)는 침묵이 아니라 '해당 없음' 결과를 남긴다."""
    cf = _statement("현금흐름표", [["과목", "당기"], ["영업활동현금흐름", "1,000"]])
    checks = check_statement_footing(_report(cf), tolerance=1)
    nt = next(c for c in checks if c.check_type == "statement_net_income_tie")
    assert nt.status == "not_tested"
    assert "직접법" in nt.reason or "해당 없음" in nt.reason
```

- [ ] **Step 2: 실패 확인 → Step 3: 구현** — ① Phase 3 체크들의 "결과 미방출" 분기를 `NOT_TESTED` + 사유("해당 없음 — {구체 사유}") 방출로 전환(대상 재무제표가 존재할 때만; 재무제표 자체가 없으면 현행대로 미방출). ② 진행현황 패널의 미검증 집계를 3분할: **검증됨 / 해당 없음(적용 불가) / 미커버(적용 가능하나 검증 없음)** — not_tested 의 reason 유무로 구분. ③ `coverage.py` 집계에 3분할 필드 추가, `corpus_result.json` 에 반영. 주의: NOT_TESTED 는 이미 5-status 의 정식 값이므로 status 어휘는 불변 — reason 층에서만 구분한다(ADR-0006 계약 유지).
- [ ] **Step 4: 코퍼스 게이트 — not_tested 증가는 이 태스크의 의도된 효과이므로, 증가분이 전부 신규 check_type 의 '해당 없음' 사유인지 fingerprint diff 로 확인 후 baseline 갱신 + Commit**

### Task R.6: Excel·오프라인 검증앱 패리티

**Files:**
- Modify: `src/dart_footing_reconciler/audit_workbook.py` (그룹·방법 컬럼), `src/dart_footing_reconciler/verify_app.py` / `static/dart-verify/` (동일 범례·배치)
- Test: `tests/test_audit_workbook.py`, `tests/test_verify_app.py`

- [ ] **Step 1: 실패하는 테스트 작성** — 워크북 시트에 `검증 방법` 컬럼이 존재하고 R.3 의 `CHECK_METHOD_DESCRIPTIONS` 와 동일 문구인지; verify-app 번들이 렌더하는 check_type 집합이 HTML 과 동일한지(`KNOWN_CHECK_TYPES` 기준 집합 비교 테스트).
- [ ] **Step 2: 구현** — 세 표면(HTML·Excel·verify-app)이 같은 `report_frame` 상수(`CHECK_GROUPS`/`CHECK_METHOD_DESCRIPTIONS`)를 단일 출처로 공유하도록 배선 — 표면별 사본 금지.
- [ ] **Step 3: 통과 확인 + Commit**

---

# Phase 4 — 정확도 측정 체계 (Gold Set · 사유 세분화 · 금액가중 커버리지)

브랜치: `feat/accuracy-measurement` (4.1 은 코드+검토작업 혼합 — 코드만 이 브랜치)

### Task 4.1: Gold Set 하네스 + 라벨링 워크플로

배경: `docs/validation/verification-accuracy-strategy.md` 가 요구하는 Gold Set(20–30건 검토 완료 기대값)의 **도구 쪽 절반**. 라벨링 자체는 검토자(사용자) 작업.

**Files:**
- Create: `src/dart_footing_reconciler/gold_set.py`, `gold/gold_manifest.example.json`, `docs/validation/gold-set-workflow.md`
- Modify: `src/dart_footing_reconciler/cli.py` (`gold-validate` 커맨드)
- Test: `tests/test_gold_set.py`

- [ ] **Step 1: 스키마 확정 + 예시 manifest 커밋**

```json
{
  "schema_version": 1,
  "samples": [
    {
      "company": "삼성SDI",
      "rcp_no": "20250310001234",
      "source": "out/corpus/run_2026-06-22/raw/samsung_sdi.html",
      "scope": "nonfinancial",
      "expectations": [
        {
          "check_type": "fs_note_match",
          "account_key": "property_plant_equipment",
          "consolidation_basis": "consolidated",
          "expected_status": "matched",
          "evidence_note": "주석12 유형자산 기말 순장부금액 = BS 유형자산",
          "reviewer": "kjun",
          "reviewed_date": "2026-07-15"
        }
      ]
    }
  ]
}
```

- [ ] **Step 2: 실패하는 테스트 작성**

```python
def test_gold_run_scores_expectations(tmp_path):
    from dart_footing_reconciler.gold_set import score_expectations

    engine_results = [_check(check_type="fs_note_match",
                             account_key="property_plant_equipment",
                             consolidation_basis="consolidated",
                             status="matched")]
    expectations = [{"check_type": "fs_note_match",
                     "account_key": "property_plant_equipment",
                     "consolidation_basis": "consolidated",
                     "expected_status": "matched"}]
    scored = score_expectations(engine_results, expectations)
    assert scored.reviewed_accuracy == 1.0
    assert scored.false_match_count == 0


def test_false_match_counted():
    """검토자가 gap 이라 판정했는데 엔진이 matched → 허위 일치(최고 위험)."""
    engine_results = [_check(check_type="fs_note_match",
                             account_key="borrowings",
                             consolidation_basis="separate",
                             status="matched")]
    expectations = [{"check_type": "fs_note_match",
                     "account_key": "borrowings",
                     "consolidation_basis": "separate",
                     "expected_status": "unexplained_gap"}]
    scored = score_expectations(engine_results, expectations)
    assert scored.false_match_count == 1
```

- [ ] **Step 3: 구현** — `gold_set.py`: manifest 로드 → 샘플별 `parse_full_report` + `assemble_report_checks` → expectation 을 `(check_type, account_key, consolidation_basis)` 키로 엔진 결과에 매칭(다건 매칭 시 그 expectation 은 `ambiguous` 로 별도 카운트) → 지표 산출: `reviewed_accuracy`(기대=실제 비율), `false_match_count/rate`(기대 non-matched·엔진 matched — 최우선 지표), `abstain_on_expected_matched`(기대 matched·엔진 기권), `unmatched_expectations`(엔진에 해당 체크 자체가 없음 = 커버리지 구멍). 출력: `gold_report.md` + `gold_result.json`. CLI: `dart-footing gold-validate gold/gold_manifest.json out/gold/`.
- [ ] **Step 4: 통과 확인 + Commit**
- [ ] **Step 5: 라벨링 워크플로 문서화 + 1차 배치 착수 (코드 외 작업)** — `docs/validation/gold-set-workflow.md`:
  - 대상: 기존 18-co 캐시에서 산업 분산 유지하며 20개 선정 (+ 후속 배치에서 화학/엔터/게임/디스플레이 추가 → 목표 30).
  - 검토 절차: `workpaper-html` 출력을 열고 회사당 primary check 5–10개(유형자산·무형자산·차입금·리스·투자부동산 + CF 브리지)에 대해 기대 status 와 근거 위치를 기록. 예상 소요 회사당 1–2시간.
  - false-match 의심 건은 `false_matched_review` 샘플(corpus.py 산출물)에서 우선 선정.
  - 완료 기준: 기대값 100건 이상 축적 시 `gold-validate` 를 회귀 게이트 3종(코퍼스/스냅샷/fingerprint) 옆의 4번째 게이트로 승격.

### Task 4.2: parse_uncertain 사유 세분화

배경: ~500건의 98%가 `AMOUNT_PARSE_FAILED` 단일 코드(`checks_totals.py:54` 가 유일 방출점 — 모든 기권이 여기로 수렴).

**Files:**
- Modify: `src/dart_footing_reconciler/label_resolver.py` (사유 코드 추가), `src/dart_footing_reconciler/checks_totals.py` (기권 경로별 사유 분기), `src/dart_footing_reconciler/report_html.py` (사유 텍스트 맵 + 사유별 집계)
- Test: `tests/test_checks_totals.py`, `tests/test_report_html_cockpit.py`

- [ ] **Step 1: 기권 경로 목록화** — Run: `grep -n "PARSE_UNCERTAIN" src/dart_footing_reconciler/checks_totals.py` 로 방출 경로를 나열하고, 각 경로의 실제 원인(전기 미러 표 / 그룹 구조 헤더 보류 / 진짜 금액 파싱 실패)을 코드 주석 기준으로 분류해 기록.
- [ ] **Step 2: 실패하는 테스트 작성**

```python
def test_prior_mirror_table_abstain_reason():
    """전기 미러 표 기권은 '정당한 기권' 사유 코드를 달아야 한다."""
    checks = check_table_totals(_prior_mirror_table(), note_no="5", tolerance=1)
    uncertain = [c for c in checks if c.status == "parse_uncertain"]
    assert uncertain
    assert all(c.parse_uncertain_reason == "prior_period_mirror_table"
               for c in uncertain)
```

- [ ] **Step 3: 구현** — `label_resolver.py` 사유 상수 추가: `PRIOR_PERIOD_MIRROR = "prior_period_mirror_table"`, `GROUP_STRUCTURE_HELD_BACK = "group_structure_held_back"` (기존 예약 코드 `AMBIGUOUS_MULTIPLE`/`COLUMN_NOT_DETECTED`/`TABLE_NOT_FOUND` 는 이번에 실제 방출 경로에 배정). `checks_totals.py:54` 의 단일 배정을 Step 1 분류에 따라 경로별 배정으로 교체. `report_html.py` 사유 텍스트 맵에 한국어 설명 추가 + 진행현황 패널에 parse_uncertain 사유별 소계 표시("검토 불요 기권" vs "파서 개선 대상" 구분이 목적).
- [ ] **Step 4: 코퍼스 게이트** — status 분포는 byte-identical(사유 필드만 변경)이어야 함. 사유별 분포를 accuracy-backlog 에 기록.
- [ ] **Step 5: Commit**

### Task 4.3: 금액가중 커버리지 지표

**Files:**
- Modify: `src/dart_footing_reconciler/coverage.py`, `src/dart_footing_reconciler/report_html.py` (진행현황 패널)
- Test: `tests/test_coverage.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_amount_weighted_coverage():
    """BS 라인 중 체크가 붙은 라인의 |금액| 합 / 전체 라인 |금액| 합."""
    from dart_footing_reconciler.coverage import build_amount_weighted_coverage

    report = _report_with_bs_lines({"유형자산": 700, "무형자산": 200, "기타자산": 100})
    checks = [_check_bound_to("유형자산"), _check_bound_to("무형자산")]
    cov = build_amount_weighted_coverage(report, checks)
    assert cov.statement_ratios["재무상태표"] == 0.9   # (700+200)/1000
```

- [ ] **Step 2: 실패 확인 → Step 3: 구현** — `report_frame` 이 이미 계정 상태 배지를 위해 statement 행↔체크 결과 바인딩을 갖고 있으므로(`report_html.py` `_account_state_badge` 경로) 그 바인딩 함수를 재사용한다: BS/PL 첫 표의 금액 파싱 가능한 행에 대해 `covered = 바인딩된 체크 존재(status ≠ not_tested)` 로 표시하고 `Σ|covered 금액| / Σ|전체 금액|` 산출. 소계·총계 행(자산총계 등 `label_resolver` 총계 role 매칭 행)은 분모에서 제외(이중 계상 방지). HTML 진행현황 패널에 "금액 가중 커버리지: 재무상태표 XX% · 손익계산서 XX%" 카드 추가. `corpus_result.json` 회사별 필드에도 추가.
- [ ] **Step 4: 통과 확인 + 코퍼스 게이트(표시 전용 변경 — 5-status fingerprint byte-identical) + Commit**

---

# Phase 5 — explainable_gap 어휘 확충 + 브리지 명세

브랜치: `feat/explainable-vocabulary`

배경: 기준선 8,676건 중 explainable_gap 10건 — 조정 어휘 빈약으로 사실상 미작동. 목표: 이자자본화·환율·손상을 조정 클래스로 추가하고, explainable_gap 의 화면 표기를 "설명 후보 존재"에서 "조정 후보별 금액 명세 + 잔여차이"로 올린다.

### Task 5.1: 이자자본화(차입원가 자본화) 조정 클래스

**Files:**
- Modify: `src/dart_footing_reconciler/reconciliation_inputs.py` (movement role 어휘 사다리), `src/dart_footing_reconciler/reconciliation_targets.py` (PPE·무형·투자부동산 acquisitions 의 `required_adjustments` 에 `"capitalized_interest"` 추가), `src/dart_footing_reconciler/checks_cfs_note.py` (explainable 키워드 목록에 `자본화` 추가)
- Test: `tests/test_reconciliation_inputs.py`, `tests/test_checks_reconciliation.py`

- [ ] **Step 1: 어휘 사다리 위치 확인** — Run: `grep -n "미지급\|사업결합\|noncash" src/dart_footing_reconciler/reconciliation_inputs.py | head -20` 으로 기존 non-cash 조정 role 분류 지점을 특정.
- [ ] **Step 2: 실패하는 테스트 작성**

```python
def test_capitalized_interest_row_classified_as_noncash_adjustment():
    """주석 취득 내역의 '자본화차입원가' 행은 현금성 취득에서 차감되는
    비현금 조정(role: capitalized_interest)으로 분류돼야 한다."""
    role = _movement_role_for_label("자본화차입원가")  # 기존 분류 함수에 위임
    assert role == "capitalized_interest"
```

- [ ] **Step 3: 구현** — 토큰: `이자자본화`, `차입원가자본화`, `자본화차입원가`, `자본화된차입원가` (bare `이자` 는 과광범위 — 금지). 분류 role `capitalized_interest` 신설, `_cash_basis_note_movement_amount` 의 조정 적용 목록에 등록(방향: 비현금 가산분 — `noncash_payable` addback 과 동일 방향). `reconciliation_targets.py` 의 PPE/무형/투자부동산 acquisitions `required_adjustments` 튜플에 `"capitalized_interest"` 추가. `checks_cfs_note.py:82-88` 키워드 목록(비현금·미지급·리스·대체·환율·외화)에 `자본화` 추가.
- [ ] **Step 4: 코퍼스 게이트** — 이자자본화가 있는 회사(건설·에너지 계열 유력: 현대건설, SGC에너지)에서 unexplained→matched/explainable 전환 건을 육안 확인. 회귀 핀: 실코퍼스 사례 1건을 픽스처로 고정.
- [ ] **Step 5: Commit**

### Task 5.2: 환율·손상 조정 클래스 (staged)

**Files:** Task 5.1 과 동일 + `src/dart_footing_reconciler/orientation.py` (MOVEMENT_LABELS 에 환율 토큰)

- [ ] **Step 1: 실패하는 테스트 작성** — 롤포워드에 `외화환산차이` 열이 있는 자산 주석에서 CF 취득 브리지가 이 열을 조정 후보로 집계하는지 (기존 `외화환산` 비현금 처리 reconciliation_inputs.py:1505 부근을 취득 브리지 조정 목록으로 승격).
- [ ] **Step 2: 구현** — `fx_translation` role: 토큰 `외화환산`, `환율변동`, `해외사업환산`. `impairment` role: 토큰 `손상차손`(환입 포함 `손상차손환입`) — 처분 브리지의 조정 후보로만 등록(취득 쪽은 무관). `orientation.MOVEMENT_LABELS` 에 `외화환산`·`환율변동` 추가(FX 열 있는 롤포워드가 orientation 1급 인식되도록).
- [ ] **Step 3: 코퍼스 게이트** — MOVEMENT_LABELS 확장은 orientation 분류를 바꾸므로 파급 diff 전수 확인. 신규 matched 전건 육안.
- [ ] **Step 4: Commit**

### Task 5.3: explainable_gap 브리지 명세 (보고 층)

**Files:**
- Modify: `src/dart_footing_reconciler/checks_reconciliation.py` (EXPLAINABLE_GAP 시 조정 후보를 evidence 로 첨부 + reason 에 잔여차이 명시), `src/dart_footing_reconciler/report_html.py` (드릴다운에 "설명 후보 조정" 블록)
- Test: `tests/test_checks_reconciliation.py`, `tests/test_report_html_evidence.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_explainable_gap_carries_adjustment_breakdown():
    check = _explainable_gap_cashflow_check()   # 기존 픽스처 재사용
    labels = [e.label for e in check.evidence]
    # 조정 후보 행(미지급금 증감 등)이 증거로 첨부되고
    assert any("미지급" in l for l in labels)
    # reason 에 잔여차이가 수치로 명시된다
    assert "잔여차이" in check.reason
```

- [ ] **Step 2: 구현** — `_cashflow_status` 가 EXPLAINABLE_GAP 을 낼 때, 인식된 조정 후보 movement (role·label·금액·source)를 evidence 목록에 추가하고 reason 을 `"설명 후보 {role 한글명} {금액} 존재 · 잔여차이 {N}"` 형식으로. `report_html` 드릴다운의 구성요소 블록 아래 "설명 후보 조정" 표(조정명 / 금액 / 근거 위치 / 적용 후 잔여차이) 렌더.
- [ ] **Step 3: 코퍼스 게이트(status fingerprint byte-identical — evidence/reason 필드만 변경) + Commit**

---

# Phase 6 — 범위 확장 로드맵 (각 항목 착수 전 별도 grill+plan 필수)

이 Phase 의 항목들은 설계 불확실성이 커서 이 문서에서 코드 수준으로 고정하지 않는다. 각각 착수 시 `grill-with-docs` → 전용 spec/plan(Tier-3) 을 거친다. 순서는 가치/리스크 순.

### 6.1 차입금·사채 유동/비유동 구분 대사 (리스 패턴 이식)
- B-2b 에서 검증된 4차원 페어링(`Account × Consolidation Basis × Report Period × Balance Level`)을 차입금/사채에 적용. HANDOFF "Next planned feature" 그대로 — 오염 토큰(ADR-0013 BLOCKER-1) 격리 → 레벨 페어링 순.
- 진입 조건: Phase 2 merge 후. 게이트: 리스 B-2b 와 동일한 하드 게이트.

### 6.2 이연법인세 잔액 tie 등 FS-note 계정 확장
- `FS_NOTE_ACCOUNT_KEYS` 에 `deferred_tax_assets`/`deferred_tax_liabilities` 추가가 1차. 법인세 주석의 상계표시(자산·부채 상계 후 표시) 때문에 단순 합계 tie 는 FP 위험 — grill 필요.
- 이후: `cash_and_cash_equivalents`(주석 구성내역 tie), 충당부채·퇴직급여 FS tie, 배당(결의 vs 지급 구분).

### 6.3 XBRL 교차검증 (본문 금액 이중 확인)
- 조사 태스크 먼저: 키리스로 XBRL 인스턴스 확보 가능한지 확인 (DART 뷰어의 재무제표 XBRL 첨부 존재 여부를 3개 회사 rcp_no 로 실측). 가능하면 본문 파싱 결과 vs XBRL 값 대조 체크(`statement_xbrl_tie`) 신설 — 단위·부호 파싱 오류의 자동 검출기가 된다. 키가 필요하면 OPTIONAL(API-key 제공 시에만 활성) 기능으로 격리 — "키리스 재현" 코퍼스 원칙 훼손 금지.

### 6.4 분반기 보고서 지원
- 중간재무제표 비교표시 관행(BS: 전기말 대비 / PL: 전년동기·누적 대비)의 기간 모델 확장. Report Period 어휘(`당분기`/`전분기`/`누적`/`3개월`)를 pairing key 에 정식 편입해야 하므로 대형 grill. Gold Set 에 분기보고서 샘플 2~3건을 먼저 넣어 실태 파악 후 착수.

### 6.5 전기 보고서 자동 페어링 (재작성 감지 상시화)
- `PriorReportHarness` 는 전기 파일 수동 제공 시에만 가동. kreports MCP `search_dataset` 으로 직전 연도 rcp_no 를 찾아 `--prior-html` 자동 채움을 corpus runner 와 CLI 에 추가(fetch 는 기존 `dart_fetch` 재사용, 네트워크 명시 옵션 뒤에).

### 6.6 DART fetch 견고화
- TOC 리터럴(`III. 재무에 관한 사항`) + 1400자 창 스크레이핑을 노드 트리 탐색으로 교체, 실패 시 명확한 오류 메시지(어떤 TOC 라벨을 찾았는지). 소형 슬라이스 — Phase 2 에 편승 가능.

### 6.7 자본변동표 매트릭스 footing + 포괄손익 tie
- SCE 매트릭스 검산: 각 자본 구성요소 열에 대해 기초 + Σ변동행 = 기말, 각 행에 대해 Σ구성요소 = 자본총계 열. 퇴화 헤더('자본' 반복)와 병합 셀 때문에 열 식별이 어려워 전용 grill 필요 — Phase 3 의 `_rightmost_amount` 방식이 코퍼스에서 안정되면 착수.
- 포괄손익 tie: PL 당기순이익 + 기타포괄손익 = 총포괄손익(단일표/별개표 두 표시 형식), 총포괄손익 ↔ SCE 반영액. 별개표 형식은 두 statement 섹션 파싱 정합부터 확인.

---

## 실행 순서·의존성 요약

| 순서 | Phase | 산출물 | 의존성 | 예상 규모 |
|---|---|---|---|---|
| 1 | Phase 1 단위 견고화 | PR 1개 (Task 1.1–1.5) | 없음 | 소–중 |
| 2 | Phase R 리포트 표면 정합 | PR 1개 (Task R.1–R.6; R.5 는 Phase 3 이후로 이월 가능) | 없음 (1·2와 병행 가능) — **R.1·R.2 는 Phase 2·3 의 신규 check_type merge 전에 선행 필수** | 소–중 |
| 3 | Phase 2 범위 완성 | PR 1개 (Task 2.1–2.3, +6.6 편승 가능) | R.1·R.2 merge 후 (신규 check_type 의 표면 등록 규칙 가동 상태에서) | 소 |
| 4 | Phase 3 본문 footing | PR 1개 (Task 3.1–3.4, v1→승격 커밋 분리) | Phase 1 merge 권장(단위 정합 후 발화), R.1·R.2 필수 | 중 |
| 5 | Phase 4 측정 체계 | PR 1개 + 라벨링 작업(사용자) | Gold Set 라벨링은 Phase 1–3 merge 후 시작(기대값이 구버전 엔진에 고정되는 것 방지) | 중 |
| 6 | Phase 5 설명 어휘 | PR 1개 (Task 5.1–5.3) | Phase 1 merge 후 | 중 |
| 7 | Phase 6 확장 | 항목별 별도 grill+plan | 항목별 상이 | 대 |

병행 규칙: Phase 1·R·2 는 파일 겹침이 작아 병행 가능(R 과 2 가 모두 report_frame 을 건드리면 R 선행). Phase 3 이후는 순차.

---

## 리스크 대장

| 리스크 | 완화 |
|---|---|
| Task 1.3 단위 리셋이 정당한 상속을 깨서 대량 gap 발생 | 계측 선행(Step 1–2), 리셋 지점을 영역 경계로 한정, 게이트 실패 시 TOC 전환만으로 후퇴 |
| Task 2.3 주석 참조 체크의 결과 건수 폭증 | 신규 check_type 분리 게이트 + valid 요약 접기 옵션 |
| Phase 3 활동합계의 라벨 어휘 미비 → FP gap | v1 abstain-first (UNEXPLAINED_GAP 금지) → triage 후 승격 |
| Task 5.2 MOVEMENT_LABELS 확장의 orientation 파급 | 파급 diff 전수 확인, 실패 시 orientation 변경만 분리 롤백 |
| Gold Set 기대값이 엔진 버전에 종속 | 기대값에 evidence_note(근거 위치) 필수 기록 — 엔진이 바뀌어도 사람이 재검증 가능 |
| Phase R 표시 변경이 verdict 에 영향 | 표시 계층 전용 게이트: 5-status fingerprint byte-identical 확인 (R.5 의 not_tested 방출만 예외 — 신규 check_type 분리 triage) |
| R.5 로 not_tested 급증 → 완료율 지표 하락으로 오독 | 3분할 표시('해당 없음' 별도 집계)와 함께 배포 — 분모에서 '해당 없음' 제외한 완료율을 병기 |

## 이 계획이 커버하는 점검 발견사항 매핑

| 2026-07-09 점검 발견 | 커버 위치 |
|---|---|
| 1. 단위·부호·인코딩 파싱 리스크 | Phase 1 (1.1–1.5), 6.3 XBRL |
| 2. Gold Set 부재 | Task 4.1 |
| 3. 투자부동산 미가동·사채 미분리 | Task 2.1, 2.2 |
| 4. 본문 footing·당기순이익 tie 부재 | Phase 3 (3.1–3.4); SCE 매트릭스·포괄손익은 6.7 |
| 5. explainable_gap 미작동 | Phase 5 (5.1–5.3) |
| 6. parse_uncertain 뭉텅이 | Task 4.2 |
| 7. 금액가중 커버리지·중요성 축 부재 | Task 4.3 (중요성 정렬은 4.3 후속 — 표시 전용) |
| 8. 계정 커버리지 공백 (이연법인세 등) | 6.2 |
| 9. 분반기·전기 자동화·fetch 취약 | 6.4, 6.5, 6.6 |
| 10. note_reference_check 미배선 | Task 2.3 |
| 11. 웹 표현 완전성 — 미배치 체크·끊긴 앵커·조용한 그룹 fallback·검증 방법 미표시·'해당 없음' 미구분 (2026-07-09 추가 발견) | Phase R (R.1–R.6) |
