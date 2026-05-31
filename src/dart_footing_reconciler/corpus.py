"""Multi-company workpaper corpus runner."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dart_footing_reconciler.checks import CheckResult
from dart_footing_reconciler.checks_note_bridges import check_asset_note_bridges
from dart_footing_reconciler.checks_note_note import check_note_note_matches
from dart_footing_reconciler.checks_prior_year import check_prior_year_reconciliation
from dart_footing_reconciler.checks_reconciliation import check_reconciliation_targets
from dart_footing_reconciler.checks_totals import check_table_totals
from dart_footing_reconciler.dart_fetch import fetch_financial_section
from dart_footing_reconciler.document import FullReport, parse_full_report
from dart_footing_reconciler.note_assertions import check_note_assertions
from dart_footing_reconciler.report_html import export_audit_reconciliation_html

PRIMARY_CORPUS_CHECK_TYPES = {
    "primary_balance_reconciliation",
    "cashflow_reconciliation",
    "expense_allocation",
    "prior_year_beginning_balance_match",
}

DETERMINATE_STATUSES = {"matched", "explainable_gap", "unexplained_gap"}
ROOT_CAUSE_CLASSES = {
    "scope_mismatch",
    "wrong_table_class",
    "wrong_period",
    "wrong_unit",
    "wrong_sign",
    "direct_evidence_missing",
    "composite_statement_account",
    "note_candidate_conflict",
    "formula_template_missing",
    "parser_table_boundary_issue",
}


@dataclass(frozen=True)
class CorpusSample:
    name: str
    company: str
    rcp_no: str | None
    source: str | None
    tags: tuple[str, ...]


def run_workpaper_corpus(
    manifest_path: str | Path,
    output_dir: str | Path,
    *,
    fetch_missing: bool = True,
    tolerance: int = 1,
) -> dict[str, Any]:
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    base_dir = Path(manifest_path).parent
    output = Path(output_dir)
    raw_dir = output / "raw"
    report_dir = output / "reports"
    raw_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    sample_reports = [
        _run_sample(
            _sample_from_dict(item),
            base_dir,
            raw_dir,
            report_dir,
            fetch_missing=fetch_missing,
            tolerance=tolerance,
        )
        for item in manifest.get("samples", [])
    ]
    payload = {
        "manifest": str(manifest_path),
        "output_dir": str(output),
        "summary": _summary(sample_reports),
        "samples": sample_reports,
    }
    taxonomy = primary_unresolved_taxonomy(payload)
    false_matched_review = false_matched_review_sample(payload)
    payload["summary"]["false_matched_review_samples"] = len(false_matched_review["items"])
    (output / "corpus_result.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output / "corpus_report.md").write_text(corpus_markdown(payload), encoding="utf-8")
    (output / "primary_unresolved_taxonomy.json").write_text(
        json.dumps(taxonomy, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output / "primary_unresolved_taxonomy.md").write_text(
        taxonomy_markdown(taxonomy),
        encoding="utf-8",
    )
    (output / "false_matched_review.md").write_text(
        false_matched_review_markdown(false_matched_review),
        encoding="utf-8",
    )
    return payload


def corpus_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# 다중 회사 DART 감사 대사 검증 결과",
        "",
        f"- 표본 회사: {summary['samples']}",
        f"- 생성 보고서: {summary['generated_reports']}",
        f"- 생성 실패: {summary['failed_samples']}",
        f"- 전체 검증 항목: {summary['total_checks']}",
        f"- 대사 완료: {summary['matched']}",
        f"- 차이내역 확인 필요: {summary['explainable_gap']}",
        f"- 자동화 보완 필요: {summary['unexplained_gap']}",
        f"- 표 구조 해석 필요: {summary['parse_uncertain']}",
        f"- 자동 검증 제외: {summary['not_tested']}",
        f"- 주요 대사 항목: {summary['primary_checks']}",
        f"- 주요 무차이 대사: {summary['primary_matched']}",
        f"- 주요 후속 확인: {summary['primary_unresolved']}",
        f"- 주요 무차이 대사율: {_rate(summary['primary_matched'], summary['primary_checks'])}",
        f"- 주요 자동 판정률: {_rate(summary.get('primary_determinate', 0), summary['primary_checks'])}",
        f"- 주석별 검증 항목: {summary.get('note_assertion_checks', 0)}",
        f"- 주석별 검증 완료: {summary.get('note_assertion_matched', 0)}",
        f"- 주석별 후속 확인: {summary.get('note_assertion_unresolved', 0)}",
        "",
        "## 회사별 결과",
        "",
        "| 회사 | 상태 | 재무제표 | 주석 | 검증 항목 | 주요 대사 | 주요 무차이 대사 | 주요 후속 확인 | 무차이 대사율 | 자동 판정률 | 대사 완료 | 자동화 보완 필요 | 표 구조 해석 필요 | 보고서 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for sample in payload["samples"]:
        status_counts = sample.get("status_counts", {})
        primary_status = sample.get("primary_status_counts", {})
        primary_unresolved = sample.get("primary_checks", 0) - primary_status.get("matched", 0)
        primary_determinate = sample.get("primary_determinate", 0)
        lines.append(
            "| {company} | {status} | {statements} | {notes} | {checks} | {primary_checks} | {primary_matched} | {primary_unresolved} | {primary_rate} | {primary_judgment_rate} | {matched} | {unexplained} | {parse_uncertain} | `{report}` |".format(
                company=sample["company"],
                status=_sample_status_label(str(sample["status"])),
                statements=sample.get("statements", 0),
                notes=sample.get("notes", 0),
                checks=sample.get("checks", 0),
                primary_checks=sample.get("primary_checks", 0),
                primary_matched=primary_status.get("matched", 0),
                primary_unresolved=primary_unresolved,
                primary_rate=_rate(primary_status.get("matched", 0), sample.get("primary_checks", 0)),
                primary_judgment_rate=_rate(primary_determinate, sample.get("primary_checks", 0)),
                matched=status_counts.get("matched", 0),
                unexplained=status_counts.get("unexplained_gap", 0),
                parse_uncertain=status_counts.get("parse_uncertain", 0),
                report=sample.get("report_html", ""),
            )
        )
    lines.extend(["", "## 후속 확인 분류", ""])
    for category, count in summary["gap_categories"].items():
        lines.append(f"- {_gap_category_label(category)}: {count}")
    lines.extend(["", "## 검증유형별 성공률", ""])
    lines.append("| 검증유형 | 주요 항목 | 주요 무차이 대사 | 주요 후속 확인 | 무차이 대사율 | 자동 판정률 |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for check_type, counts in _primary_type_status_counts(payload).items():
        total = sum(counts.values())
        matched = counts.get("matched", 0)
        determinate = sum(counts.get(status, 0) for status in DETERMINATE_STATUSES)
        lines.append(
            "| {label} | {total} | {matched} | {unresolved} | {matched_rate} | {judgment_rate} |".format(
                label=_check_type_label(check_type),
                total=total,
                matched=matched,
                unresolved=total - matched,
                matched_rate=_rate(matched, total),
                judgment_rate=_rate(determinate, total),
            )
        )
    lines.extend(
        [
            "",
            "## 필요한 보완",
            "",
            "- 현금흐름표 투자·재무활동 행과 주석 후보는 라벨 룰만이 아니라 표 제목, 헤더, 금액 방향으로 스코어링해야 함.",
            "- FSC 계정은 확인됐지만 주석 금액 표 후보가 부족한 계정은 주석 제목 alias와 table schema 후보를 확장해야 함.",
            "- 합계 검증은 주석별 표 구조가 다르므로 합계, 소계, 장부금액 컬럼 역할을 분리해야 함.",
            "- 연결/별도 재무제표와 연결/별도 주석이 섞이는 케이스는 acode scope와 제목 scope를 함께 써서 필터링해야 함.",
        ]
    )
    return "\n".join(lines) + "\n"


def _primary_type_status_counts(payload: dict[str, Any]) -> dict[str, Counter[str]]:
    summary_counts = payload.get("summary", {}).get("primary_type_status_counts")
    if summary_counts:
        return {
            check_type: Counter(counts)
            for check_type, counts in summary_counts.items()
        }
    aggregate: dict[str, Counter[str]] = {}
    for sample in payload.get("samples", []):
        for check_type, counts in sample.get("primary_type_status_counts", {}).items():
            aggregate.setdefault(check_type, Counter()).update(counts)
    return aggregate


def _sample_status_label(status: str) -> str:
    labels = {
        "generated": "생성 완료",
        "failed": "생성 실패",
    }
    return labels.get(status, status)


def _rate(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "-"
    return f"{numerator / denominator:.1%}"


def _gap_category_label(category: str) -> str:
    labels = {
        "parse_uncertain_total": "표 구조 해석 필요 - 합계 검증",
        "unexplained_total_check": "자동화 보완 필요 - 표 합계 검증",
        "unexplained_cashflow_reconciliation": "자동화 보완 필요 - 현금흐름 대사",
        "explainable_cashflow_reconciliation": "차이내역 확인 필요 - 현금흐름 대사",
        "statement_parse_sparse": "원천 근거 부족 - 재무제표 구조",
        "note_parse_sparse": "원천 근거 부족 - 주석 구조",
        "cashflow_target_sparse": "자동화 보완 필요 - 현금흐름 대사 대상",
        "sample_failed": "표본 생성 실패",
    }
    if category in labels:
        return labels[category]
    if category.startswith("unexplained_"):
        return f"자동화 보완 필요 - {_check_type_label(category.removeprefix('unexplained_'))}"
    if category.startswith("parse_uncertain_"):
        return f"표 구조 해석 필요 - {_check_type_label(category.removeprefix('parse_uncertain_'))}"
    if category.startswith("explainable_"):
        return f"차이내역 확인 필요 - {_check_type_label(category.removeprefix('explainable_'))}"
    return category


def _check_type_label(check_type: str) -> str:
    labels = {
        "total": "합계 검증",
        "total_check": "표 합계 검증",
        "cashflow_reconciliation": "현금흐름 대사",
        "primary_balance_reconciliation": "재무제표-주석 금액 대사",
        "expense_allocation": "성격별 비용 대사",
        "prior_year_beginning_balance_match": "전기말-당기초 대사",
        "note_note_reconciliation": "주석 간 대사",
        "note_note_match": "주석 간 대사",
        "note_rollforward_check": "주석 증감표 검산",
        "asset_note_bridge_check": "자산 주석 연결 대사",
    }
    return labels.get(check_type, check_type.replace("_", " "))


def _sample_from_dict(item: dict[str, Any]) -> CorpusSample:
    return CorpusSample(
        name=item["name"],
        company=item.get("company") or item["name"],
        rcp_no=item.get("rcp_no") or item.get("receipt_no"),
        source=item.get("source"),
        tags=tuple(item.get("tags", [])),
    )


def _run_sample(
    sample: CorpusSample,
    base_dir: Path,
    raw_dir: Path,
    report_dir: Path,
    *,
    fetch_missing: bool,
    tolerance: int,
) -> dict[str, Any]:
    try:
        source = _sample_source(sample, base_dir, raw_dir, fetch_missing)
        report = parse_full_report(source, company=sample.company)
        checks = _run_checks(report, None, tolerance)
        report_html = report_dir / f"{sample.name}.html"
        export_audit_reconciliation_html(report, checks, report_html)
        status_counts = Counter(check.status for check in checks)
        check_type_counts = Counter(check.check_type for check in checks)
        note_assertion_checks = [
            check for check in checks if check.check_type.startswith("note_") and check.check_type != "note_note_match"
        ]
        note_assertion_status_counts = Counter(check.status for check in note_assertion_checks)
        primary_checks = [check for check in checks if check.check_type in PRIMARY_CORPUS_CHECK_TYPES]
        primary_status_counts = Counter(check.status for check in primary_checks)
        primary_type_status_counts: dict[str, Counter[str]] = {}
        for check in primary_checks:
            primary_type_status_counts.setdefault(check.check_type, Counter()).update([check.status])
        primary_determinate = sum(
            1 for check in primary_checks if check.status in DETERMINATE_STATUSES
        )
        primary_unresolved = [
            _primary_unresolved_item(sample.company, sample.name, check)
            for check in primary_checks
            if check.status != "matched"
        ]
        primary_matched_items = [
            _primary_matched_item(sample.company, sample.name, check)
            for check in primary_checks
            if check.status == "matched"
        ]
        return {
            "name": sample.name,
            "company": sample.company,
            "rcp_no": sample.rcp_no,
            "source": str(source),
            "status": "generated",
            "statements": len(report.statements),
            "notes": len(report.notes),
            "checks": len(checks),
            "status_counts": dict(status_counts),
            "check_type_counts": dict(check_type_counts),
            "note_assertion_checks": len(note_assertion_checks),
            "note_assertion_status_counts": dict(note_assertion_status_counts),
            "primary_checks": len(primary_checks),
            "primary_status_counts": dict(primary_status_counts),
            "primary_type_status_counts": {
                check_type: dict(counts)
                for check_type, counts in primary_type_status_counts.items()
            },
            "primary_determinate": primary_determinate,
            "primary_unresolved_items": primary_unresolved,
            "primary_matched_items": primary_matched_items,
            "gap_categories": _gap_categories(report, checks),
            "report_html": str(report_html),
        }
    except Exception as exc:  # noqa: BLE001 - corpus report must keep going across companies.
        return {
            "name": sample.name,
            "company": sample.company,
            "rcp_no": sample.rcp_no,
            "status": "failed",
            "error": str(exc),
            "gap_categories": {"sample_failed": 1},
        }


def _sample_source(sample: CorpusSample, base_dir: Path, raw_dir: Path, fetch_missing: bool) -> Path:
    if sample.source:
        source = Path(sample.source)
        if not source.is_absolute():
            source = base_dir / source
        if source.exists():
            return source
    if not sample.rcp_no:
        raise ValueError(f"{sample.name} has no source and no rcp_no")
    output = raw_dir / f"{sample.name}_{sample.rcp_no}.html"
    if output.exists():
        return output
    if not fetch_missing:
        raise FileNotFoundError(output)
    return fetch_financial_section(sample.rcp_no, output)


def _run_checks(report: FullReport, prior_report: FullReport | None, tolerance: int) -> list[CheckResult]:
    checks: list[CheckResult] = []
    for note in report.notes:
        for block in note.blocks:
            if block.table is not None:
                checks.extend(check_table_totals(block.table, note_no=note.note_no, tolerance=tolerance))
    checks.extend(check_note_assertions(report, tolerance=tolerance))
    checks.extend(check_reconciliation_targets(report, tolerance=tolerance))
    checks.extend(check_asset_note_bridges(report, tolerance=tolerance))
    checks.extend(check_note_note_matches(report, tolerance=tolerance))
    if prior_report is not None:
        checks.extend(check_prior_year_reconciliation(report, prior_report, tolerance=tolerance))
    return checks


def _summary(samples: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: Counter[str] = Counter()
    gap_categories: Counter[str] = Counter()
    primary_type_status_counts: dict[str, Counter[str]] = {}
    for sample in samples:
        status_counts.update(sample.get("status_counts", {}))
        gap_categories.update(sample.get("gap_categories", {}))
        for check_type, counts in sample.get("primary_type_status_counts", {}).items():
            primary_type_status_counts.setdefault(check_type, Counter()).update(counts)
    primary_checks = sum(sample.get("primary_checks", 0) for sample in samples)
    primary_matched = sum(
        sample.get("primary_status_counts", {}).get("matched", 0) for sample in samples
    )
    primary_determinate = sum(sample.get("primary_determinate", 0) for sample in samples)
    note_assertion_checks = sum(sample.get("note_assertion_checks", 0) for sample in samples)
    note_assertion_matched = sum(
        sample.get("note_assertion_status_counts", {}).get("matched", 0) for sample in samples
    )
    note_assertion_unresolved = sum(
        sample.get("note_assertion_status_counts", {}).get("unexplained_gap", 0) for sample in samples
    )
    return {
        "samples": len(samples),
        "generated_reports": sum(1 for sample in samples if sample["status"] == "generated"),
        "failed_samples": sum(1 for sample in samples if sample["status"] == "failed"),
        "total_checks": sum(sample.get("checks", 0) for sample in samples),
        "matched": status_counts.get("matched", 0),
        "explainable_gap": status_counts.get("explainable_gap", 0),
        "unexplained_gap": status_counts.get("unexplained_gap", 0),
        "parse_uncertain": status_counts.get("parse_uncertain", 0),
        "not_tested": status_counts.get("not_tested", 0),
        "primary_checks": primary_checks,
        "primary_matched": primary_matched,
        "primary_unresolved": primary_checks - primary_matched,
        "primary_determinate": primary_determinate,
        "primary_type_status_counts": {
            check_type: dict(counts)
            for check_type, counts in primary_type_status_counts.items()
        },
        "note_assertion_checks": note_assertion_checks,
        "note_assertion_matched": note_assertion_matched,
        "note_assertion_unresolved": note_assertion_unresolved,
        "gap_categories": dict(gap_categories),
    }


def primary_unresolved_taxonomy(payload: dict[str, Any]) -> dict[str, Any]:
    items = [
        item
        for sample in payload.get("samples", [])
        for item in sample.get("primary_unresolved_items", [])
    ]
    root_causes = Counter(item["root_cause"] for item in items)
    check_types = Counter(item["check_type"] for item in items)
    companies = Counter(item["company"] for item in items)
    total = len(items)
    top_root_count = sum(count for _cause, count in root_causes.most_common(3))
    return {
        "summary": {
            "total_primary_unresolved": total,
            "root_cause_counts": dict(root_causes),
            "check_type_counts": dict(check_types),
            "low_success_companies": [
                {"company": company, "primary_unresolved": count}
                for company, count in companies.most_common(20)
            ],
            "top_root_cause_coverage": (top_root_count / total) if total else 0,
            "allowed_root_causes": sorted(ROOT_CAUSE_CLASSES),
        },
        "top_examples": items[:20],
        "items": items,
    }


def false_matched_review_sample(payload: dict[str, Any], limit_per_type: int = 5) -> dict[str, Any]:
    selected: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for sample in payload.get("samples", []):
        for item in sample.get("primary_matched_items", []):
            check_type = item["check_type"]
            if counts[check_type] >= limit_per_type:
                continue
            selected.append(item)
            counts[check_type] += 1
    return {
        "summary": {
            "samples": len(selected),
            "check_type_counts": dict(counts),
            "selection_rule": f"first {limit_per_type} matched primary checks per verification type",
        },
        "items": selected,
    }


def false_matched_review_markdown(review: dict[str, Any]) -> str:
    summary = review["summary"]
    lines = [
        "# False Matched Review Sample",
        "",
        f"- Review samples: {summary['samples']}",
        f"- Selection rule: {summary['selection_rule']}",
        "",
        "## Check Type Counts",
        "",
        "| Check type | Samples |",
        "|---|---:|",
    ]
    for check_type, count in summary["check_type_counts"].items():
        lines.append(f"| {_check_type_label(check_type)} | {count} |")
    lines.extend(["", "## Samples", ""])
    for item in review["items"]:
        lines.extend(
            [
                f"### {item['company']} / {item['check_id']}",
                "",
                f"- Check type: {_check_type_label(item['check_type'])}",
                f"- Expected: {item['expected']}",
                f"- Actual: {item['actual']}",
                f"- Difference: {item['difference']}",
                f"- Tolerance: {item['tolerance']}",
                f"- Reason: {item['reason']}",
                "",
                "| Evidence | Amount | Source |",
                "|---|---:|---|",
            ]
        )
        for evidence in item["evidence"]:
            lines.append(
                f"| {evidence['label']} | {evidence['amount']} | `{evidence['source']}` |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def taxonomy_markdown(taxonomy: dict[str, Any]) -> str:
    summary = taxonomy["summary"]
    lines = [
        "# Primary Unresolved Taxonomy",
        "",
        f"- Primary unresolved: {summary['total_primary_unresolved']}",
        f"- Top root-cause coverage: {summary['top_root_cause_coverage']:.1%}",
        "",
        "## Root Cause Counts",
        "",
        "| Root cause | Count |",
        "|---|---:|",
    ]
    for cause, count in summary["root_cause_counts"].items():
        lines.append(f"| {cause} | {count} |")
    lines.extend(["", "## Check Type Counts", "", "| Check type | Count |", "|---|---:|"])
    for check_type, count in summary["check_type_counts"].items():
        lines.append(f"| {check_type} | {count} |")
    lines.extend(["", "## Low Success Companies", "", "| Company | Primary unresolved |", "|---|---:|"])
    for row in summary["low_success_companies"]:
        lines.append(f"| {row['company']} | {row['primary_unresolved']} |")
    lines.extend(["", "## Top 20 Examples", ""])
    for item in taxonomy["top_examples"]:
        lines.extend(
            [
                f"### {item['company']} / {item['check_id']}",
                "",
                f"- Root cause: {item['root_cause']}",
                f"- Check type: {item['check_type']}",
                f"- Status: {item['status']}",
                f"- Difference: {item['difference']}",
                f"- Reason: {item['reason']}",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def _primary_unresolved_item(company: str, sample_name: str, check: CheckResult) -> dict[str, Any]:
    return {
        "company": company,
        "sample": sample_name,
        "check_id": check.check_id,
        "check_type": check.check_type,
        "status": check.status,
        "root_cause": _root_cause_for_check(check),
        "note_no": check.note_no,
        "title": check.title,
        "expected": check.expected,
        "actual": check.actual,
        "difference": check.difference,
        "tolerance": check.tolerance,
        "reason": check.reason,
        "evidence": [asdict(evidence) for evidence in check.evidence[:8]],
    }


def _primary_matched_item(company: str, sample_name: str, check: CheckResult) -> dict[str, Any]:
    return {
        "company": company,
        "sample": sample_name,
        "check_id": check.check_id,
        "check_type": check.check_type,
        "status": check.status,
        "note_no": check.note_no,
        "title": check.title,
        "expected": check.expected,
        "actual": check.actual,
        "difference": check.difference,
        "tolerance": check.tolerance,
        "reason": check.reason,
        "evidence": [asdict(evidence) for evidence in check.evidence[:8]],
    }


def _root_cause_for_check(check: CheckResult) -> str:
    text = " ".join(
        [
            check.check_type,
            check.title,
            check.reason,
            " ".join(evidence.label for evidence in check.evidence),
            " ".join(evidence.source for evidence in check.evidence),
        ]
    )
    lowered = text.lower()
    if any(token in text for token in ("연결", "별도", "scope")) and "불일치" in text:
        return "scope_mismatch"
    if any(token in text for token in ("약정", "공정가치", "손상", "정책", "commitment", "fair value")):
        return "wrong_table_class"
    if any(token in text for token in ("전기", "전전기", "prior", "comparative")):
        return "wrong_period"
    if any(token in text for token in ("단위", "천원", "백만원", "unit")):
        return "wrong_unit"
    if any(token in text for token in ("부호", "유출", "유입", "positive", "negative", "sign")):
        return "wrong_sign"
    if check.check_type == "note_note_match":
        return "note_candidate_conflict"
    if check.check_type == "expense_allocation":
        return "formula_template_missing"
    if check.check_type == "cashflow_reconciliation":
        if check.status == "explainable_gap" or any(
            token in text for token in ("산식", "조정", "bridge", "formula")
        ):
            return "formula_template_missing"
        return "direct_evidence_missing"
    if any(token in lowered for token in ("parse", "table boundary", "row:", "col:")) and not check.evidence:
        return "parser_table_boundary_issue"
    if " + " in check.reason or " + " in check.title:
        return "composite_statement_account"
    return "direct_evidence_missing"


def _gap_categories(report: FullReport, checks: list[CheckResult]) -> dict[str, int]:
    categories: Counter[str] = Counter()
    for check in checks:
        if check.status == "parse_uncertain":
            categories["parse_uncertain_total"] += 1
        elif check.status == "unexplained_gap":
            categories[f"unexplained_{check.check_type}"] += 1
        elif check.status == "explainable_gap":
            categories[f"explainable_{check.check_type}"] += 1
    if len(report.statements) < 4:
        categories["statement_parse_sparse"] += 1
    if len(report.notes) < 20:
        categories["note_parse_sparse"] += 1
    if not any(check.check_type == "cashflow_reconciliation" for check in checks):
        categories["cashflow_target_sparse"] += 1
    return dict(categories)
