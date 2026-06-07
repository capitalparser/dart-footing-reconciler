# ADR-0004: 주석 탭 내 검증 표면화 + 전기대사 = 동일 파일 전기 컬럼

- Status: Accepted
- Date: 2026-06-07
- Deciders: 사용자(김경준), Claude(plan), Codex(impl 예정)
- Related: ADR-0003(signature-driven verification), CONTEXT.md(Reconciliation Axis 6종)

## 맥락

보고서는 `재무상태표 → 손익계산서 → 자본변동표 → 현금흐름표 → 주석` 순서와,
주석 번호별 탭(`note-workspace`) + 각 탭 내 5개 대사 패널(BS/IS/SCE/CF/다른 주석)
레이아웃을 이미 갖추고 있다([report_html.py](../../src/dart_footing_reconciler/report_html.py) `_note_comparison_panels`).

그러나 실제 산출물(`out/corpus/run_2026-06-06-inveni-one/reports/inveni_2024.html`)에서
대사 패널 대부분이 "연결된 자동 검증 결과가 없습니다"로 비어 있다.

### 근본 원인 (진단 2026-06-07)

1. **`check_fs_note_matches`(note↔BS/PL = `fs_note_match`)와 `check_cfs_note_matches`(note↔CF = `cfs_note_match`)가
   구현·단위테스트까지 통과하지만 어떤 runner에서도 호출되지 않는 dead code.**
   호출처는 자기 정의 파일뿐. `corpus._run_checks`, `cli._run_workpaper_checks` 모두 미호출.
2. 그 결과 inveni 790개 check 중 cross-statement 대사는 사실상 footing(`total_check` 681)·
   formula(94)에 집중되고, note↔BS/PL은 0, note↔CF는 우연한 4건, note↔note 1건뿐.
3. 재무제표 leadsheet의 주석 연결 232건은 `CheckResult`가 아니라 render-time label-match라
   탭 패널 라우팅(`_note_related_checks`)에 들어가지 않는다.
4. 전기대사는 별도 prior HTML 파일이 제공될 때만 수행(`check_prior_year_reconciliation`),
   미제공 시 skip → 동일 파일 내 전기 컬럼은 대사하지 않음.

검증: 미연결 함수를 즉석 호출 시 `fs_note_match` 9건(matched 2/gap 7), `cfs_note_match` 3건 생성됨.
즉 **배선만 하면 패널이 실제로 채워짐.** 단 fs_note의 높은 gap률은 기간 컬럼 정렬 미흡(naive `[0]` hit) 탓.

## 결정

### D1. 검증을 CheckResult로 통일하고 탭 패널로 라우팅
note↔BS/PL/CF/note 대사를 모두 `CheckResult`(note_no + statement evidence source 보유)로 생성해
기존 `_note_comparison_panels` 라우팅(note_no 매칭 + `statement_kind_from_source`)으로 자동 표면화한다.
별도 label-match 경로를 패널의 1차 소스로 쓰지 않는다.

### D2. 전기대사 = **동일 파일 전기 컬럼** (cross-filing 아님)
공시 1개 파일 안의 전기/당기 2개 컬럼을 사용해 전기 정합성을 검증한다.
- (a) 전기 재무제표 금액 ↔ 전기 주석 금액 (fs_note 대사의 전기 컬럼 버전)
- (b) 증감표(roll-forward) 주석의 기초잔액 ↔ 전기말 재무상태표 잔액

**대안(기각): 별도 전기 공시 파일 cross-filing.** 더 엄밀하나 입력 파일 2개를 요구해
단일 공시 검토 UX를 깨고, 전기 공시 fetch/정렬 비용이 큼. 향후 prior 파일이 제공되면
기존 `check_prior_year_reconciliation` 경로로 보강하는 옵션은 열어 둔다(추가 작업, 본 결정과 비배타).

### D4. 매칭은 의미기반, 거짓 일치 제조 금지 (감사 무결성)
note↔FS/CF 매칭에서 **값 근접(closest-amount) 선택을 금지**한다. 라벨 의미(합계/기말잔액/rule 키워드)로만 대응 행을 고르고, 의미상 대응 행의 값이 다르면 **정직하게 `unexplained_gap`** 으로 둔다.

**근거:** 값 근접 매칭은 재무제표 금액에 우연히 같은 다른 주석 행을 끌어다 "일치"로 만들어 실제 차이를 은폐한다. 감사에서 놓친 차이(false matched)는 정직한 gap보다 위험하다. repo가 `false_matched_review.md`를 별도 추적하는 이유와 정합. plan Task 2 Step 4(정직한 gap 회귀 테스트) + Task 8 Step 4(corpus false-matched 가드)로 강제.

**대안(기각): matched 수 극대화 위한 값 근접 매칭.** 표면 지표는 좋아지나 감사 신뢰를 깨므로 기각.

**기존 코드 가드레일(Codex 도전 2026-06-07):** `taxonomy.py:816` generic note 경로에는 이미 값 근접 수용 로직이 있다. 현재 `FS_NOTE_ACCOUNT_KEYS`는 canonical 키라 fs-note 매칭엔 안 물리지만, **fs-note 매칭을 generic FSC amount로 확장하면 D4가 깨진다** — 확장 시 그 값 기반 수용을 반드시 제거/우회할 것.

### D3. 주석 원문 표면 재구성
주석 탭 상단의 거대한 텍스트 덤프를 **관련 표 우선 + 전체 원문은 접이식(`<details>`)** 으로 바꿔
탭 안에서 "원문 → 대사" 흐름이 읽히게 한다(html-report-kit/interactive-patterns-kit 네이티브 `<details>` 사용).

## 결과

- 변경 파일: `checks_fs_note.py`, `checks_cfs_note.py`(품질), `corpus.py`·`cli.py`(배선),
  신규 `checks_prior_column.py`(전기대사), `checks_note_note.py`(강화), `report_html.py`(원문 재구성·순서).
- 검증 축(CONTEXT.md): `note_to_bs`, `note_to_pl`, `note_to_sce`, `note_to_cf`, `note_to_note`가
  실제 산출물에 채워짐. `전기대사`는 동일 파일 전기 컬럼 정의로 신설.
- 회귀 위험: footing 위주이던 KPI 분모/분자가 cross-statement 대사 추가로 변동.
  inveni 기준 전/후 check 수·status 분포를 plan 검증 단계에서 비교한다.
