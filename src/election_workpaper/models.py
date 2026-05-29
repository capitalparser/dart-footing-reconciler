from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl


class ReviewStatus(StrEnum):
    EXTRACTED = "extracted"
    NEEDS_REVIEW = "needs_review"
    REVIEWED = "reviewed"
    CORRECTED = "corrected"
    REJECTED = "rejected"


class PolicyTag(StrEnum):
    TRANSPORTATION = "transportation"
    HOUSING = "housing"
    WELFARE = "welfare"
    EDUCATION = "education"
    INDUSTRY = "industry"
    BUDGET = "budget"
    CLIMATE = "climate"
    SAFETY = "safety"
    ADMINISTRATION = "administration"
    HEALTH = "health"
    CULTURE = "culture"
    CHILDCARE = "childcare"
    JOBS = "jobs"
    DIGITAL = "digital"
    OTHER = "other"


class FeasibilitySignalType(StrEnum):
    FUNDING_MENTIONED = "funding_mentioned"
    FUNDING_NOT_MENTIONED = "funding_not_mentioned"
    AUTHORITY_STATED = "authority_stated"
    AUTHORITY_UNCLEAR = "authority_unclear"
    TIMELINE_STATED = "timeline_stated"
    TIMELINE_UNCLEAR = "timeline_unclear"
    LAW_CHANGE_CANDIDATE = "law_change_candidate"
    CENTRAL_GOVERNMENT_DEPENDENCY = "central_government_dependency"
    STATISTIC_CHECK_NEEDED = "statistic_check_needed"


class ElectionArea(BaseModel):
    area_id: str
    name: str
    region_code: str
    mapping_source: str = "fixture"
    mapping_confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ElectionContest(BaseModel):
    contest_id: str
    area_id: str
    contest_type: str
    name: str
    nec_election_id: str | None = None


class Candidate(BaseModel):
    candidate_id: str
    contest_id: str
    name: str
    party: str
    profile: dict[str, str] = Field(default_factory=dict)
    profile_source_ids: dict[str, str] = Field(default_factory=dict)


class SourceEvidence(BaseModel):
    source_id: str
    source_type: str
    title: str
    url: HttpUrl | None = None
    retrieved_date: str
    raw_text: str
    page: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class PromiseClaim(BaseModel):
    claim_id: str
    candidate_id: str
    contest_id: str
    raw_text: str
    summary: str
    policy_tags: list[PolicyTag] = Field(default_factory=list)
    source_ids: list[str]
    review_status: ReviewStatus


class FeasibilitySignal(BaseModel):
    signal_id: str
    claim_id: str
    signal_type: FeasibilitySignalType
    explanation: str
    source_ids: list[str]
    review_status: ReviewStatus = ReviewStatus.NEEDS_REVIEW


class ComparisonCluster(BaseModel):
    cluster_id: str
    policy_tag: PolicyTag
    claim_ids: list[str]
    rationale: str
    review_status: ReviewStatus = ReviewStatus.NEEDS_REVIEW
