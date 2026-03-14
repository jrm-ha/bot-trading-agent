"""
Auto-restart logic with crash loop protection and market-aware timing.
"""

import subprocess
import time
import logging
from typing import Optional
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger("monitor.restarter")


class BotRestarter:
    """Handle bot restart logic"""
    
    def __init__(self, bot_config: dict, bot_dir: Path, db, alerter):
        self.name = bot_config['name']
        self.script_name = bot_config['script']
        self.log_path = bot_config['log']
        self.bot_dir = bot_dir
        self.db = db
        self.alerter = alerter
    
    def should_restart(self, crash_window_sec: int, max_crashes: int) -> tuple[bool, str]:
        """
        Determine if bot should be restarted.
        
        Returns:
            (should_restart: bool, reason: str)
        """
        # Check crash loop
        recent_crashes = self.db.get_recent_crashes(self.name, crash_window_sec)
        
        if recent_crashes >= max_crashes:
            reason = f"Crash loop detected ({recent_crashes} crashes in {crash_window_sec}s)"
            logger.warning(f"{self.name}: {reason}")
            return False, reason
        
        return True, "OK to restart"
    
    def wait_for_market_close(self, market_duration_sec: int, max_wait_sec: int = 900):
        """
        Wait for current 15-minute market to close before restarting.
        
        This prevents interrupting an active trade.
        
        Args:
            market_duration_sec: Duration of one market (default 15min)
            max_wait_sec: Maximum time to wait (default 15min)
        """
        # Calculate time until next market close
        # Markets close at :00, :15, :30, :45 past the hour
        now = datetime.now()
        minute = now.minute
        
        # Find next close time
        next_close_minute = ((minute // 15) + 1) * 15
        if next_close_minute >= 60:
            next_close_minute = 0
            next_close = now.replace(hour=(now.hour + 1) % 24, minute=0, second=0, microsecond=0)
        else:
            next_close = now.replace(minute=next_close_minute, second=0, microsecond=0)
        
        wait_seconds = (next_close - now).total_seconds()
        
        # Cap wait time
        wait_seconds = min(wait_seconds, max_wait_sec)
        
        if wait_seconds > 0:
            logger.info(f"{self.name}: Waiting {wait_seconds:.0f}s for market close before restart")
            time.sleep(wait_seconds)
    
    def restart_bot(self, wait_for_market: bool = True) -> tuple[bool, Optional[int]]:
        """
        Restart the bot process.
        
        Args:
            wait_for_market: If True, wait for market close before restarting
            
        Returns:
            (success: bool, new_pid: int or None)
        """
        logger.info(f"{self.name}: Starting restart procedure")
        
        # Wait for market close
        if wait_for_market:
            self.wait_for_market_close(market_duration_sec=15 * 60)
        
        # Build restart command
        script_path = self.bot_dir / self.script_name
        log_file = self.bot_dir / self.log_path
        
        # Restart command: nohup python3 -u script.py > log.log 2>&1 &
        cmd = [
            'nohup',
            'python3',
            '-u',
            str(script_path),
        ]
        
        try:
            # Start process in background
            with open(log_file, 'a') as log_f:
                proc = subprocess.Popen(
                    cmd,
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                    cwd=str(self.bot_dir),
                    start_new_session=True  # Detach from parent
                )
            
            # Give it a moment to start
            time.sleep(3)
            
            # Verify it's running
            try:
                # Check if process is alive
                proc.poll()
                if proc.returncode is not None:
                    # Process already exited
                    logger.error(f"{self.name}: Process exited immediately (code {proc.returncode})")
                    return False, None
                
                new_pid = proc.pid
                logger.info(f"{self.name}: Restarted successfully (PID {new_pid})")
                
                # Log to database
                crash_count = self.db.get_recent_crashes(self.name, window_sec=5 * 60)
                self.db.log_restart(
                    bot_name=self.name,
                    reason="auto_restart_after_crash",
                    success=True,
                    new_pid=new_pid,
                    crash_count=crash_count + 1
                )
                
                # Reset failure counter
                self.db.reset_failure_count(self.name)
                
                # Alert success
                self.alerter.alert_restart_success(self.name, new_pid)
                
                return True, new_pid
                
            except Exception as e:
                logger.error(f"{self.name}: Failed to verify restart: {e}")
                return False, None
        
        except Exception as e:
            logger.error(f"{self.name}: Restart failed: {e}")
            
            # Log failure
            self.db.log_restart(
                bot_name=self.name,
                reason="auto_restart_after_crash",
                success=False,
                new_pid=None,
                crash_count=0
            )
            
            # Increment failure counter
            self.db.increment_failure_count(self.name)
            
            # Alert failure
            self.alerter.alert_restart_failed(self.name, str(e))
            
            return False, None
    
    def force_stop(self, pid: int) -> bool:
        """
        Force-stop a bot process.
        Use with caution.
        """
        try:
            import signal
            import os
            
            os.kill(pid, signal.SIGTERM)
            time.sleep(2)
            
            # Check if still alive
            try:
                os.kill(pid, 0)  # Check if process exists
                # Still alive, force kill
                os.kill(pid, signal.SIGKILL)
                logger.warning(f"{self.name}: Force killed PID {pid}")
            except OSError:
                # Already dead
                logger.info(f"{self.name}: Process {pid} terminated")
            
            return True
            
        except Exception as e:
            logger.error(f"{self.name}: Failed to stop PID {pid}: {e}")
            return False
