from dart_footing_reconciler.checks_fs_note import (
    _check_debt_level_column_matches,
    check_fs_note_matches,
    infer_balance_level,
)
from dart_footing_reconciler.taxonomy import classify_report
from dart_footing_reconciler.document import (
    FullReport,
    ReportBlock,
    ReportSection,
    ReportTable,
    SourceLocation,
)


def _section(section_id, title, kind, note_no, table, *, scope=""):
    return ReportSection(
        section_id,
        title,
        kind,
        note_no,
        [ReportBlock("table", "", table, table.location)],
        scope=scope,
    )


def _section_with_tables(section_id, title, kind, note_no, tables, *, scope=""):
    return ReportSection(
        section_id,
        title,
        kind,
        note_no,
        [ReportBlock("table", "", table, table.location) for table in tables],
        scope=scope,
    )


def _lease_results(report, *, tolerance=0):
    return [
        result
        for result in check_fs_note_matches(report, tolerance=tolerance)
        if result.check_id.startswith("fs_note:lease_liabilities")
    ]


def _lease_status_by_suffix(results):
    return {result.check_id.rsplit(":", 1)[-1]: result.status for result in results}


def _lease_statement(rows, *, scope="consolidated", table_index=0, section_id="statement:bs"):
    return _section(
        section_id,
        "재무상태표",
        "statement",
        "",
        ReportTable(
            table_index,
            rows,
            "재무상태표",
            SourceLocation(section_id, 0, table_index),
        ),
        scope=scope,
    )


def _lease_note(title, note_no, tables, *, scope="consolidated", section_id=None):
    section_id = section_id or f"note:{note_no}"
    if len(tables) == 1:
        return _section(section_id, title, "note", note_no, tables[0], scope=scope)
    return _section_with_tables(section_id, title, "note", note_no, tables, scope=scope)


def _lease_note_table(index, rows, *, note_no="17", heading=None, unit_multiplier=1):
    return ReportTable(
        index,
        rows,
        heading or f"{note_no}. 리스부채",
        SourceLocation(f"note:{note_no}", 0, index),
        unit_multiplier=unit_multiplier,
    )


def _debt_results(report, account_key="borrowings", *, tolerance=0):
    # 레벨-열 인식 헬퍼를 직접 시험한다(BLOCKER 가드가 여기 산다). dispatch의
    # additive-fallback(레벨 abstain 시 단일 페어링으로 폴백)은 corpus 하드 게이트로
    # 검증되므로(매치 +7, 정타 파괴 0), 단위 테스트는 헬퍼의 match/abstain를 핀한다.
    fs_hits = [
        line
        for line in classify_report(report).statement_lines
        if line.account_key == account_key
    ]
    return _check_debt_level_column_matches(report, account_key, fs_hits, tolerance)


def _debt_status_by_suffix(results):
    return {result.check_id.rsplit(":", 1)[-1]: result.status for result in results}


def _debt_statement(rows, *, scope="consolidated", table_index=0, section_id="statement:bs"):
    return _section(
        section_id,
        "재무상태표",
        "statement",
        "",
        ReportTable(
            table_index,
            rows,
            "재무상태표",
            SourceLocation(section_id, 0, table_index),
        ),
        scope=scope,
    )


def _debt_note(title, note_no, tables, *, scope="consolidated", section_id=None):
    section_id = section_id or f"note:{note_no}"
    if len(tables) == 1:
        return _section(section_id, title, "note", note_no, tables[0], scope=scope)
    return _section_with_tables(section_id, title, "note", note_no, tables, scope=scope)


def _debt_note_table(index, rows, *, note_no="18", heading=None, unit_multiplier=1):
    return ReportTable(
        index,
        rows,
        heading or f"{note_no}. 차입금",
        SourceLocation(f"note:{note_no}", 0, index),
        unit_multiplier=unit_multiplier,
    )


def test_check_fs_note_matches_balance_sheet_line_to_note_total():
    statement_table = ReportTable(
        0, [["구분", "당기"], ["유형자산(순액)", "1,000"]], "재무상태표", SourceLocation("statement:bs", 0, 0)
    )
    note_table = ReportTable(
        1, [["구분", "합계"], ["기말 장부금액", "1,000"]], "11. 유형자산 및 사용권자산", SourceLocation("note:11", 0, 1)
    )
    report = FullReport(
        "sample.html",
        "Sample Co",
        [_section("statement:bs", "재무상태표", "statement", "", statement_table)],
        [_section("note:11", "유형자산 및 사용권자산", "note", "11", note_table)],
    )
    results = check_fs_note_matches(report, tolerance=0)
    assert results[0].check_type == "fs_note_match"
    assert results[0].status == "matched"
    assert results[0].check_id == "fs_note:property_plant_equipment:11"


def test_check_fs_note_matches_pl_sce_and_cf_lines():
    statements = [
        _section("statement:pl", "손익계산서", "statement", "", ReportTable(0, [["구분", "당기"], ["매출액", "500"], ["감가상각비", "30"]], "손익계산서", SourceLocation("statement:pl", 0, 0))),
        _section("statement:sce", "자본변동표", "statement", "", ReportTable(1, [["구분", "당기"], ["배당", "20"]], "자본변동표", SourceLocation("statement:sce", 0, 1))),
        _section("statement:cf", "현금흐름표", "statement", "", ReportTable(2, [["구분", "당기"], ["현금및현금성자산의증가", "10"]], "현금흐름표", SourceLocation("statement:cf", 0, 2))),
    ]
    notes = [
        _section("note:20", "고객과의 계약에서 생기는 수익", "note", "20", ReportTable(3, [["구분", "금액"], ["매출액", "500"]], "20. 수익", SourceLocation("note:20", 0, 3))),
        _section("note:25", "비용의 성격별 분류", "note", "25", ReportTable(4, [["구분", "금액"], ["감가상각비", "30"]], "25. 비용", SourceLocation("note:25", 0, 4))),
        _section("note:30", "배당", "note", "30", ReportTable(5, [["구분", "금액"], ["배당", "20"]], "30. 배당", SourceLocation("note:30", 0, 5))),
        _section("note:31", "현금및현금성자산", "note", "31", ReportTable(6, [["구분", "금액"], ["현금및현금성자산의증가", "10"]], "31. 현금", SourceLocation("note:31", 0, 6))),
    ]

    results = check_fs_note_matches(FullReport("sample.html", "Sample Co", statements, notes), tolerance=0)

    assert {"매출액", "감가상각비", "배당", "현금및현금성자산의증가"} <= {
        result.title.split()[0] for result in results if result.status == "matched"
    }


