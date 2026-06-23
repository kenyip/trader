#!/usr/bin/env python3
"""
Strategy layer: entry signals + exit ladder.

Single-leg short premium. The classifier in data.py picks one side per evaluation;
this module turns that signal into a Position and manages it through the exit
ladder. No state held outside Position itself — the engine re-evaluates every bar.

Exit ladder (first to fire wins, checked in this order):
    1. expiration           T <= 0  →  settle intrinsic
    2. max loss             pnl <= -max_loss_mult * credit
    3. daily profit capture pnl/days >= daily_capture_mult * (credit / dte_at_entry)
    4. profit target        pnl >= profit_target * credit
    5. delta breach         |delta| > delta_breach
    6. DTE stop             dte_remaining <= dte_stop (longer-dated only)
    7. regime flip          puts close on reversal/bearish; calls close on bullish
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Optional
import numpy as np
import pandas as pd

import pricing
from backtest import Position


@dataclass
class StrategyConfig:
    # entry filter
    iv_rank_min: float = 10.0           # skip if iv_rank below this
    min_credit_pct: float = 0.010       # v1.3: skip if credit / strike < this (1.0% floor; swept best for both tickers)

    # default ("long-dated") trade — used outside reversal/high-iv
    long_target_delta: float = 0.15     # v1.1: walk-forward modal (6/11 windows)
    long_dte: int = 30

    # defensive trade — used on reversal or high_iv (in non-bearish regimes)
    short_target_delta: float = 0.17
    short_dte: int = 7

    # bearish-regime trade — symmetric to the long-put trade, but sells a call.
    # `bear_dte = 0` means disabled (legacy stand-aside behavior). Any positive
    # value enables the call branch in bearish regimes with these parameters.
    bear_dte: int = 0
    bear_target_delta: float = 0.20

    # exits
    profit_target: float = 0.55         # fraction of credit
    max_loss_mult: float = 1.8          # in multiples of credit
    delta_breach: float = 0.38          # |delta| trigger
    dte_stop: int = 21                  # close longer trades at this DTE
    dte_stop_min_entry: int = 14        # only apply dte_stop for entries above this
    regime_flip_exit_enabled: bool = True   # when False, only profit-side + max_loss + delta_breach fire (regime-change doesn't close)

    # daily profit capture multipliers, picked at entry by DTE bucket
    daily_capture_mult_short: float = 1.0   # DTE <= 7
    daily_capture_mult_mid: float = 1.5     # DTE 8 – 15
    daily_capture_mult_long: float = 1.5    # v1.1: walk-forward consensus (10/11 windows)

    # execution
    slippage_pct: float = 0.0           # applied to every exit fill
    gap_slippage_mult: float = 0.15     # v1.3: extra slippage on max_loss exits after a gap day
    gap_threshold_pct: float = 0.03     # v1.3: overnight |gap| that triggers gap_slippage_mult
    risk_free_rate: float = 0.04

    # wheel mechanic (v1.4) — accept put assignment, sell aggressive covered calls
    wheel_enabled: bool = False         # off by default — existing backtests unchanged
    cc_dte: int = 14                    # DTE for covered calls (shorter than puts → more cycles)
    cc_target_delta: float = 0.30       # used only if cc_strike_mode == 'delta'
    cc_strike_mode: str = 'basis'       # 'basis' (aggressive, sell AT basis to cycle out) | 'delta'
    wheel_put_dte: int = 14             # DTE for wheel-mode puts (shorter than long_dte=30 → less time for regime_flip to fire before expiration)
    wheel_put_max_loss_mult: float = 3.0  # override max_loss_mult for wheel-mode puts; ≥3.0 lets puts survive deeper before stopping out
    wheel_skip_regime_flip: bool = True   # in wheel mode, don't close puts on bearish regime — accept assignment instead

    # roll-on-max_loss (v1.11) — when max_loss fires, attempt a credit roll instead of leaving flat
    roll_on_max_loss: bool = False      # off by default — preserves v1.10 behavior
    roll_dte: int = 14                  # DTE of the rolled position (longer = more theta room to recover)
    roll_target_delta: float = 0.15     # delta of the rolled strike (lower than entry → further OTM)
    roll_credit_ratio: float = 1.0      # require new_credit >= roll_credit_ratio × close_cost (1.0 = credit roll)
    # v1.10 — trade-group cap policy. A "chain" is one originating entry + up to
    # max_rolls_per_group rolls. max_chain_loss_mult bounds total realized loss
    # across the chain (relative to the first position's credit). When either is
    # exceeded the chain accepts the loss and terminates; a fresh entry starts a
    # new group on the next bar.
    max_rolls_per_group: int = 1        # legacy: 1 keeps v1.11 single-roll behavior
    max_chain_loss_mult: float = 2.0    # hard cap on cumulative chain loss in multiples of first credit

    # adaptive rules (v1.11) — extension point for context-aware knob adjustment
    # at pick_entry time. Each rule is a function (row, cfg, current) -> dict that
    # may modify the per-entry params or set 'skip': True. Default = no rules =
    # behavior identical to v1.10. Rules are registered in `ADAPTIVE_RULES`.
    adaptive_rules: tuple = ()
    # v1.13 — exit-side adaptive rules. Each rule is a function
    # (position, mark, row, cfg) -> dict. May return {'close': True, 'reason': str}
    # to close the position with a custom reason. Empty dict = no-op (defer to
    # the standard ladder). Rules are registered in `ADAPTIVE_EXIT_RULES`.
    # When set, exit rules fire BEFORE the standard ladder (highest priority).
    exit_rules: tuple = ()
    ticker: str = ''                    # set by get_config so rules can branch per-ticker without re-plumbing

    # === PR 2 model-driven entry knobs (safe defaults; only affect experimental model path) ===
    # enable_model_entry=False keeps the main rule path (pick_entry + adapt_entry_params + ADAPTIVE_RULES) 100% untouched.
    enable_model_entry: bool = False
    model_min_should_trade: float = 0.55   # first cheap gate (should_trade prob must be >= this)
    model_min_policy_conf: float = 0.35    # policy model confidence filter
    model_min_edge: float = 0.0            # P/L edge filter (only if PICK_ENTRY_USE_PL=1 and pl model loaded)
    model_debug: bool = False              # rich per-decision prints in model path
    model_best_policy_path: Optional[str] = None  # for pinning a specific model file
    model_should_trade_path: Optional[str] = None

    # === Phase C: model-driven management (close/roll re-scoring via trajectory features) ===
    # enable_model_management=False (default) keeps 100% rule path: check_exits + ADAPTIVE_EXIT_RULES + ladder.
    # When True (lab only), after ladder the advisor may propose overrides or early-close signals.
    # Proposals feed adapt_exit hook or are surfaced read-only (positions tracker, what-if).
    # No behavior change to backtest/scenarios/live until distilled or explicitly enabled + validated.
    enable_model_management: bool = False
    model_min_management_conf: float = 0.30  # advisor confidence gate (PR 2 pattern)
    model_min_mgmt_edge: float = 4.0         # expected improvement $ gate
    model_management_path: Optional[str] = None  # pin specific advisor model


# v1.5: per-ticker defaults from the DTE × delta sweep on 5y backtest + 12-regime suite validation.
# Different underlyings have different optimal entry params (TSLL is 2x-leveraged, smaller price,
# higher relative IV → shorter DTE / higher delta is the sweet spot).
DEFAULT_CONFIG_BY_TICKER = {
    'TSLA': {'long_dte': 7,  'long_target_delta': 0.20, 'min_credit_pct': 0.010, 'delta_breach': 0.50, 'daily_capture_mult_short': 2.0, 'bear_dte': 3, 'bear_target_delta': 0.20, 'regime_flip_exit_enabled': False, 'adaptive_rules': ('tsla_skip_mild_intraday_up',), 'model_min_should_trade': 0.58, 'model_min_policy_conf': 0.40},
    'TSLL': {'long_dte': 3,  'long_target_delta': 0.30, 'min_credit_pct': 0.012, 'delta_breach': 0.45, 'daily_capture_mult_short': 1.25, 'max_loss_mult': 10.0, 'bear_dte': 5, 'bear_target_delta': 0.20, 'adaptive_rules': ('tsll_skip_marginal_up', 'tsll_skip_tuesday', 'tsll_skip_post_earnings_drift', 'tsll_skip_downtrend_high_iv', 'ride_high_credit_mgmt'), 'model_min_should_trade': 0.65, 'model_min_policy_conf': 0.45},
}

# Model-inspired candidates from simulator training (as of 2026-05-14):
# Tested via validate_rule.py. None have shipped yet.
#
# Best hard-skip so far on TSLA:   'skip_high_gamma_marginal_ret1d_v4'   (ultra-selective)
# Best dynamic approach on TSLL:   'dynamic_credit_on_high_gamma_marginal' (almost neutral)
#
# To experiment:
#   TSLA:  'adaptive_rules': ('tsla_skip_mild_intraday_up', 'skip_high_gamma_marginal_ret1d_v4')
#   TSLL:  'adaptive_rules': (..., 'dynamic_credit_on_high_gamma_marginal')
#
# All variants were generated from the first policy model trained on simulator-labeled data.

# =============================================================================
# MODEL-DRIVEN ENTRY (pick_entry_model) — Work in Progress
# =============================================================================
# This is the integration point for the simulator-trained policy models.
# It allows the engine to use a trained model (instead of or in addition to rules)
# to propose full strategies (entry + recommended management policy).
#
# See simulator/pick_entry_model.py for the actual model logic.
# See simulator/validate_model_policy.py for historical backtesting of model policies.

try:
    from simulator.pick_entry_model import PickEntryModel, Recommendation, EntryAction, ManagementPolicy
    from simulator.trade_labeler import EntryAction as TL_EntryAction  # for type hints if needed
    from simulator.feature_utils import get_peek_features_for_action
    _PICK_ENTRY_MODEL = PickEntryModel()
except Exception as e:
    _PICK_ENTRY_MODEL = None
    # Silent fail during development — will be loud once we're ready to ship


def pick_entry_model(row: pd.Series, cfg: StrategyConfig, S: float, today: pd.Timestamp):
    """
    Model-driven entry function (experimental).

    Uses the trained Best Management Policy + P/L models from the simulator
    to recommend a full trade plan (side, DTE, delta + management policy).

    PR 2: respects cfg.model_* knobs, delegates peek to feature_utils (no dupe pricing),
    forwards all 4 policy overrides (incl. delta_breach_override), runs post-veto skeleton,
    rich per-candidate + "why []" diagnostics when cfg.model_debug.
    The main rule path (pick_entry) is completely untouched unless enable_model_entry + PR3 wiring.
    """
    if _PICK_ENTRY_MODEL is None:
        return None

    debug = getattr(cfg, "model_debug", False)
    min_conf = getattr(cfg, "model_min_policy_conf", 0.35)
    min_edge = getattr(cfg, "model_min_edge", 0.0)
    min_should = getattr(cfg, "model_min_should_trade", 0.55)

    try:
        # Delegate to single-source get_peek (removes manual pricing duplication per PR 2)
        default_action = EntryAction("put", 5, 0.22)
        row = row.copy()
        peek = get_peek_features_for_action(row, default_action)
        row["peek_credit"] = peek.get("peek_credit", 0.5)
        row["peek_gamma_dollar"] = peek.get("peek_gamma_dollar", 0.15)
        row["peek_theta_yield"] = peek.get("peek_theta_yield", 0.03)

        # Fill any missing expected columns with reasonable defaults
        for col in ["ret_1d", "ret_5d", "ret_14d", "iv_rank", "ema_stack", "volume_surge"]:
            if col not in row or pd.isna(row.get(col)):
                row[col] = 0.0

        # Call hardened recommend with cfg knobs (should-trade gate inside)
        recs = _PICK_ENTRY_MODEL.recommend(
            row,
            min_policy_conf=min_conf,
            min_edge=min_edge,
            min_should_trade=min_should,
            use_should_trade_gate=True,
            debug=debug,
        )
        if not recs:
            if debug:
                print("[pick_entry_model] recommend returned [] (should_gate or min_* filters or post-veto)")
            return None

        best = recs[0]
        action = best.entry_action
        policy = best.recommended_policy

        # Post-model veto skeleton (PR 2) — proven hard-skip rules only (see _passes_model_veto_rules)
        if not _passes_model_veto_rules(row, action, cfg):
            if debug:
                print("[pick_entry_model] post-model veto fired — falling back (model path)")
            return None

        # Pricing for the chosen action (unchanged logic)
        iv = float(row.get("iv_proxy", 0.55))
        T = action.dte / 365.0
        try:
            K = pricing.strike_from_delta(S, T, iv, action.target_delta, action.side, r=cfg.risk_free_rate)
            K = pricing.round_strike(K, 2.5)
            credit = pricing.price(S, K, T, iv, action.side, r=cfg.risk_free_rate)
        except Exception:
            return None

        if credit / K < getattr(action, "min_credit_pct", 0.010):
            if credit / K < 0.008:
                return None

        expiration = today + pd.Timedelta(days=action.dte)

        # All 4 overrides forwarded (delta_breach_override is the new one for PR 2)
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

        if debug:
            print(f"[pick_entry_model] MODEL PROPOSAL accepted: {action.side} {action.dte}d @ {action.target_delta}Δ "
                  f"policy={policy.name} (conf={best.confidence:.2f} edge=${best.predicted_pnl:.1f})")

        return position

    except Exception as e:
        if debug:
            print(f"[pick_entry_model] error (safe return None): {e}")
        # Fail safely during early development
        return None


def _build_traj_for_advisor(position_dict: dict, row: pd.Series, mark: dict | None = None) -> dict:
    """Delegates to single source of truth in feature_utils (fixes dupe + None/gap/now() past patterns).
    today=None lets caller pass deterministic timestamp for backtests/gauntlet purity.
    """
    from simulator.feature_utils import build_trajectory_dict
    return build_trajectory_dict(position=position_dict, row=row, mark=mark, today=None)


def recommend_management_advisor(row: pd.Series, position_dict: dict, cfg: StrategyConfig, mark: dict | None = None) -> dict:
    """Thin safe wrapper (Phase C). Delegates to PickEntryModel.recommend_management when enable_model_management.
    Returns proposal dict (or {}) — caller may log, surface read-only, or feed to adapt_exit_params.
    Zero impact when flag False (default). Reuses exact PR 2 gate/diag/alignment discipline.
    """
    if not getattr(cfg, "enable_model_management", False) or _PICK_ENTRY_MODEL is None:
        return {}
    debug = getattr(cfg, "model_debug", False)
    min_c = getattr(cfg, "model_min_management_conf", 0.30)
    min_e = getattr(cfg, "model_min_mgmt_edge", 4.0)
    try:
        traj = _build_traj_for_advisor(position_dict, row, mark)
        rec = _PICK_ENTRY_MODEL.recommend_management(
            row, position=position_dict, trajectory=traj,
            min_conf=min_c, min_edge=min_e, debug=debug
        )
        if debug:
            print(f"[recommend_management_advisor] {rec.get('reason', '')[:60]} conf={rec.get('confidence', 0):.2f}")
        return rec or {}
    except Exception as e:
        if debug:
            print(f"[recommend_management_advisor] safe neutral on error: {e}")
        return {}


def get_config(ticker: str, **overrides) -> StrategyConfig:
    """Return the per-ticker default config, optionally with field overrides."""
    base = DEFAULT_CONFIG_BY_TICKER.get(ticker, {})
    merged = {'ticker': ticker, **base, **overrides}
    return StrategyConfig(**merged)


# v1.11 — adaptive-rules registry. Each entry is name → callable.
# A rule has signature: (row: pd.Series, cfg: StrategyConfig, current: dict) -> dict
# and may return any subset of {'skip': True, 'side': 'put'|'call', 'dte': int,
# 'target_delta': float}. Returning {} means no-op. Rules see the current resolved
# params via `current` and the row's features via `row`. They can branch on
# cfg.ticker to apply per-ticker logic.
ADAPTIVE_RULES: dict[str, Callable] = {}

# v1.13 — exit-side adaptive rules registry. Each entry is name → callable
# with signature: (position, mark, row, cfg) -> dict. Return {'close': True,
# 'reason': str} to short-circuit the standard ladder. Default empty dict =
# defer to the ladder.
ADAPTIVE_EXIT_RULES: dict[str, Callable] = {}


def adapt_exit_params(position, mark: dict, row: pd.Series, cfg: StrategyConfig) -> dict:
    """Run any active exit-side rules in registration order. The first rule
    that returns {'close': True, ...} wins."""
    if not getattr(cfg, 'exit_rules', ()):
        return {}
    for name in cfg.exit_rules:
        rule = ADAPTIVE_EXIT_RULES.get(name)
        if rule is None:
            continue
        diff = rule(position, mark, row, cfg)
        if diff and diff.get('close'):
            return diff
    return {}


def _rule_tsll_skip_marginal_up(row, cfg, current):
    """v1.12 — skip TSLL entries when ret_14d ∈ [0, +5%].

    Empirical motivation (v1.10 trade-log bucket analysis):
        ret_14d in [0, +0.05] on TSLL: n=28, wr=57%, avg=$-0.9, total=-$25
        All other ret_14d buckets are clearly profitable.

    Hypothesis: "stalled rally after a small up-move" is the symmetric-direction
    blind spot — regime says bullish but momentum is fading, so put entries get
    caught by reversals more often than the larger-move buckets.
    """
    if cfg.ticker != 'TSLL':
        return {}
    r14 = row.get('ret_14d')
    if r14 is None or not np.isfinite(r14):
        return {}
    if 0.0 <= r14 <= 0.05:
        return {'skip': True}
    return {}


ADAPTIVE_RULES['tsll_skip_marginal_up'] = _rule_tsll_skip_marginal_up


def _rule_tsll_skip_low_gamma(row, cfg, current):
    """v1.13 — skip TSLL entries when the would-be position's gamma_dollar
    is in the low-but-not-tiny band [0.02, 0.08].

    Empirical motivation (analyze.py bins=5 on TSLL 5y trade log):
        peek_gamma_dollar ∈ (0.0209, 0.0767]: n=48, wr=56%, avg=$-3.9, t=-2.50

    Mechanism: gamma_dollar = γ × S² × IV² / 365 is the expected daily P/L cost
    from gamma. A *moderately low* gamma_dollar combined with TSLL's high
    realized vol implies the strike is far enough OTM that credit is thin
    relative to the still-meaningful adverse-move risk — small credit, real
    tail. The lowest gamma_dollar bucket (extremely OTM) is empirically
    neutral because protection-by-distance compensates; this band is the
    "stuck in the middle" zone.
    """
    if cfg.ticker != 'TSLL':
        return {}
    g = current.get('gamma_dollar')
    if g is None or not np.isfinite(g):
        return {}
    if 0.02 <= g <= 0.08:
        return {'skip': True}
    return {}


ADAPTIVE_RULES['tsll_skip_low_gamma'] = _rule_tsll_skip_low_gamma


def _rule_tsll_skip_late_post_earnings(row, cfg, current):
    """Candidate: skip TSLL entries 49-70 days after earnings.

    Empirical motivation (analyze.py bins=4 on TSLL 5y trade log):
        days_since_earnings ∈ (49, 70.75]: n=58, wr=64%, avg=$-2.8, t=-1.76

    Mechanism (hypothesized): this window often falls 7-10 trading days before
    the next earnings event — IV is creeping up but not yet at the earnings
    premium that would meaningfully justify entry credit. Bull-side puts get
    caught in the IV crush or pre-event chop.
    """
    if cfg.ticker != 'TSLL':
        return {}
    d = row.get('days_since_earnings')
    if d is None or not np.isfinite(d):
        return {}
    if 49 <= d <= 70:
        return {'skip': True}
    return {}


ADAPTIVE_RULES['tsll_skip_late_post_earnings'] = _rule_tsll_skip_late_post_earnings


def _rule_tsla_skip_mild_intraday_up(row, cfg, current):
    """v1.13 — skip TSLA entries when intraday_return ∈ [0.5%, 1.6%].

    Empirical motivation (analyze.py narrow-window scan on TSLA 5y trade log):
        intraday_return ∈ (0.505, 1.605]: n=13, wr=62%, avg=$-113.4, t=-1.98
        total impact in bucket: $-1,474 (≈9% of 5y P/L on 12% of trades)

    Hypothesis: "exhaustion candle into a mild green day" — small positive
    intraday moves often precede next-bar reversals. The bullish-regime path
    fires (so we sell puts) but the realized continuation is reversed,
    catching the short put. Sharper moves (>1.6%) typically trend; this
    middle zone is the failure mode.
    """
    if cfg.ticker != 'TSLA':
        return {}
    ir = row.get('intraday_return')
    if ir is None or not np.isfinite(ir):
        return {}
    if 0.505 <= ir <= 1.605:
        return {'skip': True}
    return {}


ADAPTIVE_RULES['tsla_skip_mild_intraday_up'] = _rule_tsla_skip_mild_intraday_up


def _rule_tsll_skip_tuesday(row, cfg, current):
    """v1.13 — skip TSLL entries on Tuesdays.

    Empirical motivation (analyze.py narrow-window scan on TSLL 5y trade log):
        day_of_week ∈ [0.8, 1.5] (Tuesday only): n=49, wr=65%, avg=$-5.7, t=-1.91
        total impact: $-279 across 49 trades.

    Mechanism (hypothesized): Tuesday TSLL puts at 3-DTE expire Friday, so
    they sit through a full Wed→Thu→Fri trading sequence — typically more
    overnight gap risk than Wed or Thu entries, and the daily_capture-friendly
    Friday entries skew much better (Friday n=56 avg=$+34 wr=88%, the
    strongest day of the week).
    """
    if cfg.ticker != 'TSLL':
        return {}
    d = row.get('day_of_week')
    if d is None or not np.isfinite(d):
        return {}
    if int(d) == 1:  # Tuesday (Mon=0, Tue=1, …, Fri=4)
        return {'skip': True}
    return {}


ADAPTIVE_RULES['tsll_skip_tuesday'] = _rule_tsll_skip_tuesday


def _rule_tsll_skip_low_gamma_band(row, cfg, current):
    """v1.13 — skip TSLL entries when gamma_dollar ∈ [0.037, 0.070] (narrow band).

    Empirical motivation (analyze.py narrow-window scan on TSLL 5y trade log,
    measured AFTER tsll_skip_tuesday is active so the residual signal is the
    remaining gamma_dollar effect):
        peek_gamma_dollar ∈ (0.037, 0.070]: n=23, wr=48%, avg=$-6.5, t=-2.34
        total impact: $-150 in this narrow band.

    Replaces the earlier wider [0.02, 0.08] band (null result — that band
    swept up neutral trades). The narrow scan finds the sharper "moderately
    OTM with thin credit" zone where the wider band was diluted by either
    extremely-OTM (safe) or higher-gamma (well-credited) trades.
    """
    if cfg.ticker != 'TSLL':
        return {}
    g = current.get('gamma_dollar')
    if g is None or not np.isfinite(g):
        return {}
    if 0.037 <= g <= 0.070:
        return {'skip': True}
    return {}


ADAPTIVE_RULES['tsll_skip_low_gamma_band'] = _rule_tsll_skip_low_gamma_band


def _rule_tsll_skip_post_earnings_drift(row, cfg, current):
    """v1.13 — skip TSLL entries 11-21 days after earnings.

    Empirical motivation (analyze.py narrow-window scan on TSLL 5y trade log,
    measured AFTER tsll_skip_tuesday is active):
        days_since_earnings ∈ (11.4, 20.8]: n=21, wr=62%, avg=$-6.8, t=-2.15
        total impact: $-143.

    Hypothesis: this window catches the post-earnings drift / IV-rank decay
    period where IV-rank often re-crosses the entry threshold, but realized
    moves are still driven by the recent earnings reaction. The IV-rank
    signal is misleading — TSLL puts entered here get caught by the residual
    post-earnings volatility.
    """
    if cfg.ticker != 'TSLL':
        return {}
    d = row.get('days_since_earnings')
    if d is None or not np.isfinite(d):
        return {}
    if 11 <= d <= 21:
        return {'skip': True}
    return {}


ADAPTIVE_RULES['tsll_skip_post_earnings_drift'] = _rule_tsll_skip_post_earnings_drift


def _rule_tsll_skip_downtrend_high_iv(row, cfg, current):
    """v1.13 — skip TSLL puts when 14-day return is meaningfully negative AND
    iv_rank is elevated. The interaction is the signal.

    Empirical motivation (analyze.py --pairs scan on TSLL 5y trade log,
    measured AFTER all other v1.13 rules are active):
        ret_14d ∈ (-0.632, -0.073] × iv_rank ∈ (77.4, 100]: n=19, wr=58%,
        avg=$-11.7, t=-2.49, p=0.022 (total = $-222).

    Hypothesis: post-decline IV spike that hasn't yet capitulated — premium
    looks rich (high iv_rank) but the underlying is still trending down, so
    the bullish-regime put-sell pretext gets caught by continued downside.
    The combo is more selective than either feature alone (ret_14d quartile
    bucket alone is positive; iv_rank quartile alone is positive).
    """
    if cfg.ticker != 'TSLL':
        return {}
    r14 = row.get('ret_14d')
    ivr = row.get('iv_rank')
    if r14 is None or ivr is None or not (np.isfinite(r14) and np.isfinite(ivr)):
        return {}
    if -0.632 <= r14 <= -0.073 and ivr >= 77.0:
        return {'skip': True}
    return {}


ADAPTIVE_RULES['tsll_skip_downtrend_high_iv'] = _rule_tsll_skip_downtrend_high_iv


def _rule_skip_high_gamma_marginal_ret1d(row, cfg, current):
    """
    Model-inspired rule (from first policy model trained on simulator data).

    Skip when 1-day return is in a narrow "uncertain" band AND gamma risk on
    the would-be position is high. This is a more conservative version after
    the first validation pass showed the initial thresholds were too aggressive
    (especially hurt v_recovery).

    Top signals from the simulator-trained model: ret_1d (#1) + peek_gamma_dollar (#3).
    """
    r1 = row.get('ret_1d')
    g = current.get('gamma_dollar')

    if r1 is None or g is None or not (np.isfinite(r1) and np.isfinite(g)):
        return {}

    # Narrower uncertain band + higher gamma threshold (more conservative)
    if -0.008 <= r1 <= 0.015 and g > 0.095:
        return {'skip': True}
    return {}


ADAPTIVE_RULES['skip_high_gamma_marginal_ret1d'] = _rule_skip_high_gamma_marginal_ret1d


def _rule_skip_high_gamma_marginal_ret1d_v2(row, cfg, current):
    """
    v2 (more conservative) of the simulator-model-inspired rule.

    Key changes after v1 validation failure:
    - Much narrower "uncertain momentum" band on ret_1d
    - Significantly higher gamma_dollar threshold (only skip when risk is truly elevated)
    - Goal: keep the signal while protecting v_recovery and normal regimes.
    """
    r1 = row.get('ret_1d')
    g = current.get('gamma_dollar')

    if r1 is None or g is None or not (np.isfinite(r1) and np.isfinite(g)):
        return {}

    # Tighter, more conservative conditions
    if -0.006 <= r1 <= 0.012 and g > 0.11:
        return {'skip': True}
    return {}


ADAPTIVE_RULES['skip_high_gamma_marginal_ret1d_v2'] = _rule_skip_high_gamma_marginal_ret1d_v2


def _rule_skip_high_gamma_marginal_ret1d_credit(row, cfg, current):
    """
    Variant that also considers peek_credit (model's #2 feature).

    Skip when momentum is marginal, gamma risk is high, *and* credit quality
    is not excellent. This tries to be more selective than pure gamma rules.
    """
    r1 = row.get('ret_1d')
    g = current.get('gamma_dollar')
    credit = current.get('credit')

    if None in (r1, g, credit) or not all(np.isfinite(x) for x in (r1, g, credit)):
        return {}

    # Marginal momentum + high gamma + mediocre credit
    if -0.007 <= r1 <= 0.013 and g > 0.09 and credit < 1.8:
        return {'skip': True}
    return {}


ADAPTIVE_RULES['skip_high_gamma_marginal_ret1d_credit'] = _rule_skip_high_gamma_marginal_ret1d_credit


def _rule_tsla_only_high_gamma_marginal_ret1d_v3(row, cfg, current):
    """
    Extremely conservative TSLA-only version (v3).

    Only skips in a very narrow band and only when gamma is *very* high.
    Designed specifically to avoid hurting v_recovery while still capturing
    the core model signal (ret_1d + gamma_dollar).
    """
    if cfg.ticker != 'TSLA':
        return {}

    r1 = row.get('ret_1d')
    g = current.get('gamma_dollar')

    if r1 is None or g is None or not (np.isfinite(r1) and np.isfinite(g)):
        return {}

    # Very tight band + very high gamma threshold
    if -0.004 <= r1 <= 0.009 and g > 0.135:
        return {'skip': True}
    return {}


ADAPTIVE_RULES['tsla_only_high_gamma_marginal_ret1d_v3'] = _rule_tsla_only_high_gamma_marginal_ret1d_v3


def _rule_skip_high_gamma_marginal_ret1d_v4(row, cfg, current):
    """
    v4 — extremely selective hard-skip version.

    Only fires on a very narrow uncertain momentum band and *very* high gamma.
    Intended as a final attempt at a pure skip rule before moving to dynamic knobs.
    """
    r1 = row.get('ret_1d')
    g = current.get('gamma_dollar')

    if r1 is None or g is None or not (np.isfinite(r1) and np.isfinite(g)):
        return {}

    if -0.003 <= r1 <= 0.008 and g > 0.145:
        return {'skip': True}
    return {}


ADAPTIVE_RULES['skip_high_gamma_marginal_ret1d_v4'] = _rule_skip_high_gamma_marginal_ret1d_v4


def _rule_dynamic_credit_on_high_gamma_marginal(row, cfg, current):
    """
    A2: Dynamic knob version (preferred direction).

    Instead of hard-skipping, raise the credit floor when momentum is marginal
    and gamma risk is elevated. This uses the M4 per-position override system.

    This is more surgical than a hard skip — it still allows very high-quality
    premium when it exists, but demands better compensation when risk is high.
    """
    r1 = row.get('ret_1d')
    g = current.get('gamma_dollar')

    if r1 is None or g is None or not (np.isfinite(r1) and np.isfinite(g)):
        return {}

    if -0.006 <= r1 <= 0.012 and g > 0.10:
        # Raise the bar from the default (0.010 / 0.012) to 1.45%
        return {'min_credit_pct': 0.0145}
    return {}


ADAPTIVE_RULES['dynamic_credit_on_high_gamma_marginal'] = _rule_dynamic_credit_on_high_gamma_marginal


def _rule_ride_high_credit_mgmt(row, cfg, current):
    """Phase 3 distill: when peek credit is rich, use hold_longer-style exits (model label)."""
    credit = current.get('credit')
    if credit is None or not np.isfinite(credit):
        return {}
    strike = float(current.get('strike') or row.get('close') or 1.0)
    if strike <= 0:
        return {}
    credit_pct = float(credit) / strike
    threshold = 0.012 if cfg.ticker == 'TSLL' else 0.010
    if credit_pct < threshold * 1.35:
        return {}
    return {'daily_capture_mult': 2.2, 'profit_target': 0.70}


ADAPTIVE_RULES['ride_high_credit_mgmt'] = _rule_ride_high_credit_mgmt


def _rule_tight_risk_high_gamma(row, cfg, current):
    """Phase 3b distill: elevated gamma → tight_risk management overrides."""
    g = current.get('gamma_dollar')
    if g is None or not np.isfinite(g) or float(g) < 0.30:
        return {}
    return {'daily_capture_mult': 1.3, 'profit_target': 0.50, 'delta_breach': 0.38}


ADAPTIVE_RULES['tight_risk_high_gamma'] = _rule_tight_risk_high_gamma


def _exit_rule_take_half_on_reversal(position, mark: dict, row: pd.Series, cfg: StrategyConfig) -> dict:
    """v1.13 EXAMPLE exit rule — close early when we're already ≥50% in profit AND
    today is a reversal (puts) or bearish (calls). Locks in half-credit before the
    standard daily_capture/profit_target rungs do, on the day the context turns against
    us. Not enabled by default; demonstrates the exit-side hook contract.
    """
    pnl = position.credit - mark['price'] * (1.0 + cfg.slippage_pct)
    if pnl < 0.5 * position.credit:
        return {}
    if position.side == 'put' and bool(row.get('reversal', False)):
        return {'close': True, 'reason': 'adapt_exit_half_reversal'}
    if position.side == 'call' and row.get('regime') == 'bullish':
        return {'close': True, 'reason': 'adapt_exit_half_bull_flip'}
    return {}


ADAPTIVE_EXIT_RULES['take_half_on_reversal'] = _exit_rule_take_half_on_reversal


def _peek(row: pd.Series, cfg: StrategyConfig, current: dict) -> dict:
    """v1.12 — call pricing.peek_position with the current resolved params.
    Returns the peek dict; caller merges its keys into `current` so rules can
    read greeks (delta, gamma, theta, vega) and derived metrics (theta_yield,
    gamma_dollar, strike, credit) for the would-be position."""
    return pricing.peek_position(
        S=float(row['close']),
        dte=int(current['dte']),
        target_delta=float(current['target_delta']),
        side=current['side'],
        iv=float(row['iv_proxy']),
        r=cfg.risk_free_rate,
    )


def adapt_entry_params(row: pd.Series, cfg: StrategyConfig, base: dict) -> dict:
    """Apply the active adaptive rules to `base` in registration order.

    Each rule sees the current intended params + the row's features + the
    would-be position's greeks (peeked from BSM at the current candidate
    params). Each rule can modify side / dte / target_delta or set
    'skip': True. After any rule modifies dte/target_delta, the peek is
    refreshed so the next rule sees current greeks.

    Default (no rules) returns `base` unchanged → zero behavior change vs v1.10.
    """
    if not cfg.adaptive_rules:
        return base
    current = dict(base)
    # Initial peek for the regime-branch base params
    current.update(_peek(row, cfg, current))
    for name in cfg.adaptive_rules:
        rule = ADAPTIVE_RULES.get(name)
        if rule is None:
            continue
        diff = rule(row, cfg, current)
        if diff:
            params_changed = any(k in diff for k in ('dte', 'target_delta', 'side'))
            current.update(diff)
            if params_changed and not current.get('skip'):
                current.update(_peek(row, cfg, current))
        if current.get('skip'):
            break
    return current


def _daily_capture_mult_for(dte: int, cfg: StrategyConfig) -> float:
    if dte <= 7:
        return cfg.daily_capture_mult_short
    if dte <= 15:
        return cfg.daily_capture_mult_mid
    return cfg.daily_capture_mult_long


def _passes_model_veto_rules(row: pd.Series, action: "EntryAction", cfg: StrategyConfig) -> bool:
    """Lightweight post-model veto skeleton (PR 2).

    Runs only the *proven* hard-skip rules (the five shipped in DEFAULT_CONFIG_BY_TICKER
    plus the model-inspired gamma hard-skips that already survived validate_rule.py).
    Returns True if the model proposal survives (no veto); False → fall back to rule path.

    This is the "proposer can change; validator cannot" guard. Only hard skips for v1;
    softer dynamic rules remain model-influenceable. Called from the experimental model path
    (pick_entry_model wrapper + future PR3 hybrid).
    """
    if not action:
        return True
    current = {
        "side": action.side,
        "dte": action.dte,
        "target_delta": action.target_delta,
    }
    # Proven hard-skip names (from DEFAULT + gamma model-derived that passed real gauntlet)
    veto_rule_names = (
        "tsla_skip_mild_intraday_up",
        "tsll_skip_marginal_up",
        "tsll_skip_tuesday",
        "tsll_skip_post_earnings_drift",
        "tsll_skip_downtrend_high_iv",
        # model-inspired gamma hard skips (v4 is the selective one)
        "skip_high_gamma_marginal_ret1d_v4",
        "skip_high_gamma_marginal_ret1d",
    )
    debug = getattr(cfg, "model_debug", False)
    for name in veto_rule_names:
        rule = ADAPTIVE_RULES.get(name)
        if rule is None:
            continue
        try:
            res = rule(row, cfg, dict(current))
            if res and res.get("skip"):
                if debug:
                    print(f"[veto] post-model veto by {name}")
                return False
        except Exception:
            # never let a rule crash kill the path
            if debug:
                print(f"[veto] rule {name} errored (ignored)")
            continue
    return True


def pick_entry(row: pd.Series, cfg: StrategyConfig, S: float, today: pd.Timestamp):
    """Decide side + parameters from regime flags, then size a Position."""
    iv = float(row['iv_proxy'])
    if not np.isfinite(iv) or iv <= 0:
        return None
    if row['iv_rank'] < cfg.iv_rank_min:
        return None

    if row['regime'] == 'bearish':
        if cfg.bear_dte <= 0:
            return None  # legacy stand-aside behavior
        side = 'call'
        target_delta = cfg.bear_target_delta
        dte = cfg.bear_dte
    else:
        defensive = bool(row['reversal']) or (
            bool(row['high_iv']) and row['ema_21'] < row['ema_55']
        )
        if defensive:
            side = 'call'
            target_delta = cfg.short_target_delta
            dte = cfg.short_dte
        elif cfg.wheel_enabled:
            side = 'put'
            target_delta = cfg.long_target_delta
            dte = cfg.wheel_put_dte    # shorter DTE in wheel mode → less time for regime_flip to fire
        else:
            side = 'put'
            target_delta = cfg.long_target_delta
            dte = cfg.long_dte

    # v1.11 — adaptive rules may adjust (side, dte, target_delta) or force skip
    # v1.13 — rules may also return per-position knob overrides:
    #   min_credit_pct, max_loss_mult, delta_breach, profit_target, daily_capture_mult
    resolved = adapt_entry_params(row, cfg, {'side': side, 'dte': dte, 'target_delta': target_delta})
    if resolved.get('skip'):
        return None
    side = resolved['side']
    dte = int(resolved['dte'])
    target_delta = float(resolved['target_delta'])

    T = dte / 365.0
    try:
        K_exact = pricing.strike_from_delta(S, T, iv, target_delta, side, r=cfg.risk_free_rate)
    except ValueError:
        return None
    K = pricing.round_strike(K_exact, 2.5)

    credit = pricing.price(S, K, T, iv, side, r=cfg.risk_free_rate)
    credit *= (1.0 - cfg.slippage_pct)
    if credit <= 0.01:
        return None
    # v1.13 — adaptive rule may override the credit floor for this entry
    eff_min_credit_pct = float(resolved.get('min_credit_pct', cfg.min_credit_pct))
    if K > 0 and credit / K < eff_min_credit_pct:
        return None

    expiration = today + pd.Timedelta(days=dte)
    # v1.13 — if a rule supplied a daily_capture_mult override, use it; else DTE-bucket default
    if 'daily_capture_mult' in resolved:
        dcap = float(resolved['daily_capture_mult'])
    else:
        dcap = _daily_capture_mult_for(dte, cfg)

    return Position(
        side=side,
        entry_date=today,
        expiration=expiration,
        strike=K,
        credit=credit,
        dte_at_entry=dte,
        iv_at_entry=iv,
        regime_at_entry=str(row['regime']),
        daily_theta_target=credit / dte,
        daily_capture_mult=dcap,
        max_loss_mult_override=(
            float(resolved['max_loss_mult']) if 'max_loss_mult' in resolved else None
        ),
        delta_breach_override=(
            float(resolved['delta_breach']) if 'delta_breach' in resolved else None
        ),
        profit_target_override=(
            float(resolved['profit_target']) if 'profit_target' in resolved else None
        ),
    )


def check_exits(position: Position, mark: dict, row: pd.Series, cfg: StrategyConfig):
    """Return an exit-reason string if any ladder rung fires, else None.

    Wheel covered calls (`position.is_wheel_cc`) run a simplified ladder: only
    expiration + early profit-take rungs fire — we WANT assignment-away, so
    max_loss / delta_breach / regime_flip don't apply.

    In wheel mode, short puts skip dte_stop and delta_breach so they can ride
    to expiration (where ITM puts become wheel assignments). Loss-protection
    (max_loss) and profit-take (daily_capture, profit_target) still fire.
    """
    cur_price = mark['price'] * (1.0 + cfg.slippage_pct)  # cost to close eats slippage
    cur_delta = mark['delta']
    dte_remaining = mark['dte_remaining']

    if dte_remaining <= 0:
        return 'expired'

    pnl = position.credit - cur_price
    days_held = max((row.name - position.entry_date).days, 1)

    # v1.13 — exit-side adaptive rules run BEFORE the standard ladder so they
    # can close positions on context the ladder can't see (e.g. intraday-reversal
    # take-profit). Skip for wheel-CC since those have their own simplified ladder.
    if not getattr(position, 'is_wheel_cc', False):
        exit_diff = adapt_exit_params(position, mark, row, cfg)
        if exit_diff and exit_diff.get('close'):
            return str(exit_diff.get('reason', 'adapt_exit'))

    if getattr(position, 'is_wheel_cc', False):
        # Wheel covered call: only fast-cycle early profits. Let it ride to assignment.
        if pnl > 0 and pnl / days_held >= position.daily_capture_mult * position.daily_theta_target:
            return 'daily_capture'
        if pnl >= cfg.profit_target * position.credit:
            return 'profit_target'
        return None

    wheel_put = position.side == 'put' and getattr(cfg, 'wheel_enabled', False)

    # 2. max loss — hardest stop, check before profit-side rungs
    # In wheel mode puts get more rope (`wheel_put_max_loss_mult`) so they can survive
    # to expiration; only truly catastrophic dives stop them out before assignment.
    # v1.13 — per-position override (set by adaptive rule at entry) wins over cfg.
    if wheel_put:
        max_loss_mult = cfg.wheel_put_max_loss_mult
    else:
        max_loss_mult = position.max_loss_mult_override if position.max_loss_mult_override is not None else cfg.max_loss_mult
    if pnl <= -max_loss_mult * position.credit:
        return 'max_loss'

    # 3. daily profit capture
    if pnl > 0 and pnl / days_held >= position.daily_capture_mult * position.daily_theta_target:
        return 'daily_capture'

    # 4. hard profit target (v1.13: per-position override allowed)
    profit_target = position.profit_target_override if position.profit_target_override is not None else cfg.profit_target
    if pnl >= profit_target * position.credit:
        return 'profit_target'

    # 5. delta breach (skipped for wheel-mode puts so they can ride into ITM territory)
    # v1.13 — per-position override allowed.
    delta_breach = position.delta_breach_override if position.delta_breach_override is not None else cfg.delta_breach
    if not wheel_put and abs(cur_delta) > delta_breach:
        return 'delta_breach'

    # 6. DTE stop (skipped for wheel-mode puts so they can reach expiration)
    if not wheel_put and position.dte_at_entry > cfg.dte_stop_min_entry and dte_remaining <= cfg.dte_stop:
        return 'dte_stop'

    # 7. regime flip (skipped for wheel-mode puts when wheel_skip_regime_flip — bearish exits would prevent assignment)
    if getattr(cfg, 'regime_flip_exit_enabled', True):
        if position.side == 'put' and (bool(row['reversal']) or row['regime'] == 'bearish'):
            if not (wheel_put and getattr(cfg, 'wheel_skip_regime_flip', False)):
                return 'regime_flip'
        if position.side == 'call' and row['regime'] == 'bullish' and not bool(row['reversal']):
            return 'regime_flip'

    return None


def pick_roll(row: pd.Series, cfg: StrategyConfig, S: float, today: pd.Timestamp,
              closed_position: Position, close_cost: float):
    """v1.11 — when max_loss fires, try to construct a credit-roll position.

    Rules:
    - Same side as the closed position
    - Strike MUST be strictly further OTM than the closed strike (no doubling down)
    - DTE = `roll_dte`, delta = `roll_target_delta`
    - Accept only if new_credit >= roll_credit_ratio × close_cost (credit roll by default)

    Returns a `Position` if a valid roll exists, else None (engine falls through to flat).
    """
    iv = float(row['iv_proxy'])
    if not np.isfinite(iv) or iv <= 0:
        return None

    side = closed_position.side
    dte = cfg.roll_dte
    target_delta = cfg.roll_target_delta
    T = dte / 365.0
    try:
        K_exact = pricing.strike_from_delta(S, T, iv, target_delta, side, r=cfg.risk_free_rate)
    except ValueError:
        return None
    K = pricing.round_strike(K_exact, 2.5)

    # Safety rail: the rolled strike MUST be strictly further OTM than the original.
    # For a put this means a LOWER strike; for a call, a HIGHER strike.
    if side == 'put' and K >= closed_position.strike:
        return None
    if side == 'call' and K <= closed_position.strike:
        return None

    credit = pricing.price(S, K, T, iv, side, r=cfg.risk_free_rate) * (1.0 - cfg.slippage_pct)
    if credit <= 0.01:
        return None
    if credit < cfg.roll_credit_ratio * close_cost:
        return None

    expiration = today + pd.Timedelta(days=dte)
    return Position(
        side=side,
        entry_date=today,
        expiration=expiration,
        strike=K,
        credit=credit,
        dte_at_entry=dte,
        iv_at_entry=iv,
        regime_at_entry='rolled',
        daily_theta_target=credit / dte,
        daily_capture_mult=_daily_capture_mult_for(dte, cfg),
    )


def pick_covered_call(row: pd.Series, cfg: StrategyConfig, S: float, today: pd.Timestamp, stock_basis: float):
    """Wheel: select a covered call against stock acquired at `stock_basis`.

    Aggressive mode (`cc_strike_mode='basis'`): strike = round(basis). We WANT
    to be assigned away — that completes the cycle and frees cash. If stock is
    below basis, this is OTM (we collect premium while waiting for recovery).
    If stock is at/above basis, this is ATM/ITM (immediate assignment likely,
    P/L = credit collected).
    """
    iv = float(row['iv_proxy'])
    if not np.isfinite(iv) or iv <= 0:
        return None
    if row['iv_rank'] < cfg.iv_rank_min:
        return None

    dte = cfg.cc_dte
    T = dte / 365.0

    if cfg.cc_strike_mode == 'basis':
        K = pricing.round_strike(stock_basis, 2.5)
    else:
        try:
            K_exact = pricing.strike_from_delta(S, T, iv, cfg.cc_target_delta, 'call', r=cfg.risk_free_rate)
        except ValueError:
            return None
        K = pricing.round_strike(K_exact, 2.5)

    if K <= 0:
        return None

    credit = pricing.price(S, K, T, iv, 'call', r=cfg.risk_free_rate)
    credit *= (1.0 - cfg.slippage_pct)
    if credit <= 0.01:
        return None
    if credit / K < cfg.min_credit_pct:
        return None

    expiration = today + pd.Timedelta(days=dte)
    pos = Position(
        side='call',
        entry_date=today,
        expiration=expiration,
        strike=K,
        credit=credit,
        dte_at_entry=dte,
        iv_at_entry=iv,
        regime_at_entry='wheel_cc',
        daily_theta_target=credit / dte,
        daily_capture_mult=_daily_capture_mult_for(dte, cfg),
    )
    pos.is_wheel_cc = True
    return pos
