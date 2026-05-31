from dart_footing_reconciler.dart_fetch import financial_section_params, viewer_url


def test_financial_section_params_extracts_dart_tree_node():
    html = """
    var node1 = {};
    node1['text'] = "III. 재무에 관한 사항";
    node1['id'] = "17";
    node1['rcpNo'] = "20250320001493";
    node1['dcmNo'] = "10440036";
    node1['eleId'] = "17";
    node1['offset'] = "203161";
    node1['length'] = "3002954";
    node1['dtd'] = "dart4.xsd";
    """

    params = financial_section_params(html)

    assert params.rcp_no == "20250320001493"
    assert params.dcm_no == "10440036"
    assert params.ele_id == "17"
    assert "rcpNo=20250320001493" in viewer_url(params)
    assert "dtd=dart4.xsd" in viewer_url(params)
