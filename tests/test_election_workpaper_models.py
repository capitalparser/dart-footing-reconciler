from election_workpaper.models import (
    Candidate,
    ElectionArea,
    ElectionContest,
    PolicyTag,
    PromiseClaim,
    ReviewStatus,
    SourceEvidence,
)


def test_promise_claim_requires_source_evidence():
    source = SourceEvidence(
        source_id="src-1",
        source_type="official_pledge",
        title="후보자 공약",
        url="https://example.test/pledge",
        retrieved_date="2026-05-29",
        raw_text="버스 배차 간격을 단축하겠습니다.",
        confidence=1.0,
    )
    claim = PromiseClaim(
        claim_id="claim-1",
        candidate_id="cand-1",
        contest_id="contest-1",
        raw_text="버스 배차 간격을 단축하겠습니다.",
        summary="버스 배차 간격 단축",
        policy_tags=[PolicyTag.TRANSPORTATION],
        source_ids=["src-1"],
        review_status=ReviewStatus.NEEDS_REVIEW,
    )

    assert source.source_id in claim.source_ids
    assert claim.policy_tags == [PolicyTag.TRANSPORTATION]
    assert claim.review_status == ReviewStatus.NEEDS_REVIEW


def test_candidate_profile_stores_only_source_backed_fields():
    area = ElectionArea(area_id="area-1", name="서울특별시 중구", region_code="11140")
    contest = ElectionContest(
        contest_id="contest-1",
        area_id=area.area_id,
        contest_type="district_head",
        name="중구청장",
        nec_election_id="20260603",
    )
    candidate = Candidate(
        candidate_id="cand-1",
        contest_id=contest.contest_id,
        name="김선거",
        party="무소속",
        profile={"career": "전 구의원"},
        profile_source_ids={"career": "src-profile-1"},
    )

    assert candidate.profile["career"] == "전 구의원"
    assert candidate.profile_source_ids["career"] == "src-profile-1"
