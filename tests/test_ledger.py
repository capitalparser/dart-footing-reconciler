import ast
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

from dart_footing_reconciler.audit_workbook import export_audit_workbook
from dart_footing_reconciler.check_pipeline import assemble_report_checks
from dart_footing_reconciler.checks import (
    ALL_STATUSES,
    EXPLAINABLE_GAP,
    MATCHED,
    NOT_TESTED,
    PARSE_UNCERTAIN,
    UNEXPLAINED_GAP,
    CheckEvidence,
    CheckResult,
)
from dart_footing_reconciler.document import (
    FullReport,
    ReportBlock,
    ReportSection,
    ReportTable,
    SourceLocation,
)
from dart_footing_reconciler.report_html import export_audit_reconciliation_html
from dart_footing_reconciler.run_artifact import (
    RunArtifactMetadata,
    canonical_result_fingerprints,
    load_run_artifact,
    write_check_result_artifact,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from check_per_company_snapshot import compute_drift  # noqa: E402


CORE_MODULES = ("check_pipeline", "checks", "corpus", "document", "cli")
MATCH_AND_GAP_STATUSES = {MATCHED, EXPLAINABLE_GAP, UNEXPLAINED_GAP}


def _synthetic_metadata() -> RunArtifactMetadata:
    return RunArtifactMetadata(
        source_file_hash="synthetic-source-sha256",
        canonical_input_hash="synthetic-canonical-input-sha256",
        config_hash="synthetic-config-sha256",
        engine_version="test-engine",
        parser_version="synthetic-parser",
        classifier_version="synthetic-classifier",
        rulepack_version="synthetic-rulepack",
        normalization_policy_version="synthetic-normalization",
        source_doc_identity="synthetic://ledger-fixture",
    )


def _synthetic_checks() -> list[CheckResult]:
    return [
        CheckResult(
            check_id="fs_note:current:ppe_total",
            check_type="fs_note_match",
            status=MATCHED,
            scope="report",
            note_no="11",
            title="current ppe total",
            expected=1000,
            actual=1000,
            difference=0,
            tolerance=1,
            reason="current financial statement amount agrees to note amount",
            evidence=[
                CheckEvidence(
                    "statement ppe", 1000, "statement:bs/table:0/row:2/col:1", "expected"
                ),
                CheckEvidence("note ppe", 1000, "note:11/table:0/row:1/col:1", "actual"),
            ],
        ),
        CheckResult(
            check_id="cfs_note:current:ppe_additions",
            check_type="cashflow_reconciliation",
            status=EXPLAINABLE_GAP,
            scope="report",
            note_no="11",
            title="current ppe acquisitions",
            expected=-250,
            actual=-240,
            difference=10,
            tolerance=1,
            reason="classification difference explained by non-cash acquisition",
            evidence=[
                CheckEvidence(
                    "cash flow ppe acquisition",
                    -250,
                    "statement:cf/table:0/row:1/col:1",
                    "expected",
                ),
                CheckEvidence("note ppe addition", -240, "note:11/table:0/row:2/col:1", "actual"),
            ],
        ),
        CheckResult(
            check_id="note_total:current:ppe_rollforward_total",
            check_type="total_check",
            status=UNEXPLAINED_GAP,
            scope="note",
            note_no="11",
            title="current ppe movement total",
            expected=1150,
            actual=1100,
            difference=-50,
            tolerance=1,
            reason="current note movement total does not foot",
            evidence=[
                CheckEvidence(
                    "note opening plus additions",
                    1150,
                    "note:11/table:0/row:3/col:1",
                    "expected",
                ),
                CheckEvidence("note reported total", 1100, "note:11/table:0/row:4/col:1", "actual"),
            ],
        ),
        CheckResult(
            check_id="statement_cash_tie:current:cash_total",
            check_type="statement_cash_tie",
            status=PARSE_UNCERTAIN,
            scope="report",
            note_no="cf",
            title="current cash total",
            expected=500,
            actual=490,
            difference=-10,
            tolerance=1,
            reason="cash equivalent label was ambiguous",
            evidence=[
                CheckEvidence(
                    "cash flow ending cash",
                    500,
                    "statement:cf/table:0/row:2/col:1",
                    "expected",
                ),
                CheckEvidence(
                    "balance sheet cash",
                    490,
                    "statement:bs/table:0/row:1/col:1",
                    "actual",
                ),
            ],
            parse_uncertain_reason="LABEL_NOT_FOUND",
        ),
        CheckResult(
            check_id="prior_report:current:ppe_prior_total",
            check_type="prior_column_rollforward",
            status=NOT_TESTED,
            scope="report",
            note_no="11",
            title="current ppe prior total",
            expected=900,
            actual=900,
            difference=0,
            tolerance=1,
            reason="prior report fixture intentionally absent",
            evidence=[
                CheckEvidence("current note prior column", 900, "note:11/table:0/row:1/col:2"),
                CheckEvidence("current note current column", 1000, "note:11/table:0/row:1/col:1"),
            ],
        ),
    ]


def _table(section_id: str, index: int, rows: list[list[str]], heading: str) -> ReportTable:
    location = SourceLocation(section_id, 0, index)
    return ReportTable(index, rows, heading, location)


def _section(
    section_id: str,
    title: str,
    kind: str,
    note_no: str,
    rows: list[list[str]],
) -> ReportSection:
    table = _table(section_id, 0, rows, title)
    return ReportSection(
        section_id=section_id,
        title=title,
        kind=kind,
        note_no=note_no,
        blocks=[ReportBlock("table", "", table, table.location)],
    )


def _synthetic_report() -> FullReport:
    balance_sheet = _section(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        [
            ["구분", "당기"],
            ["현금및현금성자산", "490"],
            ["유형자산", "1,000"],
            ["자산총계", "1,500"],
            ["부채총계", "800"],
            ["자본총계", "700"],
        ],
    )
    cash_flow = _section(
        "statement:cf",
        "현금흐름표",
        "statement",
        "",
        [
            ["구분", "당기"],
            ["유형자산의 취득", "(250)"],
            ["기말의 현금및현금성자산", "500"],
        ],
    )
    note = _section(
        "note:11",
        "유형자산",
        "note",
        "11",
        [
            ["구분", "당기", "전기"],
            ["장부금액", "1,000", "900"],
            ["취득", "240", "200"],
            ["기초+취득", "1,150", "1,100"],
            ["보고 합계", "1,100", "1,050"],
        ],
    )
    return FullReport(
        source="synthetic-ledger-fixture.html",
        company="Synthetic Ledger Co",
        statements=[balance_sheet, cash_flow],
        notes=[note],
    )


def _write_synthetic_artifact(path: Path, checks: list[CheckResult] | None = None) -> Path:
    return write_check_result_artifact(
        checks or _synthetic_checks(),
        path,
        metadata=_synthetic_metadata(),
    )


def _fingerprints_ndjson(path: Path) -> bytes:
    return ("\n".join(canonical_result_fingerprints(path)) + "\n").encode("utf-8")


def _check_signature(checks: list[CheckResult]) -> list[dict[str, object]]:
    rows = []
    for check in checks:
        rows.append(
            {
                "check_id": check.check_id,
                "check_type": check.check_type,
                "status": check.status,
                "scope": check.scope,
                "note_no": check.note_no,
                "title": check.title,
                "expected": check.expected,
                "actual": check.actual,
                "difference": check.difference,
                "tolerance": check.tolerance,
                "reason": check.reason,
                "parse_uncertain_reason": check.parse_uncertain_reason,
                "evidence": [
                    {
                        "label": evidence.label,
                        "amount": evidence.amount,
                        "source": evidence.source,
                        "role": evidence.role,
                    }
                    for evidence in check.evidence
                ],
            }
        )
    return sorted(rows, key=lambda row: (str(row["check_id"]), str(row["status"])))


def _matched_and_gap_keyset(
    checks: list[CheckResult],
) -> set[tuple[str, str, str, int | None, int | None, int | None]]:
    return {
        (
            check.check_id,
            check.check_type,
            check.status,
            check.expected,
            check.actual,
            check.difference,
        )
        for check in checks
        if check.status in MATCH_AND_GAP_STATUSES
    }


def _schema_sql(db_path: Path) -> str:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT sql FROM sqlite_schema WHERE sql IS NOT NULL ORDER BY type, name"
        ).fetchall()
    return "\n".join(row[0] for row in rows)


