import numpy as np
import pandas as pd
from unittest.mock import patch

from scripts.spy_index_theta_carry_lab import (
    candidate_config,
    control_config,
    build_features,
    evaluate_discovery,
    select_blueprints,
    select_anchored_blueprints,
    simulate_axes,
    run_lab,
)


def test_candidate_and_control_freeze_only_bearish_entry_permission():
    candidate = candidate_config()
    control = control_config()

    assert candidate["symbol"] == "SPY"
    assert candidate["target_dte"] == 21
    assert candidate["target_delta"] == 0.20
    assert candidate["spread_width"] == 2.0
    assert candidate["min_credit"] == 0.30
    assert candidate["max_sessions"] == 10
    assert candidate["profit_target"] == 0.50
    assert candidate["defined_loss_exit_frac"] == 0.70
    assert candidate["delta_breach"] == 0.45
    assert candidate["allowed_signal_regimes"] == ["bullish", "neutral"]
    assert control == {**candidate, "allowed_signal_regimes": ["bullish", "neutral", "bearish"]}


def _axis(*, pnl: float, avg: float, entries: list[str]) -> dict:
    return {
        "n_completed": 24,
        "total_pnl_usd": pnl,
        "avg_pnl_usd": avg,
        "profit_factor": 1.20,
        "max_drawdown_usd": 100.0,
        "expected_shortfall_90_usd": -100.0,
        "maximum_structural_or_realized_one_trade_loss_usd": 190.0,
        "integrity_violations": [],
        "entry_dates": entries,
    }


def test_discovery_gate_requires_dual_cost_edge_and_control_outperformance():
    entries = [f"2024-01-{day:02d}" for day in range(1, 25)]
    candidate_axes = {
        "slippage_5pct": _axis(pnl=240.0, avg=10.0, entries=entries),
        "fixed_0p01_per_leg": _axis(pnl=192.0, avg=8.0, entries=entries),
    }
    control_axes = {
        "slippage_5pct": _axis(pnl=120.0, avg=5.0, entries=entries),
        "fixed_0p01_per_leg": _axis(pnl=96.0, avg=4.0, entries=entries),
    }

    result = evaluate_discovery(
        candidate_axes,
        control_axes,
        holdout_identity={
            "sealed": True,
            "option_outcomes_evaluated": False,
            "start": "2024-02-01",
            "end": "2025-01-01",
        },
    )

    assert result["pass"] is True
    assert result["outcome"] == "STRATEGY_ADVANCED"
    assert all(result["checks"].values())


def test_repaired_regime_contrast_supersedes_low_density_path_comparator():
    entries = [f"2024-01-{day:02d}" for day in range(1, 25)]
    candidate_axes = {
        axis: _axis(pnl=96.0, avg=4.0, entries=entries)
        for axis in ("slippage_5pct", "fixed_0p01_per_leg")
    }
    control_axes = {
        axis: _axis(pnl=120.0, avg=5.0, entries=entries)
        for axis in ("slippage_5pct", "fixed_0p01_per_leg")
    }
    contrast = {
        "identical_entries_across_cost_axes": True,
        "non_bearish": {
            axis: {**_axis(pnl=80.0, avg=8.0, entries=entries[:10]), "n_completed": 10}
            for axis in ("slippage_5pct", "fixed_0p01_per_leg")
        },
        "bearish": {
            axis: {**_axis(pnl=-20.0, avg=-2.0, entries=entries[10:20]), "n_completed": 10}
            for axis in ("slippage_5pct", "fixed_0p01_per_leg")
        },
    }

    result = evaluate_discovery(
        candidate_axes,
        control_axes,
        holdout_identity={
            "sealed": True,
            "option_outcomes_evaluated": False,
            "start": "2024-02-01",
            "end": "2025-01-01",
        },
        regime_contrast=contrast,
    )

    assert result["pass"] is True
    assert result["checks"]["anchored_regime_contrast_non_vacuous"] is True
    assert result["checks"]["non_bearish_worst_axis_average_gt_bearish"] is True
    assert result["diagnostics"]["path_control_candidate_worst_axis_average_gt_control"] is False


