"""Target-driven audit reconciliation checks."""

from __future__ import annotations

from dataclasses import replace
from itertools import combinations

from dart_footing_reconciler.checks import (
    CheckEvidence,
    CheckResult,
    EXPLAINABLE_GAP,
    MATCHED,
    PARSE_UNCERTAIN,
    UNEXPLAINED_GAP,
)
from dart_footing_reconciler.document import FullReport, ReportSection
from dart_footing_reconciler.formula_templates import (
    FORMULA_TEMPLATES,
    FormulaMatchResult,
    extract_note_label_amount_pairs,
    match_formula_template,
)
from dart_footing_reconciler.reconciliation_inputs import (
    CfsLineInput,
    FunctionalExpenseInput,
    NoteMovementInput,
    NoteBalanceInput,
    StatementLineInput,
    extract_reconciliation_inputs,
)
from dart_footing_reconciler.reconciliation_targets import RECONCILIATION_TARGETS

# Template key for each (account_key, movement_role) pair.
_CASHFLOW_TEMPLATE_KEY: dict[tuple[str, str], str] = {
    ("property_plant_equipment", "acquisition"): "ppe_acquisition",
    ("investment_property", "acquisition"): "ppe_acquisition",
    ("intangible_assets", "acquisition"): "intangible_acquisition",
    ("borrowings", "financing_cashflow"): "borrowing_net",
    ("bonds", "financing_cashflow"): "borrowing_net",
    ("lease_liabilities", "repayment"): "lease_payment",
}


def check_reconciliation_targets(
    report: FullReport, *, tolerance: int = 1
) -> list[CheckResult]:
    inputs = extract_reconciliation_inputs(report)
    results: list[CheckResult] = []

    for target in RECONCILIATION_TARGETS:
        if target.assertion_type == "balance":
            statement = _combined_statement_line(inputs.statement_lines, target.account_key)
            note_balance = _closest_note_ending_balance(
                inputs.note_balances,
                target.account_key,
                statement.amount if statement is not None else None,
                tolerance,
            )
            if statement is None or note_balance is None:
                continue

            difference = note_balance.amount - statement.amount
            effective_tolerance = _balance_effective_tolerance(
                tolerance,
                statement.amount,
                note_balance.amount,
                note_balance.unit_multiplier,
            )
            implausible_balance_candidate = _balance_candidate_difference_exceeds_statement(
                difference, statement.amount, effective_tolerance
            )
            status = (
                PARSE_UNCERTAIN
                if implausible_balance_candidate
                else _status_for_difference(difference, effective_tolerance, target.required_adjustments)
            )
            results.append(
                CheckResult(
                    check_id=f"reconciliation:{target.key}",
                    check_type="primary_balance_reconciliation",
                    status=status,
                    scope="report",
                    note_no=note_balance.note_no,
                    title=target.key,
                    expected=statement.amount,
                    actual=note_balance.amount,
                    difference=difference,
                    tolerance=effective_tolerance,
                    reason=_balance_reconciliation_reason(
                        status, implausible_balance_candidate
                    ),
                    evidence=[
                        CheckEvidence(
                            f"statement {statement.label}",
                            statement.amount,
                            statement.source,
                        ),
                        CheckEvidence(
                            f"note {note_balance.note_no} {note_balance.label}",
                            note_balance.amount,
                            note_balance.source,
                        ),
                    ],
                )
            )
            continue

        if target.assertion_type == "cashflow_financing_net":
            cfs_lines = _cfs_lines_for_financing_net(inputs.cfs_lines, target.account_key)
            note_movements = _note_movements_by_role(
                inputs.note_movements, target.account_key, "financing_cashflow"
            )
            if not cfs_lines or not note_movements:
                continue
            if not any(
                not _is_financing_cashflow_adjustment(movement)
                for movement in note_movements
            ):
                continue

            expected = sum(line.amount for line in cfs_lines)
            all_note_movements = list(note_movements)
            note_movements = _select_financing_cashflow_movements(
                note_movements, expected, tolerance
            )
            excluded_movements = _excluded_financing_cashflow_movements(all_note_movements, note_movements)
            actual = sum(movement.amount for movement in note_movements)
            difference = actual - expected
            effective_tolerance = _cashflow_effective_tolerance(
                tolerance, note_movements
            )
            status = _status_for_difference(difference, effective_tolerance, target.required_adjustments)
            if status == MATCHED:
                excluded_movements = []
            results.append(
                CheckResult(
                    check_id=f"reconciliation:{target.key}",
                    check_type="cashflow_reconciliation",
                    status=status,
                    scope="report",
                    note_no=note_movements[0].note_no,
                    title=target.key,
                    expected=expected,
                    actual=actual,
                    difference=difference,
                    tolerance=effective_tolerance,
                    reason=_financing_cashflow_reason(
                        status, cfs_lines, note_movements, expected, actual, difference, excluded_movements
                    ),
                    evidence=[
                        *[
                            CheckEvidence(
                                f"cfs {line.label}",
                                line.amount,
                                line.source,
                            )
                            for line in cfs_lines
                        ],
                        *[
                            CheckEvidence(
                                f"note {movement.note_no} {movement.label}",
                                movement.amount,
                                movement.source,
                            )
                            for movement in note_movements
                        ],
                        *[
                            CheckEvidence(
                                f"excluded note {movement.note_no} {movement.label} ({movement.exclusion_reason})",
                                movement.amount,
                                movement.source,
                            )
                            for movement in excluded_movements
                        ],
                    ],
                )
            )
            continue

        if target.assertion_type == "expense_allocation":
            result = _expense_allocation_result(
                inputs.functional_expenses,
                target.key,
                target.account_key,
                tolerance,
            )
            if result is not None:
                results.append(result)
            continue

        if target.assertion_type.startswith("cashflow_"):
            movement_role = _cashflow_movement_role(target.assertion_type)
            if movement_role is None:
                continue
            cfs_line = _first_cfs_line(
                inputs.cfs_lines, target.account_key, movement_role
            )
            expected_amount = abs(cfs_line.amount) if cfs_line is not None else None
            note_movements = _note_movements_for_cashflow(
                inputs.note_movements,
                target.account_key,
                movement_role,
                expected_amount,
                tolerance,
                include_right_of_use_acquisition=_is_combined_ppe_rou_acquisition_cfs_line(cfs_line),
            )
            if cfs_line is None or not note_movements:
                continue

            expected = abs(cfs_line.amount)
            actual = abs(_cash_basis_note_movement_amount(note_movements, movement_role))
            difference = actual - expected
            effective_tolerance = _cashflow_bridge_effective_tolerance(
                tolerance,
                note_movements,
                expected,
                difference,
                target.required_adjustments,
            )
            status = _cashflow_status(
                difference, effective_tolerance, target.required_adjustments, note_movements
            )
            primary_result = CheckResult(
                check_id=f"reconciliation:{target.key}",
                check_type="cashflow_reconciliation",
                status=status,
                scope="report",
                note_no=note_movements[0].note_no,
                title=target.key,
                expected=expected,
                actual=actual,
                difference=difference,
                tolerance=effective_tolerance,
                reason=_cashflow_bridge_reason(
                    status,
                    cfs_line,
                    note_movements,
                    movement_role,
                    expected,
                    actual,
                    difference,
                    effective_tolerance,
                ),
                evidence=[
                    CheckEvidence(
                        f"cfs {cfs_line.label}",
                        cfs_line.amount,
                        cfs_line.source,
                    ),
                    *[
                        CheckEvidence(
                            f"note {movement.note_no} {movement.label}",
                            movement.amount,
                            movement.source,
                        )
                        for movement in note_movements
                    ],
                ],
            )
            # Formula template fallback: retry with raw note rows when not matched
            final_result = _upgrade_cashflow_result_via_template(
                primary_result, report, target.account_key, movement_role, tolerance
            )
            results.append(final_result)

    return results


