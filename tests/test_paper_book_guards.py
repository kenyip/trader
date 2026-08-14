"""Paper book place guards: one-open-per-symbol + max_concurrent=2."""

from __future__ import annotations

import tempfile
from pathlib import Path

from trader_platform.execution.broker_adapter import PaperBroker
from trader_platform.execution.paper_book_guards import (
    MAX_CONCURRENT_WORKING,
    refuse_paper_place,
)
from trader_platform.risk_governor import OrderIntent


def _intent(symbol: str, *, tag: str = "spine:pack_grade_test", ml: float = 80.0) -> OrderIntent:
    return OrderIntent(
        symbol=symbol,
        side="sell",
        qty=1,
        order_type="limit",
        limit_price=0.20,
        strategy_id=f"test_{symbol.lower()}",
        tag=tag,
        structure="iron_condor",
        max_loss_usd=ml,
    )


def test_refuse_same_symbol_and_concurrent_cap() -> None:
    working = [
        {"symbol": "INTC", "tag": "spine:a"},
        {"symbol": "BAC", "tag": "spine:b"},
    ]
    assert "one_open_per_symbol INTC" in (refuse_paper_place(symbol="INTC", working=working) or "")
    assert "max_concurrent" in (refuse_paper_place(symbol="F", working=working) or "")
    smoke = [{"symbol": "INTC", "tag": "m0_stub:smoke_test"}]
    assert refuse_paper_place(symbol="INTC", working=smoke) is None
    assert MAX_CONCURRENT_WORKING == 2


def test_paper_broker_refuses_same_symbol_spray() -> None:
    with tempfile.TemporaryDirectory() as td:
        br = PaperBroker(Path(td) / "ledger.json")
        first = br.place_limit(_intent("INTC"))
        assert first.ok and first.order
        second = br.place_limit(_intent("INTC"))
        assert not second.ok
        assert "one_open_per_symbol INTC" in second.message
        assert len(br.list_open_orders()) == 1


def test_paper_broker_refuses_third_symbol_over_cap() -> None:
    with tempfile.TemporaryDirectory() as td:
        br = PaperBroker(Path(td) / "ledger.json")
        assert br.place_limit(_intent("INTC")).ok
        assert br.place_limit(_intent("BAC")).ok
        third = br.place_limit(_intent("F"))
        assert not third.ok
        assert "max_concurrent" in third.message
        assert {o.symbol for o in br.list_open_orders()} == {"INTC", "BAC"}


def test_paper_broker_smoke_stub_does_not_consume_seat() -> None:
    with tempfile.TemporaryDirectory() as td:
        br = PaperBroker(Path(td) / "ledger.json")
        smoke = br.place_limit(_intent("TSLA", tag="m0_stub:smoke_test"))
        assert smoke.ok
        real = br.place_limit(_intent("INTC"))
        assert real.ok
        assert len(br.list_open_orders()) == 2
