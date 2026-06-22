import asyncio
import os
import json
import httpx
import structlog
from typing import Any
from src.config import settings
from src.core.oracle import AccountStatus
from src.core.notifier import TelegramNotifier

logger = structlog.get_logger()

class TelegramBot:
    """
    Adapter module for handling Telegram command updates.
    Decoupled from core execution engine to improve locality and testability.
    """
    def __init__(self, engine: Any):
        self.engine = engine
        self.notifier = TelegramNotifier()
        self.running = False
        self.task = None

    def start(self):
        """Starts the background polling task."""
        if not settings.TELEGRAM_ENABLED or not settings.TELEGRAM_BOT_TOKEN:
            logger.info("Telegram Bot: Disabled or token missing")
            return
        self.running = True
        self.task = asyncio.create_task(self.poll_updates())
        logger.info("Telegram Bot: Polling task started")

    async def stop(self):
        """Stops the background polling task."""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            logger.info("Telegram Bot: Polling task stopped")

    async def poll_updates(self):
        """Polls Telegram for command updates."""
        token = settings.TELEGRAM_BOT_TOKEN
        chat_id = str(settings.TELEGRAM_CHAT_ID)
        base_url = f"https://api.telegram.org/bot{token}"
        offset = 0
        
        # Clear old updates on start
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(f"{base_url}/getUpdates", params={"offset": -1, "timeout": 1})
                if res.status_code == 200:
                    data = res.json()
                    if data.get("ok") and data.get("result"):
                        offset = data["result"][-1]["update_id"] + 1
        except Exception as e:
            logger.error("Telegram Bot: Failed to clear initial updates", error=str(e))

        while self.running:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{base_url}/getUpdates",
                        params={"offset": offset, "timeout": 10},
                        timeout=15.0
                    )
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("ok") and data.get("result"):
                            for update in data["result"]:
                                offset = update["update_id"] + 1
                                message = update.get("message")
                                if not message:
                                    continue
                                
                                msg_chat_id = str(message.get("chat", {}).get("id", ""))
                                if chat_id and msg_chat_id != chat_id:
                                    continue
                                    
                                text = message.get("text", "").strip()
                                if text.startswith("/"):
                                    await self.process_telegram_command(text)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Telegram Bot: Polling error", error=str(e))
                await asyncio.sleep(5)
            await asyncio.sleep(1)

    async def process_telegram_command(self, command: str):
        """Processes Telegram commands."""
        parts = command.split()
        if not parts:
            return
        cmd = parts[0].lower().split('@')[0]
        
        if cmd == "/help":
            help_msg = (
                "🤖 *CelestiumQT Commands:*\n"
                "━━━━━━━━━━━━━━━\n"
                "• `/status` - Current balance, daily PNL, position, and system status\n"
                "• `/pause` - Manually pause Oracle trading\n"
                "• `/resume` - Manually resume Oracle trading\n"
                "• `/positions` - View current open positions\n"
                "• `/vetoes` - View Oracle veto logs for today\n"
                "• `/performance` - View model & trading performance statistics\n"
                "• `/shadow [on/off]` - Toggle or set Shadow Mode execution\n"
                "• `/backtest` - Run 1-year historical simulation\n"
                "• `/help` - Show this help menu"
            )
            await self.notifier.notify(help_msg)
            
        elif cmd == "/shadow":
            args = parts[1:]
            current_shadow = settings.SHADOW_MODE
            
            if args:
                target = args[0].lower()
                if target in ["on", "true", "1"]:
                    new_shadow = True
                elif target in ["off", "false", "0"]:
                    new_shadow = False
                else:
                    await self.notifier.notify("⚠️ Invalid argument. Use `/shadow on` or `/shadow off`.")
                    return
            else:
                new_shadow = not current_shadow
                
            settings.SHADOW_MODE = new_shadow
            
            config_path = "deployment_config.json"
            config_data = {}
            if os.path.exists(config_path):
                try:
                    with open(config_path, "r") as f:
                        config_data = json.load(f)
                except Exception as e:
                    logger.error("Telegram Bot: Failed to load config to save", error=str(e))
            
            config_data["shadow_mode"] = new_shadow
            
            try:
                with open(config_path, "w") as f:
                    json.dump(config_data, f, indent=4)
            except Exception as e:
                logger.error("Telegram Bot: Failed to save config to disk", error=str(e))
                
            state_str = "🟡 SHADOW MODE (Simulated)" if new_shadow else "🟢 LIVE TRADING (Alpaca)"
            await self.notifier.notify(f"🔄 *EXECUTION MODE UPDATED*\nSystem is now in `{state_str}`.")
            logger.info("Telegram Bot: Shadow mode updated", shadow_mode=new_shadow)
            
        elif cmd == "/backtest":
            await self.notifier.notify("⏳ *STARTING BACKTEST* - Loading S&P 500 data and running 1-year historical simulation...")
            asyncio.create_task(self.run_telegram_backtest())
            
        elif cmd == "/performance":
            backtest_data = {}
            if os.path.exists("data/backtest_report.json"):
                try:
                    with open("data/backtest_report.json", "r") as f:
                        backtest_data = json.load(f)
                except Exception as e:
                    logger.error("Telegram Bot: Failed to load backtest report", error=str(e))

            history = self.engine.account_state.trading_history
            total_sessions = len(history)
            net_pnl = sum(s.pnl for s in history)
            win_days = len([s for s in history if s.pnl > 0])
            loss_days = len([s for s in history if s.pnl < 0])
            avg_pnl = net_pnl / total_sessions if total_sessions > 0 else 0.0
            win_rate_days = (win_days / total_sessions * 100.0) if total_sessions > 0 else 0.0
            
            model_size_mb = 0.0
            model_path = getattr(self.engine.classifier, 'model_path', 'models/alpha_v1.ubj')
            if os.path.exists(model_path):
                model_size_mb = os.path.getsize(model_path) / (1024 * 1024)

            msg = (
                f"📊 *MODEL & TRADING PERFORMANCE*\n"
                f"━━━━━━━━━━━━━━━\n"
                f"🧠 *Model Architecture:*\n"
                f"• *Model File:* `{os.path.basename(model_path)}`\n"
                f"• *Size:* `{model_size_mb:.2f} MB`\n"
                f"• *Classifier:* `XGBoost (Layer 2)`\n"
                f"• *Signal Threshold:* `{settings.SIGNAL_THRESHOLD}`\n"
                f"━━━━━━━━━━━━━━━\n"
            )
            
            if backtest_data:
                bt_win_rate = backtest_data.get("Win Rate", 0.0) * 100.0
                msg += (
                    f"🔬 *Historical Backtest (1-Year SPY):*\n"
                    f"• *Total Trades:* `{backtest_data.get('Total Trades', 0)}`\n"
                    f"• *Model Win Rate:* `{bt_win_rate:.1f}%`\n"
                    f"• *Net Profit:* `${backtest_data.get('Total Net Profit', 0.0):.2f}`\n"
                    f"• *Max Drawdown:* `${backtest_data.get('Max Drawdown', 0.0):.2f}`\n"
                    f"• *Recovery Factor:* `{backtest_data.get('Recovery Factor', 0.0):.2f}`\n"
                    f"• *Consistency Score:* `{backtest_data.get('Consistency Score', 0.0):.3f}`\n"
                    f"━━━━━━━━━━━━━━━\n"
                )
            else:
                msg += "🔬 *Historical Backtest:* `No backtest report found` (Run backtest script to generate)\n━━━━━━━━━━━━━━━\n"
                
            msg += (
                f"🟢 *Live Session Performance:*\n"
                f"• *Total Trading Days:* `{total_sessions}`\n"
                f"• *Net PNL:* `${net_pnl:.2f}`\n"
                f"• *Win Days:* `{win_days}` ({win_rate_days:.1f}%)\n"
                f"• *Loss Days:* `{loss_days}`\n"
                f"• *Avg Daily PNL:* `${avg_pnl:.2f}`"
            )
            await self.notifier.notify(msg)
            
        elif cmd == "/status":
            await self.engine.router._verify_position(self.engine.current_symbol)
            pos = self.engine.router.current_position
            mode = "SHADOW MODE" if settings.SHADOW_MODE else "LIVE TRADING"
            status_emoji = "🟢" if self.engine.account_state.status == AccountStatus.ACTIVE else "🔴"
            
            status_msg = (
                f"📊 *SYSTEM STATUS*\n"
                f"━━━━━━━━━━━━━━━\n"
                f"*Status:* `{self.engine.account_state.status.value.upper()}` {status_emoji}\n"
                f"*Execution Mode:* `{mode}`\n"
                f"*Balance:* `${self.engine.account_state.balance:.2f}`\n"
                f"*Equity:* `${self.engine.account_state.equity:.2f}`\n"
                f"*Daily PNL:* `${self.engine.account_state.current_daily_pnl:.2f}`\n"
                f"*Open Position:* `{pos}` shares\n"
                f"*Target Symbol:* `{self.engine.current_symbol}`\n"
                f"━━━━━━━━━━━━━━━\n"
                f"*Settled Cash:* `${self.engine.account_state.settled_cash:.2f}`\n"
                f"*Unsettled Cash:* `${self.engine.account_state.unsettled_cash:.2f}`\n"
                f"*Oracle Vetos Today:* `{len(self.engine.veto_logs)}`"
            )
            await self.notifier.notify(status_msg)
            
        elif cmd == "/pause":
            if self.engine.account_state.status == AccountStatus.ACTIVE:
                self.engine.account_state.status = AccountStatus.PAUSED
                self.engine.account_state.save()
                await self.notifier.notify("⏸ *SYSTEM PAUSED* - Oracle has been manually paused. New signals will be vetoed.")
                logger.info("Telegram Bot: System manually paused")
            else:
                await self.notifier.notify(f"⚠️ Bot is already in `{self.engine.account_state.status.value}` state.")
                
        elif cmd == "/resume":
            if self.engine.account_state.status == AccountStatus.PAUSED:
                self.engine.account_state.status = AccountStatus.ACTIVE
                self.engine.account_state.save()
                await self.notifier.notify("▶️ *SYSTEM RESUMED* - Oracle is now active and monitoring signals.")
                logger.info("Telegram Bot: System manually resumed")
            else:
                await self.notifier.notify(f"⚠️ Cannot resume from state `{self.engine.account_state.status.value}`. Only manually paused bots can be resumed.")
                
        elif cmd == "/positions":
            await self.engine.router._verify_position(self.engine.current_symbol)
            pos = self.engine.router.current_position
            if pos == 0:
                await self.notifier.notify("📦 *POSITIONS*\nNo active positions.")
            else:
                side = "LONG" if pos > 0 else "SHORT"
                pos_msg = (
                    f"📦 *OPEN POSITION*\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"*Symbol:* `{self.engine.current_symbol}`\n"
                    f"*Direction:* `{side}`\n"
                    f"*Size:* `{abs(pos)}` shares\n"
                    f"*Entry Price:* `${self.engine.router.entry_price:.2f}`\n"
                    f"*Stop Loss:* `${self.engine.router.stop_loss:.2f}`\n"
                    f"*Take Profit:* `${self.engine.router.take_profit:.2f}`"
                )
                await self.notifier.notify(pos_msg)
                
        elif cmd == "/vetoes":
            if not self.engine.veto_logs:
                await self.notifier.notify("🛡 *ORACLE VETOES*\nNo vetoes recorded today.")
            else:
                veto_list = "\n".join([f"• {log}" for log in self.engine.veto_logs])
                await self.notifier.notify(f"🛡 *ORACLE VETOES TODAY*\n━━━━━━━━━━━━━━━\n{veto_list}")
                
        else:
            await self.notifier.notify("❓ Unknown command. Type `/help` for available commands.")

    async def run_telegram_backtest(self):
        """Runs historical backtest and reports results."""
        try:
            import polars as pl
            from src.core.backtest_engine import BacktestEngine
            from src.features.regime import add_regime_features
            
            data_path = f"data/processed/databento_{settings.SYMBOL.lower()}.parquet"
            if not os.path.exists(data_path):
                await self.notifier.notify(f"📥 *Parquet Data Not Found:* Automatically launching Databento historical data ingestion for {settings.SYMBOL} (365 days)...")
                from scripts.ingest_databento import ingest_historical_data
                await asyncio.to_thread(ingest_historical_data, 365)
                
                if not os.path.exists(data_path):
                    await self.notifier.notify("❌ *Ingestion Failed:* Parquet data file could not be created. Please check your DATABENTO_API_KEY.")
                    return
                else:
                    await self.notifier.notify("✅ *Ingestion/Resampling Successful:* Proceeding with the backtest...")
                
            def _execute():
                df = pl.read_parquet(data_path)
                if "atr" not in df.columns:
                    df = add_regime_features(df)
                
                old_thresh = settings.SIGNAL_THRESHOLD
                settings.SIGNAL_THRESHOLD = 0.5
                try:
                    engine = BacktestEngine()
                    report = engine.run(df)
                    return report
                finally:
                    settings.SIGNAL_THRESHOLD = old_thresh
                    
            report = await asyncio.to_thread(_execute)
            
            win_rate = report.get("Win Rate", 0.0) * 100.0
            msg = (
                f"🔬 *HISTORICAL BACKTEST RESULTS*\n"
                f"━━━━━━━━━━━━━━━\n"
                f"• *Target Symbol:* `{settings.SYMBOL}`\n"
                f"• *Total Trades:* `{report.get('Total Trades', 0)}`\n"
                f"• *Model Win Rate:* `{win_rate:.1f}%`\n"
                f"• *Net Profit:* `${report.get('Total Net Profit', 0.0):.2f}`\n"
                f"• *Max Drawdown:* `${report.get('Max Drawdown', 0.0):.2f}`\n"
                f"• *Recovery Factor:* `{report.get('Recovery Factor', 0.0):.2f}`\n"
                f"• *Consistency Score:* `{report.get('Consistency Score', 0.0):.3f}`\n"
                f"• *Qualifying Days:* `{report.get('Qualifying Day Count', 0)}`"
            )
            await self.notifier.notify(msg)
        except Exception as e:
            logger.error("Telegram Bot: Backtest run failed", error=str(e))
            await self.notifier.notify(f"❌ *Backtest Failed:* {str(e)}")