def test_full_result_fingerprints_are_identical_with_ledger_enabled(tmp_path):
    from dart_footing_reconciler.ledger import materialize_run_artifact

    disabled_artifact = _write_synthetic_artifact(tmp_path / "disabled.ndjson")
    enabled_artifact = _write_synthetic_artifact(tmp_path / "enabled.ndjson")
    disabled_loaded = load_run_artifact(disabled_artifact)
    enabled_loaded = load_run_artifact(enabled_artifact)
    before = _fingerprints_ndjson(disabled_artifact)

    assert disabled_loaded.header["result_count"] == len(_synthetic_checks())
    assert enabled_loaded.header["result_count"] == disabled_loaded.header["result_count"]
    assert _fingerprints_ndjson(enabled_artifact) == before

    result = materialize_run_artifact(
        enabled_artifact,
        tmp_path / "result-ledger.sqlite",
        rule_catalog_snapshot=[{"attempt_id": "fixture-only-snapshot"}],
    )

    assert result.success is True
    assert _fingerprints_ndjson(enabled_artifact) == before

    with sqlite3.connect(tmp_path / "result-ledger.sqlite") as conn:
        stored_statuses = {
            row[0] for row in conn.execute("SELECT DISTINCT status FROM check_results")
        }
        assert set(ALL_STATUSES) <= stored_statuses
        assert conn.execute("SELECT COUNT(*) FROM result_evidence").fetchone()[0] == 10
        assert conn.execute("SELECT COUNT(*) FROM cross_module_signals").fetchone()[0] == 0
        finding_statuses = {
            row[0] for row in conn.execute("SELECT DISTINCT core_status FROM findings")
        }
        coverage_statuses = {
            row[0]
            for row in conn.execute("SELECT DISTINCT status FROM coverage_observations")
        }
        assert finding_statuses == {UNEXPLAINED_GAP, PARSE_UNCERTAIN}
        assert coverage_statuses == {MATCHED, NOT_TESTED}
        # Intentional per the brief: explainable_gap is stored as a check_result only,
        # not projected into findings or coverage_observations.
        assert EXPLAINABLE_GAP not in finding_statuses
        assert EXPLAINABLE_GAP not in coverage_statuses

    schema = _schema_sql(tmp_path / "result-ledger.sqlite").upper()
    assert "REAL" not in schema
    for forbidden in ("SUM(", "AVG(", "ROUND("):
        assert forbidden not in schema

    def fail_followup(_row):
        raise RuntimeError("follow-up generator unavailable")

    materialize_run_artifact(
        enabled_artifact,
        tmp_path / "followup-error.sqlite",
        followup_generator=fail_followup,
    )
    with sqlite3.connect(tmp_path / "followup-error.sqlite") as conn:
        exception_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM check_results
            WHERE status IN ('unexplained_gap', 'parse_uncertain')
            """
        ).fetchone()[0]
        finding_errors = [
            row[0]
            for row in conn.execute(
                """
                SELECT followup_generation_error
                FROM findings
                """
            )
        ]
    assert len(finding_errors) == exception_count
    assert finding_errors == [1] * exception_count


def test_core_modules_do_not_import_ledger_sqlite_or_materializer():
    forbidden_modules = {"ledger", "sqlite3", "materializer"}
    package_root = Path("src/dart_footing_reconciler")

    for module_name in CORE_MODULES:
        source = (package_root / f"{module_name}.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[-1] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[-1])
        assert not (imports & forbidden_modules), module_name

    imported_before = set(sys.modules)
    for module_name in CORE_MODULES:
        __import__(f"dart_footing_reconciler.{module_name}")
    imported_after = set(sys.modules) - imported_before
    assert "dart_footing_reconciler.ledger" not in imported_after


def test_ledger_write_failure_is_operational_event_and_does_not_change_core_outputs(
    tmp_path, monkeypatch
):
    from dart_footing_reconciler import ledger

    report = _synthetic_report()
    checks = _synthetic_checks()
    artifact = _write_synthetic_artifact(tmp_path / "canonical_check_results.ndjson", checks)
    html_path = export_audit_reconciliation_html(report, checks, tmp_path / "report.html")
    excel_path = export_audit_workbook(report, checks, tmp_path / "workpaper.xlsx")
    status_counts = Counter(check.status for check in checks)
    signature = _check_signature(checks)
    html_bytes = html_path.read_bytes()
    excel_bytes = excel_path.read_bytes()
    fingerprints = canonical_result_fingerprints(artifact)

    def fail_connect(*_args, **_kwargs):
        raise sqlite3.OperationalError("simulated sqlite write failure")

    monkeypatch.setattr(ledger.sqlite3, "connect", fail_connect)

    result = ledger.materialize_run_artifact_safely(artifact, tmp_path / "broken.sqlite")

    assert result.success is False
    assert [event.event_type for event in result.operational_events] == [
        "ledger_materialization_failed"
    ]
    assert result.result_fingerprints == tuple(fingerprints)
    after_checks = _synthetic_checks()
    assert set(status_counts) == set(ALL_STATUSES)
    assert Counter(check.status for check in after_checks) == status_counts
    assert _check_signature(after_checks) == signature
    assert html_path.read_bytes() == html_bytes
    assert excel_path.read_bytes() == excel_bytes


def test_rule_catalog_snapshot_is_written_but_core_coverage_is_not_db_driven(
    tmp_path, monkeypatch
):
    from dart_footing_reconciler import ledger

    artifact = _write_synthetic_artifact(tmp_path / "canonical_check_results.ndjson")
    bogus_snapshot = [
        {"attempt_id": "only_rule_that_would_exist_if_db_drove_coverage", "enabled": True}
    ]

    ledger.materialize_run_artifact(
        artifact,
        tmp_path / "coverage.sqlite",
        rule_catalog_snapshot=bogus_snapshot,
    )

    with sqlite3.connect(tmp_path / "coverage.sqlite") as conn:
        stored = conn.execute(
            "SELECT rule_catalog_snapshot_json FROM validation_runs"
        ).fetchone()[0]
    assert json.loads(stored) == bogus_snapshot

    report = _synthetic_report()
    normal_checks = assemble_report_checks(report, None, tolerance=1)
    normal_count = len(normal_checks)
    normal_signature = _check_signature(normal_checks)
    assert normal_count > 0

    def fail_if_core_reads_sqlite(*_args, **_kwargs):
        raise AssertionError("core attempted to read the ledger")

    monkeypatch.setattr(sqlite3, "connect", fail_if_core_reads_sqlite)

    after_checks = assemble_report_checks(report, None, tolerance=1)
    assert len(after_checks) == normal_count
    assert _check_signature(after_checks) == normal_signature


def test_corpus_hard_gate_baselines_and_check_level_sets_stay_unchanged(tmp_path):
    from dart_footing_reconciler.ledger import materialize_run_artifact

    for baseline_path in (
        Path("tests/baselines/per_company_counts.json"),
        Path("tests/baselines/per_company_counts_2026-06-22-expansion.json"),
    ):
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        assert compute_drift(baseline, baseline) == []

    checks = _synthetic_checks()
    before_set = _matched_and_gap_keyset(checks)
    artifact = _write_synthetic_artifact(tmp_path / "canonical_check_results.ndjson", checks)

    materialize_run_artifact(artifact, tmp_path / "ledger.sqlite")

    after_checks = _synthetic_checks()
    assert _matched_and_gap_keyset(after_checks) == before_set
