#!/usr/bin/env python3
"""Per-company regression check for the corpus gate.

Aggregate corpus counts can stay flat while individual companies break and
offset each other. This masked the B-5 net-vs-gross regression: aggregate
matched moved +4 while 8 genuine matches broke and 12 unrelated ones recovered.
A per-company snapshot catches that — each company's per-status counts are
compared against a committed baseline, so offsetting per-company drift can no
longer hide behind a stable total.

Usage:
    python scripts/check_per_company_snapshot.py <corpus_result.json>
    python scripts/check_per_company_snapshot.py <corpus_result.json> --update

--update rewrites the baseline from the given corpus result. Use only when a
change is intentionally accepted, and explain the delta in the PR.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASELINE = Path(__file__).resolve().parent.parent / "tests" / "baselines" / "per_company_counts.json"
STATUSES = ("matched", "explainable_gap", "unexplained_gap", "parse_uncertain", "not_tested")


def counts_from_corpus(corpus_result: dict) -> dict[str, dict[str, int]]:
    """Extract {company: {status: count}} from a corpus_result.json payload."""
    out: dict[str, dict[str, int]] = {}
    for sample in corpus_result.get("samples", []):
        sc = sample.get("status_counts", {}) or {}
        out[sample["company"]] = {st: int(sc.get(st, 0)) for st in STATUSES}
    return out


def compute_drift(
    baseline: dict[str, dict[str, int]], current: dict[str, dict[str, int]]
) -> list[tuple[str, str, object, object]]:
    """Return drift rows (company, what, baseline_value, current_value).

    Pure function — unit-tested without running the corpus.
    """
    drift: list[tuple[str, str, object, object]] = []
    for company in sorted(set(baseline) | set(current)):
        b = baseline.get(company)
        c = current.get(company)
        if b is None:
            drift.append((company, "NEW (not in baseline)", None, c))
            continue
        if c is None:
            drift.append((company, "MISSING from corpus run", b, None))
            continue
        for st in STATUSES:
            if int(b.get(st, 0)) != int(c.get(st, 0)):
                drift.append((company, st, b.get(st, 0), c.get(st, 0)))
    return drift


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("corpus_result", help="path to a corpus_result.json")
    ap.add_argument("--update", action="store_true", help="rewrite the baseline from this result")
    args = ap.parse_args(argv)

    payload = json.loads(Path(args.corpus_result).read_text(encoding="utf-8"))
    current = counts_from_corpus(payload)

    if args.update:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(
            json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"baseline updated: {len(current)} companies -> {BASELINE}")
        return 0

    if not BASELINE.exists():
        print(f"no baseline at {BASELINE}; create it with --update", file=sys.stderr)
        return 2

    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    drift = compute_drift(baseline, current)
    if not drift:
        print(f"per-company snapshot OK: {len(baseline)} companies unchanged")
        return 0

    print("PER-COMPANY DRIFT DETECTED:")
    for company, what, b, c in drift:
        print(f"  {company:14} {what:24} baseline={b} current={c}")
    print(f"\n{len(drift)} drift(s). If intentional, re-run with --update and explain in the PR.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
