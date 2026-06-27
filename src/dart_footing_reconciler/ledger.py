"""SQLite result ledger materialized from sealed run artifacts only."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from dart_footing_reconciler.run_artifact import (
    canonical_result_fingerprints,
    hash_canonical,
    load_run_artifact,
)

LEDGER_SCHEMA_VERSION = "1.0"
FINDING_PROJECTION_VERSION = "stage1b.1"
EXCEPTION_STATUSES = {"unexplained_gap", "parse_uncertain"}
COVERAGE_STATUSES = {"matched", "not_tested"}

FollowupGenerator = Callable[[dict[str, Any]], str | list[str] | tuple[str, ...] | None]


@dataclass(frozen=True)
class OperationalEvent:
    event_type: str
    message: str
    details: dict[str, Any]


@dataclass(frozen=True)
class LedgerMaterializationResult:
    success: bool
    run_id: str | None
    result_fingerprints: tuple[str, ...]
    operational_events: tuple[OperationalEvent, ...] = ()


def initialize_ledger(db_path: str | Path) -> None:
    """Create the Stage 1B ledger schema without inserting run rows."""
    conn = sqlite3.connect(str(db_path))
    try:
        _initialize_schema(conn)
    finally:
        conn.close()


def materialize_run_artifact(
    artifact_path: str | Path,
    db_path: str | Path,
    *,
    rule_catalog_snapshot: Any = None,
    followup_generator: FollowupGenerator | None = None,
) -> LedgerMaterializationResult:
    """Materialize a sealed run artifact into SQLite.

    The only accepted input is the artifact path. This function reads the
    artifact through run_artifact.py and never consumes live result objects.
    """
    fingerprints = tuple(canonical_result_fingerprints(artifact_path))
    artifact = load_run_artifact(artifact_path)
    run_id = _run_id(artifact.header)
    conn = sqlite3.connect(str(db_path))
    try:
        _initialize_schema(conn)
        with conn:
            _delete_run_projection(conn, run_id)
            _insert_validation_run(conn, artifact.header, rule_catalog_snapshot)
            _insert_check_results(conn, artifact.results)
            _insert_result_evidence(conn, artifact.results)
            _insert_findings(conn, artifact.results, followup_generator)
            _insert_coverage_observations(conn, artifact.results)
    finally:
        conn.close()
    return LedgerMaterializationResult(
        success=True,
        run_id=run_id,
        result_fingerprints=fingerprints,
    )


def materialize_run_artifact_safely(
    artifact_path: str | Path,
    db_path: str | Path,
    *,
    rule_catalog_snapshot: Any = None,
    followup_generator: FollowupGenerator | None = None,
) -> LedgerMaterializationResult:
    """Materialize a run artifact and return an operational event on ledger failure."""
    fingerprints: tuple[str, ...] = ()
    try:
        fingerprints = tuple(canonical_result_fingerprints(artifact_path))
        return materialize_run_artifact(
            artifact_path,
            db_path,
            rule_catalog_snapshot=rule_catalog_snapshot,
            followup_generator=followup_generator,
        )
    except Exception as exc:  # noqa: BLE001 - ledger failure is intentionally isolated.
        return LedgerMaterializationResult(
            success=False,
            run_id=None,
            result_fingerprints=fingerprints,
            operational_events=(
                OperationalEvent(
                    event_type="ledger_materialization_failed",
                    message=str(exc),
                    details={
                        "artifact_path": str(artifact_path),
                        "db_path": str(db_path),
                        "error_type": type(exc).__name__,
                    },
                ),
            ),
        )


def _initialize_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS validation_runs (
            run_id TEXT PRIMARY KEY,
            run_fingerprint TEXT NOT NULL,
            artifact_schema_version TEXT NOT NULL,
            ledger_schema_version TEXT NOT NULL,
            source_file_hash TEXT NOT NULL,
            canonical_input_hash TEXT NOT NULL,
            engine_version TEXT NOT NULL,
            parser_version TEXT NOT NULL,
            classifier_version TEXT NOT NULL,
            rulepack_version TEXT NOT NULL,
            config_hash TEXT NOT NULL,
            normalization_policy_version TEXT NOT NULL,
            result_count INTEGER NOT NULL,
            rule_catalog_snapshot_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS check_results (
            result_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            run_fingerprint TEXT NOT NULL,
            full_result_fingerprint TEXT NOT NULL,
            result_lineage_key TEXT NOT NULL,
            attempt_id TEXT NOT NULL,
            rule_semantic_id TEXT NOT NULL,
            rule_version TEXT NOT NULL,
            account TEXT NOT NULL,
            consolidation_basis TEXT NOT NULL,
            report_period TEXT NOT NULL,
            balance_level TEXT NOT NULL,
            status TEXT NOT NULL,
            expected_amount_value TEXT,
            expected_amount_scale INTEGER,
            actual_amount_value TEXT,
            actual_amount_scale INTEGER,
            gap_amount_value TEXT,
            gap_amount_scale INTEGER,
            tolerance_value TEXT,
            tolerance_scale INTEGER,
            abstain_reason TEXT,
            parse_uncertain_reason TEXT,
            confidence_json TEXT NOT NULL,
            source_location_fingerprints_json TEXT NOT NULL,
            normalization_policy_id TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES validation_runs(run_id)
        );

        CREATE TABLE IF NOT EXISTS result_evidence (
            run_id TEXT NOT NULL,
            result_id TEXT NOT NULL,
            evidence_ordinal INTEGER NOT NULL,
            fact_id TEXT NOT NULL,
            original_label TEXT NOT NULL,
            normalized_amount_value TEXT,
            normalized_amount_scale INTEGER,
            unit TEXT NOT NULL,
            source_location TEXT NOT NULL,
            source_location_fingerprint TEXT NOT NULL,
            role TEXT NOT NULL,
            PRIMARY KEY(result_id, evidence_ordinal),
            FOREIGN KEY(run_id) REFERENCES validation_runs(run_id),
            FOREIGN KEY(result_id) REFERENCES check_results(result_id)
        );

        CREATE TABLE IF NOT EXISTS findings (
            finding_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            result_id TEXT NOT NULL,
            result_lineage_key TEXT NOT NULL,
            domain TEXT NOT NULL,
            account TEXT NOT NULL,
            core_status TEXT NOT NULL,
            finding_class TEXT NOT NULL,
            triage_reason TEXT NOT NULL,
            operational_priority TEXT NOT NULL,
            followup_json TEXT NOT NULL,
            followup_generation_error INTEGER NOT NULL,
            followup_generation_error_message TEXT,
            FOREIGN KEY(run_id) REFERENCES validation_runs(run_id),
            FOREIGN KEY(result_id) REFERENCES check_results(result_id)
        );

        CREATE TABLE IF NOT EXISTS coverage_observations (
            coverage_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            account TEXT NOT NULL,
            consolidation_basis TEXT NOT NULL,
            report_period TEXT NOT NULL,
            balance_level TEXT NOT NULL,
            status TEXT NOT NULL,
            observed_count INTEGER NOT NULL,
            result_digest TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES validation_runs(run_id)
        );

        CREATE TABLE IF NOT EXISTS reviewer_decisions (
            decision_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            result_id TEXT NOT NULL,
            result_lineage_key TEXT NOT NULL,
            core_status TEXT NOT NULL,
            review_status TEXT NOT NULL,
            reviewer TEXT,
            decision_reason TEXT,
            decided_at TEXT
        );

        CREATE TABLE IF NOT EXISTS cross_module_signals (
            signal_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            finding_id TEXT,
            result_id TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            destination_module TEXT,
            signal_type TEXT,
            payload_json TEXT,
            produced_at TEXT,
            supersedes_signal_id TEXT
        );

        CREATE VIEW IF NOT EXISTS v_findings_by_domain AS
            SELECT domain, core_status, COUNT(*) AS finding_count
            FROM findings
            GROUP BY domain, core_status
            ORDER BY domain, core_status;

        CREATE VIEW IF NOT EXISTS v_coverage_by_account AS
            SELECT
                run_id,
                account,
                consolidation_basis,
                report_period,
                balance_level,
                status,
                observed_count,
                result_digest
            FROM coverage_observations
            ORDER BY account, consolidation_basis, report_period, balance_level, status;

        CREATE VIEW IF NOT EXISTS v_pending_cross_module_signals AS
            SELECT
                signal_id,
                run_id,
                finding_id,
                result_id,
                destination_module,
                signal_type,
                payload_json,
                produced_at,
                supersedes_signal_id
            FROM cross_module_signals
            WHERE status = 'pending'
            ORDER BY run_id, signal_id;
        """
    )


