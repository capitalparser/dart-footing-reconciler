# Election Workpaper MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fixture-backed local Election Workpaper MVP that can load one pilot region, preserve source evidence, extract pledge claims, tag and cluster claims, apply non-ranking feasibility signals, export reviewed data, and render a local HTML workbench.

**Architecture:** Add a separate `election_workpaper` Python package inside this repository, leaving `dart_footing_reconciler` untouched. The first vertical slice uses local JSON fixtures that mimic official NEC/API/PDF-derived data, deterministic extraction/classification rules, Pydantic domain models, a Typer CLI, JSON/CSV exports, and a static HTML workbench generated from reviewed records.

**Tech Stack:** Python 3.11+, Pydantic v2, Typer, pytest, stdlib `json`, `csv`, `html`, and `pathlib`.

---

## Scope Check

The approved design describes a larger product with ingestion, normalization, extraction, classification, comparison, review, presentation, and later public views. This plan implements the first working vertical slice only:

- local fixture ingestion instead of live NEC API calls
- city/county/district selection by fixture area code
- deterministic claim extraction from official-source-like fixture text
- deterministic topic tags and feasibility signals
- non-ranking comparison clusters
- JSON/CSV export
- static HTML workbench

Live API clients, PDF OCR, address-to-district mapping, authentication, hosted deployment, and nationwide ingestion are separate plans after this slice works.

## File Structure

- Create `src/election_workpaper/__init__.py`: package exports.
- Create `src/election_workpaper/models.py`: Pydantic data model and enum definitions.
- Create `src/election_workpaper/repository.py`: load pilot region JSON fixtures into domain models.
- Create `src/election_workpaper/extraction.py`: split source text into source-backed `PromiseClaim` records.
- Create `src/election_workpaper/classification.py`: assign neutral policy tags and feasibility signals.
- Create `src/election_workpaper/comparison.py`: group similar claims without ranking candidates.
- Create `src/election_workpaper/guardrails.py`: reject score/rank/grade/recommendation fields in public output.
- Create `src/election_workpaper/export.py`: build reviewed JSON/CSV export rows.
- Create `src/election_workpaper/report_html.py`: render a static local workbench.
- Create `src/election_workpaper/cli.py`: Typer CLI entrypoint.
- Modify `pyproject.toml`: include `src/election_workpaper` in wheel packages and add `election-workpaper` CLI script.
- Create `tests/fixtures/election_workpaper/pilot_region.json`: one pilot region fixture with two candidates and source-backed pledge text.
- Create tests under `tests/test_election_workpaper_*.py`.

## Task 1: Package Skeleton and CLI Smoke

**Files:**
- Create: `src/election_workpaper/__init__.py`
- Create: `src/election_workpaper/cli.py`
- Modify: `pyproject.toml`
- Test: `tests/test_election_workpaper_package.py`

- [ ] **Step 1: Write the failing package and CLI test**

Create `tests/test_election_workpaper_package.py`:

```python
from typer.testing import CliRunner

from election_workpaper import __version__
from election_workpaper.cli import app


def test_package_exposes_version():
    assert __version__ == "0.1.0"


def test_cli_version_command():
    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0
    assert "election-workpaper 0.1.0" in result.stdout
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
uv run pytest tests/test_election_workpaper_package.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'election_workpaper'`.

- [ ] **Step 3: Add the package skeleton**

Create `src/election_workpaper/__init__.py`:

```python
"""Evidence-based election pledge workpaper tools."""

__version__ = "0.1.0"
```

Create `src/election_workpaper/cli.py`:

```python
import typer

from election_workpaper import __version__

app = typer.Typer(help="Evidence-based election pledge workpaper CLI.")


@app.command()
def version() -> None:
    """Print the Election Workpaper version."""
    typer.echo(f"election-workpaper {__version__}")
```

Modify `pyproject.toml`:

```toml
[project.scripts]
dart-footing = "dart_footing_reconciler.cli:app"
election-workpaper = "election_workpaper.cli:app"

[tool.hatch.build.targets.wheel]
packages = ["src/dart_footing_reconciler", "src/election_workpaper"]
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
uv run pytest tests/test_election_workpaper_package.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/election_workpaper/__init__.py src/election_workpaper/cli.py tests/test_election_workpaper_package.py
git commit -m "feat: add election workpaper package skeleton"
```

## Task 2: Domain Models With Source Evidence

