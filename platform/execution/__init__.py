"""Broker adapters — paper implemented; live RH MCP stubbed."""

from platform.execution.broker_adapter import (
    BrokerAdapter,
    NotConnected,
    OrderResult,
    PaperBroker,
    RobinhoodMcpBroker,
    WorkingOrder,
)

__all__ = [
    "BrokerAdapter",
    "NotConnected",
    "OrderResult",
    "PaperBroker",
    "RobinhoodMcpBroker",
    "WorkingOrder",
]
