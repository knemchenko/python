import sys
import os
import pandas as pd
import joblib
from tqdm import tqdm

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.data_loader import DataLoader
from src.predictor import Predictor
from src.signal_utils import generate_signals
from src import config


def _load_sigma_dict(ticker: str):
    """Loads the sigma dictionary for the given ticker."""
    metrics_path = os.path.join(config.DATA_DIR, f"metrics_{ticker}.pkl")
    if not os.path.exists(metrics_path):
        raise FileNotFoundError(
            f"Metrics file not found at {metrics_path}. Please run training first."
        )
    return joblib.load(metrics_path)


def main():
    """
    Main function to back-fill the forecast history.
    This is a one-time script to run to build up historical data for metrics
    calculation.
    """
    print("--- Starting Historical Forecast Back-fill ---")

    all_historical_signals = []
    data_loader = DataLoader()

    for ticker in config.TICKERS:
        print("\n=================================================")
        print(f"=== Back-filling ticker: {ticker}")
        print("=================================================")

        try:
            # 1. Load all available historical data
            full_data_df = data_loader.load_data(ticker)
            if len(full_data_df) < 200:  # Ensure we have enough data to backfill
                print(
                    f"Not enough data for {ticker} to backfill (need > 200 days). "
                    "Skipping."
                )
                continue

            # 2. Load the trained models and metrics
            # We use the same trained models throughout the backfill for consistency
            predictor = Predictor(ticker=ticker)
            sigma_dict = _load_sigma_dict(ticker)

            # 3. Iterate through a portion of the history to generate signals
            # We start from day 200 to ensure models have enough data to run.
            # We stop 30 days before the end to ensure we can generate 30-day
            # forecasts.
            start_index = 200
            end_index = len(full_data_df) - 30

            print(f"Iterating from day {start_index} to {end_index}...")
            for i in tqdm(range(start_index, end_index)):
                # This is the data available "on this day" in history
                historical_slice_df = full_data_df.iloc[:i]

                # Generate forecasts based on data up to this point
                # Note: This uses the pre-trained models and re-fits them on the
                # slice. This simulates the daily update process.
                forecasts_data = predictor.update_and_predict(
                    full_data=historical_slice_df["Close"], n_periods=30
                )

                # Generate signals
                signals = generate_signals(
                    ticker=ticker,
                    forecasts=forecasts_data,
                    sigma_dict=sigma_dict,
                    vix_data=historical_slice_df["VIX_Close"],
                )

                if signals:
                    # We need to manually set the timestamp to the "current day" of
                    # the backfill
                    current_day = historical_slice_df.index[-1]
                    for s in signals:
                        s["timestamp"] = current_day
                    all_historical_signals.extend(signals)

        except FileNotFoundError as e:
            print(
                f"SKIPPING {ticker}: Could not find required file. "
                f"Please run the initial training script first. Details: {e}"
            )
            continue
        except Exception as e:
            print(
                f"An unexpected error occurred while processing {ticker}. "
                f"Details: {e}"
            )
            continue

    # 4. Save all generated signals to the history file
    if all_historical_signals:
        history_path = os.path.join(config.DATA_DIR, "forecast_history.parquet")
        history_df = pd.DataFrame(all_historical_signals)
        history_df.to_parquet(history_path, index=False)
        print(
            f"\nSuccessfully back-filled and saved {len(all_historical_signals)} "
            f"signals to {history_path}"
        )
    else:
        print("\nNo historical signals were generated.")

    print("\n--- Historical Forecast Back-fill Finished ---")


if __name__ == "__main__":
    main()
