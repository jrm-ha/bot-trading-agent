"""
SQLite database for persistent state tracking.
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
from contextlib import contextmanager

logger = logging.getLogger("monitor.database")


class Database:
    """Persistent state storage"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_schema()
    
    @contextmanager
    def _conn(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()
    
    def _init_schema(self):
        """Create tables if they don't exist"""
        with self._conn() as conn:
            conn.executescript("""
                -- Bot health state
                CREATE TABLE IF NOT EXISTS bot_health (
                    bot_name TEXT PRIMARY KEY,
                    pid INTEGER,
                    is_running BOOLEAN,
                    last_activity TEXT,
                    last_check TEXT,
                    status TEXT,
                    consecutive_failures INTEGER DEFAULT 0
                );
                
                -- Restart history
                CREATE TABLE IF NOT EXISTS restart_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot_name TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    reason TEXT,
                    success BOOLEAN,
                    new_pid INTEGER,
                    crash_count_in_window INTEGER
                );
                
                -- Trade events (parsed from logs)
                CREATE TABLE IF NOT EXISTS trade_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot_name TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,  -- 'placed', 'won', 'lost', 'stop_loss'
                    ticker TEXT,
                    side TEXT,
                    price INTEGER,
                    count INTEGER,
                    profit REAL,
                    details TEXT
                );
                
                -- Error log
                CREATE TABLE IF NOT EXISTS error_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot_name TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    error_type TEXT NOT NULL,
                    message TEXT,
                    log_line TEXT
                );
                
                -- Daily metrics
                CREATE TABLE IF NOT EXISTS daily_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot_name TEXT NOT NULL,
                    date TEXT NOT NULL,
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    total_profit REAL DEFAULT 0.0,
                    trade_count INTEGER DEFAULT 0,
                    UNIQUE(bot_name, date)
                );
                
                -- Alert history (to prevent spam)
                CREATE TABLE IF NOT EXISTS alert_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_type TEXT NOT NULL,
                    bot_name TEXT,
                    timestamp TEXT NOT NULL,
                    message TEXT
                );
            """)
        logger.info(f"Database initialized: {self.db_path}")
    
    # ── Bot Health ──────────────────────────────────────────────────
    
    def update_bot_health(self, bot_name: str, pid: Optional[int], 
                          is_running: bool, last_activity: Optional[str],
                          status: str):
        """Update current health state for a bot"""
        with self._conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO bot_health 
                (bot_name, pid, is_running, last_activity, last_check, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (bot_name, pid, is_running, last_activity, 
                  datetime.now().isoformat(), status))
    
    def get_bot_health(self, bot_name: str) -> Optional[Dict]:
        """Get current health state"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM bot_health WHERE bot_name = ?", 
                (bot_name,)
            ).fetchone()
            return dict(row) if row else None
    
    def increment_failure_count(self, bot_name: str):
        """Increment consecutive failure counter"""
        with self._conn() as conn:
            conn.execute("""
                UPDATE bot_health 
                SET consecutive_failures = consecutive_failures + 1
                WHERE bot_name = ?
            """, (bot_name,))
    
    def reset_failure_count(self, bot_name: str):
        """Reset failure counter (bot recovered)"""
        with self._conn() as conn:
            conn.execute("""
                UPDATE bot_health 
                SET consecutive_failures = 0
                WHERE bot_name = ?
            """, (bot_name,))
    
    # ── Restart History ─────────────────────────────────────────────
    
    def log_restart(self, bot_name: str, reason: str, success: bool,
                    new_pid: Optional[int], crash_count: int):
        """Record a restart attempt"""
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO restart_history 
                (bot_name, timestamp, reason, success, new_pid, crash_count_in_window)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (bot_name, datetime.now().isoformat(), reason, 
                  success, new_pid, crash_count))
    
    def get_recent_crashes(self, bot_name: str, window_sec: int) -> int:
        """Count crashes in time window"""
        cutoff = datetime.now().timestamp() - window_sec
        cutoff_iso = datetime.fromtimestamp(cutoff).isoformat()
        
        with self._conn() as conn:
            result = conn.execute("""
                SELECT COUNT(*) FROM restart_history
                WHERE bot_name = ? 
                AND timestamp > ?
                AND reason LIKE '%crash%'
            """, (bot_name, cutoff_iso)).fetchone()
            return result[0] if result else 0
    
    # ── Trade Events ────────────────────────────────────────────────
    
    def log_trade_event(self, bot_name: str, event_type: str,
                       ticker: Optional[str] = None,
                       side: Optional[str] = None,
                       price: Optional[int] = None,
                       count: Optional[int] = None,
                       profit: Optional[float] = None,
                       details: Optional[str] = None):
        """Record a trade event from logs"""
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO trade_events
                (bot_name, timestamp, event_type, ticker, side, price, count, profit, details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (bot_name, datetime.now().isoformat(), event_type,
                  ticker, side, price, count, profit, details))
    
    def get_today_trades(self, bot_name: str) -> List[Dict]:
        """Get all trades for today"""
        today = datetime.now().date().isoformat()
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM trade_events
                WHERE bot_name = ?
                AND DATE(timestamp) = ?
                ORDER BY timestamp DESC
            """, (bot_name, today)).fetchall()
            return [dict(row) for row in rows]
    
    # ── Error Log ───────────────────────────────────────────────────
    
    def log_error(self, bot_name: str, error_type: str, message: str,
                  log_line: Optional[str] = None):
        """Record an error from logs"""
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO error_log
                (bot_name, timestamp, error_type, message, log_line)
                VALUES (?, ?, ?, ?, ?)
            """, (bot_name, datetime.now().isoformat(), error_type,
                  message, log_line))
    
    # ── Daily Metrics ───────────────────────────────────────────────
    
    def update_daily_metrics(self, bot_name: str, date: str,
                            wins: int = 0, losses: int = 0,
                            profit: float = 0.0):
        """Update or increment daily metrics"""
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO daily_metrics (bot_name, date, wins, losses, total_profit, trade_count)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(bot_name, date) DO UPDATE SET
                    wins = wins + excluded.wins,
                    losses = losses + excluded.losses,
                    total_profit = total_profit + excluded.total_profit,
                    trade_count = trade_count + excluded.trade_count
            """, (bot_name, date, wins, losses, profit, wins + losses))
    
    def get_daily_metrics(self, bot_name: str, date: str) -> Optional[Dict]:
        """Get metrics for a specific date"""
        with self._conn() as conn:
            row = conn.execute("""
                SELECT * FROM daily_metrics
                WHERE bot_name = ? AND date = ?
            """, (bot_name, date)).fetchone()
            return dict(row) if row else None
    
    # ── Alert History ───────────────────────────────────────────────
    
    def log_alert(self, alert_type: str, bot_name: Optional[str], message: str):
        """Record an alert sent"""
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO alert_history (alert_type, bot_name, timestamp, message)
                VALUES (?, ?, ?, ?)
            """, (alert_type, bot_name, datetime.now().isoformat(), message))
    
    def get_recent_alerts(self, alert_type: str, minutes: int = 5) -> int:
        """Count recent alerts of this type (prevent spam)"""
        cutoff = datetime.now().timestamp() - (minutes * 60)
        cutoff_iso = datetime.fromtimestamp(cutoff).isoformat()
        
        with self._conn() as conn:
            result = conn.execute("""
                SELECT COUNT(*) FROM alert_history
                WHERE alert_type = ? AND timestamp > ?
            """, (alert_type, cutoff_iso)).fetchone()
            return result[0] if result else 0
