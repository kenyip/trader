#!/usr/bin/env python3
"""Train-only official 2s10s bull-steepening regional-bank discovery lab.

BUILD/L0 only. The final 40% of frozen event identities remains outcome-unread and
no option pricing occurs.
"""
from __future__ import annotations

import argparse
from io import BytesIO
import hashlib
import json
from pathlib import Path
import sys
from typing import Callable
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FORWARD_SESSIONS = 10
UNDERLYING_ROUND_TRIP_COST_BPS = 10.0


def parse_treasury_csv(payload: bytes) -> pd.DataFrame:
    """Parse persisted U.S. Treasury daily par-yield CSV bytes fail closed."""
    raw = pd.read_csv(BytesIO(payload))
    required = {"Date", "2 Yr", "10 Yr"}
    if not required.issubset(raw.columns):
        raise ValueError("Treasury CSV missing Date, 2 Yr, or 10 Yr")
    frame = pd.DataFrame(
        {
            "dgs2": np.asarray(pd.to_numeric(raw["2 Yr"], errors="coerce"), dtype=float),
            "dgs10": np.asarray(pd.to_numeric(raw["10 Yr"], errors="coerce"), dtype=float),
        },
        index=pd.DatetimeIndex(pd.to_datetime(raw["Date"], errors="coerce")),
    )
    frame = frame.sort_index()
    if frame.index.hasnans:
        raise ValueError("Treasury curve contains an invalid Date")
    if not frame.index.is_unique:
        raise ValueError("Treasury curve contains duplicate dates")
    missing_direct_rows = int(frame[["dgs2", "dgs10"]].isna().any(axis=1).sum())
    frame = frame.dropna(subset=["dgs2", "dgs10"])
    values = frame.to_numpy(dtype=float)
    if (
        frame.empty
        or not frame.index.is_unique
        or not frame.index.is_monotonic_increasing
        or not np.isfinite(values).all()
        or (values <= 0.0).any()
    ):
        raise ValueError("Treasury curve must be unique, increasing, finite, and positive")
    frame["spread_2s10s"] = frame["dgs10"] - frame["dgs2"]
    frame.attrs["missing_direct_rows_dropped"] = missing_direct_rows
    return frame


def _request_bytes(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "Trader research/BUILD"})
    with urlopen(request, timeout=45) as response:  # nosec B310 - fixed official URL
        payload = response.read()
    if not payload:
        raise ValueError("empty Treasury response")
    return payload


