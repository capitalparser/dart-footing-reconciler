from pathlib import Path

from election_workpaper.extraction import extract_claims
from election_workpaper.models import ReviewStatus
from election_workpaper.repository import load_region_fixture


def test_extract_claims_preserves_candidate_and_source_ids():
    dataset = load_region_fixture(
        Path("tests/fixtures/election_workpaper/pilot_region.json")
    )
    claims = extract_claims(dataset)

    assert [claim.claim_id for claim in claims] == [
        "claim-cand-a-pledge-a-1",
        "claim-cand-a-pledge-a-2",
        "claim-cand-b-pledge-b-1",
        "claim-cand-b-pledge-b-2",
    ]
    assert [claim.candidate_id for claim in claims] == [
        "cand-a",
        "cand-a",
        "cand-b",
        "cand-b",
    ]
    assert [claim.source_ids for claim in claims] == [
        ["pledge-a"],
        ["pledge-a"],
        ["pledge-b"],
        ["pledge-b"],
    ]
    assert all(claim.contest_id == "jung-head-2026" for claim in claims)
    assert all(claim.review_status == ReviewStatus.NEEDS_REVIEW for claim in claims)
    assert all(claim.summary for claim in claims)
    assert claims[0].candidate_id == "cand-a"
    assert claims[0].source_ids == ["pledge-a"]
    assert (
        claims[0].raw_text
        == "구 예산 120억 원을 활용해 마을버스 배차 간격을 10분 이내로 줄이겠습니다."
    )
    assert claims[0].summary == "구 예산 120억 원을 활용해 마을버스 배차 간격을 10분 이내로 줄이겠습니다"
