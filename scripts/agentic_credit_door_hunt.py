#!/usr/bin/env python3
"""Paper-only agentic-sleeve credit-door hunt. Never places orders.

Reads a live/last-RTH NBBO snapshot, applies defined-risk DNA gates, optionally
runs dollar backtests through trader_platform.research.pcs_sim (MODEL), and
writes RESULT.json / SUMMARY.md / CROWN.json.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


MIN_CREDIT_PCT = 0.10
MAX_ABS_DELTA = 0.30
MIN_IVR = 20.0
MAX_LOCK_USD = 855.0
MAX_HALF_SPREAD_FRAC = 0.40
MIN_NATURAL_CREDIT = 0.05
MULTIPLIER = 100.0

DISCARD_PRIMARY = frozenset(
    {
        "TRGP",
        "MPC",
        "PSX",
        "VLO",
        "INTU",
        "HUM",
        "CAT",
        "DE",
        "V",
        "PFE",
        "REGN",
        "AMGN",
        "LNG",
        "LOW",
        "TGT",
        "BMY",
    }
)
DISCARD_UNLESS_NEW_STRIKE = frozenset({"DG", "JNJ", "MRK"})
DISCARD_CCS_ONLY = frozenset({"MCD", "XOM"})
DISCARD_BANKS = frozenset(
    {"JPM", "BAC", "WFC", "C", "USB", "PNC", "TFC", "COF", "GS", "MS", "BK", "STT"}
)

MRK_MEASURED = {
    "symbol": "MRK",
    "structure": "put_credit_spread",
    "label": "MEASURED",
    "avg_pnl_usd": 27.08,
    "n": 15,
    "note": "prior-cell paper champion; lock not in this checkout",
}
OKE_OCCUPANT = {
    "symbol": "OKE",
    "structure": "bull_call_debit",
    "expiry": "2026-10-16",
    "strikes": [100.0, 105.0],
    "net_debit": 1.40,
    "long": {"strike": 100.0, "avg": 2.25},
    "short": {"strike": 105.0, "avg": 0.85},
    "label": "KEEP",
    "avg1_usd": 37.57,
    "n": 19,
}

DEFAULT_AS_OF = "2026-09-03"


def _f(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def lock_usd(width: float, credit: float) -> float:
    return max(float(width) - float(credit), 0.0) * MULTIPLIER


def sendable_roc(avg_pnl_usd: float, lock: float) -> float | None:
    if lock <= 0:
        return None
    return float(avg_pnl_usd) / float(lock)


def mid(bid: float, ask: float) -> float:
    if bid > 0 and ask > 0:
        return (bid + ask) / 2.0
    return max(bid, ask, 0.0)


def quote_inverted(bid: float, ask: float) -> bool:
    return bid > 0 and ask > 0 and ask < bid


def half_spread(bid: float, ask: float) -> float:
    if bid <= 0 or ask <= 0:
        return float("inf")
    return max(ask - bid, 0.0) / 2.0


def natural_credit(*, structure: str, short_bid: float, long_ask: float) -> float:
    return float(short_bid) - float(long_ask)


def discard_reason(symbol: str, structure: str, *, new_strike_or_expiry: bool) -> str | None:
    sym = symbol.upper()
    struct = structure.lower()
    if sym in DISCARD_BANKS:
        return "discard_banks"
    if sym in DISCARD_PRIMARY:
        return "discard_prior_hunt"
    if sym in DISCARD_CCS_ONLY and "call_credit" in struct:
        return "discard_ccs_only"
    if sym in DISCARD_UNLESS_NEW_STRIKE and not new_strike_or_expiry:
        return "discard_unless_new_strike_expiry"
    return None


def evaluate_structure(row: dict[str, Any], *, cash_usd: float, lock_cap_usd: float) -> dict[str, Any]:
    """Apply hard DNA. Pure; no network."""
    gates: dict[str, bool] = {}
    fails: list[str] = []

    symbol = str(row.get("symbol") or "").upper()
    structure = str(row.get("structure") or "")
    expiry = str(row.get("expiry") or "")
    short_k = _f(row.get("short_strike"))
    long_k = _f(row.get("long_strike"))
    width = abs(short_k - long_k)
    short_bid = _f(row.get("short_bid"))
    short_ask = _f(row.get("short_ask"))
    long_bid = _f(row.get("long_bid"))
    long_ask = _f(row.get("long_ask"))
    delta = abs(_f(row.get("short_delta")))
    ivr = row.get("ivr")
    ivr_f = None if ivr is None else _f(ivr)
    earnings = row.get("earnings")
    as_of = str(row.get("as_of") or DEFAULT_AS_OF)
    new_strike = bool(row.get("new_strike_or_expiry"))

    discarded = discard_reason(symbol, structure, new_strike_or_expiry=new_strike)
    gates["not_discarded"] = discarded is None
    if discarded:
        fails.append(discarded)

    gates["width_positive"] = width > 0
    if width <= 0:
        fails.append("width_zero")

    inverted = quote_inverted(short_bid, short_ask) or quote_inverted(long_bid, long_ask)
    gates["not_inverted"] = not inverted
    if inverted:
        fails.append("nbbo_inverted")

    gates["short_bid_live"] = short_bid > 0
    if short_bid <= 0:
        fails.append("short_bid_dead")
    gates["long_ask_live"] = long_ask > 0
    if long_ask <= 0:
        fails.append("long_ask_dead")

    credit = natural_credit(structure=structure, short_bid=short_bid, long_ask=long_ask)
    credit_pct = (credit / width) if width > 0 else 0.0
    gates["min_credit"] = credit >= MIN_NATURAL_CREDIT
    gates["width_not_skinny"] = credit_pct + 1e-12 >= MIN_CREDIT_PCT
    if credit < MIN_NATURAL_CREDIT:
        fails.append("credit_too_small")
    if credit_pct + 1e-12 < MIN_CREDIT_PCT:
        fails.append("width_skinny")

    combined_hs = half_spread(short_bid, short_ask) + half_spread(long_bid, long_ask)
    hs_frac = combined_hs / credit if credit > 0 else float("inf")
    gates["fillable_width_vs_premium"] = hs_frac <= MAX_HALF_SPREAD_FRAC
    if hs_frac > MAX_HALF_SPREAD_FRAC:
        fails.append("spread_vs_premium")

    gates["delta_not_hot"] = 0 < delta <= MAX_ABS_DELTA
    if delta <= 0:
        fails.append("delta_missing")
    elif delta > MAX_ABS_DELTA:
        fails.append("delta_hot")

    if ivr_f is None:
        gates["ivr_not_dead"] = False
        fails.append("ivr_unknown")
    else:
        gates["ivr_not_dead"] = ivr_f >= MIN_IVR
        if ivr_f < MIN_IVR:
            fails.append("ivr_dead")

    earn_date = None
    if earnings:
        earn_date = str(earnings)
    gates["earnings_outside_hold"] = True
    if earn_date:
        try:
            e = date.fromisoformat(earn_date[:10])
            start = date.fromisoformat(as_of[:10])
            end = date.fromisoformat(expiry[:10]) if expiry else start
            inside = start <= e <= end
            gates["earnings_outside_hold"] = not inside
            if inside:
                fails.append("earnings_inside_hold")
        except ValueError:
            gates["earnings_outside_hold"] = False
            fails.append("earnings_unparseable")

    lock = lock_usd(width, credit)
    gates["lock_under_cap"] = lock <= lock_cap_usd + 1e-9
    if lock > lock_cap_usd + 1e-9:
        fails.append("lock_over_cash")

    long_debit_usd = long_ask * MULTIPLIER
    gates["one_leg_cash_fit"] = long_debit_usd <= cash_usd + 1e-9
    if long_debit_usd > cash_usd + 1e-9:
        fails.append("long_leg_cash_fail")

    defined = True
    gates["defined_risk"] = defined
    if str(row.get("naked") or "").lower() in {"1", "true", "yes"}:
        gates["defined_risk"] = False
        fails.append("naked_short")

    passed = all(gates.values())
    return {
        "symbol": symbol,
        "structure": structure,
        "expiry": expiry,
        "short_strike": short_k,
        "long_strike": long_k,
        "width": round(width, 4),
        "natural_credit": round(credit, 4),
        "credit_pct_of_width": round(credit_pct, 4),
        "lock_usd": round(lock, 2),
        "long_debit_usd": round(long_debit_usd, 2),
        "short_delta_abs": round(delta, 4),
        "ivr": None if ivr_f is None else round(ivr_f, 1),
        "earnings": earn_date,
        "half_spread_frac": None if not math.isfinite(hs_frac) else round(hs_frac, 4),
        "gates": gates,
        "fails": fails,
        "dna_pass": passed,
        "scale_ticket": {
            "lock_1lot_usd": round(lock, 2),
            "lots_at_3k": int(3000 // lock) if lock > 0 else 0,
            "lots_at_10k": int(10000 // lock) if lock > 0 else 0,
            "note": "scale lock is 1-lot defined max loss; wire capital before adding lots",
        },
    }


def crown_decision(
    survivors: list[dict[str, Any]],
    *,
    mrk_measured: dict[str, Any] = MRK_MEASURED,
    mrk_model_roc: float | None,
    mrk_model_lock: float | None,
) -> dict[str, Any] | None:
    """Crown only if sendable ROC beats MRK and the ticket is fillable under the cash cap."""
    measured_lock = mrk_model_lock if mrk_model_lock and mrk_model_lock > 0 else 400.0
    measured_roc = sendable_roc(float(mrk_measured["avg_pnl_usd"]), measured_lock)
    bar = measured_roc or 0.0
    if mrk_model_roc is not None:
        bar = max(bar, mrk_model_roc)

    best: dict[str, Any] | None = None
    best_roc = -1.0
    for row in survivors:
        if not row.get("dna_pass"):
            continue
        if not row.get("fillable_under_855"):
            continue
        avg = row.get("model_avg_pnl_usd")
        lock = _f(row.get("lock_usd"))
        n = int(row.get("model_n") or 0)
        if avg is None or lock <= 0 or n <= 0:
            continue
        roc = sendable_roc(float(avg), lock)
        if roc is None or roc <= bar:
            continue
        if roc > best_roc:
            best_roc = roc
            best = {
                "symbol": row["symbol"],
                "structure": row["structure"],
                "expiry": row.get("expiry"),
                "short_strike": row.get("short_strike"),
                "long_strike": row.get("long_strike"),
                "lock_usd": lock,
                "natural_credit": row.get("natural_credit"),
                "model_avg_pnl_usd": avg,
                "model_n": n,
                "sendable_roc": round(roc, 4),
                "beat_mrk_bar_roc": round(bar, 4),
                "mrk_measured_avg": mrk_measured["avg_pnl_usd"],
                "mrk_measured_n": mrk_measured["n"],
                "reason": (
                    f"{row['symbol']} {row['structure']} sendable ROC {roc:.3%} "
                    f"beats MRK bar {bar:.3%} and is fillable under $855"
                ),
            }
    return best


def _model_backtest(symbol: str, structure: str, width: float, delta: float, dte: int) -> dict[str, Any]:
    from trader_platform.research.pcs_sim import run_pcs_backtest

    cfg = {
        "structure": structure,
        "long_dte": max(int(dte), 14),
        "long_target_delta": min(max(abs(delta), 0.12), 0.28),
        "spread_width": float(width),
        "min_credit_pct": MIN_CREDIT_PCT,
        "max_loss_budget_usd": MAX_LOCK_USD,
        "profit_target": 0.50,
        "defined_loss_exit_frac": 0.85,
        "delta_breach": 0.45,
        "dte_stop": 5,
        "iv_rank_min": 0.0,
        "bear_dte": 0,
        "call_in_bull_ok": structure == "call_credit_spread",
        "regime_flip_exit_enabled": True,
        "half_spread_per_leg": 0.02,
        "slippage_pct": 0.0,
    }
    result = run_pcs_backtest(
        symbol,
        period="5y",
        use_cache=True,
        config=cfg,
        sleeve_usd=3000.0,
        open_risk_budget_usd=MAX_LOCK_USD,
        structure=structure,
    )
    metrics = result.metrics or {}
    return {
        "ok": bool(result.ok),
        "skipped": bool(result.skipped),
        "reason": result.reason,
        "label": "MODEL",
        "n": int(metrics.get("n_trades") or result.n_trades or 0),
        "avg_pnl_usd": round(float(metrics.get("avg_pnl_per_contract") or 0.0), 2),
        "total_pnl_usd": round(float(metrics.get("total_pnl_per_contract") or 0.0), 2),
        "win_rate_pct": round(float(metrics.get("win_rate_pct") or 0.0), 1),
        "max_dd_usd": round(float(metrics.get("max_dd_per_contract") or 0.0), 2),
        "profit_factor": metrics.get("profit_factor"),
        "avg_max_loss_usd": round(float(metrics.get("avg_max_loss_usd") or 0.0), 2),
        "avg_days_held": round(float(metrics.get("avg_days_held") or 0.0), 1),
        "engine": "pcs_sim.run_pcs_backtest",
        "period": "5y",
        "config": {
            "long_dte": cfg["long_dte"],
            "spread_width": cfg["spread_width"],
            "long_target_delta": cfg["long_target_delta"],
            "min_credit_pct": cfg["min_credit_pct"],
            "max_loss_budget_usd": cfg["max_loss_budget_usd"],
            "half_spread_per_leg": cfg["half_spread_per_leg"],
        },
    }


def _ivr_from_engine(symbol: str) -> float | None:
    try:
        from data import build
    except Exception:
        return None
    try:
        df = build(symbol, period="5y", use_cache=True)
    except Exception:
        return None
    if df is None or df.empty or "iv_rank" not in df.columns:
        return None
    val = df["iv_rank"].iloc[-1]
    try:
        out = float(val)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _dte(as_of: str, expiry: str) -> int:
    try:
        return (date.fromisoformat(expiry[:10]) - date.fromisoformat(as_of[:10])).days
    except ValueError:
        return 43


def load_snapshot(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_hunt(
    snapshot: dict[str, Any],
    *,
    backtest: bool = False,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    cash = _f(snapshot.get("cash_usd"), 854.90)
    live_bp = _f(snapshot.get("buying_power_usd"), 784.86)
    lock_cap = _f(snapshot.get("lock_cap_usd"), MAX_LOCK_USD)
    as_of = str(snapshot.get("as_of") or DEFAULT_AS_OF)
    book = snapshot.get("book") or {}
    candidates = list(snapshot.get("candidates") or [])

    evaluated: list[dict[str, Any]] = []
    for raw in candidates:
        row = dict(raw)
        row.setdefault("as_of", as_of)
        if backtest and row.get("ivr") is None:
            ivr = _ivr_from_engine(str(row.get("symbol") or ""))
            if ivr is not None:
                row["ivr"] = ivr
                row["ivr_source"] = "MODEL data.py iv_rank"
        scored = evaluate_structure(row, cash_usd=cash, lock_cap_usd=lock_cap)
        scored["fillable_under_855"] = bool(
            scored["dna_pass"] and scored["lock_usd"] <= MAX_LOCK_USD + 1e-9
        )
        scored["coexist_vs_live_bp"] = scored["lock_usd"] <= live_bp + 1e-9
        scored["quote"] = {
            "short_bid": row.get("short_bid"),
            "short_ask": row.get("short_ask"),
            "long_bid": row.get("long_bid"),
            "long_ask": row.get("long_ask"),
            "implied_vol": row.get("implied_vol"),
        }
        scored["notes"] = list(row.get("notes") or [])
        scored["new_strike_or_expiry"] = bool(row.get("new_strike_or_expiry"))
        scored["ivr_source"] = row.get("ivr_source")
        if backtest and scored.get("dna_pass"):
            model = _model_backtest(
                scored["symbol"],
                scored["structure"],
                scored["width"],
                scored["short_delta_abs"],
                _dte(as_of, scored["expiry"]),
            )
            scored["model"] = model
            scored["model_avg_pnl_usd"] = model.get("avg_pnl_usd")
            scored["model_n"] = model.get("n")
            roc = sendable_roc(_f(model.get("avg_pnl_usd")), scored["lock_usd"])
            scored["model_sendable_roc"] = None if roc is None else round(roc, 4)
        evaluated.append(scored)

    mrk_rows = [r for r in evaluated if r["symbol"] == "MRK" and r["structure"] == "put_credit_spread"]
    mrk_model_roc = None
    mrk_model_lock = None
    if mrk_rows and mrk_rows[0].get("model_n"):
        mrk_model_roc = sendable_roc(_f(mrk_rows[0].get("model_avg_pnl_usd")), _f(mrk_rows[0].get("lock_usd")))
        mrk_model_lock = _f(mrk_rows[0].get("lock_usd"))

    survivors = [r for r in evaluated if r.get("dna_pass")]
    crown = crown_decision(
        evaluated,
        mrk_model_roc=mrk_model_roc,
        mrk_model_lock=mrk_model_lock,
    )

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of": as_of,
        "mode": "analysis_only",
        "live_orders": False,
        "account": {
            "nickname": "Agentic",
            "masked": "••••8507",
            "cash_usd": cash,
            "buying_power_usd": live_bp,
            "account_value_usd": snapshot.get("account_value_usd"),
            "lock_cap_usd": lock_cap,
            "note": "live BP is lower than cash while OKE occupies the book",
        },
        "occupant": {**OKE_OCCUPANT, **book},
        "working_orders_readonly": snapshot.get("working_orders") or [],
        "incumbents": {
            "mrk_pcs_measured": MRK_MEASURED,
            "oke_debit_keep": OKE_OCCUPANT,
        },
        "dna": {
            "min_credit_pct_of_width": MIN_CREDIT_PCT,
            "max_abs_delta": MAX_ABS_DELTA,
            "min_ivr": MIN_IVR,
            "max_lock_usd": MAX_LOCK_USD,
            "max_half_spread_frac_of_credit": MAX_HALF_SPREAD_FRAC,
            "one_leg": "BUY long first; leftover long is defined = debit paid",
            "defined_risk_only": True,
        },
        "candidates": evaluated,
        "survivors": [
            {
                "symbol": r["symbol"],
                "structure": r["structure"],
                "expiry": r["expiry"],
                "short_strike": r["short_strike"],
                "long_strike": r["long_strike"],
                "natural_credit": r["natural_credit"],
                "lock_usd": r["lock_usd"],
                "coexist_vs_live_bp": r["coexist_vs_live_bp"],
                "model_avg_pnl_usd": r.get("model_avg_pnl_usd"),
                "model_n": r.get("model_n"),
                "model_sendable_roc": r.get("model_sendable_roc"),
            }
            for r in survivors
        ],
        "crown": crown,
        "labels": {
            "MODEL": "pcs_sim Black-Scholes daily marks via this repo engine",
            "MEASURED": "prior-cell paper/live NBBO result, not re-simulated here",
        },
    }

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "RESULT.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        (out_dir / "CROWN.json").write_text(json.dumps(crown, indent=2) + "\n", encoding="utf-8")
        (out_dir / "SUMMARY.md").write_text(render_summary(result), encoding="utf-8")
    return result


def render_summary(result: dict[str, Any]) -> str:
    acct = result["account"]
    crown = result.get("crown")
    lines = [
        "# Agentic sleeve — next credit door (analysis only)",
        "",
        f"As-of **{result['as_of']}**. No live orders. Multi-leg send is rejected on this sleeve; 1-leg LIMIT only.",
        "",
        "## Crown",
        "",
    ]
    if crown:
        lines.append(
            f"**CROWN: {crown['symbol']} {crown['structure']} "
            f"{crown['expiry']} {crown['short_strike']}/{crown['long_strike']}**"
        )
        lines.append("")
        lines.append(crown["reason"])
        lines.append("")
        lines.append(
            f"Lock ${crown['lock_usd']:.2f} · MODEL avg ${crown['model_avg_pnl_usd']:.2f} "
            f"n={crown['model_n']} · sendable ROC {crown['sendable_roc']:.2%}"
        )
    else:
        lines.append(
            "**CROWN: null.** No survivor beat MRK on sendable ROC while staying fillable under $855."
        )
        lines.append("")
        lines.append(
            f"MRK MEASURED remains the paper credit champion: +${MRK_MEASURED['avg_pnl_usd']:.2f} "
            f"n={MRK_MEASURED['n']}. Live MRK Oct-16 140/135 is a *new* strike (allowed) but is not crowned "
            "unless MODEL ROC clears that bar."
        )
    lines.extend(
        [
            "",
            "## Live book (do not add a second cash-fail lot)",
            "",
            f"- Agentic ••••8507: cash ${acct['cash_usd']:.2f}, BP ${acct['buying_power_usd']:.2f}, "
            f"account ${acct.get('account_value_usd')}.",
            "- Occupant: OKE Oct-16 2026 100/105 bull-call debit, net 1.40 (long 100C @2.25, short 105C @0.85).",
            "- Working GTC BTC on the short 105C at 0.70 (agentic, confirmed, unfilled) — left untouched.",
            "- Free BP today cannot fund an ~$880 second lot (MPC 340/330 class). Coexist requires lock ≤ live BP.",
            "",
            "## DNA",
            "",
            "- Defined risk only. BUY the long wing first so a missed short leaves a long option, not a naked short.",
            f"- Credit/width ≥ {MIN_CREDIT_PCT:.0%}; |Δ| ≤ {MAX_ABS_DELTA:.2f}; IVR ≥ {MIN_IVR:.0f}; "
            f"combined half-spread ≤ {MAX_HALF_SPREAD_FRAC:.0%} of credit; earnings outside the hold; lock ≤ ${MAX_LOCK_USD:.0f}.",
            "- Discard list honored (TRGP, refiners, INTU/HUM, CAT/DE, DG/JNJ/MRK unless new strike/expiry, "
            "MCD CCS, V, PFE, XOM CCS, banks, REGN/AMGN, LNG, stale Aug-26 LOW/TGT/BMY).",
            "",
            "## Candidates",
            "",
            "| Name | Struct | Expiry | Strikes | Credit | Lock | Δ | DNA | MODEL avg (n) | ROC |",
            "|---|---|---|---|---:|---:|---:|---|---:|---:|",
        ]
    )
    for row in result["candidates"]:
        model = ""
        roc = ""
        if row.get("model_n"):
            model = f"${row.get('model_avg_pnl_usd'):.2f} n={row['model_n']}"
            if row.get("model_sendable_roc") is not None:
                roc = f"{row['model_sendable_roc']:.2%}"
        dna = "PASS" if row.get("dna_pass") else ",".join(row.get("fails") or ["fail"])
        lines.append(
            f"| {row['symbol']} | {row['structure']} | {row.get('expiry','')} | "
            f"{row.get('short_strike')}/{row.get('long_strike')} | "
            f"{row.get('natural_credit')} | ${row.get('lock_usd')} | "
            f"{row.get('short_delta_abs')} | {dna} | {model} | {roc} |"
        )
    lines.extend(
        [
            "",
            "## Labels",
            "",
            "- **MODEL** = `pcs_sim.run_pcs_backtest` Black-Scholes daily marks (this engine). Not fills.",
            "- **MEASURED** = prior-cell paper/live NBBO result. MRK +$27.08 n=15 is MEASURED.",
            "- n is printed on every average.",
            "",
            "## Scale ticket",
            "",
            "Think in 1-lot defined max loss, then add lots only after Ken wires. "
            "Today's sleeve sizes to $855 post-OKE-flat, ~$785 while OKE is on.",
            "",
            "## Authority",
            "",
            "Analysis only. No `place_option_order`. No arm. No main-account use.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshot", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--backtest", action="store_true", help="Run MODEL dollar backtests via pcs_sim")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    snapshot = load_snapshot(args.snapshot)
    run_hunt(snapshot, backtest=bool(args.backtest), out_dir=args.out_dir)
    print(f"wrote {args.out_dir}/RESULT.json SUMMARY.md CROWN.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
