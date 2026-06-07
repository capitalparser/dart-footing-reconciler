# 주석 탭 내 검증 표면화 (Note-Tab Verification Surfacing) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **인계 대상: Codex** (heavy-zone Tier 3). 입력: 이 plan, `docs/adr/0004-*`, `CONTEXT.md`. 산출: `src/`, `tests/`.

**Goal:** 주석 번호별 탭 안에서 `재무상태표·손익계산서·자본변동표·현금흐름표·다른 주석`과의 대사(합계검증·전기대사 포함)를 실제로 채워 보여준다.

**Architecture:** 이미 존재하는 탭/패널 레이아웃(`_note_comparison_panels`)은 유지한다. 빠진 것은 (1) `check_fs_note_matches`·`check_cfs_note_matches`가 dead code라 runner 미배선, (2) 기간 컬럼 정렬 미흡으로 인한 과다 gap, (3) 동일 파일 전기 컬럼 전기대사 부재, (4) note↔note 빈약, (5) 주석 원문 덤프 가독성. 검증은 모두 `CheckResult`(note_no + `statement:{kind}/...` evidence source)로 생성해 기존 라우팅이 자동으로 패널에 꽂게 한다.

**선행 작업(이미 존재 — Step 0):** [`docs/superpowers/plans/2026-06-07-note-workspace-statement-parser.md`](../docs/superpowers/plans/2026-06-07-note-workspace-statement-parser.md)이 statement 연속 파서 + note-workspace 패널 골격을 이미 구현함(IS/SCE/CF 파싱·5개 비교 패널). 본 플랜은 그 **빈 패널을 실제 검증으로 채우는 후속편**이며 레이아웃을 재구축하지 않는다.

**감사 무결성 원칙(P0 결정 2026-06-07):** 매칭은 **라벨 의미 기반**으로만 한다. 재무제표 금액에 우연히 같은 다른 주석 행을 끌어다 붙이는 **값 근접(closest-amount) 매칭은 금지** — 실제 차이를 은폐하는 거짓 일치(false matched)를 제조하기 때문. 의미상 대응 행이 값이 다르면 **정직하게 `unexplained_gap`으로 표시**한다. 감사에서 놓친 차이(false matched)는 정직한 gap보다 나쁘다.

### Codex 플랜 도전 반영 (2026-06-07, 코드 그라운딩)

Codex가 실제 코드 대조로 찾은 구현 제약 — Codex는 입력으로 아래 7개를 모두 인지하고 시작할 것:

