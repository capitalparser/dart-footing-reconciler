"""Financial statement to note matching checks."""

from __future__ import annotations

from dart_footing_reconciler.amount_compare import amounts_agree, display_unit_tolerance
from dart_footing_reconciler.checks import (
    CheckEvidence,
    CheckResult,
    MATCHED,
    NOT_TESTED,
    UNEXPLAINED_GAP,
)
from dart_footing_reconciler.document import FullReport, ReportSection, ReportTable
from dart_footing_reconciler.table_semantics import (
    amount_from_current_period,
    current_period_columns,
    prior_period_columns,
    row_amount_prefer_current,
)
from dart_footing_reconciler.taxonomy import (
    ClassifiedNoteAmount,
    ClassifiedStatementLine,
    TAXONOMY,
    classify_report,
)

FS_NOTE_ACCOUNT_KEYS = (
    "property_plant_equipment",
    "intangible_assets",
    "investment_property",
    "borrowings",
    "bonds",
    "lease_liabilities",
    "revenue",
    "cost_of_sales",
    "selling_general_admin",
    "income_tax_expense_benefit",
    "earnings_per_share",
    "depreciation_expense",
    "dividends",
    "cash_and_cash_equivalents_increase",
)


def check_fs_note_matches(report: FullReport, *, tolerance: int = 1) -> list[CheckResult]:
    results: list[CheckResult] = []
    classified = classify_report(report)
    for account_key in FS_NOTE_ACCOUNT_KEYS:
        fs_hits = [
            line for line in classified.statement_lines if line.account_key == account_key
        ]
        note_hits = [
            amount for amount in classified.note_amounts if amount.account_key == account_key
        ]
        note_hits = [hit for hit in note_hits if _plausible_amount(hit.amount)]
        if account_key == "lease_liabilities":
            results.extend(_check_lease_liability_matches(report, fs_hits, note_hits, tolerance))
            continue
        if not fs_hits or not note_hits:
            continue
        fs_hit = fs_hits[0]
        if account_key == "earnings_per_share" and not _plausible_eps(fs_hit.amount):
            # 주당금액이 1천만원을 넘으면 원/총액 파싱 잔재로 보고 거짓 gap 대신 abstain한다.
            continue
        note_hit = _select_note_hit_by_label(note_hits, account_key)
        if note_hit is None:
            # 라벨 근거 없이 첫 후보로 페어링하면 거짓 차이를 만든다.
            # 의미 기반 라벨 매칭이 실패하면 검증 후보로 보지 않는다.
            continue
        if account_key == "earnings_per_share" and not _plausible_eps(note_hit.amount):
            # 주석 쪽도 주당금액 상한을 넘으면 EPS 후보로 신뢰하지 않는다.
            continue
        difference = note_hit.amount - fs_hit.amount
        status = (
            MATCHED
            if amounts_agree(
                fs_hit.amount, note_hit.amount, tolerance, display_unit=note_hit.unit_multiplier
            )
            else UNEXPLAINED_GAP
        )
        effective_tolerance = display_unit_tolerance(
            fs_hit.amount, note_hit.amount, tolerance, display_unit=note_hit.unit_multiplier
        )
        matched_reason = (
            "financial statement amount agrees to note amount"
            if difference == 0
            else "financial statement amount agrees within display-unit rounding"
        )
        results.append(
            CheckResult(
                check_id=f"fs_note:{account_key}:{note_hit.note_no}",
                check_type="fs_note_match",
                status=status,
                scope="report",
                note_no=note_hit.note_no,
                title=f"{fs_hit.display_name} FS to note match",
                expected=fs_hit.amount,
                actual=note_hit.amount,
                difference=difference,
                tolerance=effective_tolerance,
                reason=matched_reason
                if status == MATCHED
                else "financial statement amount does not agree to note amount",
                evidence=[
                    CheckEvidence(_statement_evidence_label(fs_hit), fs_hit.amount, fs_hit.source),
                    CheckEvidence(_note_evidence_label(note_hit), note_hit.amount, note_hit.source),
                ],
            )
        )
    return results


