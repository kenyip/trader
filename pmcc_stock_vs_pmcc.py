#!/usr/bin/env python3
from __future__ import annotations

import pricing
from pmcc.chain_data import fetch_call_chain
from pmcc.positions import load_pmcc_positions, _calendar_dte
from pmcc.playthrough import POLICY_BY_PRESET
from pmcc.daily_playthrough import daily_policy
from pmcc.playbook import _roll_target


def bs_call(spot, strike, dte, iv, r=0.04):
    if dte <= 0:
        return max(spot - strike, 0.0)
    return pricing.price(spot, strike, dte / 365.0, iv, "call", r=r)


def bs_delta(spot, strike, dte, iv, r=0.04):
    if dte <= 0:
        return 1.0 if spot > strike else 0.0
    return pricing.delta(spot, strike, dte / 365.0, iv, "call", r=r)


def main():
    spot_now, chain = fetch_call_chain('TSLA', refresh=False)
    rec = load_pmcc_positions()[0]
    leaps_k = float(rec['leaps_strike'])
    short_k = float(rec['short_strike'])
    leaps_dte = _calendar_dte(rec['leaps_expiration'])
    short_dte = _calendar_dte(rec['short_expiration'])
    leaps_debit = float(rec['leaps_debit'])
    short_credit = float(rec['short_credit'])
    entry_spot = float(rec['spot_at_entry'])
    contracts = 3
    shares = 300

    def chain_row(exp, strike):
        sub = chain[(chain.expiration.astype(str) == str(exp)[:10]) & (chain.strike.astype(float) == float(strike))]
        return sub.iloc[0] if not sub.empty else None

    lr = chain_row(rec['leaps_expiration'], leaps_k)
    sr = chain_row(rec['short_expiration'], short_k)
    leaps_iv = float(lr.iv) if lr is not None else float(rec.get('leaps_iv', 0.55))
    short_iv = float(sr.iv) if sr is not None else float(rec.get('short_iv', 0.45))
    leaps_mid_now = float(lr.mid) * 100 if lr is not None else bs_call(spot_now, leaps_k, leaps_dte, leaps_iv) * 100
    short_mid_now = float(sr.mid) * 100 if sr is not None else bs_call(spot_now, short_k, short_dte, short_iv) * 100

    stock_capital = shares * entry_spot
    pmcc_net_debit_per = leaps_debit - short_credit
    pmcc_capital = contracts * pmcc_net_debit_per
    current_pmcc_pnl_per = (leaps_mid_now - leaps_debit) + (short_credit - short_mid_now)
    current_stock_pnl = shares * (spot_now - entry_spot)

    policy = daily_policy(POLICY_BY_PRESET['managed'])

    print(f"spot_now {spot_now:.2f}")
    print(f"entry_spot {entry_spot:.2f}")
    print(f"leaps_iv {leaps_iv:.4f} short_iv {short_iv:.4f}")
    print(f"leaps_dte {leaps_dte} short_dte {short_dte}")
    print(f"current_chain_marks per PMCC: LEAPS ${leaps_mid_now:,.0f}, short ${short_mid_now:,.0f}, pnl ${current_pmcc_pnl_per:+,.0f}")
    print(f"capital: 300 shares ${stock_capital:,.0f}; 3 PMCC net debit ${pmcc_capital:,.0f}")
    print(f"current_pnl: 300 shares ${current_stock_pnl:+,.0f}; 3 PMCC ${contracts*current_pmcc_pnl_per:+,.0f}")
    print()

    hdr = (
        "target  stock_pnl stock_ret  pmcc_pnl  pmcc_ret  pmcc_vs_stock  "
        "pmcc_delta_after_close  action"
    )
    print(hdr)
    print('-' * len(hdr))
    for target in [450, 500, 525, 550, 575, 600]:
        stock_pnl = shares * (target - entry_spot)
        stock_ret = stock_pnl / stock_capital * 100
        leaps_mark = bs_call(target, leaps_k, leaps_dte, leaps_iv) * 100
        short_buyback = bs_call(target, short_k, short_dte, short_iv) * 100
        pmcc_pnl_per = (leaps_mark - leaps_debit) + (short_credit - short_buyback)
        pmcc_pnl = contracts * pmcc_pnl_per
        pmcc_ret = pmcc_pnl / pmcc_capital * 100
        leaps_delta = bs_delta(target, leaps_k, leaps_dte, leaps_iv)
        short_delta = bs_delta(target, short_k, short_dte, short_iv)
        net_delta_still_short = contracts * 100 * (leaps_delta - short_delta)
        delta_after_close = contracts * 100 * leaps_delta
        if target >= leaps_k * policy.leaps_extreme_itm_threshold:
            action = "CLOSE short; keep 3 LEAPS naked"
        elif target >= short_k:
            roll_k = _roll_target(target, short_k, leaps_k, policy)
            # rescue roll credit estimate at default 60d and current short IV
            new_credit = bs_call(target, roll_k, policy.short_dte_new, short_iv) * 100
            action = f"ROLL/close old short; if rolling, target ~${roll_k:.0f} credit~${new_credit:,.0f}/ct"
        else:
            action = "HOLD; short not challenged"
        print(
            f"${target:<6.0f} ${stock_pnl:>9,.0f} {stock_ret:>7.1f}% "
            f"${pmcc_pnl:>9,.0f} {pmcc_ret:>7.1f}% ${pmcc_pnl-stock_pnl:>11,.0f} "
            f"{delta_after_close:>8.0f}sh  {action}"
        )

    print()
    same_cap_contracts = int(stock_capital // pmcc_net_debit_per)
    same_cap_used = same_cap_contracts * pmcc_net_debit_per
    print(f"Same-capital lens: 300 shares uses ${stock_capital:,.0f}; that could fund about {same_cap_contracts} PMCCs using ${same_cap_used:,.0f}.")
    print("This is NOT my recommended sizing; it shows why PMCC is a leverage/capital-efficiency trade.")
    print("target  300sh_pnl  same_cap_pmcc_pnl  same_cap_pmcc_ret")
    print("-------------------------------------------------------")
    for target in [450, 500, 525, 550, 575, 600]:
        stock_pnl = shares * (target - entry_spot)
        leaps_mark = bs_call(target, leaps_k, leaps_dte, leaps_iv) * 100
        short_buyback = bs_call(target, short_k, short_dte, short_iv) * 100
        pmcc_pnl_per = (leaps_mark - leaps_debit) + (short_credit - short_buyback)
        same_pnl = same_cap_contracts * pmcc_pnl_per
        same_ret = same_pnl / same_cap_used * 100
        print(f"${target:<6.0f} ${stock_pnl:>9,.0f} ${same_pnl:>17,.0f} {same_ret:>10.1f}%")

    print()
    print("Note: PMCC P/L is immediate mark-to-market after buying back/marking the existing $500 short.")
    print("Selling a replacement short does not change immediate equity much; it changes future carry/risk.")
    print("If you do NOT close/roll the short above $500, net delta is capped lower:")
    for target in [500, 550, 600]:
        ld = bs_delta(target, leaps_k, leaps_dte, leaps_iv)
        sd = bs_delta(target, short_k, short_dte, short_iv)
        print(f"  target ${target}: still-short net delta ≈ {contracts*100*(ld-sd):.0f} shares; after close ≈ {contracts*100*ld:.0f} shares")


if __name__ == '__main__':
    main()
