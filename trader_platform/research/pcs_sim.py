"""Defined-risk vertical / iron credit simulators.

Paper/research only. Uses BS marks on daily bars (same data pipeline as the
single-leg engine). Max loss is hard-capped by wing width − net credit — the
point of these structures for the $3k sleeve.

Structures:
  - put_credit_spread  (bull put vertical) — original PCS path
  - call_credit_spread (bear call vertical)
  - iron_condor        (OTM put wing + OTM call wing)

Does not place orders. Does not mutate strategies.py defaults.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Mapping, Optional, Sequence, cast

import numpy as np
import pandas as pd

import pricing


ContractGrid = Mapping[str | pd.Timestamp, Mapping[str, Sequence[float]]]
ContractGridProvider = Callable[[str, pd.Timestamp], Optional[ContractGrid]]


def _calendar_days_between(expiration: pd.Timestamp, today: pd.Timestamp) -> int:
    """Calendar DTE independent of intraday timezone metadata."""
    expiration_date = pd.Timestamp(expiration).date()
    today_date = pd.Timestamp(today).date()
    return int((expiration_date - today_date).days)


def strike_increment_for(spot: float) -> float:
    s = float(spot or 0.0)
    if s <= 0:
        return 1.0
    if s < 25:
        return 0.5
    if s < 100:
        return 1.0
    if s < 300:
        return 2.5
    return 5.0


def defined_max_loss_usd(width: float, net_credit: float) -> float:
    """1-lot worst case: (width − credit) * 100, floored at 0."""
    w = max(float(width), 0.0)
    c = max(float(net_credit), 0.0)
    return max(w - c, 0.0) * 100.0


def capital_fit_pcs(
    *,
    max_loss_usd: float,
    sleeve_usd: float = 3000.0,
    open_risk_budget_usd: float = 750.0,
    max_loss_budget_usd: float = 300.0,
    structure: str = "put_credit_spread",
) -> dict[str, Any]:
    """Capital envelope for a 1-lot defined-risk vertical / iron."""
    ml = float(max_loss_usd)
    fits_sleeve = ml > 0 and ml <= sleeve_usd
    fits_open_risk = ml > 0 and ml <= open_risk_budget_usd
    fits_budget = ml > 0 and ml <= max_loss_budget_usd
    max_lots = 0
    if ml > 0:
        by_sleeve = int(sleeve_usd // ml)
        by_risk = int(open_risk_budget_usd // ml) if open_risk_budget_usd > 0 else by_sleeve
        max_lots = max(0, min(by_sleeve, by_risk, 3))
    if fits_budget and fits_open_risk and fits_sleeve and max_lots >= 1:
        fit = "fit_3k" if sleeve_usd <= 3000 else "fit_sleeve"
    elif fits_sleeve and max_lots >= 1:
        fit = "fit_sleeve_soft"  # funds but soft on open-risk/budget
    elif ml > 0 and ml <= 5000:
        fit = "fit_5k"
    elif ml > 0 and ml <= 15000:
        fit = "fit_15k"
    else:
        fit = "oversized" if ml > 0 else "unknown"
    return {
        "structure": structure or "put_credit_spread",
        "capital_fit_usd": round(ml, 2),  # BP ≈ defined max loss for verticals
        "max_loss_usd": round(ml, 2),
        "max_lots": int(max_lots),
        "capital_fit": fit,
        "fits_open_risk_budget": fits_open_risk,
        "fits_max_loss_budget": fits_budget,
        "open_risk_budget_usd": open_risk_budget_usd,
        "max_loss_budget_usd": max_loss_budget_usd,
        "sleeve_usd": sleeve_usd,
        "note": "defined_risk_bp_proxy=max_loss_usd (not cash CSP)",
    }


@dataclass
class PcsTrade:
    """One credit vertical wing (put or call). Also used as iron_condor container via wings."""

    entry_date: pd.Timestamp
    expiration: pd.Timestamp
    short_strike: float
    long_strike: float
    width: float
    net_credit: float  # per share
    dte_at_entry: int
    iv_at_entry: float
    regime_at_entry: str
    short_delta_entry: float
    max_loss_per_share: float
    right: str = "put"  # put | call | iron_condor
    # Iron condor only: second wing (call side). Put wing uses short/long/width fields.
    call_short_strike: float = 0.0
    call_long_strike: float = 0.0
    call_width: float = 0.0
    put_credit: float = 0.0
    call_credit: float = 0.0
    closed: bool = False
    exit_date: Optional[pd.Timestamp] = None
    exit_debit: Optional[float] = None  # per share cost to close net
    exit_reason: Optional[str] = None
    group_id: int = 0

    def _wing_debit(
        self,
        S: float,
        sigma: float,
        today: pd.Timestamp,
        *,
        right: str,
        short_k: float,
        long_k: float,
        r: float,
        half_spread_per_leg: float = 0.0,
    ) -> tuple[float, float]:
        days = _calendar_days_between(self.expiration, today)
        if days <= 0:
            if right == "call":
                short_intr = max(S - short_k, 0.0)
                long_intr = max(S - long_k, 0.0)
                short_d = 1.0 if S > short_k else 0.0
            else:
                short_intr = max(short_k - S, 0.0)
                long_intr = max(long_k - S, 0.0)
                short_d = -1.0 if S < short_k else 0.0
            return max(short_intr - long_intr, 0.0), float(short_d)
        T = days / 365.0
        half_spread = max(float(half_spread_per_leg), 0.0)
        short_px = pricing.price(S, short_k, T, sigma, right, r=r) + half_spread
        long_px = max(pricing.price(S, long_k, T, sigma, right, r=r) - half_spread, 0.0)
        short_d = pricing.delta(S, short_k, T, sigma, right, r=r)
        return max(short_px - long_px, 0.0), float(short_d)

    def mark_net_debit(
        self,
        S: float,
        sigma: float,
        today: pd.Timestamp,
        r: float = 0.04,
        half_spread_per_leg: float = 0.0,
    ) -> dict:
        days = _calendar_days_between(self.expiration, today)
        if self.right == "iron_condor":
            put_debit, put_d = self._wing_debit(
                S,
                sigma,
                today,
                right="put",
                short_k=self.short_strike,
                long_k=self.long_strike,
                r=r,
                half_spread_per_leg=half_spread_per_leg,
            )
            call_debit, call_d = self._wing_debit(
                S,
                sigma,
                today,
                right="call",
                short_k=self.call_short_strike,
                long_k=self.call_long_strike,
                r=r,
                half_spread_per_leg=half_spread_per_leg,
            )
            # Threat = side with larger absolute short delta
            threat_d = put_d if abs(put_d) >= abs(call_d) else call_d
            return {
                "net_debit": max(put_debit + call_debit, 0.0),
                "short_delta": float(threat_d),
                "dte_remaining": days,
            }
        right = "call" if self.right == "call" else "put"
        debit, short_d = self._wing_debit(
            S,
            sigma,
            today,
            right=right,
            short_k=self.short_strike,
            long_k=self.long_strike,
            r=r,
            half_spread_per_leg=half_spread_per_leg,
        )
        return {
            "net_debit": debit,
            "short_delta": short_d,
            "dte_remaining": days,
        }

    def pnl_per_share(self, net_debit: float) -> float:
        return self.net_credit - net_debit


@dataclass
class PcsSimResult:
    symbol: str
    ok: bool
    skipped: bool = False
    reason: str = ""
    period: str = ""
    n_trades: int = 0
    metrics: dict[str, Any] = field(default_factory=dict)
    trades: list[PcsTrade] = field(default_factory=list)
    capital: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # trades may be large; keep summary fields
        d["trades"] = [
            {
                "entry": str(t.entry_date.date()) if t.entry_date is not None else None,
                "exit": str(t.exit_date.date()) if t.exit_date is not None else None,
                "Ks": t.short_strike,
                "Kl": t.long_strike,
                "width": t.width,
                "credit": round(t.net_credit, 4),
                "exit_debit": None if t.exit_debit is None else round(t.exit_debit, 4),
                "pnl_share": None
                if t.exit_debit is None
                else round(t.net_credit - t.exit_debit, 4),
                "reason": t.exit_reason,
                "max_loss_share": round(t.max_loss_per_share, 4),
            }
            for t in self.trades
        ]
        return d


def _cfg_float(cfg: dict[str, Any], key: str, default: float) -> float:
    try:
        return float(cfg.get(key, default))
    except (TypeError, ValueError):
        return float(default)


def _cfg_int(cfg: dict[str, Any], key: str, default: int) -> int:
    try:
        return int(round(float(cfg.get(key, default))))
    except (TypeError, ValueError):
        return int(default)


def _entry_weekdays(cfg: dict[str, Any]) -> set[int] | None:
    raw = cfg.get("entry_weekdays")
    if raw in (None, "", "all"):
        return None
    values = raw if isinstance(raw, (list, tuple, set)) else str(raw).split(",")
    weekdays = {int(value) for value in values}
    if not weekdays or any(value < 0 or value > 4 for value in weekdays):
        raise ValueError("entry_weekdays must contain weekday integers 0..4")
    return weekdays


def _entry_session_buckets(cfg: dict[str, Any]) -> set[str] | None:
    raw = cfg.get("entry_session_buckets")
    if raw in (None, "", "all"):
        return None
    values = raw if isinstance(raw, (list, tuple, set)) else str(raw).split(",")
    buckets = {str(value).strip().lower() for value in values if str(value).strip()}
    allowed = {"open", "midday", "late"}
    if not buckets or not buckets.issubset(allowed):
        raise ValueError(f"entry_session_buckets must be a subset of {sorted(allowed)}")
    return buckets


def entry_filters_pass(row: pd.Series, cfg: dict[str, Any]) -> bool:
    """Apply optional current-row entry bounds without looking ahead."""
    bounds = (
        ("intraday_return", "entry_intraday_return_min", "entry_intraday_return_max"),
        ("volume_surge", "entry_volume_surge_min", "entry_volume_surge_max"),
        ("ret_1d", "entry_ret_1d_min", "entry_ret_1d_max"),
        ("ret_5d", "entry_ret_5d_min", "entry_ret_5d_max"),
        ("ret_14d", "entry_ret_14d_min", "entry_ret_14d_max"),
        ("ema_stack", "entry_ema_stack_min", "entry_ema_stack_max"),
        ("rsi_14", "entry_rsi_min", "entry_rsi_max"),
        ("hv_ratio_20_60", "entry_hv_ratio_min", "entry_hv_ratio_max"),
    )
    for column, minimum_key, maximum_key in bounds:
        if minimum_key not in cfg and maximum_key not in cfg:
            continue
        if column == "hv_ratio_20_60":
            hv_20 = row.get("hv_20")
            hv_60 = row.get("hv_60")
            if hv_20 is None or hv_60 is None:
                return False
            try:
                hv_20_value = float(hv_20)
                hv_60_value = float(hv_60)
            except (TypeError, ValueError):
                return False
            if not np.isfinite(hv_20_value) or not np.isfinite(hv_60_value) or hv_60_value <= 0.0:
                return False
            value = hv_20_value / hv_60_value
        else:
            value = row.get(column)
        if value is None:
            return False
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return False
        if not np.isfinite(numeric_value):
            return False
        if minimum_key in cfg and numeric_value < _cfg_float(cfg, minimum_key, float("-inf")):
            return False
        if maximum_key in cfg and numeric_value > _cfg_float(cfg, maximum_key, float("inf")):
            return False
    return True


def listed_weekly_expiration(entry_date: pd.Timestamp, target_dte: int) -> pd.Timestamp:
    """Return the first Friday on or after the target calendar DTE."""
    if pd.isna(entry_date):
        raise ValueError("entry_date must be a real timestamp")
    target = pd.Timestamp(entry_date.date()) + pd.Timedelta(days=max(int(target_dte), 1))
    days_to_friday = (4 - target.weekday()) % 7
    return cast(pd.Timestamp, target + pd.Timedelta(days=days_to_friday))


def _available_contract(
    contract_grid: ContractGrid,
    *,
    today: pd.Timestamp,
    target_dte: int,
    right: str,
    target_short_strike: float,
    spread_width: float,
) -> tuple[pd.Timestamp, float, float] | None:
    target_expiration = pd.Timestamp(today.date()) + pd.Timedelta(days=max(int(target_dte), 1))
    expirations: list[tuple[pd.Timestamp, Mapping[str, Sequence[float]]]] = []
    for raw_expiration, rights in contract_grid.items():
        expiration = pd.Timestamp(raw_expiration)
        if not pd.isna(expiration) and expiration >= target_expiration:
            expirations.append((cast(pd.Timestamp, expiration), rights))
    for expiration, rights in sorted(expirations, key=lambda item: item[0]):
        strikes = sorted(
            {
                float(strike)
                for strike in rights.get(right, ())
                if np.isfinite(float(strike)) and float(strike) > 0
            }
        )
        if not strikes:
            continue
        short_strike = min(strikes, key=lambda strike: (abs(strike - target_short_strike), strike))
        target_long = short_strike - spread_width if right == "put" else short_strike + spread_width
        if right == "put":
            long_candidates = [strike for strike in strikes if strike < short_strike]
        else:
            long_candidates = [strike for strike in strikes if strike > short_strike]
        if not long_candidates:
            continue
        long_strike = min(long_candidates, key=lambda strike: (abs(strike - target_long), strike))
        return expiration, short_strike, long_strike
    return None


def pick_vertical_entry(
    row: pd.Series,
    S: float,
    today: pd.Timestamp,
    cfg: dict[str, Any],
    *,
    right: str = "put",
    contract_grid: Optional[ContractGrid] = None,
    require_contract_grid: bool = False,
) -> Optional[PcsTrade]:
    """Pick a single credit vertical (put or call)."""
    right = "call" if str(right).lower().startswith("c") else "put"
    iv = float(row.get("iv_proxy") or 0.0)
    if not np.isfinite(iv) or iv <= 0:
        return None
    iv_rank_min = _cfg_float(cfg, "iv_rank_min", 0.0)
    if float(row.get("iv_rank") or 0.0) < iv_rank_min:
        return None

    regime = str(row.get("regime") or "")
    # Put credit: stand aside pure bear unless bear branch enabled.
    # Call credit: stand aside pure bull unless call_in_bull_ok.
    if right == "put" and regime == "bearish" and _cfg_int(cfg, "bear_dte", 0) <= 0:
        return None
    if right == "call" and regime == "bullish" and not bool(cfg.get("call_in_bull_ok", False)):
        return None

    target_dte = max(_cfg_int(cfg, "long_dte", 14), 2)
    target_delta = _cfg_float(cfg, "long_target_delta", 0.20)
    target_delta = min(max(target_delta, 0.08), 0.40)
    width = _cfg_float(cfg, "spread_width", 2.0)
    if width <= 0:
        return None

    synthetic_expiration = listed_weekly_expiration(today, target_dte)
    synthetic_dte = int((synthetic_expiration - pd.Timestamp(today.date())).days)
    T = synthetic_dte / 365.0
    r = _cfg_float(cfg, "risk_free_rate", 0.04)
    try:
        k_exact = pricing.strike_from_delta(S, T, iv, target_delta, right, r=r)
    except ValueError:
        return None
    if contract_grid is not None:
        available = _available_contract(
            contract_grid,
            today=today,
            target_dte=target_dte,
            right=right,
            target_short_strike=k_exact,
            spread_width=width,
        )
        if available is None:
            return None
        expiration, k_short, k_long = available
        dte = int((expiration - pd.Timestamp(today.date())).days)
        T = dte / 365.0
        actual_width = abs(k_short - k_long)
    elif require_contract_grid:
        return None
    else:
        expiration = synthetic_expiration
        dte = synthetic_dte
        inc = strike_increment_for(S)
        k_short = pricing.round_strike(k_exact, inc)
        if right == "put":
            k_long = pricing.round_strike(k_short - width, inc)
            if k_long <= 0 or k_long >= k_short:
                k_long = max(inc, k_short - max(width, inc))
                k_long = pricing.round_strike(k_long, inc)
                if k_long >= k_short:
                    k_long = k_short - inc
                if k_long <= 0:
                    return None
            actual_width = k_short - k_long
        else:
            k_long = pricing.round_strike(k_short + width, inc)
            if k_long <= k_short:
                k_long = k_short + max(width, inc)
                k_long = pricing.round_strike(k_long, inc)
                if k_long <= k_short:
                    k_long = k_short + inc
            actual_width = k_long - k_short
    if actual_width <= 0:
        return None

    slip = _cfg_float(cfg, "slippage_pct", 0.0)
    half_spread = max(_cfg_float(cfg, "half_spread_per_leg", 0.0), 0.0)
    short_px = max(
        float(pricing.price(S, k_short, T, iv, right, r=r)) * (1.0 - slip) - half_spread,
        0.0,
    )
    long_px = float(pricing.price(S, k_long, T, iv, right, r=r)) * (1.0 + slip) + half_spread
    net = short_px - long_px
    if net <= 0.01:
        return None

    min_credit_pct = _cfg_float(cfg, "min_credit_pct", 0.15)
    if net / actual_width < min_credit_pct:
        return None

    max_loss_share = actual_width - net
    max_loss_usd = max_loss_share * 100.0
    budget = _cfg_float(cfg, "max_loss_budget_usd", 300.0)
    if max_loss_usd > budget + 1e-6:
        return None

    short_d = float(pricing.delta(S, k_short, T, iv, right, r=r))
    return PcsTrade(
        entry_date=today,
        expiration=expiration,
        short_strike=float(k_short),
        long_strike=float(k_long),
        width=float(actual_width),
        net_credit=float(net),
        dte_at_entry=dte,
        iv_at_entry=iv,
        regime_at_entry=regime,
        short_delta_entry=short_d,
        max_loss_per_share=float(max_loss_share),
        right=right,
        put_credit=float(net) if right == "put" else 0.0,
        call_credit=float(net) if right == "call" else 0.0,
    )


def pick_pcs_entry(
    row: pd.Series,
    S: float,
    today: pd.Timestamp,
    cfg: dict[str, Any],
    *,
    contract_grid: Optional[ContractGrid] = None,
    require_contract_grid: bool = False,
) -> Optional[PcsTrade]:
    """Backward-compatible put credit spread entry."""
    return pick_vertical_entry(
        row,
        S,
        today,
        cfg,
        right="put",
        contract_grid=contract_grid,
        require_contract_grid=require_contract_grid,
    )


def pick_ccs_entry(
    row: pd.Series,
    S: float,
    today: pd.Timestamp,
    cfg: dict[str, Any],
    *,
    contract_grid: Optional[ContractGrid] = None,
    require_contract_grid: bool = False,
) -> Optional[PcsTrade]:
    """Call credit spread (bear call vertical) entry."""
    return pick_vertical_entry(
        row,
        S,
        today,
        cfg,
        right="call",
        contract_grid=contract_grid,
        require_contract_grid=require_contract_grid,
    )


def pick_iron_condor_entry(
    row: pd.Series,
    S: float,
    today: pd.Timestamp,
    cfg: dict[str, Any],
    *,
    contract_grid: Optional[ContractGrid] = None,
    require_contract_grid: bool = False,
) -> Optional[PcsTrade]:
    """OTM put wing + OTM call wing; defined risk ≈ max(widths) − total credit."""
    allowed_regimes = cfg.get("ic_allowed_regimes")
    if allowed_regimes is not None:
        allowed = (
            {str(value) for value in allowed_regimes}
            if isinstance(allowed_regimes, (list, tuple, set))
            else {value.strip() for value in str(allowed_regimes).split(",") if value.strip()}
        )
        if str(row.get("regime") or "") not in allowed:
            return None
    put_cfg = {
        **cfg,
        "bear_dte": max(_cfg_int(cfg, "bear_dte", 0), 1),
        "long_target_delta": _cfg_float(
            cfg, "put_target_delta", _cfg_float(cfg, "long_target_delta", 0.20)
        ),
        "spread_width": _cfg_float(
            cfg, "put_spread_width", _cfg_float(cfg, "spread_width", 2.0)
        ),
        "min_credit_pct": _cfg_float(
            cfg, "put_min_credit_pct", _cfg_float(cfg, "min_credit_pct", 0.12)
        ),
    }
    call_cfg = {
        **cfg,
        "call_in_bull_ok": True,
        "long_target_delta": _cfg_float(
            cfg, "call_target_delta", _cfg_float(cfg, "long_target_delta", 0.20)
        ),
        "spread_width": _cfg_float(
            cfg, "call_spread_width", _cfg_float(cfg, "spread_width", 2.0)
        ),
        "min_credit_pct": _cfg_float(
            cfg, "call_min_credit_pct", _cfg_float(cfg, "min_credit_pct", 0.12)
        ),
    }
    put = pick_vertical_entry(
        row,
        S,
        today,
        put_cfg,
        right="put",
        contract_grid=contract_grid,
        require_contract_grid=require_contract_grid,
    )
    call = pick_vertical_entry(
        row,
        S,
        today,
        call_cfg,
        right="call",
        contract_grid=contract_grid,
        require_contract_grid=require_contract_grid,
    )
    if put is None or call is None:
        return None
    if not (put.long_strike < put.short_strike < S < call.short_strike < call.long_strike):
        return None
    total_credit = float(put.net_credit + call.net_credit)
    wing = max(float(put.width), float(call.width))
    if total_credit <= 0.02 or wing <= 0:
        return None
    min_credit_pct = _cfg_float(cfg, "min_credit_pct", 0.12)
    if total_credit / wing < min_credit_pct:
        return None
    max_loss_share = wing - total_credit
    if max_loss_share <= 0:
        return None
    max_loss_usd = max_loss_share * 100.0
    budget = _cfg_float(cfg, "max_loss_budget_usd", 300.0)
    if max_loss_usd > budget + 1e-6:
        return None
    threat_d = (
        put.short_delta_entry
        if abs(put.short_delta_entry) >= abs(call.short_delta_entry)
        else call.short_delta_entry
    )
    return PcsTrade(
        entry_date=put.entry_date,
        expiration=put.expiration,
        short_strike=put.short_strike,
        long_strike=put.long_strike,
        width=float(wing),
        net_credit=total_credit,
        dte_at_entry=put.dte_at_entry,
        iv_at_entry=put.iv_at_entry,
        regime_at_entry=put.regime_at_entry,
        short_delta_entry=float(threat_d),
        max_loss_per_share=float(max_loss_share),
        right="iron_condor",
        call_short_strike=float(call.short_strike),
        call_long_strike=float(call.long_strike),
        call_width=float(call.width),
        put_credit=float(put.net_credit),
        call_credit=float(call.net_credit),
    )


def max_close_debit(trade: PcsTrade) -> float:
    """Maximum simultaneous close debit under the defined-risk payoff."""
    if trade.right == "iron_condor":
        put_width = abs(float(trade.short_strike) - float(trade.long_strike))
        return max(put_width, float(trade.call_width))
    return float(trade.width)


def pick_structure_entry(
    row: pd.Series,
    S: float,
    today: pd.Timestamp,
    cfg: dict[str, Any],
    *,
    structure: str = "put_credit_spread",
    contract_grid: Optional[ContractGrid] = None,
    require_contract_grid: bool = False,
) -> Optional[PcsTrade]:
    s = (structure or "put_credit_spread").strip().lower()
    if s in {"call_credit_spread", "ccs", "bear_call_spread", "call_vertical_credit"}:
        return pick_ccs_entry(
            row,
            S,
            today,
            cfg,
            contract_grid=contract_grid,
            require_contract_grid=require_contract_grid,
        )
    if s in {"iron_condor", "ic", "short_iron_condor"}:
        return pick_iron_condor_entry(
            row,
            S,
            today,
            cfg,
            contract_grid=contract_grid,
            require_contract_grid=require_contract_grid,
        )
    return pick_pcs_entry(
        row,
        S,
        today,
        cfg,
        contract_grid=contract_grid,
        require_contract_grid=require_contract_grid,
    )


def check_pcs_exit(
    trade: PcsTrade,
    mark: dict,
    row: pd.Series,
    cfg: dict[str, Any],
) -> Optional[str]:
    dte_rem = int(mark["dte_remaining"])
    if dte_rem <= 0:
        return "expired"

    net_debit = float(mark["net_debit"])
    slip = _cfg_float(cfg, "slippage_pct", 0.0)
    net_debit *= 1.0 + slip
    pnl = trade.net_credit - net_debit

    profit_target = _cfg_float(cfg, "profit_target", 0.50)
    if trade.net_credit > 0 and pnl >= profit_target * trade.net_credit:
        return "profit_target"

    # Defined-risk stop: fraction of max loss (not naked mult of credit)
    max_loss_frac = _cfg_float(cfg, "defined_loss_exit_frac", 0.0)
    if max_loss_frac <= 0:
        # fallback: if max_loss_mult looks like a fraction, use it; else 0.85
        raw = _cfg_float(cfg, "max_loss_mult", 0.85)
        max_loss_frac = raw if raw <= 1.0 else 0.85
    max_loss_frac = min(max(max_loss_frac, 0.3), 1.0)
    if pnl <= -max_loss_frac * trade.max_loss_per_share:
        return "max_defined_loss"

    delta_breach = _cfg_float(cfg, "delta_breach", 0.45)
    short_delta_abs = abs(float(mark.get("short_delta") or 0.0))
    if short_delta_abs >= delta_breach:
        return "delta_breach"

    dte_stop = _cfg_int(cfg, "dte_stop", 3)
    if dte_rem <= dte_stop and dte_rem < trade.dte_at_entry:
        return "dte_stop"

    if bool(cfg.get("regime_flip_exit_enabled", True)):
        reg = str(row.get("regime") or "")
        if trade.regime_at_entry in ("bullish", "neutral") and reg == "bearish":
            return "regime_flip"

    return None


def compute_pcs_metrics(trades: list[PcsTrade]) -> dict[str, Any]:
    if not trades:
        return {"n_trades": 0}

    pnl_share = np.array(
        [t.net_credit - (t.exit_debit if t.exit_debit is not None else 0.0) for t in trades],
        dtype=float,
    )
    pnl_contract = pnl_share * 100.0
    wins = pnl_share[pnl_share > 0]
    losses = pnl_share[pnl_share <= 0]
    equity = np.cumsum(pnl_contract)
    peak = np.maximum.accumulate(equity)
    drawdown = peak - equity
    gross_win = float(wins.sum()) if len(wins) else 0.0
    gross_loss = float(abs(losses.sum())) if len(losses) else 0.0
    pf = gross_win / gross_loss if gross_loss > 0 else float("inf")

    reasons: dict[str, int] = {}
    for t in trades:
        reasons[t.exit_reason or "unknown"] = reasons.get(t.exit_reason or "unknown", 0) + 1

    days_held = np.array(
        [(t.exit_date - t.entry_date).days for t in trades if t.exit_date is not None],
        dtype=float,
    )
    max_losses = np.array([t.max_loss_per_share * 100.0 for t in trades], dtype=float)
    widths = np.array([t.width for t in trades], dtype=float)
    credits = np.array([t.net_credit for t in trades], dtype=float)

    return {
        "n_trades": len(trades),
        "win_rate_pct": float(len(wins) / len(trades) * 100),
        "total_pnl_per_contract": float(pnl_contract.sum()),
        "avg_pnl_per_contract": float(pnl_contract.mean()),
        "avg_win_per_contract": float(wins.mean() * 100) if len(wins) else 0.0,
        "avg_loss_per_contract": float(losses.mean() * 100) if len(losses) else 0.0,
        "profit_factor": float(pf) if np.isfinite(pf) else float("inf"),
        "max_dd_per_contract": float(drawdown.max()) if len(drawdown) else 0.0,
        "avg_days_held": float(days_held.mean()) if len(days_held) else 0.0,
        "exit_reasons": reasons,
        "n_groups": len(trades),
        "group_win_rate_pct": float(len(wins) / len(trades) * 100),
        "avg_group_pnl_per_contract": float(pnl_contract.mean()),
        "worst_group_pnl_per_contract": float(pnl_contract.min()),
        "best_group_pnl_per_contract": float(pnl_contract.max()),
        "avg_positions_per_group": 1.0,
        "max_positions_per_group": 1.0,
        "avg_max_loss_usd": float(max_losses.mean()) if len(max_losses) else 0.0,
        "p95_max_loss_usd": float(np.percentile(max_losses, 95)) if len(max_losses) else 0.0,
        "worst_max_loss_usd": float(max_losses.max()) if len(max_losses) else 0.0,
        "avg_width": float(widths.mean()) if len(widths) else 0.0,
        "avg_net_credit": float(credits.mean()) if len(credits) else 0.0,
        "structure": "defined_risk_credit",
    }


def run_pcs_backtest(
    symbol: str,
    *,
    period: str = "2y",
    use_cache: bool = True,
    config: Optional[dict[str, Any]] = None,
    sleeve_usd: float = 3000.0,
    open_risk_budget_usd: float = 750.0,
    df: Optional[pd.DataFrame] = None,
    min_bars: int = 15,
    structure: str = "put_credit_spread",
    contract_grid_provider: Optional[ContractGridProvider] = None,
    require_contract_grid: bool = False,
) -> PcsSimResult:
    """Daily event-loop defined-risk credit sim (PCS / CCS / iron condor).

    Pass ``df`` to stress a regime window without reloading full history.
    When ``df`` is provided, ``period`` is only a label on the result.
    ``structure`` selects put_credit_spread | call_credit_spread | iron_condor.
    """
    sym = symbol.upper()
    cfg = dict(config or {})
    structure = str(cfg.get("structure") or structure or "put_credit_spread").strip().lower()
    if structure in {"pcs", "bull_put", "bull_put_spread", "put_vertical_credit"}:
        structure = "put_credit_spread"
    elif structure in {"ccs", "bear_call", "bear_call_spread", "call_vertical_credit"}:
        structure = "call_credit_spread"
    elif structure in {"ic", "short_iron_condor"}:
        structure = "iron_condor"
    if df is None:
        try:
            from data import build
        except Exception as exc:  # noqa: BLE001
            return PcsSimResult(
                symbol=sym, ok=False, skipped=True, reason=f"data import: {exc}", period=period, config=cfg
            )

        try:
            df = build(sym, period=period, use_cache=use_cache)
        except Exception as exc:  # noqa: BLE001
            return PcsSimResult(
                symbol=sym, ok=False, skipped=True, reason=f"build failed: {exc}", period=period, config=cfg
            )

    if df is None or len(df) < int(min_bars):
        return PcsSimResult(
            symbol=sym,
            ok=False,
            skipped=True,
            reason="insufficient history",
            period=period,
            config=cfg,
        )

    trades: list[PcsTrade] = []
    open_t: Optional[PcsTrade] = None
    gid = 0
    r = _cfg_float(cfg, "risk_free_rate", 0.04)
    half_spread = max(_cfg_float(cfg, "half_spread_per_leg", 0.0), 0.0)
    entry_weekdays = _entry_weekdays(cfg)
    entry_session_buckets = _entry_session_buckets(cfg)
    entered_session_buckets: set[tuple[object, str]] = set()

    for row_number, (today, row) in enumerate(df.iterrows()):
        S = float(row["close"])
        sigma = float(row["iv_proxy"])
        if not np.isfinite(sigma) or sigma <= 0:
            continue
        session_bucket = str(row.get("session_bucket") or "").strip().lower()
        session_key = (pd.Timestamp(str(today)).date(), session_bucket)

        closed_this_bar = False
        if open_t is not None:
            mark = open_t.mark_net_debit(
                S, sigma, pd.Timestamp(str(today)), r=r, half_spread_per_leg=half_spread
            )
            decision = check_pcs_exit(open_t, mark, row, cfg)
            if decision is not None:
                debit = float(mark["net_debit"]) * (1.0 + _cfg_float(cfg, "slippage_pct", 0.0))
                # Only one non-overlapping condor wing can finish in the money.
                max_debit = max_close_debit(open_t)
                debit = min(debit, max_debit)
                open_t.exit_date = today
                open_t.exit_debit = debit
                open_t.exit_reason = decision
                open_t.closed = True
                trades.append(open_t)
                open_t = None
                closed_this_bar = True
                # An exit consumes this date/bucket too. Otherwise a position
                # opened on an earlier date could close early in a bucket and
                # re-enter later in that same bucket.
                if entry_session_buckets is not None:
                    entered_session_buckets.add(session_key)

        # One position per bar: never re-enter on the close bar (canonical harness).
        signal_lag = max(_cfg_int(cfg, "entry_signal_lag_bars", 0), 0)
        signal_row = df.iloc[row_number - signal_lag] if row_number >= signal_lag else None
        if (
            open_t is None
            and not closed_this_bar
            and (entry_weekdays is None or pd.Timestamp(str(today)).weekday() in entry_weekdays)
            and (
                entry_session_buckets is None
                or (
                    session_bucket in entry_session_buckets
                    and session_key not in entered_session_buckets
                )
            )
            and signal_row is not None
            and entry_filters_pass(signal_row, cfg)
        ):
            entry_date = cast(pd.Timestamp, pd.Timestamp(str(today)))
            if contract_grid_provider or require_contract_grid:
                contract_grid = contract_grid_provider(sym, entry_date) if contract_grid_provider else None
                ent = pick_structure_entry(
                    signal_row,
                    S,
                    entry_date,
                    cfg,
                    structure=structure,
                    contract_grid=contract_grid,
                    require_contract_grid=require_contract_grid,
                )
            else:
                ent = pick_structure_entry(signal_row, S, entry_date, cfg, structure=structure)
            if ent is not None:
                ent.group_id = gid
                gid += 1
                open_t = ent
                if entry_session_buckets is not None:
                    entered_session_buckets.add(session_key)

    # EOD close
    if open_t is not None:
        last_date = df.index[-1]
        last_row = df.iloc[-1]
        S_last = float(last_row["close"])
        sigma_last = float(last_row["iv_proxy"])
        mark = open_t.mark_net_debit(
            S_last,
            max(sigma_last, 1e-6),
            pd.Timestamp(str(last_date)),
            r=r,
            half_spread_per_leg=half_spread,
        )
        max_debit = max_close_debit(open_t)
        debit = min(
            float(mark["net_debit"]) * (1.0 + _cfg_float(cfg, "slippage_pct", 0.0)),
            max_debit,
        )
        open_t.exit_date = last_date
        open_t.exit_debit = debit
        open_t.exit_reason = "end_of_data"
        open_t.closed = True
        trades.append(open_t)

    metrics = compute_pcs_metrics(trades)
    metrics["contract_grid_mode"] = (
        "required_observed" if require_contract_grid else "injected_optional" if contract_grid_provider else "synthetic"
    )
    # Representative capital from median trade defined max loss
    if trades:
        med_ml = float(np.median([t.max_loss_per_share * 100.0 for t in trades]))
        p95_ml = float(metrics.get("p95_max_loss_usd") or med_ml)
        rep_ml = max(med_ml, p95_ml * 0.85)  # slightly conservative
    else:
        # theoretical from last spot + config
        spot = float(df["close"].iloc[-1])
        width = _cfg_float(cfg, "spread_width", 2.0)
        # assume credit ≈ 25% of width if no trades
        rep_ml = defined_max_loss_usd(width, width * 0.25)

    budget = _cfg_float(cfg, "max_loss_budget_usd", 300.0)
    capital = capital_fit_pcs(
        max_loss_usd=rep_ml,
        sleeve_usd=sleeve_usd,
        open_risk_budget_usd=open_risk_budget_usd,
        max_loss_budget_usd=budget,
        structure=structure,
    )
    metrics["structure"] = structure
    capital["structure"] = structure
    if trades:
        capital["median_max_loss_usd"] = round(float(np.median([t.max_loss_per_share * 100 for t in trades])), 2)
        capital["p95_max_loss_usd"] = round(float(metrics.get("p95_max_loss_usd") or 0), 2)

    return PcsSimResult(
        symbol=sym,
        ok=True,
        skipped=False,
        reason="ok",
        period=period,
        n_trades=len(trades),
        metrics=metrics,
        trades=trades,
        capital=capital,
        config=cfg,
    )
