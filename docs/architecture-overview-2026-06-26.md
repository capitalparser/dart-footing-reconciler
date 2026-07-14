# DART Footing Reconciler — 기술 아키텍처 / 검증로직 / 구현상태 상세 보고서

**작성일** 2026-06-26
**대상 상태** `main` = PR#20 머지(`1edfd78`) + 차입금/사채 슬라이스(`feat/level-aware-borrowings-bonds` `1fd69bc`, **PR#21 오픈·미머지**)
**규모** 26,167 LOC / ~45 모듈 / 891 tests(63 파일) / ADR 13개 / spec 8개 / 코퍼스 18사(비금융)

> 본 문서는 툴 자체의 구조·검증·구현 상태를 기록한 내부 기술 보고서다. 산출물(HTML 보고서/Excel 조서)이 아니라 엔진 메타-문서이며, CONTEXT.md(도메인 사전)·domain-model.md(엔티티 모델)·docs/adr/(설계 결정)을 종합한다.

## 0. 한 줄 요약 (verdict)
**감사용역 등급 footing·reconciliation 엔진. 비금융 상장사 v0.** 결정론 파이프라인 + 엔티티-키 대사 모델로 "정확성 > 커버리지 · 추측보다 abstain · false match 절대 금지"를 **코퍼스 하드 게이트 + 교차모델 리뷰**로 강제한다. 핵심 대사(BS·PL·CF·SCE↔주석, 내부 footing)는 load-bearing으로 가동 중이고, 레벨 인식(유동/비유동) 대사가 리스(머지)·차입금/사채(리뷰 대기)로 확장 중이다. 일부 "설계됐으나 부분 채택"된 레이어(signature/semantic 엔진)는 진단용으로만 떠 있다.

---

## 1. 시스템 아키텍처

### 1.1 도그마 (load-bearing 설계 원칙 — CONTEXT.md Core Domain Rules)
1. **도메인 정확성 > 기술적 우아함**
2. **추측보다 abstain** (모르면 `not_tested`, 추측 매칭 금지)
3. **감사 verdict는 false match를 절대 운반하지 않는다** (matched 오판 = 감사인이 검산 통과로 오신 → 최악)
4. **산수는 결정론 Python** (LLM 판단 배제). 라벨 매핑만 확률적이되 confidence + source evidence로 명시.

이 4개가 모든 모듈·검증·게이트의 상위 제약이다. 아래 모든 설계 결정이 여기서 파생한다.

### 1.2 파이프라인 (단방향, 4단)
```
DART DSD/HTML
  │  document.parse_full_report()         [파싱 — 구조 추출, scope 태깅]
  ▼  FullReport(sections[], scope=연결/별도)
  │  taxonomy.classify_report()           [분류 — 라벨↔계정, confidence]
  ▼  ClassifiedReport(statement_lines[], note_amounts[])
  │  check_pipeline.assemble_report_checks()
  │     └ split_report_by_scope()         [연결/별도 슬라이스 분리]
  │     └ 슬라이스마다 4개 Harness 실행
  ▼  list[CheckResult]  (status ∈ 5종)
  │  report_frame / report_html / excel / audit_workbook
  ▼  HTML 보고서 · Excel 조서 · cockpit
```
파싱·정규화·계산·보고를 **레이어로 분리**(CLAUDE.md 작성 원칙)하는 게 구조의 뼈대다. core 패키지가 MCP 없이 독립 실행된다(ADR-0001).