def _delete_run_projection(conn: sqlite3.Connection, run_id: str) -> None:
    for table in ("coverage_observations", "findings", "result_evidence", "check_results"):
        conn.execute(f"DELETE FROM {table} WHERE run_id = ?", (run_id,))


def _insert_validation_run(
    conn: sqlite3.Connection,
    header: dict[str, Any],
    rule_catalog_snapshot: Any,
) -> None:
    fingerprint_inputs = header.get("fingerprint_inputs", {})
    run_id = _run_id(header)
    conn.execute(
        """
        INSERT OR REPLACE INTO validation_runs (
            run_id,
            run_fingerprint,
            artifact_schema_version,
            ledger_schema_version,
            source_file_hash,
            canonical_input_hash,
            engine_version,
            parser_version,
            classifier_version,
            rulepack_version,
            config_hash,
            normalization_policy_version,
            result_count,
            rule_catalog_snapshot_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            _text(header.get("run_fingerprint")),
            _text(header.get("artifact_schema_version")),
            LEDGER_SCHEMA_VERSION,
            _text(fingerprint_inputs.get("source_file_hash")),
            _text(fingerprint_inputs.get("canonical_input_hash")),
            _text(fingerprint_inputs.get("engine_version")),
            _text(fingerprint_inputs.get("parser_version")),
            _text(fingerprint_inputs.get("classifier_version")),
            _text(fingerprint_inputs.get("rulepack_version")),
            _text(fingerprint_inputs.get("config_hash")),
            _text(fingerprint_inputs.get("normalization_policy_version")),
            int(header.get("result_count") or 0),
            _canonical_json(rule_catalog_snapshot or []),
        ),
    )


def _insert_check_results(conn: sqlite3.Connection, results: list[dict[str, Any]]) -> None:
    for row in results:
        expected_value, expected_scale = _amount_pair(row.get("expected_amount"))
        actual_value, actual_scale = _amount_pair(row.get("actual_amount"))
        gap_value, gap_scale = _amount_pair(row.get("gap_amount"))
        tolerance_value, tolerance_scale = _amount_pair(row.get("tolerance"))
        entity_key = row.get("entity_key") or {}
        conn.execute(
            """
            INSERT INTO check_results (
                result_id,
                run_id,
                run_fingerprint,
                full_result_fingerprint,
                result_lineage_key,
                attempt_id,
                rule_semantic_id,
                rule_version,
                account,
                consolidation_basis,
                report_period,
                balance_level,
                status,
                expected_amount_value,
                expected_amount_scale,
                actual_amount_value,
                actual_amount_scale,
                gap_amount_value,
                gap_amount_scale,
                tolerance_value,
                tolerance_scale,
                abstain_reason,
                parse_uncertain_reason,
                confidence_json,
                source_location_fingerprints_json,
                normalization_policy_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _text(row.get("result_id")),
                _text(row.get("run_id")),
                _text(row.get("run_fingerprint")),
                _text(row.get("full_result_fingerprint")),
                _text(row.get("result_lineage_key")),
                _text(row.get("attempt_id")),
                _text(row.get("rule_semantic_id")),
                _text(row.get("rule_version")),
                _text(entity_key.get("account")),
                _text(entity_key.get("consolidation_basis")),
                _text(entity_key.get("report_period")),
                _text(entity_key.get("balance_level")),
                _text(row.get("status")),
                expected_value,
                expected_scale,
                actual_value,
                actual_scale,
                gap_value,
                gap_scale,
                tolerance_value,
                tolerance_scale,
                row.get("abstain_reason"),
                row.get("parse_uncertain_reason"),
                _canonical_json(row.get("confidence") or {}),
                _canonical_json(row.get("source_location_fingerprints") or []),
                _text(row.get("normalization_policy_id")),
            ),
        )


