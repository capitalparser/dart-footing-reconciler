from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_accuracy_strategy_separates_report_volume_from_accuracy():
    text = (ROOT / "docs/validation/verification-accuracy-strategy.md").read_text(
        encoding="utf-8"
    )

    assert "보고서 수는 정확도 지표가 아니다" in text
    for required in [
        "Gold Set",
        "Stratified Smoke",
        "Broad Corpus",
        "Adversarial Set",
        "false-match rate",
        "재무제표 본문-주석",
        "주석 내부",
        "현금흐름표-주석",
    ]:
        assert required in text
