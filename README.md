# Bot Trading Agent

Production monitoring system for Kalshi trading bots (BTC, ETH, SOL).

## What It Does

**Real-time Monitoring:**
- Checks bot processes every 30 seconds
- Parses logs for trades, wins, losses, and errors
- Detects crashed, frozen, or stuck bots
- Verifies Kalshi balance on demand

**Automated Recovery:**
- Auto-restarts crashed bots after market close
- Prevents crash loops (stops after 2nd crash in 5min)
- Restarts only affected bots, not all

**Instant Alerts (via Telegram):**
- Bot crashed
- Exception/error in logs
- Stop-loss failure (full bet lost)
- Bot frozen (alive but inactive 16+ min)
- Crash loop detected

**Daily Summaries (via Telegram):**
- Morning (8am) and evening (8pm)
- Per-bot totals: wins, losses, profit, trade count

## Architecture

```
monitor.py (main loop)
├── bot_tracker.py (PID/health tracking)
├── log_parser.py (event detection)
├── alerter.py (Telegram integration)
├── restarter.py (auto-restart logic)
├── metrics.py (daily summary tracking)
└── database.py (SQLite state persistence)
```

## Installation

```bash
cd ~/bot-trading-agent
pip install -r requirements.txt
```

## Configuration

Edit `config.py` or set environment variables:
- `TELEGRAM_BOT_TOKEN` - Bot token for alerts
- `TELEGRAM_CHAT_ID` - Chat ID for critical alerts (James)
- `TELEGRAM_TRIAGE_CHAT_ID` - Chat ID for triage alerts (Molly group)
- `BOT_DIR` - Path to kalshi-bot directory
- `CHECK_INTERVAL` - Seconds between checks (default: 30)

## Running

**Monitor (auto-restarts, alerts):**
```bash
cd ~/bot-trading-agent
nohup python3 monitor.py > monitor_output.log 2>&1 &
```

**Command Handler (Telegram /bal, /status, /health):**
```bash
cd ~/bot-trading-agent
nohup python3 bot_commands.py > bot_commands.log 2>&1 &
```

**Check if running:**
```bash
ps aux | grep -E "(monitor|bot_commands).py" | grep -v grep
```

## Safety Features

- **Read-only log parsing** - Never modifies bot files
- **Crash loop protection** - Stops auto-restart after 2 failures
- **Market-aware restarts** - Waits for market close before restarting
- **State persistence** - Tracks all actions in SQLite
- **Comprehensive logging** - Monitor has its own detailed logs

## Database Schema

**bot_health** - Current state of each bot
**restart_history** - All restart attempts with timestamps
**trade_events** - Parsed from logs (placed/won/lost)
**error_log** - All detected errors/exceptions
**daily_metrics** - Aggregated daily summaries

## Monitored Bots

- **BTC** - `/Users/moltbot/kalshi-bot/experiment_continuous.py`
- **ETH** - `/Users/moltbot/kalshi-bot/experiment_eth.py`
- **SOL** - `/Users/moltbot/kalshi-bot/experiment_sol.py`

## Telegram Commands

Send these commands in your Telegram chat with the bot:

- **`/bal`** or **`/balance`** - Today's profit/loss + bot health
- **`/status`** - Detailed status (PID, last activity, recent errors)
- **`/health`** - Quick health check (all systems operational?)

Example `/bal` output:
```
💰 Kalshi Bot Balance

🟢 BTC: +$12.50 (3W-1L, 4 trades)
🔴 ETH: -$5.00 (1W-2L, 3 trades)
⚪️ SOL: No trades today

Total Today: +$7.50

📊 Bot Health:
✅ BTC: healthy
✅ ETH: healthy
✅ SOL: healthy
```

## Alert Routing

**Two-tier alert system:**

### 🚨 Critical → James Directly
- **Bot Crashed** - PID missing, auto-restart after market close
- **Stop-loss Failed** - Full bet lost (critical bug)
- **Crash Loop** - 2+ crashes in 5min, restart disabled
- **Restart Failed** - Couldn't restart bot
- **Daily Summary** - Morning (8am) and evening (8pm) totals

### ⚠️ Triage → Kalshi/Molly Alerts Group
- **Exception in Log** - Error detected, needs investigation
- **Bot Frozen** - No activity for 16min
- **Restart Success** - Bot auto-restarted successfully
- **Balance Mismatch** - Discrepancy detected

**Why two tiers?**
- James only gets pinged for truly critical issues
- Molly triages exceptions/warnings during heartbeats
- Reduces noise, faster response on both ends

---

**Status:** Deployed 2026-03-14  
Built by Molly for James
