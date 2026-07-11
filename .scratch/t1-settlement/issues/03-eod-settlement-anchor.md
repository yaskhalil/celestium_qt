Status: completed

## What to build

Update the End of Day (EOD) process to handle T+1 cash settlement conversion.

- `process_eod_anchor` must transition all intraday `unsettled_cash` into `settled_cash` for the next day's session.
- `unsettled_cash` must be reset to zero at EOD.
- Daily session PnL and trade count must be reset, and status reset from `PAUSED_DAILY_LOSS` to `ACTIVE`.

## Acceptance criteria

- [ ] `process_eod_anchor` correctly moves `unsettled_cash` into `settled_cash`.
- [ ] `unsettled_cash` is 0.0 after EOD processing.
- [ ] Unit tests simulate an end-to-end T+1 settlement flow (BUY trade, SELL trade, EOD run, check next day settled cash).

## Blocked by

- [.scratch/t1-settlement/issues/02-update-session-cash-flow.md](file:///Users/yaseenkhalil/celestium_qt/.scratch/t1-settlement/issues/02-update-session-cash-flow.md)
