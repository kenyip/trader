"""Broker adapters — paper + paper_rh_bridge; RH MCP review stubs + fail-closed place."""

from trader_platform.execution.broker_adapter import (
    BrokerAdapter,
    LiveOrdersBlocked,
    NotConnected,
    OrderResult,
    PaperBroker,
    PaperRhBridge,
    RhMcpReadAdapter,
    RhReviewPayload,
    RobinhoodMcpBroker,
    WorkingOrder,
    build_review_equity_order,
    build_review_option_order,
    get_broker,
)

__all__ = [
    "BrokerAdapter",
    "LiveOrdersBlocked",
    "NotConnected",
    "OrderResult",
    "PaperBroker",
    "PaperRhBridge",
    "RhMcpReadAdapter",
    "RhReviewPayload",
    "RobinhoodMcpBroker",
    "WorkingOrder",
    "build_review_equity_order",
    "build_review_option_order",
    "get_broker",
]