def test_repaired_regime_contrast_fails_closed_without_bearish_support():
    entries = [f"2024-01-{day:02d}" for day in range(1, 25)]
    candidate_axes = {
        axis: _axis(pnl=96.0, avg=4.0, entries=entries)
        for axis in ("slippage_5pct", "fixed_0p01_per_leg")
    }
    control_axes = {
        axis: _axis(pnl=120.0, avg=5.0, entries=entries)
        for axis in ("slippage_5pct", "fixed_0p01_per_leg")
    }
    contrast = {
        "identical_entries_across_cost_axes": True,
        "non_bearish": {
            axis: {**_axis(pnl=80.0, avg=8.0, entries=entries[:10]), "n_completed": 10}
            for axis in ("slippage_5pct", "fixed_0p01_per_leg")
        },
        "bearish": {
            axis: {**_axis(pnl=0.0, avg=0.0, entries=[]), "n_completed": 0}
            for axis in ("slippage_5pct", "fixed_0p01_per_leg")
        },
    }

    result = evaluate_discovery(
        candidate_axes,
        control_axes,
        holdout_identity={
            "sealed": True,
            "option_outcomes_evaluated": False,
            "start": "2024-02-01",
            "end": "2025-01-01",
        },
        regime_contrast=contrast,
    )

    assert result["pass"] is False
    assert result["outcome"] == "FAMILY_CLOSED"
    assert result["checks"]["anchored_regime_contrast_non_vacuous"] is False
    assert result["checks"]["non_bearish_worst_axis_average_gt_bearish"] is False
    assert result["failed_checks"] == [
        "anchored_regime_contrast_non_vacuous",
        "non_bearish_worst_axis_average_gt_bearish",
    ]


def test_discovery_gate_fails_closed_when_a_cost_axis_is_missing():
    entries = [f"2024-01-{day:02d}" for day in range(1, 25)]
    candidate_axes = {
        "slippage_5pct": _axis(pnl=240.0, avg=10.0, entries=entries),
    }
    control_axes = {
        "slippage_5pct": _axis(pnl=120.0, avg=5.0, entries=entries),
        "fixed_0p01_per_leg": _axis(pnl=96.0, avg=4.0, entries=entries),
    }

    result = evaluate_discovery(
        candidate_axes,
        control_axes,
        holdout_identity={
            "sealed": True,
            "option_outcomes_evaluated": False,
            "start": "2024-02-01",
            "end": "2025-01-01",
        },
    )

    assert result["pass"] is False
    assert result["outcome"] == "FAMILY_CLOSED"
    assert result["failed_checks"] == ["dual_cost_axes_complete"]


def test_blueprints_use_prior_regime_and_fixed_nonoverlapping_cadence():
    index = pd.bdate_range("2024-01-02", periods=60)
    features = pd.DataFrame(
        {
            "close": np.linspace(100.0, 105.0, len(index)),
            "vix": 45.0,
            "latest_prior_vix": 45.0,
            "regime": ["bearish"] + ["bullish"] * (len(index) - 1),
        },
        index=index,
    )

    rows = select_blueprints(features, candidate_config())

    assert len(rows) >= 2
    positions = [int(features.index.get_loc(pd.Timestamp(row["entry_date"]))) for row in rows]
    assert all(following - previous >= 11 for previous, following in zip(positions, positions[1:]))
    assert all(row["signal_regime"] in {"bullish", "neutral"} for row in rows)
    assert all(row["signal_date"] < row["entry_date"] for row in rows)
    assert all(row["structural_max_loss_usd"] <= 300.0 for row in rows)
    assert all(
        row["entry_credits"][axis] >= candidate_config()["min_credit"]
        for row in rows
        for axis in ("slippage_5pct", "fixed_0p01_per_leg")
    )