def _first_statement_line(
    statement_lines: list[StatementLineInput], account_key: str
) -> StatementLineInput | None:
    return next(
        (line for line in statement_lines if line.account_key == account_key),
        None,
    )


def _effective_tolerance(tolerance: int, *unit_multipliers: int) -> int:
    if tolerance == 0:
        return 0
    return max(tolerance, *[max(unit_multiplier, 0) for unit_multiplier in unit_multipliers])


def _cashflow_effective_tolerance(
    tolerance: int, note_movements: list[NoteMovementInput]
) -> int:
    if tolerance == 0:
        return 0
    source_precision = sum(
        max(movement.unit_multiplier, 0) for movement in note_movements
    )
    return max(tolerance, source_precision)


def _cashflow_bridge_effective_tolerance(
    tolerance: int,
    note_movements: list[NoteMovementInput],
    expected: int,
    difference: int,
    required_adjustments: tuple[str, ...],
) -> int:
    source_precision = _cashflow_effective_tolerance(tolerance, note_movements)
    if tolerance == 0:
        return source_precision
    if abs(difference) <= source_precision:
        return source_precision
    if not required_adjustments or len(note_movements) <= 1:
        return source_precision
    residual_tolerance = _cashflow_bridge_residual_tolerance(expected)
    return max(source_precision, residual_tolerance)


def _cashflow_bridge_residual_tolerance(expected: int) -> int:
    return (abs(expected) + 19) // 20


def _select_financing_cashflow_movements(
    note_movements: list[NoteMovementInput], expected: int, tolerance: int
) -> list[NoteMovementInput]:
    if len(note_movements) <= 1 or len(note_movements) > 10:
        return note_movements

    full_difference = abs(sum(movement.amount for movement in note_movements) - expected)
    matches: list[tuple[int, int, tuple[NoteMovementInput, ...]]] = []
    for subset_size in range(1, len(note_movements)):
        for subset in combinations(note_movements, subset_size):
            subset_movements = list(subset)
            if not any(
                not _is_financing_cashflow_adjustment(movement)
                for movement in subset_movements
            ):
                continue
            subset_actual = sum(movement.amount for movement in subset_movements)
            subset_tolerance = _cashflow_effective_tolerance(
                tolerance, subset_movements
            )
            subset_difference = abs(subset_actual - expected)
            if subset_difference <= subset_tolerance and subset_difference < full_difference:
                matches.append((subset_difference, subset_size, subset))

    if not matches:
        return note_movements

    matches.sort(key=lambda match: (match[0], match[1]))
    return list(matches[0][2])


def _excluded_financing_cashflow_movements(
    all_movements: list[NoteMovementInput], selected_movements: list[NoteMovementInput]
) -> list[NoteMovementInput]:
    selected_sources = {movement.source for movement in selected_movements}
    excluded: list[NoteMovementInput] = []
    for movement in all_movements:
        if movement.source in selected_sources:
            continue
        reason = "financing_adjustment_not_cash" if _is_financing_cashflow_adjustment(movement) else "not_needed_for_best_formula"
        excluded.append(
            NoteMovementInput(
                movement.account_key,
                movement.movement_role,
                movement.note_no,
                movement.label,
                movement.amount,
                movement.source,
                movement.unit_multiplier,
                movement.table_class,
                movement.period_role,
                movement.exclusion_reason or reason,
            )
        )
    return excluded


def _is_financing_cashflow_adjustment(movement: NoteMovementInput) -> bool:
    return (
        movement.account_key == "lease_liabilities"
        and movement.label == "리스부채 이자비용 조정"
    )


def _balance_effective_tolerance(
    tolerance: int, statement_amount: int, note_amount: int, note_unit_multiplier: int
) -> int:
    if tolerance == 0:
        return 0
    source_precision = _effective_tolerance(tolerance, note_unit_multiplier)
    if max(abs(statement_amount), abs(note_amount)) >= 1_000_000_000:
        source_precision = max(source_precision, 1_000_000)
    return source_precision


