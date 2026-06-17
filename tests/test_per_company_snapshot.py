"""Tests for the per-company corpus regression checker.

The checker exists to catch offsetting per-company drift that a stable aggregate
hides (the B-5 failure mode). These tests pin its drift logic without running the
corpus.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from check_per_company_snapshot import compute_drift, counts_from_corpus  # noqa: E402


def test_no_drift_when_identical():
    base = {"A": {"matched": 10, "unexplained_gap": 2}}
    cur = {"A": {"matched": 10, "unexplained_gap": 2}}
    assert compute_drift(base, cur) == []


def test_detects_offsetting_drift_that_aggregate_would_hide():
    # Aggregate matched is unchanged (20) but the two companies swapped — the
    # exact masking that let B-5 through. Must be flagged.
    base = {"A": {"matched": 12}, "B": {"matched": 8}}
    cur = {"A": {"matched": 8}, "B": {"matched": 12}}
    drift = compute_drift(base, cur)
    companies = {d[0] for d in drift}
    assert companies == {"A", "B"}


def test_detects_status_shift_within_company():
    base = {"A": {"matched": 10, "unexplained_gap": 0}}
    cur = {"A": {"matched": 9, "unexplained_gap": 1}}
    drift = compute_drift(base, cur)
    fields = {d[1] for d in drift}
    assert "matched" in fields and "unexplained_gap" in fields


def test_flags_new_and_missing_company():
    base = {"A": {"matched": 1}}
    cur = {"B": {"matched": 1}}
    drift = compute_drift(base, cur)
    rows = {(d[0], d[1]) for d in drift}
    assert ("A", "MISSING from corpus run") in rows
    assert ("B", "NEW (not in baseline)") in rows


def test_counts_from_corpus_extracts_per_company():
    payload = {
        "samples": [
            {"company": "회사A", "status_counts": {"matched": 5, "parse_uncertain": 2}},
            {"company": "회사B", "status_counts": {"matched": 3}},
        ]
    }
    out = counts_from_corpus(payload)
    assert out["회사A"]["matched"] == 5
    assert out["회사A"]["parse_uncertain"] == 2
    assert out["회사A"]["not_tested"] == 0  # absent -> 0
    assert out["회사B"]["matched"] == 3
