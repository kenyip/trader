# Agentic sleeve — autonomy + Robinhood MCP readiness

**Pinned:** 2026-07-20 (live MCP probe in trader Hermes session)  
**Authority:** research + paper only until Ken arms. No self-arm. No main-account trading.

This is the operator contract so Trader can **decide next steps autonomously**: find strategies, wait for setups, manage paper/shadow, and only after arm day manage **Agentic** live 1-lot risk.

---

## RH MCP probe (2026-07-20 ~01:43 PT)

### Accounts (masked)

| Account | Nick | agentic_allowed | Type | Options | Capital |
|---|---|---|---|---|---|
| ••••8507 | **Agentic** | **true** | cash | **none (empty)** | **$0** |
| ••••5223 | Individual (default) | **false** | margin | option_level_3 | ~main book — **do not trade via agent** |

Isolation: **PASS** — main is non-agentic to this agent; Agentic is the only mutable target once armed.

### What works on MCP today (read path — verified)

| Capability | Status |
|---|---|
| `get_accounts` | OK |
| Agentic portfolio / BP | OK (zeros) |
| Equity quotes (SPY/IWM/AMZN) | OK (after-hours marks) |
| Option chains (IWM expiries) | OK |
| Equity/option positions list | OK (empty on Agentic) |
| Options upgrade URL | OK |

### Critical gaps for “prime time”

| Gap | Impact | Owner |
|---|---|---|
| Agentic **unfunded** | No live risk capacity | Ken deposit |
| Agentic **no options level** | Cannot open options even if funded | Ken: upgrade link below |
| MCP **options place = single-leg only** | No native multi-leg PCS/IC via MCP | Strategy design + future RH |
| Platform `RobinhoodMcpBroker.place_*` | Still **fail-closed NotImplemented** until dedicated wire+arm task | Trader BUILD after paper/shadow |
| `agentic.enabled: false` | Soft kill (correct) | Ken arm day only |
| Multi-session paper + shadow + kill drill | Not done for a quality TOP_HYP | Trader continuum |

### Options upgrade (Agentic only)

Complete in Robinhood app:

https://applink.robinhood.com/upgrade_options?account_number=987168507

**Target level:** at least **option_level_2** (long options, CSP, covered calls).  
Level 3 on the *account* does not unlock multi-leg **via MCP** — MCP place is still single-leg even on L3.

After approval, ask Trader to re-run `get_accounts` (do not trust cached option_level).

---

## MCP vs our income strategies

Preferred research DNA (PCS / CCS / IC) is **defined-risk multi-leg**.  
RH MCP `place_option_order` / `review_option_order`: **exactly one leg**.

| Structure | Research/paper | Live via MCP (when armed) |
|---|---|---|
| Put credit spread / call credit / IC | Full sim path | **Not native** — would require legging (extra risk) or app |
| Cash-secured put (CSP) | Supported | **Native single-leg** (needs cash + L2) |
| Long call/put / debit single-leg | Supported | **Native** |
| Covered call | Needs long stock | Equity + short call (two single-leg ops) |
| Equity shares | Supported | Native |

**Implication for autonomy success:**  
First live sleeve should prefer **MCP-native single-leg defined-ish risk** (CSP with cash collateral, small long options with hard stops) **or** accept that multi-leg stays paper until RH multi-leg MCP lands.  
Do **not** arm multi-leg PCS as “live autonomous” until place path can express both legs atomically or legging risk is explicitly accepted in the arm packet.

---

## Funding plan (Ken)

### Phase T0.5 — plumbing test (recommended first)

| Item | Value |
|---|---|
| Deposit | **$300–$500** to Agentic only |
| Purpose | Settled cash, options application, **no** expectation of income |
| Live trading | **Still off** (`agentic.enabled=false`) |
| Optional later | One **Ken-supervised** dry review of equity limit (not required) |

This proves deposits clear and options level attaches. It is **not** strategy readiness.

