"""Financial statement to note matching checks."""

from __future__ import annotations

from dart_footing_reconciler.amount_compare import amounts_agree, display_unit_tolerance
from dart_footing_reconciler.checks import CheckEvidence, CheckResult, MATCHED, UNEXPLAINED_GAP
from dart_footing_reconciler.document import FullReport
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