def _insert_result_evidence(conn: sqlite3.Connection, results: list[dict[str, Any]]) -> None:
    for row in results:
        for evidence_ordinal, fact in enumerate(row.get("evidence_facts") or []):
            amount_value, amount_scale = _amount_pair(fact.get("normalized_amount"))
            conn.execute(
                """
                INSERT INTO result_evidence (
                    run_id,
                    result_id,
                    evidence_ordinal,
                    fact_id,
                    original_label,
                    normalized_amount_value,
                    normalized_amount_scale,
                    unit,
                    source_location,
                    source_location_fingerprint,
                    role
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _text(row.get("run_id")),
                    _text(row.get("result_id")),
                    evidence_ordinal,
                    _text(fact.get("fact_id")),
                    _text(fact.get("original_label")),
                    amount_value,
                    amount_scale,
                    _text(fact.get("unit")),
                    _text(fact.get("source_location")),
                    _text(fact.get("source_location_fingerprint")),
                    _text(fact.get("role")),
                ),
            )


def _insert_findings(
    conn: sqlite3.Connection,
    results: list[dict[str, Any]],
    followup_generator: FollowupGenerator | None,
) -> None:
    for row in results:
        status = _text(row.get("status"))
        if status not in EXCEPTION_STATUSES:
            continue
        followups, error_message = _followups(row, followup_generator)
        entity_key = row.get("entity_key") or {}
        finding_class = "exception_projection"
        finding_id = hash_canonical(
            {
                "result_id": row.get("result_id"),
                "finding_projection_version": FINDING_PROJECTION_VERSION,
            }
        )
        conn.execute(
            """
            INSERT INTO findings (
                finding_id,
                run_id,
                result_id,
                result_lineage_key,
                domain,
                account,
                core_status,
                finding_class,
                triage_reason,
                operational_priority,
                followup_json,
                followup_generation_error,
                followup_generation_error_message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                finding_id,
                _text(row.get("run_id")),
                _text(row.get("result_id")),
                _text(row.get("result_lineage_key")),
                _text(row.get("rule_semantic_id")),
                _text(entity_key.get("account")),
                status,
                finding_class,
                _triage_reason(status),
                "review_queue",
                _canonical_json(followups),
                1 if error_message else 0,
                error_message,
            ),
        )