def test_fs_note_selects_admitted_candidate_by_label_priority():
    bs = _section(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "당기"], ["유형자산(순액)", "1,000"]],
            "재무상태표",
            SourceLocation("statement:bs", 0, 0),
        ),
    )
    note = _section(
        "note:11",
        "유형자산",
        "note",
        "11",
        ReportTable(
            1,
            [["구분", "당기"], ["장부금액", "980"], ["기말 장부금액", "1,000"]],
            "11. 유형자산",
            SourceLocation("note:11", 0, 1),
        ),
    )

    results = check_fs_note_matches(FullReport("s.html", "Co", [bs], [note]), tolerance=0)

    ppe = [r for r in results if r.check_id.startswith("fs_note:property_plant_equipment")]
    assert ppe and ppe[0].actual == 1000 and ppe[0].status == "matched", [
        (r.actual, r.status) for r in ppe
    ]


def test_fs_note_investment_property_true_total_not_overtaken_by_closing_subline():
    bs = _section(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "당기"], ["투자부동산", "1,000"]],
            "재무상태표",
            SourceLocation("statement:bs", 0, 0),
        ),
    )
    note = _section(
        "note:12",
        "투자부동산",
        "note",
        "12",
        ReportTable(
            1,
            [["구분", "당기"], ["장부금액", "1,000"], ["기말환율조정", "900"]],
            "12. 투자부동산",
            SourceLocation("note:12", 0, 1),
        ),
    )

    results = check_fs_note_matches(FullReport("s.html", "Co", [bs], [note]), tolerance=0)

    investment_property = [
        r for r in results if r.check_id.startswith("fs_note:investment_property")
    ]
    assert investment_property and investment_property[0].status == "matched", [
        (r.actual, r.status) for r in investment_property
    ]
    assert investment_property[0].actual == 1000
    assert any("장부금액" in evidence.label for evidence in investment_property[0].evidence)
    assert not any("기말환율조정" in evidence.label for evidence in investment_property[0].evidence)


def test_fs_note_gross_cost_row_not_selected_over_net_carrying_total():
    # F-1 (Codex 적대적 리뷰): "기말 취득원가"는 gross 원가 행이라 "기말"로 시작해도
    # 순장부금액 총계가 아니다. 접두 매칭된 "기말"이 진짜 순총계("장부금액")를 밀어내면
    # gross를 잡아 거짓 페어링이 된다 → _is_balance_row의 "취득원가" reject로 차단.
    bs = _section(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "당기"], ["투자부동산", "1,000"]],
            "재무상태표",
            SourceLocation("statement:bs", 0, 0),
        ),
    )
    note = _section(
        "note:12",
        "투자부동산",
        "note",
        "12",
        ReportTable(
            1,
            [["구분", "당기"], ["장부금액", "1,000"], ["기말 취득원가", "1,500"]],
            "12. 투자부동산",
            SourceLocation("note:12", 0, 1),
        ),
    )

    results = check_fs_note_matches(FullReport("s.html", "Co", [bs], [note]), tolerance=0)

    ip = [r for r in results if r.check_id.startswith("fs_note:investment_property")]
    assert ip and ip[0].status == "matched", [(r.actual, r.status) for r in ip]
    assert ip[0].actual == 1000
    assert any("장부금액" in evidence.label for evidence in ip[0].evidence)
    assert not any("취득원가" in evidence.label for evidence in ip[0].evidence)


def test_fs_note_keeps_honest_gap_when_admitted_row_differs():
    bs = _section(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "당기"], ["유형자산(순액)", "1,000"]],
            "재무상태표",
            SourceLocation("statement:bs", 0, 0),
        ),
    )
    note = _section(
        "note:11",
        "유형자산",
        "note",
        "11",
        ReportTable(
            1,
            [["구분", "당기"], ["장부금액", "1,000"], ["기말 장부금액", "900"]],
            "11. 유형자산",
            SourceLocation("note:11", 0, 1),
        ),
    )

    results = check_fs_note_matches(FullReport("s.html", "Co", [bs], [note]), tolerance=0)

    ppe = [r for r in results if r.check_id.startswith("fs_note:property_plant_equipment")]
    assert ppe and ppe[0].actual == 900 and ppe[0].status == "unexplained_gap", [
        (r.actual, r.status) for r in ppe
    ]


def test_fs_note_uses_current_period_column():
    bs_tbl = ReportTable(
        0,
        [["구분", "당기", "전기"], ["유형자산(순액)", "1,000", "800"]],
        "재무상태표",
        SourceLocation("statement:bs", 0, 0),
    )
    note_tbl = ReportTable(
        1,
        [["구분", "당기", "전기"], ["기말 장부금액", "1,000", "800"]],
        "11. 유형자산",
        SourceLocation("note:11", 0, 1),
    )
    report = FullReport(
        "s.html",
        "Co",
        [_section("statement:bs", "재무상태표", "statement", "", bs_tbl)],
        [_section("note:11", "유형자산", "note", "11", note_tbl)],
    )

    results = check_fs_note_matches(report, tolerance=0)

    ppe = [r for r in results if r.check_id.startswith("fs_note:property_plant_equipment")]
    assert ppe and ppe[0].expected == 1000 and ppe[0].actual == 1000


def test_fs_note_allows_large_statement_note_rounding_under_one_thousand():
    statement = _section(
        "statement:pl",
        "손익계산서",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "당기"], ["매출액", "16,592,248,884,388"]],
            "손익계산서",
            SourceLocation("statement:pl", 0, 0),
        ),
    )
    note = _section(
        "note:6",
        "영업부문",
        "note",
        "6",
        ReportTable(
            1,
            [["구분", "당기"], ["매출액", "16,592,248,884"]],
            "6. 영업부문 매출액 (단위 : 천원)",
            SourceLocation("note:6", 0, 1),
            unit_multiplier=1000,
        ),
    )

    results = check_fs_note_matches(FullReport("s.html", "Co", [statement], [note]), tolerance=1)

    revenue = [result for result in results if result.check_id.startswith("fs_note:revenue")]
    assert revenue and revenue[0].status == "matched"
    assert revenue[0].difference == -388


def test_fs_note_keeps_eps_difference_in_won_as_gap():
    statement = _section(
        "statement:pl",
        "포괄손익계산서",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "당기"], ["보통주 기본및희석주당이익 (단위 : 원)", "8,961"]],
            "포괄손익계산서",
            SourceLocation("statement:pl", 0, 0),
        ),
    )
    note = _section(
        "note:30",
        "주당이익",
        "note",
        "30",
        ReportTable(
            1,
            [["구분", "당기"], ["계속영업기본주당이익(손실) - 보통주", "8,138"]],
            "30. 주당이익 (단위 : 원)",
            SourceLocation("note:30", 0, 1),
        ),
    )

    results = check_fs_note_matches(FullReport("s.html", "Co", [statement], [note]), tolerance=1)

    eps = [result for result in results if result.check_id.startswith("fs_note:earnings_per_share")]
    assert eps and eps[0].status == "unexplained_gap"
    assert eps[0].difference == -823


