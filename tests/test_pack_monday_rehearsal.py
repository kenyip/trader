from scripts.trader_pack_monday_rehearsal import DOOR_STEMS, DOOR_NAMES

from tests.test_pack_grade_paper_consumption import BU4, BU6
from trader_platform.research.pack_grade import (
    first_live_door_rank,
    is_first_live_door,
)


def test_door_stems_are_first_live_pcs_cells():
    assert DOOR_STEMS[0] == BU4
    assert DOOR_STEMS[1] == BU6
    assert DOOR_NAMES[BU4] == "bu_4"
    assert DOOR_NAMES[BU6] == "bu_6"
    assert is_first_live_door(candidate_id=BU4, symbol="KO")
    assert is_first_live_door(candidate_id=BU6, symbol="PLTR")
    assert not is_first_live_door(candidate_id=BU4, symbol="INTC")
    assert not is_first_live_door(candidate_id=BU4, symbol="AMZN")
    assert first_live_door_rank(candidate_id=BU4, symbol="KO") < first_live_door_rank(
        candidate_id=BU6, symbol="PLTR"
    )
