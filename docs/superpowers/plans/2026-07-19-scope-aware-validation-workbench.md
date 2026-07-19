# 범위 전환형 검증 워크벤치 구현 계획

**Goal:** 한 검증보고서에서 연결·별도 범위를 완전히 분리해 전환하고, 재무제표 행 드로워,
합계 목표 셀 테두리, 양방향 표 사이 대사와 현금흐름표 검증을 명확하게 표시한다.

**Architecture:** Python 검증 엔진과 `CheckResult`를 원천으로 유지한다. `report_frame.py`는
검증의 범위와 모든 원문 anchor를 정규화하고, `report_html.py`는 범위별 DOM과 단일 화면
상태를 렌더링한다. 현금흐름표 내부 산술과 주석 대사는 서로 다른 검사 계층으로 유지한다.

**Tech Stack:** Python 3.11+, pytest, HTML/CSS, vanilla JavaScript, Vitest, Playwright

## 전역 제약

- 실패 테스트를 먼저 추가하고 실패 원인을 확인한 다음 최소 구현으로 통과시킨다.
- git 명령을 실행하지 않는다.
- React, Next.js와 새 프론트엔드 런타임을 추가하지 않는다.
- 모바일 UI를 구현하지 않는다.
- 기존 결과의 ID, 상태, 금액, 차이, 순서를 렌더링 변경으로 바꾸지 않는다.

## Task 1: 범위별 화면 모델과 전환

**Files:**
- Modify: `src/dart_footing_reconciler/report_html.py`
- Test: `tests/test_report_html_new.py`

1. 연결·별도 혼합 fixture에서 좌상단 선택기, 범위별 탐색·패널·드로워 속성, 범위별
   상단 건수를 요구하는 실패 테스트를 추가한다.
2. 단일 범위 보고서에서는 선택기가 숨겨지는 실패 테스트를 추가한다.
3. 결과 범위를 `consolidation_basis`와 evidence 섹션으로 결정하는 helper를 구현한다.
4. 헤더, 탐색 항목, 원문 패널, 드로워에 동일한 범위 속성을 렌더링한다.
5. JavaScript에서 범위 전환 시 네 영역을 함께 갱신하고 열린 드로워를 닫는다.
6. 새 테스트와 기존 HTML 테스트를 통과시킨다.

## Task 2: 재무제표 계정 행 드로워 진입점

**Files:**
- Modify: `src/dart_footing_reconciler/report_html.py`
- Test: `tests/test_report_html_new.py`

1. 한 재무제표 행의 금액 셀에 대사가 연결된 fixture를 만들고 행 전체의 drawer index,
   접근성 이름, 결과 건수를 요구하는 실패 테스트를 추가한다.
2. 표 렌더러에 `section_kind` 또는 statement 여부를 전달한다.
3. 재무제표 행별 drawer index를 모아 계정명 셀과 행에 진입점을 추가한다.
4. 개별 셀 진입점 우선순위와 행 클릭·Enter·Space 동작을 JavaScript에 추가한다.
5. 주석 표에는 행 전체 진입점이 생기지 않는 회귀 테스트를 추가한다.

## Task 3: 합계·행 합계 표시 강화

**Files:**
- Modify: `src/dart_footing_reconciler/report_html.py`
- Test: `tests/test_report_html_new.py`
- Test: `tests/test_report_frame.py`

1. 마지막 열 목표 셀과 소계 목표 셀이 `cell-check`로 렌더링되는 fixture 테스트를 추가한다.
2. 목표 역할이 없는 구성 셀에는 표시가 생기지 않는 회귀 테스트를 추가한다.
3. `outline`을 스크롤 경계에서도 보이는 inset `box-shadow`로 교체한다.
4. 합계 검증 상태를 접근성 문구에 추가하고 여러 검증 건수 배지를 유지한다.

## Task 4: 양방향 대사와 섹션별 검증 요약

**Files:**
- Modify: `src/dart_footing_reconciler/report_frame.py`
- Modify: `src/dart_footing_reconciler/report_html.py`
- Test: `tests/test_report_frame.py`
- Test: `tests/test_report_html_new.py`

1. 재무제표-주석 검증의 양쪽 exact evidence와 주석-주석 검증의 두 note evidence가 같은
   drawer item을 여는 실패 테스트를 추가한다.
2. 중복 anchor를 순서 보존 방식으로 제거하고 모든 렌더링 가능한 exact anchor를 유지한다.
3. 원문 패널 상단에 검증 그룹별 건수를 표시하는 실패 테스트를 추가한다.
4. `report_frame`의 canonical group label을 사용해 패널 요약 칩을 렌더링한다.
5. 범위가 다른 anchor가 섞이면 표시하지 않는 회귀 테스트를 추가한다.

## Task 5: 현금흐름표 검증 계열 확장

**Files:**
- Modify: `src/dart_footing_reconciler/checks_cfs_note.py`
- 필요 시 Modify: `src/dart_footing_reconciler/reconciliation_targets.py`
- 필요 시 Modify: `src/dart_footing_reconciler/checks_reconciliation.py`
- Test: `tests/test_checks_cfs_note.py`
- Test: `tests/test_checks_reconciliation.py`

1. 유형·무형자산 처분, 투자부동산 취득·처분, 사채 발행·상환, 리스 원금 상환의 실패
   테스트를 추가한다.
2. 계정 계열과 movement role을 명시하는 데이터 규칙으로 정적 튜플을 교체한다.
3. exact/prefix/contains 라벨 점수와 후보 동률 기권을 구현한다.
4. 비현금 차이 설명은 정확한 금액과 허용 키워드 및 원문 근거가 있을 때만 적용한다.
5. 모든 생성 결과의 statement/note evidence가 정확한 row/col source인지 테스트한다.
6. 강한 `cashflow_reconciliation`과 중복되는 보조 검증 억제 계약을 확인한다.

## Task 6: 현금흐름표 UI 결과 표시

**Files:**
- Modify: `src/dart_footing_reconciler/report_frame.py`
- Modify: `src/dart_footing_reconciler/report_html.py`
- Test: `tests/test_report_html_new.py`

1. 현금흐름표 계정 행에 결과 상태와 drawer 진입점이 표시되는 실패 테스트를 추가한다.
2. 드로워 그룹명을 `현금흐름표-주석 대사`로 통일한다.
3. 드로워에서 기준 금액, 주석 구성 금액, 비현금 조정, 차이와 행동을 업무 문구로 표시한다.

## Task 7: 전체 검증과 SK이터닉스 QA

1. 관련 테스트 묶음을 실행한다.
2. `uv run pytest` 전체를 실행하고 외부 fixture 부재 등 환경 실패를 분리 기록한다.
3. `uv run ruff check src tests`를 실행한다.
4. Vitest와 Playwright 상호작용 테스트를 실행한다.
5. SK이터닉스 HTML을 재생성한다.
6. 1440x900과 1600x1000에서 범위 전환, 재무제표 행 클릭, 현금흐름표 행 클릭,
   3-1 금융상품 연결의 마지막 열 행 합계, 재무제표-주석·주석-주석 양방향 진입을 확인한다.