def test_fs_note_ignores_generic_balance_row_from_unrelated_note_topic():
    statement = _section(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "당기"], ["유형자산(순액)", "1,000"]],
            "재무상태표",
            SourceLocation("statement:bs", 0, 0),
        ),
    )
    risk_note = _section(
        "note:5",
        "금융위험관리",
        "note",
        "5",
        ReportTable(
            1,
            [["구분", "합계"], ["기말 장부금액", "1,000"]],
            "5. 금융위험관리 장부금액",
            SourceLocation("note:5", 0, 1),
        ),
    )
    ppe_note = _section(
        "note:13",
        "유형자산",
        "note",
        "13",
        ReportTable(
            2,
            [["구분", "합계"], ["장부금액", "900"]],
            "13. 유형자산",
            SourceLocation("note:13", 0, 2),
        ),
    )

    results = check_fs_note_matches(
        FullReport("s.html", "Co", [statement], [risk_note, ppe_note]), tolerance=0
    )

    ppe = [result for result in results if result.check_id.startswith("fs_note:property_plant_equipment")]
    assert ppe and ppe[0].note_no == "13"
    assert ppe[0].actual == 900


def test_select_note_hit_prefers_topic_matching_note_over_label_priority():
    """실데이터 FP: taxonomy가 금융위험관리 주석의 '장부금액 합계'를 유형자산으로
    과분류하면, 행 라벨 우선순위('합계')만 보는 선택기는 무관한 주석을 고른다.
    주석 주제(note_title)가 계정과 맞는 후보(유형자산)를 우선해야 한다."""
    from dart_footing_reconciler.checks_fs_note import _select_note_hit_by_label
    from dart_footing_reconciler.taxonomy import ClassifiedNoteAmount

    def _na(note_no, note_title, label, amount):
        return ClassifiedNoteAmount(
            "property_plant_equipment", "유형자산", note_no, note_title, label, amount,
            f"note:{note_no}", 1.0, "",
        )

    hits = [
        _na("5-1", "금융위험관리 (연결)", "장부금액 합계", 3_282_074_209_000),
        _na("13", "유형자산 (연결)", "기말 유형자산", 17_706_530_246_000),
    ]

    chosen = _select_note_hit_by_label(hits, "property_plant_equipment")

    assert chosen is not None and chosen.note_no == "13", chosen


def test_fs_note_million_won_note_rounding_matches():
    """백만원 단위 주석 총액이 원 단위 FS와 표시 반올림(<1 백만) 내에서 일치하면 matched.

    한화오션 type: FS 유형자산 4,648,353,653,506원 vs 주석 백만원 표 기말 4,648,354(백만).
    """
    bs = _section(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "당기"], ["유형자산", "4648353653506"]],
            "재무상태표",
            SourceLocation("statement:bs", 0, 0),
        ),
    )
    note = _section(
        "note:14",
        "유형자산 및 사용권자산",
        "note",
        "14",
        ReportTable(
            1,
            [["구분", "합계"], ["기말 유형자산", "4648354"]],
            "14. 유형자산 및 사용권자산",
            SourceLocation("note:14", 0, 1),
            unit_multiplier=1_000_000,
        ),
    )
    results = check_fs_note_matches(FullReport("s.html", "Co", [bs], [note]), tolerance=1)
    ppe = [r for r in results if r.check_id.startswith("fs_note:property_plant_equipment")]
    assert ppe and ppe[0].status == "matched", [
        (r.expected, r.actual, r.difference, r.status) for r in ppe
    ]


def test_fs_note_million_won_note_real_gap_still_flagged():
    """백만 단위라도 1 백만 이상 차이가 나면 gap으로 남는다(반올림 흡수 과확장 방지)."""
    bs = _section(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "당기"], ["유형자산", "4648353653506"]],
            "재무상태표",
            SourceLocation("statement:bs", 0, 0),
        ),
    )
    note = _section(
        "note:14",
        "유형자산 및 사용권자산",
        "note",
        "14",
        ReportTable(
            1,
            [["구분", "합계"], ["기말 유형자산", "4650000"]],  # 4,650,000 백만 → 1.6십억 차이
            "14. 유형자산 및 사용권자산",
            SourceLocation("note:14", 0, 1),
            unit_multiplier=1_000_000,
        ),
    )
    results = check_fs_note_matches(FullReport("s.html", "Co", [bs], [note]), tolerance=1)
    ppe = [r for r in results if r.check_id.startswith("fs_note:property_plant_equipment")]
    assert ppe and ppe[0].status == "unexplained_gap", [
        (r.expected, r.actual, r.difference, r.status) for r in ppe
    ]


def test_fs_note_dividends_ignores_non_payout_confounder_rows():
    """배당 reconciliation은 실제 지급배당금 총액만 페어링한다. 배당수익(income)·
    배당받은 주식수(count)·주당배당금(per-share)·배당평균적립금(reserve)·미지급배당금
    같은 confounder 행은 제외한다(부호 차이로 status는 gap일 수 있으나 행은 정타)."""
    sce = _section(
        "statement:sce",
        "자본변동표",
        "statement",
        "",
        ReportTable(0, [["구분", "당기"], ["연차배당", "-100"]], "자본변동표", SourceLocation("statement:sce", 0, 0)),
    )
    note = _section(
        "note:26",
        "배당금",
        "note",
        "26",
        ReportTable(
            1,
            [
                ["구분", "금액"],
                ["배당수익", "5000"],
                ["배당받은 주식수", "999999"],
                ["보통주에 지급된 주당배당금", "1700"],
                ["배당평균적립금", "70000"],
                ["재무제표 발행승인일 전에 제안 또는 선언되었으나 인식되지 아니한 배당금", "88888"],
                ["보통주에 지급된 배당금", "100"],
            ],
            "26. 배당금",
            SourceLocation("note:26", 0, 1),
        ),
    )
    results = check_fs_note_matches(FullReport("s.html", "Co", [sce], [note]), tolerance=1)
    div = [r for r in results if r.check_id.startswith("fs_note:dividends")]
    assert div, "dividends check should fire on the payout total"
    # 지급된 배당금만 페어링; 배당수익/주식수/주당/평균적립금/인식되지아니한배당금 전부 제외
    assert div[0].actual == 100, [r.actual for r in div]


