import json
from pathlib import Path

import pytest

from election_workpaper.repository import load_region_fixture


FIXTURE = Path("tests/fixtures/election_workpaper/pilot_region.json")


def test_load_region_fixture_preserves_source_text():
    dataset = load_region_fixture(FIXTURE)

    assert len(dataset.areas) == 1
    assert dataset.areas[0].area_id == "seoul-jung"
    assert len(dataset.contests) == 1
    assert dataset.contests[0].name == "서울특별시 중구청장"
    assert len(dataset.candidates) == 2
    assert [candidate.candidate_id for candidate in dataset.candidates] == [
        "cand-a",
        "cand-b",
    ]
    assert len(dataset.sources) == 4
    official_pledge_source_ids = [
        source.source_id
        for source in dataset.sources.values()
        if source.source_type == "official_pledge"
    ]
    assert official_pledge_source_ids == ["pledge-a", "pledge-b"]
    assert dataset.sources["pledge-a"].raw_text.startswith("구 예산 120억 원")


def test_load_region_fixture_rejects_duplicate_source_ids(tmp_path):
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["sources"][1]["source_id"] = "profile-a"
    fixture = tmp_path / "duplicate_source.json"
    fixture.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate source_id.*profile-a"):
        load_region_fixture(fixture)


def test_load_region_fixture_rejects_contest_without_area(tmp_path):
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["contests"][0]["area_id"] = "missing-area"
    fixture = tmp_path / "missing_area.json"
    fixture.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="area_id.*missing-area"):
        load_region_fixture(fixture)


def test_load_region_fixture_rejects_candidate_without_contest(tmp_path):
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["candidates"][0]["contest_id"] = "missing-contest"
    fixture = tmp_path / "missing_contest.json"
    fixture.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="contest_id.*missing-contest"):
        load_region_fixture(fixture)


def test_load_region_fixture_rejects_candidate_profile_source_without_source(
    tmp_path,
):
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["candidates"][0]["profile_source_ids"]["career"] = "missing-profile"
    fixture = tmp_path / "missing_profile_source.json"
    fixture.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="profile_source_ids.*missing-profile"):
        load_region_fixture(fixture)
