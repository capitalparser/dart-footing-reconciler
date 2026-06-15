# DART Footing Reconciler — Audit UI & Parsing Robustness

**Date:** 2026-06-12  
**Status:** Draft (pending user review)  
**Scope:** (1) `report_html.py` 전면 교체 — evidence_cockpit 디자인 적용, (2) 레이블 매칭 강건화 — 범용 회사 구조 대응  
**Tier:** T3 (Q1 새 용어, Q2 파일 3개↑, Q4 인터페이스 변경, Q5 설계 분기 존재)

---

## 1. Goal

현재 `report_html.py`가 생산하는 HTML은 `check_type`, `status: matched`, `source: statement:bs/table:1/row:0` 같은 프로그래밍 내부 용어를 그대로 노출한다. 감사팀이나 회사 재무팀이 직접 쓸 수 있는 수준이 아니다.

목표는 두 가지:

1. **HTML 보고서 UI 재설계** — 재무제표 원문 형태를 유지하면서 검증 결과를 직관적으로 표면화하는 evidence_cockpit 패턴 적용.
2. **파싱 강건화** — 회사마다 다른 레이블·테이블 구조를 허용 오차 범위 내에서 해석하고, 해석 불확실도를 검증 결과와 함께 사용자에게 투명하게 전달.

---

## 2. Users & Use Cases

| 사용자 | 주요 동선 |
|--------|----------|
| 감사인 (인차지/팀원) | 보고서 열기 → 요약 배너에서 전체 pass/fail 즉시 확인 → 빨간/노란 항목만 드릴다운 → 주석별 탭에서 roll-forward 확인 |
| 회사 재무팀 | 감사 전 자가점검 → 어느 행에서 차이가 생겼는지 원문 표 위에서 직접 확인 → 차이 원인 메모 참고 |
| 두 그룹 공통 | 파싱 실패 행이 있으면 "왜 못 찾았는지"를 이해하고 보고서 품질을 평가 |

---

## 3. 승인된 디자인 결정 (브레인스토밍 산출)

| 항목 | 결정 |
|------|------|
| 출력 형태 | 단일 self-contained HTML 파일 |
| 첫 화면 | Verdict Banner (전체 pass/fail 요약) |
| 검사 항목 스타일 | 숫자 비교 행 + 인라인 드릴다운 |
| 드릴다운 방식 | 행 아래 인라인 확장 (side panel 아님) |
| 네비게이션 | 다크 사이드바 — 재무제표 본문(BS→IS→SCE→CF) → 주석별 탭 순 |
| 재무제표 본문 패널 | DART 원문 표 그대로 + 검증 행에 tick badge 오버레이 |
| 디자인 시스템 | `evidence_cockpit` profile, PAS design tokens, Pretendard |
| 파싱 불확실 행 | `?` badge — ✓(일치)/⚠(차이)와 구분, 이유 드릴다운 |

---

## 4. 파싱 강건성 아키텍처

### 4.1 문제 정의

DART 공시는 회사마다 계정과목명, 들여쓰기 깊이, 소계/합계 배치, 컬럼 헤더가 다르다. 현재 구현의 한계:

- 레이블 매칭: frozenset 완전 일치 + 부분 문자열 두 계층만 존재 — 미등록 변형은 즉시 실패
- 신뢰도 점수 없음 — `parse_uncertain` 이면에 "왜 못 찾았는지" 정보가 없음
- 들여쓰기/계층 구조 미활용
- 컬럼 헤더도 exact match 의존

### 4.2 Label Resolver — 신규 모듈

`label_resolver.py` 를 신설한다. 기존 check 모듈들이 직접 frozenset을 들고 있던 패턴을 대체하는 단일 진입점.

**역할:** 주어진 테이블에서 `AccountRole`(의미론적 계정 역할)에 해당하는 행을 찾아 `RowMatch`를 반환한다.

```
AccountRole (enum):
  ASSET_TOTAL, LIABILITY_TOTAL, EQUITY_TOTAL,
  CASH_END, CASH_BEGIN,
  PROFIT_LOSS, REVENUE,
  ...

RowMatch (dataclass):
  row: list[str]           # 원본 행 데이터
  confidence: float        # 0.0 ~ 1.0
  match_tier: MatchTier    # EXACT | PREFIX | CONTAINS | POSITION | FUZZY
  matched_label: str       # 실제 매칭된 레이블
  candidates: list[str]    # 신뢰도 0.3 이상의 대안 후보들
  reason: str              # 매칭 근거 한 줄 설명 (UI 표시용 한국어)
```

