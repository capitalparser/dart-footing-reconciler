# Codex Work Order — Reconciliation Logic Advancement (2026-05-31)

> **Author (Claude / planning):** session 2026-05-31
> **Executor:** Codex (code 구현·수정·테스트 lane)
> **Input docs:** `docs/validation/2026-05-31-ab-difference-triage.md`, `HANDOFF.md`, `CONTEXT.md`
> **Baseline corpus:** `out/corpus/run_2026-05-27-hundred-accuracy-v1` (primary 575 / matched 460 = 80.0% / unresolved 115)

---

## 0. 사용자 작업계획서 vs 실제 레포 — 방향 검증 결과 (READ FIRST)

별도로 전달된 "Dart Footing 작업계획서"(Slice 1~6, OpenDART JSON 기반 greenfield)는
**현 레포와 아키텍처가 충돌하므로 그대로 구현하지 말 것.** 실제 레포는 이미 다른(더 적합한)
경로로 Slice 5 수준까지 완성돼 있음.

| 계획서 Slice | 판정 | 근거 |
|---|---|---|
| 1. OpenDART JSON API (`fnlttSinglAcntAll.json`) | **채택 금지** | `dart_fetch.py`는 DSD/HTML 뷰어 파싱. JSON API엔 **주석(note) 없음** → 주석↔재무제표·현금흐름 대사 불가. 채택 시 회귀 |
| 2. 파싱 → AccountItem | 이미 완료 | `document.py`/`scope.py`/`taxonomy.py`/`amounts.py` (주석 포함). 계획서 schema는 다운그레이드 |
| 3. vertical/horizontal/cross footing | 완료+ / 일부 갭 | `checks_totals`/`checks_prior_year`/`checks_fs_note`/`checks_reconciliation`/`note_assertions` 존재. cross-statement(BS현금↔CF, BS자본↔SCE) tie만 갭 |
| 4. 오류 분류 + **materiality** | **진짜 갭** | status/taxonomy는 있으나 감사 중요성 기준 부재 |
| 5. 출력(감사 조서) | 완료 | HTML 검산조서 + Excel + corpus.md (CSV/비교만 소폭 갭) |
| 6. 배치 & CLI | 완료 | `cli.py`(typer) + `corpus.py` |

**계획서 Open Questions 처리**: Q1(JSON vs XBRL) = DSD/HTML로 이미 결정됨. Q2(표준코드) = `taxonomy.py`.
Q5(금융사 별도 파서) = 실제 갭(한화손해보험·삼성생명·SK리츠 등 primary 0건). 나머지는 본 work order 범위 밖.

---

## 공통 작업 계약 (모든 task 공통, 위반 금지)

프로젝트 보수 규칙 (`HANDOFF.md` Constraints + `CONTEXT.md`):

1. **RED/GREEN TDD**: 각 변경은 실패 테스트 먼저 → 최소 구현 → green.
2. **100사 corpus 재생성 검증**: 변경 후 `workpaper-corpus`로 100사 재생성하고 다음을 보고:
   `primary checks / matched / unresolved / no-difference rate / judgment rate / newly-unresolved primary IDs`.
3. **`0 newly unresolved primary check IDs`** 가 머지 기준. 새 미해소를 만들면 그 슬라이스는 reject.
4. **No false matched**: 재현 가능한 원천 금액 + 산술 + 명시적 tolerance 근거 없이는 matched 금지.
   보수적 unresolved가 false matched보다 낫다.
5. **tolerance=0 은 exact-only 유지**. 잔차 허용은 source-precision 누적 또는 명시적 bounded rule로만.
6. 매 슬라이스 완료 시 `HANDOFF.md`에 implementation slice 노트 1건 추가(기존 포맷 따름).
7. 모든 material amount는 source location 보존.

---

## STREAM 1 (PRIMARY) — Type B reconciliation 로직 (triage 33건)

목표: triage Type B 패턴을 산식으로 반영해 unresolved 115 → 감소, no-difference rate 80% → 상향.
각 패턴은 triage 문서의 회사/금액으로 검증.