def test_fs_note_dividends_record_date_cell_never_selected():
    sce = _section(
        "statement:sce",
        "자본변동표",
        "statement",
        "",
        ReportTable(0, [["구분", "당기"], ["연차배당", "-100"]], "자본변동표", SourceLocation("statement:sce", 0, 0)),
    )
    note = _section(
        "note:26",
        "배당금",
        "note",
        "26",
        ReportTable(
            1,
            [
                ["구분", "금액"],
                ["배당기준일", "20250228"],
                ["보통주에 지급된 배당금", "100"],
            ],
            "26. 배당금",
            SourceLocation("note:26", 0, 1),
        ),
    )

    results = check_fs_note_matches(FullReport("s.html", "Co", [sce], [note]), tolerance=1)

    div = [r for r in results if r.check_id.startswith("fs_note:dividends")]
    assert div, "dividends check should use the payout amount, not the record date"
    assert div[0].actual == 100, [(r.actual, r.status) for r in div]
    assert not any("배당기준일" in evidence.label for evidence in div[0].evidence)


def test_fs_note_dividends_statement_ignores_stock_and_hybrid_dividend():
    """FS 앵커는 소유주 현금배당만. 주식배당(0)·신종자본증권에 대한 배당은 배당 앵커로 쓰지 않는다."""
    sce = _section(
        "statement:sce",
        "자본변동표",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "당기"], ["주식배당", "0"], ["신종자본증권에 대한 배당", "-50"], ["연차배당", "-100"]],
            "자본변동표",
            SourceLocation("statement:sce", 0, 0),
        ),
    )
    note = _section(
        "note:26",
        "배당금",
        "note",
        "26",
        ReportTable(1, [["구분", "금액"], ["보통주에 지급된 배당금", "100"]], "26. 배당금", SourceLocation("note:26", 0, 1)),
    )
    results = check_fs_note_matches(FullReport("s.html", "Co", [sce], [note]), tolerance=1)
    div = [r for r in results if r.check_id.startswith("fs_note:dividends")]
    assert div and div[0].expected == -100, [r.expected for r in div]  # 연차배당, not 주식배당/신종자본증권


def test_fs_note_borrowings_abstains_when_note_total_is_only_reclassification():
    """차입금/사채 주석을 찾았더라도 후보가 재분류('유동성 대체')·음수 행뿐이면, 잔액이
    아닌 행과 페어링하거나 무관한 주석으로 폴백하지 않고 abstain한다. 차입금 잔액은 음수가
    될 수 없으므로 -1,120,559,090,000 같은 대체 행은 페어링 대상이 아니다(삼성SDI 패턴)."""
    bs = _section(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "당기"], ["단기차입금", "6,514,149,732,576"]],
            "재무상태표",
            SourceLocation("statement:bs", 0, 0),
        ),
    )
    borrow_note = _section(
        "note:17",
        "차입금",
        "note",
        "17",
        ReportTable(
            1,
            [["구분", "당기"], ["비유동차입금의 유동성 대체 부분", "-1,120,559,090,000"]],
            "17. 차입금",
            SourceLocation("note:17", 0, 1),
        ),
    )
    # 무관 주석이 'borrowings'로 과분류돼도(유동/비유동 alias), 폴백 garbage 페어링 금지.
    other_note = _section(
        "note:10",
        "기타투자자산",
        "note",
        "10",
        ReportTable(
            2,
            [["구분", "당기"], ["비유동기타투자자산", "981,102,542,000"]],
            "10. 기타투자자산",
            SourceLocation("note:10", 0, 2),
        ),
    )
    results = check_fs_note_matches(
        FullReport("s.html", "Co", [bs], [borrow_note, other_note]), tolerance=1
    )
    borrow = [r for r in results if r.check_id.startswith("fs_note:borrowings")]
    assert not borrow, [(r.actual, r.status) for r in borrow]


def test_fs_note_borrowings_picks_balance_row_over_reclassification():
    """잔액 행(유동차입금 +744,668M)과 재분류 행(유동성 대체 -395,968M)이 함께 있으면
    잔액 행을 고른다(현대건설 주석17 패턴 — 기존 matched 보존)."""
    bs = _section(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "당기"], ["단기차입금", "744,668,000,000"]],
            "재무상태표",
            SourceLocation("statement:bs", 0, 0),
        ),
    )
    borrow_note = _section(
        "note:17",
        "차입금",
        "note",
        "17",
        ReportTable(
            1,
            [
                ["구분", "당기"],
                ["유동차입금", "744,668,000,000"],
                ["유동성 금융기관 차입금(사채 제외)", "-395,968,000,000"],
            ],
            "17. 차입금",
            SourceLocation("note:17", 0, 1),
        ),
    )
    results = check_fs_note_matches(FullReport("s.html", "Co", [bs], [borrow_note]), tolerance=1)
    borrow = [r for r in results if r.check_id.startswith("fs_note:borrowings")]
    assert borrow and borrow[0].actual == 744668000000 and borrow[0].status == "matched", [
        (r.actual, r.status) for r in borrow
    ]


def test_fs_note_borrowings_cj_shape_matches_level_columns():
    bs = _debt_statement(
        [
            ["구분", "당기"],
            ["유동부채", ""],
            ["단기차입금", "3,090"],
            ["비유동부채", ""],
            ["장기차입금", "995"],
        ]
    )
    note = _debt_note(
        "차입금",
        "21",
        [
            _debt_note_table(
                1,
                [
                    ["차입금명칭", "단기차입금", "장기차입금", "유동성장기차입금"],
                    ["합계", "3,090", "995", "1,276"],
                ],
                note_no="21",
                heading="21. 차입금",
            )
        ],
    )

    results = _debt_results(FullReport("s.html", "CJ", [bs], [note]))

    assert _debt_status_by_suffix(results) == {
        "current": "matched",
        "noncurrent": "matched",
    }
    assert {result.actual for result in results} == {3090, 995}
    assert not any(result.actual == 1276 for result in results)


def test_fs_note_borrowings_and_bonds_naver_shape_matches_combined_current_and_bonds():
    bs = _debt_statement(
        [
            ["구분", "당기"],
            ["유동부채", ""],
            ["단기차입금", "135"],
            ["유동성장기차입금", "200"],
            ["비유동부채", ""],
            ["장기차입금", "863"],
            ["사채", "2,007"],
        ]
    )
    note = _debt_note(
        "차입금 및 사채",
        "18",
        [
            _debt_note_table(
                1,
                [
                    ["구분", "단기차입금 및 유동성장기차입금", "장기차입금", "사채"],
                    ["합계", "335", "863", "2,007"],
                ],
                note_no="18",
                heading="18. 차입금 및 사채",
            )
        ],
    )

    borrowings = _debt_results(FullReport("s.html", "NAVER", [bs], [note]))
    bonds = _debt_results(FullReport("s.html", "NAVER", [bs], [note]), "bonds")

    assert _debt_status_by_suffix(borrowings) == {
        "current": "matched",
        "noncurrent": "matched",
    }
    assert {result.actual for result in borrowings} == {335, 863}
    assert _debt_status_by_suffix(bonds) == {"noncurrent": "matched"}
    assert bonds[0].actual == 2007