**매칭 계층 (우선순위 순):**

| Tier | 예시 | 신뢰도 |
|------|------|--------|
| EXACT | 자산총계 == 자산총계 | 1.0 |
| PREFIX | 자산총계로 시작 | 0.85 |
| CONTAINS | 자산 포함 + 총/합/계 포함 | 0.70 |
| POSITION | 섹션 마지막 행 + 볼드/합계 스타일 | 0.55 |
| FUZZY | Jaro-Winkler ≥ 0.88 | 0.40 |

신뢰도 임계값:
- ≥ 0.70 → `matched` 처리 가능 (검증 로직에 사용)
- 0.40 ~ 0.69 → 검증 실행하되 결과를 `parse_uncertain` 플래그와 함께 전달
- < 0.40 → 행 미발견 처리 → `parse_uncertain`

**기존 frozenset 마이그레이션:**  
`checks_statement_ties.py`, `checks_totals.py`, `footing.py`, `note_assertions.py`의 직접 frozenset 참조를 `LabelResolver.find_row(table, AccountRole.X)` 호출로 교체. 기존 레이블 목록은 `label_resolver.py`의 `_CANONICAL_LABELS` dict로 통합.

### 4.3 구조 기반 보조 신호

행 위치와 HTML 구조에서 추출하는 보조 신호. `MatchTier.POSITION` 판정에 사용.

```
StructuralSignals (dataclass):
  is_last_in_section: bool     # 섹션(자산/부채/자본 블록) 마지막 행
  indent_level: int            # 들여쓰기 레벨 (0=최상위)
  has_subtotal_style: bool     # 볼드 또는 bgcolor 적용 여부
  follows_subtotals: bool      # 앞 행들이 소계 패턴
```

**구현 원칙:** `label_resolver.py`가 `ReportTable.rows` 데이터를 받아 내부적으로 계산.  
`html_tables.py`·`TableRow` 수정은 불필요. 들여쓰기 레벨은 `row[0]`의 선행 공백(또는 `<td class>`)으로 추정, 스타일은 `TableRow.cell_source_lines`의 HTML 원문 파편에서 추출.

### 4.4 `ParseUncertainReason` — 실패 사유 코드

`parse_uncertain` 결과에 사유를 코드로 첨부해 UI와 향후 디버깅에 활용.

```
ParseUncertainReason (enum):
  LABEL_NOT_FOUND           # 어떤 계층도 매칭 안 됨
  LOW_CONFIDENCE_MATCH      # 매칭됐으나 신뢰도 < 0.70
  AMBIGUOUS_MULTIPLE        # 동일 점수 후보 복수 존재
  COLUMN_NOT_DETECTED       # 당기/전기 컬럼 식별 실패
  TABLE_NOT_FOUND           # 대상 재무제표/주석 섹션 자체 없음
  AMOUNT_PARSE_FAILED       # 행은 찾았으나 숫자 추출 실패
```

`CheckResult.parse_uncertain_reason: ParseUncertainReason | None` 필드 추가.

### 4.5 영향 범위

| 파일 | 변경 유형 |
|------|----------|
| `label_resolver.py` | 신규 생성 |
| `checks_statement_ties.py` | `_find_row()` → `LabelResolver` 교체 |
| `checks_totals.py` | 동일 |
| `footing.py` | 동일 |
| `note_assertions.py` | 동일 |
| `domain.py` | `CheckResult`에 `parse_uncertain_reason` 필드 추가 |
| `html_tables.py` | `TableRow`에 `structural_hints` 추가 (선택적) |

---

## 5. HTML 보고서 아키텍처

### 5.1 교체 대상

`src/dart_footing_reconciler/report_html.py` (6,342 lines) 전면 교체.  
동일한 Python 모듈 경로와 공개 함수 시그니처 유지:

```python
def export_audit_reconciliation_html(
    report: FullReport,
    check_results: list[CheckResult],
    output_path: Path,
    *,
    company_name: str = "",
    period_label: str = "",
) -> None: ...
```

CLI(`cli.py`)의 `export_audit_reconciliation_html` 호출부는 수정 없음.

### 5.2 내부 렌더링 구조

