"""Internal verification harness contracts and runner."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from dart_footing_reconciler.checks import CheckResult
from dart_footing_reconciler.document import FullReport

LAYER_STATEMENT_NOTE = "statement_note"
LAYER_NOTE_INTERNAL = "note_internal"
LAYER_STATEMENT_CROSS = "statement_cross"
LAYER_PRIOR_REPORT = "prior_report"


@dataclass(frozen=True)
class VerificationContext:
    report: FullReport
    prior_report: FullReport | None
    tolerance: int
    candidates: tuple[object, ...] = field(default_factory=tuple)


class VerificationHarness(Protocol):
    harness_id: str
    layer: str

    def run(self, context: VerificationContext) -> list[CheckResult]:
        """Return CheckResult rows for this harness."""


@dataclass(frozen=True)
class HarnessRun:
    harness_id: str
    layer: str
    checks: tuple[CheckResult, ...]


def run_harnesses(
    harnesses: list[VerificationHarness],
    context: VerificationContext,
) -> list[HarnessRun]:
    runs: list[HarnessRun] = []
    for harness in harnesses:
        checks = tuple(harness.run(context))
        runs.append(
            HarnessRun(
                harness_id=harness.harness_id,
                layer=harness.layer,
                checks=checks,
            )
        )
    return runs


def flatten_harness_runs(runs: list[HarnessRun]) -> list[CheckResult]:
    return [check for run in runs for check in run.checks]
