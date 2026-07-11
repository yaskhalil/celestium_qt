Status: completed

## What to build

Update the session and cash pool tracking logic to properly deduct and allocate cash during active trading.

- Adjust `update_session` to accept trade side, cash flow, and quantity/commissions.
- For BUY orders, decrease `settled_cash` by trade cost + commissions.
- For SELL orders, increase `unsettled_cash` by trade proceeds - commissions.
- Ensure backtest engine and live trading engine pass correct arguments when calling `update_session`.

## Acceptance criteria

- [ ] `update_session` successfully manages settled and unsettled cash pools.
- [ ] Total balance is correctly updated as the sum of settled and unsettled cash.
- [ ] Backtest engine calls `update_session` with appropriate cash flow and quantity details.
- [ ] Execution engines integrate seamlessly without failing.
- [ ] Test cases verify correct balance and cash pool movements after mock BUY and SELL trades.

## Blocked by

- [.scratch/t1-settlement/issues/01-update-account-state-gfv-prevention.md](file:///Users/yaseenkhalil/celestium_qt/.scratch/t1-settlement/issues/01-update-account-state-gfv-prevention.md)