def _balance_candidate_difference_exceeds_statement(
    difference: int, statement_amount: int, tolerance: int
) -> bool:
    if abs(difference) <= tolerance:
        return False
    return abs(difference) > abs(statement_amount)


def _balance_reconciliation_reason(status: str, implausible_candidate: bool) -> str:
    if status == MATCHED:
        return "financial statement line agrees to note ending balance"
    if implausible_candidate:
        return "candidate difference exceeds statement amount; note balance match is parse uncertain"
    return "financial statement line does not agree to note ending balance"


def _status_for_difference(
    difference: int, tolerance: int, required_adjustments: tuple[str, ...]
) -> str:
    if abs(difference) <= tolerance:
        return MATCHED
    if required_adjustments:
        return EXPLAINABLE_GAP
    return UNEXPLAINED_GAP


def _reconciliation_reason(status: str, required_adjustments: tuple[str, ...]) -> str:
    if status == MATCHED:
        return "cash flow statement line agrees to note cash movement"
    if status == EXPLAINABLE_GAP:
        return "difference requires listed audit adjustments: " + ", ".join(required_adjustments)
    return "cash flow statement line does not agree to note cash movement"


def _financing_cashflow_reason(
    status: str,
    cfs_lines: list[CfsLineInput],
    note_movements: list[NoteMovementInput],
    expected: int,
    actual: int,
    difference: int,
    excluded_movements: list[NoteMovementInput] | None = None,
) -> str:
    formula = " + ".join(
        f"현금흐름표 {line.label} {_format_amount(line.amount)}" for line in cfs_lines
    )
    note_formula = " + ".join(
        f"주석 {movement.label} {_format_amount(movement.amount)}" for movement in note_movements
    )
    verdict = "주석 재무활동현금흐름과 직접 대사됨" if status == MATCHED else "주석 재무활동현금흐름과 직접 대사되지 않음"
    excluded_note = ""
    if excluded_movements:
        excluded_note = "; 후보 제외 " + ", ".join(
            f"{movement.label}({movement.exclusion_reason})" for movement in excluded_movements[:5]
        )
    return (
        f"{formula} = {_format_amount(expected)}; "
        f"{note_formula} = {_format_amount(actual)}; "
        f"차이 {_format_amount(difference)}; {verdict}{excluded_note}"
    )


def _expense_allocation_result(
    expenses: list[FunctionalExpenseInput],
    target_key: str,
    account_key: str,
    tolerance: int,
) -> CheckResult | None:
    nature = _first_functional_expense(expenses, account_key, "nature_total")
    allocation_total = _closest_functional_expense(
        expenses, account_key, "allocation_total", nature.amount if nature is not None else None
    )
    if nature is None or allocation_total is None:
        return None

    allocation_components = _allocation_components(expenses, allocation_total)
    effective_tolerance = _effective_tolerance(tolerance, allocation_total.unit_multiplier)
    nature_exclusions = _nature_exclusion_components(
        expenses,
        account_key,
        nature,
        allocation_total.amount,
        effective_tolerance,
    )
    expected = nature.amount - sum(abs(component.amount) for component in nature_exclusions)
    actual, excluded_components = _expense_allocation_comparable_amount(
        allocation_total.amount,
        expected,
        allocation_components,
        effective_tolerance,
    )
    difference = actual - expected
    status = _status_for_difference(difference, effective_tolerance, ())
    reason = _expense_allocation_reason(
        status,
        nature,
        allocation_components,
        nature_exclusions,
        excluded_components,
        actual,
        expected,
        difference,
    )
    return CheckResult(
        check_id=f"reconciliation:{target_key}",
        check_type="expense_allocation",
        status=status,
        scope="report",
        note_no=_note_no_from_source(allocation_total.source),
        title=target_key,
        expected=expected,
        actual=actual,
        difference=difference,
        tolerance=effective_tolerance,
        reason=reason,
        evidence=[
            CheckEvidence(
                f"nature {nature.label}",
                nature.amount,
                nature.source,
            ),
            *[
                CheckEvidence(
                    f"nature exclusion {component.label}",
                    component.amount,
                    component.source,
                )
                for component in nature_exclusions
            ],
            *[
                CheckEvidence(
                    f"allocation {component.label}",
                    component.amount,
                    component.source,
                )
                for component in allocation_components
            ],
            CheckEvidence(
                f"allocation total {allocation_total.label}",
                allocation_total.amount,
                allocation_total.source,
            ),
        ],
    )


def _first_functional_expense(
    expenses: list[FunctionalExpenseInput], account_key: str, classification: str
) -> FunctionalExpenseInput | None:
    return next(
        (
            expense
            for expense in expenses
            if expense.account_key == account_key and expense.classification == classification
        ),
        None,
    )


def _closest_functional_expense(
    expenses: list[FunctionalExpenseInput],
    account_key: str,
    classification: str,
    amount: int | None,
) -> FunctionalExpenseInput | None:
    candidates = [
        expense
        for expense in expenses
        if expense.account_key == account_key and expense.classification == classification
    ]
    if not candidates:
        return None
    if amount is None:
        return candidates[0]
    return min(candidates, key=lambda expense: abs(expense.amount - amount))


def _allocation_components(
    expenses: list[FunctionalExpenseInput], allocation_total: FunctionalExpenseInput
) -> list[FunctionalExpenseInput]:
    table_source = allocation_total.source.split("/row:", 1)[0]
    return [
        expense
        for expense in expenses
        if expense.account_key == allocation_total.account_key
        and expense.source.split("/row:", 1)[0] == table_source
        and expense.classification
        in {"cost_of_sales", "selling_admin", "research_development", "other_function"}
    ]


def _nature_exclusion_components(
    expenses: list[FunctionalExpenseInput],
    account_key: str,
    nature: FunctionalExpenseInput,
    allocation_total: int,
    tolerance: int,
) -> list[FunctionalExpenseInput]:
    if account_key != "property_plant_equipment" or nature.expense_role != "depreciation":
        return []
    candidates = [
        expense
        for expense in expenses
        if expense.account_key == "investment_property"
        and expense.expense_role == "depreciation"
        and expense.classification == "nature_exclusion"
    ]
    exclusion_amount = sum(abs(component.amount) for component in candidates)
    if exclusion_amount and abs(allocation_total - (nature.amount - exclusion_amount)) <= tolerance:
        return candidates
    return []


