from dart_footing_reconciler.checks import MATCHED, UNEXPLAINED_GAP, PARSE_UNCERTAIN
from dart_footing_reconciler.checks_statement_ties import check_statement_ties
from dart_footing_reconciler.document import (
    FullReport, ReportBlock, ReportSection, ReportTable, SourceLocation,
)


def _stmt(section_id: str, title: str, rows: list[list[str]]) -> ReportSection:
    table = ReportTable(0, rows, title, SourceLocation(section_id, 0, 0))
    return ReportSection(
        section_id, title, "statement", "",
        [ReportBlock("table", "", table, table.location)],
    )


def _report(statements: list[ReportSection]) -> FullReport:
    return FullReport("sample.html", "테스트", statements, [])


def test_bs_equation_matched():
    bs = _stmt(
        "statement:재무상태표",
        "재무상태표",
        [
            ["구분", "당기"],
            ["자산총계", "1,000"],
            ["부채총계", "600"],
            ["자본총계", "400"],
        ],
    )
    results = check_statement_ties(_report([bs]))
    eq = [r for r in results if r.check_type == "statement_bs_equation"]
    assert len(eq) == 1
    assert eq[0].status == MATCHED
    assert eq[0].expected == 1000
    assert eq[0].actual == 1000


def test_bs_equation_gap():
    bs = _stmt(
        "statement:재무상태표",
        "재무상태표",
        [
            ["구분", "당기"],
            ["자산총계", "1,000"],
            ["부채총계", "600"],
            ["자본총계", "500"],
        ],
    )
    results = check_statement_ties(_report([bs]))
    eq = [r for r in results if r.check_type == "statement_bs_equation"]
    assert eq[0].status == UNEXPLAINED_GAP


def test_bs_equation_alias_자본과부채총계():
    bs = _stmt(
        "statement:재무상태표",
        "재무상태표",
        [
            ["구분", "당기"],
            ["부채총계", "600"],
            ["자본총계", "400"],
            ["자본과부채총계", "1,000"],
        ],
    )
    results = check_statement_ties(_report([bs]))
    eq = [r for r in results if r.check_type == "statement_bs_equation"]
    assert len(eq) == 1
    assert eq[0].status == MATCHED


def test_bs_equation_missing_부채총계_returns_parse_uncertain():
    bs = _stmt(
        "statement:재무상태표",
        "재무상태표",
        [
            ["구분", "당기"],
            ["자본총계", "400"],
            ["자본과부채총계", "1,000"],
        ],
    )
    results = check_statement_ties(_report([bs]))
    eq = [r for r in results if r.check_type == "statement_bs_equation"]
    assert len(eq) == 1
    assert eq[0].status == PARSE_UNCERTAIN


def test_cash_tie_matched():
    bs = _stmt(
        "statement:재무상태표",
        "재무상태표",
        [
            ["구분", "당기"],
            ["자산총계", "1,000"],
            ["부채총계", "500"],
            ["자본총계", "500"],
            ["현금및현금성자산", "500,000"],
        ],
    )
    cf = _stmt(
        "statement:현금흐름표",
        "현금흐름표",
        [
            ["구분", "당기"],
            ["기말현금및현금성자산", "500,000"],
        ],
    )
    results = check_statement_ties(_report([bs, cf]))
    cash = [r for r in results if r.check_type == "statement_cash_tie"]
    assert len(cash) == 1
    assert cash[0].status == MATCHED


def test_cash_tie_gap():
    bs = _stmt(
        "statement:재무상태표",
        "재무상태표",
        [
            ["구분", "당기"],
            ["현금및현금성자산", "500,000"],
        ],
    )
    cf = _stmt(
        "statement:현금흐름표",
        "현금흐름표",
        [
            ["구분", "당기"],
            ["기말현금및현금성자산", "499,000"],
        ],
    )
    results = check_statement_ties(_report([bs, cf]))
    cash = [r for r in results if r.check_type == "statement_cash_tie"]
    assert len(cash) == 1
    assert cash[0].status == UNEXPLAINED_GAP


def test_cash_tie_no_cf_returns_empty_not_uncertain():
    bs = _stmt(
        "statement:재무상태표",
        "재무상태표",
        [
            ["구분", "당기"],
            ["현금및현금성자산", "500,000"],
        ],
    )
    results = check_statement_ties(_report([bs]))
    cash = [r for r in results if r.check_type == "statement_cash_tie"]
    assert cash == []


def test_equity_tie_matched():
    bs = _stmt(
        "statement:재무상태표",
        "재무상태표",
        [
            ["구분", "당기"],
            ["자본총계", "1,000,000"],
        ],
    )
    sce = _stmt(
        "statement:자본변동표",
        "자본변동표",
        [
            ["구분", "당기"],
            ["자본총계", "1,000,000"],
        ],
    )
    results = check_statement_ties(_report([bs, sce]))
    eq = [r for r in results if r.check_type == "statement_equity_tie"]
    assert len(eq) == 1
    assert eq[0].status == MATCHED


