#!/usr/bin/env python3
"""Official SEC Form 4 clustered-insider-buying train-only discovery lab.

BUILD/L0 only. The final chronological 40% remains identity-only; no option
pricing occurs. Original SEC quarterly Form 3/4/5 archives are cached under
.cache and hash-cited in the claim artifact.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
from typing import Any
import zipfile

import numpy as np
import pandas as pd
import requests

try:
    from scripts.fomc_information_resolution_train_lab import load_adjusted_ohlcv
except ModuleNotFoundError as exc:
    if exc.name != "scripts":
        raise
    from fomc_information_resolution_train_lab import load_adjusted_ohlcv  # type: ignore[no-redef]

CANDIDATE_ID = "SEC_FORM4_CLUSTERED_INSIDER_BUYING_CALL_21D_V1"
FAMILY_ID = "SEC_FORM4_CLUSTERED_OPEN_MARKET_BUYING_FORWARD_UPDRIFT"
PANEL = (
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "AMD", "NFLX", "TSLA",
    "COIN", "PLTR", "SMCI", "AVGO", "MU", "JPM", "XOM", "BAC", "F", "SOFI",
    "AAL", "PFE", "SNAP", "CCL",
)
SYMBOL_ALIASES = {"FB": "META", "GOOG": "GOOGL"}
SEC_ARCHIVE_BASE = "https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets"
SEC_SOURCE_PAGE = "https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets"
COMMON_EQUITY_RE = re.compile(r"(?:common|ordinary shares|capital stock)", re.I)
EXCLUDED_SECURITY_RE = re.compile(r"(?:preferred|unit|depositary|restricted|phantom)", re.I)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _parse_sec_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, format="%d-%b-%Y", errors="coerce").dt.tz_localize(None)


def _normalise_symbol(value: Any) -> str:
    symbol = str(value).strip().upper()
    symbol = SYMBOL_ALIASES.get(symbol, symbol)
    return symbol


def _read_tsv(archive: zipfile.ZipFile, name: str) -> pd.DataFrame:
    with archive.open(name) as handle:
        return pd.read_csv(handle, sep="\t", dtype=str, keep_default_na=False, low_memory=False)


def parse_quarter_archive(payload: bytes, *, archive_label: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Return accession-level qualified open-market purchases from one SEC ZIP."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile as exc:
        raise ValueError(f"invalid SEC ZIP {archive_label}") from exc
    required = {"SUBMISSION.tsv", "REPORTINGOWNER.tsv", "NONDERIV_TRANS.tsv"}
    if not required.issubset(set(archive.namelist())):
        raise ValueError(f"SEC ZIP {archive_label} missing required tables")
    submissions = _read_tsv(archive, "SUBMISSION.tsv")
    owners = _read_tsv(archive, "REPORTINGOWNER.tsv")
    transactions = _read_tsv(archive, "NONDERIV_TRANS.tsv")
    required_submission = {
        "ACCESSION_NUMBER", "FILING_DATE", "DOCUMENT_TYPE", "ISSUERCIK",
        "ISSUERTRADINGSYMBOL",
    }
    required_owner = {"ACCESSION_NUMBER", "RPTOWNERCIK", "RPTOWNER_RELATIONSHIP"}
    required_transaction = {
        "ACCESSION_NUMBER", "SECURITY_TITLE", "TRANS_DATE", "TRANS_FORM_TYPE",
        "TRANS_CODE", "TRANS_SHARES", "TRANS_PRICEPERSHARE", "TRANS_ACQUIRED_DISP_CD",
        "DIRECT_INDIRECT_OWNERSHIP",
    }
    if not required_submission.issubset(submissions.columns):
        raise ValueError(f"SEC ZIP {archive_label} submission schema mismatch")
    if not required_owner.issubset(owners.columns):
        raise ValueError(f"SEC ZIP {archive_label} owner schema mismatch")
    if not required_transaction.issubset(transactions.columns):
        raise ValueError(f"SEC ZIP {archive_label} transaction schema mismatch")

    submissions = submissions.loc[
        submissions["DOCUMENT_TYPE"].str.strip().eq("4"),
        list(required_submission),
    ].copy()
    submissions["symbol"] = submissions["ISSUERTRADINGSYMBOL"].map(_normalise_symbol)
    submissions = submissions.loc[submissions["symbol"].isin(PANEL)].copy()
    submissions["filing_date"] = _parse_sec_date(submissions["FILING_DATE"])
    submissions = submissions.loc[submissions["filing_date"].notna()].copy()

    relationships = owners["RPTOWNER_RELATIONSHIP"].str.strip()
    owners = owners.loc[
        relationships.str.contains("Officer|Director", regex=True, na=False),
        list(required_owner),
    ].copy()
    owners["RPTOWNERCIK"] = owners["RPTOWNERCIK"].str.strip()
    owners = owners.loc[owners["RPTOWNERCIK"].str.fullmatch(r"\d+")].copy()
    owner_map = (
        owners.groupby("ACCESSION_NUMBER", sort=False)["RPTOWNERCIK"]
        .agg(lambda values: tuple(sorted(set(values))))
        .to_dict()
    )

    title = transactions["SECURITY_TITLE"].str.strip()
    transactions = transactions.loc[
        transactions["TRANS_FORM_TYPE"].str.strip().eq("4")
        & transactions["TRANS_CODE"].str.strip().eq("P")
        & transactions["TRANS_ACQUIRED_DISP_CD"].str.strip().eq("A")
        & transactions["DIRECT_INDIRECT_OWNERSHIP"].str.strip().eq("D")
        & title.str.contains(COMMON_EQUITY_RE, na=False)
        & ~title.str.contains(EXCLUDED_SECURITY_RE, na=False),
        list(required_transaction),
    ].copy()
    transactions["trans_date"] = _parse_sec_date(transactions["TRANS_DATE"])
    transactions["shares"] = pd.to_numeric(transactions["TRANS_SHARES"], errors="coerce")
    transactions["price"] = pd.to_numeric(transactions["TRANS_PRICEPERSHARE"], errors="coerce")
    transactions["value_usd"] = transactions["shares"] * transactions["price"]
    transactions = transactions.loc[
        transactions["trans_date"].notna()
        & np.isfinite(transactions["shares"].to_numpy(dtype=float))
        & np.isfinite(transactions["price"].to_numpy(dtype=float))
        & (transactions["shares"] > 0.0)
        & (transactions["price"] > 0.0)
        & (transactions["value_usd"] >= 10_000.0)
    ].copy()

    merged = transactions.merge(
        submissions[["ACCESSION_NUMBER", "filing_date", "symbol", "ISSUERCIK"]],
        on="ACCESSION_NUMBER",
        how="inner",
        validate="many_to_one",
    )
    merged["filing_delay_days"] = (merged["filing_date"] - merged["trans_date"]).dt.days
    merged = merged.loc[merged["filing_delay_days"].between(0, 5, inclusive="both")].copy()
    merged["owner_ciks"] = merged["ACCESSION_NUMBER"].map(owner_map)
    merged = merged.loc[merged["owner_ciks"].map(lambda value: isinstance(value, tuple) and bool(value))]

    rows: list[dict[str, Any]] = []
    for accession, group in merged.groupby("ACCESSION_NUMBER", sort=True):
        issuer_ciks = sorted(set(group["ISSUERCIK"].astype(str).str.strip()))
        symbols = sorted(set(group["symbol"].astype(str)))
        filing_dates = sorted(set(pd.Timestamp(value) for value in group["filing_date"]))
        owner_ciks = sorted(set(cik for values in group["owner_ciks"] for cik in values))
        if len(issuer_ciks) != 1 or len(symbols) != 1 or len(filing_dates) != 1 or not owner_ciks:
            continue
        transaction_dates = sorted(set(pd.Timestamp(value) for value in group["trans_date"]))
        rows.append(
            {
                "archive_label": archive_label,
                "accession_number": str(accession),
                "issuer_cik": issuer_ciks[0],
                "symbol": symbols[0],
                "filing_date": filing_dates[0],
                "transaction_dates": tuple(transaction_dates),
                "owner_ciks": tuple(owner_ciks),
                "qualified_value_usd": float(group["value_usd"].sum()),
                "qualified_transaction_rows": int(len(group)),
                "max_filing_delay_days": int(group["filing_delay_days"].max()),
            }
        )
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.sort_values(["symbol", "filing_date", "accession_number"]).reset_index(drop=True)
    return frame, {
        "archive_label": archive_label,
        "sha256": _sha256_bytes(payload),
        "zip_bytes": len(payload),
        "submission_rows": int(len(submissions)),
        "qualified_accession_rows": int(len(frame)),
    }


def download_archives(
    cache_dir: Path,
    *,
    start_year: int,
    end_year: int,
    user_agent: str,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    if start_year > end_year or start_year < 2006:
        raise ValueError("invalid SEC archive year range")
    cache_dir.mkdir(parents=True, exist_ok=True)
    frames: list[pd.DataFrame] = []
    provenance: list[dict[str, Any]] = []
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"})
    for year in range(start_year, end_year + 1):
        for quarter in range(1, 5):
            label = f"{year}q{quarter}_form345.zip"
            path = cache_dir / label
            url = f"{SEC_ARCHIVE_BASE}/{label}"
            if path.exists():
                payload = path.read_bytes()
            else:
                response = session.get(url, timeout=90)
                if response.status_code != 200:
                    raise RuntimeError(f"SEC archive fetch failed {response.status_code}: {url}")
                downloaded = response.content
                zipfile.ZipFile(io.BytesIO(downloaded)).testzip()
                path.write_bytes(downloaded)
                # Claim-bearing evaluation always consumes the persisted representation.
                payload = path.read_bytes()
            frame, meta = parse_quarter_archive(payload, archive_label=label)
            meta.update({"url": url, "cache_path": str(path)})
            frames.append(frame)
            provenance.append(meta)
    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if combined.empty:
        raise ValueError("no qualified SEC purchase accessions in frozen panel")
    duplicates = combined.duplicated(subset=["accession_number"], keep=False)
    if duplicates.any():
        raise ValueError("duplicate accessions across SEC quarterly archives")
    combined = combined.sort_values(["symbol", "filing_date", "accession_number"]).reset_index(drop=True)
    return combined, provenance


def build_cluster_signals(
    filings: pd.DataFrame,
    *,
    cluster_days: int = 20,
    min_distinct_owners: int = 2,
    min_aggregate_value_usd: float = 100_000.0,
) -> list[dict[str, Any]]:
    """Freeze the first publicly knowable non-overlapping cluster signal per issuer."""
    required = {
        "accession_number", "issuer_cik", "symbol", "filing_date", "owner_ciks",
        "qualified_value_usd",
    }
    if not required.issubset(filings.columns):
        raise ValueError("filings missing cluster fields")
    if cluster_days < 1 or min_distinct_owners < 2 or min_aggregate_value_usd <= 0.0:
        raise ValueError("invalid cluster geometry")
    rows: list[dict[str, Any]] = []
    for symbol, symbol_rows in filings.groupby("symbol", sort=True):
        grouped: list[dict[str, Any]] = []
        for filing_date, date_rows in symbol_rows.groupby("filing_date", sort=True):
            grouped.append(
                {
                    "filing_date": pd.Timestamp(filing_date),
                    "accessions": tuple(sorted(set(date_rows["accession_number"].astype(str)))),
                    "owner_ciks": tuple(sorted(set(cik for values in date_rows["owner_ciks"] for cik in values))),
                    "qualified_value_usd": float(date_rows["qualified_value_usd"].sum()),
                    "issuer_ciks": tuple(sorted(set(date_rows["issuer_cik"].astype(str)))),
                }
            )
        last_signal: pd.Timestamp | None = None
        for current in grouped:
            date = current["filing_date"]
            if last_signal is not None and (date - last_signal).days <= cluster_days:
                continue
            window = [row for row in grouped if 0 <= (date - row["filing_date"]).days <= cluster_days]
            accessions = sorted(set(accession for row in window for accession in row["accessions"]))
            owner_ciks = sorted(set(cik for row in window for cik in row["owner_ciks"]))
            issuer_ciks = sorted(set(cik for row in window for cik in row["issuer_ciks"]))
            aggregate = float(sum(row["qualified_value_usd"] for row in window))
            if (
                len(accessions) < 2
                or len(owner_ciks) < min_distinct_owners
                or len(issuer_ciks) != 1
                or aggregate < min_aggregate_value_usd
            ):
                continue
            rows.append(
                {
                    "symbol": str(symbol),
                    "issuer_cik": issuer_ciks[0],
                    "signal_date": date,
                    "window_start": date - pd.Timedelta(days=cluster_days),
                    "accession_numbers": tuple(accessions),
                    "owner_ciks": tuple(owner_ciks),
                    "n_accessions": len(accessions),
                    "n_distinct_owners": len(owner_ciks),
                    "aggregate_value_usd": aggregate,
                }
            )
            last_signal = date
    return sorted(rows, key=lambda row: (row["signal_date"], row["symbol"]))


def _prepare_prices(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    prepared = frame.copy()
    prepared.index = pd.DatetimeIndex(pd.to_datetime(prepared.index)).tz_localize(None).normalize()
    prepared.columns = [str(column).strip().lower() for column in prepared.columns]
    if "close" not in prepared.columns:
        raise ValueError(f"{symbol} price frame missing close")
    prepared = prepared.loc[:, ["close"]].apply(pd.to_numeric, errors="coerce")
    if (
        prepared.empty
        or not prepared.index.is_unique
        or not prepared.index.is_monotonic_increasing
        or not np.isfinite(prepared.to_numpy(dtype=float)).all()
        or (prepared["close"] <= 0.0).any()
    ):
        raise ValueError(f"{symbol} prices must be unique, increasing, finite, and positive")
    prepared["ret20"] = prepared["close"] / prepared["close"].shift(20) - 1.0
    prepared["sma100"] = prepared["close"].rolling(100, min_periods=100).mean()
    return prepared


def freeze_price_blueprints(
    signals: list[dict[str, Any]],
    frames: dict[str, pd.DataFrame],
    *,
    forward_sessions: int = 10,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Attach lag-safe market geometry without reading forward returns."""
    if forward_sessions < 1 or "SPY" not in frames:
        raise ValueError("price blueprints require SPY and a positive horizon")
    prepared = {symbol: _prepare_prices(frame, symbol) for symbol, frame in frames.items()}
    spy = prepared["SPY"]
    rows: list[dict[str, Any]] = []
    rejects: list[dict[str, Any]] = []
    for signal in signals:
        symbol = str(signal["symbol"])
        signal_date = pd.Timestamp(signal["signal_date"]).normalize()
        if symbol not in prepared:
            rejects.append({"symbol": symbol, "signal_date": str(signal_date.date()), "reason": "missing_price_frame"})
            continue
        prices = prepared[symbol]
        feature_positions = np.flatnonzero(prices.index < signal_date)
        entry_positions = np.flatnonzero(prices.index > signal_date)
        spy_positions = np.flatnonzero(spy.index < signal_date)
        if not len(feature_positions) or not len(entry_positions) or not len(spy_positions):
            rejects.append({"symbol": symbol, "signal_date": str(signal_date.date()), "reason": "missing_lagged_or_entry_session"})
            continue
        feature_pos = int(feature_positions[-1])
        entry_pos = int(entry_positions[0])
        exit_pos = entry_pos + forward_sessions
        spy_pos = int(spy_positions[-1])
        if exit_pos >= len(prices):
            rejects.append({"symbol": symbol, "signal_date": str(signal_date.date()), "reason": "insufficient_forward_sessions"})
            continue
        ret20 = float(prices.iloc[feature_pos]["ret20"])
        spy_close = float(spy.iloc[spy_pos]["close"])
        spy_sma100 = float(spy.iloc[spy_pos]["sma100"])
        if not np.isfinite([ret20, spy_close, spy_sma100]).all():
            rejects.append({"symbol": symbol, "signal_date": str(signal_date.date()), "reason": "underwarmed_features"})
            continue
        row = dict(signal)
        row.update(
            {
                "feature_date": pd.Timestamp(prices.index[feature_pos]),
                "entry_date": pd.Timestamp(prices.index[entry_pos]),
                "exit_date": pd.Timestamp(prices.index[exit_pos]),
                "feature_pos": feature_pos,
                "entry_pos": entry_pos,
                "exit_pos": exit_pos,
                "ret20": ret20,
                "spy_feature_date": pd.Timestamp(spy.index[spy_pos]),
                "spy_above_sma100": bool(spy_close > spy_sma100),
            }
        )
        rows.append(row)
    return sorted(rows, key=lambda row: (row["signal_date"], row["symbol"])), rejects