def _statement_evidence_label(hit: ClassifiedStatementLine) -> str:
    return f"{hit.statement_title} {hit.label}"


def _note_evidence_label(hit: ClassifiedNoteAmount) -> str:
    return f"주석 {hit.note_no} {hit.note_title} {hit.label}"


def _check_lease_liability_matches(
    report: FullReport,
    fs_hits: list[ClassifiedStatementLine],
    classified_note_hits: list[ClassifiedNoteAmount],
    tolerance: int,
) -> list[CheckResult]:
    if not fs_hits:
        return []

    note_hits = _lease_note_candidates(report, classified_note_hits)
    note_hits = [hit for hit in note_hits if _plausible_amount(hit.amount)]
    if not note_hits:
        return []

    note_no = note_hits[0].note_no
    if not _has_single_consolidation_basis(report):
        return [
            _lease_not_tested_result(
                note_no,
                "total",
                "lease FS-note pairing requires a single consolidation basis",
            )
        ]

    fs_by_level, fs_unknown = _lease_statement_lines_by_level(report, fs_hits)
    # 당기·전기 별도 표는 _lease_note_hits_by_level이 당기(최저 인덱스) 표만 채택해 해소하므로
    # 여기서 multi-table abstain은 불필요하다(세 번째 반환값은 항상 False, 호환용으로만 유지).
    note_by_level, total_hits, _ = _lease_note_hits_by_level(report, note_hits)

    has_current_note = bool(note_by_level["current"])
    has_noncurrent_note = bool(note_by_level["noncurrent"])
    if has_current_note or has_noncurrent_note:
        return _lease_level_results(
            note_no, fs_by_level, note_by_level, tolerance, fs_unknown
        )

    if total_hits:
        return [
            _lease_total_result(
                note_no, fs_by_level, fs_unknown, total_hits, tolerance
            )
        ]

    return []


def _lease_level_results(
    note_no: str,
    fs_by_level: dict[str, list[ClassifiedStatementLine]],
    note_by_level: dict[str, list[ClassifiedNoteAmount]],
    tolerance: int,
    fs_unknown: list[ClassifiedStatementLine],
) -> list[CheckResult]:
    results: list[CheckResult] = []
    for level in ("current", "noncurrent"):
        fs_lines = fs_by_level[level]
        note_hits = note_by_level[level]
        if len(fs_lines) == 1 and len(note_hits) == 1 and not fs_unknown:
            results.append(
                _lease_match_result(note_no, level, fs_lines, note_hits[0], tolerance)
            )
        elif fs_lines or note_hits:
            results.append(
                _lease_not_tested_result(
                    note_no,
                    level,
                    "lease-liability level pairing is incomplete or ambiguous",
                    fs_lines,
                    note_hits,
                )
            )
    return results


def _lease_total_result(
    note_no: str,
    fs_by_level: dict[str, list[ClassifiedStatementLine]],
    fs_unknown: list[ClassifiedStatementLine],
    total_hits: list[ClassifiedNoteAmount],
    tolerance: int,
) -> CheckResult:
    current_lines = fs_by_level["current"]
    noncurrent_lines = fs_by_level["noncurrent"]
    if (
        len(current_lines) != 1
        or len(noncurrent_lines) != 1
        or fs_unknown
        or len(total_hits) != 1
    ):
        return _lease_not_tested_result(
            note_no,
            "total",
            "lease-liability total pairing requires exactly one current and one noncurrent line",
            [*current_lines, *noncurrent_lines, *fs_unknown],
            total_hits,
        )
    return _lease_match_result(
        note_no, "total", [current_lines[0], noncurrent_lines[0]], total_hits[0], tolerance
    )


