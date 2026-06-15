# Audit Reconciliation Report Design Draft

## Verdict

Conditional: HTML/PDF 산출물은 `감사 대사 결과 보고서`로 설계한다. 기본 화면은 JSON이나 내부 필드명을 보여주는 개발자 리포트가 아니라, 감사인이 바로 판단할 수 있는 결론형 조서 뷰여야 한다.

## Design Principles

- 한국어 우선: 화면의 제목, 상태, 버튼, 표 머리글은 모두 한국어로 표시한다.
- 구현 용어 비노출: `JSON`, `schema`, `payload`, `check_type`, `account_key`, `assertion_type` 같은 내부 표현은 기본 화면에 노출하지 않는다.
- 근거 추적 가능: 원천 위치, 주석 번호, 표/행/열 위치는 숨기지 않되 `근거 위치`, `원천 표`, `대사 기준` 같은 사람용 라벨로 표시한다.
- 결론 우선: 첫 화면에서 회사, 보고기간, 전체 결론, 미해소 차이 수, 자동 대사 범위가 보여야 한다.
- PDF 친화: HTML은 그대로 인쇄하거나 PDF로 저장해도 표 머리글, 상태 색상, 페이지 나눔이 깨지지 않아야 한다.

## First Viewport

첫 화면은 다음 순서로 구성한다.

1. 보고서 헤더
   - 제목: `감사 대사 결과 보고서`
   - 보조 정보: 회사명, 보고기간, 공시 원천, 생성일시
   - 전체 결론 배지: `일치`, `추가 확인 필요`, `미해소 차이`

2. 핵심 지표
   - `전체 대사 항목`: 자동 수행된 공식 계정/현금흐름/전기 대사 수
   - `일치`: 차이 허용범위 내 항목 수
   - `미해소 차이`: 조서 검토가 필요한 항목 수
   - `검증 제외`: 필요한 원천 자료가 없어 수행하지 않은 항목 수

3. 다음 행동
   - 미해소 차이가 있으면: `미해소 차이 검토`
   - 검증 제외가 있으면: `누락 원천 확인`
   - 모두 일치하면: `조서 근거 확인`

## Navigation

데스크톱 HTML은 좌측 고정 내비게이션을 둔다.

- `요약`
- `재무제표-주석 공식 계정 대사`
- `현금흐름표-주석 현금 변동 대사`
- `전기말-당기초 대사`
- `보조 검증`
- `검증 제외 및 한계`
- `원천 근거`

모바일과 PDF는 같은 순서를 단일 컬럼으로 출력한다.

## Section Model

### 1. Summary

목적: 전체 결론과 위험 신호를 한 화면에서 판단하게 한다.

표시 항목:

- 전체 결론
- 미해소 차이 상위 5개
- 자동 대사 수행 범위
- 수행하지 않은 대사와 이유

표현 예시:

| 항목 | 결과 | 의미 | 필요 조치 |
| --- | --- | --- | --- |
| 유형자산 기말금액 | 일치 | 재무상태표 금액과 주석 기말 장부금액이 일치함 | 조서 근거로 첨부 가능 |
| 유형자산 취득 현금 | 미해소 차이 | 현금흐름표 취득액과 주석 취득 변동금액이 다름 | 미지급 취득, 리스 취득, 대체 여부 확인 |

### 2. Primary Balance Reconciliation

사용자-facing 제목: `재무제표-주석 공식 계정 대사`

용어 설명:

> 공식 계정 대사: 재무상태표 또는 손익계산서의 계정 금액이 관련 주석의 기말금액 또는 표시금액과 맞는지 확인하는 절차입니다. 이 대사가 맞아야 주석 금액이 재무제표 본문을 제대로 뒷받침한다고 볼 수 있습니다.

표 컬럼:

- `공식 계정`
- `재무제표 금액`
- `주석 금액`
- `차이`
- `결과`
- `근거 위치`
- `필요 조치`

내부 값 매핑:

