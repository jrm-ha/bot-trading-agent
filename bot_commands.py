"""
Telegram bot command handler for status checks.
Responds to /bal, /balance, /status commands.
"""

import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from config import Config
from database import Database

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class BotCommandHandler:
    """Handle Telegram commands for bot status"""
    
    def __init__(self, token: str, db: Database):
        self.token = token
        self.db = db
        self.app = Application.builder().token(token).build()
        
        # Register command handlers
        self.app.add_handler(CommandHandler("bal", self.balance_command))
        self.app.add_handler(CommandHandler("balance", self.balance_command))
        self.app.add_handler(CommandHandler("status", self.status_command))
        self.app.add_handler(CommandHandler("health", self.health_command))
    
    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /bal and /balance commands"""
        # Get today's profit/loss per bot
        today = datetime.now().date()
        
        message_lines = ["💰 **Kalshi Bot Balance**\n"]
        
        total_profit = 0
        for bot_name in ["BTC", "ETH", "SOL"]:
            # Get daily metrics
            daily = self.db.get_daily_metrics(bot_name, today.isoformat())
            
            if daily:
                wins = daily.get('wins', 0)
                losses = daily.get('losses', 0)
                profit = daily.get('total_profit', 0)
                trades = daily.get('trade_count', 0)
                
                total_profit += profit
                
                # Format
                profit_str = f"+${profit:.2f}" if profit >= 0 else f"-${abs(profit):.2f}"
                emoji = "🟢" if profit >= 0 else "🔴"
                
                message_lines.append(
                    f"{emoji} **{bot_name}**: {profit_str} ({wins}W-{losses}L, {trades} trades)"
                )
            else:
                message_lines.append(f"⚪️ **{bot_name}**: No trades today")
        
        # Total
        total_str = f"+${total_profit:.2f}" if total_profit >= 0 else f"-${abs(total_profit):.2f}"
        message_lines.append(f"\n**Total Today**: {total_str}")
        
        # Bot health
        message_lines.append("\n📊 **Bot Health:**")
        for bot_name in ["BTC", "ETH", "SOL"]:
            health = self.db.get_latest_health(bot_name)
            if health:
                status = health.get('status', 'unknown')
                is_running = health.get('is_running', False)
                
                if status == "healthy":
                    emoji = "✅"
                elif status == "frozen":
                    emoji = "⚠️"
                elif status == "crashed":
                    emoji = "❌"
                else:
                    emoji = "❓"
                
                message_lines.append(f"{emoji} {bot_name}: {status}")
        
        await update.message.reply_text("\n".join(message_lines), parse_mode="Markdown")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command - detailed bot status"""
        message_lines = ["📈 **Bot Status Report**\n"]
        
        for bot_name in ["BTC", "ETH", "SOL"]:
            health = self.db.get_latest_health(bot_name)
            
            if health:
                status = health.get('status', 'unknown')
                is_running = health.get('is_running', False)
                pid = health.get('pid')
                last_activity = health.get('last_activity')
                
                # Status emoji
                if status == "healthy":
                    emoji = "✅"
                elif status == "frozen":
                    emoji = "⚠️"
                elif status == "crashed":
                    emoji = "❌"
                else:
                    emoji = "❓"
                
                message_lines.append(f"{emoji} **{bot_name}**")
                message_lines.append(f"  Status: {status}")
                message_lines.append(f"  Running: {'Yes' if is_running else 'No'}")
                if pid:
                    message_lines.append(f"  PID: {pid}")
                
                if last_activity:
                    try:
                        last_time = datetime.fromisoformat(last_activity)
                        idle_min = int((datetime.now() - last_time).total_seconds() / 60)
                        message_lines.append(f"  Last Activity: {idle_min}m ago")
                    except:
                        pass
                
                message_lines.append("")
        
        # Recent errors
        errors = self.db.get_recent_errors(hours=1)
        if errors:
            message_lines.append(f"⚠️ **Recent Errors ({len(errors)}):**")
            for err in errors[:3]:  # Show max 3
                bot = err.get('bot_name', '?')
                error_type = err.get('error_type', 'unknown')
                message_lines.append(f"  • {bot}: {error_type}")
        
        await update.message.reply_text("\n".join(message_lines), parse_mode="Markdown")
    
    async def health_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /health command - just quick health check"""
        healthy = 0
        crashed = 0
        frozen = 0
        
        for bot_name in ["BTC", "ETH", "SOL"]:
            health = self.db.get_latest_health(bot_name)
            if health:
                status = health.get('status', 'unknown')
                if status == "healthy":
                    healthy += 1
                elif status == "crashed":
                    crashed += 1
                elif status == "frozen":
                    frozen += 1
        
        if crashed > 0:
            emoji = "❌"
            message = f"**Critical:** {crashed} bot(s) crashed"
        elif frozen > 0:
            emoji = "⚠️"
            message = f"**Warning:** {frozen} bot(s) frozen"
        elif healthy == 3:
            emoji = "✅"
            message = "**All systems operational**"
        else:
            emoji = "❓"
            message = "**Status unknown**"
        
        await update.message.reply_text(f"{emoji} {message}")
    
    def run(self):
        """Start the command handler (blocking)"""
        logger.info("Starting Telegram command handler...")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)


def main():
    """Entry point"""
    db = Database(Config.DB_PATH)
    handler = BotCommandHandler(Config.TELEGRAM_BOT_TOKEN, db)
    handler.run()


if __name__ == "__main__":
    main()
