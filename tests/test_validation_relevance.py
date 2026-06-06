from dart_footing_reconciler.validation_relevance import classify_validation_relevance


def test_classifies_general_note_table_as_non_validation_relevant():
    result = classify_validation_relevance(
        title="일반사항",
        headers=("구분", "내용"),
        row_labels=("회사",),
    )

    assert result.validation_relevant is False
    assert result.key == "non_validation_note_table"


def test_classifies_unknown_asset_rollforward_shape_as_validation_relevant():
    result = classify_validation_relevance(
        title="유형자산",
        headers=("구분", "내용"),
        row_labels=("취득", "기말장부금액"),
    )

    assert result.validation_relevant is True
    assert result.key == "asset_rollforward_candidate"
    assert "asset movement topic" in result.evidence


def test_classifies_cashflow_bridge_shape_as_validation_relevant():
    result = classify_validation_relevance(
        title="현금흐름 관련 주석",
        headers=("구분", "당기"),
        row_labels=("차입", "상환"),
    )

    assert result.validation_relevant is True
    assert result.key == "cashflow_bridge_candidate"


def test_classifies_asset_depreciation_functional_table_as_expense_allocation():
    result = classify_validation_relevance(
        title="유형자산",
        headers=("", "매출원가", "판매비와 일반관리비", "기능별 항목 합계"),
        row_labels=("감가상각비, 유형자산",),
    )

    assert result.validation_relevant is True
    assert result.key == "expense_allocation_candidate"


def test_classifies_asset_purchase_commitment_as_non_validation_note_table():
    result = classify_validation_relevance(
        title="유형자산",
        headers=("", "공시금액"),
        row_labels=("유형자산을 취득하기 위한 약정액",),
    )

    assert result.validation_relevant is False
    assert result.key == "non_validation_note_table"


def test_classifies_asset_collateral_table_as_non_validation_note_table():
    result = classify_validation_relevance(
        title="담보제공자산",
        headers=("구분", "담보제공자산", "장부금액", "담보설정금액", "관련 계정과목"),
        row_labels=("투자부동산",),
    )

    assert result.validation_relevant is False
    assert result.key == "non_validation_note_table"


def test_classifies_related_party_asset_rows_as_non_validation_note_table():
    result = classify_validation_relevance(
        title="특수관계자와의 거래",
        headers=("", "전체 특수관계자"),
        row_labels=("", "", "", "기말 사용권자산", "기말 리스부채", "리스료 지급", "리스 이자비용"),
    )

    assert result.validation_relevant is False
    assert result.key == "non_validation_note_table"


def test_classifies_accounting_policy_useful_life_table_as_non_validation_note_table():
    result = classify_validation_relevance(
        title="중요한 회계정책",
        headers=("구분", "추정내용연수", "상각방법"),
        row_labels=("개발비", "산업재산권", "기타의무형자산"),
    )

    assert result.validation_relevant is False
    assert result.key == "non_validation_note_table"


def test_classifies_investment_property_restriction_table_as_non_validation_note_table():
    result = classify_validation_relevance(
        title="투자부동산",
        headers=("", "취득 완료 투자부동산"),
        row_labels=(
            "투자부동산의 실현가능성 또는 임대수익과 처분대금의 송금에 대한 제약에 대한 설명",
            "투자부동산의 실현가능성에 대한 또는 임대수익과 처분대금의 송금에 대한 제약",
        ),
    )

    assert result.validation_relevant is False
    assert result.key == "non_validation_note_table"
