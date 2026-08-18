"""Agentic 1-lot RH MCP place wire — fake mcp_call only, no network."""

from __future__ import annotations

import re
from typing import Any

import pytest

from trader_platform.execution.broker_adapter import (
    LIVE_MAX_NOTIONAL_USD,
    LiveOrdersBlocked,
    NotConnected,
    RobinhoodMcpBroker,
    get_broker,
)
from trader_platform.risk_governor import OrderIntent, RiskGovernor, load_limits

# Synthetic book ids — last4 8507 is the only allowed Agentic sleeve.
# Not a real RH account number.
_AGENTIC_ACCT = "RHUNIT8507"
_OTHER_ACCT = "RHUNIT0001"
_OPTION_ID = "11111111-2222-4333-8444-555555555555"
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

_PLACE_KEYS = {
    "account_number",
    "legs",
    "direction",
    "type",
    "quantity",
    "price",
    "stop_price",
    "time_in_force",
    "market_hours",
    "ref_id",
}
_LEG_KEYS = {"option_id", "side", "position_effect", "ratio_quantity"}
_CANCEL_KEYS = {"account_number", "order_id"}


class FakeMcp:
    """Records tool calls. Never talks to Robinhood."""

    def __init__(
        self,
        *,
        review: Any = None,
        place: Any = None,
        accounts: Any = None,
        instruments: Any = None,
        review_error: Any = None,
    ) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.review = review if review is not None else {"ok": True, "alerts": []}
        self.place = place if place is not None else {
            "id": "ord-test-1",
            "state": "confirmed",
        }
        self.review_error = review_error
        self.accounts = accounts if accounts is not None else {
            "accounts": [
                {
                    "account_number": _AGENTIC_ACCT,
                    "nickname": "Agentic",
                    "agentic_allowed": True,
                    "option_level": "option_level_3",
                },
                {
                    "account_number": _OTHER_ACCT,
                    "nickname": "Individual",
                    "agentic_allowed": False,
                    "option_level": "option_level_3",
                },
            ]
        }
        self.instruments = instruments if instruments is not None else {
            "results": [
                {
                    "id": _OPTION_ID,
                    "type": "put",
                    "strike_price": "385.0",
                    "expiration_date": "2026-09-18",
                }
            ]
        }

    def __call__(self, name: str, args: dict[str, Any]) -> Any:
        self.calls.append((name, dict(args or {})))
        if name == "get_accounts":
            return self.accounts
        if name == "get_option_instruments":
            return self.instruments
        if name == "review_option_order":
            if isinstance(self.review_error, Exception):
                raise self.review_error
            if self.review_error is not None:
                return self.review_error
            return self.review
        if name == "place_option_order":
            return self.place
        if name == "cancel_option_order":
            return {"ok": True, "id": (args or {}).get("order_id")}
        if name == "get_option_orders":
            return {"orders": []}
        raise AssertionError(f"unexpected tool {name}")

    def names(self) -> list[str]:
        return [n for n, _ in self.calls]

    def args_for(self, name: str) -> dict[str, Any]:
        for n, a in self.calls:
            if n == name:
                return a
        raise AssertionError(f"{name} was not called; saw {self.names()}")


def _armed(mcp_call: Any | None = None) -> RobinhoodMcpBroker:
    return RobinhoodMcpBroker(
        connected=True,
        mode="agentic_live",
        agentic_enabled=True,
        mcp_call=mcp_call,
    )


def _csp_intent(**overrides: Any) -> OrderIntent:
    base: dict[str, Any] = dict(
        symbol="TSLA",
        side="sell",
        qty=1,
        order_type="limit",
        limit_price=1.25,
        option_right="put",
        short_strike=385.0,
        expiration="2026-09-18",
        structure="cash_secured_put",
        strategy_id="hyp_test_csp",
        tag="test:place_wire",
    )
    base.update(overrides)
    return OrderIntent(**base)


def _uuid_leg_intent(**overrides: Any) -> OrderIntent:
    return _csp_intent(
        legs=[
            {
                "option_id": _OPTION_ID,
                "side": "sell",
                "position_effect": "open",
                "ratio_quantity": 1,
            }
        ],
        **overrides,
    )


def _assert_last4_safe_message(message: str) -> None:
    assert _AGENTIC_ACCT not in (message or "")
    assert _OTHER_ACCT not in (message or "")


def _assert_schema_args(args: dict[str, Any], *, extra_ok: set[str] | None = None) -> None:
    extra_ok = extra_ok or set()
    assert set(args) <= (_PLACE_KEYS | extra_ok)
    legs = args.get("legs") or []
    assert isinstance(legs, list)
    for leg in legs:
        assert set(leg) <= _LEG_KEYS


def test_enabled_connected_without_mcp_call_stays_blocked() -> None:
    br = _armed(mcp_call=None)
    with pytest.raises(LiveOrdersBlocked):
        br.place_limit(_uuid_leg_intent())


