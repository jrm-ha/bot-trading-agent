"""
Main monitoring loop for Kalshi trading bots.

Monitors BTC, ETH, SOL bots for:
- Process crashes
- Frozen/stuck processes
- Errors in logs
- Stop-loss failures
- Trade events

Auto-restarts crashed bots with crash-loop protection.
Sends Telegram alerts and daily summaries.
"""

import time
import logging
import sys
from pathlib import Path
from datetime import datetime

from config import Config
from database import Database
from alerter import Alerter
from log_parser import LogParser
from bot_tracker import BotTracker
from restarter import BotRestarter
from metrics import MetricsTracker

# Set up logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Config.LOG_PATH),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("monitor.main")


class BotMonitor:
    """Main monitoring orchestrator"""
    
    def __init__(self):
        logger.info("Initializing Bot Monitor...")
        
        # Validate config
        try:
            Config.validate()
        except Exception as e:
            logger.error(f"Configuration error: {e}")
            sys.exit(1)
        
        # Initialize components
        self.db = Database(Config.DB_PATH)
        self.alerter = Alerter(
            Config.TELEGRAM_BOT_TOKEN, 
            Config.TELEGRAM_CHAT_ID,
            self.db,
            triage_chat_id=Config.TELEGRAM_TRIAGE_CHAT_ID
        )
        self.metrics = MetricsTracker(self.db, self.alerter)
        
        # Initialize bot monitors
        self.bots = {}
        for bot_name, bot_config in Config.BOTS.items():
            log_path = Config.BOT_DIR / bot_config['log']
            parser = LogParser(log_path)
            tracker = BotTracker(bot_config, parser, self.db)
            restarter = BotRestarter(bot_config, Config.BOT_DIR, self.db, self.alerter)
            
            self.bots[bot_name] = {
                'config': bot_config,
                'parser': parser,
                'tracker': tracker,
                'restarter': restarter,
            }
        
        logger.info(f"Monitoring {len(self.bots)} bots: {', '.join(self.bots.keys())}")
        
        # State
        self.running = True
        self.check_count = 0
    
    def check_bot(self, bot_name: str) -> dict:
        """
        Perform health check on a single bot.
        
        Returns:
            Status dict with needs_action flag
        """
        bot = self.bots[bot_name]
        tracker = bot['tracker']
        parser = bot['parser']
        
        # Check health
        health = tracker.check_health(Config.FROZEN_THRESHOLD_SEC)
        
        # Parse new log events
        events = parser.parse_new_events()
        
        # Process trade events for metrics
        if events:
            self.metrics.process_trade_events(bot_name, events)
        
        # Check for errors
        if events.get('errors'):
            for error in events['errors'][:3]:  # Limit to first 3 errors
                self.db.log_error(
                    bot_name=bot_name,
                    error_type='exception',
                    message=error['line'][:500],
                    log_line=error['line']
                )
                self.alerter.alert_exception(bot_name, error['line'])
        
        # Check for stop-loss failures
        if events.get('stop_losses'):
            for sl in events['stop_losses']:
                # Alert on stop-loss (may indicate failure if full loss)
                logger.warning(f"{bot_name}: Stop-loss triggered")
                # In future, compare actual loss to expected
        
        # Alert based on status
        if health['status'] == 'crashed':
            self.alerter.alert_bot_crashed(
                bot_name,
                last_seen=health['last_activity'].isoformat() if health['last_activity'] else None
            )
        
        elif health['status'] == 'frozen':
            idle_minutes = int(
                (datetime.now() - health['last_activity']).total_seconds() / 60
            ) if health['last_activity'] else 0
            self.alerter.alert_bot_frozen(bot_name, idle_minutes)
        
        return health
    
    def handle_crashed_bot(self, bot_name: str):
        """
        Handle a crashed bot - attempt restart with protection.
        """
        bot = self.bots[bot_name]
        restarter = bot['restarter']
        
        # Check if we should restart
        should_restart, reason = restarter.should_restart(
            crash_window_sec=Config.CRASH_LOOP_WINDOW_SEC,
            max_crashes=Config.MAX_CRASHES_IN_WINDOW
        )
        
        if not should_restart:
            logger.error(f"{bot_name}: {reason} - NOT restarting")
            
            # Alert crash loop
            crash_count = self.db.get_recent_crashes(
                bot_name, 
                Config.CRASH_LOOP_WINDOW_SEC
            )
            self.alerter.alert_crash_loop(bot_name, crash_count)
            
            return
        
        # Attempt restart
        logger.info(f"{bot_name}: Attempting restart...")
        success, new_pid = restarter.restart_bot(wait_for_market=True)
        
        if success:
            logger.info(f"{bot_name}: Restarted successfully (PID {new_pid})")
            # Update config with new PID
            bot['config']['pid'] = new_pid
        else:
            logger.error(f"{bot_name}: Restart failed")
    
    def run_check_cycle(self):
        """Run one monitoring cycle across all bots"""
        self.check_count += 1
        logger.debug(f"Check cycle #{self.check_count}")
        
        # Update heartbeat file (so external monitors can detect if we freeze)
        try:
            heartbeat_file = Path("/tmp/monitor_heartbeat")
            heartbeat_file.touch()
        except Exception as e:
            logger.warning(f"Failed to update heartbeat file: {e}")
        
        for bot_name in self.bots.keys():
            try:
                health = self.check_bot(bot_name)
                
                # Handle crashed bots
                if health['status'] == 'crashed':
                    self.handle_crashed_bot(bot_name)
                
            except Exception as e:
                logger.error(f"Error checking {bot_name}: {e}", exc_info=True)
        
        # Check if daily summary is due
        self.metrics.send_summary_if_due(Config.SUMMARY_TIMES)
    
    def run(self):
        """Main monitoring loop"""
        logger.info("=" * 60)
        logger.info("Bot Monitor Started")
        logger.info(f"Check interval: {Config.CHECK_INTERVAL_SEC}s")
        logger.info(f"Frozen threshold: {Config.FROZEN_THRESHOLD_SEC}s ({Config.FROZEN_THRESHOLD_SEC/60:.1f}min)")
        logger.info(f"Crash loop: {Config.MAX_CRASHES_IN_WINDOW} crashes in {Config.CRASH_LOOP_WINDOW_SEC}s")
        logger.info(f"Daily summaries: {', '.join(Config.SUMMARY_TIMES)}")
        logger.info("=" * 60)
        
        try:
            while self.running:
                self.run_check_cycle()
                time.sleep(Config.CHECK_INTERVAL_SEC)
                
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
            self.shutdown()
        except Exception as e:
            logger.error(f"Fatal error in main loop: {e}", exc_info=True)
            self.shutdown()
            raise
    
    def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down monitor...")
        self.running = False
        logger.info("Monitor stopped")


def main():
    """Entry point"""
    monitor = BotMonitor()
    monitor.run()


if __name__ == "__main__":
    main()
