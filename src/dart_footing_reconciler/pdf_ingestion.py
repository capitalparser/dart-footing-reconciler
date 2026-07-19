"""Native-text PDF extraction with page and table provenance."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

import pdfplumber
from pdfminer.pdfdocument import PDFEncryptionError
from pdfplumber.utils.exceptions import PdfminerException

from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.attachment_ingestion import (
    AttachmentDiagnostic,
    AttachmentIngestionError,
)


_LINE_TABLE_SETTINGS = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
}
_TEXT_TABLE_SETTINGS = {
    "vertical_strategy": "text",
    "horizontal_strategy": "text",
    "min_words_vertical": 2,
    "min_words_horizontal": 1,
    "intersection_tolerance": 4,
    "text_tolerance": 3,
}
_MAX_CONFLICT_TEXT_CANDIDATES = 12


@dataclass(frozen=True)
class PdfExtraction:
    markup: str
    diagnostics: tuple[AttachmentDiagnostic, ...] = ()


def extract_pdf_markup(source: Path) -> PdfExtraction:
    """Extract page-ordered native PDF content into source-annotated markup."""
    blocks: list[str] = []
    diagnostics: list[AttachmentDiagnostic] = []
    non_whitespace_characters = 0
    page_count = 0
    has_page_image = False
    table_count = 0

    try:
        with pdfplumber.open(source) as pdf:
            if pdf.doc.encryption is not None:
                raise AttachmentIngestionError(
                    "PDF_ENCRYPTED",
                    "암호화된 PDF는 검증할 수 없습니다.",
                )
            for page in pdf.pages:
                page_count += 1
                has_page_image = has_page_image or bool(page.images)
                line_tables = [
                    (tuple(table.bbox), table.extract())
                    for table in page.find_tables(_LINE_TABLE_SETTINGS)
                ]
                needs_text_candidates = not line_tables or any(
                    _amount_count(rows) > 0 and _label_count(rows) == 0
                    for _bbox, rows in line_tables
                )
                text_tables = (
                    [
                        (tuple(table.bbox), table.extract())
                        for table in page.find_tables(_TEXT_TABLE_SETTINGS)
                    ]
                    if needs_text_candidates
                    else []
                )
                table_blocks, fragments_recovered = _select_table_candidates(
                    line_tables,
                    text_tables,
                )
                if not line_tables and table_blocks:
                    diagnostics.append(
                        AttachmentDiagnostic(
                            code="PDF_TABLE_STRUCTURE_INFERRED",
                            message=(
                                "선으로 구분된 표 경계를 찾지 못해 텍스트 정렬을 "
                                "기준으로 표 구조를 추정했습니다."
                            ),
                            page=page.page_number,
                        )
                    )
                if fragments_recovered:
                    diagnostics.append(
                        AttachmentDiagnostic(
                            code="PDF_TABLE_FRAGMENT_RECOVERED",
                            message=(
                                "표의 금액 영역과 분리된 행 제목을 함께 복구했습니다."
                            ),
                            page=page.page_number,
                        )
                    )
                table_count += len(table_blocks)

                words = page.extract_words()
                non_whitespace_characters += sum(
                    len("".join(str(word.get("text", "")).split())) for word in words
                )
                narrative_words = [
                    word
                    for word in words
                    if not any(
                        _word_center_inside_bbox(word, bbox)
                        for bbox, _rows in table_blocks
                    )
                ]
                narrative_lines = _group_words_into_lines(narrative_words)

                ordered_blocks: list[tuple[float, float, str]] = []
                for line in narrative_lines:
                    bbox = _words_bbox(line)
                    text = " ".join(str(word.get("text", "")) for word in line)
                    ordered_blocks.append(
                        (
                            bbox[1],
                            bbox[0],
                            _serialize_paragraph(page.page_number, bbox, text),
                        )
                    )
                for bbox, rows in table_blocks:
                    ordered_blocks.append(
                        (
                            bbox[1],
                            bbox[0],
                            _serialize_table(page.page_number, bbox, rows),
                        )
                    )
                blocks.extend(markup for _top, _x0, markup in sorted(ordered_blocks))
    except PdfminerException as exc:
        if _is_encryption_error(exc):
            raise AttachmentIngestionError(
                "PDF_ENCRYPTED",
                "암호화된 PDF는 검증할 수 없습니다.",
            ) from exc
        raise AttachmentIngestionError(
            "ATTACHMENT_DECODE_FAILED",
            "PDF 첨부가 손상되었거나 읽을 수 없습니다.",
        ) from exc

    if page_count and non_whitespace_characters < 20 and has_page_image:
        raise AttachmentIngestionError(
            "PDF_OCR_REQUIRED",
            "텍스트를 읽을 수 없는 PDF입니다. OCR 처리된 PDF가 필요합니다.",
        )
    if table_count == 0:
        raise AttachmentIngestionError(
            "PDF_TABLES_NOT_FOUND",
            "PDF에서 검증 가능한 표를 찾지 못했습니다.",
        )

    return PdfExtraction(markup="\n".join(blocks), diagnostics=tuple(diagnostics))


def _amount_count(rows: list[list[str | None]]) -> int:
    return sum(parse_amount(cell or "") is not None for row in rows for cell in row)


def _label_count(rows: list[list[str | None]]) -> int:
    return sum(
        bool((cell or "").strip()) and parse_amount(cell or "") is None
        for row in rows
        for cell in row[:2]
    )


def _bbox_overlap_ratio(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    first_x0, first_top, first_x1, first_bottom = first
    second_x0, second_top, second_x1, second_bottom = second
    intersection_width = max(0.0, min(first_x1, second_x1) - max(first_x0, second_x0))
    intersection_height = max(
        0.0,
        min(first_bottom, second_bottom) - max(first_top, second_top),
    )
    intersection_area = intersection_width * intersection_height
    first_area = max(0.0, first_x1 - first_x0) * max(0.0, first_bottom - first_top)
    second_area = max(0.0, second_x1 - second_x0) * max(0.0, second_bottom - second_top)
    smaller_area = min(first_area, second_area)
    if smaller_area == 0:
        return 0.0
    return intersection_area / smaller_area


def _select_table_candidates(
    line_tables: list[tuple[tuple[float, float, float, float], list[list[str | None]]]],
    text_tables: list[tuple[tuple[float, float, float, float], list[list[str | None]]]],
) -> tuple[
    list[tuple[tuple[float, float, float, float], list[list[str | None]]]],
    bool,
]:
    line_neighbors = [set() for _table in line_tables]
    text_neighbors = [set() for _table in text_tables]
    for line_index, (line_bbox, _line_rows) in enumerate(line_tables):
        for text_index, (text_bbox, _text_rows) in enumerate(text_tables):
            if _bbox_overlap_ratio(line_bbox, text_bbox) > 0:
                line_neighbors[line_index].add(text_index)
                text_neighbors[text_index].add(line_index)

    selected_indexes: list[tuple[str, int]] = []
    fragments_recovered = False
    for component_lines, component_texts in _overlap_components(
        line_neighbors,
        text_neighbors,
    ):
        if not component_lines:
            for text_index in component_texts:
                text_rows = text_tables[text_index][1]
                if _amount_count(text_rows) > 0 and _label_count(text_rows) > 0:
                    selected_indexes.append(("text", text_index))
            continue

        baseline = [("line", index) for index in component_lines]
        if (
            not component_texts
            or len(component_texts) > _MAX_CONFLICT_TEXT_CANDIDATES
            or not any(
                _amount_count(line_tables[index][1]) > 0
                and _label_count(line_tables[index][1]) == 0
                for index in component_lines
            )
        ):
            selected_indexes.extend(baseline)
            continue

        replacement = _best_component_replacement(
            component_lines,
            component_texts,
            line_tables,
            text_tables,
            text_neighbors,
        )
        if replacement is None:
            selected_indexes.extend(baseline)
            continue
        selected_indexes.extend(replacement)
        fragments_recovered = True

    selected = [
        line_tables[index] if kind == "line" else text_tables[index]
        for kind, index in selected_indexes
    ]
    selected.sort(key=lambda candidate: (candidate[0][1], candidate[0][0]))
    return selected, fragments_recovered


def _overlap_components(
    line_neighbors: list[set[int]],
    text_neighbors: list[set[int]],
) -> list[tuple[list[int], list[int]]]:
    components: list[tuple[list[int], list[int]]] = []
    unseen_lines = set(range(len(line_neighbors)))
    unseen_texts = set(range(len(text_neighbors)))

    while unseen_lines or unseen_texts:
        if unseen_lines:
            pending = [("line", min(unseen_lines))]
        else:
            pending = [("text", min(unseen_texts))]
        component_lines: set[int] = set()
        component_texts: set[int] = set()
        while pending:
            kind, index = pending.pop()
            if kind == "line":
                if index not in unseen_lines:
                    continue
                unseen_lines.remove(index)
                component_lines.add(index)
                pending.extend(("text", item) for item in line_neighbors[index])
            else:
                if index not in unseen_texts:
                    continue
                unseen_texts.remove(index)
                component_texts.add(index)
                pending.extend(("line", item) for item in text_neighbors[index])
        components.append((sorted(component_lines), sorted(component_texts)))
    return components


def _best_component_replacement(
    component_lines: list[int],
    component_texts: list[int],
    line_tables: list[tuple[tuple[float, float, float, float], list[list[str | None]]]],
    text_tables: list[tuple[tuple[float, float, float, float], list[list[str | None]]]],
    text_neighbors: list[set[int]],
) -> list[tuple[str, int]] | None:
    line_amounts = {
        index: _amount_count(line_tables[index][1]) for index in component_lines
    }
    line_labels = {
        index: _label_count(line_tables[index][1]) for index in component_lines
    }
    text_amounts = {
        index: _amount_count(text_tables[index][1]) for index in component_texts
    }
    text_labels = {
        index: _label_count(text_tables[index][1]) for index in component_texts
    }
    baseline_amounts = sum(line_amounts.values())
    baseline_labels = sum(line_labels.values())
    numeric_fragment_lines = {
        index
        for index in component_lines
        if line_amounts[index] > 0 and line_labels[index] == 0
    }

    # At most 2**12 states: candidates sharing any original line cannot coexist.
    states: dict[frozenset[int], tuple[int, ...]] = {frozenset(): ()}
    for text_index in component_texts:
        covered_by_text = frozenset(text_neighbors[text_index])
        next_states = dict(states)
        for covered_lines, selected_texts in states.items():
            if covered_lines & covered_by_text:
                continue
            combined_lines = covered_lines | covered_by_text
            combined_texts = (*selected_texts, text_index)
            previous = next_states.get(combined_lines)
            if previous is None or _text_set_rank(
                combined_texts,
                text_amounts,
                text_labels,
            ) > _text_set_rank(previous, text_amounts, text_labels):
                next_states[combined_lines] = combined_texts
        states = next_states

    best_selection: tuple[int, ...] | None = None
    best_rank: tuple[int, int, int] | None = None
    for covered_lines, selected_texts in states.items():
        if not selected_texts or not covered_lines & numeric_fragment_lines:
            continue
        uncovered_lines = set(component_lines) - covered_lines
        amount_count = sum(text_amounts[index] for index in selected_texts) + sum(
            line_amounts[index] for index in uncovered_lines
        )
        label_count = sum(text_labels[index] for index in selected_texts) + sum(
            line_labels[index] for index in uncovered_lines
        )
        if amount_count < baseline_amounts or label_count <= baseline_labels:
            continue
        rank = (label_count, amount_count, -len(selected_texts))
        if best_rank is None or rank > best_rank:
            best_selection = selected_texts
            best_rank = rank

    if best_selection is None:
        return None
    covered_lines = set().union(
        *(text_neighbors[index] for index in best_selection),
    )
    return [
        *(("line", index) for index in component_lines if index not in covered_lines),
        *(("text", index) for index in best_selection),
    ]


def _text_set_rank(
    text_indexes: tuple[int, ...],
    text_amounts: dict[int, int],
    text_labels: dict[int, int],
) -> tuple[int, int, int]:
    return (
        sum(text_labels[index] for index in text_indexes),
        sum(text_amounts[index] for index in text_indexes),
        -len(text_indexes),
    )


def _is_encryption_error(exc: PdfminerException) -> bool:
    return any(
        isinstance(candidate, PDFEncryptionError)
        for candidate in (*exc.args, exc.__context__, exc.__cause__)
    )


def _word_center_inside_bbox(
    word: dict[str, Any],
    bbox: tuple[float, float, float, float],
) -> bool:
    center_x = (float(word["x0"]) + float(word["x1"])) / 2
    center_y = (float(word["top"]) + float(word["bottom"])) / 2
    x0, top, x1, bottom = bbox
    return x0 <= center_x <= x1 and top <= center_y <= bottom


def _group_words_into_lines(
    words: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    lines: list[list[dict[str, Any]]] = []
    for word in sorted(words, key=lambda item: (float(item["top"]), float(item["x0"]))):
        if not lines or abs(float(word["top"]) - float(lines[-1][0]["top"])) > 3:
            lines.append([word])
        else:
            lines[-1].append(word)
    for line in lines:
        line.sort(key=lambda item: float(item["x0"]))
    return lines


def _words_bbox(words: list[dict[str, Any]]) -> tuple[float, float, float, float]:
    return (
        min(float(word["x0"]) for word in words),
        min(float(word["top"]) for word in words),
        max(float(word["x1"]) for word in words),
        max(float(word["bottom"]) for word in words),
    )


def _serialize_paragraph(
    page_number: int,
    bbox: tuple[float, float, float, float],
    text: str,
) -> str:
    return (
        f'<p data-pdf-page="{page_number}" data-pdf-bbox="{_format_bbox(bbox)}">'
        f"{escape(text)}</p>"
    )


def _serialize_table(
    page_number: int,
    bbox: tuple[float, float, float, float],
    rows: list[list[str | None]],
) -> str:
    rows = [row for row in rows if any((cell or "").strip() for cell in row)]
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(cell or '')}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    return (
        f'<table data-pdf-page="{page_number}" '
        f'data-pdf-bbox="{_format_bbox(bbox)}">{body}</table>'
    )


def _format_bbox(bbox: tuple[float, float, float, float]) -> str:
    return ",".join(str(float(value)) for value in bbox)
