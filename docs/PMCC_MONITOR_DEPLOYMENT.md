# PMCC Always-On Monitor Deployment

This guide moves the TSLA PMCC monitor to a 24/7 machine and routes actionable alerts to Telegram via Hermes Agent.

The repo tracks code, docs, examples, and bootstrap scripts. It does **not** track live positions or secrets:

- `pmcc_positions.yaml` is gitignored because it contains your real open trade.
- `.cache/` is gitignored because it contains market data snapshots.
- Hermes config/secrets under `~/.hermes/` are not committed. Export/copy them privately or re-run setup on the new host.

## 1. Clone and bootstrap the repo

On the always-on machine:

```bash
git clone git@github.com:kenyip/tsla-tsll-options-tracker.git
cd tsla-tsll-options-tracker
scripts/bootstrap_pmcc_monitor.sh
```

If the machine does not have SSH GitHub auth yet, use HTTPS temporarily or add an SSH key to GitHub first.

The bootstrap script runs `just setup`, creates `pmcc_positions.yaml` from the example if missing, and writes:

```text
~/.hermes/scripts/pmcc_monitor.sh
```

That script is what Hermes cron should run. It is silent unless action is needed.

## 2. Copy the real live position privately

From this machine, copy the real file to the 24/7 box. Example:

```bash
scp /Users/jarvis/dev/tsla-tsll-options-tracker/pmcc_positions.yaml USER@HOST:~/dev/tsla-tsll-options-tracker/pmcc_positions.yaml
```

Or manually edit on the new host:

```bash
cp pmcc_positions.example.yaml pmcc_positions.yaml
$EDITOR pmcc_positions.yaml
```

Current expected schema:

```yaml
pmcc_positions:
  - ticker: TSLA
    leaps_strike: 410
    leaps_expiration: 2028-06-16
    leaps_debit: 13000
    short_strike: 500
    short_expiration: 2026-08-21
    short_credit: 725
    entry_date: 2026-06-22
    short_open_date: 2026-06-22
    short_open_dte: 60
    spot_at_entry: 405.05
    contracts: 1
    income_floor_daily: 10
    income_good_daily: 15
    income_strong_daily: 20
```

## 3. Verify PMCC commands

```bash
cd ~/dev/tsla-tsll-options-tracker
just pmcc-manage
just pmcc-manage --monitor
just pmcc-monitor
```

Expected behavior:

- `just pmcc-manage` prints the full dashboard.
- `just pmcc-manage --monitor` prints a concise status.
- `just pmcc-monitor` is quiet when no action is needed.

To test an alert path without changing positions:

```bash
just pmcc-manage --monitor --quiet-ok --spot 506
```

That should emit a challenged-short alert for the current 410/500 structure.

## 4. Install and configure Hermes + the Trader profile on the 24/7 box

Install Hermes if needed:

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
hermes setup
hermes model
hermes doctor
```

Use your preferred provider/model. Do not commit API keys. Hermes secrets live in:

```text
~/.hermes/.env
~/.hermes/config.yaml
```

Create or repair the dedicated trading profile from the repo root:

```bash
cd ~/dev/tsla-tsll-options-tracker
scripts/bootstrap_trader_profile.sh
trader config check
trader skills list | grep -E 'trading-partner|pmcc-strategy'
```

For a faithful private copy of the current local trading agent, use profile export/import instead of git:

```bash
hermes profile export trader -o ~/trader-profile.tar.gz
scp ~/trader-profile.tar.gz USER@HOST:~/
# on target:
hermes profile import ~/trader-profile.tar.gz
```

The profile archive may contain config, `.env`, memory, and private state. Keep it private. Avoid blindly committing or publishing `~/.hermes/.env`, `auth.json`, OAuth files, provider keys, broker credentials, Telegram tokens, or config files containing secrets.

## 5. Configure Telegram gateway

On the 24/7 machine, use the dedicated trading profile:

```bash
trader gateway setup telegram
trader gateway install
trader gateway start
trader gateway status
```

During Telegram setup you will need a Telegram bot token from BotFather. Store it in Hermes config/env when prompted, not in this repo.

After the bot is reachable from your Telegram chat, set/approve the chat as a delivery target from Telegram using Hermes gateway commands such as:

```text
/sethome
/status
/platforms
```

If gateway setup differs on the installed Hermes version, stay inside the `trader` profile and use:

```bash
trader gateway setup
trader gateway status
```

## 6. Schedule the monitor on the 24/7 Trader profile

Create the scheduler job from a `trader` Hermes session on the 24/7 box, or with the profile CLI if available. The desired job is:

```text
Name: TSLA PMCC action monitor
Schedule: */30 7-13 * * 1-5
Script: pmcc_monitor.sh
Mode: script-only/no-agent
Delivery: Telegram/home/origin
Workdir: ~/dev/tsla-tsll-options-tracker
```

The existing job on this laptop is local to this Hermes install and does not automatically move with the repo. Re-create it on the always-on host.

Profile CLI shape:

```bash
trader cron create '*/30 7-13 * * 1-5' \
  --name 'TSLA PMCC action monitor' \
  --script pmcc_monitor.sh \
  --no-agent \
  --workdir ~/dev/tsla-tsll-options-tracker
```

If using the Hermes in-chat cron tool, create it as a script-only watchdog:

```text
Schedule: */30 7-13 * * 1-5
Script: pmcc_monitor.sh
no_agent: true
workdir: /home/USER/dev/tsla-tsll-options-tracker
```

It should be silent unless `pmcc_manage.py --monitor --quiet-ok` prints an actionable alert.

## 7. Operating checklist

Daily/manual:

```bash
just pmcc-manage
```

When you close or roll a short, edit `pmcc_positions.yaml`:

- update `short_strike`
- update `short_expiration`
- update `short_credit`
- update `short_open_date`
- update `short_open_dte`
- keep the LEAPS fields unchanged unless you actually roll/reset the LEAPS

When strict chain scans are needed, run during market hours:

```bash
just pmcc-scan --preset managed --refresh
```

After-hours, strict scans may fail because yfinance often returns zero bid/ask and broken greeks. Use the approximate model-cleaned scan only for strategic ranking:

```bash
.venv/bin/python pmcc_afterhours_model_scan.py
```

## 8. Current action model

The monitor alerts on:

- harvest: short mark <= 50% of credit
- challenged short: spot near/through short strike
- force close: short ITM and <= 14 DTE
- LEAPS roll window: LEAPS <= 365 DTE, unless deep/extreme ITM rules apply
- extreme ITM: close short and keep LEAPS naked

It also tracks premium-clock economics:

- floor: $10/day mostly pays LEAPS carry
- good: $15/day creates real net income
- strong: $20/day is excellent, but do not chase with too-tight calls

Formula:

```text
wait budget after harvest = harvest_profit / target_daily - days_held
```
