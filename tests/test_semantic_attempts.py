from dart_footing_reconciler.semantic_attempts import SEMANTIC_ATTEMPTS, attempts_for_signatures
from dart_footing_reconciler.signatures import SignatureMatch


def test_attempt_registry_has_layers_and_no_company_or_layout_routing_fields():
    for attempt in SEMANTIC_ATTEMPTS:
        assert not hasattr(attempt, "company")
        assert not hasattr(attempt, "layout_key")
        assert attempt.required_signatures
        assert attempt.layer in {"statement_note", "note_internal", "statement_cross"}
        assert attempt.axis in {
            "internal",
            "note_to_note",
            "note_to_bs",
            "note_to_pl",
            "note_to_sce",
            "note_to_cf",
            "statement_to_statement",
        }


def test_attempts_are_selected_by_signature_confidence():
    attempts = attempts_for_signatures(
        (
            SignatureMatch("internal_closure", 0.85, {"axis": "row"}),
            SignatureMatch("rollforward_axis", 0.75, {"degree": "minimal"}),
        )
    )

    ids = {attempt.attempt_id for attempt in attempts}
    assert "internal_table_total" in ids
    assert "rollforward_internal_formula" in ids
    internal_attempts = [
        attempt
        for attempt in attempts
        if attempt.attempt_id in {"internal_table_total", "rollforward_internal_formula"}
    ]
    assert {attempt.layer for attempt in internal_attempts} == {"note_internal"}


def test_low_confidence_signature_does_not_trigger_attempt():
    attempts = attempts_for_signatures(
        (
            SignatureMatch("internal_closure", 0.2, {}),
            SignatureMatch("rollforward_axis", 0.2, {}),
        )
    )

    assert attempts == ()
