#!/usr/bin/env python3
"""Merge real backtest trade logs into a synthetic training parquet."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data import build
from simulator.feature_utils import build_model_features, _stable_regime_float
from simulator.trade_labeler import EntryAction, ManagementPolicy, CANONICAL_MGMT_POLICY_NAMES


def _nearest_row(df: pd.DataFrame, ts: pd.Timestamp) -> pd.Series | None:
    if ts in df.index:
        return df.loc[ts]
    idx = df.index.get_indexer([ts], method="nearest")
    if idx[0] < 0:
        return None
    return df.iloc[int(idx[0])]


def _infer_target_delta(side: str, strike: float, spot: float, dte: int) -> float:
    if spot <= 0 or strike <= 0:
        return 0.25 if side == "put" else 0.20
    m = abs(strike - spot) / spot
    if side == "put":
        return float(np.clip(0.15 + m * 2.5, 0.15, 0.40))
    return float(np.clip(0.15 + m * 2.0, 0.15, 0.35))


def trades_to_rows(ticker: str, trades_path: Path, period: str = "10y") -> pd.DataFrame:
    trades = pd.read_csv(trades_path)
    if trades.empty:
        return pd.DataFrame()

    trades["entry_date"] = pd.to_datetime(trades["entry_date"])
    feat_df = build(ticker, period=period)
    feat_df.index = pd.to_datetime(feat_df.index)

    records = []
    for i, tr in trades.iterrows():
        row = _nearest_row(feat_df, tr["entry_date"])
        if row is None:
            continue

        side = str(tr["side"])
        dte = int(tr["dte_at_entry"])
        spot = float(row["close"])
        strike = float(tr["strike"])
        delta = _infer_target_delta(side, strike, spot, dte)
        mcp = 0.012 if ticker == "TSLL" else 0.010

        action = EntryAction(side, dte, delta, min_credit_pct=mcp)
        pt = float(tr["profit_target_override"]) if pd.notna(tr.get("profit_target_override")) else 0.55
        ml = float(tr["max_loss_mult_override"]) if pd.notna(tr.get("max_loss_mult_override")) else (10.0 if ticker == "TSLL" else 1.8)
        dc = float(tr["daily_capture_mult"]) if pd.notna(tr.get("daily_capture_mult")) else 1.5
        db = float(tr["delta_breach_override"]) if pd.notna(tr.get("delta_breach_override")) else (0.45 if ticker == "TSLL" else 0.50)
        policy = ManagementPolicy("real_trade", profit_target=pt, max_loss_mult=ml, daily_capture_mult=dc, delta_breach=db)

        feats = build_model_features(row, action, policy)
        rec = feats.iloc[0].to_dict()

        pnl = float(tr["pnl_per_contract"])
        credit = float(tr["credit"])
        days_held = int(tr.get("days_held", dte) or dte)
        best_pol = "hold_longer" if pt >= 0.65 else "standard"
        rec.update({
            "path_id": -1000 - i,
            "ticker": ticker,
            "scenario_type": "real_backtest",
            "entry_index": 0,
            "side": side,
            "dte": dte,
            "target_delta": delta,
            "profit_target": pt,
            "max_loss_mult": ml,
            "daily_capture_mult": dc,
            "pnl_per_contract": pnl,
            "max_adverse": min(0.0, pnl * 0.5),
            "days_held": days_held,
            "exit_reason": str(tr.get("exit_reason", "unknown")),
            "needed_roll": bool(tr.get("is_roll", False)),
            "best_policy_for_path": best_pol,
            "oracle_best_pnl": pnl,
            "oracle_best_policy": best_pol,
            "regret_vs_oracle": 0.0,
            "decision_step": days_held,
            "current_pnl_pct": pnl / (credit * 100) if credit > 0 else 0.0,
            "current_pace_vs_target": 1.0,
            "days_held_norm": min(days_held / max(dte, 1), 1.5),
            "max_adverse_pct": min(0.0, pnl / (credit * 100)) if credit > 0 else 0.0,
            "is_gap_day": False,
            "regime_at_decision": _stable_regime_float(str(tr.get("regime_at_entry", row.get("regime", "")))),
            "ret_since_entry_1d": float(row.get("ret_1d", 0.0) or 0.0),
            "ret_since_entry_3d": float(row.get("ret_5d", 0.0) or 0.0) * 0.6,
            "iv_rank_at_decision": float(row.get("iv_rank", 50.0) or 50.0),
            "entry_spot": spot,
            "data_source": "real",
        })
        for name in CANONICAL_MGMT_POLICY_NAMES:
            rec.setdefault(f"mgmt_{name}", 1.0 if name == best_pol else 0.0)
        records.append(rec)

    return pd.DataFrame(records)


def merge_training_sets(
    synthetic_path: Path,
    output_path: Path,
    period: str = "10y",
    tickers: list[str] | None = None,
) -> Path:
    tickers = tickers or ["TSLA", "TSLL"]
    syn = pd.read_parquet(synthetic_path)
    syn = syn.loc[:, ~syn.columns.duplicated(keep="first")]
    if "data_source" not in syn.columns:
        syn["data_source"] = "synthetic"

    parts = [syn]
    for ticker in tickers:
        trades_path = Path(f".cache/{ticker}_trades.csv")
        if not trades_path.exists():
            print(f"  skip {ticker}: no {trades_path} (run: just backtest -- --dump-trades)")
            continue
        real = trades_to_rows(ticker, trades_path, period=period)
        print(f"  {ticker}: {len(real)} real trade rows from {trades_path.name}")
        if len(real):
            parts.append(real)

    merged = pd.concat(parts, ignore_index=True)
    merged = merged.loc[:, ~merged.columns.duplicated(keep="first")]
    if "regime_at_decision" in merged.columns:
        merged["regime_at_decision"] = merged["regime_at_decision"].map(
            lambda v: _stable_regime_float(v) if isinstance(v, str) else float(v) if pd.notna(v) else 0.0
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(output_path, index=False)

    n_real = int((merged["data_source"] == "real").sum()) if "data_source" in merged.columns else 0
    print(f"\nMerged {len(merged):,} rows ({n_real:,} real + {len(merged) - n_real:,} synthetic) -> {output_path}")
    if "regret_vs_oracle" in merged.columns:
        sub = merged[merged["data_source"] == "synthetic"] if "data_source" in merged.columns else merged
        zr = (sub["regret_vs_oracle"] == 0).mean() * 100
        print(f"Synthetic slice: mean regret ${sub['regret_vs_oracle'].mean():.1f} | zero-regret {zr:.1f}%")
    return output_path


def main():
    p = argparse.ArgumentParser(description="Union synthetic training parquet with real trade feature rows")
    p.add_argument("--synthetic", required=True, help="Input training parquet from build_training_set.py")
    p.add_argument("--output", required=True, help="Merged output parquet")
    p.add_argument("--period", default="10y", help="History window for feature join on real trades")
    p.add_argument("--tickers", nargs="+", default=["TSLA", "TSLL"])
    args = p.parse_args()
    merge_training_sets(Path(args.synthetic), Path(args.output), period=args.period, tickers=args.tickers)


if __name__ == "__main__":
    main()