def _expense_allocation_comparable_amount(
    allocation_total: int,
    expected: int,
    allocation_components: list[FunctionalExpenseInput],
    tolerance: int,
) -> tuple[int, list[FunctionalExpenseInput]]:
    development_components = [
        component
        for component in allocation_components
        if _is_research_or_development_function(component.label)
    ]
    development_amount = sum(component.amount for component in development_components)
    if development_amount and abs((allocation_total - development_amount) - expected) <= tolerance:
        return allocation_total - development_amount, development_components
    return allocation_total, []


def _is_research_or_development_function(label: str) -> bool:
    return any(keyword in label for keyword in ("개발", "연구"))


def _expense_allocation_reason(
    status: str,
    nature: FunctionalExpenseInput,
    allocation_components: list[FunctionalExpenseInput],
    nature_exclusions: list[FunctionalExpenseInput],
    excluded_components: list[FunctionalExpenseInput],
    actual: int,
    expected: int,
    difference: int,
) -> str:
    comparable_components = [
        component
        for component in allocation_components
        if component not in excluded_components
    ]
    formula = " + ".join(
        f"{component.label} {_format_amount(component.amount)}"
        for component in comparable_components
    )
    if not formula:
        formula = f"기능별 배부 합계 {_format_amount(actual)}"
    excluded = ""
    if excluded_components:
        excluded = (
            "; "
            + " + ".join(
                f"{component.label} {_format_amount(component.amount)}"
                for component in excluded_components
            )
            + "은 성격별 비용 대사 기준에서 제외"
        )
    verdict = "성격별 비용 주석과 자산 주석 기능별 배부가 직접 대사됨" if status == MATCHED else "성격별 비용 주석과 자산 주석 기능별 배부가 직접 대사되지 않음"
    parts = [
        f"{formula} = {_format_amount(actual)}",
    ]
    nature_formula = f"성격별 비용 {nature.label} {_format_amount(nature.amount)}"
    if nature_exclusions:
        nature_formula += "".join(
            f" - {component.label} {_format_amount(abs(component.amount))}"
            for component in nature_exclusions
        )
        nature_formula += f" = {_format_amount(expected)}"
    parts.append(nature_formula)
    if excluded:
        parts.append(excluded.lstrip("; "))
    parts.append(f"차이 {_format_amount(difference)}")
    parts.append(verdict)
    return "; ".join(parts)


def _note_no_from_source(source: str) -> str:
    if source.startswith("note:"):
        return source.split("/", 1)[0].replace("note:", "")
    return ""


def _cashflow_status(
    difference: int,
    tolerance: int,
    required_adjustments: tuple[str, ...],
    note_movements: list[NoteMovementInput],
) -> str:
    if abs(difference) <= tolerance:
        return MATCHED
    if required_adjustments and len(note_movements) > 1:
        return EXPLAINABLE_GAP
    return UNEXPLAINED_GAP


def _cashflow_bridge_reason(
    status: str,
    cfs_line: CfsLineInput,
    note_movements: list[NoteMovementInput],
    movement_role: str,
    expected: int,
    actual: int,
    difference: int,
    tolerance: int,
) -> str:
    formula = _cashflow_bridge_formula(note_movements, movement_role)
    if status == MATCHED and difference != 0:
        verdict = f"허용오차 {_format_amount(tolerance)} 이내로 현금흐름표 금액과 대사됨"
    else:
        verdict = "현금흐름표 금액과 직접 대사됨" if status == MATCHED else "현금흐름표 금액과 직접 대사되지 않음"
    return (
        f"{formula} = {_format_amount(actual)}; "
        f"현금흐름표 {cfs_line.label} {_format_amount(expected)}; "
        f"차이 {_format_amount(difference)}; {verdict}"
    )


def _cashflow_bridge_formula(note_movements: list[NoteMovementInput], movement_role: str) -> str:
    parts: list[str] = []
    primary = note_movements[0] if note_movements else None
    for idx, movement in enumerate(note_movements):
        contribution = _cashflow_bridge_contribution(movement, movement_role, idx, primary)
        label = _cashflow_bridge_label(movement, movement_role)
        amount = abs(contribution)
        if idx == 0:
            parts.append(f"{label} {_format_amount(amount)}")
        else:
            operator = "+" if contribution >= 0 else "-"
            parts.append(f"{operator} {label} {_format_amount(amount)}")
    return " ".join(parts)


def _cashflow_bridge_contribution(
    movement: NoteMovementInput,
    cashflow_role: str,
    idx: int,
    primary: NoteMovementInput | None = None,
) -> int:
    if idx == 0:
        return abs(movement.amount)
    if cashflow_role == "acquisition" and movement.movement_role == "business_combination":
        return -abs(movement.amount)
    if cashflow_role == "acquisition" and movement.movement_role == "noncash_payable":
        return -_noncash_payable_delta(movement)
    if cashflow_role == "acquisition" and movement.movement_role == "noncash_payable_decrease_candidate":
        return abs(movement.amount)
    if cashflow_role == "acquisition" and movement.movement_role == "noncash_payable_addback":
        return abs(movement.amount)
    if cashflow_role == "acquisition" and movement.movement_role == "right_of_use_noncash_acquisition":
        return -abs(movement.amount)
    if cashflow_role == "acquisition" and movement.movement_role == "right_of_use_cash_acquisition_component":
        return abs(movement.amount)
    if cashflow_role == "acquisition" and movement.movement_role == "noncash_transfer_acquisition":
        return -abs(movement.amount)
    if cashflow_role == "acquisition" and movement.movement_role == "rollforward_transfer_acquisition":
        return movement.amount
    if cashflow_role == "disposal":
        if movement.movement_role == "disposal_gain_loss":
            return _disposal_gain_loss_cash_contribution(movement, primary)
        if movement.movement_role == "government_grant_disposal":
            return abs(movement.amount)
        if movement.movement_role in {
            "accumulated_depreciation_disposal",
            "disposal_loss",
            "noncash_receivable",
            "right_of_use_noncash_disposal",
        }:
            return -abs(movement.amount)
    return movement.amount


