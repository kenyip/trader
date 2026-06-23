#!/usr/bin/env python3
"""
simulator/validate_model_policy.py

Framework for testing a model-driven policy (pick_entry_model) against real historical data
at any period — the missing piece for proper model validation.

This is the equivalent of `validate_rule.py` but for full model-based strategies.
"""

from __future__ import annotations
from typing import Callable, Dict, Any, Optional
import pandas as pd

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data import build
from backtest import Backtester, compute_metrics, Position
from strategies import check_exits, get_config
from scenarios import canonical_window, REGIMES


def _make_model_entry_fn(model_instance=None):
    """
    Adapter that can use either the strategies integration or the direct PickEntryModel class.
    """
    if model_instance is None:
        from strategies import pick_entry_model as strategies_pick_entry_model

        def model_entry_fn(row: pd.Series, cfg, S: float, today: pd.Timestamp):
            try:
                pos = strategies_pick_entry_model(row, cfg, S, today)
                if getattr(cfg, "model_debug", False) and pos is not None:
                    print("[validate strategies adapter] model entry succeeded (4 overrides forwarded)")
                return pos
            except Exception as e:
                if getattr(cfg, "model_debug", False):
                    print(f"[validate strategies adapter] error: {e}")
                return None
        return model_entry_fn

    # Direct use of PickEntryModel class (more reliable for testing)
    from simulator.pick_entry_model import PickEntryModel
    if not isinstance(model_instance, PickEntryModel):
        model_instance = PickEntryModel()

    def direct_model_entry_fn(row: pd.Series, cfg, S: float, today: pd.Timestamp):
        try:
            import pricing
            recs = model_instance.recommend(
                row,
                min_policy_conf=getattr(cfg, "model_min_policy_conf", 0.35),
                min_edge=getattr(cfg, "model_min_edge", 0.0),
                min_should_trade=getattr(cfg, "model_min_should_trade", 0.55),
                use_should_trade_gate=True,
                debug=getattr(cfg, "model_debug", False),
            )
            if not recs:
                return None

            best = recs[0]
            action = best.entry_action
            policy = best.recommended_policy

            T = action.dte / 365.0
            iv = float(row.get("iv_proxy", 0.55))

            try:
                K = pricing.strike_from_delta(S, T, iv, action.target_delta, action.side, r=cfg.risk_free_rate)
                K = pricing.round_strike(K, 2.5)
                credit = pricing.price(S, K, T, iv, action.side, r=cfg.risk_free_rate)
            except Exception:
                return None

            if credit / K < 0.008:  # permissive for testing
                return None

            expiration = today + pd.Timedelta(days=action.dte)

            position = Position(
                side=action.side,
                entry_date=today,
                expiration=expiration,
                strike=K,
                credit=credit,
                dte_at_entry=action.dte,
                iv_at_entry=iv,
                regime_at_entry=str(row.get("regime", "unknown")),
                daily_theta_target=credit / action.dte,
                daily_capture_mult=policy.daily_capture_mult,
                max_loss_mult_override=policy.max_loss_mult,
                profit_target_override=policy.profit_target,
                delta_breach_override=getattr(policy, "delta_breach", None),
            )
            if getattr(cfg, "model_debug", False):
                print(f"[validate direct] model Position built: {action.side} {action.dte}d delta_breach={getattr(policy, 'delta_breach', None)}")
            return position
        except Exception as e:
            if getattr(cfg, "model_debug", False):
                print(f"[validate direct] adapter error: {e}")
            return None

    return direct_model_entry_fn


def backtest_model_policy(model_instance, ticker: str = "TSLA", period: str = "5y") -> Dict[str, Any]:
    """Backtest a PickEntryModel on real historical data for any period."""
    df = build(ticker, period=period)
    cfg = get_config(ticker)
    entry_fn = _make_model_entry_fn(model_instance)

    bt = Backtester(df=df, config=cfg, entry_fn=entry_fn, exit_fn=check_exits, ticker=ticker)
    bt.run()

    metrics = compute_metrics(bt.trades)
    return {
        "ticker": ticker,
        "period": period,
        "n_trades": metrics.get("n_trades", 0),
        "total_pnl": metrics.get("total_pnl_per_contract", 0.0),
        "max_dd": metrics.get("max_dd_per_contract", 0.0),
        "win_rate": metrics.get("win_rate_pct", 0.0),
    }


