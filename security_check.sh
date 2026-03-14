#!/bin/bash

echo "=== SECURITY REVIEW #5 ===" echo
echo "## 1. Checking File Permissions"
echo

# Check Python files
echo "Python files:"
ls -l *.py | awk '{print $1, $9}'
echo

# Check if database exists yet
if [ -f "monitor.db" ]; then
    echo "Database file:"
    ls -l monitor.db | awk '{print $1, $9}'
else
    echo "Database: Not created yet (will be created with default permissions)"
fi
echo

# Check if log exists yet
if [ -f "monitor.log" ]; then
    echo "Monitor log:"
    ls -l monitor.log | awk '{print $1, $9}'
else
    echo "Monitor log: Not created yet"
fi
echo

echo "## 2. Checking for Hardcoded Secrets"
echo

echo "Searching for API keys, passwords, tokens..."
rg -i "api.?key|password|secret|token" --type py | grep -v "TELEGRAM_BOT_TOKEN" | grep -v "# " || echo "  ✅ No unexpected secrets found"
echo

echo "Telegram token in config.py:"
grep "TELEGRAM_BOT_TOKEN" config.py | head -1
echo "  ⚠️  Hardcoded token present (acceptable per Review #3 - private repo)"
echo

echo "## 3. Checking for Command Injection Risks"
echo

echo "Looking for shell=True in subprocess calls..."
grep -n "shell=True" *.py || echo "  ✅ No shell=True found"
echo

echo "Checking subprocess calls..."
grep -n "subprocess\." *.py | head -20
echo

echo "## 4. Checking External Input Handling"
echo

echo "Looking for user input / external data usage..."
rg "input\(|eval\(|exec\(" --type py || echo "  ✅ No dangerous input functions"
echo

echo "## 5. SQL Injection Check"
echo

echo "Checking for string formatting in SQL..."
rg "f\".*SELECT|f\".*INSERT|\.format\(.*SELECT" --type py || echo "  ✅ No SQL injection risk (using placeholders)"
echo

echo "=== END SECURITY REVIEW ==="