def _cashflow_bridge_label(movement: NoteMovementInput, cashflow_role: str) -> str:
    labels = {
        "acquisition": "주석 취득",
        "disposal": "주석 처분 장부금액",
        "disposal_proceeds": "주석 처분금액",
        "accumulated_depreciation_disposal": "감가상각누계액 처분",
        "disposal_gain_loss": "처분손익",
        "disposal_loss": "처분손실",
        "noncash_receivable": "비현금거래-미수금",
        "noncash_payable": "비현금거래-미지급금",
        "noncash_payable_decrease_candidate": "비현금거래-미지급금 감소",
        "noncash_payable_addback": "비현금거래-미지급금 증가",
        "business_combination": "사업결합 취득",
        "right_of_use_noncash_acquisition": "사용권자산 비현금 취득",
        "right_of_use_cash_acquisition_component": "사용권자산 취득",
        "right_of_use_noncash_disposal": "사용권자산 비현금 처분",
        "government_grant_disposal": "정부보조금 처분",
        "noncash_transfer_acquisition": "비현금거래-대체취득",
        "rollforward_transfer_acquisition": "변동표 대체",
    }
    label = labels.get(movement.movement_role, movement.label)
    if cashflow_role == "acquisition" and movement.movement_role == "noncash_payable":
        direction = "감소" if _noncash_payable_delta(movement) < 0 else "증가"
        return f"{label} {direction}"
    if cashflow_role == "acquisition" and movement.movement_role == "rollforward_transfer_acquisition":
        direction = "감소" if movement.amount < 0 else "증가"
        return f"{label} {direction}"
    return label


def _format_amount(value: int) -> str:
    if value < 0:
        return f"({abs(value):,})"
    return f"{value:,}"


def _combined_statement_line(
    statement_lines: list[StatementLineInput], account_key: str
) -> StatementLineInput | None:
    matches = [line for line in statement_lines if line.account_key == account_key]
    if not matches:
        return None
    first_table = _statement_table_source(matches[0].source)
    matches = [line for line in matches if _statement_table_source(line.source) == first_table]
    if account_key == "trade_receivables":
        matches = _dedupe_trade_receivable_statement_parent_child_lines(matches)
    if len(matches) == 1:
        return matches[0]
    return StatementLineInput(
        account_key=account_key,
        label=" + ".join(line.label for line in matches),
        amount=sum(line.amount for line in matches),
        source="; ".join(line.source for line in matches),
    )


def _dedupe_trade_receivable_statement_parent_child_lines(
    lines: list[StatementLineInput],
) -> list[StatementLineInput]:
    child_indexes_to_drop: set[int] = set()
    for child_index, child in enumerate(lines):
        if not _is_trade_receivable_child_statement_label(child.label):
            continue
        child_period = _trade_receivable_statement_period(child.label)
        for parent_index, parent in enumerate(lines):
            if parent_index == child_index:
                continue
            if parent.amount != child.amount:
                continue
            if _trade_receivable_statement_period(parent.label) != child_period:
                continue
            if _is_trade_receivable_parent_statement_label(parent.label):
                child_indexes_to_drop.add(child_index)
                break

    return [
        line
        for index, line in enumerate(lines)
        if index not in child_indexes_to_drop
    ]


def _is_trade_receivable_parent_statement_label(label: str) -> bool:
    normalized = _compact_label(label)
    return "매출채권" in normalized and "기타" in normalized and "채권" in normalized


def _is_trade_receivable_child_statement_label(label: str) -> bool:
    normalized = _compact_label(label)
    for suffix in ("총액", "합계"):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
    return normalized in {"매출채권", "장기매출채권"}


def _trade_receivable_statement_period(label: str) -> str:
    normalized = _compact_label(label)
    if "장기" in normalized or "비유동" in normalized:
        return "noncurrent"
    return "current"


def _compact_label(label: str) -> str:
    return "".join(ch for ch in label if ch.isalnum())


def _statement_table_source(source: str) -> str:
    return source.split("/row:", 1)[0]


def _closest_note_ending_balance(
    note_balances: list[NoteBalanceInput],
    account_key: str,
    statement_amount: int | None,
    tolerance: int,
) -> NoteBalanceInput | None:
    candidates = [
        balance
        for balance in note_balances
        if balance.account_key == account_key and balance.balance_role == "ending"
    ]
    if not candidates:
        return None
    if statement_amount is None:
        return candidates[0]
    closest_single = min(candidates, key=lambda balance: abs(balance.amount - statement_amount))
    combined = _combined_note_balance_candidate(
        candidates, statement_amount, account_key, tolerance
    )
    if combined is not None and abs(combined.amount - statement_amount) < abs(
        closest_single.amount - statement_amount
    ):
        return combined
    return closest_single


def _combined_note_balance_candidate(
    candidates: list[NoteBalanceInput],
    statement_amount: int,
    account_key: str,
    tolerance: int,
) -> NoteBalanceInput | None:
    grouped: dict[str, list[NoteBalanceInput]] = {}
    for candidate in candidates:
        grouped.setdefault(_note_table_source(candidate.source), []).append(candidate)
        if account_key == "trade_receivables":
            grouped.setdefault(f"note:{candidate.note_no}", []).append(candidate)

    best: NoteBalanceInput | None = None
    best_difference: int | None = None
    for table_candidates in grouped.values():
        if len(table_candidates) < 2:
            continue
        subsets = _small_balance_subsets(table_candidates)
        if account_key == "trade_receivables":
            subsets.extend(_trade_receivable_current_noncurrent_total_subsets(table_candidates))
        for subset in subsets:
            amount = sum(
                _note_balance_contribution(item, account_key) for item in subset
            )
            difference = abs(amount - statement_amount)
            unit_multiplier = max(item.unit_multiplier for item in subset)
            if _uses_signed_allowance(subset, account_key) and difference > _balance_effective_tolerance(
                tolerance, statement_amount, amount, unit_multiplier
            ):
                continue
            if best_difference is None or difference < best_difference:
                best_difference = difference
                best = NoteBalanceInput(
                    subset[0].account_key,
                    subset[0].balance_role,
                    subset[0].note_no,
                    " + ".join(item.label for item in subset),
                    amount,
                    "; ".join(item.source for item in subset),
                    unit_multiplier,
                )
    return best


