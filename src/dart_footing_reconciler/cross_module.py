"""Stage 2A cross-module signal outbox.

This module is intentionally downstream of findings. It does not import
consumers, CLI entrypoints, or verdict-path modules.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Mapping

from dart_footing_reconciler.run_artifact import hash_canonical

SCHEMA_VERSION = "1.0"
ROUTING_VERSION = "stage2a.lease.1"
PRODUCER_MODULE = "09_dart_footing_reconciler"
DEFAULT_QUEUE_DIR = Path("out/cross_module_queue")
DEFAULT_STALE_AFTER_DAYS = 30

LEASE_ACCOUNT_KEY = "lease_liabilities"
UNEXPLAINED_GAP = "unexplained_gap"
PARSE_UNCERTAIN = "parse_uncertain"
UNKNOWN_VALUES = {"", "unknown", "none", "null"}


@dataclass(frozen=True)
class EntityKey:
    account: str
    consolidation_basis: str
    report_period: str
    balance_level: str

    def as_payload(self) -> dict[str, str]:
        return {
            "account": self.account,
            "consolidation_basis": self.consolidation_basis,
            "report_period": self.report_period,
            "balance_level": self.balance_level,
        }


@dataclass(frozen=True)
class RouteResult:
    signal_id: str
    idempotency_key: str
    dedupe_key: str
    run_id: str
    run_fingerprint: str
    source_file_hash: str
    rulepack_version: str
    finding_id: str
    result_id: str
    result_lineage_key: str
    destination_module: str
    signal_type: str
    payload: dict[str, Any]
    payload_hash: str
    supersedes_signal_id: str | None = None
    stale_after_days: int = DEFAULT_STALE_AFTER_DAYS


def route_finding(finding: Mapping[str, Any] | Any) -> RouteResult | None:
    """Route an in-scope Stage 2A finding to a cross-module signal."""
    status = _text(_field(finding, "status"))
    if status == PARSE_UNCERTAIN or status != UNEXPLAINED_GAP:
        return None

    entity_key = _entity_key(finding)
    if entity_key is None or entity_key.account != LEASE_ACCOUNT_KEY:
        return None
    if not _has_required_signal_fields(finding):
        return None

    gap_amount = _gap_amount(finding)
    if _is_missing(gap_amount):
        return None
    source_locations = _source_locations(finding)
    if not isinstance(source_locations, list) or not source_locations:
        return None

    if entity_key.consolidation_basis == "consolidated":
        return None
    if entity_key.consolidation_basis != "separate":
        return None

    destination_module = "erp_recon"
    signal_type = "journal_drilldown_required"

    finding_id = _required_text(_field(finding, "finding_id"))
    result_lineage_key = _required_text(_field(finding, "result_lineage_key"))
    signal_id = hash_canonical(
        {
            "finding_id": finding_id,
            "destination_module": destination_module,
            "signal_type": signal_type,
            "routing_version": ROUTING_VERSION,
        }
    )
    dedupe_key = hash_canonical(
        {
            "result_lineage_key": result_lineage_key,
            "destination_module": destination_module,
            "signal_type": signal_type,
            "routing_version": ROUTING_VERSION,
        }
    )
    payload = _payload(
        finding,
        entity_key,
        gap_amount=gap_amount,
        source_locations=source_locations,
    )
    payload_hash = hash_canonical(payload)

    return RouteResult(
        signal_id=signal_id,
        idempotency_key=signal_id,
        dedupe_key=dedupe_key,
        run_id=_required_text(_field(finding, "run_id")),
        run_fingerprint=_required_text(_field(finding, "run_fingerprint")),
        source_file_hash=_required_text(_field(finding, "source_file_hash")),
        rulepack_version=_required_text(_field(finding, "rulepack_version")),
        finding_id=finding_id,
        result_id=_required_text(_field(finding, "result_id")),
        result_lineage_key=result_lineage_key,
        destination_module=destination_module,
        signal_type=signal_type,
        payload=payload,
        payload_hash=payload_hash,
        supersedes_signal_id=_optional_text(_field(finding, "supersedes_signal_id")),
        stale_after_days=_stale_after_days(finding),
    )


def write_signal(
    route_result: RouteResult,
    produced_at: datetime,
    *,
    queue_dir: str | Path | None = None,
    conn: sqlite3.Connection | None = None,
) -> None:
    """Write the outbox row and atomic JSON envelope for a routed signal."""
    produced_at_utc = _utc(produced_at)
    output_dir = Path(queue_dir) if queue_dir is not None else DEFAULT_QUEUE_DIR
    envelope_path = output_dir / f"{route_result.signal_id}.json"

    if conn is not None:
        with conn:
            existing = conn.execute(
                """
                SELECT status
                FROM cross_module_signals
                WHERE signal_id = ?
                """,
                (route_result.signal_id,),
            ).fetchone()
            if existing is not None:
                if existing[0] == "pending" and not envelope_path.exists():
                    envelope_text = _envelope_text(route_result, produced_at_utc)
                    _atomic_write_text(
                        envelope_path,
                        envelope_text,
                        signal_id=route_result.signal_id,
                    )
                return

            supersedes_signal_id = conn.execute(
                """
                SELECT signal_id
                FROM cross_module_signals
                WHERE dedupe_key = ?
                  AND status = 'pending'
                  AND signal_id != ?
                LIMIT 1
                """,
                (route_result.dedupe_key, route_result.signal_id),
            ).fetchone()
            route_to_write = route_result
            if supersedes_signal_id is not None:
                old_signal_id = supersedes_signal_id[0]
                route_to_write = replace(route_result, supersedes_signal_id=old_signal_id)
                conn.execute(
                    """
                    UPDATE cross_module_signals
                    SET status = 'superseded'
                    WHERE signal_id = ?
                    """,
                    (old_signal_id,),
                )
                _remove_envelope_file(output_dir, old_signal_id)

            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO cross_module_signals (
                    signal_id,
                    dedupe_key,
                    run_id,
                    finding_id,
                    result_id,
                    status,
                    destination_module,
                    signal_type,
                    payload_json,
                    produced_at,
                    supersedes_signal_id
                )
                VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?)
                """,
                (
                    route_to_write.signal_id,
                    route_to_write.dedupe_key,
                    route_to_write.run_id,
                    route_to_write.finding_id,
                    route_to_write.result_id,
                    route_to_write.destination_module,
                    route_to_write.signal_type,
                    _canonical_json(route_to_write.payload),
                    _isoformat(produced_at_utc),
                    route_to_write.supersedes_signal_id,
                ),
            )
            if cursor.rowcount == 0:
                if not envelope_path.exists():
                    envelope_text = _envelope_text(route_to_write, produced_at_utc)
                    _atomic_write_text(
                        envelope_path,
                        envelope_text,
                        signal_id=route_to_write.signal_id,
                    )
                return
            envelope_text = _envelope_text(route_to_write, produced_at_utc)
            _atomic_write_text(envelope_path, envelope_text, signal_id=route_to_write.signal_id)
            return
    elif envelope_path.exists():
        return

    envelope_text = _envelope_text(route_result, produced_at_utc)
    _atomic_write_text(envelope_path, envelope_text, signal_id=route_result.signal_id)