def test_fs_note_borrowings_maturity_or_undiscounted_table_abstains():
    bs = _debt_statement([["구분", "당기"], ["단기차입금", "100"]])
    note = _debt_note(
        "차입금",
        "21",
        [
            _debt_note_table(
                1,
                [
                    ["잔존만기", "단기차입금"],
                    ["1년이내", "80"],
                    ["1~5년", "20"],
                    ["합계", "100"],
                ],
                note_no="21",
                heading="21. 차입금 미할인 계약상현금흐름",
            )
        ],
    )

    results = _debt_results(FullReport("s.html", "Co", [bs], [note]))

    assert _debt_status_by_suffix(results) == {"current": "not_tested"}
    assert not any(result.status == "matched" for result in results)


def test_fs_note_borrowings_uses_current_period_level_column_not_prior_match():
    bs = _debt_statement([["구분", "당기"], ["단기차입금", "100"]])
    note = _debt_note(
        "차입금",
        "21",
        [
            _debt_note_table(
                1,
                [
                    ["구분", "제 2 기 단기차입금", "제 1 기 단기차입금"],
                    ["합계", "120", "100"],
                ],
                note_no="21",
                heading="21. 차입금",
            )
        ],
    )

    results = _debt_results(FullReport("s.html", "Co", [bs], [note]))

    assert len(results) == 1
    assert results[0].check_id == "fs_note:borrowings:21:current"
    assert results[0].status == "unexplained_gap"
    assert results[0].actual == 120


def test_fs_note_bonds_rejects_gross_and_contra_columns_and_selects_net():
    bs = _debt_statement([["구분", "당기"], ["사채", "900"]])
    note = _debt_note(
        "사채",
        "19",
        [
            _debt_note_table(
                1,
                [
                    ["구분", "사채액면", "사채할인발행차금", "사채(순액)"],
                    ["합계", "1,000", "-100", "900"],
                ],
                note_no="19",
                heading="19. 사채",
            )
        ],
    )

    results = _debt_results(FullReport("s.html", "Co", [bs], [note]), "bonds")

    assert _debt_status_by_suffix(results) == {"noncurrent": "matched"}
    assert results[0].actual == 900
    evidence_text = " ".join(evidence.label for result in results for evidence in result.evidence)
    assert "사채액면" not in evidence_text
    assert "사채할인발행차금" not in evidence_text


def test_fs_note_borrowings_combined_account_column_abstains():
    bs = _debt_statement([["구분", "당기"], ["단기차입금", "100"]])
    note = _debt_note(
        "차입금 및 사채",
        "18",
        [
            _debt_note_table(
                1,
                [["구분", "차입금및사채"], ["합계", "100"]],
                note_no="18",
                heading="18. 차입금 및 사채",
            )
        ],
    )

    results = _debt_results(FullReport("s.html", "Co", [bs], [note]))

    assert _debt_status_by_suffix(results) == {"current": "not_tested"}
    assert not any(result.status == "matched" for result in results)


def test_fs_note_borrowings_combined_account_note_title_blocks_legacy_gap():
    bs = _debt_statement([["구분", "당기"], ["단기차입금", "100"]])
    note = _debt_note(
        "차입금및사채",
        "17",
        [
            _debt_note_table(
                1,
                [["구분", "당기"], ["유동 차입금(사채 포함)", "80"]],
                note_no="17",
                heading="17. 차입금및사채",
            )
        ],
    )

    results = _debt_results(FullReport("s.html", "Co", [bs], [note]))

    assert _debt_status_by_suffix(results) == {"current": "not_tested"}
    assert not any(result.status == "unexplained_gap" for result in results)


def test_fs_note_borrowings_per_loan_without_total_level_pattern_abstains():
    bs = _debt_statement([["구분", "당기"], ["단기차입금", "100"]])
    note = _debt_note(
        "차입금",
        "21",
        [
            _debt_note_table(
                1,
                [["차입처", "단기차입금"], ["은행A", "70"], ["은행B", "30"]],
                note_no="21",
                heading="21. 차입금",
            )
        ],
    )

    results = _debt_results(FullReport("s.html", "Co", [bs], [note]))

    assert _debt_status_by_suffix(results) == {"current": "not_tested"}
    assert not any(result.status == "matched" for result in results)


def test_fs_note_borrowings_unknown_statement_level_abstains_instead_of_subset_match():
    bs = _debt_statement(
        [
            ["구분", "당기"],
            ["단기차입금", "100"],
            ["차입금", "50"],
        ]
    )
    note = _debt_note(
        "차입금",
        "21",
        [
            _debt_note_table(
                1,
                [["구분", "단기차입금"], ["합계", "100"]],
                note_no="21",
                heading="21. 차입금",
            )
        ],
    )

    results = _debt_results(FullReport("s.html", "Co", [bs], [note]))

    assert _debt_status_by_suffix(results) == {"current": "not_tested"}
    assert not any(result.status == "matched" for result in results)


def test_fs_note_borrowings_selection_does_not_change_to_match_statement_amount():
    note = _debt_note(
        "차입금",
        "21",
        [
            _debt_note_table(
                1,
                [["구분", "단기차입금"], ["합계", "100"]],
                note_no="21",
                heading="21. 차입금",
            ),
            _debt_note_table(
                2,
                [["구분", "단기차입금"], ["합계", "999"]],
                note_no="21",
                heading="21. 차입금",
            ),
        ],
    )
    matching_bs = _debt_statement([["구분", "당기"], ["단기차입금", "100"]])
    nonmatching_bs = _debt_statement([["구분", "당기"], ["단기차입금", "999"]])

    matching = _debt_results(FullReport("s.html", "Co", [matching_bs], [note]))
    nonmatching = _debt_results(FullReport("s.html", "Co", [nonmatching_bs], [note]))

    assert matching[0].actual == nonmatching[0].actual == 100
    assert matching[0].status == "matched"
    assert nonmatching[0].status == "unexplained_gap"


def test_infer_balance_level_out_of_range_row_returns_unknown():
    rows = [["유동부채", ""], ["단기차입금", "100"]]

    assert infer_balance_level(rows, 99) == "unknown"