### T1. 처분 cash-flow bridge 일반화 (가장 다빈도)
- **패턴**: `처분 장부금액 − 처분손익(− 감가상각누계 등) = CFS 처분대가`.
- **대상**: 현대건설·현대모비스·지누스·한화시스템·더존비즈온·GS리테일 PPE/무형 처분.
- **주의**: 현대모비스 PPE처분 차이 77.7B는 처분 장부금액에 **ROU/리스 처분(비현금)** 포함 의심 → 비현금 처분 제외 후 대사. 단일 gain 차감만으로 안 닫히는 케이스는 multi-component.
- **수용**: 위 회사 중 최소 4건 matched, 0 newly unresolved.

### T2. CFS 합산 라인 분해
- **패턴**: CFS `유형자산 및 사용권자산의 취득`처럼 PPE+ROU **합산 표시** → 주석 PPE취득 + ROU취득(증감표 추가) = CFS.
- **대상**: 롯데하이마트 PPE취득(−1,761M).
- **수용**: 롯데하이마트 PPE취득 matched, 합산 라벨 패턴 일반화, 0 newly unresolved.

### T3. 취득 미지급/건설중 bridge (주석 취득 > CFS)
- **패턴**: 주석 취득 − 미지급 취득 증가(+ 건설중자산 등) = CFS 취득.
- **대상**: 현대차(350B)·해성디에스(17.3B)·더존(1.19B)·GS리테일(8.4B)·세아제강(5.65B).
- **주의**: HANDOFF에 기존 미지급 sign-flip 회귀 이력(v78) 있음 — 전역 sign flip 금지, 케이스별 방향 선택.
- **수용**: 최소 3건 matched, 0 newly unresolved.

### T4. financing 구성요소 완전성 + 분류 swap
- **패턴 A (분류 swap)**: 풍산 차입 +100,000,407,199 / 사채 −100,000,676,800 거의 상쇄 →
  유동성장기차입 ↔ 사채 분류 오배정. CFS row 분류 규칙 점검.
- **패턴 B (component 누락)**: 현대건설·해성디에스 차입 — 주석 재무활동현금흐름이 일부 component만 공시.
  주석이 **net만** 공시하면 reconcile 불가 → A(실질 차이)로 유지.
- **수용**: 풍산 차입·사채 동시 matched, 0 newly unresolved.

### T5. balance wrong-row 매칭 방어 (결함 수정)
- **패턴**: 롯데하이마트 무형 balance 차이 **572.9B (계정 규모 초과)** = 명백한 wrong-row 매칭.
- **규칙**: 매칭 후보의 차이가 재무제표 본문 금액(또는 자산총계 합리 상한)을 초과하면 매칭 거부 →
  `parse_uncertain` 강등 (false 결과 제거). false matched 방지 차원에서도 필요.
- **수용**: 롯데하이마트 무형 balance가 garbage 결과에서 제거(matched 아님, parse_uncertain), 0 newly unresolved.

### T6. balance 영업권/정부보조금 조정
- **패턴**: 무형 balance에 영업권 포함/제외(현대건설 334B), PPE balance 정부보조금/리스(풍산 −7.83B).
- **참고**: HANDOFF v53(영업권 제외 후보 추가) 패턴 재사용.
- **수용**: 해당 케이스 matched 또는 정당한 parse_uncertain, 0 newly unresolved.

### Type A (구현 대상 아님 — 유지)
- 현대차 무형처분(주석 roll-forward 처분=0), GS리테일 PPE처분(처분=대규모 재분류 의심).
- **실질 차이 확인 필요**로 유지. 억지 산식으로 matched 만들지 말 것.

---

## STREAM 2 — 작업계획서에서 채택할 진짜 신규 항목

### S2-1. Materiality 분류 (계획서 Slice 4 — 최우선 신규)
- **목적**: 차이를 material/immaterial로 분류해 **A/B triage를 자동화**.
  immaterial 잔차 → A 후보(미해소 유지하되 저순위), material → B(우선 reconcile).
