"""Deterministic facts for table-adjacent DART narrative disclosures."""

from __future__ import annotations

import re
from dataclasses import dataclass

from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.document import FullReport, ReportBlock, ReportSection, ReportTable
from dart_footing_reconciler.note_reference_validator import extract_note_ref_tokens


_MARKER_RE = re.compile(r"^\s*(\(\s*\*\s*\d*\s*\)|\(\s*주\s*\d+\s*\)|\[\s*주\s*\d+\s*\]|\*|※)")
_INLINE_HEADING_RE = re.compile(r"\s+(?=(?:\d+-\d+|\(\d+\)|[가-힣]\.)\s+)")
_HEADING_RE = re.compile(r"^(?:\d+-\d+|\(\d+\)|[가-힣]\.)\s+")
_AMOUNT_RE = re.compile(r"(?<![\d.-])(\d[\d,]*)(?:\.(\d+))?\s*(억원|백만원|천원|원)")
_REFERENCE_CONTEXT = ("참조", "참고", "포함", "기재", "설명", "공시")
_BACKWARD_TOKENS = ("상기", "위 금액", "위의", "해당", "동 금액")
_DISCLAIMERS = ("주주총회 승인 전", "주주총회 승인전", "정정보고서")
_UNIT_MULTIPLIERS = {"원": 1, "천원": 1_000, "백만원": 1_000_000, "억원": 100_000_000}
_TABLE_TOPIC_NOUNS = (
    "재무정보",
    "경영성과",
    "차입금",
    "유형자산",
    "무형자산",
    "투자부동산",
    "금융자산",
    "금융부채",
    "종속기업",
    "관계기업",
    "공동기업",
)


@dataclass(frozen=True)
class NarrativeSource:
    section_id: str
    scope: str
    note_no: str
    block_index: int
    segment_index: int
    source_key: str


@dataclass(frozen=True)
class NarrativeSegment:
    source: NarrativeSource
    text: str
    marker: str
    is_heading: bool
    is_disclaimer: bool


@dataclass(frozen=True)
class NarrativeAttachment:
    segment_source: str
    table_source: str
    direction: str
    confidence: float
    evidence: str


@dataclass(frozen=True)
class NarrativeNoteReference:
    source: NarrativeSource
    note_no: str
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class NarrativeAmountMention:
    source: NarrativeSource
    raw_text: str
    amount: int
    unit: str
    role: str
    start: int
    end: int


@dataclass(frozen=True)
class NarrativeEvidenceDataset:
    segments: tuple[NarrativeSegment, ...]
    attachments: tuple[NarrativeAttachment, ...]
    note_references: tuple[NarrativeNoteReference, ...]
    amount_mentions: tuple[NarrativeAmountMention, ...]

    def reconciliation_candidates_for(
        self, source_key: str
    ) -> tuple[NarrativeAmountMention, ...]:
        allowed = {
            "borrowing_amount",
            "borrowing_transferred_by_merger",
            "replacement_amount",
        }
        return tuple(
            mention
            for mention in self.amount_mentions
            if mention.source.source_key == source_key and mention.role in allowed
        )


def build_narrative_evidence(report: FullReport) -> NarrativeEvidenceDataset:
    segments: list[NarrativeSegment] = []
    attachments: list[NarrativeAttachment] = []
    references: list[NarrativeNoteReference] = []
    amounts: list[NarrativeAmountMention] = []
    for section in [*report.statements, *report.notes]:
        _append_section_facts(section, segments, attachments, references, amounts)
    return NarrativeEvidenceDataset(
        tuple(segments),
        tuple(attachments),
        tuple(references),
        tuple(amounts),
    )


def _append_section_facts(
    section: ReportSection,
    segments: list[NarrativeSegment],
    attachments: list[NarrativeAttachment],
    references: list[NarrativeNoteReference],
    amounts: list[NarrativeAmountMention],
) -> None:
    previous_table: ReportTable | None = None
    for block_index, block in enumerate(section.blocks):
        if block.table is not None:
            previous_table = block.table
            continue
        if block.kind != "text" or not block.text.strip():
            continue
        block_segments = block.text_segments or (block.text,)
        segment_index = 0
        for raw_segment in block_segments:
            for text in _split_segments(raw_segment):
                source = _narrative_source(section, block, block_index, segment_index)
                segment_index += 1
                marker = _marker(text)
                is_heading = bool(_HEADING_RE.match(text))
                is_disclaimer = any(token in text for token in _DISCLAIMERS)
                segment = NarrativeSegment(source, text, marker, is_heading, is_disclaimer)
                segments.append(segment)
                if previous_table is not None and not is_heading and not is_disclaimer:
                    attachment = _attachment_for(segment, previous_table, section)
                    if attachment is not None:
                        attachments.append(attachment)
                references.extend(_note_references(segment))
                amounts.extend(_amount_mentions(segment))


