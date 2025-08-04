import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.data_loader import DataLoader
from src.predictor import Predictor
from src.visualizer import Visualizer
from src.reporter import Reporter
from src import config

def main():
    """
    Main function to run the daily update and reporting pipeline.
    """
    print("--- Starting Daily Forecast Update and Reporting ---")
    print(f"Processing tickers: {config.TICKERS}")

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
            print(f"\n[Step 2/4] Generating new forecasts for {ticker}...")
            predictor = Predictor(ticker=ticker)
            forecasts = predictor.update_and_predict(full_data=data_df['Close'], n_periods=30)

            # 3. Create visualization
            print(f"\n[Step 3/4] Creating visualization for {ticker}...")
            plot_path = visualizer.create_plot(
                ticker=ticker,
                historical_data=data_df['Close'],
                forecasts=forecasts
            )

            # 4. Send report
            print(f"\n[Step 4/4] Sending report for {ticker}...")
            latest_price = data_df['Close'].iloc[-1]
            reporter.send_report(
                ticker=ticker,
                current_price=latest_price,
                forecasts=forecasts,
                plot_path=plot_path
            )

            print(f"\nSuccessfully completed daily update for {ticker}.")

        except FileNotFoundError as e:
            print(f"SKIPPING {ticker}: Could not find model file. Please run the initial training script first. Details: {e}")
        except Exception as e:
            print(f"An unexpected error occurred while processing {ticker}. Details: {e}")

    print("\n--- Daily Forecast Update Finished ---")

if __name__ == "__main__":
    main()
