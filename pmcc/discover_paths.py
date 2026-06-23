from __future__ import annotations

import pandas as pd

from data import build


def discover_tsla_patterns(*, period: str = "10y") -> pd.DataFrame:
    """Summarize recurring TSLA spot patterns for PMCC path design."""
    df = build("TSLA", period=period)
    ret = df["close"].pct_change()

    rows: list[dict] = []

    big_up = int((ret >= 0.08).sum())
    big_down = int((ret <= -0.08).sum())
    rows.append({
        "pattern": "single_day |ret|≥8%",
        "count_10y": big_up + big_down,
        "detail": f"{big_up} up-days, {big_down} down-days",
        "pmcc_path": "single_day_rip_10 / gap_flush",
    })

    rip_flush = 0
    examples: list[str] = []
    for i in range(1, len(df) - 5):
        if ret.iloc[i] >= 0.08:
            fwd5 = df["close"].iloc[i + 5] / df["close"].iloc[i] - 1
            if fwd5 <= -0.04:
                rip_flush += 1
                if len(examples) < 5:
                    examples.append(f"{df.index[i].date()} +{ret.iloc[i]:.0%} → 5d {fwd5:+.0%}")
    rows.append({
        "pattern": "gap rip ≥8% then −4% within 5d",
        "count_10y": rip_flush,
        "detail": "; ".join(examples),
        "pmcc_path": "gap_rip_flush",
    })

    double = 0
    for i in range(1, len(df) - 90):
        window = ret.iloc[i : i + 90]
        ups = window[window >= 0.08]
        downs = window[window <= -0.06]
        if len(ups) >= 1 and len(downs) >= 1 and len(window[abs(window) >= 0.06]) >= 4:
            double += 1
    rows.append({
        "pattern": "90d: ≥1 +8% day AND ≥1 −6% day AND 4+ |6%| days",
        "count_10y": double,
        "detail": "classic rip/flush chop within a quarter",
        "pmcc_path": "gap_whipsaw_double",
    })

    whipsaw_60 = 0
    for i in range(60, len(df) - 60, 5):
        w = ret.iloc[i : i + 60]
        big = w[abs(w) >= 0.06]
        if len(big) >= 4 and (big > 0).sum() >= 2 and (big < 0).sum() >= 2:
            whipsaw_60 += 1
    rows.append({
        "pattern": "60d mixed-sign whipsaw (4+ |6%| days)",
        "count_10y": whipsaw_60,
        "detail": "net flat-ish but violent two-way moves",
        "pmcc_path": "tsla_range_chop",
    })

    monthly = df["close"].resample("ME").agg(lambda s: (s.max() - s.min()) / s.iloc[0])
    top = monthly.sort_values(ascending=False).head(3)
    rows.append({
        "pattern": "worst monthly range (high-low)/open",
        "count_10y": 3,
        "detail": ", ".join(f"{idx.date()}: {v:.0%}" for idx, v in top.items()),
        "pmcc_path": "moonshot / v_recovery windows",
    })

    return pd.DataFrame(rows)


def format_discovery(df: pd.DataFrame) -> str:
    lines = ["# TSLA pattern discovery (10y history)", ""]
    for _, r in df.iterrows():
        lines.append(f"## {r['pattern']}")
        lines.append(f"- Count: **{r['count_10y']}**")
        lines.append(f"- Detail: {r['detail']}")
        lines.append(f"- PMCC path: `{r['pmcc_path']}`")
        lines.append("")
    return "\n".join(lines)