def _envelope(route_result: RouteResult, produced_at: datetime) -> dict[str, Any]:
    stale_after = produced_at + timedelta(days=route_result.stale_after_days)
    return {
        "signal_id": route_result.signal_id,
        "idempotency_key": route_result.idempotency_key,
        "dedupe_key": route_result.dedupe_key,
        "schema_version": SCHEMA_VERSION,
        "producer_module": PRODUCER_MODULE,
        "producer_version": _producer_version(),
        "run_id": route_result.run_id,
        "run_fingerprint": route_result.run_fingerprint,
        "source_file_hash": route_result.source_file_hash,
        "rulepack_version": route_result.rulepack_version,
        "finding_id": route_result.finding_id,
        "result_id": route_result.result_id,
        "result_lineage_key": route_result.result_lineage_key,
        "destination_module": route_result.destination_module,
        "signal_type": route_result.signal_type,
        "produced_at": _isoformat(produced_at),
        "stale_after": _isoformat(stale_after),
        "supersedes_signal_id": route_result.supersedes_signal_id,
        "payload_hash": route_result.payload_hash,
        "payload": route_result.payload,
    }


def _envelope_text(route_result: RouteResult, produced_at: datetime) -> str:
    envelope = _envelope(route_result, produced_at)
    return json.dumps(envelope, ensure_ascii=False, indent=2, sort_keys=True)


