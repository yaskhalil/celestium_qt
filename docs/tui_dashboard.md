# CelestiumQT Dashboard (Textual UI Design)

```text
======================================================================
                        CELESTIUM QT TUI
======================================================================
[ SYSTEM STATUS ]
State:       ACTIVE
Shadow Mode: TRUE
Broker:      Alpaca (Cash)

[ TICKERS & DATA ]
Target:      SPLG (Fractional)
Trend:       [ ▄▅▇██▇▅▃  ] (BULLISH)
Chart:       [+] +1.2% (Daily)
DB Size:     274 KB (data/celestium.db)

[ RISK FIREWALL & CASH ]
Balance:         $358.00
Settled Cash:    $358.00 (Available)
Unsettled (T+1): $0.00
Payout Cap:      $0.00
DLL:             -$20.00

[ LAYER 2 MODEL ]
Engine:      XGBoost Classifier
File:        alpha_v1.ubj
Win Rate:    38.50% (Drop!)
[RETRAIN MODEL] <-- ⚠️ SUGGESTED (Win Rate < 40%)

[ ACTIVE TRADE ]
Symbol:      SPLG
Position:    5.20 Shares
Entry:       $60.00
Unrealized:  -$1.20 🔴
Target (TP): $61.50
Stop (SL):   $59.25

[ BACKTEST ENGINE ]
Status:      READY (Last run: 2 days ago)
Period:      Trailing 30 Days
Model:       alpha_v1.ubj (Current) vs alpha_v2_new.ubj
Est. PNL:    +$145.20 (New model beats old by 12%)
[RUN BACKTEST] | [DEPLOY NEW MODEL]

======================================================================
                           LIVE LOGS
======================================================================
23:50:01 [info ] Engine: Signal check triggered (5m interval)
23:50:02 [info ] Classifier: Prediction generated prob=0.42
23:50:02 [veto ] Oracle: VETO - Hurst below threshold (0.38 < 0.42)
23:55:01 [info ] Engine: Signal check triggered (5m interval)
23:55:02 [info ] Classifier: Prediction generated prob=0.76
23:55:02 [info ] Router: SIGNAL APPROVED. Executing trade.

======================================================================
[F] Flatten All  |  [P] Pause Engine  |  [R] Retrain Model  |  [Q] Quit
======================================================================
```