def test_fs_note_balance_account_abstains_when_no_topical_note_exists():
    """잔액 계정(PPE)에 제목이 일치하는 주석이 아예 없으면, 과분류된 무관 주석 행
    (예: 매출채권 '장부금액 합계')으로 폴백해 garbage 차이를 만들지 않고 abstain한다
    (셀트리온 패턴: 유형자산 1.24조 vs 매출채권 267백만 페어링 방지)."""
    bs = _section(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "당기"], ["유형자산", "1,244,567,343,881"]],
            "재무상태표",
            SourceLocation("statement:bs", 0, 0),
        ),
    )
    # PPE 제목과 무관한 주석. PPE의 장부금액 alias가 이 행을 과분류하지만, 제목이 안
    # 맞으므로 잔액 계정은 abstain해야 한다.
    unrelated = _section(
        "note:8",
        "매출채권",
        "note",
        "8",
        ReportTable(
            1,
            [["구분", "당기"], ["장부금액 합계", "267,755,000"]],
            "8. 매출채권",
            SourceLocation("note:8", 0, 1),
        ),
    )
    results = check_fs_note_matches(FullReport("s.html", "Co", [bs], [unrelated]), tolerance=1)
    ppe = [r for r in results if r.check_id.startswith("fs_note:property_plant_equipment")]
    assert not ppe, [(r.actual, r.status) for r in ppe]


def test_fs_note_revenue_keeps_fallback_to_segment_note():
    """비잔액 계정(매출)은 주석 제목이 계정명과 다르므로(예: '영업부문') 주제 일치가
    안 돼도 기존 폴백을 유지한다 — 잔액 계정 abstain 규칙이 매출 매칭을 깨면 안 된다."""
    pl = _section(
        "statement:pl",
        "손익계산서",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "당기"], ["매출액", "16,592,248,884,388"]],
            "손익계산서",
            SourceLocation("statement:pl", 0, 0),
        ),
    )
    segment = _section(
        "note:6",
        "영업부문",
        "note",
        "6",
        ReportTable(
            1,
            [["구분", "당기"], ["매출액", "16,592,248,884"]],
            "6. 영업부문 (단위 : 천원)",
            SourceLocation("note:6", 0, 1),
            unit_multiplier=1000,
        ),
    )
    results = check_fs_note_matches(FullReport("s.html", "Co", [pl], [segment]), tolerance=1)
    rev = [r for r in results if r.check_id.startswith("fs_note:revenue")]
    assert rev and rev[0].status == "matched", [(r.actual, r.status) for r in rev]


def test_fs_note_intangible_prefers_closing_amount_over_carrying_subline():
    bs = _section(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "당기"], ["무형자산", "3,657,186,453"]],
            "재무상태표",
            SourceLocation("statement:bs", 0, 0),
        ),
    )
    note = _section(
        "note:14",
        "무형자산",
        "note",
        "14",
        ReportTable(
            1,
            [
                ["구분", "당기"],
                ["순장부금액", "997,924"],
                ["기말금액", "3,657,186,453"],
            ],
            "14. 무형자산",
            SourceLocation("note:14", 0, 1),
        ),
    )

    results = check_fs_note_matches(FullReport("s.html", "Co", [bs], [note]), tolerance=0)

    intangible = [r for r in results if r.check_id.startswith("fs_note:intangible_assets")]
    assert intangible and intangible[0].actual == 3657186453
    assert intangible[0].status == "matched"
    assert any("기말금액" in evidence.label for evidence in intangible[0].evidence)


def test_fs_note_intangible_bare_closing_total_wins_over_development_cost_subline():
    bs = _section(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "당기"], ["무형자산", "4,540,627"]],
            "재무상태표",
            SourceLocation("statement:bs", 0, 0),
        ),
    )
    note = _section(
        "note:15",
        "무형자산",
        "note",
        "15",
        ReportTable(
            1,
            [
                ["구분", "당기"],
                ["자산화된 연구개발비 장부금액", "22,301"],
                ["기말", "4,540,627"],
            ],
            "15. 무형자산",
            SourceLocation("note:15", 0, 1),
        ),
    )

    results = check_fs_note_matches(FullReport("s.html", "Co", [bs], [note]), tolerance=0)

    intangible = [r for r in results if r.check_id.startswith("fs_note:intangible_assets")]
    assert intangible and intangible[0].actual == 4540627
    assert intangible[0].status == "matched"
    assert any("기말" in evidence.label for evidence in intangible[0].evidence)


def test_fs_note_lease_level_split_matches_current_and_noncurrent():
    bs = _lease_statement(
        [
            ["구분", "당기"],
            ["유동부채", ""],
            ["리스부채", "100"],
            ["비유동부채", ""],
            ["리스부채", "300"],
        ]
    )
    note = _lease_note(
        "리스부채",
        "17",
        [
            _lease_note_table(
                1,
                [
                    ["구분", "당기"],
                    ["유동 리스부채", "100"],
                    ["비유동 리스부채", "300"],
                ],
            )
        ],
    )

    results = _lease_results(FullReport("s.html", "Co", [bs], [note]))

    assert _lease_status_by_suffix(results) == {
        "current": "matched",
        "noncurrent": "matched",
    }
    assert {result.expected for result in results} == {100, 300}
    assert {result.actual for result in results} == {100, 300}


def test_fs_note_lease_total_only_matches_bounded_current_noncurrent_sum():
    bs = _lease_statement(
        [
            ["구분", "당기"],
            ["유동 리스부채", "100"],
            ["비유동 리스부채", "300"],
        ]
    )
    note = _lease_note(
        "리스부채",
        "17",
        [_lease_note_table(1, [["구분", "당기"], ["기말", "400"]])],
    )

    results = _lease_results(FullReport("s.html", "Co", [bs], [note]))

    assert len(results) == 1
    assert results[0].check_id == "fs_note:lease_liabilities:17:total"
    assert results[0].status == "matched"
    assert results[0].expected == 400
    assert results[0].actual == 400


def test_fs_note_lease_noncurrent_only_matches_noncurrent_and_abstains_current_reclass():
    bs = _lease_statement(
        [
            ["구분", "당기"],
            ["유동 리스부채", "100"],
            ["비유동 리스부채", "900"],
        ]
    )
    note = _lease_note(
        "리스부채",
        "17",
        [
            _lease_note_table(
                1,
                [
                    ["구분", "당기"],
                    ["유동성대체부분", "-100"],
                    ["비유동 리스부채", "900"],
                ],
            )
        ],
    )

    results = _lease_results(FullReport("s.html", "Co", [bs], [note]))

    assert _lease_status_by_suffix(results) == {
        "current": "not_tested",
        "noncurrent": "matched",
    }
    assert [result.actual for result in results if result.check_id.endswith(":noncurrent")] == [900]
    assert not any(result.actual == -100 for result in results)