def _narrative_source(
    section: ReportSection,
    block: ReportBlock,
    block_index: int,
    segment_index: int,
) -> NarrativeSource:
    scope = section.scope or "unknown"
    actual_block_index = block.location.block_index if block.location else block_index
    source_key = (
        f"{section.section_id}@{scope}/block:{actual_block_index}/segment:{segment_index}"
    )
    return NarrativeSource(
        section.section_id,
        scope,
        section.note_no,
        actual_block_index,
        segment_index,
        source_key,
    )


def _split_segments(text: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in _INLINE_HEADING_RE.split(text) if part.strip())


def _marker(text: str) -> str:
    match = _MARKER_RE.match(text)
    return match.group(1).strip() if match is not None else ""


def _normalized_marker(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def _attachment_for(
    segment: NarrativeSegment,
    table: ReportTable,
    section: ReportSection,
) -> NarrativeAttachment | None:
    table_text = " ".join(cell for row in table.rows for cell in row)
    table_markers = {
        _normalized_marker(match.group(1))
        for match in re.finditer(_MARKER_RE.pattern.replace("^", ""), table_text)
    }
    normalized_marker = _normalized_marker(segment.marker)
    table_source = f"{section.section_id}/table:{table.index}"
    if normalized_marker and normalized_marker in table_markers:
        return NarrativeAttachment(
            segment.source.source_key,
            table_source,
            "backward",
            1.0,
            "exact_marker_match",
        )
    if normalized_marker:
        return NarrativeAttachment(
            segment.source.source_key,
            table_source,
            "backward",
            0.9,
            "adjacent_explicit_marker",
        )
    if not any(token in segment.text for token in _BACKWARD_TOKENS):
        return None
    if not _shares_table_noun(segment.text, table):
        return None
    return NarrativeAttachment(
        segment.source.source_key,
        table_source,
        "backward",
        0.7,
        "backward_reference_with_shared_noun",
    )


def _shares_table_noun(text: str, table: ReportTable) -> bool:
    normalized_text = _compact(text)
    normalized_table = _compact(
        " ".join(
            [
                table.heading,
                *(cell for row in table.rows for cell in row),
            ]
        )
    )
    if any(
        topic in normalized_text and topic in normalized_table
        for topic in _TABLE_TOPIC_NOUNS
    ):
        return True
    if "요약재무정보" in normalized_text and any(
        topic in normalized_table for topic in ("자산", "부채", "자본", "매출", "손익")
    ):
        return True
    if "요약경영성과" in normalized_text and any(
        topic in normalized_table for topic in ("매출", "수익", "영업", "손익", "이익")
    ):
        return True
    for row in table.rows[1:]:
        if not row:
            continue
        label = _compact(row[0])
        if len(label) >= 4 and label in normalized_text:
            return True
    return False


def _note_references(segment: NarrativeSegment) -> list[NarrativeNoteReference]:
    if not any(token in segment.text for token in _REFERENCE_CONTEXT):
        return []
    references: list[NarrativeNoteReference] = []
    for note_no in extract_note_ref_tokens(segment.text):
        match = re.search(rf"(?<!\d){re.escape(note_no)}(?!\d)", segment.text)
        start = match.start() if match is not None else 0
        end = match.end() if match is not None else start
        references.append(
            NarrativeNoteReference(
                segment.source,
                note_no,
                segment.text,
                start,
                end,
            )
        )
    return references


def _amount_mentions(segment: NarrativeSegment) -> list[NarrativeAmountMention]:
    if segment.is_disclaimer:
        return []
    role = _amount_role(segment.text)
    if not role:
        return []
    mentions: list[NarrativeAmountMention] = []
    for match in _AMOUNT_RE.finditer(segment.text):
        whole, decimals, unit = match.groups()
        if decimals:
            continue
        parsed = parse_amount(whole)
        if parsed is None:
            continue
        mentions.append(
            NarrativeAmountMention(
                segment.source,
                match.group(0),
                parsed * _UNIT_MULTIPLIERS[unit],
                unit,
                role,
                match.start(),
                match.end(),
            )
        )
    return mentions


def _amount_role(text: str) -> str:
    compact = _compact(text)
    if "합병" in compact and "이관" in compact and "차입금" in compact:
        return "borrowing_transferred_by_merger"
    if "한도" in compact:
        return "borrowing_limit"
    if "담보" in compact:
        return "collateral_amount"
    if "내부거래" in compact and "제거전" in compact:
        return "internal_transactions_not_eliminated"
    if "대체" in compact:
        return "replacement_amount"
    if "포함" in compact:
        return "included_amount"
    if "차입금" in compact:
        return "borrowing_amount"
    return ""


def _compact(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", value or "").lower()