def match_prior_controls(
    blueprints: list[dict[str, Any]],
    frames: dict[str, pd.DataFrame],
    *,
    source_coverage_start: pd.Timestamp,
    forward_sessions: int = 10,
    max_ret20_gap: float = 0.05,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Attach deterministic prior-only same-symbol no-reuse controls."""
    if max_ret20_gap <= 0.0:
        raise ValueError("control return gap must be positive")
    prepared = {symbol: _prepare_prices(frame, symbol) for symbol, frame in frames.items()}
    signal_dates_by_symbol: dict[str, list[pd.Timestamp]] = defaultdict(list)
    for row in blueprints:
        signal_dates_by_symbol[str(row["symbol"])].append(pd.Timestamp(row["signal_date"]))
    used_windows: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]] = defaultdict(list)
    matched: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    for row in blueprints:
        symbol = str(row["symbol"])
        signal_date = pd.Timestamp(row["signal_date"])
        prices = prepared[symbol]
        candidates: list[tuple[float, int, int]] = []
        for control_pos in range(100, len(prices) - forward_sessions - 1):
            feature_date = pd.Timestamp(prices.index[control_pos])
            entry_pos = control_pos + 1
            exit_pos = entry_pos + forward_sessions
            entry_date = pd.Timestamp(prices.index[entry_pos])
            exit_date = pd.Timestamp(prices.index[exit_pos])
            if feature_date < source_coverage_start or exit_date >= signal_date:
                continue
            ret20 = float(prices.iloc[control_pos]["ret20"])
            if not np.isfinite(ret20):
                continue
            ret_gap = abs(float(row["ret20"]) - ret20)
            if ret_gap > max_ret20_gap:
                continue
            prior_signals = [date for date in signal_dates_by_symbol[symbol] if date <= signal_date]
            if any(abs((feature_date - date).days) <= 20 for date in prior_signals):
                continue
            window = (entry_date, exit_date)
            if any(not (window[1] < prior[0] or window[0] > prior[1]) for prior in used_windows[symbol]):
                continue
            spy = prepared["SPY"]
            spy_positions = np.flatnonzero(spy.index <= feature_date)
            if not len(spy_positions):
                continue
            spy_pos = int(spy_positions[-1])
            spy_regime = float(spy.iloc[spy_pos]["close"]) > float(spy.iloc[spy_pos]["sma100"])
            if not np.isfinite(float(spy.iloc[spy_pos]["sma100"])) or bool(spy_regime) != bool(row["spy_above_sma100"]):
                continue
            distance = int(prices.index.get_loc(row["feature_date"]) - control_pos)
            candidates.append((ret_gap, distance, control_pos))
        if not candidates:
            unmatched.append({"symbol": symbol, "signal_date": str(signal_date.date()), "reason": "no_prior_same_regime_control"})
            continue
        ret_gap, distance, control_pos = min(candidates, key=lambda value: (value[0], value[1], value[2]))
        entry_pos = control_pos + 1
        exit_pos = entry_pos + forward_sessions
        item = dict(row)
        item.update(
            {
                "control_feature_pos": control_pos,
                "control_entry_pos": entry_pos,
                "control_exit_pos": exit_pos,
                "control_feature_date": pd.Timestamp(prices.index[control_pos]),
                "control_entry_date": pd.Timestamp(prices.index[entry_pos]),
                "control_exit_date": pd.Timestamp(prices.index[exit_pos]),
                "control_ret20": float(prices.iloc[control_pos]["ret20"]),
                "ret20_match_gap": float(ret_gap),
                "control_distance_sessions": distance,
            }
        )
        matched.append(item)
        used_windows[symbol].append((item["control_entry_date"], item["control_exit_date"]))
    return matched, unmatched


def _block_lower_bound(values: np.ndarray, *, samples: int, seed: int = 20260716) -> float:
    vector = np.asarray(values, dtype=float)
    if vector.ndim != 1 or not len(vector) or not np.isfinite(vector).all() or samples < 100:
        raise ValueError("bootstrap requires finite non-empty values and at least 100 samples")
    block = min(3, len(vector))
    count = int(np.ceil(len(vector) / block))
    offsets = np.arange(block)
    rng = np.random.default_rng(seed)
    estimates = np.empty(samples, dtype=float)
    for index in range(samples):
        starts = rng.integers(0, len(vector), size=count)
        draw = np.concatenate([vector[(start + offsets) % len(vector)] for start in starts])[: len(vector)]
        estimates[index] = float(draw.mean())
    return float(np.quantile(estimates, 0.10))


def _worst_decile(values: np.ndarray) -> float:
    count = max(1, int(np.ceil(len(values) * 0.10)))
    return float(np.sort(values)[:count].mean())


def evaluate_train(
    matched_train: list[dict[str, Any]],
    frames: dict[str, pd.DataFrame],
    *,
    n_train_eligible: int,
    round_trip_cost_bps: float = 10.0,
    bootstrap_samples: int = 10_000,
    min_pairs: int = 24,
    min_years: int = 6,
    min_symbols: int = 6,
) -> dict[str, Any]:
    if n_train_eligible < 1:
        raise ValueError("train requires eligible signals")
    prepared = {symbol: _prepare_prices(frame, symbol) for symbol, frame in frames.items()}
    pairs: list[dict[str, Any]] = []
    violations: list[str] = []
    used_accessions: set[str] = set()
    used_controls: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]] = defaultdict(list)
    cost = round_trip_cost_bps / 10_000.0
    for index, row in enumerate(matched_train):
        symbol = str(row["symbol"])
        prices = prepared[symbol]
        signal_date = pd.Timestamp(row["signal_date"])
        feature_date = pd.Timestamp(row["feature_date"])
        entry_date = pd.Timestamp(row["entry_date"])
        exit_date = pd.Timestamp(row["exit_date"])
        control_feature = pd.Timestamp(row["control_feature_date"])
        control_entry = pd.Timestamp(row["control_entry_date"])
        control_exit = pd.Timestamp(row["control_exit_date"])
        if not (feature_date < signal_date < entry_date < exit_date):
            violations.append(f"event_chronology:{index}")
        if not (control_feature < control_entry < control_exit < signal_date):
            violations.append(f"control_chronology:{index}")
        accessions = set(str(value) for value in row["accession_numbers"])
        if used_accessions.intersection(accessions):
            violations.append(f"cluster_accession_overlap:{index}")
        used_accessions.update(accessions)
        window = (control_entry, control_exit)
        if any(not (window[1] < prior[0] or window[0] > prior[1]) for prior in used_controls[symbol]):
            violations.append(f"control_reuse:{index}")
        used_controls[symbol].append(window)
        event_raw = float(prices.loc[exit_date, "close"] / prices.loc[entry_date, "close"] - 1.0)
        control_raw = float(prices.loc[control_exit, "close"] / prices.loc[control_entry, "close"] - 1.0)
        event_after_cost = event_raw - cost
        control_after_cost = control_raw - cost
        if not np.isfinite([event_raw, control_raw, event_after_cost, control_after_cost]).all():
            violations.append(f"nonfinite_outcome:{index}")
            continue
        pairs.append(
            {
                "symbol": symbol,
                "signal_date": str(signal_date.date()),
                "feature_date": str(feature_date.date()),
                "entry_date": str(entry_date.date()),
                "exit_date": str(exit_date.date()),
                "control_feature_date": str(control_feature.date()),
                "control_entry_date": str(control_entry.date()),
                "control_exit_date": str(control_exit.date()),
                "n_accessions": int(row["n_accessions"]),
                "n_distinct_owners": int(row["n_distinct_owners"]),
                "aggregate_value_usd": float(row["aggregate_value_usd"]),
                "event_raw_return": event_raw,
                "control_raw_return": control_raw,
                "event_return_after_10bps": event_after_cost,
                "control_return_after_10bps": control_after_cost,
                "paired_excess": event_after_cost - control_after_cost,
                "ret20_match_gap": float(row["ret20_match_gap"]),
                "control_distance_sessions": int(row["control_distance_sessions"]),
            }
        )
    events = np.asarray([row["event_return_after_10bps"] for row in pairs], dtype=float)
    controls = np.asarray([row["control_return_after_10bps"] for row in pairs], dtype=float)
    paired = events - controls
    years = sorted({pd.Timestamp(row["signal_date"]).year for row in pairs})
    symbols = sorted({row["symbol"] for row in pairs})
    support = len(pairs) / n_train_eligible
    event_mean = float(events.mean()) if len(events) else None
    paired_mean = float(paired.mean()) if len(paired) else None
    lower = _block_lower_bound(paired, samples=bootstrap_samples) if len(paired) else None
    positive_frequency = float(np.mean(events > 0.0)) if len(events) else None
    tail = _worst_decile(events) if len(events) else None
    gate_checks = {
        "minimum_24_train_pairs": len(pairs) >= min_pairs,
        "minimum_6_signal_years": len(years) >= min_years,
        "minimum_6_distinct_symbols": len(symbols) >= min_symbols,
        "minimum_70pct_control_support": support >= 0.70,
        "event_mean_after_10bps_above_25bps": event_mean is not None and event_mean > 0.0025,
        "paired_excess_mean_above_20bps": paired_mean is not None and paired_mean > 0.0020,
        "paired_excess_block_bootstrap_lb90_positive": lower is not None and lower > 0.0,
        "positive_frequency_at_least_55pct": positive_frequency is not None and positive_frequency >= 0.55,
        "event_return_worst_decile_at_least_negative_8pct": tail is not None and tail >= -0.08,
        "zero_integrity_violations": not violations,
    }
    return {
        "n_train_eligible_signals": int(n_train_eligible),
        "n_matched_pairs": len(pairs),
        "signal_years": years,
        "symbols": symbols,
        "control_support": support,
        "event_mean_return_after_10bps": event_mean,
        "control_mean_return_after_10bps": float(controls.mean()) if len(controls) else None,
        "paired_excess_mean": paired_mean,
        "paired_excess_median": float(np.median(paired)) if len(paired) else None,
        "paired_excess_block_bootstrap_lb90": lower,
        "positive_frequency": positive_frequency,
        "event_return_worst_decile_mean": tail,
        "median_control_distance_sessions": float(np.median([row["control_distance_sessions"] for row in pairs])) if pairs else None,
        "max_control_distance_sessions": max((row["control_distance_sessions"] for row in pairs), default=None),
        "round_trip_underlying_cost_bps": round_trip_cost_bps,
        "bootstrap_samples": bootstrap_samples,
        "bootstrap_block_length_pairs": 3,
        "integrity_violations": violations,
        "gate_checks": gate_checks,
        "gate_pass": bool(all(gate_checks.values())),
        "pairs": pairs,
    }


def _identity_payload(rows: list[dict[str, Any]], eligible_count: int) -> dict[str, Any]:
    identities = [
        {
            "symbol": str(row["symbol"]),
            "signal_date": str(pd.Timestamp(row["signal_date"]).date()),
            "entry_date": str(pd.Timestamp(row["entry_date"]).date()),
            "exit_date": str(pd.Timestamp(row["exit_date"]).date()),
            "control_feature_date": str(pd.Timestamp(row["control_feature_date"]).date()),
            "control_entry_date": str(pd.Timestamp(row["control_entry_date"]).date()),
            "control_exit_date": str(pd.Timestamp(row["control_exit_date"]).date()),
        }
        for row in rows
    ]
    return {
        "n_eligible_signals": eligible_count,
        "n_matched_pairs": len(identities),
        "identity_sha256": _sha256_bytes(_canonical_json_bytes(identities)),
        "first_signal_date": identities[0]["signal_date"] if identities else None,
        "last_signal_date": identities[-1]["signal_date"] if identities else None,
        "identity_fields": list(identities[0]) if identities else [],
        "outcome_metrics_read": False,
        "simulation_run": False,
        "option_pricing_calls": 0,
    }


def run_lab(
    filings: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
    *,
    sec_provenance: list[dict[str, Any]],
    price_provenance: dict[str, Any],
    train_fraction: float = 0.60,
    bootstrap_samples: int = 10_000,
) -> dict[str, Any]:
    signals = build_cluster_signals(filings)
    blueprints, price_rejects = freeze_price_blueprints(signals, frames)
    if len(blueprints) < 2:
        raise ValueError("fewer than two price-complete cluster signals")
    split = int(len(blueprints) * train_fraction)
    if split < 1 or split >= len(blueprints):
        raise ValueError("train/holdout split is empty")
    train_last_date = pd.Timestamp(blueprints[split - 1]["signal_date"])
    matched, unmatched = match_prior_controls(
        blueprints,
        frames,
        source_coverage_start=pd.Timestamp(f"{min(int(item['archive_label'][:4]) for item in sec_provenance)}-01-01"),
    )
    matched_train = [row for row in matched if pd.Timestamp(row["signal_date"]) <= train_last_date]
    matched_holdout = [row for row in matched if pd.Timestamp(row["signal_date"]) > train_last_date]
    eligible_train = [row for row in blueprints if pd.Timestamp(row["signal_date"]) <= train_last_date]
    eligible_holdout = [row for row in blueprints if pd.Timestamp(row["signal_date"]) > train_last_date]
    train = evaluate_train(
        matched_train,
        frames,
        n_train_eligible=len(eligible_train),
        bootstrap_samples=bootstrap_samples,
    )
    failed = [name for name, passed in train["gate_checks"].items() if not passed]
    advanced = bool(train["gate_pass"])
    dominant = None
    if not advanced:
        dominant = (
            "The exact official clustered-buying geometry failed the frozen train discovery conjunction. "
            f"Only these gates failed: {', '.join(failed)}; "
            f"event_mean_after_10bps={train['event_mean_return_after_10bps']}; "
            f"paired_excess_mean={train['paired_excess_mean']}; "
            f"lb90={train['paired_excess_block_bootstrap_lb90']}."
        )
    return {
        "schema_version": "sec_form4_clustered_buying_train_lab.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "BUILD_L0_UNDERLYING_DISCOVERY",
        "paper_only": True,
        "candidate_id": CANDIDATE_ID,
        "family_id": FAMILY_ID,
        "economic_mechanism": (
            "Multiple officers/directors spending their own capital on timely disclosed direct open-market "
            "common-share purchases may convey issuer-specific valuation information that diffuses over ten sessions."
        ),
        "forecast_type": "issuer_specific_bullish_ten_session_drift",
        "planned_option_structure": "future_conditional_18_24dte_2wide_bull_call_debit_spread",
        "capital_fit_usd": 200.0,
        "max_loss_usd": 200.0,
        "max_loss_label": "frictionless_planning_structural_debit_cap_before_closing_friction",
        "max_lots": 1,
        "funnel_stage_before": "F0_MECHANISM",
        "funnel_stage_after": "F1_TRAIN" if advanced else "F0_MECHANISM",
        "strategy_outcome": "STRATEGY_ADVANCED" if advanced else "FAMILY_CLOSED",
        "strategy_advancement": advanced,
        "claim_bar": "L0_DISCOVERY_ONLY",
        "closed_families": [] if advanced else [CANDIDATE_ID, FAMILY_ID],
        "dominant_failure_mechanism": dominant,
        "frozen_panel": list(PANEL),
        "filing_filter": {
            "document_type": "original Form 4 only",
            "transaction_code": "P",
            "acquired_disposed": "A",
            "ownership": "D",
            "relationship": "Officer or Director",
            "security": "common/ordinary/capital stock excluding preferred, units, depositary, restricted, phantom",
            "minimum_transaction_value_usd": 10_000.0,
            "maximum_filing_delay_calendar_days": 5,
        },
        "cluster_filter": {
            "calendar_days": 20,
            "minimum_distinct_owner_ciks": 2,
            "minimum_distinct_accessions": 2,
            "minimum_aggregate_value_usd": 100_000.0,
            "overlapping_signal_suppression_days": 20,
        },
        "population": {
            "qualified_accessions": int(len(filings)),
            "cluster_signals": len(signals),
            "price_complete_blueprints": len(blueprints),
            "train_eligible": len(eligible_train),
            "holdout_eligible": len(eligible_holdout),
            "price_rejects": price_rejects,
            "control_unmatched": unmatched,
        },
        "train": train,
        "holdout": _identity_payload(matched_holdout, len(eligible_holdout)),
        "failed_gates": failed,
        "sec_data_provenance": {
            "source_page": SEC_SOURCE_PAGE,
            "quarterly_archives": sec_provenance,
            "source_is_official_sec": True,
        },
        "price_data_provenance": price_provenance,
        "methodology_boundaries": {
            "point_in_time": "signal is original Form 4 filing date; entry is first session close strictly after filing",
            "controls": "prior-only same-symbol, no-reuse, same broad-market SMA100 state, nearest ret20 within 5pp; outcome fully realized before signal",
            "holdout": "chronological final 40% identity only; outcomes unread; no option simulation",
            "cost": "10 bps underlying round-trip hurdle, not option spread/fill friction",
            "tail_metric": "worst-decile mean is computed from event returns after 10 bps, not paired excess",
            "option_marks": "zero; future bull-call expression is planning context only",
            "population": "fixed present-day panel has survivorship and ticker-alias limitations",
            "bulk_data_limit": "quarterly data has filing date but not acceptance timestamp; next-session entry avoids same-day timing ambiguity",
        },
        "all_train_rows_are_inspected_development_data": True,
        "f2_claim": False,
        "l1_claim": False,
        "option_pricing_calls": 0,
        "authority": "research only; no L1, capital seat, registry, paper, shadow, broker, funding, arm, or live authority",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=2014)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--price-end", default="2026-07-16")
    parser.add_argument("--sec-cache-dir", default=".cache/platform/sec_form345")
    parser.add_argument("--price-cache-dir", default=".cache/platform/sec_form4_prices")
    parser.add_argument("--sec-user-agent", default="TraderResearch/1.0 paper-only local research")
    parser.add_argument("--bootstrap-samples", type=int, default=10_000)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    filings, sec_provenance = download_archives(
        Path(args.sec_cache_dir),
        start_year=args.start_year,
        end_year=args.end_year,
        user_agent=args.sec_user_agent,
    )
    signals = build_cluster_signals(filings)
    signal_symbols = sorted({str(row["symbol"]) for row in signals})
    frames: dict[str, pd.DataFrame] = {}
    price_provenance: dict[str, Any] = {}
    for symbol in ["SPY", *signal_symbols]:
        frame, meta = load_adjusted_ohlcv(
            symbol,
            cache_dir=Path(args.price_cache_dir),
            start=f"{args.start_year}-01-01",
            end=args.price_end,
        )
        frames[symbol] = frame
        price_provenance[symbol] = meta
    payload = run_lab(
        filings,
        frames,
        sec_provenance=sec_provenance,
        price_provenance=price_provenance,
        bootstrap_samples=args.bootstrap_samples,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    summary = {
        "candidate_id": payload["candidate_id"],
        "strategy_outcome": payload["strategy_outcome"],
        "funnel_stage_after": payload["funnel_stage_after"],
        "qualified_accessions": payload["population"]["qualified_accessions"],
        "cluster_signals": payload["population"]["cluster_signals"],
        "price_complete_blueprints": payload["population"]["price_complete_blueprints"],
        "train_pairs": payload["train"]["n_matched_pairs"],
        "event_mean": payload["train"]["event_mean_return_after_10bps"],
        "paired_mean": payload["train"]["paired_excess_mean"],
        "lb90": payload["train"]["paired_excess_block_bootstrap_lb90"],
        "failed_gates": payload["failed_gates"],
        "out": str(out),
    }
    print(json.dumps(summary, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
