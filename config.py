"""
Configuration for bot trading monitor.
All settings can be overridden via environment variables.
"""

import os
from pathlib import Path

class Config:
    """Monitor configuration"""
    
    # Telegram alerting
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8736902793:AAEguym8s4-FX2WIT5_5MucYbbHn8li5L4Q")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "5311548956")  # James's personal chat
    
    # Bot directory
    BOT_DIR = Path(os.getenv("BOT_DIR", "/Users/moltbot/kalshi-bot"))
    
    # Monitoring intervals
    CHECK_INTERVAL_SEC = int(os.getenv("CHECK_INTERVAL", "30"))
    FROZEN_THRESHOLD_SEC = int(os.getenv("FROZEN_THRESHOLD", str(16 * 60)))  # 16 minutes
    
    # Auto-restart settings
    CRASH_LOOP_WINDOW_SEC = int(os.getenv("CRASH_LOOP_WINDOW", str(5 * 60)))  # 5 minutes
    MAX_CRASHES_IN_WINDOW = int(os.getenv("MAX_CRASHES", "2"))
    MARKET_DURATION_SEC = int(os.getenv("MARKET_DURATION", str(15 * 60)))  # 15 minutes
    
    # Unusual loss threshold (full bet lost = stop-loss failed)
    STOP_LOSS_FAILURE_THRESHOLD = 0.95  # If loss >= 95% of bet, stop-loss failed
    
    # Daily summary times (CST)
    SUMMARY_TIMES = ["08:00", "20:00"]  # 8am and 8pm
    
    # Database
    DB_PATH = Path(__file__).parent / "monitor.db"
    
    # Monitor logs
    LOG_PATH = Path(__file__).parent / "monitor.log"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # Bots to monitor
    BOTS = {
        "BTC": {
            "name": "BTC",
            "script": "experiment_continuous.py",
            "log": "experiment.log",
            "pid": None,  # Will be detected
        },
        "ETH": {
            "name": "ETH",
            "script": "experiment_eth.py",
            "log": "experiment_eth.log",
            "pid": None,
        },
        "SOL": {
            "name": "SOL",
            "script": "experiment_sol.py",
            "log": "experiment_sol.log",
            "pid": None,
        },
    }
    
    @classmethod
    def validate(cls):
        """Validate critical configuration"""
        if not cls.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN not set - cannot send alerts!")
        
        if not cls.BOT_DIR.exists():
            raise ValueError(f"BOT_DIR does not exist: {cls.BOT_DIR}")
        
        return True