```
report_html.py
 ├── _build_html(report, results, meta) → str          # 진입점
 ├── _render_sidebar(nav_items) → str
 ├── _render_verdict_banner(summary) → str             # KPI strip + 전체 판정
 ├── _render_statement_panel(stmt, tied_results) → str # 재무제표 원문 + tick
 ├── _render_note_panel(note, tied_results) → str      # 주석 원문 + check rows
 ├── _render_parse_uncertain_panel(results) → str      # 파싱 실패 진단
 └── _inline_js() → str                               # 드릴다운 micro-runtime
```

`FullReport`와 `list[CheckResult]`만 입력. 외부 CDN·프레임워크 없음.

### 5.3 결과 연결 (tying)

`report_html.py`는 렌더링 전에 `CheckResult` 목록을 소스 위치로 분류:

```python
def _tie_results(
    results: list[CheckResult],
) -> dict[str, list[CheckResult]]:
    # key: "bs" | "is" | "sce" | "cf" | "note:{note_no}"
    # value: 해당 섹션과 관련된 CheckResult 목록
```

`CheckResult.evidence`의 `source` 필드에서 섹션 키를 추출. 예: `"statement:bs/..."` → `"bs"`.

---

## 6. 패널별 상세 스펙

### 6.1 Verdict Banner (요약 패널)

최상단 고정. 3개 KPI 타일 + 전체 판정 뱃지.

| KPI | 계산 방법 |
|-----|----------|
| 검증 완료 | `status == MATCHED` 건수 |
| 검토 필요 | `status == UNEXPLAINED_GAP` 건수 |
| 파싱 불확실 | `status == PARSE_UNCERTAIN` 건수 |

전체 판정: UNEXPLAINED_GAP > 0 → **검토 필요** (주황), PARSE_UNCERTAIN > 0 → **확인 필요** (회색), 나머지 → **이상 없음** (초록).

### 6.2 재무제표 본문 패널 (BS / IS / SCE / CF)

**핵심 원칙:** DART 원문 표를 수정 없이 렌더링. 검증 결과는 오버레이만.

구성:
1. `<table class="fs-table">` — 원문 행 그대로 (과목 / 당기 / 전기)
2. 검증 관련 행에 CSS 클래스 추가: `verified-ok`, `verified-warn`, `verified-uncertain`
3. 각 클래스별 `::after` pseudo-element로 ✓ / ⚠ / ? 배지 표시
4. 배지 행 클릭 시 바로 아래 `<tr class="dd-row">` 인라인 확장
5. 드릴다운 내용: 좌(원본 소스 셀) + 우(대응 소스 셀) + 판정 콜아웃

**파싱 불확실 행 처리:**  
`parse_uncertain_reason`이 있으면 `verified-uncertain` 클래스. `?` 배지.  
드릴다운: "파서가 찾은 항목: {matched_label}, 신뢰도: {confidence*100:.0f}%, 사유: {reason}"

**행 연결 방식:**  
`CheckResult.evidence`의 `source`에서 row index를 추출해 `<tr data-check-row="{idx}">` attribute로 마킹. JavaScript가 클릭 이벤트를 row index로 매핑.

### 6.3 주석별 패널

사이드바 `주석 {N}` 항목 선택 시 표시. 구성:

1. 주석 원문 테이블 (원문 그대로)
2. 해당 주석에 연결된 CheckResult 목록 — 비교 행 형태
   ```
   [✓/⚠/?] {check 이름}    {expected}  →  {actual}   차이 {diff}
   ```
3. 각 비교 행 클릭 → 인라인 드릴다운 (근거 셀 좌우 비교)

### 6.4 파싱 진단 패널

파싱 실패 건이 1건 이상일 때만 사이드바에 "파싱 진단 {N건}" 항목 표시.

구성: 실패 건별 카드. 각 카드:
- 어느 재무제표/주석의 어느 역할(AccountRole) 탐색에 실패했는가
- `ParseUncertainReason` 코드 + 한국어 설명
- 시도한 후보 레이블 목록과 신뢰도
- 사용자 행동 가이드: "이 항목이 공시에 포함된 경우 issue를 제보하세요"

---

## 7. Outcome Label → UI 매핑

| CheckResult.status | badge class | 배지 | 배경 | 의미 (사용자용) |
|---|---|---|---|---|
| MATCHED | `verified-ok` | ✓ | `--ok-dim` | 일치 |
| UNEXPLAINED_GAP | `verified-warn` | ⚠ | `--warn-dim` | 차이 발생 |
| UNRESOLVED_WITH_SIGNATURE | `verified-warn` | ⚠ | `--warn-dim` | 서명 불일치 |
| PARSE_UNCERTAIN (confidence ≥ 0.4) | `verified-uncertain-low` | ? | `--surface-2` | 낮은 신뢰도로 확인됨 |
| PARSE_UNCERTAIN (no match) | `verified-uncertain` | ? | `--surface-2` | 확인 불가 |