- **구현**: `tolerance`와 별개로 `materiality_threshold` 도입.
  기본값 정책은 Open Question(아래) — 잠정 절대금액 + 총자산 % 병행 옵션.
- **출력 연동**: HTML 검산조서 leadsheet `표기`에 material/immaterial 구분 노출(예: Φ vs φ),
  corpus 요약에 material 미해소 / immaterial 미해소 분리 카운트.
- **수용**: threshold 옵션 동작, corpus 요약에 material/immaterial 분리 표시, 기존 matched 불변.

### S2-2. Cross-statement tie (계획서 Slice 3 갭)
- **대상**: BS 현금및현금성자산 = CF 기말 현금및현금성자산; BS 자본총계 = SCE 기말 자본총계.
- **현황**: taxonomy에 현금 매핑은 있으나 명시적 cross-statement 검증 check 부재 — 먼저 확인 후 없으면 추가.
- **수용**: 두 tie를 supporting check로 추가, 100사에서 false FAIL 없이 동작.

### S2-3. CSV 상세 export + 기간/회사 비교 (계획서 Slice 5 소폭)
- CSV: `check_type, status, target, expected, actual, diff, tolerance, materiality, evidence_source` (UTF-8 BOM, Excel 호환).
- 비교: 동일 회사 복수 연도 / 복수 회사 동일 연도 diff delta. (우선순위 낮음 — Stream 1·S2-1 이후)

---

## 실행 순서 (권장)

```
1) T5 (결함 방어 — 빠르고 false 제거)
2) T1 → T2 → T3 (cash-flow 다빈도, ROI 최고)
3) T4 (financing 분류)
4) T6 (balance 조정)
5) S2-1 (materiality — A/B 자동화)
6) S2-2, S2-3
```

각 단계 후 100사 corpus 재생성 + 메트릭 보고 + HANDOFF 노트. Stream 1 완료 시 no-difference rate 목표 재설정.

## ⚠️ BASELINE 재현성 이슈 (Codex 발견 2026-05-31 — 구현 검증 전 해결 필요)

Codex T5/T1/T2 착수 중 발견: triage가 근거로 삼은 `hundred-accuracy-v1` 아티팩트는
**primary 575 / matched 460 / unresolved 115**를 기록하지만, **현재 캐시된 raw 공시로는
clean HEAD에서도 primary 243 baseline만 재현**됨 (`manifest_2026-05-27-hundred-asset-note-bridges.json`
기준 100/100, primary 243 / matched 190 / unresolved 53).

영향:
- triage의 37개 항목은 575-baseline에서 추출 → 일부 회사/케이스가 **로컬 243-baseline에서는 생성되지 않을 수 있음** → T1·T3·T4·T6 검증이 해당 케이스로 불가할 수 있음.
- T5는 243-baseline에서도 검증됨(local primary determinate 243→224, balance gap 19건 parse_uncertain 강등, 0 newly unresolved).

**선결 과제 (Codex)**: 검증 baseline을 하나로 고정.
(a) 575-baseline을 만든 raw 공시 set을 재확보(`dart_fetch`/manifest 정합)하거나,
(b) 재현 가능한 243-baseline 기준으로 triage 케이스를 재매핑.
어느 쪽이든 "검증에 쓰는 corpus가 무엇인지"를 work order 메트릭에 명시.

## 미결 사항 (사용자 결정 반영)

| # | 질문 | 결정 | 영향 |
|---|---|---|---|
| MQ1 | materiality 기본 기준 | **병행** — 기본 총자산/매출 % 기반, CLI `--materiality-abs` 절대금액 override 옵션 제공 | S2-1 |
| MQ2 | 금융사 별도 파서 우선순위 | 미정 — 본 work order 후속 별건 | 별건 |
| MQ3 | A 후보를 리포트에 "실질 차이" 라벨 분리 노출 | 미정 — 출력 단계에서 재확인 | 출력 |
