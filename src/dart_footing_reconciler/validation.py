"""Validation manifest runner for fixture corpus checks."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from dart_footing_reconciler.footing import MATCHED, UNEXPLAINED_GAP
from dart_footing_reconciler.scan import scan_html

DEFAULT_TOLERANCE = 1
VALIDATION_MODES = {"conservative", "diagnostic"}


def run_manifest(
    manifest_path: str | Path,
    *,
    mode: str = "conservative",
    tag: str | None = None,
    tolerance: int = DEFAULT_TOLERANCE,
    include_results: bool = False,
) -> dict[str, Any]:
    """Run all selected samples in a validation manifest."""
    if mode not in VALIDATION_MODES:
        raise ValueError(f"mode must be one of: {', '.join(sorted(VALIDATION_MODES))}")

    path = Path(manifest_path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    samples = [
        sample
        for sample in manifest.get("samples", [])
        if tag is None or tag in sample.get("tags", []) or sample.get("industry") == tag
    ]

    sample_reports = [
        _run_sample(
            sample,
            path.parent,
            mode=mode,
            tolerance=tolerance,
            include_results=include_results,
        )
        for sample in samples
    ]
    passed = sum(1 for sample in sample_reports if sample["status"] == "passed")
    failed = sum(1 for sample in sample_reports if sample["status"] == "failed")

    return {
        "manifest": str(path),
        "mode": mode,
        "tag": tag,
        "tolerance": tolerance,
        "summary": {
            "samples": len(sample_reports),
            "passed": passed,
            "failed": failed,
            "total_tables": sum(sample["actual"]["total"] for sample in sample_reports),
            "matched": sum(sample["actual"]["matched"] for sample in sample_reports),
            "unexplained_gap": sum(
                sample["actual"]["unexplained_gap"] for sample in sample_reports
            ),
        },
        "samples": sample_reports,
    }


def _run_sample(
    sample: dict[str, Any],
    manifest_dir: Path,
    *,
    mode: str,
    tolerance: int,
    include_results: bool,
) -> dict[str, Any]:
    source = _resolve_source(manifest_dir, sample["source"])
    results = scan_html(
        source.read_text(encoding=sample.get("encoding", "utf-8")),
        tolerance=tolerance,
        include_all=mode == "diagnostic",
    )
    actual = _summary(results)
    expected = sample.get("expected")
    status = "passed" if expected is None or _matches_expected(actual, expected) else "failed"

    report = {
        "name": sample["name"],
        "company": sample.get("company"),
        "industry": sample.get("industry"),
        "tags": sample.get("tags", []),
        "source": str(source),
        "status": status,
        "expected": expected,
        "actual": actual,
    }
    if include_results:
        report["results"] = [asdict(result) for result in results]
    return report


def _resolve_source(manifest_dir: Path, source: str) -> Path:
    path = Path(source)
    if path.is_absolute():
        return path
    return manifest_dir / path


def _summary(results: list) -> dict[str, int]:
    return {
        "total": len(results),
        "matched": sum(1 for result in results if result.status == MATCHED),
        "unexplained_gap": sum(1 for result in results if result.status == UNEXPLAINED_GAP),
    }


def _matches_expected(actual: dict[str, int], expected: dict[str, int]) -> bool:
    return all(actual.get(key) == value for key, value in expected.items())