def test_anchored_blueprints_hold_calendar_opportunities_fixed_across_regimes():
    index = pd.bdate_range("2024-01-02", periods=70)
    regimes = ["neutral"] * len(index)
    for signal_position in range(0, len(index) - 1, 11):
        regimes[signal_position] = "bearish" if (signal_position // 11) % 2 else "bullish"
    features = pd.DataFrame(
        {
            "close": np.linspace(100.0, 105.0, len(index)),
            "vix": 80.0,
            "latest_prior_vix": 80.0,
            "regime": regimes,
        },
        index=index,
    )

    rows = select_anchored_blueprints(features, {**candidate_config(), "min_credit": 0.0})

    positions = [int(features.index.get_loc(pd.Timestamp(row["entry_date"]))) for row in rows]
    assert positions == list(range(1, len(index) - 1, 11))
    assert {row["signal_regime"] for row in rows} == {"bullish", "bearish"}


def test_simulation_reuses_entry_population_and_reconciles_cashflows():
    index = pd.bdate_range("2024-01-02", periods=70)
    features = pd.DataFrame(
        {
            "close": np.linspace(100.0, 110.0, len(index)),
            "vix": 45.0,
            "latest_prior_vix": 45.0,
            "regime": "bullish",
        },
        index=index,
    )
    config = candidate_config()
    blueprints = select_blueprints(features, config)

    axes = simulate_axes(features, blueprints, config)

    assert axes["slippage_5pct"]["entry_dates"] == axes["fixed_0p01_per_leg"]["entry_dates"]
    assert axes["slippage_5pct"]["n_completed"] == len(blueprints)
    assert axes["fixed_0p01_per_leg"]["n_completed"] == len(blueprints)
    assert axes["slippage_5pct"]["integrity_violations"] == []
    assert axes["fixed_0p01_per_leg"]["integrity_violations"] == []
    assert all(
        1 <= trade["sessions_held"] <= config["max_sessions"]
        for axis in axes.values()
        for trade in axis["trades"]
    )


def test_features_use_strictly_prior_vix_for_option_marks():
    index = pd.bdate_range("2023-01-03", periods=260)
    close = np.linspace(100.0, 130.0, len(index))
    spy = pd.DataFrame(
        {
            "open": close - 0.2,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": 1_000_000,
        },
        index=index,
    )
    vix = pd.Series(np.linspace(15.0, 30.0, len(index)), index=index, name="vix")

    with patch("data.load_vix", return_value=vix):
        features = build_features(spy, vix)

    first_date = pd.Timestamp(features.index[0])
    first_position = int(index.get_loc(first_date))
    assert first_position > 0
    assert features.loc[first_date, "vix"] == vix.loc[first_date]
    assert features.loc[first_date, "latest_prior_vix"] == vix.iloc[first_position - 1]
    assert features[["close", "regime", "vix", "latest_prior_vix"]].notna().all().all()


def test_run_lab_keeps_chronological_holdout_option_outcomes_unread():
    index = pd.bdate_range("2022-01-03", periods=500)
    close = np.linspace(100.0, 150.0, len(index))
    spy = pd.DataFrame(
        {
            "open": close - 0.2,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": 1_000_000,
        },
        index=index,
    )
    vix = pd.Series(35.0, index=index, name="vix")

    with patch("data.load_vix", return_value=vix):
        result = run_lab(
            spy,
            vix,
            spy_provenance={"path": "spy.csv", "sha256": "spy-hash"},
            vix_provenance={"path": "vix.csv", "sha256": "vix-hash"},
            train_fraction=0.60,
        )

    assert result["partition"]["train_end"] < result["holdout_identity"]["start"]
    assert result["holdout_identity"]["sealed"] is True
    assert result["holdout_identity"]["option_outcomes_evaluated"] is False
    assert "holdout_axes" not in result
    assert set(result["candidate"]) == {
        "config",
        "entry_coverage",
        "n_blueprints",
        "train_axes",
    }
    assert result["gates"]["expected_shortfall_worst_10pct_gte_usd"] == -125.0
    entry_coverage = result["candidate"]["entry_coverage"]
    assert entry_coverage["train_start"] == result["partition"]["train_start"]
    assert entry_coverage["train_end"] == result["partition"]["train_end"]
    assert entry_coverage["identical_entries_across_cost_axes"] is True
    assert entry_coverage["n_unique_entry_dates"] == result["candidate"]["n_blueprints"]
    assert "do not establish compatibility across the full train period" in entry_coverage["claim_boundary"]
    assert result["decision"]["outcome"] in {"STRATEGY_ADVANCED", "FAMILY_CLOSED"}
    assert result["wake_outcome"] == "BLOCKER_REMOVED_AND_RETESTED"
    assert result["retest_decision"] == result["strategy_outcome"]