- `primary_balance_reconciliation` -> `재무제표-주석 공식 계정 대사`
- `matched` -> `일치`
- `unexplained_gap` -> `미해소 차이`
- `not_tested` -> `검증 제외`

### 3. Cash Flow Reconciliation

사용자-facing 제목: `현금흐름표-주석 현금 변동 대사`

용어 설명:

> 현금 변동 대사: 현금흐름표의 취득, 처분, 차입, 상환 금액이 주석의 현금성 변동 내역과 맞는지 확인하는 절차입니다. 단순 증감표 합계가 아니라 현금흐름표 금액을 설명할 수 있는 주석 근거가 있는지가 핵심입니다.

표 컬럼:

- `대상 거래`
- `현금흐름표 금액`
- `주석 변동금액`
- `차이`
- `결과`
- `검토 포인트`
- `근거 위치`

검토 포인트 예시:

- 유형자산 취득 차이: `미지급 취득, 리스 취득, 사업결합, 계정 대체 여부 확인`
- 유형자산 처분 차이: `처분 장부금액과 처분대가를 혼동했는지 확인`
- 차입금 상환 차이: `유동/비유동 대체 또는 환율효과가 포함되었는지 확인`

부호 표시 원칙:

- 기본 표의 비교 금액은 현금흐름표와 주석의 `금액 크기`를 비교한다.
- 원천 표시 부호는 `근거 위치` 또는 상세 펼침 영역에서 보존한다.
- 예: 현금흐름표 `(300)`과 주석 `300`은 기본 결과에서 `일치`로 표시하고, 상세에는 원문 부호를 보여준다.

### 4. Prior Ending To Current Beginning

사용자-facing 제목: `전기말-당기초 대사`

용어 설명:

> 전기말-당기초 대사: 전기 주석의 기말 장부금액이 당기 주석의 기초 장부금액으로 이어지는지 확인하는 절차입니다. 이 대사가 맞지 않으면 전기 재작성, 표시 구조 변경, 파싱 오류 가능성을 먼저 확인해야 합니다.

표 컬럼:

- `주석`
- `전기 기말금액`
- `당기 기초금액`
- `차이`
- `결과`
- `근거 위치`
- `필요 조치`

행 선택 원칙:

- 인정: `기초`, `기초장부금액`, `기초금액`, `기초잔액`, `당기초`
- 인정: `기말`, `기말장부금액`, `기말금액`, `기말잔액`, `전기말`, `장부금액`, `순장부금액`, `장부가액`
- 제외: `기초취득원가`, `기초감가상각누계액`, `기말상각누계액`처럼 상세 구성요소인 행

### 5. Supporting Checks

사용자-facing 제목: `보조 검증`

보조 검증은 결론의 중심이 아니라 근거 품질 확인으로 표시한다.

- `합계 검증`: 행/열 합계가 표시 합계와 맞는지 확인
- `증감표 산술 검증`: 기초 + 변동 = 기말 산술 구조 확인
- `전기 공시 금액 대사`: 당기 비교표시 전기금액과 전기 공시 당기금액 비교

이 섹션에서는 `보조 검증` 배지를 붙여 primary 대사와 구분한다.

## Gap Classification

각 미해소 또는 검증 제외 항목은 다음 중 하나로 분류한다.

- `필수 확인`: 결론에 직접 영향을 줄 수 있어 조서 검토 전 해소 필요
- `권장 확인`: 금액은 일치하나 표시 또는 근거 위치 확인 필요
- `모니터링`: 자동화 정확도 개선을 위해 추적할 항목
- `추정 금지`: 원천 근거가 부족해 자동 결론을 내리지 않는 항목

## HTML Layout Draft

