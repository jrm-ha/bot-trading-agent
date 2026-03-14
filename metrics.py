"""
Track and aggregate trading metrics for daily summaries.
"""

import logging
from typing import Dict
from datetime import datetime, time as dt_time

logger = logging.getLogger("monitor.metrics")


class MetricsTracker:
    """Aggregate and report bot metrics"""
    
    def __init__(self, db, alerter):
        self.db = db
        self.alerter = alerter
        self.last_summary_date = None
    
    def process_trade_events(self, bot_name: str, events: Dict):
        """
        Process trade events from log parser and update metrics.
        
        Args:
            bot_name: Name of bot
            events: Dict from LogParser.parse_new_events()
        """
        today = datetime.now().date().isoformat()
        
        # Track trades placed
        for trade in events.get('trades_placed', []):
            self.db.log_trade_event(
                bot_name=bot_name,
                event_type='placed',
                ticker=trade.get('ticker'),
                side=trade.get('side'),
                price=trade.get('price'),
                count=trade.get('count')
            )
        
        # Track filled trades
        for trade in events.get('trades_filled', []):
            self.db.log_trade_event(
                bot_name=bot_name,
                event_type='filled',
                ticker=trade.get('ticker'),
                side=trade.get('side'),
                price=trade.get('price'),
                count=trade.get('filled'),
                details=f"Requested: {trade.get('requested', 0)}"
            )
        
        # Track unfilled trades
        for trade in events.get('trades_unfilled', []):
            self.db.log_trade_event(
                bot_name=bot_name,
                event_type='unfilled',
                ticker=trade.get('ticker'),
                side=trade.get('side'),
                price=trade.get('price'),
                count=0
            )
        
        # Track stop-losses
        for sl in events.get('stop_losses', []):
            self.db.log_trade_event(
                bot_name=bot_name,
                event_type='stop_loss',
                ticker=sl.get('ticker'),
                side=sl.get('side'),
                price=sl.get('price'),
                count=sl.get('count'),
                details=f"Type: {sl.get('stop_loss_type', 'unknown')}"
            )
            
            # Check if stop-loss failed (full loss)
            self._check_stop_loss_failure(bot_name, sl)
    
    def _check_stop_loss_failure(self, bot_name: str, stop_loss_event: Dict):
        """
        Detect if stop-loss failed (full bet lost instead of ~20% loss).
        
        This is a critical alert condition.
        """
        # For now, any stop-loss trigger is worth noting
        # In future, compare actual loss to expected ~20% loss
        
        # If we detect a large loss (>95% of bet), alert
        # This requires tracking profit before/after the trade
        # For MVP, we'll alert on any stop-loss and let James review
        
        logger.warning(f"{bot_name}: Stop-loss triggered - {stop_loss_event}")
    
    def update_daily_totals(self, bot_name: str, wins: int = 0, 
                           losses: int = 0, profit: float = 0.0):
        """
        Manually update daily totals (called when we parse profit from logs).
        """
        today = datetime.now().date().isoformat()
        self.db.update_daily_metrics(
            bot_name=bot_name,
            date=today,
            wins=wins,
            losses=losses,
            profit=profit
        )
    
    def get_today_summary(self, bot_name: str) -> Dict:
        """Get summary for today"""
        today = datetime.now().date().isoformat()
        metrics = self.db.get_daily_metrics(bot_name, today)
        
        if not metrics:
            return {
                'wins': 0,
                'losses': 0,
                'total_profit': 0.0,
                'trade_count': 0,
            }
        
        return metrics
    
    def get_all_summaries(self) -> Dict[str, Dict]:
        """Get today's summary for all bots"""
        # Bot names from config
        from config import Config
        
        summaries = {}
        for bot_name in Config.BOTS.keys():
            summaries[bot_name] = self.get_today_summary(bot_name)
        
        return summaries
    
    def should_send_summary(self, summary_times: list) -> bool:
        """
        Check if it's time to send daily summary.
        
        Args:
            summary_times: List of time strings like ["08:00", "20:00"]
            
        Returns:
            True if summary should be sent now
        """
        now = datetime.now()
        current_time = now.time()
        
        # Check if we already sent today
        if self.last_summary_date == now.date():
            return False
        
        # Check if current time matches any summary time (within 1 minute)
        for time_str in summary_times:
            hour, minute = map(int, time_str.split(':'))
            target_time = dt_time(hour, minute)
            
            # If within 1 minute of target time
            time_diff = abs(
                (current_time.hour * 60 + current_time.minute) -
                (target_time.hour * 60 + target_time.minute)
            )
            
            if time_diff <= 1:
                self.last_summary_date = now.date()
                return True
        
        return False
    
    def send_summary_if_due(self, summary_times: list):
        """Send daily summary if it's time"""
        if self.should_send_summary(summary_times):
            summaries = self.get_all_summaries()
            self.alerter.send_daily_summary(summaries)
            logger.info("Sent daily summary")
