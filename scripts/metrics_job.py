import sys
import os
import pandas as pd
import numpy as np

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src import config

def calculate_sharpe_ratio(returns, periods=252):
    """Calculates the annualized Sharpe ratio."""
    if returns.std() == 0:
        return 0
    return np.sqrt(periods) * (returns.mean() / returns.std())

def calculate_psi(expected, actual, buckets=10):
    """
    Calculates the Population Stability Index (PSI) to see if the distribution of
    model scores has shifted.
    """
    def get_buckets(data):
        # Use quantiles to create buckets with roughly equal numbers of observations
        return pd.qcut(data, buckets, retbins=True, duplicates='drop')[1]

    # Use the expected (e.g., training/older) distribution to define buckets
    breakpoints = get_buckets(expected)
    expected_dist = pd.cut(expected, bins=breakpoints, include_lowest=True)
    actual_dist = pd.cut(actual, bins=breakpoints, include_lowest=True)

    expected_counts = expected_dist.value_counts(normalize=True)
    actual_counts = actual_dist.value_counts(normalize=True)

    # Replace zeros to avoid division by zero
    expected_counts = expected_counts.replace(0, 0.0001)
    actual_counts = actual_counts.replace(0, 0.0001)

    # Align indices to ensure we are comparing the same buckets
    all_buckets = expected_counts.index.union(actual_counts.index)
    expected_counts = expected_counts.reindex(all_buckets, fill_value=0.0001)
    actual_counts = actual_counts.reindex(all_buckets, fill_value=0.0001)

    psi_value = np.sum((actual_counts - expected_counts) * np.log(actual_counts / expected_counts))

    return psi_value

def main():
    """
    Main function to run the weekly metrics calculation job.
    """
    print("--- Starting Weekly Metrics Calculation Job ---")
    history_path = os.path.join(config.DATA_DIR, "forecast_history.parquet")
    metrics_path = os.path.join(config.DATA_DIR, "metrics.csv")
    retrain_flag_path = os.path.join(config.DATA_DIR, "RETRAIN_REQUIRED")

    if not os.path.exists(history_path):
        print(f"History file not found at {history_path}. Exiting.")
        return

    df = pd.read_parquet(history_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    # We need actual returns to calculate Sharpe Ratio. This requires knowing the outcome of the trade.
    # This part of the logic is missing from the current implementation.
    # For now, we will simulate it by assuming the expected_return was realized.
    # THIS IS A PLACEHOLDER AND SHOULD BE REPLACED WITH ACTUAL REALIZED RETURNS.
    df['realized_return'] = df['expected_return'] * np.random.choice([1, -0.5], size=len(df), p=[0.6, 0.4])

    # --- Calculate Metrics ---

    # 1. Walk-forward Sharpe Ratio (last 60 days)
    recent_trades = df[df['timestamp'] > (pd.Timestamp.now() - pd.Timedelta(days=60))]
    sr_60d = calculate_sharpe_ratio(recent_trades['realized_return'])

    # 2. Coverage (percentage of days with a signal)
    if not df.empty:
        trading_days = (df['timestamp'].max() - df['timestamp'].min()).days
        if trading_days > 0:
            coverage = df['timestamp'].dt.date.nunique() / trading_days
        else:
            coverage = 0.0
    else:
        coverage = 0.0

    # 3. PSI (on model confidence score)
    if len(df) > 20: # Need enough data for a meaningful split
        split_point = len(df) // 2
        reference_data = df.iloc[:split_point]['confidence_sigma']
        current_data = df.iloc[split_point:]['confidence_sigma']
        psi = calculate_psi(reference_data, current_data)
    else:
        psi = np.nan

    # --- Save Metrics ---
    new_metric = pd.DataFrame([{
        "date": pd.Timestamp.now().strftime('%Y-%m-%d'),
        "sharpe_ratio_60d": sr_60d,
        "coverage_pct": coverage * 100,
        "psi_confidence": psi
    }])

    if os.path.exists(metrics_path):
        metrics_df = pd.read_csv(metrics_path)
        metrics_df = pd.concat([metrics_df, new_metric], ignore_index=True)
    else:
        metrics_df = new_metric

    metrics_df.to_csv(metrics_path, index=False)
    print(f"Metrics saved to {metrics_path}")
    print(new_metric.to_string())

    # --- Check for Retraining ---
    if sr_60d < 0.5:
        print(f"Sharpe Ratio ({sr_60d:.2f}) is below 0.5. Creating retrain flag.")
        with open(retrain_flag_path, 'w') as f:
            f.write(f"Retraining required as of {pd.Timestamp.now()}")
    elif os.path.exists(retrain_flag_path):
        print("Sharpe Ratio is above threshold. Removing retrain flag.")
        os.remove(retrain_flag_path)

    print("\n--- Weekly Metrics Calculation Finished ---")

if __name__ == "__main__":
    main()
