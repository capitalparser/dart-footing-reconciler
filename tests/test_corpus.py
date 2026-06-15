import json

from dart_footing_reconciler.checks import CheckEvidence, CheckResult
from dart_footing_reconciler.corpus import corpus_markdown, run_workpaper_corpus


def test_run_workpaper_corpus_reuses_local_sources_and_writes_summary(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <p>재무상태표</p><table><tr><th>구분</th><th>당기</th></tr><tr><td>유형자산</td><td>1,000</td></tr></table>
        <p>현금흐름표</p><table><tr><th>구분</th><th>당기</th></tr><tr><td>유형자산의 취득</td><td>(500)</td></tr></table>
        <p>11. 유형자산</p><table><tr><th>구분</th><th>당기</th></tr><tr><td>장부금액</td><td>1,000</td></tr><tr><td>취득</td><td>500</td></tr></table>
        """,
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "samples": [
                    {
                        "name": "sample",
                        "company": "Sample Co",
                        "source": str(source),
                        "tags": ["unit"],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = run_workpaper_corpus(manifest, tmp_path / "out", fetch_missing=False)

    assert payload["summary"]["samples"] == 1
    assert payload["summary"]["generated_reports"] == 1
    assert payload["summary"]["total_note_tables"] == 1
    assert payload["summary"]["known_layout_tables"] == 1
    assert payload["summary"]["unknown_layout_tables"] == 0
    assert payload["samples"][0]["coverage"]["total_tables"] == 1
    assert (tmp_path / "out" / "reports" / "sample.html").exists()
    corpus_report = (tmp_path / "out" / "corpus_report.md").read_text(encoding="utf-8")
    assert "Sample Co" in corpus_report
    assert "전체 주석 표: 1" in corpus_report
    assert "미분류 주석 표: 0" in corpus_report
    assert "미분류/저신뢰 layout 후보: 0" in corpus_report
    assert "검증 관련 미분류 후보: 0" in corpus_report


def test_run_workpaper_corpus_can_prune_raw_and_report_artifacts(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <p>재무상태표</p><table><tr><th>구분</th><th>당기</th></tr><tr><td>유형자산</td><td>1,000</td></tr></table>
        <p>11. 유형자산</p><table><tr><th>구분</th><th>당기</th></tr><tr><td>장부금액</td><td>1,000</td></tr></table>
        """,
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "samples": [
                    {
                        "name": "sample",
                        "company": "Sample Co",
                        "source": str(source),
                        "tags": ["unit"],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = run_workpaper_corpus(
        manifest,
        tmp_path / "out",
        fetch_missing=False,
        keep_artifacts=False,
    )

    assert payload["summary"]["generated_reports"] == 1
    assert (tmp_path / "out" / "corpus_result.json").exists()
    assert (tmp_path / "out" / "corpus_report.md").exists()
    assert not (tmp_path / "out" / "raw").exists()
    assert not (tmp_path / "out" / "reports").exists()


def test_corpus_markdown_counts_explainable_primary_gaps_as_unresolved():
    markdown = corpus_markdown(
        {
            "summary": {
                "samples": 1,
                "generated_reports": 1,
                "failed_samples": 0,
                "total_checks": 3,
                "matched": 1,
                "explainable_gap": 1,
                "unexplained_gap": 1,
                "parse_uncertain": 0,
                "not_tested": 0,
                "primary_checks": 3,
                "primary_matched": 1,
                "primary_unresolved": 2,
                "gap_categories": {},
            },
            "samples": [
                {
                    "company": "Sample Co",
                    "status": "generated",
                    "statements": 1,
                    "notes": 1,
                    "checks": 3,
                    "primary_checks": 3,
                    "primary_status_counts": {
                        "matched": 1,
                        "explainable_gap": 1,
                        "unexplained_gap": 1,
                    },
                    "status_counts": {
                        "matched": 1,
                        "explainable_gap": 1,
                        "unexplained_gap": 1,
                    },
                    "report_html": "sample.html",
                }
            ],
        }
    )

    assert "| Sample Co | 생성 완료 | 1 | 1 | 3 | 3 | 1 | 2 |" in markdown
    assert "자동화 보완 필요" in markdown
    assert "표 구조 해석 필요" in markdown
    assert "Unexplained" not in markdown
    assert "Parse uncertain" not in markdown


def test_corpus_markdown_includes_primary_success_rates_by_check_type():
    markdown = corpus_markdown(
        {
            "summary": {
                "samples": 1,
                "generated_reports": 1,
                "failed_samples": 0,
                "total_checks": 5,
                "matched": 3,
                "explainable_gap": 1,
                "unexplained_gap": 1,
                "parse_uncertain": 0,
                "not_tested": 0,
                "primary_checks": 4,
                "primary_matched": 2,
                "primary_unresolved": 2,
                "primary_determinate": 4,
                "gap_categories": {},
                "primary_type_status_counts": {
                    "primary_balance_reconciliation": {
                        "matched": 1,
                        "unexplained_gap": 1,
                    },
                    "cashflow_reconciliation": {
                        "matched": 1,
                        "explainable_gap": 1,
                    },
                },
            },
            "samples": [
                {
                    "company": "Sample Co",
                    "status": "generated",
                    "statements": 1,
                    "notes": 1,
                    "checks": 5,
                    "primary_checks": 4,
                    "primary_determinate": 4,
                    "primary_status_counts": {
                        "matched": 2,
                        "explainable_gap": 1,
                        "unexplained_gap": 1,
                    },
                    "status_counts": {
                        "matched": 3,
                        "explainable_gap": 1,
                        "unexplained_gap": 1,
                    },
                    "report_html": "sample.html",
                }
            ],
        }
    )

    assert "## 검증유형별 성공률" in markdown
    assert "| 검증유형 | 주요 항목 | 주요 무차이 대사 | 주요 후속 확인 | 무차이 대사율 | 자동 판정률 |" in markdown
    assert "| 재무제표-주석 금액 대사 | 2 | 1 | 1 | 50.0% | 100.0% |" in markdown
    assert "| 현금흐름 대사 | 2 | 1 | 1 | 50.0% | 100.0% |" in markdown


def test_corpus_writes_primary_unresolved_taxonomy(monkeypatch, tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <p>재무상태표</p><table><tr><th>구분</th><th>당기</th></tr><tr><td>유형자산</td><td>1,000</td></tr></table>
        <p>11. 유형자산</p><table><tr><th>구분</th><th>당기</th></tr><tr><td>장부금액</td><td>900</td></tr></table>
        """,
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {"samples": [{"name": "sample", "company": "Sample Co", "source": str(source)}]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    def fake_checks(report, prior_report, tolerance):
        return [
            CheckResult(
                check_id="reconciliation:ppe_balance",
                check_type="primary_balance_reconciliation",
                status="unexplained_gap",
                scope="report",
                note_no="11",
                title="ppe_balance",
                expected=1000,
                actual=900,
                difference=-100,
                tolerance=1,
                reason="financial statement line does not agree to note ending balance",
                evidence=[
                    CheckEvidence("statement 유형자산", 1000, "statement:bs/row:1/col:1"),
                    CheckEvidence("note 11 장부금액", 900, "note:11/table:0/row:1/col:1"),
                ],
            )
        ]

    monkeypatch.setattr("dart_footing_reconciler.corpus._run_checks", fake_checks)

    payload = run_workpaper_corpus(manifest, tmp_path / "out", fetch_missing=False)

    taxonomy_path = tmp_path / "out" / "primary_unresolved_taxonomy.json"
    taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    assert payload["summary"]["primary_unresolved"] == 1
    assert taxonomy["summary"]["total_primary_unresolved"] == 1
    assert taxonomy["items"][0]["root_cause"] == "direct_evidence_missing"
    assert taxonomy["items"][0]["company"] == "Sample Co"
    assert taxonomy["items"][0]["evidence"][0]["source"] == "statement:bs/row:1/col:1"
    assert (tmp_path / "out" / "primary_unresolved_taxonomy.md").exists()


def test_corpus_writes_unknown_layout_taxonomy(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <p>1. 일반사항</p>
        <table><tr><th>구분</th><th>내용</th></tr><tr><td>회사</td><td>샘플</td></tr></table>
        <p>11. 유형자산</p>
        <table><tr><th>구분</th><th>내용</th></tr><tr><td>취득</td><td>500</td></tr></table>
        """,
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {"samples": [{"name": "sample", "company": "Sample Co", "source": str(source)}]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = run_workpaper_corpus(manifest, tmp_path / "out", fetch_missing=False)

    taxonomy_path = tmp_path / "out" / "unknown_layout_taxonomy.json"
    taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    assert payload["summary"]["unknown_layout_items"] == 2
    assert payload["summary"]["validation_relevant_unknown_layout_items"] == 1
    assert taxonomy["summary"]["total_unknown_layout_items"] == 2
    assert taxonomy["summary"]["validation_relevant_unknown_layout_items"] == 1
    assert taxonomy["summary"]["non_validation_unknown_layout_items"] == 1
    assert taxonomy["summary"]["validation_relevance_counts"] == {
        "non_validation_note_table": 1,
        "asset_rollforward_candidate": 1,
    }
    assert taxonomy["items"][0]["company"] == "Sample Co"
    assert taxonomy["items"][0]["note_no"] == "1"
    assert taxonomy["items"][0]["layout_key"] == "unknown_layout"
    assert taxonomy["items"][0]["orientation_key"] == "unknown"
    assert taxonomy["items"][0]["headers"] == ["구분", "내용"]
    assert taxonomy["items"][0]["row_labels"] == ["회사"]
    assert taxonomy["items"][0]["validation_relevant"] is False
    assert taxonomy["items"][0]["validation_relevance"] == "non_validation_note_table"
    assert taxonomy["items"][1]["validation_relevant"] is True
    assert taxonomy["items"][1]["validation_relevance"] == "asset_rollforward_candidate"
    assert taxonomy["top_examples"][0]["validation_relevance"] == "asset_rollforward_candidate"
    assert (tmp_path / "out" / "unknown_layout_taxonomy.md").exists()


def test_corpus_writes_false_matched_review_sample(monkeypatch, tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <p>재무상태표</p><table><tr><th>구분</th><th>당기</th></tr><tr><td>유형자산</td><td>1,000</td></tr></table>
        <p>11. 유형자산</p><table><tr><th>구분</th><th>당기</th></tr><tr><td>장부금액</td><td>1,000</td></tr></table>
        """,
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {"samples": [{"name": "sample", "company": "Sample Co", "source": str(source)}]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    def fake_checks(report, prior_report, tolerance):
        return [
            CheckResult(
                check_id="reconciliation:ppe_balance",
                check_type="primary_balance_reconciliation",
                status="matched",
                scope="report",
                note_no="11",
                title="ppe_balance",
                expected=1000,
                actual=1000,
                difference=0,
                tolerance=1,
                reason="financial statement line agrees to note ending balance",
                evidence=[
                    CheckEvidence("statement 유형자산", 1000, "statement:bs/row:1/col:1"),
                    CheckEvidence("note 11 장부금액", 1000, "note:11/table:0/row:1/col:1"),
                ],
            )
        ]

    monkeypatch.setattr("dart_footing_reconciler.corpus._run_checks", fake_checks)

    payload = run_workpaper_corpus(manifest, tmp_path / "out", fetch_missing=False)

    review_path = tmp_path / "out" / "false_matched_review.md"
    review = review_path.read_text(encoding="utf-8")
    assert payload["summary"]["false_matched_review_samples"] == 1
    assert "False Matched Review Sample" in review
    assert "reconciliation:ppe_balance" in review
    assert "Expected: 1000" in review
    assert "Actual: 1000" in review
    assert "statement:bs/row:1/col:1" in review
