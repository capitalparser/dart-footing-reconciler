# Reviewer Lens for DART Footing MVP

## Verdict

Pass. This should be treated as a separate reviewer interpretation layer on top
of DART footing and reconciliation, not as part of the footing engine itself.

The useful product is not an automatic audit-risk conclusion system. The useful
product is a reviewer question generator that turns DART evidence into
business-model-aware hypotheses, required follow-ups, and engagement team
questions.

## Product Definition

User-facing Korean name:

```text
DART 푸팅 기반 리뷰어 렌즈
```

English working name:

```text
Reviewer Lens for DART Footing
```

Primary job:

```text
리뷰어가 대상 회사 보고서를 볼 때 먼저 물어야 할 질문을 만든다.
```

Non-goal:

```text
감사위험이 존재한다고 단정하지 않는다.
```

## Evidence Flow

```text
DART 푸팅
→ 보고서 구조화
→ 재무제표/주석/사업내용 추출
→ 계정 변화 분석
→ 사업모델 기반 위험 가설
→ 주요 계정 리뷰 포인트
→ 리뷰어 질문 리스트
```

## Architecture Layers

### Layer 1. Footing / Extraction

Purpose:

```text
DART 보고서에서 재무제표, 주석, 사업의 내용, 감사보고서, KAM,
계정별 텍스트와 금액 근거를 구조화한다.
```

Output examples:

- Financial statement lines
- Note tables and narrative blocks
- Footing and reconciliation checks
- Source locations
- Business section snippets
- Audit report and KAM snippets

### Layer 2. Accounting Interpretation

Purpose:

```text
계정 변화, 비율, 추세, 주석 키워드를 사업모델별 문법으로 해석한다.
```

Output examples:

- Key account movement table
- Ratio and trend signals
- Business-model sensitivity notes
- Evidence-backed anomaly candidates

### Layer 3. Reviewer Coach

Purpose:

```text
위험평가, 주요 계정 리뷰 포인트, 요청자료 리스트,
파트너/매니저 질문 초안을 생성한다.
```

Output examples:

- Risk hypotheses
- Reviewer questions
- Required follow-up
- Recommended follow-up
- Request list

## Output Contract

Each reviewer lens item should follow this shape:

```text
Verdict:
conditional / high-risk / normal-with-watchpoints

Why it matters:
숫자 변화가 어떤 회사 활동을 시사하는지

Evidence:
재무제표 수치, 주석 문구, 사업보고서 섹션

Risk hypothesis:
가능한 활동 가설

Reviewer questions:
리뷰어가 engagement team에 물어볼 질문

Required follow-up:
추가 확인 없이는 결론 내리면 안 되는 항목

Recommended follow-up:
품질을 높이는 추가 검토 항목
```

## MVP

Target:

```text
제조업 상장사 1개
```

Input:

```text
최근 3개년 사업보고서/감사보고서 DART 푸팅 결과
```

Output:

1. 사업모델 10줄 요약
2. 주요 계정 변화표
3. 이상 신호 5개
4. 위험 가설 5개
5. 주요 계정별 리뷰 질문
6. 요청자료 리스트

Initial account families:

- 매출
- 매출채권
- 재고자산
- 매출원가
- 유형자산
- 감가상각비
- 영업현금흐름
- 충당부채/반품/판매장려금

## Example Tone

Good:

```text
매출채권 증가율이 매출 증가율을 크게 상회하고 영업현금흐름이 악화되어,
기말 판매조건 완화 또는 채널 밀어내기 가능성을 후속 확인할 필요 있음.
```

Bad:

```text
매출 밀어내기 있음.
```

## Reviewer Question Examples

For a manufacturing company:

- 기말 전후 주요 거래처 매출과 후속 입금은 확인했는가?
- 재고 증가가 원재료, 재공품, 제품 중 어디에서 발생했는가?
- 가동률 하락이 있었고, 유휴원가는 손익 처리됐는가?
- 원재료 가격 상승분의 판가 전가 근거가 있는가?
- 재고평가충당금 산정 로직이 전기와 달라졌는가?

## Implementation Guardrails

- Footing result and reviewer lens result must be separate data objects.
- Reviewer lens cannot change reconciliation status.
- All risk hypotheses must cite numeric or narrative evidence.
- Follow-up items must be split into required and recommended.
- Generated questions should be phrased as questions to the engagement team,
  not as conclusions about the company.
- The UI should label this area as reviewer interpretation, not footing result.

## First Integration Point

Add a new report section after `리뷰 큐`:

```text
리뷰어 렌즈
```

Initial state before full implementation:

```text
이 섹션은 푸팅 결과를 기반으로 사업모델, 주요 계정 변화, 위험 가설,
리뷰어 질문을 생성하는 확장 기능입니다. 현재 MVP에서는 푸팅/대사 결과와
분리하여 설계 중입니다.
```

This keeps the current audit reconciliation report honest while reserving the
right product surface for the reviewer-coach layer.
