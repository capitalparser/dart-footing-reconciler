from dart_footing_reconciler.evidence_candidates import CandidateEvidence, select_best_subset


def test_select_best_subset_returns_exact_cashflow_formula_candidates():
    candidates = [
        CandidateEvidence(
            "borrowings",
            "proceeds",
            "차입",
            100,
            "note:1/table:0/row:1/col:1",
            "1",
            "financing_liability_rollforward",
            score=5,
        ),
        CandidateEvidence(
            "borrowings",
            "repayment",
            "상환",
            -40,
            "note:1/table:0/row:2/col:1",
            "1",
            "financing_liability_rollforward",
            score=5,
        ),
        CandidateEvidence(
            "borrowings",
            "foreign_exchange",
            "환산",
            3,
            "note:1/table:0/row:3/col:1",
            "1",
            "financing_liability_rollforward",
            score=1,
        ),
    ]

    selected, rejected = select_best_subset(candidates, target_amount=60, tolerance=0, max_terms=3)

    assert [candidate.label for candidate in selected] == ["차입", "상환"]
    assert rejected[0].exclusion_reason == "not_needed_for_best_formula"