def _payload(
    finding: Mapping[str, Any] | Any,
    entity_key: EntityKey,
    *,
    gap_amount: Any,
    source_locations: list[Any],
) -> dict[str, Any]:
    return {
        "entity_key": entity_key.as_payload(),
        "gap_amount": gap_amount,
        "related_accounts": ["lease_liability", "right_of_use_asset"],
        "suggested_gl_queries": _suggested_queries(entity_key),
        "source_locations": source_locations,
        "difference_kind": _text(_field(finding, "difference_kind", "unexplained_gap")),
        "routing_reason": _routing_reason(),
    }


def _suggested_queries(entity_key: EntityKey) -> list[str]:
    return [
        f"Drill down lease liability activity for {entity_key.report_period}.",
        "Review closing-entry and post-close manual journal entries affecting lease liabilities.",
    ]


def _routing_reason() -> str:
    return "lease_liabilities unexplained_gap with full entity key"


def _entity_key(finding: Mapping[str, Any] | Any) -> EntityKey | None:
    raw_entity = _field(finding, "entity_key", {}) or {}
    if not isinstance(raw_entity, Mapping):
        raw_entity = {}

    account = _text(
        _field(finding, "account_key")
        or _field(finding, "account")
        or raw_entity.get("account")
        or raw_entity.get("account_key")
    )
    key = EntityKey(
        account=account,
        consolidation_basis=_text(
            _field(finding, "consolidation_basis") or raw_entity.get("consolidation_basis")
        ),
        report_period=_text(_field(finding, "report_period") or raw_entity.get("report_period")),
        balance_level=_text(_field(finding, "balance_level") or raw_entity.get("balance_level")),
    )
    if any(_is_missing(value) for value in key.as_payload().values()):
        return None
    return key


def _source_locations(finding: Mapping[str, Any] | Any) -> list[Any]:
    direct_locations = _field(finding, "source_locations")
    if direct_locations:
        return _jsonable(direct_locations)

    evidence = _field(finding, "evidence") or _field(finding, "evidence_facts") or []
    locations: list[dict[str, Any]] = []
    for item in evidence:
        source = _field(item, "source") or _field(item, "source_location")
        if source:
            locations.append(
                {
                    "role": _text(_field(item, "role", "")),
                    "source": _text(source),
                    "fingerprint": _text(_field(item, "source_location_fingerprint", "")),
                }
            )
    return locations


def _gap_amount(finding: Mapping[str, Any] | Any) -> Any:
    return _jsonable(_field(finding, "gap_amount", _field(finding, "difference")))


def _stale_after_days(finding: Mapping[str, Any] | Any) -> int:
    try:
        return int(_field(finding, "stale_after_days", DEFAULT_STALE_AFTER_DAYS))
    except (TypeError, ValueError):
        return DEFAULT_STALE_AFTER_DAYS


def _has_required_signal_fields(finding: Mapping[str, Any] | Any) -> bool:
    required = (
        "finding_id",
        "result_id",
        "result_lineage_key",
        "run_id",
        "run_fingerprint",
        "source_file_hash",
        "rulepack_version",
    )
    return all(not _is_missing(_field(finding, field)) for field in required)


def _atomic_write_text(path: Path, text: str, *, signal_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.{signal_id[:16]}.tmp")
    fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
        _fsync_dir(path.parent)
    except Exception:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass
        raise


def _remove_envelope_file(output_dir: Path, signal_id: str) -> None:
    try:
        (output_dir / f"{signal_id}.json").unlink()
    except FileNotFoundError:
        pass


def _fsync_dir(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _field(value: Mapping[str, Any] | Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


def _required_text(value: Any) -> str:
    text = _text(value)
    if _is_missing(text):
        raise ValueError("required signal field is missing")
    return text


def _optional_text(value: Any) -> str | None:
    if _is_missing(value):
        return None
    return _text(value)


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _is_missing(value: Any) -> bool:
    return _text(value).lower() in UNKNOWN_VALUES


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError("produced_at must be a datetime")
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _isoformat(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat()


def _producer_version() -> str:
    try:
        return version("dart-footing-reconciler")
    except PackageNotFoundError:
        return "unknown"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
