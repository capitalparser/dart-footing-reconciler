"""Stage 1A run-artifact tests — fully synthetic fixtures (no gitignored corpus).

Mirrors the project's convention of reproducing real structure with synthetic
fixtures (architecture-overview §2.4); must pass with out/corpus absent (ADR-0017 M1).
"""

from pathlib import Path

import pytest

import dart_footing_reconciler.run_artifact as run_artifact
from dart_footing_reconciler.checks import (
    EXPLAINABLE_GAP,
    MATCHED,
    NOT_TESTED,
    PARSE_UNCERTAIN,
    UNEXPLAINED_GAP,
    CheckEvidence,
    CheckResult,
)
from dart_footing_reconciler.run_artifact import (
    UNKNOWN,
    RunArtifactMetadata,
    _amount,
    load_run_artifact,
    write_check_result_artifact,
)


def _metadata(**overrides) -> RunArtifactMetadata:
    base = dict(
        source_file_hash="synthetic-source-sha256",
        canonical_input_hash="synthetic-canonical-input-sha256",
        config_hash="synthetic-config-sha256",
        engine_version="test-engine",
        parser_version="synthetic-parser",
        classifier_version="synthetic-classifier",
        rulepack_version="synthetic-rulepack",
        normalization_policy_version="synthetic-normalization",
        source_doc_identity="synthetic://run-artifact-fixture",
    )
    base.update(overrides)
    return RunArtifactMetadata(**base)


def _check(
    check_id,
    status,
    *,
    title="syn",
    scope="report",
    note_no="11",
    expected=100,
    actual=100,
    difference=0,
    tolerance=1,
    reason="syn",
    parse_uncertain_reason=None,
    evidence=None,
    account_key=None,
    consolidation_basis=None,
    report_period=None,
    balance_level=None,
) -> CheckResult:
    entity_kwargs = {}
    if account_key is not None:
        entity_kwargs["account_key"] = account_key
    if consolidation_basis is not None:
        entity_kwargs["consolidation_basis"] = consolidation_basis
    if report_period is not None:
        entity_kwargs["report_period"] = report_period
    if balance_level is not None:
        entity_kwargs["balance_level"] = balance_level
    return CheckResult(
        check_id=check_id,
        check_type="synthetic_check",
        status=status,
        scope=scope,
        note_no=note_no,
        title=title,
        expected=expected,
        actual=actual,
        difference=difference,
        tolerance=tolerance,
        reason=reason,
        parse_uncertain_reason=parse_uncertain_reason,
        evidence=evidence
        or [CheckEvidence("syn label", expected, "note:11/table:0/row:1/col:1", "expected")],
        **entity_kwargs,
    )


def _five_status_checks() -> list[CheckResult]:
    return [
        _check("fs_note:current:ppe", MATCHED, title="current ppe total",
               expected=1000, actual=1000, difference=0),
        _check("cfs_note:current:ppe_add", EXPLAINABLE_GAP, title="current ppe acquisitions",
               expected=-250, actual=-240, difference=10),
        _check("note_total:current:ppe_roll", UNEXPLAINED_GAP, title="current ppe movement total",
               expected=1150, actual=1100, difference=-50),
        _check("statement_cash_tie:current:cash", PARSE_UNCERTAIN, title="current cash total",
               expected=500, actual=490, difference=-10, parse_uncertain_reason="LABEL_NOT_FOUND"),
        _check("prior_report:ppe", NOT_TESTED, title="ppe prior total",
               expected=900, actual=900, difference=0,
               reason="prior report fixture intentionally absent"),
    ]


def _write(path: Path, checks=None, metadata=None) -> Path:
    return write_check_result_artifact(
        checks or _five_status_checks(), path, metadata=metadata or _metadata()
    )


def test_same_input_writes_byte_identical_artifact(tmp_path):
    a = _write(tmp_path / "a.ndjson")
    b = _write(tmp_path / "b.ndjson")
    assert a.read_bytes() == b.read_bytes()


