"""Canonical account and note topic classification.

The taxonomy is intentionally internal: external DART/FSC labels and common
filing variants map into stable engine keys, while the original source label is
kept as evidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.document import FullReport, ReportSection
from dart_footing_reconciler.table_semantics import row_amount_prefer_current


@dataclass(frozen=True)
class TaxonomyEntry:
    key: str
    display_name: str
    statement_titles: tuple[str, ...]
    statement_aliases: tuple[str, ...]
    note_title_aliases: tuple[str, ...]
    note_amount_aliases: tuple[str, ...]
    note_amount_exclusions: tuple[str, ...] = ()
    fsc_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ClassifiedStatementLine:
    account_key: str
    display_name: str
    statement_title: str
    label: str
    amount: int
    source: str
    confidence: float
    evidence: str


@dataclass(frozen=True)
class ClassifiedNoteTopic:
    topic_key: str
    display_name: str
    note_no: str
    title: str
    section_id: str
    confidence: float
    evidence: str
    source: str = ""


@dataclass(frozen=True)
class ClassifiedNoteAmount:
    account_key: str
    display_name: str
    note_no: str
    note_title: str
    label: str
    amount: int
    source: str
    confidence: float
    evidence: str
    #: Disclosure step of the source note table in KRW (1 = 원, 1_000 = 천원,
    #: 1_000_000 = 백만원). ``amount`` is already scaled by this; it is kept so
    #: comparisons can allow sub-display-unit rounding against finer FS amounts.
    unit_multiplier: int = 1


@dataclass(frozen=True)
class ClassifiedReport:
    statement_lines: list[ClassifiedStatementLine]
    note_topics: list[ClassifiedNoteTopic]
    note_amounts: list[ClassifiedNoteAmount]


TAXONOMY: tuple[TaxonomyEntry, ...] = (
    TaxonomyEntry(
        "property_plant_equipment",
        "유형자산",
        ("재무상태표",),
        ("유형자산", "유형자산순액", "propertyplantandequipment"),
        ("유형자산", "유형자산및사용권자산", "유형자산및투자부동산"),
        ("장부금액", "기말장부금액", "순장부금액", "장부가액", "기말"),
        fsc_codes=("ifrs-full_PropertyPlantAndEquipment",),
    ),
    TaxonomyEntry(
        "intangible_assets",
        "무형자산",
        ("재무상태표",),
        ("무형자산", "무형자산순액", "intangibleassets"),
        ("무형자산",),
        ("장부금액", "기말장부금액", "순장부금액", "장부가액", "기말"),
        fsc_codes=("ifrs-full_IntangibleAssets", "ifrs-full_IntangibleAssetsAndGoodwill"),
    ),
    TaxonomyEntry(
        "investment_property",
        "투자부동산",
        ("재무상태표",),
        ("투자부동산", "investmentproperty"),
        ("투자부동산",),
        ("장부금액", "공정가치", "기말장부금액", "기말"),
        fsc_codes=("ifrs-full_InvestmentProperty",),
    ),
    TaxonomyEntry(
        "cash_and_cash_equivalents",
        "현금및현금성자산",
        ("재무상태표",),
        ("현금및현금성자산", "cashandcashequivalents"),
        ("현금및현금성자산", "범주별금융상품"),
        ("현금및현금성자산", "현금및현금성자산의기말잔액", "기말"),
        ("증가", "순증가", "감소", "순감소"),
        fsc_codes=("ifrs-full_CashAndCashEquivalents",),
    ),
    TaxonomyEntry(
        "financial_deposits",
        "금융상품",
        ("재무상태표",),
        (
            "단기금융상품",
            "장기금융상품",
            "장기금융자산",
            "shorttermfinancialinstruments",
            "longtermfinancialinstruments",
        ),
        ("사용이제한된금융자산",),
        ("단기금융상품", "장기금융상품", "장기금융자산", "금융상품"),
        fsc_codes=(
            "ifrs-full_ShorttermFinancialInstruments",
            "ifrs-full_LongtermFinancialInstruments",
        ),
    ),
    TaxonomyEntry(
        "trade_receivables",
        "매출채권",
        ("재무상태표",),
        ("매출채권", "매출채권및기타채권", "tradeandotherreceivables", "tradereceivables"),
        (
            "매출채권및기타채권",
            "매출채권및기타수취채권",
            "매출채권및기타수취채권",
            "매출채권및계약자산",
            "매출채권및기타채권",
            "매출채권",
        ),
        ("매출채권", "외상매출금", "받을어음"),
        ("대손충당금", "손실충당금", "현재가치할인차금"),
        fsc_codes=("ifrs-full_CurrentTradeReceivables", "ifrs-full_NoncurrentTradeReceivables", "ifrs-full_TradeReceivables"),
    ),
    TaxonomyEntry(
        "other_financial_assets",
        "기타금융자산",
        ("재무상태표",),
        (
            "기타금융자산",
            "기타유동금융자산",
            "기타비유동금융자산",
            "장기금융자산",
            "otherfinancialassets",
        ),
        ("기타금융자산",),
        ("기타금융자산", "기타유동금융자산", "기타비유동금융자산", "장기금융자산"),
        fsc_codes=(
            "ifrs-full_CurrentOtherFinancialAssets",
            "ifrs-full_NoncurrentOtherFinancialAssets",
            "ifrs-full_OtherFinancialAssets",
        ),
    ),
    TaxonomyEntry(
        "contract_assets",
        "계약자산",
        ("재무상태표",),
        ("미청구공사", "계약자산", "contractassets"),
        ("계약체결원가나계약이행원가중에서인식한자산", "수주계약현황"),
        ("미청구공사", "계약자산"),
        fsc_codes=("ifrs-full_ContractAssets", "ifrs-full_CurrentContractAssets"),
    ),
    TaxonomyEntry(
        "other_assets",
        "기타자산",
        ("재무상태표",),
        ("기타유동자산", "기타비유동자산", "기타자산", "otherassets"),
        ("기타유동자산및기타비유동자산", "기타자산"),
        ("기타유동자산", "기타비유동자산", "기타자산"),
        fsc_codes=(
            "ifrs-full_OtherCurrentAssets",
            "ifrs-full_OtherNoncurrentAssets",
            "ifrs-full_OtherAssets",
        ),
    ),
    TaxonomyEntry(
        "current_tax_assets",
        "당기법인세자산",
        ("재무상태표",),
        ("당기법인세자산", "currenttaxassets"),
        ("당기법인세자산",),
        ("당기법인세자산", "회수가능성이높은법인세자산"),
        fsc_codes=("ifrs-full_CurrentTaxAssets",),
    ),
    TaxonomyEntry(
        "deferred_tax_assets",
        "이연법인세자산",
        ("재무상태표",),
        ("이연법인세자산", "deferredtaxassets"),
        ("이연법인세자산", "순이연법인세자산", "이연법인세자산과부채"),
        ("이연법인세자산", "순이연법인세자산"),
        fsc_codes=("ifrs-full_DeferredTaxAssets",),
    ),
    TaxonomyEntry(
        "current_tax_liabilities",
        "당기법인세부채",
        ("재무상태표",),
        ("당기법인세부채", "currenttaxliabilities"),
        ("당기법인세부채",),
        ("당기법인세부채",),
        fsc_codes=("ifrs-full_CurrentTaxLiabilities",),
    ),
    TaxonomyEntry(
        "deferred_tax_liabilities",
        "이연법인세부채",
        ("재무상태표",),
        ("이연법인세부채", "deferredtaxliabilities"),
        ("이연법인세부채", "이연법인세자산과부채"),
        ("이연법인세부채",),
        fsc_codes=("ifrs-full_DeferredTaxLiabilities",),
    ),
    TaxonomyEntry(
        "borrowings",
        "차입금",
        ("재무상태표",),
        ("차입금", "단기차입금", "장기차입금", "borrowings"),
        ("차입금", "단기차입금", "장기차입금"),
        ("기말", "장부금액", "유동", "비유동"),
        fsc_codes=("ifrs-full_Borrowings", "ifrs-full_CurrentBorrowings", "ifrs-full_NoncurrentBorrowings"),
    ),
    TaxonomyEntry(
        "bonds",
        "사채",
        ("재무상태표",),
        ("사채", "전환사채", "신주인수권부사채", "bonds"),
        ("사채", "전환사채", "신주인수권부사채"),
        ("기말", "장부금액", "유동", "비유동"),
        fsc_codes=("ifrs-full_BondsIssued", "ifrs-full_CurrentBondsIssued", "ifrs-full_NoncurrentBondsIssued"),
    ),
    TaxonomyEntry(
        "lease_liabilities",
        "리스부채",
        ("재무상태표",),
        ("리스부채", "leaseliabilities"),
        ("리스부채", "리스"),
        ("기말", "장부금액", "유동", "비유동"),
        fsc_codes=("ifrs-full_LeaseLiabilities", "ifrs-full_CurrentLeaseLiabilities", "ifrs-full_NoncurrentLeaseLiabilities"),
    ),
    TaxonomyEntry(
        "revenue",
        "매출액",
        ("손익계산서", "포괄손익계산서"),
        ("매출액", "수익매출액", "영업수익", "revenue"),
        ("고객과의계약에서생기는수익", "매출액"),
        ("매출액", "영업수익", "고객과의계약에서생기는수익", "수익합계"),
        fsc_codes=("ifrs-full_Revenue", "ifrs-full_RevenueFromContractsWithCustomers"),
    ),
    TaxonomyEntry(
        "cost_of_sales",
        "매출원가",
        ("손익계산서", "포괄손익계산서"),
        ("매출원가", "영업비용", "costofsales"),
        ("비용의성격별분류", "매출원가및판매비와관리비", "성격별비용"),
        (),
        fsc_codes=("ifrs-full_CostOfSales",),
    ),
    TaxonomyEntry(
        "selling_general_admin",
        "판매비와관리비",
        ("손익계산서", "포괄손익계산서"),
        ("판매비와관리비", "판매및일반관리비", "sellinggeneralandadministrativeexpense"),
        ("비용의성격별분류", "판매비와관리비", "성격별비용"),
        (),
        fsc_codes=("ifrs-full_SellingGeneralAndAdministrativeExpense",),
    ),
    TaxonomyEntry(
        "other_operating_income",
        "영업외수익",
        ("손익계산서", "포괄손익계산서"),
        ("영업외수익", "기타수익", "otherincome"),
        ("영업외수익", "기타수익", "영업외손익", "기타손익"),
        ("영업외수익", "기타수익", "수익합계"),
    ),
    TaxonomyEntry(
        "other_operating_expense",
        "영업외비용",
        ("손익계산서", "포괄손익계산서"),
        ("영업외비용", "기타비용", "otherexpense"),
        ("영업외비용", "기타비용", "영업외손익", "기타손익"),
        ("영업외비용", "기타비용", "비용합계"),
    ),
    TaxonomyEntry(
        "finance_income",
        "금융수익",
        ("손익계산서", "포괄손익계산서"),
        ("금융수익", "financeincome"),
        ("금융수익", "금융손익", "금융수익및금융비용", "금융수익및금융원가"),
        ("금융수익", "이자수익", "배당금수익", "외환차익", "외화환산이익"),
        fsc_codes=("ifrs-full_FinanceIncome",),
    ),
    TaxonomyEntry(
        "finance_costs",
        "금융비용",
        ("손익계산서", "포괄손익계산서"),
        ("금융비용", "금융원가", "financecosts"),
        ("금융비용", "금융원가", "금융손익", "금융수익및금융비용", "금융수익및금융원가"),
        ("금융비용", "금융원가", "이자비용", "외환차손", "외화환산손실"),
        fsc_codes=("ifrs-full_FinanceCosts",),
    ),
    TaxonomyEntry(
        "income_tax_expense_benefit",
        "법인세비용(수익)",
        ("손익계산서", "포괄손익계산서"),
        ("법인세비용(수익)", "incometaxexpense"),
        ("법인세비용(수익)", "이연법인세"),
        ("법인세비용(수익)", "당기법인세비용(수익)", "이연법인세비용(수익)", "법인세비용(수익)합계"),
        ("차감전", "세율로계산", "적용세율", "법인세효과"),
        fsc_codes=("ifrs-full_IncomeTaxExpenseContinuingOperations", "ifrs-full_IncomeTaxExpense"),
    ),
    TaxonomyEntry(
        "earnings_per_share",
        "주당이익(손실)",
        ("손익계산서", "포괄손익계산서"),
        ("기본주당이익(손실)", "희석주당이익(손실)", "기본주당순이익(손실)", "희석주당순이익(손실)", "주당이익(손실)", "주당순이익(손실)"),
        ("주당이익(손실)", "주당순이익(손실)"),
        ("기본주당이익(손실)", "희석주당이익(손실)", "기본주당순이익(손실)", "희석주당순이익(손실)", "주당이익(손실)", "주당순이익(손실)"),
    ),
    TaxonomyEntry(
        "depreciation_expense",
        "감가상각비",
        ("손익계산서", "포괄손익계산서", "현금흐름표"),
        ("감가상각비", "depreciation"),
        ("유형자산", "비용의성격별분류"),
        ("감가상각비",),
    ),
    TaxonomyEntry(
        "dividends",
        "배당",
        ("자본변동표", "현금흐름표"),
        ("배당", "배당금", "dividends"),
        ("배당", "배당금"),
        ("배당", "배당금"),
        # 배당 reconciliation은 소유주에게 "지급된" 현금배당 총액만 대상으로 한다. 같은
        # 라벨에 섞여 들어오는 다른 개념(배당수익=income, 수취/수령=received,
        # 주식수=count, 주당/배당률/배당성향=per-share·rate·ratio, 평균적립금=reserve,
        # 미지급=payable, 비지배=NCI, 신종자본증권=hybrid coupon, 주식배당=stock
        # dividend, 배당권 파싱 잔재, "인식되지 아니한 배당금"=보고기간 후 제안된
        # 배당(subsequent event))은 양쪽(주석·재무제표)에서 모두 제외한다.
        # "인식되지"는 정타인 "인식된"과 구별된다. "배당성향"은 금액이 아닌 비율이라
        # 페어링하면 act=0/비율값 같은 무의미 행을 고른다.
        (
            "수익",
            "수취",
            "수령",
            "받은",
            "받을",
            "주식수",
            "주당",
            "배당률",
            "배당성향",
            "평균적립금",
            "미지급",
            "배당권",
            "비지배",
            "신종자본증권",
            "주식배당",
            "인식되지",
        ),
    ),
    TaxonomyEntry(
        "cash_and_cash_equivalents_increase",
        "현금및현금성자산의증가",
        ("현금흐름표",),
        ("현금및현금성자산의증가", "현금및현금성자산의순증가", "cashandcashequivalents"),
        ("현금및현금성자산",),
        ("현금및현금성자산의증가", "현금및현금성자산의순증가", "기말"),
    ),
)


def classify_report(report: FullReport) -> ClassifiedReport:
    """Classify statement lines and note topics into canonical internal keys."""
    statement_lines = _classify_statement_lines(report.statements)
    note_topics = _classify_note_topics(report.notes)
    generic_note_topics, generic_note_amounts = _classify_generic_note_matches(
        report.notes, statement_lines
    )
    return ClassifiedReport(
        statement_lines=statement_lines,
        note_topics=note_topics + generic_note_topics,
        note_amounts=_classify_note_amounts(report.notes, note_topics) + generic_note_amounts,
    )


def _classify_statement_lines(sections: list[ReportSection]) -> list[ClassifiedStatementLine]:
    lines: list[ClassifiedStatementLine] = []
    for section in sections:
        for block in section.blocks:
            table = block.table
            if table is None or not table.rows:
                continue
            headers = table.rows[0]
            for row_idx, row in enumerate(table.rows[1:], start=1):
                if not row:
                    continue
                label = row[0]
                row_acodes = _row_acodes(table, row_idx)
                entry = _entry_for_acodes(row_acodes) or _entry_for_statement_label(section.title, label)
                amount, col_idx = _row_amount(row, headers)
                if amount is None or col_idx is None:
                    continue
                amount *= table.unit_multiplier
                if entry is None:
                    generic_concept = _generic_statement_concept(row_acodes)
                    if generic_concept is None:
                        continue
                    lines.append(
                        ClassifiedStatementLine(
                            account_key=f"fsc:{_normalize_code(generic_concept)}",
                            display_name=label,
                            statement_title=section.title,
                            label=label,
                            amount=amount,
                            source=f"{section.section_id}/table:{table.index}/row:{row_idx}/col:{col_idx}",
                            confidence=0.7,
                            evidence=f"statement acode preserved as generic FSC account: {generic_concept}",
                        )
                    )
                    continue
                lines.append(
                    ClassifiedStatementLine(
                        account_key=entry.key,
                        display_name=entry.display_name,
                        statement_title=section.title,
                        label=label,
                        amount=amount,
                        source=f"{section.section_id}/table:{table.index}/row:{row_idx}/col:{col_idx}",
                        confidence=1.0,
                        evidence=_statement_evidence(entry, label, row_acodes),
                    )
                )
    return lines


def _classify_note_topics(sections: list[ReportSection]) -> list[ClassifiedNoteTopic]:
    topics: list[ClassifiedNoteTopic] = []
    seen: set[tuple[str, str, str]] = set()
    for section in sections:
        for entry in _entries_for_note_title(section.title):
            _append_note_topic(
                topics,
                seen,
                entry,
                section.note_no,
                section.title,
                section.section_id,
                0.9,
                f"note title matched canonical alias: {section.title}",
            )
        for block in section.blocks:
            table = block.table
            if table is None:
                continue
            table_entries = _entries_for_note_title(table.heading)
            if not table_entries:
                table_entry = _entry_for_table_acodes(table)
                table_entries = [table_entry] if table_entry is not None else []
            for table_entry in table_entries:
                _append_note_topic(
                    topics,
                    seen,
                    table_entry,
                    section.note_no,
                    _inferred_note_title(section, table.heading),
                    section.section_id,
                    0.75,
                    f"note table heading or acode matched canonical alias: {table.heading}",
                    source=f"{section.section_id}/table:{table.index}",
                )
    return topics


def _classify_note_amounts(
    sections: list[ReportSection], topics: list[ClassifiedNoteTopic]
) -> list[ClassifiedNoteAmount]:
    amounts: list[ClassifiedNoteAmount] = []
    for section in sections:
        for block in section.blocks:
            table = block.table
            if table is None or not table.rows:
                continue
            table_entry = _entry_for_note_title(section.title) or _entry_for_note_title(table.heading)
            headers = table.rows[0]
            for row_idx, row in enumerate(table.rows[1:], start=1):
                if not row:
                    continue
                row_acodes = _row_acodes(table, row_idx)
                acode_entry = _entry_for_acodes(row_acodes)
                row_entry = _entry_for_note_amount_label(row[0])
                table_row_entry = _table_entry_for_note_row(table_entry, row[0])
                entry = acode_entry or _note_row_entry(row_entry, table_row_entry, row[0])
                if entry is None:
                    continue
                label_matched = _matches_any(row[0], entry.note_amount_aliases)
                acode_matched = (
                    _entry_for_acodes(row_acodes) == entry
                    and _allow_note_acode_match(entry, table.heading, row[0])
                )
                if not label_matched and not acode_matched:
                    continue
                if _matches_any(row[0], entry.note_amount_exclusions):
                    continue
                amount, col_idx = _row_amount(row, headers)
                if amount is None or col_idx is None:
                    continue
                amount *= table.unit_multiplier
                amounts.append(
                    ClassifiedNoteAmount(
                        account_key=entry.key,
                        display_name=entry.display_name,
                        note_no=section.note_no,
                        note_title=section.title,
                        label=row[0],
                        amount=amount,
                        source=f"{section.section_id}/table:{table.index}/row:{row_idx}/col:{col_idx}",
                        confidence=0.9,
                        evidence=_note_amount_evidence(entry, section.title, table.heading, row[0], row_acodes),
                        unit_multiplier=table.unit_multiplier,
                    )
                )
    return amounts


def _classify_generic_note_matches(
    sections: list[ReportSection], statement_lines: list[ClassifiedStatementLine]
) -> tuple[list[ClassifiedNoteTopic], list[ClassifiedNoteAmount]]:
    generic_lines = [line for line in statement_lines if line.account_key.startswith("fsc:")]
    if not generic_lines:
        return [], []

    topics: list[ClassifiedNoteTopic] = []
    amounts: list[ClassifiedNoteAmount] = []
    seen_topics: set[tuple[str, str]] = set()
    seen_amounts: set[tuple[str, str]] = set()
    for section in sections:
        for block in section.blocks:
            table = block.table
            if table is None or not table.rows:
                continue
            if _exclude_generic_note_table(table.heading):
                continue
            _append_generic_topic_only_matches(
                topics, seen_topics, section, table, generic_lines
            )
            headers = table.rows[0]
            for row_idx, row in enumerate(table.rows[1:], start=1):
                if not row:
                    continue
                row_acodes = _row_acodes(table, row_idx)
                for line in generic_lines:
                    amount, col_idx = _generic_note_row_amount(line, row, row_acodes, table.unit_multiplier)
                    if amount is None or col_idx is None:
                        continue
                    table_source = f"{section.section_id}/table:{table.index}"
                    topic_key = (line.account_key, table_source)
                    if topic_key not in seen_topics:
                        seen_topics.add(topic_key)
                        topics.append(
                            ClassifiedNoteTopic(
                                topic_key=line.account_key,
                                display_name=line.display_name,
                                note_no=section.note_no,
                                title=_inferred_generic_note_title(line, section.title, table.heading),
                                section_id=section.section_id,
                                confidence=0.65,
                                evidence=f"generic FSC account matched note row: {line.label} / {row[0]}",
                                source=table_source,
                            )
                        )
                    amount_source = f"{table_source}/row:{row_idx}/col:{col_idx}"
                    amount_key = (line.account_key, amount_source)
                    if amount_key in seen_amounts:
                        continue
                    seen_amounts.add(amount_key)
                    amounts.append(
                        ClassifiedNoteAmount(
                            account_key=line.account_key,
                            display_name=line.display_name,
                            note_no=section.note_no,
                            note_title=section.title,
                            label=row[0],
                            amount=amount,
                            source=amount_source,
                            confidence=0.65,
                            evidence=f"generic FSC account amount matched statement line: {line.label} / {row[0]}",
                            unit_multiplier=table.unit_multiplier,
                        )
                    )
    return topics, amounts


def _append_generic_topic_only_matches(
    topics: list[ClassifiedNoteTopic],
    seen_topics: set[tuple[str, str]],
    section: ReportSection,
    table,
    generic_lines: list[ClassifiedStatementLine],
) -> None:
    table_source = f"{section.section_id}/table:{table.index}"
    if _exclude_generic_note_table(table.heading):
        return
    normalized_heading = _normalize(table.heading)
    normalized_row_labels = [
        _normalize(cell)
        for row in table.rows[1:]
        for cell in row
        if cell and parse_amount(cell) is None
    ]
    for line in generic_lines:
        if _is_structural_statement_label(line.label):
            continue
        label_variants = _generic_label_variants(line.label)
        if not label_variants:
            continue
        heading_matched = any(variant in normalized_heading for variant in label_variants)
        row_matched = any(
            variant == row_label or variant in row_label
            for row_label in normalized_row_labels
            for variant in label_variants
        )
        if not heading_matched and not row_matched:
            continue
        topic_key = (line.account_key, table_source)
        if topic_key in seen_topics:
            continue
        seen_topics.add(topic_key)
        topics.append(
            ClassifiedNoteTopic(
                topic_key=line.account_key,
                display_name=line.display_name,
                note_no=section.note_no,
                title=_inferred_generic_note_title(line, section.title, table.heading),
                section_id=section.section_id,
                confidence=0.45,
                evidence=f"generic FSC account label matched note candidate: {line.label}",
                source=table_source,
            )
        )


def _exclude_generic_note_table(heading: str) -> bool:
    normalized = _normalize(heading)
    risk_keywords = ("신용위험", "시장위험", "유동성위험", "자본위험")
    disclosure_keywords = ("장부금액", "변동", "내역", "범주별", "구성내역", "세부내역")
    return any(keyword in normalized for keyword in risk_keywords) and not any(
        keyword in normalized for keyword in disclosure_keywords
    )


def _append_note_topic(
    topics: list[ClassifiedNoteTopic],
    seen: set[tuple[str, str, str]],
    entry: TaxonomyEntry,
    note_no: str,
    title: str,
    section_id: str,
    confidence: float,
    evidence: str,
    source: str = "",
) -> None:
    key = (entry.key, note_no, title)
    if key in seen:
        return
    seen.add(key)
    topics.append(
        ClassifiedNoteTopic(
            topic_key=entry.key,
            display_name=entry.display_name,
            note_no=note_no,
            title=title,
            section_id=section_id,
            confidence=confidence,
            evidence=evidence,
            source=source or section_id,
        )
    )


def _entry_for_statement_label(statement_title: str, label: str) -> TaxonomyEntry | None:
    normalized_title = _normalize(statement_title)
    normalized_label = _normalize(label)
    for entry in TAXONOMY:
        if not any(_normalize(title) in normalized_title for title in entry.statement_titles):
            continue
        if entry.key == "income_tax_expense_benefit" and "차감전" in normalized_label:
            continue
        if _matches_any(label, entry.statement_aliases):
            # 라벨이 별칭과 맞아도 명시적 제외어(예: 배당의 주식배당/신종자본증권/수취)는
            # 같은 계정으로 보지 않는다. 주석 행과 동일한 제외 규칙을 재무제표 행에도 적용.
            if _matches_any(label, entry.note_amount_exclusions):
                continue
            return entry
    return None


def _entry_for_note_title(title: str) -> TaxonomyEntry | None:
    return next(iter(_entries_for_note_title(title)), None)


def _entries_for_note_title(title: str) -> list[TaxonomyEntry]:
    matches = [entry for entry in TAXONOMY if _matches_any(title, entry.note_title_aliases)]
    if _is_multi_account_note_title(title):
        return matches
    return matches[:1]


def _is_multi_account_note_title(title: str) -> bool:
    normalized = _normalize(title)
    return any(
        keyword in normalized
        for keyword in ("비용의성격별분류", "성격별비용", "매출원가및판매비와관리비")
    ) or ("이연법인세자산" in normalized and "부채" in normalized) or any(
        keyword in normalized
        for keyword in ("영업외수익및영업외비용", "기타수익및기타비용", "금융수익및금융비용", "금융수익및금융원가")
    )


def _entry_for_note_amount_label(label: str) -> TaxonomyEntry | None:
    for entry in TAXONOMY:
        if entry.key == "investment_property" and _normalize(label) != "투자부동산":
            continue
        if _is_generic_balance_label(label) and not _matches_any(label, entry.statement_aliases):
            continue
        if _matches_any(label, entry.note_amount_aliases):
            if _matches_any(label, entry.note_amount_exclusions):
                continue
            return entry
    return None


def _is_generic_balance_label(label: str) -> bool:
    normalized = _normalize(label)
    generic_labels = {
        "장부금액",
        "기말장부금액",
        "기초장부금액",
        "순장부금액",
        "장부가액",
        "기말잔액",
        "기초잔액",
        "기말",
        "기초",
        "합계",
        "소계",
    }
    if normalized in generic_labels:
        return True
    return any(
        normalized == f"{prefix}{suffix}"
        for prefix in ("기초", "기말", "당기말", "전기말")
        for suffix in ("장부금액", "잔액", "금액")
    )


def _table_entry_for_note_row(entry: TaxonomyEntry | None, label: str) -> TaxonomyEntry | None:
    if entry is None:
        return None
    if not _matches_any(label, entry.note_amount_aliases):
        return None
    if _matches_any(label, entry.note_amount_exclusions):
        return None
    return entry


def _entry_for_acodes(acodes: list[str]) -> TaxonomyEntry | None:
    concepts = {_acode_concept(acode) for acode in acodes}
    concepts.discard("")
    for entry in TAXONOMY:
        if any(_normalize_code(code) in concepts for code in entry.fsc_codes):
            return entry
    return None


def _note_row_entry(
    row_entry: TaxonomyEntry | None, table_row_entry: TaxonomyEntry | None, label: str
) -> TaxonomyEntry | None:
    if row_entry is None:
        return table_row_entry
    if table_row_entry is None or row_entry == table_row_entry:
        return row_entry
    normalized = _normalize(label)
    tax_balance_keys = {
        "current_tax_assets",
        "deferred_tax_assets",
        "current_tax_liabilities",
        "deferred_tax_liabilities",
    }
    if row_entry.key in tax_balance_keys and (
        "법인세자산" in normalized or "법인세부채" in normalized
    ):
        return row_entry
    if row_entry.key in {"contract_assets", "other_assets"} and _matches_any(
        label, row_entry.note_amount_aliases
    ):
        return row_entry
    return table_row_entry


def _entry_for_table_acodes(table) -> TaxonomyEntry | None:
    if not table.row_acodes:
        return None
    for row_idx, row_acodes in enumerate(table.row_acodes):
        entry = _entry_for_acodes(row_acodes)
        row_label = table.rows[row_idx][0] if row_idx < len(table.rows) and table.rows[row_idx] else ""
        if entry is not None and _allow_note_acode_match(entry, table.heading, row_label):
            return entry
    return None


def _row_acodes(table, row_idx: int) -> list[str]:
    if not table.row_acodes or row_idx >= len(table.row_acodes):
        return []
    return table.row_acodes[row_idx]


def _acode_concept(acode: str) -> str:
    return _normalize_code(acode.split("|", 1)[0])


def _generic_statement_concept(acodes: list[str]) -> str | None:
    for acode in acodes:
        concept = acode.split("|", 1)[0].strip()
        if not concept or concept == "||||":
            continue
        normalized = _normalize_code(concept)
        if not normalized or normalized.endswith("abstract"):
            continue
        if normalized.startswith(("ifrs-full", "ifrsfull", "dart", "entity")):
            return concept
    return None


def _generic_note_row_matches(
    line: ClassifiedStatementLine, row_label: str, row_acodes: list[str], note_amount: int
) -> bool:
    if _is_structural_statement_label(line.label):
        return False
    if not _amounts_close(line.amount, note_amount):
        return False
    line_label = _normalize(line.label)
    normalized_row_label = _normalize(row_label)
    if line_label and (line_label == normalized_row_label or line_label in normalized_row_label):
        return True
    line_concept = line.account_key.removeprefix("fsc:")
    return any(_acode_concept(acode) == line_concept for acode in row_acodes)


def _generic_note_row_amount(
    line: ClassifiedStatementLine, row: list[str], row_acodes: list[str], unit_multiplier: int
) -> tuple[int | None, int | None]:
    if not row:
        return None, None
    line_label = _normalize(line.label)
    normalized_row_cells = [_normalize(cell) for cell in row if parse_amount(cell) is None]
    label_matched = any(
        line_label and (line_label == cell or line_label in cell) for cell in normalized_row_cells
    )
    line_concept = line.account_key.removeprefix("fsc:")
    acode_matched = any(_acode_concept(acode) == line_concept for acode in row_acodes)
    if not label_matched and not acode_matched:
        return None, None
    for col_idx in range(len(row) - 1, 0, -1):
        amount = parse_amount(row[col_idx])
        if amount is None:
            continue
        amount *= unit_multiplier
        if _amounts_close(line.amount, amount):
            return amount, col_idx
    return None, None


def _generic_label_variants(label: str) -> set[str]:
    normalized = _normalize(label)
    variants = {normalized} if normalized else set()
    replacements = (
        ("당기법인세자산", "법인세"),
        ("당기법인세부채", "법인세"),
        ("이연법인세자산", "이연법인세"),
        ("이연법인세부채", "이연법인세"),
        ("순확정급여자산", "확정급여"),
        ("퇴직급여부채", "퇴직급여"),
        ("해외사업장환산외환차이", "해외사업장"),
        ("해외사업장환산외환차이", "해외사업환산손익"),
        ("해외사업장환산외환차이", "환산외환차이"),
        ("관계기업의자본변동", "관계기업"),
        ("신종자본증권상환", "신종자본증권"),
        ("종속기업의처분", "종속기업"),
        ("자기주식의처분및발행", "자기주식"),
        ("비지배지분과자본거래등", "비지배지분"),
    )
    for source, target in replacements:
        if source in normalized:
            variants.add(_normalize(target))
    return {variant for variant in variants if variant}


def _amounts_close(left: int, right: int) -> bool:
    if min(abs(left), abs(right)) >= 1_000_000:
        return abs(left - right) <= 999
    return left == right


def _inferred_generic_note_title(line: ClassifiedStatementLine, section_title: str, table_heading: str) -> str:
    normalized_label = _normalize(line.label)
    for candidate in (table_heading, section_title):
        if normalized_label and normalized_label in _normalize(candidate):
            return candidate
    return f"{table_heading} {line.label}"


def _is_structural_statement_label(label: str) -> bool:
    normalized = _normalize(label)
    if re.search(r"\d{4}\d{2}\d{2}.*(?:기초|기말)자본", normalized):
        return True
    structural_labels = {
        "자산",
        "부채",
        "자본",
        "유동자산",
        "비유동자산",
        "자산총계",
        "유동부채",
        "비유동부채",
        "부채총계",
        "자본총계",
        "자본과부채총계",
        "총포괄손익",
        "지배기업소유주지분",
        "지배기업의소유주에게귀속되는자본",
    }
    return normalized in structural_labels


def _normalize_code(value: str) -> str:
    return value.lower().replace("_", "")


def _statement_evidence(entry: TaxonomyEntry, label: str, acodes: list[str]) -> str:
    acode = _matched_acode(entry, acodes)
    if acode:
        return f"statement acode matched canonical FSC code: {acode}"
    return f"statement label matched canonical alias: {label}"


def _note_amount_evidence(
    entry: TaxonomyEntry, section_title: str, table_heading: str, label: str, acodes: list[str]
) -> str:
    acode = _matched_acode(entry, acodes)
    if acode:
        return f"note acode matched canonical FSC code: {acode}"
    return f"note topic and amount label matched canonical aliases: {section_title} / {table_heading} / {label}"


def _matched_acode(entry: TaxonomyEntry, acodes: list[str]) -> str:
    normalized_codes = {_normalize_code(code) for code in entry.fsc_codes}
    for acode in acodes:
        concept = acode.split("|", 1)[0]
        if _normalize_code(concept) in normalized_codes:
            return concept
    return ""


def _inferred_note_title(section: ReportSection, table_heading: str) -> str:
    if _entry_for_note_title(section.title):
        return section.title
    return table_heading


def _allow_note_acode_match(entry: TaxonomyEntry, table_heading: str, label: str) -> bool:
    if _matches_any(label, entry.note_amount_aliases):
        return True
    normalized_heading = _normalize(table_heading)
    if _matches_any(table_heading, entry.note_title_aliases):
        return True
    financial_asset_context = ("금융자산" in normalized_heading or "매출채권" in normalized_heading)
    financial_liability_context = ("금융부채" in normalized_heading or "재무활동에서생기는부채" in normalized_heading)
    if entry.key == "trade_receivables" and financial_asset_context:
        return True
    if entry.key in {"borrowings", "bonds", "lease_liabilities"} and financial_liability_context:
        return True
    if entry.key in {"property_plant_equipment", "intangible_assets", "investment_property"}:
        return _matches_any(table_heading, entry.note_title_aliases)
    if entry.key in {"income_tax_expense_benefit", "earnings_per_share"}:
        return _matches_any(table_heading, entry.note_title_aliases)
    return False


def _row_amount(row: list[str], headers: list[str]) -> tuple[int | None, int | None]:
    if _is_allowance_reconciliation_table(headers, row):
        for col_idx in range(len(row) - 1, 0, -1):
            amount = parse_amount(row[col_idx])
            if amount is not None:
                return amount, col_idx

    return row_amount_prefer_current(row, headers)


def _is_allowance_reconciliation_table(headers: list[str], row: list[str]) -> bool:
    header_text = _normalize(" ".join(headers))
    if not any(keyword in header_text for keyword in ("대손충당금", "손실충당금", "충당금")):
        return False
    numeric_values = [parse_amount(cell) for cell in row[1:]]
    numeric_values = [value for value in numeric_values if value is not None]
    if len(numeric_values) < 2:
        return False
    return any(value < 0 for value in numeric_values)


def _matches_any(value: str, aliases: tuple[str, ...]) -> bool:
    normalized_value = _normalize(value)
    return any(variant in normalized_value for alias in aliases for variant in _alias_variants(alias))


def _alias_variants(alias: str) -> set[str]:
    normalized_alias = _normalize(alias)
    variants = {normalized_alias}
    match = re.search(r"^(?P<prefix>.*?)[\(（](?P<option>[^)）]+)[\)）](?P<suffix>.*)$", alias)
    if match is None:
        return variants

    prefix = match.group("prefix")
    option = match.group("option")
    suffix = match.group("suffix")
    variants.add(_normalize(f"{prefix}{suffix}"))
    variants.add(_normalize(f"{prefix}{option}{suffix}"))

    replacement = _replace_last_polarity_term(prefix, option)
    if replacement is not None:
        variants.add(_normalize(f"{replacement}{suffix}"))
    return {variant for variant in variants if variant}


def _replace_last_polarity_term(prefix: str, option: str) -> str | None:
    replacements = (
        ("비용", "수익"),
        ("수익", "비용"),
        ("이익", "손실"),
        ("손실", "이익"),
    )
    for left, right in replacements:
        if _normalize(option) != _normalize(right):
            continue
        index = prefix.rfind(left)
        if index == -1:
            continue
        return f"{prefix[:index]}{right}{prefix[index + len(left):]}"
    return None


def _normalize(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", value).lower()