**Files:**
- Create: `src/election_workpaper/models.py`
- Test: `tests/test_election_workpaper_models.py`

- [ ] **Step 1: Write the failing model tests**

Create `tests/test_election_workpaper_models.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
uv run pytest tests/test_election_workpaper_models.py -v
```

Expected: FAIL with `ModuleNotFoundError` or missing model names.

- [ ] **Step 3: Implement the models**

Create `src/election_workpaper/models.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
uv run pytest tests/test_election_workpaper_models.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/election_workpaper/models.py tests/test_election_workpaper_models.py
git commit -m "feat: model election workpaper evidence records"
```

## Task 3: Pilot Fixture Repository

**Files:**
- Create: `tests/fixtures/election_workpaper/pilot_region.json`
- Create: `src/election_workpaper/repository.py`
- Test: `tests/test_election_workpaper_repository.py`

- [ ] **Step 1: Write the pilot fixture**

Create `tests/fixtures/election_workpaper/pilot_region.json`:

```json
{
  "areas": [
    {"area_id": "seoul-jung", "name": "서울특별시 중구", "region_code": "11140"}
  ],
  "contests": [
    {
      "contest_id": "jung-head-2026",
      "area_id": "seoul-jung",
      "contest_type": "district_head",
      "name": "서울특별시 중구청장",
      "nec_election_id": "20260603"
    }
  ],
  "candidates": [
    {
      "candidate_id": "cand-a",
      "contest_id": "jung-head-2026",
      "name": "김도시",
      "party": "가칭미래당",
      "profile": {"career": "전 서울시 정책보좌관"},
      "profile_source_ids": {"career": "profile-a"}
    },
    {
      "candidate_id": "cand-b",
      "contest_id": "jung-head-2026",
      "name": "이생활",
      "party": "가칭시민당",
      "profile": {"career": "전 중구의회 의원"},
      "profile_source_ids": {"career": "profile-b"}
    }
  ],
  "sources": [
    {
      "source_id": "profile-a",
      "source_type": "official_profile",
      "title": "김도시 후보자 정보",
      "url": "https://example.test/candidate-a",
      "retrieved_date": "2026-05-29",
      "raw_text": "경력: 전 서울시 정책보좌관",
      "confidence": 1.0
    },
    {
      "source_id": "profile-b",
      "source_type": "official_profile",
      "title": "이생활 후보자 정보",
      "url": "https://example.test/candidate-b",
      "retrieved_date": "2026-05-29",
      "raw_text": "경력: 전 중구의회 의원",
      "confidence": 1.0
    },
    {
      "source_id": "pledge-a",
      "source_type": "official_pledge",
      "title": "김도시 후보 공약",
      "url": "https://example.test/pledge-a",
      "retrieved_date": "2026-05-29",
      "raw_text": "구 예산 120억 원을 활용해 마을버스 배차 간격을 10분 이내로 줄이겠습니다. 2027년까지 노후 공공임대주택 안전 점검을 확대하겠습니다.",
      "confidence": 1.0
    },
    {
      "source_id": "pledge-b",
      "source_type": "official_pledge",
      "title": "이생활 후보 공약",
      "url": "https://example.test/pledge-b",
      "retrieved_date": "2026-05-29",
      "raw_text": "서울시와 협의해 출퇴근 버스 노선을 늘리겠습니다. 재원 계획을 마련해 청년 월세 지원 대상을 확대하겠습니다.",
      "confidence": 1.0
    }
  ]
}
```

- [ ] **Step 2: Write the failing repository test**

Create `tests/test_election_workpaper_repository.py`:

```python
from pathlib import Path

from election_workpaper.repository import load_region_fixture


FIXTURE = Path("tests/fixtures/election_workpaper/pilot_region.json")


def test_load_region_fixture_preserves_source_text():
    dataset = load_region_fixture(FIXTURE)

    assert dataset.areas[0].area_id == "seoul-jung"
    assert dataset.contests[0].name == "서울특별시 중구청장"
    assert len(dataset.candidates) == 2
    assert dataset.sources["pledge-a"].raw_text.startswith("구 예산 120억 원")
```

- [ ] **Step 3: Run the test to verify it fails**

Run:

```bash
uv run pytest tests/test_election_workpaper_repository.py -v
```

Expected: FAIL because `election_workpaper.repository` does not exist.

- [ ] **Step 4: Implement the repository**

Create `src/election_workpaper/repository.py`:

```python
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
```

