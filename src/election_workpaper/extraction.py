import re

from election_workpaper.models import PromiseClaim, ReviewStatus
from election_workpaper.repository import ElectionDataset


def extract_claims(dataset: ElectionDataset) -> list[PromiseClaim]:
    claims: list[PromiseClaim] = []
    pledge_sources = [
        source
        for source in dataset.sources.values()
        if source.source_type == "official_pledge"
    ]
    candidates_by_order = list(dataset.candidates)

    for candidate, source in zip(candidates_by_order, pledge_sources, strict=True):
        sentences = _split_korean_sentences(source.raw_text)
        for index, sentence in enumerate(sentences, start=1):
            claim_id = f"claim-{candidate.candidate_id}-{source.source_id}-{index}"
            claims.append(
                PromiseClaim(
                    claim_id=claim_id,
                    candidate_id=candidate.candidate_id,
                    contest_id=candidate.contest_id,
                    raw_text=sentence,
                    summary=_summarize(sentence),
                    policy_tags=[],
                    source_ids=[source.source_id],
                    review_status=ReviewStatus.NEEDS_REVIEW,
                )
            )
    return claims


def _split_korean_sentences(text: str) -> list[str]:
    parts = re.findall(r"[^.!?。]+[.!?。]", text)
    return [part.strip() for part in parts if part.strip()]


def _summarize(sentence: str) -> str:
    return sentence.removesuffix(".").strip()