def _lease_match_result(
    note_no: str,
    suffix: str,
    fs_lines: list[ClassifiedStatementLine],
    note_hit: ClassifiedNoteAmount,
    tolerance: int,
) -> CheckResult:
    expected = sum(line.amount for line in fs_lines)
    actual = note_hit.amount
    if suffix == "total":
        effective_tolerance = sum(
            display_unit_tolerance(
                line.amount,
                line.amount,
                tolerance,
                display_unit=note_hit.unit_multiplier,
            )
            for line in fs_lines
        )
    else:
        effective_tolerance = display_unit_tolerance(
            expected, actual, tolerance, display_unit=note_hit.unit_multiplier
        )
    difference = actual - expected
    status = MATCHED if abs(difference) <= effective_tolerance else UNEXPLAINED_GAP
    if status == MATCHED:
        reason = (
            "financial statement amount agrees to note amount"
            if difference == 0
            else "financial statement amount agrees within display-unit rounding"
        )
    else:
        reason = "financial statement amount does not agree to note amount"
    evidence = [
        CheckEvidence(_statement_evidence_label(fs_line), fs_line.amount, fs_line.source)
        for fs_line in fs_lines
    ]
    evidence.append(CheckEvidence(_note_evidence_label(note_hit), note_hit.amount, note_hit.source))
    return CheckResult(
        check_id=f"fs_note:lease_liabilities:{note_no}:{suffix}",
        check_type="fs_note_match",
        status=status,
        scope="report",
        note_no=note_no,
        title=f"리스부채 FS to note match ({suffix})",
        expected=expected,
        actual=actual,
        difference=difference,
        tolerance=effective_tolerance,
        reason=reason,
        evidence=evidence,
    )


def _lease_not_tested_result(
    note_no: str,
    suffix: str,
    reason: str,
    fs_lines: list[ClassifiedStatementLine] | None = None,
    note_hits: list[ClassifiedNoteAmount] | None = None,
) -> CheckResult:
    evidence = [
        CheckEvidence(_statement_evidence_label(fs_line), fs_line.amount, fs_line.source)
        for fs_line in (fs_lines or [])[:2]
    ]
    evidence.extend(
        CheckEvidence(_note_evidence_label(note_hit), note_hit.amount, note_hit.source)
        for note_hit in (note_hits or [])[:2]
    )
    return CheckResult(
        check_id=f"fs_note:lease_liabilities:{note_no}:{suffix}",
        check_type="fs_note_match",
        status=NOT_TESTED,
        scope="report",
        note_no=note_no,
        title=f"리스부채 FS to note match ({suffix})",
        expected=None,
        actual=None,
        difference=None,
        tolerance=0,
        reason=reason,
        evidence=evidence,
    )


def _lease_statement_lines_by_level(
    report: FullReport, fs_hits: list[ClassifiedStatementLine]
) -> tuple[dict[str, list[ClassifiedStatementLine]], list[ClassifiedStatementLine]]:
    table_rows = _section_table_rows(report.statements)
    by_level: dict[str, list[ClassifiedStatementLine]] = {"current": [], "noncurrent": []}
    unknown: list[ClassifiedStatementLine] = []
    for hit in fs_hits:
        if _lease_wrong_account_label(hit.label):
            continue
        source = _parse_source(hit.source)
        rows = table_rows.get((source["section"], source["table"])) if source else None
        level = infer_balance_level(rows or [], source["row"] if source else -1)
        if level in by_level:
            by_level[level].append(hit)
        else:
            unknown.append(hit)
    return by_level, unknown


def infer_balance_level(section_rows: list[list[str]], row_index: int) -> str:
    """Infer current/noncurrent balance level from label first, then BS headers."""
    label = ""
    if 0 <= row_index < len(section_rows) and section_rows[row_index]:
        label = section_rows[row_index][0]
    label_level = _balance_level_from_label(label)
    if label_level != "unknown":
        return label_level
    for index in range(min(row_index - 1, len(section_rows) - 1), -1, -1):
        if not section_rows[index]:
            continue
        header = _normalize_label(section_rows[index][0])
        if _is_noncurrent_liability_header(header):
            return "noncurrent"
        if _is_current_liability_header(header):
            return "current"
    return "unknown"