def test_artifact_represents_all_five_statuses_and_entity_key_shape(tmp_path):
    artifact = load_run_artifact(_write(tmp_path / "art.ndjson"))
    assert artifact.header["result_count"] == 5
    statuses = {row["status"] for row in artifact.results}
    assert statuses == {MATCHED, EXPLAINABLE_GAP, UNEXPLAINED_GAP, PARSE_UNCERTAIN, NOT_TESTED}
    for row in artifact.results:
        assert set(row["entity_key"]) == {
            "account",
            "consolidation_basis",
            "report_period",
            "balance_level",
        }


def test_amounts_are_canonical_decimal_strings_not_floats(tmp_path):
    artifact = load_run_artifact(_write(tmp_path / "art.ndjson"))
    for row in artifact.results:
        for field in ("expected_amount", "actual_amount", "gap_amount", "tolerance"):
            amount = row[field]
            if amount is not None:
                assert set(amount) == {"value", "scale"}
                assert isinstance(amount["value"], str)
                assert isinstance(amount["scale"], int)
    with pytest.raises(TypeError):
        _amount(1.5)
    with pytest.raises(TypeError):
        _amount(True)


def test_header_records_unknown_version_sources_explicitly(tmp_path):
    src = tmp_path / "src.html"
    src.write_text("<html></html>", encoding="utf-8")
    md = RunArtifactMetadata.from_source_file(src, config={"tolerance": 1})
    artifact = load_run_artifact(_write(tmp_path / "art.ndjson", metadata=md))
    fingerprint_inputs = artifact.header["fingerprint_inputs"]
    for unsourced in (
        "parser_version",
        "classifier_version",
        "rulepack_version",
        "normalization_policy_version",
    ):
        assert fingerprint_inputs[unsourced] == UNKNOWN


def test_entity_key_reads_structured_check_result_fields(tmp_path):
    checks = [
        _check(
            "fs_note:lease_liabilities:17:noncurrent",
            MATCHED,
            title="리스부채 FS to note match (noncurrent)",
            scope="report",
            account_key="lease_liabilities",
            consolidation_basis="consolidated",
            report_period="current",
            balance_level="noncurrent",
        )
    ]
    row = load_run_artifact(_write(tmp_path / "art.ndjson", checks=checks)).results[0]
    assert row["entity_key"] == {
        "account": "lease_liabilities",
        "consolidation_basis": "consolidated",
        "report_period": "current",
        "balance_level": "noncurrent",
    }


def test_entity_key_string_inference_helpers_are_deleted():
    assert not hasattr(run_artifact, "_report_period")
    assert not hasattr(run_artifact, "_balance_level")


def test_result_id_does_not_collide_when_only_amounts_differ(tmp_path):
    # Same attempt/entity/evidence/status, different amounts -> distinct result_id,
    # because result_id includes full_result_fingerprint (ADR-0017). Without the fix
    # these would collide on the check_results primary key.
    evidence = [CheckEvidence("same label", 100, "note:11/table:0/row:1/col:1", "expected")]
    c1 = _check("dup:check", UNEXPLAINED_GAP, title="dup",
                expected=100, actual=90, difference=-10, evidence=evidence)
    c2 = _check("dup:check", UNEXPLAINED_GAP, title="dup",
                expected=100, actual=80, difference=-20, evidence=evidence)
    artifact = load_run_artifact(_write(tmp_path / "art.ndjson", checks=[c1, c2]))
    assert len({row["result_id"] for row in artifact.results}) == 2


def test_load_run_artifact_rejects_truncated_artifact(tmp_path):
    path = _write(tmp_path / "art.ndjson")
    lines = path.read_text(encoding="utf-8").splitlines()
    truncated = tmp_path / "truncated.ndjson"
    # Drop a check_result row but keep the header's declared result_count.
    truncated.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_run_artifact(truncated)


def test_engine_version_override_flows_into_fingerprint(tmp_path):
    src = tmp_path / "src.html"
    src.write_text("<html></html>", encoding="utf-8")
    md = RunArtifactMetadata.from_source_file(src, engine_version="explicit-build-42")
    assert md.engine_version == "explicit-build-42"
    artifact = load_run_artifact(_write(tmp_path / "art.ndjson", metadata=md))
    assert artifact.header["fingerprint_inputs"]["engine_version"] == "explicit-build-42"