### Phase T1 — prime-time capital

| Item | Value |
|---|---|
| Deposit / transfer | **$3,000** to Agentic |
| When | After TOP_HYP quality + multi-session paper + shadow + kill drill + place_* wired |
| Risk yaml | Scale to $3k (already planning defaults in repo) |
| Size | **1 lot** only |

Do **not** transfer $3k early just to “have money sitting.” T0.5 is enough until edge exists. Transfer $3k when Trader drafts a LIVE_PACKET.

### Risk scales at each tier

| Capital | max_notional | max_contracts | max_open_risk | max_daily_loss |
|---|---|---|---|---|
| $0 now | paper defaults | 1 | 750 | 300 |
| $300–500 test | no live | 1 | n/a | n/a |
| $3,000 prime | 300 | 1 | 750 | 300 |

---

## Autonomy model (Trader decides; Ken arms once)

```text
ALWAYS (gateway up)
  autonomous-tick every 2h     → engine handoff → MoA if survivor else multi-symbol + dry paper
  BUILD named slots            → same continuum
  RTH paper-ops + rth-eval     → watch setups; paper by default

WHEN TOP_HYP quality leader exists
  intentional paper open/manage/close across sessions
  shadow propose→risk→log
  kill-switch drill
  wire place_* fail-open only under arm gates

WHEN Ken arms agentic_live (once)
  RTH loop may place/replace/cancel LIMITS on Agentic only
  RiskGovernor + kill file + daily loss + 1-lot
  no main account; no per-trade ping unless envelope breach / kill
```

### What Trader may decide alone (green)

- Symbol, structure, DNA, experiments (research/paper)
- When to stand aside
- Paper execute on quality leader when intentional paper path is enabled
- Shadow logging
- Code, skills, readiness, next seeds
- When to draft LIVE_PACKET

### What requires Ken (red)

- Deposit / transfer money  
- Options application  
- Set `agentic.enabled=true` + mode `agentic_live`  
- Broaden size past 1-lot / raise daily loss  
- Trade main account  
- Disable kill switch permanently  

---

## Success setup checklist

### Ken (this week)

- [ ] Open options upgrade link for Agentic; get **L2+**  
- [ ] Deposit **$300–$500** test cash to Agentic (optional but useful)  
- [ ] Leave main account non-agentic  
- [ ] Keep trader Hermes **gateway running**  
- [ ] Do **not** ask to arm live yet  

### Trader (autonomous)

- [x] Continuum cron (no 5m densify thrash)  
- [x] RH MCP read path verified 2026-07-20  
- [ ] Strategy search biased toward **MCP-native live shapes** for first arm (CSP / single-leg) while multi-leg remains paper research  
- [ ] Quality TOP_HYP (multi-symbol / thick n / dual-cost)  
- [ ] Multi-session paper manage path  
- [ ] Shadow + kill drill  
- [ ] Implement `place_limit` → MCP single-leg option/equity under arm guards  
- [ ] LIVE_PACKET when A+B green  

### Arm day (later)

- [ ] Re-probe: funded, L2+, BP, empty or known positions  
- [ ] `agentic.enabled=true` only after packet  
- [ ] Allowlist one hyp  
- [ ] Kill file procedure tested  
- [ ] First live = 1 lot, working limits  

---

## Explicit non-goals until packet

- No live orders from continuum  
- No paper→live promotion of thin densify AMZN/IWM seats  
- No multi-leg live via legging without written Ken acceptance  
- No use of main ••••5223 for agent orders  

---

## Related

- `docs/TRADER_CRON_LAYOUT.md` — wake cadence  
- `docs/AGENTIC_AUTONOMY_POLICY.md` — mode/arm policy  
- `docs/GO_LIVE_READINESS.md` — A/B/C scoreboard  
- `reports/readiness/LATEST.md` — current phase  
- `trader_platform/risk_limits.yaml` — soft kill + limits  
