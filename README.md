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
- `TELEGRAM_CHAT_ID` - Your chat ID
- `BOT_DIR` - Path to kalshi-bot directory
- `CHECK_INTERVAL` - Seconds between checks (default: 30)

## Running

**As spawned OpenClaw agent:**
```bash
# From OpenClaw, spawn persistent agent:
/sessions spawn --runtime subagent --mode session --task "Run monitoring agent" --label bot-monitor
```

**Standalone (testing):**
```bash
cd ~/bot-trading-agent
python monitor.py
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

## Alerts Reference

| Alert | Trigger | Action |
|-------|---------|--------|
| Bot Crashed | PID missing | Auto-restart after market close |
| Exception in Log | Error detected | Immediate Telegram alert |
| Stop-loss Failed | Full bet lost | Immediate alert (critical) |
| Bot Frozen | No activity 16min | Investigate + alert |
| Crash Loop | 2nd crash in 5min | Stop restart + alert |
| Balance Mismatch | Large discrepancy | Alert for review |

## NOT DEPLOYED YET

**Status:** Code built, under review.  
**Deploy after:** 3 more reviews at 8am 2026-03-14.

---

Built by Molly for James - March 14, 2026
