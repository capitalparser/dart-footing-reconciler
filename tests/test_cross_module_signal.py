import json
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dart_footing_reconciler.cross_module import route_finding, write_signal
from dart_footing_reconciler.ledger import initialize_ledger


PRODUCED_AT = datetime(2026, 6, 28, 4, 30, tzinfo=UTC)


def _synthetic_finding(**overrides: Any) -> dict[str, Any]:
    finding = {
        "finding_id": "finding-lease-gap-001",
        "result_id": "result-lease-gap-001",
        "result_lineage_key": "lineage:lease_liabilities:separate:2025:noncurrent",
        "run_id": "run-stage2a-001",
        "run_fingerprint": "run-fingerprint-stage2a",
        "source_file_hash": "source-file-sha256-stage2a",
        "rulepack_version": "rulepack-2026-06",
        "status": "unexplained_gap",
        "account_key": "lease_liabilities",
        "consolidation_basis": "separate",
        "report_period": "2025-12-31",
        "balance_level": "noncurrent",
        "gap_amount": {"value": "125000000", "scale": 0},
        "source_locations": [
            {
                "role": "expected",
                "source": "statement:bs/table:0/row:8/col:2",
                "fingerprint": "src-fp-expected",
            },
            {
                "role": "actual",
                "source": "note:leases/table:2/row:5/col:4",
                "fingerprint": "src-fp-actual",
            },
        ],
        "difference_kind": "level_mismatch",
    }
    finding.update(overrides)
    return finding


def _write_signal(tmp_path: Path, finding: dict[str, Any]) -> tuple[dict[str, Any], sqlite3.Connection]:
    db_path = tmp_path / "ledger.sqlite"
    queue_dir = tmp_path / "queue"
    initialize_ledger(db_path)
    conn = sqlite3.connect(db_path)
    route_result = route_finding(finding)
    assert route_result is not None

    write_signal(route_result, PRODUCED_AT, queue_dir=queue_dir, conn=conn)

    envelope_files = sorted(queue_dir.glob("*.yaml"))
    assert len(envelope_files) == 1
    return json.loads(envelope_files[0].read_text(encoding="utf-8")), conn


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class FakeSignalConsumer:
    def __init__(self, *, now: datetime) -> None:
        self.now = now
        self.processed_keys: set[str] = set()
        self.active_signals: dict[str, dict[str, Any]] = {}

    def process(self, envelope: dict[str, Any]) -> str:
        if _parse_datetime(envelope["stale_after"]) <= self.now:
            return "stale"
        if envelope["idempotency_key"] in self.processed_keys:
            return "duplicate"

        superseded = envelope.get("supersedes_signal_id")
        if superseded:
            self.active_signals.pop(superseded, None)
        self.processed_keys.add(envelope["idempotency_key"])
        self.active_signals[envelope["signal_id"]] = envelope
        return "processed"


def _load_schema() -> dict[str, Any]:
    return json.loads(
        Path("schema/cross_module_signal.schema.json").read_text(encoding="utf-8")
    )


def _assert_json_schema_valid(value: Any, schema: dict[str, Any], path: str = "$") -> None:
    if "const" in schema:
        assert value == schema["const"], f"{path} expected const {schema['const']!r}"
    if "enum" in schema:
        assert value in schema["enum"], f"{path} not in enum {schema['enum']!r}"

    expected_type = schema.get("type")
    if expected_type is not None:
        types = expected_type if isinstance(expected_type, list) else [expected_type]
        assert any(_matches_json_type(value, json_type) for json_type in types), (
            f"{path} expected type {expected_type!r}, got {type(value).__name__}"
        )

    if schema.get("format") == "date-time":
        assert isinstance(value, str)
        _parse_datetime(value)
    if "pattern" in schema and isinstance(value, str):
        assert re.fullmatch(schema["pattern"], value), f"{path} does not match pattern"

    if isinstance(value, dict):
        required = schema.get("required", [])
        for field in required:
            assert field in value, f"{path} missing required field {field!r}"

        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extras = sorted(set(value) - set(properties))
            assert not extras, f"{path} has unexpected fields {extras!r}"
        for field, field_schema in properties.items():
            if field in value:
                _assert_json_schema_valid(value[field], field_schema, f"{path}.{field}")

    if isinstance(value, list):
        if "minItems" in schema:
            assert len(value) >= schema["minItems"], f"{path} has too few items"
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                _assert_json_schema_valid(item, item_schema, f"{path}[{index}]")


