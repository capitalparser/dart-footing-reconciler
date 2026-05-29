from pathlib import Path

from election_workpaper.extraction import extract_claims
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
    assert claims[0].candidate_id == "cand-a"
    assert claims[0].source_ids == ["pledge-a"]
    assert (
        claims[0].raw_text
        == "구 예산 120억 원을 활용해 마을버스 배차 간격을 10분 이내로 줄이겠습니다."
    )
