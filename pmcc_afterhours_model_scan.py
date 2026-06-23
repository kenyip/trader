#!/usr/bin/env python3
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pricing

from pmcc.chain_data import _fetch_call_chain_live
from pmcc.scenarios import PmccPair
from pmcc.playthrough import POLICY_BY_PRESET
from pmcc.daily_playthrough import run_daily_path, daily_policy, pnl_return_pct
from pmcc_playbook_gen import build_paths

R = 0.04
OUT = Path('.cache/pmcc_afterhours_model_scan_TSLA_managed.parquet')


def bs_price(s, k, dte, iv):
    return pricing.price(s, k, dte / 365.0, iv, 'call', r=R)


def implied_vol_from_price(s, k, dte, px):
    if px <= max(s - k, 0):
        return None
    lo, hi = 0.05, 2.50
    try:
        plo = bs_price(s, k, dte, lo)
        phi = bs_price(s, k, dte, hi)
    except Exception:
        return None
    if px < plo or px > phi:
        return None
    for _ in range(80):
        mid = (lo + hi) / 2
        pm = bs_price(s, k, dte, mid)
        if pm < px:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def clean_rows(df, spot):
    rows = []
    for _, row in df.iterrows():
        dte = int(row['dte'])
        strike = float(row['strike'])
        mark = float(row['mid'] or 0)
        if mark <= 0:
            continue
        # yfinance often returns nonsensical IV/delta after-hours; derive IV from last/mid mark.
        iv = implied_vol_from_price(spot, strike, dte, mark)
        if iv is None:
            iv = float(row.get('iv') or 0)
            if not (0.15 <= iv <= 1.50):
                continue
        try:
            delta = pricing.delta(spot, strike, dte / 365.0, iv, 'call', r=R)
            theta = pricing.theta(spot, strike, dte / 365.0, iv, 'call', r=R) / 365.0
        except Exception:
            continue
        rows.append({
            'expiration': str(row['expiration']),
            'dte': dte,
            'strike': strike,
            'mark': mark,
            'iv': iv,
            'delta': delta,
            'theta_per_day': theta,
            'last': float(row.get('last') or 0),
            'volume': float(row.get('volume') or 0),
            'open_interest': float(row.get('open_interest') or 0),
        })
    return pd.DataFrame(rows)


def scenario_score(pair: PmccPair):
    paths = build_paths(pair.leaps_dte)
    keep = {
        'flat_chop', 'steady_bull', 'moonshot', 'steady_bear', 'crash_recover',
        'rip_pullback', 'gap_whipsaw_double', 'post_earnings_whipsaw',
    }
    paths = tuple(p for p in paths if p.name in keep)
    results = {}
    policy = daily_policy(POLICY_BY_PRESET['managed'])
    for path in paths:
        df = run_daily_path(pair, path, policy, r=R)
        if df.empty:
            results[path.name] = 0.0
            continue
        final = df.iloc[-1]
        results[path.name] = pnl_return_pct(float(final['net_pnl']), pair.net_debit)
    bull_names = ['steady_bull', 'moonshot']
    whip_names = ['gap_whipsaw_double', 'post_earnings_whipsaw', 'rip_pullback']
    flat_names = ['flat_chop']
    bear_names = ['steady_bear', 'crash_recover']
    def avg(names):
        vals = [results[n] for n in names if n in results]
        return sum(vals) / len(vals) if vals else 0.0
    bull = avg(bull_names)
    whip = avg(whip_names)
    flat = avg(flat_names)
    bear = avg(bear_names)
    score = (bull * 2.0 + whip * 1.5 + flat * 1.0 + bear * 0.5) / 5.0
    return score, bull, whip, flat, bear, results


