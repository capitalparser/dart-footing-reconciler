from election_workpaper.classification import classify_claim, classify_claims
from election_workpaper.models import PolicyTag, FeasibilitySignalType


def test_classify_transport_claim_with_funding_and_timeline():
    claim, signals = classify_claim(
        claim_id="claim-1",
        candidate_id="cand-a",
        contest_id="contest-1",
        raw_text="구 예산 120억 원을 활용해 마을버스 배차 간격을 10분 이내로 줄이겠습니다.",
        source_ids=["pledge-a"],
    )

    assert claim.policy_tags == [PolicyTag.TRANSPORTATION, PolicyTag.BUDGET]
    assert {signal.signal_type for signal in signals} == {
        FeasibilitySignalType.FUNDING_MENTIONED,
        FeasibilitySignalType.AUTHORITY_STATED,
        FeasibilitySignalType.TIMELINE_UNCLEAR,
    }


def test_classify_claims_returns_claims_and_signals():
    claims, signals = classify_claims(
        [
            {
                "claim_id": "claim-1",
                "candidate_id": "cand-a",
                "contest_id": "contest-1",
                "raw_text": "서울시와 협의해 출퇴근 버스 노선을 늘리겠습니다.",
                "source_ids": ["pledge-b"],
            }
        ]
    )

    assert claims[0].policy_tags == [PolicyTag.TRANSPORTATION]
    assert FeasibilitySignalType.CENTRAL_GOVERNMENT_DEPENDENCY in {
        signal.signal_type for signal in signals
    }
