"""Robinhood MCP helper for the isolated Agentic sleeve.

Live import of ``mcp`` is isolated so unit tests pass without the package
or a network. Never log access tokens or full account numbers.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Callable, Optional

from trader_platform.execution.broker_adapter import NotConnected

TOKEN_PATH = (
    Path.home()
    / ".hermes"
    / "profiles"
    / "trader"
    / "mcp-tokens"
    / "robinhood-trading.json"
)
MCP_URL = "https://agent.robinhood.com/mcp/trading"
AGENTIC_LAST4 = "8507"
ALLOWED_TOOLS = frozenset(
    {
        "get_accounts",
        "get_option_instruments",
        "review_option_order",
        "place_option_order",
        "cancel_option_order",
        "get_option_orders",
    }
)

McpCall = Callable[[str, dict[str, Any]], Any]


def _load_access_token() -> str:
    if not TOKEN_PATH.is_file():
        raise NotConnected(
            "Robinhood MCP token file missing "
            "(~/.hermes/profiles/trader/mcp-tokens/robinhood-trading.json)"
        )
    try:
        data = json.loads(TOKEN_PATH.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise NotConnected("Robinhood MCP token file unreadable") from exc
    if not isinstance(data, dict):
        raise NotConnected("Robinhood MCP token file invalid")
    token = data.get("access_token")
    if not token or not isinstance(token, str):
        raise NotConnected("Robinhood MCP token file has no access_token")
    exp = data.get("expires_at")
    if exp is not None:
        try:
            if float(exp) < time.time() + 30:
                raise NotConnected("Robinhood MCP access token expired")
        except (TypeError, ValueError):
            pass
    return token


def _parse_tool_result(result: Any) -> Any:
    if result is None:
        return None
    if getattr(result, "isError", False):
        return {"error": True, "content": str(getattr(result, "content", result))}
    structured = getattr(result, "structuredContent", None)
    content = getattr(result, "content", None)
    if not content:
        return structured if structured is not None else {}
    texts: list[str] = []
    for block in content:
        text = getattr(block, "text", None)
        if text:
            texts.append(text)
    joined = "\n".join(texts).strip()
    if not joined:
        return structured if structured is not None else {}
    try:
        return json.loads(joined)
    except json.JSONDecodeError:
        return structured if structured is not None else {"raw_text": joined[:4000]}


async def _call_tool_async(
    name: str,
    args: dict[str, Any],
    token: str,
    ClientSession: Any,
    streamablehttp_client: Any,
) -> Any:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/event-stream",
    }
    async with streamablehttp_client(MCP_URL, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, args)
            return _parse_tool_result(result)


def _run_coro(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # Sync callers inside an event loop: run on a private loop in a thread.
    import concurrent.futures

    def _runner() -> Any:
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_runner).result()


def call_tool(name: str, args: Optional[dict[str, Any]] = None) -> Any:
    if name not in ALLOWED_TOOLS:
        raise RuntimeError(f"refusing non-allowlisted MCP tool {name}")
    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client
    except ImportError as exc:
        raise NotConnected(
            "mcp package not installed in this interpreter; "
            "inject mcp_call= for tests or run from a Hermes-capable env"
        ) from exc
    token = _load_access_token()
    payload = dict(args or {})
    return _run_coro(
        _call_tool_async(name, payload, token, ClientSession, streamablehttp_client)
    )


def _iter_accounts(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [a for a in raw if isinstance(a, dict)]
    if not isinstance(raw, dict):
        return []
    data = raw.get("data")
    if isinstance(data, dict) and isinstance(data.get("accounts"), list):
        return [a for a in data["accounts"] if isinstance(a, dict)]
    for key in ("accounts", "results"):
        val = raw.get(key)
        if isinstance(val, list):
            return [a for a in val if isinstance(a, dict)]
        if isinstance(val, dict) and isinstance(val.get("accounts"), list):
            return [a for a in val["accounts"] if isinstance(a, dict)]
    if raw.get("account_number") or raw.get("accountNumber"):
        return [raw]
    return []


def _account_number(acc: dict[str, Any]) -> str:
    return str(acc.get("account_number") or acc.get("accountNumber") or "").strip()


def _agentic_allowed(acc: dict[str, Any]) -> bool:
    flag = acc.get("agentic_allowed")
    if flag is None:
        flag = acc.get("agenticAllowed")
    return bool(flag)


def resolve_agentic_account_number(*, mcp_call: Optional[McpCall] = None) -> str:
    """Pick the Agentic book: agentic_allowed=true AND last4 8507 only."""
    call = mcp_call or call_tool
    raw = call("get_accounts", {})
    matches: list[tuple[str, str]] = []
    for acc in _iter_accounts(raw):
        num = _account_number(acc)
        if not num.endswith(AGENTIC_LAST4):
            continue
        if not _agentic_allowed(acc):
            continue
        nick = str(acc.get("nickname") or acc.get("account_nickname") or "")
        matches.append((num, nick))
    if not matches:
        raise NotConnected(
            "Agentic account last4 8507 with agentic_allowed=true not found; "
            "refusing to pick another book"
        )
    named = [m for m in matches if "agentic" in m[1].lower()]
    return (named or matches)[0][0]