def _lease_note_candidates(
    report: FullReport, classified_note_hits: list[ClassifiedNoteAmount]
) -> list[ClassifiedNoteAmount]:
    # 당기(current-period)만 후보로 만든다. taxonomy 분류(classified_note_hits)는 같은
    # 행의 당기·전기를 모두 담아 레벨/총계 카운트를 부풀렸고, 그 결과 `==1` 가드가
    # 전부 abstain됐다(CJ 기말 [당기 2.11조, 전기 1.99조] → total 2개 → abstain). 행마다
    # row_amount_prefer_current로 당기 열만 추출하면 (행, 레벨)당 당기 후보 1개만 남는다.
    candidates: list[ClassifiedNoteAmount] = []
    seen_sources: set[str] = set()
    for section in report.notes:
        for table in _section_tables(section):
            if not (
                _lease_title_matches(section.title) or _lease_title_matches(table.heading)
            ):
                continue
            if not table.rows:
                continue
            headers = table.rows[0]
            current_cols = current_period_columns(headers)
            if not current_cols and prior_period_columns(headers):
                # 전기(prior-year)-only 표는 건너뛴다: 당기 헤더가 없으면
                # row_amount_prefer_current가 최우측(=전기) 열을 잡아, 그 표가 더 앞
                # 인덱스이고 리스가 YoY flat이면 틀린 기간으로 false match가 날 수 있다.
                continue
            for row_idx, row in enumerate(table.rows[1:], start=1):
                if not row or not _raw_lease_note_row_candidate(row[0]):
                    continue
                if current_cols:
                    # 당기 열이 식별되면 그 열만 사용(전기 열 혼입 차단).
                    amount, col_idx = amount_from_current_period(row, headers)
                else:
                    # 기간 헤더가 전혀 없는 단일 금액 표만 generic 폴백 허용.
                    amount, col_idx = row_amount_prefer_current(row, headers)
                if amount is None or col_idx is None:
                    continue
                source = f"{section.section_id}/table:{table.index}/row:{row_idx}/col:{col_idx}"
                if source in seen_sources:
                    continue
                seen_sources.add(source)
                candidates.append(
                    ClassifiedNoteAmount(
                        account_key="lease_liabilities",
                        display_name="리스부채",
                        note_no=section.note_no,
                        note_title=section.title,
                        label=row[0],
                        amount=amount * table.unit_multiplier,
                        source=source,
                        confidence=0.75,
                        evidence=(
                            "lease note row surfaced by check-layer lease-liability isolation"
                        ),
                        unit_multiplier=table.unit_multiplier,
                    )
                )
    return candidates


def _lease_note_hits_by_level(
    report: FullReport, note_hits: list[ClassifiedNoteAmount]
) -> tuple[dict[str, list[ClassifiedNoteAmount]], list[ClassifiedNoteAmount], bool]:
    by_level: dict[str, list[ClassifiedNoteAmount]] = {"current": [], "noncurrent": []}
    total_hits: list[ClassifiedNoteAmount] = []
    # 노트가 당기·전기 롤포워드를 *별도 표*로 싣는 경우가 흔하다(CJ 기말 표129[당기]/표130[전기];
    # NAVER 유동·비유동 리스부채 표111[당기]/표112[전기]). 각 표가 기말/유동/비유동을 가져
    # 카운트를 부풀려 모든 `==1` 가드를 abstain시켰다. 당기 롤포워드가 문서상 먼저 오므로
    # (table.index가 작음) 잔액 레벨/총계 행을 가진 표 중 **가장 앞선 표 하나만** 당기로 채택한다.
    # (리스채권 표는 _is_wrong_account_row로, 미할인 만기표는 _is_lease_schedule_table로 이미 제외.)
    table_levels: dict[tuple[str, int], list[tuple[str, ClassifiedNoteAmount]]] = {}
    for hit in note_hits:
        if not _is_isolated_lease_note_balance_row(hit):
            continue
        if _is_lease_schedule_table(report, hit):
            continue
        level = _lease_note_balance_level(hit)
        if level not in ("current", "noncurrent", "total"):
            continue
        source = _parse_source(hit.source)
        table_key = (source["section"], source["table"]) if source else ("", -1)
        table_levels.setdefault(table_key, []).append((level, hit))
    if not table_levels:
        return by_level, total_hits, False
    # 유동/비유동 레벨 행을 가진 표를 총계만 있는 표보다 우선한다(대한항공처럼 BS 분할
    # 노트 외에 6.0조짜리 sub-component 총계 표가 더 앞 인덱스에 있을 때, 후자를 잘못
    # 고르면 오해를 부르는 거짓 gap이 된다). 그 우선 집합 안에서 문서 순서상 가장 앞선
    # (=당기) 표를 채택. 레벨 표가 없으면(CJ처럼 기말 총계만) 총계 표 중 최저 인덱스.
    level_tables = [
        key
        for key, entries in table_levels.items()
        if any(level in ("current", "noncurrent") for level, _ in entries)
    ]
    current_year_table = min(level_tables) if level_tables else min(table_levels)
    for level, hit in table_levels[current_year_table]:
        if level in by_level:
            by_level[level].append(hit)
        elif level == "total":
            total_hits.append(hit)
    return by_level, total_hits, False


