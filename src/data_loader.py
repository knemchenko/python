import os
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from src import config
from src.features import FeatureEngineer

class DataLoader:
    """
    Handles fetching and caching of financial data from yfinance.
    """

    def __init__(self):
        """
        Initializes the DataLoader, creating the data directory if it doesn't exist.
        """
        self.start_date = config.DATA_SETTINGS["start_date"]
        self.prices_path = os.path.join(config.DATA_SETTINGS["data_dir"], config.DATA_SETTINGS["prices_path"])
        if not os.path.exists(self.prices_path):
            os.makedirs(self.prices_path)

    def _get_cache_filepath(self, ticker: str) -> str:
        """
        Gets the file path for the cached data of a given ticker.
        """
        return os.path.join(self.prices_path, f"{ticker}.parquet")

    def _fetch_history(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        """
        Fetches historical data for a ticker using the yf.Ticker object.
        This returns a cleaner dataframe than yf.download for a single ticker.
        """
        ticker_obj = yf.Ticker(ticker)
        # Use auto_adjust=True to get adjusted prices and simple column names
        df = ticker_obj.history(start=start, end=end, auto_adjust=True)
        return df

    def load_data(self, ticker: str, benchmark_ticker: str = None, load_benchmark: bool = False) -> pd.DataFrame:
        """
        Loads data for a given ticker, enriches it with features, and caches it.
        Can also load data for a benchmark ticker without adding features to it.

        Args:
            ticker (str): The primary ticker symbol to load.
            benchmark_ticker (str, optional): The benchmark ticker for beta calculation.
            load_benchmark (bool): If True, skips feature engineering. Used for loading benchmark data.

        Returns:
            pd.DataFrame: DataFrame with historical data and added features.
        """
        filepath = self._get_cache_filepath(ticker)
        today = datetime.now().strftime('%Y-%m-%d')

        df = None
        needs_update = True

        if os.path.exists(filepath):
            df = pd.read_parquet(filepath)
            last_date = df.index.max()
            if last_date.date() >= (datetime.now() - timedelta(days=1)).date():
                print(f"Data for {ticker} is already up-to-date.")
                needs_update = False

        if needs_update:
            print(f"Fetching or updating data for {ticker}...")
            full_history = self._fetch_history(ticker, start=self.start_date, end=today)

            if full_history.empty:
                print(f"Could not download any data for {ticker}.")
                return pd.DataFrame()

            # Only add features if it's the main asset, not a benchmark being loaded
            if not load_benchmark:
                benchmark_df = None
                if benchmark_ticker:
                    # Recursively load benchmark data, but without adding features to it
                    benchmark_df = self.load_data(benchmark_ticker, load_benchmark=True)

                # Add features
                feature_engineer = FeatureEngineer()
                df = feature_engineer.add_features(asset_df=full_history, benchmark_df=benchmark_df)
            else:
                df = full_history

            # Drop columns that are not needed to keep the cache clean
            # Note: FeatureEngineer adds columns in lowercase, so we select capitalized versions
            required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
            feature_cols = [col for col in df.columns if col not in required_cols]
            df = df[required_cols + feature_cols]

            df.sort_index(inplace=True)
            df.to_parquet(filepath)
            print(f"Data for {ticker} (with features) saved to {filepath}")

        return df