def _matches_json_type(value: Any, json_type: str) -> bool:
    if json_type == "object":
        return isinstance(value, dict)
    if json_type == "array":
        return isinstance(value, list)
    if json_type == "string":
        return isinstance(value, str)
    if json_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if json_type == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    if json_type == "boolean":
        return isinstance(value, bool)
    if json_type == "null":
        return value is None
    raise AssertionError(f"unsupported schema type: {json_type}")


def test_route_finding_routes_only_lease_unexplained_gap_and_abstains_conservatively() -> None:
    route_result = route_finding(_synthetic_finding())
    assert route_result is not None
    assert route_result.destination_module == "erp_recon"
    assert route_result.signal_type == "journal_drilldown_required"

    abstain_cases = [
        _synthetic_finding(status="parse_uncertain"),
        _synthetic_finding(status="matched"),
        _synthetic_finding(account_key="borrowings"),
        _synthetic_finding(balance_level="unknown"),
        _synthetic_finding(report_period=""),
    ]
    for finding in abstain_cases:
        assert route_finding(finding) is None


def test_route_finding_routes_consolidated_lease_gap_to_bridge_candidate() -> None:
    route_result = route_finding(_synthetic_finding(consolidation_basis="consolidated"))
    assert route_result is not None
    assert route_result.destination_module != "erp_recon"
    assert route_result.signal_type == "consolidation_bridge_drilldown_candidate"


def test_generated_envelope_conforms_to_schema_and_reaches_db_and_queue(
    tmp_path: Path,
) -> None:
    envelope, conn = _write_signal(tmp_path, _synthetic_finding())
    try:
        _assert_json_schema_valid(envelope, _load_schema())

        row = conn.execute(
            """
            SELECT signal_id, run_id, finding_id, result_id, destination_module,
                   signal_type, payload_json, produced_at, supersedes_signal_id
            FROM cross_module_signals
            """
        ).fetchone()
        assert row is not None
        assert row[0] == envelope["signal_id"]
        assert row[1] == envelope["run_id"]
        assert row[2] == envelope["finding_id"]
        assert row[3] == envelope["result_id"]
        assert row[4] == "erp_recon"
        assert row[5] == "journal_drilldown_required"
        assert row[7] == envelope["produced_at"]
        assert row[8] is None

        payload = json.loads(row[6])
        assert payload == envelope["payload"]
        assert payload["entity_key"] == {
            "account": "lease_liabilities",
            "consolidation_basis": "separate",
            "report_period": "2025-12-31",
            "balance_level": "noncurrent",
        }
        assert payload["difference_kind"] == "level_mismatch"
        assert payload["source_locations"][0]["fingerprint"] == "src-fp-expected"
        assert envelope["payload_hash"] == route_finding(_synthetic_finding()).payload_hash

        consumer = FakeSignalConsumer(now=PRODUCED_AT)
        assert consumer.process(envelope) == "processed"
        assert envelope["signal_id"] in consumer.active_signals
    finally:
        conn.close()