@pytest.mark.parametrize(
    "kwargs,exc",
    [
        ({"mode": "paper", "connected": True, "agentic_enabled": True}, NotConnected),
        ({"mode": "shadow", "connected": True, "agentic_enabled": True}, NotConnected),
        ({"mode": "agentic_live", "connected": False, "agentic_enabled": True}, NotConnected),
        ({"mode": "agentic_live", "connected": True, "agentic_enabled": False}, LiveOrdersBlocked),
    ],
)
def test_place_and_cancel_skip_mcp_unless_live_connected_and_enabled(
    kwargs: dict[str, Any], exc: type[Exception]
) -> None:
    fake = FakeMcp()
    br = RobinhoodMcpBroker(mcp_call=fake, **kwargs)
    with pytest.raises(exc):
        br.place_limit(_uuid_leg_intent())
    with pytest.raises(exc):
        br.cancel("ord-test-1")
    assert fake.names() == []


def test_enabled_false_is_live_orders_blocked_even_with_mcp() -> None:
    fake = FakeMcp()
    br = RobinhoodMcpBroker(
        connected=True,
        mode="agentic_live",
        agentic_enabled=False,
        mcp_call=fake,
    )
    with pytest.raises(LiveOrdersBlocked, match="agentic.enabled"):
        br.place_limit(_uuid_leg_intent())
    with pytest.raises(LiveOrdersBlocked, match="agentic.enabled"):
        br.cancel("ord-test-1")
    assert fake.names() == []
    assert "place_option_order" not in fake.names()
    assert "cancel_option_order" not in fake.names()


def test_fake_mcp_reviews_then_places_one_sell_put() -> None:
    fake = FakeMcp()
    br = _armed(fake)
    res = br.place_limit(_uuid_leg_intent())
    assert res.ok
    assert res.order is not None
    assert res.order.order_id
    _assert_last4_safe_message(res.message)

    names = fake.names()
    assert "review_option_order" in names
    assert "place_option_order" in names
    assert names.index("review_option_order") < names.index("place_option_order")

    place = fake.args_for("place_option_order")
    review = fake.args_for("review_option_order")
    _assert_schema_args(place)
    _assert_schema_args(review, extra_ok={"chain_symbol", "underlying_type"})

    assert str(place["account_number"]).endswith("8507")
    assert str(review["account_number"]).endswith("8507")
    assert place["quantity"] == "1"
    assert place["type"] == "limit"
    assert str(place["price"]) == "1.25"
    assert place.get("time_in_force") in (None, "gfd", "gtc")
    assert "direction" not in place  # single-leg: omit
    assert len(place["legs"]) == 1
    leg = place["legs"][0]
    assert _UUID_RE.match(str(leg["option_id"]))
    assert leg["side"] == "sell"
    assert leg["position_effect"] == "open"
    if "ratio_quantity" in leg:
        assert int(leg["ratio_quantity"]) == 1


def test_fake_review_error_does_not_place() -> None:
    fake = FakeMcp(review_error={"error": True, "message": "hard reject"})
    br = _armed(fake)
    res = br.place_limit(_uuid_leg_intent())
    assert not res.ok
    assert "place_option_order" not in fake.names()
    assert "review_option_order" in fake.names()
    _assert_last4_safe_message(res.message)


def test_qty_two_or_market_does_not_place() -> None:
    fake_qty = FakeMcp()
    br_qty = _armed(fake_qty)
    try:
        res = br_qty.place_limit(_uuid_leg_intent(qty=2))
        assert not res.ok
    except Exception:
        pass
    assert "place_option_order" not in fake_qty.names()

    fake_mkt = FakeMcp()
    br_mkt = _armed(fake_mkt)
    try:
        res = br_mkt.place_limit(
            _uuid_leg_intent(order_type="market", limit_price=None)
        )
        assert not res.ok
    except Exception:
        pass
    assert "place_option_order" not in fake_mkt.names()


def test_max_loss_over_100_does_not_place() -> None:
    fake = FakeMcp()
    br = _armed(fake)
    res = br.place_limit(_uuid_leg_intent(max_loss_usd=150.0))
    assert not res.ok
    assert "100" in (res.message or "")
    assert "place_option_order" not in fake.names()
    assert "review_option_order" not in fake.names()


def test_max_loss_at_100_still_places() -> None:
    fake = FakeMcp()
    br = _armed(fake)
    res = br.place_limit(_uuid_leg_intent(max_loss_usd=100.0))
    assert res.ok
    assert "place_option_order" in fake.names()