def _atomic_persist(path: Path, payload: bytes) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def load_treasury_year(
    year: int,
    *,
    cache_dir: Path,
    requester: Callable[[str], bytes] = _request_bytes,
    persister: Callable[[Path, bytes], None] = _atomic_persist,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Fetch once, then hash and parse the exact persisted official bytes."""
    if year < 1990 or year > 2100:
        raise ValueError("Treasury year is outside the supported range")
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"daily_treasury_yield_curve_{year}.csv"
    url = (
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
        f"daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve&"
        f"field_tdr_date_value={year}&page&_format=csv"
    )
    if not path.exists():
        persister(path, requester(url))
    persisted = path.read_bytes()
    frame = parse_treasury_csv(persisted)
    return frame, {
        "year": year,
        "url": url,
        "path": str(path),
        "sha256": hashlib.sha256(persisted).hexdigest(),
        "rows": len(frame),
        "missing_direct_rows_dropped": int(frame.attrs["missing_direct_rows_dropped"]),
        "start": str(frame.index[0].date()),
        "end": str(frame.index[-1].date()),
        "fields": ["2 Yr", "10 Yr"],
        "source_semantics": "official U.S. Treasury daily par yield curve",
    }


def build_feature_panel(
    curve: pd.DataFrame,
    closes: dict[str, pd.Series],
) -> pd.DataFrame:
    """Join direct curve observations and adjusted closes on exact completed dates."""
    required_curve = {"dgs2", "dgs10", "spread_2s10s"}
    if not required_curve.issubset(curve.columns):
        raise ValueError("curve fields are incomplete")
    if set(closes) != {"KRE", "XLF", "SPY"}:
        raise ValueError("closes must contain exactly KRE, XLF, and SPY")
    prepared = curve.loc[:, ["dgs2", "dgs10", "spread_2s10s"]].copy()
    prepared.index = pd.DatetimeIndex(pd.to_datetime(prepared.index)).tz_localize(None).normalize()
    for symbol in ("KRE", "XLF", "SPY"):
        series = pd.Series(closes[symbol], copy=True, dtype=float)
        series.index = pd.DatetimeIndex(pd.to_datetime(series.index)).tz_localize(None).normalize()
        prepared = prepared.join(series.rename(symbol.lower()), how="inner")
    prepared = prepared.sort_index()
    values = prepared.to_numpy(dtype=float)
    if (
        prepared.empty
        or not prepared.index.is_unique
        or not prepared.index.is_monotonic_increasing
        or not np.isfinite(values).all()
        or (prepared[["dgs2", "dgs10", "kre", "xlf", "spy"]] <= 0.0).any().any()
    ):
        raise ValueError("feature inputs must be finite, positive, unique, and increasing")
    prepared["spread_change20"] = prepared["spread_2s10s"].diff(20)
    prepared["dgs2_change20"] = prepared["dgs2"].diff(20)
    prepared["kre_sma100"] = prepared["kre"].rolling(100, min_periods=100).mean()
    prepared["spy_sma100"] = prepared["spy"].rolling(100, min_periods=100).mean()
    return prepared


def trigger_mask(panel: pd.DataFrame) -> pd.Series:
    needed = ["spread_change20", "dgs2_change20", "kre", "kre_sma100", "spy", "spy_sma100"]
    finite = np.isfinite(panel[needed].to_numpy(dtype=float)).all(axis=1)
    return (
        pd.Series(finite, index=panel.index)
        & (panel["spread_change20"] >= 0.20)
        & (panel["dgs2_change20"] <= -0.10)
        & (panel["kre"] > panel["kre_sma100"])
        & (panel["spy"] > panel["spy_sma100"])
    )


def freeze_events(panel: pd.DataFrame, *, forward_sessions: int = 10) -> list[dict[str, object]]:
    """Freeze rising-edge, non-overlapping event identities before reading outcomes."""
    if forward_sessions < 1:
        raise ValueError("forward_sessions must be positive")
    trigger = trigger_mask(panel)
    rising = trigger & ~trigger.shift(1, fill_value=False)
    events: list[dict[str, object]] = []
    next_available = 0
    for signal_pos in range(len(panel)):
        if signal_pos < next_available or not bool(rising.iloc[signal_pos]):
            continue
        entry_pos = signal_pos + 1
        exit_pos = entry_pos + forward_sessions
        if exit_pos >= len(panel):
            continue
        events.append(
            {
                "signal_pos": signal_pos,
                "signal_date": pd.Timestamp(panel.index[signal_pos]),
                "feature_max_date": pd.Timestamp(panel.index[signal_pos]),
                "entry_pos": entry_pos,
                "entry_date": pd.Timestamp(panel.index[entry_pos]),
                "exit_pos": exit_pos,
                "exit_date": pd.Timestamp(panel.index[exit_pos]),
                "spread_change20": float(panel.iloc[signal_pos]["spread_change20"]),
                "dgs2_change20": float(panel.iloc[signal_pos]["dgs2_change20"]),
            }
        )
        next_available = exit_pos + 1
    return events


def partition_events(
    events: list[dict[str, object]], *, train_fraction: float = 0.60
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    if not 0.0 < train_fraction < 1.0 or len(events) < 2:
        raise ValueError("partition requires at least two events and a proper fraction")
    ordered = sorted(events, key=lambda row: pd.Timestamp(row["signal_date"]))
    if len({pd.Timestamp(row["signal_date"]) for row in ordered}) != len(ordered):
        raise ValueError("signal dates must be unique")
    cutoff = max(1, min(len(ordered) - 1, int(np.floor(len(ordered) * train_fraction))))
    return ordered[:cutoff], ordered[cutoff:]


def holdout_identity_payload(events: list[dict[str, object]]) -> dict[str, object]:
    identities = [
        {
            key: str(row[key]) if key.endswith("date") else row[key]
            for key in (
                "signal_pos",
                "signal_date",
                "feature_max_date",
                "entry_pos",
                "entry_date",
                "exit_pos",
                "exit_date",
                "spread_change20",
                "dgs2_change20",
            )
        }
        for row in events
    ]
    encoded = json.dumps(identities, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return {
        "n_identity_rows": len(identities),
        "identities": identities,
        "identity_sha256": hashlib.sha256(encoded).hexdigest(),
        "outcome_metrics_read": False,
        "simulation_run": False,
        "option_pricing_calls": 0,
    }


def planning_risk_boundaries() -> dict[str, object]:
    return {
        "structure": "KRE $2-wide bull call debit spread",
        "planned_option_dte_min": 18,
        "planned_option_dte_max": 28,
        "underlying_horizon_sessions": 10,
        "capital_fit_usd": 200.0,
        "max_loss_usd": 200.0,
        "max_loss_semantics": (
            "frictionless planning width ceiling before actual debit, closing friction, "
            "assignment/exercise, or management-path validation"
        ),
        "max_lots": 1,
        "option_path_measured": False,
        "option_pricing_calls": 0,
    }


def frozen_geometry() -> dict[str, object]:
    """Return the exact predeclared geometry with unambiguous cost semantics."""
    return {
        "spread_change_observations": 20,
        "spread_change_threshold_percentage_points": 0.20,
        "dgs2_change_threshold_percentage_points": -0.10,
        "trend_filters": ["KRE close > SMA100", "SPY close > SMA100"],
        "rising_edge_only": True,
        "forward_sessions": FORWARD_SESSIONS,
        "entry_lag_sessions": 1,
        "nonoverlap": True,
        "train_fraction": 0.60,
        "holdout_fraction": 0.40,
        "underlying_round_trip_cost_bps": UNDERLYING_ROUND_TRIP_COST_BPS,
        "specificity_control": "same-date XLF ten-session return",
    }


def _circular_block_bootstrap_lb90(
    values: np.ndarray, *, block_size: int = 5, samples: int = 2_000
) -> float:
    if values.size == 0 or samples < 100:
        raise ValueError("bootstrap requires values and at least 100 samples")
    block = min(block_size, values.size)
    rng = np.random.default_rng(20260716)
    means = np.empty(samples, dtype=float)
    for sample in range(samples):
        draw: list[float] = []
        while len(draw) < values.size:
            start = int(rng.integers(0, values.size))
            draw.extend(float(values[(start + offset) % values.size]) for offset in range(block))
        means[sample] = float(np.mean(draw[: values.size]))
    return float(np.quantile(means, 0.05))


def evaluate_train(
    panel: pd.DataFrame,
    events: list[dict[str, object]],
    *,
    min_episodes: int = 24,
    min_years: int = 10,
    bootstrap_samples: int = 2_000,
) -> dict[str, object]:
    """Read train outcomes only and apply the complete frozen discovery conjunction."""
    if not {"kre", "xlf"}.issubset(panel.columns) or not events:
        raise ValueError("evaluation requires KRE/XLF panel and train events")
    if min_episodes < 1 or min_years < 1:
        raise ValueError("density gates must be positive")
    rows: list[dict[str, object]] = []
    previous_exit = -1
    integrity_violations: list[str] = []
    for event in events:
        signal_pos = int(event["signal_pos"])
        entry_pos = int(event["entry_pos"])
        exit_pos = int(event["exit_pos"])
        signal_date = pd.Timestamp(event["signal_date"])
        feature_date = pd.Timestamp(event["feature_max_date"])
        entry_date = pd.Timestamp(event["entry_date"])
        exit_date = pd.Timestamp(event["exit_date"])
        if not (
            feature_date == signal_date
            and signal_date < entry_date < exit_date
            and entry_pos == signal_pos + 1
            and exit_pos == entry_pos + FORWARD_SESSIONS
            and previous_exit < entry_pos
            and 0 <= signal_pos < entry_pos < exit_pos < len(panel)
            and pd.Timestamp(panel.index[signal_pos]) == signal_date
            and pd.Timestamp(panel.index[entry_pos]) == entry_date
            and pd.Timestamp(panel.index[exit_pos]) == exit_date
        ):
            integrity_violations.append(str(signal_date.date()))
            continue
        previous_exit = exit_pos
        kre_raw = float(panel.iloc[exit_pos]["kre"] / panel.iloc[entry_pos]["kre"] - 1.0)
        xlf_raw = float(panel.iloc[exit_pos]["xlf"] / panel.iloc[entry_pos]["xlf"] - 1.0)
        round_trip_cost = UNDERLYING_ROUND_TRIP_COST_BPS / 10_000.0
        kre_after_cost = kre_raw - round_trip_cost
        xlf_after_cost = xlf_raw - round_trip_cost
        rows.append(
            {
                "signal_date": str(signal_date.date()),
                "entry_date": str(entry_date.date()),
                "exit_date": str(exit_date.date()),
                "kre_return_after_10bps": kre_after_cost,
                "xlf_return_after_10bps": xlf_after_cost,
                "kre_minus_xlf": kre_after_cost - xlf_after_cost,
            }
        )
    if not rows:
        raise ValueError("no integrity-valid train episodes")
    kre = np.asarray([row["kre_return_after_10bps"] for row in rows], dtype=float)
    excess = np.asarray([row["kre_minus_xlf"] for row in rows], dtype=float)
    year_counts: dict[str, int] = {}
    for row in rows:
        year = str(row["signal_date"])[:4]
        year_counts[year] = year_counts.get(year, 0) + 1
    years = len(year_counts)
    tail_count = max(1, int(np.ceil(len(kre) * 0.10)))
    tail = float(np.mean(np.sort(kre)[:tail_count]))
    lb90 = _circular_block_bootstrap_lb90(excess, samples=bootstrap_samples)
    checks = {
        "at_least_min_train_episodes": len(rows) >= min_episodes,
        "at_least_min_train_years": years >= min_years,
        "kre_mean_after_10bps_positive": float(np.mean(kre)) > 0.0,
        "kre_minus_xlf_mean_positive": float(np.mean(excess)) > 0.0,
        "kre_minus_xlf_five_episode_block_lb90_positive": len(rows) >= 5 and lb90 > 0.0,
        "kre_positive_frequency_at_least_55pct": float(np.mean(kre > 0.0)) >= 0.55,
        "kre_minus_xlf_positive_frequency_at_least_52pct": float(np.mean(excess > 0.0)) >= 0.52,
        "kre_event_return_worst_decile_at_least_negative_7pct": tail >= -0.07,
        "zero_integrity_violations": not integrity_violations,
    }
    return {
        "n_train_episodes": len(rows),
        "n_train_years": years,
        "train_signal_year_counts": year_counts,
        "train_calendar_concentration_max_fraction": max(year_counts.values()) / len(rows),
        "kre_mean_return_after_10bps": float(np.mean(kre)),
        "xlf_mean_return_after_10bps": float(
            np.mean([row["xlf_return_after_10bps"] for row in rows])
        ),
        "kre_minus_xlf_mean": float(np.mean(excess)),
        "kre_minus_xlf_block_bootstrap_lb90": lb90,
        "kre_positive_frequency_after_cost": float(np.mean(kre > 0.0)),
        "kre_minus_xlf_positive_frequency": float(np.mean(excess > 0.0)),
        "kre_event_return_worst_decile_mean_after_10bps": tail,
        "integrity_violations": integrity_violations,
        "gate_checks": checks,
        "gate_pass": bool(all(checks.values())),
        "episodes": rows,
    }


def _dominant_failure(checks: dict[str, bool]) -> str:
    priority = [
        ("zero_integrity_violations", "chronology_or_population_integrity"),
        ("at_least_min_train_episodes", "insufficient_nonoverlapping_episode_density"),
        ("at_least_min_train_years", "insufficient_calendar_breadth"),
        ("kre_mean_after_10bps_positive", "negative_absolute_KRE_center"),
        ("kre_minus_xlf_mean_positive", "no_regional_bank_specificity_vs_XLF"),
        (
            "kre_minus_xlf_five_episode_block_lb90_positive",
            "relative_edge_not_stable_under_five_episode_blocks",
        ),
        ("kre_positive_frequency_at_least_55pct", "absolute_hit_rate_below_floor"),
        ("kre_minus_xlf_positive_frequency_at_least_52pct", "relative_hit_rate_below_floor"),
        (
            "kre_event_return_worst_decile_at_least_negative_7pct",
            "absolute_KRE_tail_below_floor",
        ),
    ]
    for key, label in priority:
        if not checks.get(key, False):
            return label
    return "none"


def run_lab(
    *,
    start_year: int,
    end_year: int,
    end_exclusive: str,
    cache_dir: Path,
    output_path: Path,
    bootstrap_samples: int = 10_000,
) -> dict[str, object]:
    """Run the frozen train-only experiment and write a strict replay artifact."""
    from scripts.fomc_information_resolution_train_lab import load_adjusted_ohlcv

    treasury_frames: list[pd.DataFrame] = []
    treasury_sources: list[dict[str, object]] = []
    for year in range(start_year, end_year + 1):
        frame, source = load_treasury_year(year, cache_dir=cache_dir / "treasury")
        treasury_frames.append(frame)
        treasury_sources.append(source)
    curve = pd.concat(treasury_frames).sort_index()
    if not curve.index.is_unique:
        raise ValueError("Treasury year concatenation created duplicate dates")

    market_sources: dict[str, dict[str, object]] = {}
    closes: dict[str, pd.Series] = {}
    for symbol in ("KRE", "XLF", "SPY"):
        price, source = load_adjusted_ohlcv(
            symbol,
            cache_dir=cache_dir / "market",
            start=f"{start_year}-01-01",
            end=end_exclusive,
        )
        market_sources[symbol] = source
        closes[symbol] = price["close"].copy()

    panel = build_feature_panel(curve, closes)
    events = freeze_events(panel, forward_sessions=FORWARD_SESSIONS)
    if len(events) >= 2:
        train_events, holdout_events = partition_events(events, train_fraction=0.60)
    elif events:
        train_events, holdout_events = list(events), []
    else:
        train_events, holdout_events = [], []

    holdout = holdout_identity_payload(holdout_events)
    if train_events:
        train_result = evaluate_train(
            panel,
            train_events,
            min_episodes=24,
            min_years=10,
            bootstrap_samples=bootstrap_samples,
        )
    else:
        checks = {
            "at_least_min_train_episodes": False,
            "at_least_min_train_years": False,
            "kre_mean_after_10bps_positive": False,
            "kre_minus_xlf_mean_positive": False,
            "kre_minus_xlf_five_episode_block_lb90_positive": False,
            "kre_positive_frequency_at_least_55pct": False,
            "kre_minus_xlf_positive_frequency_at_least_52pct": False,
            "kre_event_return_worst_decile_at_least_negative_7pct": False,
            "zero_integrity_violations": True,
        }
        train_result = {
            "n_train_episodes": 0,
            "n_train_years": 0,
            "gate_checks": checks,
            "gate_pass": False,
            "episodes": [],
        }
    gate_pass = bool(train_result["gate_pass"])
    checks = dict(train_result["gate_checks"])
    outcome = "STRATEGY_ADVANCED" if gate_pass else "FAMILY_CLOSED"
    failed = [key for key, passed in checks.items() if not passed]

    signal_dates = [pd.Timestamp(row["signal_date"]) for row in events]
    gaps = [int((right - left).days) for left, right in zip(signal_dates, signal_dates[1:])]
    script_path = Path(__file__).resolve()
    charter_path = (
        Path(__file__).resolve().parents[1]
        / "reports/trader-wakes/moa/2026-07-16T1123/strategy-charter.md"
    )
    artifact: dict[str, object] = {
        "schema_version": 1,
        "wake": "2026-07-16T1123",
        "generated_at": pd.Timestamp.now(tz="America/Los_Angeles").isoformat(),
        "phase": "BUILD",
        "authority": "research_only_L0_discovery",
        "candidate_id": "OFFICIAL_2S10S_BULL_STEEPENING_KRE_BULL_CALL_21D_V1",
        "family_id": "OFFICIAL_YIELD_CURVE_BULL_STEEPENING_REGIONAL_BANK_RELATIVE_UPDRIFT",
        "funnel_before": "F0_MECHANISM",
        "funnel_after": "F1_TRAIN" if gate_pass else "F0_MECHANISM",
        "bar": "discovery_bar_only",
        "living_capital_leader": None,
        "source_provenance": {
            "treasury": treasury_sources,
            "market": market_sources,
            "treasury_rows_joined": len(curve),
            "exact_common_completed_rows": len(panel),
            "common_start": str(panel.index[0].date()),
            "common_end": str(panel.index[-1].date()),
            "no_curve_forward_fill": True,
            "market_end_exclusive": end_exclusive,
        },
        "frozen_geometry": frozen_geometry(),
        "population": {
            "n_total_frozen_events": len(events),
            "n_train_events": len(train_events),
            "n_holdout_identity_events": len(holdout_events),
            "first_signal_date": str(signal_dates[0].date()) if signal_dates else None,
            "last_signal_date": str(signal_dates[-1].date()) if signal_dates else None,
            "consecutive_signal_gap_days_min": min(gaps) if gaps else None,
            "consecutive_signal_gaps_le_30_days": sum(gap <= 30 for gap in gaps),
        },
        "train_only_result": train_result,
        "sealed_holdout": holdout,
        "capital_planning_boundary": planning_risk_boundaries(),
        "validity": {
            "holdout_outcomes_read": False,
            "option_path_measured": False,
            "option_pricing_calls": 0,
            "observed_option_evidence": False,
            "proxy_option_evidence": False,
            "strict_json": True,
            "script_path": str(script_path),
            "script_sha256": hashlib.sha256(script_path.read_bytes()).hexdigest(),
            "charter_path": str(charter_path),
            "charter_sha256": hashlib.sha256(charter_path.read_bytes()).hexdigest(),
        },
        "strategy_decision": {
            "outcome": outcome,
            "decision": "F0_MECHANISM -> F1_TRAIN" if gate_pass else "F0_MECHANISM -> F0_MECHANISM",
            "failed_gates": failed,
            "dominant_failure": _dominant_failure(checks),
            "quarantine": (
                None
                if gate_pass
                else "Quarantine exact threshold/horizon/trend/control geometry; no threshold, horizon, sign, or option-wrapper salvage without a genuinely new evidence class."
            ),
            "capital_seat": False,
            "paper_status": False,
            "shadow_or_live_authority": False,
        },
    }
    encoded = json.dumps(artifact, indent=2, sort_keys=True, allow_nan=False) + "\n"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(encoded)
    temporary.replace(output_path)
    replay = json.loads(output_path.read_text())
    if replay != artifact:
        raise RuntimeError("strict JSON replay mismatch")
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=2006)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--end-exclusive", default="2026-07-16")
    parser.add_argument(
        "--cache-dir", type=Path, default=Path(".cache/platform/yield_curve_regional_bank")
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(
            ".cache/platform/yield_curve_regional_bank_train_lab_2026-07-16T1123.json"
        ),
    )
    parser.add_argument("--bootstrap-samples", type=int, default=10_000)
    args = parser.parse_args()
    artifact = run_lab(
        start_year=args.start_year,
        end_year=args.end_year,
        end_exclusive=args.end_exclusive,
        cache_dir=args.cache_dir,
        output_path=args.out,
        bootstrap_samples=args.bootstrap_samples,
    )
    print(
        json.dumps(
            {
                "out": str(args.out),
                "outcome": artifact["strategy_decision"]["outcome"],
                "population": artifact["population"],
                "failed_gates": artifact["strategy_decision"]["failed_gates"],
                "dominant_failure": artifact["strategy_decision"]["dominant_failure"],
            },
            indent=2,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
