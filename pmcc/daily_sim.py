from __future__ import annotations

from pmcc.daily_playthrough import daily_policy, score_daily_policy
from pmcc.playthrough import PlayPolicy
from pmcc.scenarios import PmccPair
from pmcc.tune import tune_policy


def score_policy(
    pair: PmccPair,
    policy: PlayPolicy,
    *,
    r: float = 0.04,
    bear_loss_cap: float = -3200.0,
) -> dict:
    """Daily sim score (whipsaw-weighted)."""
    return score_daily_policy(pair, daily_policy(policy), r=r, bear_loss_cap=bear_loss_cap)


def search_rules(
    pair: PmccPair,
    base: PlayPolicy,
    *,
    r: float = 0.04,
) -> tuple[PlayPolicy, dict]:
    tuned, tuned_score, _ = tune_policy(pair, base, r=r, fast=True)
    return tuned, tuned_score