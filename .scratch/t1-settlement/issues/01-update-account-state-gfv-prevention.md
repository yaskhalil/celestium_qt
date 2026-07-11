Status: completed

## What to build

Update the AccountState data model to support cash account settlement tracking and implement trade validation checks in the Oracle to prevent Good Faith Violations (GFV).

- `settled_cash` and `unsettled_cash` fields must exist on AccountState, defaulting to balance if not specified.
- The Oracle must veto BUY orders if the required trade value exceeds the available `settled_cash`.

## Acceptance criteria

- [ ] AccountState schema updated with `settled_cash` and `unsettled_cash` fields.
- [ ] AccountState models initialize correctly, with settled cash defaulting to the account balance.
- [ ] Oracle's `validate_trade` correctly blocks BUY orders that exceed `settled_cash`.
- [ ] Unit tests added to verify AccountState fields and GFV blocking logic.

## Blocked by

None - can start immediately.