def _is_isolated_lease_note_balance_row(hit: ClassifiedNoteAmount) -> bool:
    return (
        _lease_title_matches(hit.note_title)
        and not _is_non_amount_field_label(hit.label)
        and _is_balance_row(hit)
        and not _is_wrong_account_row(hit, "lease_liabilities")
    )


def _lease_note_balance_level(hit: ClassifiedNoteAmount) -> str:
    level = _balance_level_from_label(hit.label)
    if level != "unknown":
        return level
    if _is_total_balance_label(hit.label) and _is_lease_liability_total_context(hit):
        return "total"
    return "unknown"


def _is_lease_liability_total_context(hit: ClassifiedNoteAmount) -> bool:
    # 무맥락 집계 라벨(합계/소계/장부금액/기말)은 그 자체로 리스부채 총계임을 보장하지
    # 않는다: 결합 주석("리스 및 사용권자산")의 자산측 소계가 FS 합산과 우연히 일치하면
    # 거짓 매치가 된다(row-label isolation은 무맥락 집계 라벨엔 무력). 라벨이 리스부채를
    # 명시하거나, note 제목이 순수 리스부채 맥락(리스 포함·사용권자산/자산 불포함)일 때만
    # 총계로 인정한다. CJ "기말"(제목 "리스부채")는 통과, "리스 및 사용권자산"의 bare
    # "합계"는 거부.
    if "리스부채" in _normalize_label(hit.label):
        return True
    title = _normalize_label(hit.note_title)
    return "리스" in title and not any(token in title for token in ("사용권자산", "자산"))


def _balance_level_from_label(label: str) -> str:
    normalized = _normalize_label(label)
    if "비유동" in normalized or "장기" in normalized:
        return "noncurrent"
    if "유동성" in normalized or "유동" in normalized:
        return "current"
    return "unknown"


def _is_total_balance_label(label: str) -> bool:
    normalized = _normalize_label(label)
    if normalized in {"기말", "합계", "소계", "장부금액", "리스부채", "리스부채합계"}:
        return True
    return normalized.startswith(("기말", "당기말")) or "총리스부채" in normalized


def _raw_lease_note_row_candidate(label: str) -> bool:
    normalized = _normalize_label(label)
    if "리스부채" in normalized or "리스채권" in normalized:
        return True
    return any(
        token in normalized
        for token in ("기말", "당기말", "합계", "소계", "장부금액", "유동", "비유동", "장기")
    )


def _lease_title_matches(title: str) -> bool:
    normalized = _normalize_label(title)
    return "리스부채" in normalized or "리스" in normalized


def _lease_wrong_account_label(label: str) -> bool:
    normalized = _normalize_label(label)
    return any(token in normalized for token in _LEASE_WRONG_ACCOUNT_ROW_TOKENS)


_LEASE_WRONG_ACCOUNT_ROW_TOKENS = (
    "사용권자산",
    "자산",
    "채권",
    "재고",
    "차입금",
    "사채",
    "투자부동산",
)


def _is_current_liability_header(normalized_label: str) -> bool:
    return normalized_label in {"유동", "유동부채"} or normalized_label.startswith("유동부채")


def _is_noncurrent_liability_header(normalized_label: str) -> bool:
    return normalized_label in {"비유동", "비유동부채"} or normalized_label.startswith(
        "비유동부채"
    )


