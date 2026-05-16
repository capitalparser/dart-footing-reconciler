from dart_footing_reconciler.checks import CheckEvidence, CheckResult, MATCHED


def test_check_result_preserves_source_evidence():
    result = CheckResult(
        check_id="total:note11:table0:row3",
        check_type="total_check",
        status=MATCHED,
        scope="note",
        note_no="11",
        title="유형자산 합계",
        expected=1000,
        actual=1000,
        difference=0,
        tolerance=1,
        reason="row total agrees",
        evidence=[CheckEvidence("합계", 1000, "note:11/table:0/row:3/col:4")],
    )
    assert result.status == "matched"
    assert result.evidence[0].source == "note:11/table:0/row:3/col:4"
