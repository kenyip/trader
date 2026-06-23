#!/usr/bin/env python3
"""Sweep model_min_policy_conf × model_min_should_trade on real history (2y default)."""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pricing
from data import build
from backtest import Backtester, compute_metrics, Position
from strategies import check_exits, get_config, pick_entry
from simulator.pick_entry_model import PickEntryModel


def model_entry_fn_factory(model: PickEntryModel, cfg):
    def entry_fn(row, _cfg, S, today):
        recs = model.recommend(
            row,
            min_policy_conf=cfg.model_min_policy_conf,
            min_edge=cfg.model_min_edge,
            min_should_trade=cfg.model_min_should_trade,
            use_should_trade_gate=True,
            debug=False,
        )
        if not recs:
            return None
        best = recs[0]
        action = best.entry_action
        policy = best.recommended_policy
        T = action.dte / 365.0
        iv = float(row.get("iv_proxy", 0.55))
        K = pricing.strike_from_delta(S, T, iv, action.target_delta, action.side, r=_cfg.risk_free_rate)
        K = pricing.round_strike(K, 2.5)
        credit = pricing.price(S, K, T, iv, action.side, r=_cfg.risk_free_rate)
        if credit / K < max(action.min_credit_pct, 0.008):
            return None
        exp = today + pd.Timedelta(days=action.dte)
        return Position(
            side=action.side, entry_date=today, expiration=exp, strike=K, credit=credit,
            dte_at_entry=action.dte, iv_at_entry=iv, regime_at_entry=str(row.get("regime", "")),
            daily_theta_target=credit / action.dte, daily_capture_mult=policy.daily_capture_mult,
            max_loss_mult_override=policy.max_loss_mult,
            profit_target_override=policy.profit_target,
            delta_breach_override=policy.delta_breach,
        )
    return entry_fn


def run_once(ticker: str, period: str, conf: float, should: float, df, model, rule_metrics):
    cfg = get_config(ticker, model_min_policy_conf=conf, model_min_should_trade=should, model_min_edge=0.0)
    bt = Backtester(df=df, config=cfg, entry_fn=model_entry_fn_factory(model, cfg),
                    exit_fn=check_exits, ticker=ticker)
    bt.run()
    m = compute_metrics(bt.trades)
    cost = m.get("total_pnl_per_contract", 0) - m.get("max_dd_per_contract", 0)
    rule_cost = rule_metrics["cost"]
    return {
        "conf": conf, "should": should,
        "n_trades": m.get("n_trades", 0),
        "pnl": m.get("total_pnl_per_contract", 0),
        "max_dd": m.get("max_dd_per_contract", 0),
        "cost": cost,
        "delta_vs_rule": cost - rule_cost,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ticker", default="TSLA")
    p.add_argument("--period", default="2y")
    p.add_argument("--conf", default="0.35,0.40,0.45,0.50,0.55")
    p.add_argument("--should", default="0.55,0.58,0.60,0.62,0.65")
    args = p.parse_args()

    confs = [float(x) for x in args.conf.split(",")]
    shoulds = [float(x) for x in args.should.split(",")]

    print(f"Loading model + {args.period} data for {args.ticker}...")
    model = PickEntryModel()
    df = build(args.ticker, period=args.period)
    cfg = get_config(args.ticker)
    bt = Backtester(df=df, config=cfg, entry_fn=pick_entry, exit_fn=check_exits, ticker=args.ticker)
    bt.run()
    rm = compute_metrics(bt.trades)
    rule = {"n_trades": rm.get("n_trades"), "pnl": rm.get("total_pnl_per_contract", 0),
            "max_dd": rm.get("max_dd_per_contract", 0),
            "cost": rm.get("total_pnl_per_contract", 0) - rm.get("max_dd_per_contract", 0)}
    print(f"RULE baseline: trades={rule['n_trades']} pnl=${rule['pnl']:,.0f} max_dd=${rule['max_dd']:,.0f} cost={rule['cost']:,.0f}\n")

    rows = []
    for c in confs:
        for s in shoulds:
            r = run_once(args.ticker, args.period, c, s, df, model, rule)
            rows.append(r)
            print(f"conf={c:.2f} should={s:.2f}  trades={r['n_trades']:3d}  pnl=${r['pnl']:7,.0f}  "
                  f"max_dd=${r['max_dd']:6,.0f}  cost={r['cost']:8,.0f}  Δrule={r['delta_vs_rule']:+,.0f}")

    best = max(rows, key=lambda x: x["cost"])
    print(f"\nBest cost: conf={best['conf']} should={best['should']} cost={best['cost']:,.0f} "
          f"(trades={best['n_trades']}, max_dd=${best['max_dd']:,.0f})")


if __name__ == "__main__":
    main()