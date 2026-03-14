# Deployment Guide

## ⚠️ Pre-Deployment Checklist

**DO NOT DEPLOY until all reviews are complete:**

- [ ] Code review #1 (while building) ✅ 
- [ ] Code review #2 (edge cases)
- [ ] Code review #3 (financial safety)
- [ ] **Wait until 8am March 14, 2026**
- [ ] Code review #4 (fresh eyes - 8am)
- [ ] Code review #5 (fresh eyes - 8am)
- [ ] Code review #6 (fresh eyes - 8am)
- [ ] Manual testing (dry-run mode)
- [ ] James approval

---

## Installation

### 1. Clone Repository

```bash
cd ~
git clone https://github.com/jrm-ha/bot-trading-agent.git
cd bot-trading-agent
```

### 2. Install Dependencies

```bash
pip3 install -r requirements.txt
```

### 3. Configure Environment

Get Telegram bot token if needed:
```bash
# Create bot via @BotFather on Telegram
# Get your chat ID from @userinfobot
```

Set environment variables (or edit `config.py`):
```bash
export TELEGRAM_BOT_TOKEN="your_token_here"
export TELEGRAM_CHAT_ID="5311548956"
export BOT_DIR="/Users/moltbot/kalshi-bot"
```

### 4. Test Configuration

```bash
python3 -c "from config import Config; Config.validate(); print('Config OK')"
```

---

## Testing (Pre-Deployment)

### Dry-Run Test

```bash
# Run monitor in test mode (short cycles)
CHECK_INTERVAL=5 python3 monitor.py
```

**What to verify:**
- [ ] Finds all 3 bot PIDs correctly
- [ ] Parses logs without errors
- [ ] Database created and populated
- [ ] No crashes in first 5 minutes
- [ ] Telegram token works (if set)

### Crash Detection Test

```bash
# In another terminal:
# Kill one bot
kill <BTC_PID>

# Monitor should detect crash within 30s
# Should log restart attempt
# Should wait for market close
```

### Log Parsing Test

```bash
# Check recent log parsing
python3 -c "
from log_parser import LogParser
from pathlib import Path
parser = LogParser(Path('/Users/moltbot/kalshi-bot/experiment.log'))
events = parser.parse_new_events()
print(f'Events: {events}')
"
```

---

## Deployment

### Option 1: As OpenClaw Spawned Agent (Recommended)

From OpenClaw chat:
```
/sessions spawn \
  --runtime subagent \
  --mode session \
  --task "cd ~/bot-trading-agent && python3 monitor.py" \
  --label bot-monitor \
  --thread false
```

**Verify it's running:**
```
/sessions list
```

**Check logs:**
```
tail -f ~/bot-trading-agent/monitor.log
```

### Option 2: Standalone Background Process

```bash
cd ~/bot-trading-agent
nohup python3 monitor.py > monitor.log 2>&1 &
echo $! > monitor.pid
```

**Stop it:**
```bash
kill $(cat ~/bot-trading-agent/monitor.pid)
```

---

## Post-Deployment Verification

### Immediate Checks (first 5 minutes)

- [ ] Monitor process is running
- [ ] Database file created (`monitor.db`)
- [ ] Log file being written (`monitor.log`)
- [ ] No errors in logs
- [ ] All 3 bots detected (check logs for PIDs)
- [ ] No immediate restarts triggered

### After 1 Hour

- [ ] Health checks running every 30s (check log timestamps)
- [ ] Trade events being parsed (check database)
- [ ] No crash loops
- [ ] Telegram alerts working (if configured)

### After 24 Hours

- [ ] Daily summary sent (8am and 8pm)
- [ ] Database growing appropriately
- [ ] No memory leaks (check process memory)
- [ ] All 3 bots still healthy

---

## Monitoring the Monitor

### Check if monitor is running
```bash
ps aux | grep "monitor.py" | grep -v grep
```

### View recent logs
```bash
tail -50 ~/bot-trading-agent/monitor.log
```

### Check database stats
```bash
sqlite3 ~/bot-trading-agent/monitor.db "
SELECT bot_name, status, last_check 
FROM bot_health;
"
```

### View recent restarts
```bash
sqlite3 ~/bot-trading-agent/monitor.db "
SELECT bot_name, timestamp, success, new_pid 
FROM restart_history 
ORDER BY timestamp DESC 
LIMIT 10;
"
```

### View today's metrics
```bash
sqlite3 ~/bot-trading-agent/monitor.db "
SELECT * FROM daily_metrics 
WHERE date = DATE('now');
"
```

---

## Troubleshooting

### Monitor not starting
```bash
# Check Python path
which python3

# Check dependencies
pip3 list | grep -E "psutil|requests"

# Run with verbose logging
LOG_LEVEL=DEBUG python3 monitor.py
```

### Telegram alerts not working
```bash
# Test token
python3 -c "
from alerter import Alerter
from database import Database
from pathlib import Path

db = Database(Path('test.db'))
alerter = Alerter('YOUR_TOKEN', 'YOUR_CHAT_ID', db)
alerter.send('Test message', 'test')
"
```

### Bots not detected
```bash
# Check bot directory
ls -la /Users/moltbot/kalshi-bot/experiment*.py

# Check processes manually
ps aux | grep experiment
```

### Restart not working
```bash
# Check bot directory permissions
ls -la /Users/moltbot/kalshi-bot/

# Test restart manually
cd /Users/moltbot/kalshi-bot
nohup python3 -u experiment_continuous.py > experiment.log 2>&1 &
```

---

## Emergency Stop

### Stop monitor only
```bash
# If spawned via OpenClaw:
/subagents kill bot-monitor

# If standalone:
pkill -f "python3 monitor.py"
```

### Stop everything (monitor + all bots)
```bash
pkill -f "experiment_.*\.py"
pkill -f "monitor.py"
```

---

## Rollback Plan

If monitor causes issues:

1. **Stop monitor immediately:**
   ```bash
   pkill -f "monitor.py"
   ```

2. **Verify bots still running:**
   ```bash
   ps aux | grep experiment
   ```

3. **Check what monitor did:**
   ```bash
   tail -100 ~/bot-trading-agent/monitor.log
   sqlite3 ~/bot-trading-agent/monitor.db "SELECT * FROM restart_history;"
   ```

4. **If bots were stopped, restart manually:**
   ```bash
   cd /Users/moltbot/kalshi-bot
   ./restart_bots.sh  # Or manual commands from KALSHI_BOT.md
   ```

---

## Success Metrics

**After 1 week, monitor should have:**
- Zero crash loops (stopped after 2nd crash correctly)
- Successfully restarted any crashed bots
- Sent 14 daily summaries (2 per day)
- Detected and alerted on all errors
- No false positives (frozen bot alerts when bot is actually fine)

---

Built by Molly for James - Ready for deployment after 6 reviews