- [ ] **Step 5: Run the test to verify it passes**

Run:

```bash
uv run pytest tests/test_election_workpaper_repository.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/election_workpaper/repository.py tests/fixtures/election_workpaper/pilot_region.json tests/test_election_workpaper_repository.py
git commit -m "feat: load election workpaper pilot fixture"
```

## Task 4: Source-Backed Claim Extraction

**Files:**
- Create: `src/election_workpaper/extraction.py`
- Test: `tests/test_election_workpaper_extraction.py`

- [ ] **Step 1: Write the failing extraction test**

Create `tests/test_election_workpaper_extraction.py`:

```python
from pathlib import Path

from election_workpaper.extraction import extract_claims
from election_workpaper.repository import load_region_fixture


def test_extract_claims_preserves_candidate_and_source_ids():
    dataset = load_region_fixture(Path("tests/fixtures/election_workpaper/pilot_region.json"))
    claims = extract_claims(dataset)

    assert [claim.claim_id for claim in claims] == [
        "claim-cand-a-pledge-a-1",
        "claim-cand-a-pledge-a-2",
        "claim-cand-b-pledge-b-1",
        "claim-cand-b-pledge-b-2",
    ]
    assert claims[0].candidate_id == "cand-a"
    assert claims[0].source_ids == ["pledge-a"]
    assert claims[0].raw_text == "구 예산 120억 원을 활용해 마을버스 배차 간격을 10분 이내로 줄이겠습니다."
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
uv run pytest tests/test_election_workpaper_extraction.py -v
```

Expected: FAIL because `election_workpaper.extraction` does not exist.

- [ ] **Step 3: Implement deterministic extraction**

Create `src/election_workpaper/extraction.py`:

```python
import re

from election_workpaper.models import PromiseClaim, ReviewStatus
from election_workpaper.repository import ElectionDataset


def extract_claims(dataset: ElectionDataset) -> list[PromiseClaim]:
    claims: list[PromiseClaim] = []
    pledge_sources = [
        source for source in dataset.sources.values()
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
uv run pytest tests/test_election_workpaper_extraction.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/election_workpaper/extraction.py tests/test_election_workpaper_extraction.py
git commit -m "feat: extract source backed pledge claims"
```

## Task 5: Neutral Tags and Feasibility Signals

**Files:**
- Create: `src/election_workpaper/classification.py`
- Test: `tests/test_election_workpaper_classification.py`

- [ ] **Step 1: Write the failing classification tests**

Create `tests/test_election_workpaper_classification.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
uv run pytest tests/test_election_workpaper_classification.py -v
```

Expected: FAIL because `election_workpaper.classification` does not exist.

- [ ] **Step 3: Implement deterministic classification**

Create `src/election_workpaper/classification.py`:

```python
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


def classify_claims(items: Iterable[dict[str, object]]) -> tuple[list[PromiseClaim], list[FeasibilitySignal]]:
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


def apply_classification(claims: list[PromiseClaim]) -> tuple[list[PromiseClaim], list[FeasibilitySignal]]:
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
        tag for tag, keywords in TAG_KEYWORDS
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
uv run pytest tests/test_election_workpaper_classification.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/election_workpaper/classification.py tests/test_election_workpaper_classification.py
git commit -m "feat: classify pledge claims with neutral signals"
```

## Task 6: Non-Ranking Comparison Clusters

**Files:**
- Create: `src/election_workpaper/comparison.py`
- Test: `tests/test_election_workpaper_comparison.py`

- [ ] **Step 1: Write the failing comparison tests**

Create `tests/test_election_workpaper_comparison.py`:

```python
from election_workpaper.comparison import build_comparison_clusters
from election_workpaper.models import PolicyTag, PromiseClaim, ReviewStatus


def test_build_comparison_clusters_groups_by_policy_tag_without_ranking():
    claims = [
        PromiseClaim(
            claim_id="claim-a",
            candidate_id="cand-a",
            contest_id="contest-1",
            raw_text="마을버스 배차 간격을 줄이겠습니다.",
            summary="마을버스 배차 간격 단축",
            policy_tags=[PolicyTag.TRANSPORTATION],
            source_ids=["pledge-a"],
            review_status=ReviewStatus.NEEDS_REVIEW,
        ),
        PromiseClaim(
            claim_id="claim-b",
            candidate_id="cand-b",
            contest_id="contest-1",
            raw_text="출퇴근 버스 노선을 늘리겠습니다.",
            summary="출퇴근 버스 노선 확대",
            policy_tags=[PolicyTag.TRANSPORTATION],
            source_ids=["pledge-b"],
            review_status=ReviewStatus.NEEDS_REVIEW,
        ),
    ]

    clusters = build_comparison_clusters(claims)

    assert len(clusters) == 1
    assert clusters[0].policy_tag == PolicyTag.TRANSPORTATION
    assert clusters[0].claim_ids == ["claim-a", "claim-b"]
    assert "rank" not in clusters[0].model_dump()
    assert "score" not in clusters[0].model_dump()
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
uv run pytest tests/test_election_workpaper_comparison.py -v
```

