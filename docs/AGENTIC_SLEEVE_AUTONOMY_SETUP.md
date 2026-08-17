# Agentic sleeve — autonomy + Robinhood MCP readiness

**Pinned:** 2026-07-20 (live MCP probe in trader Hermes session)  
**Authority:** research + paper only until Ken arms. No self-arm. No main-account trading.

This is the operator contract so Trader can **decide next steps autonomously**: find strategies, wait for setups, manage paper/shadow, and only after arm day manage **Agentic** live 1-lot risk.

---

### RH MCP probe (2026-07-20 ~01:43 PT) — superseded by re-probe below

### RH MCP re-probe (2026-07-20 after Ken L2 + $500)

| Account | Nick | agentic_allowed | Type | Options | Capital |
|---|---|---|---|---|---|
| ••••8507 | **Agentic** | **true** | **cash** (not margin) | **option_level_2** | **$500** cash / BP; pending_deposits $500 |
| ••••5223 | Individual (default) | **false** | margin | option_level_3 | main book — **do not trade via agent** |

Isolation: **PASS**. Options level: **PASS (L2)**. Funded test tier: **PASS ($500)**. Margin conversion: **not required** for T0.5 / first MCP-native live (CSP + long options).

### What works on MCP today (read path — verified)

| Capability | Status |
|---|---|
| `get_accounts` | OK — L2 on Agentic |
| Agentic portfolio / BP | OK — $500 |
| Equity quotes | OK |
| Option chains | OK |
| Equity/option positions list | OK (empty) |

### Critical gaps for “prime time”

| Gap | Impact | Owner |
|---|---|---|
| Agentic still **cash** not margin | Expected RH behavior for many new/agentic sleeves; GFV/settlement rules apply; spreads still blocked by MCP single-leg + L2 scope | Accept for v1; optional margin later in app if RH allows |
| Only **$500** test capital | Not $3k income sleeve; size for plumbing / tiny probes only | Ken transfers $3k at LIVE_PACKET |
| MCP **options place = single-leg only** | No native multi-leg PCS/IC via MCP | Strategy design |
| Platform `RobinhoodMcpBroker.place_*` | **Wired 2026-08-17** to `review_option_order` then `place_option_order` (1-lot limit, Agentic last4 8507 only) when `mcp_call` is injected. Still **fail-closed** (`LiveOrdersBlocked`) without it. `replace_limit` stays blocked. `agentic.enabled` remains **false**. No live place in this build. | Trader BUILD |
| `agentic.enabled: false` | Soft kill (correct) | Ken arm day only |
| Multi-session paper + shadow + kill drill + TOP_HYP | Not done | Trader continuum |

**Place wire (2026-08-17):** `RobinhoodMcpBroker.place_limit` / `cancel` can call RH MCP `review_option_order` → `place_option_order` / `cancel_option_order` when Hermes/cron injects `mcp_call`. Account resolution is Agentic last4 `8507` + `agentic_allowed=true` only. Soft kill stays off (`agentic.enabled: false`). This build does **not** place a live order.

### Cash vs margin (Ken note)

Cash Agentic is **compatible** with first-live plan:

- **Cash-secured puts** — native L2 + cash collateral (fits MCP single-leg)
- **Long calls/puts** — native L2 (defined debit risk)
- **Covered calls** — need long shares first
- **Credit spreads / IC** — need multi-leg MCP (missing) and usually margin/L3; stay **paper research** for now

Do **not** block progress waiting on margin. If RH later allows margin on this account in-app, nice-to-have; not a gate for CSP/single-leg arm.

### Options upgrade (Agentic only)

**Done 2026-07-20:** option_level_2 confirmed via MCP.

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

### Phase T0.5 — plumbing test (DONE 2026-07-20)

| Item | Value |
|---|---|
| Deposit | **$500** on Agentic |
| Options | **option_level_2** |
| Account type | **cash** (margin not required for v1) |
| Pending | `pending_deposits` may show until fully settled — prefer settled cash before any live probe |
| Live trading | **Still off** (`agentic.enabled=false`) |

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

- [x] Open options upgrade link for Agentic; get **L2+**  
- [x] Deposit **$300–$500** test cash to Agentic  
- [x] Leave main account non-agentic  
- [ ] Keep trader Hermes **gateway running**  
- [ ] Do **not** ask to arm live yet  
- [ ] Optional later: margin conversion in RH app if offered (not a v1 gate)  

### Trader (autonomous)

- [x] Continuum cron (no 5m densify thrash)  
- [x] RH MCP read path verified 2026-07-20  
- [ ] Strategy search biased toward **MCP-native live shapes** for first arm (CSP / single-leg) while multi-leg remains paper research  
- [ ] Quality TOP_HYP (multi-symbol / thick n / dual-cost)  
- [ ] Multi-session paper manage path  
- [ ] Shadow + kill drill  
- [x] Wire `place_limit` → MCP review+place (1-lot limit, Agentic last4 8507 only); still disarmed (`agentic.enabled=false`, no live place)
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
