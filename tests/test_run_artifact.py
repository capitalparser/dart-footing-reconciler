from pathlib import Path
from typing import Any

from dart_footing_reconciler.check_pipeline import assemble_report_checks
from dart_footing_reconciler.checks import ALL_STATUSES
from dart_footing_reconciler.document import parse_full_report
from dart_footing_reconciler.run_artifact import (
    RunArtifactMetadata,
    load_run_artifact,
    write_check_result_artifact,
)


INVENI = Path("out/corpus/run_2026-06-06-inveni-one/raw/inveni_2024_20250310000926.html")
AMOUNT_FIELDS = ("expected_amount", "actual_amount", "gap_amount", "tolerance")
ENTITY_KEY_FIELDS = ("account", "consolidation_basis", "report_period", "balance_level")


def _inveni_checks():
    report = parse_full_report(INVENI)
    return assemble_report_checks(report, None, tolerance=1)


def _write_inveni_artifact(path: Path):
    metadata = RunArtifactMetadata.from_source_file(INVENI, config={"tolerance": 1})
    write_check_result_artifact(_inveni_checks(), path, metadata=metadata)
    return load_run_artifact(path)


def _assert_no_float(value: Any) -> None:
    assert not isinstance(value, float)
    if isinstance(value, dict):
        for child in value.values():
            _assert_no_float(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_float(child)


def test_same_corpus_input_writes_byte_identical_artifact(tmp_path):
    first = tmp_path / "first.ndjson"
    second = tmp_path / "second.ndjson"

    first_artifact = _write_inveni_artifact(first)
    second_artifact = _write_inveni_artifact(second)

    assert first.read_bytes() == second.read_bytes()
    assert first_artifact.header["run_fingerprint"] == second_artifact.header["run_fingerprint"]


def test_artifact_represents_all_five_statuses_and_complete_entity_keys(tmp_path):
    artifact = _write_inveni_artifact(tmp_path / "canonical_check_results.ndjson")

    statuses = {row["status"] for row in artifact.results}

    assert set(ALL_STATUSES) <= statuses
    for row in artifact.results:
        assert tuple(row["entity_key"]) == ENTITY_KEY_FIELDS
        assert all(row["entity_key"][field] for field in ENTITY_KEY_FIELDS)


def test_artifact_amounts_are_canonical_decimal_strings_not_floats(tmp_path):
    artifact = _write_inveni_artifact(tmp_path / "canonical_check_results.ndjson")

    for row in artifact.results:
        _assert_no_float(row)
        for field in AMOUNT_FIELDS:
            amount = row[field]
            if amount is None:
                continue
            assert amount["scale"] == 0
            assert isinstance(amount["value"], str)
            int(amount["value"])


def test_artifact_header_records_unknown_version_sources_explicitly(tmp_path):
    artifact = _write_inveni_artifact(tmp_path / "canonical_check_results.ndjson")

    fingerprint_inputs = artifact.header["fingerprint_inputs"]

    assert fingerprint_inputs["engine_version"] != ""
    assert fingerprint_inputs["parser_version"] == "unknown"
    assert fingerprint_inputs["classifier_version"] == "unknown"
    assert fingerprint_inputs["rulepack_version"] == "unknown"
    assert fingerprint_inputs["normalization_policy_version"] == "unknown"
