#!/usr/bin/env python3
"""
Streamlit dashboard — daily desk + research.

  Today    — open positions, playbook alerts, new short-premium signals
  Research — PMCC pair exploration, backtest, regime suite

Run with:  just run
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from data import build
from backtest import Backtester, compute_metrics, trades_to_dataframe
from strategies import pick_entry, check_exits, pick_roll, get_config
from scenarios import REGIMES, canonical_window
from live import make_recommendation
from positions import (
    POSITIONS_PATH,
    load_positions,
    save_positions,
    check_position,
    _exit_target_dollars,
    _DECISION_ACTION,
)


def _format_cell(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return f"{v:.6g}"
    return str(v)


def _display_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        out[col] = out[col].map(_format_cell)
    return out


def _sanitize_multiselect(key: str, options: list[str], *, default_n: int = 3) -> None:
    if key in st.session_state:
        st.session_state[key] = [x for x in st.session_state[key] if x in options]
    elif options:
        st.session_state[key] = options[: min(default_n, len(options))]


_PMCC_LEVEL_ICON = {"alert": "🚨", "warn": "⚠️", "ok": "✅", "info": "ℹ️"}


st.set_page_config(page_title="TSLA / TSLL options", layout="wide")

st.sidebar.title("Options desk")
st.sidebar.caption(
    "Config lives in `strategies.py`. "
    "CLI: `just backtest` · `just scenarios` · `just pmcc-scan`"
)


# ─── Cached loaders ───────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def load_data(ticker: str, period: str = "5y") -> pd.DataFrame:
    return build(ticker, period=period)


@st.cache_data(ttl=3600)
def run_full_backtest(ticker: str, period: str = "5y") -> tuple[pd.DataFrame, dict]:
    df = load_data(ticker, period)
    cfg = get_config(ticker)
    bt = Backtester(
        df=df, config=cfg, entry_fn=pick_entry, exit_fn=check_exits, ticker=ticker,
        roll_fn=pick_roll if getattr(cfg, "roll_on_max_loss", False) else None,
    )
    bt.run()
    trades_df = trades_to_dataframe(bt.trades)
    metrics = compute_metrics(bt.trades)
    if not trades_df.empty:
        trades_df = trades_df.sort_values("exit_date").reset_index(drop=True)
        trades_df["cumulative_pnl"] = trades_df["pnl_per_contract"].cumsum()
    return trades_df, metrics


@st.cache_data(ttl=3600)
def run_scenarios(ticker: str) -> pd.DataFrame:
    df = load_data(ticker)
    cfg = get_config(ticker)
    rows = []
    for regime in REGIMES:
        w = canonical_window(df, ticker, regime)
        if w is None:
            rows.append({"regime": regime, "available": False})
            continue
        bt = Backtester(
            df=w, config=cfg, entry_fn=pick_entry, exit_fn=check_exits, ticker=ticker,
            roll_fn=pick_roll if getattr(cfg, "roll_on_max_loss", False) else None,
        )
        bt.run()
        m = compute_metrics(bt.trades)
        ret = (w["close"].iloc[-1] - w["close"].iloc[0]) / w["close"].iloc[0]
        rows.append({
            "regime": regime,
            "available": True,
            "start": w.index[0].date(),
            "end": w.index[-1].date(),
            "underlying_ret_pct": ret * 100,
            "n_trades": m.get("n_trades", 0),
            "win_rate_pct": m.get("win_rate_pct", 0),
            "total_pnl": m.get("total_pnl_per_contract", 0),
            "max_dd": m.get("max_dd_per_contract", 0),
            "dominant_exit": max(m.get("exit_reasons", {"-": 0}).items(), key=lambda kv: kv[1])[0],
        })
    return pd.DataFrame(rows)


@st.cache_data(ttl=1800)
def load_pmcc_grid(preset: str, refresh: bool) -> tuple[float, pd.DataFrame, str]:
    from pmcc.analyze import build_pmcc_grid
    from pmcc.chain_data import chain_fetch_meta, format_chain_source
    from pmcc.config import PmccConfig, apply_preset

    cfg = apply_preset(PmccConfig(ticker="TSLA"), preset)
    cfg = PmccConfig(**{**cfg.__dict__, "chain_refresh": refresh})
    if preset == "bullish":
        cfg = PmccConfig(**{**cfg.__dict__, "target_spot": 550.0})
    spot, grid = build_pmcc_grid(cfg)
    return spot, grid, format_chain_source(chain_fetch_meta())


@st.cache_data(ttl=1800)
def load_call_chain(ticker: str, refresh: bool) -> tuple[float, pd.DataFrame]:
    from pmcc.chain_data import fetch_call_chain

    return fetch_call_chain(ticker, refresh=refresh)


@st.cache_data(ttl=1800)
def run_pmcc_daily_summary(
    preset: str, leaps_strike: float, short_strike: float, spot: float, refresh: bool,
) -> pd.DataFrame:
    from pmcc.config import PmccConfig, apply_preset
    from pmcc.daily_playthrough import build_daily_paths, daily_policy, run_all_daily_paths
    from pmcc.playthrough import POLICY_BY_PRESET, PlayPolicy
    from pmcc.scenarios import PmccPair
    from pmcc.tune import load_tuned_policy

    cfg = apply_preset(PmccConfig(ticker="TSLA"), preset)
    cfg = PmccConfig(**{**cfg.__dict__, "chain_refresh": refresh})
    if preset == "bullish":
        cfg = PmccConfig(**{**cfg.__dict__, "target_spot": 550.0})
    _, grid, _ = load_pmcc_grid(preset, refresh)
    m = grid[(grid.leaps_strike == leaps_strike) & (grid.short_strike == short_strike)]
    if m.empty:
        return pd.DataFrame()
    pair = PmccPair.from_row(m.iloc[0], spot)
    base = POLICY_BY_PRESET.get(preset, PlayPolicy())
    policy = daily_policy(load_tuned_policy(preset, leaps_strike, short_strike, base))
    key_paths = tuple(
        p for p in build_daily_paths(pair.leaps_dte)
        if p.name in {
            "steady_bear", "rip_plateau", "moonshot", "single_day_rip_10",
            "gap_rip_then_plateau", "double_gap_rip", "steady_bull",
            "gap_rip_flush", "gap_whipsaw_double", "tsla_range_chop", "post_earnings_whipsaw",
        }
    )
    _, summary = run_all_daily_paths(pair, key_paths, policy, r=cfg.risk_free_rate)
    return summary


@st.cache_data(ttl=3600)
def load_pmcc_pair_scan(preset: str, refresh: bool) -> tuple[pd.DataFrame, str]:
    from pmcc.pair_scan import run_full_scan

    scan, meta = run_full_scan(
        preset=preset, ticker="TSLA", refresh_chain=refresh, use_cache=not refresh,
    )
    if meta is None:
        return pd.DataFrame(), "no scan — run `just pmcc-scan --refresh`"
    label = (
        f"{meta.n_pairs} pairs @ ${meta.spot:,.2f} "
        f"({meta.scanned_at.strftime('%Y-%m-%d %H:%M')} UTC)"
    )
    return scan, label


@st.cache_data(ttl=3600)
def load_pmcc_full_scan(preset: str) -> tuple[pd.DataFrame, str]:
    from pmcc.pair_scan import load_scan

    scan, meta = load_scan(preset, "TSLA", mode="full")
    if meta is None or scan.empty:
        return pd.DataFrame(), "no full scan — run `just pmcc-scan --mode full --refresh`"
    label = (
        f"{meta.n_pairs} cells @ ${meta.spot:,.2f} "
        f"({meta.scanned_at.strftime('%Y-%m-%d %H:%M')} UTC)"
    )
    return scan, label


def _pmcc_market_banner(chain_meta) -> None:
    from pmcc.market_hours import cache_policy_label, is_regular_trading_session

    if is_regular_trading_session():
        if chain_meta and chain_meta.age_minutes > 30:
            st.warning(
                f"Market open — chain is {chain_meta.age_minutes:.0f}m old. "
                "Check **Refresh chain** for live quotes."
            )
        else:
            st.success("Market open — chain loaded.")
    else:
        st.info(f"Market closed — {cache_policy_label()}")


# ─── Header ───────────────────────────────────────────────────────────────
st.title("TSLA / TSLL options desk")
st.caption("**Today** = entry picks, open positions, signals · **Research** = width/DTE & validation")

tab_today, tab_research = st.tabs(["Today", "Research"])


# ═══════════════════════════════════════════════════════════════════════════
# TODAY — unified PMCC desk
# ═══════════════════════════════════════════════════════════════════════════
with tab_today:
    from pmcc.chain_data import chain_fetch_meta, format_chain_source
    from pmcc.desk import build_position_rows, build_situation, select_next_short
    from pmcc.positions import (
        PMCC_POSITIONS_PATH,
        check_pmcc_position,
        load_pmcc_positions,
        save_pmcc_positions,
    )
    from pmcc.staged_entry import build_tsla_staged_entry_plan

    c_pmcc_preset, c_pmcc_refresh = st.columns([1, 2])
    pmcc_preset = c_pmcc_preset.selectbox(
        "PMCC preset", ["managed", "balanced", "bullish", "income"], key="today_pmcc_preset",
    )
    pmcc_refresh = c_pmcc_refresh.checkbox("Refresh PMCC chain", value=False, key="today_pmcc_refresh")

    spot_pmcc = None
    plan_chain = pd.DataFrame()
    chain_meta = None
    try:
        spot_pmcc, plan_chain = load_call_chain("TSLA", pmcc_refresh)
        chain_meta = chain_fetch_meta()
        _pmcc_market_banner(chain_meta)
        st.caption(format_chain_source(chain_meta))
    except Exception as ex:
        st.error(f"PMCC chain load failed: {ex}")

    pmcc_records = load_pmcc_positions()
    pmcc_statuses: list[dict] = []
    staged = None

    if spot_pmcc is not None:
        try:
            staged = build_tsla_staged_entry_plan(pmcc_records, plan_chain, spot=spot_pmcc)
        except Exception as ex:
            st.warning(f"Staged plan unavailable: {ex}")
        for r in pmcc_records:
            try:
                pmcc_statuses.append(check_pmcc_position(r, spot_pmcc, preset=pmcc_preset))
            except Exception as ex:
                st.warning(
                    f"Position check failed for LEAPS {r.get('leaps_strike', '?')}: {ex}"
                )

    situation = build_situation(
        spot=spot_pmcc or 0.0,
        chain_age_minutes=chain_meta.age_minutes if chain_meta else None,
        statuses=pmcc_statuses,
        staged=staged,
    )

    # ── Block 1: Situation bar ────────────────────────────────────────────
    age_caption = (
        f"chain {situation['chain_age_minutes']:.0f}m old"
        if situation.get("chain_age_minutes") is not None else "chain age —"
    )
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("TSLA spot", f"${situation['spot']:.2f}" if spot_pmcc else "—", age_caption)
    icon = _PMCC_LEVEL_ICON.get(situation["primary_level"], "•")
    s2.metric("Next action", f"{icon} {situation['primary_action']}")
    s3.metric("Patience", situation["patience_budget"])
    s4.metric("Catalyst", situation["catalyst"][:40] + ("…" if len(situation["catalyst"]) > 40 else ""))
    if situation["primary_detail"]:
        st.caption(situation["primary_detail"])
    expires = situation["patience_expires"]
    if expires.get("label") and expires["label"] != "—":
        st.markdown(f"**{expires['label']}** ({expires.get('explanation', '')})")

    # ── Block 2: MY POSITIONS ───────────────────────────────────────────────
    st.subheader("MY POSITIONS")

    if not pmcc_records:
        st.caption(f"No diagonals in `{PMCC_POSITIONS_PATH.name}`.")
    elif spot_pmcc is None:
        st.warning("Chain unavailable — cannot mark positions.")
    else:
        pos_rows = build_position_rows(pmcc_statuses, spot_pmcc)
        display_cols = [
            "diagonal", "leg", "strike_exp_dte", "entry_cost", "mark",
            "leg_pnl", "net_pnl", "delta", "per_day", "upside_pct", "status",
        ]
        st.dataframe(
            pd.DataFrame(pos_rows)[display_cols],
            hide_index=True,
            width="stretch",
        )

        seen_diag: set[str] = set()
        for i, s in enumerate(pmcc_statuses):
            p = s["pair"]
            diag_key = f"{p.leaps_strike}"
            if diag_key in seen_diag:
                continue
            seen_diag.add(diag_key)
            icon = _PMCC_LEVEL_ICON.get(s["primary_level"], "•")
            label = (
                f"{icon} {int(p.leaps_strike)}"
                f"{'' if s.get('no_open_short') else f'/{int(p.short_strike)}'}"
                f" — playbook"
            )
            with st.expander(label, expanded=s["primary_level"] in ("alert", "warn")):
                for item in s["checks"]:
                    lvl = item["level"]
                    fn = {"alert": st.error, "warn": st.warning, "info": st.info}.get(lvl, st.success)
                    fn(f"**{item['rule']}** — {item['detail']}")
                if s.get("no_open_short"):
                    clock = s.get("closed_short_clock")
                    if clock:
                        st.markdown("**Premium clock (closed shorts)**")
                        clock_rows = []
                        for key in ("floor", "good", "strong"):
                            t = clock["targets"][key]
                            clock_rows.append({
                                "tier": key,
                                "target $/d": f"${t['portfolio_target_daily']:.0f}",
                                "days covered": f"{t['portfolio_days_covered']:.1f}",
                                "wait budget": f"{t['portfolio_wait_days']:.1f}d",
                                "until": t.get("portfolio_budget_until", "—"),
                            })
                        st.dataframe(pd.DataFrame(clock_rows), hide_index=True, width="stretch")
                        st.caption(f"Reload mode: {clock.get('reload_mode', '—')}")
                if st.button("Remove position", key=f"pmcc_rm_{i}"):
                    rec = s["record"]
                    fresh = [
                        x for x in load_pmcc_positions()
                        if not (
                            float(x.get("leaps_strike", -1)) == float(rec.get("leaps_strike", -2))
                            and str(x.get("leaps_expiration", ""))[:10]
                            == str(rec.get("leaps_expiration", ""))[:10]
                        )
                    ]
                    save_pmcc_positions(fresh)
                    st.rerun()

        with st.expander("Add / edit PMCC positions"):
            with st.form("add_pmcc_position", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                in_leaps_k = c1.number_input("LEAPS strike", step=5.0, value=380.0)
                in_leaps_exp = c2.date_input("LEAPS exp")
                in_leaps_debit = c3.number_input("LEAPS debit $", step=50.0, value=11000.0)
                c4, c5, c6 = st.columns(3)
                in_short_k = c4.number_input("Short strike", step=5.0, value=490.0)
                in_short_exp = c5.date_input("Short exp")
                in_short_credit = c6.number_input("Short credit $", step=25.0, value=700.0)
                in_contracts = st.number_input("Contracts", min_value=1, value=1, step=1)
                if st.form_submit_button("Add diagonal"):
                    if spot_pmcc is None:
                        st.warning("PMCC chain not loaded.")
                    else:
                        save_pmcc_positions(load_pmcc_positions() + [{
                            "ticker": "TSLA",
                            "leaps_strike": float(in_leaps_k),
                            "leaps_expiration": str(in_leaps_exp),
                            "leaps_debit": float(in_leaps_debit),
                            "short_strike": float(in_short_k),
                            "short_expiration": str(in_short_exp),
                            "short_credit": float(in_short_credit),
                            "spot_at_entry": spot_pmcc,
                            "contracts": int(in_contracts),
                        }])
                        st.rerun()

    # ── Block 3: NEXT SHORT TO SELL ───────────────────────────────────────
    st.subheader("NEXT SHORT TO SELL")

    if spot_pmcc is None:
        st.warning("Chain unavailable — cannot quote candidates.")
    else:
        next_short = select_next_short(
            spot=spot_pmcc,
            chain=plan_chain,
            records=pmcc_records,
            statuses=pmcc_statuses,
            staged=staged,
            preset=pmcc_preset,
        )
        st.success(f"**{next_short['hero']}**")
        st.caption(f"Source: {next_short.get('source', '—')}")
        cand_df = pd.DataFrame(next_short.get("candidates") or [])
        if not cand_df.empty:
            show_cols = [c for c in ["pick", "strike", "exp", "bid", "$/day", "delta", "upside %", "income", "risk"] if c in cand_df.columns]
            st.dataframe(cand_df[show_cols], hide_index=True, width="stretch")
        if staged:
            with st.expander("Rip management levels & staged packages"):
                st.dataframe(pd.DataFrame(staged.get("management") or []), hide_index=True, width="stretch")
                pkg_rows = []
                for key in ("initial", "higher", "add_on", "wider_add_on"):
                    p = (staged.get("packages") or {}).get(key)
                    if p:
                        pkg_rows.append({
                            "stage": p["label"],
                            "legs": p["legs"],
                            "bid credit": f"${p['bid_credit']:,.0f}",
                            "bid $/day": f"${p['bid_per_day']:.2f}",
                            "status": p.get("status", "—"),
                        })
                if pkg_rows:
                    st.dataframe(pd.DataFrame(pkg_rows), hide_index=True, width="stretch")
                events = staged.get("events") or {}
                if events.get("headline_risk"):
                    st.caption(events["headline_risk"])

    # ── Footer: wheel strategy (separate) ───────────────────────────────────
    with st.expander("Wheel / short puts (separate)"):
        st.caption("Standalone short-premium strategy — not PMCC diagonals.")
        records = load_positions()
        all_statuses: list[dict] = []

        if not records:
            st.caption(f"No positions in `{POSITIONS_PATH.name}`.")
        else:
            rows_for_table = []
            for r in records:
                try:
                    s = check_position(r)
                    all_statuses.append(s)
                    pos = s["position"]
                    action = _DECISION_ACTION.get(s["exit_decision"], "HOLD")
                    rows_for_table.append({
                        "ticker": s["ticker"],
                        "side": pos.side,
                        "strike": f"${pos.strike:.2f}",
                        "exp": pos.expiration.date(),
                        "dte": s["dte_remaining"],
                        "pnl/sh": f"${s['pnl_per_share']:+.2f}",
                        "action": "🚨 " + action if s["exit_decision"] else "✅ HOLD",
                    })
                except Exception as e:
                    rows_for_table.append({
                        "ticker": r.get("ticker", "?"),
                        "side": r.get("side", "?"),
                        "strike": r.get("strike", "?"),
                        "exp": r.get("expiration", "?"),
                        "dte": "—", "pnl/sh": "—",
                        "action": f"❌ {e}",
                    })
            st.dataframe(pd.DataFrame(rows_for_table), hide_index=True, width="stretch")

            for i, s in enumerate(all_statuses):
                if not s["exit_decision"]:
                    continue
                pos = s["position"]
                with st.expander(
                    f"🚨 {s['ticker']} {pos.side} ${pos.strike:.2f} — "
                    f"{_DECISION_ACTION.get(s['exit_decision'], '')}",
                ):
                    mark = s["mark"]
                    pnl_share = s["pnl_per_share"]
                    st.metric("P/L", f"${pnl_share:+.2f}/sh", f"{s['pnl_pct_credit']:+.1f}% credit")
                    st.metric("Δ", f"{mark['delta']:+.3f}")
                    if st.button("Remove", key=f"close_{i}"):
                        fresh = [
                            r for r in load_positions()
                            if not (
                                r["ticker"].upper() == s["ticker"].upper()
                                and float(r["strike"]) == pos.strike
                                and str(r["expiration"]) == str(pos.expiration.date())
                            )
                        ]
                        save_positions(fresh)
                        st.rerun()

        with st.expander("Add short premium position", expanded=False):
            with st.form("add_position", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                in_ticker = c1.selectbox("Ticker", ["TSLA", "TSLL"])
                in_side = c2.selectbox("Side", ["put", "call"])
                in_strike = c3.number_input("Strike", step=2.5, format="%.2f")
                c4, c5, c6 = st.columns(3)
                in_entry = c4.date_input("Entry date")
                in_expiration = c5.date_input("Expiration")
                in_credit = c6.number_input("Credit $/sh", step=0.01, format="%.2f")
                if st.form_submit_button("Add"):
                    save_positions(load_positions() + [{
                        "ticker": in_ticker, "side": in_side,
                        "strike": float(in_strike),
                        "entry_date": str(in_entry),
                        "expiration": str(in_expiration),
                        "credit": float(in_credit),
                    }])
                    st.rerun()

        st.markdown("**New short-premium signals**")
        col_tsla, col_tsll = st.columns(2, gap="large")
        for ticker, col in [("TSLA", col_tsla), ("TSLL", col_tsll)]:
            with col:
                rec = make_recommendation(ticker)
                st.markdown(f"**{ticker}** ${rec['spot']:.2f} · {rec['date'].date()}")
                if rec["action"] == "STAND_ASIDE":
                    st.warning(rec["reason"])
                else:
                    side = "PUT" if "PUT" in rec["action"] else "CALL"
                    st.success(
                        f"SELL {side} ${rec['strike']:.2f} · "
                        f"{rec['expiration'].date()} ({rec['dte']}d) · "
                        f"~${rec['estimated_credit']*100:,.0f}/ct"
                    )
                    with st.expander("Exit targets"):
                        e = rec["exit_targets"]
                        st.dataframe(pd.DataFrame([
                            {"rung": "profit", "level": f"≤ ${e['profit_target_buyback']:.2f}"},
                            {"rung": "max loss", "level": f"≥ ${e['max_loss_buyback']:.2f}"},
                            {"rung": "delta", "level": f"|Δ| > {e['delta_breach']}"},
                        ]), hide_index=True, width="stretch")


# ═══════════════════════════════════════════════════════════════════════════
# RESEARCH — pair selection + strategy validation
# ═══════════════════════════════════════════════════════════════════════════
with tab_research:
    st.header("PMCC pair research")

    c_preset, c_refresh = st.columns([1, 2])
    pmcc_preset = c_preset.selectbox(
        "Preset", ["managed", "balanced", "bullish", "income"], key="research_pmcc_preset",
    )
    pmcc_refresh = c_refresh.checkbox("Refresh chain", value=False, key="research_pmcc_refresh")
    scan_refresh = c_refresh.checkbox(
        "Rescan pairs (~5 min)", value=False, key="research_scan_refresh",
    )

    try:
        spot_pmcc, grid_pmcc, chain_src = load_pmcc_grid(pmcc_preset, pmcc_refresh)
    except Exception as ex:
        st.error(f"Chain load failed: {ex}")
        st.stop()

    from pmcc.chain_data import chain_fetch_meta

    _pmcc_market_banner(chain_fetch_meta())
    st.caption(chain_src)

    # ── Width × DTE explorer ──────────────────────────────────────────────
    st.subheader("Width × DTE explorer")
    with st.spinner("Loading full grid…"):
        full_scan, full_label = load_pmcc_full_scan(pmcc_preset)
    st.caption(full_label)

    if full_scan.empty:
        st.info("Run `just pmcc-scan --mode full --refresh` to populate.")
    else:
        from pmcc.explore import (
            METRIC_COLS,
            best_per_width,
            compare_pairs_on_paths,
            dte_matrix_at_width,
            enrich_scan_axes,
            top_cells_at_width,
        )

        metric_labels = {
            "path_sim": "Path sim (rank)",
            "return": "Scenario return %",
            "roll_burden": "Roll burden %",
            "bear": "Bear worst %",
        }
        c_met, c_tol = st.columns([2, 1])
        explore_metric = c_met.selectbox(
            "Rank by",
            list(metric_labels.keys()),
            format_func=lambda k: metric_labels[k],
            key="pmcc_explore_metric",
        )
        width_tol = c_tol.slider("Width ±$", 2, 15, 5, key="pmcc_width_tol")

        axes = enrich_scan_axes(full_scan, spot_pmcc)
        width_opts = sorted({
            int(w) for w in axes["spread_width"].round().astype(int).unique() if int(w) >= 10
        })
        if width_opts:
            default_w = 110 if 110 in width_opts else width_opts[len(width_opts) // 2]
            if (
                "pmcc_explore_width" in st.session_state
                and st.session_state.pmcc_explore_width not in width_opts
            ):
                st.session_state.pmcc_explore_width = default_w
            explore_width = st.select_slider(
                "Spread width ($)", options=width_opts, value=default_w, key="pmcc_explore_width",
            )

            bpw = best_per_width(full_scan, spot_pmcc, metric=explore_metric)
            if not bpw.empty:
                col_name = METRIC_COLS[explore_metric]
                st.line_chart(bpw.set_index("width_bucket")[[col_name]], height=180)

            mat = dte_matrix_at_width(
                full_scan, spot_pmcc, explore_width,
                metric=explore_metric, tolerance=float(width_tol),
            )
            if not mat.empty:
                pivot = mat.pivot(index="leaps_dte", columns="short_dte", values="metric")
                st.dataframe(
                    _display_df(pivot.sort_index(ascending=False).map(
                        lambda x: f"{x:,.0f}" if x == x else "—"
                    )),
                    hide_index=True, width="stretch",
                )

            top_cells = top_cells_at_width(
                full_scan, spot_pmcc, explore_width,
                metric=explore_metric, tolerance=float(width_tol), top_n=8,
            )
            if not top_cells.empty:
                show = top_cells[[
                    c for c in [
                        "pair", "leaps_dte", "short_dte", "path_sim_score",
                        "path_return_score", "roll_tax_burden", "bear_worst", "net_debit",
                    ] if c in top_cells.columns
                ]].copy()
                st.dataframe(show, hide_index=True, width="stretch")

                if "pair_dte" not in top_cells.columns:
                    top_cells = top_cells.copy()
                    top_cells["pair_dte"] = (
                        top_cells["pair"] + "@"
                        + top_cells["leaps_dte"].astype(int).astype(str)
                        + "/" + top_cells["short_dte"].astype(int).astype(str)
                    )
                compare_opts = top_cells["pair_dte"].tolist()
                _sanitize_multiselect("pmcc_path_compare", compare_opts)
                compare_pick = st.multiselect(
                    "Compare path P/L", compare_opts, key="pmcc_path_compare",
                )
                if compare_pick and st.button("Run compare", key="pmcc_path_compare_btn"):
                    cmp_paths = compare_pairs_on_paths(full_scan, compare_pick)
                    if not cmp_paths.empty:
                        st.dataframe(cmp_paths, hide_index=True, width="stretch")

    st.markdown("---")
    st.subheader("Top pairs (scenario scan)")
    with st.spinner("Loading pair scan…"):
        scan_df, scan_label = load_pmcc_pair_scan(pmcc_preset, scan_refresh)
    st.caption(scan_label)

    if scan_df.empty:
        st.info("Run `just pmcc-scan --refresh`.")
    else:
        top_cols = [
            c for c in [
                "rank", "pair", "net_debit", "path_sim_score", "path_return_score",
                "roll_tax_burden", "bear_worst", "path_moonshot", "path_gap_whipsaw_double",
            ] if c in scan_df.columns
        ]
        st.dataframe(scan_df[top_cols].head(8), hide_index=True, width="stretch")

        with st.expander("Scenario heatmap (top 8)"):
            from pmcc.pair_scan import scenario_matrix
            mat = scenario_matrix(scan_df, 8)
            path_cols = [c for c in mat.columns if c != "sim_score"]
            st.dataframe(
                _display_df(mat[path_cols].map(lambda x: f"{x:+.1f}%" if x == x else "—")),
                hide_index=True, width="stretch",
            )

    st.markdown("---")
    with st.expander("Pair drill-down — playbook & daily sim"):
        pair_options = [f"{r['pair']} (#{int(r['rank'])})" for _, r in scan_df.head(8).iterrows()] if not scan_df.empty else []
        pair_options += [
            f"{int(r.leaps_strike)}/{int(r.short_strike)}"
            for _, r in grid_pmcc.head(12).iterrows()
        ]
        pair_pick = st.selectbox("Pair", pair_options or ["—"], key="research_pmcc_pair")
        if pair_pick and pair_pick != "—":
            leaps_k, short_k = [float(x) for x in pair_pick.split()[0].split("/")]
            m = grid_pmcc[(grid_pmcc.leaps_strike == leaps_k) & (grid_pmcc.short_strike == short_k)]
            if m.empty:
                st.warning("Pair not in today's grid.")
            else:
                from pmcc.config import PmccConfig, apply_preset
                from pmcc.playbook import evaluate_live_status, generate_triggers
                from pmcc.playthrough import POLICY_BY_PRESET, PlayPolicy
                from pmcc.scenarios import PmccPair
                from pmcc.tune import load_tuned_policy

                pair = PmccPair.from_row(m.iloc[0], spot_pmcc)
                cfg = apply_preset(PmccConfig(ticker="TSLA"), pmcc_preset)
                base = POLICY_BY_PRESET.get(pmcc_preset, PlayPolicy())
                policy = load_tuned_policy(pmcc_preset, pair.leaps_strike, pair.short_strike, base)

                st.caption(
                    f"LEAPS ${pair.leaps_strike:.0f} ({pair.leaps_dte}d) · "
                    f"Short ${pair.short_strike:.0f} ({pair.short_dte}d) · "
                    f"Debit ${pair.net_debit:,.0f}"
                )
                for item in evaluate_live_status(pair, policy, spot_pmcc, r=cfg.risk_free_rate):
                    fn = {"alert": st.error, "warn": st.warning, "info": st.info}.get(item["level"], st.success)
                    fn(f"**{item['rule']}** — {item['detail']}")

                with st.spinner("Daily sim…"):
                    daily_sum = run_pmcc_daily_summary(
                        pmcc_preset, leaps_k, short_k, spot_pmcc, pmcc_refresh,
                    )
                if not daily_sum.empty:
                    st.dataframe(daily_sum, hide_index=True, width="stretch")

                with st.expander("Full playbook"):
                    triggers = generate_triggers(pair, policy, r=cfg.risk_free_rate)
                    st.dataframe(
                        pd.DataFrame([{"if": t.condition, "then": t.action} for t in triggers]),
                        hide_index=True, width="stretch",
                    )

    st.markdown("---")
    st.header("Short-premium strategy validation")

    with st.expander("Backtest performance (5y)"):
        for ticker in ("TSLA", "TSLL"):
            st.subheader(ticker)
            trades_df, metrics = run_full_backtest(ticker)
            if metrics.get("n_trades", 0) == 0:
                st.info("No trades.")
                continue
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Trades", metrics["n_trades"])
            c2.metric("Win rate", f"{metrics['win_rate_pct']:.1f}%")
            c3.metric("Total P/L", f"${metrics['total_pnl_per_contract']:,.0f}")
            c4.metric("Max DD", f"${metrics['max_dd_per_contract']:,.0f}")
            if "cumulative_pnl" in trades_df.columns:
                st.line_chart(
                    trades_df[["exit_date", "cumulative_pnl"]].set_index("exit_date"), height=200,
                )

    with st.expander("Regime stress-test suite"):
        st.caption("Run `just scenarios` before/after every strategy change.")
        for ticker in ("TSLA", "TSLL"):
            st.subheader(ticker)
            df = run_scenarios(ticker)
            available = df[df["available"]].copy()
            if available.empty:
                st.info("No canonical windows.")
                continue
            for col in ("underlying_ret_pct", "win_rate_pct", "total_pnl", "max_dd"):
                available[col] = available[col].round(1)
            st.dataframe(available.drop(columns=["available"]), hide_index=True, width="stretch")
            profitable = (available["total_pnl"] > 0).sum()
            st.caption(f"Profitable regimes: {profitable}/{len(available)}")