def test_equity_tie_gap():
    bs = _stmt(
        "statement:재무상태표",
        "재무상태표",
        [
            ["구분", "당기"],
            ["자본총계", "1,000,000"],
        ],
    )
    sce = _stmt(
        "statement:자본변동표",
        "자본변동표",
        [
            ["구분", "당기"],
            ["자본총계", "999,000"],
        ],
    )
    results = check_statement_ties(_report([bs, sce]))
    eq = [r for r in results if r.check_type == "statement_equity_tie"]
    assert len(eq) == 1
    assert eq[0].status == UNEXPLAINED_GAP


def test_equity_tie_sce_matrix_picks_total_column():
    """SCE 기말 행이 매트릭스(자본금…자본총계)이고 헤더가 퇴화('자본' 반복)일 때,
    첫 컬럼(자본금)이 아니라 마지막 자본총계 컬럼을 BS와 대사해야 한다.
    (현대모비스 type 버그: 첫 셀 fallback이 491,096 자본금을 집어 45.6조 false gap 발생.)"""
    bs = _stmt(
        "statement:재무상태표",
        "재무상태표",
        [
            ["구분", "당기"],
            ["자본총계", "46,118,232"],
        ],
    )
    sce = _stmt(
        "statement:자본변동표",
        "자본변동표",
        [
            ["", "자본", "자본", "자본", "자본"],  # degenerate merged header
            ["2024.12.31 (기말자본)", "491,096", "1,367,293", "42,911,192", "46,118,232"],
        ],
    )
    results = check_statement_ties(_report([bs, sce]))
    eq = [r for r in results if r.check_type == "statement_equity_tie"]
    assert len(eq) == 1
    assert eq[0].status == MATCHED
    assert eq[0].actual == 46_118_232  # BS 자본총계
    assert eq[0].expected == 46_118_232  # SCE 기말 자본총계 (마지막 컬럼, 자본금 아님)


def _stmt_multiplier(section_id: str, title: str, rows: list[list[str]], unit_multiplier: int) -> ReportSection:
    table = ReportTable(0, rows, title, SourceLocation(section_id, 0, 0), unit_multiplier=unit_multiplier)
    return ReportSection(
        section_id, title, "statement", "",
        [ReportBlock("table", "", table, table.location)],
    )


def test_bs_equation_unit_multiplier():
    """unit_multiplier=1000 が正しく適用されること: 생(raw)값 1000/600/400 → 실값 1_000_000/600_000/400_000."""
    bs = _stmt_multiplier(
        "statement:재무상태표",
        "재무상태표",
        [
            ["구분", "당기"],
            ["자산총계", "1,000"],
            ["부채총계", "600"],
            ["자본총계", "400"],
        ],
        unit_multiplier=1000,
    )
    results = check_statement_ties(_report([bs]))
    eq = [r for r in results if r.check_type == "statement_bs_equation"]
    assert len(eq) == 1
    assert eq[0].status == MATCHED
    assert eq[0].actual == 1_000_000
    assert eq[0].expected == 1_000_000


def test_equity_tie_sce_last_row_wins():
    """_find_sce_equity_end_row은 마지막 자본총계 행(기말잔액)을 선택해야 한다."""
    bs = _stmt(
        "statement:재무상태표",
        "재무상태표",
        [
            ["구분", "당기"],
            ["자본총계", "1,000,000"],
        ],
    )
    sce = _stmt(
        "statement:자본변동표",
        "자본변동표",
        [
            ["구분", "당기"],
            ["자본총계", "800,000"],   # 기초잔액 — 무시돼야 함
            ["자본총계", "1,000,000"],  # 기말잔액 — 이 행이 선택돼야 함
        ],
    )
    results = check_statement_ties(_report([bs, sce]))
    eq = [r for r in results if r.check_type == "statement_equity_tie"]
    assert len(eq) == 1
    assert eq[0].status == MATCHED


# ---------------------------------------------------------------------------
# Edge-case / gap tests (Task 2 additions)
# ---------------------------------------------------------------------------


def test_bs_no_bs_section_returns_empty():
    """statements에 재무상태표 없이 현금흐름표만 있으면 [] 반환 (PARSE_UNCERTAIN 아님)."""
    cf = _stmt(
        "statement:현금흐름표",
        "현금흐름표",
        [
            ["구분", "당기"],
            ["기말현금및현금성자산", "300,000"],
        ],
    )
    results = check_statement_ties(_report([cf]))
    assert results == []


def test_bs_equation_zero_equity():
    """자본총계=0: 방정식 500_000 = 500_000 + 0 → MATCHED."""
    bs = _stmt(
        "statement:재무상태표",
        "재무상태표",
        [
            ["구분", "당기"],
            ["자산총계", "500,000"],
            ["부채총계", "500,000"],
            ["자본총계", "0"],
        ],
    )
    results = check_statement_ties(_report([bs]))
    eq = [r for r in results if r.check_type == "statement_bs_equation"]
    assert len(eq) == 1
    assert eq[0].status == MATCHED
    assert eq[0].actual == 500_000
    assert eq[0].expected == 500_000


