"""
Telegram alerting system with rate limiting and deduplication.
"""

import logging
import requests
from typing import Optional
from datetime import datetime

logger = logging.getLogger("monitor.alerter")


class Alerter:
    """Send alerts via Telegram with spam prevention and severity-based routing"""
    
    def __init__(self, bot_token: str, chat_id: str, db, triage_chat_id: Optional[str] = None):
        self.bot_token = bot_token
        self.chat_id = chat_id  # Critical alerts → James
        self.triage_chat_id = triage_chat_id or chat_id  # Triage → Molly or fallback to James
        self.db = db
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
    
    def send(self, message: str, alert_type: str = "info", 
             bot_name: Optional[str] = None, 
             rate_limit_min: int = 1,
             target_chat_id: Optional[str] = None) -> bool:
        """
        Send Telegram message with rate limiting.
        
        Args:
            message: Alert message
            alert_type: Type of alert (for deduplication)
            bot_name: Bot this alert is about
            rate_limit_min: Don't send same alert_type within N minutes
            target_chat_id: Override default chat_id (for routing)
            
        Returns:
            True if sent, False if rate-limited or failed
        """
        # Check rate limit
        recent_count = self.db.get_recent_alerts(alert_type, rate_limit_min)
        if recent_count > 0:
            logger.info(f"Rate-limited alert type '{alert_type}' (sent {recent_count}x in last {rate_limit_min}min)")
            return False
        
        chat_id = target_chat_id or self.chat_id
        
        try:
            response = requests.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "Markdown",
                },
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Alert sent: {alert_type}")
                self.db.log_alert(alert_type, bot_name, message)
                return True
            else:
                logger.error(f"Telegram API error {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            return False
    
    # ── Predefined Alert Templates ─────────────────────────────────
    
    def alert_bot_crashed(self, bot_name: str, last_seen: Optional[str] = None):
        """Alert that a bot process died"""
        msg = f"🚨 **{bot_name} Bot Crashed**\n\n"
        msg += f"Process is no longer running.\n"
        if last_seen:
            msg += f"Last seen: {last_seen}\n"
        msg += f"\nWill auto-restart after market close."
        
        return self.send(msg, alert_type=f"crash_{bot_name}", 
                        bot_name=bot_name, rate_limit_min=5)
    
    def alert_bot_frozen(self, bot_name: str, minutes_idle: int):
        """Alert that bot is alive but inactive → TRIAGE"""
        msg = f"⚠️ **{bot_name} Bot Frozen**\n\n"
        msg += f"Process running but no activity for {minutes_idle} minutes.\n"
        msg += f"Investigating..."
        
        return self.send(msg, alert_type=f"frozen_{bot_name}",
                        bot_name=bot_name, rate_limit_min=10,
                        target_chat_id=self.triage_chat_id)
    
    def alert_exception(self, bot_name: str, error_line: str):
        """Alert on exception in logs → TRIAGE"""
        msg = f"❌ **{bot_name} Exception**\n\n"
        msg += f"```\n{error_line[:200]}\n```"
        
        return self.send(msg, alert_type=f"exception_{bot_name}",
                        bot_name=bot_name, rate_limit_min=3,
                        target_chat_id=self.triage_chat_id)
    
    def alert_stop_loss_failure(self, bot_name: str, trade_details: dict):
        """CRITICAL: Stop-loss failed, full bet lost"""
        msg = f"🔴 **CRITICAL: {bot_name} Stop-Loss Failed**\n\n"
        msg += f"Full bet amount lost!\n"
        msg += f"Side: {trade_details.get('side', 'unknown')}\n"
        msg += f"Price: {trade_details.get('price', 'unknown')}¢\n"
        msg += f"Count: {trade_details.get('count', 'unknown')}\n"
        msg += f"\n⚠️ Check stop-loss code immediately!"
        
        # Critical alerts bypass rate limiting
        return self.send(msg, alert_type=f"stop_loss_fail_{bot_name}",
                        bot_name=bot_name, rate_limit_min=0)
    
    def alert_crash_loop(self, bot_name: str, crash_count: int):
        """Alert that bot is crash-looping"""
        msg = f"🛑 **{bot_name} Crash Loop Detected**\n\n"
        msg += f"Bot crashed {crash_count} times in 5 minutes.\n"
        msg += f"Auto-restart **disabled** to prevent loop.\n"
        msg += f"\nManual intervention required!"
        
        return self.send(msg, alert_type=f"crash_loop_{bot_name}",
                        bot_name=bot_name, rate_limit_min=15)
    
    def alert_restart_success(self, bot_name: str, new_pid: int):
        """Inform that bot was restarted → TRIAGE"""
        msg = f"✅ **{bot_name} Restarted**\n\n"
        msg += f"New PID: {new_pid}\n"
        msg += f"Monitoring resumed."
        
        return self.send(msg, alert_type=f"restart_{bot_name}",
                        bot_name=bot_name, rate_limit_min=5,
                        target_chat_id=self.triage_chat_id)
    
    def alert_restart_failed(self, bot_name: str, reason: str):
        """Alert that restart attempt failed"""
        msg = f"❌ **{bot_name} Restart Failed**\n\n"
        msg += f"Reason: {reason}\n"
        msg += f"Bot remains down!"
        
        return self.send(msg, alert_type=f"restart_fail_{bot_name}",
                        bot_name=bot_name, rate_limit_min=5)
    
    def send_daily_summary(self, summaries: dict):
        """
        Send daily summary for all bots.
        
        Args:
            summaries: Dict of bot_name -> metrics
        """
        time_label = datetime.now().strftime("%I:%M %p")
        msg = f"📊 **Daily Summary ({time_label})**\n\n"
        
        for bot_name, metrics in summaries.items():
            wins = metrics.get('wins', 0)
            losses = metrics.get('losses', 0)
            profit = metrics.get('total_profit', 0.0)
            trades = metrics.get('trade_count', 0)
            
            profit_emoji = "🟢" if profit >= 0 else "🔴"
            
            msg += f"**{bot_name}:**\n"
            msg += f"  Trades: {trades} ({wins}W / {losses}L)\n"
            msg += f"  Profit: {profit_emoji} ${profit:+.2f}\n\n"
        
        return self.send(msg, alert_type="daily_summary", rate_limit_min=60)
    
    def alert_balance_mismatch(self, expected: float, actual: float):
        """Alert on significant balance discrepancy"""
        diff = actual - expected
        diff_pct = (diff / expected * 100) if expected > 0 else 0
        
        msg = f"⚠️ **Balance Mismatch**\n\n"
        msg += f"Expected: ${expected:.2f}\n"
        msg += f"Actual: ${actual:.2f}\n"
        msg += f"Difference: ${diff:+.2f} ({diff_pct:+.1f}%)\n"
        
        return self.send(msg, alert_type="balance_mismatch", rate_limit_min=30)