def main():
    spot, raw = _fetch_call_chain_live('TSLA', r=R, min_dte=1)
    clean = clean_rows(raw, spot)
    leaps_dtes = [d for d in sorted(clean['dte'].unique()) if d in (725, 907)]
    short_dtes = [d for d in sorted(clean['dte'].unique()) if d in (60, 88)]
    rows = []
    for ldte in leaps_dtes:
        leaps_sub = clean[(clean['dte'] == ldte) & (clean['strike'].between(390, 430))]
        leaps_sub = leaps_sub[(leaps_sub['delta'] >= 0.58) & (leaps_sub['delta'] <= 0.78)]
        for _, l in leaps_sub.iterrows():
            for sdte in short_dtes:
                short_sub = clean[(clean['dte'] == sdte) & (clean['strike'].between(480, 530))]
                short_sub = short_sub[(short_sub['mark'] >= 1.0) & (short_sub['delta'] >= 0.05) & (short_sub['delta'] <= 0.45)]
                for _, s in short_sub.iterrows():
                    if float(s['strike']) <= float(l['strike']):
                        continue
                    pair = PmccPair(
                        spot_entry=float(spot),
                        leaps_strike=float(l['strike']), leaps_exp=str(l['expiration']), leaps_dte=int(ldte),
                        leaps_iv=float(l['iv']), leaps_debit=float(l['mark']) * 100,
                        short_strike=float(s['strike']), short_exp=str(s['expiration']), short_dte=int(sdte),
                        short_iv=float(s['iv']), short_credit=float(s['mark']) * 100,
                        leaps_delta_target=float(l['delta']), short_delta_target=float(s['delta']),
                    )
                    if pair.net_debit <= 0:
                        continue
                    score, bull, whip, flat, bear, results = scenario_score(pair)
                    rows.append({
                        'pair': f"{int(pair.leaps_strike)}/{int(pair.short_strike)}",
                        'leaps_strike': pair.leaps_strike,
                        'short_strike': pair.short_strike,
                        'leaps_exp': pair.leaps_exp,
                        'short_exp': pair.short_exp,
                        'leaps_dte': pair.leaps_dte,
                        'short_dte': pair.short_dte,
                        'leaps_delta': pair.leaps_delta_target,
                        'short_delta': pair.short_delta_target,
                        'leaps_debit': pair.leaps_debit,
                        'short_credit': pair.short_credit,
                        'net_debit': pair.net_debit,
                        'coverage_pct': pair.short_credit / pair.leaps_debit * 100,
                        'score': score,
                        'bull_avg': bull,
                        'whipsaw_avg': whip,
                        'flat_chop': flat,
                        'bear_avg': bear,
                        **{f'path_{k}': v for k, v in results.items()},
                    })
    out = pd.DataFrame(rows)
    if out.empty:
        raise SystemExit('no rows after model cleaning')
    out = out.sort_values(['score', 'leaps_dte'], ascending=[False, False]).reset_index(drop=True)
    OUT.parent.mkdir(exist_ok=True)
    out.to_parquet(OUT, index=False)
    print(f'spot=${spot:.2f}')
    print(f'raw_rows={len(raw)} clean_rows={len(clean)} rows_scored={len(out)}')
    print(f'leaps_dtes={leaps_dtes}')
    print(f'short_dtes={short_dtes}')
    print(f'wrote={OUT}')
    cols = ['pair','leaps_dte','short_dte','leaps_debit','short_credit','coverage_pct','score','flat_chop','bear_avg','bull_avg','whipsaw_avg']
    print(out.head(15)[cols].to_string(index=False, formatters={
        'leaps_debit': lambda x: f'${x:,.0f}',
        'short_credit': lambda x: f'${x:,.0f}',
        'coverage_pct': lambda x: f'{x:.1f}%',
        'score': lambda x: f'{x:.1f}',
        'flat_chop': lambda x: f'{x:+.0f}%',
        'bear_avg': lambda x: f'{x:+.0f}%',
        'bull_avg': lambda x: f'{x:+.0f}%',
        'whipsaw_avg': lambda x: f'{x:+.0f}%',
    }))


if __name__ == '__main__':
    main()
