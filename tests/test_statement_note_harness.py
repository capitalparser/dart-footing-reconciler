from dart_footing_reconciler.checks import CheckEvidence, CheckResult
from dart_footing_reconciler.document import FullReport
from dart_footing_reconciler.statement_note_harness import StatementNoteHarness
from dart_footing_reconciler.verification_harness import LAYER_STATEMENT_NOTE, VerificationContext


def _check(check_id: str, check_type: str, account_key: str = "unknown") -> CheckResult:
    return CheckResult(
        check_id=check_id,
        check_type=check_type,
        status="matched",
        scope="report",
        note_no="1",
        title=check_id,
        expected=100,
        actual=100,
        difference=0,
        tolerance=1,
        reason="matched",
        evidence=[
            CheckEvidence("재무상태표", 100, "statement:bs/table:0/row:1/col:1"),
            CheckEvidence("주석", 100, "note:1/table:0/row:1/col:1"),
        ],
        account_key=account_key,
    )


def test_statement_note_harness_exposes_layer_identity():
    harness = StatementNoteHarness()

    assert harness.harness_id == "statement_note"
    assert harness.layer == LAYER_STATEMENT_NOTE


def test_statement_note_harness_routes_cashflow_as_separate_strategy(monkeypatch):
    calls: list[str] = []

    def fake_reconciliation(report, *, tolerance):
        calls.append("reconciliation")
        return [
            _check("balance", "primary_balance_reconciliation"),
            _check("cashflow", "cashflow_reconciliation"),
            _check("expense", "expense_allocation"),
        ]

    def fake_bridges(report, *, tolerance):
        calls.append("bridges")
        return [_check("asset-bridge", "asset_note_bridge_check")]

    def fake_fs(report, *, tolerance):
        calls.append("fs")
        return [_check("fs-note", "fs_note_match")]

    def fake_cfs(report, *, tolerance):
        calls.append("cfs")
        return [_check("cfs-note", "cfs_note_match")]

    def fake_prior_column(report, *, tolerance):
        calls.append("prior-column")
        return [_check("prior-column", "prior_column_fs_note")]

    monkeypatch.setattr("dart_footing_reconciler.statement_note_harness.check_reconciliation_targets", fake_reconciliation)
    monkeypatch.setattr("dart_footing_reconciler.statement_note_harness.check_asset_note_bridges", fake_bridges)
    monkeypatch.setattr("dart_footing_reconciler.statement_note_harness.check_fs_note_matches", fake_fs)
    monkeypatch.setattr("dart_footing_reconciler.statement_note_harness.check_cfs_note_matches", fake_cfs)
    monkeypatch.setattr("dart_footing_reconciler.statement_note_harness.check_prior_column_matches", fake_prior_column)

    context = VerificationContext(FullReport("sample.html", "Sample", [], []), None, tolerance=1)
    checks = StatementNoteHarness().run(context)

    assert calls == ["reconciliation", "bridges", "fs", "cfs", "prior-column"]
    assert [check.check_type for check in checks] == [
        "primary_balance_reconciliation",
        "expense_allocation",
        "asset_note_bridge_check",
        "fs_note_match",
        "cashflow_reconciliation",
        "cfs_note_match",
        "prior_column_fs_note",
    ]


def test_statement_note_harness_suppresses_legacy_match_when_stronger_account_check_exists(
    monkeypatch,
):
    def fake_reconciliation(report, *, tolerance):
        return [
            _check(
                "primary-ppe",
                "primary_balance_reconciliation",
                "property_plant_equipment",
            ),
            _check(
                "cash-ppe",
                "cashflow_reconciliation",
                "property_plant_equipment",
            ),
        ]

    monkeypatch.setattr(
        "dart_footing_reconciler.statement_note_harness.check_reconciliation_targets",
        fake_reconciliation,
    )
    monkeypatch.setattr(
        "dart_footing_reconciler.statement_note_harness.check_asset_note_bridges",
        lambda report, *, tolerance: [],
    )
    monkeypatch.setattr(
        "dart_footing_reconciler.statement_note_harness.check_fs_note_matches",
        lambda report, *, tolerance: [
            _check("legacy-fs-ppe", "fs_note_match", "property_plant_equipment"),
            _check("legacy-fs-debt", "fs_note_match", "borrowings"),
        ],
    )
    monkeypatch.setattr(
        "dart_footing_reconciler.statement_note_harness.check_cfs_note_matches",
        lambda report, *, tolerance: [
            _check("legacy-cfs-ppe", "cfs_note_match", "property_plant_equipment")
        ],
    )
    monkeypatch.setattr(
        "dart_footing_reconciler.statement_note_harness.check_prior_column_matches",
        lambda report, *, tolerance: [],
    )
    monkeypatch.setattr(
        "dart_footing_reconciler.statement_note_harness.check_note_references",
        lambda report: [],
    )

    checks = StatementNoteHarness().run(
        VerificationContext(FullReport("sample.html", "Sample", [], []), None, tolerance=1)
    )

    assert [check.check_id for check in checks] == [
        "primary-ppe",
        "legacy-fs-ppe",
        "legacy-fs-debt",
        "cash-ppe",
        "legacy-cfs-ppe",
    ]
    assert [check.status for check in checks] == [
        "matched",
        "not_tested",
        "matched",
        "matched",
        "not_tested",
    ]
