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
