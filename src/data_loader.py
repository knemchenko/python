import os
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from src import config

class DataLoader:
    """
    Handles fetching and caching of financial data from yfinance.
    """

    def __init__(self):
        """
        Initializes the DataLoader, creating the data directory if it doesn't exist.
        """
        self.start_date = config.START_DATE
        self.data_dir = config.DATA_DIR
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

    def _get_cache_filepath(self, ticker: str) -> str:
        """
        Gets the file path for the cached data of a given ticker.
        """
        return os.path.join(self.data_dir, f"{ticker}.csv")

    def _fetch_history(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        """
        Fetches historical data for a ticker using the yf.Ticker object.
        This returns a cleaner dataframe than yf.download for a single ticker.
        """
        ticker_obj = yf.Ticker(ticker)
        # Use auto_adjust=True to get adjusted prices and simple column names
        df = ticker_obj.history(start=start, end=end, auto_adjust=True)
        return df

    def load_data(self, ticker: str) -> pd.DataFrame:
        """
        Loads data for a given ticker. It uses a local cache to avoid
        downloading all data every time. If cached data is found, it only
        fetches the newer data since the last record.

        Args:
            ticker (str): The ticker symbol to load data for (e.g., "AAPL").

        Returns:
            pd.DataFrame: A DataFrame containing the historical data with
                          'Date' as the index.
        """
        filepath = self._get_cache_filepath(ticker)
        today = datetime.now().strftime('%Y-%m-%d')

        df = None

        if os.path.exists(filepath):
            print(f"Loading cached data for {ticker} from {filepath}")
            df = pd.read_csv(filepath, index_col='Date', parse_dates=True)

            last_date = df.index.max()
            start_fetch_date = last_date + timedelta(days=1)

            if start_fetch_date.strftime('%Y-%m-%d') < today:
                print(f"Fetching new data for {ticker} from {start_fetch_date.strftime('%Y-%m-%d')} to {today}")
                new_data = self._fetch_history(ticker, start=start_fetch_date.strftime('%Y-%m-%d'), end=today)

                if not new_data.empty:
                    # Append new data and remove potential duplicates
                    df = pd.concat([df, new_data])
                    df = df[~df.index.duplicated(keep='last')]
            else:
                print(f"Data for {ticker} is already up to date.")

        else:
            print(f"No cached data found for {ticker}. Fetching all data from {self.start_date}.")
            df = self._fetch_history(ticker, start=self.start_date, end=today)

        if df is not None and not df.empty:
            # Drop columns that are not needed to keep the cache clean
            df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
            # Sort index just in case of concatenation issues
            df.sort_index(inplace=True)
            # Save the updated data back to cache
            df.to_csv(filepath, index_label='Date')
            print(f"Data for {ticker} saved to {filepath}")
        else:
            print(f"Could not download any data for {ticker}.")
            # Return an empty dataframe if nothing could be fetched
            return pd.DataFrame()

        return df