def test_fs_note_lease_multi_table_selects_current_year_first_table():
    # 당기·전기 롤포워드를 별도 표로 싣는 흔한 패턴(CJ 표129[당기]/표130[전기];
    # NAVER 표111[당기]/표112[전기]). 문서상 먼저 오는 표(=당기, 낮은 table.index)만
    # 채택하고 전기 표는 무시한다. 답(FS)을 보고 표를 고르지 않는 결정론적 신호.
    bs = _lease_statement(
        [
            ["구분", "당기"],
            ["유동 리스부채", "100"],
            ["비유동 리스부채", "300"],
        ]
    )
    note = _lease_note(
        "리스부채",
        "17",
        [
            _lease_note_table(
                1,
                [["구분", "당기"], ["유동 리스부채", "100"], ["비유동 리스부채", "300"]],
            ),
            _lease_note_table(
                2,
                [["구분", "당기"], ["유동 리스부채", "120"], ["비유동 리스부채", "340"]],
            ),
        ],
    )

    results = _lease_results(FullReport("s.html", "Co", [bs], [note]))

    # 당기 표(table 1, 100/300)로 레벨 매칭; 전기 표(table 2, 120/340)는 채택 안 됨.
    assert _lease_status_by_suffix(results) == {
        "current": "matched",
        "noncurrent": "matched",
    }
    matched_actuals = {result.actual for result in results if result.status == "matched"}
    assert matched_actuals == {100, 300}
    assert 120 not in matched_actuals and 340 not in matched_actuals


def test_fs_note_lease_bare_aggregate_in_asset_titled_note_not_matched_as_total():
    # Code-review BLOCKER: 결합 주석 "리스 및 사용권자산"의 무맥락 '합계'(자산측 소계)가
    # FS 합산(100+300=400)과 우연히 일치해도 리스부채 total로 승격되면 안 된다(거짓 매치).
    # note 제목이 순수 리스부채 맥락(리스 포함·사용권자산/자산 불포함)이 아니면 total 거부.
    bs = _lease_statement(
        [["구분", "당기"], ["유동 리스부채", "100"], ["비유동 리스부채", "300"]]
    )
    note = _lease_note(
        "리스 및 사용권자산",
        "17",
        [
            _lease_note_table(
                1,
                [["구분", "당기"], ["합계", "400"]],
                heading="17. 리스 및 사용권자산",
            )
        ],
    )

    results = _lease_results(FullReport("s.html", "Co", [bs], [note]))

    assert not any(result.status == "matched" for result in results), [
        (r.check_id, r.status, r.actual) for r in results
    ]


def test_fs_note_lease_prior_year_only_table_not_matched_as_current():
    # Code-review MAJOR-1: 전기(prior)-only 표(당기 헤더 없음)는 건너뛴다. 안 그러면
    # row_amount_prefer_current가 최우측(=전기) 열을 잡아 리스가 YoY flat일 때 틀린
    # 기간으로 거짓 매치가 날 수 있다(전기 100/300 == FS 100/300).
    bs = _lease_statement(
        [["구분", "당기"], ["유동 리스부채", "100"], ["비유동 리스부채", "300"]]
    )
    note = _lease_note(
        "리스부채",
        "17",
        [
            _lease_note_table(
                1,
                [["구분", "전기"], ["유동 리스부채", "100"], ["비유동 리스부채", "300"]],
            )
        ],
    )

    results = _lease_results(FullReport("s.html", "Co", [bs], [note]))

    assert not any(result.status == "matched" for result in results), [
        (r.check_id, r.status, r.actual) for r in results
    ]


def test_fs_note_lease_mixed_consolidated_and_unscoped_basis_abstains():
    # Code-review MAJOR-2: 연결 + 미식별("") scope가 한 슬라이스에 섞이면(별도 없어
    # split 안 됨) 연결 유동 + 미식별 비유동이 합산/페어링돼 거짓 매치가 날 수 있다 →
    # 혼재 시 abstain(미식별 scope도 distinct basis로 카운트).
    bs_consolidated = _lease_statement(
        [["구분", "당기"], ["유동 리스부채", "100"]],
        scope="consolidated",
        section_id="statement:bs1",
        table_index=0,
    )
    bs_unscoped = _lease_statement(
        [["구분", "당기"], ["비유동 리스부채", "300"]],
        scope="",
        section_id="statement:bs2",
        table_index=1,
    )
    note = _lease_note(
        "리스부채",
        "17",
        [
            _lease_note_table(
                1,
                [["구분", "당기"], ["유동 리스부채", "100"], ["비유동 리스부채", "300"]],
            )
        ],
    )

    results = _lease_results(
        FullReport("s.html", "Co", [bs_consolidated, bs_unscoped], [note])
    )

    assert not any(result.status == "matched" for result in results), [
        (r.check_id, r.status, r.actual) for r in results
    ]


def test_fs_note_lease_row_label_isolation_rejects_asset_inventory_receivable_contamination():
    bs = _lease_statement(
        [
            ["구분", "당기"],
            ["유동 리스부채", "100"],
            ["비유동 리스부채", "300"],
        ]
    )
    note = _lease_note(
        "리스 및 사용권자산",
        "17",
        [
            _lease_note_table(
                1,
                [
                    ["구분", "당기"],
                    ["기말 사용권자산", "999"],
                    ["기말 재고자산", "888"],
                    ["유동 리스채권", "777"],
                    ["유동 리스부채", "100"],
                    ["비유동 리스부채", "300"],
                ],
            )
        ],
    )

    results = _lease_results(FullReport("s.html", "Co", [bs], [note]))

    assert _lease_status_by_suffix(results) == {
        "current": "matched",
        "noncurrent": "matched",
    }
    evidence_text = " ".join(evidence.label for result in results for evidence in result.evidence)
    assert "기말 사용권자산" not in evidence_text
    assert "기말 재고자산" not in evidence_text
    assert "유동 리스채권" not in evidence_text


def test_fs_note_lease_rows_survive_asset_titled_note():
    bs = _lease_statement(
        [
            ["구분", "당기"],
            ["유동 리스부채", "100"],
            ["비유동 리스부채", "300"],
        ]
    )
    note = _lease_note(
        "리스 및 사용권자산",
        "17",
        [
            _lease_note_table(
                1,
                [["구분", "당기"], ["유동 리스부채", "100"], ["비유동 리스부채", "300"]],
            )
        ],
    )

    results = _lease_results(FullReport("s.html", "Co", [bs], [note]))

    assert _lease_status_by_suffix(results) == {
        "current": "matched",
        "noncurrent": "matched",
    }