```html
<body>
  <div class="report-shell">
    <aside class="report-sidebar">
      <div class="brand">감사 대사</div>
      <nav>
        <a href="#summary">요약</a>
        <a href="#balance">공식 계정 대사</a>
        <a href="#cashflow">현금 변동 대사</a>
        <a href="#prior">전기말-당기초</a>
        <a href="#supporting">보조 검증</a>
        <a href="#gaps">검증 제외 및 한계</a>
      </nav>
    </aside>
    <main class="report-main">
      <header class="report-header" id="summary">
        <p class="eyebrow">DART 공시 기반 감사 대사</p>
        <h1>감사 대사 결과 보고서</h1>
        <p class="context">회사명 · 보고기간 · 공시 원천 · 생성일시</p>
        <span class="status status-warning">추가 확인 필요</span>
      </header>

      <section class="kpi-strip" aria-label="핵심 지표">
        <article><span>전체 대사 항목</span><strong>24</strong></article>
        <article><span>일치</span><strong>19</strong></article>
        <article><span>미해소 차이</span><strong>3</strong></article>
        <article><span>검증 제외</span><strong>2</strong></article>
      </section>

      <section class="report-section" id="balance">
        <h2>재무제표-주석 공식 계정 대사</h2>
        <p class="term-note"><strong>공식 계정 대사</strong>: 재무제표 본문 계정과 관련 주석 금액이 서로 뒷받침되는지 확인합니다.</p>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>공식 계정</th>
                <th>재무제표 금액</th>
                <th>주석 금액</th>
                <th>차이</th>
                <th>결과</th>
                <th>필요 조치</th>
              </tr>
            </thead>
            <tbody></tbody>
          </table>
        </div>
      </section>
    </main>
  </div>
</body>
```

## PDF Rules

- A4 portrait 기본, wide evidence table은 landscape page break 허용.
- 첫 페이지에는 요약과 KPI를 반드시 포함한다.
- 각 primary section은 새 페이지에서 시작할 수 있게 `break-before: page`를 적용한다.
- 표 머리글은 페이지가 넘어가도 반복되게 `thead { display: table-header-group; }`를 적용한다.
- 상태 색상은 흑백 출력에서도 구분되도록 텍스트 라벨을 반드시 함께 표시한다.
- 상세 원천 근거는 기본 PDF에는 요약 경로만 표시하고, 전체 원천 위치는 부록 섹션에 모은다.

## Data Presentation Mapping

내부 데이터는 다음 사람용 라벨로 변환한다.

| 내부 의미 | 화면 라벨 |
| --- | --- |
| `check_id` | 대사 항목 |
| `check_type` | 대사 유형 |
| `status` | 결과 |
| `expected` | 기준 금액 |
| `actual` | 확인 금액 |
| `difference` | 차이 |
| `tolerance` | 허용 차이 |
| `evidence` | 근거 위치 |
| `reason` | 판단 근거 |

기본 화면에서는 내부 이름을 표시하지 않는다. 필요한 경우에만 `기술 세부정보` 접힘 영역에서 원문 데이터를 제공한다.

## Implementation Draft

1. `report_html.py` 추가
   - `render_audit_reconciliation_html(report, checks, output)`
   - self-contained HTML 생성
   - CSS token 내장

2. CLI 추가
   - `workpaper-html CURRENT_HTML OUTPUT.html --company ... --prior-html ...`
   - 기존 `workpaper-excel`과 같은 체크 파이프라인 사용

3. PDF 경로
   - 1차: HTML을 브라우저/Playwright로 PDF 출력
   - 2차: CLI 옵션 `--pdf OUTPUT.pdf` 추가

4. 테스트
   - HTML에 새 라벨 3종이 표시되는지 확인
   - HTML 기본 화면에 `JSON`, `payload`, `check_type`, `account_key`가 노출되지 않는지 확인
   - PDF용 print stylesheet가 포함되는지 확인

## Open Decisions

- legacy 직접 대사 결과를 HTML 기본 화면에 같이 표시할지, `보조 검증`으로 내릴지 결정 필요.
- 검증 제외 항목을 실제 `not_tested` 결과로 생성할지, 현재처럼 입력이 없으면 생략할지 결정 필요.
- PDF 생성 엔진을 Playwright 기반으로 둘지, HTML만 생성하고 사용자가 브라우저 인쇄를 하게 할지 결정 필요.