def _insert_coverage_observations(
    conn: sqlite3.Connection, results: list[dict[str, Any]]
) -> None:
    grouped: dict[tuple[str, str, str, str, str, str], list[str]] = {}
    for row in results:
        status = _text(row.get("status"))
        if status not in COVERAGE_STATUSES:
            continue
        entity_key = row.get("entity_key") or {}
        key = (
            _text(row.get("run_id")),
            _text(entity_key.get("account")),
            _text(entity_key.get("consolidation_basis")),
            _text(entity_key.get("report_period")),
            _text(entity_key.get("balance_level")),
            status,
        )
        grouped.setdefault(key, []).append(_text(row.get("full_result_fingerprint")))

    for key, fingerprints in grouped.items():
        run_id, account, consolidation_basis, report_period, balance_level, status = key
        result_digest = hash_canonical(sorted(fingerprints))
        coverage_id = hash_canonical(
            {
                "run_id": run_id,
                "account": account,
                "consolidation_basis": consolidation_basis,
                "report_period": report_period,
                "balance_level": balance_level,
                "status": status,
                "result_digest": result_digest,
            }
        )
        conn.execute(
            """
            INSERT INTO coverage_observations (
                coverage_id,
                run_id,
                account,
                consolidation_basis,
                report_period,
                balance_level,
                status,
                observed_count,
                result_digest
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                coverage_id,
                run_id,
                account,
                consolidation_basis,
                report_period,
                balance_level,
                status,
                len(fingerprints),
                result_digest,
            ),
        )


def _followups(
    row: dict[str, Any], followup_generator: FollowupGenerator | None
) -> tuple[list[str], str | None]:
    if followup_generator is None:
        return [_default_followup(row)], None
    try:
        generated = followup_generator(row)
    except Exception as exc:  # noqa: BLE001 - preserve the finding and flag generation failure.
        return [], f"{type(exc).__name__}: {exc}"
    if generated is None:
        return [], None
    if isinstance(generated, str):
        return [generated], None
    return [str(item) for item in generated], None


def _default_followup(row: dict[str, Any]) -> str:
    if row.get("status") == "parse_uncertain":
        return "Review parser/source-location evidence for this check result."
    return "Review source evidence and explain the unresolved difference."


def _triage_reason(status: str) -> str:
    if status == "parse_uncertain":
        return "low_parse_confidence"
    return "high_confidence_unexplained_gap"


def _amount_pair(amount: Any) -> tuple[str | None, int | None]:
    if amount is None:
        return None, None
    if not isinstance(amount, dict):
        raise TypeError("artifact amount must be a mapping or null")
    value = amount.get("value")
    scale = amount.get("scale")
    if isinstance(value, float) or isinstance(scale, float):
        raise TypeError("ledger amount storage forbids floating point values")
    if value is None:
        return None, int(scale or 0)
    return str(value), int(scale or 0)


def _run_id(header: dict[str, Any]) -> str:
    return _text(header.get("run_id") or header.get("run_fingerprint"))


def _text(value: Any) -> str:
    if value is None:
        return "unknown"
    return str(value)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
