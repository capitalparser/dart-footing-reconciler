import json
from pathlib import Path

from pydantic import BaseModel, model_validator

from election_workpaper.models import (
    Candidate,
    ElectionArea,
    ElectionContest,
    SourceEvidence,
)


class ElectionDataset(BaseModel):
    areas: list[ElectionArea]
    contests: list[ElectionContest]
    candidates: list[Candidate]
    sources: dict[str, SourceEvidence]

    @model_validator(mode="after")
    def validate_cross_record_references(self) -> "ElectionDataset":
        area_ids = {area.area_id for area in self.areas}
        contest_ids = {contest.contest_id for contest in self.contests}
        source_ids = set(self.sources)

        missing_area_ids = {
            contest.area_id
            for contest in self.contests
            if contest.area_id not in area_ids
        }
        if missing_area_ids:
            missing = ", ".join(sorted(missing_area_ids))
            raise ValueError(f"contest area_id references unknown areas: {missing}")

        missing_contest_ids = {
            candidate.contest_id
            for candidate in self.candidates
            if candidate.contest_id not in contest_ids
        }
        if missing_contest_ids:
            missing = ", ".join(sorted(missing_contest_ids))
            raise ValueError(
                f"candidate contest_id references unknown contests: {missing}"
            )

        missing_profile_source_ids = {
            source_id
            for candidate in self.candidates
            for source_id in candidate.profile_source_ids.values()
            if source_id not in source_ids
        }
        if missing_profile_source_ids:
            missing = ", ".join(sorted(missing_profile_source_ids))
            raise ValueError(
                f"candidate profile_source_ids reference unknown sources: {missing}"
            )

        return self


def load_region_fixture(path: Path) -> ElectionDataset:
    payload = json.loads(path.read_text(encoding="utf-8"))
    seen_source_ids = set()
    duplicate_source_ids = set()
    for item in payload["sources"]:
        source_id = item["source_id"]
        if source_id in seen_source_ids:
            duplicate_source_ids.add(source_id)
        seen_source_ids.add(source_id)

    if duplicate_source_ids:
        duplicates = ", ".join(sorted(duplicate_source_ids))
        raise ValueError(f"duplicate source_id values: {duplicates}")

    sources = {
        item["source_id"]: SourceEvidence.model_validate(item)
        for item in payload["sources"]
    }
    return ElectionDataset(
        areas=[ElectionArea.model_validate(item) for item in payload["areas"]],
        contests=[ElectionContest.model_validate(item) for item in payload["contests"]],
        candidates=[Candidate.model_validate(item) for item in payload["candidates"]],
        sources=sources,
    )