def test_write_signal_is_idempotent_for_duplicate_idempotency_key(tmp_path: Path) -> None:
    db_path = tmp_path / "ledger.sqlite"
    queue_dir = tmp_path / "queue"
    initialize_ledger(db_path)
    conn = sqlite3.connect(db_path)
    try:
        route_result = route_finding(_synthetic_finding())
        assert route_result is not None

        write_signal(route_result, PRODUCED_AT, queue_dir=queue_dir, conn=conn)
        write_signal(route_result, PRODUCED_AT, queue_dir=queue_dir, conn=conn)

        assert conn.execute("SELECT COUNT(*) FROM cross_module_signals").fetchone()[0] == 1
        envelope_files = sorted(queue_dir.glob("*.yaml"))
        assert len(envelope_files) == 1

        envelope = json.loads(envelope_files[0].read_text(encoding="utf-8"))
        consumer = FakeSignalConsumer(now=PRODUCED_AT)
        assert consumer.process(envelope) == "processed"
        assert consumer.process(envelope) == "duplicate"
        assert len(consumer.active_signals) == 1
    finally:
        conn.close()


def test_write_signal_preserves_supersede_semantics(tmp_path: Path) -> None:
    db_path = tmp_path / "ledger.sqlite"
    queue_dir = tmp_path / "queue"
    initialize_ledger(db_path)
    conn = sqlite3.connect(db_path)
    try:
        original = route_finding(_synthetic_finding())
        assert original is not None
        replacement = route_finding(
            _synthetic_finding(
                finding_id="finding-lease-gap-002",
                result_id="result-lease-gap-002",
                supersedes_signal_id=original.signal_id,
            )
        )
        assert replacement is not None

        write_signal(original, PRODUCED_AT, queue_dir=queue_dir, conn=conn)
        write_signal(replacement, PRODUCED_AT, queue_dir=queue_dir, conn=conn)

        envelopes = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(queue_dir.glob("*.yaml"))
        ]
        original_envelope = [
            envelope for envelope in envelopes if envelope["signal_id"] == original.signal_id
        ][0]
        replacement_envelope = [
            envelope for envelope in envelopes if envelope["signal_id"] == replacement.signal_id
        ][0]
        assert replacement_envelope["supersedes_signal_id"] == original.signal_id

        consumer = FakeSignalConsumer(now=PRODUCED_AT)
        assert consumer.process(original_envelope) == "processed"
        assert consumer.process(replacement_envelope) == "processed"
        assert original.signal_id not in consumer.active_signals
        assert replacement.signal_id in consumer.active_signals
    finally:
        conn.close()


def test_stale_after_is_present_parseable_and_stale_envelope_is_skipped(
    tmp_path: Path,
) -> None:
    envelope, conn = _write_signal(
        tmp_path,
        _synthetic_finding(stale_after_days=-1),
    )
    try:
        assert "stale_after" in envelope
        stale_after = _parse_datetime(envelope["stale_after"])
        assert stale_after < PRODUCED_AT

        consumer = FakeSignalConsumer(now=PRODUCED_AT)
        assert consumer.process(envelope) == "stale"
        assert not consumer.active_signals
    finally:
        conn.close()


def test_atomic_write_does_not_leave_tmp_files(tmp_path: Path) -> None:
    queue_dir = tmp_path / "queue"
    envelope, conn = _write_signal(tmp_path, _synthetic_finding())
    try:
        assert envelope["signal_id"]
        assert not list(queue_dir.glob("*.tmp"))
        assert not list(queue_dir.glob("*.yaml.*"))
    finally:
        conn.close()


def test_write_signal_restores_missing_queue_file_without_duplicate_row(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "ledger.sqlite"
    queue_dir = tmp_path / "queue"
    initialize_ledger(db_path)
    conn = sqlite3.connect(db_path)
    try:
        route_result = route_finding(_synthetic_finding())
        assert route_result is not None
        write_signal(route_result, PRODUCED_AT, queue_dir=queue_dir, conn=conn)

        envelope_path = next(queue_dir.glob("*.yaml"))
        envelope_path.unlink()

        write_signal(route_result, PRODUCED_AT, queue_dir=queue_dir, conn=conn)

        assert conn.execute("SELECT COUNT(*) FROM cross_module_signals").fetchone()[0] == 1
        restored_files = sorted(queue_dir.glob("*.yaml"))
        assert len(restored_files) == 1
        restored = json.loads(restored_files[0].read_text(encoding="utf-8"))
        assert restored["signal_id"] == route_result.signal_id
    finally:
        conn.close()
