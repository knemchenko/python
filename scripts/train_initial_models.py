import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.data_loader import DataLoader
from src.trainer import Trainer
from src import config

def main():
    """
    Main function to run the initial model training pipeline.
    """
    print("--- Starting Initial Model Training and Selection ---")
    print(f"Processing tickers: {config.TICKERS}")

    data_loader = DataLoader()

    for ticker in config.TICKERS:
        print(f"\n=================================================")
        print(f"=== Processing ticker: {ticker}")
        print(f"=================================================")

        # 1. Load data
        print(f"\n[Step 1/2] Loading data for {ticker}...")
        try:
            data_df = data_loader.load_data(ticker)
            if data_df.empty:
                print(f"No data loaded for {ticker}. Skipping.")
                continue
            print(f"Data loaded successfully for {ticker}. Shape: {data_df.shape}")
        except Exception as e:
            print(f"Failed to load data for {ticker}. Error: {e}")
            continue

        # 2. Train, evaluate, and select models
        print(f"\n[Step 2/2] Training and selecting models for {ticker}...")
        try:
            trainer = Trainer(ticker=ticker, data=data_df)
            trainer.train_and_evaluate()
            trainer.select_and_save_best_models()
            print(f"Successfully completed training for {ticker}.")
        except Exception as e:
            print(f"An error occurred during the training process for {ticker}. Error: {e}")
            continue

    print("\n--- Initial Model Training Finished ---")

if __name__ == "__main__":
    main()