### 1.3 모듈 맵 (레이어별 책임)
| 레이어 | 핵심 모듈 (LOC) | 책임 |
|---|---|---|
| **파싱** | `document.py`(636), `html_tables.py`, `dart_fetch.py` | DSD/HTML → ReportSection/Table, `scope`(연결/별도) 태깅, 셀 source 보존 |
| **분류** | `taxonomy.py`(1066), `label_resolver.py`, `_match_helpers.py` | 라벨↔acode, 계정↔주석 분류, 별칭 테이블(데이터) |
| **셀 선택(SSOT 지향)** | `amount_locator.py`(943) | "이 표에서 `<계정>`의 `<역할>` 금액은 어느 셀?" — archetype별 전략. **부분 채택**(자산 net-carrying 가동; current/noncurrent_portion 역할은 stub) |
| **구조/형태 감지** | `layout_variants.py`(1841), `orientation.py`(1078), `table_semantics.py`, `formula_discovery.py`(1781), `formula_templates.py` | 표 archetype 분류, 당기/전기 열, 행/열 방향, footing 공식 발견 |
| **검증(체크 11종)** | `checks*.py` (§2.2) | 축별 산술 대사 → CheckResult |
| **오케스트레이션** | `check_pipeline.py`(122) + `*_harness.py` | scope 슬라이스 × 4 Harness 실행·평탄화 |
| **후보/입력** | `verification_candidates.py`(3856), `reconciliation_inputs.py`(2009), `reconciliation_targets.py` | 검증 후보 금액 추출, 축별 *Input 행 구성 |
| **진단 오버레이(비-게이트)** | `signatures.py`(3/17 방출), `semantic_layer.py`, `semantic_attempts.py`, `semantic_validation.py` | ADR-0003 설계였으나 **진단용으로 강등**(검증 산출 0 기여) |
| **보고** | `report_html.py`(982), `excel.py`, `audit_workbook.py`(551), `report_frame.py`, `report_order.py` | self-contained HTML, Excel 조서, cockpit |
| **코퍼스/CLI** | `corpus.py`(831), `cli.py`(767), `local_report.py` | 회귀 코퍼스 러너, CLI |

### 1.4 엔티티-키 도메인 모델 (ADR-0012, `docs/domain-model.md` — 2026-06 신설)
대사 페어링의 자의성을 없애는 4차원 키:
> **페어링 키 = (Account × Consolidation Basis × Report Period × Balance Level)**

| 차원 | 값 | 추론 출처 | 코드 |
|---|---|---|---|
| Account | taxonomy keys (차입금/사채/리스부채/무형…) | 별칭 매칭 | `account_key` |
| **Consolidation Basis**(연결기준) | consolidated/separate | TOC heading | `ReportSection.scope` |
| **Report Period** | 당기/전기 | 열 위치 | `current_period_columns` |
| **Balance Level** | 유동/비유동/합계 | 라벨 토큰 + BS 섹션 헤더 | 체크-레이어 helper |

교차-basis/period/level 페어링은 금지된다. **strangler 이행**(점진) — taxonomy+checks가 load-bearing이고, 한 계정씩 엔티티-키로 마이그레이션한다. 리스=1번째, 차입금/사채=2번째 슬라이스.

### 1.5 룰베이스 ↔ 데이터드라이븐 하이브리드 (도그마-안전 3층)
| 층 | 종류 | 예 |
|---|---|---|
| 지식의 데이터화 | 선언적 DATA(코퍼스 큐레이션) | taxonomy 별칭, layout archetype, 레벨/basis 토큰 |
| 입력 형태 적응 | 결정론 전략 선택 | 주석 공시 형태(레벨 분리/총계/열 지향)에 따라 전략 분기 |
| 룰 엔진 | 결정론 Python | footing 산술, 키 페어링, bounded 합산, tolerance 비교, abstain |

**confidence는 downgrade(matched→parse_uncertain)·gate(abstain)만 가능하고 matched를 생성할 수 없다** → 확률에서 false match가 나오지 않는다. **ML 페어링은 도그마상 배제**(코퍼스는 oracle/게이트 + 규칙 큐레이션 출처이지 학습셋이 아니다).

---

## 2. 검증 로직

### 2.1 결과 어휘 (단일 진실원천 `checks.ALL_STATUSES`, 5종)
`matched` · `explainable_gap` · `unexplained_gap` · `parse_uncertain` · `not_tested`(검증 미적용 = 커버리지, 절대 드롭 안 함). 모든 요약·KPI·JSON이 정확히 이 5개만 집계한다(ADR-0006). 6-value Outcome Label(signature 엔진용)은 통계/진단 뷰일 뿐, 런타임 어휘는 이 5개다.

