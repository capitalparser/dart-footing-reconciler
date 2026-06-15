from dart_footing_reconciler.checks import CheckEvidence, CheckResult
from dart_footing_reconciler.document import FullReport
from dart_footing_reconciler.semantic_validation import SemanticValidationCandidate
from dart_footing_reconciler.verification_harness import (
    LAYER_NOTE_INTERNAL,
    VerificationContext,
    VerificationHarness,
    flatten_harness_runs,
    run_harnesses,
)


def _check(check_id: str) -> CheckResult:
    return CheckResult(
        check_id=check_id,
        check_type="total_check",
        status="matched",
        scope="report",
        note_no="1",
        title=check_id,
        expected=100,
        actual=100,
        difference=0,
        tolerance=1,
        reason="matched",
        evidence=[CheckEvidence("합계", 100, "note:1/table:0/row:1/col:1")],
    )


class FakeHarness:
    harness_id = "fake"
    layer = LAYER_NOTE_INTERNAL

    def run(self, context: VerificationContext) -> list[CheckResult]:
        assert context.tolerance == 1
        assert context.candidates[0].layer == LAYER_NOTE_INTERNAL
        return [_check("fake-check")]


def test_run_harnesses_preserves_harness_metadata_checks_and_candidates():
    candidate = SemanticValidationCandidate(
        candidate_id="note:1/table:0:internal_table_total",
        layer=LAYER_NOTE_INTERNAL,
        attempt_id="internal_table_total",
        check_type="total_check",
        table_source="note:1/table:0",
        evidence_sources=("note:1/table:0/row:1/col:1",),
        confidence=0.85,
    )
    context = VerificationContext(
        report=FullReport("sample.html", "Sample Co", [], []),
        prior_report=None,
        tolerance=1,
        candidates=(candidate,),
    )

    runs = run_harnesses([FakeHarness()], context)

    assert len(runs) == 1
    assert runs[0].harness_id == "fake"
    assert runs[0].layer == LAYER_NOTE_INTERNAL
    assert [check.check_id for check in runs[0].checks] == ["fake-check"]
    assert [check.check_id for check in flatten_harness_runs(runs)] == ["fake-check"]


def test_fake_harness_satisfies_protocol_shape():
    harness: VerificationHarness = FakeHarness()

    assert harness.harness_id == "fake"
    assert harness.layer == LAYER_NOTE_INTERNAL
