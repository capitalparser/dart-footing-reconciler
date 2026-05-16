from dart_footing_reconciler.amounts import parse_amount


def test_parse_amount_handles_korean_report_number_formats() -> None:
    assert parse_amount("1,234") == 1234
    assert parse_amount("(1,234)") == -1234
    assert parse_amount("△1,234") == -1234
    assert parse_amount("-") is None
    assert parse_amount("") is None


def test_parse_amount_ignores_unit_annotations() -> None:
    assert parse_amount("1,234천원") == 1234
    assert parse_amount("  ( 9,876 ) ") == -9876
