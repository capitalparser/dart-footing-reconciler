"""Internal verification harness contracts and runner."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
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
    consolidation_basis: str = "unknown"


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
        checks = tuple(_with_context_consolidation_basis(harness.run(context), context))
        runs.append(
            HarnessRun(
                harness_id=harness.harness_id,
                layer=harness.layer,
                checks=checks,
            )
        )
    return runs


def _with_context_consolidation_basis(
    checks: list[CheckResult], context: VerificationContext
) -> list[CheckResult]:
    if context.consolidation_basis == "unknown":
        return checks
    return [
        replace(check, consolidation_basis=context.consolidation_basis)
        if check.consolidation_basis == "unknown"
        else check
        for check in checks
    ]


def flatten_harness_runs(runs: list[HarnessRun]) -> list[CheckResult]:
    return [check for run in runs for check in run.checks]
