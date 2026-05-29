from collections.abc import Iterable

from election_workpaper.models import (
    FeasibilitySignal,
    FeasibilitySignalType,
    PolicyTag,
    PromiseClaim,
    ReviewStatus,
)

TAG_KEYWORDS: list[tuple[PolicyTag, tuple[str, ...]]] = [
    (PolicyTag.TRANSPORTATION, ("버스", "노선", "배차", "교통", "출퇴근")),
    (PolicyTag.HOUSING, ("주택", "월세", "임대", "부동산")),
    (PolicyTag.WELFARE, ("복지", "지원", "돌봄")),
    (PolicyTag.EDUCATION, ("교육", "학교", "학생")),
    (PolicyTag.BUDGET, ("예산", "재원", "원")),
    (PolicyTag.SAFETY, ("안전", "점검", "재난")),
]


def classify_claim(
    claim_id: str,
    candidate_id: str,
    contest_id: str,
    raw_text: str,
    source_ids: list[str],
) -> tuple[PromiseClaim, list[FeasibilitySignal]]:
    tags = _tags_for(raw_text)
    claim = PromiseClaim(
        claim_id=claim_id,
        candidate_id=candidate_id,
        contest_id=contest_id,
        raw_text=raw_text,
        summary=raw_text.removesuffix(".").strip(),
        policy_tags=tags,
        source_ids=source_ids,
        review_status=ReviewStatus.NEEDS_REVIEW,
    )
    signals = _signals_for(claim)
    return claim, signals


def classify_claims(
    items: Iterable[dict[str, object]],
) -> tuple[list[PromiseClaim], list[FeasibilitySignal]]:
    claims: list[PromiseClaim] = []
    signals: list[FeasibilitySignal] = []
    for item in items:
        claim, claim_signals = classify_claim(
            claim_id=str(item["claim_id"]),
            candidate_id=str(item["candidate_id"]),
            contest_id=str(item["contest_id"]),
            raw_text=str(item["raw_text"]),
            source_ids=list(item["source_ids"]),
        )
        claims.append(claim)
        signals.extend(claim_signals)
    return claims, signals


def apply_classification(
    claims: list[PromiseClaim],
) -> tuple[list[PromiseClaim], list[FeasibilitySignal]]:
    classified: list[PromiseClaim] = []
    signals: list[FeasibilitySignal] = []
    for claim in claims:
        updated, claim_signals = classify_claim(
            claim.claim_id,
            claim.candidate_id,
            claim.contest_id,
            claim.raw_text,
            claim.source_ids,
        )
        classified.append(updated)
        signals.extend(claim_signals)
    return classified, signals


def _tags_for(text: str) -> list[PolicyTag]:
    tags = [
        tag
        for tag, keywords in TAG_KEYWORDS
        if any(keyword in text for keyword in keywords)
    ]
    return tags or [PolicyTag.OTHER]


def _signals_for(claim: PromiseClaim) -> list[FeasibilitySignal]:
    text = claim.raw_text
    signal_types: list[FeasibilitySignalType] = []

    if any(keyword in text for keyword in ("예산", "재원", "원")):
        signal_types.append(FeasibilitySignalType.FUNDING_MENTIONED)
    else:
        signal_types.append(FeasibilitySignalType.FUNDING_NOT_MENTIONED)

    if any(keyword in text for keyword in ("구 ", "구청", "시 ", "서울시")):
        signal_types.append(FeasibilitySignalType.AUTHORITY_STATED)
    else:
        signal_types.append(FeasibilitySignalType.AUTHORITY_UNCLEAR)

    if any(keyword in text for keyword in ("2026년", "2027년", "2028년", "임기 내")):
        signal_types.append(FeasibilitySignalType.TIMELINE_STATED)
    else:
        signal_types.append(FeasibilitySignalType.TIMELINE_UNCLEAR)

    if any(keyword in text for keyword in ("서울시와 협의", "정부", "국회", "중앙정부")):
        signal_types.append(FeasibilitySignalType.CENTRAL_GOVERNMENT_DEPENDENCY)

    return [
        FeasibilitySignal(
            signal_id=f"signal-{claim.claim_id}-{index}",
            claim_id=claim.claim_id,
            signal_type=signal_type,
            explanation=_explanation(signal_type),
            source_ids=claim.source_ids,
        )
        for index, signal_type in enumerate(signal_types, start=1)
    ]


def _explanation(signal_type: FeasibilitySignalType) -> str:
    return {
        FeasibilitySignalType.FUNDING_MENTIONED: "공약 원문에 예산 또는 재원 표현이 있습니다.",
        FeasibilitySignalType.FUNDING_NOT_MENTIONED: "공약 원문에서 재원 표현을 찾지 못했습니다.",
        FeasibilitySignalType.AUTHORITY_STATED: "공약 원문에 실행 주체로 볼 수 있는 기관 표현이 있습니다.",
        FeasibilitySignalType.AUTHORITY_UNCLEAR: "공약 원문에서 실행 주체 표현을 찾지 못했습니다.",
        FeasibilitySignalType.TIMELINE_STATED: "공약 원문에 연도 또는 기간 표현이 있습니다.",
        FeasibilitySignalType.TIMELINE_UNCLEAR: "공약 원문에서 연도 또는 기간 표현을 찾지 못했습니다.",
        FeasibilitySignalType.CENTRAL_GOVERNMENT_DEPENDENCY: "공약 원문에 외부 기관 협의 또는 중앙 단위 의존 표현이 있습니다.",
        FeasibilitySignalType.LAW_CHANGE_CANDIDATE: "공약 원문에 법령 변경 검토가 필요한 표현이 있습니다.",
        FeasibilitySignalType.STATISTIC_CHECK_NEEDED: "공약 원문에 외부 통계 확인이 필요한 표현이 있습니다.",
    }[signal_type]