def _is_lease_schedule_table(report: FullReport, hit: ClassifiedNoteAmount) -> bool:
    source = _parse_source(hit.source)
    if source is None:
        return False
    table = _section_table_map(report.notes).get((source["section"], source["table"]))
    if table is None:
        return False
    text = _normalize_label(
        " ".join([table.heading, *(" ".join(row) for row in table.rows)])
    )
    return any(token in text for token in ("미할인", "만기", "현재가치"))


def _has_single_consolidation_basis(report: FullReport) -> bool:
    # 미식별 scope("")도 distinct basis로 센다: split_report_by_scope는 연결·별도가 *둘 다*
    # 있을 때만 쪼개므로, 연결+미식별(별도 없음) 조합은 한 슬라이스에 섞인다. ""를 무시하면
    # 연결 유동 + 미식별 비유동이 합산돼 거짓 매치가 날 수 있다 → 혼재 시 abstain.
    scopes = {section.scope for section in [*report.statements, *report.notes]}
    return len(scopes) <= 1


def _section_table_rows(sections: list[ReportSection]) -> dict[tuple[str, int], list[list[str]]]:
    return {
        (section.section_id, table.index): table.rows
        for section in sections
        for table in _section_tables(section)
    }


def _section_table_map(sections: list[ReportSection]) -> dict[tuple[str, int], ReportTable]:
    return {
        (section.section_id, table.index): table
        for section in sections
        for table in _section_tables(section)
    }


def _section_tables(section: ReportSection) -> list[ReportTable]:
    return [block.table for block in section.blocks if block.table is not None]


def _parse_source(source: str) -> dict[str, int | str] | None:
    try:
        section, table_part, row_part, col_part = source.rsplit("/", 3)
        if not (
            table_part.startswith("table:")
            and row_part.startswith("row:")
            and col_part.startswith("col:")
        ):
            return None
        return {
            "section": section,
            "table": int(table_part.removeprefix("table:")),
            "row": int(row_part.removeprefix("row:")),
            "col": int(col_part.removeprefix("col:")),
        }
    except (ValueError, TypeError):
        return None


_NOTE_LABEL_PRIORITY = (
    "기말장부금액",
    "기말순장부금액",
    "기말금액",
    "기말잔액",
    "기말",
    "합계",
    "소계",
)

# 단독 "기말"은 접두 매칭으로만 판정한다. 진짜 기말 총계 행은 "기말", "기말금액",
# "기말의 무형자산 및 영업권", "기말 영업권 이외의 무형자산"처럼 "기말"로 시작하지만,
# substring 매칭이면 "자산화된 연구개발비 장부금액" 같은 하위 구성요소가 아니라 오히려
# "기말환율조정"/"기말 평가손익" 같은 하위 변동행까지 끌어와 진짜 총계를 밀어낼 수 있다.
# 변동행은 _is_balance_row(아래 _NON_BALANCE_LABEL_TOKENS)에서 먼저 걸러지고, 접두 매칭은
# "기말"로 시작하는 잔액 총계만 잡는다(구성요소·움직임이 아닌 진짜 기말잔액).
_PREFIX_MATCH_LABEL_TOKENS = frozenset({"기말"})


