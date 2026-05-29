import json
from pathlib import Path

from pydantic import BaseModel

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


def load_region_fixture(path: Path) -> ElectionDataset:
    payload = json.loads(path.read_text(encoding="utf-8"))
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