Expected: FAIL because `election_workpaper.comparison` does not exist.

- [ ] **Step 3: Implement comparison clusters**

Create `src/election_workpaper/comparison.py`:

```python
from collections import defaultdict

from election_workpaper.models import ComparisonCluster, PolicyTag, PromiseClaim


def build_comparison_clusters(claims: list[PromiseClaim]) -> list[ComparisonCluster]:
    grouped: dict[PolicyTag, list[PromiseClaim]] = defaultdict(list)
    for claim in claims:
        first_tag = claim.policy_tags[0] if claim.policy_tags else PolicyTag.OTHER
        grouped[first_tag].append(claim)

    clusters: list[ComparisonCluster] = []
    for tag in sorted(grouped, key=lambda item: item.value):
        tag_claims = sorted(grouped[tag], key=lambda claim: claim.claim_id)
        clusters.append(
            ComparisonCluster(
                cluster_id=f"cluster-{tag.value}-1",
                policy_tag=tag,
                claim_ids=[claim.claim_id for claim in tag_claims],
                rationale=f"{tag.value} 주제로 분류된 공약을 후보 순위 없이 함께 표시합니다.",
            )
        )
    return clusters
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
uv run pytest tests/test_election_workpaper_comparison.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/election_workpaper/comparison.py tests/test_election_workpaper_comparison.py
git commit -m "feat: group pledge claims without ranking candidates"
```

## Task 7: Guarded JSON and CSV Exports

**Files:**
- Create: `src/election_workpaper/guardrails.py`
- Create: `src/election_workpaper/export.py`
- Test: `tests/test_election_workpaper_export.py`

- [ ] **Step 1: Write the failing export tests**

Create `tests/test_election_workpaper_export.py`:

```python
import pytest

from election_workpaper.export import build_public_claim_rows
from election_workpaper.guardrails import assert_public_output_is_non_ranking
from election_workpaper.models import PolicyTag, PromiseClaim, ReviewStatus


def test_public_rows_include_sources_and_review_status():
    claim = PromiseClaim(
        claim_id="claim-a",
        candidate_id="cand-a",
        contest_id="contest-1",
        raw_text="마을버스 배차 간격을 줄이겠습니다.",
        summary="마을버스 배차 간격 단축",
        policy_tags=[PolicyTag.TRANSPORTATION],
        source_ids=["pledge-a"],
        review_status=ReviewStatus.REVIEWED,
    )

    rows = build_public_claim_rows([claim])

    assert rows == [
        {
            "claim_id": "claim-a",
            "candidate_id": "cand-a",
            "contest_id": "contest-1",
            "summary": "마을버스 배차 간격 단축",
            "policy_tags": "transportation",
            "source_ids": "pledge-a",
            "review_status": "reviewed",
        }
    ]


def test_guardrail_rejects_score_rank_grade_and_recommendation_fields():
    with pytest.raises(ValueError, match="ranking-style field"):
        assert_public_output_is_non_ranking({"candidate_id": "cand-a", "score": 87})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
uv run pytest tests/test_election_workpaper_export.py -v
```

Expected: FAIL because export and guardrail modules do not exist.

- [ ] **Step 3: Implement guardrails and export rows**

Create `src/election_workpaper/guardrails.py`:

```python
FORBIDDEN_PUBLIC_FIELDS = {
    "score",
    "rank",
    "ranking",
    "grade",
    "tier",
    "recommendation",
    "recommended_candidate",
    "best_candidate",
    "win_probability",
}


def assert_public_output_is_non_ranking(payload: object) -> None:
    if isinstance(payload, dict):
        forbidden = FORBIDDEN_PUBLIC_FIELDS.intersection(payload)
        if forbidden:
            field = sorted(forbidden)[0]
            raise ValueError(f"public output contains ranking-style field: {field}")
        for value in payload.values():
            assert_public_output_is_non_ranking(value)
    elif isinstance(payload, list):
        for item in payload:
            assert_public_output_is_non_ranking(item)
```