def test_live_yaml_honors_soft_kill_one_lot_and_100() -> None:
    import tempfile
    from pathlib import Path

    limits = load_limits()
    assert limits["agentic"]["enabled"] is False
    assert float(limits["order"]["max_notional_per_order"]) == LIVE_MAX_NOTIONAL_USD
    assert float(limits["order"]["max_contracts_per_order"]) == 1

    with tempfile.TemporaryDirectory() as tmp:
        gov = RiskGovernor(limits=limits, repo_root=Path(tmp))
        live_deny = gov.check(_csp_intent(max_loss_usd=80.0), mode="agentic_live")
        assert not live_deny.allowed
        assert any("agentic.enabled" in r for r in live_deny.reasons)

        qty_deny = gov.check(_csp_intent(qty=2, max_loss_usd=80.0), mode="paper")
        assert not qty_deny.allowed

        over_deny = gov.check(_csp_intent(max_loss_usd=150.0), mode="paper")
        assert not over_deny.allowed

        ok = gov.check(_csp_intent(max_loss_usd=80.0), mode="paper")
        assert ok.allowed, ok.reasons


def test_cancel_with_mcp_call_sends_cancel_option_order() -> None:
    fake = FakeMcp()
    br = _armed(fake)
    res = br.cancel("ord-test-1")
    assert res.ok
    assert "cancel_option_order" in fake.names()
    args = fake.args_for("cancel_option_order")
    assert set(args) <= _CANCEL_KEYS
    assert args["order_id"] == "ord-test-1"
    assert str(args["account_number"]).endswith("8507")
    _assert_last4_safe_message(res.message)


def test_cancel_without_mcp_call_stays_blocked() -> None:
    br = _armed(mcp_call=None)
    with pytest.raises(LiveOrdersBlocked):
        br.cancel("ord-test-1")


def test_replace_limit_stays_blocked_even_with_mcp_call() -> None:
    fake = FakeMcp()
    br = _armed(fake)
    with pytest.raises(LiveOrdersBlocked):
        br.replace_limit("ord-test-1", limit_price=1.10)
    assert not any("place" in n or "replace" in n for n in fake.names())


def test_get_broker_passes_mcp_call() -> None:
    fake = FakeMcp()
    br = get_broker(
        "agentic_live",
        rh_connected=True,
        agentic_enabled=True,
        mcp_call=fake,
    )
    assert isinstance(br, RobinhoodMcpBroker)
    res = br.place_limit(_uuid_leg_intent())
    assert res.ok
    assert "place_option_order" in fake.names()


def test_resolve_agentic_picks_8507_and_refuses_other() -> None:
    from trader_platform.execution.rh_mcp_client import resolve_agentic_account_number

    fake = FakeMcp()
    acct = resolve_agentic_account_number(mcp_call=fake)
    assert acct.endswith("8507")
    assert acct == _AGENTIC_ACCT

    refuse = FakeMcp(
        accounts={
            "accounts": [
                {
                    "account_number": "RHUNIT5223",
                    "nickname": "Individual",
                    "agentic_allowed": False,
                }
            ]
        }
    )
    with pytest.raises(Exception):
        resolve_agentic_account_number(mcp_call=refuse)


def test_call_tool_allowlist_refuses_unknown_without_mcp() -> None:
    from trader_platform.execution.rh_mcp_client import call_tool

    with pytest.raises(Exception, match="(?i)refus|allowlist|unknown|forbidden"):
        call_tool("place_equity_order", {})


def test_csp_fields_resolve_option_id_then_place() -> None:
    fake = FakeMcp()
    br = _armed(fake)
    res = br.place_limit(_csp_intent(legs=None))
    assert res.ok
    assert "get_option_instruments" in fake.names()
    place = fake.args_for("place_option_order")
    assert place["legs"][0]["option_id"] == _OPTION_ID
    assert place["legs"][0]["side"] == "sell"
    assert place["quantity"] == "1"
    _assert_last4_safe_message(res.message)


def test_run_tick_injects_mcp_call_only_when_armed(monkeypatch: pytest.MonkeyPatch) -> None:
    from trader_platform.execution.rh_mcp_client import call_tool
    from trader_platform import autonomy_loop as loop

    captured: dict[str, Any] = {}

    def fake_get_broker(mode: str, **kwargs: Any) -> Any:
        captured["mode"] = mode
        captured.update(kwargs)
        raise RuntimeError("stop-before-scan")

    monkeypatch.setattr(loop, "get_broker", fake_get_broker)
    monkeypatch.setattr(loop, "_agentic_enabled_from_limits", lambda: True)
    monkeypatch.setattr(loop, "try_load_snapshot", lambda *a, **k: None)
    with pytest.raises(RuntimeError, match="stop-before-scan"):
        loop.run_tick(
            mode="agentic_live",
            rh_connected=True,
            stub_proposals=True,
            event="place_wire_test",
        )
    assert captured.get("mcp_call") is call_tool

    captured.clear()
    monkeypatch.setattr(loop, "_agentic_enabled_from_limits", lambda: False)
    out = loop.run_tick(
        mode="agentic_live",
        rh_connected=True,
        stub_proposals=True,
        event="place_wire_test",
    )
    assert out.get("ok") is False
    assert "mcp_call" not in captured
