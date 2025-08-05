import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
import os
import sys
import joblib
import pandas as pd

from src.data_loader import DataLoader
from src.predictor import Predictor
from src.visualizer import Visualizer
from src.reporter import Reporter
from src.signal_utils import generate_signals
from src import config

def _load_sigma_dict(ticker: str):
    """Loads the sigma dictionary for the given ticker."""
    metrics_path = os.path.join(config.DATA_DIR, f"metrics_{ticker}.pkl")
    if not os.path.exists(metrics_path):
        raise FileNotFoundError(f"Metrics file not found at {metrics_path}. Please run training first.")
    return joblib.load(metrics_path)

def _append_to_history(signals: list):
    """Appends a list of signals to the parquet history file."""
    history_path = os.path.join(config.DATA_DIR, "forecast_history.parquet")
    new_data = pd.DataFrame(signals)

    if os.path.exists(history_path):
        history_df = pd.read_parquet(history_path)
        combined_df = pd.concat([history_df, new_data], ignore_index=True)
    else:
        combined_df = new_data

    combined_df.to_parquet(history_path, index=False)
    print(f"Successfully wrote {len(signals)} signals to {history_path}")


async def main():
    """
    Main asynchronous function to run the daily update and reporting pipeline.
    """
    print("--- Starting Daily Forecast Update and Reporting ---")
    print(f"Processing tickers: {config.TICKERS}")

    data_loader = DataLoader()
    visualizer = Visualizer()
    reporter = Reporter()

    for ticker in config.TICKERS:
        print(f"\n=================================================")
        print(f"=== Processing ticker: {ticker}")
        print(f"=================================================")

        try:
            # 1. Load data
            print(f"\n[Step 1/5] Loading data for {ticker}...")
            data_df = data_loader.load_data(ticker)
            if data_df.empty:
                print(f"No data loaded for {ticker}. Skipping.")
                continue

            # 2. Generate new forecasts and returns
            print(f"\n[Step 2/5] Generating new forecasts for {ticker}...")
            predictor = Predictor(ticker=ticker)
            # The structure of `forecasts` is now {'model': {'forecast': Series, 'r_hat': Series}}
            forecasts_data = predictor.update_and_predict(full_data=data_df['Close'], n_periods=30)

            # 3. Generate Signals
            print(f"\n[Step 3/5] Generating signals for {ticker}...")
            sigma_dict = _load_sigma_dict(ticker)

            signals = generate_signals(
                ticker=ticker,
                forecasts=forecasts_data,
                sigma_dict=sigma_dict,
                vix_data=data_df['VIX_Close'],
                volume_data=data_df['ma30_volume']
            )

            # 4. Save signals to history and filter for reporting
            print(f"\n[Step 4/5] Saving signals and filtering for {ticker}...")
            if signals:
                _append_to_history(signals)

            signals_to_publish = signals
            if config.PUBLISH_LONG_ONLY:
                signals_to_publish = [s for s in signals if s['direction'] == 'Long' and s['expected_return'] > 0]
                print(f"Filtered for LONG positions only. Kept {len(signals_to_publish)} out of {len(signals)} signals.")

            # 5. Create visualization and send report
            print(f"\n[Step 5/5] Creating visualization and sending report for {ticker}...")
            # The visualizer needs the price forecasts, not the full forecast_data dict
            price_forecasts = {model: data['forecast'] for model, data in forecasts_data.items()}
            plot_path = visualizer.create_plot(
                ticker=ticker,
                historical_data=data_df['Close'],
                forecasts=price_forecasts
            )

            await reporter.send_report(
                ticker=ticker,
                signals=signals_to_publish,
                plot_path=plot_path
            )

            print(f"\nSuccessfully completed daily update for {ticker}.")

        except FileNotFoundError as e:
            print(f"SKIPPING {ticker}: Could not find required file. Please run the initial training script first. Details: {e}")
        except Exception as e:
            print(f"An unexpected error occurred while processing {ticker}. Details: {e}")

    print("\n--- Daily Forecast Update Finished ---")

if __name__ == "__main__":
    # Run the main async function
    asyncio.run(main())