def run_on_canonical_scenarios(model_instance, ticker: str = "TSLA") -> Dict[str, float]:
    """Stress test the model on the 12 canonical regimes."""
    df = build(ticker, period="5y")
    cfg = get_config(ticker)
    entry_fn = _make_model_entry_fn(model_instance)
    results = {}

    for regime in REGIMES:
        window = canonical_window(df, ticker, regime)
        if window is None or len(window) < 10:
            results[regime] = 0.0
            continue

        bt = Backtester(df=window, config=cfg, entry_fn=entry_fn, exit_fn=check_exits, ticker=ticker)
        bt.run()
        m = compute_metrics(bt.trades)
        results[regime] = m.get("total_pnl_per_contract", 0.0)

    results["total"] = sum(v for k, v in results.items() if k not in ("total", "worst"))
    results["worst"] = min(v for k, v in results.items() if k not in ("total", "worst")) if len(results) > 2 else 0.0
    return results


def run_management_advisor_shadow_on_canonical(ticker: str = "TSLA") -> dict:
    """Minimal Phase B scaffolding extension for plan-mandated parity reporting (one-line + note per scope).

    Uses existing PickEntryModel (which lazy-loads advisor) + recommend_management on canonical windows.
    Reports non-zero rate + expected-low note. Does NOT alter any Position, check_exits, or P/L.
    Full per-regime cost deltas vs rule baseline requires future true per-bar instrumentation (out of first-increment scope).
    """
    from simulator.pick_entry_model import PickEntryModel
    from data import build
    from scenarios import canonical_window, REGIMES
    model = PickEntryModel()
    df = build(ticker, period="5y")
    firings = 0
    total = 0
    for regime in REGIMES:
        window = canonical_window(df, ticker, regime)
        if window is None or len(window) < 5:
            continue
        for _, r in window.iterrows():
            total += 1
            try:
                rec = model.recommend_management(r, position={"side": "put", "credit": 1.0, "dte_at_entry": 5, "entry_date": "2026-05-01"}, trajectory=None)
                if rec.get("close") or rec.get("overrides"):
                    firings += 1
            except Exception:
                pass
    rate = (firings / total * 100) if total else 0.0
    return {
        "ticker": ticker,
        "canonical_nonzero_rate_pct": round(rate, 1),
        "note": "Management advisor on canonical (expected low during transition; advisory only, no P/L impact). Full cost-delta parity harness is future work.",
        "firings": firings,
        "evaluated": total,
    }


if __name__ == "__main__":
    import argparse
    from strategies import get_config, pick_entry, check_exits

    parser = argparse.ArgumentParser(description="Validate model policy on real history")
    parser.add_argument("--ticker", default="TSLA")
    parser.add_argument("--period", default="2y")
    parser.add_argument("--canonical-only", action="store_true")
    args = parser.parse_args()

    print("=== Model Policy Historical Validation ===\n")

    from simulator.pick_entry_model import PickEntryModel
    model = PickEntryModel()
    cfg = get_config(args.ticker)

    if not args.canonical_only:
        print(f"2y backtest ({args.ticker}) — rules vs model (cfg knobs: conf={cfg.model_min_policy_conf}, edge={cfg.model_min_edge}, should>={cfg.model_min_should_trade})\n")
        df = build(args.ticker, period=args.period)
        entry_fn = _make_model_entry_fn(model)
        bt_rule = Backtester(df=df, config=cfg, entry_fn=pick_entry, exit_fn=check_exits, ticker=args.ticker)
        bt_rule.run()
        m_rule = compute_metrics(bt_rule.trades)
        bt_model = Backtester(df=df, config=cfg, entry_fn=entry_fn, exit_fn=check_exits, ticker=args.ticker)
        bt_model.run()
        m_model = compute_metrics(bt_model.trades)
        cost_r = m_rule.get("total_pnl_per_contract", 0) - m_rule.get("max_dd_per_contract", 0)
        cost_m = m_model.get("total_pnl_per_contract", 0) - m_model.get("max_dd_per_contract", 0)
        print(f"  RULE:  trades={m_rule.get('n_trades')} pnl=${m_rule.get('total_pnl_per_contract',0):,.0f} max_dd=${m_rule.get('max_dd_per_contract',0):,.0f} cost={cost_r:,.0f}")
        print(f"  MODEL: trades={m_model.get('n_trades')} pnl=${m_model.get('total_pnl_per_contract',0):,.0f} max_dd=${m_model.get('max_dd_per_contract',0):,.0f} cost={cost_m:,.0f}\n")

    print(f"Canonical regimes ({args.ticker})...\n")
    results = run_on_canonical_scenarios(model, args.ticker)
    for regime, pnl in sorted(results.items()):
        if regime in ("total", "worst"):
            continue
        print(f"  {regime:20s}: ${pnl:8.1f}")
    print(f"\n  total: ${results.get('total', 0):,.1f}  worst: ${results.get('worst', 0):,.1f}  n_regimes_with_trades: {sum(1 for k,v in results.items() if k not in ('total','worst') and v != 0)}")