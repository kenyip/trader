"""Robinhood read-only snapshot schema + readiness checks (Stage2).

MCP lives in Hermes, not in this package. Agents/operators write a local
snapshot under .cache/platform/ (gitignored) after a read-only MCP smoke.
Code here never places orders and never stores secrets.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from trader_platform.risk_governor import PortfolioSnapshot

_REPO = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT_PATH = _REPO / ".cache" / "platform" / "rh_readonly_snapshot.json"
SMOKE_REPORT_PATH = _REPO / ".cache" / "platform" / "rh_readonly_smoke.json"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def mask_account(account_number: str | None) -> str:
    s = (account_number or "").strip()
    if len(s) <= 4:
        return "••••"
    return f"••••{s[-4:]}"


@dataclass
class EquityPositionView:
    symbol: str
    quantity: float
    average_buy_price: Optional[float] = None
    position_type: str = "long"  # long | short


@dataclass
class OptionPositionView:
    chain_symbol: str
    quantity: float
    position_type: str  # long | short
    expiration_date: str = ""
    strike: Optional[float] = None
    option_type: str = ""  # call | put
    average_price: Optional[float] = None  # RH dollars per contract (signed)
    option_id: str = ""


@dataclass
class AccountView:
    account_number_masked: str
    nickname: str = ""
    account_type: str = ""  # margin | cash
    brokerage_account_type: str = "individual"
    agentic_allowed: bool = False
    option_level: str = ""
    is_default: bool = False
    total_value: float = 0.0
    equity_value: float = 0.0
    options_value: float = 0.0
    cash: float = 0.0
    buying_power: float = 0.0
    equities: list[EquityPositionView] = field(default_factory=list)
    options: list[OptionPositionView] = field(default_factory=list)
    open_equity_orders: int = 0
    open_option_orders: int = 0


@dataclass
class RhReadiness:
    ok: bool
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    agentic_account_masked: str = ""
    agentic_total_value: float = 0.0
    agentic_option_level: str = ""
    agentic_allowed: bool = False


@dataclass
class RhSnapshot:
    fetched_at: str
    data_quality: str  # RTH | after_hours | weekend | unknown
    source: str = "hermes_mcp_readonly"
    accounts: list[AccountView] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def agentic_accounts(self) -> list[AccountView]:
        return [a for a in self.accounts if a.agentic_allowed]

    def default_account(self) -> Optional[AccountView]:
        for a in self.accounts:
            if a.is_default:
                return a
        return self.accounts[0] if self.accounts else None

    def readiness(self) -> RhReadiness:
        blockers: list[str] = []
        warnings: list[str] = []
        agentics = self.agentic_accounts()
        if not agentics:
            blockers.append("no agentic_allowed account visible to this agent")
            return RhReadiness(ok=False, blockers=blockers, warnings=warnings)

        # Prefer nickname Agentic if present
        ag = next((a for a in agentics if "agentic" in (a.nickname or "").lower()), agentics[0])
        if ag.total_value <= 0 and ag.cash <= 0 and ag.buying_power <= 0:
            blockers.append(
                f"agentic account {ag.account_number_masked} has ~$0 capital "
                "(fund before any agentic_live arming)"
            )
        opt = (ag.option_level or "").strip().lower()
        if not opt or opt in ("option_level_0", "option_level_none", "none"):
            blockers.append(
                f"agentic account {ag.account_number_masked} has no options level "
                "(upgrade to option_level_2+ before options autonomy)"
            )
        if ag.account_type == "cash" and ag.total_value > 0:
            warnings.append(
                "agentic account is cash (not margin) — CSP/covered structures need full cash collateral"
            )
        if not ag.agentic_allowed:
            blockers.append("agentic_allowed=false on selected agentic account")

        main = self.default_account()
        if main and main.agentic_allowed:
            warnings.append(
                "default account is agentic_allowed — confirm isolation policy still holds"
            )
        if main and not main.agentic_allowed:
            warnings.append(
                f"main/default {main.account_number_masked} correctly non-agentic for this agent"
            )

        return RhReadiness(
            ok=not blockers,
            blockers=blockers,
            warnings=warnings,
            agentic_account_masked=ag.account_number_masked,
            agentic_total_value=float(ag.total_value),
            agentic_option_level=ag.option_level or "",
            agentic_allowed=bool(ag.agentic_allowed),
        )

    def portfolio_for_risk(self, *, prefer_agentic: bool = True) -> PortfolioSnapshot:
        """Map snapshot → RiskGovernor PortfolioSnapshot (open orders only; open_risk=0 unless known)."""
        targets = self.agentic_accounts() if prefer_agentic else []
        if not targets:
            targets = self.accounts
        open_orders = 0
        for a in targets:
            open_orders += int(a.open_equity_orders) + int(a.open_option_orders)
        return PortfolioSnapshot(open_risk=0.0, open_order_count=open_orders, daily_pnl=0.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fetched_at": self.fetched_at,
            "data_quality": self.data_quality,
            "source": self.source,
            "notes": list(self.notes),
            "accounts": [
                {
                    **{k: v for k, v in asdict(a).items() if k not in ("equities", "options")},
                    "equities": [asdict(e) for e in a.equities],
                    "options": [asdict(o) for o in a.options],
                }
                for a in self.accounts
            ],
            "readiness": asdict(self.readiness()),
        }

    @classmethod
    def from_dict(cls, data: MappingLike) -> "RhSnapshot":
        accounts: list[AccountView] = []
        for raw in data.get("accounts") or []:
            equities = [
                EquityPositionView(
                    symbol=str(e.get("symbol", "")).upper(),
                    quantity=float(e.get("quantity") or 0),
                    average_buy_price=_opt_float(e.get("average_buy_price")),
                    position_type=str(e.get("position_type") or e.get("type") or "long"),
                )
                for e in (raw.get("equities") or [])
            ]
            options = [
                OptionPositionView(
                    chain_symbol=str(o.get("chain_symbol", "")).upper(),
                    quantity=float(o.get("quantity") or 0),
                    position_type=str(o.get("position_type") or o.get("type") or "long"),
                    expiration_date=str(o.get("expiration_date") or ""),
                    strike=_opt_float(o.get("strike")),
                    option_type=str(o.get("option_type") or ""),
                    average_price=_opt_float(o.get("average_price")),
                    option_id=str(o.get("option_id") or ""),
                )
                for o in (raw.get("options") or [])
            ]
            accounts.append(
                AccountView(
                    account_number_masked=str(raw.get("account_number_masked") or "••••"),
                    nickname=str(raw.get("nickname") or ""),
                    account_type=str(raw.get("account_type") or ""),
                    brokerage_account_type=str(raw.get("brokerage_account_type") or "individual"),
                    agentic_allowed=bool(raw.get("agentic_allowed")),
                    option_level=str(raw.get("option_level") or ""),
                    is_default=bool(raw.get("is_default")),
                    total_value=float(raw.get("total_value") or 0),
                    equity_value=float(raw.get("equity_value") or 0),
                    options_value=float(raw.get("options_value") or 0),
                    cash=float(raw.get("cash") or 0),
                    buying_power=float(raw.get("buying_power") or 0),
                    equities=equities,
                    options=options,
                    open_equity_orders=int(raw.get("open_equity_orders") or 0),
                    open_option_orders=int(raw.get("open_option_orders") or 0),
                )
            )
        return cls(
            fetched_at=str(data.get("fetched_at") or _now()),
            data_quality=str(data.get("data_quality") or "unknown"),
            source=str(data.get("source") or "hermes_mcp_readonly"),
            accounts=accounts,
            notes=list(data.get("notes") or []),
        )


# typing helper without importing Mapping from typing for runtime simplicity
MappingLike = dict[str, Any]


def _opt_float(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    return float(v)


def save_snapshot(snap: RhSnapshot, path: Path | str | None = None) -> Path:
    p = Path(path) if path else DEFAULT_SNAPSHOT_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w") as f:
        json.dump(snap.to_dict(), f, indent=2)
    return p


def load_snapshot(path: Path | str | None = None) -> RhSnapshot:
    p = Path(path) if path else DEFAULT_SNAPSHOT_PATH
    with p.open() as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"snapshot must be object: {p}")
    return RhSnapshot.from_dict(data)


def try_load_snapshot(path: Path | str | None = None) -> Optional[RhSnapshot]:
    p = Path(path) if path else DEFAULT_SNAPSHOT_PATH
    if not p.exists():
        return None
    return load_snapshot(p)


def recommend_risk_limits(agentic_capital: float) -> dict[str, Any]:
    """Suggest risk_limits.yaml scales from agentic sleeve capital (not main account)."""
    c = max(0.0, float(agentic_capital))
    if c <= 0:
        return {
            "status": "unfunded",
            "message": "Agentic capital is $0 — keep agentic.enabled=false; do not arm live",
            "suggested": {
                "order.max_notional_per_order": 2500.0,
                "order.max_contracts_per_order": 2,
                "portfolio.max_open_risk": 2500.0,
                "portfolio.max_daily_loss": 250.0,
                "portfolio.max_open_orders": 3,
            },
        }
    # Conservative: ~10% daily loss of capital, ~25% open risk, ~10% single-order notional
    return {
        "status": "funded",
        "agentic_capital": c,
        "suggested": {
            "order.max_notional_per_order": round(min(2500.0, max(200.0, 0.10 * c)), 2),
            "order.max_contracts_per_order": 2 if c < 5000 else (3 if c < 15000 else 5),
            "portfolio.max_open_risk": round(min(5000.0, max(500.0, 0.25 * c)), 2),
            "portfolio.max_daily_loss": round(min(750.0, max(100.0, 0.10 * c)), 2),
            "portfolio.max_open_orders": 3 if c < 10000 else 10,
            "instrument_allowlist": ["TSLA", "TSLL"],
            "strategy_allowlist_note": "pin explicit hyp_* ids before agentic_live",
        },
    }


def capital_plan_tiers() -> list[dict[str, Any]]:
    """Static funding tiers for the isolated Agentic sleeve."""
    return [
        {
            "tier": "T0_unfunded",
            "capital": 0,
            "use": "read-only smoke + paper/shadow only",
            "allowed_modes": ["research", "paper", "shadow"],
            "arm_agentic_live": False,
        },
        {
            "tier": "T1_seed",
            "capital": 2500,
            "use": "tiny equity/option single-leg limits; prove order lifecycle",
            "allowed_modes": ["research", "paper", "shadow", "agentic_live(limits only)"],
            "arm_agentic_live": "after options level + risk yaml review",
            "max_daily_loss_hint": 250,
            "max_notional_hint": 250,
        },
        {
            "tier": "T2_income_lab",
            "capital": 5000,
            "use": "small short-premium / 1-lot PMCC income experiments on allowlist only",
            "max_daily_loss_hint": 500,
            "max_notional_hint": 500,
            "arm_agentic_live": "after 5+ clean paper days + promotion evidence",
        },
        {
            "tier": "T3_scaled",
            "capital": 10000,
            "use": "scaled agentic sleeve still << main account; not a full income engine migration",
            "max_daily_loss_hint": 750,
            "max_notional_hint": 1000,
            "arm_agentic_live": "only with explicit strategy allowlist + kill switch drill",
        },
    ]