def _trade_receivable_current_noncurrent_total_subsets(
    candidates: list[NoteBalanceInput],
) -> list[tuple[NoteBalanceInput, ...]]:
    current_totals: list[NoteBalanceInput] = []
    noncurrent_totals: list[NoteBalanceInput] = []
    for candidate in candidates:
        normalized = "".join(ch for ch in candidate.label if ch.isalnum())
        if "매출채권" not in normalized or "합계" not in normalized:
            continue
        if "비유동" in normalized:
            noncurrent_totals.append(candidate)
        elif "유동" in normalized:
            current_totals.append(candidate)
    return [
        (current, noncurrent)
        for current in current_totals
        for noncurrent in noncurrent_totals
    ]


def _uses_signed_allowance(
    balances: tuple[NoteBalanceInput, ...], account_key: str
) -> bool:
    return any(
        _note_balance_contribution(balance, account_key) != balance.amount
        for balance in balances
    )


def _note_balance_contribution(balance: NoteBalanceInput, account_key: str) -> int:
    if account_key == "trade_receivables":
        normalized = "".join(ch for ch in balance.label if ch.isalnum())
        if any(alias in normalized for alias in ("손실충당금", "대손충당금", "충당금", "손상차손누계액")):
            return -abs(balance.amount)
    return balance.amount


def _small_balance_subsets(candidates: list[NoteBalanceInput]) -> list[tuple[NoteBalanceInput, ...]]:
    if len(candidates) > 12:
        return [tuple(candidates)]
    subsets: list[tuple[NoteBalanceInput, ...]] = []
    total_masks = 1 << len(candidates)
    for mask in range(1, total_masks):
        if mask & (mask - 1) == 0:
            continue
        subsets.append(tuple(candidate for idx, candidate in enumerate(candidates) if mask & (1 << idx)))
    return subsets


def _note_table_source(source: str) -> str:
    return source.split("/row:", 1)[0]


def _cashflow_movement_role(assertion_type: str) -> str | None:
    if assertion_type == "cashflow_issue_redemption":
        # A single bond target can represent both issuance proceeds and redemption payments.
        # Keep it out until the target registry splits the two directions explicitly.
        return None
    roles = {
        "cashflow_acquisition": "acquisition",
        "cashflow_disposal": "disposal",
        "cashflow_repayment": "repayment",
        "cashflow_proceeds": "proceeds",
    }
    return roles.get(assertion_type)


def _first_cfs_line(
    cfs_lines: list[CfsLineInput], account_key: str, movement_role: str
) -> CfsLineInput | None:
    return next(
        (
            line
            for line in cfs_lines
            if line.account_key == account_key and line.movement_role == movement_role
        ),
        None,
    )


def _cfs_lines_for_financing_net(
    cfs_lines: list[CfsLineInput], account_key: str
) -> list[CfsLineInput]:
    roles = {"proceeds", "repayment", "net_change"}
    matches = [
        line
        for line in cfs_lines
        if line.account_key == account_key and line.movement_role in roles
    ]
    if account_key != "lease_liabilities":
        return matches
    return matches[:1]


def _is_combined_ppe_rou_acquisition_cfs_line(cfs_line: CfsLineInput | None) -> bool:
    if cfs_line is None:
        return False
    normalized = "".join(ch for ch in cfs_line.label if ch.isalnum())
    return (
        cfs_line.account_key == "property_plant_equipment"
        and cfs_line.movement_role == "acquisition"
        and "유형자산" in normalized
        and "사용권자산" in normalized
    )


def _first_note_movement(
    note_movements: list[NoteMovementInput], account_key: str, movement_role: str
) -> NoteMovementInput | None:
    return next(
        (
            movement
            for movement in note_movements
            if movement.account_key == account_key
            and movement.movement_role == movement_role
        ),
        None,
    )


def _note_movements_by_role(
    note_movements: list[NoteMovementInput], account_key: str, movement_role: str
) -> list[NoteMovementInput]:
    return [
        movement
        for movement in note_movements
        if movement.account_key == account_key
        and movement.movement_role == movement_role
    ]


def _note_movements_for_cashflow(
    note_movements: list[NoteMovementInput],
    account_key: str,
    movement_role: str,
    expected_amount: int | None = None,
    tolerance: int = 1,
    include_right_of_use_acquisition: bool = False,
) -> list[NoteMovementInput]:
    if movement_role == "disposal":
        direct_proceeds = _closest_note_movement(
            note_movements, account_key, "disposal_proceeds", expected_amount
        )
        if direct_proceeds is not None:
            return [direct_proceeds]
    if movement_role == "acquisition":
        primary = _closest_note_movement(
            note_movements, account_key, movement_role, expected_amount
        )
    elif movement_role == "disposal" and expected_amount is not None:
        primary = _best_disposal_primary_movement(
            note_movements, account_key, expected_amount, tolerance
        )
    else:
        primary = _first_note_movement(note_movements, account_key, movement_role)
    if primary is None:
        return []
    if movement_role == "acquisition":
        adjustment_roles = {
            "business_combination",
            "noncash_payable",
            "noncash_payable_decrease_candidate",
            "noncash_payable_addback",
            "right_of_use_noncash_acquisition",
            "noncash_transfer_acquisition",
            "rollforward_transfer_acquisition",
        }
    elif movement_role == "disposal":
        adjustment_roles = {
            "accumulated_depreciation_disposal",
            "disposal_gain_loss",
            "disposal_loss",
            "noncash_receivable",
            "right_of_use_noncash_disposal",
            "government_grant_disposal",
        }
    else:
        adjustment_roles = set()
    adjustments = [
        movement
        for movement in note_movements
        if movement.account_key == account_key
        and movement.movement_role in adjustment_roles
    ]
    if movement_role == "acquisition" and include_right_of_use_acquisition:
        adjustments = [
            replace(movement, movement_role="right_of_use_cash_acquisition_component")
            if movement.movement_role == "right_of_use_noncash_acquisition"
            else movement
            for movement in adjustments
        ]
    adjustments = _deduplicate_cashflow_adjustments(adjustments)
    if movement_role in {"acquisition", "disposal"} and expected_amount is not None:
        adjustments = _best_cashflow_adjustment_subset(primary, adjustments, movement_role, expected_amount)
    return [primary, *adjustments]


