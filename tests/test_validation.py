import json

from dart_footing_reconciler.validation import run_manifest


def test_run_manifest_validates_expected_summary(tmp_path) -> None:
    source = tmp_path / "manufacturing.html"
    source.write_text(
        """
        <p>9. 유형자산</p>
        <p>당기와 전기 중 발생한 유형자산의 취득, 처분 내역 및 장부금액은 다음과 같습니다.</p>
        <table>
          <tr><th>구분</th><th>합계</th></tr>
          <tr><td>기초 장부금액</td><td>1,000</td></tr>
          <tr><td>취득</td><td>500</td></tr>
          <tr><td>감가상각</td><td>(200)</td></tr>
          <tr><td>기말 장부금액</td><td>1,300</td></tr>
        </table>
        """,
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "samples": [
                    {
                        "name": "manufacturer-a",
                        "company": "Manufacturer A",
                        "industry": "manufacturing",
                        "tags": ["manufacturing", "ppe"],
                        "source": source.name,
                        "expected": {
                            "total": 1,
                            "matched": 1,
                            "unexplained_gap": 0,
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    report = run_manifest(manifest)

    assert report["summary"]["samples"] == 1
    assert report["summary"]["passed"] == 1
    assert report["samples"][0]["status"] == "passed"


def test_run_manifest_can_filter_manufacturing_tag(tmp_path) -> None:
    manufacturing = tmp_path / "manufacturing.html"
    manufacturing.write_text(
        """
        <p>9. 유형자산</p>
        <p>유형자산의 변동내용은 다음과 같습니다.</p>
        <table>
          <tr><th>구분</th><th>합계</th></tr>
          <tr><td>기초</td><td>100</td></tr>
          <tr><td>취득</td><td>50</td></tr>
          <tr><td>기말</td><td>150</td></tr>
        </table>
        """,
        encoding="utf-8",
    )
    finance = tmp_path / "finance.html"
    finance.write_text("<html></html>", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "samples": [
                    {"name": "mfg", "tags": ["manufacturing"], "source": manufacturing.name},
                    {"name": "fin", "tags": ["financial"], "source": finance.name},
                ]
            }
        ),
        encoding="utf-8",
    )

    report = run_manifest(manifest, tag="manufacturing")

    assert report["summary"]["samples"] == 1
    assert report["samples"][0]["name"] == "mfg"


def test_run_manifest_diagnostic_mode_uses_all_footable_tables(tmp_path) -> None:
    source = tmp_path / "equity.html"
    source.write_text(
        """
        <p>21. 자본금과 자본잉여금</p>
        <p>2) 자본금 및 주식발행초과금의 변동내용은 다음과 같습니다.</p>
        <table>
          <tr><th>구분</th><th>자본금</th></tr>
          <tr><td>기초</td><td>1,000</td></tr>
          <tr><td>증가</td><td>500</td></tr>
          <tr><td>기말</td><td>1,500</td></tr>
        </table>
        """,
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"samples": [{"name": "equity", "source": source.name}]}),
        encoding="utf-8",
    )

    conservative = run_manifest(manifest, mode="conservative")
    diagnostic = run_manifest(manifest, mode="diagnostic")

    assert conservative["samples"][0]["actual"]["total"] == 0
    assert diagnostic["samples"][0]["actual"]["total"] == 1
