from pathlib import Path

from election_workpaper.repository import load_region_fixture


FIXTURE = Path("tests/fixtures/election_workpaper/pilot_region.json")


def test_load_region_fixture_preserves_source_text():
    dataset = load_region_fixture(FIXTURE)

    assert dataset.areas[0].area_id == "seoul-jung"
    assert dataset.contests[0].name == "서울특별시 중구청장"
    assert len(dataset.candidates) == 2
    assert dataset.sources["pledge-a"].raw_text.startswith("구 예산 120억 원")
