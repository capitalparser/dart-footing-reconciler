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


def test_report_verification_contract_documents_validation_lanes_and_status():
    text = (ROOT / "docs/validation/report-verification-contract.md").read_text(
        encoding="utf-8"
    )

    for required in [
        "재무제표 본문 검증",
        "재무제표와 주석간 대사",
        "현금흐름표와 주석 대사",
        "주석 내 검산",
        "주석 간 대사",
        "전기 숫자 검증",
        "검증 QA",
        "CheckEvidence",
        "component",
        "total",
        "ending",
        "not_tested",
        "백엔드-프론트 표시 계약",
    ]:
        assert required in text


def test_readme_and_agents_reference_report_verification_contract():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    contract_path = "docs/validation/report-verification-contract.md"
    assert contract_path in readme
    assert contract_path in agents
    assert "Every check returns one of five statuses" in readme
    assert "Validation Intent Contract" in agents