### 2.2 체크 패밀리 (축별 분리 — 4개 Harness가 묶음)
| Harness | 체크 모듈 | 축 |
|---|---|---|
| `StatementCrossHarness` | `checks_statement_ties` | BS↔CF 기말현금, BS↔SCE 자본총계 (주석 무경유) |
| `NoteInternalHarness` | `checks_note_note`, `checks_totals`(557), `footing` | 주석 내부 footing(기초+증감=기말), 합계=구성요소, note↔note |
| `StatementNoteHarness` | `checks_fs_note`(1434), `checks_cfs_note`(123), `checks_prior_column` | **note↔BS**(잔액/레벨 인식), note↔CF(현금증감), note↔PL |
| `PriorReportHarness` | `checks_prior_year` | 전기 보고서 대사 |

보조: `checks_note_bridges`, `checks_note_references`, `checks_reconciliation`(1488). 축 혼합은 등록 시 거부된다(footing ≠ reconciliation 도그마). footing(표 내부 산술)과 reconciliation(표↔표/표↔재무제표)은 별개 검사다.

### 2.3 핵심 대사 — note↔BS 레벨 인식 (2026-06 집중 영역)
- **리스부채(머지, PR#20)**: 주석이 *행 라벨*(유동/비유동 리스부채)로 레벨 공시 → 행 기반. 진짜 잔액행 격리(사용권자산/채권/contra 배제) → 레벨 매칭 또는 bounded Σ(유동+비유동)↔기말총계 → 미해소 abstain. 당기-표(최저 인덱스, 레벨행 우선) 선택으로 당기·전기 별도표 처리.
- **차입금/사채(리뷰 대기, PR#21)**: 주석이 *열 헤더*(단기/장기차입금)로 레벨 공시, 금액은 합계 행 → **행×열 추출**. carrying-table allowlist(미할인/만기표 배제) + period∩level + 열-측 contra(할인발행차금/액면) 배제 + 정렬 분류기(유동성 우선) → bounded Σ. **additive-fallback**: 레벨 매치 없으면 기존 단일-페어링으로 폴백(기존 매치 보존).

### 2.4 메타-검증 (툴 자체의 품질 보증 — 이 프로젝트의 차별점)
1. **코퍼스 하드 게이트**: 로컬 18사(비금융 10+8) HTML(gitignored)을 before/after 파싱, **check-level matched+gap diff**(stash src → `assemble_report_checks` 양 manifest → `comm`). 규칙: **matched ↑/flat · false match 0 · 정타 파괴 0 · gap은 FP 제거로만↓.** `scripts/check_per_company_snapshot.py`가 회사별 status 카운트를 committed 베이스라인(2개)과 HARD 비교(상쇄 drift 차단).
2. **교차모델 리뷰 2-leg (Tier-3 필수)**: Opus(아키텍처/엣지) + Codex(코드 그라운드). 패밀리가 달라 blind spot이 상이하다. **실적**: plan 리뷰가 코드 전 BLOCKER 2~3건 포착(리스·차입금), code 리뷰가 green 게이트도 못 본 false-match 3건 포착(B-2b). 차이는 `docs/adr/{NNNN}-review-findings.md`에 기록.
3. **테스트 891개**(결정론 ×2 + ruff). 회귀 핀 = 실 코퍼스 구조를 합성 픽스처로 재현.

---

## 3. 구현 상태

### 3.1 가동(load-bearing)
- 파싱·분류·11개 체크·4 Harness·scope 슬라이싱·코퍼스 러너·CLI·HTML/Excel/cockpit 보고 — **전부 가동**.
- **Canonical Amount Locator**(ADR-0008): 자산 net-carrying 셀 선택 가동(`reconciliation_inputs` wiring, PR#14에서 +4 matched). current/noncurrent_portion 역할은 **stub(abstain)** — 레벨 인식은 현재 체크-레이어 helper가 담당.
- **엔티티-키 레벨 인식**: 리스(머지) + 차입금/사채(PR#21 오픈).

### 3.2 부분 채택 / 진단용
- **signature/semantic 엔진**(ADR-0003 설계): `signatures.py`가 17개 중 3개만 방출, `semantic_layer`는 검증 산출에 0 기여(deletion-test 확인) → **진단 오버레이로 강등**(ADR-0003 amended, ADR-0008). 실제 정확도는 taxonomy+checks 실용경로에서 나온다.

### 3.3 미구현 / 이연
- `essential_notes.py` **미구축**(grid는 taxonomy+reconciliation_inputs에 암묵 존재).
- Locator로의 레벨-역할 승격(2~3개 cell-selector가 체크-레이어에 산재 = **SSOT 침식 부채**, ADR-0012).
- 이연 계정: dividends(declared-vs-paid 모호), revenue(P&L 세그먼트), total_check(ADR-0007 force-foot 금지), 금융상품(비금융 scope edge), 사채-무주석 케이스.

### 3.4 ADR 타임라인 (설계 결정 13개)
0001 core-first · 0002 Claude HTML · 0003 signature-driven(후 amended) · 0004 note-tab surfacing · 0005 pyodide single-engine · 0006 schema/semantic 통합 · 0007 structure-aware footing · 0008 Canonical Amount Locator · 0009/0010 locator plan/code 리뷰 · **0011 FP-slice 리뷰** · **0012 엔티티-키 모델** · **0013 B-2b code 리뷰** (0011~0013 = 2026-06). 0014(차입금 code 리뷰)는 예정.

### 3.5 최근 산출 (2026-06 세션, 3 슬라이스)
| PR | 내용 | 코퍼스 효과 | 상태 |
|---|---|---|---|
| #19 | FP fix slice(pairing/parse/EPS 가드) | +11 정타, −3 거짓·공허, −22 FP gap | 머지 |
| #20 | 엔티티-키 모델 + B-2b 리스 레벨 인식 | +22 정타, 파괴 0 | 머지 |
| #21 | 차입금/사채 레벨 인식(열 지향) | +7 정타, 파괴 0, false 0 | **오픈·code리뷰 대기** |

---

## 4. 알려진 한계 · 리스크 레지스터
| 항목 | 성격 | 도그마 영향 |
|---|---|---|
| **차입금 PR#21 정식 code 리뷰 미실행** | 머지 전 필수 | 열 추출 false-match 표면 미검증(plan은 BLOCKER 3건 지적) — **머지 전 리뷰 권장** |
| 공시 이질성 → 낮은 커버리지 | 차입금 6사 중 2사만 매치 | 정상(패턴 없으면 abstain) |
| Locator SSOT 침식 | 체크-레이어에 cell-selector 2~3개 | 부채(정확도 영향 0), 승격 이연 |
| dispatch-fallback 단위 핀 부재 | 차입금 폴백 | corpus-verified지만 단위 미핀 |
| 대한항공 리스 잔여 gap | 표선택 휴리스틱 | gap(안전), false match 아님 |
| Codex 런타임 불안정 | 세션 내 interim 잦음 | 검증 인계 시 작업트리 확인 필요 |

---

## 5. 로드맵 (다음 레버, HANDOFF 기록)
1. **차입금 PR#21 정식 cross-model code 리뷰** → ADR-0014 → 머지 (1순위)
2. dispatch-fallback 단위 핀
3. Locator 레벨-역할 승격(SSOT 회복)
4. 대한항공 리스 표선택 정교화
5. 코퍼스 Gold Set(20~30사) 확장

---
_본 보고서는 2026-06-26 시점 스냅샷이다. 권위 있는 최신 상태는 HANDOFF.md·CONTEXT.md·docs/adr/·docs/domain-model.md를 따른다._