def _select_note_hit_by_label(
    note_hits: list[ClassifiedNoteAmount], account_key: str
) -> ClassifiedNoteAmount | None:
    """Pick the semantically strongest note row without considering amount value."""
    note_hits = [hit for hit in note_hits if not _is_non_amount_field_label(hit.label)]
    if not note_hits:
        return None

    priority = _label_priority_for_account(account_key)
    # taxonomy가 무관한 주석의 행을 이 계정으로 과분류할 수 있으므로(예: 금융위험관리
    # '장부금액 합계'를 유형자산으로), 계정 주제와 일치하는 note_title 후보를 우선한다.
    # 주제 일치 후보가 있으면 그 안에서만 라벨 우선순위로 고른다. 없으면(주제 라벨이
    # 없는 계정 등) 기존 동작으로 폴백한다.
    title_aliases = _note_title_aliases_for_account(account_key)
    topical = [hit for hit in note_hits if _title_matches(hit.note_title, title_aliases)]
    if account_key in _SIGNED_VALUE_ACCOUNTS:
        # EPS 손실·법인세효익·현금감소·배당은 음수가 정상이고, 주석 제목이 계정명과
        # 달라(예: 법인세 매칭은 폴백 경유) 기존 폴백 동작을 그대로 유지한다.
        pool = topical if topical else note_hits
    elif topical:
        # 주제 일치 주석을 찾았으면, 그 안에서 잔액이 아닌 행은 후보에서 뺀다. 재무상태표
        # 잔액·항상 양수인 비용은 음수가 될 수 없고, 재분류('유동성 대체')·발행차금 contra
        # 행은 순변동/조정이지 잔액이 아니다(예: 차입금 주석의 "비유동차입금의 유동성 대체
        # 부분" -1,120,559,090,000). 잔액 행이 하나도 없으면 무관한 주석의 행으로
        # 폴백하지 않고 abstain한다(거짓 차이·garbage 페어링 방지).
        balance_topical = [
            hit
            for hit in topical
            if _is_balance_row(hit) and not _is_wrong_account_row(hit, account_key)
        ]
        if not balance_topical:
            return None
        pool = balance_topical
    elif account_key in _BALANCE_SHEET_ACCOUNTS:
        # 재무상태표 잔액 계정인데 제목이 일치하는 주석이 아예 없으면, taxonomy가 무관한
        # 주석(매출채권·기타투자자산·현금흐름표 등)을 과분류한 행으로 폴백하지 않고
        # abstain한다(예: PPE 1.24조 vs 매출채권 267백만, 사채 96조 vs SPC 10백만 방지).
        # 잔액 계정의 진짜 주석은 항상 제목이 일치하므로(차입금/사채/유형자산 등), 제목
        # 불일치는 곧 진짜 주석 부재를 뜻한다.
        return None
    else:
        # 비잔액·비음수 계정(revenue/cost/sga/depreciation)은 주석 제목이 계정명과
        # 달라서(예: 매출 주석 "영업부문") 주제 일치가 안 되므로 기존 폴백 유지.
        pool = note_hits
    ranked = [
        (rank, index, hit)
        for index, hit in enumerate(pool)
        if (rank := _label_rank(hit.label, priority)) is not None
    ]
    if not ranked:
        return None
    ranked.sort(key=lambda item: (item[0], item[1]))
    return ranked[0][2]


# DART 원화 공시에서 1경(1e16)원을 넘는 단일 금액은 셀 병합/병기 텍스트의
# 파싱 잔재로 본다. 거짓 페어링 방지를 위한 보수적 상한.
_MAX_PLAUSIBLE_AMOUNT = 10**16


def _plausible_amount(amount: int | None) -> bool:
    return amount is not None and abs(amount) < _MAX_PLAUSIBLE_AMOUNT


_MAX_PLAUSIBLE_EPS = 10_000_000


def _plausible_eps(amount: int | None) -> bool:
    return amount is not None and abs(amount) <= _MAX_PLAUSIBLE_EPS


def _label_priority_for_account(account_key: str) -> tuple[str, ...]:
    aliases: list[str] = list(_NOTE_LABEL_PRIORITY)
    entry = next((item for item in TAXONOMY if item.key == account_key), None)
    if entry is not None:
        aliases.extend(entry.note_amount_aliases)
    return tuple(dict.fromkeys(_normalize_label(alias) for alias in aliases if alias))


def _note_title_aliases_for_account(account_key: str) -> tuple[str, ...]:
    entry = next((item for item in TAXONOMY if item.key == account_key), None)
    if entry is None:
        return ()
    aliases = [entry.display_name, *entry.note_title_aliases]
    return tuple(dict.fromkeys(_normalize_label(alias) for alias in aliases if alias))


def _title_matches(note_title: str, title_aliases: tuple[str, ...]) -> bool:
    normalized = _normalize_label(note_title or "")
    return any(alias and alias in normalized for alias in title_aliases)


