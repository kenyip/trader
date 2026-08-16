from scripts.trader_pack_monday_rehearsal import DOOR_STEMS, DOOR_NAMES

from tests.test_pack_grade_paper_consumption import BU4, BU6


def test_door_stems_are_first_live_pcs_cells():
    assert DOOR_STEMS[0] == BU4
    assert DOOR_STEMS[1] == BU6
    assert DOOR_NAMES[BU4] == "bu_4"
    assert DOOR_NAMES[BU6] == "bu_6"
