"""Paper book place policy — campaign-equivalent guards at the broker.

Handoff / opportunity / pack-grade execute paths used to bypass
``trader_paper_campaign.sh`` (max_concurrent=2, one-open-per-symbol) and
spray identical spine DNA. Enforce the same book law in ``PaperBroker.place_limit``
so every caller fails closed. Smoke stubs do not count.
"""

from __future__ import annotations

from typing import Any, Iterable

from trader_platform.paper_filters import is_smoke_stub_tag

# Match paper-campaign residual: two defined-risk seats, one working order per symbol.
MAX_CONCURRENT_WORKING = 2


def _is_smoke(order: Any) -> bool:
    tag = getattr(order, "tag", None)
    if tag is None and isinstance(order, dict):
        tag = order.get("tag")
    return is_smoke_stub_tag(str(tag or ""))


def _symbol(order: Any) -> str:
    raw = getattr(order, "symbol", None)
    if raw is None and isinstance(order, dict):
        raw = order.get("symbol")
    return str(raw or "").upper()


def real_working_orders(orders: Iterable[Any]) -> list[Any]:
    return [o for o in orders if not _is_smoke(o)]


def refuse_paper_place(
    *,
    symbol: str,
    working: Iterable[Any],
    max_concurrent: int = MAX_CONCURRENT_WORKING,
) -> str | None:
    """Return a refusal message, or None if the place is book-legal."""
    real = real_working_orders(working)
    want = str(symbol or "").upper()
    if not want:
        return "paper_book_guard: missing symbol"
    if any(_symbol(o) == want for o in real):
        return f"paper_book_guard: one_open_per_symbol {want} already working"
    if len(real) >= int(max_concurrent):
        return (
            f"paper_book_guard: max_concurrent {len(real)} >= {int(max_concurrent)}"
        )
    return None
