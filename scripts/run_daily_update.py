import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import sys
import os
import asyncio

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.data_loader import DataLoader
from src.predictor import Predictor
from src.visualizer import Visualizer
from src.reporter import Reporter
from src.history_manager import HistoryManager
from src.evaluator import Evaluator
from src import config

async def main():
    """
    Main asynchronous function to run the daily update and reporting pipeline.
    """
    print("--- Starting Daily Forecast Update and Reporting ---")
    print(f"Processing tickers: {config.TICKERS}")

    # DEBUG: List files in data directory to check for persistence
    if os.path.exists(config.DATA_DIR):
        print(f"--- [DEBUG] Files in '{config.DATA_DIR}': {os.listdir(config.DATA_DIR)}")
    else:
        print(f"--- [DEBUG] Data directory '{config.DATA_DIR}' does not exist.")

    data_loader = DataLoader()
    visualizer = Visualizer()

    try:
        reporter = Reporter()
    except ValueError as e:
        print(f"Cannot initialize Reporter. Please check your Telegram configuration in src/config.py. Error: {e}")
        return

    for ticker in config.TICKERS:
        print(f"\n=================================================")
        print(f"=== Processing ticker: {ticker}")
        print(f"=================================================")

        try:
            # 1. Load data
            print(f"\n[Step 1/4] Loading data for {ticker}...")
            data_df = data_loader.load_data(ticker)
            if data_df.empty:
                print(f"No data loaded for {ticker}. Skipping.")
                continue

            # 2. Generate new forecasts
            print(f"\n[Step 2/5] Generating new forecasts for {ticker}...")
            predictor = Predictor(ticker=ticker)
            forecasts = predictor.update_and_predict(full_data=data_df['Close'], n_periods=30)

            # 3. Save the new forecasts to history
            print(f"\n[Step 3/6] Saving forecasts for {ticker}...")
            history_manager = HistoryManager(ticker=ticker)
            history_manager.save_forecasts(forecasts)

            # 4. Evaluate historical accuracy
            print(f"\n[Step 4/6] Evaluating historical accuracy for {ticker}...")
            evaluator = Evaluator(ticker=ticker, actual_data=data_df['Close'])
            accuracy_results = evaluator.calculate_accuracy()

            # 5. Create visualization
            print(f"\n[Step 5/6] Creating visualization for {ticker}...")
            forecast_history = history_manager.load_forecast_history()
            plot_path = visualizer.create_plot(
                ticker=ticker,
                historical_data=data_df['Close'],
                forecasts=forecasts,
                forecast_history=forecast_history
            )

            # 6. Send report
            print(f"\n[Step 6/6] Sending report for {ticker}...")
            latest_price = data_df['Close'].iloc[-1]
            await reporter.send_report(
                ticker=ticker,
                current_price=latest_price,
                forecasts=forecasts,
                accuracy_results=accuracy_results,
                plot_path=plot_path
            )

            print(f"\nSuccessfully completed daily update for {ticker}.")

        except FileNotFoundError as e:
            print(f"SKIPPING {ticker}: Could not find model file. Please run the initial training script first. Details: {e}")
        except Exception as e:
            print(f"An unexpected error occurred while processing {ticker}. Details: {e}")

    print("\n--- Daily Forecast Update Finished ---")

if __name__ == "__main__":
    # Run the main async function
    asyncio.run(main())
