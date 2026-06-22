# Architecture Deepening Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Deepen the interfaces of `ScheduledEngine`, `AlpacaRouter`, and signal/strategy components to maximize **locality** and **leverage**.

---

## Task 1: Decouple Telegram Bot Adapter

### Step 1: Create `TelegramBot` module
- [x] Create `src/core/telegram_bot.py` containing `TelegramBot`.
- [x] Move `poll_telegram_updates` and `process_telegram_command` logic from `ScheduledEngine` to `TelegramBot`.
- [x] Introduce a clear control **Seam** so `TelegramBot` interacts with `ScheduledEngine` via a clean controller interface (e.g. `engine.get_status()`, `engine.pause()`, `engine.resume()`).

### Step 2: Inject Notifier Adapter
- [x] Update `AlpacaRouter` and `Oracle` to accept an injected `TelegramNotifier` instance in their constructors.
- [x] Remove direct class instantiation of `TelegramNotifier` inside those modules.

### Step 3: Update Engine Lifecycle
- [x] Remove all Telegram polling and parsing logic from `ScheduledEngine`.
- [x] Update `src/main.py` to instantiate `TelegramBot` and link it to the engine.

### Step 4: Run tests and verify
- [x] Ensure `tests/test_telegram_commands.py` and `tests/test_engine.py` pass or are updated to reflect the new seam.

---

## Task 2: Deepen Signal Generator (Strategy Interface)

### Step 1: Create `SignalGenerator` module
- [x] Create `src/core/strategy.py`.
- [x] Define `TradeProposal` data class or Pydantic model.
- [x] Define `SignalGenerator` class.

### Step 2: Extract Logic from Engine
- [x] Move Boolean network attractor mapping, classifier predictions, Hurst exponent checks, and size calculations from `ScheduledEngine.tick_signal` into `SignalGenerator.generate_proposal`.

### Step 3: Update Engine Signal Tick
- [x] Simplify `ScheduledEngine.tick_signal` to fetch context, call `SignalGenerator.generate_proposal(context)`, and if a proposal is returned, execute the trade.

---

## Task 3: Deepen Position Manager (Trade Router Interface)

### Step 1: Define `PositionManager` class
- [x] Extend/rename `AlpacaRouter` or create `src/execution/position_manager.py`.
- [x] Encapsulate the active trade tracking (e.g. `entry_price`, `take_profit`, `stop_loss`).
- [x] Move TP/SL checks and monitoring from `ScheduledEngine.tick_monitor` into `PositionManager.update_price(price)`.
- [x] Move compliance hold sleeps, client order placement, and `Oracle.update_session` calls into `PositionManager`.

### Step 2: Simplify Engine Monitor Tick
- [x] Update `ScheduledEngine.tick_monitor` to query the current market price and call `PositionManager.update_price(current_price)`.
- [x] Delete all TP/SL logic, position monitoring, and manual exit order triggers from the engine.
