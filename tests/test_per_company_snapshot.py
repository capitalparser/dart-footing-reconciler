"""Tests for the per-company corpus regression checker.

The checker exists to catch offsetting per-company drift that a stable aggregate
hides (the B-5 failure mode). These tests pin its drift logic without running the
corpus.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import check_per_company_snapshot as snapshot  # noqa: E402
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


def test_main_uses_selected_baseline_for_update_and_compare(tmp_path, monkeypatch):
    corpus_result = tmp_path / "corpus_result.json"
    default_baseline = tmp_path / "default.json"
    selected_baseline = tmp_path / "expansion.json"
    corpus_result.write_text(
        json.dumps(
            {
                "samples": [
                    {
                        "company": "회사A",
                        "status_counts": {"matched": 2},
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    default_baseline.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(snapshot, "BASELINE", default_baseline)

    assert (
        snapshot.main(
            [
                str(corpus_result),
                "--baseline",
                str(selected_baseline),
                "--update",
            ]
        )
        == 0
    )
    assert json.loads(default_baseline.read_text(encoding="utf-8")) == {}
    assert json.loads(selected_baseline.read_text(encoding="utf-8")) == {
        "회사A": {
            "explainable_gap": 0,
            "matched": 2,
            "not_tested": 0,
            "parse_uncertain": 0,
            "unexplained_gap": 0,
        }
    }
    assert (
        snapshot.main(
            [
                str(corpus_result),
                "--baseline",
                str(selected_baseline),
            ]
        )
        == 0
    )


def test_main_uses_default_baseline_when_option_is_omitted(tmp_path, monkeypatch):
    corpus_result = tmp_path / "corpus_result.json"
    default_baseline = tmp_path / "default.json"
    corpus_result.write_text(
        json.dumps(
            {
                "samples": [
                    {
                        "company": "회사A",
                        "status_counts": {"matched": 2},
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    default_baseline.write_text(
        json.dumps(
            {
                "회사A": {
                    "explainable_gap": 0,
                    "matched": 2,
                    "not_tested": 0,
                    "parse_uncertain": 0,
                    "unexplained_gap": 0,
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(snapshot, "BASELINE", default_baseline)

    assert snapshot.main([str(corpus_result)]) == 0
