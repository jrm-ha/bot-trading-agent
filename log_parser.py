"""
Parse bot logs to extract trade events, errors, and activity.
"""

import re
import logging
from typing import Optional, Dict, List, Tuple
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("monitor.log_parser")


class LogParser:
    """Parse bot log files for events"""
    
    # Regex patterns for log events
    PATTERNS = {
        'bet_placed': re.compile(
            r'💰 BETTING: (YES|NO) @ (\d+)¢ x(\d+)'
        ),
        'order_placed': re.compile(
            r'✅ Order placed: ([a-f0-9-]+)'
        ),
        'filled': re.compile(
            r'✅ FILLED: (\d+) of (\d+) contracts'
        ),
        'no_fills': re.compile(
            r'❌ NO FILLS after'
        ),
        'stop_loss': re.compile(
            r'🛑 (STOP-LOSS|FORCE-EXIT) TRIGGERED!'
        ),
        'market_closed': re.compile(
            r'⏱️  Market closed'
        ),
        'profit': re.compile(
            r'Profit since restart: \$([+-]?[\d.]+)'
        ),
        'session_stats': re.compile(
            r'📊 Session: (\d+)W/(\d+)L'
        ),
        'balance': re.compile(
            r'💰 Balance: \$([\d,]+\.?\d*)'
        ),
        'error': re.compile(
            r'(❌|⚠️|ERROR|Exception|Traceback)'
        ),
    }
    
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.last_position = 0
        self.last_check = datetime.now()
    
    def get_new_lines(self) -> List[str]:
        """Read new lines since last check"""
        if not self.log_path.exists():
            return []
        
        try:
            with open(self.log_path, 'r') as f:
                f.seek(self.last_position)
                new_lines = f.readlines()
                self.last_position = f.tell()
                return new_lines
        except Exception as e:
            logger.error(f"Error reading log {self.log_path}: {e}")
            return []
    
    def parse_new_events(self) -> Dict[str, List]:
        """Parse new log lines and extract events"""
        lines = self.get_new_lines()
        
        events = {
            'trades_placed': [],
            'trades_filled': [],
            'trades_unfilled': [],
            'stop_losses': [],
            'errors': [],
            'wins': [],
            'losses': [],
        }
        
        # Track current trade context
        current_trade = {}
        
        for line in lines:
            line = line.strip()
            
            # Bet placed
            match = self.PATTERNS['bet_placed'].search(line)
            if match:
                side, price, count = match.groups()
                current_trade = {
                    'side': side,
                    'price': int(price),
                    'count': int(count),
                    'timestamp': datetime.now().isoformat(),
                }
                events['trades_placed'].append(current_trade.copy())
            
            # Order placed (get order ID)
            match = self.PATTERNS['order_placed'].search(line)
            if match and current_trade:
                current_trade['order_id'] = match.group(1)
            
            # Filled
            match = self.PATTERNS['filled'].search(line)
            if match and current_trade:
                filled, total = match.groups()
                current_trade['filled'] = int(filled)
                current_trade['requested'] = int(total)
                events['trades_filled'].append(current_trade.copy())
            
            # No fills (trade failed)
            if self.PATTERNS['no_fills'].search(line) and current_trade:
                current_trade['filled'] = 0
                events['trades_unfilled'].append(current_trade.copy())
                current_trade = {}  # Reset
            
            # Stop-loss triggered
            match = self.PATTERNS['stop_loss'].search(line)
            if match and current_trade:
                current_trade['stop_loss_type'] = match.group(1)
                events['stop_losses'].append(current_trade.copy())
            
            # Profit tracking (to detect wins/losses)
            match = self.PATTERNS['profit'].search(line)
            if match:
                profit = float(match.group(1))
                # If profit increased, likely a win
                # This is approximate - better to track specific trades
                pass
            
            # Session stats
            match = self.PATTERNS['session_stats'].search(line)
            if match:
                wins, losses = match.groups()
                # Store for daily summary
                pass
            
            # Errors
            if self.PATTERNS['error'].search(line):
                events['errors'].append({
                    'line': line,
                    'timestamp': datetime.now().isoformat(),
                })
        
        self.last_check = datetime.now()
        return events
    
    def get_last_activity_time(self) -> Optional[datetime]:
        """Get timestamp of last log entry"""
        if not self.log_path.exists():
            return None
        
        try:
            # Get last modified time of log file
            mtime = self.log_path.stat().st_mtime
            return datetime.fromtimestamp(mtime)
        except Exception as e:
            logger.error(f"Error getting log mtime: {e}")
            return None
    
    def detect_stop_loss_failure(self, events: Dict) -> List[Dict]:
        """
        Detect stop-loss failures: full bet lost instead of ~20% loss.
        
        If a trade was placed and we see a large loss without a proper
        stop-loss exit, that's a failure.
        """
        failures = []
        
        # Check for trades that triggered stop-loss
        for sl_event in events.get('stop_losses', []):
            # Check if the loss was catastrophic (full bet amount)
            # This requires tracking profit before/after
            # For now, any stop-loss trigger is logged
            failures.append({
                'type': 'stop_loss_triggered',
                'details': sl_event,
            })
        
        # Check for trades that were filled but had no fills reported
        for placed in events.get('trades_placed', []):
            filled_match = [f for f in events.get('trades_filled', [])
                           if f.get('order_id') == placed.get('order_id')]
            
            if not filled_match and placed.get('order_id'):
                # Trade placed but never filled - could indicate issue
                # Not necessarily a stop-loss failure, but worth noting
                pass
        
        return failures
    
    def analyze_recent_performance(self, lines_to_check: int = 100) -> Dict:
        """
        Analyze recent log lines for patterns.
        Returns summary of recent activity.
        """
        if not self.log_path.exists():
            return {}
        
        try:
            with open(self.log_path, 'r') as f:
                all_lines = f.readlines()
                recent_lines = all_lines[-lines_to_check:]
            
            stats = {
                'trades_placed': 0,
                'errors': 0,
                'stop_losses': 0,
                'has_activity': False,
            }
            
            for line in recent_lines:
                if self.PATTERNS['bet_placed'].search(line):
                    stats['trades_placed'] += 1
                    stats['has_activity'] = True
                
                if self.PATTERNS['stop_loss'].search(line):
                    stats['stop_losses'] += 1
                    stats['has_activity'] = True
                
                if self.PATTERNS['error'].search(line):
                    stats['errors'] += 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Error analyzing log: {e}")
            return {}
