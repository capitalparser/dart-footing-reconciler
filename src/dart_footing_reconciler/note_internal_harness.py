"""Note-content internal verification harness."""

from __future__ import annotations

from dart_footing_reconciler.checks import CheckResult
from dart_footing_reconciler.checks_note_note import check_note_note_matches
from dart_footing_reconciler.checks_totals import check_table_totals
from dart_footing_reconciler.layout_formula_assertions import check_layout_formula_assertions
from dart_footing_reconciler.note_assertions import check_note_assertions
from dart_footing_reconciler.verification_harness import LAYER_NOTE_INTERNAL, VerificationContext


class NoteInternalHarness:
    """Run checks whose evidence and arithmetic live inside note contents."""

    harness_id = "note_internal"
    layer = LAYER_NOTE_INTERNAL

    def run(self, context: VerificationContext) -> list[CheckResult]:
        results: list[CheckResult] = []
        for note in context.report.notes:
            for block in note.blocks:
                if block.table is not None:
                    results.extend(
                        check_table_totals(
                            block.table,
                            note_no=note.note_no,
                            tolerance=context.tolerance,
                        )
                    )
        results.extend(check_note_assertions(context.report, tolerance=context.tolerance))
        results.extend(check_layout_formula_assertions(context.report, tolerance=context.tolerance))
        results.extend(check_note_note_matches(context.report, tolerance=context.tolerance))
        return results
