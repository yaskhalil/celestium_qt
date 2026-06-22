import json
import random
import numpy as np
import structlog
import os
from src.config import settings

logger = structlog.get_logger()

def run_stress_test(num_simulations: int = 1000, initial_balance: float = None):
    if initial_balance is None:
        initial_balance = settings.STARTING_BALANCE
    """
    Monte Carlo Simulation for Sequence-of-Returns Risk.
    Shuffles trades to see how often the $26,100 floor is breached.
    """
    trades_path = "data/trades.json"
    
    if not os.path.exists(trades_path):
        logger.error("Trades data not found. Run backtest first.", path=trades_path)
        return

    # 1. Load Trades
    with open(trades_path, "r") as f:
        trades = json.load(f)
        
    pnls = [t["pnl"] for t in trades]
    
    if not pnls:
        logger.warning("No trades found to shuffle.")
        return

    logger.info("Starting Monte Carlo Stress Test", n=num_simulations, trades=len(pnls))
    
    survivals = 0
    final_balances = []
    max_drawdowns = []
    
    # Floor is 26,100 (Apex Safety Net)
    SAFETY_NET_FLOOR = settings.BALANCE_FLOOR
    
    for i in range(num_simulations):
        # 2. Shuffle trades to create a new return path
        shuffled_pnls = random.sample(pnls, len(pnls))
        
        balance = initial_balance
        peak = balance
        survived = True
        mdd = 0.0
        
        # 3. Simulate equity curve for this path
        for pnl in shuffled_pnls:
            balance += pnl
            
            # Check for liquidation
            if balance <= SAFETY_NET_FLOOR:
                survived = False
                # We stop the simulation for this path as the account is blown
                break
                
            # Track peak and drawdown
            if balance > peak:
                peak = balance
            dd = peak - balance
            if dd > mdd:
                mdd = dd
        
        if survived:
            survivals += 1
            final_balances.append(balance)
        else:
            final_balances.append(SAFETY_NET_FLOOR) # Blown account
            
        max_drawdowns.append(mdd)

    # 4. Generate Results Summary
    survival_rate = survivals / num_simulations
    avg_final_balance = np.mean(final_balances)
    percentile_5 = np.percentile(final_balances, 5) # 5% VaR equivalent
    worst_drawdown = max(max_drawdowns)

    results = {
        "Survival Rate (%)": survival_rate * 100,
        "Average Final Balance": round(avg_final_balance, 2),
        "Worst-Case Final Balance (5th Percentile)": round(percentile_5, 2),
        "Max Drawdown (Any Path)": round(worst_drawdown, 2),
        "Black Swan Breach Count": num_simulations - survivals
    }
    
    # 5. Save and Print Results
    results_path = "data/stress_test_report.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=4)
        
    logger.info("Stress Test Complete", survival_rate=results["Survival Rate (%)"])
    print("\n--- SYNTHETIC STRESS TEST (MONTE CARLO) ---")
    print(f"Total Simulations: {num_simulations}")
    for k, v in results.items():
        print(f"{k}: {v}")
        
    if survival_rate < 0.95:
        print("\nCRITICAL WARNING: Survival rate below 95%. Consider reducing position size in allocator.py.")
    else:
        print("\nPASS: Survival rate >= 95%. Risk parameters within tolerance.")

if __name__ == "__main__":
    run_stress_test()
