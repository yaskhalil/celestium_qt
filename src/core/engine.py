import structlog
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import asyncio

import httpx
import json
import os
from src.config import settings
from src.data.pipeline import DuckDBBuffer
from src.core.oracle import Oracle, AccountState, AccountStatus
from src.core.boolean_network import BooleanStateSpace
from src.execution.router import AlpacaRouter
from src.models.classifier import Classifier
from src.core.allocator import Allocator
from src.core.advisor import Advisor

from src.data.ingestion import AlpacaIngestor
from src.execution.alpaca_client import AlpacaClient
from src.core.notifier import TelegramNotifier

logger = structlog.get_logger()

class ScheduledEngine:
    """
    Scheduled Engine: Dual-loop execution for safety and precision.
    Monitor (1m): Exits and position tracking.
    Signal (5m): Heavy model inference and entries.
    """

    def __init__(self, alpaca_client: AlpacaClient, account_state: Optional[AccountState] = None):
        self.account_state = account_state or AccountState.load()
        self.alpaca_client = alpaca_client
        self.buffer = DuckDBBuffer()
        self.bn = BooleanStateSpace()
        self.oracle = Oracle(self.account_state)
        self.allocator = Allocator()
        self.classifier = Classifier()
        
        self.router = AlpacaRouter(alpaca_client, self.account_state)
        self.ingestor = AlpacaIngestor(client=alpaca_client)
        self.advisor = Advisor()
        self.notifier = TelegramNotifier()
        
        self.scheduler = AsyncIOScheduler()
        self.running = False
        self.veto_logs = []
        self.telegram_listener_task = None
        
        # Live Trade Monitoring
        self.current_symbol = settings.SYMBOL
        self.context_symbol = settings.CONTEXT_SYMBOL
        self.stop_loss = 0.0
        self.take_profit = 0.0
        self.entry_price = 0.0

    async def tick_monitor(self):
        """Fast tick: Triggered every minute to monitor and exit positions."""
        symbol = self.current_symbol
        current_price = None
        
        # 0. Ingest latest data (Required for exit price check and context)
        try:
            await self.ingestor.fetch_and_persist(symbol, lookback_minutes=15)
            await self.ingestor.fetch_and_persist(self.context_symbol, lookback_minutes=15)
        except Exception as e:
            logger.error("Engine: Ingestion failed", error=str(e))

        # Check buffer for price
        context = self.buffer.get_context(symbol, window=5)
        if not context.is_empty():
            last_bar = context.tail(1).to_dicts()[0]
            current_price = last_bar["close"]

        # Fallback to Alpaca for real-time price monitoring if ingestion failed or was empty
        if current_price is None:
            logger.info("Engine: Fetching real-time price from Alpaca", symbol=symbol)
            current_price = await self.alpaca_client.get_last_price(symbol)
            
        if current_price is None:
            logger.error("Engine: Could not obtain current price for monitoring", symbol=symbol)
            return

        try:
            # Position Management (Exits)
            await self.router._verify_position(symbol)
            if self.router.current_position != 0:
                # Use current_price for monitoring logic
                if current_price <= self.stop_loss:
                    logger.warning("Engine: STOP LOSS HIT", price=self.stop_loss, current=current_price)
                    await self.router.execute_trade(symbol, abs(self.router.current_position), "SELL", price=current_price)
                    self.oracle.update_session(pnl=(current_price - self.entry_price) * self.router.current_position, 
                                               cash_flow=abs(self.router.current_position) * current_price,
                                               quantity=abs(self.router.current_position), side="SELL")
                elif current_price >= self.take_profit:
                    logger.info("Engine: TAKE PROFIT HIT", price=self.take_profit, current=current_price)
                    await self.router.execute_trade(symbol, abs(self.router.current_position), "SELL", price=current_price)
                    self.oracle.update_session(pnl=(current_price - self.entry_price) * self.router.current_position,
                                               cash_flow=abs(self.router.current_position) * current_price,
                                               quantity=abs(self.router.current_position), side="SELL")
        except Exception as e:
            logger.error("Engine: Monitor tick failed", error=str(e))

    async def tick_signal(self):
        """Slow tick: Triggered every 5 minutes to generate new trade signals."""
        logger.info("Engine: Signal check triggered (5m interval)")
        symbol = self.current_symbol

        # 1. Fetch context (Requires 111+ bars for model)
        # We also need the context symbol (QQQ) for the BooleanStateSpace
        try:
            context = self.buffer.get_context(symbol, window=150)
            context_market = self.buffer.get_context(self.context_symbol, window=150)
        except Exception as e:
            logger.error("Engine: Failed to fetch context", error=str(e))
            return

        if context.is_empty() or len(context) < 111 or context_market.is_empty():
            logger.warning("Engine: Insufficient data context. Attempting Alpaca historical backfill.", 
                           symbol_len=len(context), context_len=len(context_market))
            try:
                await self.ingestor.fetch_and_persist(symbol, lookback_minutes=200)
                await self.ingestor.fetch_and_persist(self.context_symbol, lookback_minutes=200)
                context = self.buffer.get_context(symbol, window=150)
                context_market = self.buffer.get_context(self.context_symbol, window=150)
            except Exception as e:
                logger.error("Engine: Alpaca backfill failed", error=str(e))

        if context.is_empty() or len(context) < 111:
            logger.warning("Engine: Still insufficient data context after backfill")
            return
            
        # Don't enter new trades if already in one
        await self.router._verify_position(symbol)
        if self.router.current_position != 0:
            logger.debug("Engine: Existing position active, skipping signal generation")
            return

        # 2. Map context to Boolean state bits
        # Note: We pass both to map_to_bits if it's designed to use market context
        state = self.bn.map_to_bits(context, context_market)
        
        # 3. Check if state is in an attractor
        if not self.bn.is_in_attractor(state):
            logger.info("Engine: State not in attractor, skipping", state=state)
            return

        # 4. Proceed with Layer 2 (Classifier)
        signal_prob = self.classifier.predict(context)
        
        if signal_prob > settings.SIGNAL_THRESHOLD:
            # 5. Allocator
            last_bar = context.tail(1).to_dicts()[0]
            decision_price = last_bar["close"]
            atr = last_bar["atr"] if "atr" in last_bar else 1.0
            
            # Fetch VIXY (ProShares VIX ETF) to use as circuit breaker volatility proxy
            vix_price = await self.alpaca_client.get_last_price("VIXY") or 15.0
            
            size = self.allocator.calculate_size(
                probability=signal_prob, 
                atr=atr, 
                balance=self.account_state.balance, 
                current_price=decision_price,
                daily_pnl=self.account_state.current_daily_pnl
            )
            
            if size > 0:
                # 6. Oracle validation
                decision_price = last_bar["close"]
                if self.oracle.validate_trade(size, decision_price, "BUY", 
                                             current_hurst=context["hurst"].tail(1).item() if "hurst" in context.columns else 0.5,
                                             current_vix=vix_price):
                    logger.info("Engine: SIGNAL APPROVED. Executing trade.", 
                                size=size, price=decision_price)
                    # Calculate targets (ATR-based)
                    self.entry_price = decision_price
                    self.take_profit = decision_price + (atr * settings.PT_MULTIPLIER)
                    self.stop_loss = decision_price - (atr * settings.SL_MULTIPLIER)

                    await self.router.execute_trade(symbol, size, "BUY", price=decision_price, tp=self.take_profit, sl=self.stop_loss)
                    self.oracle.update_session(cash_flow=size * decision_price, quantity=size, side="BUY")
                else:
                    self.veto_logs.append(f"Oracle vetoed: prob {signal_prob}")
                    logger.info("Engine: Signal vetoed by Oracle")
        else:
            logger.debug("Engine: Signal below threshold", prob=signal_prob)

    def start(self):
        """Starts the scheduler with dual-loop configuration."""
        logger.info("Engine: Starting scheduler")
        self.running = True
        asyncio.create_task(self.notifier.notify_startup(self.account_state.balance, settings.SHADOW_MODE))
        
        # Start Telegram Command Listener loop in background
        self.telegram_listener_task = asyncio.create_task(self.poll_telegram_updates())
        
        # 1. Fast Monitor Loop (Every 1 minute)
        self.scheduler.add_job(
            self.tick_monitor, 
            CronTrigger(day_of_week='mon-fri', hour='9-15', minute='*', timezone='America/New_York'),
            id='monitor_tick'
        )
        
        # 2. Slow Signal Loop (Every 5 minutes)
        self.scheduler.add_job(
            self.tick_signal,
            CronTrigger(day_of_week='mon-fri', hour='9-15', minute='0,5,10,15,20,25,30,35,40,45,50,55', timezone='America/New_York'),
            id='signal_tick'
        )
        
        # 3. EOD Flatten (3:55 PM ET)
        self.scheduler.add_job(
            self.tick_monitor,
            CronTrigger(day_of_week='mon-fri', hour='15', minute='55', timezone='America/New_York'),
            id='market_tick_eod'
        )
        
        # 4. EOD Telegram Recap (4:05 PM ET)
        self.scheduler.add_job(
            self.trigger_eod_recap,
            CronTrigger(day_of_week='mon-fri', hour='16', minute='5', timezone='America/New_York'),
            id='market_tick_recap'
        )
        
        # 5. DB Vacuum (Saturday Midnight)
        self.scheduler.add_job(
            self.buffer.storage.vacuum,
            CronTrigger(day_of_week='sat', hour='0', minute='0', timezone='America/New_York'),
            id='db_vacuum'
        )
        
        self.scheduler.start()

    async def stop(self):
        """Stops the scheduler and generates summary."""
        logger.info("Engine: Stopping scheduler")
        self.running = False
        
        # Cancel Telegram Command Listener loop
        if self.telegram_listener_task:
            self.telegram_listener_task.cancel()
            try:
                await self.telegram_listener_task
            except asyncio.CancelledError:
                pass
        
        await self.notifier.notify_shutdown(self.account_state.balance)
        self.scheduler.shutdown()
        
        await self.advisor.generate_summary(
            self.account_state, 
            self.veto_logs, 
            {} # Final metrics context
        )

    async def poll_telegram_updates(self):
        """Polls Telegram for commands in the background."""
        if not settings.TELEGRAM_ENABLED or not settings.TELEGRAM_BOT_TOKEN:
            return

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
            logger.error("Telegram Listener: Failed to clear initial updates", error=str(e))

        logger.info("Telegram Listener: Started polling updates", offset=offset)

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
                logger.error("Telegram Listener: Polling error", error=str(e))
                await asyncio.sleep(5)
            await asyncio.sleep(1)

    async def process_telegram_command(self, command: str):
        """Processes received Telegram commands."""
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
            # Determine target state
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
                
            # Update settings in memory
            settings.SHADOW_MODE = new_shadow
            
            # Save override to deployment_config.json
            config_path = "deployment_config.json"
            config_data = {}
            if os.path.exists(config_path):
                try:
                    with open(config_path, "r") as f:
                        config_data = json.load(f)
                except Exception as e:
                    logger.error("Telegram shadow: Failed to load config to save", error=str(e))
            
            config_data["shadow_mode"] = new_shadow
            
            try:
                with open(config_path, "w") as f:
                    json.dump(config_data, f, indent=4)
            except Exception as e:
                logger.error("Telegram shadow: Failed to save config to disk", error=str(e))
                
            state_str = "🟡 SHADOW MODE (Simulated)" if new_shadow else "🟢 LIVE TRADING (Alpaca)"
            await self.notifier.notify(f"🔄 *EXECUTION MODE UPDATED*\nSystem is now in `{state_str}`.")
            logger.info("Telegram: Shadow mode updated", shadow_mode=new_shadow)
            
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
                    logger.error("Telegram performance: Failed to load backtest report", error=str(e))

            history = self.account_state.trading_history
            total_sessions = len(history)
            net_pnl = sum(s.pnl for s in history)
            win_days = len([s for s in history if s.pnl > 0])
            loss_days = len([s for s in history if s.pnl < 0])
            avg_pnl = net_pnl / total_sessions if total_sessions > 0 else 0.0
            win_rate_days = (win_days / total_sessions * 100.0) if total_sessions > 0 else 0.0
            
            model_size_mb = 0.0
            model_path = getattr(self.classifier, 'model_path', 'models/alpha_v1.ubj')
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
            await self.router._verify_position(self.current_symbol)
            pos = self.router.current_position
            mode = "SHADOW MODE" if settings.SHADOW_MODE else "LIVE TRADING"
            status_emoji = "🟢" if self.account_state.status == AccountStatus.ACTIVE else "🔴"
            
            status_msg = (
                f"📊 *SYSTEM STATUS*\n"
                f"━━━━━━━━━━━━━━━\n"
                f"*Status:* `{self.account_state.status.value.upper()}` {status_emoji}\n"
                f"*Execution Mode:* `{mode}`\n"
                f"*Balance:* `${self.account_state.balance:.2f}`\n"
                f"*Equity:* `${self.account_state.equity:.2f}`\n"
                f"*Daily PNL:* `${self.account_state.current_daily_pnl:.2f}`\n"
                f"*Open Position:* `{pos}` shares\n"
                f"*Target Symbol:* `{self.current_symbol}`\n"
                f"━━━━━━━━━━━━━━━\n"
                f"*Settled Cash:* `${self.account_state.settled_cash:.2f}`\n"
                f"*Unsettled Cash:* `${self.account_state.unsettled_cash:.2f}`\n"
                f"*Oracle Vetos Today:* `{len(self.veto_logs)}`"
            )
            await self.notifier.notify(status_msg)
            
        elif cmd == "/pause":
            if self.account_state.status == AccountStatus.ACTIVE:
                self.account_state.status = AccountStatus.PAUSED
                self.account_state.save()
                await self.notifier.notify("⏸ *SYSTEM PAUSED* - Oracle has been manually paused. New signals will be vetoed.")
                logger.info("Telegram: System manually paused")
            else:
                await self.notifier.notify(f"⚠️ Bot is already in `{self.account_state.status.value}` state.")
                
        elif cmd == "/resume":
            if self.account_state.status == AccountStatus.PAUSED:
                self.account_state.status = AccountStatus.ACTIVE
                self.account_state.save()
                await self.notifier.notify("▶️ *SYSTEM RESUMED* - Oracle is now active and monitoring signals.")
                logger.info("Telegram: System manually resumed")
            else:
                await self.notifier.notify(f"⚠️ Cannot resume from state `{self.account_state.status.value}`. Only manually paused bots can be resumed.")
                
        elif cmd == "/positions":
            await self.router._verify_position(self.current_symbol)
            pos = self.router.current_position
            if pos == 0:
                await self.notifier.notify("📦 *POSITIONS*\nNo active positions.")
            else:
                side = "LONG" if pos > 0 else "SHORT"
                pos_msg = (
                    f"📦 *OPEN POSITION*\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"*Symbol:* `{self.current_symbol}`\n"
                    f"*Direction:* `{side}`\n"
                    f"*Size:* `{abs(pos)}` shares\n"
                    f"*Entry Price:* `${self.entry_price:.2f}`\n"
                    f"*Stop Loss:* `${self.stop_loss:.2f}`\n"
                    f"*Take Profit:* `${self.take_profit:.2f}`"
                )
                await self.notifier.notify(pos_msg)
                
        elif cmd == "/vetoes":
            if not self.veto_logs:
                await self.notifier.notify("🛡 *ORACLE VETOES*\nNo vetoes recorded today.")
            else:
                veto_list = "\n".join([f"• {log}" for log in self.veto_logs])
                await self.notifier.notify(f"🛡 *ORACLE VETOES TODAY*\n━━━━━━━━━━━━━━━\n{veto_list}")
                
        else:
            await self.notifier.notify("❓ Unknown command. Type `/help` for available commands.")

    async def run_telegram_backtest(self):
        """Runs the historical backtest in a background thread and reports results."""
        try:
            import polars as pl
            from src.core.backtest_engine import BacktestEngine
            from src.features.regime import add_regime_features
            
            data_path = f"data/processed/databento_{settings.SYMBOL.lower()}.parquet"
            if not os.path.exists(data_path):
                await self.notifier.notify("⚠️ *Backtest Failed:* Historical data parquet not found. Please run historical data ingestion first.")
                return
                
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
            logger.error("Telegram backtest run failed", error=str(e))
            await self.notifier.notify(f"❌ *Backtest Failed:* {str(e)}")

    async def trigger_eod_recap(self):
        """Sends daily PNL recap at close."""
        history = self.account_state.trading_history
        veto_count = len(self.veto_logs)
        payout_cap = self.account_state.liquid_payout_capital
        
        # Clear vetos for next session
        self.veto_logs = []
        
        if not history:
            await self.notifier.notify_daily_recap(0.0, self.account_state.balance, 0, veto_count, payout_cap)
            return
            
        today = history[-1]
        await self.notifier.notify_daily_recap(today.pnl, self.account_state.balance, today.trade_count, veto_count, payout_cap)


if __name__ == "__main__":
    # Scheduler initialization replaced main loop
    from src.execution.alpaca_client import AlpacaClient
    
    async def main():
        # Initialize native AlpacaClient
        alpaca_client = AlpacaClient(
            api_key=settings.ALPACA_API_KEY,
            secret_key=settings.ALPACA_SECRET_KEY,
            base_url=settings.ALPACA_BASE_URL
        )
        
        engine = ScheduledEngine(alpaca_client)
        engine.start()
        
        try:
            while True:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            await engine.stop()

    asyncio.run(main())
