"""Display-precision tolerance for statement-to-note amount comparison."""

from dart_footing_reconciler.amount_compare import amounts_agree, display_unit_tolerance


def test_display_unit_tolerance_default_preserves_thousand_won_behavior():
    # 기본(천원 단위 주석): 1M 이상 금액에서 999원 미만 차이는 표시 정밀도.
    assert display_unit_tolerance(2_000_000, 2_000_500, 1) == 999
    assert amounts_agree(2_000_000, 2_000_500, 1)
    assert not amounts_agree(2_000_000, 2_001_500, 1)
    # 1M 미만 소액에는 적용하지 않는다.
    assert display_unit_tolerance(900_000, 900_500, 1) == 1


def test_display_unit_tolerance_million_won_note_rounding():
    # 한화오션 type: FS는 원, 주석은 백만원. 1 백만 미만 반올림 차이는 gap이 아니다.
    fs = 4_648_353_653_506
    note = 4_648_354_000_000  # 4,648,354 백만
    assert not amounts_agree(fs, note, 1)  # 기본(천원) tolerance로는 gap
    assert amounts_agree(fs, note, 1, display_unit=1_000_000)  # 주석 표시단위 인식 시 match
    assert display_unit_tolerance(fs, note, 1, display_unit=1_000_000) >= abs(note - fs)


def test_display_unit_tolerance_preserves_eps_gap():
    # 삼성SDI EPS 8,961 vs 8,138: 소액(원/주) genuine gap은 표시단위 인식과 무관하게 보존.
    assert not amounts_agree(8961, 8138, 1, display_unit=1)
    assert not amounts_agree(8961, 8138, 1)
    # display_unit이 커도 금액이 materiality gate 미만이면 base tolerance만 적용.
    assert not amounts_agree(8961, 8138, 1, display_unit=1_000_000)


def test_display_unit_tolerance_million_unit_gate_blocks_small_balances():
    # 백만 단위라도 balance가 gate(1000 × display_unit) 미만이면 loose tolerance 미적용.
    assert display_unit_tolerance(5_000_000, 5_400_000, 1, display_unit=1_000_000) == 1
    # gate 이상이면 적용.
    assert display_unit_tolerance(2_000_000_000, 2_000_500_000, 1, display_unit=1_000_000) == 999_999