def test_fs_note_lease_exactly_two_guard_abstains_when_filtered_levels_are_not_one_each():
    bs = _lease_statement(
        [
            ["구분", "당기"],
            ["유동 리스부채", "100"],
            ["비유동 리스부채", "300"],
            ["장기 리스부채", "400"],
        ]
    )
    note = _lease_note(
        "리스부채",
        "17",
        [_lease_note_table(1, [["구분", "당기"], ["기말", "400"]])],
    )

    results = _lease_results(FullReport("s.html", "Co", [bs], [note]))

    assert _lease_status_by_suffix(results) == {"total": "not_tested"}
    assert not any(result.expected in {400, 500, 800} and result.status == "matched" for result in results)


def test_fs_note_lease_total_sum_never_mixes_bases():
    consolidated_bs = _lease_statement(
        [["구분", "당기"], ["유동 리스부채", "100"], ["비유동 리스부채", "300"]],
        scope="consolidated",
        table_index=0,
        section_id="statement:bs:consolidated",
    )
    separate_bs = _lease_statement(
        [["구분", "당기"], ["유동 리스부채", "10"], ["비유동 리스부채", "30"]],
        scope="separate",
        table_index=1,
        section_id="statement:bs:separate",
    )
    consolidated_note = _lease_note(
        "리스부채",
        "17",
        [_lease_note_table(2, [["구분", "당기"], ["기말", "400"]])],
        scope="consolidated",
        section_id="note:17:consolidated",
    )
    separate_note = _lease_note(
        "리스부채",
        "17",
        [_lease_note_table(3, [["구분", "당기"], ["기말", "40"]])],
        scope="separate",
        section_id="note:17:separate",
    )

    results = _lease_results(
        FullReport(
            "s.html",
            "Co",
            [consolidated_bs, separate_bs],
            [consolidated_note, separate_note],
        )
    )

    assert results
    assert {result.status for result in results} == {"not_tested"}
    assert not any(result.expected == 440 or result.actual == 440 for result in results)


def test_fs_note_lease_total_sum_uses_accumulated_display_tolerance_boundary():
    within_bs = _lease_statement(
        [
            ["구분", "당기"],
            ["유동 리스부채", "1,000,001"],
            ["비유동 리스부채", "2,001,001"],
        ]
    )
    outside_bs = _lease_statement(
        [
            ["구분", "당기"],
            ["유동 리스부채", "1,000,001"],
            ["비유동 리스부채", "2,001,000"],
        ]
    )
    note = _lease_note(
        "리스부채",
        "17",
        [
            _lease_note_table(
                1,
                [["구분", "당기"], ["기말", "3,003"]],
                unit_multiplier=1_000,
            )
        ],
    )

    within = _lease_results(FullReport("s.html", "Co", [within_bs], [note]), tolerance=1)
    outside = _lease_results(FullReport("s.html", "Co", [outside_bs], [note]), tolerance=1)

    assert _lease_status_by_suffix(within) == {"total": "matched"}
    assert within[0].difference == 1_998
    assert within[0].tolerance == 1_998
    assert _lease_status_by_suffix(outside) == {"total": "unexplained_gap"}
    assert outside[0].difference == 1_999
    assert outside[0].tolerance == 1_998


def test_fs_note_lease_liability_rejects_receivable_row():
    bs = _section(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "당기"], ["유동 리스부채", "208,497"]],
            "재무상태표",
            SourceLocation("statement:bs", 0, 0),
        ),
    )
    note = _section(
        "note:17",
        "리스",
        "note",
        "17",
        ReportTable(
            1,
            [["구분", "당기"], ["유동 리스채권", "52,394"], ["유동 리스부채", "208,497"]],
            "17. 리스",
            SourceLocation("note:17", 0, 1),
        ),
    )

    results = check_fs_note_matches(FullReport("s.html", "Co", [bs], [note]), tolerance=0)

    lease = [r for r in results if r.check_id.startswith("fs_note:lease_liabilities")]
    assert lease and lease[0].actual == 208497
    assert lease[0].status == "matched"
    assert any("리스부채" in evidence.label for evidence in lease[0].evidence)
    assert not any("리스채권" in evidence.label for evidence in lease[0].evidence)


def test_fs_note_rejects_non_amount_quantity_field_label():
    bs = _section(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "당기"], ["무형자산", "1,000"]],
            "재무상태표",
            SourceLocation("statement:bs", 0, 0),
        ),
    )
    note = _section(
        "note:16",
        "무형자산",
        "note",
        "16",
        ReportTable(
            1,
            [["구분", "당기"], ["기말 배출권 수량", "605,000"]],
            "16. 무형자산",
            SourceLocation("note:16", 0, 1),
        ),
    )

    results = check_fs_note_matches(FullReport("s.html", "Co", [bs], [note]), tolerance=0)

    intangible = [r for r in results if r.check_id.startswith("fs_note:intangible_assets")]
    assert not intangible, [(r.actual, r.status) for r in intangible]


def test_fs_note_eps_abstains_when_statement_amount_is_implausible_per_share():
    statement = _section(
        "statement:pl",
        "포괄손익계산서",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "당기"], ["보통주 기본주당이익 (단위 : 원)", "92,440,000"]],
            "포괄손익계산서",
            SourceLocation("statement:pl", 0, 0),
        ),
    )
    note = _section(
        "note:30",
        "주당이익",
        "note",
        "30",
        ReportTable(
            1,
            [["구분", "당기"], ["기본주당이익(손실)", "9,294"]],
            "30. 주당이익 (단위 : 원)",
            SourceLocation("note:30", 0, 1),
        ),
    )

    results = check_fs_note_matches(FullReport("s.html", "Co", [statement], [note]), tolerance=1)

    eps = [r for r in results if r.check_id.startswith("fs_note:earnings_per_share")]
    assert not eps, [(r.actual, r.status) for r in eps]


def test_fs_note_eps_abstains_when_note_amount_is_implausible_per_share():
    statement = _section(
        "statement:pl",
        "포괄손익계산서",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "당기"], ["보통주 기본주당이익 (단위 : 원)", "9,294"]],
            "포괄손익계산서",
            SourceLocation("statement:pl", 0, 0),
        ),
    )
    note = _section(
        "note:30",
        "주당이익",
        "note",
        "30",
        ReportTable(
            1,
            [["구분", "당기"], ["기본주당이익(손실)", "92,440,000"]],
            "30. 주당이익 (단위 : 원)",
            SourceLocation("note:30", 0, 1),
        ),
    )

    results = check_fs_note_matches(FullReport("s.html", "Co", [statement], [note]), tolerance=1)

    eps = [r for r in results if r.check_id.startswith("fs_note:earnings_per_share")]
    assert not eps, [(r.actual, r.status) for r in eps]
