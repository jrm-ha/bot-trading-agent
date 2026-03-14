"""
Track bot processes and health status.
"""

import psutil
import logging
from typing import Optional, Dict
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger("monitor.bot_tracker")


class BotTracker:
    """Monitor bot process health"""
    
    def __init__(self, bot_config: dict, log_parser, db):
        self.name = bot_config['name']
        self.script_name = bot_config['script']
        self.log_path = bot_config['log']
        self.expected_pid = bot_config.get('pid')
        
        self.parser = log_parser
        self.db = db
        
        self.current_pid = None
        self.last_seen_alive = None
        self.last_activity = None
        self.status = "unknown"
    
    def check_health(self, frozen_threshold_sec: int) -> Dict:
        """
        Check current health status.
        
        Returns:
            {
                'is_running': bool,
                'pid': int or None,
                'last_activity': datetime or None,
                'status': str,
                'needs_action': bool,
                'action': str or None
            }
        """
        # Find process
        pid = self._find_process()
        is_running = pid is not None
        
        # Get last activity from log
        last_activity = self.parser.get_last_activity_time()
        
        # Determine status
        status = "healthy"
        needs_action = False
        action = None
        
        if not is_running:
            status = "crashed"
            needs_action = True
            action = "restart"
        elif last_activity:
            idle_seconds = (datetime.now() - last_activity).total_seconds()
            if idle_seconds > frozen_threshold_sec:
                status = "frozen"
                needs_action = True
                action = "investigate"
        
        # Update internal state
        self.current_pid = pid
        if is_running:
            self.last_seen_alive = datetime.now()
        self.last_activity = last_activity
        self.status = status
        
        # Update database
        self.db.update_bot_health(
            bot_name=self.name,
            pid=pid,
            is_running=is_running,
            last_activity=last_activity.isoformat() if last_activity else None,
            status=status
        )
        
        return {
            'is_running': is_running,
            'pid': pid,
            'last_activity': last_activity,
            'status': status,
            'needs_action': needs_action,
            'action': action,
        }
    
    def _find_process(self) -> Optional[int]:
        """
        Find bot process by script name.
        Returns PID if found, None otherwise.
        """
        try:
            for proc in psutil.process_iter(['pid', 'cmdline']):
                try:
                    cmdline = proc.info['cmdline']
                    if cmdline and any(self.script_name in arg for arg in cmdline):
                        return proc.info['pid']
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            logger.error(f"Error finding process for {self.name}: {e}")
        
        return None
    
    def is_process_alive(self, pid: int) -> bool:
        """Check if a specific PID is alive"""
        try:
            return psutil.pid_exists(pid) and psutil.Process(pid).is_running()
        except:
            return False
    
    def get_process_uptime(self) -> Optional[timedelta]:
        """Get how long current process has been running"""
        if not self.current_pid:
            return None
        
        try:
            proc = psutil.Process(self.current_pid)
            create_time = datetime.fromtimestamp(proc.create_time())
            return datetime.now() - create_time
        except:
            return None
    
    def get_process_memory(self) -> Optional[float]:
        """Get process memory usage in MB"""
        if not self.current_pid:
            return None
        
        try:
            proc = psutil.Process(self.current_pid)
            return proc.memory_info().rss / 1024 / 1024  # bytes to MB
        except:
            return None
    
    def analyze_recent_activity(self) -> Dict:
        """Get summary of recent bot activity from logs"""
        return self.parser.analyze_recent_performance()