def test_bs_equation_tolerance_boundary():
    """차이가 정확히 tolerance=1이면 MATCHED (경계 포함)."""
    bs = _stmt(
        "statement:재무상태표",
        "재무상태표",
        [
            ["구분", "당기"],
            ["자산총계", "1,000,001"],
            ["부채총계", "600,000"],
            ["자본총계", "400,000"],
        ],
    )
    results = check_statement_ties(_report([bs]))
    eq = [r for r in results if r.check_type == "statement_bs_equation"]
    assert len(eq) == 1
    assert eq[0].status == MATCHED


def test_bs_equation_beyond_tolerance():
    """차이가 tolerance=1 초과(차이=2)이면 UNEXPLAINED_GAP."""
    bs = _stmt(
        "statement:재무상태표",
        "재무상태표",
        [
            ["구분", "당기"],
            ["자산총계", "1,000,002"],
            ["부채총계", "600,000"],
            ["자본총계", "400,000"],
        ],
    )
    results = check_statement_ties(_report([bs]))
    eq = [r for r in results if r.check_type == "statement_bs_equation"]
    assert len(eq) == 1
    assert eq[0].status == UNEXPLAINED_GAP


def test_cash_tie_missing_label_returns_empty():
    """BS 섹션에 _CASH_BS_LABELS 매칭 행이 없으면 statement_cash_tie 결과 없음."""
    bs = _stmt(
        "statement:재무상태표",
        "재무상태표",
        [
            ["구분", "당기"],
            ["자산총계", "1,000"],
            ["부채총계", "600"],
            ["자본총계", "400"],
            # 현금 관련 행 없음
        ],
    )
    cf = _stmt(
        "statement:현금흐름표",
        "현금흐름표",
        [
            ["구분", "당기"],
            ["기말현금및현금성자산", "300,000"],
        ],
    )
    results = check_statement_ties(_report([bs, cf]))
    cash = [r for r in results if r.check_type == "statement_cash_tie"]
    assert cash == []


def test_cash_tie_both_sections_missing():
    """BS도 CF도 없는 경우(PL만 존재) → statement_cash_tie 결과 없음, 전체 결과 []."""
    pl = _stmt(
        "statement:손익계산서",
        "손익계산서",
        [
            ["구분", "당기"],
            ["매출액", "5,000,000"],
            ["당기순이익", "500,000"],
        ],
    )
    results = check_statement_ties(_report([pl]))
    assert results == []
    cash = [r for r in results if r.check_type == "statement_cash_tie"]
    assert cash == []


def test_all_three_checks_run_together():
    """BS + CF + SCE 세 섹션 모두 정합 시 세 개의 MATCHED 결과를 한 번에 반환."""
    bs = _stmt(
        "statement:재무상태표",
        "재무상태표",
        [
            ["구분", "당기"],
            ["자산총계", "2,000,000"],
            ["부채총계", "1,200,000"],
            ["자본총계", "800,000"],
            ["현금및현금성자산", "300,000"],
        ],
    )
    cf = _stmt(
        "statement:현금흐름표",
        "현금흐름표",
        [
            ["구분", "당기"],
            ["기말현금및현금성자산", "300,000"],
        ],
    )
    sce = _stmt(
        "statement:자본변동표",
        "자본변동표",
        [
            ["구분", "당기"],
            ["자본총계", "800,000"],
        ],
    )
    results = check_statement_ties(_report([bs, cf, sce]))

    assert len(results) == 3
    check_types = {r.check_type for r in results}
    assert check_types == {"statement_bs_equation", "statement_cash_tie", "statement_equity_tie"}
    for r in results:
        assert r.status == MATCHED, f"{r.check_type} expected MATCHED but got {r.status}"


def test_bs_equation_variant_label_순자산총계():
    """'순자산총계' is not in the old frozenset but LabelResolver CONTAINS should catch it."""
    bs = _stmt(
        "statement:재무상태표",
        "재무상태표",
        [
            ["구분", "당기"],
            ["자산총계", "1,000"],
            ["부채총계", "600"],
            ["순자산총계", "400"],     # variant for 자본총계
        ],
    )
    results = check_statement_ties(_report([bs]))
    eq = [r for r in results if r.check_type == "statement_bs_equation"]
    assert len(eq) == 1
    assert eq[0].status != PARSE_UNCERTAIN


def test_bs_equation_parse_uncertain_reason_when_row_missing():
    """When no row found at all, parse_uncertain_reason should be LABEL_NOT_FOUND."""
    from dart_footing_reconciler.label_resolver import LABEL_NOT_FOUND
    bs = _stmt(
        "statement:재무상태표",
        "재무상태표",
        [
            ["구분", "당기"],
            ["매출채권", "300"],     # no total rows at all
        ],
    )
    results = check_statement_ties(_report([bs]))
    eq = [r for r in results if r.check_type == "statement_bs_equation"]
    assert len(eq) == 1
    assert eq[0].status == PARSE_UNCERTAIN
    assert eq[0].parse_uncertain_reason == LABEL_NOT_FOUND
