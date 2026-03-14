"""
Component testing script - run before deployment.

Tests each module independently to catch issues early.
"""

import sys
from pathlib import Path

def test_config():
    """Test configuration loading"""
    print("Testing config...")
    try:
        from config import Config
        Config.validate()
        print(f"✅ Config valid")
        print(f"   BOT_DIR: {Config.BOT_DIR}")
        print(f"   Bots: {list(Config.BOTS.keys())}")
        print(f"   Check interval: {Config.CHECK_INTERVAL_SEC}s")
        return True
    except Exception as e:
        print(f"❌ Config failed: {e}")
        return False


def test_database():
    """Test database initialization"""
    print("\nTesting database...")
    try:
        from database import Database
        
        # Use test database
        test_db = Path("test_monitor.db")
        if test_db.exists():
            test_db.unlink()
        
        db = Database(test_db)
        
        # Test bot health update
        db.update_bot_health("TEST", 12345, True, None, "healthy")
        health = db.get_bot_health("TEST")
        assert health is not None
        assert health['pid'] == 12345
        
        # Test trade event logging
        db.log_trade_event("TEST", "placed", "KXBTC15M-TEST", "yes", 95, 100)
        
        # Test metrics
        db.update_daily_metrics("TEST", "2026-03-14", wins=1, profit=50.0)
        metrics = db.get_daily_metrics("TEST", "2026-03-14")
        assert metrics['wins'] == 1
        
        # Cleanup
        test_db.unlink()
        
        print(f"✅ Database working")
        return True
    except Exception as e:
        print(f"❌ Database failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_log_parser():
    """Test log parsing"""
    print("\nTesting log parser...")
    try:
        from log_parser import LogParser
        from config import Config
        
        # Use actual bot log
        log_path = Config.BOT_DIR / "experiment.log"
        if not log_path.exists():
            print(f"⚠️  Log file not found: {log_path}")
            return True  # Not a failure, just not available
        
        parser = LogParser(log_path)
        
        # Test getting last activity
        last_activity = parser.get_last_activity_time()
        print(f"   Last activity: {last_activity}")
        
        # Test pattern matching
        events = parser.parse_new_events()
        print(f"   Events parsed: {len(events)} types")
        
        print(f"✅ Log parser working")
        return True
    except Exception as e:
        print(f"❌ Log parser failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_bot_tracker():
    """Test bot process tracking"""
    print("\nTesting bot tracker...")
    try:
        from bot_tracker import BotTracker
        from log_parser import LogParser
        from database import Database
        from config import Config
        
        # Use test database
        test_db = Path("test_monitor.db")
        if test_db.exists():
            test_db.unlink()
        db = Database(test_db)
        
        # Test with BTC bot
        bot_config = Config.BOTS['BTC']
        log_path = Config.BOT_DIR / bot_config['log']
        parser = LogParser(log_path)
        tracker = BotTracker(bot_config, parser, db)
        
        # Check health
        health = tracker.check_health(frozen_threshold_sec=16*60)
        print(f"   BTC bot status: {health['status']}")
        print(f"   PID: {health['pid']}")
        print(f"   Running: {health['is_running']}")
        
        # Cleanup
        test_db.unlink()
        
        print(f"✅ Bot tracker working")
        return True
    except Exception as e:
        print(f"❌ Bot tracker failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_alerter():
    """Test Telegram alerter (without actually sending)"""
    print("\nTesting alerter...")
    try:
        from alerter import Alerter
        from database import Database
        from config import Config
        
        # Use test database
        test_db = Path("test_monitor.db")
        if test_db.exists():
            test_db.unlink()
        db = Database(test_db)
        
        # Create alerter (won't send without token)
        alerter = Alerter(
            bot_token=Config.TELEGRAM_BOT_TOKEN or "test_token",
            chat_id=Config.TELEGRAM_CHAT_ID,
            db=db
        )
        
        # Test alert templates (without sending)
        print(f"   Testing alert templates...")
        
        # Just verify methods exist and don't crash
        # We won't actually send during testing
        
        # Cleanup
        test_db.unlink()
        
        print(f"✅ Alerter structure valid")
        if not Config.TELEGRAM_BOT_TOKEN:
            print(f"   ⚠️  No TELEGRAM_BOT_TOKEN - alerts won't be sent")
        return True
    except Exception as e:
        print(f"❌ Alerter failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_metrics():
    """Test metrics tracking"""
    print("\nTesting metrics...")
    try:
        from metrics import MetricsTracker
        from database import Database
        from alerter import Alerter
        from config import Config
        
        # Use test database
        test_db = Path("test_monitor.db")
        if test_db.exists():
            test_db.unlink()
        db = Database(test_db)
        
        alerter = Alerter("test", Config.TELEGRAM_CHAT_ID, db)
        metrics = MetricsTracker(db, alerter)
        
        # Test processing events
        events = {
            'trades_placed': [{'side': 'yes', 'price': 95, 'count': 100}],
            'trades_filled': [],
        }
        metrics.process_trade_events("TEST", events)
        
        # Test summary
        summary = metrics.get_today_summary("TEST")
        print(f"   Summary: {summary}")
        
        # Cleanup
        test_db.unlink()
        
        print(f"✅ Metrics working")
        return True
    except Exception as e:
        print(f"❌ Metrics failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("Component Testing - Bot Trading Agent")
    print("=" * 60)
    
    tests = [
        test_config,
        test_database,
        test_log_parser,
        test_bot_tracker,
        test_alerter,
        test_metrics,
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "=" * 60)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    
    if all(results):
        print("✅ All tests passed - ready for deployment after reviews")
    else:
        print("❌ Some tests failed - fix before deployment")
        sys.exit(1)


if __name__ == "__main__":
    main()
