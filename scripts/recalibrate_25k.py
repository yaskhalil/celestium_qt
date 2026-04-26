import json
import os
import structlog

logger = structlog.get_logger()

def recalibrate_25k():
    """
    Recalibrates CelestiumQT for the Apex 25k OTP Evaluation.
    """
    config_path = "deployment_config.json"
    
    params = {
        "signal_threshold": 0.4,
        "max_position_size": 3,
        "daily_loss_limit": 500.0,
        "daily_profit_cap": 1000.0,
        "balance_floor": 24000.0,
        "tick_value": 2.0,
        "pt_multiplier": 1.0,
        "sl_multiplier": 0.5,
        "shadow_mode": True,
        "symbol": "MNQM6",
        "exchange": "CME"
    }
    
    with open(config_path, "w") as f:
        json.dump(params, f, indent=4)
        
    # Reset existing state to 25k to avoid confusion with previous PA backtests
    state_file = "data/account_state.json"
    if os.path.exists(state_file):
        os.remove(state_file)
        logger.info("Previous account state removed for fresh 25k evaluation.")

    logger.info("Recalibration Complete", target="Apex 25k OTP", floor=params["balance_floor"])
    print("\n--- RECALIBRATION SUCCESSFUL ---")
    print(f"Starting Balance: $25,000")
    print(f"Safety Net Floor: ${params['balance_floor']}")
    print(f"Daily Loss Limit: ${params['daily_loss_limit']}")
    print(f"Daily Profit Cap: ${params['daily_profit_cap']}")
    print("--------------------------------")

if __name__ == "__main__":
    recalibrate_25k()
