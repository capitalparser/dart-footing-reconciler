from dart_footing_reconciler.checks import CheckEvidence, CheckResult, MATCHED, PARSE_UNCERTAIN


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


def test_check_result_has_parse_uncertain_reason_field():
    result = CheckResult(
        check_id="x", check_type="x", status=PARSE_UNCERTAIN,
        scope="report", note_no="", title="테스트",
        expected=None, actual=None, difference=None,
        tolerance=1, reason="row not found", evidence=[],
        parse_uncertain_reason="LABEL_NOT_FOUND",
    )
    assert result.parse_uncertain_reason == "LABEL_NOT_FOUND"


def test_check_result_parse_uncertain_reason_defaults_to_none():
    result = CheckResult(
        check_id="x", check_type="x", status=MATCHED,
        scope="report", note_no="", title="테스트",
        expected=100, actual=100, difference=0,
        tolerance=1, reason="ok", evidence=[],
    )
    assert result.parse_uncertain_reason is None