# 음수 금액이 정상인 계정(잔액 필터의 음수 제외를 적용하면 안 되는 계정).
# EPS는 주당손실(음수), 법인세는 효익(음수), 현금증감은 감소(음수), 배당은 SCE측 음수.
_SIGNED_VALUE_ACCOUNTS = frozenset(
    {
        "earnings_per_share",
        "income_tax_expense_benefit",
        "cash_and_cash_equivalents_increase",
        "dividends",
    }
)

# 재무상태표 잔액 계정. 진짜 주석 제목이 항상 계정명과 일치하므로(차입금/사채/유형자산/
# 무형자산/투자부동산/리스부채), 제목 일치 주석이 없으면 곧 진짜 주석 부재 → 과분류된
# 무관 주석으로 폴백하지 않고 abstain한다. (revenue/cost 등 P&L은 주석 제목이 계정명과
# 달라 폴백이 필요하므로 제외.)
_BALANCE_SHEET_ACCOUNTS = frozenset(
    {
        "property_plant_equipment",
        "intangible_assets",
        "investment_property",
        "borrowings",
        "bonds",
        "lease_liabilities",
    }
)

# 재무상태표 *순*잔액 행이 아니라 순변동/조정/contra/gross 행임을 나타내는 라벨 토큰.
# "대체"=유동성 대체(reclassification), "할인발행차금"/"할증발행차금"=사채 발행차금 contra,
# "환율조정"/"환산"=외화환산 변동, "평가손익"=공정가치 평가 변동(움직임이지 잔액 아님),
# "취득원가"=gross 원가, "누계액"=감가상각/손상차손 누계 contra(순장부금액이 아님).
# 이 토큰들은 "기말환율조정"/"기말 취득원가"/"기말 손상차손누계액"처럼 "기말"로 시작해도
# 순장부금액 총계가 아니므로, 접두 매칭된 "기말"이 진짜 순총계(예: 투자부동산 "장부금액")를
# 밀어내지 못하게 한다. ADR-0010의 "총장부금액/취득원가는 절대 선택하지 않는다" 원칙과 일관.
_NON_BALANCE_LABEL_TOKENS = (
    "대체",
    "할인발행차금",
    "할증발행차금",
    "환율조정",
    "환산",
    "평가손익",
    "취득원가",
    "누계액",
)

# 실 triage에서 금액이 아닌 필드로 확인된 토큰만 제외한다:
# 명칭=차입금명칭, 기준일=배당기준일, 청구권=중도상환청구권, 수량=배출권 수량.
_NON_AMOUNT_FIELD_LABEL_TOKENS = ("명칭", "기준일", "청구권", "수량")


def _is_non_amount_field_label(label: str) -> bool:
    normalized = _normalize_label(label)
    return any(token in normalized for token in _NON_AMOUNT_FIELD_LABEL_TOKENS)


_LIABILITY_RECEIVABLE_REJECT_ACCOUNTS = frozenset(
    {"borrowings", "bonds", "lease_liabilities"}
)


def _is_wrong_account_row(hit: ClassifiedNoteAmount, account_key: str) -> bool:
    if account_key not in _LIABILITY_RECEIVABLE_REJECT_ACCOUNTS:
        return False
    if account_key == "lease_liabilities":
        return _lease_wrong_account_label(hit.label)
    # 채권은 받을 권리(자산)이므로 차입금/사채/리스부채 같은 부채 잔액으로 페어링하지 않는다.
    return "채권" in _normalize_label(hit.label)


def _is_balance_row(hit: ClassifiedNoteAmount) -> bool:
    """잔액으로 페어링 가능한 행인지. 음수이거나 재분류/contra 라벨이면 잔액이 아니다."""
    if hit.amount is not None and hit.amount < 0:
        return False
    normalized = _normalize_label(hit.label)
    return not any(token in normalized for token in _NON_BALANCE_LABEL_TOKENS)


def _label_rank(label: str, priority: tuple[str, ...]) -> int | None:
    normalized = _normalize_label(label)
    for index, alias in enumerate(priority):
        if alias in _PREFIX_MATCH_LABEL_TOKENS:
            if normalized.startswith(alias):
                return index
        elif alias and alias in normalized:
            return index
    return None


def _normalize_label(value: str) -> str:
    return "".join(value.split())