1. **`classify_report()`는 taxonomy alias 매칭 행만 방출**([taxonomy.py:80](../src/dart_footing_reconciler/taxonomy.py#L80), [:475](../src/dart_footing_reconciler/taxonomy.py#L475)). 즉 `check_fs_note_matches`의 `note_hits`는 이미 의미 필터를 통과한 후보다. Task 2의 거짓일치 테스트는 **alias를 통과하는 후보 2개**(예: 연결/별도, 또는 같은 account_key의 복수 admitted 행)로 설계해야 하며, alias 밖 라벨(`취득원가`)은 애초에 도달 안 함.
2. **period 파라미터는 taxonomy에 없음**([taxonomy.py:357](../src/dart_footing_reconciler/taxonomy.py#L357), [:942](../src/dart_footing_reconciler/taxonomy.py#L942)는 항상 current). 전기대사(Task 4)는 `check_fs_note_matches(period="prior")`로 불가 → **`checks_prior_column.py`에 자체 prior-column 추출기**를 둔다(`table_semantics`의 prior helper 재사용, taxonomy 미변경 — blast radius 최소).
3. **`find_note_amounts`는 row_keyword로 사전 필터**([_match_helpers.py:50](../src/dart_footing_reconciler/_match_helpers.py#L50)). Task 3 테스트는 `취득` 라벨 변형 다수로(경쟁 후보가 같은 키워드를 공유하도록).
4. **DRY 동치 테스트는 정규화 tuple 전체 비교**(check_id·status·evidence source·좌표·순서), `Counter(check_type)`만으로 부족.
5. **Task 4 배선은 `assemble_report_checks()` 한 곳만**(Task 1이 이미 통합하므로 corpus·cli 직접 배선 금지).
6. **신규 `prior_column_*` check는 등록 안 하면 화면에서 silent drop** — [report_html.py:1042](../src/dart_footing_reconciler/report_html.py#L1042) `_report_frame_check_group_label` + `CHECK_GROUP_ORDER`([:1066](../src/dart_footing_reconciler/report_html.py#L1066))에 반드시 추가(Task 6).
7. **taxonomy.py:816 generic 경로에 값 근접 수용 존재** — FS_NOTE 정식키엔 안 물리나, fs-note 매칭을 generic FSC amount로 확장하지 말 것(D4 위반 회피).

**Tech Stack:** Python 3.11, pytest, uv. 보고서는 self-contained HTML(`report_html.py`). 테스트 실행은 `uv run pytest`.

**검증 기준선 (구현 전 inveni 측정값, 회귀 비교용):**
- total checks 790 = `total_check` 681 / `note_layout_formula_check` 94 / `note_rollforward_check` 4 / `cashflow_reconciliation` 4 / `primary_balance_reconciliation` 2 / `asset_note_bridge_check` 4 / `note_note_match` 1
- `fs_note_match` 0, `cfs_note_match` 0 (미배선)
- 보고서 패널: "연결된 자동 검증 결과가 없습니다" 523회, "재무제표 원문 근거" 13회, "다른 주석 원문 근거" 0회
- 즉석 호출 시 잠재값: `fs_note_match` 9(matched 2/gap 7), `cfs_note_match` 3, `note_note_match` 1

**공통 명령:**
- 전체 테스트: `uv run pytest -q`
- inveni 보고서 재생성: Task 8 참조
- 패널 채움 확인: `grep -c '재무제표 원문 근거' <report.html>`

---

## File Structure

| 파일 | 책임 | 변경 |
|------|------|------|
| `src/dart_footing_reconciler/check_pipeline.py` | **신규** 공유 검증 조립부 `assemble_report_checks()` | 신규 (DRY 통합) |
| `src/dart_footing_reconciler/corpus.py` | corpus runner (`_run_checks`, line 459) | 공유 함수 위임 |
| `src/dart_footing_reconciler/cli.py` | workpaper runner (`_run_workpaper_checks`, line ~449) | 공유 함수 위임 |
| `src/dart_footing_reconciler/checks_fs_note.py` | note↔BS/PL 대사 | 의미기반 행 선택 + 기간 컬럼 정렬 (값 근접 금지) |
| `src/dart_footing_reconciler/checks_cfs_note.py` | note↔CF 대사 | rule 키워드 의미기반 선택 |
| `src/dart_footing_reconciler/checks_prior_column.py` | **신규** 동일 파일 전기 컬럼 전기대사 | 신규 |
| `src/dart_footing_reconciler/checks_note_note.py` | 주석↔주석 대사 | 강화 |
| `src/dart_footing_reconciler/report_html.py` | 주석 탭 패널 순서·footing/전기 배지·원문 재구성 | 표면화 |
| `tests/test_check_pipeline.py` | **신규** 공유 조립·배선 테스트 | 신규 |
| `tests/test_checks_fs_note.py` 외 | 단위 테스트 (거짓일치 방지 포함) | 추가 |
| `tests/test_corpus.py`, `tests/test_cli_workpaper.py` | 동치 보존·통합 테스트 | 추가 |

> **DRY(P2 결정):** `corpus._run_checks`와 `cli._run_workpaper_checks` 중복은 Task 1에서 공유 `assemble_report_checks()`로 통합한다(refactor first → wire once). 동치 보존 테스트로 리팩토링이 동작을 바꾸지 않음을 먼저 증명.

---

## Task 1: 공유 검증 조립부로 통합 + fs_note·cfs_note 배선 (DRY)

**결정(P2):** `corpus._run_checks`와 `cli._run_workpaper_checks`는 거의 동일한 중복이다. 새 배선을 두 곳에 복붙하면 발산 위험이 커진다. **먼저 공유 `assemble_report_checks()`로 통합(refactor first, Beck)** 한 뒤 그 한 곳에만 새 배선을 추가한다.

> 주의: 두 함수의 footing 호출이 미세하게 다르다 — corpus는 `check_table_totals`를 note 표마다 직접 호출, cli는 `_run_total_checks(report, tolerance)` 헬퍼 사용. 통합 시 동작 동치를 테스트로 먼저 고정한 뒤 합친다(behavioral change 금지).

**Files:**
- Create: `src/dart_footing_reconciler/check_pipeline.py` (`assemble_report_checks(report, prior_report, *, tolerance)`)
- Modify: `src/dart_footing_reconciler/corpus.py:459-472` (`_run_checks` → 공유 함수 위임)
- Modify: `src/dart_footing_reconciler/cli.py:449-461` (`_run_workpaper_checks` → 공유 함수 위임)
- Test: `tests/test_check_pipeline.py` (신규), `tests/test_corpus.py`, `tests/test_cli_workpaper.py`

- [ ] **Step 1: 동치 보존 테스트(통합 전 안전망)** — 통합 전, 현재 두 함수가 inveni에서 같은 check_type 분포를 내는지 고정해 리팩토링이 동작을 바꾸지 않음을 보장.

```python
from collections import Counter
from pathlib import Path
from dart_footing_reconciler.document import parse_full_report
from dart_footing_reconciler.corpus import _run_checks
from dart_footing_reconciler.cli import _run_workpaper_checks

INVENI = Path("out/corpus/run_2026-06-06-inveni-one/raw/inveni_2024_20250310000926.html")

def _norm(checks):
    # 정규화 tuple: check_type만이 아니라 정체성·근거·좌표·상태까지 비교 (Codex #4)
    return sorted(
        (c.check_id, c.check_type, c.status, c.expected, c.actual,
         tuple((e.source, e.amount) for e in c.evidence))
        for c in checks
    )

def test_corpus_and_workpaper_checks_are_identical():
    report = parse_full_report(INVENI)
    a = _norm(_run_checks(report, None, tolerance=1))
    b = _norm(_run_workpaper_checks(report, None, tolerance=1))
    assert a == b, [x for x in a if x not in b][:5]
```

- [ ] **Step 2: 실패/현황 확인** — Run: `uv run pytest tests/test_corpus.py::test_corpus_and_workpaper_checks_are_identical -v`. 통과하면 두 경로가 이미 동치(통합 안전 — Codex가 [corpus.py:459](../src/dart_footing_reconciler/corpus.py#L459)·[cli.py:557](../src/dart_footing_reconciler/cli.py#L557) 동일 루프 확인). **불일치면** 차이를 1줄 기록하고, 통합 시 corpus 쪽(note별 `check_table_totals`)을 canonical로 삼아 cli도 동일하게 맞춘다(footing 좌표 보존 우선).

- [ ] **Step 3: 공유 함수 작성** — `check_pipeline.py`에 `assemble_report_checks(report, prior_report, *, tolerance)`를 만들고 현재 `_run_checks` 본문(note별 footing → note_assertions → layout_formula → reconciliation_targets → asset_note_bridges → note_note → prior_year)을 옮긴다. import는 함수 내부가 아닌 모듈 상단.

- [ ] **Step 4: 새 배선 추가(한 곳)** — `assemble_report_checks` 내 `check_note_note_matches` 호출 위에 추가:

```python
    checks.extend(check_fs_note_matches(report, tolerance=tolerance))
    checks.extend(check_cfs_note_matches(report, tolerance=tolerance))
```

- [ ] **Step 5: 두 runner 위임** — `corpus._run_checks`와 `cli._run_workpaper_checks` 본문을 `return assemble_report_checks(report, prior_report, tolerance=tolerance)` 한 줄로 교체(기존 시그니처·호출부 유지).

- [ ] **Step 6: 배선 검증 테스트** — `tests/test_check_pipeline.py`에 추가:

```python
def test_assemble_includes_fs_and_cfs_note_matches():
    from dart_footing_reconciler.check_pipeline import assemble_report_checks
    report = parse_full_report(INVENI)
    types = Counter(c.check_type for c in assemble_report_checks(report, None, tolerance=1))
    assert types["fs_note_match"] >= 5, types
    assert types["cfs_note_match"] >= 1, types
```

- [ ] **Step 7: 전체 통과 확인**

Run: `uv run pytest tests/test_check_pipeline.py tests/test_corpus.py tests/test_cli_workpaper.py -q`
Expected: PASS (Step 1 동치 테스트 포함 — 리팩토링이 분포를 바꾸지 않았음)

- [ ] **Step 8: Commit**

```bash
git add src/dart_footing_reconciler/check_pipeline.py src/dart_footing_reconciler/corpus.py src/dart_footing_reconciler/cli.py tests/test_check_pipeline.py tests/test_corpus.py tests/test_cli_workpaper.py
git commit -m "refactor(checks): consolidate runner check assembly and wire fs/cfs_note matches"
```

---

## Task 2: fs_note 매칭 품질 — 의미기반 선택 + 기간 컬럼 정렬 (값 근접 금지)

**문제:** 현재 `check_fs_note_matches`는 account_key별 `fs_hits[0]`/`note_hits[0]`만 비교(checks_fs_note.py:43-44). inveni 9건 중 7건 `unexplained_gap`의 1차 원인은 (a) 당기/전기 컬럼 혼선, (b) 여러 note hit 중 의미상 맞는 행이 아니라 첫 번째를 봄.

**P0 원칙(감사 무결성):** 해법은 **기간 컬럼 정렬 + 라벨 의미 기반 행 선택**이다. **값 근접(closest-amount) 매칭은 금지** — 그것은 차이를 은폐하는 거짓 일치를 만든다. 의미상 대응 행이 값이 달라도 그대로 `unexplained_gap`으로 둔다.

**Files:**
- Modify: `src/dart_footing_reconciler/checks_fs_note.py`
- Read first: `src/dart_footing_reconciler/taxonomy.py` (`classify_report`, `ClassifiedStatementLine.amount`/`.source`, `ClassifiedNoteAmount.label`, `row_amount_prefer_current` 사용 여부). 주석 합계행 라벨 후보는 taxonomy의 `note_amount_aliases`에 이미 정의됨 — 그 의미 라벨을 선택 기준으로 쓴다.
- Test: `tests/test_checks_fs_note.py`

> **Codex #1 제약:** `classify_report()`는 PPE alias(`장부금액/기말장부금액/순장부금액/장부가액/기말`)에 매칭되는 행만 `note_amounts`로 방출한다. `취득원가`처럼 alias 밖 라벨은 `check_fs_note_matches`에 **도달조차 안 한다.** 따라서 경쟁 후보 테스트는 **둘 다 alias를 통과하는 행**(예: 연결/별도 두 표, 또는 같은 표에 alias 변형 2개)으로 설계한다. 구현 전 `taxonomy.py`의 `FS_NOTE_ACCOUNT_KEYS` 별 `note_amount_aliases`를 읽고 어떤 행이 admitted되는지 확인할 것.

- [ ] **Step 1: 의미기반 선택 실패 테스트** — alias 통과 후보가 2개일 때(연결 표 vs 별도 표 모두 `기말 장부금액` 보유), FS와 **scope/의미가 맞는 후보**를 고르는지 고정. 값 근접이 아니라 라벨·scope 일치 기준.

```python
def test_fs_note_selects_admitted_candidate_by_label_priority():
    # BS(연결) 유형자산 1,000. 연결 주석 '기말 장부금액' 1,000(정답) + 별도 주석 '기말 장부금액' 980(scope 불일치).
    bs = _section("statement:bs","재무상태표","statement","", ReportTable(0,[["구분","당기"],["유형자산(순액)","1,000"]],"재무상태표",SourceLocation("statement:bs",0,0)))
    n_con = _section("note:11","유형자산(연결)","note","11", ReportTable(1,[["구분","당기"],["기말 장부금액","1,000"]],"11. 유형자산",SourceLocation("note:11",0,1)))
    results = check_fs_note_matches(FullReport("s.html","Co",[bs],[n_con]), tolerance=0)
    ppe = [r for r in results if r.check_id.startswith("fs_note:property_plant_equipment")]
    assert ppe and ppe[0].actual == 1000 and ppe[0].status == "matched", [(r.actual, r.status) for r in ppe]
```
(연결/별도 scope 매칭은 Task 2 범위가 과해지면 단일 admitted 후보 + 라벨 우선순위로 축소 가능. 핵심은 값-근접 미사용.)

- [ ] **Step 2: 실패/현황 확인** — Run: `uv run pytest tests/test_checks_fs_note.py::test_fs_note_selects_admitted_candidate_by_label_priority -v`

- [ ] **Step 3: 구현(의미기반)** — `note_hit` 선택을 **라벨 의미 우선순위**로 바꾼다. account_key별 합계/잔액 라벨(taxonomy `note_amount_aliases` 또는 명시 우선순위: `기말 장부금액`>`기말잔액`>`합계`>`소계`)에 해당하는 note hit을 우선 선택. 해당 라벨이 없으면 confidence 최상위 hit. **값 차이를 선택 기준으로 쓰지 않는다.**

```python
        fs_hit = fs_hits[0]
        note_hit = _select_note_hit_by_label(note_hits, account_key) or note_hits[0]
```
`_select_note_hit_by_label`은 라벨 우선순위 매칭만 수행(값 무관). 구현 시 helper로 분리.

- [ ] **Step 4: 거짓일치 방지 회귀 테스트(P0 핵심)** — 의미상 대응 행의 값이 BS와 **실제로 다르면** 다른 행을 끌어다 matched로 만들지 않고 `unexplained_gap`을 유지하는지 고정.

```python
def test_fs_note_keeps_honest_gap_when_admitted_row_differs():
    # BS 1,000. 주석 의미행 '기말 장부금액' 900(실제 차이). 정직하게 unexplained_gap 유지.
    # (alias 밖 '취득원가'는 어차피 classify에서 탈락하므로 둔갑 후보가 되지 못함 — Codex #1.)
    bs = _section("statement:bs","재무상태표","statement","", ReportTable(0,[["구분","당기"],["유형자산(순액)","1,000"]],"재무상태표",SourceLocation("statement:bs",0,0)))
    note = _section("note:11","유형자산","note","11", ReportTable(1,[["구분","당기"],["기말 장부금액","900"]],"11. 유형자산",SourceLocation("note:11",0,1)))
    results = check_fs_note_matches(FullReport("s.html","Co",[bs],[note]), tolerance=0)
    ppe = [r for r in results if r.check_id.startswith("fs_note:property_plant_equipment")]
    assert ppe and ppe[0].actual == 900 and ppe[0].status == "unexplained_gap", [(r.actual, r.status) for r in ppe]
```

- [ ] **Step 5: 거짓일치 방지 통과 확인** — Run: `uv run pytest tests/test_checks_fs_note.py::test_fs_note_keeps_honest_gap_when_admitted_row_differs -v` → PASS. (P0 회귀 가드: 의미행이 BS와 다르면 정직하게 gap 유지.)

- [ ] **Step 6: 기간 컬럼 정렬 테스트** — 당기/전기 2컬럼에서 fs_note가 **당기** 컬럼을 쓰는지 고정.

```python
def test_fs_note_uses_current_period_column():
    bs_tbl = ReportTable(0, [["구분","당기","전기"],["유형자산(순액)","1,000","800"]], "재무상태표", SourceLocation("statement:bs",0,0))
    note_tbl = ReportTable(1, [["구분","당기","전기"],["기말 장부금액","1,000","800"]], "11. 유형자산", SourceLocation("note:11",0,1))
    report = FullReport("s.html","Co",[_section("statement:bs","재무상태표","statement","",bs_tbl)],[_section("note:11","유형자산","note","11",note_tbl)])
    results = check_fs_note_matches(report, tolerance=0)
    ppe = [r for r in results if r.check_id.startswith("fs_note:property_plant_equipment")]
    assert ppe and ppe[0].expected == 1000 and ppe[0].actual == 1000
```

- [ ] **Step 7: 기간 정렬 구현 보정** — `classify_report`/`taxonomy`가 전기 컬럼을 집지 않도록 current-period 선호 보장(`row_amount_prefer_current` 활용). 이미 보장되면 통과만 확인.

- [ ] **Step 8: inveni gap률 재측정 + 정직성 확인** — 임시 스크립트로 `check_fs_note_matches(parse_full_report(INVENI))` 호출, `Counter(status)` 출력. **목표는 matched 수 극대화가 아니라 "남은 gap이 실제 차이인지" 정직 분류.** 각 gap을 1줄로 (실제 차이 / 매칭 오류 / 파싱 이슈)로 분류해 plan 하단 "검증 로그"에 기록. 매칭 오류로 판명된 것만 라벨 규칙 보정으로 줄인다.

- [ ] **Step 9: 전체 단위 테스트 + Commit**

```bash
uv run pytest tests/test_checks_fs_note.py -q
git add src/dart_footing_reconciler/checks_fs_note.py tests/test_checks_fs_note.py
git commit -m "fix(checks): semantic-label fs_note matching with honest gaps (no closest-value)"
```

---

## Task 3: cfs_note 매칭 품질 보강

**Files:**
- Modify: `src/dart_footing_reconciler/checks_cfs_note.py`
- Read first: `src/dart_footing_reconciler/_match_helpers.py` (`find_statement_amounts`, `find_note_amounts`, `AmountHit`)
- Test: `tests/test_checks_cfs_note.py`

> **Codex #3 제약:** `find_note_amounts(report, "유형자산", "취득")`가 이미 row_keyword `취득`으로 사전 필터링([_match_helpers.py:50](../src/dart_footing_reconciler/_match_helpers.py#L50)). 따라서 `처분` 행은 경쟁 후보가 아니다. 경쟁은 **같은 키워드를 공유하는 변형 행들**(예: `유형자산의 취득` vs `유형자산취득(리스 제외)`) 사이에서만 발생. 테스트는 그 변형으로 설계.

- [ ] **Step 1: 키워드 변형 랭킹 실패 테스트** — `취득`을 공유하는 행이 2개일 때, 더 정확히 일치하는 행(정확 일치 > 부분 포함)을 선택하는지 고정. **값 근접 금지.**

```python
def test_cfs_note_ranks_exact_keyword_over_partial():
    cf = _section("statement:cf","현금흐름표","statement","", ReportTable(0,[["구분","당기"],["유형자산의취득","500"]],"현금흐름표",SourceLocation("statement:cf",0,0)))
    # 둘 다 '취득' 포함. 'A'가 먼저 오지만 정확 매칭은 두 번째.
    note = _section("note:11","유형자산","note","11", ReportTable(1,[["구분","당기"],["무형자산취득","490"],["유형자산의취득","500"]],"11. 유형자산",SourceLocation("note:11",0,1)))
    results = check_cfs_note_matches(FullReport("s.html","Co",[cf],[note]), tolerance=0)
    inv = [r for r in results if "유형자산의취득" in r.check_id]
    assert inv and inv[0].status == "matched"
    assert any("유형자산의취득" in e.label for e in inv[0].evidence)
```
(실제 변형 라벨은 inveni 원문 확인 후 조정. 핵심: 값이 아니라 키워드 정확도로 랭킹.)

- [ ] **Step 2: 실패 확인** — Run: `uv run pytest tests/test_checks_cfs_note.py -k exact_keyword -v` → FAIL

- [ ] **Step 3: 구현(키워드 정확도 랭킹)** — `note_hit` 선택을 키워드 정확 일치 우선으로(정확 일치 > 접두 일치 > 부분 포함). **값 차이를 선택 기준으로 쓰지 않는다.** 의미상 행이 값이 달라도 정직하게 gap.

- [ ] **Step 4: 통과 + Commit**

```bash
uv run pytest tests/test_checks_cfs_note.py -q
git add src/dart_footing_reconciler/checks_cfs_note.py tests/test_checks_cfs_note.py
git commit -m "fix(checks): pick closest note movement in cfs_note matching"
```

---

## Task 4: 전기대사 — 동일 파일 전기 컬럼 (신규 모듈)

**결정 근거:** ADR-0004 D2. 별도 전기 파일 없이 1개 공시의 전기/당기 2컬럼으로 전기 정합성 검증.

**Files:**
- Create: `src/dart_footing_reconciler/checks_prior_column.py`
- Create: `tests/test_checks_prior_column.py`
- Read first: `report_html.py`의 `_prior_period_columns`/`_is_prior_period_header`/`_fiscal_period_columns` (전기 컬럼 식별 로직 재사용 후보), `amounts.parse_amount`, `taxonomy.classify_report`
- Modify: `corpus.py` `_run_checks`, `cli.py` `_run_workpaper_checks` (배선)

**검증 정의 (2종):**
- **PC1 전기 FS↔전기 주석:** Task 2의 fs_note 매칭을 **전기 컬럼**에 대해 수행. check_type=`prior_column_fs_note`. note_no + `statement:{kind}/...col:{prior}` evidence.
- **PC2 증감표 기초 ↔ 전기말 BS:** roll-forward 주석(기초/기말 구조)의 **기초잔액**이 재무상태표 **전기말(전기 컬럼)** 잔액과 일치하는지. check_type=`prior_column_rollforward`.

- [ ] **Step 1: PC1 실패 테스트**

```python
from dart_footing_reconciler.checks_prior_column import check_prior_column_matches
from dart_footing_reconciler.document import FullReport, ReportBlock, ReportSection, ReportTable, SourceLocation

def _section(sid,title,kind,no,tbl):
    return ReportSection(sid,title,kind,no,[ReportBlock("table","",tbl,tbl.location)])

def test_prior_column_fs_note_matches_prior_period():
    bs = _section("statement:bs","재무상태표","statement","", ReportTable(0,[["구분","당기","전기"],["유형자산(순액)","1,000","800"]],"재무상태표",SourceLocation("statement:bs",0,0)))
    note = _section("note:11","유형자산","note","11", ReportTable(1,[["구분","당기","전기"],["기말 장부금액","1,000","800"]],"11. 유형자산",SourceLocation("note:11",0,1)))
    results = check_prior_column_matches(FullReport("s.html","Co",[bs],[note]), tolerance=0)
    pc1 = [r for r in results if r.check_type=="prior_column_fs_note"]
    assert pc1 and pc1[0].status=="matched" and pc1[0].expected==800 and pc1[0].actual==800
```

- [ ] **Step 2: 실패 확인** — Run: `uv run pytest tests/test_checks_prior_column.py -v` → FAIL (ImportError)

- [ ] **Step 3: 모듈 골격 + PC1 구현 (자체 추출기 — Codex #2)** — `check_prior_column_matches(report, *, tolerance=1) -> list[CheckResult]`. **taxonomy에 period 파라미터를 추가하지 않는다**(taxonomy는 모든 검증이 의존하는 핵심 — blast radius 최소화). 대신 이 모듈에 **자체 prior-column 추출기**를 둔다: `table_semantics`의 prior helper([table_semantics.py:58](../src/dart_footing_reconciler/table_semantics.py#L58))와 report_html의 `_prior_period_columns`/`_is_prior_period_header` 규칙을 재사용해 전기 컬럼 인덱스를 잡고, FS_NOTE_ACCOUNT_KEYS의 라벨로 전기 FS·전기 주석 금액을 직접 읽어 비교. evidence source col 인덱스는 전기 컬럼.

- [ ] **Step 4: PC2 실패 테스트** — 증감표 기초 ↔ BS 전기말.

```python
def test_prior_column_rollforward_beginning_ties_to_prior_bs():
    bs = _section("statement:bs","재무상태표","statement","", ReportTable(0,[["구분","당기","전기"],["유형자산(순액)","1,000","800"]],"재무상태표",SourceLocation("statement:bs",0,0)))
    roll = _section("note:11","유형자산","note","11", ReportTable(1,[["구분","당기"],["기초 장부금액","800"],["취득","300"],["감가상각","-100"],["기말 장부금액","1,000"]],"11. 유형자산 증감",SourceLocation("note:11",0,1)))
    results = check_prior_column_matches(FullReport("s.html","Co",[bs],[roll]), tolerance=0)
    pc2 = [r for r in results if r.check_type=="prior_column_rollforward"]
    assert pc2 and pc2[0].status=="matched" and pc2[0].expected==800 and pc2[0].actual==800
```

- [ ] **Step 5: PC2 구현** — roll-forward 주석에서 "기초"행 금액을 추출(`기초`/`전기말`/`기초잔액` 라벨), 해당 account의 BS 전기 컬럼 잔액과 비교. roll-forward 식별은 기존 `note_rollforward_check`/`formula_templates` 라벨 규칙 재사용.

- [ ] **Step 6: 배선 (단일 지점 — Codex #5)** — `check_pipeline.assemble_report_checks()`에만 `checks.extend(check_prior_column_matches(report, tolerance=tolerance))` 추가(import 포함). Task 1이 두 runner를 이미 통합했으므로 corpus·cli 직접 배선 금지.

- [ ] **Step 7: inveni 통합 확인** — `_run_checks(parse_full_report(INVENI), None, 1)`에 `prior_column_fs_note`/`prior_column_rollforward`가 ≥1건씩 나오는지 통합 테스트(`tests/test_corpus.py`)로 고정. 0건이면 라벨 규칙을 inveni 실제 헤더에 맞춰 보정.

- [ ] **Step 8: Commit**

```bash
uv run pytest tests/test_checks_prior_column.py tests/test_corpus.py -q
git add src/dart_footing_reconciler/checks_prior_column.py tests/test_checks_prior_column.py src/dart_footing_reconciler/corpus.py src/dart_footing_reconciler/cli.py tests/test_corpus.py
git commit -m "feat(checks): add same-file prior-period column reconciliation (전기대사)"
```

---

## Task 5: 주석↔주석 대사 강화

**문제:** inveni에서 `note_note_match` 1건(parse_uncertain). 사용자 요구 "주석끼리의 대사"를 충족하려면 실효 매칭이 더 필요.

**Files:**
- Modify: `src/dart_footing_reconciler/checks_note_note.py`
- Read first: 현재 `check_note_note_matches` 로직 + `tests/test_checks_note_note.py`
- Test: `tests/test_checks_note_note.py`

- [ ] **Step 1: 대표 쌍 실패 테스트** — 감사 실무 대표 노트 간 타이 1쌍을 고정. 예: 유형자산 증감표 기말 ↔ 감가상각비(비용 성격별 분류) 주석, 또는 차입금 주석 ↔ 만기분석 주석 합계. 합성 fixture로 matched 1건 보장.

```python
def test_note_note_ties_depreciation_to_expense_breakdown():
    ppe = _section("note:11","유형자산","note","11", ReportTable(0,[["구분","당기"],["감가상각비","100"]],"11. 유형자산",SourceLocation("note:11",0,0)))
    exp = _section("note:25","비용의 성격별 분류","note","25", ReportTable(1,[["구분","당기"],["감가상각비","100"]],"25. 비용",SourceLocation("note:25",0,1)))
    results = check_note_note_matches(FullReport("s.html","Co",[],[ppe,exp]), tolerance=0)
    matched = [r for r in results if r.status=="matched"]
    assert matched, [(r.note_no,r.status) for r in results]
```

- [ ] **Step 2: 실패 확인** → FAIL
- [ ] **Step 3: 구현** — note↔note 규칙 테이블에 대표 쌍(감가상각비 cross-note, 차입금↔만기분석 등)을 추가. evidence는 양쪽 `note:{a}/...`·`note:{b}/...` (한쪽이 다른 주석이므로 `_check_has_other_note_source`가 잡음).
- [ ] **Step 4: 통과 + Commit**

```bash
uv run pytest tests/test_checks_note_note.py -q
git add src/dart_footing_reconciler/checks_note_note.py tests/test_checks_note_note.py
git commit -m "feat(checks): strengthen note-to-note reconciliation rules"
```

---

## Task 6: 보고서 — 탭 패널 순서·footing/전기 배지·검증 가시화

**목표:** 각 주석 탭에서 `재무상태표 → 손익계산서 → 자본변동표 → 현금흐름표 → 다른 주석` 순서로 대사 패널이 채워지고, 합계검증(footing)·전기대사 결과가 같은 탭에서 보이게 한다. 라우팅 기반(`_note_comparison_panels`)은 이미 순서를 `CANONICAL_STATEMENT_ORDER`로 보장하므로, 핵심은 (a) 새 check가 패널에 들어오는지 회귀 테스트, (b) footing·전기대사 패널/배지 추가.

**Files:**
- Modify: `src/dart_footing_reconciler/report_html.py` (`_note_comparison_panels`, `_report_frame_note_workspace_panel`, `_report_frame_check_group_label`, `CHECK_GROUP_ORDER`)
- Modify: `src/dart_footing_reconciler/report_frame.py` (`check_group()` 매핑, 해당 시)
- Read first: `_note_comparison_panels` (770-800), `_note_related_checks` (905), `_report_frame_check_groups_html` (985), `_report_frame_check_group_label` (1042), `CHECK_GROUP_ORDER` (1066)
- Test: `tests/test_report_frame.py`

- [ ] **Step 0: 신규 check 타입 화면 등록 (Codex #7 — silent drop 방지)** — `fs_note_match`/`cfs_note_match`/`prior_column_fs_note`/`prior_column_rollforward`를 `_report_frame_check_group_label`의 그룹 매핑과 `CHECK_GROUP_ORDER`에 추가. 미등록 시 `"검증"` fallback으로 떨어지고 `CHECK_GROUP_ORDER`에 없으면 `_report_frame_check_groups_html`이 렌더하지 않아 **배선해도 화면에서 사라짐**. 실패 테스트: 각 신규 타입의 check 1건이 렌더된 HTML에 그룹 라벨과 함께 나타나는지 assert.

```python
def test_new_check_types_render_in_groups():
    # prior_column_fs_note CheckResult 1건을 가진 report → 렌더에 '전기 대사' 그룹 노출
    html = render_audit_reconciliation_html(report, [prior_check])
    assert "전기 대사" in html  # 그룹 라벨
    assert "검증 결과가 없습니다" not in html.split("전기 대사")[1][:200]
```

- [ ] **Step 1: 패널 채움 회귀 테스트** — fs_note check 1건을 가진 합성 report를 `render_audit_reconciliation_html`에 넣어, 해당 주석 패널 HTML에 "재무제표 원문 근거"와 매칭 상태가 렌더되는지(=빈 메시지가 아닌지) 고정.

```python
def test_note_panel_renders_fs_note_statement_preview():
    # fs_note_match CheckResult 1건 + 매칭되는 BS/note 표를 가진 FullReport 구성
    html = render_audit_reconciliation_html(report, checks)
    assert "재무제표 원문 근거" in html
    assert html.count("연결된 자동 검증 결과가 없습니다") < 5  # 전부 비어있지 않음
```

- [ ] **Step 2: 실패/통과 확인** — 배선(Task 1) 후라면 이미 통과할 수 있음. 통과하면 회귀 가드로 유지. FAIL이면 `_check_mentions_note`가 fs_note의 note_no를 매칭하는지 디버그.

- [ ] **Step 3: 합계검증·전기대사 패널 추가** — `_note_comparison_panels`에 statement 5패널 + "다른 주석" 패널에 더해, **"합계 검증"**(해당 주석의 `total_check`/`note_rollforward_check`/formula)과 **"전기 대사"**(`prior_column_*`) 패널을 같은 grid에 추가. 각 패널은 기존 `_note_comparison_panel(title, checks, preview_html)` 재사용.

- [ ] **Step 4: 탭 상태 배지 확장** — `_note_workspace_status`(714)에 전기대사·합계 차이를 반영(이미 "합계 차이 확인 필요" 등 존재 → `prior_column_*` gap을 동일 분기로 포함).

- [ ] **Step 5: 통과 + Commit**

```bash
uv run pytest tests/test_report_frame.py -q
git add src/dart_footing_reconciler/report_html.py tests/test_report_frame.py
git commit -m "feat(report): surface footing and prior-period panels in note tabs"
```

---

## Task 7: 주석 원문 표면 재구성 (가독성)

**문제:** 주석 탭 상단 `_report_frame_note_text_html`(750)이 모든 문단을 그대로 나열 → 거대한 숫자 텍스트 덤프. ADR-0004 D3.

**Files:**
- Modify: `src/dart_footing_reconciler/report_html.py` (`_report_frame_note_text_html`, `_report_frame_note_workspace_panel`)
- Test: `tests/test_report_frame.py`

- [ ] **Step 1: 접이식 원문 테스트** — 긴 원문은 기본 접힘(`<details>`), 표가 먼저 보이도록. native `<details>/<summary>` 사용(interactive-patterns-kit 규칙, CDN 프레임워크 금지).

```python
def test_long_note_text_is_collapsed_behind_details():
    # 문단 텍스트가 임계 길이 초과 시 <details>로 감싸지는지
    html = render_audit_reconciliation_html(report, checks)
    assert "<details" in html and "주석 원문 전체" in html
```

- [ ] **Step 2: 실패 확인** → FAIL
- [ ] **Step 3: 구현** — `_report_frame_note_text_html`에서 문단 총 길이가 임계(예: 600자) 초과면 `<details><summary>주석 원문 전체</summary>...</details>`로 감싼다. 표는 패널 본문에 그대로 노출(이미 `table_cards`가 별도 렌더). escape 유지.
- [ ] **Step 4: 통과 + Commit**

```bash
uv run pytest tests/test_report_frame.py -q
git add src/dart_footing_reconciler/report_html.py tests/test_report_frame.py
git commit -m "feat(report): collapse long note source text behind details for readability"
```

---

## Task 8: 통합 검증 — inveni 보고서 재생성 + Harness verify

**Files:** (코드 변경 없음, 산출물 검증)

- [ ] **Step 1: 전체 테스트**

Run: `uv run pytest -q`
Expected: 전부 PASS (기존 테스트 회귀 없음 포함)

- [ ] **Step 2: inveni 보고서 재생성** — 선행 플랜에서 확인된 정확한 커맨드:

```bash
uv run dart-footing workpaper-corpus out/corpus/manifest_2026-06-06-inveni-one.json out/corpus/run_2026-06-06-inveni-one --tolerance 1
```
산출: `out/corpus/run_2026-06-06-inveni-one/reports/inveni_2024.html`.

- [ ] **Step 3: 패널 채움 정량 확인**

```bash
f=out/corpus/run_2026-06-06-inveni-one/reports/inveni_2024.html
echo "fs/cf preview: $(grep -c '재무제표 원문 근거' $f) (기준선 13, 증가 기대)"
echo "other-note preview: $(grep -c '다른 주석 원문 근거' $f) (기준선 0, ≥1 기대)"
echo "empty panels: $(grep -c '연결된 자동 검증 결과가 없습니다' $f) (기준선 523, 감소 기대)"
```
Expected: "재무제표 원문 근거" 증가, "다른 주석 원문 근거" ≥1, 빈 패널 감소.

- [ ] **Step 4: false-matched 회귀 가드 (P1 — 감사 무결성)** — 새 check 배선으로 corpus false-matched율이 악화되지 않았는지 확인. repo의 `false_matched_review.md` 산출 경로(workpaper-corpus가 생성)를 기준선과 대조.

```bash
# 재생성 run 디렉토리의 false_matched_review.md에서 fs_note_match/cfs_note_match의 거짓일치 건수 확인
d=out/corpus/run_2026-06-06-inveni-one
grep -c 'fs_note_match\|cfs_note_match' $d/false_matched_review.md 2>/dev/null || echo "0 (파일 없으면 false-matched 없음)"
```
판정: fs_note/cfs_note의 false-matched가 **0이거나, 0이 아니면 각 건을 Task 2 Step 8 분류로 설명 가능**해야 통과. 설명 불가한 거짓일치가 1건이라도 있으면 **블로커** — Task 2 라벨 규칙으로 회귀시켜 수정. (값-근접을 안 쓰므로 원칙상 0이어야 함.)

- [ ] **Step 5: 시각 확인** — playwright로 매출채권/유형자산 주석 탭 스크린샷, 5개 대사 패널 중 최소 BS/PL이 채워졌는지 육안 확인(데스크탑+모바일 폭에서 overlap·표 가독성).

- [ ] **Step 6: Harness verify** — `./Harness/verify.sh` 통과(있으면). `Harness/progress.md`·`session-handoff.md` 갱신.

- [ ] **Step 7: 최종 Commit**

```bash
git add -A
git commit -m "chore: regenerate inveni report with populated note-tab verification panels"
```

---

## Self-Review (작성자 체크)

- **Spec 커버리지:** 합계검증(기존 total_check, Task 6에서 패널 노출) ✓ / 전기대사(Task 4) ✓ / BS·IS·SCE·CF↔주석 대사(Task 1 배선 + Task 2·3 품질) ✓ / 주석↔주석(Task 5) ✓ / 보고서 순서 BS→IS→SCE→CF→주석(Task 6, 기존 CANONICAL_STATEMENT_ORDER) ✓ / 탭 내 직접 비교(Task 6·7) ✓.
- **Placeholder:** 알고리즘 의존부(taxonomy current-period, roll-forward 라벨, note-note 규칙)는 "read first" 파일 명시 + 실패 테스트로 행동 고정. 최종 라인은 Codex가 내부 읽고 채움 — 단위/통합 테스트가 스펙 역할.
- **감사 무결성(P0):** Task 2·3은 의미기반 선택만 사용, 값 근접 금지. Task 2 Step 4의 "정직한 gap 유지" 회귀 테스트가 거짓일치 방지 가드. Task 8 Step 4가 corpus 레벨 false-matched 가드.
- **타입 일관성:** check_type — `fs_note_match`(기존), `cfs_note_match`(기존), `prior_column_fs_note`·`prior_column_rollforward`(신규 Task 4). 공유 `assemble_report_checks(report, prior_report, *, tolerance)` 시그니처를 corpus·cli 위임부와 일치시킴. `check_fs_note_matches`에 `period` 파라미터를 추가(Task 4 PC1 재사용)할 경우 기존 호출부·테스트 동시 갱신.
- **회귀:** 기존 `test_checks_fs_note.py` 단일-hit 테스트 2개는 의미기반 선택이 단일 hit이면 그 hit을 그대로 쓰므로 보존. Task 1 동치 테스트가 DRY 통합의 안전망. KPI·false-matched 분포 변동은 Task 8에서 기준선과 대조.

## 진행 상태 (2026-06-07)

- [x] **Task 1** 완료 (커밋 `3f99517`) — 공유 `assemble_report_checks()` + fs/cfs 배선 + 죽은 `_run_total_checks` 제거. 동치 테스트(정규화 tuple) 통과 = 두 runner 통합 전 완전 동일.
- [x] **Task 2** 완료 (커밋 `4fa82ce`) — `_select_note_hit_by_label` 의미기반(값-독립). P0 거짓일치 방지 가드 테스트 통과.
- [x] **Task 3** 완료 (커밋 `6688d32`) — `_select_note_hit_by_keyword` 정확도 랭킹(값-독립).
- [x] **Task 6** 완료 (커밋 `1445e5f`) — cfs_note_match·prior_column_* 그룹 등록(silent drop 해소) + 합계검증·전기대사 패널 추가. **inveni 재생성 검증: "재무제표 원문 근거" 13→30, 빈 패널 523→501, fs/cfs 거짓일치 0.** 주석 탭에서 BS·CF·footing 대사가 실제로 표시됨(스크린샷 확인).
- [x] **Task 4** 완료 (커밋 `22f5370`) — `checks_prior_column.py` 자체 추출기. **PC1(prior_column_fs_note)은 inveni에서 0건 — Option B: inveni 주석 표가 단일기간(period가 heading 분리, 컬럼 아님)이라 정당한 0. 값-스왑 강요 거부(P0).** PC2 rollforward 1건(무형자산 기초↔전기말).
- [x] **Task 5** 완료 (커밋 `4c008df`) — note↔note 감가상각비 규칙. "다른 주석 원문 근거" 0→4.
- [x] **Task 7** 완료 (커밋 `c588ab8`) — 긴 주석 원문 `<details>` 접이식.
- [x] **UX 폴리시** 완료 (커밋 `9ecdb41`) — 빈 대사 축을 "자동 대사 없음:" 한 줄로 압축. **"검증 결과가 없습니다" 501→351**, 주석당 빈 박스 6개 제거.

## 최종 결과 (2026-06-07)
- 커밋 13개. 전체 테스트 **681 passed, 0 fail.** 신규 check 거짓일치 **0** (corpus `false_matched_review.md` 검증).
- inveni 보고서: 주석 탭에서 BS·CF·합계검증 대사가 실제 표시(스크린샷 확인). "재무제표 원문 근거" 13→30.
- **알려진 한계(정직 기록):** ① PC1 전기 FS↔주석은 단일기간 주석에서 0(heading 기반 전기 주석 추출은 후속 enhancement 후보). ② fs_note residual 2건(lease_liabilities·dividends 매칭오류) — 거짓일치 아닌 정직한 gap. ③ "다른 주석 대사"는 대표 규칙만(전수 아님).

## 검증 로그

- **Task 2 inveni `fs_note_match` 분포:** `Counter({'unexplained_gap': 6, 'matched': 3})` (기준선 2/7 → 3/6). 정직 분류:
  - `revenue:18` — **실제 차이** (매출 라벨 간 18,000 차이, 정당한 gap)
  - `property_plant_equipment:10` — parse 이슈 (연결 PPE인데 별도 기초행 선택)
  - `income_tax_expense_benefit:23` — parse 이슈 (계층 손실; 정확 금액이 타 행에 있으나 **값-스왑 거부 = P0 준수**)
  - `cash_and_cash_equivalents_increase:4-4` — parse 이슈 (주석 아래 CF 섹션에 매칭)
  - `lease_liabilities:30` — **매칭 오류 residual** (리스부채 대신 `기말 사용권자산` 선택 → 후속 라벨 규칙 보정 대상)
  - `dividends:24` — **매칭 오류 residual** (배당 부호/집계 의미 미반영 → 후속 보정 대상)
- **전체 테스트:** `668 passed` (Task 1~3 후, +4 신규, 0 fail).
- **알려진 residual (후속):** lease_liabilities·dividends 매칭 오류 2건 — 거짓일치 아니라 정직한 gap으로 표시됨(P0 안전). Task 5/후속 라벨 보정에서 처리.
