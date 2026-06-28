"""Immutable canonical artifacts for report check results.

This module is a downstream adapter: it serializes already-produced
``CheckResult`` rows. The deterministic check pipeline must not import it.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Iterable

from dart_footing_reconciler.checks import (
    NOT_TESTED,
    PARSE_UNCERTAIN,
    CheckEvidence,
    CheckResult,
)

ARTIFACT_SCHEMA_VERSION = "1.0"
UNKNOWN = "unknown"
NORMALIZATION_POLICY_ID = UNKNOWN

ENTITY_KEY_FIELDS = ("account", "consolidation_basis", "report_period", "balance_level")
AMOUNT_FIELDS = ("expected_amount", "actual_amount", "gap_amount", "tolerance")


@dataclass(frozen=True)
class RunArtifactMetadata:
    source_file_hash: str
    canonical_input_hash: str
    config_hash: str
    engine_version: str
    parser_version: str = UNKNOWN
    classifier_version: str = UNKNOWN
    rulepack_version: str = UNKNOWN
    normalization_policy_version: str = UNKNOWN
    source_doc_identity: str | None = None

    @classmethod
    def from_source_file(
        cls,
        source_file: str | Path,
        *,
        config: dict[str, Any] | None = None,
        engine_version: str | None = None,
        parser_version: str = UNKNOWN,
        classifier_version: str = UNKNOWN,
        rulepack_version: str = UNKNOWN,
        normalization_policy_version: str = UNKNOWN,
    ) -> "RunArtifactMetadata":
        # engine_version: pass an explicit build identity from the run path so the
        # run_id is stable across installed/editable/uninstalled environments; the
        # importlib lookup is only a best-effort default (ADR-0017).
        source_file_hash = hash_file(source_file)
        config_hash = hash_canonical(config or {})
        canonical_input_hash = hash_canonical(
            {
                "source_file_hash": source_file_hash,
                "config_hash": config_hash,
            }
        )
        return cls(
            source_file_hash=source_file_hash,
            canonical_input_hash=canonical_input_hash,
            config_hash=config_hash,
            engine_version=engine_version or _engine_version(),
            parser_version=parser_version,
            classifier_version=classifier_version,
            rulepack_version=rulepack_version,
            normalization_policy_version=normalization_policy_version,
            source_doc_identity=source_file_hash,
        )

    @property
    def fingerprint_inputs(self) -> dict[str, str]:
        return {
            "source_file_hash": self.source_file_hash,
            "canonical_input_hash": self.canonical_input_hash,
            "engine_version": self.engine_version,
            "parser_version": self.parser_version,
            "classifier_version": self.classifier_version,
            "rulepack_version": self.rulepack_version,
            "config_hash": self.config_hash,
            "normalization_policy_version": self.normalization_policy_version,
        }

    @property
    def run_fingerprint(self) -> str:
        return hash_canonical(self.fingerprint_inputs)

    @property
    def run_id(self) -> str:
        return self.run_fingerprint


@dataclass(frozen=True)
class LoadedRunArtifact:
    header: dict[str, Any]
    results: list[dict[str, Any]]


def write_check_result_artifact(
    results: Iterable[CheckResult],
    path: str | Path,
    *,
    metadata: RunArtifactMetadata,
) -> Path:
    """Write a deterministic NDJSON run artifact for completed check results."""
    rows = [_artifact_row(result, metadata) for result in results]
    rows.sort(
        key=lambda row: (
            row["attempt_id"],
            _canonical_json(row["entity_key"]),
            row["status"],
            row["result_id"],
        )
    )
    header = {
        "record_type": "run_header",
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "run_id": metadata.run_id,
        "run_fingerprint": metadata.run_fingerprint,
        "fingerprint_inputs": metadata.fingerprint_inputs,
        "result_count": len(rows),
    }
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "\n".join(_canonical_line(record) for record in (header, *rows)) + "\n",
        encoding="utf-8",
    )
    return output


def load_run_artifact(path: str | Path) -> LoadedRunArtifact:
    records = [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not records:
        raise ValueError("run artifact is empty")
    header = records[0]
    if header.get("record_type") != "run_header":
        raise ValueError("run artifact first record must be run_header")
    # Validate the artifact before any downstream materialization (ADR-0017): a
    # truncated or malformed artifact must fail loudly, not materialize partial rows.
    for required in ("run_id", "run_fingerprint", "fingerprint_inputs", "result_count"):
        if required not in header:
            raise ValueError(f"run artifact header missing required field: {required}")
    results = [record for record in records[1:] if record.get("record_type") == "check_result"]
    declared = header.get("result_count")
    if declared != len(results):
        raise ValueError(
            f"run artifact result_count {declared!r} != {len(results)} check_result rows"
        )
    return LoadedRunArtifact(header=header, results=results)


def canonical_result_fingerprints(path: str | Path) -> list[str]:
    """Return sorted full-result fingerprints for verdict-immutability checks."""
    artifact = load_run_artifact(path)
    return sorted(row["full_result_fingerprint"] for row in artifact.results)


def hash_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_canonical(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _artifact_row(result: CheckResult, metadata: RunArtifactMetadata) -> dict[str, Any]:
    evidence_facts = [_evidence_fact(evidence, metadata) for evidence in result.evidence]
    evidence_fact_ids = sorted(fact["fact_id"] for fact in evidence_facts)
    entity_key = _entity_key(result)
    expected_amount = _amount(result.expected)
    actual_amount = _amount(result.actual)
    gap_amount = _amount(result.difference)
    tolerance = _amount(result.tolerance)
    abstain_reason = result.reason if result.status == NOT_TESTED else None
    # Fingerprint uses the parse_uncertain CODE value only — never the free-text
    # reason — so the verdict-immutability fingerprint is insensitive to prose (ADR-0017).
    parse_uncertain_reason = (
        result.parse_uncertain_reason if result.status == PARSE_UNCERTAIN else None
    )
    source_location_fingerprints = [
        fact["source_location_fingerprint"] for fact in evidence_facts
    ]
    # full_result_fingerprint defines result identity; compute it BEFORE result_id so
    # two results sharing attempt/entity/evidence/status but differing in amounts or
    # reasons cannot collide on the result_id primary key (ADR-0017).
    full_result_fingerprint = hash_canonical(
        {
            "attempt_id": result.check_id,
            "entity_key": entity_key,
            "status": result.status,
            "expected_amount": expected_amount,
            "actual_amount": actual_amount,
            "gap_amount": gap_amount,
            "tolerance": tolerance,
            "abstain_reason": abstain_reason,
            "parse_uncertain_reason": parse_uncertain_reason,
            "source_location_fingerprints": source_location_fingerprints,
            "normalization_policy_id": NORMALIZATION_POLICY_ID,
        }
    )
    result_id = hash_canonical(
        {
            "run_id": metadata.run_id,
            "attempt_id": result.check_id,
            "entity_key": entity_key,
            "evidence_fact_ids": evidence_fact_ids,
            "status": result.status,
            "full_result_fingerprint": full_result_fingerprint,
        }
    )
    result_lineage_key = hash_canonical(
        {
            "source_doc_identity": metadata.source_doc_identity or metadata.source_file_hash,
            "attempt_id": result.check_id,
            "entity_key": entity_key,
            "rule_semantic_id": result.check_type,
        }
    )
    return {
        "record_type": "check_result",
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "run_id": metadata.run_id,
        "run_fingerprint": metadata.run_fingerprint,
        "result_id": result_id,
        "result_lineage_key": result_lineage_key,
        "attempt_id": result.check_id,
        "rule_semantic_id": result.check_type,
        "rule_version": UNKNOWN,
        "entity_key": entity_key,
        # display_title is a NON-KEY human-browsing field — never a content-addressed
        # axis (a free-text title is not a stable account key; ADR-0017).
        "display_title": result.title or UNKNOWN,
        "status": result.status,
        "expected_amount": expected_amount,
        "actual_amount": actual_amount,
        "gap_amount": gap_amount,
        "tolerance": tolerance,
        "abstain_reason": abstain_reason,
        "parse_uncertain_reason": parse_uncertain_reason,
        "confidence": {"value": UNKNOWN, "evidence": []},
        "source_location_fingerprints": source_location_fingerprints,
        "normalization_policy_id": NORMALIZATION_POLICY_ID,
        "evidence_facts": evidence_facts,
        "full_result_fingerprint": full_result_fingerprint,
    }


def _evidence_fact(evidence: CheckEvidence, metadata: RunArtifactMetadata) -> dict[str, Any]:
    normalized_amount = _amount(evidence.amount)
    source_location = evidence.source or UNKNOWN
    original_label = evidence.label or UNKNOWN
    unit = UNKNOWN
    # fact_id is role-blind BY DESIGN: a fact's identity is (location + value), not its
    # role. The same cell used as both expected/actual is one fact; role lives at the
    # result level (result_evidence carries ordinal + role). (ADR-0017 m1.)
    fact_id = hash_canonical(
        {
            "source_doc_hash": metadata.source_file_hash,
            "source_location": source_location,
            "original_label": original_label,
            "normalized_amount": normalized_amount,
            "unit": unit,
        }
    )
    return {
        "fact_id": fact_id,
        "original_label": original_label,
        "normalized_amount": normalized_amount,
        "unit": unit,
        "source_location": source_location,
        "source_location_fingerprint": hash_canonical(source_location),
        "role": evidence.role,
    }


def _entity_key(result: CheckResult) -> dict[str, str]:
    # Honesty over fabrication (ADR-0017). The deterministic core does not yet
    # surface a canonical account key or the consolidated/separate basis on
    # CheckResult, so we record "unknown" rather than a fabricated value:
    #   - account: result.title is free text (often an f-string sentence), NOT a
    #     stable account key -> "unknown" here; the title is preserved as the
    #     non-key display_title field for human browsing.
    #   - consolidation_basis: result.scope only ever holds "note"/"report", which
    #     is NOT 연결/별도 -> never put it in the consolidation slot.
    # report_period / balance_level are best-effort inferences that fall back to
    # "unknown" when the label is ambiguous. Promoting all four to core-emitted
    # fields is REQUIRED before any Stage 2 cross-module signal (ADR-0017 deferred).
    return {
        "account": UNKNOWN,
        "consolidation_basis": UNKNOWN,
        "report_period": _report_period(result),
        "balance_level": _balance_level(result),
    }


def _report_period(result: CheckResult) -> str:
    text = f"{result.check_id} {result.title} {result.reason}".lower()
    if "전기" in text or re.search(r"\bprior\b", text):
        return "prior"
    # Word-boundary match so "current" does NOT match inside "noncurrent" (a balance
    # level, not a period) — the substring bug found in code review (ADR-0017 M2).
    if "당기" in text or re.search(r"\bcurrent\b", text):
        return "current"
    return UNKNOWN


def _balance_level(result: CheckResult) -> str:
    text = f"{result.check_id} {result.title}".lower()
    if "noncurrent" in text or "비유동" in text:
        return "noncurrent"
    if "current" in text or "유동" in text:
        return "current"
    if "total" in text or "합계" in text or "총계" in text:
        return "total"
    return UNKNOWN


def _amount(value: int | None) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"artifact amounts must be integers, got {type(value).__name__}")
    return {"value": str(value), "scale": 0}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _canonical_line(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=False, separators=(",", ":"))


def _engine_version() -> str:
    try:
        return version("dart-footing-reconciler")
    except PackageNotFoundError:
        return UNKNOWN
