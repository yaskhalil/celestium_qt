# CelestiumQT Dashboard

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
DuckDB:      Online (Polars Native)

[ RISK FIREWALL ]
Balance:     $358.00 (Settled)
DLL:         -$20.00
Max Trades:  50
Hurst Min:   0.42

[ LAYER 2 MODEL ]
Engine:      XGBoost Classifier
File:        alpha_v1.ubj
Accuracy:    56.25% Win Rate
Profit:      $36.08
Drawdown:    -$2.46
Trades:      32

======================================================================
                         SYSTEM FLOW
======================================================================

         [ MARKET DATA ] 
         (Ingestion/Alpaca)
                 |
                 v
        [ LAYER 1: REGIME ]
       (Hurst, ADX, ATR, DuckDB)
                 |
                 v
        [ LAYER 2: SIGNAL ]
       (XGBoost Classifier)
                 |
                 v
        [ LAYER 3: ORACLE ]
 ----------------------------------
 | - Checks DLL / Profit Ceiling  |
 | - Checks GFV (T+1 Settlement)  |
 | - Checks Hurst Threshold       |
 ----------------------------------
                 |
            (Veto? -> Halt)
                 |
            (Pass? -> Go)
                 v
       [ LAYER 4: EXECUTION ]
        (Alpaca API -> BUY)
                 |
                 v
       [ LAYER 4: ADVISOR ]
        (LLM Session Summary)
======================================================================
```