Create `src/election_workpaper/export.py`:

```python
import csv
import json
from pathlib import Path

from election_workpaper.guardrails import assert_public_output_is_non_ranking
from election_workpaper.models import PromiseClaim, ReviewStatus


def build_public_claim_rows(claims: list[PromiseClaim]) -> list[dict[str, str]]:
    rows = [
        {
            "claim_id": claim.claim_id,
            "candidate_id": claim.candidate_id,
            "contest_id": claim.contest_id,
            "summary": claim.summary,
            "policy_tags": ",".join(tag.value for tag in claim.policy_tags),
            "source_ids": ",".join(claim.source_ids),
            "review_status": claim.review_status.value,
        }
        for claim in claims
        if claim.review_status in {ReviewStatus.REVIEWED, ReviewStatus.CORRECTED}
    ]
    assert_public_output_is_non_ranking(rows)
    return rows


def write_public_json(rows: list[dict[str, str]], path: Path) -> None:
    assert_public_output_is_non_ranking(rows)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def write_public_csv(rows: list[dict[str, str]], path: Path) -> None:
    assert_public_output_is_non_ranking(rows)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
uv run pytest tests/test_election_workpaper_export.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/election_workpaper/guardrails.py src/election_workpaper/export.py tests/test_election_workpaper_export.py
git commit -m "feat: export non ranking public claim rows"
```

## Task 8: Static Workbench Renderer and End-to-End CLI

**Files:**
- Create: `src/election_workpaper/report_html.py`
- Modify: `src/election_workpaper/cli.py`
- Test: `tests/test_election_workpaper_cli.py`

- [ ] **Step 1: Write the failing end-to-end CLI test**

Create `tests/test_election_workpaper_cli.py`:

```python
from pathlib import Path

from typer.testing import CliRunner

from election_workpaper.cli import app


def test_build_workbench_generates_html_and_json(tmp_path):
    fixture = Path("tests/fixtures/election_workpaper/pilot_region.json")
    output_dir = tmp_path / "workbench"

    result = CliRunner().invoke(
        app,
        ["build-workbench", str(fixture), "--out", str(output_dir)],
    )

    assert result.exit_code == 0
    assert (output_dir / "workbench.html").exists()
    assert (output_dir / "claims.json").exists()
    html = (output_dir / "workbench.html").read_text(encoding="utf-8")
    assert "Election Workpaper" in html
    assert "마을버스 배차 간격" in html
    assert "score" not in html.lower()
    assert "rank" not in html.lower()
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
uv run pytest tests/test_election_workpaper_cli.py -v
```

Expected: FAIL because `build-workbench` command does not exist.

- [ ] **Step 3: Implement the HTML renderer**

Create `src/election_workpaper/report_html.py`:

```python
from html import escape

from election_workpaper.models import PromiseClaim


def render_workbench_html(claims: list[PromiseClaim]) -> str:
    rows = "\n".join(_claim_row(claim) for claim in claims)
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Election Workpaper</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 24px; color: #1f2933; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #d9e2ec; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f0f4f8; }}
    .tag {{ display: inline-block; margin-right: 4px; color: #334e68; }}
  </style>
</head>
<body>
  <h1>Election Workpaper</h1>
  <table>
    <thead>
      <tr>
        <th>Candidate</th>
        <th>Policy Tags</th>
        <th>Claim</th>
        <th>Sources</th>
        <th>Review</th>
      </tr>
    </thead>
    <tbody>
{rows}
    </tbody>
  </table>
</body>
</html>
"""


def _claim_row(claim: PromiseClaim) -> str:
    tags = " ".join(
        f'<span class="tag">{escape(tag.value)}</span>'
        for tag in claim.policy_tags
    )
    sources = ", ".join(escape(source_id) for source_id in claim.source_ids)
    return f"""      <tr>
        <td>{escape(claim.candidate_id)}</td>
        <td>{tags}</td>
        <td>{escape(claim.summary)}</td>
        <td>{sources}</td>
        <td>{escape(claim.review_status.value)}</td>
      </tr>"""
```

- [ ] **Step 4: Add the CLI command**

Replace `src/election_workpaper/cli.py` with:

```python
from pathlib import Path

import typer

from election_workpaper import __version__
from election_workpaper.classification import apply_classification
from election_workpaper.export import build_public_claim_rows, write_public_json
from election_workpaper.extraction import extract_claims
from election_workpaper.models import ReviewStatus
from election_workpaper.report_html import render_workbench_html
from election_workpaper.repository import load_region_fixture

app = typer.Typer(help="Evidence-based election pledge workpaper CLI.")


@app.command()
def version() -> None:
    """Print the Election Workpaper version."""
    typer.echo(f"election-workpaper {__version__}")


@app.command("build-workbench")
def build_workbench(fixture: Path, out: Path = typer.Option(..., "--out")) -> None:
    """Build a local static HTML workbench from a pilot fixture."""
    dataset = load_region_fixture(fixture)
    extracted = extract_claims(dataset)
    claims, _signals = apply_classification(extracted)
    reviewed_claims = [
        claim.model_copy(update={"review_status": ReviewStatus.REVIEWED})
        for claim in claims
    ]

    out.mkdir(parents=True, exist_ok=True)
    rows = build_public_claim_rows(reviewed_claims)
    write_public_json(rows, out / "claims.json")
    (out / "workbench.html").write_text(
        render_workbench_html(reviewed_claims),
        encoding="utf-8",
    )
    typer.echo(f"wrote {out / 'workbench.html'}")
```

- [ ] **Step 5: Run the end-to-end test**

Run:

```bash
uv run pytest tests/test_election_workpaper_cli.py -v
```

Expected: PASS.

- [ ] **Step 6: Run the complete Election Workpaper slice**

Run:

```bash
uv run pytest \
  tests/test_election_workpaper_package.py \
  tests/test_election_workpaper_models.py \
  tests/test_election_workpaper_repository.py \
  tests/test_election_workpaper_extraction.py \
  tests/test_election_workpaper_classification.py \
  tests/test_election_workpaper_comparison.py \
  tests/test_election_workpaper_export.py \
  tests/test_election_workpaper_cli.py \
  -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/election_workpaper/report_html.py src/election_workpaper/cli.py tests/test_election_workpaper_cli.py
git commit -m "feat: render election workpaper html workbench"
```

## Task 9: Whole-Repo Verification and Documentation Note

**Files:**
- Modify: `README.md`
- Test: whole repo test suite

- [ ] **Step 1: Add a short README section**

Append to `README.md`:

````markdown
## Adjacent Product Experiment: Election Workpaper

`election-workpaper` is a separate, fixture-backed experiment for an
evidence-based Korean local-election pledge workbench. It is intentionally
separate from the DART footing engine and does not score, rank, grade, or
recommend candidates.

```bash
election-workpaper build-workbench tests/fixtures/election_workpaper/pilot_region.json --out out/election_workpaper
```
````

- [ ] **Step 2: Run all tests**

Run:

```bash
uv run pytest
```

Expected: PASS. If unrelated pre-existing tests fail, record the failing test
names and rerun the Election Workpaper slice from Task 8 Step 6 to confirm the
new package is green.

- [ ] **Step 3: Manually build the workbench artifact**

Run:

```bash
uv run election-workpaper build-workbench tests/fixtures/election_workpaper/pilot_region.json --out out/election_workpaper
```

Expected: command prints `wrote out/election_workpaper/workbench.html`, and both
`out/election_workpaper/workbench.html` and `out/election_workpaper/claims.json`
exist.

- [ ] **Step 4: Commit**

```bash
git add README.md out/election_workpaper/workbench.html out/election_workpaper/claims.json
git commit -m "docs: document election workpaper mvp workflow"
```

## Self-Review

- Spec coverage: this plan covers region fixture loading, contest/candidate records, source evidence preservation, claim extraction, policy tagging, feasibility signals, non-ranking clusters, reviewer/public status, exports, and a local workbench. Live NEC API ingestion, PDF extraction, address mapping, hosted deployment, and public voter pages remain outside this first implementation plan by design.
- Placeholder scan: the plan contains no placeholder work items. Each task has concrete files, test commands, expected outcomes, and code snippets.
- Type consistency: the model names used across tasks are consistent: `ElectionArea`, `ElectionContest`, `Candidate`, `SourceEvidence`, `PromiseClaim`, `FeasibilitySignal`, `ComparisonCluster`, `PolicyTag`, `ReviewStatus`, and `FeasibilitySignalType`.