def _best_disposal_primary_movement(
    note_movements: list[NoteMovementInput],
    account_key: str,
    expected_amount: int,
    tolerance: int,
) -> NoteMovementInput | None:
    candidates = [
        movement
        for movement in note_movements
        if movement.account_key == account_key
        and movement.movement_role == "disposal"
    ]
    if not candidates:
        return None
    first = candidates[0]
    adjustments = [
        movement
        for movement in note_movements
        if movement.account_key == account_key
        and movement.movement_role
        in {
            "accumulated_depreciation_disposal",
            "disposal_gain_loss",
            "disposal_loss",
            "noncash_receivable",
            "right_of_use_noncash_disposal",
            "government_grant_disposal",
        }
    ]
    adjustments = _deduplicate_cashflow_adjustments(adjustments)
    first_subset = _best_cashflow_adjustment_subset(
        first, adjustments, "disposal", expected_amount
    )
    first_movements = [first, *first_subset]
    first_difference = abs(
        abs(_cash_basis_note_movement_amount(first_movements, "disposal")) - expected_amount
    )

    best = first
    best_difference = first_difference
    for candidate in candidates[1:]:
        subset = _best_cashflow_adjustment_subset(
            candidate, adjustments, "disposal", expected_amount
        )
        movements = [candidate, *subset]
        actual = abs(_cash_basis_note_movement_amount(movements, "disposal"))
        difference = abs(actual - expected_amount)
        effective_tolerance = _cashflow_effective_tolerance(tolerance, movements)
        if difference <= effective_tolerance and difference < best_difference:
            best = candidate
            best_difference = difference
    return best


def _deduplicate_cashflow_adjustments(
    adjustments: list[NoteMovementInput],
) -> list[NoteMovementInput]:
    unique: list[NoteMovementInput] = []
    seen: set[tuple[str, int]] = set()
    for adjustment in adjustments:
        key = (adjustment.movement_role, abs(adjustment.amount))
        if key in seen:
            continue
        seen.add(key)
        unique.append(adjustment)
    return unique


def _best_cashflow_adjustment_subset(
    primary: NoteMovementInput,
    adjustments: list[NoteMovementInput],
    movement_role: str,
    expected_amount: int,
) -> list[NoteMovementInput]:
    if not adjustments:
        return []
    if len(adjustments) > 8:
        return adjustments

    best_subset: list[NoteMovementInput] = []
    best_difference = abs(abs(primary.amount) - expected_amount)
    best_size = 0
    for mask in range(1, 1 << len(adjustments)):
        subset = [
            adjustment
            for idx, adjustment in enumerate(adjustments)
            if mask & (1 << idx)
        ]
        actual = abs(_cash_basis_note_movement_amount([primary, *subset], movement_role))
        difference = abs(actual - expected_amount)
        if difference < best_difference or (
            difference == best_difference
            and _cashflow_adjustment_subset_rank(subset, primary) < _cashflow_adjustment_subset_rank(best_subset, primary)
        ):
            best_difference = difference
            best_size = len(subset)
            best_subset = subset
    return best_subset


def _closest_note_movement(
    note_movements: list[NoteMovementInput],
    account_key: str,
    movement_role: str,
    expected_amount: int | None,
) -> NoteMovementInput | None:
    candidates = [
        movement
        for movement in note_movements
        if movement.account_key == account_key
        and movement.movement_role == movement_role
    ]
    if not candidates:
        return None
    if expected_amount is None:
        return candidates[0]
    return min(candidates, key=lambda movement: abs(abs(movement.amount) - expected_amount))


def _cash_basis_note_movement_amount(
    note_movements: list[NoteMovementInput], movement_role: str
) -> int:
    primary = note_movements[0].amount
    if movement_role == "disposal" and note_movements[0].movement_role == "disposal_proceeds":
        return primary
    adjustments = note_movements[1:]
    if movement_role == "acquisition":
        noncash_payables = sum(
            _noncash_payable_delta(movement)
            for movement in adjustments
            if movement.movement_role == "noncash_payable"
        )
        payable_addbacks = sum(
            abs(movement.amount)
            for movement in adjustments
            if movement.movement_role == "noncash_payable_addback"
        )
        payable_decrease_candidates = sum(
            abs(movement.amount)
            for movement in adjustments
            if movement.movement_role == "noncash_payable_decrease_candidate"
        )
        business_combinations = sum(
            abs(movement.amount)
            for movement in adjustments
            if movement.movement_role == "business_combination"
        )
        right_of_use_acquisitions = sum(
            abs(movement.amount)
            for movement in adjustments
            if movement.movement_role == "right_of_use_noncash_acquisition"
        )
        right_of_use_cash_components = sum(
            abs(movement.amount)
            for movement in adjustments
            if movement.movement_role == "right_of_use_cash_acquisition_component"
        )
        transfer_acquisitions = sum(
            abs(movement.amount)
            for movement in adjustments
            if movement.movement_role == "noncash_transfer_acquisition"
        )
        rollforward_transfers = sum(
            movement.amount
            for movement in adjustments
            if movement.movement_role == "rollforward_transfer_acquisition"
        )
        return primary - noncash_payables + payable_addbacks + payable_decrease_candidates - business_combinations - right_of_use_acquisitions + right_of_use_cash_components - transfer_acquisitions + rollforward_transfers
    if movement_role == "disposal":
        amount = abs(primary)
        for movement in adjustments:
            if movement.movement_role == "disposal_gain_loss":
                amount += _disposal_gain_loss_cash_contribution(movement, note_movements[0])
            elif movement.movement_role == "accumulated_depreciation_disposal":
                amount -= abs(movement.amount)
            elif movement.movement_role == "disposal_loss":
                amount -= abs(movement.amount)
            elif movement.movement_role == "noncash_receivable":
                amount -= abs(movement.amount)
            elif movement.movement_role == "right_of_use_noncash_disposal":
                amount -= abs(movement.amount)
            elif movement.movement_role == "government_grant_disposal":
                amount += abs(movement.amount)
        return amount
    return primary