---

## 8. 데이터 흐름

```
CLI: export_audit_reconciliation_html(report, results, output_path)
  │
  ▼
report_html._build_html(report, results, meta)
  │
  ├─ _tie_results(results)          → dict[section_key, list[CheckResult]]
  │
  ├─ _render_sidebar(nav_items)     → sidebar HTML
  │
  ├─ _render_verdict_banner(...)    → banner HTML
  │
  ├─ for stmt in [bs, is, sce, cf]:
  │    _render_statement_panel(stmt, tied[stmt.kind])
  │      ├─ 원문 행 렌더링
  │      └─ 검증 행 오버레이 (data-check-row, css class)
  │
  ├─ for note in report.notes:
  │    _render_note_panel(note, tied[f"note:{note.note_no}"])
  │
  ├─ _render_parse_uncertain_panel(uncertain_results)
  │
  └─ _inline_js()                   → micro-runtime (드릴다운 토글)
```

외부 네트워크 호출 없음. CSS·JS 모두 인라인.

---

## 9. 디자인 토큰 (evidence_cockpit)

```css
:root {
  --bg: #ffffff; --surface: #f8fafc; --surface-2: #f1f5f9;
  --border: #e2e8f0; --text: #0f172a; --muted: #64748b;
  --accent: #3b82f6; --accent-dim: rgba(59,130,246,0.12);
  --warn: #f59e0b; --warn-dim: #fef3c7;
  --ok: #16a34a; --ok-dim: #dcfce7;
  --down: #dc2626; --down-dim: #fee2e2;
  --sidebar-bg: #0f172a; --sidebar-text: #94a3b8;
  --sidebar-active: #f1f5f9; --sidebar-accent: #3b82f6;
  --font: Pretendard, ui-sans-serif, system-ui, -apple-system, sans-serif;
}
/* letter-spacing: 0; line-height: 1.6; font-size base: 13px */
```

---

## 10. 엣지 케이스 및 오류 처리

| 상황 | 처리 |
|------|------|
| 재무제표 섹션 자체 없음 (파싱 실패) | 해당 사이드바 항목 비활성화 + "공시에서 찾을 수 없음" 표시 |
| 검증 결과 0건 | Verdict Banner: "검증 항목 없음" 안내 |
| 주석 연결 검증 없는 주석 | 주석 원문만 표시, 검증 결과 섹션 생략 |
| Label Resolver 신뢰도 0.40~0.69 | 검증 실행 + `PARSE_UNCERTAIN` 플래그 + 실제 차이도 표시 |
| 단위 mismatch (백만원 vs 원) | `CheckResult.difference`가 비정상적으로 크면 별도 경고 ("단위 차이 가능성") |

---

## 11. 범위 밖 (Out of Scope)

- 사용자가 매핑을 직접 수정하는 interactive 편집 UI
- 회사별 alias 커스터마이징 파일 제공
- PDF 출력 최적화
- 서버 배포 / 동적 API

파싱 강건화는 **새 `label_resolver.py` 모듈 신설 + 기존 check 모듈의 직접 frozenset 참조 교체**로 구현. 기존 `html_tables.py`·`document.py`의 HTML 파싱 로직은 건드리지 않음.

---

## 12. Codex 구현 가이드라인

- `label_resolver.py` 신설 후 check 모듈을 순차적으로 마이그레이션. 기존 테스트가 깨지지 않아야 함.
- `report_html.py` 교체는 `export_audit_reconciliation_html` 시그니처 유지 필수. `cli.py` 수정 불필요.
- 드릴다운 JS는 외부 라이브러리 없이 `data-*` attribute 기반 micro-runtime으로 구현.
- 각 렌더링 함수(`_render_*`)는 독립적으로 단위 테스트 가능하게 작성 (`str` 반환, HTML 파싱으로 assertion).
- `label_resolver.py`의 `LabelResolver.find_row()` 메서드는 결정적(deterministic)이어야 함 — 동일 입력에 동일 `RowMatch` 반환.

---

_Spec written: 2026-06-12 | Author: Claude (brainstorming session) | Next: writing-plans_