def _cashflow_adjustment_subset_rank(
    subset: list[NoteMovementInput], primary: NoteMovementInput
) -> tuple[int, int]:
    net_adjustments = sum(
        1 for movement in subset if _is_net_disposal_gain_loss_adjustment(movement, primary)
    )
    return net_adjustments, len(subset)


def _disposal_gain_loss_cash_contribution(
    movement: NoteMovementInput, primary: NoteMovementInput | None
) -> int:
    if primary is not None and _is_net_disposal_gain_loss_adjustment(movement, primary):
        return -movement.amount
    return abs(movement.amount)


def _is_net_disposal_gain_loss_adjustment(
    movement: NoteMovementInput, primary: NoteMovementInput
) -> bool:
    normalized = "".join(ch for ch in movement.label if ch.isalnum())
    return (
        movement.movement_role == "disposal_gain_loss"
        and "처분손익" in normalized
        and _note_source_prefix(movement.source) != _note_source_prefix(primary.source)
    )


def _note_source_prefix(source: str) -> str:
    return source.split("/", 1)[0]


# ---------------------------------------------------------------------------
# Formula template fallback helpers
# ---------------------------------------------------------------------------


def _formula_template_key(account_key: str, movement_role: str) -> str | None:
    """Return the FORMULA_TEMPLATES key for *account_key* + *movement_role*, or None."""
    return _CASHFLOW_TEMPLATE_KEY.get((account_key, movement_role))


def _note_rows_for_template(
    report: FullReport,
    note_no: str,
    account_key: str,
) -> list[tuple[str, int]]:
    """Collect raw (label, amount) pairs from all tables in the note section
    identified by *note_no* that are relevant to *account_key*.

    Scans every table in the matching note section and concatenates pairs so
    that match_formula_template() can search across all rows.
    """
    pairs: list[tuple[str, int]] = []
    for section in report.notes:
        if section.note_no != note_no:
            continue
        for block in section.blocks:
            if block.table is None or not block.table.rows:
                continue
            pairs.extend(
                extract_note_label_amount_pairs(
                    block.table.rows,
                    block.table.unit_multiplier,
                )
            )
    return pairs


def _upgrade_cashflow_result_via_template(
    result: CheckResult,
    report: FullReport,
    account_key: str,
    movement_role: str,
    tolerance: int,
) -> CheckResult:
    """If *result* is not MATCHED, attempt a formula-template re-match.

    Returns an upgraded (MATCHED) CheckResult when the formula template
    closes the gap within tolerance; otherwise returns *result* unchanged.
    """
    if result.status == MATCHED:
        return result

    template_key = _formula_template_key(account_key, movement_role)
    if template_key is None:
        return result

    # Infer note_no from the first evidence item labelled "note …"
    note_no = _infer_note_no_from_evidence(result)
    if not note_no:
        return result

    raw_rows = _note_rows_for_template(report, note_no, account_key)
    if not raw_rows:
        return result

    fm = match_formula_template(
        cfs_amount=result.expected,
        note_rows=raw_rows,
        template_key=template_key,
        tolerance=max(tolerance, FORMULA_TEMPLATES[template_key]["tolerance"]),
    )

    if not fm.matched:
        return result

    upgraded_reason = (
        f"공식 템플릿 '{template_key}' 적용: "
        + " + ".join(fm.matched_labels)
        + f" = {_format_amount(fm.formula_total)}; "
        f"현금흐름표 {_format_amount(result.expected)}; "
        f"잔차 {_format_amount(fm.residual)}; 공식 템플릿으로 대사됨"
    )
    return CheckResult(
        check_id=result.check_id,
        check_type=result.check_type,
        status=MATCHED,
        scope=result.scope,
        note_no=result.note_no,
        title=result.title,
        expected=result.expected,
        actual=fm.formula_total,
        difference=fm.formula_total - result.expected,
        tolerance=max(tolerance, FORMULA_TEMPLATES[template_key]["tolerance"]),
        reason=upgraded_reason,
        evidence=result.evidence,
    )


def _infer_note_no_from_evidence(result: CheckResult) -> str:
    """Extract note_no from the first evidence item whose label starts with 'note'."""
    for evidence in result.evidence:
        if evidence.label.startswith("note "):
            parts = evidence.label.split()
            if len(parts) >= 2:
                return parts[1]
    return result.note_no or ""


def _noncash_payable_delta(movement: NoteMovementInput) -> int:
    normalized = "".join(ch for ch in movement.label if ch.isalnum())
    if "감소증가" in normalized:
        return -abs(movement.amount)
    if (
        movement.amount < 0
        and "변동" in normalized
        and "관련" in normalized
        and ("유무형자산" not in normalized and "유ㆍ무형자산" not in movement.label)
        and ("유형자산" in normalized or "무형자산" in normalized)
    ):
        return abs(movement.amount)
    return movement.amount
